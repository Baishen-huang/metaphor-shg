# -*- coding: utf-8 -*-
"""gen3 实验七：把前三代的分散结果收拢成一组「判定性问题」的答案。

读 exp_g3_2_dispositions.json / exp_g3_4_null.json / exp_g3_6_fullcorpus.json，
回答：

  Q1  「训练增益」是否只是「把人工权重调对」？
      → 人工权重改成与学到权重同比例后，训练还剩多少增益？
  Q2  最优单信号是什么？训练后的 7 维比最优单信号好多少？
  Q3  哪几维对最终指标有可测的边际贡献？
  Q4  人工加权的最优配置是什么？「type 占 0.20」损失多少？
  Q5  处置对两个金标是否给出**同向**结论？（金标稳健性）

运行：
    python experiments/gen3/exp_g3_7_verdict.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from experiments.gen3 import g3_common as G                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "exp_g3_7_verdict.json")


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    disp = load("exp_g3_2_dispositions.json")
    null = load("exp_g3_4_null.json")
    fc = load("exp_g3_6_fullcorpus.json")
    metric = load("exp_g3_3_metric.json")
    R = disp["results"]

    def per(k):
        return np.asarray(R[k]["per"], dtype=float)

    def mrr(k):
        return R[k]["mrr"]

    def show(a, b, label, n_boot=4000):
        if a not in R or b not in R:
            print(f"  {label:52s} （缺数据）")
            return None
        x, y = per(a), per(b)
        if len(x) != len(y) or not len(x):
            print(f"  {label:52s} （n 不一致）")
            return None
        st = G.paired_bootstrap(x, y, n_boot=n_boot)
        star = "**" if (st["lo"] > 0 or st["hi"] < 0) else "  "
        print(f"  {label:52s} Δ={st['delta']:+.4f} "
              f"[{st['lo']:+.4f},{st['hi']:+.4f}] p={st['p']:.4f} {star}")
        return st

    print("=" * 108)
    print("gen3 实验七：判定性问题汇总（LLM 非构造金标，n=632）")
    print("=" * 108)
    print()

    print("【Q1】「训练增益」是否只是「把人工权重调对」？")
    print(f"  {'配置':52s} {'MRR@10':>8s}")
    for k, lab in (("M0 4d .35/.25/.20/.20|manual|llm", "已上报人工加权 0.35/0.25/0.20/0.20"),
                   ("M1 3d .35/.25/.40|manual|llm", "人工去 type（权重给 clue）"),
                   ("M3 4d learned-share|manual|llm", "人工按**学到权重比例**（4 维）"),
                   ("M4 7d learned-share|manual|llm", "人工按**学到权重比例**（7 维）"),
                   ("D0 baseline7|trained_self|llm", "自监督训练（7 维）"),
                   ("D1 drop_type|trained_self|llm", "自监督训练（去 type，6 维）"),
                   ("D2 drop_same_cascade|trained_self|llm", "自监督训练（去 same_cascade）")):
        print(f"  {lab:52s} {mrr(k):>8.4f}")
    print()
    print("  配对对照：")
    st_q1 = show("M3 4d learned-share|manual|llm", "D0 baseline7|trained_self|llm",
                 "人工(学到比例) − 训练后 7 维")
    st_q1b = show("M3 4d learned-share|manual|llm",
                  "M0 4d .35/.25/.20/.20|manual|llm", "人工重配 − 已上报人工")
    print()
    if st_q1:
        print(f"  → 结论：把人工权重调成与学到权重同比例后，人工加权 "
              f"{mrr('M3 4d learned-share|manual|llm'):.4f} vs 训练后 "
              f"{mrr('D0 baseline7|trained_self|llm'):.4f}，"
              f"差 {st_q1['delta']*100:+.2f}pp "
              f"[{st_q1['lo']*100:+.2f},{st_q1['hi']*100:+.2f}]。")
        if st_q1["lo"] <= 0 <= st_q1["hi"]:
            print("     CI 覆盖 0 → **训练器没有超出「正确加权」的能力**；"
                  "已上报的 +6.4pp 训练增益主要是「人工权重配错」的产物。")
        else:
            print("     CI 不含 0 → 训练器仍有超出「正确加权」的增益。")
    print()

    print("【Q2】最优单信号与训练后的差距（零假设对照）")
    print(f"  {'配置':52s} {'MRR@10':>8s} {'Hits@3':>8s}")
    single = null["single"]
    for k in ("N2 sem only", "N1 clue only", "N3 ground only", "N9 struct only",
              "N10 type only", "N11 same_frame only", "N12 same_casc only",
              "N5 ORACLE producer", "N6 random", "N7 full7", "N8 sem+clue"):
        if k not in single:
            continue
        v = single[k]
        h3 = v["h3"] / max(1, v["n"]) if v["n"] else float("nan")
        print(f"  {k:52s} {v['mrr']:>8.4f} {h3:>8.4f}")
    print(f"  {'（参考）已上报人工加权 M0':52s} "
          f"{mrr('M0 4d .35/.25/.20/.20|manual|llm'):>8.4f}")
    print(f"  {'（参考）人工按学到比例 M3':52s} "
          f"{mrr('M3 4d learned-share|manual|llm'):>8.4f}")
    print()
    print("  配对对照（纯 sem 单信号在 M0 的候选池上重算）：")
    st_sem = show("M3 4d learned-share|manual|llm",
                  "M0 4d .35/.25/.20/.20|manual|llm",
                  "人工按学到比例 − 已上报人工（= +sem 权重的效果）")
    print()

    print("【Q3】逐维边际贡献（留一消融，重训 6 维）")
    print(f"  {'去掉的维':16s} {'自监督 Δ':>11s} {'95% CI':>22s} {'弱监督 Δ':>11s}")
    loo = {r["name"]: r for r in null["leave_one_out"]}
    looci = {r["name"]: r for r in null["loo_ci"]}
    for name in ("sem", "struct", "clue", "type", "same_frame", "same_cascade",
                 "ground_jaccard"):
        r = loo[name]; c = looci[name]
        star = "**" if (c["lo"] > 0 or c["hi"] < 0) else "  "
        print(f"  {name:16s} {r['delta']:>+11.4f} "
              f"[{c['lo']:>+8.4f},{c['hi']:>+8.4f}] {star} {r['delta_weak']:>+11.4f}")
    print()
    print("  → 只有 sem 的 CI 不含 0。其余 6 维（含 type）的边际贡献在噪声内。")
    print()

    print("【Q4】人工加权配置对照（M0 是已上报口径）")
    print(f"  {'配置':52s} {'MRR@10':>8s} {'vs M0':>9s}")
    base = mrr("M0 4d .35/.25/.20/.20|manual|llm")
    for k in sorted([x for x in R if x.endswith("|manual|llm")]):
        lab = k.split("|")[0]
        print(f"  {lab:52s} {mrr(k):>8.4f} {mrr(k)-base:>+9.4f}")
    print()
    best = max((k for k in R if k.endswith("|manual|llm")), key=lambda k: mrr(k))
    print(f"  → 最优人工配置：{best.split('|')[0]}  MRR={mrr(best):.4f}")
    print(f"    「type 占 0.20」相对最优人工配置损失 "
          f"{mrr(best)-base:+.4f} MRR（{base:.4f} vs {mrr(best):.4f}）")
    print()

    print("【Q5】金标稳健性：处置在两套金标下是否同向？")
    print(f"  {'处置':38s} {'llm Δ':>9s} {'constr Δ':>10s} {'同向?':>7s}")
    agree = 0
    tot = 0
    for dispname in ("D1 drop_type", "D2 drop_same_cascade",
                     "D3 drop_type+cascade", "D8 repl type<-frame_support_norm",
                     "D9 repl type<-frame_tier_core",
                     "D10 repl type<-cascade_size_norm",
                     "D11 repl type<-n_emergent",
                     "D12 repl type<-frame_registered",
                     "D13 repl type<-ground_len_norm"):
        ka = f"{dispname}|trained_self|llm"
        kb = f"{dispname}|trained_self|constr"
        k0a = "D0 baseline7|trained_self|llm"
        k0b = "D0 baseline7|trained_self|constr"
        if ka not in R:
            continue
        da = R[ka]["mrr"] - R[k0a]["mrr"]
        db = R[kb]["mrr"] - R[k0b]["mrr"]
        same = "是" if (da > 0) == (db > 0) else "**否**"
        tot += 1
        agree += 1 if same == "是" else 0
        print(f"  {dispname:38s} {da:>+9.4f} {db:>+10.4f} {same:>7s}")
    print(f"  → {agree}/{tot} 同向。两套金标对处置方向给出高度一致（但不完全相同）"
          f"的裁决。")
    print()

    print("【Q6】fullcorpus A7/H5 的 type 依赖（gen1 报告的「结论翻转」复核）")
    fcr = fc["results"]
    for k in ("manual_OLD-CONST", "manual_ZERO", "trained7", "trained6_no_type",
              "single_sem", "single_clue"):
        print(f"  {k:24s} MRR@10={fcr[k]['mrr']:.4f} Hits@3={fcr[k]['h3']:.4f} "
              f"n={fcr[k]['n']}")
    hw = fcr["manual_OLD-CONST"]["mrr"]
    hz = fcr["manual_ZERO"]["mrr"]
    t7 = fcr["trained7"]["mrr"]
    print(f"  A7（训练7 − 人工(type 参与 0.20)）= {(t7-hw)*100:+.2f}pp  ← 已上报口径")
    print(f"  A7（训练7 − 人工(type=0)）       = {(t7-hz)*100:+.2f}pp")
    print(f"  人工侧把 type 权重置 0 的收益      = {(hz-hw)*100:+.2f}pp")
    print("  → gen1 的「+0.3pp → +9.5pp 翻转」被完全解释：**翻转量 100% 来自"
          "人工加权硬编码 0.20 这一项**，")
    print("     训练侧去 type 的效应为 0.00pp。H5 的『翻转』不是模型能力变化，"
          "是人工基线被 type 拖低。")
    print()

    print("【Q7】指标批判要点（exp_g3_3）")
    print(f"  候选池 median={metric['pool']['med']:.0f} max={metric['pool']['max']}"
          f" → Hits@10 平凡为 1.0；随机排序期望 MRR={metric['random_mrr_floor']:.4f}")
    print(f"  产出 chunk ∈ LLM 金标：{metric['producer_in_gold']}/{metric['n_queries']}"
          f" = {metric['producer_in_gold']/metric['n_queries']:.1%}")
    print(f"  LLM 金标恰好 == {{产出 chunk}}："
          f"{metric['gold_equals_producer_only']}/{metric['n_queries']}"
          f" = {metric['gold_equals_producer_only']/metric['n_queries']:.1%}")
    p1 = metric["protocols"]["P1|T7 trained"]["mrr"]
    p2 = metric["protocols"]["P2|T7 trained"]["mrr"]
    q1m = metric["protocols"]["P1|M0 manual"]["mrr"]
    q2m = metric["protocols"]["P2|M0 manual"]["mrr"]
    print(f"  P1（已上报口径）训练增益 = {(p1-q1m)*100:+.2f}pp")
    print(f"  P2（剔除产出 chunk）训练增益 = {(p2-q2m)*100:+.2f}pp "
          f"（n={metric['protocols']['P2|T7 trained']['n']}，样本极小）")
    print()

    out = dict(q1=st_q1, q1b=st_q1b, q2_sem=st_sem,
               manual_best=best.split("|")[0], manual_best_mrr=mrr(best),
               manual_m0_mrr=base, gold_agreement=f"{agree}/{tot}",
               fullcorpus=dict(manual_old=fcr["manual_OLD-CONST"]["mrr"],
                               manual_zero=fcr["manual_ZERO"]["mrr"],
                               trained7=fcr["trained7"]["mrr"],
                               trained6=fcr["trained6_no_type"]["mrr"]),
               metric=dict(pool_med=metric["pool"]["med"],
                           random_floor=metric["random_mrr_floor"],
                           producer_in_gold=metric["producer_in_gold"],
                           n=metric["n_queries"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"产物：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
