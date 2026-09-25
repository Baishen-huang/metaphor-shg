# -*- coding: utf-8 -*-
"""步骤 0c：为什么 raw 嵌入的配对准确率是 0.150（低于随机）？

诊断：打印每个配对样本的 (src, tgt, neg, cos_pos, cos_neg) 原值，
并统计嵌入空间的零余弦比例。这决定「raw 基线」是否是一个有意义的下界。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import build_graph, cos

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph import embeddings


def main():
    print("=" * 78)
    print("步骤 0c —— raw 嵌入基线的配对明细")
    print("=" * 78)
    rng = np.random.default_rng(20260830)
    allpos, allneg = [], []
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2)

        def frame_of(ent):
            out = set()
            for e in shg.edges:
                if e.frame_id and ent in e.member_entities:
                    out.add(e.frame_id)
            return out

        print(f"\n--- {did} (V={g.num_nodes}, entities={len(g.entities)}) ---")
        print(f"{'src':14s} {'tgt':14s} {'neg':14s} {'cos_pos':>8s} {'cos_neg':>8s} "
              f"{'|src|':>7s} {'src∩tgt grams':>13s}")
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
            va = np.array(embeddings.embed(src))
            vb = np.array(embeddings.embed(tgt))
            vn = np.array(embeddings.embed(n2))
            cp, cn = cos(va, vb), cos(va, vn)
            allpos.append(cp)
            allneg.append(cn)
            # 共享字符 n-gram
            def grams(t):
                return set(t) | {t[i:i+2] for i in range(len(t) - 1)}
            shared = len(grams(src) & grams(tgt))
            print(f"{src:14s} {tgt:14s} {n2:14s} {cp:>8.4f} {cn:>8.4f} "
                  f"{np.linalg.norm(va):>7.4f} {shared:>13d}")
    ap, an = np.array(allpos), np.array(allneg)
    print(f"\n汇总：cos_pos mean={ap.mean():.4f} min={ap.min():.4f} max={ap.max():.4f} "
          f"zero比例={(ap == 0).mean():.3f}")
    print(f"      cos_neg mean={an.mean():.4f} min={an.min():.4f} max={an.max():.4f} "
          f"zero比例={(an == 0).mean():.3f}")
    print(f"      配对准确率 = P(pos>neg) = {(ap > an).mean():.3f} (n={len(ap)})")
    print(f"      并列(pos==neg) 比例 = {(ap == an).mean():.3f}  → 计入分母但不计正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
