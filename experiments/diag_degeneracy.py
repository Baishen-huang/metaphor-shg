# -*- coding: utf-8 -*-
"""步骤 0b：诊断 —— 退化程度随 layers 的变化，以及负样本是否落在同分量内。

这决定 H4 的「同分量指示」解释是否成立：
  - 若 layers 很小（2），退化不完全，coherence 仍携带超边级信息；
  - 若负样本大多落在 src 的同一连通分量内，则「同分量指示」在 H4 上
    不可能给出 0.95 的准确率，说明 H4 的判别力来自更细的结构。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (build_graph, components, cos, incidence, S_matrix, M_matrix)

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph import embeddings


def main():
    print("=" * 78)
    print("步骤 0b —— 退化随 layers 的演化 + 负样本分量归属")
    print("=" * 78)

    print("\n[A] 无源项：同分量 / 跨分量余弦随 layers 演化（doc_project）")
    shg = MetaphorSHGBuilder().build(DOCS["doc_project"], doc_id="doc_project")
    g = MetaphorHGNN(shg, layers=1)
    S = S_matrix(g)
    comps = components(g)
    comp_of = {}
    for ci, c in enumerate(comps):
        for i in c:
            comp_of[i] = ci
    X0 = g.X.copy()
    print(f"{'layers':>7s} {'同分量cos':>10s} {'跨分量cos':>10s} {'gap':>8s} "
          f"{'与X0余弦(源保留)':>16s}")
    for L in (1, 2, 3, 5, 10, 50, 500):
        X = X0.copy()
        for _ in range(L):
            X = 0.5 * (X + S @ X)
        same, diff = [], []
        for a in range(g.num_nodes):
            for b in range(a + 1, g.num_nodes):
                if np.linalg.norm(X[a]) < 1e-12 or np.linalg.norm(X[b]) < 1e-12:
                    continue
                (same if comp_of[a] == comp_of[b] else diff).append(cos(X[a], X[b]))
        # 源保留度：X 与 X0 的平均余弦
        keep = np.mean([cos(X[i], X0[i]) for i in range(g.num_nodes)])
        print(f"{L:>7d} {np.mean(same):>10.6f} {np.mean(diff):>10.6f} "
              f"{np.mean(same)-np.mean(diff):>8.4f} {keep:>16.4f}")

    print("\n[B] 负样本是否与 src 同分量？（H4 抽样逻辑原样复现）")
    rng = np.random.default_rng(20260830)
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2)
        g.forward()
        comps = components(g)
        comp_of = {}
        for ci, c in enumerate(comps):
            for i in c:
                comp_of[i] = ci
        def frame_of(ent):
            out = set()
            for e in shg.edges:
                if e.frame_id and ent in e.member_entities:
                    out.add(e.frame_id)
            return out
        same_comp = tot = 0
        pair_dists = []
        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [n for n in e.member_entities
                    if n in g.node_index and n not in (e.frame_id or "")]
            if len(ents) < 2:
                continue
            src, tgt = ents[0], ents[-1]
            cand = [n for n in g.entities if n not in (src, tgt) and src not in frame_of(n)]
            if not cand:
                cand = [n for n in g.entities if n != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng.integers(len(cand))]
            tot += 1
            if comp_of[g.node_index[src]] == comp_of[g.node_index[n2]]:
                same_comp += 1
            pair_dists.append(1.0 - cos(g.X[g.node_index[src]], g.X[g.node_index[n2]]))
        print(f"  {did}: 负样本与 src 同分量 {same_comp}/{tot} "
              f"({same_comp/max(tot,1):.3f}) | 分量数 {len(comps)}")

    print("\n[C] 分量规模分布")
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2)
        sizes = sorted((len(c) for c in components(g)), reverse=True)
        print(f"  {did}: V={g.num_nodes} 分量规模 {sizes}")

    print("\n[D] 正样本对 (src,tgt) 在原始嵌入空间的距离 vs 负样本对")
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2)
        rng2 = np.random.default_rng(20260830)
        pos, neg = [], []
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
            pos.append(cos(g.X[g.node_index[src]], g.X[g.node_index[tgt]]))
            cand = [n for n in g.entities if n not in (src, tgt) and src not in frame_of(n)]
            if not cand:
                cand = [n for n in g.entities if n != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng2.integers(len(cand))]
            neg.append(cos(g.X[g.node_index[src]], g.X[g.node_index[n2]]))
        print(f"  {did}: raw cos 正={np.mean(pos):.4f}(n={len(pos)}) "
              f"负={np.mean(neg):.4f}(n={len(neg)})")

    print("\n[E] 「完美同分量指示器」在 H4 配对样本上的准确率上限")
    print("    （= 1 - 同分量负样本数/总数；这是退化假设能解释的最大值）")
    rng3 = np.random.default_rng(20260830)
    tot_ok = tot = 0
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2)
        g.forward()
        comp_of = {}
        for ci, c in enumerate(components(g)):
            for i in c:
                comp_of[i] = ci

        def frame_of(ent):
            out = set()
            for e in shg.edges:
                if e.frame_id and ent in e.member_entities:
                    out.add(e.frame_id)
            return out

        ok = n = 0
        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [x for x in e.member_entities
                    if x in g.node_index and x not in (e.frame_id or "")]
            if len(ents) < 2:
                continue
            src, tgt = ents[0], ents[-1]
            cand = [x for x in g.entities if x not in (src, tgt)
                    and src not in frame_of(x)]
            if not cand:
                cand = [x for x in g.entities if x != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng3.integers(len(cand))]
            n += 1
            pred = 1.0 if comp_of[g.node_index[src]] == comp_of[g.node_index[n2]] else 0.0
            if 1.0 > pred:
                ok += 1
        print(f"  {did}: 上限 {ok}/{n} = {ok/n:.4f}")
        tot_ok += ok
        tot += n
    print(f"  合计: {tot_ok}/{tot} = {tot_ok/tot:.4f}  "
          f"→ H4 实测 0.950 {'超出' if 0.95 > tot_ok/tot else '未超出'}该上限")
    return 0


if __name__ == "__main__":
    sys.exit(main())
