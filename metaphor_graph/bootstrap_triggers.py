# -*- coding: utf-8 -*-
"""从 CCL2018 训练集自举触发词（方案 §9.1 自举回流的第一刀）。

动机（方案 §4.1.4 / §6.5 的核心矛盾）：
  种子本体的触发词是「动词型」（推进/攻击/沸腾…），对中文「X是Y / X像Y」式
  **名词喻体**（舞台/宝石/泥潭/太阳/酒…）覆盖极差 → 召回 <5%。
  直接接入 LLM 之前，先用真实标注数据把高频喻体词挖出来回填，是成本最低、
  且能立刻拉升召回的自举手段。

方法（两路互补，都以「字面安全」为硬约束）：
  A. 等比结构挖喻体（名词，高精度）：
      中文名词隐喻多为「X[是/像/如/似/般]Y」结构，喻体 Y 就在标记词旁。
      用 jieba 在标记词前/后抽取名词短语作为喻体候选。
  B. 动词喻体（从 label=1 动词隐喻句，按 lift 收紧）：
      动词本身就是喻体（沸腾/开花/撞击/淡化/深化…），用高 lift + 字面零出现约束。
  两路都强制 df_neu == 0（在训练集中性句里从没出现过）→ 回填后几乎不抬高 P1。
  落盘 bootstrap_triggers.json（可复现、可人工巡检），并 build_bootstrap_ontology()
  把词灌进 GENERIC_VEHICLE 通道的新 cascade。

运行：
  python -m metaphor_graph.bootstrap_triggers            # 挖词 + 落盘 + 自检
  （evaluate_real.py --use-bootstrap 会直接调用 build_bootstrap_ontology）
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph.ontology import (
    CascadeOntology, DEFAULT_ONTOLOGY, FrameSpec, CascadeSpec,
)
try:
    import jieba
    import jieba.posseg as posseg
    jieba.setLogLevel(60)
except ImportError:  # pragma: no cover
    raise SystemExit(
        "需要 jieba：请用 venv 运行 "
        "(.../versions/3.13.12/venv_jieba/Scripts/python.exe "
        "-m metaphor_graph.bootstrap_triggers)")

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_TRAIN = os.path.abspath(os.path.join(
    _HERE, "..", "data", "CCL2018-Chinese-Metaphor-Analysis",
    "dataset", "subtask1-metaphor-recognition", "train.xml"))
_OUT_JSON = os.path.join(_HERE, "bootstrap_triggers.json")

# 等比标记：标记后取喻体
_MARKERS_AFTER = ["就是", "便是", "成了", "变成", "成为", "当作", "好像",
                  "如同", "犹如", "宛如", "宛若", "好似", "好比", "像",
                  "是", "如", "似", "若"]
# 等比标记：标记前取喻体
_MARKERS_BEFORE = ["一样", "一般", "般", "似的"]
# 喻体前的功能词（跳过，不计入喻体）
_STOP_FUNC = {"个", "之", "一种", "一个", "的", "一", "那", "这", "了",
              "也", "都", "还", "便", "就", "和", "与", "对", "被", "把",
              "给", "让", "使", "上", "中", "里"}
# 动词喻体黑名单（lift 虽高但非隐喻动词，属噪声）
_VERB_NOISE = {"作为", "认为", "说话", "学习", "活动", "出来", "进行", "成为",
               "表现", "表示", "说明", "体现", "发挥", "起到", "具有", "存在"}

_NOUN_FLAG = ("n", "nz", "nt", "nn", "ni", "nl")
_VERB_FLAG = ("v", "vd", "vn", "vshi", "vyou")


# ---------------------------------------------------------------------------
# 解析 train.xml（正则，容忍裸 & 等脏数据）
# ---------------------------------------------------------------------------
def parse_train_xml(path: str = _DEFAULT_TRAIN) -> List[Tuple[str, int]]:
    """返回 [(sentence, label), ...]，label: 0=中性 1=动词隐喻 2=名词隐喻。"""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"未找到 train.xml，请先运行 download_datasets.py。期望: {path}")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = []
    block = re.compile(r"<metaphor>(.*?)</metaphor>", re.S)
    sent_re = re.compile(r"<Sentence>(.*?)</Sentence>", re.S)
    lab_re = re.compile(r"<Label>(.*?)</Label>", re.S)
    for b in block.finditer(text):
        body = b.group(1)
        m_sent = sent_re.search(body)
        m_lab = lab_re.search(body)
        if not m_sent or not m_lab:
            continue
        sent = m_sent.group(1).strip()
        lab_raw = m_lab.group(1).strip()
        if not sent or not lab_raw:
            continue
        try:
            lab = int(lab_raw)
        except ValueError:
            continue
        if lab not in (0, 1, 2):
            continue
        out.append((sent, lab))
    return out


# ---------------------------------------------------------------------------
# A. 等比结构挖喻体（名词）
# ---------------------------------------------------------------------------
def _vehicle_after(sent: str, pos: int) -> Optional[str]:
    """标记后取名词短语（跳过前导功能词），返回原始词面拼接。"""
    sub = sent[pos:]
    veh = []
    started = False
    for w in posseg.cut(sub):
        if w.word in _STOP_FUNC and not started:
            continue
        if w.flag.startswith(_NOUN_FLAG):
            started = True
            veh.append(w.word)
            if len(veh) >= 3:
                break
        else:
            if started:
                break
    return "".join(veh) if veh else None


def _vehicle_before(sent: str, pos: int) -> Optional[str]:
    """标记前取 1-2 个名词，返回原始词面拼接。"""
    sub = sent[:pos]
    veh = []
    for w in reversed(list(posseg.cut(sub))):
        if w.flag.startswith(_NOUN_FLAG):
            veh.insert(0, w.word)
            if len(veh) >= 2:
                break
        else:
            break
    return "".join(veh) if veh else None


def extract_equative_pattern(sent: str) -> Optional[str]:
    """从等比句抽取「标记+喻体」模式串（如 是舞台 / 像棉花糖 / 若太阳 / 花般）。

    关键设计：触发词用 *模式串* 而非裸名词。字面句「我在舞台上」不含「是舞台」
    「像棉花糖」，因此不会误触 —— 这是把 P1 字面误判率压回硬门槛的核心手段。
    """
    # 先试「标记前」（般/一样/一般/似的）：模式 = 喻体 + 标记
    for mk in _MARKERS_BEFORE:
        i = sent.find(mk)
        if i >= 0:
            v = _vehicle_before(sent, i)
            if v:
                return v + mk
    # 再试「标记后」，长标记优先（避免 "是" 误命中 "也是/可是"）
    for mk in sorted(_MARKERS_AFTER, key=len, reverse=True):
        i = sent.find(mk)
        if i >= 0:
            v = _vehicle_after(sent, i + len(mk))
            if v:
                return mk + v
    return None


# ---------------------------------------------------------------------------
# B. 动词喻体（lift 收紧）
# ---------------------------------------------------------------------------
def _verb_candidates(sent: str):
    for w in posseg.cut(sent):
        if w.flag.startswith(_VERB_FLAG) and len(w.word) >= 2:
            yield w.word


# ---------------------------------------------------------------------------
# 主挖掘
# ---------------------------------------------------------------------------
def mine_triggers(path: str = _DEFAULT_TRAIN,
                  min_df: int = 3,
                  min_lift: float = 3.0,
                  include_verbs: bool = False,
                  out_json: str = _OUT_JSON) -> dict:
    """挖喻体名词(等比模式串)，按 lift(隐喻主导度)软过滤，落盘 JSON。

    字面保护改用 *lift* 而非 df_neu==0 硬约束：一个模式只要「在隐喻句里极常见、
    在字面句里极罕见」(高 lift) 就保留。这样既不至于像裸名词那样全量误触(P1 爆炸)，
    也不至于像 df_neu==0 那样误杀大量好喻体(召回崩溃)。

    include_verbs：动词喻体无等比标记、裸词字面风险高，默认关闭（方案 §9.1
    自举回流也明确只回填「喻体名词」）。开启需自行承担 P1 抬升。
    """
    samples = parse_train_xml(path)
    met_sents = [s for s, l in samples if l in (1, 2)]
    neu_sents = [s for s, l in samples if l == 0]
    n_met, n_neu = len(met_sents), len(neu_sents)

    # --- 名词喻体：等比结构 → 模式串触发词 ---
    noun_met: Dict[str, int] = defaultdict(int)
    noun_neu: Dict[str, int] = defaultdict(int)
    for s in met_sents:
        v = extract_equative_pattern(s)
        if v:
            noun_met[v] += 1
    for s in neu_sents:
        v = extract_equative_pattern(s)
        if v:
            noun_neu[v] += 1

    eps = 1e-9
    noun_rows, verb_rows = [], []
    for w, dm in noun_met.items():
        dn = noun_neu.get(w, 0)
        if dm < min_df:
            continue
        lift = (dm / (n_met + eps)) / ((dn / (n_neu + eps)) + eps)
        if lift < min_lift:
            continue
        noun_rows.append(dict(word=w, df_met=dm, df_neu=dn, lift=round(lift, 1)))

    if include_verbs:
        vmet: Dict[str, int] = defaultdict(int)
        vneu: Dict[str, int] = defaultdict(int)
        lab1 = [s for s, l in samples if l == 1]
        for s in lab1:
            for w in set(_verb_candidates(s)):
                vmet[w] += 1
        for s in neu_sents:
            for w in set(_verb_candidates(s)):
                vneu[w] += 1
        for w, dm in vmet.items():
            dn = vneu.get(w, 0)
            if w in _VERB_NOISE or dm < min_df or dn > 0:
                continue
            lift = (dm / (n_met + eps)) / (dn / (n_neu + eps) + eps)
            if lift < 20:
                continue
            verb_rows.append(dict(word=w, df_met=dm, df_neu=dn, lift=round(lift, 1)))

    noun_rows.sort(key=lambda r: -r["df_met"])
    verb_rows.sort(key=lambda r: -r["df_met"])
    noun_vehicles = [r["word"] for r in noun_rows]
    verb_vehicles = [r["word"] for r in verb_rows]

    result = dict(
        source=os.path.basename(path),
        n_met=n_met, n_neu=n_neu,
        min_df=min_df, literal_constraint="df_neu==0",
        n_noun=len(noun_vehicles), n_verb=len(verb_vehicles),
        noun_vehicles=noun_vehicles,
        verb_vehicles=verb_vehicles,
        noun_rows=noun_rows,
        verb_rows=verb_rows,
    )
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def build_bootstrap_ontology(base: Optional[CascadeOntology] = None,
                             json_path: str = _OUT_JSON,
                             top_k: Optional[int] = None,
                             min_lift: Optional[float] = None) -> CascadeOntology:
    """把自举喻体词灌进新 cascade，叠加到 base 本体。

    top_k：每类最多取前 top_k。min_lift：若给定则按该 lift 阈值现场重挖
    （用于扫描 P1/召回甜点），否则读已落盘的 json。
    """
    if base is None:
        base = DEFAULT_ONTOLOGY
    if min_lift is not None:
        data = mine_triggers(min_lift=min_lift)
    elif os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = mine_triggers()

    noun = data["noun_vehicles"]
    verb = data["verb_vehicles"]
    if top_k:
        noun, verb = noun[:top_k], verb[:top_k]

    frames = copy.deepcopy(base.frames)
    cascades = copy.deepcopy(base.cascades)

    if noun:
        frames["F_BOOTSTRAP_NOUN"] = FrameSpec(
            "F_BOOTSTRAP_NOUN", "GENERIC_VEHICLE_NOUN", "GENERIC_VEHICLE_MAP",
            source_domain="自举名词喻体", target_domain="自举目标域",
            ground=[], triggers=noun,
            source_type="GENERIC_VEHICLE",
            source_frame="Vehicle", target_frame="Target")
    if verb:
        frames["F_BOOTSTRAP_VERB"] = FrameSpec(
            "F_BOOTSTRAP_VERB", "GENERIC_VEHICLE_VERB", "GENERIC_VEHICLE_MAP",
            source_domain="自举动词喻体", target_domain="自举目标域",
            ground=[], triggers=verb,
            source_type="GENERIC_VEHICLE",
            source_frame="Vehicle", target_frame="Target")

    members = [fid for fid in ("F_BOOTSTRAP_NOUN", "F_BOOTSTRAP_VERB") if fid in frames]
    cascades["C_BOOTSTRAP"] = CascadeSpec(
        "C_BOOTSTRAP", "GENERIC_VEHICLE_BOOTSTRAP",
        member_frames=members,
        discourse_domains=["自举语料"],
        typical_triggers=(noun + verb)[:10])

    return CascadeOntology(frames=frames, cascades=cascades)


def _self_check():
    r = mine_triggers()
    print(f"训练集: 隐喻句 {r['n_met']} / 中性句 {r['n_neu']}  "
          f"(字面硬约束: {r['literal_constraint']})")
    print(f"自举候选: 名词喻体 {r['n_noun']} / 动词喻体 {r['n_verb']}")
    print(f"落盘: {_OUT_JSON}")
    print("\nTop 25 名词喻体模式串(等比结构, 按语料频次):")
    print("  " + "  ".join(r["noun_vehicles"][:25]))
    print("\nTop 25 动词喻体(按语料频次):")
    print("  " + "  ".join(r["verb_vehicles"][:25]))
    print("\n构建自举本体 ...")
    ont = build_bootstrap_ontology()
    print("  ", ont.stats())


if __name__ == "__main__":
    _self_check()
