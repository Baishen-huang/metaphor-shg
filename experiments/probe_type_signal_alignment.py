# -*- coding: utf-8 -*-
"""机制探针：type 变成可区分信号后，它到底在奖励还是惩罚金标？

修复前 type ≡ 1.0（常数，对排序无影响）；修复后 type ∈ {1.0, 0.5, 0.0}。
若金标边里「未注册回退框架」占比高于非金标，则这个信号在**惩罚金标**——
那它就是一个有害信号，人工加权（固定 0.20 权重）会被它拖累，
而训练路径可以学到更小的权重（或不依赖它）。

统计：
  ① 全图 L1 边中金标 vs 非金标 的 frame 构成
  ② §6.2 每个查询下，金标 chunk 与非金标 chunk 的 type 均值
  ③ fullcorpus 的 Q_self 查询下同样对比

运行：
    python experiments/probe_type_signal_alignment.py
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
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend,
                                                build_queries)
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, _chunk_of,
                                             GEN_CACHE, JUDGE_CACHE, _load_json)


def frame_kind(ont, fid):
    if not fid:
        return "no_frame"
    if ont.get_frame(fid) is None:
        return "fallback_unreg"
    return "registered"


def main():
    ont, _ = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)
    k = 10
    n_docs = (len(samples) + k - 1) // k

    # ① 图级：金标边 vs 非金标边的 frame 构成（§6.2 口径）
    gold_kind = defaultdict(int)
    nongold_kind = defaultdict(int)
    # ② chunk 级 type 均值对比（§6.2）
    gold_type_mean = []
    nongold_type_mean = []
    # ③ fullcorpus Q_self 口径
    fc_gold_kind = defaultdict(int)
    fc_nongold_kind = defaultdict(int)

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
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}

        # ---- §6.2 ----
        qs = filter_violations(build_queries_rich(shg, chunk_map, did),
                               gen_cache)
        for q in qs:
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {_chunk_of(e) for e in shg.edges
                           if e.id in rel and _chunk_of(e)}
            if not gold_chunks:
                continue
            gv, nv = [], []
            for m in eng.live_edges():
                t = ont.type_reliability_of(m.frame_id, m.source_type)
                is_gold = _chunk_of(m) in gold_chunks
                if is_gold:
                    gv.append(t)
                    gold_kind[frame_kind(ont, m.frame_id)] += 1
                else:
                    nv.append(t)
                    nongold_kind[frame_kind(ont, m.frame_id)] += 1
            if gv:
                gold_type_mean.append(sum(gv) / len(gv))
            if nv:
                nongold_type_mean.append(sum(nv) / len(nv))

        # ---- fullcorpus Q_self ----
        for query, gold in build_queries(shg, ont)["q_self"]:
            gold_ids = sorted(gold)
            for m in eng.live_edges():
                cid = None
                for s in m.chunk_spans:
                    cid = s.chunk_id
                    break
                kd = frame_kind(ont, m.frame_id)
                if cid in gold_ids:
                    fc_gold_kind[kd] += 1
                else:
                    fc_nongold_kind[kd] += 1

    def show(name, gold, nongold):
        tg = sum(gold.values())
        tn = sum(nongold.values())
        print(f"\n【{name}】")
        print(f"{'frame 类别':18s} {'金标边占比':>12s} {'非金标边占比':>14s}")
        for kd in ("registered", "fallback_unreg", "no_frame"):
            pg = gold.get(kd, 0) / max(1, tg)
            pn = nongold.get(kd, 0) / max(1, tn)
            print(f"{kd:18s} {pg:>11.1%} {pn:>13.1%}")
        print(f"{'(总数)':18s} {tg:>11d} {tn:>13d}")

    print("=" * 80)
    print("type 信号与金标的一致性（修复后编码：注册1.0/未注册0.5/无归属0.0）")
    print("=" * 80)
    show("§6.2 LLM 金标（候选边按 chunk 是否金标分组）", gold_kind, nongold_kind)
    show("fullcorpus Q_self（by-construction 金标）", fc_gold_kind, fc_nongold_kind)

    if gold_type_mean and nongold_type_mean:
        gm = sum(gold_type_mean) / len(gold_type_mean)
        nm = sum(nongold_type_mean) / len(nongold_type_mean)
        print(f"\n§6.2 每查询的 type 均值：金标候选 {gm:.4f}  vs  "
              f"非金标候选 {nm:.4f}  差 {gm - nm:+.4f}")
        better = sum(1 for a, b in zip(gold_type_mean, nongold_type_mean) if a > b)
        worse = sum(1 for a, b in zip(gold_type_mean, nongold_type_mean) if a < b)
        print(f"  金标 type 均值更高的查询数 {better}，更低的 {worse} "
              f"（共 {len(gold_type_mean)}）")
        if gm < nm:
            print("→ **type 信号在此基准上与金标负相关**：它惩罚金标。")
            print("  人工加权固定给 0.20 权重 → 被拖累；训练可学到更小权重 → 不受害。")
        else:
            print("→ type 信号与金标正相关，人工加权应受益。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
