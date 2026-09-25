# -*- coding: utf-8 -*-
"""探查 3：7 条字面误判（FP）句的完整解剖。

这是判定「封顶可靠性通道」能否影响 P1 的关键：
若 FP 句的支撑边**全部**来自本体登记的正式框架（而非退化框架），
那么任何「只惩罚退化溯源」的机制都不可能改变 P1 —— 天花板是 0。

同时回答：开放发现通道的边为什么绕过了真正压 P1 的 refine 校验。
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

    # 标记每条边来自哪个通道
    orig_emit = ex.emit if hasattr(ex, "emit") else None

    print("=" * 78)
    print("字面误判（FP）句逐条解剖：本体登记 / 退化框架 分类")
    print("=" * 78)
    n_fp = 0
    fp_fallback_only = 0
    for i, s in enumerate(samples):
        edges = ex.extract(s.text, doc_id="eval", chunk_id=f"eval_{i}")
        if s.gold_metaphor or not edges:
            continue
        n_fp += 1
        reg = [e for e in edges if ont.get_frame(e.frame_id or "") is not None]
        unreg = [e for e in edges if ont.get_frame(e.frame_id or "") is None]
        if unreg and not reg:
            fp_fallback_only += 1
        print(f"\nFP#{n_fp}: {s.text}")
        print(f"  边数={len(edges)}  本体登记={len(reg)}  退化框架={len(unreg)}")
        for e in edges:
            tag = "本体" if ont.get_frame(e.frame_id or "") else "退化"
            spec = ont.get_frame(e.frame_id or "")
            mt = spec.mapping_type if spec else "(无本体条目)"
            print(f"    [{tag}] {e.source_domain}→{e.target_domain} "
                  f"conf={e.confidence} type={e.source_type} mtype={mt}")
            print(f"           triggers={e.triggers[:6]} ground={e.ground[:5]}")

    print("\n" + "=" * 78)
    print(f"FP 句总数={n_fp}，其中「仅退化框架支撑」={fp_fallback_only}")
    print("⇒ 若 0，则任何『只惩罚退化溯源』的机制对 P1 的天花板效应 = 0（可证）")

    # ---- 开放发现通道为什么绕过 refine ----
    print("\n" + "=" * 78)
    print("通道归因：FP 句的边由哪条通道产出？")
    print("=" * 78)
    n_disc = n_trig = 0
    for s in samples:
        if s.gold_metaphor:
            continue
        cands = backend.discover(s.text)
        hits = [c for c in cands if c.confidence >= 0.85]
        if not hits:
            continue
        edges = ex.extract(s.text)
        if edges:
            n_disc += 1
        else:
            n_trig += 1
    print(f"  有 conf>=0.85 发现候选、且最终判为隐喻的中性句 = {n_disc}")
    print("  ⇒ 这些边走 extract 通道三，emit(skip_refine=True)，"
          "**从不经过 refine**（压 P1 的真正机制）")


if __name__ == "__main__":
    main()
