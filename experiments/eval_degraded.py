# -*- coding: utf-8 -*-
"""退化溯源可靠性通道：before/after 评测（离线、零 API、缓存重放）。

测什么
------
1. P1 / 召回 / 精确率 / F1 —— 封顶可靠性通道开启 vs 关闭；
2. `_type_rejects` —— 类型连贯性检查拦下的候选数（应不变：本通道不动绑定）；
3. 排序指标 MRR@10 / Hits@3 / Hits@10 —— 全量 CCL2018 伪文档，含 `*_reliab` 配置；
4. L2/L3 覆盖率 —— 现报口径 vs **诚实口径**（只算本体登记框架/级联）；
5. A1 消融（类型约束开/关）在**本通道已启用**时的重测。

关键设计约束（决定了结果会是什么样）
------------------------------------
P1 是**句级布尔**指标：`pred = bool(edges)`（evaluate_real.eval_split）。
软通道只在打分/排序层生效，对「这句有没有边」没有影响，
因此对 P1 的影响在数学上恒等于 0。本脚本把这一点作为**实测项**报出来，
而不是含糊过去。

运行：
    python experiments/eval_degraded.py            # 全量
    python experiments/eval_degraded.py --quick    # 跳过全量建图（只跑 P1/A1）
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph import provenance
from metaphor_graph.ablation import TrackedBackend, make_ontology, measure
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.health import graph_health
from metaphor_graph.llm_backend import load_table, LLMRefine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
ONT_JSON = os.path.join(ROOT, "metaphor_graph", "llm_ontology_train.json")


def load_backend():
    table = load_table(CACHE)
    with open(CACHE + ".refine.json", "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None)
                  for k, v in json.load(fh)}
    return TrackedBackend(table, None, rtable)


def p1_table(samples, ont, backend):
    """P1/召回/精确率/F1 + _type_rejects。"""
    rows = {}
    for label, floor in (("通道关闭（基线口径）",
                          provenance.RELIABILITY_FLOOR_OFF),
                         ("通道开启（封顶 0.5）",
                          provenance.RELIABILITY_FLOOR)):
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        m = measure(ex, samples)
        m["type_rejects"] = ex._type_rejects
        rows[label] = m
    return rows


def a1_table(samples, ont, backend, floor):
    """A1 消融：类型约束开 / 关（在给定可靠性 floor 下）。"""
    ex_on = MetaphorExtractor(ontology=ont, use_semfield=True,
                              llm_backend=backend, llm_conf_threshold=0.85)
    on = measure(ex_on, samples)
    on["type_rejects"] = ex_on._type_rejects

    orig_coher = MetaphorExtractor._type_coherent
    orig_valid = ont.type_valid
    MetaphorExtractor._type_coherent = lambda self, *a, **k: True
    ont.type_valid = lambda *a, **k: True
    try:
        ex_off = MetaphorExtractor(ontology=ont, use_semfield=True,
                                   llm_backend=backend, llm_conf_threshold=0.85)
        off = measure(ex_off, samples)
        off["type_rejects"] = ex_on._type_rejects
    finally:
        del ont.type_valid
        ont.type_valid = orig_valid
        del ont.type_valid              # 清掉实例属性，恢复类方法
        MetaphorExtractor._type_coherent = orig_coher
    return on, off


def coverage_table(samples, ont, backend):
    """L2/L3 覆盖率：现报口径 vs 诚实口径。"""
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    pos = [s.text for s in samples if ex.extract(s.text)]
    shg = MetaphorSHGBuilder(ontology=ont, llm_backend=backend).build(
        pos, doc_id="cov")
    h_old = graph_health(shg)                      # 历史口径
    h_new = graph_health(shg, ontology=ont)        # 诚实口径
    return {
        "n_edges": h_new.n_edges,
        "reported_coverage": h_old.hierarchy_coverage,
        "reported_frame": h_old.frame_coverage,
        "reported_cascade": h_old.cascade_coverage,
        "registered_frame": h_new.registered_frame_coverage,
        "registered_cascade": h_new.registered_cascade_coverage,
        "degraded_edge_rate": h_new.degraded_edge_rate,
        "avg_reliability": h_new.avg_provenance_reliability,
        "n_cascades": len(shg.cascades),
        "n_adhoc_cascades": sum(1 for c in shg.cascades
                                if c.id.startswith("C_ADHOC_")),
    }


def ranking_table(ont, backend, doc_size=10, floor=None):
    """全量建图上的排序指标（含 *_reliab 配置）。"""
    from metaphor_graph.evaluate_retrieval import (score_conditions, _mrr_hits)
    from metaphor_graph.retrieval import RetrievalEngine
    from metaphor_graph.training import train_from_shg
    from metaphor_graph.evaluate_fullcorpus import build_queries

    samples = load_ccl2018()
    k = doc_size
    n_docs = (len(samples) + k - 1) // k
    fl = provenance.RELIABILITY_FLOOR if floor is None else floor
    agg = {}
    for di in range(n_docs):
        texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(texts, doc_id=did)
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, texts, doc_id=did, ontology=ont)
        order = {f"{did}_c{i}": i for i in range(len(texts))}
        cmap = {f"{did}_c{i}": c for i, c in enumerate(texts)}
        scorer, _ = train_from_shg(shg, chunk_order=order, chunks=cmap,
                                   ontology=ont)
        qs = build_queries(shg, ont)
        for query, gold in qs["q_ext"] + qs["q_self"]:
            ranked = score_conditions(eng, scorer, query, reliability=True,
                                      floor=fl)
            for cfg, r in ranked.items():
                a = agg.setdefault(cfg, {"mrr": 0.0, "h3": 0, "h10": 0, "n": 0})
                m = _mrr_hits(r, sorted(gold))
                a["mrr"] += m["mrr"]; a["h3"] += m["hits@3"]
                a["h10"] += m["hits@10"]; a["n"] += 1
    return agg


def _pct(x):
    return "n/a" if x is None else f"{x:.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑 P1/A1，跳过全量排序")
    ap.add_argument("--doc-size", type=int, default=10)
    args = ap.parse_args()

    samples = load_ccl2018()
    ont = make_ontology(True, ONT_JSON)
    backend = load_backend()
    print(f"测试集 {len(samples)} 句（中性 "
          f"{sum(1 for s in samples if not s.gold_metaphor)} 句），"
          f"本体 {len(ont.frames)} 框架")
    print(f"本体登记框架 {sum(1 for f in ont.frames if not f.startswith('F_LLM_'))} "
          f"人工种子 / {sum(1 for f in ont.frames if f.startswith('F_LLM_'))} "
          f"自举沉淀（同前缀，故判据用『本体是否有条目』而非前缀）")

    # ---- 1) P1 / 召回 ----
    print("\n" + "=" * 84)
    print("【1】P1 / 召回 / 精确率 / F1（可靠性通道开 vs 关）")
    print("=" * 84)
    rows = p1_table(samples, ont, backend)
    print(f"{'配置':26s} {'召回':>8s} {'P1':>8s} {'精确率':>8s} {'F1':>8s} "
          f"{'type_rejects':>13s}")
    for label, m in rows.items():
        print(f"{label:26s} {m['recall']:>8.3f} {m['p1']:>8.3f} "
              f"{m['precision']:>8.3f} {m['f1']:>8.3f} {m['type_rejects']:>13d}")
    base = rows["通道关闭（基线口径）"]
    on = rows["通道开启（封顶 0.5）"]
    print(f"\n  差值：召回 {on['recall']-base['recall']:+.4f}  "
          f"P1 {on['p1']-base['p1']:+.4f}  F1 {on['f1']-base['f1']:+.4f}")

    # ---- 2) A1 消融 ----
    print("\n" + "=" * 84)
    print("【2】A1 消融（类型约束开/关）—— 可靠性通道已启用")
    print("=" * 84)
    on_c, off_c = a1_table(samples, ont, backend, provenance.RELIABILITY_FLOOR)
    print(f"{'配置':30s} {'召回':>8s} {'P1':>8s} {'精确率':>8s} {'F1':>8s}")
    for label, m in (("A1 类型检查开", on_c), ("A1 类型检查关", off_c)):
        print(f"{label:30s} {m['recall']:>8.3f} {m['p1']:>8.3f} "
              f"{m['precision']:>8.3f} {m['f1']:>8.3f}")
    print(f"  连贯性检查拦下 {on_c['type_rejects']} 个候选；"
          f"P1 {on_c['p1']:.3f} → {off_c['p1']:.3f}"
          f"（差 {off_c['p1']-on_c['p1']:+.4f}）")

    # ---- 3) 覆盖率 ----
    print("\n" + "=" * 84)
    print("【3】L2/L3 覆盖率：现报口径 vs 诚实口径")
    print("=" * 84)
    cov = coverage_table(samples, ont, backend)
    print(f"  超边总数 = {cov['n_edges']}")
    print(f"  现报 hierarchy_coverage = {_pct(cov['reported_coverage'])}"
          f"（frame {_pct(cov['reported_frame'])} / "
          f"cascade {_pct(cov['reported_cascade'])}）")
    print(f"  诚实口径（本体登记框架）= {_pct(cov['registered_frame'])}"
          f"；本体登记级联 = {_pct(cov['registered_cascade'])}")
    print(f"  退化边占比 = {_pct(cov['degraded_edge_rate'])}"
          f"；平均溯源可靠性 = {cov['avg_reliability']:.3f}")
    print(f"  级联总数 {cov['n_cascades']}，其中 C_ADHOC_ 事后补的 "
          f"{cov['n_adhoc_cascades']}")

    # ---- 4) 排序 ----
    if not args.quick:
        print("\n" + "=" * 84)
        print("【4】排序指标（全量 CCL2018 伪文档，MRR@10 / Hits@3 / Hits@10）")
        print("=" * 84)
        agg = ranking_table(ont, backend, args.doc_size)
        n = agg.get("trained", {}).get("n", 0)
        print(f"  查询数 n={n}")
        print(f"  {'配置':26s} {'MRR@10':>9s} {'Hits@3':>8s} {'Hits@10':>9s}")
        for cfg in ("trained", "trained_reliab", "trained_no_role",
                    "hand_weighted", "hand_weighted_reliab"):
            a = agg.get(cfg)
            if not a or not a["n"]:
                continue
            print(f"  {cfg:26s} {a['mrr']/a['n']:>9.4f} {a['h3']/a['n']:>8.4f} "
                  f"{a['h10']/a['n']:>9.4f}")
        t = agg.get("trained"); tr = agg.get("trained_reliab")
        hw = agg.get("hand_weighted"); hwr = agg.get("hand_weighted_reliab")
        if t and tr and t["n"]:
            print(f"\n  训练后 + 可靠性折扣：MRR@10 差 "
                  f"{(tr['mrr']-t['mrr'])/t['n']:+.4f}")
        if hw and hwr and hw["n"]:
            print(f"  人工加权 + 可靠性折扣：MRR@10 差 "
                  f"{(hwr['mrr']-hw['mrr'])/hw['n']:+.4f}")

    print("\n【诚实边界】P1 是句级布尔指标（pred = bool(edges)）；"
          "本通道只作用于打分/排序，不改变任何句子的产出与否 —— "
          "因此对 P1 的效应上界为 0，这是结构性事实而非调参结果。")


if __name__ == "__main__":
    main()
