# -*- coding: utf-8 -*-
"""gen2 实验 5：机制定位 —— 级联层影响指标的**唯一**通路是「cascade_id 是否为 None」。

实验 4 的关键异常：变体 A（生产现状）、B（本体级联/兜底关）、C（source 级联/兜底关）
三者的检索指标**逐位相同**（MRR 0.5025 / Hits@3 0.6044 / 级联通路 0.0417），
但覆盖率 B/C 只有 0.767（A 是 1.000）。而变体 D（cascade_id 全为 None）指标明显下降。

本实验把这条因果链拆开验证：

  H1  级联**结构**（成员分组）不影响任何检索指标 —— A/B/C 的 `edge.cascade_id`
      非空集合完全相同，故 `_centrality` 的 struct 特征、`same_cascade` 特征、
      检索的目标域扩展集都只受「非空/同 id」影响，不受分组质量影响。
  H2  级联**存在性**（非空）影响指标 —— 因为 `struct = 0.5*len(ground)
      + 0.5*[cascade_id 非空]`（`retrieval.py:73`、`training.py:76/107`），
      去掉级联归属等于给每条边减 0.5 的 struct 特征。
  H3  「同一 cascade_id」这个二值条件在现状下几乎等价于「同一 target_domain」
      （因为 99.2% 级联单一目标域）—— 所以 `same_cascade` 特征携带的信息
      与 `same_frame` 高度重叠，这是 A9（去角色特征）无差异的一个结构性解释。

逐档测量：cascade_id 非空边数 / struct 特征均值 / same_cascade 命中率 /
三条特征下 MRR。另加一个人工构造的「假级联」对照：给每条边发一个**唯一**的
cascade_id（全单例，结构上最退化但非空）→ 若指标与 A 一致，则 H2 得证。

产物：experiments/gen2/exp_g2_5_mechanism.json + stdout
运行：<python> experiments/gen2/exp_g2_5_mechanism.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine              # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.training import train_from_shg                # noqa: E402
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits  # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)
from metaphor_graph.evaluate_llmgold import (                     # noqa: E402
    build_queries_rich, filter_violations, _load_json, _chunk_of,
    GEN_CACHE, JUDGE_CACHE)
from metaphor_graph.ontology import CascadeSpec                   # noqa: E402

DOC_SIZE, LLM_CONF = 10, 0.85
OUT = os.path.join(HERE, "exp_g2_5_mechanism.json")


def unique_id_ontology(ont):
    """给每个框架发一个**唯一** cascade_id（全单例，但非空）—— H2 的判定对照。"""
    for fid in ont.frames:
        ont.cascades[f"SINGLE_{fid}"] = CascadeSpec(
            id=f"SINGLE_{fid}", name=f"SINGLE::{fid}", member_frames=[fid],
            discourse_domains=[], typical_triggers=[])
        ont._frame_to_cascade[fid] = f"SINGLE_{fid}"
    return ont


def run(label, ont_factory, samples, gen_cache, judge_cache, orphan_rule="none"):
    ont, n_frames = ont_factory()
    backend = build_replay_backend(ont)
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k

    n_l1 = n_with_cas = 0
    struct_vals, same_cas_hits, same_frame_hits = [], [], []
    n_cas_used = set()
    cas_target_multi = Counter()
    per_cfg = defaultdict(lambda: {"mrr": 0.0, "h3": 0.0, "n": 0})
    cross_rec, cross_n = 0.0, 0
    om, on = [], []

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=backend,
                                 orphan_cascade_rule=orphan_rule).build(
            chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        n_l1 += len(l1)
        n_with_cas += sum(1 for e in l1 if e.cascade_id)
        for e in l1:
            if e.cascade_id:
                n_cas_used.add(e.cascade_id)
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        for e in l1:
            struct_vals.append(eng._centrality.get(e.id, 0.0))
        # same_cascade vs same_frame 的同现率（A9 的结构性解释）
        for i, a in enumerate(l1):
            for b in l1[i + 1:]:
                if a.cascade_id and a.cascade_id == b.cascade_id:
                    same_cas_hits.append(1)
                    same_frame_hits.append(1 if a.frame_id == b.frame_id else 0)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        try:
            scorer, _ = train_from_shg(shg, chunk_order=chunk_order,
                                       chunks=chunk_map, ontology=ont)
        except Exception:
            scorer = None
        if scorer is None:
            continue
        qs = filter_violations(build_queries_rich(shg, chunk_map, did), gen_cache)
        for q in qs:
            o = __import__("metaphor_graph.observability", fromlist=["measure"]).measure(
                q["question"], ont)
            om.append(o.omega)
            on.append(o.omega_n)
            gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gch = {_chunk_of(e) for e in shg.edges if e.id in rel and _chunk_of(e)}
            if not gch:
                continue
            cross = eng.cross_domain_retrieve(q["question"]).chunk_ids
            cross_rec += len(gch & set(cross[:10])) / len(gch)
            cross_n += 1
            for cfg, ranked in score_conditions(eng, scorer, q["question"]).items():
                m = _mrr_hits(ranked, sorted(gch))
                a = per_cfg[cfg]
                a["mrr"] += m["mrr"]
                a["h3"] += m["hits@3"]
                a["n"] += 1

    nom = max(1, len(om))
    return dict(
        label=label, n_l1=n_l1, n_with_cascade_id=n_with_cas,
        frac_with_cascade_id=n_with_cas / max(1, n_l1),
        n_distinct_cascades_used=len(n_cas_used),
        struct_mean=sum(struct_vals) / max(1, len(struct_vals)),
        struct_with_cas_mean=(sum(v for v in struct_vals if v > 0.5)
                              / max(1, sum(1 for v in struct_vals if v > 0.5))),
        same_cascade_pair_hit=sum(same_cas_hits),
        same_cascade_implies_same_frame=(
            sum(same_frame_hits) / max(1, len(same_frame_hits))),
        per_cfg={k: {kk: (vv / max(1, v["n"]) if kk != "n" else vv)
                     for kk, vv in v.items()} for k, v in per_cfg.items()},
        cross_path_recall=cross_rec / max(1, cross_n), cross_n=cross_n,
        omega=dict(mean=sum(om) / nom, zero_frac=sum(1 for v in om if v == 0) / nom,
                   omega_n_mean=sum(on) / nom,
                   omega_n_pos_frac=sum(1 for v in on if v > 0) / nom),
    )


def main():
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)
    print("=" * 100)
    print("gen2 实验 5：机制定位 —— cascade_id 的「存在性」而非「结构」在起作用")
    print("=" * 100)

    variants = [
        ("A 本体级联(json)+兜底",
         lambda: build_replay_ontology(cascade_rule="json"), "target"),
        ("B 本体级联(json)，兜底关",
         lambda: build_replay_ontology(cascade_rule="json"), "none"),
        ("C source 级联，兜底关",
         lambda: build_replay_ontology(cascade_rule="source"), "none"),
        ("E 全单例级联（唯一 id，非空）",
         lambda: (unique_id_ontology(
             build_replay_ontology(cascade_rule="json")[0]), 2209), "none"),
        ("D 无级联", lambda: build_replay_ontology(cascade_rule="none"), "none"),
    ]
    out = {}
    for label, fac, orph in variants:
        r = run(label, fac, samples, gen_cache, judge_cache, orphan_rule=orph)
        out[label] = r
        hw, tr = r["per_cfg"].get("hand_weighted", {}), r["per_cfg"].get("trained", {})
        print(f"\n[{label}]")
        print(f"  cascade_id 非空 {r['n_with_cascade_id']}/{r['n_l1']}"
              f" = {r['frac_with_cascade_id']:.3f}"
              f"  用到的 distinct 级联 {r['n_distinct_cascades_used']}")
        print(f"  struct 特征均值 {r['struct_mean']:.4f}")
        print(f"  same_cascade 配对命中 {r['same_cascade_pair_hit']}"
              f"  其中同框架占比 {r['same_cascade_implies_same_frame']:.3f}"
              f"  ← same_cascade 的增量信息 = 1−该值")
        if hw:
            print(f"  语义超图(人工加权) MRR={hw['mrr']:.4f} Hits@3={hw['h3']:.4f}")
        if tr:
            print(f"  语义超图(训练后)   MRR={tr['mrr']:.4f} Hits@3={tr['h3']:.4f}")
        print(f"  级联通路 Recall@10={r['cross_path_recall']:.4f} (n={r['cross_n']})")
        o = r["omega"]
        print(f"  Ω mean={o['mean']:.4f}  Ω_N mean={o['omega_n_mean']:.4f}"
              f"  Ω_N>0 {o['omega_n_pos_frac']:.1%}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
