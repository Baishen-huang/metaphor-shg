# -*- coding: utf-8 -*-
"""探查 5：可靠性折扣为何**损害** by-construction 排序指标 + 折扣强度敏感性。

上一轮实测：人工加权 MRR@10 0.9948 → 0.8922（-0.1025）。
必须解释清楚这是「机制错了」还是「评测金标与通道前提冲突」，
并扫描折扣强度，看是否存在任何一档能带来净增益。

金标前提（evaluate_fullcorpus.build_queries）：
  Q_self 的金标 = **产出该超边的那个 chunk**。也就是说，
  一条退化（回退框架）超边所在 chunk 被金标认定为正确答案。
  ⇒ 任何对退化边的降权，都在直接惩罚金标自身。
这是评测口径与通道设计前提的**结构性冲突**，不是实现 bug。
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph import provenance
from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.llm_backend import load_table, LLMRefine
from metaphor_graph.retrieval import RetrievalEngine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cache = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
    table = load_table(cache)
    with open(cache + ".refine.json", "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None)
                  for k, v in json.load(fh)}
    backend = TrackedBackend(table, None, rtable)
    ont = make_ontology(True, os.path.join(ROOT, "metaphor_graph",
                                           "llm_ontology_train.json"))
    samples = load_ccl2018()

    from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits
    from metaphor_graph.training import train_from_shg
    from metaphor_graph.evaluate_fullcorpus import build_queries

    floors = [1.0, 0.9, 0.75, 0.5]
    agg = {f: {"trained": [0.0, 0, 0, 0], "hand": [0.0, 0, 0, 0]}
           for f in floors}
    gold_deg = gold_tot = 0

    k, n_docs = 10, (len(samples) + 9) // 10
    for di in range(n_docs):
        texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(texts, doc_id=did)
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, texts, doc_id=did, ontology=ont)
        order = {f"{did}_c{i}": i for i in range(len(texts))}
        cmap = {f"{did}_c{i}": c for i, c in enumerate(texts)}
        scorer, _ = train_from_shg(shg, chunk_order=order, chunks=cmap,
                                   ontology=ont)
        qs = build_queries(shg, ont)
        for query, gold in qs["q_ext"] + qs["q_self"]:
            gold_tot += 1
            # 金标 chunk 对应的边是否退化
            gset = set(gold)
            deg = any(provenance.edge_reliability(e, ont) < 1.0
                      for e in shg.edges
                      if any(s.chunk_id in gset for s in e.chunk_spans))
            gold_deg += bool(deg)
            for fl in floors:
                ranked = score_conditions(eng, scorer, query,
                                          reliability=True, floor=fl)
                for key, cfg in (("trained", "trained_reliab"),
                                 ("hand", "hand_weighted_reliab")):
                    m = _mrr_hits(ranked[cfg], sorted(gold))
                    a = agg[fl][key]
                    a[0] += m["mrr"]; a[1] += m["hits@3"]
                    a[2] += m["hits@10"]; a[3] += 1

    n = agg[1.0]["trained"][3]
    print("=" * 78)
    print(f"查询数 n={n}；金标 chunk 含退化边的查询 = {gold_deg} "
          f"({gold_deg/max(1,n):.1%})")
    print("\n折扣强度敏感性（floor 越小 = 折扣越狠；floor=1.0 = 通道关闭）")
    print(f"  {'floor':>6s} {'trained MRR@10':>16s} {'hand MRR@10':>13s} "
          f"{'hand Hits@3':>13s}")
    for fl in floors:
        t, h = agg[fl]["trained"], agg[fl]["hand"]
        print(f"  {fl:>6.2f} {t[0]/max(1,t[3]):>16.4f} {h[0]/max(1,h[3]):>13.4f} "
              f"{h[1]/max(1,h[3]):>13.4f}")
    print("\n⇒ 若所有 floor 档位都 ≤ floor=1.0 的基线，则不存在「调参能救」的档位，"
          "通道对该指标是纯损害（机制与金标前提冲突，非实现问题）。")


if __name__ == "__main__":
    main()
