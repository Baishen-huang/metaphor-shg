# -*- coding: utf-8 -*-
"""gen3 实验四：零假设对照 —— 训练增益到底是不是「学会复读 clue」？

**动机**
实验三证明：632 条查询里 619 条（97.9%）的 LLM 金标**恰好只有产出那一个
chunk**，且候选池只有 7 个 chunk。在这种任务上，「把产出 chunk 排第一」
的最优策略可能根本不需要 7 维特征——只要复读 clue（触发词命中）或 sem。

本实验用**单信号基线**做零假设对照：
  N1  纯 clue            s = f[2]（触发词命中）
  N2  纯 sem             s = f[0]
  N3  纯 ground_jaccard  s = f[6]
  N4  clue + sem         s = f[2] + f[0]
  N5  ORACLE 产出标志     s = 1 若候选 chunk == 产出 chunk（上界）
  N6  随机排序           s = 随机（20 个种子平均）
  N7  训练后排序器（7 维，基线）
  N8  训练后排序器（只用 sem+clue 两维重训）

若 N1（纯 clue）已接近 N7，则「训练增益」的实质是「训练器学会给 clue 高权重」，
与隐喻结构特征无关 —— 这正是 gen1 已经指出的 clue AUC≈1.0 天花板的后果。

同时给出**特征消融的边际贡献**：从 7 维中逐个去掉一维重训，看 MRR 变化，
得到每一维对最终指标的边际贡献（而非只看权重绝对值）。

运行：
    python experiments/gen3/exp_g3_4_null.py
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
                   "exp_g3_4_null.json")


def fit_scorer(X, y, seed=42):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) == 0 or len(np.unique(y)) < 2:
        return None
    return MetaphorScorer(n_features=X.shape[1], seed=seed).fit(TrainingSet(X, y))


# 单信号基线：名字 → (特征列索引 或 None, 说明)
SINGLE = {
    "N1 clue only":        [G.IDX["clue"]],
    "N2 sem only":         [G.IDX["sem"]],
    "N3 ground only":      [G.IDX["ground_jaccard"]],
    "N4 clue+sem":         [G.IDX["clue"], G.IDX["sem"]],
    "N9 struct only":      [G.IDX["struct"]],
    "N10 type only":       [G.IDX["type"]],
    "N11 same_frame only": [G.IDX["same_frame"]],
    "N12 same_casc only":  [G.IDX["same_cascade"]],
    "N13 clue+sem+ground": [G.IDX["clue"], G.IDX["sem"], G.IDX["ground_jaccard"]],
}

# 逐维边际消融：留 6 维（去掉该维）重训
LEAVE_ONE_OUT = {f"L1 drop_{n}": [j for j, m in enumerate(FEATURE_NAMES) if m != n]
                 for n in FEATURE_NAMES}


def main():
    payload = G.build_cache("default")
    docs = payload["docs"]
    N = sum(len(d["queries"]) for d in docs)
    print("=" * 100)
    print("gen3 实验四：零假设对照与逐维边际贡献")
    print("=" * 100)
    print(f"{len(docs)} 伪文档 ｜ {N} 条查询 ｜ LLM 非构造金标")
    print()

    res = defaultdict(lambda: dict(mrr=0.0, per=[], n=0, h3=0))

    def add(key, mrr, h3):
        a = res[key]
        a["mrr"] += mrr
        a["per"].append(mrr)
        a["h3"] += h3
        a["n"] += 1

    # ---- 单信号：直接取特征值当分数（无训练）----
    # ---- 留一消融：重训 ----
    tr = defaultdict(dict)
    for didx, d in enumerate(docs):
        for name, cols in LEAVE_ONE_OUT.items():
            tr[name][didx] = fit_scorer(d["X_self"][:, cols], d["y_self"])
            Xw = d["X_weak"][:, cols]
            tr[name + "_w"][didx] = fit_scorer(Xw, d["y_weak"]) if len(Xw) else None
        tr["N8 sem+clue"][didx] = fit_scorer(
            d["X_self"][:, SINGLE["N4 clue+sem"]], d["y_self"])
        tr["N7 full7"][didx] = fit_scorer(d["X_self"], d["y_self"])

    rng = np.random.default_rng(5)
    for didx, d in enumerate(docs):
        meta = d["cand_meta"]
        for q in d["queries"]:
            F = q["feats"]
            gold = q["gold_llm"]
            # 单信号
            for name, cols in SINGLE.items():
                s = F[:, cols].mean(axis=1)
                r = G.rank_chunks(s, meta)
                add(name, G.mrr_of(r, gold), G.hits_of(r, gold, 3))
            # oracle：产出 chunk 直接置顶
            s = np.array([1.0 if m["chunk_id"] == q["producer_chunk"] else 0.0
                          for m in meta])
            r = G.rank_chunks(s, meta)
            add("N5 ORACLE producer", G.mrr_of(r, gold), G.hits_of(r, gold, 3))
            # 随机（20 个种子平均，同一查询内平均）
            mrrs = []
            for _ in range(20):
                s = rng.random(len(meta))
                r = G.rank_chunks(s, meta)
                mrrs.append(G.mrr_of(r, gold))
            add("N6 random", float(np.mean(mrrs)), 0.0)
            # 训练后
            for name, cols in (("N7 full7", None),
                               ("N8 sem+clue", SINGLE["N4 clue+sem"])):
                sc = tr[name][didx]
                if sc is None:
                    continue
                Fi = F if cols is None else F[:, cols]
                r = G.rank_chunks(G.chunk_scores(Fi, scorer=sc), meta)
                add(name, G.mrr_of(r, gold), G.hits_of(r, gold, 3))
            for name in LEAVE_ONE_OUT:
                sc = tr[name][didx]
                if sc is None:
                    continue
                r = G.rank_chunks(
                    G.chunk_scores(F[:, LEAVE_ONE_OUT[name]], scorer=sc), meta)
                add(name, G.mrr_of(r, gold), G.hits_of(r, gold, 3))
                scw = tr[name + "_w"][didx]
                if scw is not None:
                    r = G.rank_chunks(
                        G.chunk_scores(F[:, LEAVE_ONE_OUT[name]], scorer=scw),
                        meta)
                    add(name + " (weak)", G.mrr_of(r, gold),
                        G.hits_of(r, gold, 3))

    print("【表 A】单信号基线 vs 训练后（无训练，直接取特征值）")
    print(f"{'配置':22s} {'MRR@10':>8s} {'Hits@3':>8s} {'n':>5s}")
    keys = list(SINGLE) + ["N5 ORACLE producer", "N6 random",
                           "N7 full7", "N8 sem+clue"]
    for name in keys:
        a = res[name]
        if not a["n"]:
            continue
        n = a["n"]
        print(f"{name:22s} {a['mrr']/n:>8.4f} {a['h3']/n:>8.4f} {n:>5d}")
    print()

    base = res["N7 full7"]["per"]
    print("【表 B】与训练后 7 维的配对 bootstrap 对照（LLM 金标）")
    print(f"{'配置':22s} {'Δ MRR@10':>10s} {'95% CI':>22s} {'p':>7s}")
    null_rows = []
    for name in keys:
        if name == "N7 full7" or not res[name]["n"]:
            continue
        a = np.asarray(res[name]["per"])
        b = np.asarray(base)
        if len(a) != len(b):
            continue
        st = G.paired_bootstrap(a, b, n_boot=2000)
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"{name:22s} {st['delta']:>+10.4f} "
              f"[{st['lo']:>+8.4f},{st['hi']:>+8.4f}] {st['p']:>6.3f} {star}")
        null_rows.append(dict(name=name, **st))
    print()

    print("【表 C】逐维边际贡献（留一消融，重训 6 维）")
    print(f"{'去掉的维':22s} {'MRR@10(自)':>11s} {'Δ vs 全 7 维':>13s} "
          f"{'MRR@10(弱)':>11s} {'Δ vs 全 7 维':>13s}")
    base_mrr = res["N7 full7"]["mrr"] / res["N7 full7"]["n"]
    loo_rows = []
    for name in FEATURE_NAMES:
        key = f"L1 drop_{name}"
        a = res[key]
        aw = res[key + " (weak)"]
        m = a["mrr"] / max(1, a["n"])
        mw = aw["mrr"] / max(1, aw["n"])
        print(f"{name:22s} {m:>11.4f} {m-m:>13s}" if False else
              f"{name:22s} {m:>11.4f} {m-base_mrr:>+13.4f} "
              f"{mw:>11.4f} {mw-base_mrr:>+13.4f}")
        loo_rows.append(dict(name=name, mrr=m, delta=m - base_mrr,
                             mrr_weak=mw, delta_weak=mw - base_mrr))
    print(f"{'（基线：全 7 维）':22s} {base_mrr:>11.4f}")
    print()
    print("  读法：Δ 为正 = 去掉该维反而更好（该维在训练侧是负担）；")
    print("        Δ 为负 = 该维有正贡献。全部逐维 Δ 都要与配对 CI 一起读。")
    print()

    # 留一消融的配对 CI
    print("【表 D】留一消融的配对 bootstrap 95% CI（vs 全 7 维，自监督）")
    ci_rows = []
    for name in FEATURE_NAMES:
        key = f"L1 drop_{name}"
        a = np.asarray(res[key]["per"]); b = np.asarray(base)
        if len(a) != len(b):
            continue
        st = G.paired_bootstrap(a, b, n_boot=2000)
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"  drop {name:18s} Δ={st['delta']:+.4f} "
              f"[{st['lo']:+.4f},{st['hi']:+.4f}] p={st['p']:.3f} {star} "
              f"(+{st['n_pos']}/−{st['n_neg']}/={st['n_tie']})")
        ci_rows.append(dict(name=name, **st))
    print()

    out = dict(
        n_queries=N,
        single={k: dict(mrr=v["mrr"] / max(1, v["n"]), h3=v["h3"],
                        n=v["n"], per=[float(x) for x in v["per"]])
                for k, v in res.items()},
        null_vs_full7=null_rows, leave_one_out=loo_rows, loo_ci=ci_rows)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
