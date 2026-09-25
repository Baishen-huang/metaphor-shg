# -*- coding: utf-8 -*-
"""gen3 实验 7：最强候选 S_query 的完整档案 + 文档内（within-doc）下游检验。

实验 3–6 的结论指向一个候选：**S_query = Ω，但去掉 Ω_N 分量里的 `min(1,·)` 截断**。
本实验把它做成完整档案：

  A. S_query vs Ω 的逐档对照（AUC 全样本 / 子集、ρ(n_seed)、1-bit 一致率、
     取值数、分层内置换 p）在 4 条级联规则上；
  B. **within-doc 下游检验**：per-query MRR 的相关性在**文档内**（控制文档难度）
     还剩多少？全样本的 ρ 有相当一部分是「文档难度」这一共同因素造成的
     （难文档里所有查询都差、且都更容易没命中触发词）。文档内置换检验是
     这个问题上的正确零分布。
  C. 把 `n_gold`（LLM 判为相关的 chunk 数）单列 —— 它不是查询侧量
     （由候选侧判定产生），用作「**不可用**但强相关的对照」，以显示
     下游目标本身是有信号的，只是查询侧拿不到。

产物：experiments/gen3/exp_g3_7_squery.json + stdout
运行：<python> experiments/gen3/exp_g3_7_squery.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

import _stats as S                                              # noqa: E402
from _collect import load_dataset                               # noqa: E402

OUT = os.path.join(HERE, "exp_g3_7_squery.json")
RULES = ("json", "source", "metanet", "source_type")
SEED = 20260924


def boot_auc(pos, neg, n=2000, seed=SEED):
    rng = random.Random(seed)
    if not pos or not neg:
        return float("nan"), float("nan"), float("nan")
    v = []
    for _ in range(n):
        a = [pos[rng.randrange(len(pos))] for _ in pos]
        b = [neg[rng.randrange(len(neg))] for _ in neg]
        v.append(S.auc(a, b))
    v.sort()
    return S.auc(pos, neg), v[int(0.025 * n)], v[min(n - 1, int(0.975 * n))]


def _s_query(n_seed, n_frames, n_emergent, omega_f, comp, eps=1e-3):
    """S_query：Ω 的单点修改版（去掉 Ω_N 的 min(1,·) 截断）。"""
    if n_seed <= 0 or n_frames <= 0:
        return 0.0
    vals = (max(min(1.0, n_frames / n_seed), eps),
            max(n_emergent / n_seed, eps), max(omega_f, eps))
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) * comp


def cond_auc(rows, getter, keys, target="cascade_nonempty"):
    layers = defaultdict(list)
    for r in rows:
        if r["n_seed"] >= 1:
            layers[tuple(r[k] for k in keys)].append(r)
    ws = wd = 0.0
    for L in layers.values():
        p = [getter(r) for r in L if r[target]]
        n = [getter(r) for r in L if not r[target]]
        if not p or not n:
            continue
        w = len(p) * len(n)
        ws += S.auc(p, n) * w
        wd += w
    return (ws / wd if wd else float("nan")), wd


def within_doc_rho(rows, getter, ykey, n_perm=4000, seed=SEED, min_doc=5):
    """文档内平均 Spearman ρ + **文档内**置换检验（控制文档难度）。"""
    def stat(rs):
        byd = defaultdict(list)
        for r in rs:
            if r[ykey] is not None:
                byd[r["doc_id"]].append(r)
        vals = []
        for L in byd.values():
            if len(L) < min_doc:
                continue
            xs = [getter(r) for r in L]
            ys = [r[ykey] for r in L]
            if (len({round(x, 9) for x in xs}) < 2
                    or len({round(y, 9) for y in ys}) < 2):
                continue
            v = S.spearman(xs, ys)[0]
            if v == v:
                vals.append(v)
        return sum(vals) / len(vals) if vals else float("nan")

    rng = random.Random(seed)
    obs = stat(rows)
    if obs != obs:
        return float("nan"), float("nan"), 0, 0
    byd = defaultdict(list)
    for i, r in enumerate(rows):
        if r[ykey] is not None:
            byd[r["doc_id"]].append(i)
    null = []
    for _ in range(n_perm):
        perm = list(rows)
        for ids in byd.values():
            ys = [rows[i][ykey] for i in ids]
            rng.shuffle(ys)
            for i, y in zip(ids, ys):
                perm[i] = {**rows[i], ykey: y}
        v = stat(perm)
        if v == v:
            null.append(v)
    null.sort()
    if not null:
        return obs, float("nan"), 0, 0
    p = (sum(1 for x in null if abs(x) >= abs(obs)) + 1) / (len(null) + 1)
    n_docs = sum(1 for ids in byd.values() if len(ids) >= min_doc)
    return obs, p, len(null), n_docs


def main():
    print("=" * 100)
    print("gen3 实验 7：S_query 完整档案 + within-doc 下游检验")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        g = [r for r in rows if r["mrr_hand"] is not None]
        sq = lambda r: _s_query(r["n_seed"], r["n_frames"], r["n_emergent"],
                                r["omega_f"], r["comp"])       # noqa: E731
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub), n_gold=len(g),
                          n_pos_sub=sum(r["cascade_nonempty"] for r in sub))}

        # ============================================== A. S_query vs Ω
        def aucs(getter):
            return dict(
                auc_all=boot_auc([getter(r) for r in rows
                                  if r["cascade_nonempty"]],
                                 [getter(r) for r in rows
                                  if not r["cascade_nonempty"]]),
                auc_sub=boot_auc([getter(r) for r in sub
                                  if r["cascade_nonempty"]],
                                 [getter(r) for r in sub
                                  if not r["cascade_nonempty"]]),
                cond_auc_reach=cond_auc(rows, getter, ("n_reach",))[0],
                cond_auc_reach_doc=cond_auc(
                    rows, getter, ("doc_id", "n_reach"))[0],
                uniq_all=len({round(getter(r), 12) for r in rows}),
                uniq_sub=len({round(getter(r), 12) for r in sub}),
                agree_1bit=sum(1 for r in rows
                               if (getter(r) > 0) == (r["n_seed"] >= 1))
                / len(rows),
                spearman_nseed=S.spearman(
                    [getter(r) for r in rows],
                    [float(r["n_seed"]) for r in rows])[0],
            )

        res["A_squery"] = aucs(sq)
        res["A_omega"] = aucs(lambda r: r["omega"])
        res["A_n_emergent"] = aucs(lambda r: float(r["n_emergent"]))
        res["A_n_reach"] = aucs(lambda r: float(r["n_reach"]))
        res["A_n_seed"] = aucs(lambda r: float(r["n_seed"]))

        # ============================================== B. within-doc 下游
        scal = {
            "S_query": sq,
            "omega": lambda r: r["omega"],
            "n_seed": lambda r: float(r["n_seed"]),
            "n_seed_indicator": lambda r: 1.0 if r["n_seed"] >= 1 else 0.0,
            "n_emergent": lambda r: float(r["n_emergent"]),
            "n_reach": lambda r: float(r["n_reach"]),
            "completeness": lambda r: r["comp"],
            "qlen": lambda r: float(r["qlen"]),
            "cascade_nonempty": lambda r: float(r["cascade_nonempty"]),
            "cascade_nhit": lambda r: float(r["cascade_nhit"]),
            "n_gold (NOT query-side)": lambda r: float(r["n_gold"]),
        }
        down = {}
        for name, fn in scal.items():
            r1, p1, n1, d1 = within_doc_rho(g, fn, "mrr_hand")
            r2, p2, n2, _ = within_doc_rho(g, fn, "mrr_tr")
            rho_all_h = S.spearman([fn(r) for r in g],
                                   [r["mrr_hand"] for r in g])[0]
            rho_all_t = S.spearman([fn(r) for r in g],
                                   [r["mrr_tr"] for r in g])[0]
            down[name] = dict(
                rho_all_mrr_hand=rho_all_h, rho_all_mrr_tr=rho_all_t,
                within_doc_rho_hand=r1, within_doc_p_hand=p1,
                within_doc_nperm=n1, within_doc_ndocs=d1,
                within_doc_rho_tr=r2, within_doc_p_tr=p2,
            )
        res["B_downstream"] = down
        out[rule] = res

        # ---------------------------------------------------------- 打印
        n = res["_n"]
        print(f"\n{'=' * 100}\n[{rule}] n={n['n_all']}  n_seed≥1 {n['n_sub']}"
              f"（通路非空 {n['n_pos_sub']}）  有 LLM 金标 {n['n_gold']}\n{'=' * 100}")
        print(f"[A] S_query vs Ω（目标 = 级联通路非空）")
        print(f"  {'标量':16s} {'AUC全':>18s} {'AUC子集':>22s}"
              f" {'条件AUC(|reach|)':>17s} {'+doc后':>7s} {'取值':>5s}"
              f" {'1bit':>7s} {'ρ(nseed)':>9s}")
        for key, label in (("A_squery", "S_query"), ("A_omega", "omega"),
                           ("A_n_emergent", "n_emergent"),
                           ("A_n_reach", "n_reach"), ("A_n_seed", "n_seed")):
            v = res[key]
            a_all = f"{v['auc_all'][0]:.4f}[{v['auc_all'][1]:.3f},{v['auc_all'][2]:.3f}]"
            a_sub = f"{v['auc_sub'][0]:.4f}[{v['auc_sub'][1]:.3f},{v['auc_sub'][2]:.3f}]"
            cd = (f"{v['cond_auc_reach_doc']:.4f}"
                  if v["cond_auc_reach_doc"] == v["cond_auc_reach_doc"] else "n/a")
            print(f"  {label:16s} {a_all:>18s} {a_sub:>22s}"
                  f" {v['cond_auc_reach']:>17.4f} {cd:>7s} {v['uniq_sub']:>5d}"
                  f" {v['agree_1bit']:>7.4f} {v['spearman_nseed']:>9.4f}")
        print(f"\n[B] 下游 per-query MRR：全样本 ρ  vs  **文档内** ρ（控制文档难度）")
        print(f"  {'标量':24s} {'ρ全(hand)':>10s} {'ρ全(tr)':>9s}"
              f" {'ρ内(hand)':>10s} {'文档内置换p':>11s} {'ρ内(tr)':>9s}"
              f" {'p':>8s}")
        for name, v in sorted(down.items(),
                              key=lambda kv: -(kv[1]["within_doc_rho_hand"]
                                               if kv[1]["within_doc_rho_hand"]
                                               == kv[1]["within_doc_rho_hand"]
                                               else -9)):
            print(f"  {name:24s} {v['rho_all_mrr_hand']:>+10.4f}"
                  f" {v['rho_all_mrr_tr']:>+9.4f}"
                  f" {v['within_doc_rho_hand']:>+10.4f}"
                  f" {v['within_doc_p_hand']:>11.4f}"
                  f" {v['within_doc_rho_tr']:>+9.4f}"
                  f" {v['within_doc_p_tr']:>8.4f}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
