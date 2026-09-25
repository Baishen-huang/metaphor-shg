# -*- coding: utf-8 -*-
"""gen2 实验 4：L3 消融（真正的「无级联层」对照）+ 覆盖率归因。

**为什么要单独做这个**
`builder._ensure_cascades` 是**不可绕过**的：只要它开着，任何级联构造规则下的
`graph_health.cascade_coverage` 都会是 1.000 —— 因为它把每个还没归属的框架
按目标域补一个 `C_ADHOC_*` 级联。所以「L2/L3 覆盖率 100%」这个已上报数字，
在结构上**不是**本体级联的功劳，而是这个兜底函数的功劳。本实验把这个变量
单独拉出来测：

  A. 本体级联 + 兜底（= 生产现状）           → 覆盖率 ?
  B. 本体级联，兜底关闭                       → 覆盖率 ?
  C. 本体级联替换为 source 规则 + 兜底关闭    → 覆盖率 ?
  D. 完全无级联（ont 清空 + 兜底关闭）        → 覆盖率 ?

同时测每档的检索指标（改写查询三通路 + Q_cas + Ω），以回答
「级联层是否存在」对指标的影响。

产物：experiments/gen2/exp_g2_4_l3ablation.json + stdout
运行：<python> experiments/gen2/exp_g2_4_l3ablation.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine              # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.health import graph_health                    # noqa: E402
from metaphor_graph.training import train_from_shg                # noqa: E402
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits  # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)
from metaphor_graph.evaluate_llmgold import (                     # noqa: E402
    build_queries_rich, filter_violations, _load_json, _chunk_of,
    GEN_CACHE, JUDGE_CACHE)
from metaphor_graph.cascade_rules import apply_rule               # noqa: E402
from metaphor_graph.observability import ObservabilityMeter       # noqa: E402

DOC_SIZE, LLM_CONF = 10, 0.85
OUT = os.path.join(HERE, "exp_g2_4_l3ablation.json")

# (标签, 级联规则, 孤儿打包规则)
VARIANTS = [
    ("A 生产现状（本体级联+兜底）", "json", "target"),
    ("B 本体级联，兜底关闭", "json", "none"),
    ("C source 级联，兜底关闭", "source", "none"),
    ("D 无级联（L3 全消融）", "none", "none"),
]


def run_variant(label, rule, orphan_rule, samples, gen_cache, judge_cache):
    ont, n_frames = build_replay_ontology(cascade_rule=rule)
    backend = build_replay_backend(ont)
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    covs, frame_covs, n_cascades_shg = [], [], []
    paths = defaultdict(lambda: {"rec": 0.0, "h3": 0, "n": 0})
    per_cfg = defaultdict(lambda: {"mrr": 0.0, "h3": 0, "rec": 0.0, "n": 0})
    a8 = {"on": 0.0, "off": 0.0, "n": 0}
    om, on = [], []
    n_q = 0
    n_l1 = 0

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=backend,
                                 orphan_cascade_rule=orphan_rule).build(
            chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        n_l1 += len(l1)
        h = graph_health(shg)
        covs.append(h.cascade_coverage)
        frame_covs.append(h.frame_coverage)
        n_cascades_shg.append(len(shg.cascades))

        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        try:
            scorer, _ = train_from_shg(shg, chunk_order=chunk_order,
                                       chunks=chunk_map, ontology=ont)
        except Exception:
            scorer = None

        # Q_cas（by-construction，A8 口径）
        for e in l1:
            if not e.frame_id:
                continue
            gold = set()
            for o in l1:
                if o.frame_id == e.frame_id:
                    gold |= {sp.chunk_id for sp in o.chunk_spans}
            if len(gold) < 2:
                continue
            query = "，".join(dict.fromkeys(t for t in e.triggers if t))
            if not query or not any(t in query for t in ont._trigger_index):
                continue
            onids = eng.cross_domain_retrieve(query, adaptive=True).chunk_ids
            offids = eng.cross_domain_retrieve(query, adaptive=False).chunk_ids
            for cid, key in ((onids, "on"), (offids, "off")):
                a8[key] += len(gold & set(cid[:10])) / len(gold)
            a8["n"] += 1

        if scorer is None:
            continue
        qs = filter_violations(build_queries_rich(shg, chunk_map, did), gen_cache)
        for q in qs:
            o = ObservabilityMeter(ont).measure(q["question"])
            om.append(o.omega)
            on.append(o.omega_n)
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gch = {_chunk_of(e) for e in shg.edges if e.id in rel and _chunk_of(e)}
            if not gch:
                continue
            n_q += 1
            cross = eng.cross_domain_retrieve(q["question"]).chunk_ids
            literal = [f"{did}_c{i}" for i, c in enumerate(chunk_texts)
                       if q["question"] in c]
            for name, ranked in (("path_cross", cross), ("path_literal", literal)):
                top = set(ranked[:10])
                paths[name]["rec"] += len(gch & top) / len(gch)
                paths[name]["h3"] += 1 if any(c in gch for c in ranked[:3]) else 0
                paths[name]["n"] += 1
            for cfg, ranked in score_conditions(eng, scorer, q["question"]).items():
                m = _mrr_hits(ranked, sorted(gch))
                a = per_cfg[cfg]
                a["mrr"] += m["mrr"]
                a["h3"] += m["hits@3"]
                a["rec"] += len(gch & set(c for c, _ in ranked[:10])) / len(gch)
                a["n"] += 1

    def _agg(a):
        kk = max(1, a["n"])
        return {k2: (v / kk if k2 != "n" else v) for k2, v in a.items()}

    nom = max(1, len(om))
    return dict(
        label=label, rule=rule, orphan_rule=orphan_rule, n_l1=n_l1,
        cascade_coverage_min=min(covs), cascade_coverage_mean=sum(covs) / len(covs),
        frame_coverage_min=min(frame_covs),
        n_cascades_ont=len(ont.cascades),
        n_cascades_shg_mean=sum(n_cascades_shg) / max(1, len(n_cascades_shg)),
        paths={k: _agg(v) for k, v in paths.items()},
        per_cfg={k: _agg(v) for k, v in per_cfg.items()},
        a8={**{k: v / max(1, a8["n"]) for k, v in a8.items() if k != "n"},
            "n": a8["n"]},
        n_llm_queries=n_q,
        omega=dict(n=nom, mean=sum(om) / nom,
                   zero_frac=sum(1 for v in om if v == 0) / nom,
                   omega_n_mean=sum(on) / nom,
                   omega_n_pos_frac=sum(1 for v in on if v > 0) / nom),
    )


def main():
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)
    print("=" * 100)
    print(f"gen2 实验 4：L3 消融与覆盖率归因（CCL2018 n={len(samples)}，$0 重放）")
    print("=" * 100)
    out = {}
    for label, rule, orph in VARIANTS:
        r = run_variant(label, rule, orph, samples, gen_cache, judge_cache)
        out[label] = r
        p, pc = r["paths"], r["per_cfg"]
        print(f"\n[{label}]  本体级联 {r['n_cascades_ont']}"
              f"  shg 级联均值 {r['n_cascades_shg_mean']:.1f}  L1 边 {r['n_l1']}")
        print(f"  L3 级联覆盖 min={r['cascade_coverage_min']:.4f}"
              f" mean={r['cascade_coverage_mean']:.4f}"
              f"  （L2 框架覆盖 min={r['frame_coverage_min']:.4f}）")
        print(f"  改写查询 n={r['n_llm_queries']}"
              f"  级联通路 Recall@10={p['path_cross']['rec']:.4f}"
              f" Hits@3={p['path_cross']['h3']:.4f}")
        hw, tr = pc.get("hand_weighted", {}), pc.get("trained", {})
        if hw:
            print(f"  语义超图(人工加权) MRR={hw['mrr']:.4f} Hits@3={hw['h3']:.4f}")
        if tr:
            print(f"  语义超图(训练后)   MRR={tr['mrr']:.4f} Hits@3={tr['h3']:.4f}")
        print(f"  Q_cas Recall@10 开={r['a8']['on']:.4f} 关={r['a8']['off']:.4f}"
              f" (n={r['a8']['n']})")
        o = r["omega"]
        print(f"  Ω mean={o['mean']:.4f}  Ω_N mean={o['omega_n_mean']:.4f}"
              f"  Ω_N>0 {o['omega_n_pos_frac']:.1%}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
