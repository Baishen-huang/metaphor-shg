# -*- coding: utf-8 -*-
"""gen3 实验 4：下游检验 + **目标本身是不是同义反复**的判决。

实验 3 留下两个必须回答的问题：

  Q1 「级联通路非空」这个目标到底是什么？
     本实验给出**定理级**答案：`cascade_nonempty = 1 ⟺ reachable_domains ∩
     live_domains(doc) ≠ ∅`（逐条核验 635/635）。也就是说它不是一个检索质量
     目标，而是「查询可达域集合与图中 live 边的域集合是否相交」这个
     **集合成员判定**。因此：
       - 用「集合大小」当分数去预测它，本质是「集合越大越可能与任何东西相交」；
       - 大小匹配的**随机集合**（身份随机、大小相同）能拿到的 AUC 就是
         「纯机械尺寸效应」的上界。
     这一节把这两个数并排放，回答「n_emergent 的 0.836 有多少是真信号」。

  Q2 有没有**非平凡**的下游目标？有：项目主通路（语义超图通路，`score_conditions`
     的 chunk 排序）对 LLM 金标的 **MRR@10**（人工加权 0.5025 / 训练后 0.5463）。
     这是端到端质量，有真实余量，且 gen1/gen2 从未测过。
     本节检验：任何查询侧标量能否预测 per-query MRR？
     做法：按标量分箱看 MRR 均值 + Spearman ρ + 置换检验。

产物：experiments/gen3/exp_g3_4_downstream.json + stdout
运行：<python> experiments/gen3/exp_g3_4_downstream.py
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

OUT = os.path.join(HERE, "exp_g3_4_downstream.json")
RULES = ("json", "source", "metanet", "source_type")
SEED = 20260924


def boot_mean(xs, n_boot=2000, seed=SEED):
    if not xs:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        vals.append(sum(xs[rng.randrange(len(xs))] for _ in range(len(xs)))
                    / len(xs))
    vals.sort()
    return S.mean(xs), vals[int(0.025 * n_boot)], vals[min(n_boot - 1,
                                                           int(0.975 * n_boot))]


def _s_query(n_seed, n_frames, n_emergent, omega_f, comp, eps=1e-3):
    """与 `metaphor_graph.query_signal._s_query` 同一实现（独立复写做交叉校验）。"""
    if n_seed <= 0 or n_frames <= 0:
        return 0.0
    vals = (max(min(1.0, n_frames / n_seed), eps),
            max(n_emergent / n_seed, eps), max(omega_f, eps))
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) * comp


def perm_rho(rows, getter, ykey, n_perm=2000, seed=SEED):
    """Spearman ρ 的置换检验（打乱 y）。返回 (rho, p, null_q025, null_q975)。"""
    rng = random.Random(seed)
    xs = [getter(r) for r in rows]
    ys = [r[ykey] for r in rows]
    obs = S.spearman(xs, ys)[0]
    null = []
    for _ in range(n_perm):
        rng.shuffle(ys)
        null.append(S.spearman(xs, ys)[0])
    null = [v for v in null if v == v]
    null.sort()
    p = (sum(1 for v in null if abs(v) >= abs(obs)) + 1) / (len(null) + 1)
    return (obs, p, null[int(0.025 * len(null))],
            null[min(len(null) - 1, int(0.975 * len(null)))])


def size_matched_control(rows, meta, vocab, n_rep=200, seed=SEED):
    """大小匹配的随机集合控制：身份随机、大小相同。"""
    rng = random.Random(seed)
    live = {k: set(v) for k, v in meta.get("live_domains", {}).items()}
    if not vocab or not live:
        return None
    byk = defaultdict(lambda: [0, 0, 0])         # k -> [n, real_hits, rand_hits]
    for r in rows:
        k = len(r["reachable_domains"])
        byk[k][0] += 1
        byk[k][1] += r["cascade_nonempty"]
    for _ in range(n_rep):
        for r in rows:
            k = len(r["reachable_domains"])
            if k > 0:
                samp = set(rng.sample(vocab, min(k, len(vocab))))
                if samp & live.get(r["doc_id"], set()):
                    byk[k][2] += 1
    per_k = {}
    for k in sorted(byk):
        n, rh, rr = byk[k]
        if n < 3:
            continue
        per_k[str(k)] = dict(n=n, real=rh / n, rand=(rr / n_rep) / n,
                             ratio=(rh / n) / max(1e-9, (rr / n_rep) / n))
    tot_real = sum(v[1] for v in byk.values()) / len(rows)
    tot_rand = (sum(v[2] for v in byk.values()) / n_rep) / len(rows)
    return dict(per_k=per_k, real_rate=tot_real, rand_rate=tot_rand,
                n_rep=n_rep)


def within_size_auc(rows, getter, size_key="n_reach",
                    target="cascade_nonempty"):
    """在「可达集合大小」固定的层内测 getter 的加权 AUC。"""
    layers = defaultdict(list)
    for r in rows:
        if r["n_seed"] >= 1:
            layers[int(r[size_key])].append(r)
    wsum = wden = 0.0
    per = {}
    for k, L in sorted(layers.items()):
        p = [getter(r) for r in L if r[target]]
        n = [getter(r) for r in L if not r[target]]
        if not p or not n:
            continue
        a = S.auc(p, n)
        w = min(len(p), len(n))
        per[str(k)] = dict(n=len(L), n_pos=len(p), n_neg=len(n), auc=a, weight=w)
        wsum += a * w
        wden += w
    return (wsum / wden if wden else float("nan")), int(wden), per


def main():
    print("=" * 100)
    print("gen3 实验 4：下游检验（per-query MRR）+ 目标同义反复判决")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        meta = d["meta"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub))}

        # =============================== Q1 目标是定理吗？
        live = {k: set(v) for k, v in meta.get("live_domains", {}).items()}
        agree = sum(1 for r in rows
                    if (1 if (set(r["reachable_domains"])
                              & live.get(r["doc_id"], set())) else 0)
                    == r["cascade_nonempty"])
        res["Q1_target_is_intersection"] = dict(
            n=len(rows), agree=agree, rate=agree / len(rows))
        vocab = sorted({x for v in live.values() for x in v})
        res["Q1_size_matched_random"] = size_matched_control(rows, meta, vocab)
        # 纯大小基线：只用 |reachable| 预测
        res["Q1_size_only"] = dict(
            auc_all=S.auc([float(r["n_reach"]) for r in rows
                           if r["cascade_nonempty"]],
                          [float(r["n_reach"]) for r in rows
                           if not r["cascade_nonempty"]]),
            auc_sub=S.auc([float(r["n_reach"]) for r in sub
                           if r["cascade_nonempty"]],
                          [float(r["n_reach"]) for r in sub
                           if not r["cascade_nonempty"]]))
        for name, g in (("n_emergent", lambda r: float(r["n_emergent"])),
                        ("n_reach", lambda r: float(r["n_reach"])),
                        ("n_members", lambda r: float(r["n_members"])),
                        ("omega", lambda r: r["omega"])):
            a, w, per = within_size_auc(sub, g)
            res[f"Q1_within_size_auc_{name}"] = dict(auc=a, weight=w, per=per)

        # =============================== Q2 下游 per-query MRR
        g = [r for r in rows if r["mrr_hand"] is not None]
        res["Q2_n_gold"] = len(g)
        res["Q2_baseline_mrr"] = dict(
            hand=boot_mean([r["mrr_hand"] for r in g]),
            trained=boot_mean([r["mrr_tr"] for r in g]),
        )
        # 候选标量（全部查询侧）
        scalars = {
            "n_seed": lambda r: float(r["n_seed"]),
            "n_seed_indicator": lambda r: 1.0 if r["n_seed"] >= 1 else 0.0,
            "n_frames": lambda r: float(r["n_frames"]),
            "n_cascades": lambda r: float(r["n_cascades"]),
            "n_emergent": lambda r: float(r["n_emergent"]),
            "n_new_domains": lambda r: float(r["n_new_domains"]),
            "n_reach": lambda r: float(r["n_reach"]),
            "n_members": lambda r: float(r["n_members"]),
            "omega": lambda r: r["omega"],
            "omega_geo": lambda r: r["omega_geo"],
            "omega_n": lambda r: r["omega_n"],
            "omega_e": lambda r: r["omega_e"],
            "completeness": lambda r: r["comp"],
            "qlen": lambda r: float(r["qlen"]),
            "n_gold": lambda r: float(r["n_gold"]),
            "cascade_nonempty": lambda r: float(r["cascade_nonempty"]),
            "cascade_nhit": lambda r: float(r["cascade_nhit"]),
            # gen3 最强手术变体：Ω 去掉 Ω_N 的 min(1,·) 截断
            "S_query": lambda r: _s_query(r["n_seed"], r["n_frames"],
                                          r["n_emergent"], r["omega_f"],
                                          r["comp"]),
            "omega_nounclipN": lambda r: _s_query(r["n_seed"], r["n_frames"],
                                                  r["n_emergent"],
                                                  r["omega_f"], r["comp"]),
        }
        table = {}
        for name, fn in scalars.items():
            rho_h, p_h, lo_h, hi_h = perm_rho(g, fn, "mrr_hand")
            rho_t, p_t, lo_t, hi_t = perm_rho(g, fn, "mrr_tr")
            # 分箱（4 档分位）的 MRR 均值
            vals = sorted({round(fn(r), 9) for r in g})
            bins = {}
            if len(vals) >= 2:
                try:
                    qs = [S.quantile(vals, q) for q in (0.25, 0.5, 0.75)]
                    for label, sel in (("q1", lambda r: fn(r) <= qs[0]),
                                       ("q2", lambda r: qs[0] < fn(r) <= qs[1]),
                                       ("q3", lambda r: qs[1] < fn(r) <= qs[2]),
                                       ("q4", lambda r: fn(r) > qs[2])):
                        sel_rows = [r for r in g if sel(r)]
                        if sel_rows:
                            bins[label] = dict(
                                n=len(sel_rows),
                                mrr_hand=S.mean([r["mrr_hand"]
                                                 for r in sel_rows]),
                                mrr_tr=S.mean([r["mrr_tr"] for r in sel_rows]))
                except Exception:
                    pass
            table[name] = dict(
                rho_mrr_hand=rho_h, perm_p_hand=p_h,
                null_hand=[lo_h, hi_h],
                rho_mrr_tr=rho_t, perm_p_tr=p_t, null_tr=[lo_t, hi_t],
                uniq=len(vals), bins=bins)
        res["Q2_scalar_vs_mrr"] = table
        out[rule] = res

        # ---------------------------------------------------------- 打印
        q1 = res["Q1_target_is_intersection"]
        print(f"\n{'=' * 100}\n[{rule}] n={len(rows)}\n{'=' * 100}")
        print(f"[Q1] 「级联通路非空 ⟺ 可达域 ∩ live 边域 ≠ ∅」"
              f" 逐条一致 {q1['agree']}/{q1['n']} = {q1['rate']:.4f}")
        sm = res["Q1_size_matched_random"]
        if sm:
            print(f"     大小匹配随机集合：真实非空率 {sm['real_rate']:.4f}"
                  f"  vs 随机 {sm['rand_rate']:.4f}"
                  f"  （{sm['n_rep']} 次重采样）")
            print(f"     {'|reach|':>8s} {'n':>5s} {'real':>8s} {'rand':>8s}"
                  f" {'ratio':>7s}")
            for k, v in sm["per_k"].items():
                print(f"     {k:>8s} {v['n']:>5d} {v['real']:>8.4f}"
                      f" {v['rand']:>8.4f} {v['ratio']:>7.2f}")
        print(f"     纯大小基线 AUC：全样本 {res['Q1_size_only']['auc_all']:.4f}"
              f"  子集 {res['Q1_size_only']['auc_sub']:.4f}")
        print(f"     控制 |reach| 后的层内加权 AUC：")
        for name in ("n_emergent", "n_reach", "n_members", "omega"):
            v = res[f"Q1_within_size_auc_{name}"]
            print(f"       {name:12s} {v['auc']:.4f} (w={v['weight']})")
        print(f"\n[Q2] 下游 per-query MRR（n={res['Q2_n_gold']}）")
        print(f"     基线 MRR@10：人工加权 "
              f"{res['Q2_baseline_mrr']['hand'][0]:.4f}"
              f"[{res['Q2_baseline_mrr']['hand'][1]:.4f},"
              f"{res['Q2_baseline_mrr']['hand'][2]:.4f}]"
              f"  训练后 {res['Q2_baseline_mrr']['trained'][0]:.4f}"
              f"[{res['Q2_baseline_mrr']['trained'][1]:.4f},"
              f"{res['Q2_baseline_mrr']['trained'][2]:.4f}]")
        print(f"     {'标量':20s} {'ρ(MRR_hand)':>12s} {'perm_p':>8s}"
              f" {'ρ(MRR_tr)':>11s} {'perm_p':>8s} {'取值':>5s}")
        for name, v in sorted(table.items(),
                              key=lambda kv: -abs(kv[1]["rho_mrr_hand"])):
            print(f"     {name:20s} {v['rho_mrr_hand']:>12.4f}"
                  f" {v['perm_p_hand']:>8.4f} {v['rho_mrr_tr']:>11.4f}"
                  f" {v['perm_p_tr']:>8.4f} {v['uniq']:>5d}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
