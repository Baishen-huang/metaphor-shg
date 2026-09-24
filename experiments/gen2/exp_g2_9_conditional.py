# -*- coding: utf-8 -*-
"""gen2 实验 9：Ω_N 的信息量是否**超出** n_seed（条件判别检验）。

实验 8 发现：在 Ω>0 子集内，`n_emergent`（涌现目标域**原始计数**）对「级联通路
非空」的 AUC 达到 0.836（source）/ 0.874（source_type），高于 Ω 自身的
0.654 / 0.839。但这两个量都与 n_seed 正相关（触发词越多 → 点亮框架越多 →
涌现目标域越多），所以必须**在 n_seed 固定的条件下**再检验一次，否则只是
n_seed 的代理。

本实验：
  1. 按 n_seed 分层（1 / 2 / 3 / ≥4），层内测 n_emergent 与 Ω_N 的 AUC；
  2. 用「层内 AUC 的加权平均」给出条件判别力（不依赖线性模型假设）；
  3. 给出 Spearman ρ(n_emergent, n_seed) 以量化两者的共线程度。

产物：experiments/gen2/exp_g2_9_conditional.json + stdout
运行：<python> experiments/gen2/exp_g2_9_conditional.py
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
OUT = os.path.join(HERE, "exp_g2_9_conditional.json")


def collect(rule, samples, gen_cache):
    ont, _ = build_replay_ontology(cascade_rule=rule)
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
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(ct, doc_id=did)
        if not [e for e in shg.edges if not e.is_extended]:
            continue
        eng = RetrievalEngine(shg, ct, doc_id=did, ontology=ont)
        qs = filter_violations(build_queries_rich(
            shg, {f"{did}_c{i}": c for i, c in enumerate(ct)}, did), gen_cache)
        for q in qs:
            o = measure(q["question"], ont)
            res = eng.cross_domain_retrieve(q["question"])
            rows.append(dict(
                omega=o.omega, omega_n=o.omega_n,
                n_seed=int(len(matched_triggers(q["question"], ont))),
                n_frames=o.n_activated_frames,
                n_emergent=len(o.emergent_targets),
                n_cascades=len(o.activated_cascades),
                nonempty=1 if res.chunk_ids else 0))
    return rows


def _boot_auc(pos, neg, n_boot=2000, seed=20260924):
    """AUC 的 bootstrap 95% CI（重采样正负样本）。零依赖实现。"""
    import random
    rng = random.Random(seed)
    if not pos or not neg:
        return float("nan"), float("nan"), float("nan")
    vals = []
    for _ in range(n_boot):
        a = [pos[rng.randrange(len(pos))] for _ in range(len(pos))]
        b = [neg[rng.randrange(len(neg))] for _ in range(len(neg))]
        vals.append(S.auc(a, b))
    vals.sort()
    lo = vals[int(0.025 * n_boot)]
    hi = vals[min(n_boot - 1, int(0.975 * n_boot))]
    return S.auc(pos, neg), lo, hi


def main():
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    print("=" * 96)
    print("gen2 实验 9：Ω_N / n_emergent 是否在 n_seed 之外携带信息（分层条件检验）")
    print("=" * 96)
    out = {}
    for rule in ("json", "source", "metanet", "source_type"):
        rows = collect(rule, samples, gen_cache)
        # 只在「有触发词命中」的子集内检验（Ω=0 的样本无信息可言）
        sub = [r for r in rows if r["n_seed"] >= 1]
        rho_ne, p_ne, _ = S.spearman([float(r["n_emergent"]) for r in sub],
                                     [float(r["n_seed"]) for r in sub])
        rho_fr, _, _ = S.spearman([float(r["n_frames"]) for r in sub],
                                  [float(r["n_seed"]) for r in sub])
        layers = defaultdict(list)
        for r in sub:
            key = str(min(r["n_seed"], 4))
            layers[key].append(r)
        per_layer = {}
        wsum, wden = 0.0, 0
        wsum_f, wden_f = 0.0, 0
        wsum_o, wden_o = 0.0, 0
        for key in sorted(layers):
            L = layers[key]
            pos = [r for r in L if r["nonempty"]]
            neg = [r for r in L if not r["nonempty"]]
            if not pos or not neg:
                per_layer[key] = dict(n=len(L), n_pos=len(pos),
                                      auc_emergent=None, auc_frames=None,
                                      auc_omega=None)
                continue
            pe = [float(r["n_emergent"]) for r in pos]
            ne = [float(r["n_emergent"]) for r in neg]
            pf = [float(r["n_frames"]) for r in pos]
            nf = [float(r["n_frames"]) for r in neg]
            po = [r["omega"] for r in pos]
            no = [r["omega"] for r in neg]
            a_e, e_lo, e_hi = _boot_auc(pe, ne)
            a_f, f_lo, f_hi = _boot_auc(pf, nf)
            a_o, o_lo, o_hi = _boot_auc(po, no)
            w = min(len(pos), len(neg))
            per_layer[key] = dict(n=len(L), n_pos=len(pos), n_neg=len(neg),
                                  auc_emergent=a_e, auc_emergent_ci=[e_lo, e_hi],
                                  auc_frames=a_f, auc_frames_ci=[f_lo, f_hi],
                                  auc_omega=a_o, auc_omega_ci=[o_lo, o_hi],
                                  weight=w)
            wsum += a_e * w
            wden += w
            wsum_f += a_f * w
            wden_f += w
            wsum_o += a_o * w
            wden_o += w
        # 全子集（不分层）的 AUC 对照
        all_pos = [r for r in sub if r["nonempty"]]
        all_neg = [r for r in sub if not r["nonempty"]]
        a_e_all, e_lo_all, e_hi_all = _boot_auc(
            [float(r["n_emergent"]) for r in all_pos],
            [float(r["n_emergent"]) for r in all_neg])
        a_o_all, o_lo_all, o_hi_all = _boot_auc(
            [r["omega"] for r in all_pos], [r["omega"] for r in all_neg])
        out[rule] = dict(
            n_all=len(rows), n_with_seed=len(sub),
            rho_emergent_nseed=rho_ne, p_emergent_nseed=p_ne,
            rho_frames_nseed=rho_fr,
            per_layer=per_layer,
            cond_auc_emergent=wsum / wden if wden else float("nan"),
            cond_auc_frames=wsum_f / wden_f if wden_f else float("nan"),
            cond_auc_omega=wsum_o / wden_o if wden_o else float("nan"),
            cond_weight=wden,
            pooled_auc_emergent=a_e_all, pooled_auc_emergent_ci=[e_lo_all, e_hi_all],
            pooled_auc_omega=a_o_all, pooled_auc_omega_ci=[o_lo_all, o_hi_all],
        )
        print(f"\n[{rule}] n_seed≥1 的样本 {len(sub)}/{len(rows)}")
        print(f"  ρ(n_emergent, n_seed) = {rho_ne:.4f} (p={p_ne:.2e})"
              f"   ρ(n_frames, n_seed) = {rho_fr:.4f}")
        print(f"  {'n_seed':>7s} {'n':>5s} {'pos':>5s} {'neg':>5s}"
              f" {'AUC(n_emergent)':>26s} {'AUC(n_frames)':>16s} {'AUC(Ω)':>18s}")
        for key, d in sorted(per_layer.items()):
            def f(x, ci=None):
                if x is None:
                    return "     n/a     "
                if ci:
                    return f"{x:.3f}[{ci[0]:.3f},{ci[1]:.3f}]"
                return f"{x:.3f}"
            print(f"  {key:>7s} {d['n']:>5d} {d['n_pos']:>5d}"
                  f" {d.get('n_neg', 0):>5d}"
                  f" {f(d['auc_emergent'], d.get('auc_emergent_ci')):>26s}"
                  f" {f(d['auc_frames'], d.get('auc_frames_ci')):>16s}"
                  f" {f(d['auc_omega'], d.get('auc_omega_ci')):>18s}")
        print(f"  层内加权 AUC：n_emergent={out[rule]['cond_auc_emergent']:.4f}"
              f"  n_frames={out[rule]['cond_auc_frames']:.4f}"
              f"  Ω={out[rule]['cond_auc_omega']:.4f}")
        print(f"  合并（不分层）AUC：n_emergent={a_e_all:.4f}"
              f"[{e_lo_all:.4f},{e_hi_all:.4f}]"
              f"   Ω={a_o_all:.4f}[{o_lo_all:.4f},{o_hi_all:.4f}]")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
