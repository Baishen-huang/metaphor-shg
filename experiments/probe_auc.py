# -*- coding: utf-8 -*-
"""探查 7：可靠性通道的**判别力**审计 + 人工金标检索集上的效应。

为什么必须做
------------
by-construction 排序金标（Q_self/Q_ext）把**产出该超边的 chunk** 定为正确答案，
其中 26.6% 的金标 chunk 含退化边 —— 该指标与「惩罚退化溯源」的前提直接冲突，
所以它测出负效应并不能说明通道「没用」，只能说明**该指标不该用来评它**。

本探查换两把独立的尺子：
  R1 判别力（AUC）：把 `provenance_reliability` 当作句级「真隐喻 vs 字面」
      的打分，算 AUC。AUC ≈ 0.5 即该通道对任务**零信息**。
  R2 人工金标检索集（eval_corpus，2 文档 8 查询，人工撰写、非构造）：
      可靠性折扣开/关是否改变 Recall@10 / Hits@3 / MRR。
      这是唯一与通道前提不冲突的检索尺子。
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


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    gt = sum(1 for p in pos for n in neg if p > n)
    eq = sum(1 for p in pos for n in neg if p == n)
    return (gt + 0.5 * eq) / (len(pos) * len(neg))


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
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)

    # ---- R1 判别力 ----
    print("=" * 78)
    print("R1 判别力审计：provenance_reliability 能区分真隐喻句与字面句吗？")
    print("=" * 78)
    pos, neg = [], []
    for i, s in enumerate(samples):
        edges = ex.extract(s.text, doc_id="e", chunk_id=f"e{i}")
        if not edges:
            continue
        # 句级得分：该句所有边里最高的可靠性
        best = max(provenance.edge_reliability(e, ont) for e in edges)
        (pos if s.gold_metaphor else neg).append(best)
    print(f"  有边的隐喻句 n={len(pos)}，有边的字面句 n={len(neg)}")
    a = auc(pos, neg)
    print(f"  句级 AUC = {a:.4f}")
    print(f"  隐喻句可靠性分布：{_dist(pos)}")
    print(f"  字面句可靠性分布：{_dist(neg)}")
    print(f"  ⇒ AUC≈0.5 表示该通道对『这句是不是隐喻』**零判别力**"
          f"（与 P1 无位移一致）")

    # ---- R2 人工金标检索集 ----
    print("\n" + "=" * 78)
    print("R2 人工金标检索集（eval_corpus，非构造金标）：折扣开/关")
    print("=" * 78)
    from metaphor_graph.eval_corpus import DOCS, GOLD_RETRIEVAL
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        on = RetrievalEngine(shg, chunks, doc_id=did,
                             reliability_floor=provenance.RELIABILITY_FLOOR)
        off = RetrievalEngine(shg, chunks, doc_id=did,
                              reliability_floor=provenance.RELIABILITY_FLOOR_OFF)
        items = [(q, g) for (qd, q, g) in GOLD_RETRIEVAL if qd == did]
        agg_on = agg_off = 0.0
        for q, g in items:
            gset = {f"{did}_c{i}" for i in g}
            for eng, acc in ((on, "on"), (off, "off")):
                ids = eng.cross_domain_retrieve(q).chunk_ids[:10]
                r = len(gset & set(ids)) / len(gset) if gset else 1.0
                if acc == "on":
                    agg_on += r
                else:
                    agg_off += r
        n = max(1, len(items))
        print(f"  {did:18s} n={len(items)}  Recall@10  开={agg_on/n:.3f}  "
              f"关={agg_off/n:.3f}  差={((agg_on-agg_off)/n):+.3f}")


def _dist(xs):
    xs = sorted(xs)
    n = len(xs)
    return (f"min={xs[0]:.2f} p50={xs[n//2]:.2f} max={xs[-1]:.2f} "
            f"｜ =1.0 占比 {sum(1 for x in xs if x >= 1.0)/n:.1%}")


if __name__ == "__main__":
    main()
