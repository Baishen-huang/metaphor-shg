# -*- coding: utf-8 -*-
"""精确测量 A6：BUGGY-RETR 与 FIXED-CAP 的 top-5 是否真的相同。

报告初稿写的「两者对未注册边都是同一常量 → 排序不变」是**错的**：
buggy 给未注册边 0.0 / 已注册 1.0；fixed 给未注册边 0.5 / 已注册 1.0。
未注册边整体 +0.5（×0.20 = +0.1 分）会改变组间相对排序。
所以必须实测，不能靠推理。

运行：
    python experiments/probe_a6_buggy_vs_fixed.py
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
from metaphor_graph.training import extract_text_features


def type_of(mode, eng, m):
    if mode == "old":
        return 1.0 if m.frame_id else 0.0
    if mode == "buggy":
        fsp = eng.ont.get_frame(m.frame_id) if m.frame_id else None
        mt = fsp.mapping_type if fsp else m.frame_id or ""
        return 1.0 if eng.ont.type_valid(m.source_type, mt) else 0.0
    return eng.ont.type_reliability_of(m.frame_id, m.source_type)


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
    chg_old_fixed = chg_buggy_fixed = 0
    chg_buggy_fixed_top10 = 0
    rec = {"old": 0.0, "buggy": 0.0, "fixed": 0.0}
    h3 = {"old": 0, "buggy": 0, "fixed": 0}
    # 修复是否改变「未注册边进入 top-5」的条数
    n_unreg_in_top5 = {"old": 0, "buggy": 0, "fixed": 0}

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
            feats = {m.id: extract_text_features(text, m, eng._centrality, ont)
                     for m in pool}
            tops, chunks = {}, {}
            for mode in ("old", "buggy", "fixed"):
                def sc(m, _mode=mode):
                    f = list(feats[m.id])
                    f[3] = type_of(_mode, eng, m)
                    return round(0.35 * f[0] + 0.25 * min(f[1], 1.0)
                                 + 0.20 * f[2] + 0.20 * f[3], 4)
                ordered = sorted(pool, key=lambda m: -sc(m))
                tops[mode] = [m.id for m in ordered[:5]]
                n_unreg_in_top5[mode] += sum(
                    1 for m in ordered[:5]
                    if m.frame_id and ont.get_frame(m.frame_id) is None)
                seen = []
                for m in ordered[:5]:
                    for s in m.chunk_spans:
                        if s.chunk_id not in seen:
                            seen.append(s.chunk_id)
                chunks[mode] = seen
                top = set(seen[:10])
                rec[mode] += len(gold_chunks & top) / len(gold_chunks)
                h3[mode] += 1 if any(c in gold_chunks for c in seen[:3]) else 0
            if tops["old"] != tops["fixed"]:
                chg_old_fixed += 1
            if tops["buggy"] != tops["fixed"]:
                chg_buggy_fixed += 1
            if chunks["buggy"] != chunks["fixed"]:
                chg_buggy_fixed_top10 += 1

    print("=" * 78)
    print(f"A6 精确敏感性（n={n_q}）")
    print("=" * 78)
    print(f"top-5 变化：OLD-CONST vs FIXED   : {chg_old_fixed} "
          f"= {chg_old_fixed / max(1, n_q):.1%}")
    print(f"top-5 变化：BUGGY    vs FIXED   : {chg_buggy_fixed} "
          f"= {chg_buggy_fixed / max(1, n_q):.1%}   ← 关键")
    print(f"top-5 chunk 序列变化 BUGGY vs FIXED: {chg_buggy_fixed_top10} "
          f"= {chg_buggy_fixed_top10 / max(1, n_q):.1%}")
    print()
    print(f"top-5 中未注册回退边的条数：buggy {n_unreg_in_top5['buggy']}  "
          f"vs fixed {n_unreg_in_top5['fixed']}")
    print()
    print(f"{'type 编码':22s} {'Recall@10':>10s} {'Hits@3':>8s}")
    for mode, label in (("old", "OLD-CONST 恒1.0"),
                        ("buggy", "BUGGY-RETR"),
                        ("fixed", "FIXED-CAP 封顶0.5")):
        print(f"{label:22s} {rec[mode] / max(1, n_q):>10.4f} "
              f"{h3[mode] / max(1, n_q):>8.4f}")
    print()
    if chg_buggy_fixed == 0:
        print("→ BUGGY 与 FIXED 的 top-5 **完全相同**：本次修复不改变 A6 数字。")
    else:
        print(f"→ BUGGY 与 FIXED 的 top-5 有 {chg_buggy_fixed} 个查询不同，")
        print("  但 A6 的 Recall@10/Hits@3 指标仍可能相同（指标只看 chunk 并集）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
