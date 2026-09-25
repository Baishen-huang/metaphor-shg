# -*- coding: utf-8 -*-
"""P5c：flat-vs-HGNN 平局的**逐对**严格检验（α / ε 全网格）。

任务书的核心科学问题：加源项后平局是否被打破？
单看准确率是否相等不够 —— 必须看：
  1. 逐对一致性：flat 与 hgnn 在**同一批配对**上判对/判错的模式是否相同；
  2. 精确检验：McNemar 式不一致对数（b, c）+ 精确二项 p 值；
  3. 分数层面的差异：|pos_flat - pos_hgnn|、|neg_flat - neg_hgnn| 的分布。

同时报告 raw 基线的**并列率**（cos 恰为 0 的比例）—— 它决定 raw=0.150
这个「低于随机」的数字该怎么解读。

运行：python experiments/tie_analysis.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import write_csv, write_json

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN, EMB_DIM
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph.evaluate_hgnn import _NumpyGRU, _l1_comembers
from metaphor_graph import embeddings

OUT = os.path.dirname(os.path.abspath(__file__))


def paired_scores(alpha: float, leak: float):
    """复现 measure_h4 的抽样，返回逐对的四方法分数（严格配对）。"""
    gru = _NumpyGRU(EMB_DIM)
    rng = np.random.default_rng(20260830)
    rows = []
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
            cand = [n for n in g.entities if n not in (src, tgt)
                    and src not in frame_of(n)]
            if not cand:
                cand = [n for n in g.entities if n != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng.integers(len(cand))]

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

            rows.append({
                "doc": did, "src": src, "tgt": tgt, "neg": n2,
                "hgnn_pos": g.metaphor_coherence(src, tgt),
                "hgnn_neg": g.metaphor_coherence(src, n2),
                "flat_pos": gf.metaphor_coherence(src, tgt),
                "flat_neg": gf.metaphor_coherence(src, n2),
                "raw_pos": raw(src, tgt), "raw_neg": raw(src, n2),
                "gru_pos": gr(src, tgt), "gru_neg": gr(src, n2),
            })
    return rows


def mcnemar_exact(b: int, c: int):
    """不一致对 (b, c) 的精确二项双尾 p 值。"""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return float(min(1.0, 2 * tail))


def analyse(rows, alpha, leak):
    hp = np.array([r["hgnn_pos"] for r in rows])
    hn = np.array([r["hgnn_neg"] for r in rows])
    fp = np.array([r["flat_pos"] for r in rows])
    fn = np.array([r["flat_neg"] for r in rows])
    rp = np.array([r["raw_pos"] for r in rows])
    rn = np.array([r["raw_neg"] for r in rows])
    gp = np.array([r["gru_pos"] for r in rows])
    gn = np.array([r["gru_neg"] for r in rows])

    ok_h = hp > hn
    ok_f = fp > fn
    ok_r = rp > rn
    ok_g = gp > gn

    # McNemar：flat vs hgnn
    b = int(np.sum(ok_f & ~ok_h))    # flat 对 / hgnn 错
    c = int(np.sum(ok_h & ~ok_f))    # hgnn 对 / flat 错
    n_disc = int(np.sum(ok_h | ok_f))
    return {
        "alpha": alpha, "leak": leak, "n": len(rows),
        "acc_hgnn": float(ok_h.mean()), "acc_flat": float(ok_f.mean()),
        "acc_raw": float(ok_r.mean()), "acc_gru": float(ok_g.mean()),
        "mcnemar_b_flat_only": b, "mcnemar_c_hgnn_only": c,
        "mcnemar_p": mcnemar_exact(b, c),
        "identical_pattern": bool(np.array_equal(ok_h, ok_f)),
        "n_diff_pattern": int(np.sum(ok_h != ok_f)),
        "mean_abs_dpos": float(np.mean(np.abs(fp - hp))),
        "mean_abs_dneg": float(np.mean(np.abs(fn - hn))),
        "max_abs_dpos": float(np.max(np.abs(fp - hp))),
        "raw_tie_rate_pos": float(np.mean(rp == rn)),
        "raw_zero_pos": float(np.mean(rp == 0.0)),
        "raw_zero_neg": float(np.mean(rn == 0.0)),
        "raw_chance_note": "并列计为错 → acc<0.5 是口径产物，非「反向判别」",
    }


def main():
    print("=" * 100)
    print("P5c —— flat-vs-HGNN 平局的逐对严格检验（α / ε 网格）")
    print("=" * 100)
    print(f"{'α':>5s} {'ε':>5s} | {'n':>3s} {'acc_hgnn':>9s} {'acc_flat':>9s} "
          f"{'acc_raw':>8s} {'acc_gru':>8s} | {'b(flat独对)':>11s} {'c(hgnn独对)':>11s} "
          f"{'p':>7s} | {'判对模式全同':>12s} | {'|Δpos|':>7s} {'|Δneg|':>7s}")
    out = []
    for e in (0.0, 0.1, 0.2):
        for a in (1.0, 0.9, 0.7, 0.5, 0.3, 0.1):
            rows = paired_scores(a, e)
            r = analyse(rows, a, e)
            out.append(r)
            print(f"{a:>5.2f} {e:>5.2f} | {r['n']:>3d} {r['acc_hgnn']:>9.3f} "
                  f"{r['acc_flat']:>9.3f} {r['acc_raw']:>8.3f} {r['acc_gru']:>8.3f} "
                  f"| {r['mcnemar_b_flat_only']:>11d} {r['mcnemar_c_hgnn_only']:>11d} "
                  f"{r['mcnemar_p']:>7.3f} | {str(r['identical_pattern']):>12s} "
                  f"| {r['mean_abs_dpos']:>7.4f} {r['mean_abs_dneg']:>7.4f}")
        print("-" * 100)

    r0 = out[0]
    print("\n[raw 基线口径] 逐对并列率（cos_pos == cos_neg）: "
          f"{r0['raw_tie_rate_pos']:.3f}")
    print(f"  raw cos 恰为 0 的比例：pos={r0['raw_zero_pos']:.3f} neg={r0['raw_zero_neg']:.3f}")
    print("  → 默认哈希编码器下抽象域标签（『旅程』『停滞』）几乎无共享 n-gram，")
    print("    余弦恒为 0，故 80% 配对是**精确并列**。配对准确率把并列记为错，")
    print("    因此 raw=0.150 是「并列惩罚」的口径产物，不是「反向判别」。")
    print("    正确解读：raw 基线在默认编码器下**无信息**（而非有害）。")

    write_csv(os.path.join(OUT, "tie_analysis.csv"),
              [[r["alpha"], r["leak"], r["n"], r["acc_hgnn"], r["acc_flat"],
                r["acc_raw"], r["acc_gru"], r["mcnemar_b_flat_only"],
                r["mcnemar_c_hgnn_only"], r["mcnemar_p"], r["identical_pattern"],
                r["n_diff_pattern"], r["mean_abs_dpos"], r["mean_abs_dneg"],
                r["raw_tie_rate_pos"]] for r in out],
              header=["alpha", "leak", "n", "acc_hgnn", "acc_flat", "acc_raw",
                      "acc_gru", "mcnemar_b_flat_only", "mcnemar_c_hgnn_only",
                      "mcnemar_p", "identical_pattern", "n_diff_pattern",
                      "mean_abs_dpos", "mean_abs_dneg", "raw_tie_rate"])
    write_json(os.path.join(OUT, "tie_analysis.json"), out)
    print(f"\n已写 {OUT}/tie_analysis.csv, tie_analysis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
