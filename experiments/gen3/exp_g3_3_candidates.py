# -*- coding: utf-8 -*-
"""gen3 实验 3：候选查询侧标量总表 + 零假设控制。

实验 2 定位了元凶（分量内部的 `min(1, ·)` 截断），本实验把候选标量一次性
摆到同一张表上，并对每一个做三类诚实性控制：

  1. **分层条件 AUC**（n_seed 固定层内加权），这是 gen2 用的口径；
  2. **置换零假设**：把标签打乱 1000 次，得到「同边际分布下随机变量能达到的
     AUC 分布」→ 给出 p 值。**没有这一步，任何 AUC 都是不可解释的**（n=114、
     正样本 68，随机变量的 AUC 期望就是 0.5 但方差不可忽略）。
  3. **集合大小匹配的随机对照**：级联通路的非空与否 = 「查询可达域集合」与
     「该伪文档 live 超边的域集合」是否相交。因此一个**只含大小的随机集合**
     也能拿到一定的 AUC。本控制回答：候选标量的判别力有多少是「集合更大
     ⇒ 更可能与任何东西相交」这个纯机械效应，多少是「买到了**对的**域」。
     这是本报告最重要的诚实性控制。

另外：条件 z 分数标量必须做**跨文档交叉验证**（normalizer 在训练折上拟合、
在测试折上变换），否则 in-sample 的 AUC 是自欺。

产物：experiments/gen3/exp_g3_3_candidates.json + stdout
运行：<python> experiments/gen3/exp_g3_3_candidates.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

import _stats as S                                              # noqa: E402
from _collect import load_dataset                               # noqa: E402

OUT = os.path.join(HERE, "exp_g3_3_candidates.json")
RULES = ("json", "source", "metanet", "source_type")
EPS = 1e-3
N_PERM = 1000
SEED = 20260924


# ------------------------------------------------------------------ 工具
def boot_auc(pos, neg, n_boot=2000, seed=SEED):
    rng = random.Random(seed)
    if not pos or not neg:
        return float("nan"), float("nan"), float("nan")
    vals = []
    for _ in range(n_boot):
        a = [pos[rng.randrange(len(pos))] for _ in range(len(pos))]
        b = [neg[rng.randrange(len(neg))] for _ in range(len(neg))]
        vals.append(S.auc(a, b))
    vals.sort()
    return (S.auc(pos, neg), vals[int(0.025 * n_boot)],
            vals[min(n_boot - 1, int(0.975 * n_boot))])


def perm_p(rows, getter, target="cascade_nonempty", n_perm=N_PERM, seed=SEED):
    """置换检验：打乱 target 标签，得到 AUC 的零分布，返回 (AUC, p, null_mean,
    null_q025, null_q975)。

    单侧 p（观测值 ≥ 零分布）—— 我们只关心「正相关方向的判别力」，
    反向的 AUC<0.5 不构成发现（可用 1−AUC 对称读）。
    """
    rng = random.Random(seed)
    vals = [getter(r) for r in rows]
    labs = [1 if r[target] else 0 for r in rows]
    obs = S.auc([v for v, y in zip(vals, labs) if y],
                [v for v, y in zip(vals, labs) if not y])
    null = []
    idx = list(range(len(labs)))
    for _ in range(n_perm):
        rng.shuffle(idx)
        y = [labs[i] for i in idx]
        a = [v for v, yy in zip(vals, y) if yy]
        b = [v for v, yy in zip(vals, y) if not yy]
        if a and b:
            null.append(S.auc(a, b))
    null.sort()
    ge = sum(1 for x in null if x >= obs)
    p = (ge + 1) / (len(null) + 1)
    return (obs, p, S.mean(null), null[int(0.025 * len(null))],
            null[min(len(null) - 1, int(0.975 * len(null)))])


def strat_auc(rows, getter, target="cascade_nonempty", cap=4):
    layers = defaultdict(list)
    for r in rows:
        if r["n_seed"] >= 1:
            layers[min(int(r["n_seed"]), cap)].append(r)
    wsum = wden = 0.0
    per = {}
    for k, L in sorted(layers.items()):
        p = [getter(r) for r in L if r[target]]
        n = [getter(r) for r in L if not r[target]]
        if not p or not n:
            per[str(k)] = dict(n=len(L), auc=None)
            continue
        a = S.auc(p, n)
        w = min(len(p), len(n))
        per[str(k)] = dict(n=len(L), n_pos=len(p), n_neg=len(n), auc=a,
                           weight=w)
        wsum += a * w
        wden += w
    return (wsum / wden if wden else float("nan"), int(wden), per)


def agree_1bit(rows, getter):
    return sum(1 for r in rows if (getter(r) > 0) == (r["n_seed"] >= 1)) / len(rows)


def rho_seed(rows, getter):
    return S.spearman([getter(r) for r in rows],
                      [float(r["n_seed"]) for r in rows])[0]


# ------------------------------------------------- 候选标量定义（全部查询侧）
def build_candidates(rows):
    """返回 {name: getter}。全部只读查询侧字段。"""
    def geo(vals, floor=True):
        v = [max(x, EPS) for x in vals] if floor else [x for x in vals if x > 0]
        if not v:
            return 0.0
        return math.exp(sum(math.log(x) for x in v) / len(v))

    def cands():
        return {
            # ---- 朴素基线 ----
            "n_seed": lambda r: float(r["n_seed"]),
            "n_seed_indicator": lambda r: 1.0 if r["n_seed"] >= 1 else 0.0,
            "n_frames": lambda r: float(r["n_frames"]),
            "n_cascades": lambda r: float(r["n_cascades"]),
            "qlen": lambda r: float(r["qlen"]),
            "completeness": lambda r: r["comp"],
            # ---- gen2 发现的原始计数 ----
            "n_emergent": lambda r: float(r["n_emergent"]),
            "n_new_domains": lambda r: float(r["n_new_domains"]),
            "n_reach": lambda r: float(r["n_reach"]),
            "n_members": lambda r: float(r["n_members"]),
            "n_expanded_td": lambda r: float(r["n_expanded_td"]),
            "n_cross_cascades": lambda r: float(r["n_cross_cascades"]),
            # ---- gen1 基线 ----
            "omega": lambda r: r["omega"],
            "omega_geo": lambda r: r["omega_geo"],
            "omega_e": lambda r: r["omega_e"],
            "omega_n": lambda r: r["omega_n"],
            "omega_f": lambda r: r["omega_f"],
            # ---- 手术变体：只去掉 Ω_N 的 min(1,·) 截断 ----
            "omega_nounclipN": lambda r: (
                geo([min(1.0, r["n_frames"] / r["n_seed"]) if r["n_seed"] else 0.0,
                     (r["n_emergent"] / r["n_seed"]) if r["n_seed"] else 0.0,
                     r["omega_f"]]) * r["comp"]) if r["n_seed"] else 0.0,
            "omega_nounclip_both": lambda r: (
                geo([(r["n_frames"] / r["n_seed"]) if r["n_seed"] else 0.0,
                     (r["n_emergent"] / r["n_seed"]) if r["n_seed"] else 0.0,
                     r["omega_f"]]) * r["comp"]) if r["n_seed"] else 0.0,
            # ---- 无 ε 下界 / 无除法 / 无完备度的组合 ----
            "S_log": lambda r: (math.log1p(r["n_frames"])
                                + math.log1p(r["n_cascades"])
                                + math.log1p(r["n_new_domains"])),
            "S_log_dom": lambda r: (math.log1p(r["n_frames"])
                                    + math.log1p(r["n_cascades"])
                                    + math.log1p(r["n_reach"])),
            "S_struct": lambda r: (
                geo([min(1.0, r["n_frames"] / r["n_seed"])]
                    + ([min(1.0, r["n_new_domains"] / r["n_seed"])]
                       if r["n_cascades"] > 0 and r["n_new_domains"] > 0 else []),
                    floor=False)) if r["n_seed"] else 0.0,
            "S_geo_nodiv": lambda r: geo([float(r["n_frames"]),
                                          float(r["n_new_domains"]),
                                          r["max_flow"]]) if r["n_seed"] else 0.0,
            # ---- 单分量 + 显式分档（结构处理替代 ε 下界）----
            "S_bucket_reach": lambda r: (
                0.0 if r["n_seed"] == 0 else
                (1.0 if r["n_reach"] >= 8 else
                 0.5 if r["n_reach"] >= 2 else 0.25)),
            # ---- gen3 最强手术变体：Ω 去掉 Ω_N 的 min(1,·) 截断 ----
            "S_query": lambda r: _s_query(r["n_seed"], r["n_frames"],
                                          r["n_emergent"], r["omega_f"],
                                          r["comp"]),
        }
    return cands()


def _s_query(n_seed, n_frames, n_emergent, omega_f, comp, eps=1e-3):
    """与 `metaphor_graph.query_signal._s_query` 同一实现（独立复写以做交叉校验）。"""
    if n_seed <= 0 or n_frames <= 0:
        return 0.0
    vals = (max(min(1.0, n_frames / n_seed), eps),
            max(n_emergent / n_seed, eps), max(omega_f, eps))
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) * comp


def main():
    print("=" * 100)
    print("gen3 实验 3：候选查询侧标量总表 + 零假设控制")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        cands = build_candidates(rows)
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub),
                          n_pos_sub=sum(1 for r in sub if r["cascade_nonempty"]),
                          n_pos_all=sum(1 for r in rows if r["cascade_nonempty"]))}
        table = {}
        for name, g in cands.items():
            a_all, lo_all, hi_all = boot_auc(
                [g(r) for r in rows if r["cascade_nonempty"]],
                [g(r) for r in rows if not r["cascade_nonempty"]])
            a_sub, lo_sub, hi_sub = boot_auc(
                [g(r) for r in sub if r["cascade_nonempty"]],
                [g(r) for r in sub if not r["cascade_nonempty"]])
            cond, wden, per = strat_auc(rows, g)
            obs, p, nmean, nlo, nhi = perm_p(rows, g)
            obs_s, p_s, nmean_s, nlo_s, nhi_s = perm_p(sub, g)
            table[name] = dict(
                auc_all=a_all, auc_all_ci=[lo_all, hi_all],
                auc_sub=a_sub, auc_sub_ci=[lo_sub, hi_sub],
                cond_auc=cond, cond_weight=wden, cond_per_layer=per,
                perm_p_all=p, perm_null_all=[nmean, nlo, nhi],
                perm_p_sub=p_s, perm_null_sub=[nmean_s, nlo_s, nhi_s],
                perm_obs_sub=obs_s,
                agree_1bit=agree_1bit(rows, g), spearman_nseed=rho_seed(rows, g),
                uniq_all=len({round(g(r), 12) for r in rows}),
                uniq_sub=len({round(g(r), 12) for r in sub}),
            )
        res["candidates"] = table

        # ------------------------------------ 条件 z 分数（跨文档交叉验证）
        res["conditional_cv"] = {}
        for src in ("n_emergent", "n_new_domains", "n_reach"):
            for scheme, folds in (("cv_doc_parity", 2), ("cv_doc_mod5", 5)):
                vals = [None] * len(rows)
                for f in range(folds):
                    tr = [r for i, r in enumerate(rows) if i % folds != f]
                    te = [(i, r) for i, r in enumerate(rows) if i % folds == f]
                    from metaphor_graph.query_signal import StratifiedNormalizer
                    nz = StratifiedNormalizer(source=src).fit(tr)
                    for i, r in te:
                        vals[i] = nz.transform_one(int(r["n_seed"]), float(r[src]))
                tmp = [{**r, "_z": v} for r, v in zip(rows, vals)]
                subz = [t for t in tmp if t["n_seed"] >= 1]
                a_sub, lo, hi = boot_auc(
                    [t["_z"] for t in subz if t["cascade_nonempty"]],
                    [t["_z"] for t in subz if not t["cascade_nonempty"]])
                cond, wden, _ = strat_auc(tmp, lambda r: r["_z"])
                obs, p, nmean, nlo, nhi = perm_p(tmp, lambda r: r["_z"])
                res["conditional_cv"][f"{src}|{scheme}"] = dict(
                    auc_all=boot_auc([t["_z"] for t in tmp if t["cascade_nonempty"]],
                                     [t["_z"] for t in tmp
                                      if not t["cascade_nonempty"]])[0],
                    auc_sub=a_sub, auc_sub_ci=[lo, hi], cond_auc=cond,
                    perm_p=p, perm_null=[nmean, nlo, nhi],
                    agree_1bit=agree_1bit(tmp, lambda r: r["_z"]),
                    spearman_nseed=rho_seed(tmp, lambda r: r["_z"]),
                    uniq_sub=len({round(t["_z"], 9) for t in subz}))

        # -------------------------- 集合大小匹配的随机对照（最重要的一项）
        # 机制：cascade_nonempty = 1 ⟺ reachable_domains ∩ live_domains(doc) ≠ ∅。
        # 控制：保持「可达集合的**大小**」不变，把**身份**换成从本体域词表里
        # 随机抽的域，看 AUC 掉多少。掉得多 ⇒ 判别力来自「买到了对的域」；
        # 几乎不掉 ⇒ 判别力只是「集合更大」这个机械效应。
        vocab = sorted({dd for dd in d["meta"].get("live_domains", {}).values()
                        for dd in dd} or set())
        if not vocab:                       # 兜底：从行数据里收集
            vocab = sorted({dd for r in rows for dd in r["reachable_domains"]})
        live_by_doc = {k: set(v) for k, v in
                       d["meta"].get("live_domains", {}).items()}
        rng = random.Random(SEED)
        rand_rows = []
        for r in rows:
            k = len(r["reachable_domains"])
            live = live_by_doc.get(r["doc_id"], set())
            if k == 0:
                hit = 0
            else:
                samp = set(rng.sample(vocab, min(k, len(vocab))))
                hit = 1 if (samp & live) else 0
            rand_rows.append({**r, "_rand_nonempty": hit})
        # 随机集合（大小匹配）的 AUC
        a_r, lo_r, hi_r = boot_auc(
            [float(len(r["reachable_domains"]))
             for r in rand_rows if r["_rand_nonempty"]],
            [float(len(r["reachable_domains"]))
             for r in rand_rows if not r["_rand_nonempty"]])
        # 真实集合的 AUC（同一批行）
        a_t, lo_t, hi_t = boot_auc(
            [float(len(r["reachable_domains"]))
             for r in rand_rows if r["cascade_nonempty"]],
            [float(len(r["reachable_domains"]))
             for r in rand_rows if not r["cascade_nonempty"]])
        # 随机集合的「非空率」与真实非空率
        res["size_matched_random_set"] = dict(
            vocab_size=len(vocab),
            real_nonempty_rate=sum(1 for r in rand_rows
                                   if r["cascade_nonempty"]) / len(rand_rows),
            rand_nonempty_rate=sum(1 for r in rand_rows
                                   if r["_rand_nonempty"]) / len(rand_rows),
            auc_real_size=a_t, auc_real_size_ci=[lo_t, hi_t],
            auc_rand_size=a_r, auc_rand_size_ci=[lo_r, hi_r],
            # 用真实 vs 随机的「非空」做标签，看同一个「大小」标量的判别力
            auc_size_predicts_real=a_t, auc_size_predicts_rand=a_r,
        )
        # 同一控制下，n_emergent 的表现
        a_er, lo_er, hi_er = boot_auc(
            [float(r["n_emergent"]) for r in rand_rows if r["_rand_nonempty"]],
            [float(r["n_emergent"]) for r in rand_rows if not r["_rand_nonempty"]])
        res["size_matched_random_set"]["auc_emergent_predicts_rand"] = a_er
        res["size_matched_random_set"]["auc_emergent_predicts_rand_ci"] = [lo_er, hi_er]

        out[rule] = res

        # ---------------------------------------------------------- 打印
        n = res["_n"]
        print(f"\n{'=' * 100}\n[{rule}] n={n['n_all']}  n_seed≥1 {n['n_sub']}"
              f"（通路非空 {n['n_pos_sub']}）\n{'=' * 100}")
        print(f"  {'标量':22s} {'AUC全':>7s} {'AUC子集':>23s} {'层内AUC':>8s}"
              f" {'ρ(nseed)':>9s} {'1bit':>7s} {'取值':>5s} {'perm_p':>8s}")
        for name, v in sorted(table.items(),
                              key=lambda kv: -(kv[1]["cond_auc"]
                                               if kv[1]["cond_auc"] == kv[1]["cond_auc"]
                                               else -1)):
            print(f"  {name:22s} {v['auc_all']:>7.4f}"
                  f" {v['auc_sub']:>9.4f}[{v['auc_sub_ci'][0]:.3f},"
                  f"{v['auc_sub_ci'][1]:.3f}]"
                  f" {v['cond_auc']:>8.4f} {v['spearman_nseed']:>9.4f}"
                  f" {v['agree_1bit']:>7.4f} {v['uniq_sub']:>5d}"
                  f" {v['perm_p_sub']:>8.4f}")
        print(f"\n  [条件 z 分数（跨文档交叉验证）]")
        print(f"  {'设置':34s} {'AUC子集':>23s} {'层内AUC':>8s}"
              f" {'ρ(nseed)':>9s} {'1bit':>7s} {'perm_p':>8s}")
        for name, v in res["conditional_cv"].items():
            print(f"  {name:34s} {v['auc_sub']:>9.4f}[{v['auc_sub_ci'][0]:.3f},"
                  f"{v['auc_sub_ci'][1]:.3f}] {v['cond_auc']:>8.4f}"
                  f" {v['spearman_nseed']:>9.4f} {v['agree_1bit']:>7.4f}"
                  f" {v['perm_p']:>8.4f}")
        sm = res["size_matched_random_set"]
        print(f"\n  [集合大小匹配的随机对照]  域词表 {sm['vocab_size']} 个")
        print(f"    真实可达集合非空率 {sm['real_nonempty_rate']:.4f}"
              f"  vs 同大小随机集合非空率 {sm['rand_nonempty_rate']:.4f}")
        print(f"    用「可达集合大小」预测真实非空：AUC={sm['auc_real_size']:.4f}"
              f"[{sm['auc_real_size_ci'][0]:.3f},{sm['auc_real_size_ci'][1]:.3f}]")
        print(f"    用「可达集合大小」预测随机非空：AUC={sm['auc_rand_size']:.4f}"
              f"[{sm['auc_rand_size_ci'][0]:.3f},{sm['auc_rand_size_ci'][1]:.3f}]")
        print(f"    用 n_emergent  预测随机非空：AUC="
              f"{sm['auc_emergent_predicts_rand']:.4f}"
              f"[{sm['auc_emergent_predicts_rand_ci'][0]:.3f},"
              f"{sm['auc_emergent_predicts_rand_ci'][1]:.3f}]")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
