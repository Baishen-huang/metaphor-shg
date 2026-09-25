# -*- coding: utf-8 -*-
"""探查 6：分级可靠性前沿 + 独立证据（refine 缓存）交叉验证。

两个问题：

Q1 三级可靠性（curated / llm-frame / ephemeral）如果**允许**做门控，
    P1-召回前沿长什么样？（明确标注：这是 filter，仅作前沿参考，
    不构成本次交付的方案 —— 交付方案是软折扣。）

Q2 7 条字面误判句的边来自 discover 通道（skip_refine=True），
    **从不经过 refine**。refine 缓存里有真实 LLM 对同一
    (chunk, 源域, 目标域) 的判断 —— 直接查出来看它们是不是本来就会被否。
    这是与可靠性通道**独立**的证据链，用来判定「谁才真正压 P1」。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.llm_backend import load_table, LLMRefine, _refine_key

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIER = {"curated": 1.0, "llm-frame": 0.75, "ephemeral": 0.5}


def tier_of(ont, e):
    if not e.frame_id or ont.get_frame(e.frame_id) is None:
        return "ephemeral"
    return "llm-frame" if e.frame_id.startswith("F_LLM_") else "curated"


def main():
    cache = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
    table = load_table(cache)
    with open(cache + ".refine.json", "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    rtable = {tuple(k): (LLMRefine(**v) if v else None) for k, v in raw}

    class Tracked(TrackedBackend):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.missing = set()

        def refine(self, chunk, frame):
            if _refine_key(chunk, frame) not in self.refine_table:
                self.missing.add(_refine_key(chunk, frame))
            return super().refine(chunk, frame)

    backend = Tracked(table, None, rtable)
    ont = make_ontology(True, os.path.join(ROOT, "metaphor_graph",
                                           "llm_ontology_train.json"))
    samples = load_ccl2018()
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    rows = [(s, ex.extract(s.text, doc_id="e", chunk_id=f"e{i}"))
            for i, s in enumerate(samples)]

    # ---- Q1 三级前沿（filter 口径，仅参考）----
    print("=" * 78)
    print("Q1 分级可靠性门控前沿（**filter 口径**，非交付方案，仅作上界参考）")
    print("=" * 78)
    print(f"  {'保留层级':>28s} {'召回':>8s} {'P1':>8s} {'精确率':>8s} {'F1':>8s}")
    for keep, label in (
            ({"curated"}, "仅 curated"),
            ({"curated", "llm-frame"}, "curated + llm-frame"),
            ({"curated", "llm-frame", "ephemeral"}, "全保留（基线）")):
        tp = fp = tn = fn = 0
        for s, edges in rows:
            pred = bool([e for e in edges if tier_of(ont, e) in keep])
            if s.gold_metaphor:
                tp += pred; fn += (not pred)
            else:
                fp += pred; tn += (not pred)
        R = tp / (tp + fn) if (tp + fn) else 0.0
        P1 = fp / (fp + tn) if (fp + tn) else 0.0
        P = tp / (tp + fp) if (tp + fp) else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        print(f"  {label:>28s} {R:>8.3f} {P1:>8.3f} {P:>8.3f} {F:>8.3f}")

    # ---- Q2 refine 缓存交叉验证 ----
    print("\n" + "=" * 78)
    print("Q2 独立证据：FP 句的边若走 refine，会不会被否？（查真实 LLM 缓存）")
    print("=" * 78)
    n_fp = 0
    would_reject = 0
    cache_hit = 0
    for s, edges in rows:
        if s.gold_metaphor or not edges:
            continue
        n_fp += 1
        print(f"\nFP#{n_fp}: {s.text[:60]}")
        for e in edges:
            spec = ont.get_frame(e.frame_id or "")
            if spec is None:
                continue
            k = _refine_key(s.text, spec)
            if k in rtable:
                cache_hit += 1
                v = rtable[k]
                verdict = ("无记录(None)" if v is None else
                           f"is_metaphor={v.is_metaphor} conf={v.confidence}")
                if v is None or not v.is_metaphor:
                    would_reject += 1
                    mark = "→ refine 会否决 ✅"
                else:
                    mark = "→ refine 也判为隐喻 ❌"
                print(f"    {e.source_domain}→{e.target_domain}: {verdict} {mark}")
            else:
                print(f"    {e.source_domain}→{e.target_domain}: 缓存无此键"
                      f"（discover 通道 skip_refine，从未请求过）")

    print(f"\n  FP 句 {n_fp} 条；其边在 refine 缓存中命中 {cache_hit} 条，"
          f"其中会被否决 {would_reject} 条")
    print("  ⇒ 若命中且会否决，说明**真正能压 P1 的机制是 refine 校验**，"
          "而 discover 通道的 skip_refine=True 绕过了它。"
          "可靠性通道与这条证据链正交，不能替代它。")


if __name__ == "__main__":
    main()
