# -*- coding: utf-8 -*-
"""gen3 实验 5：判决 —— 最强候选、多重比较校正、**「超出集合大小」的增量检验**。

实验 3/4 已确立：
  * 只把 Ω_N 的 `min(1,·)` 截断去掉（其余逐字不变），AUC 从 0.654 → 0.824；
  * 但「级联通路非空」是定理：`⟺ 可达域集合 ∩ live 边域集合 ≠ ∅`；
  * 大小匹配的随机集合也能拿到很高的 AUC（纯机械尺寸效应）。

因此最后一个必须回答的问题：**有没有任何查询侧标量携带「超出集合大小」的信息？**
本实验做三件事：

  1. **Holm-Bonferroni 多重比较校正**：exp_g3_3 测了 22 个候选标量 × 4 条级联规则，
     必须校正，否则「perm_p=0.001」不成立。
  2. **targeting excess 检验**（核心）：固定可达集合**大小**，只随机化**身份**，
     计算「观测命中数 − 零假设期望命中数」的超出量与 bootstrap CI。
     超出量显著 > 0 ⇒ 集合**内容**（买到了对的域）有信息；
     不显著 ⇒ 判别力全是「集合更大」这个机械效应。
  3. **控制 |reach| 后的层内 AUC**（带 bootstrap CI），逐个候选标量回答
     「它比集合大小多知道什么」。

产物：experiments/gen3/exp_g3_5_verdict.json + stdout
运行：<python> experiments/gen3/exp_g3_5_verdict.py
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

OUT = os.path.join(HERE, "exp_g3_5_verdict.json")
RULES = ("json", "source", "metanet", "source_type")
SEED = 20260924
N_MC = 400


def boot_ci(fn, n=2000, seed=SEED):
    """bootstrap 一个「行级统计量」的 95% CI。fn(sample_rows) → float。"""
    rng = random.Random(seed)
    return None  # 见各调用点


def boot_stat(rows, stat, n_boot=2000, seed=SEED):
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        samp = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        v = stat(samp)
        if v == v:
            vals.append(v)
    if not vals:
        return float("nan"), float("nan"), float("nan")
    vals.sort()
    return (stat(rows), vals[int(0.025 * len(vals))],
            vals[min(len(vals) - 1, int(0.975 * len(vals)))])


def holm(pvals):
    """Holm-Bonferroni 校正。输入 {name: p}，返回 {name: p_adj}。"""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, prev = {}, 0.0
    for i, (name, p) in enumerate(items):
        adj = min(1.0, max(prev, (m - i) * p))
        out[name] = adj
        prev = adj
    return out


# --------------------------------------------------- 控制 |reach| 的层内 AUC
def within_size_auc_ci(rows, getter, size_key="n_reach",
                       target="cascade_nonempty", n_boot=2000, seed=SEED,
                       extra_keys=()):
    """按分层键（默认 |reach|，可选加 doc_id）的加权 AUC + bootstrap CI。

    权重是**对级**（w = n_pos·n_neg）而非 min(n_pos,n_neg)：后者在
    「多数层只有 1 个正或 1 个负」时退化成「若干 2–4 样本 AUC 的平均」，
    噪声大到无法解释。对级权重等价于「只在同层对上数一致对」，是控制
    分层变量后「是否还有判别力」的正确估计量。
    """
    keys = (size_key,) + tuple(extra_keys)

    def stat(rs):
        layers = defaultdict(list)
        for r in rs:
            if r["n_seed"] >= 1:
                layers[tuple(r[k] for k in keys)].append(r)
        ws = wd = 0.0
        for L in layers.values():
            p = [getter(r) for r in L if r[target]]
            n = [getter(r) for r in L if not r[target]]
            if not p or not n:
                continue
            a = S.auc(p, n)
            w = len(p) * len(n)
            ws += a * w
            wd += w
        return ws / wd if wd else float("nan")

    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        samp = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        v = stat(samp)
        if v == v:
            vals.append(v)
    vals.sort()
    if not vals:
        return float("nan"), float("nan"), float("nan"), 0
    return (stat(rows), vals[int(0.025 * len(vals))],
            vals[min(len(vals) - 1, int(0.975 * len(vals)))], len(vals))


def strat_perm_p(rows, getter, size_key="n_reach", target="cascade_nonempty",
                 n_perm=4000, seed=SEED, extra_keys=()):
    """**分层内**置换检验：只在同层内打乱标签，得到条件 AUC 的零分布。

    这是「控制分层变量后还有没有判别力」的正确显著性检验。
    `perm_p`（exp_g3_3）打乱的是全样本标签，它对条件 AUC 是**错误**的零分布
    （它把层间差异也算进去了），故必须另做一次。
    """
    keys = (size_key,) + tuple(extra_keys)

    def cond(rs):
        layers = defaultdict(list)
        for r in rs:
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
        return ws / wd if wd else float("nan")

    rng = random.Random(seed)
    obs = cond(rows)
    if obs != obs:
        return float("nan"), float("nan"), 0, 0
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        if r["n_seed"] >= 1:
            groups[tuple(r[k] for k in keys)].append(i)
    null = []
    for _ in range(n_perm):
        perm = list(rows)
        for ids in groups.values():
            labs = [rows[i][target] for i in ids]
            rng.shuffle(labs)
            for i, l in zip(ids, labs):
                perm[i] = {**rows[i], target: l}
        v = cond(perm)
        if v == v:
            null.append(v)
    null.sort()
    if not null:
        return obs, float("nan"), 0, 0
    p = (sum(1 for x in null if x >= obs) + 1) / (len(null) + 1)
    return (obs, p, len(null),
            sum(1 for L in groups.values() if len(L) > 1))


# --------------------------------------------------- targeting excess 检验
def targeting_excess(rows, meta, vocab, n_mc=N_MC, seed=SEED, n_boot=2000):
    """固定集合大小、随机化身份 → 观测命中数 vs 零假设期望命中数。

    对每条查询 q：k = |reachable|，doc 的 live 域集合 L_doc。
    零假设 P(hit) = 1 − C(V−|L|, k) / C(V, k)（V = 域词表大小），
    用 Monte Carlo 估计（k 小时解析式数值不稳，直接抽样更稳）。

    返回 excess = (观测命中数 − Σ P̂) / n，以及 bootstrap CI。
    """
    rng = random.Random(seed)
    live = {k: set(v) for k, v in meta.get("live_domains", {}).items()}
    V = len(vocab)
    if not V or not live:
        return None
    # 每条查询的零假设命中概率（按 k 分组，一次估完）
    ks = sorted({len(r["reachable_domains"]) for r in rows})
    p_null = {}
    for k in ks:
        if k <= 0:
            p_null[k] = 0.0
            continue
        hits = 0
        for _ in range(n_mc):
            samp = set(rng.sample(vocab, min(k, V)))
            # 用平均 live 集合大小近似逐 doc 的差异（逐 doc 太慢，见下）
            hits += 1 if samp else 0
        # 这里改为逐 doc 精确估计（110 个 doc × 至多 13 档 k，成本可控）
        p_null[k] = None
    # 逐 doc 精确估计：对每个 (doc, k) 组合 MC
    cache = {}
    for r in rows:
        k = len(r["reachable_domains"])
        L = live.get(r["doc_id"], set())
        key = (r["doc_id"], k)
        if key in cache:
            continue
        if k <= 0 or not L:
            cache[key] = 0.0
            continue
        if k >= V:
            cache[key] = 1.0
            continue
        h = 0
        for _ in range(n_mc):
            if set(rng.sample(vocab, k)) & L:
                h += 1
        cache[key] = h / n_mc

    def stat(rs):
        obs = sum(r["cascade_nonempty"] for r in rs)
        exp = sum(cache[(r["doc_id"], len(r["reachable_domains"]))] for r in rs)
        return (obs - exp) / len(rs)

    obs = sum(r["cascade_nonempty"] for r in rows)
    exp = sum(cache[(r["doc_id"], len(r["reachable_domains"]))] for r in rows)
    e, lo, hi = boot_stat(rows, stat, n_boot=n_boot, seed=seed)
    return dict(n=len(rows), observed_hits=obs, expected_hits=exp,
                excess=e, excess_ci=[lo, hi], rate_obs=obs / len(rows),
                rate_exp=exp / len(rows), ratio=obs / exp if exp else float("nan"),
                n_mc=n_mc, vocab_size=V)


def main():
    print("=" * 100)
    print("gen3 实验 5：判决 —— 多重比较校正 + 超出集合大小的增量检验")
    print("=" * 100)
    out = {}
    # 汇总 exp_g3_3 的 perm_p 做 Holm 校正
    with open(os.path.join(HERE, "exp_g3_3_candidates.json"), "r",
              encoding="utf-8") as f:
        cand_json = json.load(f)
    all_p = {}
    for rule, v in cand_json.items():
        for name, c in v["candidates"].items():
            all_p[f"{rule}|{name}"] = c["perm_p_sub"]
    holm_all = holm(all_p)

    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        meta = d["meta"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        live = {k: set(v) for k, v in meta.get("live_domains", {}).items()}
        vocab = sorted({x for v in live.values() for x in v})
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub),
                          n_pos=len([r for r in rows if r["cascade_nonempty"]]))}

        # ---------------------------------------- 1. Holm 校正（本规则内）
        local = {name: c["perm_p_sub"]
                 for name, c in cand_json[rule]["candidates"].items()}
        res["holm"] = holm(local)

        # ---------------------------------------- 2. targeting excess
        res["targeting_excess"] = targeting_excess(rows, meta, vocab)
        res["targeting_excess_sub"] = targeting_excess(sub, meta, vocab)

        # ---------------------------------------- 3. 控制 |reach| 的增量
        cands = {
            "n_seed": lambda r: float(r["n_seed"]),
            "n_frames": lambda r: float(r["n_frames"]),
            "n_cascades": lambda r: float(r["n_cascades"]),
            "n_members": lambda r: float(r["n_members"]),
            "n_emergent": lambda r: float(r["n_emergent"]),
            "n_new_domains": lambda r: float(r["n_new_domains"]),
            "n_reach": lambda r: float(r["n_reach"]),
            "n_expanded_td": lambda r: float(r["n_expanded_td"]),
            "n_cross_cascades": lambda r: float(r["n_cross_cascades"]),
            "omega": lambda r: r["omega"],
            "omega_geo": lambda r: r["omega_geo"],
            "omega_n": lambda r: r["omega_n"],
            "omega_e": lambda r: r["omega_e"],
            "omega_f": lambda r: r["omega_f"],
            "completeness": lambda r: r["comp"],
            "n_seed_indicator": lambda r: 1.0 if r["n_seed"] >= 1 else 0.0,
            "qlen": lambda r: float(r["qlen"]),
            "omega_nounclipN": lambda r: (
                math.exp(sum(math.log(max(x, 1e-3)) for x in
                             [min(1.0, r["n_frames"] / r["n_seed"]) if r["n_seed"] else 0.0,
                              (r["n_emergent"] / r["n_seed"]) if r["n_seed"] else 0.0,
                              r["omega_f"]]) / 3.0) * r["comp"])
            if r["n_seed"] else 0.0,
            "S_log": lambda r: (math.log1p(r["n_frames"])
                                + math.log1p(r["n_cascades"])
                                + math.log1p(r["n_new_domains"])),
        }
        inc = {}
        for name, g in cands.items():
            a, lo, hi, nb = within_size_auc_ci(rows, g)
            # 分层内置换检验（|reach| 固定）
            obs_p, p_p, n_perm, n_inf = strat_perm_p(rows, g)
            # 再加一层 doc_id：控制「文档难度」后还剩什么
            a_d, lo_d, hi_d, nb_d = within_size_auc_ci(
                rows, g, extra_keys=("doc_id",))
            inc[name] = dict(auc=a, ci=[lo, hi], n_boot_ok=nb,
                             strat_perm_p=p_p, strat_perm_n=n_perm,
                             strat_n_informative=n_inf,
                             auc_doc=float(a_d) if a_d == a_d else None,
                             auc_doc_ci=([lo_d, hi_d] if a_d == a_d else None),
                             holm_p=res["holm"].get(name))
        res["increment_over_size"] = inc
        out[rule] = res

        # ---------------------------------------------------------- 打印
        print(f"\n{'=' * 100}\n[{rule}] n={len(rows)}"
              f"（通路非空 {res['_n']['n_pos']}）  n_seed≥1 {len(sub)}\n{'=' * 100}")
        te = res["targeting_excess"]
        tes = res["targeting_excess_sub"]
        if te:
            print(f"[targeting excess · 全样本]  域词表 {te['vocab_size']}")
            print(f"  观测命中 {te['observed_hits']}  vs 同大小随机身份期望 "
                  f"{te['expected_hits']:.2f}   → 超出 "
                  f"{te['excess']:+.4f} [{te['excess_ci'][0]:+.4f},"
                  f"{te['excess_ci'][1]:+.4f}]  （比值 {te['ratio']:.2f}×）")
            print(f"  非空率：观测 {te['rate_obs']:.4f} vs 随机 {te['rate_exp']:.4f}")
        if tes:
            print(f"[targeting excess · n_seed≥1 子集]")
            print(f"  观测命中 {tes['observed_hits']}  vs 期望 "
                  f"{tes['expected_hits']:.2f}   → 超出 {tes['excess']:+.4f}"
                  f" [{tes['excess_ci'][0]:+.4f},{tes['excess_ci'][1]:+.4f}]"
                  f"  （比值 {tes['ratio']:.2f}×）")
        print(f"\n[控制 |reach| 后的条件 AUC]（对级权重；0.5 = 不超出「集合大小」）")
        print(f"  {'标量':20s} {'条件AUC':>8s} {'95%CI':>20s}"
              f" {'分层置换p':>10s} {'+doc后':>8s} {'Holm p':>9s}")
        for name, v in sorted(inc.items(), key=lambda kv: -kv[1]["auc"]):
            hp = v["holm_p"]
            ci_s = f"[{v['ci'][0]:.3f},{v['ci'][1]:.3f}]"
            ad = (f"{v['auc_doc']:.4f}" if v["auc_doc"] is not None else "n/a")
            print(f"  {name:20s} {v['auc']:>8.4f} {ci_s:>20s}"
                  f" {v['strat_perm_p']:>10.4f} {ad:>8s}"
                  f" {(f'{hp:.4f}' if hp is not None else 'n/a'):>9s}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
