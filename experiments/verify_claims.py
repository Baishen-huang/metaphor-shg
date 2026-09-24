# -*- coding: utf-8 -*-
"""步骤 0：验证任务书里声称的 4 条既成事实（在改动 hgnn.py 之前先独立复现）。

声称：
 1. S 行和恰为 1.0（行随机），谱半径 1.0
 2. 无源项时 X ← M X 收敛到连通分量的平稳分布 → 同分量节点向量相同
 3. metaphor_coherence 退化为「是否同分量」的近似二值指示
 4. 加源项（u = (1-a)S + a T(u)）保住源身份：同分量平均余弦 ≈ 0.17-0.21

运行：python experiments/verify_claims.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (all_graphs, build_graph, components, incidence, label,
                     S_matrix, M_matrix, cos, spectral_report, write_json)

import numpy as np


def main():
    out = {}
    print("=" * 78)
    print("步骤 0 —— 独立复核任务书声称的 4 条事实")
    print("=" * 78)

    # ---------- 事实 1：行和 / 谱半径 ----------
    print("\n[1] S 行和与谱半径")
    print(f"{'doc':16s} {'V':>4s} {'E':>4s} {'iso':>4s} {'#comp':>6s} "
          f"{'S行和(min,max,活节点)':>26s} {'rho(S)':>8s} {'rho(M)':>8s}")
    reps = {}
    for did, g in all_graphs(layers=2).items():
        r = spectral_report(g, leak=0.0)
        reps[did] = r
        print(f"{did:16s} {r['num_nodes']:>4d} {r['num_hyperedges']:>4d} "
              f"{r['isolated_nodes']:>4d} {r['num_components']:>6d} "
              f"({r['S_rowsum_min_live']:.6f},{r['S_rowsum_max_live']:.6f})"
              f"{'':>6s} {r['S_rho']:>8.6f} {r['M_rho']:>8.6f}")
        print(f"{'':16s} 活节点行和 == 1 精确成立: {r['S_rowsum_exact_one_live']} | "
              f"孤立节点数(行和 0): {r['isolated_nodes']}")
    out["spectral"] = reps

    # ---------- 事实 2：无源项迭代收敛到分量平稳分布 ----------
    print("\n[2] 无源项 X ← M X 迭代（layers=500）是否抹平源身份")
    print(f"{'doc':16s} {'同分量余弦均值':>14s} {'配对数':>8s} {'最大逐节点偏差':>16s}")
    iters = 500
    conv = {}
    for did, g in all_graphs(layers=1).items():
        M = M_matrix(g)
        X = g.X.copy()
        for _ in range(iters):
            X = M @ X
        m, n = _within_cos(g, X)
        # 分量内最大偏差
        dev = 0.0
        for comp in components(g):
            comp = [i for i in comp if np.linalg.norm(X[i]) > 1e-12]
            for a in range(len(comp)):
                for b in range(a + 1, len(comp)):
                    va, vb = X[comp[a]], X[comp[b]]
                    dev = max(dev, float(np.max(np.abs(va / (np.linalg.norm(va) + 1e-12)
                                                    - vb / (np.linalg.norm(vb) + 1e-12)))))
        conv[did] = {"within_cos_mean": m, "n_pairs": n, "max_unit_dev": dev}
        print(f"{did:16s} {m:>14.6f} {n:>8d} {dev:>16.3e}")
    out["undriven_convergence_500"] = conv

    # ---------- 事实 3：metaphor_coherence 退化为同分量指示 ----------
    print("\n[3] 无源项 metaphor_coherence 是否退化为「同分量」指示")
    for did, g in all_graphs(layers=2).items():
        g.forward()
        same, diff = [], []
        for comp in components(g):
            live = [i for i in comp if np.linalg.norm(g.H[i]) > 1e-12]
            for a in range(len(live)):
                for b in range(a + 1, len(live)):
                    same.append(cos(g.H[live[a]], g.H[live[b]]))
        for a in range(g.num_nodes):
            for b in range(a + 1, g.num_nodes):
                if not _same_comp(g, a, b) and np.linalg.norm(g.H[a]) > 1e-12 \
                        and np.linalg.norm(g.H[b]) > 1e-12:
                    diff.append(cos(g.H[a], g.H[b]))
        print(f"{did:16s} 同分量余弦 mean={np.mean(same):.6f} min={np.min(same):.6f} "
              f"(n={len(same)}) | 跨分量 mean={np.mean(diff):.6f} max={np.max(diff):.6f} (n={len(diff)})")

    # ---------- 事实 4：加源项保住源身份（用简单 resolvent 迭代） ----------
    print("\n[4] 加源项（resolvent u = (1-a)S u + a X0, a=0.5, 200 次）是否保住源身份")
    for did, g in all_graphs(layers=1).items():
        S = S_matrix(g)
        X0 = g.X.copy()
        U = X0.copy()
        for _ in range(200):
            U = (1 - 0.5) * (S @ U) + 0.5 * X0
        m, n = _within_cos(g, U)
        print(f"{did:16s} 同分量余弦 mean={m:.6f} (n={n})")
        out.setdefault("driven_source_identity", {})[did] = m

    write_json(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "step0_verify_claims.json"), out)
    print("\n已写 experiments/step0_verify_claims.json")
    return 0


def _within_cos(g, X):
    vals = []
    for comp in components(g):
        live = [i for i in comp if np.linalg.norm(X[i]) > 1e-12]
        for a in range(len(live)):
            for b in range(a + 1, len(live)):
                vals.append(cos(X[live[a]], X[live[b]]))
    return (float(np.mean(vals)) if vals else float("nan")), len(vals)


def _same_comp(g, a, b):
    for comp in components(g):
        if a in comp and b in comp:
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
