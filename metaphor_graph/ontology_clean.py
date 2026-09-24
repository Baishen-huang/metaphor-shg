# -*- coding: utf-8 -*-
"""自举本体清洗（P0 收官 → 生产级默认本体，路线图 §8.2 P1 项）。

**为什么需要它**
`llm_ontology_train.json` 的 2185 个框架是 LLM 从 train.xml 一次性沉淀的原始产物，
README §8.1 明确指出它「来自 cache，需清洗去重后沉淀为生产默认本体」。探查发现
三类可度量的质量问题：

  1. **自环框架**（source_domain == target_domain，如「束缚→束缚」）——
     模型没找到真正的跨域映射，把目标词原样抄进了源域。这种框架挂进 L2/L3
     是纯噪声：级联「围绕同一目标概念组织映射」的语义对它不成立。
  2. **喻底被明喻标记污染**——模型的 ground 字段里混着「如/像/似/般」等
     比较词本身（如「海洋→爱」ground=["如","海洋"]）。喻底是超边的 n 元端点
     （方案 §1.1），比较词不是喻底内容，会污染 extended.py 的喻底交集判据
     与 retrieval 的 sem/ground 信号。
  3. **支持度无分层**——86% 的框架只被 1 个候选支持（count==1），而 count≥2
     的只有 301 个。单例框架并非全删：它们承担「模糊匹配锚点 → L2/L3 归属」
     的职责（P2 覆盖率），删了会掉覆盖率；但它们从未被二次验证，不应与
     高支持度框架平权。故按支持度打 **tier 标签**（core / longtail），生产
     默认两级都载入（保覆盖），core-only 模式供消融对照。

**刻意不做的规则（探查后否决，防止过清洗）**
  - 「源域出现在自己的 triggers/ground 里 → 删」：探查发现这是**名词隐喻的
    正常形态**——名词喻体本身就是域代表（「金钱→时间」「海洋→知识」「道路→人生」
    的触发词/喻底里都含源域词），删掉会误伤最经典的概念隐喻。
  - 「动词当源域 → 删」（推翻/推动/捕捉）：中文无词性标注环境（jieba 不可用）
    下列定不可靠，且这类框架的支持度本来就低、触发词已被 lift 过滤——
    留给支持度分层处理，不做脆弱的词性猜测。

**验证方式（零 API 费用）**
`--verify` 用 data/llm_cache_deepseek.json（真实 DeepSeek 全量预取）做**缓存重放**：
discover/refine 结果全部来自缓存，不同本体变体下的评估差异只来自本体本身。
refine 缓存键为 (chunk, 源域, 目标域)——清洗只删框架/改喻底，保留框架的
触发通道绑定不变，因此 refine 键是原跑的子集，缓存命中率应为 100%（脚本实测）。

运行：
    python -m metaphor_graph.ontology_clean                # 清洗 + 落盘
    python -m metaphor_graph.ontology_clean --verify       # 清洗 + 三变体对照验证
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

from .llm_ontology import (  # noqa: E402
    DEFAULT_OUT, _stable_id, collect_pairs, save_specs)
from .llm_backend import load_table  # noqa: E402
from .ontology import CascadeSpec, FrameSpec  # noqa: E402

DEFAULT_TRAIN_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "llm_ontology_train.json")
DEFAULT_OUT_CLEAN = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ontology_default.json")
DEFAULT_TRAIN_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "llm_cache_train.json")

# 明喻标记：出现在 ground 里即视为「比较词混入」，不是喻底内容。
# （MIPVU 口径下明喻也是隐喻，框架可保留；只是 ground 必须是喻底集合本身。）
_SIMILE_MARKERS = {"如", "像", "似", "般", "若", "宛如", "仿佛", "好比", "犹如",
                   "像…一样", "一般"}


# ---------------------------------------------------------------------------
# 1) 支持度重算（从 train 缓存，不调 LLM）
# ---------------------------------------------------------------------------
def recompute_support(train_cache: str,
                      canon: dict,
                      min_conf: float = 0.85) -> Dict[Tuple[str, str], int]:
    """按 canon 归并映射重算每个规范 (源域,目标域) 的候选支持数。

    build_specs 落盘时没有把 count 写进 FrameSpec（只留 triggers/ground），
    这里从缓存重放同一段聚合逻辑 —— 键必须与 _stable_id("F_LLM", s, t) 的
    (s, t) 一致，否则对不上号。
    """
    table = load_table(train_cache)
    agg = collect_pairs(table, min_conf=min_conf)
    src_map = canon.get("sources", {}) or {}
    tgt_map = canon.get("targets", {}) or {}
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for (rs, rt), rec in agg.items():
        counts[(src_map.get(rs, rs), tgt_map.get(rt, rt))] += rec["count"]
    return counts


# ---------------------------------------------------------------------------
# 2) 清洗规则
# ---------------------------------------------------------------------------
def clean_ground(ground: List[str]) -> Tuple[List[str], int]:
    """剔掉喻底里的明喻标记，返回 (清洗后喻底, 剔除数)。"""
    kept = [g for g in ground if g not in _SIMILE_MARKERS]
    return kept, len(ground) - len(kept)


def clean_frames(frames: List[dict],
                 counts: Dict[Tuple[str, str], int],
                 core_min_support: int = 2,
                 drop_self_loops: bool = True) -> Tuple[List[FrameSpec], dict]:
    """应用全部清洗规则，返回 (框架列表, 统计)。

    规则（每条都给独立计数，验证时逐条核对）：
      R1 自环删除        —— source==target，建模错误。
      R2 明喻标记清理    —— 只清 ground 内容，不删框架（MIPVU 口径下明喻
                            也是隐喻，框架本身有效）。
      R3 支持度分层      —— count>=core_min_support → core，否则 longtail。
                            单例不删：它们是 P2 模糊匹配的锚点（见模块 docstring）。
    """
    stats = {"n_in": len(frames), "r1_self_loop": 0, "r2_ground_fixed": 0,
             "n_ground_markers": 0, "n_core": 0, "n_longtail": 0,
             "n_triggers": 0}
    out: List[FrameSpec] = []
    for f in frames:
        s, t = f["source_domain"], f["target_domain"]
        if drop_self_loops and s == t:
            stats["r1_self_loop"] += 1
            continue
        ground, n_mark = clean_ground(f.get("ground", []))
        stats["n_ground_markers"] += n_mark
        if n_mark:
            stats["r2_ground_fixed"] += 1
        support = int(counts.get((s, t), 0))
        tier = "core" if support >= core_min_support else "longtail"
        stats["n_core" if tier == "core" else "n_longtail"] += 1
        stats["n_triggers"] += len(f.get("triggers", []))
        out.append(FrameSpec(
            id=f["id"], name=f["name"], mapping_type=f["mapping_type"],
            source_domain=s, target_domain=t, ground=ground,
            triggers=list(f.get("triggers", [])),
            source_type=f["source_type"],
            support=support, tier=tier))
    stats["n_out"] = len(out)
    return out, stats


def rebuild_cascades(frames: List[FrameSpec]) -> List[CascadeSpec]:
    """按目标域重建级联（与 llm_ontology.build_specs 同规则、同稳定 id）。"""
    by_target: Dict[str, List[str]] = defaultdict(list)
    for f in frames:
        by_target[f.target_domain].append(f.id)
    return [CascadeSpec(
        id=_stable_id("C_LLM", t), name=f"LLM_TARGET::{t}",
        member_frames=sorted(fids), discourse_domains=[t], typical_triggers=[])
        for t, fids in sorted(by_target.items())]


def clean(train_json: str = DEFAULT_TRAIN_JSON,
          train_cache: str = DEFAULT_TRAIN_CACHE,
          out_path: str = DEFAULT_OUT_CLEAN,
          core_min_support: int = 2) -> Tuple[List[FrameSpec], List[CascadeSpec], dict]:
    """完整清洗流程：载入 → 重算支持度 → 清洗 → 重建级联 → 落盘。"""
    with open(train_json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    frames_raw = payload.get("frames", [])
    canon = payload.get("canon", {}) or {}

    counts = recompute_support(train_cache, canon)
    frames, stats = clean_frames(frames_raw, counts,
                                 core_min_support=core_min_support)
    cascades = rebuild_cascades(frames)
    stats["n_cascades"] = len(cascades)

    provenance = {
        "source_json": os.path.basename(train_json),
        "source_cache": os.path.basename(train_cache),
        "rules": {
            "R1": "删除自环框架（source_domain == target_domain）",
            "R2": f"剔除喻底中的明喻标记 {sorted(_SIMILE_MARKERS)}",
            "R3": f"支持度分层：count>={core_min_support} → core，否则 longtail",
        },
        "note": ("刻意不做：按词性删动词源域（无词性标注环境下列定不可靠，"
                 "且「源域词出现在触发词/喻底」是名词隐喻的正常形态）。"),
        "stats": stats,
    }
    save_specs(frames, cascades, out_path, canon=canon)
    # save_specs 只写 frames/cascades/canon，provenance 单独补写
    with open(out_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["provenance"] = provenance
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return frames, cascades, stats


# ---------------------------------------------------------------------------
# 3) 缓存重放验证（V0 原始 / V1 清洗全量 / V2 清洗 core-only）
# ---------------------------------------------------------------------------
class _CountingPrecomputed:
    """PrecomputedBackend + refine 缓存命中计数。

    命中率必须 = 100%：清洗只删框架/清喻底，保留框架的触发通道绑定不变，
    refine 键 (chunk, 源域, 目标域) 应为原跑缓存键的子集。出现 miss 说明
    某条规则改变了绑定行为 —— 验证不通过，须回查规则。
    """

    def __init__(self, table, refine_table, fallback):
        from .llm_backend import PrecomputedBackend
        self._impl = PrecomputedBackend(table, fallback,
                                        refine_table=refine_table)
        self.refine_hits = 0
        self.refine_misses = 0

    def discover(self, chunk):
        return self._impl.discover(chunk)

    def refine(self, chunk, frame):
        from .llm_backend import _refine_key
        if self._impl.refine_table is not None:
            if _refine_key(chunk, frame) in self._impl.refine_table:
                self.refine_hits += 1
            else:
                self.refine_misses += 1
        return self._impl.refine(chunk, frame)

    def cluster(self, edges):
        return self._impl.cluster(edges)


def _load_refine_table(path: str) -> dict:
    from .llm_backend import LLMRefine
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {tuple(k): (LLMRefine(**v) if v else None) for k, v in raw}


def _build_variant(frame_dicts: List[dict], cascade_dicts: List[dict],
                   use_core_only: bool = False):
    """按变体构造本体（metanet + bootstrap 底座 + 清洗/原始框架并入）。"""
    from .metanet_migrate import build_metanet_ontology
    from .bootstrap_triggers import build_bootstrap_ontology
    from .llm_ontology import build_llm_ontology
    base = build_bootstrap_ontology(build_metanet_ontology())
    sel_f = [f for f in frame_dicts
             if not (use_core_only and f.get("tier") == "longtail")]
    if use_core_only:
        # core-only 时级联按筛选后的框架重建（否则挂了已删框架的空级联）
        from .llm_ontology import _stable_id as _sid
        by_t = defaultdict(list)
        for f in sel_f:
            by_t[f["target_domain"]].append(f["id"])
        cascade_dicts = [
            {"id": _sid("C_LLM", t), "name": f"LLM_TARGET::{t}",
             "member_frames": sorted(fids), "discourse_domains": [t],
             "typical_triggers": []}
            for t, fids in sorted(by_t.items())]
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                      encoding="utf-8")
    json.dump({"frames": sel_f, "cascades": cascade_dicts}, tmp,
              ensure_ascii=False)
    tmp.close()
    try:
        return build_llm_ontology(path=tmp.name, base=base), len(sel_f)
    finally:
        os.unlink(tmp.name)


def verify(clean_json: str = DEFAULT_OUT_CLEAN,
           original_json: str = DEFAULT_TRAIN_JSON,
           discover_cache: str = None) -> int:
    """三变体对照：P1 / 召回 / 精确率 / F1 / P2 覆盖率 / refine 命中率。"""
    from .data_loader import load_ccl2018
    from .evaluate_real import eval_split
    from .llm_backend import LocalHeuristicBackend, PrecomputedBackend
    from .builder import MetaphorSHGBuilder
    from .health import graph_health

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    discover_cache = discover_cache or os.path.join(
        root, "data", "llm_cache_deepseek.json")
    refine_cache = discover_cache + ".refine.json"

    with open(original_json, "r", encoding="utf-8") as f:
        orig = json.load(f)
    with open(clean_json, "r", encoding="utf-8") as f:
        clean = json.load(f)

    variants = [
        ("V0 原始自举本体", orig["frames"], orig["cascades"], False),
        ("V1 清洗全量(core+longtail)", clean["frames"], clean["cascades"], False),
        ("V2 清洗 core-only", clean["frames"], clean["cascades"], True),
    ]

    samples = load_ccl2018()
    table = load_table(discover_cache)
    refine_table = _load_refine_table(refine_cache)

    print("=" * 84)
    print("自举本体清洗验证（缓存重放，零 API 费用；CCL2018 测试集 n=1100）")
    print("=" * 84)

    results = []
    for name, fd, cd, core_only in variants:
        ont, n_frames = _build_variant(fd, cd, core_only)
        backend = _CountingPrecomputed(table, refine_table,
                                       LocalHeuristicBackend(ontology=ont))
        r = eval_split(samples, ont, conf=0.35, use_semfield=True,
                       llm_backend=backend, llm_conf=0.85)
        # P2 覆盖率：对判为隐喻的样本建图
        ex_hits = [s.text for s in samples
                   if _quick_hit(ont, backend, s.text)]
        shg = MetaphorSHGBuilder(ontology=ont, llm_backend=backend).build(
            ex_hits, doc_id="verify")
        h = graph_health(shg)
        n_trig = len(ont._trigger_index)
        results.append(dict(name=name, n_frames=n_frames, n_trig=n_trig, r=r,
                            cov=h.hierarchy_coverage,
                            hits=backend.refine_hits,
                            misses=backend.refine_misses))
        print(f"\n[{name}]  框架={n_frames}  触发词={n_trig}")
        print(f"  P1={r['literal_error_rate']:.3f}  召回={r['recall']:.3f}  "
              f"精确率={r['precision']:.3f}  F1={r['f1']:.3f}")
        print(f"  P2 层级覆盖率={h.hierarchy_coverage:.3f}  "
              f"refine 缓存命中={backend.refine_hits} 未命中={backend.refine_misses}")

    print("\n【对照结论】")
    v0, v1, v2 = results
    for a, b, lab in ((v0, v1, "V1 vs V0（清洗全量）"),
                      (v0, v2, "V2 vs V0（core-only）")):
        d = {k: b["r"][k] - a["r"][k]
             for k in ("recall", "precision", "literal_error_rate", "f1")}
        print(f"  {lab}: 召回 {d['recall']:+.3f}  精确率 {d['precision']:+.3f}  "
              f"P1 {d['literal_error_rate']:+.3f}  F1 {d['f1']:+.3f}  "
              f"覆盖率 {b['cov'] - a['cov']:+.3f}")
    if v1["misses"] or v2["misses"]:
        print(f"  ⚠️ refine 缓存出现未命中（V1={v1['misses']}, V2={v2['misses']}），"
              f"差异可能混入离线近似后端的影响，须回查清洗规则。")
    else:
        print("  ✅ refine 缓存命中率 100%：评估差异全部来自本体本身，对照干净。")
    return 0


def _quick_hit(ont, backend, text: str) -> bool:
    from .extractor import MetaphorExtractor
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    return bool(ex.extract(text, doc_id="verify", chunk_id="q"))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--train-json", default=DEFAULT_TRAIN_JSON)
    ap.add_argument("--train-cache", default=DEFAULT_TRAIN_CACHE)
    ap.add_argument("--out", default=DEFAULT_OUT_CLEAN)
    ap.add_argument("--core-min-support", type=int, default=2,
                    help="core 层支持度下限（count>=该值 → core，否则 longtail）")
    ap.add_argument("--verify", action="store_true",
                    help="清洗后跑 V0/V1/V2 三变体缓存重放对照")
    ap.add_argument("--discover-cache", default=None,
                    help="验证用的 discover 缓存（默认 data/llm_cache_deepseek.json）")
    args = ap.parse_args()

    frames, cascades, stats = clean(args.train_json, args.train_cache,
                                    args.out, args.core_min_support)
    print(f"清洗完成 → {args.out}")
    print(f"  输入框架 {stats['n_in']} → 输出 {stats['n_out']}"
          f"（删自环 {stats['r1_self_loop']}，"
          f"清喻底标记 {stats['n_ground_markers']} 处/{stats['r2_ground_fixed']} 框架）")
    print(f"  分层：core {stats['n_core']} / longtail {stats['n_longtail']}；"
          f"级联 {stats['n_cascades']}；触发词总数 {stats['n_triggers']}")
    print(f"  P0 验收「种子 ≥300 框架」: "
          f"{'✅ 达标' if stats['n_out'] >= 300 else '❌'}"
          f"（core-only 也有 {stats['n_core']} 个）")

    if args.verify:
        return verify(args.out, args.train_json, args.discover_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
