"""方案 A 构建器：L1 → L2 → L3（方案 §4.1.4）。

核心改进：用 cascade 本体「查表」替代 embedding 聚类 + LLM 逐组验证。
成本对比（每 1000 条 L1 超边）：
    embedding 聚类 + LLM 验证：~200 次 LLM 调用
    本方案（cascade 查表）：~20 次（仅未匹配项回退 LLM 聚类）
"""

from __future__ import annotations

import hashlib
import logging  # 稳定 id：内置 hash 受 PYTHONHASHSEED 随机化影响，不可用于本体 id
import uuid
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from .extended import link_extended_metaphors
from .extractor import MetaphorExtractor
from .models import MetaphorCascade, MetaphorFrame, MetaphorHyperedge, MetaphorSHG
from .ontology import CascadeOntology, DEFAULT_ONTOLOGY
from .llm_backend import MetaphorLLMBackend


class MetaphorSHGBuilder:
    def __init__(self, ontology: CascadeOntology = None,
                 extractor: Optional[MetaphorExtractor] = None,
                 llm_cluster_fn: Optional[Callable[[List[MetaphorHyperedge]], dict]] = None,
                 llm_backend: Optional["MetaphorLLMBackend"] = None,
                 use_extended: bool = True,
                 extended_continuity: str = "ground1",
                 llm_verify_extended: bool = False,
                 verify_cache_path: Optional[str] = None):
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.llm_verify_extended = llm_verify_extended
        self.verify_cache_path = verify_cache_path
        self.llm_backend = llm_backend
        # 未显式传入 extractor 时，把 LLM 后端透传下去（discover + refine 通道生效）
        self.extractor = extractor or MetaphorExtractor(ontology=self.ont,
                                                        llm_backend=self.llm_backend)
        self.llm_cluster_fn = llm_cluster_fn
        # A5 消融开关：关闭后不生成跨 chunk 扩展超边（§4.2 / §6.3）
        self.use_extended = use_extended
        # L1.5 延续性判据（连贯文档质量评审后新增，README §7.3）：
        # ground1=原口径（喻底交集≥1）；vehicle_repeat=触发词跨 chunk 词面复现或喻底交集≥2
        self.extended_continuity = extended_continuity

    def build(self, chunks: List[str], doc_id: str = "doc0") -> MetaphorSHG:
        # ---- L1 抽取（每个 chunk 一次）----
        all_edges: List[MetaphorHyperedge] = []
        chunk_order: Dict[str, int] = {}
        for i, c in enumerate(chunks):
            cid = f"{doc_id}_c{i}"
            chunk_order[cid] = i
            edges = self.extractor.extract(c, doc_id=doc_id, chunk_id=cid)
            all_edges.extend(edges)

        # ---- L1.5 扩展隐喻链接 ----
        ext_edges = link_extended_metaphors(all_edges, chunk_order,
                                            continuity=self.extended_continuity) if self.use_extended \
            else []
        all_edges.extend(ext_edges)

        # ---- L1.5b 语义校验（可选，延续性判据的语义级方案）----
        # LLM 逐链判定「跨段延续」，剔除未通过链。校验缺失（批次失败不写缓存）
        # 的链按未校验剔除 —— 严格口径优先（§7.2：失败必须可见，缓存缺失可重跑）。
        if self.llm_verify_extended and self.llm_backend is not None and ext_edges:
            from .llm_backend import verify_chains_batch
            vchains = []
            for e in ext_edges:
                idxs = sorted({int(s.chunk_id.split("_c")[-1])
                               for s in e.chunk_spans})
                texts = [chunks[i] for i in idxs if 0 <= i < len(chunks)]
                vchains.append(dict(
                    key=f"{doc_id}|{e.source_domain}|{'、'.join(sorted(e.ground)[:4])}",
                    doc_title=doc_id, source=e.source_domain,
                    target=e.target_domain, ground=list(e.ground), texts=texts))
            vres = verify_chains_batch(self.llm_backend, vchains, 8, True,
                                       self.verify_cache_path)
            kept, dropped = [], 0
            for e in ext_edges:
                key = f"{doc_id}|{e.source_domain}|{'、'.join(sorted(e.ground)[:4])}"
                if vres.get(key):
                    kept.append(e)
                else:
                    dropped += 1
            for e in kept:
                if e in all_edges:
                    pass
            dropped_ids = {e.id for e in ext_edges if e not in kept}
            all_edges = [e for e in all_edges if e.id not in dropped_ids]
            logger = logging.getLogger(__name__)
            logger.info("L1.5 语义校验: 候选 %d 条, 保留 %d 条, 剔除 %d 条",
                        len(ext_edges), len(kept), dropped)

        # ---- L2：按框架归属（查表，非聚类）----
        frames_by_id: Dict[str, List[MetaphorHyperedge]] = defaultdict(list)
        for e in all_edges:
            if e.frame_id:
                frames_by_id[e.frame_id].append(e)

        frame_objs: List[MetaphorFrame] = []
        for fid, member_edges in frames_by_id.items():
            spec = self.ont.get_frame(fid)
            frame_objs.append(MetaphorFrame(
                id=fid,
                name=spec.name if spec else fid,
                member_mapping_ids=[e.id for e in member_edges],
                source_frame=spec.source_frame if spec else "",
                target_frame=spec.target_frame if spec else "",
            ))

        # ---- L3：按级联归属（同样是查表）----
        cascades_by_id: Dict[str, List[str]] = defaultdict(list)
        for f in frame_objs:
            # 该 frame 对应的 cascade —— 取其任一成员超边的 cascade_id
            spec = self.ont.get_frame(f.id)
            cid = self.ont.get_cascade(f.id) if spec else None
            if cid:
                cascades_by_id[cid].append(f.id)

        cascade_objs: List[MetaphorCascade] = []
        for cid, frame_ids in cascades_by_id.items():
            spec = self.ont.get_cascade_spec(cid)
            cascade_objs.append(MetaphorCascade(
                id=cid,
                name=spec.name if spec else cid,
                member_frame_ids=frame_ids,
                discourse_domains=spec.discourse_domains if spec else [],
                typical_triggers=spec.typical_triggers if spec else [],
            ))

        # ---- 未匹配项回退 LLM 聚类（少量）----
        unmatched = [e for e in all_edges if not e.frame_id]
        if unmatched and (self.llm_cluster_fn or self.llm_backend):
            self._llm_cluster_fallback(unmatched, frame_objs, cascade_objs)

        # ---- 保证「用了的框架都挂到某个级联」----
        self._ensure_cascades(all_edges, frame_objs, cascade_objs)

        return MetaphorSHG(edges=all_edges, frames=frame_objs, cascades=cascade_objs)

    def _ensure_cascades(self, all_edges, frame_objs, cascade_objs):
        """给「不属于任何级联」的孤儿框架补上 L3 归属。

        为什么需要：LLM 开放发现遇到本体没有的新喻体时，抽取器会临时建一个
        `F_LLM_*` 框架（这是开放发现换召回的代价）。这些框架不在本体里，
        `get_cascade()` 恒为 None —— 实测 L3 覆盖率因此卡在 67%（P2 门槛 85%）。

        规则：按 **目标域** 把孤儿框架打包成级联。这与 cascade 理论一致
        （级联是「围绕同一目标概念组织、共同出现的映射集合」），
        也与 `llm_ontology` 构成本体级联时用的规则一致。

        id 用 md5 而非内置 hash —— 后者受 PYTHONHASHSEED 随机化影响，
        会导致同一份语料每次构建的级联 id 都不同，本体无法复现。
        """
        covered = {fid for c in cascade_objs for fid in c.member_frame_ids}
        orphans = [f for f in frame_objs if f.id not in covered]
        if not orphans:
            return

        edges_by_frame: Dict[str, List[MetaphorHyperedge]] = defaultdict(list)
        for e in all_edges:
            if e.frame_id:
                edges_by_frame[e.frame_id].append(e)

        groups: Dict[str, List[str]] = defaultdict(list)
        for f in orphans:
            mem = edges_by_frame.get(f.id) or []
            tgt = mem[0].target_domain if mem else "未标注"
            groups[tgt].append(f.id)

        for tgt, fids in groups.items():
            cid = "C_ADHOC_" + hashlib.md5(tgt.encode("utf-8")).hexdigest()[:8]
            # 已存在同 id 级联则合并，避免重复
            existing = next((c for c in cascade_objs if c.id == cid), None)
            if existing:
                merged = sorted(set(existing.member_frame_ids) | set(fids))
                existing.member_frame_ids = merged
            else:
                cascade_objs.append(MetaphorCascade(
                    id=cid,
                    name=f"AD_HOC::{tgt}",
                    member_frame_ids=sorted(fids),
                    discourse_domains=[tgt],
                    typical_triggers=[],
                ))

    def _llm_cluster_fallback(self, unmatched: List[MetaphorHyperedge],
                              frame_objs, cascade_objs):
        """仅对未匹配项做 LLM 聚类（~20 次/1000 条），结果回流本体。"""
        # 演示实现：按 source_domain 简单分组为「新框架」
        groups: Dict[str, List[MetaphorHyperedge]] = defaultdict(list)
        for e in unmatched:
            groups[e.source_domain].append(e)
        for src, edges in groups.items():
            fid = f"F_NOVEL_{uuid.uuid4().hex[:6]}"
            # 若接了 LLM 后端，优先用它给新框架命名（真实场景：命名 + 归属级联）
            name = f"NOVEL::{src}"
            if self.llm_backend is not None:
                suggestion = self.llm_backend.cluster(edges) or {}
                name = suggestion.get("frame_name", name)
            frame_objs.append(MetaphorFrame(
                id=fid, name=name, member_mapping_ids=[e.id for e in edges]))
            if self.llm_cluster_fn:
                self.llm_cluster_fn(edges)  # 旧接口：调用 LLM 命名+归属级联
