# -*- coding: utf-8 -*-
"""gen3 实验 6：条件判别力的正确估计 + 最后一个查询侧候选（域先验）。

实验 5 用 `min(n_pos, n_neg)` 给层加权，在 26 个层、多数层只有 1 个正或 1 个负
的情况下，那其实是「若干 2–4 样本 AUC 的平均」，噪声极大（CI 宽到 0.46–0.82）。
本实验换成**对级加权**（w = n_pos·n_neg），这是「控制 |reach| 后是否还能判别」
的正确估计量：它等价于只在**同大小对**上数一致/不一致对。

三个问题：
  A. 对级加权的条件 AUC（+ bootstrap CI）：还有哪个标量在控制大小后有效？
  B. **域先验标量**（最后一个真正的查询侧候选）：把「某个域在语料里有多常见」
     做成一张**本体级**先验表（在偶数号伪文档上拟合、在奇数号上评估，
     与查询本身无关，因此不破坏「只读查询」不变式），
     看它能否捕获 targeting excess（1.73× 那个信号）。
  C. **上界对照**：如果允许读图（`|reach ∩ live(doc)|`，Ω_G 那一支），
     判别力是多少？这条给出「不变式的代价」的量化边界。

产物：experiments/gen3/exp_g3_6_conditional.json + stdout
运行：<python> experiments/gen3/exp_g3_6_conditional.py
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

OUT = os.path.join(HERE, "exp_g3_6_conditional.json")
RULES = ("json", "source", "metanet", "source_type")
SEED = 20260924


def cond_auc(rows, getter, size_key="n_reach", target="cascade_nonempty"):
    """对级加权的条件 AUC：只在**同 |size| 对**上数一致对。

    返回 (auc, weight, n_layers, n_informative_layers)。
    """
    layers = defaultdict(list)
    for r in rows:
        if r["n_seed"] >= 1:
            layers[int(r[size_key])].append(r)
    ws = wd = 0.0
    n_layers = n_inf = 0
    for L in layers.values():
        n_layers += 1
        p = [getter(r) for r in L if r[target]]
        n = [getter(r) for r in L if not r[target]]
        if not p or not n:
            continue
        n_inf += 1
        w = len(p) * len(n)
        ws += S.auc(p, n) * w
        wd += w
    return (ws / wd if wd else float("nan")), wd, n_layers, n_inf


def cond_auc_ci(rows, getter, n_boot=2000, seed=SEED, **kw):
    a, w, nl, ni = cond_auc(rows, getter, **kw)
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        samp = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        v = cond_auc(samp, getter, **kw)[0]
        if v == v:
            vals.append(v)
    vals.sort()
    if not vals:
        return a, float("nan"), float("nan"), w, nl, ni
    return (a, vals[int(0.025 * len(vals))],
            vals[min(len(vals) - 1, int(0.975 * len(vals)))], w, nl, ni)


def main():
    print("=" * 100)
    print("gen3 实验 6：对级加权的条件 AUC + 域先验标量 + 读图上界")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        meta = d["meta"]
        live = {k: set(v) for k, v in meta.get("live_domains", {}).items()}
        # ---------------------------------------------- 域先验表（跨文档 CV）
        # 训练折 = 偶数号伪文档的 live 域集合；测试折 = 奇数号。
        # 先验只依赖**语料**（本体级），与单条查询无关 → 不破坏只读查询不变式。
        tr_docs = {k for k in live if int(k[2:]) % 2 == 0}
        te_docs = {k for k in live if int(k[2:]) % 2 == 1}
        cnt = defaultdict(int)
        for k in tr_docs:
            for x in live[k]:
                cnt[x] += 1
        n_tr = max(1, len(tr_docs))

        def prior(x, cnt=cnt, n_tr=n_tr):
            return cnt.get(x, 0) / n_tr

        def S_prior(r):
            return sum(prior(x) for x in r["reachable_domains"])

        def S_prior_max(r):
            return max((prior(x) for x in r["reachable_domains"]), default=0.0)

        # 在测试折（奇数号文档）上评估，保证先验未见
        te = [r for r in rows if r["doc_id"] in te_docs]
        tes = [r for r in te if r["n_seed"] >= 1]

        # ---------------------------------------------- 读图上界（Ω_G 那一支）
        def S_graph(r):
            return float(len(set(r["reachable_domains"])
                             & live.get(r["doc_id"], set())))

        def S_graph_bin(r):
            return 1.0 if S_graph(r) > 0 else 0.0

        # ---------------------------------------------- 标量表
        def omega_nounclipN(r):
            if not r["n_seed"]:
                return 0.0
            vs = [max(x, 1e-3) for x in
                  [min(1.0, r["n_frames"] / r["n_seed"]),
                   r["n_emergent"] / r["n_seed"], r["omega_f"]]]
            return math.exp(sum(math.log(v) for v in vs) / 3.0) * r["comp"]

        cands = {
            "n_reach": lambda r: float(r["n_reach"]),
            "n_members": lambda r: float(r["n_members"]),
            "n_emergent": lambda r: float(r["n_emergent"]),
            "n_new_domains": lambda r: float(r["n_new_domains"]),
            "n_frames": lambda r: float(r["n_frames"]),
            "n_seed": lambda r: float(r["n_seed"]),
            "n_seed_indicator": lambda r: 1.0 if r["n_seed"] >= 1 else 0.0,
            "completeness": lambda r: r["comp"],
            "omega": lambda r: r["omega"],
            "omega_geo": lambda r: r["omega_geo"],
            "omega_n": lambda r: r["omega_n"],
            "omega_nounclipN": omega_nounclipN,
            "S_log": lambda r: (math.log1p(r["n_frames"])
                                + math.log1p(r["n_cascades"])
                                + math.log1p(r["n_new_domains"])),
            "S_prior_sum": S_prior,
            "S_prior_max": S_prior_max,
            "[reads graph] S_graph": S_graph,
            "[reads graph] S_graph_bin": S_graph_bin,
        }
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub), n_te=len(te),
                          n_tes=len(tes), n_tr_docs=len(tr_docs),
                          n_te_docs=len(te_docs))}
        table = {}
        for name, g in cands.items():
            a, lo, hi, w, nl, ni = cond_auc_ci(rows, g)
            table[name] = dict(cond_auc=a, cond_auc_ci=[lo, hi], weight=w,
                               n_layers=nl, n_informative=ni)
        # 域先验在**未见文档**上的单独评估（严格 CV）
        for name, g in (("S_prior_sum", S_prior), ("S_prior_max", S_prior_max)):
            p = [g(r) for r in te if r["cascade_nonempty"]]
            n = [g(r) for r in te if not r["cascade_nonempty"]]
            table[name]["cv_te_auc_all"] = S.auc(p, n) if p and n else float("nan")
            p2 = [g(r) for r in tes if r["cascade_nonempty"]]
            n2 = [g(r) for r in tes if not r["cascade_nonempty"]]
            table[name]["cv_te_auc_sub"] = (S.auc(p2, n2) if p2 and n2
                                            else float("nan"))
            a2, lo2, hi2, w2, nl2, ni2 = cond_auc_ci(te, g)
            table[name]["cv_te_cond_auc"] = a2
            table[name]["cv_te_cond_ci"] = [lo2, hi2]
        # 读图上界的普通 AUC（全样本/子集）
        for name in ("[reads graph] S_graph", "[reads graph] S_graph_bin"):
            g = cands[name]
            p = [g(r) for r in rows if r["cascade_nonempty"]]
            n = [g(r) for r in rows if not r["cascade_nonempty"]]
            table[name]["auc_all"] = S.auc(p, n) if p and n else float("nan")
            p2 = [g(r) for r in sub if r["cascade_nonempty"]]
            n2 = [g(r) for r in sub if not r["cascade_nonempty"]]
            table[name]["auc_sub"] = S.auc(p2, n2) if p2 and n2 else float("nan")
        res["table"] = table
        # targeting excess 的「能否被先验解释」：先验和 vs 观测命中
        res["prior_coverage"] = dict(
            n_train_docs=len(tr_docs),
            n_test_docs=len(te_docs),
            n_domains_in_train=len(cnt),
            mean_prior_of_reachable=S.mean([S_prior(r) for r in sub]),
            mean_prior_of_new=S.mean(
                [sum(prior(x) for x in r["new_domains"]) for r in sub]),
        )
        out[rule] = res

        # ---------------------------------------------------------- 打印
        print(f"\n{'=' * 100}\n[{rule}] n={len(rows)}  n_seed≥1 {len(sub)}"
              f"   测试折文档 {len(te_docs)}（查询 {len(te)}）\n{'=' * 100}")
        print(f"  {'标量':26s} {'条件AUC':>8s} {'95%CI':>20s} {'对权':>7s}"
              f" {'层':>4s} {'有效层':>6s}")
        for name, v in sorted(table.items(), key=lambda kv: -kv[1]["cond_auc"]):
            ci = f"[{v['cond_auc_ci'][0]:.3f},{v['cond_auc_ci'][1]:.3f}]"
            print(f"  {name:26s} {v['cond_auc']:>8.4f} {ci:>20s}"
                  f" {v['weight']:>7.0f} {v['n_layers']:>4d}"
                  f" {v['n_informative']:>6d}")
        pc = res["prior_coverage"]
        print(f"  [域先验表] 训练 {pc['n_train_docs']} 文档 / "
              f"{pc['n_domains_in_train']} 个域；测试 {pc['n_test_docs']} 文档")
        print(f"    可达域的平均先验质量 {pc['mean_prior_of_reachable']:.4f}"
              f"   新增域的平均先验质量 {pc['mean_prior_of_new']:.4f}")
        for name in ("S_prior_sum", "S_prior_max"):
            v = table[name]
            print(f"    {name}: 未见文档 AUC 全样本 {v['cv_te_auc_all']:.4f}"
                  f"  子集 {v['cv_te_auc_sub']:.4f}"
                  f"  条件 AUC {v['cv_te_cond_auc']:.4f}"
                  f"[{v['cv_te_cond_ci'][0]:.3f},{v['cv_te_cond_ci'][1]:.3f}]")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
