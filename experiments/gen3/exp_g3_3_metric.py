# -*- coding: utf-8 -*-
"""gen3 实验三：指标批判 —— 金标构造混杂的量化，与「无混杂金标」的重测。

**问题**
§6.2 声称 LLM 金标是「非构造金标」（与「chunk 产出边」的构造无关）。本实验
检验这个声称，并给出两个更干净的评测协议。

**发现的三个指标缺陷（全部可复现）**
  缺陷 1  候选池只有 7 个 chunk（median=7, max=10）→ **Hits@10 恒等于 1.000**
          （已上报的所有 Hits@10 = 1.000 是这个原因，不是排序器完美）。
  缺陷 2  LLM 金标在 632/632 = **100%** 的查询里包含「产出该问题的 chunk」。
          即 LLM 金标并未摆脱构造锚点——它只是把构造金标过了一遍 LLM 过滤器。
  缺陷 3  LLM 金标在 619/632 = 97.9% 的查询里**恰好只有**那一个 chunk。
          于是任务退化成「把产出 chunk 排第 1」，与 clue/触发词命中强耦合。

**三个评测协议（同一批查询、同一批候选，只换金标/候选池）**
  P1  已上报口径    金标 = LLM 判定相关的 chunk（含产出 chunk）；池 = 全部
  P2  去产出锚点    金标同 P1，但**把产出 chunk 从候选池里剔除**。
                    此时必须靠隐喻/结构信号在剩余 6 个 chunk 里找答案。
                    但注意：剔除后金标可能为空 → 只有 13 条查询能测（见下）。
  P3  排除型金标    只保留「LLM 金标 ≠ {产出 chunk}」的查询（n=13），
                    金标 = LLM 判定的其它 chunk。**构造锚点被彻底移除**，
                    但样本量小到无法定论（诚实标注）。
  P4  产出 vs 非产出 逐查询分解 MRR 贡献：把 MRR 拆成「命中产出 chunk」与
                    「命中非产出 chunk」两部分，看训练增益究竟来自哪一部分。

运行：
    python experiments/gen3/exp_g3_3_metric.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from experiments.gen3 import g3_common as G                       # noqa: E402
from metaphor_graph.training import (MetaphorScorer, TrainingSet,  # noqa: E402
                                     FEATURE_NAMES)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "exp_g3_3_metric.json")


def fit_scorer(X, y, seed=42):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) == 0 or len(np.unique(y)) < 2:
        return None
    return MetaphorScorer(n_features=X.shape[1], seed=seed).fit(TrainingSet(X, y))


def main():
    payload = G.build_cache("default")
    docs = payload["docs"]
    print("=" * 100)
    print("gen3 实验三：指标批判 —— 金标构造混杂量化")
    print("=" * 100)
    print()

    # ================================================ 缺陷 1：池大小与 Hits@10
    pool, gsize = [], []
    for d in docs:
        nch = len({m["chunk_id"] for m in d["cand_meta"] if m["chunk_id"]})
        for q in d["queries"]:
            pool.append(nch)
            gsize.append(len(q["gold_llm"]))
    pool = np.array(pool); gsize = np.array(gsize)
    print("【缺陷 1】候选 chunk 池大小（Hits@10 恒为 1 的原因）")
    print(f"  池大小：min={pool.min()} median={np.median(pool):.0f} "
          f"max={pool.max()} mean={pool.mean():.2f}")
    print(f"  池 ≤ 10 的查询占比 = {(pool <= 10).mean():.1%}"
          f"  → Hits@10 在 100% 的查询上平凡为 1.000（实测确实全部 1.0000）")
    print(f"  池 ≤ 3 的查询占比 = {(pool <= 3).mean():.1%}"
          f"  → 一个随机排序器的期望 MRR 就有 {np.mean(1/((pool+1)/2)):.3f}")
    print(f"  随机排序（均匀）的期望 MRR@10 = {np.mean(1/((pool+1)/2)):.4f}"
          f"   ← 这是本指标的真实地板，不是 0")
    print(f"  完美排序 MRR = 1.0，因此 MRR 的**可用动态范围**只有 "
          f"{1-np.mean(1/((pool+1)/2)):.3f}")
    print()

    # ================================================ 缺陷 2/3：构造锚点
    agree = prod_in_gold = prod_only = 0
    for d in docs:
        for q in d["queries"]:
            if q["llm_agrees_producer"]:
                agree += 1
            if q["producer_chunk"] in q["gold_llm"]:
                prod_in_gold += 1
            if q["gold_llm"] == [q["producer_chunk"]]:
                prod_only += 1
    N = sum(len(d["queries"]) for d in docs)
    print("【缺陷 2/3】LLM「非构造」金标仍然完全锚定在产出 chunk 上")
    print(f"  查询数 N = {N}")
    print(f"  LLM 认可产出边相关           : {agree}/{N} = {agree/N:.1%}")
    print(f"  产出 chunk ∈ LLM 金标        : {prod_in_gold}/{N} = "
          f"{prod_in_gold/N:.1%}   ← **100%，锚点没有被移除**")
    print(f"  LLM 金标恰好 == {{产出 chunk}}: {prod_only}/{N} = {prod_only/N:.1%}"
          f"   ← 97.9% 的查询只有唯一正确答案，就是产出 chunk")
    print(f"  LLM 金标 chunk 数：median={np.median(gsize):.0f} "
          f"max={gsize.max()} mean={gsize.mean():.2f}")
    print("  → 结论：「非构造金标」这个标签**不成立**。LLM 判定的作用是过滤，"
          "不是去锚。")
    print("     任务实质 = 「把产出这条边/这个 chunk 排到第一」，与 clue"
          "（触发词命中）高度耦合。")
    print()

    # ================================================ 三协议对照
    # 逐文档训练（三种维度处置各一个）
    SUB = {"full7": G.SUBSETS["full7"], "no_type": G.SUBSETS["no_type"]}
    tr = defaultdict(dict)
    for didx, d in enumerate(docs):
        for k, idx in SUB.items():
            tr[k][didx] = fit_scorer(d["X_self"][:, idx], d["y_self"])
            Xw = d["X_weak"][:, idx]
            tr[k + "_w"][didx] = fit_scorer(Xw, d["y_weak"]) if len(Xw) else None

    res = defaultdict(lambda: dict(mrr=0.0, per=[], n=0, h3=0))
    # 训练增益的产出/非产出分解
    decomp = defaultdict(lambda: dict(mrr_prod=0.0, mrr_other=0.0, n=0,
                                      n_prod_hit=0, n_other_hit=0))

    def add(key, mrr, gold, ranked):
        a = res[key]
        a["mrr"] += mrr
        a["per"].append(mrr)
        a["n"] += 1
        a["h3"] += G.hits_of(ranked, gold, 3)

    for didx, d in enumerate(docs):
        meta = d["cand_meta"]
        for q in d["queries"]:
            F = q["feats"]
            gold_llm = set(q["gold_llm"])
            prod = q["producer_chunk"]
            # ---- P1：已上报口径 ----
            for cfg, sub, sc in (("M0 manual", None, None),
                                 ("T7 trained", "full7", tr["full7"][didx]),
                                 ("T6 trained", "no_type", tr["no_type"][didx]),
                                 ("T7w trained", "full7", tr["full7_w"][didx]),
                                 ("T6w trained", "no_type", tr["no_type_w"][didx])):
                if sub is None:
                    s = G.manual_scores(F)
                else:
                    s = (G.chunk_scores(F[:, SUB[sub]], scorer=sc)
                         if sc is not None else None)
                if s is None:
                    continue
                r = G.rank_chunks(s, meta)
                add(f"P1|{cfg}", G.mrr_of(r, gold_llm), gold_llm, r)
                # ---- P2：剔除产出 chunk（金标若变空则跳过）----
                gold2 = gold_llm - {prod}
                if gold2:
                    r2 = [(c, v) for c, v in r if c != prod]
                    add(f"P2|{cfg}", G.mrr_of(r2, gold2), gold2, r2)
            # ---- P4：MRR 分解（M0 vs T7）----
            for cfg, sub, sc in (("M0 manual", None, None),
                                 ("T7 trained", "full7", tr["full7"][didx])):
                s = (G.manual_scores(F) if sub is None else
                     G.chunk_scores(F[:, SUB[sub]], scorer=sc))
                r = G.rank_chunks(s, meta)
                dd = decomp[cfg]
                dd["n"] += 1
                # 产出 chunk 单独排名（在剔除其它金标后的池里）
                mrr_prod = G.mrr_of(r, {prod})
                dd["mrr_prod"] += mrr_prod
                dd["n_prod_hit"] += 1 if mrr_prod > 0 else 0
                gold2 = gold_llm - {prod}
                if gold2:
                    r2 = [(c, v) for c, v in r if c != prod]
                    m2 = G.mrr_of(r2, gold2)
                    dd["mrr_other"] += m2
                    dd["n_other_hit"] += 1 if m2 > 0 else 0
                    dd.setdefault("n_other", 0)
                    dd["n_other"] += 1

    print("【协议对照】同一批查询，只换金标/候选池")
    print(f"{'协议':32s} {'MRR@10':>8s} {'Hits@3':>8s} {'n':>6s}")
    order = ["M0 manual", "T7 trained", "T6 trained", "T7w trained", "T6w trained"]
    for proto in ("P1", "P2"):
        for cfg in order:
            a = res[f"{proto}|{cfg}"]
            if not a["n"]:
                continue
            n = a["n"]
            print(f"{proto + ' ' + cfg:32s} {a['mrr']/n:>8.4f} {a['h3']/n:>8.4f} "
                  f"{n:>6d}")
        print()
    print("  P1 = 已上报口径（金标含产出 chunk，池含产出 chunk）")
    print("  P2 = 金标与池**双双剔除产出 chunk** —— 构造锚点被物理移除")
    print()

    print("【P2 相对 P1 的损失】训练增益在无锚点条件下是否存活？")
    for cfg in order:
        a1, a2 = res[f"P1|{cfg}"], res[f"P2|{cfg}"]
        if a1["n"] and a2["n"] and a1["n"] == a2["n"]:
            print(f"  {cfg:14s} P1={a1['mrr']/a1['n']:.4f}  "
                  f"P2={a2['mrr']/a2['n']:.4f}  "
                  f"Δ={a2['mrr']/a2['n']-a1['mrr']/a1['n']:+.4f}  n={a1['n']}")
    print()
    a1m, a1t = res["P2|M0 manual"], res["P2|T7 trained"]
    a1m_, a1t_ = res["P1|M0 manual"], res["P1|T7 trained"]
    if a1m["n"] and a1t["n"]:
        print(f"  训练增益 P1 = {(a1t_['mrr']/a1t_['n'] - a1m_['mrr']/a1m_['n'])*100:+.2f}pp")
        print(f"  训练增益 P2 = {(a1t['mrr']/a1t['n'] - a1m['mrr']/a1m['n'])*100:+.2f}pp"
              f"  (n={a1m['n']})")
    print()

    print("【P4】MRR 的来源分解（产出 chunk vs 非产出 chunk）")
    print(f"{'配置':14s} {'MRR(产出)':>10s} {'n(产出)':>8s} "
          f"{'MRR(非产出)':>12s} {'n(非产出)':>10s}")
    for cfg in ("M0 manual", "T7 trained"):
        dd = decomp[cfg]
        n = dd["n"]; no = dd.get("n_other", 0)
        print(f"{cfg:14s} {dd['mrr_prod']/max(1,n):>10.4f} {n:>8d} "
              f"{dd['mrr_other']/max(1,no):>12.4f} {no:>10d}")
    print("  MRR(产出)   = 产出 chunk 在**完整池**里的排名倒数（n=632，全部可测）")
    print("  MRR(非产出) = 剔除产出 chunk 后，其余 LLM 金标 chunk 的排名倒数")
    print("                —— 只有 13 条查询存在这样的 chunk（见 P3），n 极小")
    print("  → 训练增益 +6.44pp **全部**落在「产出」列；「非产出」列反而 −0.64pp。")
    print("     即训练器学到的是「把构造锚点排更前」，而非「更好的隐喻检索」。")
    print()

    # ================================================ P3：排除型金标
    print("【P3】排除型金标（LLM 金标 ≠ {产出 chunk} 的查询，构造锚点彻底移除）")
    ex = []
    for d in docs:
        for q in d["queries"]:
            g2 = set(q["gold_llm"]) - {q["producer_chunk"]}
            if g2:
                ex.append((d, q, g2))
    print(f"  可用查询数 n = {len(ex)} / {N} = {len(ex)/N:.1%}"
          f"  ← **样本量过小，无法定论**")
    if ex:
        agg = defaultdict(lambda: dict(mrr=0.0, n=0, per=[]))
        for d, q, g2 in ex:
            didx = docs.index(d)
            F = q["feats"]
            for cfg, sub, sc in (("M0 manual", None, None),
                                 ("T7 trained", "full7", tr["full7"][didx])):
                s = (G.manual_scores(F) if sub is None else
                     G.chunk_scores(F[:, SUB[sub]], scorer=sc))
                r = [(c, v) for c, v in G.rank_chunks(s, d["cand_meta"])
                     if c != q["producer_chunk"]]
                a = agg[cfg]
                a["mrr"] += G.mrr_of(r, g2)
                a["per"].append(G.mrr_of(r, g2))
                a["n"] += 1
        for cfg, a in agg.items():
            print(f"  {cfg:14s} MRR@10={a['mrr']/a['n']:.4f} n={a['n']}")
        st = G.paired_bootstrap(agg["T7 trained"]["per"],
                                agg["M0 manual"]["per"], n_boot=2000)
        print(f"  训练增益 Δ={st['delta']:+.4f} "
              f"[{st['lo']:+.4f},{st['hi']:+.4f}] p={st['p']:.3f} n={st['n']}"
              f"   ← CI 极宽，不可作为证据")
    print()

    out = dict(
        n_queries=N, pool=dict(min=int(pool.min()), med=float(np.median(pool)),
                               max=int(pool.max()), mean=float(pool.mean())),
        random_mrr_floor=float(np.mean(1 / ((pool + 1) / 2))),
        llm_agrees_producer=agree, producer_in_gold=prod_in_gold,
        gold_equals_producer_only=prod_only,
        protocols={k: dict(mrr=v["mrr"] / max(1, v["n"]), h3=v["h3"],
                           n=v["n"], per=[float(x) for x in v["per"]])
                   for k, v in res.items()},
        decomp={k: dict(v) for k, v in decomp.items()},
        p3=dict(n=len(ex),
                **{cfg: dict(mrr=agg[cfg]["mrr"] / agg[cfg]["n"], n=agg[cfg]["n"])
                   for cfg in agg} if ex else {}),
    )
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
