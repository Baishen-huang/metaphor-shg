# -*- coding: utf-8 -*-
"""拓扑损失的**统计显著性检验**：多种子方差 + 配对检验。

**为什么需要它**：`grid_dev.json` 的 64 配置全部用 `seed=42`。
报告里 `pers_w1` 的 deanchor ΔMRR = +0.0097 是**单次训练**的结果，
无法区分"真实效应"与"训练随机性"。本脚本补上这个缺口。

做三件事：
  1. **多种子方差**：对 baseline / pers_w1 / ctrl_randgraph 各跑 N 个种子，
     报告 ΔMRR 的均值、标准差、以及"种内 vs 种间"方差分解。
  2. **配对显著性**：per-query MRR 的配对检验（bootstrap CI + 符号检验），
     因为两种排序器面对**同一批查询**，配对检验功效更高。
  3. **裁决**：ΔMRR 的 95% CI 是否跨 0。

运行（在 `.wt/toploss` 下）：
    python experiments/math/exp_math_2_significance.py --seeds 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import exp_math_1_toploss as E1  # noqa: E402
import topo_common as TC  # noqa: E402

OUT = E1.OUT

# 检验的臂：主候选 + 两类对照
ARMS = [
    ("baseline", 0.0),
    ("pers_w1", 3.0),        # grid 中最优 λ
    ("pers_tp", 3.0),
    ("ctrl_randgraph", 1.0),
    ("ctrl_randgrad:pers_w1", 3.0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8,
                    help="每个臂的种子数（默认 8）")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    seed_list = tuple(range(1000, 1000 + args.seeds))
    print(f"=== 多种子显著性检验（每臂 {len(seed_list)} 个种子）===", flush=True)

    ctx = E1.build_context()
    Xc, covered = E1.candidate_embedding(ctx["ds"], ctx["st"],
                                         ctx["scorer"].mu, ctx["scorer"].sd)
    losses, meta = E1.make_losses(Xc, ctx["st"], ctx["scorer"].w)
    print(f"[ctx] 候选覆盖 {int(covered.sum())}/{len(covered)}", flush=True)

    results = {}
    for name, lam in ARMS:
        recs = E1.run_arm(ctx, losses, name, lam, use_test=args.test,
                          seeds=seed_list)
        results[name] = recs
        mrrs = [r["deanchor"]["mrr"] for r in recs]
        print(f"  {name:<24} deanchor MRR = {np.mean(mrrs):.4f} "
              f"± {np.std(mrrs, ddof=1):.4f}  (n={len(mrrs)})", flush=True)

    # ---- 裁决 1：多种子下 ΔMRR 的分布 ----
    base_mrrs = np.array([r["deanchor"]["mrr"] for r in results["baseline"]])
    print("\n=== 裁决 1：相对 baseline 的 ΔMRR（多种子）===")
    print(f"{'arm':<24}{'ΔMRR 均值':>12}{'标准差':>10}{'95% CI':>22}{'跨 0?':>8}")
    verdicts = {}
    for name, _ in ARMS:
        if name == "baseline":
            continue
        arm = np.array([r["deanchor"]["mrr"] for r in results[name]])
        d = arm - base_mrrs
        lo, hi = np.percentile(d, [2.5, 97.5])
        crosses = lo <= 0 <= hi
        verdicts[name] = dict(delta_mean=float(d.mean()),
                              delta_std=float(d.std(ddof=1)),
                              ci=[float(lo), float(hi)],
                              crosses_zero=bool(crosses))
        print(f"{name:<24}{d.mean():>+12.4f}{d.std(ddof=1):>10.4f}"
              f"{f'[{lo:+.4f}, {hi:+.4f}]':>22}{'是' if crosses else '否':>8}")

    # ---- 裁决 2：配对 per-query 检验（用第一个种子的 per-query MRR）----
    print("\n=== 裁决 2：per-query 配对检验（种子 = 第一个）===")
    print("（配对检验功效更高：两种排序器面对同一批查询）")
    base_pq = np.array(results["baseline"][0]["deanchor__per_mrr"])
    print(f"{'arm':<24}{'Δper-query':>12}{'bootstrap 95% CI':>24}{'符号检验 p':>12}")
    paired = {}
    rng = np.random.default_rng(20260927)
    for name, _ in ARMS:
        if name == "baseline":
            continue
        arm_pq = np.array(results[name][0]["deanchor__per_mrr"])
        if len(arm_pq) != len(base_pq):
            print(f"{name:<24} 长度不匹配（{len(arm_pq)} vs {len(base_pq)}）")
            continue
        d = arm_pq - base_pq
        # bootstrap CI
        n = len(d)
        boots = np.array([rng.choice(d, size=n, replace=True).mean()
                          for _ in range(2000)])
        lo, hi = np.percentile(boots, [2.5, 97.5])
        # 符号检验（忽略 0）
        nz = d[d != 0]
        n_pos = int((nz > 0).sum())
        n_neg = int((nz < 0).sum())
        # 双侧二项检验 p 值（正态近似，n 大时足够）
        if n_pos + n_neg > 0:
            from math import sqrt
            k = min(n_pos, n_neg)
            N = n_pos + n_neg
            z = abs(n_pos - N / 2) / sqrt(N / 4)
            p = float(2 * (1 - 0.5 * (1 + _erf(z / sqrt(2)))))
        else:
            p = 1.0
        paired[name] = dict(delta_mean=float(d.mean()), ci=[float(lo), float(hi)],
                            n_pos=n_pos, n_neg=n_neg, sign_p=p,
                            crosses_zero=bool(lo <= 0 <= hi))
        print(f"{name:<24}{d.mean():>+12.4f}"
              f"{f'[{lo:+.4f}, {hi:+.4f}]':>24}{p:>12.4f}"
              f"   (+{n_pos}/-{n_neg})")

    TC.write_json(os.path.join(OUT, "significance.json"),
                  dict(seeds=list(seed_list), verdicts=verdicts, paired=paired))
    print(f"\n[写出] {os.path.join(OUT, 'significance.json')}")


def _erf(x: float) -> float:
    """误差函数（避免依赖 scipy）。"""
    from math import exp, pi
    t = 1.0 / (1.0 + 0.3275911 * abs(x))
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * exp(-x * x)
    return y if x >= 0 else -y


if __name__ == "__main__":
    main()
