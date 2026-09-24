# -*- coding: utf-8 -*-
"""诊断 4：其余维度的公式级分歧（排除「锚点不同」这一设计内差异）。

逐一核对同一维度在两条路径上的**公式**是否一致：
  sem            training: max(0, cos)   retrieval 人工加权: cos（无 clamp）
  struct         training: min(1, centrality.get(id,0))  retrieval: centrality.get(id,0) 后 min(1,·)
  clue           training: min(1, 0.5*命中数)   retrieval: _clue_count 同式
  type           已修（见 ontology.type_reliability）
  same_frame     文本锚点: cand.frame_id ∈ 查询触发框架集 / 边锚点: 帧 id 相等
  same_cascade   同上（级联层）
  ground_jaccard 文本锚点: 包含率 |g∩text|/|g| / 边锚点: 真 Jaccard

运行：
    python experiments/probe_formula_divergence.py
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
from metaphor_graph.training import extract_text_features, extract_features
from metaphor_graph import embeddings
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_llmgold import build_queries_rich


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    # sem clamp 的影响（同一对输入，两种公式）
    neg_cos = 0
    n_cos = 0
    worst = 0.0
    # ground_jaccard 两种定义
    gj_contain = []
    gj_jacc = []
    gj_diff = 0
    n_gj = 0
    # same_frame / same_cascade：两条路径对同一 (query, cand) 是否一致
    sf_diff = sc_diff = 0
    n_role = 0
    sf_examples = []

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
            qtext = q["query"]
            qedges = eng._query_edges(qtext)
            for m in eng.live_edges():
                # sem clamp：同一对输入（查询文本 vs 候选描述）
                c = embeddings.cosine(embeddings.embed(qtext),
                                      embeddings.embed(m.describe()))
                n_cos += 1
                if c < 0:
                    neg_cos += 1
                    worst = min(worst, c)
                # ground_jaccard 两定义（仅边锚点可比）
                if qedges:
                    qe = qedges[0]
                    ft = extract_text_features(qtext, m, eng._centrality, ont)
                    # **实际打分路径**：_pair_features 对多条查询边取 max 聚合
                    fp = eng._pair_features(qtext, m)
                    g = set(m.ground)
                    contain = (len({w for w in g if w in qtext}) /
                               max(1, len(g))) if g else 0.0
                    jac = extract_features(qe, m, eng._centrality, ont)[6]
                    gj_contain.append(contain)
                    gj_jacc.append(jac)
                    n_gj += 1
                    if abs(contain - jac) > 1e-9:
                        gj_diff += 1
                    # 角色特征：文本锚点 vs 实际打分路径（max 聚合）
                    n_role += 1
                    if abs(ft[4] - fp[4]) > 1e-9:
                        sf_diff += 1
                        if len(sf_examples) < 3:
                            sf_examples.append((did, qe.frame_id, m.frame_id,
                                                ft[4], fp[4]))
                    if abs(ft[5] - fp[5]) > 1e-9:
                        sc_diff += 1

    print("=" * 80)
    print("sem 的 clamp 分歧（training 用 max(0,cos)，retrieval 人工加权用原始 cos）")
    print("=" * 80)
    print(f"测量样本数        : {n_cos}")
    print(f"cos < 0 的样本数  : {neg_cos} = {neg_cos / max(1, n_cos):.2%}")
    print(f"最负的 cos 值     : {worst:.4f}")
    print("→ 默认哈希向量器下 cos 恒非负，clamp 不改变取值（本次语料）；")
    print("  但公式不一致是隐患：换 NgramEmbedder / 真实句向量后 cos 可为负，")
    print("  届时人工加权路径会给出负 sem（惩罚），训练路径仍为 0。已一并对齐。")
    print()
    print("=" * 80)
    print("ground_jaccard 的定义分歧（文本锚点=包含率 vs 边锚点=真 Jaccard）")
    print("=" * 80)
    print(f"可比对样本数   : {n_gj}")
    print(f"取值不同样本数 : {gj_diff} = {gj_diff / max(1, n_gj):.2%}")
    if n_gj:
        print(f"包含率均值     : {sum(gj_contain) / n_gj:.3f}")
        print(f"Jaccard 均值   : {sum(gj_jacc) / n_gj:.3f}")
        print(f"包含率 >= Jaccard 的比例: "
              f"{sum(1 for a, b in zip(gj_contain, gj_jacc) if a >= b) / n_gj:.1%}")
    print("→ 这是**设计内的锚点差异**（文本没有喻底集合，无法算 Jaccard），")
    print("  但两者不是同一函数的两种写法：包含率系统性偏高。已在报告里标注。")
    print()
    print("=" * 80)
    print("same_frame / same_cascade 的两路径一致性")
    print("=" * 80)
    print(f"可比对样本数             : {n_role}")
    print(f"same_frame 取值不同      : {sf_diff} = {sf_diff / max(1, n_role):.2%}")
    print(f"same_cascade 取值不同    : {sc_diff} = {sc_diff / max(1, n_role):.2%}")
    if sf_examples:
        print("样例（doc, 查询边frame, 候选frame, 文本锚点值, 边锚点值）:")
        for r in sf_examples:
            print("   ", r)
    print("→ retrieval._query_edges 刻意把「查询侧超边」定义为「查询触发词命中的")
    print("  框架下的超边」，因此边锚点的 same_frame 与文本锚点的语义一致；")
    print("  残留分歧来自 _pair_features 取 max 聚合（多条查询边取最强）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
