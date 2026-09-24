# -*- coding: utf-8 -*-
"""§6.2 的 real-embedder 一行（已上报 0.707/0.758/0.755）能否离线复算？

**结论先写**：不能精确复算。data/embed_cache.json 只有 3176 条向量，
评测需要 1362 条唯一文本中有 14 条未缓存（98.97% 命中）。本机无 EMBED_API_KEY，
embed 未命中会走网络并抛异常（embeddings.embed 不做静默回退）。

因此本脚本做的是**受控近似**：
  - 用缓存里的真实 embedding-3 向量（512 维）；
  - 14 条未缓存文本回落到默认哈希编码（并在报告里显式标注）；
  - 同一近似条件下对比 OLD-CONST / BUGGY-RETR / FIXED-CAP 三种 type 编码。

为什么这个近似对**本次调查的结论**仍然有效：三种编码跑的是同一套向量、
同一份图、同一套金标，唯一变量就是 f[3]。所以编码间的**差值**是内部有效的，
即便绝对水平与已上报的 0.707 有偏。

运行：
    python experiments/exp_real_embed_replay.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph import embeddings as _emb
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.training import (build_training_set, build_weak_refine_set,
                                      MetaphorScorer)
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, _chunk_of,
                                             GEN_CACHE, JUDGE_CACHE, _load_json)
from metaphor_graph.evaluate_retrieval import _mrr_hits

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "data", "embed_cache.json")
MODES = ("old_const", "buggy_retr", "fixed_cap")


class CacheBackedEmbedder:
    """只读缓存的真实向量器；未命中回落到默认哈希编码（并计数）。"""

    def __init__(self, cache_path: str):
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.model = payload.get("model", "?")
        self._cache = payload.get("vectors", {})
        self.n_miss = 0
        self.n_hit = 0
        self.missing_texts = []

    def __call__(self, text: str):
        v = self._cache.get(text)
        if v is not None:
            self.n_hit += 1
            return list(v)
        self.n_miss += 1
        if len(self.missing_texts) < 20:
            self.missing_texts.append(text)
        return _emb.embed(text)      # 回落哈希（_EMBEDDER 已换成 self，需绕过）


def main():
    emb = CacheBackedEmbedder(CACHE_PATH)
    print(f"缓存模型 {emb.model}，向量 {len(emb._cache)} 条")
    # 注入缓存向量器（propagate=False：冻结抽取管线，与已上报口径一致）
    _emb.set_embedder(emb, propagate=False)

    ont, _ = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)
    k = 10
    n_docs = (len(samples) + k - 1) // k

    agg = defaultdict(lambda: {"mrr": 0.0, "h3": 0, "n": 0})

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                      for e in shg.edges}
        ds = build_training_set(shg, chunk_order=chunk_order, chunks=chunk_map,
                                centrality=centrality, ontology=ont,
                                positive_mode="chunk", negatives_per_positive=3)
        scorer = MetaphorScorer().fit(ds) if len(ds) > 0 else None
        if scorer is None:
            continue
        ds_w, _st = build_weak_refine_set(
            shg, chunk_order=chunk_order, chunks=chunk_map, ontology=ont,
            refine_path=os.path.join(ROOT, "data",
                                     "llm_cache_deepseek.json.refine.json"),
            negatives_per_positive=3)
        weak = MetaphorScorer().fit(ds_w) if len(ds_w) > 0 else None

        qs = filter_violations(build_queries_rich(shg, chunk_map, did),
                               gen_cache)
        for q in qs:
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {_chunk_of(e) for e in shg.edges
                           if e.id in rel and _chunk_of(e)}
            if not gold_chunks:
                continue
            cands = eng.live_edges()
            base = {m.id: eng._pair_features(q["question"], m) for m in cands}
            for mode in MODES:
                for cfg in ("hand_weighted", "trained", "trained_weak"):
                    cs = {}
                    for m in cands:
                        cid = _chunk_of(m)
                        if cid is None:
                            continue
                        f = list(base[m.id])
                        if mode == "old_const":
                            f[3] = 1.0 if m.frame_id else 0.0
                        elif mode == "buggy_retr":
                            fsp = (ont.get_frame(m.frame_id)
                                   if m.frame_id else None)
                            mt = fsp.mapping_type if fsp else m.frame_id or ""
                            f[3] = 1.0 if ont.type_valid(m.source_type, mt) else 0.0
                        else:
                            f[3] = ont.type_reliability_of(m.frame_id,
                                                           m.source_type)
                        if cfg == "hand_weighted":
                            s = (0.35 * f[0] + 0.25 * min(f[1], 1.0)
                                 + 0.20 * f[2] + 0.20 * f[3])
                        elif cfg == "trained":
                            s = scorer.score_features(f)
                        else:
                            s = weak.score_features(f) if weak else 0.0
                        cs[cid] = max(cs.get(cid, -1e9), s)
                    ranked = sorted(cs.items(), key=lambda x: -x[1])
                    met = _mrr_hits(ranked, sorted(gold_chunks))
                    a = agg[(mode, cfg)]
                    a["mrr"] += met["mrr"]
                    a["h3"] += met["hits@3"]
                    a["n"] += 1

    _emb.set_embedder(None)

    print(f"embed 调用：命中 {emb.n_hit}，未命中回落哈希 {emb.n_miss} "
          f"（命中率 {emb.n_hit / max(1, emb.n_hit + emb.n_miss):.2%}）")
    print()
    print("=" * 84)
    print("§6.2 real-embedder 行的受控近似（缓存真实向量 + 未命中回落哈希）")
    print("=" * 84)
    print(f"{'type 编码':22s} {'配置':16s} {'MRR@10':>9s} {'Hits@3':>8s} {'n':>6s}")
    for mode, label in (("old_const", "OLD-CONST 恒1.0"),
                        ("buggy_retr", "BUGGY-RETR"),
                        ("fixed_cap", "FIXED-CAP 封顶0.5")):
        for cfg in ("hand_weighted", "trained", "trained_weak"):
            a = agg[(mode, cfg)]
            if not a["n"]:
                continue
            print(f"{label:22s} {cfg:16s} {a['mrr'] / a['n']:>9.4f} "
                  f"{a['h3'] / a['n']:>8.4f} {a['n']:>6d}")
        t, hw = agg[(mode, "trained")], agg[(mode, "hand_weighted")]
        n = hw["n"]
        if n:
            print(f"{'':22s} {'训练增益 (pp)':16s} "
                  f"{(t['mrr'] - hw['mrr']) / n * 100:>+9.2f}")
        print()
    print("已上报（2026-08-30，EMBED_API_KEY 实跑，100% 缓存命中口径）：")
    print("  人工加权 0.707 ｜ 自监督 0.758 ｜ 弱监督 0.755")
    print(f"未缓存文本样例：{emb.missing_texts[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
