# -*- coding: utf-8 -*-
"""用 `evaluate_real.eval_split` 做**缓存重放**的 P1 基线复现（零 API）。

为什么要单独一个脚本
--------------------
直接跑 `python -m metaphor_graph.evaluate_real --use-llm ...` 在**无 API key**
的环境下会回落到 `LocalHeuristicBackend`（离线近似后端），而该后端
**不实现 `discover_batch`/`batch_refine`**，于是 `--llm-cache` 的缓存表
根本没被消费 —— 实测 P1 假性飙到 0.434、召回掉到 0.388。
这正是 README §7.1 警告过的「A3 消融必须隔离 refine」同一类陷阱。

本脚本用 `llm_backend.PrecomputedBackend` 把真实 DeepSeek 预取缓存
（discover + refine）直接喂给 `evaluate_real.eval_split`，
指标口径与 evaluate_real 逐位一致，但零 API 请求、可复现。
"""
from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_real import eval_split
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.llm_backend import load_table, LLMRefine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
ONT_JSON = os.path.join(ROOT, "metaphor_graph", "llm_ontology_train.json")


def main():
    samples = load_ccl2018()
    table = load_table(CACHE)
    with open(CACHE + ".refine.json", "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None)
                  for k, v in json.load(fh)}
    backend = TrackedBackend(table, None, rtable)
    ont = make_ontology(True, ONT_JSON)
    print(f"数据集 CCL2018(中文)  样本数={len(samples)}  "
          f"（中性 {sum(1 for s in samples if not s.gold_metaphor)} 句）")
    print(f"本体 LLM自举本体({len(ont.frames)}框架)")
    print(f"LLM 后端 PrecomputedBackend(缓存重放 {CACHE}，"
          f"discover {len(table)} 句 / refine {len(rtable)} 条，0 次请求)")

    r = eval_split(samples, ont, conf=0.35, use_semfield=True,
                   llm_backend=backend, llm_conf=0.85)
    print(f"\n[evaluate_real.eval_split 缓存重放]  n={len(samples)}")
    print(f"  TP={r['tp']}  FP={r['fp']}  TN={r['tn']}  FN={r['fn']}")
    print(f"  Precision={r['precision']:.3f}  Recall={r['recall']:.3f}  "
          f"F1={r['f1']:.3f}")
    print(f"  字面误判率(P1) = {r['literal_error_rate']:.3f}   "
          f"{'✅ <0.15 达标' if r['literal_error_rate'] < 0.15 else '⚠️ 未达标'}")

    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    for s in samples:
        ex.extract(s.text, doc_id="eval")
    print(f"  _type_rejects = {ex._type_rejects}")

    print(f"\n  [对照] 关掉 LLM 开放发现，**但 refine 校验照查表**"
          f"（A3 正确隔离口径）：")
    # 关键：不能把 llm_backend 设成 None —— extractor 把它解释为
    # 「未接后端 → 不做否定判断」，会**顺带关掉 refine**，两个变量一起变，
    # P1 假性从 0.092 飙到 0.434（README §7.1 警告过的陷阱）。
    refine_only = TrackedBackend({}, None, rtable)
    r0 = eval_split(samples, ont, conf=0.35, use_semfield=True,
                    llm_backend=refine_only)
    print(f"    Precision={r0['precision']:.3f}  Recall={r0['recall']:.3f}  "
          f"F1={r0['f1']:.3f}  P1={r0['literal_error_rate']:.3f}")
    print(f"    开放发现的召回边际贡献 = "
          f"{r['recall'] - r0['recall']:+.3f}"
          f"（{r['recall'] - r0['recall']:+.1%}，对齐 README 的 +55.8pp）")

    print(f"\n  [对照·错误口径，仅作警示] 直接 llm_backend=None：")
    r_bad = eval_split(samples, ont, conf=0.35, use_semfield=True,
                       llm_backend=None)
    print(f"    Recall={r_bad['recall']:.3f}  P1={r_bad['literal_error_rate']:.3f}"
          f"  ← refine 被顺带关掉，P1 假性飙高，**不可用于结论**")


if __name__ == "__main__":
    main()
