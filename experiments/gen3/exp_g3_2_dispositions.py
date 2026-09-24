# -*- coding: utf-8 -*-
"""gen3 实验二：处置实验（去维 / 换权 / 换信号），before/after 指标表。

处置清单（全部在同一份缓存上，纯 numpy，可逐位复算）：
  D0  基线            7 维，人工 0.35/0.25/0.20/0.20（已上报口径）
  D1  去 type         6 维（sem/struct/clue/same_frame/same_cascade/ground_jaccard）
  D2  去 same_cascade 6 维
  D3  去 type+cascade 5 维
  D8  换 type→frame_support_norm   本体框架支撑度（对数归一）
  D9  换 type→frame_tier_core      框架层级 core/longtail
  D10 换 type→cascade_size_norm    所属级联成员框架数（对数归一）
  D11 换 type→n_emergent           级联能触达的**新**目标/源域数
  D12 换 type→frame_registered     框架是否注册（≈type 的二值版，对照）
  D13 换 type→ground_len_norm      喻底规模（struct 已含，作对照）

人工权重重配（只动权重，不动维度）：
  M0 0.35/0.25/0.20/0.20（基线）
  M1 0.35/0.25/0.40/0.00（去 type，权重给 clue）
  M2 0.35/0.25/0.35/0.05（type 降到 0.05）
  M3 按学到的权重比例（正部归一）
  M4 7 维按学到的权重比例（含角色三维）
  M5 7 维手工调（0.30/0.20/0.15/0.05/0.05/0.05/0.20）
  M6 3 维等权（1/3 各）
  M7 4 维等权（1/4 各）

三种打分路径：人工加权 / 自监督训练 / 弱监督训练。
两套金标：llm（**首选**，与 chunk 产出边的构造无关）/ constr（by-construction，对照）。
统计：配对 bootstrap 95% CI（对查询重采样，2000 次）。

运行：
    python experiments/gen3/exp_g3_2_dispositions.py
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
                   "exp_g3_2_dispositions.json")

DISPOSITIONS = {
    "D0 baseline7":         ("full7", None),
    "D1 drop_type":         ("no_type", None),
    "D2 drop_same_cascade": ("no_cascade", None),
    "D3 drop_type+cascade": ("no_type_no_casc", None),
    "D8 repl type<-frame_support_norm": ("no_type", "frame_support_norm"),
    "D9 repl type<-frame_tier_core":    ("no_type", "frame_tier_core"),
    "D10 repl type<-cascade_size_norm": ("no_type", "cascade_size_norm"),
    "D11 repl type<-n_emergent":        ("no_type", "n_emergent"),
    "D12 repl type<-frame_registered":  ("no_type", "frame_registered"),
    "D13 repl type<-ground_len_norm":   ("no_type", "ground_len_norm"),
}

# 人工权重配置：名字 → (权重字典, 顺序累加的标志)
MANUAL = {
    "M0 4d .35/.25/.20/.20": dict(sem=0.35, struct=0.25, clue=0.20, type=0.20),
    "M1 3d .35/.25/.40": dict(sem=0.35, struct=0.25, clue=0.40),
    "M2 4d .35/.25/.35/.05": dict(sem=0.35, struct=0.25, clue=0.35, type=0.05),
    "M6 3d 1/3 each": dict(sem=1 / 3, struct=1 / 3, clue=1 / 3),
    "M7 4d 1/4 each": dict(sem=0.25, struct=0.25, clue=0.25, type=0.25),
}


def fit_scorer(X, y, seed=42):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) == 0 or len(np.unique(y)) < 2:
        return None
    # n_features 必须显式传：处置后的维数可能不是 7（去维/换列）
    return MetaphorScorer(n_features=X.shape[1], seed=seed).fit(
        TrainingSet(X, y))


def main():
    payload = G.build_cache("default")
    docs = payload["docs"]
    N = sum(len(d["queries"]) for d in docs)
    SIG_KEYS = docs[0]["sig_keys"]
    SIG_COL = {k: i for i, k in enumerate(SIG_KEYS)}

    print("=" * 108)
    print("gen3 实验二：处置实验（去维 / 换权 / 换信号）")
    print("=" * 108)
    print(f"{len(docs)} 伪文档 ｜ {N} 条查询 ｜ 两套金标 ｜ 配对 bootstrap 2000")
    print()

    # ---- 学到的权重均值（用于 M3/M4 的人工重配）----
    learned = defaultdict(list)
    for d in docs:
        sc = fit_scorer(d["X_self"], d["y_self"])
        if sc is None:
            continue
        for n, v in sc.weights().items():
            learned[n].append(v)
    lw = {n: float(np.mean(v)) for n, v in learned.items()}
    pos = {n: max(0.0, lw[n]) for n in FEATURE_NAMES}
    tot = sum(pos.values())
    share4 = {n: pos[n] / sum(pos[k] for k in ("sem", "struct", "clue", "type"))
              for n in ("sem", "struct", "clue", "type")}
    MANUAL["M3 4d learned-share"] = share4
    MANUAL["M4 7d learned-share"] = {n: pos[n] / tot for n in FEATURE_NAMES}
    MANUAL["M5 7d hand .30/.20/.15/.05/.05/.05/.20"] = dict(
        sem=0.30, struct=0.20, clue=0.15, type=0.05,
        same_frame=0.05, same_cascade=0.05, ground_jaccard=0.20)

    print("学到的权重均值（标准化空间）:",
          {n: round(lw[n], 4) for n in FEATURE_NAMES})
    print("→ M3 四维按学到比例:",
          {n: round(share4[n], 4) for n in ("sem", "struct", "clue", "type")})
    print("→ M4 七维按学到比例:",
          {n: round(pos[n] / tot, 4) for n in FEATURE_NAMES})
    print()

    results = defaultdict(lambda: dict(mrr=0.0, h3=0, h10=0, per=[], n=0))
    train_cache = defaultdict(dict)

    def add(disp, cfg, gold, mrr, h3, h10):
        a = results[(disp, cfg, gold)]
        a["mrr"] += mrr
        a["h3"] += h3
        a["h10"] += h10
        a["per"].append(mrr)
        a["n"] += 1

    # ------------------------------------------------------- 逐文档训练（一次）
    for didx, d in enumerate(docs):
        S = d["S_self"]
        Sw = d["S_weak"]
        for disp, (subname, repl) in DISPOSITIONS.items():
            idx = G.SUBSETS[subname]
            Xs = d["X_self"][:, idx]
            if repl is not None:
                Xs = np.hstack([Xs, S[:, [SIG_COL[repl]]]])
            train_cache[(disp, "self")][didx] = fit_scorer(Xs, d["y_self"])
            Xw = d["X_weak"][:, idx]
            if repl is not None and len(Xw):
                Xw = np.hstack([Xw, Sw[:, [SIG_COL[repl]]]])
            train_cache[(disp, "weak")][didx] = (fit_scorer(Xw, d["y_weak"])
                                                 if len(Xw) else None)

    # ------------------------------------------------------- 评测
    for didx, d in enumerate(docs):
        meta = d["cand_meta"]
        S_cand = np.asarray([[m[k] for k in SIG_KEYS] for m in meta], dtype=float)
        for q in d["queries"]:
            F = q["feats"]
            for disp, (subname, repl) in DISPOSITIONS.items():
                idx = G.SUBSETS[subname]
                Fi = (np.hstack([F[:, idx], S_cand[:, [SIG_COL[repl]]]])
                      if repl is not None else F[:, idx])
                for src, cfgname in (("self", "trained_self"),
                                     ("weak", "trained_weak")):
                    sc = train_cache[(disp, src)].get(didx)
                    if sc is None:
                        continue
                    r = G.rank_chunks(G.chunk_scores(Fi, scorer=sc), meta)
                    for gold in ("llm", "constr"):
                        g = q["gold_llm"] if gold == "llm" else q["gold_constr"]
                        add(disp, cfgname, gold, G.mrr_of(r, g),
                            G.hits_of(r, g, 3), G.hits_of(r, g, 10))
            # ---- 人工加权 ----
            for mname, w in MANUAL.items():
                s = np.empty(len(F))
                for i in range(len(F)):
                    acc = 0.0
                    for n, wv in w.items():
                        v = F[i, G.IDX[n]]
                        if n == "struct":
                            v = min(v, 1.0)
                        acc += wv * v
                    s[i] = acc
                r = G.rank_chunks(s, meta)
                for gold in ("llm", "constr"):
                    g = q["gold_llm"] if gold == "llm" else q["gold_constr"]
                    add(mname, "manual", gold, G.mrr_of(r, g),
                        G.hits_of(r, g, 3), G.hits_of(r, g, 10))

    # ------------------------------------------------------- 打印
    def show(gold, title, note=""):
        print("=" * 108)
        print(title)
        if note:
            print(note)
        print("=" * 108)
        print(f"{'处置':36s} {'配置':14s} {'MRR@10':>8s} {'Hits@3':>8s} "
              f"{'Hits@10':>8s} {'n':>5s}")
        keys = [k for k in results if k[2] == gold]
        keys.sort(key=lambda k: (k[0], k[1]))
        for disp, cfg, a in [(k[0], k[1], results[k]) for k in keys]:
            if not a["n"]:
                continue
            n = a["n"]
            print(f"{disp:36s} {cfg:14s} {a['mrr']/n:>8.4f} {a['h3']/n:>8.4f} "
                  f"{a['h10']/n:>8.4f} {n:>5d}")
        print()

    show("llm", "【表 A】LLM 非构造金标（**首选**：金标来自 LLM 独立判定，"
                "与「chunk 产出边」的构造无关）")
    show("constr", "【表 B】by-construction 金标（对照：与自监督训练同源，"
                   "存在构造混杂，不应作为结论依据）")

    # ------------------------------------------------------- 配对显著性
    print("=" * 108)
    print("【表 C】关键对照的配对 bootstrap 95% CI（LLM 金标，配对到查询）")
    print("=" * 108)

    def get(disp, cfg, gold="llm"):
        return np.asarray(results[(disp, cfg, gold)]["per"], dtype=float)

    comparisons = [
        ("D1 drop_type", "trained_self", "D0 baseline7", "trained_self",
         "去 type（重训 6 维）− 基线 7 维"),
        ("D2 drop_same_cascade", "trained_self", "D0 baseline7", "trained_self",
         "去 same_cascade（重训 6 维）− 基线"),
        ("D3 drop_type+cascade", "trained_self", "D0 baseline7", "trained_self",
         "去 type+cascade（重训 5 维）− 基线"),
        ("D8 repl type<-frame_support_norm", "trained_self", "D0 baseline7",
         "trained_self", "换 type→frame_support − 基线"),
        ("D9 repl type<-frame_tier_core", "trained_self", "D0 baseline7",
         "trained_self", "换 type→frame_tier − 基线"),
        ("D10 repl type<-cascade_size_norm", "trained_self", "D0 baseline7",
         "trained_self", "换 type→cascade_size − 基线"),
        ("D11 repl type<-n_emergent", "trained_self", "D0 baseline7",
         "trained_self", "换 type→n_emergent − 基线"),
        ("D12 repl type<-frame_registered", "trained_self", "D0 baseline7",
         "trained_self", "换 type→frame_registered − 基线"),
        ("D13 repl type<-ground_len_norm", "trained_self", "D0 baseline7",
         "trained_self", "换 type→ground_len − 基线"),
        ("M1 3d .35/.25/.40", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工去 type（权重给 clue）− 基线人工"),
        ("M2 4d .35/.25/.35/.05", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工 type 降到 0.05 − 基线人工"),
        ("M3 4d learned-share", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工按学到比例（4 维）− 基线人工"),
        ("M4 7d learned-share", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工按学到比例（7 维）− 基线人工"),
        ("M5 7d hand .30/.20/.15/.05/.05/.05/.20", "manual",
         "M0 4d .35/.25/.20/.20", "manual", "人工 7 维手工调 − 基线人工"),
        ("M6 3d 1/3 each", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工 3 维等权 − 基线人工"),
        ("M7 4d 1/4 each", "manual", "M0 4d .35/.25/.20/.20", "manual",
         "人工 4 维等权 − 基线人工"),
    ]
    ci_rows = []
    for da, ca, db, cb, label in comparisons:
        if (da, ca, "llm") not in results or (db, cb, "llm") not in results:
            print(f"  {label:52s} 跳过（缺结果）")
            continue
        a, b = get(da, ca), get(db, cb)
        if len(a) != len(b) or len(a) == 0:
            print(f"  {label:52s} 跳过（n 不一致）")
            continue
        st = G.paired_bootstrap(a, b, n_boot=2000)
        ci_rows.append(dict(label=label, **st))
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"  {label:52s} Δ={st['delta']:+.4f} "
              f"[{st['lo']:+.4f},{st['hi']:+.4f}] p={st['p']:.3f} {star} "
              f"(+{st['n_pos']}/−{st['n_neg']}/={st['n_tie']}, n={st['n']})")
    print("  （** = 95% CI 不含 0）")
    print()

    # ------------------------------------------------------- 训练增益
    print("=" * 108)
    print("【表 D】训练增益（自监督 − 人工加权）按处置与金标")
    print("=" * 108)
    print(f"{'处置':36s} {'金标':7s} {'人工(M0)':>9s} {'自监督':>9s} "
          f"{'弱监督':>9s} {'增益(自)':>10s} {'增益(弱)':>10s}")
    gain_rows = []
    for disp in DISPOSITIONS:
        for gold in ("llm", "constr"):
            hw = results[("M0 4d .35/.25/.20/.20", "manual", gold)]
            if not hw["n"]:
                continue
            n = hw["n"]
            ts = results[(disp, "trained_self", gold)]
            tw = results[(disp, "trained_weak", gold)]
            gm = (ts["mrr"] - hw["mrr"]) / n
            gw = (tw["mrr"] - hw["mrr"]) / max(1, tw["n"])
            print(f"{disp:36s} {gold:7s} {hw['mrr']/n:>9.4f} "
                  f"{ts['mrr']/max(1,ts['n']):>9.4f} "
                  f"{tw['mrr']/max(1,tw['n']):>9.4f} "
                  f"{gm*100:>+9.2f}pp {gw*100:>+9.2f}pp")
            gain_rows.append(dict(disp=disp, gold=gold,
                                  manual=hw["mrr"] / n,
                                  trained=ts["mrr"] / max(1, ts["n"]),
                                  weak=tw["mrr"] / max(1, tw["n"]),
                                  gain_self=gm, gain_weak=gw, n=n))
    print()
    print("  人工路径按 M0 固定（0.35/0.25/0.20/0.20）—— 表 D 只变训练侧的维度。")

    out = dict(n_docs=len(docs), n_queries=N, learned_weights=lw,
               manual_configs={k: dict(v) for k, v in MANUAL.items()},
               results={f"{k[0]}|{k[1]}|{k[2]}": dict(
                   mrr=v["mrr"] / max(1, v["n"]), h3=v["h3"] / max(1, v["n"]),
                   h10=v["h10"] / max(1, v["n"]), n=v["n"],
                   per=[float(x) for x in v["per"]])
                   for k, v in results.items()},
               ci=ci_rows, gains=gain_rows)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
