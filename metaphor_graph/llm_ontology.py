# -*- coding: utf-8 -*-
"""LLM 驱动的本体自举回流（方案 §5.2 风险缓解 / §八 P0 收官）。

**为什么需要它**
- P0 的验收标准是「种子 ≥300 个框架」，而现有人肉+MetaNet 迁移本体只有 31 个 —— 差 10 倍。
- 更紧迫的是：接上 LLM 后发现大量超边挂在临时框架 `F_LLM_xxxx` 上（喻体是模型临时造的），
  这些框架不属于任何级联，直接把 **P2 的 L2/L3 覆盖率（门槛 >85%）打穿**。

**闭环价值（省钱的那一半）**
LLM 每次调用都在「临时造框架」，是一次性的。本模块把模型见到过的
(源域, 目标域, 喻体词) 沉淀成**正式框架与触发词**写回本体。之后同样的隐喻
由**免费的触发词通道**命中，不必再问模型 —— 一次付费，长期免费用。

流程：
    缓存的 LLM 候选
      → 收集 (源域, 目标域) 及其喻体词
      → LLM 把杂乱表述归并成规范域标签（"水流漩涡"/"漩涡" → "水流"）
      → 按 (规范源域, 规范目标域) 聚合成框架，按目标域打包成级联
      → 落盘 JSON + build_llm_ontology() 载入 CascadeOntology

运行：
    python -m metaphor_graph.llm_ontology --cache data/llm_cache_deepseek.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

from .llm_backend import (  # noqa: E402
    LLMCandidate, OpenAIBackend, load_table, batch_discover, _parse_json_blob)
from .ontology import (  # noqa: E402
    CascadeOntology, CascadeSpec, FrameSpec, TYPE_CONSTRAINTS, infer_source_type)

DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "llm_cache_deepseek.json")
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "llm_ontology.json")

# 归并提示：模型给的域描述很杂（"水流漩涡"/"漩涡(水流)"/"漩涡"），
# 必须归一才能聚成框架，否则同一个概念隐喻会被拆成几十个框架。
_CANON_SYSTEM = (
    "你是认知语言学专家。下面是从中文语料里抽出的隐喻域描述，表述很杂："
    "有的带修饰语、有的是同义改写、有的过细。请把它们归并到**最少数量**的"
    "规范域标签上。规范标签须是 1–4 个汉字的通用概念域（如 水流/建筑/舞台/战争/机器/人体）。"
)
_CANON_USER = (
    "待归并的域描述（共 {n} 个）：\n{body}\n"
    "只输出一个 JSON 对象，键是**原样照抄**的域描述，值是归并后的规范标签，形如：\n"
    '{{"水流漩涡": "水流", "漩涡": "水流", "建筑结构中的承重柱": "建筑"}}\n'
    "键必须齐全、不能遗漏；值必须是 1–4 个汉字。不要输出任何说明文字，只输出 JSON。"
)


def _stable_id(prefix: str, *parts: str) -> str:
    """稳定 id：同样的输入永远得到同样的 id（本体是长期资产，id 必须可复现）。"""
    h = hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


# ---------------------------------------------------------------------------
# 1) 从缓存候选中收集 (源域, 目标域) 及其喻体
# ---------------------------------------------------------------------------
def collect_pairs(table: Dict[str, List[LLMCandidate]],
                  min_conf: float = 0.85) -> Dict[Tuple[str, str], dict]:
    """聚合成 {(源域, 目标域): {count, triggers, grounds}}。

    min_conf 默认 0.85 —— 与 §6.7 实测的达标阈值一致：只用高置信候选建本体，
    避免把模型的字面误判固化进本体（那会污染下游所有实验）。
    """
    agg: Dict[Tuple[str, str], dict] = {}
    for _text, cands in table.items():
        for c in cands:
            if c.confidence < min_conf:
                continue
            key = (c.source_domain.strip(), c.target_domain.strip())
            if not key[0] or not key[1]:
                continue
            rec = agg.setdefault(key, {"count": 0, "triggers": defaultdict(int),
                                       "grounds": defaultdict(int)})
            rec["count"] += 1
            for t in c.triggers:
                rec["triggers"][t] += 1
            for g in c.ground:
                rec["grounds"][g] += 1
    return agg


def _canonicalize(backend, values: List[str], batch_size: int = 60) -> Dict[str, str]:
    """把杂乱的域描述归并成规范标签；失败时原样返回（保证流程不中断）。"""
    mapping: Dict[str, str] = {}
    for i in range(0, len(values), batch_size):
        part = values[i:i + batch_size]
        body = "\n".join(f"- {v}" for v in part)
        # 直接调用后端的 _chat（各厂商一致）；没有则退化为原样返回
        chat = getattr(backend, "_chat", None)
        if chat is None:
            return {v: v for v in values}
        parsed = chat(_CANON_SYSTEM, _CANON_USER.format(n=len(part), body=body))
        if not isinstance(parsed, dict):
            continue
        for v in part:
            lab = parsed.get(v)
            mapping[v] = str(lab).strip() if isinstance(lab, str) and lab.strip() else v
    for v in values:  # 兜底：确保每个输入都有映射
        mapping.setdefault(v, v)

    # 归并率自检：恒等映射意味着**归并未生效**（LLM 调用失败/被降级），
    # 这种失败是静默的 —— 流程会一路"成功"，但框架会碎成上千个各不相同的域。
    # 本次就是这么踩的：账户欠费 402 被吞成空结果，1927 个源域 0 归并。
    if values:
        merged = len(set(mapping[v] for v in values))
        if merged >= len(values) * 0.95:
            logger.error(
                "域归并未生效：%d 个域描述归并后仍有 %d 种（恒等映射）。"
                "通常是 LLM 调用失败被静默降级 —— 请检查后端状态（如余额）后重跑，"
                "否则本体将严重碎片化。", len(values), merged)
        else:
            logger.info("域归并：%d → %d 种", len(values), merged)
    return mapping


# ---------------------------------------------------------------------------
# 2) 生成框架与级联
# ---------------------------------------------------------------------------
def _filter_triggers(merged: Dict[Tuple[str, str], dict],
                     min_len: int = 2,
                     max_pairs: int = 3) -> Dict[str, set]:
    """剔掉「泛用触发词」，返回被剔除的词集合。

    为什么必须做：LLM 给的触发词里混着大量单字通用词（进/爬/钻/河/火）。
    它们几乎出现在任何句子里 —— 实测把自举本体接到**纯规则通道**上时，
    P1 直接飙到 **81.6%**（门槛 15%）。触发词一旦写进本体就是长期资产，
    宁可少收也不能收进噪声。

    判据：① 长度 < min_len（中文单字信息量太低）；
          ② 出现在超过 max_pairs 个不同框架里（过度多义，区分度为零）。
    """
    spreads: Dict[str, set] = defaultdict(set)
    for key, rec in merged.items():
        for t in rec["triggers"]:
            spreads[t].add(key)
    dropped = {t for t, keys in spreads.items()
               if len(t) < min_len or len(keys) > max_pairs}
    return dropped


def build_specs(agg: Dict[Tuple[str, str], dict],
                backend=None,
                min_count: int = 1,
                max_triggers: int = 8,
                canon: Optional[dict] = None,
                min_trigger_len: int = 2,
                max_trigger_spread: int = 3) -> Tuple[List[FrameSpec], List[CascadeSpec], dict]:
    """把 (源域,目标域) 聚合成 FrameSpec / CascadeSpec。

    级联按**目标域**打包 —— 这与 cascade 理论一致：一个级联是围绕同一目标概念
    组织起来的、共同出现的映射集合（如「时间」目标域下 TIME_IS_MONEY / TIME_IS_RESOURCE）。
    """
    if canon and canon.get("sources") and canon.get("targets"):
        src_map, tgt_map = dict(canon["sources"]), dict(canon["targets"])
    elif backend is not None:
        sources = sorted({s for s, _ in agg})
        targets = sorted({t for _, t in agg})
        src_map = _canonicalize(backend, sources)
        tgt_map = _canonicalize(backend, targets)
    else:
        src_map = {s: s for s, _ in agg}
        tgt_map = {t: t for _, t in agg}

    # 归一化后再聚合（不同表述归并到同一框架）
    merged: Dict[Tuple[str, str], dict] = {}
    for (s, t), rec in agg.items():
        key = (src_map.get(s, s), tgt_map.get(t, t))
        m = merged.setdefault(key, {"count": 0, "triggers": defaultdict(int),
                                    "grounds": defaultdict(int)})
        m["count"] += rec["count"]
        for k, v in rec["triggers"].items():
            m["triggers"][k] += v
        for k, v in rec["grounds"].items():
            m["grounds"][k] += v

    dropped = _filter_triggers(merged, min_trigger_len, max_trigger_spread)

    frames: List[FrameSpec] = []
    by_target: Dict[str, List[str]] = defaultdict(list)
    for (s, t), rec in merged.items():
        if rec["count"] < min_count:
            continue
        fid = _stable_id("F_LLM", s, t)
        triggers = [w for w, _ in sorted(rec["triggers"].items(),
                                         key=lambda x: -x[1])
                    if w not in dropped][:max_triggers]
        grounds = [w for w, _ in sorted(rec["grounds"].items(),
                                        key=lambda x: -x[1])[:max_triggers]]
        # 推断真实 source_type（此前一律 GENERIC_VEHICLE，会让类型约束完全失效）
        stype = infer_source_type(s)
        # 映射类型：用「源域→目标域」的规范化形式，而不是笼统的 GENERIC_VEHICLE_MAP。
        # 这样每个框架的映射是可区分的，类型约束才有信息量。
        mtype = ("GENERIC_VEHICLE_MAP" if stype == "GENERIC_VEHICLE"
                 else f"DISCOVERED::{stype}_TO_{t}")
        frames.append(FrameSpec(
            id=fid,
            name=f"LLM::{s}_IS_{t}",
            mapping_type=mtype,
            source_domain=s,
            target_domain=t,
            ground=grounds,
            triggers=triggers,
            source_type=stype,
        ))
        by_target[t].append(fid)

    cascades: List[CascadeSpec] = []
    for t, fids in by_target.items():
        cascades.append(CascadeSpec(
            id=_stable_id("C_LLM", t),
            name=f"LLM_TARGET::{t}",
            member_frames=sorted(fids),
            discourse_domains=[t],
            typical_triggers=[],
        ))
    return frames, cascades, {"sources": src_map, "targets": tgt_map,
                              "dropped_triggers": sorted(dropped)}


# ---------------------------------------------------------------------------
# 3) 落盘与载入
# ---------------------------------------------------------------------------
def filter_triggers_by_lift(frames: List[FrameSpec],
                            train_path: Optional[str] = None,
                            min_lift: float = 3.0,
                            min_df: int = 2) -> Tuple[List[FrameSpec], dict]:
    """用 **train.xml 标注**按 lift 过滤触发词（与 bootstrap_triggers 同一套纪律）。

    为什么要它：LLM 给的触发词是「它在隐喻句里见过的词」，但同一个词在字面句里
    也常见（低头/弯腰/火花）。实测不过滤就把自举本体接到纯规则通道时，
    **P1 飙到 60.5%**（门槛 15%）—— 自举反而毁掉了规则侧。

    lift = (该词在隐喻句中的文档频率) / (该词在字面句中的文档频率)，
    沿用 bootstrap_triggers 的 min_lift=3.0 口径。

    必须只吃 train.xml：**用测试集标注来挑触发词属于标签泄漏**，
    本体是长期资产，构建阶段绝不能碰测试集。

    注意：触发词被清空也**保留框架** —— 框架仍承担「LLM 候选归位 → 挂上 L3 级联」
    的职责（P2 覆盖率需要它），只是不再驱动免费的触发词通道。
    """
    from .bootstrap_triggers import parse_train_xml
    from collections import Counter

    # 注意：不能把 None 传进去，会覆盖 parse_train_xml 的默认路径
    samples = parse_train_xml(train_path) if train_path else parse_train_xml()
    n_met = sum(1 for _t, y in samples if y)
    n_neu = max(1, len(samples) - n_met)

    vocab = sorted({w for f in frames for w in f.triggers})
    df_met: Counter = Counter()
    df_neu: Counter = Counter()
    for text, y in samples:
        for w in vocab:
            if w in text:
                (df_met if y else df_neu)[w] += 1

    eps = 1e-9
    keep, dropped = set(), {}
    for w in vocab:
        lift = (df_met[w] / (n_met + eps)) / (df_neu[w] / (n_neu + eps) + eps)
        if df_met[w] >= min_df and lift >= min_lift:
            keep.add(w)
        else:
            dropped[w] = {"df_met": df_met[w], "df_neu": df_neu[w],
                          "lift": round(lift, 2)}

    out = []
    for f in frames:
        out.append(FrameSpec(
            id=f.id, name=f.name, mapping_type=f.mapping_type,
            source_domain=f.source_domain, target_domain=f.target_domain,
            ground=list(f.ground),
            triggers=[w for w in f.triggers if w in keep],
            source_type=f.source_type,
        ))
    stats = {"n_vocab": len(vocab), "n_keep": len(keep), "n_drop": len(dropped),
             "train_sentences": len(samples), "min_lift": min_lift,
             "dropped_sample": sorted(dropped, key=lambda w: -dropped[w]["df_neu"])[:8]}
    return out, stats


def save_specs(frames: List[FrameSpec], cascades: List[CascadeSpec], path: str,
               canon: Optional[dict] = None):
    import dataclasses
    payload = {
        "frames": [dataclasses.asdict(f) for f in frames],
        "cascades": [dataclasses.asdict(c) for c in cascades],
        # 归并映射一并落盘：重建本体时可复用，不必再问一次模型
        "canon": canon or {},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)


def load_canon(path: str = DEFAULT_OUT) -> dict:
    """读取已落盘的归并映射（重建时省掉一次 LLM 归并）。

    只接受**真的发生了归并**的映射：如果 value 与 key 一一相等（恒等映射，
    通常是上一轮没设 LLM_API_KEY 而退化写入的），复用它会让后续重建永远
    不做归并，必须丢弃。
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        canon = json.load(f).get("canon") or {}
    if not canon.get("sources"):
        return {}
    src = canon["sources"]
    merged = len(set(src.values())) < len(src)
    if not merged:
        return {}
    return canon


def build_llm_ontology(path: str = DEFAULT_OUT,
                       base: Optional[CascadeOntology] = None) -> CascadeOntology:
    """把落盘的框架/级联并入本体（base 默认用现有默认本体）。"""
    from .ontology import DEFAULT_ONTOLOGY
    ont = CascadeOntology(
        frames=dict((base or DEFAULT_ONTOLOGY).frames),
        cascades=dict((base or DEFAULT_ONTOLOGY).cascades),
    )
    if not os.path.exists(path):
        return ont
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    for fd in payload.get("frames", []):
        spec = FrameSpec(**fd)
        # 把自举发现的映射类型**登记进类型系统**。
        # 不做这一步的话，新建的 DISCOVERED::* 映射不在 TYPE_CONSTRAINTS 里，
        # 会被 type_valid 全判非法 —— 整个自举本体都失效。
        # 这也点出了开放发现与封闭类型系统的本质张力：
        # 每接受一个新映射，就必须扩充一次类型系统（见 README §7.1 A1）。
        TYPE_CONSTRAINTS.setdefault(spec.source_type, [])
        if spec.mapping_type not in TYPE_CONSTRAINTS[spec.source_type]:
            TYPE_CONSTRAINTS[spec.source_type].append(spec.mapping_type)
        ont.frames.setdefault(spec.id, spec)
    for cd in payload.get("cascades", []):
        spec = CascadeSpec(**cd)
        ont.cascades.setdefault(spec.id, spec)
    # 重建反向索引（本体构造时建过一次，新增条目后需要重算）
    ont._trigger_index = {}
    for fid, f in ont.frames.items():
        for t in f.triggers:
            ont._trigger_index.setdefault(t, []).append(fid)
    ont._frame_to_cascade = {}
    for cid, c in ont.cascades.items():
        for fid in c.member_frames:
            ont._frame_to_cascade[fid] = cid
    return ont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("cache", "train"), default="train",
                    help="本体语料来源。**train（默认）= 规范做法**：只用 train.xml 的隐喻句"
                         "建本体，再在测试集评估，避免语料重叠（本体是长期资产，"
                         "用测试集建的话所有 P0/P2 数字都不可claim）。"
                         "cache = 用测试集的 LLM 预取缓存建（仅作对照，勿用于对外结论）。")
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="LLM 预取缓存（--source cache 时用）")
    ap.add_argument("--train-cache",
                    default=os.path.join(os.path.dirname(DEFAULT_CACHE),
                                         "llm_cache_train.json"),
                    help="训练集预取缓存（--source train 时用）")
    ap.add_argument("--batch", type=int, default=20, help="批量大小")
    ap.add_argument("--timeout", type=float, default=90.0,
                    help="单次请求超时秒数。默认 20s 在批量场景会**静默丢批**"
                         "（超时被优雅降级成空结果），故这里默认放宽到 90s。")
    ap.add_argument("--out", default=DEFAULT_OUT, help="本体落盘路径")
    ap.add_argument("--min-count", type=int, default=1,
                    help="聚合次数下限（调高=更精，调低=更多框架）")
    ap.add_argument("--min-conf", type=float, default=0.85,
                    help="建本体所用候选的最低置信度（对齐 §6.7 达标阈值）")
    ap.add_argument("--no-canonicalize", action="store_true",
                    help="跳过 LLM 归并（离线可跑，但框架数会虚高）")
    ap.add_argument("--min-lift", type=float, default=3.0,
                    help="触发词 lift 下限（用 train.xml 标注算，口径同 bootstrap_triggers）。"
                         "设 0 关闭该过滤 —— 但实测会让纯规则通道 P1 飙到 60%。")
    ap.add_argument("--min-df", type=int, default=2,
                    help="触发词在训练集隐喻句中的最少出现次数")
    args = ap.parse_args()

    if args.source == "train":
        from .bootstrap_triggers import parse_train_xml
        train = parse_train_xml()
        # 只用**标注为隐喻**的训练句建本体：本体是隐喻知识库，
        # 掺入字面句只会把字面用法也固化进框架。
        texts = [t for t, y in train if y]
        print(f"源=train.xml：{len(train)} 句，其中隐喻句 {len(texts)} 句用于建本体")
        backend0 = OpenAIBackend(
            timeout=args.timeout,
            extra_body=({"thinking": {"type": "disabled"}}
                        if os.environ.get("LLM_MODEL", "").startswith("deepseek")
                        else None))
        table = batch_discover(backend0, texts, batch_size=args.batch,
                               cache_path=args.train_cache)
    else:
        if not os.path.exists(args.cache):
            print(f"找不到缓存 {args.cache}。先跑：\n"
                  f"  python -m metaphor_graph.evaluate_real --use-llm --llm-batch 20 "
                  f"--llm-cache {args.cache}")
            return 1
        print("源=测试集缓存 ⚠️ 存在语料重叠，仅作对照，勿用于对外结论")
        table = load_table(args.cache)

    agg = collect_pairs(table, min_conf=args.min_conf)
    print(f"高置信(≥{args.min_conf})候选聚合出 {len(agg)} 个 (源域,目标域) 组合")

    # 归并映射优先复用上一轮落盘的，避免重复付费
    canon = load_canon(args.out) if not args.no_canonicalize else {}
    backend = None
    if canon and not args.no_canonicalize:
        print("复用已落盘的域归并映射（0 次 LLM 调用）")
    elif not args.no_canonicalize and os.environ.get("LLM_API_KEY"):
        backend = OpenAIBackend(
            extra_body=({"thinking": {"type": "disabled"}}
                        if os.environ.get("LLM_MODEL", "").startswith("deepseek")
                        else None))
        print("用 LLM 归并杂乱域描述…")
    else:
        print("跳过 LLM 归并（未设 LLM_API_KEY 或显式关闭）")

    frames, cascades, canon = build_specs(
        agg, backend=backend, min_count=args.min_count, canon=canon or None)

    dropped_generic = canon.get("dropped_triggers", [])
    n_before = sum(len(f.triggers) for f in frames)

    # 用 train.xml 标注按 lift 收口：这是自举能否真正赋能规则侧的关键一步
    if args.min_lift > 0:
        frames, lift_stats = filter_triggers_by_lift(
            frames, min_lift=args.min_lift, min_df=args.min_df)
        n_after = sum(len(f.triggers) for f in frames)
        print(f"触发词：泛用剔除后 {n_before} → lift≥{args.min_lift} 过滤后 {n_after}"
              f"（训练集 {lift_stats['train_sentences']} 句）")
        print(f"  剔除示例（字面句里也常见）: {lift_stats['dropped_sample'][:6]}")
    else:
        print(f"触发词：保留 {n_before} 个（已跳过 lift 过滤）")
        lift_stats = {}

    save_specs(frames, cascades, args.out, canon)
    if drop_note := dropped_generic[:6]:
        print(f"  另剔除 {len(dropped_generic)} 个泛用词（长度/多义）: {drop_note}")

    print(f"\n生成框架 {len(frames)} 个 / 级联 {len(cascades)} 个 → {args.out}")
    print(f"P0 验收「种子 ≥300 框架」: "
          f"{'✅ 达标' if len(frames) >= 300 else f'❌ 差 {300 - len(frames)} 个'}")
    print("\n规模最大的 10 个框架：")
    for f in sorted(frames, key=lambda x: -len(x.triggers))[:10]:
        print(f"  {f.name:40s} 触发词={f.triggers[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
