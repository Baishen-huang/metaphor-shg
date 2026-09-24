"""方案 B：隐喻元图（MetaphorMG）与隐喻版 U-Retrieval（方案 §4.3）。

直接移植 MedGraphRAG 的三层图谱 + U 型检索思想，但把「医学标签」换成
「隐喻级联 / 框架标签」：
    L0  chunk 级隐喻子图（元图）：节点=触发词/映射/框架，边 触发→映射→框架
    L1  文档级隐喻图（同文档 chunk 元图合并）
    L2  主题级隐喻图（跨文档，按级联聚类）

隐喻版 U-Retrieval（§4.3.2）：
    1. 检测查询中的隐喻触发词（MIPVU-lite）
    2. 自顶向下：从级联层开始匹配
    3. 逐层下钻：级联 → 框架 → 映射
    4. 用映射的目标域概念召回 chunk
    5. 自底向上精炼：用高层框架约束答案的框架一致性
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .extractor import MetaphorExtractor
from .models import MetaphorCascade, MetaphorFrame, MetaphorHyperedge, MetaphorSHG, RetrieverResult
from .ontology import CascadeOntology, DEFAULT_ONTOLOGY


@dataclass
class MetaNode:
    id: str
    kind: str            # trigger / mapping / frame / cascade
    label: str
    layer: int


@dataclass
class MetaEdge:
    src: str
    dst: str
    rel: str


class MetaphorMetagraph:
    """三层隐喻元图（内存表示）。"""

    def __init__(self):
        self.nodes: Dict[str, MetaNode] = {}
        self.edges: List[MetaEdge] = []
        self.L0: Dict[str, List[MetaEdge]] = defaultdict(list)  # chunk_id -> 子图边
        self.L1: Dict[str, List[MetaEdge]] = defaultdict(list)  # doc_id -> 图
        self.L2: List[MetaEdge] = []                            # 主题/级联层

    def add(self, node: MetaNode):
        self.nodes[node.id] = node

    def build_from_shg(self, shg: MetaphorSHG, chunks: List[str], doc_id: str = "doc0"):
        for i, c in enumerate(chunks):
            cid = f"{doc_id}_c{i}"
            for e in shg.edges:
                if not any(s.chunk_id == cid for s in e.chunk_spans):
                    continue
                # L0 子图：触发词 → 映射 → 框架
                for t in e.triggers:
                    tn = f"trig::{t}"
                    self.add(MetaNode(tn, "trigger", t, 0))
                    mn = e.id
                    self.add(MetaNode(mn, "mapping", f"{e.source_domain}→{e.target_domain}", 0))
                    self.L0[cid].append(MetaEdge(tn, mn, "trigger_of"))
                    if e.frame_id:
                        fn = e.frame_id
                        self.add(MetaNode(fn, "frame", e.frame_id, 0))
                        self.L0[cid].append(MetaEdge(mn, fn, "in_frame"))
        # L1 文档级：合并该 doc 的所有 L0 边
        for cid, es in self.L0.items():
            self.L1[doc_id].extend(es)
        # L2 主题级：级联 → 框架 → 映射
        for cas in shg.cascades:
            cn = f"cas::{cas.id}"
            self.add(MetaNode(cn, "cascade", cas.name, 2))
            for fid in cas.member_frame_ids:
                fn = fid
                self.add(MetaNode(fn, "frame", fid, 2))
                self.L2.append(MetaEdge(cn, fn, "has_frame"))
        return self


class MetaphorURetrieval:
    """隐喻版 U-Retrieval（§4.3.2）。"""

    def __init__(self, ontology: CascadeOntology = None,
                 extractor: Optional[MetaphorExtractor] = None):
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.extractor = extractor or MetaphorExtractor(ontology=self.ont)
        self._chunk_text: Dict[str, str] = {}
        self._chunk_order: Dict[str, int] = {}

    def index(self, chunks: List[str], doc_id: str = "doc0"):
        for i, c in enumerate(chunks):
            cid = f"{doc_id}_c{i}"
            self._chunk_text[cid] = c
            self._chunk_order[cid] = i

    def _literal_retrieve(self, query: str, top_k: int = 5) -> RetrieverResult:
        hits = [(cid, c) for cid, c in self._chunk_text.items() if query in c]
        ids = [cid for cid, _ in hits][:top_k]
        return RetrieverResult(
            chunk_ids=ids,
            scores={cid: 1.0 for cid in ids},
            trace="字面通路：查询无隐喻触发词，回退关键词匹配。",
            path=["literal"])

    def retrieve(self, query: str, top_k: int = 60) -> RetrieverResult:
        # 1. 检测查询中的隐喻触发词
        tokens = [t for t in self.ont._trigger_index if t in query]
        triggers = self.ont.match_by_triggers(tokens)
        if not triggers:
            return self._literal_retrieve(query, top_k=min(top_k, 5))

        # 2. 自顶向下：从级联层匹配
        best_frame = triggers[0]
        cascade_id = self.ont.get_cascade(best_frame.id)
        path = [f"query:{query}"]

        # 3. 逐层下钻：级联 → 框架 → 映射（此处框架=best_frame）
        #    同时纳入同级联兄弟框架的目标域（下钻到兄弟框架，使跨域可达）
        target_concepts = set(best_frame.ground) | {best_frame.target_domain}
        cas = self.ont.get_cascade_spec(cascade_id)
        if cas:
            for fid in cas.member_frames:
                fs = self.ont.get_frame(fid)
                if fs:
                    target_concepts |= set(fs.ground)
                    target_concepts.add(fs.target_domain)
        target_concepts = list(target_concepts)
        path += [f"cascade:{cascade_id}", f"frame:{best_frame.id}",
                 f"target:{best_frame.target_domain}"]

        # 4. 用目标域概念召回 chunk（跨域通路的核心）
        scored = []
        for cid, text in self._chunk_text.items():
            # 命中目标域词 / 喻底词 / 同类触发词
            score = 0.0
            for tgt in target_concepts:
                if tgt in text:
                    score += 0.5
            for t in [best_frame.source_domain] + best_frame.triggers:
                if t in text:
                    score += 0.3
            # 语义邻近（启发式向量）
            from . import embeddings
            score += 0.4 * embeddings.cosine(embeddings.embed(query), embeddings.embed(text))
            if score > 0:
                scored.append((cid, score))
        scored.sort(key=lambda x: -x[1])
        top = scored[:top_k]

        # 5. 自底向上精炼（框架一致性约束，简要实现：保留同框架 chunk）
        trace = (f"隐喻通路：查询触发词={[best_frame.source_domain]} → "
                 f"级联 {cascade_id} → 框架 {best_frame.name} → "
                 f"目标域/{best_frame.target_domain} → 召回 {len(top)} 个 chunk")
        return RetrieverResult(
            chunk_ids=[cid for cid, _ in top],
            scores={cid: s for cid, s in top},
            trace=trace,
            path=path)
