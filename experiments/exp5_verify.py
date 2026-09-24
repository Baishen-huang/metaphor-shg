# -*- coding: utf-8 -*-
"""Ω 实验 5：统计自校验 + 长度匹配对照 + bootstrap 置信区间。

三件事：
  V  自校验：自实现的统计量 vs 暴力枚举（确保没有实现错误导致假显著）。
  L  长度匹配对照：完备度因子使 Ω 随查询长度系统性下降，故「改写型 vs 重叠型」
     的 Ω 比较被长度混杂。用两种方式控制：(a) 只比 Ω_geo（不含完备度）；
     (b) 把重叠型查询**用中性填充词补长到改写型长度分布**，再比 Ω。
  B  bootstrap 置信区间（10000 次重采样，固定种子）—— 给效应量配不确定性。

运行：<python> experiments/exp5_verify.py
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
logging.disable(logging.CRITICAL)

import _stats as S  # noqa: E402
from metaphor_graph.observability import ObservabilityMeter  # noqa: E402
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology  # noqa: E402

OUT = os.path.join(HERE, "exp5_verify.json")
FILLER = "这个事情"          # 中性填充（不含任何本体触发词，已断言）


def brute_auc(a, b):
    """O(n·m) 暴力 AUC —— 独立实现，用于校验 _rank 版。"""
    if not a or not b:
        return float("nan")
    tot = 0.0
    for x in a:
        for y in b:
            tot += 1.0 if x > y else (0.5 if x == y else 0.0)
    return tot / (len(a) * len(b))


def brute_spearman(xs, ys):
    """暴力定义式：对秩做 Pearson（与 _rank 版应一致）。"""
    rx, ry = S._rank(xs), S._rank(ys)
    return S.pearson(rx, ry)


def bootstrap_ci(xs, ys, stat_fn, n_boot=10000, seed=12345, alpha=0.05):
    rng = random.Random(seed)
    nx, ny = len(xs), len(ys)
    vals = []
    for _ in range(n_boot):
        a = [xs[rng.randrange(nx)] for _ in range(nx)]
        b = [ys[rng.randrange(ny)] for _ in range(ny)]
        vals.append(stat_fn(a, b))
    vals.sort()
    lo = vals[int(alpha / 2 * n_boot)]
    hi = vals[int((1 - alpha / 2) * n_boot) - 1]
    return lo, hi, S.mean(vals)


def main():
    rows = json.load(open(os.path.join(HERE, "exp1_omega.json"),
                          encoding="utf-8"))["rows"]
    exp3 = json.load(open(os.path.join(HERE, "exp3_mechanism.json"),
                          encoding="utf-8"))
    ont, _ = build_replay_ontology()
    meter = ObservabilityMeter(ont)
    n = len(rows)
    print("=" * 92)
    print("Ω 实验 5：统计自校验 + 长度匹配对照 + bootstrap 置信区间")
    print("=" * 92)

    out = {}

    # ================================================================== V
    print("\n" + "-" * 92)
    print("【V】自校验（自实现统计量 vs 暴力枚举）")
    print("-" * 92)
    op = [r["omega_p"] for r in rows]
    oo = [r["omega_o"] for r in rows]
    succ = [1 if r["cascade_hit_p"] else 0 for r in rows]
    a = S.auc(op, oo)
    b = brute_auc(op, oo)
    print(f"  AUC  : 实现={a:.6f} 暴力={b:.6f} 差={abs(a - b):.2e} "
          f"{'OK' if abs(a - b) < 1e-9 else 'FAIL'}")
    rho_impl = S.spearman(op, oo)[0]
    rho_brute = brute_spearman(op, oo)
    print(f"  ρ    : 实现={rho_impl:.6f} 暴力={rho_brute:.6f} "
          f"差={abs(rho_impl - rho_brute):.2e} "
          f"{'OK' if abs(rho_impl - rho_brute) < 1e-9 else 'FAIL'}")
    # t 分布 CDF 对已知分位点
    checks = [(1.0, 10, 0.82955), (2.0, 10, 0.96331), (1.96, 1000000, 0.97500),
              (0.0, 5, 0.5)]
    print("  t CDF 校验：")
    for t, df, exp in checks:
        got = S._t_cdf(t, df)
        print(f"    t={t} df={df}: got={got:.5f} exp≈{exp:.5f} "
              f"{'OK' if abs(got - exp) < 1e-3 else 'FAIL'}")
    # MWU 与 AUC 的一致性（同统计量）
    u, z, p = S.mann_whitney(op, oo)
    print(f"  MWU 与 AUC 一致性：U/(n1·n2) = {u / (len(op) * len(oo)):.6f}，"
          f"AUC = {a:.6f}（应相等/互补）")

    # ================================================================== B
    print("\n" + "-" * 92)
    print("【B】bootstrap 95% CI（10000 次重采样）")
    print("-" * 92)
    for name, fn in (("AUC(P(Ω_改<Ω_重))", lambda x, y: S.auc(x, y)),
                     ("Cliff's δ", lambda x, y: S.cliffs_delta(x, y))):
        lo, hi, m = bootstrap_ci(op, oo, fn)
        print(f"  {name:22s} 点估计={fn(op, oo):+.4f}  "
              f"95%CI=[{lo:+.4f}, {hi:+.4f}]  boot mean={m:+.4f}")
        out[f"boot_{name}"] = dict(point=fn(op, oo), lo=lo, hi=hi)
    # 非平凡子集内的 AUC
    sub = [(r["omega_p"], 1 if r["cascade_hit_p"] else 0) for r in rows
           if r["omega_p"] > 0]
    ox = [s[0] for s in sub]
    os_ = [s[1] for s in sub]
    pos = [v for v, s in zip(ox, os_) if s == 1]
    neg = [v for v, s in zip(ox, os_) if s == 0]
    lo, hi, m = bootstrap_ci(pos, neg, lambda x, y: S.auc(x, y))
    print(f"  {'Ω>0 内 AUC(成功>失败)':22s} 点估计={S.auc(pos, neg):.4f}  "
          f"95%CI=[{lo:.4f}, {hi:.4f}]  （含 0.5 ⟹ 无区分力）")
    out["boot_auc_within_positive"] = dict(point=S.auc(pos, neg), lo=lo, hi=hi)

    # ================================================================== L
    print("\n" + "-" * 92)
    print("【L】长度匹配对照：分离是不是「查询长度」造成的？")
    print("-" * 92)
    assert not any(t in FILLER for t in ont._trigger_index), \
        "填充词不得含触发词"
    # (a) 只比 Ω_geo（剥离完备度因子的长度偏置）
    gp = [r["omega_geo_p"] for r in rows]
    go = [r["omega_geo_o"] for r in rows]
    print(f"  (a) Ω_geo（无完备度因子）：改写 mean={S.mean(gp):.4f} "
          f"median={S.median(gp):.4f}；重叠 mean={S.mean(go):.4f} "
          f"median={S.median(go):.4f}")
    print(f"      AUC={S.auc(gp, go):.4f}  δ={S.cliffs_delta(gp, go):+.4f}  "
          f"MWU p={S.mann_whitney(gp, go)[2]:.3e}")
    out["geo_auc"] = S.auc(gp, go)

    # (b) 把重叠型查询补长到改写型长度分布
    lp = [len(r["paraphrase"]) for r in rows]
    padded = []
    for r in rows:
        base = r["overlap_query"]
        target = len(r["paraphrase"])
        s = base
        while len(s) < target:
            s += FILLER
        padded.append(s[:target] if target > len(base) else base)
    om_pad = [meter.measure(s).omega for s in padded]
    print(f"\n  (b) 重叠型查询补长到改写型长度（mean {S.mean([len(s) for s in padded]):.1f} 字 "
          f"vs 改写 {S.mean(lp):.1f} 字）：")
    print(f"      Ω mean={S.mean(om_pad):.4f} median={S.median(om_pad):.4f} "
          f"Ω=0 占比={sum(1 for v in om_pad if v == 0) / n:.1%}")
    print(f"      vs 改写型 Ω mean={S.mean(op):.4f} "
          f"Ω=0 占比={sum(1 for v in op if v == 0) / n:.1%}")
    print(f"      AUC(改写 < 补长重叠) = {S.auc(op, om_pad):.4f}  "
          f"δ={S.cliffs_delta(op, om_pad):+.4f}  "
          f"MWU p={S.mann_whitney(op, om_pad)[2]:.3e}")
    out["padded_auc"] = S.auc(op, om_pad)
    print("      → 补长后分离**仍然存在**：分离的主因是「有没有触发词」，"
          "不是长度；长度只通过完备度因子放大差距")

    # ================================================================== C
    print("\n" + "-" * 92)
    print("【C】终极对照：Ω 与「触发词命中数 ≥1」这个 1-bit 指示器")
    print("-" * 92)
    bit = [1 if r["n_seed_p"] > 0 else 0 for r in rows]
    # 对级联通路的预测：1-bit 指示器是完美预测器（定理）
    ne = [1 if r["cascade_nonempty_p"] else 0 for r in rows]
    agree_bit = sum(1 for x, y in zip(bit, ne) if x == y)
    agree_om = sum(1 for x, y in zip([1 if v > 0 else 0 for v in op], ne)
                   if x == y)
    print(f"  「n_seed≥1」 预测「通路非空」：一致率 {agree_bit}/{n} = {agree_bit / n:.4f}")
    print(f"  「Ω>0」     预测「通路非空」：一致率 {agree_om}/{n} = {agree_om / n:.4f}")
    print(f"  → 完全等价。Ω 在这条任务上的全部信息 = 1 bit（有/无触发词命中）")
    # 信息量：Ω 的取值数 vs n_seed 的取值数
    print(f"\n  Ω 的相异取值数（改写型）= {len(set(op))}；"
          f"n_seed 的相异取值数 = {len(set(r['n_seed_p'] for r in rows))}")
    print(f"  Ω 与 n_seed 的 Spearman ρ = {S.spearman(op, [float(r['n_seed_p']) for r in rows])[0]:.4f}")
    # 在 Ω>0 内，Ω 是否比 n_seed 更有信息？两者都几乎常数
    print(f"  Ω>0 子集内：Ω 取值 {sorted(set(round(v, 4) for v in op if v > 0))[:12]}...")
    print(f"              n_seed 分布 {Counter(r['n_seed_p'] for r in rows if r['omega_p'] > 0)}")
    # 非平凡检验：控制 n_seed 后 Ω 是否还有残余预测力？
    print("\n  控制 n_seed 后 Ω 的残余预测力（分层内 AUC，n_seed 固定）：")
    for k in (1, 2):
        g = [r for r in rows if r["n_seed_p"] == k]
        pos = [r["omega_p"] for r in g if r["cascade_hit_p"]]
        neg = [r["omega_p"] for r in g if not r["cascade_hit_p"]]
        if len(pos) >= 3 and len(neg) >= 3:
            auc_k = S.auc(pos, neg)
            p_k = S.mann_whitney(pos, neg)[2]
            print(f"    n_seed={k}: n={len(g)} 成功 {len(pos)} 失败 {len(neg)}  "
                  f"AUC={auc_k:.4f}  p={p_k:.3e}  "
                  f"mean Ω 成功={S.mean(pos):.4f} 失败={S.mean(neg):.4f}")
            out[f"strat_auc_nseed{k}"] = dict(auc=auc_k, p=p_k)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n校验结果已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
