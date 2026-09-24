# -*- coding: utf-8 -*-
"""gen2 实验 3：级联构造规则 × 检索指标 的受控对照。

**这是本次调查的核心实验**：级联层的质量到底动没动任何已上报数字？

方法：固定其余一切（同一份本体框架、同一份 LLM 缓存重放、同一份语料、
同一套查询构造），只替换 L3 级联构造规则，逐个跑：

  1. 结构统计（级联数 / 规模 / 跨目标域率 / 单例率 / 框架覆盖）
  2. 检索指标：
     - 触发词级联通路 Recall@10 / Hits@3（`cross_domain_retrieve`，改写查询）
     - 语义超图通路 MRR@10 / Hits@3 / Hits@10 / Recall@10（`score_conditions`）
     - Q_cas 级联查询 Recall@10（A8 用的那批）
  3. L2/L3 覆盖率（`graph_health.hierarchy_coverage`，门槛 >0.85）
  4. Ω 与 Ω_N（`observability.measure`）

改写查询与金标来自 data/llm_cache_paraphrase.json + data/llm_cache_judge.json
（真实 LLM 产物，重放零请求），口径与 evaluate_llmgold.stage_eval 一致。

产物：experiments/gen2/exp_g2_3_rules.json + stdout

运行：<python> experiments/gen2/exp_g2_3_rules.py [--rules json,source,ground,...]
"""

from __future__ import annotations

import argparse
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
from metaphor_graph.training import (train_from_shg, MetaphorScorer,
                                     build_training_set)
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits  # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend, build_queries)
from metaphor_graph.evaluate_llmgold import (                     # noqa: E402
    build_queries_rich, filter_violations, _load_json, _chunk_of,
    GEN_CACHE, JUDGE_CACHE)
from metaphor_graph.cascade_rules import (CASCADE_RULES, cascade_stats,  # noqa: E402
                                          apply_rule)
from metaphor_graph.observability import ObservabilityMeter       # noqa: E402

DOC_SIZE, LLM_CONF = 10, 0.85
OUT = os.path.join(HERE, "exp_g2_3_rules.json")


def build_docs(ont, backend, samples, orphan_rule="target"):
    """建图 + 训练排序器（每个规则各自建一遍，保证训练信号同源）。"""
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    docs = {}
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
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        try:
            scorer, _ds = train_from_shg(shg, chunk_order=chunk_order,
                                         chunks=chunk_map, ontology=ont)
        except Exception:
            scorer = None
        docs[did] = dict(shg=shg, eng=eng, scorer=scorer, chunks=chunk_texts,
                         chunk_map=chunk_map)
    return docs


def eval_rule(rule, samples, gen_cache, judge_cache, orphan_rule="target"):
    """跑一个规则下的全部指标。"""
    ont, n_frames = build_replay_ontology(cascade_rule=rule)
    backend = build_replay_backend(ont)
    docs = build_docs(ont, backend, samples, orphan_rule=orphan_rule)

    st = cascade_stats(ont.cascades, ont.frames)
    # 覆盖率：对每个文档算 hierarchy_coverage，取 min/mean（门槛 >0.85 看 min）
    covs = [graph_health(d["shg"]).hierarchy_coverage for d in docs.values()]
    frame_covs = [graph_health(d["shg"]).frame_coverage for d in docs.values()]

    # ---- 改写查询（LLM 金标口径，与 evaluate_llmgold.stage_eval 一致）----
    paths = defaultdict(lambda: {"rec": 0.0, "h3": 0, "h10": 0, "n": 0})
    per_cfg = defaultdict(lambda: {"mrr": 0.0, "h3": 0, "h10": 0, "rec": 0.0, "n": 0})
    n_q = 0
    for did, d in docs.items():
        shg, eng, scorer = d["shg"], d["eng"], d["scorer"]
        if scorer is None:
            continue
        qs = filter_violations(build_queries_rich(shg, d["chunk_map"], did),
                               gen_cache)
        for q in qs:
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {_chunk_of(e) for e in shg.edges
                           if e.id in rel and _chunk_of(e)}
            if not gold_chunks:
                continue
            n_q += 1
            cross = eng.cross_domain_retrieve(q["question"]).chunk_ids
            literal = [f"{did}_c{i}" for i, c in enumerate(d["chunks"])
                       if q["question"] in c]
            for name, ranked in (("path_cross", cross), ("path_literal", literal)):
                g = gold_chunks
                top = set(ranked[:10])
                paths[name]["rec"] += len(g & top) / len(g)
                paths[name]["h3"] += 1 if any(c in g for c in ranked[:3]) else 0
                paths[name]["h10"] += 1 if any(c in g for c in ranked[:10]) else 0
                paths[name]["n"] += 1
            # 语义超图通路（score_conditions 返回 {cfg: [(chunk_id, score)]}）
            for cfg, ranked in score_conditions(eng, scorer, q["question"]).items():
                m = _mrr_hits(ranked, sorted(gold_chunks))
                a = per_cfg[cfg]
                a["mrr"] += m["mrr"]
                a["h3"] += m["hits@3"]
                a["h10"] += m["hits@10"]
                top = set(c for c, _ in ranked[:10])
                a["rec"] += len(gold_chunks & top) / len(gold_chunks)
                a["n"] += 1

    # ---- Q_cas（A8 口径，by-construction）----
    a8 = {"on": 0.0, "off": 0.0, "n": 0}
    for did, d in docs.items():
        for query, gold in build_queries(d["shg"], ont)["q_cas"]:
            if not any(t in query for t in ont._trigger_index):
                continue
            on = d["eng"].cross_domain_retrieve(query, adaptive=True).chunk_ids
            off = d["eng"].cross_domain_retrieve(query, adaptive=False).chunk_ids
            for cid, key in ((on, "on"), (off, "off")):
                a8[key] += len(gold & set(cid[:10])) / len(gold) if gold else 1.0
            a8["n"] += 1

    # ---- Ω / Ω_N ----
    meter = ObservabilityMeter(ont)
    om_vals, on_vals, on_pos = [], [], 0
    for did, d in docs.items():
        qs = filter_violations(build_queries_rich(d["shg"], d["chunk_map"], did),
                               gen_cache)
        for q in qs:
            o = meter.measure(q["question"])
            om_vals.append(o.omega)
            on_vals.append(o.omega_n)
            if o.omega_n > 0:
                on_pos += 1
    n_om = max(1, len(om_vals))

    def _agg(a):
        k = max(1, a["n"])
        return {kk: (vv / k if kk not in ("n",) else vv) for kk, vv in a.items()}

    return dict(
        rule=rule, n_frames=n_frames, structure=st,
        coverage=dict(min=min(covs), mean=sum(covs) / len(covs),
                      frame_min=min(frame_covs)),
        paths={k: _agg(v) for k, v in paths.items()},
        per_cfg={k: _agg(v) for k, v in per_cfg.items()},
        a8={**{k: (v / max(1, a8["n"])) for k, v in a8.items() if k != "n"},
            "n": a8["n"]},
        n_llm_queries=n_q,
        omega=dict(n=n_om, mean=sum(om_vals) / n_om,
                   zero_frac=sum(1 for v in om_vals if v == 0) / n_om,
                   omega_n_mean=sum(on_vals) / n_om,
                   omega_n_pos_frac=on_pos / n_om),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="json,target,source,ground,metanet,source_type,none")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    rules = [r.strip() for r in args.rules.split(",") if r.strip()]

    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)
    print("=" * 100)
    print(f"gen2 实验 3：级联构造规则 × 检索指标（CCL2018 n={len(samples)}，"
          f"LLM 改写金标缓存 {len(judge_cache)} 条，$0 重放）")
    print("=" * 100)

    results = {}
    for r in rules:
        res = eval_rule(r, samples, gen_cache, judge_cache)
        results[r] = res
        s, p, pc = res["structure"], res["paths"], res["per_cfg"]
        print(f"\n[{r}] 级联 {s['n_cascades']}  规模 median={s['size_median']:.1f}"
              f" max={s['size_max']}  跨目标域 {s['cross_target_rate']:.1%}"
              f"  单例 {s['singleton_rate']:.1%}  框架覆盖 {s['frame_cascade_coverage']:.1%}")
        print(f"  L2/L3 覆盖率 min={res['coverage']['min']:.4f}"
              f" mean={res['coverage']['mean']:.4f}"
              f"（门槛 0.85 {'✅' if res['coverage']['min'] >= 0.85 else '❌'}）")
        print(f"  改写查询 n={res['n_llm_queries']}"
              f"  触发词级联通路 Recall@10={p['path_cross']['rec']:.4f}"
              f" Hits@3={p['path_cross']['h3']:.4f}")
        print(f"  字面通路 Recall@10={p['path_literal']['rec']:.4f}")
        hw = pc.get("hand_weighted", {})
        tr = pc.get("trained", {})
        if hw:
            print(f"  语义超图通路(人工加权) MRR={hw['mrr']:.4f} Hits@3={hw['h3']:.4f}"
                  f" Recall@10={hw['rec']:.4f}")
        if tr:
            print(f"  语义超图通路(训练后)   MRR={tr['mrr']:.4f} Hits@3={tr['h3']:.4f}"
                  f" Recall@10={tr['rec']:.4f}")
        print(f"  Q_cas Recall@10 开阈值={res['a8']['on']:.4f}"
              f" 关阈值={res['a8']['off']:.4f} (n={res['a8']['n']})")
        o = res["omega"]
        print(f"  Ω mean={o['mean']:.4f} Ω=0 占比={o['zero_frac']:.1%}"
              f"  Ω_N mean={o['omega_n_mean']:.4f}"
              f"  Ω_N>0 占比={o['omega_n_pos_frac']:.1%}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
