# -*- coding: utf-8 -*-
"""A6 敏感性检查：A6 是唯一真正调用 retrieval.py:250 buggy 表达式的已上报指标。
它是否对本次修复敏感？

A6 用 rank_mappings(adaptive=False, top_k=5) 取前 5 条超边，再把这些超边的
chunk 并集当作「隐喻通路」的召回。本脚本对同一图比较修复前/后的 top-5 集合。

运行：
    python experiments/probe_a6_sensitivity.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import (build_queries_rich, _chunk_of,
                                             GEN_CACHE, JUDGE_CACHE, _load_json)


def buggy_type(eng, m):
    fspec = eng.ont.get_frame(m.frame_id) if m.frame_id else None
    mtype = fspec.mapping_type if fspec else m.frame_id or ""
    return 1.0 if eng.ont.type_valid(m.source_type, mtype) else 0.0


def score_with(mode, eng, m, query):
    """复刻 metaphor_retriever_score 的人工加权分支，只换 type 编码。"""
    from metaphor_graph import embeddings
    from metaphor_graph.training import extract_text_features
    f = extract_text_features(query, m, eng._centrality, eng.ont)
    if mode == "old":          # 修复前 training 侧口径（恒 1.0）
        t = 1.0 if m.frame_id else 0.0
    elif mode == "buggy":      # 修复前 retrieval 侧口径
        t = buggy_type(eng, m)
    else:                      # 修复后
        t = eng.ont.type_reliability_of(m.frame_id, m.source_type)
    return round(0.35 * f[0] + 0.25 * min(f[1], 1.0) + 0.20 * f[2] + 0.20 * t, 4)


def main():
    ont, _ = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)

    by_doc = defaultdict(list)
    for i, smp in enumerate(samples):
        by_doc[f"fc{i // 10}"].append(smp)

    n_q = 0
    top5_changed = 0
    recall_changed = 0
    rec = {"old": 0.0, "buggy": 0.0, "fixed": 0.0}
    h3 = {"old": 0, "buggy": 0, "fixed": 0}

    for did, ss in sorted(by_doc.items()):
        chunk_texts = [x.text for x in ss]
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        for q in build_queries_rich(shg, chunk_map, did):
            text = gen_cache.get(f"{did}|{q['query']}", "")
            if not text:
                continue
            gold_llm = judge_cache.get(f"{did}|{text}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {c for e in shg.edges if e.id in rel
                           for c in {s.chunk_id for s in e.chunk_spans}}
            if not gold_chunks:
                continue
            n_q += 1
            pool = eng.live_edges()
            top5 = {}
            ranked_chunks = {}
            for mode in ("old", "buggy", "fixed"):
                scored = sorted(pool,
                                key=lambda m: -score_with(mode, eng, m, text))
                top5[mode] = [m.id for m in scored[:5]]
                seen = []
                for m in scored[:5]:
                    for s in m.chunk_spans:
                        if s.chunk_id not in seen:
                            seen.append(s.chunk_id)
                ranked_chunks[mode] = seen
                top = set(seen[:10])
                rec[mode] += len(gold_chunks & top) / len(gold_chunks)
                h3[mode] += 1 if any(c in gold_chunks for c in seen[:3]) else 0
            if top5["old"] != top5["fixed"] or top5["buggy"] != top5["fixed"]:
                top5_changed += 1
            if ranked_chunks["old"] != ranked_chunks["fixed"] or \
                    ranked_chunks["buggy"] != ranked_chunks["fixed"]:
                recall_changed += 1

    print("=" * 78)
    print("A6 敏感性（n=%d 改写查询；top_k=5，metric = 前5条边的 chunk 并集）"
          % n_q)
    print("=" * 78)
    print(f"top-5 集合发生变化的查询数      : {top5_changed} "
          f"= {top5_changed / max(1, n_q):.1%}")
    print(f"chunk 并集顺序发生变化的查询数  : {recall_changed} "
          f"= {recall_changed / max(1, n_q):.1%}")
    print()
    print(f"{'type 编码':22s} {'Recall@10':>10s} {'Hits@3':>8s}")
    for mode, label in (("old", "OLD-CONST 恒1.0"),
                        ("buggy", "BUGGY-RETR (retrieval)"),
                        ("fixed", "FIXED-CAP 封顶0.5")):
        print(f"{label:22s} {rec[mode] / max(1, n_q):>10.4f} "
              f"{h3[mode] / max(1, n_q):>8.4f}")
    print()
    print("对照已上报 A6 数字：隐喻通路 Recall@10=0.783 Hits@3=0.601")
    print("→ A6 用的是 rank_mappings 的人工加权分支（无 scorer），是本次修复")
    print("  唯一真正触及的已上报指标。差异见上表。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
