"""L1.5 跨 chunk 扩展隐喻链接（方案 §4.2，差异化能力）。

语言学依据：延伸比喻的延伸部分是比喻的有机组成部分，没有它绝大多数比喻
根本不能成立。同一源域的隐喻在文本中成簇出现时即构成扩展隐喻。

三判据合并（方案原文）：
    同框架 + 同源域 + chunk距离<3 + 喻底交集≥1
为什么喻底交集是关键：若两 chunk 都用「战争」源域，但喻底分别是
[对抗,胜负] 与 [伤亡,代价]，可能属于同级联下不同框架，不该合并。
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Dict, List

from .models import ChunkSpan, MetaphorHyperedge


def _min_span_gap(a: List[ChunkSpan], b: List[ChunkSpan],
                  order: Dict[str, int]) -> int:
    """两个超边跨越的最近 chunk 间距。"""
    ga = {s.chunk_id for s in a}
    gb = {s.chunk_id for s in b}
    best = 10 ** 9
    for ca in ga:
        for cb in gb:
            ia, ib = order.get(ca, 10 ** 9), order.get(cb, 10 ** 9)
            if ia != 10 ** 9 and ib != 10 ** 9:
                best = min(best, abs(ia - ib))
    return best


def link_extended_metaphors(edges: List[MetaphorHyperedge],
                            chunk_order: Dict[str, int],
                            max_gap: int = 3,
                            continuity: str = "ground1") -> List[MetaphorHyperedge]:
    """将满足条件的相邻 L1 超边合并为跨 chunk 扩展超边（is_extended=True）。

    continuity（延续性判据，连贯文档语料质量评审后新增，见 README §7.3）：
      "ground1"       喻底交集 ≥1（原口径，密度高、严格口径精度低——16.7%）
      "vehicle_repeat"  喻底交集 ≥1 **且**（同一触发词跨 chunk 词面复现
                        或 喻底交集 ≥2）——针对评审发现的失败模式：
                        词化惯用语/单点隐喻相邻重复即被合并。

    返回新生成的扩展超边，不修改原 edges。
    """
    if continuity not in ("ground1", "vehicle_repeat"):
        raise ValueError("continuity 必须是 ground1 / vehicle_repeat")
    # 分组：同框架 + 同源域
    groups: Dict[tuple, List[MetaphorHyperedge]] = defaultdict(list)
    for e in edges:
        groups[(e.frame_id, e.source_domain)].append(e)

    merged: List[MetaphorHyperedge] = []
    for (frame_id, src), group in groups.items():
        if len(group) < 2:
            continue

        # 贪心链式合并（按 chunk 顺序）
        group_sorted = sorted(
            group, key=lambda e: min(chunk_order.get(s.chunk_id, 10 ** 9)
                                     for s in e.chunk_spans))
        chain = [group_sorted[0]]
        for e in group_sorted[1:]:
            gap = _min_span_gap(chain[-1].chunk_spans, e.chunk_spans, chunk_order)
            # 喻底交集 ≥ 1 才考虑合并
            overlap = set(chain[-1].ground) & set(e.ground)
            if gap < max_gap and overlap:
                if continuity == "vehicle_repeat":
                    # 延续性证据：同一触发词跨 chunk 词面复现，或喻底交集 ≥2
                    shared_trig = set(chain[-1].triggers) & set(e.triggers)
                    if not (shared_trig or len(overlap) >= 2):
                        continue
                chain.append(e)

        if len(chain) < 2:
            continue

        # 合并为一条扩展超边
        all_ground = sorted(set().union(*[set(e.ground) for e in chain]))
        all_triggers = sorted(set().union(*[set(e.triggers) for e in chain]))
        all_spans: List[ChunkSpan] = [s for e in chain for s in e.chunk_spans]
        ext = MetaphorHyperedge(
            id="EXT_" + hashlib.md5(
                "|".join([str(frame_id), src, str(sorted(
                    s.chunk_id for sp in chain for s in sp.chunk_spans))])
                    .encode("utf-8")).hexdigest()[:8],
            source_domain=src,
            target_domain=chain[0].target_domain,
            ground=all_ground,
            triggers=all_triggers,
            chunk_spans=all_spans,
            cascade_id=chain[0].cascade_id,
            frame_id=frame_id,
            novelty=chain[0].novelty,
            sentiment=chain[0].sentiment,
            confidence=round(max(e.confidence for e in chain), 3),
            source_type=chain[0].source_type,
            # 溯源可靠性取链上**最弱**的一环：扩展边的可信度不会超过
            # 它最不可信的组成边（否则退化边会借合并"洗白"）。
            provenance_reliability=min(
                getattr(e, "provenance_reliability", 1.0) for e in chain),
            is_extended=True,
            layer=1.5,
        )
        merged.append(ext)
    return merged
