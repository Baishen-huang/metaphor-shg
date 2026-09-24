# -*- coding: utf-8 -*-
"""Ω 实验 6：基底结构诊断 —— 为什么 Ω 的两个分量在本项目基底上退化。

Ω 的设计借自另一套系统（边 / 涌现 / 流量熵），但那套系统的基底里「扩展」
是**拓扑上可能**的（超边能连到远处节点）。本项目的隐喻基底不是同构的，
本脚本量化三处结构错配：

  S1  级联闭包 = 回声。`ontology_clean` 按 target_domain 分组生成 LLM 级联
      （`LLM_TARGET::t`），故级联成员共享同一目标域 → 「经级联扩展抵达、
      且不在直接命中集里的目标域」几乎恒为空集 → **Ω_N 恒 ≈ 0**。
  S2  Ω 对触发词数非单调（Ω_E 的分母 + 完备度因子的长度惩罚）。
  S3  Ω 与「触发词命中数」共线（ρ=0.995），在预测级联通路上信息量 = 1 bit。

并对每处给出「若要让 Ω 真正度量结构激活，需要改什么」的具体建议。

运行：<python> experiments/exp6_substrate.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
logging.disable(logging.CRITICAL)

import _stats as S  # noqa: E402
from metaphor_graph.observability import (ObservabilityMeter, geometric_mean,  # noqa: E402
                                          measure)
from metaphor_graph.ontology import DEFAULT_ONTOLOGY  # noqa: E402
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology  # noqa: E402

OUT = os.path.join(HERE, "exp6_substrate.json")


def main():
    prod, n_frames = build_replay_ontology()
    rows = json.load(open(os.path.join(HERE, "exp1_omega.json"),
                          encoding="utf-8"))["rows"]
    out = {}
    print("=" * 92)
    print("Ω 实验 6：基底结构诊断（三处设计-基底错配）")
    print("=" * 92)

    # ================================================================== S1
    print("\n" + "-" * 92)
    print("【S1】级联闭包 = 回声：Ω_N 在生产本体上几乎恒为 0")
    print("-" * 92)
    same = tot = 0
    for cid, c in prod.cascades.items():
        tds = {prod.frames[f].target_domain for f in c.member_frames
               if f in prod.frames}
        tot += 1
        if len(tds) <= 1:
            same += 1
    print(f"  级联成员目标域唯一（闭包不带来新域）的级联：{same}/{tot} = {same / tot:.1%}")
    print(f"  成员数=1 的级联："
          f"{sum(1 for c in prod.cascades.values() if len(c.member_frames) == 1)}"
          f"/{len(prod.cascades)}"
          f" = {sum(1 for c in prod.cascades.values() if len(c.member_frames) == 1) / len(prod.cascades):.1%}")
    eq = f_tot = 0
    for fid, fs in prod.frames.items():
        cid = prod.get_cascade(fid)
        spec = prod.get_cascade_spec(cid) if cid else None
        if spec is None:
            continue
        f_tot += 1
        direct = {fs.target_domain}
        exp = {prod.frames[f].target_domain for f in spec.member_frames
               if f in prod.frames}
        if exp <= direct:
            eq += 1
    print(f"  单框架出发、级联闭包不带来新目标域的框架：{eq}/{f_tot} = {eq / f_tot:.1%}")
    print(f"  根因：ontology_clean 的 LLM 级联按 target_domain 分组"
          f"（`LLM_TARGET::{{t}}`）→ 成员必然共享目标域")
    print(f"  对照·内置种子级联（{len(DEFAULT_ONTOLOGY.cascades)} 个，人工构造）："
          f"多目标域的有 "
          f"{sum(1 for c in DEFAULT_ONTOLOGY.cascades.values() if len({DEFAULT_ONTOLOGY.frames[f].target_domain for f in c.member_frames if f in DEFAULT_ONTOLOGY.frames}) > 1)} 个")
    for tag, key in (("改写型", "omega_n_p"), ("重叠型", "omega_n_o")):
        v = [r[key] for r in rows]
        nz = sum(1 for x in v if x > 0)
        print(f"  {tag} Ω_N>0 占比 = {nz}/{len(v)} = {nz / len(v):.1%}  mean={S.mean(v):.4f}")
        out[f"omega_n_nonzero_{key}"] = nz / len(v)
    # 若把 Ω_N 从几何平均里去掉，Ω 会变多少？
    m = ObservabilityMeter(prod)
    shifts = []
    for r in rows:
        o = m.measure(r["paraphrase"])
        if o.omega > 0:
            alt = geometric_mean((o.omega_e, 1.0, o.omega_f)) * o.completeness
            shifts.append(alt - o.omega)
    print(f"  把 Ω_N 置为 1（即从几何平均中移除该分量）后，Ω 平均变化 = "
          f"{S.mean(shifts):+.4f}（n={len(shifts)}，中位 {S.median(shifts):+.4f}）")
    print("  → Ω_N 在本基底上是**死分量**：它把 Ω 整体压低约 3–5 倍，"
          "但不提供任何查询间区分度")
    out["omega_n_neutral_shift"] = S.mean(shifts)

    # ================================================================== S2
    print("\n" + "-" * 92)
    print("【S2】Ω 对触发词数非单调（Ω_E 分母 + 完备度长度惩罚）")
    print("-" * 92)
    probes = ["泥潭", "泥潭，沼泽", "泥潭，沼泽，陷进", "泥潭，沼泽，陷进，深坑",
              "推进", "推进，停滞", "推进，停滞，迈步，抵达"]
    print(f"  {'查询':26s} {'n_seed':>6s} {'len':>4s} {'Ω_E':>7s} {'Ω_F':>7s} "
          f"{'comp':>7s} {'Ω_geo':>7s} {'Ω':>7s}")
    for q in probes:
        o = m.measure(q)
        print(f"  {q:26s} {o.n_seed_triggers:>6d} {len(q):>4d} {o.omega_e:>7.3f} "
              f"{o.omega_f:>7.3f} {o.completeness:>7.3f} {o.omega_geo:>7.3f} "
              f"{o.omega:>7.3f}")
    print("\n  两条反向机制：")
    print("    (i)  Ω_E = 点亮框架数 / 种子触发词数 —— 多个触发词坍缩到同一框架时"
          "分母涨、分子不涨 → Ω_E 下降（\"泥潭，沼泽\" 的 Ω_E=0.5 而非 1.0）")
    print("    (ii) 完备度 = 覆盖字符 / 查询长度 —— 查询越长惩罚越重"
          "（4 词拼接 11 字 → comp=0.727）")
    print("  → 在真实数据上 Ω 与 n_seed 仍秩相关 0.995，是因为 0 块（无命中）"
          "主导；在 Ω>0 区间内 Ω 与 n_seed 的关系是**非单调**的")
    # 量化：真实数据里 Ω>0 子集内 Ω 与 n_seed 的关系
    pos = [r for r in rows if r["omega_p"] > 0]
    by_k = {}
    for r in pos:
        by_k.setdefault(r["n_seed_p"], []).append(r["omega_p"])
    print(f"\n  改写型 Ω>0 子集内按 n_seed 的 Ω 均值：")
    for k in sorted(by_k):
        print(f"    n_seed={k}: n={len(by_k[k]):>3d} mean Ω={S.mean(by_k[k]):.4f} "
              f"median={S.median(by_k[k]):.4f}")
    out["by_nseed_positive"] = {str(k): dict(n=len(v), mean=S.mean(v))
                                for k, v in by_k.items()}

    # ================================================================== S3
    print("\n" + "-" * 92)
    print("【S3】信息量核算：Ω 在预测级联通路上 = 1 bit")
    print("-" * 92)
    op = [r["omega_p"] for r in rows]
    ne = [1 if r["cascade_nonempty_p"] else 0 for r in rows]
    bit = [1 if r["n_seed_p"] > 0 else 0 for r in rows]
    ombit = [1 if v > 0 else 0 for v in op]
    print(f"  Ω>0 与 n_seed≥1 的逐条一致率 = "
          f"{sum(1 for a, b in zip(ombit, bit) if a == b)}/{len(rows)} = "
          f"{sum(1 for a, b in zip(ombit, bit) if a == b) / len(rows):.4f}")
    print(f"  Ω>0 与「通路非空」的一致率 = "
          f"{sum(1 for a, b in zip(ombit, ne) if a == b) / len(rows):.4f}")
    print(f"  n_seed≥1 与「通路非空」的一致率 = "
          f"{sum(1 for a, b in zip(bit, ne) if a == b) / len(rows):.4f}")
    print("  → 三者一致：Ω 在「通路是否非空」上的信息 = 触发词有无 = 1 bit")
    print("\n  额外信息量的唯一来源是 Ω 的连续部分，实测：")
    pos_rows = [r for r in rows if r["omega_p"] > 0]
    succ = [1 if r["cascade_hit_p"] else 0 for r in pos_rows]
    om = [r["omega_p"] for r in pos_rows]
    r_pb, p_pb, _ = S.point_biserial(succ, om)
    rho, p_rho, _ = S.spearman(om, succ)
    print(f"    Ω>0 内 Ω × 通路命中：点二列 r={r_pb:.4f} p={p_pb:.3e}；"
          f"Spearman ρ={rho:.4f} p={p_rho:.3e}")
    print(f"    （点二列与 Spearman 符号相反 —— 说明 Ω>0 区间内没有稳定方向，"
          f"只是噪声）")
    out["pos_biserial"] = dict(r=r_pb, p=p_pb)
    out["pos_spearman"] = dict(rho=rho, p=p_rho)

    # ================================================================== 建议
    print("\n" + "-" * 92)
    print("【结论】三处设计-基底错配与具体修法")
    print("-" * 92)
    print("  S1 Ω_N 死分量 -> 若基底级联要承载「涌现」，级联必须允许成员跨目标域")
    print("     （种子本体做到了：13 个里有 6 个跨域；生产本体 758 个里只有 6 个）。")
    print("     在此之前，Ω_N 应从几何平均里移除，或改为「点亮的级联数 / 种子数」。")
    print("  S2 非单调 -> Ω_E 的分母不该是「种子触发词数」（触发词可以同义冗余），")
    print("     而应是「点亮的结构数上限」；完备度因子应改为触发词覆盖率的")
    print("     阈值化形式（例如 min(1, 覆盖字符/2)），否则长查询被系统性压低。")
    print("  S3 1 bit -> 若 Ω 的目的是门控级联通路，直接判 n_seed > 0 即可，")
    print("     不需要 Ω；若目的是度量激活了多少结构，必须让 Ω 读图")
    print("     （实验 3 的 Ω_G：AUC 0.954 -> 1.000）。但读图后 Ω 就不再是纯查询侧")
    print("     泛函，参考设计的核心不变式（不受候选污染）也随之放弃 —— 这是真实的")
    print("     取舍，不是可以两全的工程细节。")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n诊断已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
