# -*- coding: utf-8 -*-
"""L3 级联构造规则（可选择的替代方案集合）。

**为什么需要这个模块**
`ontology_clean.rebuild_cascades` / `llm_ontology.build_specs` / `builder._ensure_cascades`
三处都按**目标域**打包级联。这带来一个结构性后果：一个级联的成员框架
共享同一个 target_domain，于是 `RetrievalEngine.cross_domain_retrieve` 里
「沿级联扩展目标域」那一段（`cas.member_frames → targets`）几乎取不到新目标域，
级联退化成「框架别名」。实测生产本体 758 级联中 752 个（99.2%）成员共享单一目标域、
中位规模 1。本模块把构造规则抽成可选项，让这个缺陷可度量、可对照、可回退。

**默认不变**
`RULE_JSON`（=「按 JSON 里的级联原样载入」）是**默认值**，与改动前逐位一致。
所有替代规则只在显式传入 `cascade_rule=` 时生效。

规则一览
--------
  json        原样载入本体 JSON 的级联（= 改动前的默认行为，基线）
  target      按 target_domain 打包（= JSON 的构造规则，从 frames 重算，用于自检）
  source      按 source_domain 打包（同一喻体家族 → 一个级联；经典 cascade 形态）
  ground      按**喻底集合**的 Jaccard 连通分量打包（共现喻底 = 级联的语言学判据）
  metanet     有 MetaNet/种子级联归属的框架保留原归属，孤儿按 source 规则兜底
  source_type 按推断出的 source_type（粗粒度喻体类别）打包（最粗对照）
  none        不建任何级联（L3 消融对照：测「级联层是否存在」对指标的影响）

运行：
    python -m metaphor_graph.cascade_rules --list
    python -m metaphor_graph.cascade_rules --rule source --stats
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .ontology import CascadeSpec, CascadeOntology, FrameSpec

# 原样载入 JSON 级联（默认；与改动前行为逐位一致）
RULE_JSON = "json"
CASCADE_RULES: Tuple[str, ...] = (
    RULE_JSON, "target", "source", "ground", "metanet", "source_type", "none")


def _sid(prefix: str, *parts: str) -> str:
    """稳定 id（md5 前 8 位）：本体是长期资产，id 必须跨进程可复现。"""
    h = hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{h}"


# ---------------------------------------------------------------------------
# 各规则的「分组」实现：frames → {组键: [frame_id, ...]}
# ---------------------------------------------------------------------------
def _group_by(frames: Sequence[FrameSpec], field: str) -> Dict[str, List[str]]:
    g: Dict[str, List[str]] = defaultdict(list)
    for f in frames:
        key = getattr(f, field, "") or "未标注"
        g[key].append(f.id)
    return dict(g)


def group_by_target(frames: Sequence[FrameSpec]) -> Dict[str, List[str]]:
    """按目标域分组（现状规则）。"""
    return _group_by(frames, "target_domain")


def group_by_source(frames: Sequence[FrameSpec]) -> Dict[str, List[str]]:
    """按源域分组 —— 同一喻体家族组织为一个级联。

    语言学依据：MetaNet/概念隐喻研究中大量级联正是「同一源域、多个目标域」
    的打包（如 JOURNEY 级联覆盖 LIFE/LOVE/CAREER IS A JOURNEY）。
    """
    return _group_by(frames, "source_domain")


def group_by_source_type(frames: Sequence[FrameSpec]) -> Dict[str, List[str]]:
    """按 source_type（粗粒度喻体类别）分组 —— 最粗的对照。"""
    return _group_by(frames, "source_type")


def group_by_ground(frames: Sequence[FrameSpec],
                    jaccard: float = 0.34) -> Dict[str, List[str]]:
    """按喻底集合的 Jaccard 相似度做贪心聚合（连通分量式）。

    语言学依据：级联是「预先组织好的、**共同出现**的基础隐喻与一般隐喻的打包」，
    共现的载体就是喻底（ground）集合 —— 喻底相同/重叠的映射在语篇里本就会
    一起出现。阈值 0.34 ≈ 「3 个喻底里至少重叠 1 个」（Jaccard=1/5=0.2 偏低，
    1/3=0.33 是「三个喻底共享一个」的临界），与 `extended.py` 的喻底交集判据同源。

    确定性：框架按 (support 降序, id 升序) 处理；每个未归组框架开一个新组，
    再吸收与**该组喻底并集** Jaccard ≥ 阈值的框架。
    """
    ordered = sorted(frames, key=lambda f: (-int(getattr(f, "support", 0) or 0), f.id))
    groups: List[Tuple[set, List[str]]] = []
    for f in ordered:
        gs = set(f.ground or ())
        best_i, best_j = -1, 0.0
        for i, (union, _members) in enumerate(groups):
            if not gs or not union:
                continue
            j = len(gs & union) / max(1, len(gs | union))
            if j > best_j:
                best_i, best_j = i, j
        if best_i >= 0 and best_j >= jaccard:
            union, members = groups[best_i]
            members.append(f.id)
            groups[best_i] = (union | gs, members)
        else:
            groups.append((set(gs), [f.id]))
    return {f"G{i}": sorted(m) for i, (_u, m) in enumerate(groups)}


def group_by_metanet(frames: Sequence[FrameSpec],
                     base_cascades: Dict[str, CascadeSpec],
                     fallback: str = "source") -> Dict[str, List[str]]:
    """MetaNet 风格：保留**有语言学来源**的级联，其余框架按 fallback 重组。

    「有语言学来源」的判据：级联 id 不以 `C_LLM_` 开头 —— 即手工种子
    （`ontology.py` 内置 13 个）与 MetaNet 迁移种子（25 个）。`C_LLM_*` 是
    LLM 自举后按目标域机械打包的产物，正是本次要评估的对象。

    与 `json` 的差别：现状下「语言学级联」与「工程兜底级联」混在同一个
    `ont.cascades` 里无法分离；本规则把两者显式分开，使「级联的跨域组织力
    来自语言学种子还是来自工程打包」这个问题可度量。
    """
    f2c: Dict[str, str] = {}
    for cid, spec in base_cascades.items():
        if cid.startswith("C_LLM_"):
            continue                      # 工程打包的级联不作为归属依据
        for fid in spec.member_frames:
            f2c.setdefault(fid, cid)
    groups: Dict[str, List[str]] = defaultdict(list)
    orphan: List[FrameSpec] = []
    for f in frames:
        cid = f2c.get(f.id)
        if cid:
            groups[f"KEEP::{cid}"].append(f.id)
        else:
            orphan.append(f)
    if fallback == "source":
        sub = group_by_source(orphan)
    elif fallback == "target":
        sub = group_by_target(orphan)
    elif fallback == "ground":
        sub = group_by_ground(orphan)
    else:
        raise ValueError(f"未知 fallback: {fallback}")
    for k, v in sub.items():
        groups[f"FB::{k}"] = v
    return dict(groups)


# ---------------------------------------------------------------------------
# 统一入口：frames + 规则 → cascades
# ---------------------------------------------------------------------------
_NAMES = {
    "target": "TARGET", "source": "SOURCE", "source_type": "STYPE",
    "ground": "GROUND", "metanet": "METANET",
}


def build_cascades(frames: Sequence[FrameSpec], rule: str = RULE_JSON,
                   base_cascades: Optional[Dict[str, CascadeSpec]] = None,
                   **kw) -> Dict[str, CascadeSpec]:
    """按规则构造级联字典。`json` 规则原样返回 base_cascades（默认不变）。

    `base_cascades=None` 时 `json` 规则退化为 `target`（无 JSON 可载入时的
    合理回退，也让单测可以只给 frames）。
    """
    if rule not in CASCADE_RULES:
        raise ValueError(f"未知级联构造规则 {rule!r}；可选 {CASCADE_RULES}")
    if rule == RULE_JSON:
        if base_cascades is None:
            rule = "target"
        else:
            return dict(base_cascades)
    if rule == "none":
        return {}
    if rule == "target":
        groups = group_by_target(frames)
    elif rule == "source":
        groups = group_by_source(frames)
    elif rule == "source_type":
        groups = group_by_source_type(frames)
    elif rule == "ground":
        groups = group_by_ground(frames, jaccard=kw.get("ground_jaccard", 0.34))
    elif rule == "metanet":
        groups = group_by_metanet(frames, base_cascades or {},
                                  fallback=kw.get("metanet_fallback", "source"))
    else:  # pragma: no cover - 已由上面的白名单挡住
        raise ValueError(rule)

    tag = _NAMES.get(rule, rule.upper())
    out: Dict[str, CascadeSpec] = {}
    for key, fids in sorted(groups.items()):
        fids = sorted(fids)
        if key.startswith("KEEP::"):
            cid = key.split("::", 1)[1]
            out[cid] = CascadeSpec(
                id=cid, name=f"METANET::{cid}", member_frames=fids,
                discourse_domains=[], typical_triggers=[])
            continue
        k2 = key.split("::", 1)[1] if "::" in key else key
        cid = _sid(f"C_{tag}", k2)
        out[cid] = CascadeSpec(
            id=cid, name=f"{tag}::{k2}", member_frames=fids,
            discourse_domains=[k2], typical_triggers=[])
    return out


def apply_rule(ont: CascadeOntology, rule: str = RULE_JSON, **kw) -> CascadeOntology:
    """就地替换本体的级联层（含 `_frame_to_cascade` 反向索引），返回同一对象。

    必须重建反向索引 —— `get_cascade()` 走的是缓存字典，不重建会让所有
    查询拿到旧归属（这是最容易被忽略的一致性坑）。
    """
    frames = list(ont.frames.values())
    ont.cascades = build_cascades(frames, rule, base_cascades=ont.cascades, **kw)
    ont._frame_to_cascade = {}
    for cid, c in ont.cascades.items():
        for fid in c.member_frames:
            ont._frame_to_cascade[fid] = cid
    return ont


# ---------------------------------------------------------------------------
# 统计（供实验与报告使用）
# ---------------------------------------------------------------------------
def cascade_stats(cascades: Dict[str, CascadeSpec],
                  frames: Dict[str, FrameSpec]) -> dict:
    """级联层的结构统计：规模分布 / 跨目标域 / 单例率 / 框架覆盖。"""
    sizes, n_targets, n_sources = [], [], []
    for cid, spec in cascades.items():
        fids = list(spec.member_frames)
        sizes.append(len(fids))
        tg, sg = set(), set()
        for fid in fids:
            fs = frames.get(fid)
            if fs is None:
                continue
            tg.add(fs.target_domain)
            sg.add(fs.source_domain)
        n_targets.append(len(tg))
        n_sources.append(len(sg))
    n = len(sizes)
    srt = sorted(sizes)
    med = (srt[n // 2] if n % 2 else 0.5 * (srt[n // 2 - 1] + srt[n // 2])) if n else 0.0
    covered = {fid for c in cascades.values() for fid in c.member_frames}
    return dict(
        n_cascades=n,
        size_median=med, size_mean=(sum(sizes) / n if n else 0.0),
        size_max=max(sizes or [0]),
        size_hist={str(k): v for k, v in sorted(Counter(sizes).items())},
        n_singleton=sum(1 for s in sizes if s == 1),
        singleton_rate=(sum(1 for s in sizes if s == 1) / n if n else 0.0),
        n_cross_target=sum(1 for k in n_targets if k >= 2),
        cross_target_rate=(sum(1 for k in n_targets if k >= 2) / n if n else 0.0),
        targets_median=(sorted(n_targets)[n // 2] if n else 0),
        n_multi_source=sum(1 for k in n_sources if k >= 2),
        n_frames_in_cascade=len(covered & set(frames)),
        frame_cascade_coverage=len(covered & set(frames)) / max(1, len(frames)),
    )


def main():
    ap = argparse.ArgumentParser(description="L3 级联构造规则工具")
    ap.add_argument("--rule", default=RULE_JSON, choices=CASCADE_RULES)
    ap.add_argument("--list", action="store_true", help="列出可用规则")
    ap.add_argument("--stats", action="store_true", help="打印该规则的结构统计")
    ap.add_argument("--ontology", default=None)
    args = ap.parse_args()

    if args.list:
        for r in CASCADE_RULES:
            print(f"  {r}")
        return 0

    from .evaluate_fullcorpus import build_replay_ontology
    ont, n_frames = build_replay_ontology(args.ontology) if args.ontology else \
        build_replay_ontology()
    base = dict(ont.cascades)
    apply_rule(ont, args.rule)
    st = cascade_stats(ont.cascades, ont.frames)
    print(f"规则 {args.rule}: 框架 {n_frames}（JSON 级联 {len(base)}）")
    for k in ("n_cascades", "size_median", "size_mean", "size_max",
              "n_singleton", "singleton_rate", "n_cross_target",
              "cross_target_rate", "n_multi_source", "frame_cascade_coverage"):
        v = st[k]
        print(f"  {k:24s} = {v:.4f}" if isinstance(v, float) else
              f"  {k:24s} = {v}")
    print(f"  规模直方图 = {st['size_hist']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
