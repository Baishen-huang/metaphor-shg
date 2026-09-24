# -*- coding: utf-8 -*-
"""诊断 2：§6.2 评测实际走的特征路径 + 其余 6 维的口径分歧。

要回答的问题：
  Q1 §6.2 的 hand_weighted 配置是否真的调用 retrieval.metaphor_retriever_score？
  Q2 在 §6.2 的候选池里，type 特征是否恒定（= 携带 0 排序信息）？
  Q3 same_frame / same_cascade / ground_jaccard 两条路径口径是否一致？

运行：
    python experiments/probe_feature_paths.py
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
from metaphor_graph.training import (extract_text_features, extract_features,
                                      FEATURE_NAMES)
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend,
                                                build_queries)
from metaphor_graph.evaluate_llmgold import build_queries_rich
from metaphor_graph.evaluate_retrieval import score_conditions


def main():
    # ---- Q1：源码级证据 ----
    import inspect
    src = inspect.getsource(score_conditions)
    print("=" * 80)
    print("Q1 §6.2 的 hand_weighted 到底调用了什么？")
    print("=" * 80)
    print("evaluate_retrieval.score_conditions 源码：")
    for ln in src.splitlines():
        print("   ", ln)
    print()
    print("→ 它作用于 eng._pair_features(query, m) 的 7 维向量，")
    print("  而 hand_weighted = 0.35*f0 + 0.25*f1 + 0.20*f2 + 0.20*f3。")
    print("  f3 来自 training.extract_features / extract_text_features，")
    print("  **完全不经过 retrieval.metaphor_retriever_score**。")
    print()

    # ---- 逐个 consumer 检查是否真的调用 metaphor_retriever_score ----
    import subprocess
    out = subprocess.run(
        ["git", "grep", "-n", "metaphor_retriever_score"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("仓库内 metaphor_retriever_score 的全部引用：")
    print(out.stdout)
    print()

    # ---- Q2 / Q3：在真实图上逐查询核对 ----
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    type_cols = defaultdict(list)          # doc -> [type values across candidates]
    diverge = defaultdict(int)             # feature -> count of differing values
    n_pairs = 0
    per_feature_text_edge_diff = defaultdict(list)
    n_queries = 0
    fb_registered = 0
    fb_unregistered = 0
    docs_with_type_variance = 0

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
                    fb_unregistered += 1
                else:
                    fb_registered += 1
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        queries = build_queries_rich(shg, chunk_map, did)
        if not queries:
            continue
        tv = []
        for q in queries:
            qtext = q["query"]
            n_queries += 1
            # 复刻 score_conditions 的特征计算
            for m in eng.live_edges():
                fe = eng._pair_features(qtext, m)
                # 文本锚点版本（兜底路径）
                ft = extract_text_features(qtext, m, eng._centrality, ont)
                tv.append(fe[3])
                n_pairs += 1
                for j, name in enumerate(FEATURE_NAMES):
                    if abs(fe[j] - ft[j]) > 1e-9:
                        diverge[name] += 1
                    per_feature_text_edge_diff[name].append(abs(fe[j] - ft[j]))
        type_cols[did] = tv
        if len(set(tv)) > 1:
            docs_with_type_variance += 1

    print("=" * 80)
    print("Q2 §6.2 候选池里 type 特征的取值分布（决定它是否携带排序信息）")
    print("=" * 80)
    allv = [v for vs in type_cols.values() for v in vs]
    uniq = sorted(set(allv))
    print(f"候选 (query, edge) 对总数 : {n_pairs}")
    print(f"type 特征取值种类         : {uniq}")
    print(f"type 恒为 1.0 的候选对占比 : "
          f"{sum(1 for v in allv if v == 1.0) / max(1, len(allv)):.4f}")
    print(f"逐文档 type 有方差的文档数 : {docs_with_type_variance} / {len(type_cols)}")
    print("→ type 若恒定，则它在人工加权与训练路径里都是**常数项**：")
    print("   人工加权里是固定加 0.20；训练路径里被 bias 吸收。")
    print("   两者都不影响排序 → 该特征在 §6.2 表中不贡献任何差异。")
    print()

    print("=" * 80)
    print("回退框架边的构成（注册 vs 未注册）")
    print("=" * 80)
    print(f"F_LLM_* 且本体已注册（get_frame 命中）: {fb_registered}")
    print(f"F_LLM_* 且本体未注册（get_frame=None）: {fb_unregistered}")
    print(f"→ 只有未注册的那些才会在 retrieval 人工加权路径里被 type_valid 判 0。")
    print()

    print("=" * 80)
    print("Q3 两条路径（边锚点 extract_features vs 文本锚点 "
          "extract_text_features）逐维分歧")
    print("=" * 80)
    print(f"{'特征':16s} {'分歧对数':>10s} {'分歧率':>9s} {'最大绝对差':>12s}")
    for name in FEATURE_NAMES:
        d = diverge[name]
        mx = max(per_feature_text_edge_diff[name]) if per_feature_text_edge_diff[name] else 0.0
        print(f"{name:16s} {d:>10d} {d / max(1, n_pairs):>9.1%} {mx:>12.3f}")
    print()
    print("注：sem/clue 的差异来自「锚点不同」（查询文本 vs 查询超边），属设计内；")
    print("    type 的差异来自「是否校验本体注册」，是本次调查的 bug；")
    print("    ground_jaccard 的差异若很大，需看是否连定义都不同。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
