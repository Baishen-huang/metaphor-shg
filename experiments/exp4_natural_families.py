# -*- coding: utf-8 -*-
"""Ω 实验 4：非构造查询族的 regime 分布 —— 82% collapsed 是基准产物还是普遍现象？

实验 2【C】已发现：改写基准的生成阶段**程序化禁用**了触发词（红线过滤），
因此「改写型 Ω 低」有构造性成分。要判断 Ω 的 regime 分布是否反映真实世界，
必须测**未经任何基准构造干预**的查询族：

  N1  CCL2018 原句（1100 条真实标注句，直接当查询用）
  N2  连贯文档语料 chunk 全文（data/corpus/chunks.jsonl，真实新闻/政府报告/鲁迅）
  N3  自然问句（从 N2 里取含隐喻触发词的长句做「自问」）—— 对照 N2

并对每个族报告 regime 分布与「通路是否非空」。这回答一个可证伪的问题：
如果自然文本的 Ω 也大面积 collapsed，则「查询侧可观测性低」是**中文自然语言
相对 774 词种子触发词词表的稀疏性**造成的，而不是评测构造造成的——两者
对 Ω 的实际用途（门控）含义完全不同。

运行：<python> experiments/exp4_natural_families.py
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

from metaphor_graph.observability import ObservabilityMeter  # noqa: E402
from metaphor_graph.data_loader import load_ccl2018            # noqa: E402
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology  # noqa: E402

OUT = os.path.join(HERE, "exp4_natural.json")
CORPUS_CHUNKS = os.path.join(ROOT, "data", "corpus", "chunks.jsonl")


def load_corpus_chunks():
    rows = []
    with open(CORPUS_CHUNKS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def family_stats(name, queries, meter):
    obs = [meter.measure(q) for q in queries]
    om = [o.omega for o in obs]
    reg = Counter(o.regime for o in obs)
    n = len(obs)
    d = S.describe(om)
    print(f"\n  【{name}】n={n}")
    print(f"    Ω: mean={d['mean']:.4f} sd={d['sd']:.4f} median={d['median']:.4f} "
          f"q25={d['q25']:.4f} q75={d['q75']:.4f} max={d['max']:.4f}")
    print(f"    Ω=0 占比 = {d['zero_frac']:.1%}")
    print(f"    regime: " + "  ".join(
        f"{k}={reg.get(k, 0)} ({reg.get(k, 0) / n:.1%})"
        for k in ("collapsed", "sparse", "dense")))
    print(f"    触发词命中：0 个 {sum(1 for o in obs if o.n_seed_triggers == 0)} "
          f"({sum(1 for o in obs if o.n_seed_triggers == 0) / n:.1%})；"
          f"≥1 个 {sum(1 for o in obs if o.n_seed_triggers >= 1)}；"
          f"≥2 个 {sum(1 for o in obs if o.n_seed_triggers >= 2)}")
    return dict(name=name, n=n, omega=om, regimes=dict(reg),
                n_seed=[o.n_seed_triggers for o in obs],
                len=[len(q) for q in queries])


def main():
    ont, n_frames = build_replay_ontology()
    meter = ObservabilityMeter(ont)
    print("=" * 92)
    print("Ω 实验 4：非构造查询族的 regime 分布")
    print("=" * 92)
    print(f"本体 {n_frames} 框架 / {len(ont._trigger_index)} 触发词 / "
          f"{len(ont.cascades)} 级联")

    samples = load_ccl2018()
    chunks = load_corpus_chunks()
    chunk_texts = [c["text"] for c in chunks]
    # N3：从 chunk 里按句切，取含触发词的自然句（模拟「用户拿原文里的一句来问」）
    import re
    sents = []
    for t in chunk_texts:
        for s in re.split(r"[。！？\n]", t):
            s = s.strip()
            if 8 <= len(s) <= 40:
                sents.append(s)
    sents_hit = [s for s in sents if any(x in s for x in ont._trigger_index)]
    sents_miss = [s for s in sents if not any(x in s for x in ont._trigger_index)]

    fams = {}
    fams["N1 CCL2018 原句（真实标注句）"] = [s.text for s in samples]
    fams["N2 连贯文档 chunk 全文"] = chunk_texts
    fams["N3a 文档句·含触发词"] = sents_hit[:3000]
    fams["N3b 文档句·不含触发词"] = sents_miss[:3000]

    print("\n" + "-" * 92)
    print("【1】各族 Ω 分布与 regime")
    print("-" * 92)
    res = {}
    for name, qs in fams.items():
        res[name] = family_stats(name, qs, meter)

    # 与两个构造族对照
    exp1 = json.load(open(os.path.join(HERE, "exp1_omega.json"),
                          encoding="utf-8"))["rows"]
    para = [r["omega_p"] for r in exp1]
    over = [r["omega_o"] for r in exp1]
    print("\n" + "-" * 92)
    print("【2】构造族对照（来自实验 1）")
    print("-" * 92)
    for name, om in (("C1 改写型（红线过滤后）", para),
                     ("C2 重叠型（触发词拼接）", over)):
        d = S.describe(om)
        print(f"\n  【{name}】n={len(om)}")
        print(f"    Ω: mean={d['mean']:.4f} median={d['median']:.4f} "
              f"Ω=0 占比={d['zero_frac']:.1%} max={d['max']:.4f}")

    # ==================================================== 核心对照
    print("\n" + "-" * 92)
    print("【3】核心对照：改写型 collapsed 率 vs 自然文本 collapsed 率")
    print("-" * 92)
    print(f"  {'族':34s} {'n':>6s} {'Ω=0':>8s} {'collapsed':>10s} "
          f"{'mean Ω':>8s} {'mean 长度':>9s}")
    for name, r in res.items():
        d = S.describe(r["omega"])
        print(f"  {name:34s} {r['n']:>6d} {d['zero_frac']:>8.1%} "
              f"{r['regimes'].get('collapsed', 0) / r['n']:>10.1%} "
              f"{d['mean']:>8.4f} {S.mean(r['len']):>9.1f}")
    for name, om, ln in (("C1 改写型（红线过滤后）", para, [len(r["paraphrase"]) for r in exp1]),
                         ("C2 重叠型（触发词拼接）", over, [len(r["overlap_query"]) for r in exp1])):
        d = S.describe(om)
        print(f"  {name:34s} {len(om):>6d} {d['zero_frac']:>8.1%} "
              f"{sum(1 for v in om if v == 0) / len(om):>10.1%} "
              f"{d['mean']:>8.4f} {S.mean(ln):>9.1f}")

    # 长度归一化对照：Ω 的完备度因子把长查询系统性压低
    print("\n  ⚠ 完备度因子的长度偏置：Ω = Ω_geo × (触发词覆盖字符/查询长度)，")
    print("     查询越长，同样数量的触发词命中 → 完备度越低 → Ω 越低。")
    print(f"  {'族':34s} {'mean 长度':>9s} {'mean comp':>10s} {'mean Ω_geo':>11s}")
    for name, qs in fams.items():
        obs = [meter.measure(q) for q in qs]
        print(f"  {name:34s} {S.mean([len(q) for q in qs]):>9.1f} "
              f"{S.mean([o.completeness for o in obs]):>10.4f} "
              f"{S.mean([o.omega_geo for o in obs]):>11.4f}")
    obs_p = [meter.measure(r["paraphrase"]) for r in exp1]
    print(f"  {'C1 改写型':34s} "
          f"{S.mean([len(r['paraphrase']) for r in exp1]):>9.1f} "
          f"{S.mean([o.completeness for o in obs_p]):>10.4f} "
          f"{S.mean([o.omega_geo for o in obs_p]):>11.4f}")

    # ==================================================== 结论
    print("\n" + "-" * 92)
    print("【4】结论")
    print("-" * 92)
    c_n2 = res["N2 连贯文档 chunk 全文"]["regimes"].get("collapsed", 0) / \
        res["N2 连贯文档 chunk 全文"]["n"]
    c_c1 = sum(1 for v in para if v == 0) / len(para)
    print(f"  改写型 collapsed = {c_c1:.1%}；文档 chunk 全文 collapsed = {c_n2:.1%}")
    if c_n2 > 0.5:
        print("  → 自然文本（真实新闻/政府报告/鲁迅）同样大面积 collapsed："
              "低 Ω 不是基准构造的专属产物，而是**774 词种子触发词表相对中文"
              "自然语言的长尾覆盖不足**这一本体层事实的查询侧投影")
    else:
        print("  → 自然文本 collapsed 率明显低于改写型：改写型的低 Ω 有相当部分"
              "来自基准构造（红线过滤禁用触发词）")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({k: dict(n=v["n"], regimes=v["regimes"],
                           mean_omega=S.mean(v["omega"]),
                           zero_frac=S.describe(v["omega"])["zero_frac"])
                   for k, v in res.items()}, f, ensure_ascii=False, indent=1)
    print(f"\n结果已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
