"""图健康度指标（知识管理 · 可观测性）。

此前整个项目只有 P1（字面误判率）一个指标。但知识管理需要的是**运维信号**——
图是否在退化、本体是否跟不上语料、层级是否还成立。这些信号必须在系统上线后
持续可观测，否则「图悄悄烂掉」是不会有报错的。

指标与解读：
  - avg_arity        超边平均元数。掉到 2 附近 = 超边退化成普通边，
                     整套超图假设失效（喻底集合抽不出来）。
  - orphan_rate      度 ≤ 1 的端点占比。太高 = 端点无复用，
                     扩展隐喻合并判据的「喻底交集 ≥ 1」永远不成立。
  - hierarchy_cov    L1→L2→L3 归属覆盖率。方案 §7 的 P2 门槛是 >85%。
  - deprecated_rate  软删除占比。增长过快说明知识时效策略过激或语料在漂移。
  - evidence_cov     挂了证据链的超边占比。为 0 = 完全不可溯源、无法冲突消解。
  - density          Δ = 平均每端点参与的超边数，供自适应阈值分档用
                     （下界 2.35 / 上界 5，见 context_budget）。

另外两个是**外部运维信号**，需由调用方传入：
  - unmatched_pool   未匹配累积池大小。涨太快 = 本体跟不上语料。
  - dirty_summaries  元图上层标脏待重算的摘要数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import MetaphorSHG


@dataclass
class GraphHealth:
    n_edges: int = 0
    n_frames: int = 0
    n_cascades: int = 0
    n_nodes: int = 0
    avg_arity: float = 0.0
    orphan_rate: float = 0.0
    hierarchy_coverage: float = 0.0
    frame_coverage: float = 0.0
    cascade_coverage: float = 0.0
    deprecated_rate: float = 0.0
    evidence_coverage: float = 0.0
    avg_confidence: float = 0.0
    density: float = 0.0
    unmatched_pool: int = 0
    dirty_summaries: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["warnings"] = list(self.warnings)
        return d

    def healthy(self) -> bool:
        return not self.warnings

    def report(self) -> str:
        pct = lambda x: f"{x * 100:.1f}%"
        lines = [
            f"规模：L1={self.n_edges} 超边 / L2={self.n_frames} 框架 / "
            f"L3={self.n_cascades} 级联 / 端点={self.n_nodes}",
            f"超边平均元数：{self.avg_arity:.2f}（<2.2 即退化为普通边）",
            f"孤立端点率：{pct(self.orphan_rate)}",
            f"层级覆盖：框架 {pct(self.frame_coverage)} / "
            f"级联 {pct(self.cascade_coverage)} / 综合 {pct(self.hierarchy_coverage)}",
            f"软删除占比：{pct(self.deprecated_rate)}",
            f"证据链覆盖：{pct(self.evidence_coverage)}",
            f"平均置信度：{self.avg_confidence:.3f}",
            f"图密度 Δ：{self.density:.2f}",
            f"未匹配累积池：{self.unmatched_pool} / 脏摘要：{self.dirty_summaries}",
        ]
        if self.warnings:
            lines.append("告警：")
            lines += [f"  - {w}" for w in self.warnings]
        else:
            lines.append("告警：无")
        return "\n".join(lines)


def graph_health(shg: MetaphorSHG,
                 unmatched_pool: int = 0,
                 dirty_summaries: int = 0,
                 arity_floor: float = 2.2,
                 orphan_ceiling: float = 0.8,
                 coverage_floor: float = 0.85) -> GraphHealth:
    """计算图健康度。

    coverage_floor=0.85 对齐方案 §7 的 P2 验收标准（L2/L3 覆盖率 >85%）。
    """
    h = GraphHealth()
    edges = [e for e in shg.edges]
    h.n_edges = len(edges)
    h.n_frames = len(shg.frames)
    h.n_cascades = len(shg.cascades)
    h.unmatched_pool = int(unmatched_pool)
    h.dirty_summaries = int(dirty_summaries)

    if not edges:
        h.warnings.append("图为空：尚未摄入任何超边。")
        return h

    # ---- 端点与度数 ----
    degree: Dict[str, int] = {}
    incidences = 0
    for e in edges:
        ents = list(dict.fromkeys(e.member_entities))  # 去重后再计度
        for n in ents:
            degree[n] = degree.get(n, 0) + 1
        incidences += len(ents)
    h.n_nodes = len(degree)
    h.density = incidences / max(1, h.n_nodes)
    orphans = sum(1 for d in degree.values() if d <= 1)
    h.orphan_rate = orphans / max(1, h.n_nodes)

    # ---- 超边元数 ----
    arities = [len(set(e.member_entities)) for e in edges]
    h.avg_arity = sum(arities) / len(arities)

    # ---- 层级覆盖 ----
    with_frame = sum(1 for e in edges if e.frame_id)
    h.frame_coverage = with_frame / len(edges)
    if shg.frames:
        frame_ids = {f.id for f in shg.frames}
        in_cascade = {f.id for c in shg.cascades for f in
                      [x for x in shg.frames if x.id in c.member_frame_ids]}
        h.cascade_coverage = len(in_cascade & frame_ids) / max(1, len(frame_ids))
    else:
        h.cascade_coverage = 0.0
    h.hierarchy_coverage = min(h.frame_coverage, h.cascade_coverage)

    # ---- 演化与溯源 ----
    h.deprecated_rate = sum(1 for e in edges if e.deprecated) / len(edges)
    h.evidence_coverage = sum(1 for e in edges if e.evidence) / len(edges)
    h.avg_confidence = sum(e.confidence for e in edges) / len(edges)

    # ---- 告警 ----
    if h.avg_arity < arity_floor:
        h.warnings.append(
            f"超边平均元数 {h.avg_arity:.2f} < {arity_floor}：超边已退化为普通边，"
            f"喻底集合未抽出，超图表示失去意义。")
    if h.orphan_rate > orphan_ceiling:
        h.warnings.append(
            f"孤立端点率 {h.orphan_rate * 100:.1f}% > {orphan_ceiling * 100:.0f}%："
            f"端点几乎无复用，扩展隐喻合并判据「喻底交集≥1」难以成立。")
    if h.hierarchy_coverage < coverage_floor:
        h.warnings.append(
            f"层级覆盖率 {h.hierarchy_coverage * 100:.1f}% < {coverage_floor * 100:.0f}%："
            f"未达方案 §7 的 P2 门槛，L2/L3 索引尚未建立。")
    if h.evidence_coverage == 0.0:
        h.warnings.append("证据链覆盖为 0：超边不可溯源，冲突消解无依据。")
    if h.unmatched_pool > max(50, h.n_edges * 0.3):
        h.warnings.append(
            f"未匹配累积池 {h.unmatched_pool} 条，已超阈值："
            f"本体跟不上语料，应触发批量聚类并审核回流。")
    if h.dirty_summaries > max(20, h.n_frames * 0.5):
        h.warnings.append(
            f"脏摘要 {h.dirty_summaries} 个待重算：元图上层索引滞后。")
    return h
