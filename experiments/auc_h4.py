# -*- coding: utf-8 -*-
"""P5d：高统计功效版 H4 —— AUC over 全量正/负对（替代 n=20 的配对准确率）。

为什么需要：原 H4 只有 **20 个配对样本**，分辨率 0.05。
「flat=0.950 / hgnn=0.950」这种平局可能只是**样本量不足**导致的
（逐对 McNemar 显示 b=c=0，即两者判对模式完全相同，但 n 太小）。

本实验换成全量配对：
  正样本 = 所有 L1 真边 (src, tgt) 对
  负样本 = 对每个 src，取**全部**跨框架候选（穷举，非随机抽 1 个）
  指标  = ROC-AUC（秩统计量，对样本量敏感度远低于准确率）
并报告 DeLong 式 bootstrap 置信区间（配对 bootstrap，同一样本重采样）。

同时测「同分量内 AUC」——纯同分量指示器在该子集上必然 AUC=0.5。

运行：python experiments/auc_h4.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import components, coherence_lookup, write_csv, write_json

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN, EMB_DIM
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph.evaluate_hgnn import _NumpyGRU, _l1_comembers
from metaphor_graph import embeddings

OUT = os.path.dirname(os.path.abspath(__file__))


def collect(alpha: float, leak: float):
    """穷举配对：返回 [(doc, src, tgt_or_neg, y, is_within_comp)] 及四方法分数。"""
    gru = _NumpyGRU(EMB_DIM)
    recs = []
    for did, chunks in DOCS.items():
        shg = MetaphorSHGBuilder().build(chunks, doc_id=did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        gf = MetaphorHGNN(shg, layers=2, cross_layer=False, alpha=alpha, leak=leak)
        gf.forward()
        comem = _l1_comembers(shg)
        gv = {}
        for ent, peers in comem.items():
            seq = np.stack([np.array(embeddings.embed(p)) for p in peers])
            gv[ent] = gru.forward(seq)
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

        def raw(a, b):
            va, vb = np.array(embeddings.embed(a)), np.array(embeddings.embed(b))
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na < 1e-9 or nb < 1e-9:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))

        def gr(a, b):
            va, vb = gv.get(a), gv.get(b)
            if va is None or vb is None:
                return 0.0
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na < 1e-9 or nb < 1e-9:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))

        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [n for n in e.member_entities
                    if n in g.node_index and n not in (e.frame_id or "")]
            if len(ents) < 2:
                continue
            src, tgt = ents[0], ents[-1]
            ci = comp_of[g.node_index[src]]
            base = {"doc": did, "src": src, "partner": tgt}
            recs.append({**base, "y": 1, "within": True,
                         "hgnn": g.metaphor_coherence(src, tgt),
                         "flat": gf.metaphor_coherence(src, tgt),
                         "raw": raw(src, tgt), "gru": gr(src, tgt)})
            # 全部跨框架负候选（穷举）
            for n2 in g.entities:
                if n2 in (src, tgt):
                    continue
                if src in frame_of(n2):
                    continue
                same_comp = comp_of[g.node_index[n2]] == ci
                recs.append({**base, "partner": n2, "y": 0,
                             "within": bool(same_comp),
                             "hgnn": g.metaphor_coherence(src, n2),
                             "flat": gf.metaphor_coherence(src, n2),
                             "raw": raw(src, n2), "gru": gr(src, n2)})
    return recs


def auc(scores, labels):
    """ROC-AUC（Mann-Whitney U 形式，正确处理并列）。"""
    scores = np.asarray(scores, float)
    labels = np.asarray(labels, int)
    P = int(labels.sum())
    N = len(labels) - P
    if P == 0 or N == 0:
        return float("nan")
    r = _rank(scores)
    return float((r[labels == 1].sum() - P * (P + 1) / 2.0) / (P * N))


def _rank(x):
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


def boot_ci(recs, method, n_boot=2000, seed=20260830):
    """配对 bootstrap：对 (doc, src) 分组重采样，保留组内配对结构。"""
    rng = np.random.default_rng(seed)
    groups = {}
    for r in recs:
        groups.setdefault((r["doc"], r["src"]), []).append(r)
    keys = list(groups)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        s, y = [], []
        for k in pick:
            for r in groups[keys[k]]:
                s.append(r[method])
                y.append(r["y"])
        vals.append(auc(s, y))
    vals = np.array(vals, float)
    return float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def main():
    print("=" * 100)
    print("P5d —— 高统计功效版 H4：全量正/负对 ROC-AUC（α / ε 网格）")
    print("=" * 100)
    methods = ("hgnn", "flat", "raw", "gru")
    out = []
    print(f"{'α':>5s} {'ε':>5s} | {'#pos':>5s} {'#neg':>5s} {'#neg(同分量)':>12s} | "
          f"{'AUC_hgnn':>9s} {'AUC_flat':>9s} {'AUC_raw':>8s} {'AUC_gru':>8s} | "
          f"{'flat-hgnn':>10s} {'95%CI(flat-hgnn)':>18s}")
    for e in (0.0, 0.1, 0.2):
        for a in (1.0, 0.9, 0.7, 0.5, 0.3, 0.1):
            recs = collect(a, e)
            y = [r["y"] for r in recs]
            a_h = auc([r["hgnn"] for r in recs], y)
            a_f = auc([r["flat"] for r in recs], y)
            a_r = auc([r["raw"] for r in recs], y)
            a_g = auc([r["gru"] for r in recs], y)
            npos = int(np.sum(y))
            nneg = len(y) - npos
            nw = int(np.sum([1 for r in recs if r["y"] == 0 and r["within"]]))
            # 配对 bootstrap CI（对差值）
            rng = np.random.default_rng(20260830)
            groups = {}
            for r in recs:
                groups.setdefault((r["doc"], r["src"]), []).append(r)
            keys = list(groups)
            diffs = []
            for _ in range(1000):
                pick = rng.integers(0, len(keys), len(keys))
                ss, yy = [], []
                for k in pick:
                    for r in groups[keys[k]]:
                        ss.append((r["flat"], r["hgnn"]))
                        yy.append(r["y"])
                ss = np.array(ss)
                yy = np.array(yy)
                diffs.append(auc(ss[:, 0], yy) - auc(ss[:, 1], yy))
            diffs = np.array(diffs, float)
            lo, hi = np.nanpercentile(diffs, 2.5), np.nanpercentile(diffs, 97.5)
            print(f"{a:>5.2f} {e:>5.2f} | {npos:>5d} {nneg:>5d} {nw:>12d} | "
                  f"{a_h:>9.4f} {a_f:>9.4f} {a_r:>8.4f} {a_g:>8.4f} | "
                  f"{a_f-a_h:>+10.4f} {'['+format(lo,'+.4f')+','+format(hi,'+.4f')+']':>18s}")
            out.append({"alpha": a, "leak": e, "n_pos": npos, "n_neg": nneg,
                        "n_neg_within_comp": nw,
                        "auc_hgnn": a_h, "auc_flat": a_f, "auc_raw": a_r,
                        "auc_gru": a_g, "auc_flat_minus_hgnn": a_f - a_h,
                        "ci_lo": float(lo), "ci_hi": float(hi)})
        print("-" * 100)

    # 同分量内 AUC（纯指示器必然 0.5）
    print("\n[同分量内 AUC] 负样本限制在 src 同分量 —— 纯同分量指示器必然 = 0.5000")
    print(f"{'α':>5s} {'ε':>5s} | {'AUC_hgnn':>9s} {'AUC_flat':>9s} {'AUC_raw':>8s} {'AUC_gru':>8s} {'#neg':>6s}")
    within_rows = []
    for e in (0.0,):
        for a in (1.0, 0.5, 0.3, 0.1):
            recs = collect(a, e)
            sub = [r for r in recs if r["within"]]
            y = [r["y"] for r in sub]
            if sum(y) == 0 or sum(y) == len(y):
                print(f"{a:>5.2f} {e:>5.2f} | 该子集无负样本或无正样本")
                continue
            row = {"alpha": a, "leak": e, "n_neg_within": int(len(y) - sum(y))}
            vals = []
            for m in methods:
                v = auc([r[m] for r in sub], y)
                row[f"auc_within_{m}"] = v
                vals.append(v)
            within_rows.append(row)
            print(f"{a:>5.2f} {e:>5.2f} | {vals[0]:>9.4f} {vals[1]:>9.4f} "
                  f"{vals[2]:>8.4f} {vals[3]:>8.4f} {row['n_neg_within']:>6d}")

    write_csv(os.path.join(OUT, "auc_h4.csv"),
              [[r["alpha"], r["leak"], r["n_pos"], r["n_neg"],
                r["n_neg_within_comp"], r["auc_hgnn"], r["auc_flat"],
                r["auc_raw"], r["auc_gru"], r["auc_flat_minus_hgnn"],
                r["ci_lo"], r["ci_hi"]] for r in out],
              header=["alpha", "leak", "n_pos", "n_neg", "n_neg_within_comp",
                      "auc_hgnn", "auc_flat", "auc_raw", "auc_gru",
                      "auc_flat_minus_hgnn", "ci_lo", "ci_hi"])
    write_json(os.path.join(OUT, "auc_h4.json"), {"main": out, "within": within_rows})
    print(f"\n已写 {OUT}/auc_h4.csv, auc_h4.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
