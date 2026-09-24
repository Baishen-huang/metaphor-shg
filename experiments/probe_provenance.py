# -*- coding: utf-8 -*-
"""探查：退化溯源（F_LLM_* 回退框架）在真实评测集上是否携带判别信息。

⚠️ **本脚本的判据是错的，已被 probe_provenance2.py 取代 —— 保留作反面教材。**
它按 `F_LLM_` **前缀**判定「回退框架」，但 `llm_ontology.py:201` 用
`_stable_id("F_LLM", s, t)` 给**自举沉淀的正式框架**也起了这个前缀，
于是生产本体 2177 个框架**全部**被误判为退化（本日志里 "回退框架 90.5%"
就是这么来的，真实值是 22.4%）。
正确判据是 `ontology.get_frame(fid) is not None`（本体有无条目）。
结论请看 `probe_provenance2.log` 与本目录 REPORT.md §2.2。

---- 以下为原说明 ----

要回答三个问题（决定「封顶可靠性通道」是否有戏）：
  1. 每句产出的超边里，多少挂在正式框架、多少挂在 F_LLM_* 回退框架？
  2. FP（字面误判）句 与 TP（隐喻命中）句 的框架来源分布是否不同？
  3. FP 句里「只由回退框架支撑」的占比多少 —— 这决定封顶可靠性
     能不能在不掉召回的前提下压住 P1。

离线、零 API：全部走缓存重放。
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


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    cache = os.path.join(root, "data", "llm_cache_deepseek.json")
    rcache = cache + ".refine.json"
    onto = os.path.join(root, "metaphor_graph", "llm_ontology_train.json")

    table = load_table(cache)
    with open(rcache, "r", encoding="utf-8") as fh:
        rtable = {tuple(k): (LLMRefine(**v) if v else None)
                  for k, v in json.load(fh)}
    backend = TrackedBackend(table, None, rtable)
    ont = make_ontology(True, onto)
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    samples = load_ccl2018()

    stats = Counter()
    fp_only_fallback = 0
    tp_only_fallback = 0
    fp_total = tp_total = 0
    fallback_conf = []
    ontology_conf = []
    fp_conf = []
    tp_conf = []

    for s in samples:
        edges = ex.extract(s.text)
        pred = bool(edges)
        if not edges:
            continue
        fb = [e for e in edges if e.frame_id and e.frame_id.startswith("F_LLM_")]
        on = [e for e in edges if not (e.frame_id or "").startswith("F_LLM_")]
        for e in fb:
            fallback_conf.append(e.confidence)
        for e in on:
            ontology_conf.append(e.confidence)
        if s.gold_metaphor:
            tp_total += 1
            tp_conf.append(max(e.confidence for e in edges))
            if fb and not on:
                tp_only_fallback += 1
        else:
            fp_total += 1
            fp_conf.append(max(e.confidence for e in edges))
            if fb and not on:
                fp_only_fallback += 1
        stats["edges"] += len(edges)
        stats["edges_fallback"] += len(fb)
        stats["edges_ontology"] += len(on)

    def desc(name, xs):
        if not xs:
            print(f"  {name}: 无样本")
            return
        xs = sorted(xs)
        n = len(xs)
        print(f"  {name}: n={n}  min={xs[0]:.2f} p25={xs[n//4]:.2f} "
              f"中位={xs[n//2]:.2f} p75={xs[3*n//4]:.2f} max={xs[-1]:.2f}")

    print("=" * 78)
    print("1) 超边来源分布（全测试集）")
    print(f"  超边总数={stats['edges']}  回退框架={stats['edges_fallback']} "
          f"({stats['edges_fallback']/max(1,stats['edges']):.1%})  "
          f"正式框架={stats['edges_ontology']}")
    print("\n2) 置信度分布")
    desc("回退框架边", fallback_conf)
    desc("正式框架边", ontology_conf)
    print("\n3) 句级：命中句最高置信度")
    desc("TP 句", tp_conf)
    desc("FP 句", fp_conf)

    print("\n4) 结构判别力：句子的支撑来源")
    print(f"  TP 句 n={tp_total}，其中「仅回退框架支撑」={tp_only_fallback} "
          f"({tp_only_fallback/max(1,tp_total):.1%})")
    print(f"  FP 句 n={fp_total}，其中「仅回退框架支撑」={fp_only_fallback} "
          f"({fp_only_fallback/max(1,fp_total):.1%})")
    print("\n  ⇒ 若给「仅回退框架支撑」的句子加封顶，"
          f"最坏情形掉召回 {tp_only_fallback/max(1,tp_total):.1%}、"
          f"最多压 P1 {fp_only_fallback/max(1,fp_total):.1%}")


if __name__ == "__main__":
    main()
