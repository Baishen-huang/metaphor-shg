"""上下文预算与自适应阈值（移植自 HyperRAG，WWW 2026）。

两个工程机制，都是「论文里一笔带过、但不做就会在线上翻车」的东西：

1. **上下文 token 预算 50 / 30 / 20**
   HyperRAG 把生成上下文拆成三类组件并硬性分配预算：
   超边 50% / 实体 30% / 源文本块 20%，按合理性分数降序填充，
   某一类没用完的额度顺延给下一类。
   本项目此前只有 top_k=60 / 120 这类粗粒度设定，没有预算概念——
   结果是「召回到但塞不进上下文」和「噪声挤掉关键超边」同时发生。

2. **自适应阈值衰减 + 密度感知**
   固定阈值在稀疏图上召回为空、在稠密图上召回爆炸。HyperRAG 的做法：
   每跳至少保留 M 条超边，不够就按 c 降阈值（τ₀=0.5, c=0.1, 最多降 5 次）；
   同时按图密度 Δ 分三档（下界 2.35 / 上界 5）切换策略——
   低密度时把被丢弃的候选补回，高密度时给每跳返回量设上限。
   本项目的 U-Retrieval 用固定 top_k，在稀疏隐喻图上会硬凑噪声，
   在稠密图上又会截断，正是这个机制要解决的。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# HyperRAG 论文的图密度分档边界
DENSITY_LOW = 2.35
DENSITY_HIGH = 5.0


# --------------------------------------------------------------------- 图密度
def graph_density(incidences: int, n_nodes: int) -> float:
    """超图密度 Δ = 平均每个端点参与的超边数（总关联数 / 端点数）。

    与 HyperRAG 的 Δ(G) 同义：低密度图遍历容易断，高密度图遍历容易爆。
    """
    if n_nodes <= 0:
        return 0.0
    return float(incidences) / float(n_nodes)


# ----------------------------------------------------------------- 自适应阈值
@dataclass
class ThresholdDecision:
    """一次自适应选择的审计记录（可写进 RetrieverResult.trace）。"""

    threshold: float
    n_candidates: int
    n_selected: int
    n_decays: int
    regime: str
    note: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class AdaptiveThreshold:
    """按「每跳至少 M 条」的目标反推阈值，并按图密度切换策略。"""

    def __init__(self, tau0: float = 0.5, decay: float = 0.1,
                 max_decays: int = 5, min_keep: int = 50,
                 max_keep: Optional[int] = None,
                 low: float = DENSITY_LOW, high: float = DENSITY_HIGH):
        self.tau0 = tau0
        self.decay = decay
        self.max_decays = max_decays
        self.min_keep = min_keep
        self.max_keep = max_keep
        self.low = low
        self.high = high

    def regime(self, density: float) -> str:
        if density <= self.low:
            return "low"
        if density <= self.high:
            return "mid"
        return "high"

    def select(self, scored: Sequence[Tuple[str, float]],
               density: float = 0.0) -> Tuple[List[Tuple[str, float]], ThresholdDecision]:
        """scored: [(id, score), ...]，按分数降序返回被选中的子集。"""
        if not scored:
            return [], ThresholdDecision(self.tau0, 0, 0, 0, self.regime(density),
                                         "无候选。")

        items = sorted(scored, key=lambda x: -x[1])
        tau = self.tau0
        decays = 0
        regime = self.regime(density)

        selected = [it for it in items if it[1] >= tau]
        # 不够 min_keep 就降阈值，直到够或到达衰减上限
        while len(selected) < min(self.min_keep, len(items)) and decays < self.max_decays:
            tau -= self.decay
            decays += 1
            selected = [it for it in items if it[1] >= tau]

        note = f"τ {self.tau0}→{round(tau, 2)}（降 {decays} 次），候选 {len(items)} 选 {len(selected)}"

        if regime == "low":
            # 低密度：图遍历容易断，宁多勿少——不再设上限
            note += "；低密度：不设上限，避免通路断裂"
        elif regime == "high":
            # 高密度：图遍历容易爆，给每跳返回量设上限
            cap = self.max_keep or max(self.min_keep * 3, 1)
            if len(selected) > cap:
                selected = selected[:cap]
                note += f"；高密度：截断至 {cap} 条，避免上下文爆炸"
        else:
            note += "；中密度：常规策略"

        return selected, ThresholdDecision(
            threshold=round(tau, 4), n_candidates=len(items),
            n_selected=len(selected), n_decays=decays,
            regime=regime, note=note)


# --------------------------------------------------------------- 上下文预算
@dataclass
class ContextPack:
    hyperedges: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    chunks: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        parts = []
        if self.hyperedges:
            parts.append("【隐喻映射】\n" + "\n".join(self.hyperedges))
        if self.entities:
            parts.append("【相关概念】\n" + "、".join(self.entities))
        if self.chunks:
            parts.append("【原文片段】\n" + "\n".join(self.chunks))
        return "\n\n".join(parts)


class ContextBudget:
    """按 50 / 30 / 20 分配上下文，未用完的额度顺延给下一类。

    ratios 顺序固定为 (超边, 实体, 源文本块)，与 HyperRAG 一致：
    超边信息密度最高，给最多；源文本块是「肉」，给最少。
    """

    def __init__(self, max_tokens: int = 3000,
                 ratios: Tuple[float, float, float] = (0.5, 0.3, 0.2),
                 chars_per_token: float = 1.6):
        if abs(sum(ratios) - 1.0) > 1e-6:
            raise ValueError("ratios 之和必须为 1.0")
        self.max_tokens = max_tokens
        self.ratios = ratios
        self.chars_per_token = chars_per_token

    def _cost(self, text: str) -> float:
        return max(1.0, len(text) / self.chars_per_token)

    def pack(self, hyperedge_texts: Sequence[str],
             entity_texts: Sequence[str],
             chunk_texts: Sequence[str]) -> ContextPack:
        budgets = [self.max_tokens * r for r in self.ratios]
        pools = [list(hyperedge_texts), list(entity_texts), list(chunk_texts)]
        picked: List[List[str]] = [[], [], []]

        carry = 0.0
        for i in range(3):
            room = budgets[i] + carry
            used = 0.0
            for item in pools[i]:
                c = self._cost(item)
                if used + c <= room:
                    picked[i].append(item)
                    used += c
            carry = room - used  # 没用完的额度顺延给下一类

        return ContextPack(hyperedges=picked[0], entities=picked[1], chunks=picked[2])
