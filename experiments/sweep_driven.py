# -*- coding: utf-8 -*-
"""P5 主实验：驱动/源项版 HGNN 的 α / ε 敏感性 + metaphor_coherence 判别力。

回答三个问题：
  Q1（H4）加源项后，flat-vs-HGNN 的平局是否被打破？「信号来自 L1 n 元共现、
     而非层级」的结论是否改变？
  Q2（判别力）metaphor_coherence 是否从「同分量指示」升级为更细的判别器？
      设计：把负样本限制在 **与 src 同分量** 内 —— 纯同分量指示在此必然
      退化为随机（0.5）；并测与「超图跳数」的秩相关（纯指示器相关性为 0）。
  Q3（谱）行和 / 谱半径随 ε 的实测值。

运行：python experiments/sweep_driven.py
"""
from __future__ import annotations

import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (build_graph, components, cos, incidence, label,
                     M_matrix, S_matrix, spectral_report, write_csv, write_json)

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph.evaluate_hgnn import measure_h4
from metaphor_graph import embeddings

OUT = os.path.dirname(os.path.abspath(__file__))

ALPHAS = (1.0, 0.9, 0.7, 0.5, 0.3, 0.1)
LEAKS = (0.0, 0.05, 0.1, 0.2)


# ---------------------------------------------------------------------------
# Q1：α / ε 敏感性 —— H4 表
# ---------------------------------------------------------------------------
def q1_h4_sweep():
    print("=" * 100)
    print("Q1 —— H4 表对 α / ε 的敏感性（同一组 20 配对样本，种子 20260830）")
    print("=" * 100)
    print(f"{'α':>5s} {'ε':>5s} | {'hgnn':>6s} {'flat':>6s} {'raw':>6s} {'gru':>6s} "
          f"| {'hgnn_pos':>8s} {'flat_pos':>8s} {'hgnn_neg':>8s} {'flat_neg':>8s} "
          f"| {'flat-hgnn':>9s} {'同分量cos':>9s}")
    rows = []
    base = None
    for e in LEAKS:
        for a in ALPHAS:
            h4 = measure_h4(alpha=a, leak=e)
            wc = within_cos_mean(alpha=a, leak=e)
            acc_h, acc_f = h4["hgnn"]["acc"], h4["flat"]["acc"]
            tie = abs(acc_h - acc_f) < 0.02
            rec = {"alpha": a, "leak": e,
                   "acc_hgnn": acc_h, "acc_flat": acc_f,
                   "acc_raw": h4["raw"]["acc"], "acc_gru": h4["flat_gru"]["acc"],
                   "pos_hgnn": h4["hgnn"]["pos_mean"], "pos_flat": h4["flat"]["pos_mean"],
                   "neg_hgnn": h4["hgnn"]["neg_mean"], "neg_flat": h4["flat"]["neg_mean"],
                   "flat_minus_hgnn": acc_f - acc_h, "tie": bool(tie),
                   "within_component_cos": wc, "n_pairs": h4["hgnn"]["n_pairs"]}
            rows.append(rec)
            if a == 1.0 and e == 0.0:
                base = rec
            print(f"{a:>5.2f} {e:>5.2f} | {acc_h:>6.3f} {acc_f:>6.3f} "
                  f"{h4['raw']['acc']:>6.3f} {h4['flat_gru']['acc']:>6.3f} "
                  f"| {h4['hgnn']['pos_mean']:>8.3f} {h4['flat']['pos_mean']:>8.3f} "
                  f"{h4['hgnn']['neg_mean']:>8.3f} {h4['flat']['neg_mean']:>8.3f} "
                  f"| {acc_f-acc_h:>+9.3f} {wc:>9.4f}")
        print("-" * 100)
    write_csv(os.path.join(OUT, "sweep_h4.csv"), [
        [r["alpha"], r["leak"], r["acc_hgnn"], r["acc_flat"], r["acc_raw"],
         r["acc_gru"], r["pos_hgnn"], r["neg_hgnn"], r["pos_flat"], r["neg_flat"],
         r["flat_minus_hgnn"], r["tie"], r["within_component_cos"], r["n_pairs"]]
        for r in rows],
        header=["alpha", "leak", "acc_hgnn", "acc_flat", "acc_raw", "acc_gru",
                "pos_hgnn", "neg_hgnn", "pos_flat", "neg_flat",
                "flat_minus_hgnn", "tie", "within_component_cos", "n_pairs"])
    return rows, base


def within_cos_mean(alpha=1.0, leak=0.0):
    """两个文档、所有同分量节点对的平均余弦（衡量源身份是否被抹平）。"""
    vals = []
    for did in DOCS:
        g = build_graph(did, layers=2, alpha=alpha, leak=leak)
        H = g.forward()
        _, deg, _ = incidence(g)
        for comp in components(g):
            live = [i for i in comp if deg[i] > 0]
            for x in range(len(live)):
                for y in range(x + 1, len(live)):
                    vals.append(cos(H[live[x]], H[live[y]]))
    return float(np.mean(vals)) if vals else float("nan")


# ---------------------------------------------------------------------------
# Q2：判别力 —— 同分量负样本 + 超图跳数秩相关
# ---------------------------------------------------------------------------
def hypergraph_distance(g: MetaphorHGNN):
    """节点间「超边跳数」：a→b 经过的超边条数（二分图 BFS 的一半）。"""
    V = g.num_nodes
    inc = [[] for _ in range(V)]          # node -> hyperedges
    for j, members in enumerate(g.he_members):
        for i in members:
            inc[i].append(j)
    he_nodes = [[] for _ in range(len(g.he_members))]
    for j, members in enumerate(g.he_members):
        he_nodes[j] = members
    D = np.full((V, V), np.inf)
    for s in range(V):
        if not inc[s]:
            continue
        D[s, s] = 0
        seen_he = set()
        q = deque([(s, 0)])
        while q:
            u, d = q.popleft()
            for j in inc[u]:
                if j in seen_he:
                    continue
                seen_he.add(j)
                for v in he_nodes[j]:
                    if D[s, v] > d + 1:
                        D[s, v] = d + 1
                        q.append((v, d + 1))
    return D


def _true_pairs(shg, g):
    out = []
    for e in shg.edges:
        if e.is_extended:
            continue
        ents = [n for n in e.member_entities
                if n in g.node_index and n not in (e.frame_id or "")]
        if len(ents) >= 2:
            out.append((ents[0], ents[-1]))
    return out


def _frame_of(shg, ent):
    out = set()
    for e in shg.edges:
        if e.frame_id and ent in e.member_entities:
            out.add(e.frame_id)
    return out


def _rankdata(x):
    """平均秩（处理并列），零依赖。"""
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def spearman(x, y):
    """Spearman 秩相关（零依赖）。返回 (rho, n)；并列秩恒定/无变化时返回 (0.0, n)。"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    if n < 3:
        return 0.0, n
    rx, ry = _rankdata(x), _rankdata(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    dx, dy = np.linalg.norm(rx), np.linalg.norm(ry)
    if dx < 1e-12 or dy < 1e-12:
        return 0.0, n
    return float(np.dot(rx, ry) / (dx * dy)), n


def q2_discriminativity(alpha=0.5, leak=0.0):
    """A/B/C 三项判别力测试（委托给 convergence_check.eval_discriminativity，
    保证与 layers 扫描用**同一份**配对与统计实现）。

    A  跨分量负样本（原 H4 口径）配对准确率 —— 同分量指示器也能拿高分
    B  **同分量内**负样本配对准确率 —— 纯同分量指示器必然 = 0.5（随机）
    C  同分量节点对内，coherence 与超图跳数的 Spearman 秩相关
       （纯同分量指示器恒为 0；负相关越强说明越能分辨「近 vs 远」）
    D  分数离散度 —— 二值指示器接近 0
    """
    from convergence_check import eval_discriminativity
    from _common import components, hypergraph_hops

    accA, accB, rhos, stds, tieB = [], [], [], [], 0
    pos_all, cross_all, within_pos, within_neg = [], [], [], []
    for did in DOCS:
        shg = MetaphorSHGBuilder().build(DOCS[did], doc_id=did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        comp_of = {}
        for ci, c in enumerate(components(g)):
            for i in c:
                comp_of[i] = ci
        r = eval_discriminativity(g, g.H, hypergraph_hops(g), comp_of,
                                  np.random.default_rng(20260830))
        accA.append(r["acc_cross"])
        accB.append(r["acc_within"])
        tieB += r["tie_within"]
        rhos.append(r["spearman"])
        stds.append(r["within_std_mean"])
        pos_all.append(r["within_std_mean"])
    return {
        "alpha": alpha, "leak": leak,
        "acc_cross_component_neg": float(np.nanmean(accA)),
        "acc_within_component_neg": float(np.nanmean(accB)),
        "tie_within": int(tieB),
        "spearman_dist_vs_coh": float(np.nanmean(rhos)),
        "spearman_n": 2,
        "within_std_mean": float(np.nanmean(stds)),
    }


# ---------------------------------------------------------------------------
# Q3：谱 / 行和
# ---------------------------------------------------------------------------
def q3_spectral():
    print("=" * 100)
    print("Q3 —— 行和 / 谱半径随 ε 的实测（doc_project，V=61，E=30）")
    print("=" * 100)
    print(f"{'ε':>6s} {'M行和max(活)':>14s} {'M行和min(活)':>14s} {'ρ(M)':>10s} "
          f"{'ρ(S)':>8s} {'严格<1':>8s} {'对称':>6s}")
    rows = []
    for e in (0.0, 0.01, 0.05, 0.1, 0.2, 0.5):
        g = build_graph("doc_project", layers=2, leak=e)
        r = spectral_report(g, leak=e)
        strict = r["M_rowsum_max_live"] < 1.0
        rows.append({"leak": e, "rho_M": r["M_rho"], "rho_S": r["S_rho"],
                     "rowsum_max": r["M_rowsum_max_live"],
                     "rowsum_min": r["M_rowsum_min_live"], "strict": bool(strict)})
        print(f"{e:>6.2f} {r['M_rowsum_max_live']:>14.10f} {r['M_rowsum_min_live']:>14.10f} "
              f"{r['M_rho']:>10.8f} {r['S_rho']:>8.6f} {str(strict):>8s} {str(r['M_sym']):>6s}")
    print("\n注：M = 0.5(I + (1-ε)S)。ε=0 时 M 行和恰为 1（非严格次随机，ρ=1）；")
    print("    ε>0 时行和 = 1-ε/2 < 1 严格成立，ρ(M) ≤ 1-ε/2，Neumann 级数对任意 α 收敛。")

    print("\n[ε 的代价] 无源项时 ε>0 让迭代几何衰减到 0（信息随层数流失）：")
    print(f"{'ε':>6s} {'layers=2 ||H||均值':>18s} {'layers=10':>12s} {'layers=50':>12s}")
    for e in (0.0, 0.01, 0.05, 0.1, 0.2, 0.5):
        g = build_graph("doc_project", layers=1, leak=e)
        M = M_matrix(g, leak=e)
        X = g.X.copy()
        norms = {}
        for L in (2, 10, 50):
            Y = X.copy()
            for _ in range(L):
                Y = M @ Y
            norms[L] = float(np.mean(np.linalg.norm(Y, axis=1)))
        print(f"{e:>6.2f} {norms[2]:>18.6f} {norms[10]:>12.6f} {norms[50]:>12.6f}")
    return rows


# ---------------------------------------------------------------------------
def main():
    print("=" * 100)
    print("P5 —— 驱动/源项版 HGNN：H4 结论稳健性 + metaphor_coherence 判别力")
    print("=" * 100)

    rows, base = q1_h4_sweep()
    out = {"q1_sweep": rows, "q1_baseline": base}

    print("\n" + "=" * 100)
    print("Q2 —— metaphor_coherence 判别力：跨分量 vs **同分量**负样本 + 跳数秩相关")
    print("=" * 100)
    print(f"{'α':>5s} {'ε':>5s} | {'A:跨分量负 acc':>14s} {'B:同分量负 acc':>14s} "
          f"{'B:并列':>7s} | {'C:ρ(跳数,coherence)':>19s} {'分量内std':>9s}")
    q2rows = []
    for a, e in [(1.0, 0.0), (0.9, 0.0), (0.7, 0.0), (0.5, 0.0), (0.3, 0.0),
                 (0.1, 0.0), (0.5, 0.1), (0.3, 0.1), (0.5, 0.2)]:
        r = q2_discriminativity(alpha=a, leak=e)
        q2rows.append(r)
        print(f"{a:>5.2f} {e:>5.2f} | {r['acc_cross_component_neg']:>14.3f} "
              f"{r['acc_within_component_neg']:>14.3f} {r['tie_within']:>7d} "
              f"| {r['spearman_dist_vs_coh']:>19.4f} {r['within_std_mean']:>9.5f}")
    out["q2_discriminativity"] = q2rows
    write_csv(os.path.join(OUT, "sweep_discriminativity.csv"), [
        [r["alpha"], r["leak"], r["acc_cross_component_neg"],
         r["acc_within_component_neg"], r["tie_within"],
         r["spearman_dist_vs_coh"], r["within_std_mean"]]
        for r in q2rows],
        header=["alpha", "leak", "acc_cross_comp_neg", "acc_within_comp_neg",
                "tie_within", "spearman_dist_vs_coh", "within_std_mean"])

    print("\n判读：")
    print("  - 若 B 列（同分量负样本）≈ 0.5 → coherence 在该配置下就是同分量指示器；")
    print("  - 若 B 列显著 > 0.5 → 源项让 coherence 携带分量内的细粒度信息；")
    print("  - C 列 Spearman：ρ<0 说明「超图跳数越近、coherence 越高」；")
    print("    纯同分量指示器在分量内分数恒定 → ρ 无定义/为 0。")

    print()
    spec = q3_spectral()
    out["q3_spectral"] = spec
    write_json(os.path.join(OUT, "sweep_results.json"), out)
    print(f"\n已写 {OUT}/sweep_h4.csv, sweep_discriminativity.csv, sweep_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
