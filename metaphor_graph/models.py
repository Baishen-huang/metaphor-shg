"""隐喻超超图 / 元图 —— 核心数据模型。

对应方案 §4.1.2 的四层结构定义：
    L0  触发词层      语言形式（"失血""泥潭""发条"）
    L1  映射层        隐喻超边（源域, 目标域, 喻底集合, 触发词列表）
    L2  框架层        一般隐喻 = 超顶点（L1 超边的集合）
    L3  级联层        隐喻级联 = 超超顶点（L2 框架的集合）

所有模型都设计为「无外部依赖、可序列化为 dict」，便于后续落 Neo4j / JSON。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 抽取器版本。confidence 的「口径」随抽取器变化——跨版本的置信度不可比，
# 因此每条超边都要记录产出它的版本，冲突消解与 A/B 对比只在同一版本内进行。
EXTRACTOR_VERSION = "1.0.0"


@dataclass
class Evidence:
    """一条超边的证据项（溯源 + 冲突消解用）。

    之所以不是单个 confidence 标量：标量只能回答「这次抽取有多确定」，
    回答不了「两条矛盾的映射信哪个」。证据链让超边可被审计、可被比较、
    可被按权威度/时间/票数消解。
    """

    chunk_id: str
    doc_id: str = "doc0"
    timestamp: float = field(default_factory=time.time)
    authority: float = 0.5          # 来源可信度（权威文献 > 自媒体）
    extractor_version: str = EXTRACTOR_VERSION
    snippet: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @property
    def age_days(self) -> float:
        return (time.time() - self.timestamp) / 86400.0


@dataclass
class ChunkSpan:
    """一个隐喻片段在原文中的定位信息。

    chunk_id 用于在 L1.5 阶段判断「跨 chunk」是否合并；
    start / end 为字符偏移，便于高亮与溯源。
    """

    chunk_id: str
    start: int
    end: int
    text: str
    doc_id: str = "doc0"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class MetaphorHyperedge:
    """L1：一条隐喻映射 = 一条超边。

    喻底集合 (ground) 是「超边性」的来源 —— 一条超边同时连接多个端点，
    且端点之间不存在两两语义关系。这与普通三元组有本质区别。
    """

    id: str
    source_domain: str           # 源域（如：金钱 / 泥潭 / 发条）
    target_domain: str           # 目标域（如：时间 / 项目困境 / 生活状态）
    ground: List[str]            # 喻底集合
    triggers: List[str]          # 触发词列表（L0）
    chunk_spans: List[ChunkSpan] = field(default_factory=list)
    cascade_id: Optional[str] = None   # → L3
    frame_id: Optional[str] = None     # → L2
    novelty: str = "conventional"      # conventional / novel
    sentiment: Dict[str, float] = field(default_factory=dict)  # 受 EmoBi 启发
    confidence: float = 0.0
    source_type: str = "UNKNOWN"       # 用于类型安全约束
    is_extended: bool = False          # 是否为 L1.5 合并的跨 chunk 超边
    layer: int = 1                     # 1 = L1；1.5 = 扩展
    # ---- 演化治理（知识管理，见 Evidence 说明）----
    evidence: List[Evidence] = field(default_factory=list)
    extractor_version: str = EXTRACTOR_VERSION
    deprecated: bool = False           # 软删除：保留溯源链，但不参与检索

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["chunk_spans"] = [s.to_dict() for s in self.chunk_spans]
        d["evidence"] = [v.to_dict() for v in self.evidence]
        return d

    @property
    def member_entities(self) -> List[str]:
        """超边连接的所有端点（用于关联矩阵 / 消息传递）。"""
        return [self.source_domain, self.target_domain] + list(self.ground)

    def describe(self) -> str:
        """把超边渲染成一句自然语言，供向量化与生成上下文使用。

        借鉴 HyperGraphRAG（NeurIPS 2025）：超边必须被渲染成自然语言描述
        才能参与向量检索。JSON 数组形式的 ground / 短字符串的 source/target
        无法直接嵌入——本方法即是补齐这一环。
        """
        grounds = "、".join(self.ground) if self.ground else "（未抽取到喻底）"
        trig = "、".join(self.triggers[:5]) if self.triggers else "（无）"
        return (f"{self.source_domain}→{self.target_domain}："
                f"把{self.target_domain}比作{self.source_domain}，"
                f"强调{grounds}。触发词：{trig}。")

    def authority(self) -> float:
        """证据链的权威度（无证据时回落 0.5）。用于冲突消解。"""
        if not self.evidence:
            return 0.5
        return sum(v.authority for v in self.evidence) / len(self.evidence)

    def support(self) -> int:
        """支持该超边的独立证据条数 —— 多线索汇聚的「票数」。"""
        return len({v.chunk_id for v in self.evidence}) or 1


@dataclass
class MetaphorFrame:
    """L2：一般隐喻 = 超顶点（L1 超边的类型化子集，按框架分组）。"""

    id: str
    name: str                          # "ARGUMENT_IS_PHYSICAL_FORCE"
    member_mapping_ids: List[str] = field(default_factory=list)
    source_frame: str = ""            # FrameNet 框架名
    target_frame: str = ""
    layer: int = 2

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class MetaphorCascade:
    """L3：隐喻级联 = 超超顶点（L2 框架的集合）。

    隐喻级联是预先存在的、层级组织好的基础隐喻和一般隐喻的打包集合，
    它们共同出现。这是认知语言学发现的「自然结构」，而非工程构造。
    """

    id: str
    name: str                          # "ARGUMENT_IS_WAR"
    member_frame_ids: List[str] = field(default_factory=list)
    discourse_domains: List[str] = field(default_factory=list)
    typical_triggers: List[str] = field(default_factory=list)
    layer: int = 3

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class MetaphorSHG:
    """四层隐喻超超图（方案 A）的容器对象。"""

    edges: List[MetaphorHyperedge] = field(default_factory=list)
    frames: List[MetaphorFrame] = field(default_factory=list)
    cascades: List[MetaphorCascade] = field(default_factory=list)

    @property
    def incidence(self):
        """关联矩阵 H：节点(端点) × 超边 的 0/1 归属。"""
        nodes = []
        for e in self.edges:
            for n in e.member_entities:
                if n not in nodes:
                    nodes.append(n)
        idx = {n: i for i, n in enumerate(nodes)}
        import numpy as _np  # 延迟导入，避免无 numpy 时崩溃
        H = _np.zeros((len(nodes), len(self.edges)), dtype=int)
        for j, e in enumerate(self.edges):
            for n in e.member_entities:
                H[idx[n], j] = 1
        return H, nodes

    def summary(self) -> str:
        return (f"MetaphorSHG(L1={len(self.edges)} 超边, "
                f"L2={len(self.frames)} 框架, L3={len(self.cascades)} 级联)")


@dataclass
class RetrieverResult:
    """检索结果（A/B 共享）。"""

    chunk_ids: List[str]
    scores: Dict[str, float]
    trace: str = ""        # 人类可读的「系统为什么这样召回」解释
    path: List[str] = field(default_factory=list)  # 触发的隐喻通路节点

    def to_dict(self) -> dict:
        return {"chunk_ids": self.chunk_ids, "trace": self.trace, "path": self.path}


# ---------------------------------------------------------------------------
# 冲突消解（知识管理 · 演化阶段）
# ---------------------------------------------------------------------------

def merge_evidence(target: MetaphorHyperedge,
                   sources: List[MetaphorHyperedge]) -> None:
    """合并超边时保留全部证据链（不丢溯源）。"""
    seen = {(v.chunk_id, v.snippet) for v in target.evidence}
    for s in sources:
        for v in s.evidence:
            key = (v.chunk_id, v.snippet)
            if key not in seen:
                target.evidence.append(v)
                seen.add(key)
    if not target.evidence:
        for s in sources:
            target.evidence.extend(s.evidence)


def resolve_conflict(edges: List[MetaphorHyperedge],
                     strategy: str = "hybrid",
                     now: Optional[float] = None,
                     half_life_days: float = 365.0) -> Optional[MetaphorHyperedge]:
    """在互相矛盾的超边中选出胜者。

    strategy:
      - ``authority`` 来源权威度优先（医疗 / 法律等权威敏感领域）
      - ``recent``   时间优先（时效敏感领域）
      - ``vote``     多数票（证据条数）—— 多线索汇聚天然是多数票
      - ``hybrid``   默认：权威度 × 时间衰减 × log(票数)

    跨 extractor_version 的置信度不可比，因此本函数不直接使用 confidence
    作为决胜依据——这是刻意的设计（避免度量口径漂移污染消解结果）。
    """
    live = [e for e in edges if not e.deprecated]
    if not live:
        return None
    if len(live) == 1:
        return live[0]

    now = time.time() if now is None else now

    def _recency(e: MetaphorHyperedge) -> float:
        if not e.evidence:
            return 0.5
        ages = [max(0.0, (now - v.timestamp) / 86400.0) for v in e.evidence]
        age = min(ages)  # 用最新的那条证据计时
        return 0.5 ** (age / max(half_life_days, 1e-6))

    if strategy == "authority":
        return max(live, key=lambda e: (e.authority(), e.support()))
    if strategy == "recent":
        return max(live, key=lambda e: (_recency(e), e.authority()))
    if strategy == "vote":
        return max(live, key=lambda e: (e.support(), e.authority()))

    def _hybrid(e: MetaphorHyperedge) -> float:
        import math
        return e.authority() * _recency(e) * math.log1p(e.support())

    return max(live, key=_hybrid)
