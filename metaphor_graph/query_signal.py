# -*- coding: utf-8 -*-
"""查询侧结构信号（gen3）—— 把「查询激活了什么」拆成**可组合的原始计数**。

**为什么另起一个模块而不改 Ω**
gen1 的 Ω 把三个分量用几何平均合成、给每个分量加 ε 下界、再乘观测完备度，
结果在 n=632 上与「查询有没有命中触发词」这个 1-bit 指示器等价
（ρ(Ω, n_seed)=0.9949）。gen2 发现：**原始涌现计数 `n_emergent` 本身携带信号**
（Ω>0 子集内 AUC 0.836 vs Ω 的 0.654），是 Ω 的合成方式把它稀释掉了。

gen3 的任务是把「原始计数 → 标量」这条路上的每一步都做成**可单独开关**的，
从而定位到底是哪一步毁掉了信号。因此本模块：
  1. 只暴露**原始计数**（不预设合成方式）；
  2. 提供 `compose()`：一个把「ε 下界 / 除以 n_seed / 完备度因子 / 外层特判」
     四个设计选择做成显式开关的合成器（用于机制归因实验）；
  3. 提供一个默认标量 `S_query`（合成方式见下），以及一个条件归一化版本
     `S_conditional`。

**查询侧不变式（与 Ω 同一纪律）**
签名里没有 shg / 候选边 / 检索结果 / 排序器。`measure_signal(query, ontology)`
读的只有查询字符串与本体（框架/级联/触发词表）。测试
`test_query_signal_invariant_to_candidate_pool` 把它钉成回归护栏。

**两种「可达目标域」口径（必须区分，否则数字对不上）**
  - `n_emergent`（gen2/Ω 口径）：级联成员框架的 `target_domain` 集合 −
    直接命中框架自身的 `target_domain` 集合。**只算目标域**。
  - `n_new_domains`（检索口径）：`RetrievalEngine.cross_domain_retrieve`
    真正构造的 `targets` 集合是「目标域 ∪ 源域」，且包含直接命中框架自己的
    两个域。所以「级联扩展**多买到**的域」= (直接 ∪ 扩展) − 直接，
    在「目标域 ∪ 源域」空间上算。这才是通路非空与否的充分统计量。

零 API 费用、纯本体查表。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .ontology import CascadeOntology, DEFAULT_ONTOLOGY

# 默认标量名（实验表里的行名，保持稳定便于对照）
SIG_N_SEED = "n_seed"
SIG_N_FRAMES = "n_frames"
SIG_N_CASCADES = "n_cascades"
SIG_N_EMERGENT = "n_emergent"            # gen2 口径（仅目标域）
SIG_N_NEW_DOMAINS = "n_new_domains"      # 检索口径（目标域 ∪ 源域）
SIG_N_REACH = "n_reach"                  # |直接 ∪ 扩展|（检索口径）
SIG_S_LOG = "S_log"                      # 无下界、无除法的对数计数和
SIG_S_STRUCT = "S_struct"                # 结构化合成：退化分量直接不参与
SIG_OMEGA = "omega"                      # gen1 基线
# gen3 最强候选：Ω 的**唯一**改动是去掉 Ω_N 分量的 min(1,·) 截断
SIG_S_QUERY = "S_query"

SIGNAL_NAMES: Tuple[str, ...] = (
    SIG_N_SEED, SIG_N_FRAMES, SIG_N_CASCADES, SIG_N_EMERGENT,
    SIG_N_NEW_DOMAINS, SIG_N_REACH, SIG_S_LOG, SIG_S_STRUCT, SIG_OMEGA,
    SIG_S_QUERY,
)


# ---------------------------------------------------------------------------
# 原始计数
# ---------------------------------------------------------------------------
def _domains_of(fids: Sequence[str], ont: CascadeOntology,
                which: str) -> Set[str]:
    out: Set[str] = set()
    for fid in fids:
        fs = ont.get_frame(fid)
        if fs is None:
            continue
        if which in ("target", "both"):
            out.add(fs.target_domain)
        if which in ("source", "both"):
            out.add(fs.source_domain)
    return out


def reachable_structure(query: str, ontology: Optional[CascadeOntology] = None
                        ) -> dict:
    """查询 → 直接命中结构 / 级联扩展结构 / 可达域集合。

    返回的 `frames` 是**去重后的框架 id**（与 `observability.activated_structure`
    同口径：一个框架被 k 个触发词命中只算 1 个），`hits` 保留命中权重。
    """
    from .observability import matched_triggers
    ont = ontology or DEFAULT_ONTOLOGY
    trigs = matched_triggers(query, ont)

    hits: Dict[str, int] = {}
    for tok in trigs:
        for fid in ont._trigger_index.get(tok, []):
            hits[fid] = hits.get(fid, 0) + 1
    frames = sorted(hits)

    cascades: List[str] = []
    for fid in frames:
        cid = ont.get_cascade(fid)
        if cid and cid not in cascades:
            cascades.append(cid)
    cascades = sorted(cascades)

    members: List[str] = []
    n_cross = 0
    for cid in cascades:
        spec = ont.get_cascade_spec(cid)
        if spec is None:
            continue
        span = _domains_of(spec.member_frames, ont, "target")
        if len(span) >= 2:
            n_cross += 1
        for fid in spec.member_frames:
            if fid not in members:
                members.append(fid)

    # --- gen2/Ω 口径：仅 target_domain ---
    direct_td = _domains_of(frames, ont, "target")
    expanded_td = _domains_of(members, ont, "target")
    emergent_td = expanded_td - direct_td

    # --- 检索口径：target_domain ∪ source_domain ---
    direct_both = _domains_of(frames, ont, "both")
    expanded_both = _domains_of(members, ont, "both")
    new_domains = expanded_both - direct_both
    reach = direct_both | expanded_both

    return dict(
        triggers=trigs, hits=hits, frames=frames, cascades=cascades,
        members=members, n_cross_cascades=n_cross,
        direct_targets=direct_td, expanded_targets=expanded_td,
        emergent_targets=emergent_td,
        direct_domains=direct_both, expanded_domains=expanded_both,
        new_domains=new_domains, reachable_domains=reach,
    )


# ---------------------------------------------------------------------------
# 合成器：把 Ω 的四个设计选择做成显式开关（机制归因用）
# ---------------------------------------------------------------------------
def compose(components: Dict[str, float], *, n_seed: int,
            completeness: float, floor: bool, normalize: bool,
            use_completeness: bool, outer_zero: bool,
            eps: float = 1e-3) -> float:
    """按四个开关合成一个标量（gen3 机制归因实验的核心工具）。

    开关按**与 Ω 实现相同的顺序**应用，四个开关正交：

    1. ``normalize``       True → 各分量除以 n_seed（Ω 的做法，分母是种子数）；
                           False → 用原始计数。
    2. ``floor``           True → 各分量 ``max(v, eps)``（Ω 的 ε 下界）；
                           False → 分量为 0 时**直接不参与**（结构化处理，
                           而不是被托底成常数）；全为 0 → 结果 0。
    3. 几何平均            （固定；这是被诊断的合成算子本身）
    4. ``use_completeness`` True → 结果乘观测完备度（Ω 的做法）。
    5. ``outer_zero``      True → 无激活（n_seed=0）时严格为 0（Ω 的外层特判）。

    有了它，「Ω 的信号是哪一步丢的」就不再是论证，而是逐开关的实测对照。
    """
    if n_seed <= 0:
        return 0.0
    vals = [float(v) / n_seed if normalize else float(v)
            for v in components.values()]
    if floor:
        vals = [max(v, eps) for v in vals]
    else:
        vals = [v for v in vals if v > 0.0]
        if not vals:
            return 0.0
    geo = math.exp(sum(math.log(v) for v in vals) / len(vals))
    if use_completeness:
        geo *= completeness
    return geo if not outer_zero or n_seed > 0 else 0.0


# ---------------------------------------------------------------------------
# 标量集合
# ---------------------------------------------------------------------------
@dataclass
class QuerySignal:
    """一次查询的查询侧结构信号（全部字段均为查询侧，无候选污染）。"""

    query: str
    n_seed: int
    n_frames: int
    n_cascades: int
    n_emergent: int
    n_new_domains: int
    n_reachable_targets: int
    completeness: float
    # 原始分量（Ω 口径，供事后任意重组）
    omega: float
    omega_e: float
    omega_n: float
    omega_f: float
    signals: Dict[str, float] = field(default_factory=dict)
    # 诊断快照
    matched_triggers: Tuple[str, ...] = ()
    activated_frames: Tuple[str, ...] = ()
    emergent_targets: Tuple[str, ...] = ()
    new_domains: Tuple[str, ...] = ()

    def get(self, name: str) -> float:
        return self.signals[name]

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d.pop("signals", None)
        d.update({f"sig_{k}": v for k, v in self.signals.items()})
        return d

    def summary(self) -> str:
        return (f"S_query={self.signals[SIG_S_LOG]:.4f} "
                f"[seed={self.n_seed} frames={self.n_frames} "
                f"cas={self.n_cascades} em={self.n_emergent} "
                f"new={self.n_new_domains} reach={self.n_reachable_targets}]")


def _s_log(n_frames: int, n_cascades: int, n_new_domains: int) -> float:
    """S_log = log1p(框架数) + log1p(级联数) + log1p(新买到域数)。

    与几何平均的**唯一区别**：没有 ε 下界、没有分母。退化分量（计数为 0）
    在 log 空间贡献 0（中性），既不会把整体钉死为 0，也不会被托底成常数。
    等价于 (1+n_f)(1+n_c)(1+n_new) 的几何平均 —— 即「保留几何平均、
    去掉 ε 下界与归一化」这一支。
    """
    return (math.log1p(max(0, n_frames)) + math.log1p(max(0, n_cascades))
            + math.log1p(max(0, n_new_domains)))


def _s_struct(n_seed: int, n_frames: int, n_cascades: int, n_new_domains: int
              ) -> float:
    """S_struct：结构化合成 —— 退化分量直接**不参与**，而非被托底。

    三个分量按「该分量的基底是否可能非退化」决定是否入选：
      - 框架激活：n_seed ≥ 1 时基底成立 → min(1, n_frames / n_seed)
      - 级联扩展：只有在「被激活级联带来了新域」时才入选（否则该维度对
        **所有**查询都恒为 0，把它纳入合成只会给所有查询乘同一个常数）

    这是「用显式结构处理替代 ε 下界」的那一支。
    """
    if n_seed <= 0 or n_frames <= 0:
        return 0.0
    parts = [min(1.0, n_frames / n_seed)]
    if n_cascades > 0 and n_new_domains > 0:
        parts.append(min(1.0, n_new_domains / n_seed))
    return math.exp(sum(math.log(v) for v in parts) / len(parts))


def _s_query(n_seed: int, n_frames: int, n_emergent: int, omega_f: float,
             comp: float, eps: float = 1e-3) -> float:
    """S_query：gen3 的最强候选 —— Ω 的**单点修改**版本。

    与 Ω 逐字相同，**只有一处不同**：Ω_N 分量不做 ``min(1, ·)`` 截断。

        Ω   = (Ω_E · min(1, n_em / n_seed) · Ω_F)^(1/3) × comp
        S_query = (Ω_E ·     (n_em / n_seed)  · Ω_F)^(1/3) × comp

    gen3 实验 2 的因子分解证明：这一处截断是信号被毁掉的**主要**原因。
    生产本体（`json` 规则）下 Ω_N 分母为 1 时 n_emergent 只有 3 档、
    23 个样本被截到 1.0；`source` 规则下 n_seed=1 层有 82/102 条被截到
    1.0，23 档取值塌成 2 档。去掉截断后 Ω>0 子集内的 AUC 从
    0.654 → 0.824（`source`）/ 0.593 → 0.609（`json`）。

    **注意**：AUC 变高不等于「有用」。gen3 实验 4/5 证明这个信号在控制
    「可达集合大小」后消失（条件 AUC ≈ 0.5），因为被预测的目标
    「级联通路非空」本身是集合相交的定理。本函数只是把 Ω 的**实现缺陷**
    修正掉，使 Ω_N 分量不再把 n_emergent 压成 1 bit。
    """
    if n_seed <= 0 or n_frames <= 0:
        return 0.0
    omega_e = min(1.0, n_frames / n_seed)
    omega_n = n_emergent / n_seed            # ← 与 Ω 的唯一差别：无 min(1,·)
    vals = (max(omega_e, eps), max(omega_n, eps), max(omega_f, eps))
    geo = math.exp(sum(math.log(v) for v in vals) / len(vals))
    return geo * comp


def measure_signal(query: str, ontology: Optional[CascadeOntology] = None
                   ) -> QuerySignal:
    """计算查询侧结构信号。**签名里没有候选池**——不变式由 API 形状保证。"""
    from .observability import measure, completeness as _comp
    ont = ontology or DEFAULT_ONTOLOGY
    st = reachable_structure(query, ont)
    o = measure(query, ont)

    n_seed = len(st["triggers"])
    n_frames = len(st["frames"])
    n_cascades = len(st["cascades"])
    n_emergent = len(st["emergent_targets"])
    n_new = len(st["new_domains"])
    n_reach = len(st["reachable_domains"])
    comp = _comp(query, st["triggers"])[0]

    signals = {
        SIG_N_SEED: float(n_seed),
        SIG_N_FRAMES: float(n_frames),
        SIG_N_CASCADES: float(n_cascades),
        SIG_N_EMERGENT: float(n_emergent),
        SIG_N_NEW_DOMAINS: float(n_new),
        SIG_N_REACH: float(n_reach),
        SIG_S_LOG: _s_log(n_frames, n_cascades, n_new),
        SIG_S_STRUCT: _s_struct(n_seed, n_frames, n_cascades, n_new),
        SIG_OMEGA: float(o.omega),
        SIG_S_QUERY: _s_query(n_seed, n_frames, n_emergent, o.omega_f, comp),
    }
    return QuerySignal(
        query=query, n_seed=n_seed, n_frames=n_frames,
        n_cascades=n_cascades, n_emergent=n_emergent,
        n_new_domains=n_new, n_reachable_targets=n_reach,
        completeness=comp, omega=o.omega, omega_e=o.omega_e,
        omega_n=o.omega_n, omega_f=o.omega_f, signals=signals,
        matched_triggers=tuple(st["triggers"]),
        activated_frames=tuple(st["frames"]),
        emergent_targets=tuple(sorted(st["emergent_targets"])),
        new_domains=tuple(sorted(st["new_domains"])))


# ---------------------------------------------------------------------------
# 条件归一化（n_seed 分层 z 分数）
# ---------------------------------------------------------------------------
class StratifiedNormalizer:
    """把任意查询侧计数按 **n_seed 分层** 标准化：z = (x − μ_stratum) / σ_stratum。

    为什么需要它：触发词命中数是查询的「体量」，任何随体量增长的计数
    （点亮的框架、买到的域）都与它正相关。gen2 的发现是：**在 n_seed 固定的
    层内**再检验，n_emergent 的判别力从 0.836（本来就有）稳定下来，而 Ω 的
    0.654 反而下降 —— 说明 Ω 的序在层间被体量主导。把分层标准化做成一个
    **标量**，就把「条件判别」从检验方式变成了可部署的量。

    `fit()` 只在**有触发词命中**的样本上统计（n_seed=0 的层没有可标准化的
    变异）。层内 sd=0 时回退为「x − μ」（即层内偏差），再整体除以全局 sd，
    避免整层被清零。
    """

    def __init__(self, source: str = SIG_N_NEW_DOMAINS):
        self.source = source
        self._mu: Dict[int, float] = {}
        self._sd: Dict[int, float] = {}
        self._global_sd = 1.0

    def fit(self, rows: Sequence[dict]) -> "StratifiedNormalizer":
        from collections import defaultdict
        buckets: Dict[int, List[float]] = defaultdict(list)
        for r in rows:
            if r["n_seed"] >= 1:
                buckets[int(r["n_seed"])].append(float(r[self.source]))
        devs: List[float] = []
        for k, vals in buckets.items():
            mu = sum(vals) / len(vals)
            self._mu[k] = mu
            var = (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)
                   if len(vals) > 1 else 0.0)
            self._sd[k] = math.sqrt(var)
            devs.extend(v - mu for v in vals)
        if len(devs) > 1:
            m = sum(devs) / len(devs)
            gv = sum((d - m) ** 2 for d in devs) / (len(devs) - 1)
            self._global_sd = math.sqrt(gv) if gv > 0 else 1.0
        return self

    def transform_one(self, n_seed: int, x: float) -> float:
        if n_seed <= 0:
            return 0.0
        mu = self._mu.get(int(n_seed))
        if mu is None:                     # 未见过的层 → 全局 z
            mu = sum(self._mu.values()) / len(self._mu) if self._mu else 0.0
        sd = self._sd.get(int(n_seed), 0.0)
        dev = x - mu
        if sd > 1e-9:
            return dev / sd
        return dev / self._global_sd

    def transform(self, rows: Sequence[dict]) -> List[float]:
        return [self.transform_one(r["n_seed"], float(r[self.source]))
                for r in rows]


# ---------------------------------------------------------------------------
# 门控辅助（只提供判据，不接检索路径）
# ---------------------------------------------------------------------------
def gate_by(signal: Dict[str, float], name: str, theta: float) -> bool:
    """通用门控：信号 ≥ theta 时放行。不改变任何已上报数字。"""
    if name not in signal:
        raise KeyError(f"未知信号：{name}（可选：{sorted(signal)}）")
    return signal[name] >= theta
