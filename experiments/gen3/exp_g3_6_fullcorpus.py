# -*- coding: utf-8 -*-
"""gen3 实验六：§7.3 fullcorpus A7/H5 的 type 依赖复核 + 单特征上界。

两件事：

**一、gen1 报告称「修复 type 编码让 A7/H5 从『无增益❌』翻转为『+9.5pp 有增益✅』」。
这是被标记为「需要人工复核的重大结论变更」。本实验在 evaluate_fullcorpus 的
Q_ext + Q_self（by-construction 金标，n=861）上复核：**

  四种 type 编码 × {人工加权, 训练后 7 维, 训练后 6 维（去 type）}
  OLD-CONST（修复前，恒 1.0）/ FIXED-CAP（当前）/ NO-TYPE（6 维，type 直接删除）
  / ZERO（type 恒 0，即人工加权不给 type 分数）

**二、单特征上界**：在 fullcorpus 口径下，纯 sem / 纯 clue 的 MRR 与训练后比较，
检验「训练增益」是否只是「学会了 sem 的权重」。

运行：
    python experiments/gen3/exp_g3_6_fullcorpus.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from experiments.gen3 import g3_common as G                       # noqa: E402

logging.disable(logging.CRITICAL)
from metaphor_graph.builder import MetaphorSHGBuilder              # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor             # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine               # noqa: E402
from metaphor_graph.data_loader import load_ccl2018                # noqa: E402
from metaphor_graph.training import (MetaphorScorer, TrainingSet,   # noqa: E402
                                     FEATURE_NAMES)
from metaphor_graph.evaluate_fullcorpus import (                    # noqa: E402
    build_replay_ontology, build_replay_backend, build_queries)
from metaphor_graph.evaluate_llmgold import _chunk_of               # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "exp_g3_6_fullcorpus.json")


def fit_scorer(X, y, seed=42):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) == 0 or len(np.unique(y)) < 2:
        return None
    return MetaphorScorer(n_features=X.shape[1], seed=seed).fit(TrainingSet(X, y))


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = G.DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    print("=" * 100)
    print("gen3 实验六：fullcorpus A7/H5 的 type 依赖复核")
    print("=" * 100)
    print(f"本体 {n_frames} 框架 ｜ {n_docs} 伪文档 ｜ by-construction 金标")
    print()

    IDX_TYPE = G.IDX["type"]
    res = defaultdict(lambda: dict(mrr=0.0, per=[], n=0, h3=0))
    n_q = {"q_ext": 0, "q_self": 0, "q_cas": 0}
    n_edges = n_ext = 0

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
        n_edges += len(l1)
        n_ext += sum(1 for e in shg.edges if e.is_extended)
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                      for e in shg.edges}
        ds = G.__dict__  # noqa: F841  (占位，避免误用)
        from metaphor_graph.training import build_training_set
        ds = build_training_set(shg, chunk_order=chunk_order, chunks=chunk_map,
                                centrality=centrality, ontology=ont,
                                positive_mode="chunk", negatives_per_positive=3)
        if len(ds) == 0:
            continue
        sc7 = fit_scorer(ds.X, ds.y)
        sc6 = fit_scorer(np.delete(ds.X, IDX_TYPE, axis=1), ds.y)

        queries = build_queries(shg, ont)
        for typ, items in queries.items():
            n_q[typ] += len(items)
        for query, gold in queries["q_ext"] + queries["q_self"]:
            gold_ids = sorted(gold)
            F = np.asarray([eng._pair_features(query, m) for m in eng.live_edges()])
            meta = [dict(chunk_id=_chunk_of(m) or "", id=m.id,
                         frame_id=m.frame_id or "")
                    for m in eng.live_edges()]
            cands = eng.live_edges()
            # ---- 人工加权：三种 type 口径 ----
            # 已上报（OLD-CONST）：§6.2 的 hand_weighted 用 f[3] 原值
            variants = {
                "manual_OLD-CONST": None,     # f[3] 原值（=FIXED-CAP 当前口径）
                "manual_ZERO": "zero",        # type 恒 0（即 0.35/0.25/0.20/0）
            }
            for name, mode in variants.items():
                s = np.empty(len(F))
                for i in range(len(F)):
                    t = 0.0 if mode == "zero" else F[i, IDX_TYPE]
                    s[i] = (0.35 * F[i, 0] + 0.25 * min(F[i, 1], 1.0)
                            + 0.20 * F[i, 2] + 0.20 * t)
                r = G.rank_chunks(s, meta)
                m = G.mrr_of(r, gold_ids)
                a = res[name]
                a["mrr"] += m; a["per"].append(m); a["n"] += 1
                a["h3"] += G.hits_of(r, gold_ids, 3)
            # ---- 单信号 ----
            for name, cols in (("single_sem", [0]), ("single_clue", [2]),
                               ("single_struct", [1]), ("single_type", [3]),
                               ("single_ground", [6])):
                r = G.rank_chunks(F[:, cols].mean(axis=1), meta)
                m = G.mrr_of(r, gold_ids)
                a = res[name]
                a["mrr"] += m; a["per"].append(m); a["n"] += 1
                a["h3"] += G.hits_of(r, gold_ids, 3)
            # ---- 训练后 7 维 / 6 维（去 type）----
            NO_TYPE = [j for j in range(len(FEATURE_NAMES)) if j != IDX_TYPE]
            for name, sc, cols in (("trained7", sc7, None),
                                   ("trained6_no_type", sc6, NO_TYPE)):
                if sc is None:
                    continue
                Fi = F if cols is None else F[:, cols]
                r = G.rank_chunks(G.chunk_scores(Fi, scorer=sc), meta)
                m = G.mrr_of(r, gold_ids)
                a = res[name]
                a["mrr"] += m; a["per"].append(m); a["n"] += 1
                a["h3"] += G.hits_of(r, gold_ids, 3)

    print(f"L1 边 {n_edges} 条，扩展边 {n_ext} 条 ｜ "
          f"查询 Q_ext={n_q['q_ext']} Q_self={n_q['q_self']} "
          f"（合计 n={res['trained7']['n']}）")
    print()
    print("【表 A】fullcorpus 排序指标（by-construction 金标，Q_ext+Q_self）")
    print(f"{'配置':24s} {'MRR@10':>8s} {'Hits@3':>8s} {'n':>6s}")
    for name in ("manual_OLD-CONST", "manual_ZERO", "trained7",
                 "trained6_no_type", "single_sem", "single_clue",
                 "single_struct", "single_type", "single_ground"):
        a = res[name]
        if not a["n"]:
            continue
        print(f"{name:24s} {a['mrr']/a['n']:>8.4f} {a['h3']/a['n']:>8.4f} "
              f"{a['n']:>6d}")
    print()
    hw = res["manual_OLD-CONST"]["mrr"] / res["manual_OLD-CONST"]["n"]
    hz = res["manual_ZERO"]["mrr"] / res["manual_ZERO"]["n"]
    t7 = res["trained7"]["mrr"] / res["trained7"]["n"]
    t6 = res["trained6_no_type"]["mrr"] / res["trained6_no_type"]["n"]
    print("【表 B】A7（训练 − 人工加权）在各 type 口径下")
    print(f"  人工加权（type 参与，0.20）: {hw:.4f}")
    print(f"  人工加权（type 恒 0）      : {hz:.4f}")
    print(f"  训练后 7 维                : {t7:.4f}")
    print(f"  训练后 6 维（去 type）      : {t6:.4f}")
    print(f"  A7 Δ = 训练7 − 人工(type 参与) = {(t7-hw)*100:+.2f}pp")
    print(f"  A7 Δ = 训练7 − 人工(type=0)    = {(t7-hz)*100:+.2f}pp")
    print(f"  A7 Δ = 训练6 − 人工(type=0)    = {(t6-hz)*100:+.2f}pp")
    print(f"  去掉 type 对训练侧的影响        = {(t6-t7)*100:+.2f}pp")
    print()
    print("【表 C】配对 bootstrap 95% CI")
    pairs = [
        ("manual_ZERO", "manual_OLD-CONST", "人工去掉 type 分（0.20→0）− 已上报人工"),
        ("trained7", "manual_OLD-CONST", "A7: 训练7 − 人工(type 参与)"),
        ("trained7", "manual_ZERO", "A7: 训练7 − 人工(type=0)"),
        ("trained6_no_type", "manual_ZERO", "A7: 训练6(去type) − 人工(type=0)"),
        ("trained6_no_type", "trained7", "训练侧去 type − 训练侧 7 维"),
        ("single_sem", "trained7", "纯 sem − 训练后 7 维"),
        ("single_clue", "trained7", "纯 clue − 训练后 7 维"),
    ]
    ci_rows = []
    for ka, kb, label in pairs:
        a = np.asarray(res[ka]["per"]); b = np.asarray(res[kb]["per"])
        if len(a) != len(b) or len(a) == 0:
            continue
        st = G.paired_bootstrap(a, b, n_boot=2000)
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"  {label:44s} Δ={st['delta']:+.4f} "
              f"[{st['lo']:+.4f},{st['hi']:+.4f}] p={st['p']:.3f} {star}")
        ci_rows.append(dict(label=label, **st))
    print()

    out = dict(n_edges=n_edges, n_ext=n_ext, n_queries=n_q,
               results={k: dict(mrr=v["mrr"] / max(1, v["n"]), h3=v["h3"],
                                n=v["n"], per=[float(x) for x in v["per"]])
                        for k, v in res.items()},
               ci=ci_rows)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
