# -*- coding: utf-8 -*-
"""gen3 实验一：7 维特征全量审计（本代主交付物）。

对每一维报告：
  ① 单特征 AUC（plain）＋ bootstrap 95% CI
  ② 分层 AUC（按「查询侧锚点」edge/text 分层；再按 chunk 池规模分层）
  ③ 训练后权重（110 个伪文档的均值 / 标准差 / 中位数 / 显著非零率）
  ④ 人工加权硬编码权重（来自 evaluate_retrieval.py:186-187）
  ⑤ 与其余各维的秩相关（Spearman）+ 二值重叠率（Jaccard on >0 集合）
  ⑥ 裁决：dead / redundant / useful / harmful

同时复现两代前人结论：
  - type 单特征 AUC ≈ 0.497、学到权重 ≈ +0.049、人工硬编码 0.20（gen1）
  - same_cascade 与 same_frame 的配对重叠率 ≈ 51.7%（gen2）

**AUC 的两种口径**（必须区分，否则会误判 type 为「死」）：
  - plain   ：把 110 个文档的 (查询, 候选) 对全部堆在一起算 AUC。
              跨文档的绝对水平不可比，池子大小差异会被当成信号。
  - paired  ：**同一查询内**算 AUC（金标候选 vs 非金标候选），再对查询平均。
              这是「能不能在本查询的候选池里把金标排前面」的正确口径，
              与 MRR 的排序语义一致。gen1 的 0.497 是 plain 口径。
两者都报，差异本身就是发现。

运行：
    python experiments/gen3/exp_g3_1_audit.py
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
                                     FEATURE_NAMES, feature_auc)
from metaphor_graph.retrieval import RetrievalEngine               # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "exp_g3_1_audit.json")


def per_query_auc(F, meta, gold):
    """同一查询内：金标候选 vs 非金标候选的逐特征 AUC（加权并列）。"""
    gold_set = set(gold)
    is_g = np.array([m["chunk_id"] in gold_set for m in meta])
    out = {}
    if is_g.sum() == 0 or (~is_g).sum() == 0:
        return None
    for j, name in enumerate(FEATURE_NAMES):
        col = F[:, j]
        out[name] = G.auc_pairs(col[is_g], col[~is_g])
    return out


def main():
    payload = G.build_cache("default")
    docs = payload["docs"]
    print("=" * 96)
    print("gen3 实验一：7 维特征全量审计")
    print("=" * 96)
    print(f"重放：{len(docs)} 个伪文档 ｜ {payload['n_queries']} 条 LLM 改写查询 ｜ "
          f"{payload['n_pairs']} 个 (查询,候选) 对 ｜ 本体 {payload['n_frames']} 框架")
    print()

    # ================================================== ① 池化 AUC（plain，gen1 口径）
    Xall, yall, doc_of = [], [], []
    paired = defaultdict(list)          # 分层：锚点
    paired_by_size = defaultdict(list)
    const_stats = defaultdict(lambda: defaultdict(int))
    for d in docs:
        for q in d["queries"]:
            F, meta, gold = q["feats"], d["cand_meta"], q["gold_llm"]
            gold_set = set(gold)
            y = np.array([1.0 if m["chunk_id"] in gold_set else 0.0
                          for m in meta])
            Xall.append(F)
            yall.append(y)
            doc_of.append(d["did"])
            for j, name in enumerate(FEATURE_NAMES):
                for v in F[:, j]:
                    const_stats[name][round(float(v), 3)] += 1
            pq = per_query_auc(F, meta, gold)
            if pq:
                for name, v in pq.items():
                    if v == v:
                        paired[name].append(v)
                    paired_by_size[(d["did"], len(set(m["chunk_id"] for m in meta)))] \
                        = paired_by_size.get((d["did"], 0))
    Xall = np.vstack(Xall)
    yall = np.concatenate(yall)

    ds_all = TrainingSet(Xall, yall)
    plain_auc = feature_auc(ds_all)

    # 分层：边锚点 / 文本锚点
    strat = defaultdict(lambda: defaultdict(list))
    for d in docs:
        for q in d["queries"]:
            F, meta, gold = q["feats"], d["cand_meta"], q["gold_llm"]
            pq = per_query_auc(F, meta, gold)
            if not pq:
                continue
            for name, v in pq.items():
                if v == v:
                    strat[q["anchor"]][name].append(v)

    # 分层：候选池 chunk 数（小池 vs 大池）
    sizes = []
    for d in docs:
        for q in d["queries"]:
            sizes.append(len(set(m["chunk_id"] for m in d["cand_meta"]
                                 if m["chunk_id"])))
    med_size = float(np.median(sizes))
    strat2 = defaultdict(lambda: defaultdict(list))
    for d, s in zip([dd for dd in docs for _ in dd["queries"]], sizes):
        pass
    for d in docs:
        for q in d["queries"]:
            F, meta, gold = q["feats"], d["cand_meta"], q["gold_llm"]
            nch = len(set(m["chunk_id"] for m in meta if m["chunk_id"]))
            pq = per_query_auc(F, meta, gold)
            if not pq:
                continue
            bucket = "small" if nch <= med_size else "large"
            for name, v in pq.items():
                if v == v:
                    strat2[bucket][name].append(v)

    # ================================================== ② 训练后权重
    ws = defaultdict(list)
    auc_self_plain = defaultdict(list)
    train_auc_paired = defaultdict(list)
    for d in docs:
        ds = TrainingSet(d["X_self"], d["y_self"])
        if len(ds) == 0:
            continue
        sc = MetaphorScorer().fit(ds)
        for name, v in sc.weights().items():
            ws[name].append(v)
        for name, v in feature_auc(ds).items():
            if v == v:
                auc_self_plain[name].append(v)
    # 训练集内部的配对 AUC（chunk 模式）
    for d in docs:
        X, y = d["X_self"], d["y_self"]
        # chunk 模式的「查询」= chunk：meta 未存，用行块近似——改为直接按
        # 正负全样本算（chunk 模式里正样本来自不同 chunk，池化即其口径）
        pass

    # ================================================== ③ 人工权重
    manual_w = dict(G.MANUAL_W)
    manual_norm = {k: v / sum(manual_w.values()) for k, v in manual_w.items()}

    # ================================================== ④ 冗余
    rc, ov = G.pairwise_redundancy(Xall)

    # ---- 训练集内部的重叠（这是训练器真正看到的东西）----
    Xs_all = np.vstack([d["X_self"] for d in docs if len(d["X_self"])])
    rc_s, ov_s = G.pairwise_redundancy(Xs_all)
    n_train = len(Xs_all)

    # ---- 候选级 same_frame / same_cascade 的配对重叠（gen2 的 51.7% 口径）----
    n_pair_tot = n_both = n_casc_pos = n_frame_pos = 0
    for d in docs:
        for q in d["queries"]:
            F = q["feats"]
            f_i, c_i = G.IDX["same_frame"], G.IDX["same_cascade"]
            pos = (F[:, f_i] > 0) | (F[:, c_i] > 0)
            n_pair_tot += int(pos.sum())
            n_both += int(((F[:, f_i] > 0) & (F[:, c_i] > 0)).sum())
            n_casc_pos += int((F[:, c_i] > 0).sum())
            n_frame_pos += int((F[:, f_i] > 0).sum())

    print("【表 1】单特征 AUC：池化 vs 查询内配对（LLM 非构造金标）")
    print(f"{'特征':16s} {'池化AUC':>9s} {'95%CI':>17s} {'配对AUC':>9s} "
          f"{'95%CI':>17s} {'常数率':>8s}")
    rows1 = []
    for j, name in enumerate(FEATURE_NAMES):
        p = plain_auc.get(name, float("nan"))
        col = Xall[:, j]
        pos, neg = col[yall > 0.5], col[yall < 0.5]
        lo, hi = G.auc_ci(pos, neg)
        pq = np.array(paired[name])
        pqa = float(pq.mean()) if len(pq) else float("nan")
        # 配对 AUC 的 CI（对查询重采样）
        rng = np.random.default_rng(3)
        boots = np.array([pq[rng.integers(0, len(pq), len(pq))].mean()
                          for _ in range(1000)]) if len(pq) > 1 else np.array([pqa])
        plo, phi = np.percentile(boots, [2.5, 97.5])
        top = max(const_stats[name].values()) / max(1, sum(const_stats[name].values()))
        rows1.append(dict(name=name, plain=p, plain_lo=lo, plain_hi=hi,
                          paired=pqa, paired_lo=float(plo), paired_hi=float(phi),
                          const_rate=top))
        print(f"{name:16s} {p:>9.4f} [{lo:>6.4f},{hi:>6.4f}] {pqa:>9.4f} "
              f"[{plo:>6.4f},{phi:>6.4f}] {top:>7.1%}")
    print()
    print("【表 2】分层配对 AUC（按查询侧锚点；gen1 的 0.497 是池化口径）")
    print(f"{'特征':16s} {'边锚点(n)':>16s} {'文本锚点(n)':>18s} "
          f"{'小池(n)':>15s} {'大池(n)':>15s}")
    rows2 = []
    for name in FEATURE_NAMES:
        e = np.array(strat["edge"][name]); t = np.array(strat["text"][name])
        s = np.array(strat2["small"][name]); l = np.array(strat2["large"][name])
        rows2.append(dict(name=name, edge=float(e.mean()) if len(e) else None,
                          n_edge=len(e), text=float(t.mean()) if len(t) else None,
                          n_text=len(t), small=float(s.mean()) if len(s) else None,
                          n_small=len(s), large=float(l.mean()) if len(l) else None,
                          n_large=len(l)))
        print(f"{name:16s} {e.mean():>10.4f}({len(e):>4d}) {t.mean():>12.4f}({len(t):>4d}) "
              f"{s.mean():>9.4f}({len(s):>4d}) {l.mean():>9.4f}({len(l):>4d})")
    print()

    print("【表 3】训练后权重 vs 人工权重（110 个伪文档各训一个排序器）")
    print(f"{'特征':16s} {'学到权重均值':>12s} {'标准差':>9s} {'中位数':>9s} "
          f"{'|w|>0.05率':>10s} {'人工权重':>9s} {'归一人工':>9s} {'训练集池化AUC':>13s}")
    rows3 = []
    for name in FEATURE_NAMES:
        w = np.array(ws[name])
        mw = manual_w.get(name, 0.0)
        a = np.array(auc_self_plain[name])
        frac = float((np.abs(w) > 0.05).mean())
        rows3.append(dict(name=name, w_mean=float(w.mean()), w_sd=float(w.std()),
                          w_med=float(np.median(w)), frac=frac,
                          manual=mw, manual_norm=manual_norm.get(name, 0.0),
                          train_auc=float(a.mean()) if len(a) else None))
        print(f"{name:16s} {w.mean():>+12.4f} {w.std():>9.4f} "
              f"{np.median(w):>+9.4f} {frac:>9.1%} {mw:>9.2f} "
              f"{manual_norm.get(name, 0.0):>9.3f} "
              f"{(a.mean() if len(a) else float('nan')):>13.4f}")
    print(f"（训练集 n={n_train} 个 (文本,候选) 对；学到权重为标准化空间，"
          f"人工权重为原始空间，量纲不同——见 §裁决）")
    print()

    print("【表 4】特征间冗余：秩相关（下三角）/ 二值重叠率 Jaccard（上三角）")
    print(f"{'':16s} " + " ".join(f"{n[:9]:>9s}" for n in FEATURE_NAMES))
    for i, ni in enumerate(FEATURE_NAMES):
        cells = []
        for j, nj in enumerate(FEATURE_NAMES):
            if i == j:
                cells.append(f"{'—':>9s}")
            elif i > j:
                cells.append(f"{rc[i, j]:>9.3f}")
            else:
                cells.append(f"{ov[i, j]:>9.3f}")
        print(f"{ni:16s} " + " ".join(cells))
    print()
    print("  训练集内部（X_self）同一矩阵：")
    print(f"{'':16s} " + " ".join(f"{n[:9]:>9s}" for n in FEATURE_NAMES))
    for i, ni in enumerate(FEATURE_NAMES):
        cells = []
        for j, nj in enumerate(FEATURE_NAMES):
            if i == j:
                cells.append(f"{'—':>9s}")
            elif i > j:
                cells.append(f"{rc_s[i, j]:>9.3f}")
            else:
                cells.append(f"{ov_s[i, j]:>9.3f}")
        print(f"{ni:16s} " + " ".join(cells))
    print()

    print("【表 5】same_frame / same_cascade 配对重叠（gen2 的 51.7% 口径）")
    print(f"  评测候选对上：same_frame 命中 {n_frame_pos}，same_cascade 命中 "
          f"{n_casc_pos}，两者同时命中 {n_both}")
    print(f"  same_cascade 命中里同时 same_frame 的比例 = "
          f"{n_both / max(1, n_casc_pos):.1%}")
    print(f"  并集 {n_pair_tot}；Jaccard = {n_both / max(1, n_pair_tot):.3f}")
    print()

    # ================================================== ⑤ type 三级取值构成
    print("【表 6】type 取值构成（FIXED-CAP 口径）与「近常数」程度")
    for j, name in enumerate(FEATURE_NAMES):
        d_ = const_stats[name]
        tot = sum(d_.values())
        top2 = sorted(d_.items(), key=lambda x: -x[1])[:3]
        print(f"  {name:16s} " + "  ".join(f"{k}:{v}({v/tot:.1%})"
                                          for k, v in top2))
    print()

    # ================================================== ⑥ 裁决
    print("【表 7】裁决规则与结果")
    print("  规则（预先声明，不事后调参）：")
    print("    dead      CI 覆盖 0.5 且 |配对AUC−0.5| < 0.02")
    print("    harmful   配对 AUC < 0.5 且 CI 上界 < 0.5（显著反向）")
    print("    useful    CI 下界 > 0.5 且 |配对AUC−0.5| ≥ 0.02（显著且非平凡）")
    print("    weak      CI 下界 > 0.5 但 |配对AUC−0.5| < 0.02（显著但幅度小）")
    print("    redundant 与某一维的秩相关 ≥ 0.8 或二值重叠 Jaccard ≥ 0.8")
    verdicts = {}
    for r in rows1:
        name = r["name"]
        pqa, lo, hi = r["paired"], r["paired_lo"], r["paired_hi"]
        if hi < 0.5:
            v = "harmful"
        elif lo <= 0.5 <= hi:
            v = "dead" if abs(pqa - 0.5) < 0.02 else "inconclusive"
        elif abs(pqa - 0.5) < 0.02:
            v = "weak"
        else:
            v = "useful"
        verdicts[name] = v
    # 冗余叠加
    for i, ni in enumerate(FEATURE_NAMES):
        for j, nj in enumerate(FEATURE_NAMES):
            if i < j and (abs(rc[i, j]) >= 0.8 or ov[i, j] >= 0.8):
                verdicts[ni] = f"{verdicts[ni]}+redundant({nj})"
                verdicts[nj] = f"{verdicts[nj]}+redundant({ni})"
    for name in FEATURE_NAMES:
        r = next(x for x in rows1 if x["name"] == name)
        print(f"    {name:16s} 配对AUC={r['paired']:.4f} "
              f"[{r['paired_lo']:.4f},{r['paired_hi']:.4f}] → {verdicts[name]}")
    print()

    # ================================================== ⑦ 训练增益分解：逐维权重
    print("【表 8】gen1 结论复现对照")
    print(f"  gen1 报告：type 单特征 AUC 0.4973（池化）、学到权重 +0.0487、人工 0.20")
    t = next(x for x in rows1 if x["name"] == "type")
    tw = np.array(ws["type"])
    print(f"  gen3 实测：type 池化 AUC {t['plain']:.4f}、配对 AUC {t['paired']:.4f}、"
          f"学到权重 {tw.mean():+.4f}、人工 0.20")
    print(f"  gen2 报告：same_cascade 与 same_frame 重叠 51.7%")
    print(f"  gen3 实测：{n_both / max(1, n_casc_pos):.1%}")

    result = dict(
        n_docs=len(docs), n_queries=payload["n_queries"],
        n_pairs=int(Xall.shape[0]), n_frames=payload["n_frames"],
        table1=rows1, table2=rows2, table3=rows3,
        rank_corr_eval=rc.tolist(), overlap_eval=ov.tolist(),
        rank_corr_train=rc_s.tolist(), overlap_train=ov_s.tolist(),
        same_frame_pos=n_frame_pos, same_cascade_pos=n_casc_pos,
        both_pos=n_both, union_pos=n_pair_tot,
        verdicts=verdicts, const_stats={k: dict(v) for k, v in const_stats.items()},
        med_chunk_pool=med_size)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
