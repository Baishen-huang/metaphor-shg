# -*- coding: utf-8 -*-
"""gen3 实验 2：**信号到底在哪一步被毁掉的**（两层因子分解）。

实验 1 的 2^4 开关对照给出一个反直觉结果：`floor / normalize / completeness /
outer_zero` 四个**合成层**开关的任意组合都拿不回 `n_emergent` 的信号
（最好 ~0.65，而 n_emergent 本身 0.836）。也就是说，gen1 报告里归咎的
「几何平均 + ε 下界 + 完备度因子」**不是全部原因**。

本实验把「分量定义」与「合成算子」分成两层，做完整因子分解：

  层 1 分量定义（4 档）：
    clip+div     Ω 的原做法：min(1, x / n_seed)
    noclip+div   只去掉 min(1,·) 截断，保留 / n_seed
    clip+nodiv   保留 min(1,·)，去掉 / n_seed（分母换成常量 1）
    noclip+nodiv 两者都去掉（= 原始计数）
  层 2 合成算子（4 档 × 2 下界 × 2 完备度）：
    geo / arith / max / sum   ×   floor∈{ε, 结构化丢弃} × comp∈{乘, 不乘}

判决标准：在**同一个合成算子**下，把分量从 clip+div 换成 noclip 带来的
AUC 变化，与「换合成算子」带来的变化比较。谁的变化大，谁就是元凶。

产物：experiments/gen3/exp_g3_2_mechanism.json + stdout
运行：<python> experiments/gen3/exp_g3_2_mechanism.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

import _stats as S                                              # noqa: E402
from _collect import load_dataset                               # noqa: E402

OUT = os.path.join(HERE, "exp_g3_2_mechanism.json")
EPS = 1e-3
RULES = ("json", "source", "metanet", "source_type")
COMP_DEFS = ("clip+div", "noclip+div", "clip+nodiv", "noclip+nodiv")
OPS = ("geo", "arith", "max", "sum")


def boot_auc(pos, neg, n_boot=2000, seed=20260924):
    import random
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


def auc_of(rows, getter, target="cascade_nonempty"):
    pos = [getter(r) for r in rows if r[target]]
    neg = [getter(r) for r in rows if not r[target]]
    return boot_auc(pos, neg)


# ------------------------------------------------------------- 分量 + 合成
def components(r, compdef):
    """(Ω_E, Ω_N, Ω_F) 在给定分量定义下的取值。n_seed=0 → None。"""
    ns = r["n_seed"]
    if ns <= 0:
        return None
    e_raw, n_raw = float(r["n_frames"]), float(r["n_emergent"])
    if compdef == "clip+div":
        return (min(1.0, e_raw / ns), min(1.0, n_raw / ns), r["omega_f"])
    if compdef == "noclip+div":
        return (e_raw / ns, n_raw / ns, r["omega_f"])
    if compdef == "clip+nodiv":
        return (min(1.0, e_raw), min(1.0, n_raw), r["omega_f"])
    if compdef == "noclip+nodiv":
        return (e_raw, n_raw, r["omega_f"])
    raise ValueError(compdef)


def synthesize(cs, op, floor, use_comp, comp_value):
    if cs is None:
        return 0.0
    vals = [max(v, EPS) for v in cs] if floor else [v for v in cs if v > 0.0]
    if not vals:
        return 0.0
    if op == "geo":
        out = math.exp(sum(math.log(v) for v in vals) / len(vals))
    elif op == "arith":
        out = sum(vals) / len(vals)
    elif op == "max":
        out = max(vals)
    elif op == "sum":
        out = sum(vals)
    else:
        raise ValueError(op)
    return out * comp_value if use_comp else out


def make_getter(compdef, op, floor, use_comp):
    def g(r):
        return synthesize(components(r, compdef), op, floor, use_comp, r["comp"])
    return g


def main():
    print("=" * 100)
    print("gen3 实验 2：分量定义 vs 合成算子 —— 信号在哪一层被毁掉")
    print("=" * 100)
    out = {}
    for rule in RULES:
        d = load_dataset(rule)
        rows = d["rows"]
        sub = [r for r in rows if r["n_seed"] >= 1]
        L1 = [r for r in rows if r["n_seed"] == 1]
        res = {"_n": dict(n_all=len(rows), n_sub=len(sub), n_L1=len(L1),
                          n_pos_sub=sum(1 for r in sub if r["cascade_nonempty"]),
                          n_pos_L1=sum(1 for r in L1 if r["cascade_nonempty"]))}

        # ------------------------------------------------- 参考点
        refs = {
            "ref_n_seed": lambda r: float(r["n_seed"]),
            "ref_n_emergent": lambda r: float(r["n_emergent"]),
            "ref_n_reach": lambda r: float(r["n_reach"]),
            "ref_omega": lambda r: r["omega"],
        }
        for tag, g in refs.items():
            a_all, lo_all, hi_all = auc_of(rows, g)
            a_sub, lo_sub, hi_sub = auc_of(sub, g)
            a_L1 = (S.auc([g(r) for r in L1 if r["cascade_nonempty"]],
                          [g(r) for r in L1 if not r["cascade_nonempty"]])
                    if L1 else float("nan"))
            res[tag] = dict(auc_all=a_all, auc_all_ci=[lo_all, hi_all],
                            auc_sub=a_sub, auc_sub_ci=[lo_sub, hi_sub],
                            auc_L1=a_L1,
                            uniq_all=len({round(g(r), 12) for r in rows}),
                            agree_1bit=sum(1 for r in rows
                                           if (g(r) > 0) == (r["n_seed"] >= 1))
                            / len(rows),
                            spearman_nseed=S.spearman(
                                [g(r) for r in rows],
                                [float(r["n_seed"]) for r in rows])[0])

        # ------------------------------------------------- 2×4×2×2 因子
        grid = {}
        for compdef in COMP_DEFS:
            for op in OPS:
                for floor in (True, False):
                    for use_comp in (True, False):
                        tag = f"{compdef}|{op}|floor={int(floor)}|comp={int(use_comp)}"
                        g = make_getter(compdef, op, floor, use_comp)
                        a_sub, lo, hi = auc_of(sub, g)
                        grid[tag] = dict(
                            compdef=compdef, op=op, floor=floor,
                            use_comp=use_comp,
                            auc_all=auc_of(rows, g)[0],
                            auc_sub=a_sub, auc_sub_ci=[lo, hi],
                            uniq_all=len({round(g(r), 12) for r in rows}),
                            agree_1bit=sum(1 for r in rows
                                           if (g(r) > 0) == (r["n_seed"] >= 1))
                            / len(rows),
                            spearman_nseed=S.spearman(
                                [g(r) for r in rows],
                                [float(r["n_seed"]) for r in rows])[0])
        res["grid"] = grid

        # --------------------------------------- 效应分解：哪一层的方差大
        # 对每个 (op, floor, use_comp) 组合，比较 4 档分量定义带来的 AUC 极差；
        # 对每个分量定义，比较 16 种合成设置带来的 AUC 极差。
        by_comp = defaultdict(list)
        by_op = defaultdict(list)
        for v in grid.values():
            key_c = v["compdef"]
            key_o = f"{v['op']}|floor={int(v['floor'])}|comp={int(v['use_comp'])}"
            by_comp[key_c].append(v["auc_sub"])
            by_op[key_o].append(v["auc_sub"])
        # 对每个合成设置（保持合成算子固定），分量定义带来的极差
        spread_comp = {}
        for k, vals in by_comp.items():
            spread_comp[k] = dict(min=min(vals), max=max(vals),
                                  range=max(vals) - min(vals),
                                  mean=sum(vals) / len(vals))
        # 对每个分量定义，合成算子带来的极差
        spread_op = {}
        for k, vals in by_op.items():
            spread_op[k] = dict(min=min(vals), max=max(vals),
                                range=max(vals) - min(vals))
        res["effect_decomposition"] = dict(
            comp_definition=spread_comp, composition=spread_op,
            # 固定合成算子（Ω 的实际设置）时，分量定义的效应
            comp_effect_under_omega_op=dict(
                values={k: grid[k]["auc_sub"] for k in grid
                        if k.endswith("geo|floor=1|comp=1")},
                min=min(v["auc_sub"] for v in grid.values()
                        if v["op"] == "geo" and v["floor"]
                        and v["use_comp"]),
                max=max(v["auc_sub"] for v in grid.values()
                        if v["op"] == "geo" and v["floor"]
                        and v["use_comp"]),
            ),
            # 固定分量定义（clip+div = Ω 原口径）时，合成设置的效应
            op_effect_under_omega_comps=dict(
                values={k: grid[k]["auc_sub"] for k in grid
                        if k.startswith("clip+div|")},
                min=min(v["auc_sub"] for v in grid.values()
                        if v["compdef"] == "clip+div"),
                max=max(v["auc_sub"] for v in grid.values()
                        if v["compdef"] == "clip+div"),
            ),
        )

        # ---------------------------------- 分量内部的档位损失（可解释性证据）
        loss = {}
        for k in (1, 2, 3, 4):
            Lk = [r for r in rows if int(r["n_seed"]) == k]
            if len(Lk) < 2:
                continue
            loss[str(k)] = dict(
                n=len(Lk),
                uniq_n_emergent=len({r["n_emergent"] for r in Lk}),
                uniq_omega_n=len({min(1.0, r["n_emergent"] / k) for r in Lk}),
                uniq_omega_e=len({min(1.0, r["n_frames"] / k) for r in Lk}),
                uniq_omega_f=len({r["omega_f"] for r in Lk}),
                uniq_omega=len({r["omega"] for r in Lk}),
                uniq_comp=len({r["comp"] for r in Lk}),
                n_omega_n_at_cap=sum(1 for r in Lk
                                     if min(1.0, r["n_emergent"] / k) >= 1.0),
            )
        res["per_layer_cardinality"] = loss

        # -------------------------------- Ω 的层内序由谁决定（秩序归因）
        order = {}
        for k in sorted({int(r["n_seed"]) for r in sub}):
            Lk = [r for r in sub if int(r["n_seed"]) == k]
            if len(Lk) < 4:
                continue
            order[str(k)] = {
                "n": len(Lk),
                "rho_omega_vs_n_emergent": S.spearman(
                    [r["omega"] for r in Lk],
                    [float(r["n_emergent"]) for r in Lk])[0],
                "rho_omega_vs_omega_n": S.spearman(
                    [r["omega"] for r in Lk], [r["omega_n"] for r in Lk])[0],
                "rho_omega_vs_omega_e": S.spearman(
                    [r["omega"] for r in Lk], [r["omega_e"] for r in Lk])[0],
                "rho_omega_vs_omega_f": S.spearman(
                    [r["omega"] for r in Lk], [r["omega_f"] for r in Lk])[0],
                "rho_omega_vs_comp": S.spearman(
                    [r["omega"] for r in Lk], [r["comp"] for r in Lk])[0],
            }
        res["rank_attribution"] = order

        # ------------------------- 完备度的共线：ρ(comp, n_seed) 与层内变异
        res["completeness_collinearity"] = dict(
            rho_all=S.spearman([r["comp"] for r in rows],
                               [float(r["n_seed"]) for r in rows])[0],
            rho_sub=S.spearman([r["comp"] for r in sub],
                               [float(r["n_seed"]) for r in sub])[0],
            auc_all=auc_of(rows, lambda r: r["comp"])[0],
            auc_sub=auc_of(sub, lambda r: r["comp"])[0],
            n_unique_all=len({r["comp"] for r in rows}),
        )
        out[rule] = res

        # ---------------------------------------------------------- 打印
        n = res["_n"]
        print(f"\n{'=' * 100}\n[{rule}] n={n['n_all']}  n_seed≥1 {n['n_sub']}"
              f"（通路非空 {n['n_pos_sub']}）  n_seed=1 层 {n['n_L1']}"
              f"（非空 {n['n_pos_L1']}）\n{'=' * 100}")
        print(f"  {'参考点':22s} {'AUC全':>7s} {'AUC子集':>10s} {'AUC层1':>7s}"
              f" {'取值数':>6s} {'1bit':>7s} {'ρ(nseed)':>9s}")
        for tag in ("ref_n_seed", "ref_n_emergent", "ref_n_reach", "ref_omega"):
            v = res[tag]
            print(f"  {tag:22s} {v['auc_all']:>7.4f} {v['auc_sub']:>10.4f}"
                  f" {v['auc_L1']:>7.4f} {v['uniq_all']:>6d}"
                  f" {v['agree_1bit']:>7.4f} {v['spearman_nseed']:>9.4f}")
        print(f"\n  [分量定义 × 合成算子：AUC(n_seed≥1 子集)]")
        print(f"  {'合成设置':34s}" + "".join(f"{c:>15s}" for c in COMP_DEFS))
        for op in OPS:
            for floor in (True, False):
                for uc in (True, False):
                    key = f"{op}|floor={int(floor)}|comp={int(uc)}"
                    cells = []
                    for cd in COMP_DEFS:
                        cells.append(f"{grid[f'{cd}|{key}']['auc_sub']:>15.4f}")
                    print(f"  {key:34s}" + "".join(cells))
        ed = res["effect_decomposition"]
        print(f"\n  [效应分解]")
        print(f"  固定 Ω 的合成设置（geo+ε+comp）时，4 档分量定义 "
              f"AUC 区间 [{ed['comp_effect_under_omega_op']['min']:.4f},"
              f"{ed['comp_effect_under_omega_op']['max']:.4f}]"
              f"  极差 {ed['comp_effect_under_omega_op']['max'] - ed['comp_effect_under_omega_op']['min']:.4f}")
        print(f"  固定 Ω 的分量定义（clip+div）时，16 种合成设置 "
              f"AUC 区间 [{ed['op_effect_under_omega_comps']['min']:.4f},"
              f"{ed['op_effect_under_omega_comps']['max']:.4f}]"
              f"  极差 {ed['op_effect_under_omega_comps']['max'] - ed['op_effect_under_omega_comps']['min']:.4f}")
        print(f"  → 哪个极差大，哪一层就是元凶。")
        print(f"\n  [分量档位损失]")
        for k, v in loss.items():
            print(f"    n_seed={k}: n={v['n']:4d}  取值数 "
                  f"n_emergent={v['uniq_n_emergent']:3d} → Ω_N={v['uniq_omega_n']}"
                  f"   Ω_E={v['uniq_omega_e']}  Ω_F={v['uniq_omega_f']}"
                  f"   Ω={v['uniq_omega']:3d}  comp={v['uniq_comp']:3d}"
                  f"   Ω_N 顶到 1.0 的 {v['n_omega_n_at_cap']}")
        print(f"  [Ω 的层内序由谁决定]")
        for k, v in order.items():
            print(f"    n_seed={k} (n={v['n']}): ρ(Ω,n_em)={v['rho_omega_vs_n_emergent']:.3f}"
                  f"  ρ(Ω,Ω_N)={v['rho_omega_vs_omega_n']:.3f}"
                  f"  ρ(Ω,Ω_E)={v['rho_omega_vs_omega_e']:.3f}"
                  f"  ρ(Ω,Ω_F)={v['rho_omega_vs_omega_f']:.3f}"
                  f"  ρ(Ω,comp)={v['rho_omega_vs_comp']:.3f}")
        cc = res["completeness_collinearity"]
        print(f"  [完备度] ρ(comp,n_seed)={cc['rho_all']:.4f}"
              f"  AUC 全样本={cc['auc_all']:.4f} 子集={cc['auc_sub']:.4f}"
              f"  取值数={cc['n_unique_all']}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
