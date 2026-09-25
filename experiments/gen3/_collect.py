# -*- coding: utf-8 -*-
"""gen3 数据收集：一次性把 635 条改写查询的**查询侧原始量** + **下游目标**落盘。

为什么要有这一层：gen1/gen2 的每个实验脚本各自重建一次图（110 伪文档 × 抽取），
重复且慢；而 gen3 要在同一批查询上比较十几个候选标量、还要接下游 MRR，
必须保证**所有实验看的是同一份行数据**（否则任何对照都可能被重建差异污染）。

行数据分三块（全部离线、$0）：
  A. 查询侧原始量：n_seed / n_frames / n_cascades / 直接与可达域数 / 涌现数
     / 流量权重 / 完备度 / Ω 及其分量（逐条记录，供事后任意重组）
  B. 中间目标：触发词级联通路是否非空（gen1/gen2 用的那个弱目标）
  C. 下游目标：**语义超图通路**（项目主通路，`score_conditions` 的 chunk 排序）
     对 LLM 金标的 MRR@10 / Hits@1,3,10 / Recall@10 —— 人工加权与自监督训练两档。
     这是 gen1/gen2 没测过的、有真实余量的端到端目标（MRR≈0.50 而非 1.000）。

产物：experiments/gen3/dataset_{rule}.json
运行：<python> experiments/gen3/_collect.py --rule source
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder              # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor              # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine                # noqa: E402
from metaphor_graph.data_loader import load_ccl2018                 # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                    # noqa: E402
    build_replay_ontology, build_replay_backend)
from metaphor_graph.evaluate_llmgold import (                       # noqa: E402
    build_queries_rich, filter_violations, _load_json, _chunk_of,
    GEN_CACHE, JUDGE_CACHE)
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits  # noqa: E402
from metaphor_graph.training import (build_training_set,            # noqa: E402
                                     MetaphorScorer)
from metaphor_graph.observability import matched_triggers           # noqa: E402
from metaphor_graph.query_signal import reachable_structure         # noqa: E402

DOC_SIZE, LLM_CONF = 10, 0.85
NPP = 3
RULES = ("json", "source", "metanet", "source_type", "none")


def out_path(rule: str) -> str:
    return os.path.join(HERE, f"dataset_{rule}.json")


def _recall(ranked, gold, k):
    top = {c for c, _ in ranked[:k]}
    g = set(gold)
    return len(g & top) / len(g) if g else 0.0


def collect(rule: str, verbose: bool = False) -> dict:
    """重建 110 伪文档并逐查询收集行数据。返回 {"rows": [...], "meta": {...}}。"""
    t0 = time.time()
    ont, n_frames_ont = build_replay_ontology(cascade_rule=rule)
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = _load_json(GEN_CACHE)
    judge = _load_json(JUDGE_CACHE)
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    rows, n_docs_used = [], 0
    live_domains_by_doc: dict = {}
    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=backend,
                                 orphan_cascade_rule="target").build(
                                     chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        n_docs_used += 1
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        chunk_order = {f"{did}_c{i}": i for i, _ in enumerate(chunk_texts)}
        centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                      for e in shg.edges}
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        # 本伪文档里「live 超边实际占用的域集合」—— 用于「计数 vs 身份」的
        # 零假设模拟（见 exp_g3_4）：级联通路的非空与否只取决于
        # 「查询可达域集合」与「live 边的域集合」是否相交。
        live_domains = sorted({d for e in eng.live_edges()
                               for d in (e.source_domain, e.target_domain)})
        live_domains_by_doc[did] = live_domains
        scorer = None
        try:
            ds = build_training_set(shg, chunk_order=chunk_order,
                                    chunks=chunk_map, centrality=centrality,
                                    ontology=ont, positive_mode="chunk",
                                    negatives_per_positive=NPP)
            if len(ds) > 0:
                scorer = MetaphorScorer().fit(ds)
        except Exception as exc:                        # 训练失败不该拖垮收集
            print(f"  [warn] doc {did} scorer 训练失败：{exc}")
        qs = filter_violations(build_queries_rich(shg, chunk_map, did), gen_cache)
        for q in qs:
            text = q["question"]
            st = reachable_structure(text, ont)
            from metaphor_graph.observability import measure
            o = measure(text, ont)
            res = eng.cross_domain_retrieve(text)
            # ---- C. 下游：语义超图通路对 LLM 金标的排序质量 ----
            gold_llm = judge.get(f"{did}|{text}", {})
            rel = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = sorted({_chunk_of(e) for e in shg.edges
                                  if e.id in rel and _chunk_of(e)})
            row = dict(
                doc_id=did, query=text, kind=q["kind"],
                # A. 查询侧原始量
                n_seed=len(st["triggers"]),
                n_frames=len(st["frames"]),
                n_cascades=len(st["cascades"]),
                n_cross_cascades=int(st["n_cross_cascades"]),
                n_members=len(st["members"]),
                n_direct_td=len(st["direct_targets"]),
                n_expanded_td=len(st["expanded_targets"]),
                n_emergent=len(st["emergent_targets"]),
                n_direct_dom=len(st["direct_domains"]),
                n_new_domains=len(st["new_domains"]),
                n_reach=len(st["reachable_domains"]),
                max_flow=max(o.flow_weights) if o.flow_weights else 0.0,
                n_flow=len(o.flow_weights),
                qlen=len(text),
                observed_chars=o.observed_chars,
                omega=o.omega, omega_geo=o.omega_geo, omega_e=o.omega_e,
                omega_n=o.omega_n, omega_f=o.omega_f, comp=o.completeness,
                # 集合身份（供零假设模拟：换掉「数多少」为「命中什么」）
                direct_domains=sorted(st["direct_domains"]),
                reachable_domains=sorted(st["reachable_domains"]),
                new_domains=sorted(st["new_domains"]),
                # B. 中间目标
                cascade_nonempty=1 if res.chunk_ids else 0,
                cascade_nhit=len(res.chunk_ids),
                # C. 下游目标
                has_gold=1 if gold_chunks else 0,
                n_gold=len(gold_chunks),
                mrr_hand=None, h1_hand=None, h3_hand=None, h10_hand=None,
                r10_hand=None, mrr_tr=None, h1_tr=None, h3_tr=None,
                h10_tr=None, r10_tr=None,
            )
            if gold_chunks and scorer is not None:
                ranked = score_conditions(eng, scorer, text)
                for tag, key in (("hand", "hand_weighted"), ("tr", "trained")):
                    m = _mrr_hits(ranked[key], gold_chunks)
                    row[f"mrr_{tag}"] = m["mrr"]
                    row[f"h1_{tag}"] = 1 if m["mrr"] == 1.0 else 0
                    row[f"h3_{tag}"] = m["hits@3"]
                    row[f"h10_{tag}"] = m["hits@10"]
                    row[f"r10_{tag}"] = _recall(ranked[key], gold_chunks, 10)
            rows.append(row)
        if verbose and di % 20 == 0:
            print(f"  doc {di}/{n_docs} rows={len(rows)} "
                  f"{time.time() - t0:.0f}s", flush=True)
    meta = dict(rule=rule, n_rows=len(rows), n_docs=n_docs_used,
                n_ontology_frames=n_frames_ont,
                n_ontology_cascades=len(ont.cascades),
                n_trigger_index=len(ont._trigger_index),
                doc_size=DOC_SIZE, llm_conf=LLM_CONF, npp=NPP,
                # 每伪文档的 live 域集合（零假设模拟用；110 个短列表，体积可忽略）
                live_domains={did: sorted(v) for did, v in live_domains_by_doc.items()},
                elapsed_s=round(time.time() - t0, 1))
    return dict(rows=rows, meta=meta)


def load_dataset(rule: str = "source", force: bool = False,
                 verbose: bool = False) -> dict:
    """读缓存；不存在（或 force）则重建。"""
    p = out_path(rule)
    if not force and os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    d = collect(rule, verbose=verbose)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", default="source", choices=RULES)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    d = load_dataset(args.rule, force=args.force, verbose=True)
    m = d["meta"]
    print(f"[{args.rule}] rows={m['n_rows']} docs={m['n_docs']} "
          f"frames={m['n_ontology_frames']} cascades={m['n_ontology_cascades']} "
          f"triggers={m['n_trigger_index']} 用时 {m['elapsed_s']}s")
    print(f"→ {out_path(args.rule)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
