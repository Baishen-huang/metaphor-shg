# -*- coding: utf-8 -*-
"""gen2 实验 8：Ω_N 复活后，Ω 本身是否获得信息？（分量级归因）

实验 7 显示 Ω_N 从 1.4% 复活到 14.8%（source）/18.0%（source_type），但
Spearman ρ(Ω, n_seed) 仍停在 0.995 —— 说明 Ω **整体**仍是 1-bit 指示器。
本实验把 Ω 拆开，分别测三个分量对「级联通路非空」的判别力：

  AUC(Ω)  vs  AUC(Ω_N)  vs  AUC(Ω_E)  vs  AUC(Ω_F)  vs  AUC(n_seed)

全样本 + 去掉 Ω=0 样本两档。若 Ω_N 单独在非零子集上判别力显著高于 Ω，
说明「Ω 的合成方式（几何平均 + 完备度因子）把 Ω_N 的信息稀释掉了」——
这是与上一轮不同的结论（上一轮 Ω_N 恒为 0，无从谈起）。

同时给出 Ω_N 与 Ω 在 Ω>0 子集内的 Spearman ρ（分量是否真被吸收进 Ω）。

产物：experiments/gen2/exp_g2_8_omega_attrib.json + stdout
运行：<python> experiments/gen2/exp_g2_8_omega_attrib.py
"""

from __future__ import annotations

import json
import logging
import os
import sys

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
OUT = os.path.join(HERE, "exp_g2_8_omega_attrib.json")


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
                omega=o.omega, omega_n=o.omega_n, omega_e=o.omega_e,
                omega_f=o.omega_f, comp=o.completeness,
                n_seed=float(len(matched_triggers(q["question"], ont))),
                nonempty=1 if res.chunk_ids else 0,
                n_emergent=float(len(o.emergent_targets))))
    return rows


def main():
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    print("=" * 96)
    print("gen2 实验 8：Ω 的分量级归因 —— Ω_N 复活后是否被 Ω 吸收")
    print("=" * 96)
    out = {}
    for rule in ("json", "source", "metanet", "source_type"):
        rows = collect(rule, samples, gen_cache)
        nz = [r for r in rows if r["omega"] > 0]
        res = {"rule": rule, "n": len(rows), "n_nonzero_omega": len(nz)}
        for tag, sub in (("all", rows), ("nonzero", nz)):
            pos = [r for r in sub if r["nonempty"]]
            neg = [r for r in sub if not r["nonempty"]]
            res[tag] = {}
            for name in ("omega", "omega_n", "omega_e", "omega_f", "n_seed",
                         "n_emergent"):
                a = [r[name] for r in pos]
                b = [r[name] for r in neg]
                res[tag][f"auc_{name}"] = (S.auc(a, b)
                                           if a and b else float("nan"))
        # Ω_N 与 Ω 在非零子集内的秩相关（分量是否被吸收）
        if len(nz) > 3:
            rho, p, _n = S.spearman([r["omega"] for r in nz],
                                    [r["omega_n"] for r in nz])
            res["spearman_omega_omegaN_nonzero"] = rho
            res["spearman_omega_omegaN_p"] = p
        out[rule] = res
        print(f"\n[{rule}] n={res['n']}  Ω>0 子集 n={res['n_nonzero_omega']}")
        print(f"  {'指标':14s} {'AUC 全样本':>12s} {'AUC Ω>0 子集':>14s}")
        for name in ("omega", "omega_n", "omega_e", "omega_f", "n_seed",
                     "n_emergent"):
            print(f"  {name:14s} {res['all'][f'auc_{name}']:>12.4f} "
                  f"{res['nonzero'][f'auc_{name}']:>14.4f}")
        if "spearman_omega_omegaN_nonzero" in res:
            print(f"  ρ(Ω, Ω_N) | Ω>0 = "
                  f"{res['spearman_omega_omegaN_nonzero']:.4f} "
                  f"(p={res['spearman_omega_omegaN_p']:.2e})")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
