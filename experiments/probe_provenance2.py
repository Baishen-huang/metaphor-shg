# -*- coding: utf-8 -*-
"""探查 2：退化溯源的两个子类 + 「诚实覆盖率」。

子类：
  (a) fallback-no-match  候选精确/模糊匹配都没命中任何本体框架 → 新建临时框架
  (b) fallback-type-reject  模糊匹配命中了框架，但 _type_coherent 判定类型不相干
      → 拒绑，退化为临时框架（这正是 _type_rejects 计的那 24 个）
(b) 是类型约束唯一有信息的类：若它集中在 FP 句里，封顶可靠性才有戏。

诚实覆盖率：现在的 100% 里有多少是 builder._ensure_cascades 事后补的
C_ADHOC_* 级联撑起来的？把「本体登记的框架 + 本体登记的级联」作为正式口径
重算一遍。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph.ablation import TrackedBackend, make_ontology
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.health import graph_health
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

    # 打补丁：把 _frame_for_candidate 的走法记下来，判断退化子类
    orig = MetaphorExtractor._frame_for_candidate
    marks = {}

    def patched(self, cand):
        # 复现原逻辑的分支判定，不改变返回值
        exact = self.ont.match_frame(cand.source_domain, cand.target_domain)
        f_fuzzy = self._fuzzy_match_frame(cand.source_domain, cand.target_domain)
        f_src = self._fuzzy_match_frame(cand.source_domain, cand.target_domain,
                                        require_target=False)
        f = orig(self, cand)
        if self.ont.get_frame(f.id) is not None:
            marks[f.id] = "ontology"
        elif f_fuzzy is not None or f_src is not None:
            marks[f.id] = "fallback-type-reject"
        else:
            marks[f.id] = "fallback-no-match"
        return f

    MetaphorExtractor._frame_for_candidate = patched
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    rows = []
    for i, s in enumerate(samples):
        edges = ex.extract(s.text, doc_id="eval", chunk_id=f"eval_{i}")
        rows.append((s, edges))
    MetaphorExtractor._frame_for_candidate = orig

    cnt = Counter()
    fp_by_class = Counter()
    tp_by_class = Counter()
    fp_sent = tp_sent = 0
    for s, edges in rows:
        if not edges:
            continue
        classes = {marks.get(e.frame_id, "?") for e in edges}
        for c in classes:
            cnt[c] += 1
        if s.gold_metaphor:
            tp_sent += 1
            for c in classes:
                tp_by_class[c] += 1
        else:
            fp_sent += 1
            for c in classes:
                fp_by_class[c] += 1

    print("=" * 78)
    print("1) 退化溯源子类（句级：该句至少有一条该类边）")
    for k in ("ontology", "fallback-no-match", "fallback-type-reject", "?"):
        if cnt[k]:
            print(f"  {k:24s} 句数={cnt[k]:4d}  "
                  f"TP句 {tp_by_class[k]:4d}/{tp_sent}  "
                  f"FP句 {fp_by_class[k]:4d}/{fp_sent}")
    print(f"  （_type_rejects 计数 = {ex._type_rejects}）")

    # ---- 诚实覆盖率 ----
    print("\n2) 覆盖率：现在报的 100% vs 只用本体登记框架/级联的诚实口径")
    pos = [s.text for s, edges in rows if edges]
    shg = MetaphorSHGBuilder(ontology=ont, llm_backend=backend).build(
        pos, doc_id="honest")
    h = graph_health(shg)
    n = len(shg.edges)
    reg_frame = sum(1 for e in shg.edges
                    if e.frame_id and ont.get_frame(e.frame_id) is not None)
    # 本体登记的框架 → 本体登记的级联
    def in_ont_cascade(e):
        if not e.frame_id or ont.get_frame(e.frame_id) is None:
            return False
        cid = ont.get_cascade(e.frame_id)
        return bool(cid) and cid in ont.cascades
    in_ont_cas = sum(1 for e in shg.edges if in_ont_cascade(e))
    ont_frame_ids = {f.id for f in shg.frames
                     if ont.get_frame(f.id) is not None}
    adhoc = [c for c in shg.cascades if c.id.startswith("C_ADHOC_")]
    print(f"  超边总数={n}")
    print(f"  报出的 hierarchy_coverage = {h.hierarchy_coverage:.3f} "
          f"(frame={h.frame_coverage:.3f} cascade={h.cascade_coverage:.3f})")
    print(f"  框架在本体中登记的边 = {reg_frame}/{n} = {reg_frame/n:.3f}")
    print(f"  框架+级联都在本体中的边 = {in_ont_cas}/{n} = {in_ont_cas/n:.3f}")
    print(f"  级联总数={len(shg.cascades)}，其中 C_ADHOC_ 事后补的={len(adhoc)}")
    print(f"  L2 框架数={len(shg.frames)}，其中本体登记={len(ont_frame_ids)}")


if __name__ == "__main__":
    main()
