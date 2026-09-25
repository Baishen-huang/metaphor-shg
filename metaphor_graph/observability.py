# -*- coding: utf-8 -*-
"""查询侧可观测性泛函 Ω —— 「这次查询到底激活了连贯的隐喻结构吗？」

**为什么需要它（结构性缺口）**
项目现有的全部验证信号都是 **候选侧** 的：`metaphor_coherence` 判两条超边是否
连贯、LLM 逐链判定、排序器的 7 维特征…… 它们回答的是「候选好不好」。没有任何
一个标量回答「**查询侧**激活了多少隐喻结构」。已上报的语料密度（6.3 链/100 条 L1）
是**语料**的属性，不是**查询**的属性——把语料换掉它就变，但同一个查询在不同语料
上的可观测性并不会因此改变。

Ω 在**结构**上借鉴另一套系统的设计（几何平均合成的可观测性泛函 + 观测完备度
因子），但**基底**完全换成本项目的隐喻结构：激活的是框架/级联而不是它的边与流。

**查询侧不变式（本模块的第一性质）**
Ω **只读查询与本体**，签名里根本没有候选池（无 shg / 无候选边 / 无检索结果）。
这不是一句口号，而是 API 形状：`QueryObservability` 无法访问任何候选。
因此「Ω 对候选池不变」是**结构性**成立的，而不是实验发现——单测 `TestQueryObservability`
把它钉成回归护栏（防止后续有人「顺手」把候选信号混进来改善指标）。

**三个分量（几何平均）**
  Ω_E  edge activation  查询触发词实际点亮的框架数 / 种子触发词数，clip [0,1]
  Ω_N  emergence        经级联扩展抵达、且**不在**直接命中目标域集里的目标概念数
                        / 种子触发词数，clip [0,1]
  Ω_F  flow entropy     激活权重分布的归一化熵（防止全部坍缩到一个触发词/框架）；
                        单条正流量取有限值 0.5，无流量取 0
  Ω_geo = (Ω_E · Ω_N · Ω_F)^(1/3)，各分量带 ε 下界（避免几何平均退化成「与门」）
  Ω = Ω_geo × 观测完备度（查询中被触发词覆盖的字符占比）
  无任何激活时 Ω 恒为 0（ε 下界不适用于「完全没观测到」这一情形）

**regime**：collapsed（无框架被点亮）/ sparse（Ω < 0.5）/ dense（Ω ≥ 0.5）。

**它只声称什么**
参考设计明确只声称 Ω「**能测**」（query-side scalar 可算、可审计）与「**能门控**」
（低 Ω 时该走回退通路），**不声称**它能提升下游指标。本模块遵守同一纪律：
不接入任何检索排序，不改变已上报数字；Ω 是观测量，不是打分器。

零 API 费用、纯本体查表，单次测量约 774 次子串判断（<1ms）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .ontology import CascadeOntology, DEFAULT_ONTOLOGY

# ---------------------------------------------------------------------------
# 常量（阈值与下界都可配置，集中在此便于审计）
# ---------------------------------------------------------------------------
EPS = 1e-3                  # 几何平均的分量下界（防止一个 0 把 Ω 钉死为 0）
SINGLE_FLOW_ENTROPY = 0.5   # 只有一条正流量时的有限熵值（退化情形的约定值）
SPARSE_MAX = 0.5            # Ω < 此值 → sparse；≥ → dense
REGIME_COLLAPSED = "collapsed"
REGIME_SPARSE = "sparse"
REGIME_DENSE = "dense"


@dataclass
class QueryObservability:
    """一次查询的 Ω 观测记录（全部字段均为查询侧，无候选污染）。

    分量之外保留诊断字段（命中的触发词、点亮的框架/级联、涌现目标域、流量权重、
    覆盖字符数）——「能测」的价值就在于出问题时能回答「为什么低」。
    """

    query: str
    omega: float
    omega_geo: float
    omega_e: float
    omega_n: float
    omega_f: float
    completeness: float
    regime: str
    # ---- 诊断（只读快照）----
    matched_triggers: Tuple[str, ...] = ()
    activated_frames: Tuple[str, ...] = ()
    activated_cascades: Tuple[str, ...] = ()
    direct_targets: Tuple[str, ...] = ()
    emergent_targets: Tuple[str, ...] = ()
    flow_weights: Tuple[float, ...] = ()
    observed_chars: int = 0
    n_seed_triggers: int = 0

    # -- 派生诊断（不进 Ω 定义，供分析用）--
    @property
    def n_activated_frames(self) -> int:
        return len(self.activated_frames)

    @property
    def emergence_ratio(self) -> float:
        """涌现目标域占扩展目标域全集的比例（尺度无关版 Ω_N，仅供分析）。"""
        total = set(self.direct_targets) | set(self.emergent_targets)
        return len(self.emergent_targets) / len(total) if total else 0.0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["emergence_ratio"] = self.emergence_ratio
        d["n_activated_frames"] = self.n_activated_frames
        return d

    def summary(self) -> str:
        return (f"Ω={self.omega:.4f} [{self.regime}] "
                f"E={self.omega_e:.3f} N={self.omega_n:.3f} F={self.omega_f:.3f} "
                f"obs={self.completeness:.3f} 触发词 {self.n_seed_triggers} "
                f"框架 {self.n_activated_frames}")


# ---------------------------------------------------------------------------
# 分量计算（纯函数，输入只有「查询 + 本体」）
# ---------------------------------------------------------------------------
def matched_triggers(query: str, ontology: CascadeOntology) -> List[str]:
    """查询中出现的本体触发词。

    与 `RetrievalEngine.cross_domain_retrieve` **逐字同口径**
    （`[t for t in ont._trigger_index if t in query]`）——这是 Ω 与级联通路
    对齐的前提：Ω 说「没激活」，级联通路就必然空手而归。
    """
    return [t for t in ontology._trigger_index if t in query]


def activated_structure(query: str, ontology: CascadeOntology) -> dict:
    """触发词 → 点亮的框架 / 级联 / 直接目标域 / 涌现目标域。

    「直接命中目标域」= 命中框架自身的 target_domain；
    「涌现目标域」= 沿级联取成员框架后新出现、且不在直接命中集里的 target_domain
    ——这正是级联式检索用来跨域的跳板（`cross_domain_retrieve` 里
    `cas.member_frames → targets` 那一段）。
    """
    trigs = matched_triggers(query, ontology)
    hits: Dict[str, int] = {}
    for tok in trigs:
        for fid in ontology._trigger_index.get(tok, []):
            hits[fid] = hits.get(fid, 0) + 1

    frames = sorted(hits)
    direct: set = set()
    for fid in frames:
        fs = ontology.get_frame(fid)
        if fs is not None:
            direct.add(fs.target_domain)

    cascades: set = set()
    for fid in frames:
        cid = ontology.get_cascade(fid)
        if cid:
            cascades.add(cid)

    expanded: set = set()
    for cid in cascades:
        spec = ontology.get_cascade_spec(cid)
        if spec is None:
            continue
        for fid in spec.member_frames:
            fs = ontology.get_frame(fid)
            if fs is not None:
                expanded.add(fs.target_domain)

    return dict(triggers=trigs, hits=hits, frames=frames,
                cascades=sorted(cascades), direct=direct,
                emergent=expanded - direct)


def normalized_entropy(weights: Sequence[float]) -> float:
    """激活权重的归一化熵（bits / log2(n)），值域 [0,1]。

    退化约定（参考设计「单条正流量取有限值」）：
      - 无正权重      → 0.0（没流量）
      - 仅一条正权重  → 0.5（流量存在但完全坍缩；不给 0 也不给 1）
      - n>1           → H / log2(n)
    """
    pos = [w for w in weights if w > 0]
    n = len(pos)
    if n == 0:
        return 0.0
    if n == 1:
        return SINGLE_FLOW_ENTROPY
    total = sum(pos)
    if total <= 0:
        return 0.0
    h = -sum((w / total) * math.log2(w / total) for w in pos)
    return h / math.log2(n)


def geometric_mean(values: Sequence[float], eps: float = EPS) -> float:
    """带 ε 下界的几何平均。

    为什么要有下界：几何平均是「与门」式合成，任何分量取 0 都会把 Ω 钉死为 0，
    于是 Ω 退化成单分量指示器，另外两个分量的信息全丢。ε 下界让「某分量很低」
    表现为「Ω 很小」而非「Ω = 0」，保留序信息。
    例外：**完全无激活**时 Ω 必须严格为 0（由 `measure` 特判，不走这里）。
    """
    if not values:
        return 0.0
    acc = 1.0
    for v in values:
        acc *= max(float(v), eps)
    return acc ** (1.0 / len(values))


def completeness(query: str, trigs: Sequence[str]) -> Tuple[float, int]:
    """观测完备度：查询中被触发词覆盖的字符占比（clip [0,1]）。

    这是「观测装置（触发词词表）到底看见了查询的多少」。同一个 Ω_E=1.0，
    长改写句里偶然夹一个触发词 → 完备度 ≈0.05 → Ω 被压得很低，
    即「这点激活不足以支撑『查询激活了连贯隐喻结构』的判断」。
    """
    if not query:
        return 0.0, 0
    covered = 0
    for t in trigs:
        if t:
            covered += len(t) * query.count(t)
    covered = min(covered, len(query))
    return covered / len(query), covered


def regime_of(omega: float, n_frames: int,
              sparse_max: float = SPARSE_MAX) -> str:
    """regime 分档：无激活 → collapsed；Ω < sparse_max → sparse；否则 dense。"""
    if n_frames <= 0 or omega <= 0.0:
        return REGIME_COLLAPSED
    return REGIME_SPARSE if omega < sparse_max else REGIME_DENSE


# ---------------------------------------------------------------------------
# 测量入口
# ---------------------------------------------------------------------------
def measure(query: str, ontology: Optional[CascadeOntology] = None,
            *, eps: float = EPS, sparse_max: float = SPARSE_MAX
            ) -> QueryObservability:
    """计算查询的 Ω。**签名里没有候选池**——不变式由 API 形状保证。

    Ω = (Ω_E · Ω_N · Ω_F)^(1/3) × 观测完备度，各分量带 ε 下界；
    完全无激活时 Ω = 0（特判）。
    """
    ont = ontology or DEFAULT_ONTOLOGY
    st = activated_structure(query, ont)
    trigs = st["triggers"]
    n_seed = len(trigs)
    n_frames = len(st["frames"])

    # Ω_E：点亮的框架数 / 种子触发词数（clip [0,1]）
    omega_e = min(1.0, n_frames / n_seed) if n_seed else 0.0
    # Ω_N：级联涌现目标域数 / 种子触发词数（clip [0,1]）
    omega_n = min(1.0, len(st["emergent"]) / n_seed) if n_seed else 0.0
    # Ω_F：激活权重（框架被多少个触发词命中）分布的归一化熵
    flow = tuple(float(st["hits"][fid]) for fid in st["frames"])
    omega_f = normalized_entropy(flow)
    comp, observed = completeness(query, trigs)

    if n_seed == 0 or n_frames == 0:
        # 完全没观测到隐喻结构：Ω 严格为 0（ε 下界不适用于此情形）
        omega_geo = omega = 0.0
        omega_e = omega_n = omega_f = comp = 0.0
    else:
        omega_geo = geometric_mean((omega_e, omega_n, omega_f), eps=eps)
        omega = omega_geo * comp

    return QueryObservability(
        query=query, omega=omega, omega_geo=omega_geo, omega_e=omega_e,
        omega_n=omega_n, omega_f=omega_f, completeness=comp,
        regime=regime_of(omega, n_frames, sparse_max),
        matched_triggers=tuple(trigs),
        activated_frames=tuple(st["frames"]),
        activated_cascades=tuple(st["cascades"]),
        direct_targets=tuple(sorted(st["direct"])),
        emergent_targets=tuple(sorted(st["emergent"])),
        flow_weights=flow, observed_chars=observed, n_seed_triggers=n_seed)


class ObservabilityMeter:
    """带缓存的测量器（批量实验用；本体固定，测量仍是纯查询函数）。"""

    def __init__(self, ontology: Optional[CascadeOntology] = None,
                 *, eps: float = EPS, sparse_max: float = SPARSE_MAX):
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.eps = eps
        self.sparse_max = sparse_max
        self._cache: Dict[str, QueryObservability] = {}

    def measure(self, query: str) -> QueryObservability:
        if query not in self._cache:
            if len(self._cache) > 4096:
                self._cache.clear()
            self._cache[query] = measure(query, self.ont, eps=self.eps,
                                         sparse_max=self.sparse_max)
        return self._cache[query]

    def measure_many(self, queries: Sequence[str]) -> List[QueryObservability]:
        return [self.measure(q) for q in queries]

    # ---- 门控（参考设计只声称 Ω「能门控」，故此处只提供判据，不接检索）----
    def gate(self, query: str, theta: float = 0.0) -> bool:
        """Ω ≥ theta 时放行级联通路，否则建议走回退通路。

        theta=0 的退化用法等价于现有 `cross_domain_retrieve` 里的
        `if not agg: semantic_fallback` 判据（见 REPORT 的门控等价性实验）。
        """
        return self.measure(query).omega >= theta

    def stats(self) -> str:
        return (f"ObservabilityMeter: ε={self.eps} sparse_max={self.sparse_max} "
                f"本体 {len(self.ont.frames)} 框架 / "
                f"{len(self.ont._trigger_index)} 触发词")
