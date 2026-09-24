# -*- coding: utf-8 -*-
"""gen2 实验 7：Ω_N 是否复活，以及 Ω 是否获得超出 1-bit 指示器的信息。

上一轮（exp/omega）的裁决是：Ω_N 是**死分量**（生产本体 758 级联中 752 个
成员共享单一目标域 → 涌现目标域恒为空集），迫使 Ω 塌缩成「查询有没有命中
任何一个触发词」这个 1-bit 指示器（Spearman ρ(Ω, n_seed)=0.9949）。

本实验在**替代级联构造规则**下重跑同一套判定，逐条复算：

  1. Ω_N>0 的查询占比（复活判据：现状 1.4% → ?）
  2. Spearman ρ(Ω, n_seed_triggers)（现状 0.9949）
  3. 「Ω>0 ⟺ n_seed≥1」逐条一致率（现状 632/632 = 100%）
  4. AUC(Ω 预测「级联通路非空」) 全样本 + 去掉 Ω=0 样本
  5. Ω 门控 vs 现有 `if not agg` 判据的漏检数

统计量用 experiments/_stats.py（与上一轮同一套实现，含并列修正）。

产物：experiments/gen2/exp_g2_7_omega.json + stdout
运行：<python> experiments/gen2/exp_g2_7_omega.py
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

import _stats as S                                              # noqa: E402

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine              # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)
from metaphor_graph.evaluate_llmgold import (                     # noqa: E402
    build_queries_rich, filter_violations, _load_json, GEN_CACHE)
from metaphor_graph.observability import measure, matched_triggers  # noqa: E402

DOC_SIZE, LLM_CONF = 10, 0.85
OUT = os.path.join(HERE, "exp_g2_7_omega.json")
RULES = ["json", "source", "metanet", "ground", "source_type", "none"]


def run_rule(rule, samples, gen_cache):
    ont, n_frames = build_replay_ontology(cascade_rule=rule)
    backend = build_replay_backend(ont)
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    rows = []
    for di in range(n_docs):
        ct = [s.text for s in samples[di * k:(di + 1) * k]]
        if not ct:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=backend,
                                 orphan_cascade_rule="target").build(ct, doc_id=did)
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, ct, doc_id=did, ontology=ont)
        qs = filter_violations(build_queries_rich(
            shg, {f"{did}_c{i}": c for i, c in enumerate(ct)}, did), gen_cache)
        for q in qs:
            o = measure(q["question"], ont)
            n_seed = len(matched_triggers(q["question"], ont))
            res = eng.cross_domain_retrieve(q["question"])
            rows.append(dict(
                omega=o.omega, omega_e=o.omega_e, omega_n=o.omega_n,
                omega_f=o.omega_f, comp=o.completeness,
                n_seed=n_seed, n_frames=o.n_activated_frames,
                nonempty=1 if res.chunk_ids else 0,
                n_hit=len(res.chunk_ids),
                n_cascades=len(o.activated_cascades),
                n_emergent=len(o.emergent_targets),
            ))
    n = len(rows)
    om = [r["omega"] for r in rows]
    on = [r["omega_n"] for r in rows]
    ns = [float(r["n_seed"]) for r in rows]
    rho, p_rho, _ = S.spearman(om, ns)
    # Ω>0 ⟺ n_seed≥1 逐条一致率
    agree = sum(1 for r in rows if (r["omega"] > 0) == (r["n_seed"] >= 1))
    # AUC(Ω 预测「级联通路非空」)
    pos = [r["omega"] for r in rows if r["nonempty"]]
    neg = [r["omega"] for r in rows if not r["nonempty"]]
    auc_all = S.auc(pos, neg) if pos and neg else float("nan")
    # 去掉 Ω=0 样本
    nz = [r for r in rows if r["omega"] > 0]
    p2 = [r["omega"] for r in nz if r["nonempty"]]
    n2 = [r["omega"] for r in nz if not r["nonempty"]]
    auc_nz = S.auc(p2, n2) if p2 and n2 else float("nan")
    # 门控对比：Ω=0 但通路非空（Ω 门控漏检）vs n_seed=0 但通路非空（现有判据漏检）
    omega_miss = sum(1 for r in rows if r["omega"] == 0 and r["nonempty"])
    base_miss = sum(1 for r in rows if r["n_seed"] == 0 and r["nonempty"])
    # Ω_N 的独立信息：在 n_seed 固定的子集内，Ω_N 是否仍变化
    by_seed = defaultdict(list)
    for r in rows:
        by_seed[r["n_seed"]].append(r["omega_n"])
    on_var_within_seed = {str(k2): (max(v) - min(v)) for k2, v in by_seed.items()
                          if len(v) >= 3}
    return dict(
        rule=rule, n=n, n_omega_pos=sum(1 for v in om if v > 0),
        omega_mean=S.mean(om), omega_zero_frac=sum(1 for v in om if v == 0) / n,
        omega_n_mean=S.mean(on),
        omega_n_pos=sum(1 for v in on if v > 0),
        omega_n_pos_frac=sum(1 for v in on if v > 0) / n,
        spearman_omega_nseed=rho, spearman_p=p_rho,
        omega_pos_iff_nseed_pos=agree / n,
        auc_cascade_nonempty_all=auc_all,
        auc_cascade_nonempty_nonzero_omega=auc_nz,
        n_nonzero_omega=len(nz),
        gate_miss_omega=omega_miss, gate_miss_nseed=base_miss,
        omega_n_range_within_fixed_seed=on_var_within_seed,
        rows_sample=rows[:5],
    )


def main():
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    print("=" * 100)
    print("gen2 实验 7：Ω_N 复活判定与 Ω 的信息量（改写查询，$0 重放）")
    print("=" * 100)
    out = {}
    for rule in RULES:
        r = run_rule(rule, samples, gen_cache)
        out[rule] = r
        print(f"\n[{rule}] n={r['n']}")
        print(f"  Ω_N>0: {r['omega_n_pos']}/{r['n']} = {r['omega_n_pos_frac']:.3f}"
              f"   Ω_N mean={r['omega_n_mean']:.4f}")
        print(f"  ρ(Ω, n_seed) = {r['spearman_omega_nseed']:.4f}"
              f"  (p={r['spearman_p']:.2e})")
        print(f"  「Ω>0 ⟺ n_seed≥1」一致率 = {r['omega_pos_iff_nseed_pos']:.4f}")
        print(f"  AUC(Ω → 级联通路非空) 全样本 = {r['auc_cascade_nonempty_all']:.4f}"
              f"   去 Ω=0 后 = {r['auc_cascade_nonempty_nonzero_omega']:.4f}"
              f" (n={r['n_nonzero_omega']})")
        print(f"  门控漏检：Ω 门控 {r['gate_miss_omega']} 条 /"
              f" n_seed 判据 {r['gate_miss_nseed']} 条")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
