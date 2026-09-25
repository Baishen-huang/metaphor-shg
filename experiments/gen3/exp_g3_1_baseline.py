# -*- coding: utf-8 -*-
"""gen3 实验 1：基线复现 + 几何平均为何毁掉信号的**逐步机制归因**。

三件事：
  A. 复现 gen1/gen2 的基线数字（ρ(Ω, n_seed)、「Ω>0 ⟺ n_seed≥1」一致率、
     n_emergent 的条件 AUC 0.836 vs Ω 的 0.654）。**不复现就报差异，不采信。**
  B. 分量级诊断：每个分量的独立 AUC、分量间相关、以及 Ω 的**秩序**与各分量
     秩序的关系（Spearman ρ(Ω, 分量)）。特别验证「ε 下界把 Ω_N 变成常数」
     这一机制：直接测 Ω_N 的**层内取值数**与 Ω 的层内取值数。
  C. 开关对照：用 `query_signal.compose` 的四个开关（normalize / floor /
     use_completeness / outer_zero）做 2^4 全因子对照，看**哪一个开关**
     把 n_emergent 的信号抹掉。这是本报告的科学核心。

产物：experiments/gen3/exp_g3_1_baseline.json + stdout
运行：<python> experiments/gen3/exp_g3_1_baseline.py
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

import _stats as S                                              # noqa: E402
from _collect import load_dataset                               # noqa: E402
from metaphor_graph.query_signal import compose                 # noqa: E402

OUT = os.path.join(HERE, "exp_g3_1_baseline.json")
RULES = ("json", "source", "metanet", "source_type")


# ------------------------------------------------------------------ 统计工具
def boot_auc(pos, neg, n_boot=2000, seed=20260924):
    """AUC 的 bootstrap 95% CI（重采样正负样本）。与 gen2 同一实现，便于对照。"""
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
    return (S.auc(pos, neg), vals[int(0.025 * n_boot)],
            vals[min(n_boot - 1, int(0.975 * n_boot))])


def auc_ci(rows, key, target="cascade_nonempty", seed=20260924):
    pos = [r[key] for r in rows if r[target]]
    neg = [r[key] for r in rows if not r[target]]
    return boot_auc(pos, neg, seed=seed)


def stratified_auc(rows, key, target="cascade_nonempty", cap=4):
    """n_seed 分层加权 AUC（层权 = min(n_pos, n_neg)，与 gen2 同口径）。"""
    layers = defaultdict(list)
    for r in rows:
        if r["n_seed"] >= 1:
            layers[min(int(r["n_seed"]), cap)].append(r)
    wsum = wden = 0.0
    for key2, L in sorted(layers.items()):
        pos = [r[key] for r in L if r[target]]
        neg = [r[key] for r in L if not r[target]]
        if not pos or not neg:
            continue
        w = min(len(pos), len(neg))
        wsum += S.auc(pos, neg) * w
        wden += w
    return (wsum / wden) if wden else float("nan"), int(wden)


def agree_rate(rows, key, cond="n_seed"):
    """「信号 > 0 ⟺ n_seed ≥ 1」逐条一致率。"""
    n = len(rows)
    return (sum(1 for r in rows if (r[key] > 0) == (r[cond] >= 1)) / n
            if n else float("nan"))


def omega_from_row(r, *, floor, normalize, use_completeness, outer_zero):
    """按四个开关从行数据重算一个「Ω 变体」（分量口径与 Ω 完全一致）。"""
    comps = {
        "e": min(1.0, r["n_frames"] / r["n_seed"]) if r["n_seed"] else 0.0,
        "n": min(1.0, r["n_emergent"] / r["n_seed"]) if r["n_seed"] else 0.0,
        "f": r["omega_f"],
    }
    return compose(comps, n_seed=int(r["n_seed"]), completeness=r["comp"],
                   floor=floor, normalize=normalize,
                   use_completeness=use_completeness, outer_zero=outer_zero)


def main():
    print("=" * 100)
    print("gen3 实验 1：基线复现 + 几何平均毁掉信号的机制归因")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        n = len(rows)
        res = dict(rule=rule, n=n, meta=d["meta"])

        # ================================================== A. 基线复现
        rho, p_rho, _ = S.spearman([r["omega"] for r in rows],
                                   [float(r["n_seed"]) for r in rows])
        res["A_baseline"] = dict(
            n=n,
            n_seed_pos=sum(1 for r in rows if r["n_seed"] >= 1),
            omega_pos=sum(1 for r in rows if r["omega"] > 0),
            omega_zero_frac=sum(1 for r in rows if r["omega"] == 0) / n,
            omega_mean=S.mean([r["omega"] for r in rows]),
            omega_n_pos=sum(1 for r in rows if r["omega_n"] > 0),
            omega_n_mean=S.mean([r["omega_n"] for r in rows]),
            spearman_omega_nseed=rho, spearman_p=p_rho,
            omega_pos_iff_nseed_pos=agree_rate(rows, "omega"),
        )
        sub = [r for r in rows if r["n_seed"] >= 1]
        res["A_baseline"]["n_with_seed"] = len(sub)
        for key in ("n_emergent", "omega", "n_frames", "n_seed"):
            a, lo, hi = auc_ci(sub, key)
            res["A_baseline"][f"auc_{key}_in_seed_subset"] = [a, lo, hi]
        res["A_baseline"]["pooled_auc_omega_all"] = auc_ci(rows, "omega")[0]
        res["A_baseline"]["pooled_auc_emergent_all"] = auc_ci(
            rows, "n_emergent")[0]

        # ================================================== B. 分量级诊断
        diag = dict(omega_f_unique=len({r["omega_f"] for r in rows}),
                    omega_e_unique=len({r["omega_e"] for r in rows}),
                    omega_n_unique=len({r["omega_n"] for r in rows}))
        # Ω_N 在 n_seed 固定的层内是否变化（死分量判据）
        by_seed = defaultdict(list)
        for r in rows:
            if r["n_seed"] >= 1:
                by_seed[int(r["n_seed"])].append(r)
        layers = {}
        for k2, L in sorted(by_seed.items()):
            layers[str(k2)] = dict(
                n=len(L),
                n_omega_n_pos=sum(1 for r in L if r["omega_n"] > 0),
                omega_n_unique=len({r["omega_n"] for r in L}),
                n_emergent_unique=len({r["n_emergent"] for r in L}),
                omega_unique=len({r["omega"] for r in L}),
                omega_e_unique=len({r["omega_e"] for r in L}),
                omega_f_unique=len({r["omega_f"] for r in L}),
                comp_unique=len({r["comp"] for r in L}),
                # 层内：Ω 的秩序与各分量的秩序（谁在主导 Ω 的序）
                rho_omega_vs_emergent=S.spearman(
                    [r["omega"] for r in L],
                    [float(r["n_emergent"]) for r in L])[0] if len(L) >= 4 else None,
                rho_omega_vs_frames=S.spearman(
                    [r["omega"] for r in L],
                    [float(r["n_frames"]) for r in L])[0] if len(L) >= 4 else None,
                rho_omega_vs_comp=S.spearman(
                    [r["omega"] for r in L],
                    [r["comp"] for r in L])[0] if len(L) >= 4 else None,
                rho_omega_vs_omegaf=S.spearman(
                    [r["omega"] for r in L],
                    [r["omega_f"] for r in L])[0] if len(L) >= 4 else None,
            )
        diag["layers"] = layers
        # ε 下界把 Ω_N 变成常数的直接证据：
        # 在 Ω_N=0 的样本上，Ω_geo 是否等于 (Ω_E·ε·Ω_F)^(1/3)
        const_hits = const_tot = 0
        for r in rows:
            if r["n_seed"] >= 1 and r["omega_n"] == 0.0:
                const_tot += 1
                pred = compose({"e": r["omega_e"], "n": 0.0, "f": r["omega_f"]},
                               n_seed=int(r["n_seed"]), completeness=1.0,
                               floor=True, normalize=True,
                               use_completeness=False, outer_zero=True)
                if abs(pred - r["omega_geo"]) < 1e-12:
                    const_hits += 1
        diag["eps_floor_constant_identity"] = dict(
            n_omega_n_zero_with_seed=const_tot,
            n_matching_geo=const_hits,
            rate=const_hits / const_tot if const_tot else float("nan"))
        # 分量之间的相关（层内，n_seed 固定）
        if len(sub) >= 4:
            diag["spearman_within_seed_subset"] = {
                "emergent_vs_frames": S.spearman(
                    [float(r["n_emergent"]) for r in sub],
                    [float(r["n_frames"]) for r in sub])[0],
                "emergent_vs_cascades": S.spearman(
                    [float(r["n_emergent"]) for r in sub],
                    [float(r["n_cascades"]) for r in sub])[0],
                "omega_vs_emergent": S.spearman(
                    [r["omega"] for r in sub],
                    [float(r["n_emergent"]) for r in sub])[0],
                "omega_vs_comp": S.spearman(
                    [r["omega"] for r in sub], [r["comp"] for r in sub])[0],
                "comp_vs_seed": S.spearman(
                    [r["comp"] for r in sub],
                    [float(r["n_seed"]) for r in sub])[0],
                "comp_vs_qlen": S.spearman(
                    [r["comp"] for r in sub], [float(r["qlen"]) for r in sub])[0],
            }
        # 完备度与「有没有命中触发词」的共线程度（全样本）
        diag["comp_collinearity"] = dict(
            auc_comp_all=auc_ci(rows, "comp")[0],
            auc_comp_in_subset=auc_ci(sub, "comp")[0] if sub else None,
            rho_comp_seed_all=S.spearman([r["comp"] for r in rows],
                                         [float(r["n_seed"]) for r in rows])[0],
        )
        res["B_diagnosis"] = diag

        # ================================================== C. 2^4 开关对照
        grid = {}
        for floor, norm, comp, oz in itertools.product((False, True), repeat=4):
            tag = (f"floor={int(floor)},div={int(norm)},"
                   f"comp={int(comp)},outer0={int(oz)}")
            vals = [omega_from_row(r, floor=floor, normalize=norm,
                                   use_completeness=comp, outer_zero=oz)
                    for r in rows]
            tmp = [{**r, "_v": v} for r, v in zip(rows, vals)]
            subv = [t for t in tmp if t["n_seed"] >= 1]
            a_all, lo_all, hi_all = boot_auc(
                [t["_v"] for t in tmp if t["cascade_nonempty"]],
                [t["_v"] for t in tmp if not t["cascade_nonempty"]])
            a_sub, lo_sub, hi_sub = boot_auc(
                [t["_v"] for t in subv if t["cascade_nonempty"]],
                [t["_v"] for t in subv if not t["cascade_nonempty"]])
            cond, wden = stratified_auc(tmp, "_v")
            rho2 = S.spearman(vals, [float(r["n_seed"]) for r in rows])[0]
            grid[tag] = dict(
                auc_all=a_all, auc_all_ci=[lo_all, hi_all],
                auc_subset=a_sub, auc_subset_ci=[lo_sub, hi_sub],
                cond_auc=cond, cond_weight=wden,
                spearman_nseed=rho2,
                agree_1bit=agree_rate(tmp, "_v"),
                n_pos=sum(1 for t in tmp if t["_v"] > 0),
                mean=S.mean(vals),
            )
        res["C_switch_grid"] = grid
        # Ω 自身放进同一张表（作为 reference，不是重算值）
        res["C_switch_grid"]["[omega]"] = dict(
            auc_all=auc_ci(rows, "omega")[0],
            auc_subset=auc_ci(sub, "omega")[0],
            cond_auc=stratified_auc(rows, "omega")[0],
            spearman_nseed=rho, agree_1bit=agree_rate(rows, "omega"),
            n_pos=sum(1 for r in rows if r["omega"] > 0),
            mean=S.mean([r["omega"] for r in rows]))
        out[rule] = res

        # ---------------------------------------------------------- 打印
        b = res["A_baseline"]
        print(f"\n{'=' * 100}\n[{rule}] n={n}\n{'=' * 100}")
        print(f"[A 基线复现]")
        print(f"  n_seed≥1: {b['n_seed_pos']}   Ω>0: {b['omega_pos']}"
              f"   Ω=0 占比 {b['omega_zero_frac']:.4f}   Ω mean {b['omega_mean']:.6f}")
        print(f"  Ω_N>0: {b['omega_n_pos']} ({b['omega_n_pos'] / n:.4f})"
              f"   Ω_N mean {b['omega_n_mean']:.4f}")
        print(f"  ρ(Ω, n_seed) = {rho:.4f}  (p={p_rho:.2e})"
              f"   「Ω>0 ⟺ n_seed≥1」= {b['omega_pos_iff_nseed_pos']:.4f}")
        print(f"  AUC 全样本：Ω={b['pooled_auc_omega_all']:.4f}"
              f"  n_emergent={b['pooled_auc_emergent_all']:.4f}")
        print(f"  AUC 在 n_seed≥1 子集（n={b['n_with_seed']}）：")
        for key in ("n_emergent", "omega", "n_frames", "n_seed"):
            a, lo, hi = b[f"auc_{key}_in_seed_subset"]
            print(f"    {key:12s} {a:.4f} [{lo:.4f}, {hi:.4f}]")
        print(f"[B 分量诊断]")
        print(f"  取值数（全样本）：Ω_F={diag['omega_f_unique']}"
              f"  Ω_E={diag['omega_e_unique']}  Ω_N={diag['omega_n_unique']}")
        ef = diag["eps_floor_constant_identity"]
        print(f"  ε 下界恒等式：Ω_N=0 且有触发词的 {ef['n_omega_n_zero_with_seed']}"
              f" 条中，Ω_geo == (Ω_E·ε·Ω_F)^(1/3) 的有 {ef['n_matching_geo']} 条"
              f"（{ef['rate']:.4f}）")
        for k2, L in layers.items():
            print(f"  n_seed={k2}: n={L['n']:4d}  Ω_N>0 {L['n_omega_n_pos']:3d}"
                  f"  Ω_N 取值数 {L['omega_n_unique']:3d}"
                  f"  n_emergent 取值数 {L['n_emergent_unique']:3d}"
                  f"  Ω 取值数 {L['omega_unique']:4d}"
                  f"  ρ(Ω,em)={L['rho_omega_vs_emergent']}"
                  f"  ρ(Ω,comp)={L['rho_omega_vs_comp']}")
        cc = diag["comp_collinearity"]
        print(f"  完备度：AUC 全样本 {cc['auc_comp_all']:.4f}"
              f"  子集 {cc['auc_comp_in_subset']}"
              f"  ρ(comp, n_seed)={cc['rho_comp_seed_all']:.4f}")
        print(f"[C 2^4 开关对照]（目标 = 级联通路非空）")
        print(f"  {'开关组合':42s} {'AUC全':>7s} {'AUC子集':>24s}"
              f" {'层内AUC':>8s} {'ρ(nseed)':>9s} {'1bit':>7s}")
        for tag, g in grid.items():
            if tag == "[omega]":
                continue
            print(f"  {tag:42s} {g['auc_all']:>7.4f}"
                  f" {g['auc_subset']:>10.4f}[{g['auc_subset_ci'][0]:.3f},"
                  f"{g['auc_subset_ci'][1]:.3f}]"
                  f" {g['cond_auc']:>8.4f} {g['spearman_nseed']:>9.4f}"
                  f" {g['agree_1bit']:>7.4f}")
        g = grid["[omega]"]
        print(f"  {'[Ω 实际值]':42s} {g['auc_all']:>7.4f}"
              f" {g['auc_subset']:>10.4f}{'':14s}"
              f" {g['cond_auc']:>8.4f} {g['spearman_nseed']:>9.4f}"
              f" {g['agree_1bit']:>7.4f}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
