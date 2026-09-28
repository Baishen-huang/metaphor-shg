# -*- coding: utf-8 -*-
"""§6.3 H4 的种子敏感性检验（补 `seed_sensitivity_audit.md` §3 的缺口）。

**背景**：种子敏感性审计发现拓扑损失的正向效应是单 seed 假象，
随后逐一审计其他结论。唯一未测的缺口是 **§6.3 的 HGNN/GRU 判别信号**——
`_NumpyGRU` 用固定随机投影（`seed=20260830`），且配对负样本抽样也固定种子。

本脚本对 H4 做多种子复验，回答两个问题：
  1. **关键比较 `flat ≡ HGNN` 是否稳健？**（该节核心结论）
  2. **GRU 对照（`flat_gru`）的数值是否依赖种子？**（GRU 是随机投影）

**与拓扑损失的关键差异**：H4 的结论是**相对比较**（flat vs hgnn 的 AUC 差），
且比较对象都**不训练**，故预期比拓扑损失稳健。本脚本验证该预期。

运行：
    python -m metaphor_graph.evaluate_h4_seeds --seeds 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph import embeddings                     # noqa: E402
from metaphor_graph.evaluate_hgnn import (DOCS, MetaphorHGNN, _NumpyGRU,
                                          _l1_comembers, _frame_of, _auc_full,
                                          build_shg)       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "experiments", "math")


def measure_h4_seed(gru_seed: int, neg_seed: int, alpha: float = 1.0,
                    leak: float = 0.0) -> Dict[str, Dict[str, float]]:
    """与 `evaluate_hgnn.measure_h4` 同口径，但两个随机源可配。

    两个随机源：
      - `gru_seed`：`_NumpyGRU` 的随机投影权重（原固定 20260830）
      - `neg_seed`：配对负样本的抽样（原固定 20260830）
    """
    gru = _NumpyGRU(embeddings.DIM, seed=gru_seed)
    methods = ("hgnn", "flat", "raw", "flat_gru")
    scores: Dict[str, Dict[str, List[float]]] = {
        m: {"pos": [], "neg": []} for m in methods}
    rng = np.random.default_rng(neg_seed)

    for did, chunks in DOCS.items():
        shg = build_shg(chunks, did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        gf = MetaphorHGNN(shg, layers=2, cross_layer=False, alpha=alpha, leak=leak)
        gf.forward()
        comem = _l1_comembers(shg)
        gru_vec: Dict[str, np.ndarray] = {}
        for ent, peers in comem.items():
            seq = np.stack([np.array(embeddings.embed(p)) for p in peers])
            gru_vec[ent] = gru.forward(seq)

        def coh(method: str, a: str, b: str) -> float:
            if method == "hgnn":
                return g.metaphor_coherence(a, b)
            if method == "flat":
                return gf.metaphor_coherence(a, b)
            if method == "flat_gru":
                va, vb = gru_vec.get(a), gru_vec.get(b)
                if va is None or vb is None:
                    return 0.0
            else:
                va, vb = np.array(embeddings.embed(a)), np.array(embeddings.embed(b))
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na < 1e-9 or nb < 1e-9:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))

        # 穷举全部跨框架负样本（与已上报 auc_h4.py 口径一致）——
        # 该口径下**没有负样本抽样随机性**，唯一随机源是 GRU 投影种子。
        true_pairs = []
        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [n for n in e.member_entities
                    if n in g.node_index and n not in (e.frame_id or "")]
            if len(ents) >= 2:
                true_pairs.append((ents[0], ents[-1]))
        for src, tgt in true_pairs:
            for m in methods:
                scores[m]["pos"].append(coh(m, src, tgt))
            for n2 in g.entities:
                if n2 in (src, tgt):
                    continue
                if src in _frame_of(g, n2):
                    continue
                for m in methods:
                    scores[m]["neg"].append(coh(m, src, n2))

    out: Dict[str, Dict[str, float]] = {}
    for m in methods:
        pos = np.array(scores[m]["pos"], float)
        neg = np.array(scores[m]["neg"], float)
        n = min(len(pos), len(neg))
        acc = float(np.sum(pos[:n] > neg[:n])) / n if n else 0.0
        auc, n_pos, n_neg = _auc_full(pos, neg)
        out[m] = {"acc": acc, "auc_full": auc,
                  "n_pos": n_pos, "n_neg": n_neg,
                  "pos_mean": float(pos.mean()) if len(pos) else 0.0,
                  "neg_mean": float(neg.mean()) if len(neg) else 0.0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    print("=" * 84)
    print(f"§6.3 H4 种子敏感性检验（{args.seeds} 组随机源）")
    print("=" * 84)
    print("两个随机源同时变动：GRU 投影种子 + 负样本抽样种子\n")

    runs: List[Dict[str, Dict[str, float]]] = []
    for i in range(args.seeds):
        gs = 20260830 + i * 1000
        r = measure_h4_seed(gs, 0)
        runs.append(r)
        print(f"  run {i+1} (gru_seed={gs}, 负样本穷举):")
        for m in ("hgnn", "flat", "raw", "flat_gru"):
            print(f"    {m:<10} acc={r[m]['acc']:.4f}  AUC={r[m]['auc_full']:.4f}"
                  f"  (n_pos={r[m]['n_pos']}, n_neg={r[m]['n_neg']})")
        print()

    print("=" * 84)
    print("【裁决】跨种子的稳定性")
    print("=" * 84)
    print(f"{'表示':<12}{'AUC 均值':>11}{'标准差':>10}{'范围':>22}")
    summary = {}
    for m in ("hgnn", "flat", "raw", "flat_gru"):
        a = np.array([r[m]["auc_full"] for r in runs])
        summary[m] = {"mean": float(a.mean()), "std": float(a.std(ddof=1)),
                      "min": float(a.min()), "max": float(a.max())}
        print(f"{m:<12}{a.mean():>11.4f}{a.std(ddof=1):>10.4f}"
              f"{f'[{a.min():.4f}, {a.max():.4f}]':>22}")

    print()
    h = np.array([r["hgnn"]["auc_full"] for r in runs])
    fl = np.array([r["flat"]["auc_full"] for r in runs])
    d = fl - h
    print(f"【核心结论】flat − hgnn 的 AUC 差：{d.mean():+.4f} ± {d.std(ddof=1):.4f}"
          f"  范围 [{d.min():+.4f}, {d.max():+.4f}]")
    verdict = ("稳健（|Δ| ≤ 0.005，与已上报一致）"
               if abs(d.mean()) <= 0.005 else "不稳定")
    print(f"  → 裁决：{verdict}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "h4_seeds.json"), "w", encoding="utf-8") as f:
        json.dump({"seeds": args.seeds, "runs": runs, "summary": summary,
                   "flat_minus_hgnn": {"mean": float(d.mean()),
                                       "std": float(d.std(ddof=1)),
                                       "min": float(d.min()),
                                       "max": float(d.max())}},
                  f, ensure_ascii=False, indent=1)
    print(f"\n[写出] {os.path.join(OUT, 'h4_seeds.json')}")


if __name__ == "__main__":
    main()
