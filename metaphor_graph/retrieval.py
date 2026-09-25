"""检索层（方案 A/B 共享，§4.4）。

包含四块能力：
  1. 跨域检索    —— 触发词 → 级联 → 跨域目标概念（§4.4.1）
  2. 多线索汇聚  —— 被 ≥2 个触发词支持的映射优先返回（§4.4.2）
  3. HyperRetriever 隐喻版 —— 在结构/语义/线索之外新增 type_score（§4.4.3）
  4. RRF 融合     —— 字面通路 + 隐喻通路融合

本轮补强的三处（对齐 HyperRAG，WWW 2026）：
  - **超边自然语言描述向量化**：此前直接拼接 source/target/ground 裸字段，
    语义信号很弱。改用 MetaphorHyperedge.describe() 渲染成完整句子再嵌入
    （HyperGraphRAG 的做法：超边必须渲染成自然语言才能参与向量检索）。
  - **自适应阈值**：此前固定切片 top-10 / top-60，候选不足时硬凑噪声、
    候选爆炸时又截断。改为按「每跳至少 M 条」反推阈值并按图密度分档。
  - **可训练排序器**：此前 metaphor_retriever_score 是人工加权，无训练循环。
    传入 training.MetaphorScorer 后自动切到 7 维特征的训练后打分。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from . import embeddings
from .context_budget import (AdaptiveThreshold, ContextBudget, ContextPack,
                             ThresholdDecision, graph_density)
from .models import MetaphorHyperedge, MetaphorSHG, RetrieverResult
from .ontology import CascadeOntology, DEFAULT_ONTOLOGY


def _rrf(rank_list: List[str], k: int = 60) -> Dict[str, float]:
    s: Dict[str, float] = defaultdict(float)
    for rank, cid in enumerate(rank_list):
        s[cid] += 1.0 / (k + rank + 1)
    return dict(s)


def shg_density(shg: MetaphorSHG) -> float:
    """超图密度 Δ = 总关联数 / 端点数（供自适应阈值分档）。"""
    nodes = set()
    inc = 0
    for e in shg.edges:
        ents = set(e.member_entities)
        nodes |= ents
        inc += len(ents)
    return graph_density(inc, len(nodes))


class RetrievalEngine:
    def __init__(self, shg: MetaphorSHG, chunks: List[str],
                 ontology: CascadeOntology = None, doc_id: str = "doc0",
                 scorer=None, budget: Optional[ContextBudget] = None,
                 threshold: Optional[AdaptiveThreshold] = None):
        self.shg = shg
        self.chunks = chunks
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.doc_id = doc_id
        self._chunk_text = {f"{doc_id}_c{i}": c for i, c in enumerate(chunks)}
        self._centrality = self._compute_centrality()
        # 可训练排序器（training.MetaphorScorer）；None 时回落人工加权
        self.scorer = scorer
        self.budget = budget or ContextBudget()
        self.threshold = threshold or AdaptiveThreshold()
        self.density = shg_density(shg)
        self._qe_cache: Dict[str, List[MetaphorHyperedge]] = {}
        self._cascade_vecs: Optional[Dict[str, tuple]] = None

    # ------------------------------------------------------------------ 工具
    def _compute_centrality(self) -> Dict[str, float]:
        """超边中心性：喻底规模 + 级联归属加成（用于 struct_score）。"""
        cen: Dict[str, float] = {}
        for e in self.shg.edges:
            c = 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
            cen[e.id] = c
        return cen

    def get_mappings(self, trigger: str) -> List[MetaphorHyperedge]:
        return [e for e in self.shg.edges if trigger in e.triggers]

    def live_edges(self) -> List[MetaphorHyperedge]:
        """参与检索的超边（软删除的不参与，但保留在图里供溯源）。"""
        return [e for e in self.shg.edges if not e.deprecated]

    # ----------------------------------------------------------- 1. 跨域检索
    def _cascade_index(self) -> Dict[str, tuple]:
        """级联语义索引（懒构建）：cid → (描述向量, 成员域集合)。

        供 semantic_fallback 用：查询不含任何触发词时（改写/近义表达），
        触发词级联式路径会空手而归（§7.5 实测 Recall 0.043）——此时沿
        U-Retrieval 的自顶向下思想，用查询向量对**级联描述**做粗筛，
        再回收该级联成员框架的超边 chunk。粗筛（733 级联）比逐边匹配便宜
        一个量级，也保留了「级联是检索组织层」的设计意图。
        """
        if self._cascade_vecs is not None:
            return self._cascade_vecs
        idx: Dict[str, tuple] = {}
        for cid, spec in self.ont.cascades.items():
            frame_bits = []
            domains = set()
            for fid in spec.member_frames[:8]:
                fs = self.ont.get_frame(fid)
                if fs is None:
                    continue
                frame_bits.append(f"{fs.source_domain}→{fs.target_domain}")
                domains.add(fs.source_domain)
                domains.add(fs.target_domain)
            desc = f"{spec.name}：{'；'.join(frame_bits)}"
            idx[cid] = (embeddings.embed(desc), domains)
        self._cascade_vecs = idx
        return idx

    def cross_domain_retrieve(self, query: str, top_k: int = 10,
                              adaptive: bool = True,
                              semantic_fallback: bool = False) -> RetrieverResult:
        """例：'项目推进不动' → 文档写'陷在泥潭'。

        字面/向量检索找不到，因为'推进不动'与'泥潭'在向量空间可能根本不近；
        但隐喻通路沿级联 OBSTACLE_IS_TERRAIN 命中目标域=项目困境。

        semantic_fallback=True：触发词全未命中时，退到「查询向量 vs 级联描述」
        的语义粗筛（U-Retrieval 自顶向下），专治改写/近义查询下级联通路断链
        （§7.5 实测：无回退 Recall 0.043）。默认关闭——不改变已上报行为。
        """
        tokens = [t for t in self.ont._trigger_index if t in query]
        candidates = self.ont.match_by_triggers(tokens)
        scored: List[Tuple[str, float]] = []
        agg: Dict[str, float] = defaultdict(float)
        path_nodes = set()

        for c in candidates:
            cid = self.ont.get_cascade(c.id)
            targets = {c.target_domain, c.source_domain}
            cas = self.ont.get_cascade_spec(cid) if cid else None
            if cas:
                for fid in cas.member_frames:
                    fs = self.ont.get_frame(fid)
                    if fs:
                        targets.add(fs.target_domain)
                        targets.add(fs.source_domain)
            for e in self.live_edges():
                if e.target_domain in targets or e.source_domain in targets:
                    for s in e.chunk_spans:
                        if s.chunk_id in self._chunk_text:
                            score = e.confidence + 0.3 * len(e.ground)
                            agg[s.chunk_id] += score
                            path_nodes.add(f"frame:{c.name}")
                            if cid:
                                path_nodes.add(f"cascade:{cid}")

        if not agg and semantic_fallback:
            q_vec = embeddings.embed(query)
            sims = []
            for cid, (vec, _domains) in self._cascade_index().items():
                nv = embeddings.cosine(q_vec, vec)
                if nv > 0:
                    sims.append((nv, cid))
            sims.sort(key=lambda x: -x[0])
            top_cascades = {cid for _, cid in sims[:2]}
            for e in self.live_edges():
                if e.cascade_id in top_cascades:
                    for s in e.chunk_spans:
                        if s.chunk_id in self._chunk_text:
                            agg[s.chunk_id] += e.confidence + 0.3 * len(e.ground)
                            path_nodes.add(f"cascade:{e.cascade_id}")
            if agg:
                path_nodes.add("fallback:semantic_cascade")

        if not agg:
            return RetrieverResult(chunk_ids=[], scores={}, trace="跨域检索：未命中任何隐喻通路。")

        items = list(agg.items())
        decision = None
        if adaptive:
            items, decision = self.threshold.select(items, density=self.density)
        items = items[:top_k]

        trace = (f"跨域检索：查询'{query}' 沿隐喻通路命中 {len(items)} 个 chunk"
                 f"（级联 {sorted(path_nodes)}）")
        if decision is not None:
            trace += f"；自适应阈值：{decision.note}"
        return RetrieverResult(
            chunk_ids=[c for c, _ in items],
            scores={c: s for c, s in items},
            trace=trace,
            path=sorted(path_nodes))

    # ----------------------------------------------------- 2. 多线索汇聚检索
    def multi_clue_retrieval(self, triggers: List[str],
                             threshold: float = 0.3) -> List[tuple]:
        """被 ≥2 个触发词支持的映射优先返回（§4.4.2）。"""
        candidate_scores: Dict[str, float] = defaultdict(float)
        for trig in triggers:
            for m in self.get_mappings(trig):
                candidate_scores[m.target_domain] += m.confidence
        return [(c, s) for c, s in candidate_scores.items() if s >= 2 * threshold]

    # ----------------------------------------------- 3. 隐喻版 HyperRetriever
    def _query_edges(self, query: str) -> List[MetaphorHyperedge]:
        """把文本查询映射到「查询侧超边」——即查询触发词命中的框架下的超边。

        这样训练期（超边 vs 超边）与推理期（查询 vs 超边）的特征口径才能一致：
        训练时正样本是「同一条扩展隐喻链上的两条超边」，推理时则是
        「查询触发的框架下的超边 vs 候选超边」。
        """
        if query in self._qe_cache:
            return self._qe_cache[query]
        toks = [t for t in self.ont._trigger_index if t in query]
        frames = {f.id for f in self.ont.match_by_triggers(toks)}
        qe = [e for e in self.live_edges() if e.frame_id in frames]
        if len(self._qe_cache) > 256:
            self._qe_cache.clear()
        self._qe_cache[query] = qe
        return qe

    def _text_features(self, query: str, mapping: MetaphorHyperedge) -> List[float]:
        """无框架命中时的兜底：以查询文本本身作为语义锚点。

        复用 training.extract_text_features，保证训练期与推理期口径一致
        （两处各写一份必然漂移）。
        """
        from .training import extract_text_features
        return extract_text_features(query, mapping, self._centrality, self.ont)

    def _pair_features(self, query: str, mapping: MetaphorHyperedge) -> List[float]:
        """7 维特征：查询侧超边 vs 候选超边，取「最强支持」聚合。"""
        from .training import extract_features

        qedges = self._query_edges(query)
        if not qedges:
            return self._text_features(query, mapping)
        feats = [extract_features(qe, mapping, self._centrality, self.ont)
                 for qe in qedges]
        return [max(f[i] for f in feats) for i in range(len(feats[0]))]

    def metaphor_retriever_score(self, query: str,
                                 mapping: MetaphorHyperedge) -> float:
        """相对原 HyperRetriever 唯一新增维度 type_score（结构化防污染）。

        传入训练好的 scorer 时，改走 7 维特征的学习式打分；否则回落到
        人工加权（保持向后兼容）。

        type_score 走 ontology.type_reliability_of —— 与 training.extract_features
        **同一个函数**。此前这里自己写了一份「查本体 mapping_type 再 type_valid」，
        对未注册的 F_LLM_* 回退框架会退化到用 frame_id 原串去校验（恒 False），
        于是同一候选在 training.extract_features 得 1.0、在此得 0.0（特征漂移）。
        现两路统一：注册框架 1.0 / 未注册回退框架 0.5（封顶，不丢弃）/
        无归属或非法 0.0。

        波及范围注记：本方法只被 rank_mappings / demo / 单测调用；
        §6.2 与 evaluate_fullcorpus 的排序指标走 evaluate_retrieval.score_conditions
        的共享 7 维特征，**不经过**此处的旧表达式。真正受旧表达式影响的上报指标
        是 A6（经 rank_mappings）——详见 experiments/REPORT.md §7。
        """
        if self.scorer is not None:
            return round(float(self.scorer.score_features(
                self._pair_features(query, mapping))), 4)

        # 统一到与训练路径**同一套 7 维特征** + 单一真源权重。
        #
        # 原实现走的是 4 维手写公式（0.35·sem + 0.25·struct + 0.20·clue +
        # 0.20·type），其中 type 由 `type_valid(source_type, mapping_type)` 现算。
        # `exp/source` 实测该表达式与训练路径的 `type_ok` 对未注册的 F_LLM_*
        # 边给出不同值（1.0 vs 0.0），且权重与学到权重严重错配
        # （struct 过权 49 倍、type 19 倍，`exp/typefeat`）。
        # 改用 _pair_features + hand_weighted_score 后：
        #   - 两条路径对同一候选给出同一组特征（消除口径分歧）；
        #   - 权重来自 training.HAND_WEIGHTS（按学到比例），不再手工拍定。
        feats = self._pair_features(query, mapping)
        from .training import hand_weighted_score  # 惰性导入避免循环依赖
        return round(float(hand_weighted_score(feats)), 4)
        # 注：type 维的具体取值由 training.extract_features 走
        # ontology.type_reliability_of 得到（exp/source 的封顶可靠性修复），
        # 本函数不再单独计算，故两条路径口径一致。

    def _clue_count(self, query: str, mapping: MetaphorHyperedge) -> float:
        hits = sum(1 for t in mapping.triggers if t in query)
        return min(1.0, 0.5 * hits)

    def rank_mappings(self, query: str,
                      mappings: Optional[Sequence[MetaphorHyperedge]] = None,
                      adaptive: bool = True,
                      top_k: int = 20) -> Tuple[List[MetaphorHyperedge], ThresholdDecision]:
        """对所有候选超边打分并按自适应阈值筛选（供生成前组装上下文）。"""
        pool = list(mappings if mappings is not None else self.live_edges())
        scored = [(m, self.metaphor_retriever_score(query, m)) for m in pool]
        pairs = [(m.id, s) for m, s in scored]
        if adaptive:
            kept, decision = self.threshold.select(pairs, density=self.density)
        else:
            kept, decision = sorted(pairs, key=lambda x: -x[1]), ThresholdDecision(
                0.0, len(pairs), len(pairs), 0, "off", "未启用自适应阈值")
        keep_ids = {i for i, _ in kept}
        order = {i: r for r, (i, _) in enumerate(kept)}
        ranked = sorted([m for m in pool if m.id in keep_ids],
                        key=lambda m: order.get(m.id, 10 ** 9))
        return ranked[:top_k], decision

    # ---------------------------------------------------- 4. 上下文预算打包
    def pack_context(self, mappings: Sequence[MetaphorHyperedge],
                     chunk_ids: Sequence[str]) -> ContextPack:
        """按 50/30/20 组装生成上下文（超边 / 实体 / 源文本块）。"""
        he_texts = [m.describe() for m in mappings]
        ents: List[str] = []
        for m in mappings:
            ents.extend([m.source_domain, m.target_domain])
            ents.extend(m.ground)
        chunk_texts = [self._chunk_text[c] for c in chunk_ids if c in self._chunk_text]
        return self.budget.pack(he_texts, ents, chunk_texts)

    # ----------------------------------------------------------- 5. RRF 融合
    def rrf_fusion(self, query: str, top_k: int = 10) -> RetrieverResult:
        literal = [f"{self.doc_id}_c{i}" for i, c in enumerate(self.chunks) if query in c]
        meta = self.cross_domain_retrieve(query)
        fused = defaultdict(float, _rrf(literal))
        for cid, s in _rrf(meta.chunk_ids).items():
            fused[cid] += s
        top = sorted(fused.items(), key=lambda x: -x[1])[:top_k]
        return RetrieverResult(
            chunk_ids=[c for c, _ in top],
            scores={c: s for c, _ in top},
            trace=f"RRF 融合：字面 {len(literal)} + 隐喻 {len(meta.chunk_ids)} 通路合并。",
            path=meta.path)
