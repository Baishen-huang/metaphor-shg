# -*- coding: utf-8 -*-
"""fullcorpus 的 type 编码反事实：验证 A7/H5 结论翻转是否确由 type 编码引起。

evaluate_fullcorpus 的「人工加权」用的是 score_conditions 里的
  0.35*f0 + 0.25*f1 + 0.20*f2 + 0.20*f3
其中 f 来自 eng._pair_features → training.extract_features。
本脚本用同一图 / 同一查询 / 同一训练集，只替换 f[3] 的编码，复算 A7 差值。

运行：
    python experiments/exp_fullcorpus_counterfactual.py
"""
from __future__ import annotations

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
from metaphor_graph.training import train_from_shg, MetaphorScorer
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend,
                                                build_queries)
from metaphor_graph.evaluate_retrieval import _mrr_hits

MODES = ("old_const", "buggy_retr", "fixed_cap")


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
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
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        scorer, _ds = train_from_shg(shg, chunk_order=chunk_order,
                                     chunks=chunk_map, ontology=ont)
        cands = eng.live_edges()
        for query, gold in build_queries(shg, ont)["q_ext"] + \
                build_queries(shg, ont)["q_self"]:
            gold_ids = sorted(gold)
            base = {m.id: eng._pair_features(query, m) for m in cands}
            for mode in MODES:
                for cfg in ("trained", "hand_weighted"):
                    chunk_score = {}
                    for m in cands:
                        cid = None
                        for s in m.chunk_spans:
                            cid = s.chunk_id
                            break
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
                        if cfg == "trained":
                            s = scorer.score_features(f)
                        else:
                            s = (0.35 * f[0] + 0.25 * min(f[1], 1.0)
                                 + 0.20 * f[2] + 0.20 * f[3])
                        chunk_score[cid] = max(chunk_score.get(cid, -1e9), s)
                    ranked = sorted(chunk_score.items(), key=lambda x: -x[1])
                    met = _mrr_hits(ranked, gold_ids)
                    a = agg[(mode, cfg)]
                    a["mrr"] += met["mrr"]
                    a["h3"] += met["hits@3"]
                    a["n"] += 1

    print("=" * 80)
    print("fullcorpus A7 反事实（只改 f[3] 编码）")
    print("=" * 80)
    print(f"{'type 编码':22s} {'配置':16s} {'MRR@10':>9s} {'Hits@3':>8s} {'n':>6s}")
    for mode, label in (("old_const", "OLD-CONST 恒1.0"),
                        ("buggy_retr", "BUGGY-RETR"),
                        ("fixed_cap", "FIXED-CAP 封顶0.5")):
        for cfg in ("trained", "hand_weighted"):
            a = agg[(mode, cfg)]
            if not a["n"]:
                continue
            print(f"{label:22s} {cfg:16s} {a['mrr'] / a['n']:>9.4f} "
                  f"{a['h3'] / a['n']:>8.4f} {a['n']:>6d}")
        t, hw = agg[(mode, "trained")], agg[(mode, "hand_weighted")]
        n = hw["n"]
        if n:
            print(f"{'':22s} {'A7 差 (pp)':16s} "
                  f"{(t['mrr'] - hw['mrr']) / n * 100:>+9.2f}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
