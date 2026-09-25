# -*- coding: utf-8 -*-
"""训练后的 type 权重：验证「训练路径把有害的 type 信号权重压低」这一机制。

若修复后 type 与金标负相关，训练器应学到接近 0（或负）的 type 权重，
而人工加权硬编码 0.20 → 训练相对人工加权的优势被放大。

运行：
    python experiments/probe_learned_type_weight.py
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.training import (train_from_shg, feature_auc,
                                     leakage_report, FEATURE_NAMES)
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)


def main():
    ont, _ = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    from collections import defaultdict
    import numpy as np
    ws = defaultdict(list)
    aucs = defaultdict(list)

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
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        scorer, ds = train_from_shg(shg, chunk_order=chunk_order,
                                    chunks=chunk_map, ontology=ont)
        if len(ds) == 0:
            continue
        w = scorer.weights()
        for name in FEATURE_NAMES:
            ws[name].append(w[name])
        for name, v in feature_auc(ds).items():
            if v == v:
                aucs[name].append(v)

    print("=" * 78)
    print("训练后 7 维权重（110 个伪文档的均值 / 标准差）")
    print("=" * 78)
    print(f"{'特征':18s} {'权重均值':>10s} {'权重标准差':>12s} {'单特征AUC均值':>14s}")
    for name in FEATURE_NAMES:
        w = ws[name]
        a = aucs[name]
        print(f"{name:18s} {np.mean(w):>10.4f} {np.std(w):>12.4f} "
              f"{(np.mean(a) if a else float('nan')):>14.4f}")
    print()
    print("对照：人工加权固定权重 sem=0.35 struct=0.25 clue=0.20 type=0.20，")
    print("      角色特征固定 0.0（§6.2 的 hand_weighted 公式只取前 4 维）。")
    tw = np.mean(ws["type"])
    print(f"→ 学到的 type 权重均值 = {tw:+.4f}")
    if tw < 0.05:
        print("  训练器基本忽略/压低 type —— 与「type 在基准上与金标负相关」一致。")
        print("  人工加权却硬给它 0.20 → 结构性吃亏，这就是 A7 翻转的机制。")
    else:
        print("  训练器仍给 type 可观权重，需另找机制解释 A7 翻转。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
