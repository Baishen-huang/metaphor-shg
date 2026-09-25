# -*- coding: utf-8 -*-
"""溯源可靠性通道（degraded-provenance reliability channel）。

**要解决的张力**（README §7.1 结论 1）
------------------------------------
类型连贯性检查拦下了 24 个错误绑定，P1 却纹丝不动。根因是：
被拒绑的候选**没有被丢弃**，它退化成临时框架 `F_LLM_*` 后照样产出超边。
要让约束影响精度，就必须丢弃候选 —— 那等于关掉开放发现（+55.8pp 召回）。

参考系统（VCP / RiverMemo）对同一类张力的处理方式不同：**不丢候选**，
而是给它一条**独立且封顶的可靠性通道** —— 该分支的可靠性被显式限制，
并被文档标注为「不具备与主通道同等的事实强度」。

本模块把这一模式落到隐喻超超图上：
  1. 每条超边带一个 `provenance_reliability ∈ [0,1]`，由框架溯源派生；
  2. 本体登记的框架 → 1.0；抽取器临时新建的回退框架 → 封顶 0.5；
  3. 打分/排序层用一个**有下界的乘性因子**消费它 —— 是「封顶折扣」，
     不是过滤器：任何候选都不会因此消失，召回结构完全不变。

为什么用乘性因子而不是加性 bonus
--------------------------------
加性 bonus 只改变分数绝对值、不改变相对次序（两项都加同一常数），
对排序无效。乘性因子按可靠性**缩放**分数，才能真正改变次序，
同时因为 `floor > 0` 而永不归零 —— 与「不丢弃」的设计约束一致。

为什么边界是「本体是否登记」而不是 `F_LLM_` 前缀
------------------------------------------------
**实测陷阱**：`llm_ontology.py` 把自举沉淀的正式框架也命名为 `F_LLM_*`
（`_stable_id("F_LLM", s, t)`），生产本体 2177 个框架**全部**是这个前缀。
所以按前缀判定会把整个生产本体误判为「退化」。唯一正确的判据是
**该 frame_id 在本体中是否有条目**（`ontology.get_frame(fid) is not None`）。
"""

from __future__ import annotations

from typing import Optional

# 本体登记框架的可靠性（上限）
RELIABILITY_ONTOLOGY = 1.0
# 回退框架（抽取器临时新建、本体无条目）的可靠性 —— 显式封顶
RELIABILITY_FALLBACK_CAP = 0.5
# 打分层的下界。1.0 = 关闭该通道（因子恒为 1，历史口径）
RELIABILITY_FLOOR = 0.5
RELIABILITY_FLOOR_OFF = 1.0

# 溯源分级标签（可读审计用）
PROV_ONTOLOGY = "ontology"      # 本体登记框架（人工种子 或 自举回流沉淀）
PROV_FALLBACK = "fallback"      # 抽取器临时框架，本体无条目


def frame_reliability(ontology, frame_id: Optional[str]) -> float:
    """由 frame_id 的**本体登记状态**派生可靠性。

    未登记（临时回退框架）→ 封顶 0.5；已登记 → 1.0。
    没有 ontology 可查时返回 1.0（信息不足时不做无根据的降级）。
    """
    if ontology is None or not frame_id:
        return RELIABILITY_ONTOLOGY
    try:
        registered = ontology.get_frame(frame_id) is not None
    except AttributeError:
        return RELIABILITY_ONTOLOGY
    return RELIABILITY_ONTOLOGY if registered else RELIABILITY_FALLBACK_CAP


def frame_provenance(ontology, frame_id: Optional[str]) -> str:
    """溯源分级标签（PROV_ONTOLOGY / PROV_FALLBACK）。"""
    return (PROV_ONTOLOGY
            if frame_reliability(ontology, frame_id) >= RELIABILITY_ONTOLOGY
            else PROV_FALLBACK)


def edge_reliability(edge, ontology) -> float:
    """超边的溯源可靠性。

    以「边自己记录的 `provenance_reliability`」为准（抽取器写入、可序列化、
    可审计），但**优先用本体复核** —— 手工构造或反序列化来的边不可能知道
    本体，此时按 frame_id 现算，避免默认 1.0 把退化边伪装成正式边。
    """
    derived = frame_reliability(ontology, getattr(edge, "frame_id", None))
    stored = getattr(edge, "provenance_reliability", None)
    if stored is None:
        return derived
    # 只有当存储值**更保守**时才采信（防伪升级，允许显式降级）
    return min(float(stored), derived)


def reliability_factor(reliability: float, floor: float = RELIABILITY_FLOOR) -> float:
    """把可靠性映射成有下界的乘性因子 ∈ [floor, 1]。

    floor=1.0 时恒为 1.0 —— 即关闭该通道（历史口径的精确复原开关）。
    """
    floor = min(1.0, max(0.0, float(floor)))
    r = min(1.0, max(0.0, float(reliability)))
    return floor + (1.0 - floor) * r
