# -*- coding: utf-8 -*-
"""探查 4：分级溯源可靠性的判别力 + P1 的「布尔天花板」。

关键结构事实（必须先证）：P1 = FP/(FP+TN) 是**句级布尔**指标
（`pred = bool(edges)`）。任何只在打分/排序层生效的软通道，
对 P1 的影响在数学上恒等于 0 —— 除非它改变「这句有没有边」。

因此本探查分两步：
  A) 分级溯源（curated / llm-bootstrapped / ephemeral）在 TP 与 FP 上的分布；
  B) 若按可靠性阈值过滤（这是 filter，会掉召回），P1 与召回的**上界/代价**。

分级：
  curated      内置/MetaNet/自举触发词的**人工设计**框架（种子本体）
  llm-frame    本体登记但由 LLM 自举沉淀的框架（F_LLM_*，占 98.6%）
  ephemeral    抽取器临时新建、本体无条目（真正的退化回退）

⚠️ 这里的 `llm-frame` 与 `curated` 的区分**仅用于诊断分层**（看自举沉淀
与人工种子的行为差异），**不是交付方案的分级**。交付方案 `provenance.py`
只有「本体登记 / 未登记」两级 —— 因为把自举沉淀的框架判为不可靠，
等于否定 P0 自举回流本身（它贡献了 L3 覆盖率与召回）。见 REPORT.md §2.2。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.llm_backend import load_table, LLMRefine


def classify(ont, e):
    if not e.frame_id:
        return "ephemeral"
    if ont.get_frame(e.frame_id) is None:
        return "ephemeral"
    return "llm-frame" if e.frame_id.startswith("F_LLM_") else "curated"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache = os.path.join(root, "data", "llm_cache_deepseek.json")
    table = load_table(cache)
    with open(cache + ".refine.json", "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None) for k, v in json.load(fh)}
    backend = TrackedBackend(table, None, rtable)
    ont = make_ontology(True, os.path.join(root, "metaphor_graph",
                                           "llm_ontology_train.json"))
    samples = load_ccl2018()
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)

    rows = [(s, ex.extract(s.text, doc_id="eval", chunk_id=f"eval_{i}"))
            for i, s in enumerate(samples)]

    n_cur = sum(1 for f in ont.frames if not f.startswith("F_LLM_"))
    print("=" * 78)
    print(f"本体框架分级：curated={n_cur}  llm-frame={len(ont.frames)-n_cur} "
          f"(占 {1-n_cur/len(ont.frames):.1%})")

    # ---- A) 分级分布 ----
    print("\nA) 句级最高可靠性分级（best = 该句所有边里最可信的一类）")
    order = {"curated": 2, "llm-frame": 1, "ephemeral": 0}
    best_tp = Counter(); best_fp = Counter()
    any_by_class_tp = Counter(); any_by_class_fp = Counter()
    for s, edges in rows:
        if not edges:
            continue
        cls = [classify(ont, e) for e in edges]
        best = max(cls, key=lambda c: order[c])
        (best_tp if s.gold_metaphor else best_fp)[best] += 1
        for c in set(cls):
            (any_by_class_tp if s.gold_metaphor else any_by_class_fp)[c] += 1
    print(f"  {'best 分级':12s} {'TP 句':>8s} {'FP 句':>8s}")
    for c in ("curated", "llm-frame", "ephemeral"):
        print(f"  {c:12s} {best_tp[c]:>8d} {best_fp[c]:>8d}")
    print(f"  合计          {sum(best_tp.values()):>8d} {sum(best_fp.values()):>8d}")

    # ---- B) 过滤上界（诚实标注：这是 filter，任务明确禁止作为方案）----
    print("\nB) 若按「最高可靠性 ≥ 某级」过滤（filter 口径，仅作上界参考）")
    print(f"  {'保留 curated+':>16s} {'召回':>8s} {'P1':>8s} {'精确率':>8s} {'F1':>8s}")
    for keep, label in ((["curated"], "curated"),
                        (["curated", "llm-frame"], "curated+llm-frame"),
                        (["curated", "llm-frame", "ephemeral"], "全保留(基线)")):
        tp = fp = tn = fn = 0
        for s, edges in rows:
            live = [e for e in edges if classify(ont, e) in keep]
            pred = bool(live)
            if s.gold_metaphor:
                tp += pred; fn += (not pred)
            else:
                fp += pred; tn += (not pred)
            # 不可达
        R = tp / (tp + fn) if (tp + fn) else 0.0
        P1 = fp / (fp + tn) if (fp + tn) else 0.0
        P = tp / (tp + fp) if (tp + fp) else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        print(f"  {label:>16s} {R:>8.3f} {P1:>8.3f} {P:>8.3f} {F:>8.3f}")

    # ---- C) 软通道对 P1 的天花板：结构性证明 ----
    print("\nC) 结构性证明：P1 是句级布尔指标")
    fp_all_fallback = sum(1 for s, e in rows
                          if not s.gold_metaphor and e
                          and all(classify(ont, x) == "ephemeral" for x in e))
    tp_all_fallback = sum(1 for s, e in rows
                          if s.gold_metaphor and e
                          and all(classify(ont, x) == "ephemeral" for x in e))
    n_fp = sum(1 for s, e in rows if not s.gold_metaphor and e)
    n_tp = sum(1 for s, e in rows if s.gold_metaphor and e)
    print(f"  FP 句中「全部边都是 ephemeral」= {fp_all_fallback}/{n_fp}")
    print(f"  TP 句中「全部边都是 ephemeral」= {tp_all_fallback}/{n_tp}")
    print(f"  ⇒ 只惩罚 ephemeral 的软通道对 P1 的天花板效应 = "
          f"{fp_all_fallback}/{n_fp} = {fp_all_fallback/max(1,n_fp):.1%}（分子为 0 即恒等于 0）")

    # ---- D) 分级置信度分布：软通道有没有排序判别力 ----
    print("\nD) 置信度 × 分级（软通道的排序判别力来源）")
    for c in ("curated", "llm-frame", "ephemeral"):
        confs = [e.confidence for s, edges in rows for e in edges
                 if classify(ont, e) == c]
        if confs:
            confs.sort()
            n = len(confs)
            print(f"  {c:12s} n={n:4d} 中位={confs[n//2]:.2f} "
                  f"min={confs[0]:.2f} max={confs[-1]:.2f}")


if __name__ == "__main__":
    main()
