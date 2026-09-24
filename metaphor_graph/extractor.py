"""L1 隐喻抽取器（方案 §4.1.4 / §4.6 流水线第一关）。

设计原则：
  - 三通道候选 + 双阶段过滤：
      通道一 触发词命中（MIPVU-lite「语言单位切分 + 隐喻性判定」的轻量版）
      通道二 MIPVU + Wmatrix 语义域失谐（use_semfield=True，§6.5）
      通道三 **LLM 开放发现**（llm_backend.discover，不依赖触发词表，§6.6）
    过滤：① 类型安全约束；② 置信度阈值。
  - LLM 后端可插拔（详见 llm_backend.py）：
      * llm_backend：完整后端，同时提供 discover（开放发现）+ refine（细化确认）。
        discover 是突破「触发词/词表天花板」的关键通道。
      * llm_fn(text, frame)->dict：**旧接口**，仅做细化。保留以兼容既有代码；
        若同时传入 llm_backend，则 llm_backend 优先。
  - **硬门槛**：字面误判率必须 < 15%（§6.5）。类型安全约束是结构化过滤器，
    不依赖 LLM 判断，是这道门槛的主要保障。LLM 发现的全新喻体走 GENERIC 通道
    （类型护栏放行），由更高的 llm_conf_threshold 单独把关。
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Callable, List, Optional

from .models import ChunkSpan, MetaphorHyperedge
from .ontology import (CascadeOntology, DEFAULT_ONTOLOGY, FrameSpec,
                       infer_source_type)
from . import embeddings
from .llm_backend import LLMCandidate, LLMRefine, MetaphorLLMBackend

# 字面干扰词表（用于演示「字面抗干扰」测试，§6.1 第四类）
LITERAL_STOPWORDS = {
    "苹果": "水果公司名",  # "苹果发布了新手机" → 不应判为隐喻
    "水": "饮品", "火": "物理明火", "路": "物理道路",
}


class MetaphorExtractor:
    def __init__(self, ontology: CascadeOntology = None,
                 llm_fn: Optional[Callable[[str, FrameSpec], Optional[dict]]] = None,
                 conf_threshold: float = 0.35,
                 use_semfield: bool = False,
                 llm_backend: Optional[MetaphorLLMBackend] = None,
                 llm_conf_threshold: float = 0.5):
        self.ont = ontology or DEFAULT_ONTOLOGY
        self.llm_fn = llm_fn
        self.conf_threshold = conf_threshold
        self.use_semfield = use_semfield
        self.llm_backend = llm_backend
        # LLM 开放发现通道的独立置信门槛（默认比基础阈值更严，压住 P1）
        self.llm_conf_threshold = llm_conf_threshold
        # 类型约束拦截计数（观测用，见 §7.1 A1 消融）
        self._type_rejects = 0

    # ---- 工具：在文本中定位触发词，返回 (trigger, start, end) ----
    def _locate_triggers(self, text: str, triggers: List[str]):
        found = []
        for t in triggers:
            for m in re.finditer(re.escape(t), text):
                found.append((t, m.start(), m.end()))
        return found

    # ---- LLM 细化：llm_backend 优先，回退旧 llm_fn ----
    def _refine(self, chunk: str, frame: FrameSpec) -> Optional[dict]:
        """返回 {"confidence":float, "ground":List[str]}，或 None（判为非隐喻）。

        None 也用于「没有接后端」的情况——此时调用方不应把它当作否定判断。
        """
        if self.llm_backend is not None:
            r = self.llm_backend.refine(chunk, frame)
            if r is None or not r.is_metaphor:
                return None
            return {"confidence": r.confidence, "ground": list(r.ground)}
        if self.llm_fn is not None:
            return self.llm_fn(chunk, frame)
        return None

    # ---- LLM 发现的候选 → 绑定的框架（能绑则绑，绑不上走 GENERIC 通道）----
    def _frame_for_candidate(self, cand: LLMCandidate) -> FrameSpec:
        fid = self.ont.match_frame(cand.source_domain, cand.target_domain)
        if fid:
            f = self.ont.get_frame(fid)
            if f is not None and self._type_coherent(cand.source_domain, f):
                return f
        # 仅源域命中也复用其框架，让类型安全约束继续生效
        for f in self.ont.frames.values():
            if f.source_domain == cand.source_domain and \
                    self._type_coherent(cand.source_domain, f):
                return f
        # 模糊匹配：LLM 的域描述是自由文本（"水流漩涡"/"建筑结构中的承重柱"），
        # 与本体的规范标签（"水流"/"建筑"）几乎不会字符串相等。
        # 精确匹配不到就退到子串包含 —— 这是把 P2 层级覆盖率从 2.4% 拉上来的关键：
        # 匹配上正式框架 ⇒ get_cascade() 有值 ⇒ 超边归入 L3，否则会退化成临时框架。
        f_fuzzy = self._fuzzy_match_frame(cand.source_domain, cand.target_domain)
        if f_fuzzy is not None and self._type_coherent(cand.source_domain, f_fuzzy):
            return f_fuzzy
        # 三级：只要求源域子串命中（目标域作排序依据）。
        # 实测只靠「源域+目标域都命中」时 L3 覆盖率停在 62.3%（门槛 85%）——
        # 模型的域描述在目标域一侧措辞尤其自由，两侧都卡太严。
        f_src = self._fuzzy_match_frame(cand.source_domain, cand.target_domain,
                                        require_target=False)
        if f_src is not None and self._type_coherent(cand.source_domain, f_src):
            return f_src
        # 走到这里说明：精确/模糊匹配都命中了框架，但**类型不相干被筛掉**。
        # 记为一次"类型约束拦截"，用于 §7.1 A1 消融观测。
        if f_fuzzy is not None or f_src is not None:
            self._type_rejects += 1
        # 全新喻体：GENERIC 通道（已在 TYPE_CONSTRAINTS 注册，type_valid 通过）
        return FrameSpec(
            # 临时框架 id 同样确定性（builder 的既定约定：内置 hash 受
            # PYTHONHASHSEED 随机化影响，不可用于任何 id）
            id="F_LLM_" + hashlib.md5(
                f"{cand.source_domain}|{cand.target_domain}".encode("utf-8")
            ).hexdigest()[:8],
            name=f"LLM::{cand.source_domain}->{cand.target_domain}",
            mapping_type="GENERIC_VEHICLE_MAP",
            source_domain=cand.source_domain,
            target_domain=cand.target_domain,
            ground=list(cand.ground),
            triggers=list(cand.triggers),
            source_type="GENERIC_VEHICLE",
        )

    def _type_coherent(self, cand_src_domain: str, frame: FrameSpec) -> bool:
        """候选源域的推断类型 vs 框架 source_type 是否一致。

        这是类型安全约束在**开放发现通道**上真正能起作用的地方。
        模糊匹配用的是子串包含（为覆盖率），天然可能把候选绑到语义不相干的
        框架上（例如把"水流"绑到 WAR 框架）。这里用推断出的 source_type 交叉验证：
        两边都判得出类型且不一致 → 判定为错误绑定。
        任一边推断不出（GENERIC_VEHICLE）则放行 —— 信息不足时不拦。
        """
        ct = infer_source_type(cand_src_domain)
        if ct == "GENERIC_VEHICLE" or frame.source_type == "GENERIC_VEHICLE":
            return True
        return ct == frame.source_type

    def _fuzzy_match_frame(self, src: str, tgt: str,
                           require_target: bool = True) -> Optional[FrameSpec]:
        """子串包含匹配，取重叠最长者。

        require_target=False 时只要求源域命中（三级匹配），用于兜住
        模型在目标域一侧措辞过于自由的情况。

        为什么要它：LLM 返回的域描述几乎不可能与本体规范标签字符串相等
        （模型说"水流漩涡"，本体写"水流"），全靠精确匹配的话每个候选都会
        新建临时框架，L3 级联覆盖率会崩到 2.4%（实测），直接击穿 P2 门槛。

        判据：框架源域 ⊂ 候选源域 或反之；目标域同理。两侧都命中才算数，
        避免只靠一个宽松的子串把不相关的映射绑错。
        """
        best, best_len = None, 0
        for f in self.ont.frames.values():
            if not (f.source_domain and f.target_domain):
                continue
            src_hit = f.source_domain in src or src in f.source_domain
            tgt_hit = f.target_domain in tgt or tgt in f.target_domain
            if not src_hit:
                continue
            if require_target and not tgt_hit:
                continue
            # 重叠长度排序，优先选更贴切（更具体）的框架；命中两侧额外加权
            score = len(f.source_domain) + (len(f.target_domain) if tgt_hit else 0)
            if score > best_len:
                best, best_len = f, score
        return best

    def extract(self, chunk: str, doc_id: str = "doc0",
                chunk_id: str = None) -> List[MetaphorHyperedge]:
        chunk_id = chunk_id or f"{doc_id}_c{uuid.uuid4().hex[:4]}"
        edges: List[MetaphorHyperedge] = []

        def emit(frame, locs, triggers_found, conf_hint=None, skip_refine=False):
            # 阶段二（前置）：类型安全约束 —— 字面误判过滤器
            if not self.ont.type_valid(frame.source_type, frame.mapping_type):
                return None  # 类型不匹配 → 大概率字面误判，直接丢弃
            # 字面干扰特例：触发词本身就是字面用法
            if any(LITERAL_STOPWORDS.get(t) for t in triggers_found) and \
               frame.source_domain not in ("水果", "自然物"):
                return None
            # 置信度：触发词命中数 / 语义通道置信度提示
            base = conf_hint if conf_hint is not None else \
                min(1.0, 0.4 + 0.2 * len(triggers_found))
            if skip_refine:
                # LLM 开放发现通道：结论已由 discover 给出，不再二次调用 refine
                ground = list(frame.ground)
            else:
                refine = self._refine(chunk, frame)
                if refine is not None:
                    base = float(refine.get("confidence", base))
                    ground = refine.get("ground", frame.ground)
                else:
                    # refine 返回 None：可能「未接后端」，也可能「LLM 判为非隐喻」。
                    # 只有接了后端时才视为否定判断。
                    if self.llm_backend is not None or self.llm_fn is not None:
                        return None
                    ground = frame.ground
            if base < self.conf_threshold:
                return None
            sentiment = self._heuristic_sentiment(chunk)
            # 边 id 必须确定性（md5 而非 uuid4）：金标缓存、导出与本体重放
            # 都跨进程引用边 id —— 随机 id 会让缓存重放时对不上号（实测踩坑）。
            # 同一 (chunk, span, source, target) 永远得到同一 id；_dedup 保证
            # 同 (框架, 跨度) 只留一条，因此不会撞 id。
            span_key = f"{chunk_id}|{min(s for _, s, _ in locs)}|" \
                       f"{max(e for _, _, e in locs)}|{frame.source_domain}|{frame.target_domain}"
            eid = "L1_" + hashlib.md5(span_key.encode("utf-8")).hexdigest()[:8]
            return MetaphorHyperedge(
                id=eid,
                source_domain=frame.source_domain,
                target_domain=frame.target_domain,
                ground=list(ground),
                triggers=list(triggers_found),
                chunk_spans=[ChunkSpan(chunk_id=chunk_id, start=s, end=e,
                                       text=chunk[s:e], doc_id=doc_id)
                             for t, s, e in locs],
                frame_id=frame.id,
                cascade_id=self.ont.get_cascade(frame.id),
                novelty="novel" if len(triggers_found) == 1 else "conventional",
                sentiment=sentiment,
                confidence=round(base, 3),
                source_type=frame.source_type,
            )

        # 通道一：触发词匹配（现有，§4.1.4 阶段一）
        tokens = list(self.ont._trigger_index.keys())
        hit_tokens = [t for t in tokens if t in chunk]
        for frame in self.ont.match_by_triggers(hit_tokens):
            locs = self._locate_triggers(chunk, frame.triggers)
            if not locs:
                continue
            triggers_found = sorted({t for t, _, _ in locs})
            e = emit(frame, locs, triggers_found)
            if e:
                edges.append(e)

        # 通道二：MIPVU + Wmatrix 语义失谐（轻量接入，§6.5）
        # 不依赖触发词表，用 USAS 风格语义域 + 等比标记/域失谐召回喻体
        if self.use_semfield:
            from . import mipvu
            for cand in mipvu.mipvu_candidates(chunk, self.ont):
                frame = self.ont.get_frame(cand["frame_id"])
                if frame is None:
                    continue
                locs = [(cand["vehicle"], cand["start"], cand["end"])]
                e = emit(frame, locs, [cand["vehicle"]], conf_hint=cand["conf"])
                if e:
                    edges.append(e)

        # 通道三：LLM 开放发现（§6.6）—— 不依赖触发词表/语义域词表，突破召回天花板
        # 候选先绑定本体（能绑则类型护栏生效），绑不上走 GENERIC 通道，
        # 并用更严的 llm_conf_threshold 单独把关。
        if self.llm_backend is not None:
            for cand in self.llm_backend.discover(chunk):
                if cand.confidence < self.llm_conf_threshold:
                    continue
                frame = self._frame_for_candidate(cand)
                # 触发词必须能在原文中定位，否则视为「悬空候选」丢弃
                locs = self._locate_triggers(chunk, cand.triggers) if cand.triggers else []
                if not locs:
                    locs = self._locate_triggers(chunk, [cand.source_domain])
                if not locs:
                    continue
                triggers_found = list(cand.triggers) or [chunk[locs[0][1]:locs[0][2]]]
                e = emit(frame, locs, triggers_found,
                         conf_hint=cand.confidence, skip_refine=True)
                if e:
                    edges.append(e)

        return self._dedup(edges)

    @staticmethod
    def _dedup(edges: List[MetaphorHyperedge]) -> List[MetaphorHyperedge]:
        """同一 (框架, 跨度区间) 只保留一条，避免多通道重复召回。"""
        seen, out = set(), []
        for e in edges:
            if not e.chunk_spans:
                out.append(e)
                continue
            key = (e.frame_id or f"{e.source_domain}->{e.target_domain}",
                   min(s.start for s in e.chunk_spans),
                   max(s.end for s in e.chunk_spans))
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out

    @staticmethod
    def _heuristic_sentiment(text: str) -> dict:
        anxious = ["困", "压", "陷", "难", "崩", "火", "怒", "焦虑"]
        warm = ["暖", "爱", "贴心", "融化"]
        if any(w in text for w in anxious):
            return {"polarity": -0.4, "arousal": 0.7}
        if any(w in text for w in warm):
            return {"polarity": 0.5, "arousal": 0.4}
        return {"polarity": 0.0, "arousal": 0.3}

    # ---- 字面误判率评估（P1 硬门槛用，§6.5）----
    def literal_false_positive_rate(self, labeled: List[tuple]) -> float:
        """labeled: [(chunk_text, is_metaphor_bool), ...]"""
        if not labeled:
            return 0.0
        fp = sum(1 for text, is_m in labeled
                 if (not is_m) and bool(self.extract(text)))
        total_literal = sum(1 for _, is_m in labeled if not is_m)
        return fp / total_literal if total_literal else 0.0
