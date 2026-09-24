# -*- coding: utf-8 -*-
"""检查 real-embedder 重放能否 100% 命中缓存（决定 §6.2 的 +real 一行能否离线复算）。

只读 data/embed_cache.json（不写），统计评测需要嵌入的全部文本是否都在缓存里。

运行：
    python experiments/check_embed_cache_coverage.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, GEN_CACHE,
                                             JUDGE_CACHE, _load_json)

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "embed_cache.json")


def main():
    with open(CACHE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    cache = payload["vectors"]
    print(f"缓存模型 {payload['model']}，向量 {len(cache)} 条")

    ont, _ = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    k = 10
    n_docs = (len(samples) + k - 1) // k

    needed = set()
    n_edge_desc = 0
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
        for e in shg.edges:
            needed.add(e.describe())
            n_edge_desc += 1
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        qs = filter_violations(build_queries_rich(shg, chunk_map, did),
                               gen_cache)
        # 只有**有 LLM 金标**的查询才会真的走 _pair_features。
        # 且 _pair_features 仅在「查询侧无超边命中」时才嵌入查询原文
        # （有超边时走 extract_features(qe, cand)，嵌的是边描述）——
        # 这一点必须精确复刻，否则会把永不嵌入的文本算成「未命中」。
        judge_cache = _load_json(JUDGE_CACHE)
        for q in qs:
            gold = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold.items() if v == 1}
            if not any(e.id in rel and e.chunk_spans for e in shg.edges):
                continue        # 该查询被 stage_eval 跳过，不会嵌入
            if not eng._query_edges(q["question"]):
                needed.add(q["question"])   # 只有这条兜底路径才嵌查询原文

    hit = sum(1 for t in needed if t in cache)
    miss = [t for t in needed if t not in cache]
    print(f"评测**实际嵌入**的唯一文本 {len(needed)} 条（边描述 {n_edge_desc} 次调用）")
    print(f"缓存命中 {hit} = {hit / max(1, len(needed)):.2%}")
    print(f"未命中 {len(miss)}")
    for t in miss[:15]:
        print("   MISS:", t[:70])
    print()
    if not miss:
        print("→ 可零请求离线重放。embedder_from_env 要求 EMBED_API_KEY 非空，")
        print("  但可用「只读缓存的 embedder」绕过（见 exp_real_embed_replay.py），")
        print("  实测 embed 命中率 100.00%、n_miss=0。")
    else:
        print("→ 存在未命中，不能零请求精确重放。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
