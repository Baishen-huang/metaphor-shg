# -*- coding: utf-8 -*-
"""gen3 共享实验底座：把「图 → 特征 → 训练集 → 查询金标」一次性重放并缓存。

为什么要缓存：本代实验要在**同一份数据**上跑几十种处置（去维、换权、换信号、
换金标、换向量器）。若每个处置都重建图，一是慢，二是任何一处随机性都会让
处置间不可比。这里把 110 个伪文档的
    - 候选边元数据（框架/级联/喻底/支撑度/层级/级联规模/涌现计数）
    - 每个 (查询, 候选) 的 7 维特征（修复后口径 = FIXED-CAP）
    - 训练集（chunk 模式自监督 / refine 弱监督）
    - 两套金标（LLM 非构造 / by-construction）
一次性落盘成 pickle，之后所有分析都是纯 numpy。

口径声明（与 exp/source 的已上报口径逐位一致）：
    - 本体：ontology_default.json + MetaNet 种子 + 自举底座 = 2209 框架 / 758 级联
    - 伪文档：CCL2018 连续 10 句，110 个
    - 向量器：默认哈希编码（default）或 data/embed_cache.json 缓存真实向量（real）
    - type 编码：FIXED-CAP（1.0 注册 / 0.5 未注册回退 / 0.0 无归属）
    - 训练：MetaphorScorer（logistic，标准化 + BCE + 早停），npp=3
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor           # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine             # noqa: E402
from metaphor_graph.data_loader import load_ccl2018              # noqa: E402
from metaphor_graph.training import (build_training_set,         # noqa: E402
                                     build_weak_refine_set,
                                     extract_features,
                                     extract_text_features,
                                     feature_auc, MetaphorScorer,
                                     FEATURE_NAMES, TrainingSet)
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, _chunk_of,
                                             GEN_CACHE, JUDGE_CACHE, _load_json)

CACHE_DIR = os.path.join(ROOT, "experiments", "gen3")
DOC_SIZE = 10
N_DOCS = 110
SEEDS = (42, 43, 44)

# 人工加权（evaluate_retrieval.score_conditions:186-187 的硬编码）
MANUAL_W = {"sem": 0.35, "struct": 0.25, "clue": 0.20, "type": 0.20}
MANUAL_ORDER = ("sem", "struct", "clue", "type")
IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}

# 特征子集（用于处置实验：去维 / 只留人工四维）
SUBSETS = {
    "full7":            [0, 1, 2, 3, 4, 5, 6],
    "no_type":          [0, 1, 2, 4, 5, 6],
    "no_cascade":       [0, 1, 2, 3, 4, 6],
    "no_type_no_casc":  [0, 1, 2, 4, 6],
    "manual4":          [0, 1, 2, 3],
    "manual3":          [0, 1, 2],
    "manual4_nocasc":   [0, 1, 2, 3, 4, 6],
}


# --------------------------------------------------------------------- 向量器
class CacheBackedEmbedder:
    """只读缓存的真实向量器（data/embed_cache.json）；未命中**计数并抛出**。

    与 exp/source 的 exp_real_embed_replay.py 不同，这里不静默回落哈希：
    回落会让「真实句向量」这一行的口径变成混合口径。命中率必须显式报出。
    """

    def __init__(self, cache_path: str, allow_fallback: bool = False):
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.model = payload.get("model", "?")
        self._cache = payload.get("vectors", {})
        self.n_hit = 0
        self.n_miss = 0
        self.missing = []
        self.allow_fallback = allow_fallback

    def __call__(self, text: str):
        v = self._cache.get(text)
        if v is not None:
            self.n_hit += 1
            return list(v)
        self.n_miss += 1
        if len(self.missing) < 30:
            self.missing.append(text)
        if not self.allow_fallback:
            raise KeyError(f"embed 缓存未命中：{text[:40]!r}")
        from metaphor_graph import embeddings as _emb
        return _emb.embed(text)


# ------------------------------------------------------------- 候选侧替换信号
def candidate_signals(ont, m, max_support: int, max_casc: int) -> dict:
    """候选侧（candidate-side）结构信号 —— type 的同成本替代候选。

    全部只依赖「已经查过一次本体」的信息，成本与 type_reliability 同级：
      frame_support_norm  框架支撑度（本体沉淀时的高置信候选计数）对数归一
      frame_tier_core     框架层级 core(1)/longtail(0)
      frame_is_llm        是否 LLM 自举框架（非种子/手工）
      cascade_size_norm   所属级联成员框架数（对数归一）
      n_emergent          该候选经级联能触达的**新**目标/源域数（gen2 的
                          Ω_N 的候选侧类比）
      ground_len_norm     喻底集合规模（struct 已含，作对照）
    """
    spec = ont.get_frame(m.frame_id) if m.frame_id else None
    sup = spec.support if spec is not None else 0
    tier = spec.tier if spec is not None else ""
    cid = m.cascade_id
    cspec = ont.get_cascade_spec(cid) if cid else None
    n_em = 0
    if cspec:
        doms = set()
        for fid in cspec.member_frames:
            fs = ont.get_frame(fid)
            if fs is not None:
                doms.add(fs.target_domain)
                doms.add(fs.source_domain)
        doms -= {m.target_domain, m.source_domain}
        n_em = len(doms)
    return {
        "frame_support_norm": float(np.log1p(sup) / np.log1p(max(1, max_support))),
        "frame_tier_core": 1.0 if tier == "core" else 0.0,
        "frame_is_llm": 1.0 if (m.frame_id or "").startswith("F_LLM_") else 0.0,
        "cascade_size_norm": float(np.log1p(len(cspec.member_frames))
                                   / np.log1p(max(1, max_casc)))
        if cspec else 0.0,
        "n_emergent": float(n_em),
        "ground_len_norm": min(1.0, len(m.ground) / 4.0),
    }


# ------------------------------------------------------------------ 单文档重放
def _doc_record(di, samples, ont, backend, gen_cache, judge_cache, k=DOC_SIZE):
    chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
    if not chunk_texts:
        return None
    did = f"fc{di}"
    ex = MetaphorExtractor(ontology=ont, use_semfield=True, llm_backend=backend,
                           llm_conf_threshold=0.85)
    shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                             llm_backend=backend).build(chunk_texts, doc_id=did)
    l1 = [e for e in shg.edges if not e.is_extended]
    if not l1:
        return None
    eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
    chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
    chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
    centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                  for e in shg.edges}

    # ---- 训练集（chunk 模式，与 evaluate_llmgold 逐字同参）----
    ds_self = build_training_set(shg, chunk_order=chunk_order, chunks=chunk_map,
                                 centrality=centrality, ontology=ont,
                                 positive_mode="chunk", negatives_per_positive=3)
    ds_weak, weak_stats = build_weak_refine_set(
        shg, chunk_order=chunk_order, chunks=chunk_map, ontology=ont,
        refine_path=os.path.join(ROOT, "data",
                                 "llm_cache_deepseek.json.refine.json"),
        negatives_per_positive=3)

    # ---- 候选侧元数据 ----
    max_sup = max([ont.get_frame(e.frame_id).support
                   for e in l1 if ont.get_frame(e.frame_id)] or [1])
    max_casc = max([len(ont.get_cascade_spec(e.cascade_id).member_frames)
                    for e in l1 if e.cascade_id
                    and ont.get_cascade_spec(e.cascade_id)] or [1])
    cands = eng.live_edges()
    cand_meta = []
    for m in cands:
        sig = candidate_signals(ont, m, max_sup, max_casc)
        spec = ont.get_frame(m.frame_id) if m.frame_id else None
        cand_meta.append(dict(
            id=m.id, frame_id=m.frame_id or "", cascade_id=m.cascade_id or "",
            source_type=m.source_type, source_domain=m.source_domain,
            target_domain=m.target_domain, chunk_id=_chunk_of(m) or "",
            ground_len=len(m.ground), frame_support=(spec.support if spec else 0),
            frame_tier=(spec.tier if spec else ""),
            frame_registered=1.0 if spec is not None else 0.0,
            cascade_size=(len(ont.get_cascade_spec(m.cascade_id).member_frames)
                          if m.cascade_id and ont.get_cascade_spec(m.cascade_id)
                          else 0),
            **sig))
    cand_by_id = {m["id"]: m for m in cand_meta}
    SIG_KEYS = ("frame_support_norm", "frame_tier_core", "cascade_size_norm",
                "n_emergent", "frame_registered", "ground_len_norm",
                "frame_is_llm")

    def _sig_rows(ds):
        """训练集每一行的候选侧信号矩阵（按 ds.meta 的 cand id 对齐）。"""
        out = np.zeros((len(ds.meta), len(SIG_KEYS)), dtype=float)
        for r, mm in enumerate(ds.meta):
            cm = cand_by_id.get(mm["cand"])
            if cm is None:
                continue
            for j, k in enumerate(SIG_KEYS):
                out[r, j] = cm[k]
        return out

    sig_self = _sig_rows(ds_self)
    sig_weak = _sig_rows(ds_weak) if len(ds_weak.meta) else np.zeros((0, len(SIG_KEYS)))

    # ---- 查询 + 特征 ----
    qs = filter_violations(build_queries_rich(shg, chunk_map, did), gen_cache)
    queries = []
    for q in qs:
        gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
        rel = {eid for eid, v in gold_llm.items() if v == 1}
        gold_llm_chunks = sorted({_chunk_of(e) for e in shg.edges
                                  if e.id in rel and _chunk_of(e)})
        if not gold_llm_chunks:
            continue
        qedges = eng._query_edges(q["question"])
        feats = np.asarray([eng._pair_features(q["question"], m) for m in cands],
                           dtype=float)
        queries.append(dict(
            question=q["question"], kind=q["kind"],
            anchor="edge" if qedges else "text",
            gold_llm=gold_llm_chunks,
            gold_constr=sorted(q["gold"]),
            llm_agrees_producer=(q["edge"].id in rel),
            feats=feats,
            # 候选的「产出 chunk」是否就是金标（用于金标构造混杂分析）
            producer_chunk=_chunk_of(q["edge"]) or "",
            banned_triggers=list(q["edge"].triggers)))

    return dict(did=did, chunks=chunk_texts, n_cand=len(cands),
                cand_meta=cand_meta, queries=queries,
                X_self=ds_self.X, y_self=ds_self.y,
                X_weak=ds_weak.X, y_weak=ds_weak.y,
                S_self=sig_self, S_weak=sig_weak, sig_keys=list(SIG_KEYS),
                weak_stats=weak_stats, centrality=centrality,
                n_edges_total=len(shg.edges), n_l1=len(l1))


def build_cache(embedder="default", force=False, verbose=True) -> dict:
    """构建/加载 110 文档重放缓存。embedder ∈ {default, real}。"""
    path = os.path.join(CACHE_DIR, f"cache_{embedder}.pkl")
    if os.path.exists(path) and not force:
        with open(path, "rb") as f:
            return pickle.load(f)

    from metaphor_graph import embeddings as _emb
    emb_stats = None
    if embedder == "real":
        emb = CacheBackedEmbedder(os.path.join(ROOT, "data",
                                               "embed_cache.json"))
        _emb.set_embedder(emb, propagate=False)
    elif embedder == "ngram":
        _emb.set_embedder(_emb.NgramEmbedder(), propagate=False)

    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)

    docs = []
    for di in range(N_DOCS):
        rec = _doc_record(di, samples, ont, backend, gen_cache, judge_cache)
        if rec is not None:
            docs.append(rec)
        if verbose and di % 20 == 0:
            print(f"  doc {di}/{N_DOCS} …", flush=True)

    if embedder == "real":
        emb_stats = dict(model=emb.model, n_hit=emb.n_hit, n_miss=emb.n_miss,
                         missing=emb.missing[:10])
        _emb.set_embedder(None)

    payload = dict(embedder=embedder, n_frames=n_frames, docs=docs,
                   emb_stats=emb_stats,
                   n_queries=sum(len(d["queries"]) for d in docs),
                   n_pairs=sum(len(d["queries"]) * d["n_cand"] for d in docs))
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    return payload


# ------------------------------------------------------------------ 指标工具
MANUAL_W_SEQ = ((0, 0.35), (1, 0.25), (2, 0.20), (3, 0.20))


def manual_scores(feats) -> np.ndarray:
    """人工加权，**逐项顺序累加**，逐位复刻 score_conditions:186-187。

    必须顺序累加：`0.35*f0 + 0.25*min(f1,1) + 0.20*f2 + 0.20*f3` 的浮点结合序
    与 `F @ w` 不同。实测在 632 条查询里有 1 条完整排序不同，人工加权 MRR
    因此从 0.480947（顺序）变成 0.481211（numpy 点积）。
    本代的全部人工加权数字都用顺序版，才能与 exp/source 的 0.4809 逐位对齐。
    """
    out = np.empty(len(feats), dtype=float)
    for i, f in enumerate(feats):
        out[i] = (0.35 * f[0] + 0.25 * min(f[1], 1.0)
                  + 0.20 * f[2] + 0.20 * f[3])
    return out


def chunk_scores(feats, w=None, scorer=None, idx=None, zero=None) -> np.ndarray:
    """候选特征矩阵 → 每个候选的分数。

    三种用法（互斥）：
      w       人工加权：feats[:, idx] @ w
      scorer  训练后打分器（scorer 必须已按 idx 子集拟合）
      zero    训练后打分器但把指定维权重置 0（去维消融，不重训）
    """
    idx = list(range(feats.shape[1])) if idx is None else list(idx)
    if zero is not None:
        wv = np.asarray(scorer.w, dtype=float).copy()
        for j in zero:
            wv[j] = 0.0
        X = np.asarray(feats[:, idx], dtype=float)
        Xs = (X - scorer.mu) / scorer.sd
        z = Xs @ wv + scorer.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
    if scorer is not None:
        X = np.asarray(feats[:, idx], dtype=float)
        Xs = (X - scorer.mu) / scorer.sd
        z = Xs @ scorer.w + scorer.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
    return np.asarray(feats[:, idx], dtype=float) @ np.asarray(w, dtype=float)


def rank_chunks(scores, cand_meta):
    """候选分数 → chunk 排序（chunk 取最高分）。

    与 evaluate_retrieval.score_conditions:190-197 逐字同口径：候选按原顺序
    建 dict、稳定排序，并列时保持**候选顺序**（不是 cid 字典序）。这很重要——
    并列用 cid 排序会改变 MRR，处置间就不可比了。
    """
    order, best = [], {}
    for s, m in zip(scores, cand_meta):
        cid = m["chunk_id"]
        if not cid:
            continue
        if cid not in best:
            order.append(cid)
            best[cid] = float(s)
        elif s > best[cid]:
            best[cid] = float(s)
    return sorted([(c, best[c]) for c in order], key=lambda x: -x[1])


def mrr_of(ranked, gold) -> float:
    g = set(gold)
    for r, (cid, _) in enumerate(ranked, 1):
        if cid in g:
            return 1.0 / r
    return 0.0


def hits_of(ranked, gold, k) -> int:
    g = set(gold)
    return 1 if any(cid in g for cid, _ in ranked[:k]) else 0


def paired_bootstrap(a, b, n_boot=2000, seed=7):
    """配对 bootstrap：mean(a) - mean(b) 的 95% CI 与单侧 p。

    a / b 是同一批查询上的逐查询指标（配对）。返回 dict。
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    n = len(d)
    if n == 0:
        return dict(delta=float("nan"), lo=float("nan"), hi=float("nan"),
                    p=float("nan"), n=0)
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        sel = rng.integers(0, n, n)
        boots[i] = d[sel].mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    # 双侧 p（bootstrap 分布中越过 0 的尾概率 × 2，封顶 1.0）
    p_lo = float((boots <= 0).mean())
    p_hi = float((boots >= 0).mean())
    p = min(1.0, 2.0 * min(p_lo, p_hi))
    return dict(delta=float(d.mean()), lo=float(lo), hi=float(hi),
                p=float(p), n=int(n),
                n_pos=int((d > 0).sum()), n_neg=int((d < 0).sum()),
                n_tie=int((d == 0).sum()))


def auc_pairs(x, y) -> float:
    """Mann-Whitney AUC（含 0.5 计的并列）。x=正样本得分，y=负样本得分。"""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    gt = (x[:, None] > y[None, :]).mean()
    eq = (x[:, None] == y[None, :]).mean()
    return float(gt + 0.5 * eq)


def auc_ci(x, y, n_boot=1000, seed=11):
    """AUC 的 bootstrap 95% CI（对正负样本分别重采样）。"""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or len(y) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals = np.empty(n_boot)
    for i in range(n_boot):
        xi = x[rng.integers(0, len(x), len(x))]
        yi = y[rng.integers(0, len(y), len(y))]
        vals[i] = auc_pairs(xi, yi)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def eval_rows(docs, gold_key="gold_llm"):
    """把缓存摊平成 (query, doc) 列表，供纯 numpy 分析。"""
    rows = []
    for d in docs:
        for q in d["queries"]:
            rows.append((d, q))
    return rows


def pairwise_redundancy(X, names=None):
    """特征间 Spearman 秩相关 + 二值化后的重叠率（Jaccard 于 >0 集合上）。"""
    names = names or FEATURE_NAMES
    n = X.shape[1]
    rank_corr = np.full((n, n), np.nan)
    overlap = np.full((n, n), np.nan)
    # 秩
    R = np.empty_like(X, dtype=float)
    for j in range(n):
        col = X[:, j]
        order = col.argsort()
        r = np.empty(len(col))
        r[order] = np.arange(len(col))
        R[:, j] = r
    for i in range(n):
        for j in range(n):
            ri, rj = R[:, i], R[:, j]
            if ri.std() < 1e-12 or rj.std() < 1e-12:
                rank_corr[i, j] = float("nan")
            else:
                rank_corr[i, j] = float(np.corrcoef(ri, rj)[0, 1])
            bi, bj = X[:, i] > 0, X[:, j] > 0
            inter = int((bi & bj).sum())
            union = int((bi | bj).sum())
            overlap[i, j] = inter / union if union else float("nan")
    return rank_corr, overlap
