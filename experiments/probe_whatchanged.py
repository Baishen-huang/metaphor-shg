# -*- coding: utf-8 -*-
"""探查 8：可靠性折扣**到底改变了什么**（排序序列 vs 金标名次）。

上一轮发现一个反直觉现象：训练路径 MRR@10 差 +0.0000，但排序序列被改动 37.7%。
必须把「改变了排序」与「改变了金标名次」分开测，否则会误读成「通道无效」。

本脚本同时测：
  - 排序序列被改变的比例；
  - **金标名次**被改变的比例（真正决定 MRR）；
  - top-1 正确性翻转数；
  - **头部空间**：金标本来就不是 top-1 的查询有多少条。
    若该数接近 0，则该指标已饱和，任何改动都无法在此指标上体现。
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.llm_backend import load_table, LLMRefine
from metaphor_graph.retrieval import RetrievalEngine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS = (("trained", "trained_reliab"), ("hand_weighted", "hand_weighted_reliab"))


def main():
    cache = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
    table = load_table(cache)
    with open(cache + ".refine.json", "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None)
                  for k, v in json.load(fh)}
    backend = TrackedBackend(table, None, rtable)
    ont = make_ontology(True, os.path.join(ROOT, "metaphor_graph",
                                           "llm_ontology_train.json"))
    from metaphor_graph.evaluate_retrieval import score_conditions
    from metaphor_graph.training import train_from_shg, feature_auc
    from metaphor_graph.evaluate_fullcorpus import build_queries

    samples = load_ccl2018()
    k = 10
    seq = {b: 0 for b, _ in PAIRS}
    gold_rank = {b: 0 for b, _ in PAIRS}
    top1 = {b: 0 for b, _ in PAIRS}
    headroom = {b: 0 for b, _ in PAIRS}
    tot = 0
    wsum = {}; aucs = {"clue": [], "struct": [], "sem": []}; ndoc = 0

    for di in range((len(samples) + k - 1) // k):
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
        sc, ds = train_from_shg(shg, chunk_order=order, chunks=cmap, ontology=ont)
        ndoc += 1
        for kk, vv in sc.weights().items():
            wsum[kk] = wsum.get(kk, 0.0) + vv
        a = feature_auc(ds)
        for kk in aucs:
            if a.get(kk) == a.get(kk):
                aucs[kk].append(a[kk])

        for q, g in build_queries(shg, ont)["q_self"]:
            r = score_conditions(eng, sc, q, reliability=True)
            tot += 1
            gs = set(g)

            def first(ranked):
                for i, (cid, _) in enumerate(ranked, 1):
                    if cid in gs:
                        return i
                return None

            for base, rel in PAIRS:
                if [x[0] for x in r[base]] != [x[0] for x in r[rel]]:
                    seq[base] += 1
                f1, f2 = first(r[base]), first(r[rel])
                if f1 != f2:
                    gold_rank[base] += 1
                if (r[base][0][0] in gs) != (r[rel][0][0] in gs):
                    top1[base] += 1
                if f1 != 1:
                    headroom[base] += 1

    print("=" * 78)
    print(f"查询数 n={tot}；参与训练/建图的伪文档 {ndoc} 个")
    print("=" * 78)
    print(f"  平均训练权重：{ {kk: round(v/ndoc,4) for kk,v in wsum.items()} }")
    print(f"  平均单特征 AUC："
          f"{ {kk: round(sum(v)/len(v),3) for kk,v in aucs.items() if v} }")
    print(f"\n  {'路径':>14s} {'排序序列改变':>13s} {'金标名次改变':>13s} "
          f"{'top-1翻转':>10s} {'金标非top-1(头部空间)':>20s}")
    for base, _ in PAIRS:
        print(f"  {base:>14s} {seq[base]:>6d}({seq[base]/tot:>5.1%}) "
              f"{gold_rank[base]:>6d}({gold_rank[base]/tot:>5.1%}) "
              f"{top1[base]:>10d} {headroom[base]:>20d}")
    print("\n  ⇒ 若某路径『排序序列改变』远大于『金标名次改变』，"
          "说明折扣只动了尾部、没咬到头部（指标饱和）。")
    print("  ⇒ 『金标非 top-1』= 头部空间；接近 0 表示该指标已无改善余地。")


if __name__ == "__main__":
    main()
