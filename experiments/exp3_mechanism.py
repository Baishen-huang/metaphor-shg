# -*- coding: utf-8 -*-
"""Ω 实验 3：机制分解 —— 级联通路失败的两个通道，Ω 只覆盖哪一个？

实验 1/2 已确立：
  (a) 改写型 Ω 显著低于重叠型（但 82% 的改写型 Ω 恰好 = 0）；
  (b) Ω 与「触发词命中数」秩相关 ρ=0.9949 —— 几乎是同一个量；
  (c) Ω=0 ⟹ 级联通路必空，这是代码结构的定理。

本脚本把「级联通路失败」拆成两个互斥通道，并检验 Ω 各覆盖多少：

  通道 1（激活失败）  查询没有触发词 → match_by_triggers 空 → agg 空 → 通路空
  通道 2（覆盖失败）  有触发词、框架点亮了，但点亮的域闭包与图中任何 live 超边
                      的域不相交 → 仍然 agg 空（Ω 对此**盲**：Ω 不读图）
  通道 3（召回失败）  通路非空但金标 chunk 未被覆盖 → 召回 < 1

并做三件对照：
  A  Ω_G（读图版）：查询侧 + 图结构（不读候选排序）能否把通道 2 也判出来？
     若能，则说明「Ω 缺的是图可达性，不是更多查询侧熵」。
  B  门控等价性：Ω ≥ θ 门控 与 现有 `if not agg: semantic_fallback` 判据是否等价？
     若等价，Ω 的「能门控」不带来任何新的工程动作。
  C  逐通道归因表：每个通道的查询数、Ω 分布、以及「Ω 能否区分」。

运行：<python> experiments/exp3_mechanism.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
logging.disable(logging.CRITICAL)

import _stats as S  # noqa: E402

from metaphor_graph.observability import (  # noqa: E402
    ObservabilityMeter, matched_triggers, activated_structure, measure)

import exp1_omega_distribution as E1  # noqa: E402

OUT = os.path.join(HERE, "exp3_mechanism.json")


def domain_closure(query, ont):
    """查询点亮的框架/级联所覆盖的域闭包（与 cross_domain_retrieve 同口径）。"""
    st = activated_structure(query, ont)
    targets = set()
    for fid in st["frames"]:
        fs = ont.get_frame(fid)
        if fs:
            targets.add(fs.target_domain)
            targets.add(fs.source_domain)
    for cid in st["cascades"]:
        spec = ont.get_cascade_spec(cid)
        if spec is None:
            continue
        for fid in spec.member_frames:
            fs = ont.get_frame(fid)
            if fs:
                targets.add(fs.target_domain)
                targets.add(fs.source_domain)
    return targets, st


def omega_graph(query, ont, eng, eps=1e-3):
    """Ω_G：图可达版可观测性（仍不读候选排序，只读图的域覆盖）。

    Ω_G 的 Ω_E 分量换成「点亮且**在图中有超边可落**的域数 / 种子触发词数」，
    其余分量与 Ω 一致。用来定位 Ω 缺的是哪一层信息。
    """
    base = measure(query, ont)
    if base.n_seed_triggers == 0:
        return 0.0, 0
    targets, st = domain_closure(query, ont)
    live_domains = set()
    for e in eng.live_edges():
        live_domains.add(e.target_domain)
        live_domains.add(e.source_domain)
    reachable = targets & live_domains
    e_g = min(1.0, len(reachable) / base.n_seed_triggers)
    from metaphor_graph.observability import geometric_mean
    if not reachable:
        return 0.0, 0
    geo = geometric_mean((e_g, base.omega_n, base.omega_f), eps=eps)
    return geo * base.completeness, len(reachable)


def main():
    ont, n_frames, docs, all_queries = E1.build_world()
    meter = ObservabilityMeter(ont)
    rows = json.load(open(os.path.join(HERE, "exp1_omega.json"),
                          encoding="utf-8"))["rows"]
    n = len(rows)
    print("=" * 92)
    print("Ω 实验 3：级联通路失败的机制分解（激活失败 / 覆盖失败 / 召回失败）")
    print("=" * 92)

    # ---- 逐查询计算图可达性 ----
    for r in rows:
        d = docs[r["doc_id"]]
        r["omega_g_p"], r["n_reach_p"] = omega_graph(
            r["paraphrase"], ont, d["eng"])
        r["omega_g_o"], r["n_reach_o"] = omega_graph(
            r["overlap_query"], ont, d["eng"])

    # ============================================================ 通道分解
    print("\n" + "-" * 92)
    print("【1】级联通路失败的三通道分解（改写型 n=%d）" % n)
    print("-" * 92)
    ch = Counter()
    for r in rows:
        if r["n_seed_p"] == 0:
            ch["1 激活失败（无触发词）"] += 1
        elif not r["cascade_nonempty_p"]:
            ch["2 覆盖失败（有框架无落点）"] += 1
        elif not r["cascade_hit_p"]:
            ch["3 召回失败（通路非空未命中金标）"] += 1
        else:
            ch["0 成功"] += 1
    for k in sorted(ch):
        print(f"  {k:26s} {ch[k]:>4d}  ({ch[k] / n:>6.1%})")
    tot_fail = n - ch["0 成功"]
    print(f"  → 通路失败共 {tot_fail} 条 = {tot_fail / n:.1%}")

    print("\n  各通道的 Ω 分布（检验 Ω 是否只在通道 1 上有区分度）：")
    print(f"  {'通道':26s} {'n':>5s} {'mean Ω':>9s} {'median':>9s} "
          f"{'mean Ω_G':>10s} {'Ω_G=0 占比':>11s}")
    for k in sorted(ch):
        g = [r for r in rows
             if (("1 激活失败" in k and r["n_seed_p"] == 0) or
                 ("2 覆盖失败" in k and r["n_seed_p"] > 0
                  and not r["cascade_nonempty_p"]) or
                 ("3 召回失败" in k and r["cascade_nonempty_p"]
                  and not r["cascade_hit_p"]) or
                 ("0 成功" in k and r["cascade_hit_p"]))]
        if not g:
            continue
        og = [r["omega_g_p"] for r in g]
        print(f"  {k:26s} {len(g):>5d} {S.mean([r['omega_p'] for r in g]):>9.4f} "
              f"{S.median([r['omega_p'] for r in g]):>9.4f} "
              f"{S.mean(og):>10.4f} "
              f"{sum(1 for v in og if v == 0) / len(og):>11.1%}")

    # ============================================================ A: Ω_G
    print("\n" + "-" * 92)
    print("【A】Ω_G（读图版）能否判出「覆盖失败」通道？")
    print("-" * 92)
    succ = [1 if r["cascade_hit_p"] else 0 for r in rows]
    nonempty = [1 if r["cascade_nonempty_p"] else 0 for r in rows]
    op = [r["omega_p"] for r in rows]
    og = [r["omega_g_p"] for r in rows]
    nseed = [float(r["n_seed_p"]) for r in rows]
    print(f"  AUC(预测「通路非空」)：Ω = {S.auc([op[i] for i in range(n) if nonempty[i]], [op[i] for i in range(n) if not nonempty[i]]):.4f}"
          f" ；Ω_G = {S.auc([og[i] for i in range(n) if nonempty[i]], [og[i] for i in range(n) if not nonempty[i]]):.4f}")
    print(f"  AUC(预测「通路命中」)：Ω = {S.auc([op[i] for i in range(n) if succ[i]], [op[i] for i in range(n) if not succ[i]]):.4f}"
          f" ；Ω_G = {S.auc([og[i] for i in range(n) if succ[i]], [og[i] for i in range(n) if not succ[i]]):.4f}")
    # Ω_G = 0 与通路空 的一致性
    gz = [r for r in rows if r["omega_g_p"] == 0.0]
    gz_ne = sum(1 for r in gz if r["cascade_nonempty_p"])
    print(f"\n  Ω_G=0 的查询 {len(gz)} 条；其中通路非空的 {gz_ne} 条 "
          f"（应为 0 —— Ω_G 读图，故与通路非空性定义性一致）")
    gz_hit = sum(1 for r in gz if r["cascade_hit_p"])
    print(f"  Ω_G=0 中通路命中的 {gz_hit} 条")
    # 通道 2 是否被 Ω_G 判出
    c2 = [r for r in rows if r["n_seed_p"] > 0 and not r["cascade_nonempty_p"]]
    c3 = [r for r in rows if r["cascade_nonempty_p"]]
    if c2 and c3:
        print(f"\n  通道 2（覆盖失败，n={len(c2)}）vs 通道 3（通路非空，n={len(c3)}）：")
        print(f"    Ω  mean {S.mean([r['omega_p'] for r in c2]):.4f} vs "
              f"{S.mean([r['omega_p'] for r in c3]):.4f}  "
              f"AUC={S.auc([r['omega_p'] for r in c2], [r['omega_p'] for r in c3]):.4f}")
        print(f"    Ω_G mean {S.mean([r['omega_g_p'] for r in c2]):.4f} vs "
              f"{S.mean([r['omega_g_p'] for r in c3]):.4f}  "
              f"AUC={S.auc([r['omega_g_p'] for r in c2], [r['omega_g_p'] for r in c3]):.4f}")
        print(f"    n_reach mean {S.mean([r['n_reach_p'] for r in c2]):.3f} vs "
              f"{S.mean([r['n_reach_p'] for r in c3]):.3f}")
        print("    → 通道 2 与通道 3 在 Ω 上几乎不可分（都是『有触发词』），"
              "Ω_G 才把它们分开")
    # 通道 3 内部的成功 vs 召回失败
    if c3:
        ok = [r for r in c3 if r["cascade_hit_p"]]
        bad = [r for r in c3 if not r["cascade_hit_p"]]
        print(f"\n  通道 3 内部：成功 n={len(ok)} vs 召回失败 n={len(bad)}")
        if ok and bad:
            print(f"    Ω   mean {S.mean([r['omega_p'] for r in ok]):.4f} vs "
                  f"{S.mean([r['omega_p'] for r in bad]):.4f}  "
                  f"AUC={S.auc([r['omega_p'] for r in ok], [r['omega_p'] for r in bad]):.4f}  "
                  f"MWU p={S.mann_whitney([r['omega_p'] for r in ok], [r['omega_p'] for r in bad])[2]:.3e}")
            print(f"    Ω_G mean {S.mean([r['omega_g_p'] for r in ok]):.4f} vs "
                  f"{S.mean([r['omega_g_p'] for r in bad]):.4f}  "
                  f"AUC={S.auc([r['omega_g_p'] for r in ok], [r['omega_g_p'] for r in bad]):.4f}  "
                  f"MWU p={S.mann_whitney([r['omega_g_p'] for r in ok], [r['omega_g_p'] for r in bad])[2]:.3e}")
            print(f"    级联召回 mean {S.mean([r['cascade_recall_p'] for r in ok]):.4f} vs "
                  f"{S.mean([r['cascade_recall_p'] for r in bad]):.4f}")

    # ============================================================ B: 门控等价
    print("\n" + "-" * 92)
    print("【B】门控等价性：Ω 门控 vs 现有 `if not agg` 判据")
    print("-" * 92)
    # 现有代码：cross_domain_retrieve 内 agg 空 → 返回空（或走 semantic_fallback）
    # Ω=0 ⟺ 无触发词。是否存在「无触发词但 agg 非空」？不可能（候选来自触发词）。
    # 但反向：有触发词且 agg 空（通道 2）→ 现有代码也会走回退，而 Ω>0 会放行。
    agg_empty = [1 if not r["cascade_nonempty_p"] else 0 for r in rows]
    omega_zero = [1 if r["omega_p"] == 0.0 else 0 for r in rows]
    agree = sum(1 for a, b in zip(agg_empty, omega_zero) if a == b)
    print(f"  `agg 空` 与 `Ω=0` 的一致率 = {agree}/{n} = {agree / n:.4f}")
    print(f"  不一致的 {n - agree} 条全部是：Ω>0 但 agg 空（通道 2）"
          f"——现有回退判据能拦住它们，Ω 门控拦不住")
    print(f"  → Ω 门控在**工程动作上严格弱于**现有 `if not agg` 判据："
          f"现有判据是「通路真为空」，Ω 是「通路可能为空」的代理")
    # 若把 Ω 当回退触发器：回退调用次数
    print(f"\n  回退触发次数：现有判据 {sum(agg_empty)} 次；"
          f"Ω 门控 {sum(omega_zero)} 次（少 {sum(agg_empty) - sum(omega_zero)} 次，"
          f"即漏掉通道 2）")
    # 通道 2 有多少能被回退救回？
    fallback_ok = 0
    for r in rows:
        if r["omega_p"] > 0 and not r["cascade_nonempty_p"]:
            d = docs[r["doc_id"]]
            fb = d["eng"].cross_domain_retrieve(
                r["paraphrase"], semantic_fallback=True).chunk_ids
            if fb:
                fallback_ok += 1
    print(f"  通道 2 中语义回退能给出非空结果的：{fallback_ok}/{sum(agg_empty) - sum(omega_zero)}"
          f"（回退确实能救，但救的是 Ω 看不见的那部分）")

    # ============================================================ C: 触发词身份
    print("\n" + "-" * 92)
    print("【C】改写型里 Ω>0 靠的是什么触发词？（意外命中的身份）")
    print("-" * 92)
    pos = [r for r in rows if r["omega_p"] > 0]
    tc = Counter(t for r in pos for t in r["trig_p"])
    print(f"  Ω>0 的改写查询 {len(pos)} 条，共命中 {sum(tc.values())} 次触发词，"
          f"去重 {len(tc)} 个")
    print("  最高频触发词（含该词命中后级联通路的成功率）：")
    for t, c in tc.most_common(15):
        grp = [r for r in pos if t in r["trig_p"]]
        hit = sum(1 for r in grp if r["cascade_hit_p"])
        print(f"    {t:8s} 命中 {c:>3d} 条  该词命中后通路成功 {hit:>3d} "
              f"= {hit / len(grp):.3f}")
    # 单触发词查询 vs 多触发词
    print(f"\n  Ω>0 中 n_seed=1 的 {sum(1 for r in pos if r['n_seed_p'] == 1)} 条，"
          f"n_seed≥2 的 {sum(1 for r in pos if r['n_seed_p'] >= 2)} 条")
    for k in (1, 2):
        g = [r for r in pos if r["n_seed_p"] >= k and r["n_seed_p"] < k + 1]
        if g:
            print(f"    n_seed={k}: 通路成功率 "
                  f"{sum(1 for r in g if r['cascade_hit_p']) / len(g):.4f} (n={len(g)})")

    # ============================================================ D: 天花板
    print("\n" + "-" * 92)
    print("【D】查询侧泛函的天花板：通路是查询的确定性函数")
    print("-" * 92)
    print("  cross_domain_retrieve 的 agg 是 (query, graph, ontology) 的确定性函数；")
    print("  因此任何**也读图**的查询侧泛函，对「通路是否非空」的预测上限 = 1.000")
    print(f"  （Ω_G 实测：AUC(通路非空) = "
          f"{S.auc([og[i] for i in range(n) if nonempty[i]], [og[i] for i in range(n) if not nonempty[i]]):.4f}）")
    print("  而「通路命中金标」不可由查询侧决定（依赖金标本身）：")
    print(f"  Ω_G 的 AUC(通路命中) = "
          f"{S.auc([og[i] for i in range(n) if succ[i]], [og[i] for i in range(n) if not succ[i]]):.4f}"
          f" —— 已接近上限但仍受通道 3（覆盖后未命中）拖累")
    print("  → 结论：Ω 在**不读图**的设计约束下，只能通过「有无触发词」这一"
          "单一通道起作用；把图可达性加进来（Ω_G）才能解释通道 2，"
          "但通道 3 需要候选侧信号，超出「纯查询侧」设计能覆盖的范围")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(channels=dict(ch), n=n,
                       rows=[{k: r[k] for k in
                              ("doc_id", "omega_p", "omega_g_p", "n_seed_p",
                               "n_reach_p", "cascade_nonempty_p",
                               "cascade_hit_p", "cascade_recall_p",
                               "trig_p", "paraphrase")} for r in rows]),
                  f, ensure_ascii=False)
    print(f"\n明细已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
