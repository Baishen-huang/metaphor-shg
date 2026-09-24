# -*- coding: utf-8 -*-
"""诊断 3：§6.2 的 7437 个候选对里，特征到底走「边锚点」还是「文本锚点」？

决定性问题：如果 §6.2 主要走文本锚点（extract_text_features），那么
  - type 由 `1.0 if cand.frame_id else 0.0` 决定 → 恒 1.0（常数）
  - ground_jaccard 由**包含率**公式决定（与边锚点的 Jaccard 不同定义）
如果主要走边锚点，则 ground_jaccard 是真 Jaccard。

同时量化：若 §6.2 的「人工加权」改用 retrieval.py 的 buggy 表达式，
分数会差多少（即这个 bug 若真的污染过报告数字，量级是多大）。

运行：
    python experiments/probe_path_mix.py
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
from metaphor_graph.training import extract_features, extract_text_features
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import build_queries_rich
from metaphor_graph.evaluate_retrieval import score_conditions


def buggy_retrieval_type(eng, m):
    """逐字复刻 retrieval.py:250-252 的表达式（人工加权路径）。"""
    fspec = eng.ont.get_frame(m.frame_id) if m.frame_id else None
    mtype = fspec.mapping_type if fspec else m.frame_id or ""
    return 1.0 if eng.ont.type_valid(m.source_type, mtype) else 0.0


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    n_q = 0
    n_q_empty = 0
    path_used = defaultdict(int)          # text / edge
    gj_def_diff = []                      # 包含率 vs Jaccard 的差
    n_gj_diff = 0
    hand_buggy_delta = []                 # 若用 buggy 表达式，人工加权分的差
    n_hand_buggy_diff = 0
    type_text = defaultdict(int)
    type_edge = defaultdict(int)
    # 修复后的 type（注册=1.0 / 未注册 F_LLM=0.5 / 无框架=0.0）
    type_fixed = defaultdict(int)

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
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        for q in build_queries_rich(shg, chunk_map, did):
            n_q += 1
            qtext = q["query"]
            qedges = eng._query_edges(qtext)
            if not qedges:
                n_q_empty += 1
            for m in eng.live_edges():
                if qedges:
                    fe = eng._pair_features(qtext, m)     # 边锚点（max 聚合）
                    path_used["edge"] += 1
                    t_edge = extract_features(qedges[0], m, eng._centrality)[3]
                    type_edge[t_edge] += 1
                    gj_edge = extract_features(qedges[0], m, eng._centrality)[6]
                else:
                    fe = eng._text_features(qtext, m)      # 文本锚点
                    path_used["text"] += 1
                    t_edge = None
                    gj_edge = None
                ft = extract_text_features(qtext, m, eng._centrality, ont)
                type_text[ft[3]] += 1
                # 包含率 vs Jaccard 的定义差
                if gj_edge is not None:
                    d = abs(gj_edge - ft[6])
                    gj_def_diff.append(d)
                    if d > 1e-9:
                        n_gj_diff += 1
                # 修复后的 type
                fid = m.frame_id or ""
                if not fid:
                    tf = 0.0
                elif ont.get_frame(fid) is not None:
                    tf = 1.0
                else:
                    tf = 0.5
                type_fixed[tf] += 1
                # buggy 人工加权 vs §6.2 人工加权
                hand62 = 0.35 * fe[0] + 0.25 * min(fe[1], 1.0) + \
                    0.20 * fe[2] + 0.20 * fe[3]
                bt = buggy_retrieval_type(eng, m)
                hand_buggy = 0.35 * fe[0] + 0.25 * min(fe[1], 1.0) + \
                    0.20 * fe[2] + 0.20 * bt
                d = abs(hand_buggy - hand62)
                hand_buggy_delta.append(d)
                if d > 1e-9:
                    n_hand_buggy_diff += 1

    tot = path_used["text"] + path_used["edge"]
    print("=" * 80)
    print("§6.2 特征路径的构成（决定 type 是否为常数）")
    print("=" * 80)
    print(f"查询总数                     : {n_q}")
    print(f"查询侧无超边命中（→文本锚点） : {n_q_empty} "
          f"= {n_q_empty / max(1, n_q):.1%}")
    print(f"候选对总数                   : {tot}")
    print(f"  走文本锚点 extract_text_features : {path_used['text']} "
          f"= {path_used['text'] / max(1, tot):.1%}")
    print(f"  走边锚点 extract_features        : {path_used['edge']} "
          f"= {path_used['edge'] / max(1, tot):.1%}")
    print()
    print(f"type 取值（文本锚点口径）: {dict(type_text)}")
    print(f"type 取值（边锚点口径）  : {dict(type_edge)}")
    print(f"type 取值（修复后口径）  : {dict(type_fixed)}")
    print()
    print("=" * 80)
    print("ground_jaccard：文本锚点用「包含率」，边锚点用「真 Jaccard」")
    print("=" * 80)
    if gj_def_diff:
        print(f"可比对（边锚点）样本数 : {len(gj_def_diff)}")
        print(f"两定义取值不同的样本数 : {n_gj_diff} "
              f"= {n_gj_diff / len(gj_def_diff):.1%}")
        print(f"最大绝对差             : {max(gj_def_diff):.3f}")
        print(f"平均绝对差             : {sum(gj_def_diff) / len(gj_def_diff):.3f}")
    print()
    print("=" * 80)
    print("量化：若 §6.2 的人工加权改用 retrieval.py 的 buggy 表达式")
    print("=" * 80)
    print(f"候选对数             : {len(hand_buggy_delta)}")
    print(f"分数不同的候选对     : {n_hand_buggy_diff} "
          f"= {n_hand_buggy_diff / max(1, len(hand_buggy_delta)):.1%}")
    print(f"最大绝对分差         : {max(hand_buggy_delta):.3f}")
    print(f"平均绝对分差         : "
          f"{sum(hand_buggy_delta) / max(1, len(hand_buggy_delta)):.4f}")
    print("→ 差 0.20（type 1.0→0.0）乘以 0.20 的权重 = 0.20 分，")
    print("   足以在 chunk 池内改变排序 → 若 §6.2 真用了 buggy 路径，")
    print("   人工加权 MRR 会被系统性压低。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
