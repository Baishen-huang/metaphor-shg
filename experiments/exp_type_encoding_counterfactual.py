# -*- coding: utf-8 -*-
"""§6.2 的 type 编码反事实实验（本报告的核心量化）。

三种 type 编码，同一份图 / 同一套金标 / 同一套查询，只改 f[3]：

  OLD-CONST  （已上报口径）type ≡ 1.0（有框架归属即通过；本语料全部边都有归属）
  BUGGY-RETR （retrieval.py:250 的表达式搬到 §6.2 上）
             type = 1.0 若本体注册且 type_valid 通过，否则 0.0
  FIXED-CAP  （本次修复）type = 1.0 注册 / 0.5 未注册回退框架 / 0.0 无归属

对每种编码，同时算 hand_weighted（人工加权）与 trained（自监督训练）的 MRR，
于是能直接回答：
  (a) §6.2 已上报的 +4.5pp 里，有多少来自 type 编码口径差？
  (b) 若 §6.2 当初真的走了 retrieval.py:250 的表达式，数字会是多少？

运行：
    python experiments/exp_type_encoding_counterfactual.py
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
from metaphor_graph.training import (build_training_set, build_weak_refine_set,
                                      MetaphorScorer)
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, _chunk_of,
                                             GEN_CACHE, JUDGE_CACHE, _load_json)
from metaphor_graph.evaluate_retrieval import _mrr_hits

ENCODINGS = ("old_const", "buggy_retr", "fixed_cap")


def encode(feats, mode, eng, mapping):
    """把 7 维特征的 f[3] 换成指定编码，返回新的特征列表。"""
    f = list(feats)
    if mode == "old_const":
        f[3] = 1.0 if mapping.frame_id else 0.0
    elif mode == "buggy_retr":
        fspec = eng.ont.get_frame(mapping.frame_id) if mapping.frame_id else None
        mtype = fspec.mapping_type if fspec else mapping.frame_id or ""
        f[3] = 1.0 if eng.ont.type_valid(mapping.source_type, mtype) else 0.0
    else:  # fixed_cap
        f[3] = eng.ont.type_reliability_of(mapping.frame_id,
                                           mapping.source_type)
    return f


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    judge_cache = _load_json(JUDGE_CACHE)
    gen_cache = _load_json(GEN_CACHE)

    agg = defaultdict(lambda: {"mrr": 0.0, "h3": 0, "h10": 0, "n": 0})
    n_fb_unreg = n_fb_reg = n_ont = 0

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
        for e in l1:
            fid = e.frame_id or ""
            if fid.startswith("F_LLM_"):
                if ont.get_frame(fid) is None:
                    n_fb_unreg += 1
                else:
                    n_fb_reg += 1
            else:
                n_ont += 1
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
            refine_path=os.path.join(os.path.dirname(GEN_CACHE), "..",
                                     "data", "llm_cache_deepseek.json.refine.json"),
            negatives_per_positive=3)
        weak = MetaphorScorer().fit(ds_w) if len(ds_w) > 0 else None

        qs = build_queries_rich(shg, chunk_map, did)
        qs = filter_violations(qs, gen_cache)
        for q in qs:
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {_chunk_of(e) for e in shg.edges
                           if e.id in rel and _chunk_of(e)}
            if not gold_chunks:
                continue
            cands = eng.live_edges()
            base_feats = {m.id: eng._pair_features(q["question"], m)
                          for m in cands}
            for mode in ENCODINGS:
                # 预计算该编码下的 chunk 分数
                for cfg in ("hand_weighted", "trained", "trained_weak"):
                    chunk_score = {}
                    for m in cands:
                        cid = _chunk_of(m)
                        if cid is None:
                            continue
                        f = encode(base_feats[m.id], mode, eng, m)
                        if cfg == "hand_weighted":
                            s = (0.35 * f[0] + 0.25 * min(f[1], 1.0)
                                 + 0.20 * f[2] + 0.20 * f[3])
                        elif cfg == "trained":
                            s = scorer.score_features(f)
                        else:
                            s = weak.score_features(f) if weak else 0.0
                        chunk_score[cid] = max(chunk_score.get(cid, -1e9), s)
                    ranked = sorted(chunk_score.items(), key=lambda x: -x[1])
                    met = _mrr_hits(ranked, sorted(gold_chunks))
                    a = agg[(mode, cfg)]
                    a["mrr"] += met["mrr"]
                    a["h3"] += met["hits@3"]
                    a["h10"] += met["hits@10"]
                    a["n"] += 1

    print("=" * 84)
    print("§6.2 type 编码反事实（同一图/金标/查询，只改 f[3]）")
    print("=" * 84)
    print(f"边构成：本体框架 {n_ont} ｜ F_LLM_* 已注册 {n_fb_reg} ｜ "
          f"F_LLM_* 未注册 {n_fb_unreg}（仅后者会被 buggy 表达式判 0）")
    print()
    print(f"{'type 编码':16s} {'配置':18s} {'MRR@10':>9s} {'Hits@3':>8s} {'n':>6s}")
    for mode, label in (("old_const", "OLD-CONST 恒1.0"),
                        ("buggy_retr", "BUGGY-RETR (retrieval)"),
                        ("fixed_cap", "FIXED-CAP 封顶0.5")):
        for cfg in ("hand_weighted", "trained", "trained_weak"):
            a = agg[(mode, cfg)]
            if not a["n"]:
                continue
            k_ = a["n"]
            print(f"{label:16s} {cfg:18s} {a['mrr'] / k_:>9.4f} "
                  f"{a['h3'] / k_:>8.4f} {k_:>6d}")
        # 训练增益
        hw = agg[(mode, "hand_weighted")]
        tr = agg[(mode, "trained")]
        n = hw["n"]
        if n:
            print(f"{'':16s} {'训练增益 (pp)':18s} "
                  f"{(tr['mrr'] - hw['mrr']) / n * 100:>+9.2f}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
