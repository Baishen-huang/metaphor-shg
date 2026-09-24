"""超图可达性索引 HL-index（方案 §4.5.3）。

隐喻检索本质是「触发词 → 超边 → 目标域概念」的可达性查询。HL-index 用
标签形式记录顶点以不同重叠强度可达的超边，查询时通过公共超边高效计算
最大可达性。这里给出一个轻量、可运行的实现：预计算「节点 → 可达超边」
与「超边 → 可达目标概念」的索引，查询走 O(1) 查表 + BFS 兜底。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .models import MetaphorSHG


class HLIndex:
    def __init__(self, shg: MetaphorSHG):
        self.shg = shg
        # 节点 ↔ 超边 邻接（基于 L1 喻底超边 + 触发词）
        # 触发词也是可达性起点：触发词 → 超边 → 目标域（§4.5.3）
        self.node_to_he: Dict[str, List[str]] = defaultdict(list)
        self.he_to_targets: Dict[str, List[str]] = defaultdict(list)
        for e in shg.edges:
            for n in e.member_entities:
                self.node_to_he[n].append(e.id)
            for t in e.triggers:
                self.node_to_he[t].append(e.id)
            self.he_to_targets[e.id].append(e.target_domain)
            if e.source_domain:
                self.he_to_targets[e.id].append(e.source_domain)

        # 预计算可达性索引：节点 → {可达超边}
        self.reach: Dict[str, set] = {}
        self._build()

    def _build(self):
        for node in list(self.node_to_he.keys()):
            seen = set()
            stack = list(self.node_to_he[node])
            while stack:
                he = stack.pop()
                if he in seen:
                    continue
                seen.add(he)
                # 超边的其他节点也能到达同一超边（共享超边）
                for e in self.shg.edges:
                    if e.id == he:
                        for m in e.member_entities:
                            stack.extend(self.node_to_he[m])
            self.reach[node] = seen

    def query(self, trigger: str) -> Dict[str, List[str]]:
        """触发词 → 可达的目标概念。返回 {超边id: [目标概念]}。"""
        result: Dict[str, List[str]] = {}
        for he in self.reach.get(trigger, set()):
            result[he] = self.he_to_targets.get(he, [])
        return result

    def reachable_targets(self, trigger: str) -> List[str]:
        """直接返回触发词可达的全部目标域概念（用于检索召回）。"""
        out = []
        for targets in self.query(trigger).values():
            out.extend(targets)
        return sorted(set(out))
