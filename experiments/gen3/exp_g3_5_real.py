# -*- coding: utf-8 -*-
"""gen3 实验五：real-embedder 行（缓存真实句向量）的处置对照。

已上报的 real-embedder 一行是 0.707 / 0.758 / 0.755（人工加权 / 自监督 / 弱监督）。
本实验在**缓存真实句向量**（data/embed_cache.json，embedding-3，512 维）上重跑
关键处置，检验「去 type / 换 type / 重配人工权重」的结论是否依赖哈希向量器。

**口径**：与 exp/source 的 exp_real_embed_replay.py 一致 —— 只读缓存，未命中
计数并报出。若命中率不足 100%，绝对值不可与已上报的 0.707/0.758/0.755 直接比，
但**处置间的差值**仍然内部有效（同一批向量、同一份图、同一套金标）。

运行：
    python experiments/gen3/exp_g3_5_real.py
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
                   "exp_g3_5_real.json")

DISPOSITIONS = {
    "D0 baseline7":         ("full7", None),
    "D1 drop_type":         ("no_type", None),
    "D2 drop_same_cascade": ("no_cascade", None),
    "D3 drop_type+cascade": ("no_type_no_casc", None),
    "D8 repl type<-frame_support_norm": ("no_type", "frame_support_norm"),
    "D9 repl type<-frame_tier_core":    ("no_type", "frame_tier_core"),
    "D11 repl type<-n_emergent":        ("no_type", "n_emergent"),
}


def fit_scorer(X, y, seed=42):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(X) == 0 or len(np.unique(y)) < 2:
        return None
    return MetaphorScorer(n_features=X.shape[1], seed=seed).fit(TrainingSet(X, y))


def main():
    payload = G.build_cache("real")
    docs = payload["docs"]
    es = payload["emb_stats"] or {}
    N = sum(len(d["queries"]) for d in docs)
    print("=" * 100)
    print("gen3 实验五：real-embedder（缓存真实句向量）处置对照")
    print("=" * 100)
    print(f"向量模型 {es.get('model')} ｜ 命中 {es.get('n_hit')} / 未命中 "
          f"{es.get('n_miss')} ｜ {len(docs)} 伪文档 ｜ {N} 条查询")
    if es.get("n_miss"):
        print(f"  ⚠️ 未命中 {es['n_miss']} 条 —— 本行是**混合口径**，绝对值不可与"
              f"已上报的 0.707/0.758/0.755 直接比；处置间差值仍有效。")
        print(f"  未命中样例：{es.get('missing', [])[:3]}")
    else:
        print("  命中率 100% —— 可离线精确重放")
    print()

    SIG_KEYS = docs[0]["sig_keys"]
    SIG_COL = {k: i for i, k in enumerate(SIG_KEYS)}
    learned = defaultdict(list)
    for d in docs:
        sc = fit_scorer(d["X_self"], d["y_self"])
        if sc is None:
            continue
        for n, v in sc.weights().items():
            learned[n].append(v)
    lw = {n: float(np.mean(v)) for n, v in learned.items()}
    pos = {n: max(0.0, lw[n]) for n in FEATURE_NAMES}
    share4 = {n: pos[n] / sum(pos[k] for k in ("sem", "struct", "clue", "type"))
              for n in ("sem", "struct", "clue", "type")}
    MANUAL = {
        "M0 4d .35/.25/.20/.20": dict(sem=0.35, struct=0.25, clue=0.20,
                                      type=0.20),
        "M1 3d .35/.25/.40": dict(sem=0.35, struct=0.25, clue=0.40),
        "M3 4d learned-share": share4,
        "N2 sem only": dict(sem=1.0),
    }
    print("real 口径下学到的权重均值：", {n: round(lw[n], 4) for n in FEATURE_NAMES})
    print("→ M3 四维按学到比例：", {n: round(share4[n], 4)
                                    for n in ("sem", "struct", "clue", "type")})
    print()

    res = defaultdict(lambda: dict(mrr=0.0, per=[], n=0, h3=0))
    tr = defaultdict(dict)
    for didx, d in enumerate(docs):
        S, Sw = d["S_self"], d["S_weak"]
        for disp, (subname, repl) in DISPOSITIONS.items():
            idx = G.SUBSETS[subname]
            Xs = d["X_self"][:, idx]
            if repl is not None:
                Xs = np.hstack([Xs, S[:, [SIG_COL[repl]]]])
            tr[(disp, "self")][didx] = fit_scorer(Xs, d["y_self"])
            Xw = d["X_weak"][:, idx]
            if repl is not None and len(Xw):
                Xw = np.hstack([Xw, Sw[:, [SIG_COL[repl]]]])
            tr[(disp, "weak")][didx] = fit_scorer(Xw, d["y_weak"]) if len(Xw) else None

    def add(key, mrr, h3):
        a = res[key]
        a["mrr"] += mrr
        a["per"].append(mrr)
        a["h3"] += h3
        a["n"] += 1

    for didx, d in enumerate(docs):
        meta = d["cand_meta"]
        Sc = np.asarray([[m[k] for k in SIG_KEYS] for m in meta], dtype=float)
        for q in d["queries"]:
            F = q["feats"]
            gold = q["gold_llm"]
            for disp, (subname, repl) in DISPOSITIONS.items():
                idx = G.SUBSETS[subname]
                Fi = (np.hstack([F[:, idx], Sc[:, [SIG_COL[repl]]]])
                      if repl is not None else F[:, idx])
                for src in ("self", "weak"):
                    sc = tr[(disp, src)].get(didx)
                    if sc is None:
                        continue
                    r = G.rank_chunks(G.chunk_scores(Fi, scorer=sc), meta)
                    add(f"{disp}|trained_{src}", G.mrr_of(r, gold),
                        G.hits_of(r, gold, 3))
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
                add(f"{mname}|manual", G.mrr_of(r, gold), G.hits_of(r, gold, 3))

    print("【表 A】real-embedder 处置对照（LLM 非构造金标）")
    print(f"{'处置':38s} {'配置':14s} {'MRR@10':>8s} {'Hits@3':>8s} {'n':>5s}")
    for k in sorted(res, key=lambda x: (x.split("|")[0], x.split("|")[1])):
        a = res[k]
        if not a["n"]:
            continue
        disp, cfg = k.split("|")
        print(f"{disp:38s} {cfg:14s} {a['mrr']/a['n']:>8.4f} {a['h3']/a['n']:>8.4f} "
              f"{a['n']:>5d}")
    print()

    print("【表 B】配对 bootstrap 95% CI（vs D0 基线，各自路径）")
    print(f"{'对照':58s} {'Δ':>9s} {'95% CI':>22s} {'p':>7s}")
    cmp_rows = []
    for da, db, cfg, label in (
            ("D1 drop_type", "D0 baseline7", "trained_self",
             "去 type（重训 6 维）− 基线 7 维"),
            ("D2 drop_same_cascade", "D0 baseline7", "trained_self",
             "去 same_cascade − 基线"),
            ("D3 drop_type+cascade", "D0 baseline7", "trained_self",
             "去 type+cascade − 基线"),
            ("D8 repl type<-frame_support_norm", "D0 baseline7", "trained_self",
             "换 type→frame_support − 基线"),
            ("D9 repl type<-frame_tier_core", "D0 baseline7", "trained_self",
             "换 type→frame_tier − 基线"),
            ("D11 repl type<-n_emergent", "D0 baseline7", "trained_self",
             "换 type→n_emergent − 基线"),
            ("M1 3d .35/.25/.40", "M0 4d .35/.25/.20/.20", "manual",
             "人工去 type（权重给 clue）− 基线人工"),
            ("M3 4d learned-share", "M0 4d .35/.25/.20/.20", "manual",
             "人工按学到比例 − 基线人工"),
            ("N2 sem only", "D0 baseline7", "trained_self",
             "纯 sem 单信号 − 训练后 7 维"),
            ("N2 sem only", "M0 4d .35/.25/.20/.20", "manual",
             "纯 sem 单信号 − 基线人工"),
    ):
        ka, kb = f"{da}|{cfg}", f"{db}|{cfg}"
        if ka not in res or kb not in res or not res[ka]["n"]:
            print(f"  {label:58s} 跳过")
            continue
        a = np.asarray(res[ka]["per"]); b = np.asarray(res[kb]["per"])
        if len(a) != len(b):
            continue
        st = G.paired_bootstrap(a, b, n_boot=2000)
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"  {label:58s} {st['delta']:>+9.4f} "
              f"[{st['lo']:>+8.4f},{st['hi']:>+8.4f}] {st['p']:>6.3f} {star}")
        cmp_rows.append(dict(label=label, **st))
    print()
    print("  已上报 real-embedder 基线：人工加权 0.707 ｜ 自监督 0.758 ｜ 弱监督 0.755")
    m0 = res["M0 4d .35/.25/.20/.20|manual"]
    d0 = res["D0 baseline7|trained_self"]
    d0w = res["D0 baseline7|trained_weak"]
    print(f"  本次重放：人工加权 {m0['mrr']/m0['n']:.4f} ｜ "
          f"自监督 {d0['mrr']/d0['n']:.4f} ｜ 弱监督 {d0w['mrr']/d0w['n']:.4f}")

    out = dict(emb_stats=es, n_queries=N, learned_weights=lw,
               results={k: dict(mrr=v["mrr"] / max(1, v["n"]),
                                h3=v["h3"], n=v["n"],
                                per=[float(x) for x in v["per"]])
                        for k, v in res.items()},
               comparisons=cmp_rows)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
