# -*- coding: utf-8 -*-
"""P5b：退化的**渐近性**检验 —— coherence 判别力随 layers 的演化。

关键点：任务书的事实 3（coherence 退化为同分量指示）是**渐近**命题：
无源项迭代 X ← M X 在 k→∞ 时收敛到分量平稳分布，同分量节点向量相同。
但 H4 实际工作在 layers=2，此时远未收敛（步骤 0b 实测同分量余弦仅 0.383，
500 层才到 1.000）。所以必须区分两件事：

  (a) 渐近退化：k→∞ 时 coherence 在分量内**恒定** → 同分量负样本判别
      必然 = 0.5（随机），与跳数秩相关 = 0；
  (b) 工作点退化：k=2 时的实际判别力。

源项的意义正是：α<1 时不动点 u* = (1-α)(I-αM)^{-1}X0 **保留源身份**，
即使 k→∞ 也不坍缩 → (a) 被阻止。

运行：python experiments/convergence_check.py
"""
from __future__ import annotations

import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (coherence_lookup, components, cos, hypergraph_hops,
                     incidence, label, M_matrix, write_csv, write_json)
from sweep_driven import spearman

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN, EMB_DIM
from metaphor_graph.eval_corpus import DOCS

OUT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
def build(did, **kw):
    shg = MetaphorSHGBuilder().build(DOCS[did], doc_id=did)
    return shg, MetaphorHGNN(shg, **kw)


def iterate(g: MetaphorHGNN, layers: int, alpha: float, leak: float = 0.0):
    """显式复现 forward 的驱动迭代（用于任意层数 / 收敛分析）。"""
    M = M_matrix(g, leak)
    X0 = g.X.copy()
    X = X0.copy()
    for _ in range(layers):
        X = (1.0 - alpha) * X0 + alpha * (M @ X)
    return X


def fixed_point_solve(g: MetaphorHGNN, alpha: float, leak: float = 0.0):
    """解析不动点 u* = (1-α)(I - αM)^{-1} X0（α<1 时 (I-αM) 可逆）。"""
    M = M_matrix(g, leak)
    n = g.num_nodes
    A = np.eye(n) - alpha * M
    return (1.0 - alpha) * np.linalg.solve(A, g.X)


def hop_distance(g: MetaphorHGNN):
    return hypergraph_hops(g)


def coherence_matrix(g: MetaphorHGNN, X: np.ndarray):
    """全节点对的 (a, b) -> cos；用 _common.coherence_lookup 保证覆盖框架/级联。"""
    return coherence_lookup(g, X)


def eval_discriminativity(g: MetaphorHGNN, X: np.ndarray, D, comp_of, rng):
    """给定节点表示 X，测：同分量负样本 acc / 跨分量负样本 acc / 跳数秩相关。

    负样本用**与 measure_p4b 相同的配对构造**（真边 src 对 + 另一候选），
    但候选池分别限制在「同分量」与「跨分量」。

    实现要点（两处易错）：
      1. pos / neg 必须**逐边配对构建**（同一条真边产生一个 pos 和一个 neg），
         否则截断到 min 长度后错位，准确率无意义；
      2. 跳数秩相关必须**在分量内中心化**：分量之间的平稳分布本身不同，
         混在一起算 Spearman 会把「分量间差异」误读成「分量内梯度」。
    """
    shg = g.shg
    coh = coherence_lookup(g, X)

    def frame_of(ent):
        out = set()
        for e in shg.edges:
            if e.frame_id and ent in e.member_entities:
                out.add(e.frame_id)
        return out

    triples_cross, triples_within = [], []
    for e in shg.edges:
        if e.is_extended:
            continue
        ents = [n for n in e.member_entities
                if n in g.node_index and n not in (e.frame_id or "")]
        if len(ents) < 2:
            continue
        src, tgt = ents[0], ents[-1]
        ci = comp_of[g.node_index[src]]
        p = coh(src, tgt)
        cross = [n for n in g.entities if n not in (src, tgt)
                 and comp_of[g.node_index[n]] != ci
                 and src not in frame_of(n)]
        within = [n for n in g.entities if n not in (src, tgt)
                  and comp_of[g.node_index[n]] == ci]
        if len(cross) > 1:
            triples_cross.append((p, coh(src, cross[rng.integers(len(cross))])))
        if len(within) > 1:
            triples_within.append((p, coh(src, within[rng.integers(len(within))])))

    def acc(tr):
        if not tr:
            return float("nan"), 0, 0
        pp = np.array([t[0] for t in tr])
        nn = np.array([t[1] for t in tr])
        return float(np.mean(pp > nn)), len(tr), int(np.sum(pp == nn))

    aA, nA, tA = acc(triples_cross)
    aB, nB, tB = acc(triples_within)

    # 跳数 vs coherence：**分量内** Spearman（每分量算一次再取均值）
    rhos = []
    for comp in components(g):
        live = [i for i in comp if np.isfinite(D[i, i])]
        nm = [label(g, i) for i in live]
        xs, ys = [], []
        for x in range(len(live)):
            for y in range(x + 1, len(live)):
                d = D[live[x], live[y]]
                if not np.isfinite(d) or d <= 0:
                    continue
                xs.append(d)
                ys.append(coh(nm[x], nm[y]))
        r, _ = spearman(xs, ys)
        if len(xs) >= 3:
            rhos.append(r)
    rho = float(np.mean(rhos)) if rhos else float("nan")
    nrho = int(np.sum([1 for c in components(g) for _ in range(len(c))]))

    # 同分量内 coherence 的离散度（纯指示器 → 0）
    spread = []
    for comp in components(g):
        live = [i for i in comp if np.isfinite(D[i, i])]
        nm = [label(g, i) for i in live]
        vals = [coh(nm[x], nm[y]) for x in range(len(live))
                for y in range(x + 1, len(live))]
        if len(vals) > 1:
            spread.append(float(np.std(vals)))
    return {"acc_cross": aA, "n_cross": nA, "tie_cross": tA,
            "acc_within": aB, "n_within": nB, "tie_within": tB,
            "spearman": rho, "spearman_n": len(rhos),
            "within_std_mean": float(np.mean(spread)) if spread else float("nan")}


# ---------------------------------------------------------------------------
def main():
    print("=" * 104)
    print("P5b —— 退化是渐近的：coherence 判别力 vs 迭代层数（α 控制源项）")
    print("=" * 104)

    print("\n[A] 解析不动点 vs 长迭代（验证 u* = (1-α)(I-αM)^{-1}X0）")
    print(f"{'doc':16s} {'α':>5s} {'layers=500 vs 解析':>20s} {'||u*||均值':>10s} "
          f"{'同分量cos(u*)':>14s}")
    for did in DOCS:
        shg, g = build(did, layers=1)
        for a in (1.0, 0.5):
            it = iterate(g, 500, a)
            fp = fixed_point_solve(g, a) if a < 1 else None
            if fp is not None:
                diff = float(np.max(np.abs(it - fp)) / (np.max(np.abs(fp)) + 1e-12))
            else:
                diff = float("nan")
            _, deg, _ = incidence(g)
            comp_of = {}
            for ci, c in enumerate(components(g)):
                for i in c:
                    comp_of[i] = ci
            vals = []
            for comp in components(g):
                live = [i for i in comp if deg[i] > 0]
                for x in range(len(live)):
                    for y in range(x + 1, len(live)):
                        vals.append(cos(it[live[x]], it[live[y]]))
            print(f"{did:16s} {a:>5.2f} {diff:>20.3e} "
                  f"{float(np.mean(np.linalg.norm(it, axis=1))):>10.6f} "
                  f"{float(np.mean(vals)):>14.6f}")
    print("  （α=1 无不动点：ρ(M)=1 使 I-αM 奇异，迭代收敛到分量平稳分布）")

    print("\n[B] 判别力随 layers 演化（同分量负样本 acc；纯指示器 → 0.5）")
    print(f"{'α':>5s} {'layers':>7s} | {'跨分量负acc':>11s} {'同分量负acc':>11s} "
          f"{'同分量负并列':>12s} | {'ρ(跳数,coh)':>12s} {'分量内std':>9s}")
    rows = []
    for a in (1.0, 0.5):
        for L in (1, 2, 3, 5, 10, 50, 500):
            accs_c, accs_w, rhos, stds, ties = [], [], [], [], []
            for did in DOCS:
                shg, g = build(did, layers=1)
                X = iterate(g, L, a)
                comp_of = {}
                for ci, c in enumerate(components(g)):
                    for i in c:
                        comp_of[i] = ci
                D = hop_distance(g)
                r = eval_discriminativity(g, X, D, comp_of,
                                          np.random.default_rng(20260830))
                accs_c.append(r["acc_cross"])
                accs_w.append(r["acc_within"])
                ties.append(r["tie_within"])
                rhos.append(r["spearman"])
                stds.append(r["within_std_mean"])
            print(f"{a:>5.2f} {L:>7d} | {np.nanmean(accs_c):>11.3f} "
                  f"{np.nanmean(accs_w):>11.3f} {int(np.sum(ties)):>12d} "
                  f"| {np.nanmean(rhos):>12.4f} {np.nanmean(stds):>9.5f}")
            rows.append([a, L, float(np.nanmean(accs_c)), float(np.nanmean(accs_w)),
                         int(np.sum(ties)), float(np.nanmean(rhos)),
                         float(np.nanmean(stds))])
        print("-" * 104)
    write_csv(os.path.join(OUT, "convergence_discriminativity.csv"), rows,
              header=["alpha", "layers", "acc_cross_neg", "acc_within_neg",
                      "tie_within", "spearman_hop_coh", "within_std"])

    print("\n[C] **分量内 AUC** 随 layers 演化 —— 退化真正生效时的判别力")
    print("    （纯同分量指示器在该子集上必然 AUC = 0.5000）")
    from auc_h4 import auc
    print(f"{'α':>5s} {'layers':>7s} | {'分量内AUC':>10s} {'跨分量AUC':>10s} "
          f"{'#正':>4s} {'#负(同分量)':>11s} {'#负(全部)':>9s}")
    rowsC = []
    for a in (1.0, 0.5):
        for L in (1, 2, 3, 5, 10, 50, 500):
            sw, sc, yw, yc = [], [], [], []
            for did in DOCS:
                shg, g = build(did, layers=1)
                X = iterate(g, L, a)
                comp_of = {}
                for ci, c in enumerate(components(g)):
                    for i in c:
                        comp_of[i] = ci
                coh = coherence_lookup(g, X)

                def frame_of(ent):
                    out = set()
                    for e in shg.edges:
                        if e.frame_id and ent in e.member_entities:
                            out.add(e.frame_id)
                    return out

                for e in shg.edges:
                    if e.is_extended:
                        continue
                    ents = [n for n in e.member_entities
                            if n in g.node_index and n not in (e.frame_id or "")]
                    if len(ents) < 2:
                        continue
                    src, tgt = ents[0], ents[-1]
                    ci = comp_of[g.node_index[src]]
                    sw.append(coh(src, tgt)); yw.append(1)
                    sc.append(coh(src, tgt)); yc.append(1)
                    for n2 in g.entities:
                        if n2 in (src, tgt) or src in frame_of(n2):
                            continue
                        v = coh(src, n2)
                        sc.append(v); yc.append(0)
                        if comp_of[g.node_index[n2]] == ci:
                            sw.append(v); yw.append(0)
            aw = auc(sw, yw)
            ac = auc(sc, yc)
            print(f"{a:>5.2f} {L:>7d} | {aw:>10.4f} {ac:>10.4f} "
                  f"{int(sum(yw)):>4d} {int(len(yw)-sum(yw)):>11d} "
                  f"{int(len(yc)-sum(yc)):>9d}")
            rowsC.append([a, L, aw, ac, int(sum(yw)), int(len(yw) - sum(yw))])
        print("-" * 104)
    write_csv(os.path.join(OUT, "convergence_auc.csv"), rowsC,
              header=["alpha", "layers", "auc_within_comp", "auc_all_neg",
                      "n_pos", "n_neg_within"])

    print("\n判读：")
    print("  - α=1.0 且 layers→大：同分量负 acc 应趋近 0.5、ρ→0、分量内 std→0")
    print("    → 这就是「退化为同分量指示器」的**渐近**含义，任务书事实 3 成立；")
    print("  - α=0.5：即使 layers 很大也不坍缩（源身份被保留）→ 退化被阻止；")
    print("  - 但 H4 工作在 layers=2：α=1.0 时**远未**退化，故事实 3 不能直接")
    print("    用来解释 H4 的 0.950 —— 这是本实验要澄清的关键区别。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
