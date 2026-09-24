# -*- coding: utf-8 -*-
"""全量 CCL2018 建图 —— A7/A8/A9 更大基准复验（路线图 §8.2 P1 项，零 API 费用）。

**为什么需要它**
A7/A8/A9 此前只在 2 文档 8 查询的「精选诊疗集」（eval_corpus.DOCS）上测过，
README §0.3/§7.3 明确标注「数字应读作机制可用，需更大检索集复验」。本脚本
用 LLM 缓存重放（data/llm_cache_deepseek.json，真实 DeepSeek 全量预取）在
**全部 1100 句**上建图，自动构造带金标的检索查询，复验三个结论：

  A7  自监督排序器是否仍输给人工加权（H5 不成立的「clue 单特征天花板」
      在更大候选池上是否依旧）；
  A9  去掉角色特征（same_frame/same_cascade/ground_jaccard）是否仍无差异；
  A8  自适应阈值在**更稠密**的图上是否开始有增益（小语料图稀疏时测不出）。

**金标构造方式（必须诚实声明）**
查询金标是 **by-construction**（构造即金标），不是人工标注：
  - Q_ext（扩展链查询）：查询取扩展超边的触发词拼接，金标 = 该链覆盖的全部
    chunk（扩展隐喻消歧的检索化：锚 chunk 的触发词应召回链上其它 chunk）；
  - Q_self（基础排序查询）：查询取单条 L1 边的触发词拼接，金标 = 该边所在
    chunk（排序任务：从全文档候选池里把它排到前面）；
  - Q_cas（级联查询，喂 A8）：金标 = 与查询边同框架的全部 chunk。
这继承 train_from_shg 的自监督口径——它测的是**排序器能否在干扰池中复原
抽取-建图时已建立的结构**，不测端到端抽取召回（那是 P1/§6.7 的职责）。
因此其结论只对「排序/阈值组件」有效，不能外推为系统级召回。

**伪文档分组（同样诚实声明）**
CCL2018 测试句无原生文档结构，按**连续 K 句**切成伪文档（默认 K=10）。
分组目的不是模拟真实文档，而是给 L1.5 扩展链提供合并空间、给排序提供
干扰池；跨框架 (frame, source_domain) + 喻底交集 + 间距<3 的合并判据
仍是真实语言信号，不随分组方式改变。

运行：
    python -m metaphor_graph.evaluate_fullcorpus                 # 默认 K=10
    python -m metaphor_graph.evaluate_fullcorpus --doc-size 8
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine, shg_density
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.training import (train_from_shg, FEATURE_NAMES,
                                     leakage_report, MetaphorScorer)
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits, ROLE_IDX
from metaphor_graph.llm_backend import load_table

DEFAULT_ONTOLOGY_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ontology_default.json")
DEFAULT_DISCOVER_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "llm_cache_deepseek.json")


# ---------------------------------------------------------------------------
# 复用本体清洗脚本里的重放后端与本体的组装逻辑（单一实现，避免漂移）
# ---------------------------------------------------------------------------
def build_replay_ontology(ontology_json: str = DEFAULT_ONTOLOGY_JSON):
    from metaphor_graph.ontology_clean import _build_variant
    with open(ontology_json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    ont, n_frames = _build_variant(payload["frames"], payload["cascades"],
                                   use_core_only=False)
    return ont, n_frames


def build_replay_backend(ont, discover_cache: str = DEFAULT_DISCOVER_CACHE):
    """discover/refine 全走真实 DeepSeek 缓存（重放），零 API 请求。"""
    from metaphor_graph.llm_backend import PrecomputedBackend, LocalHeuristicBackend
    from metaphor_graph.ontology_clean import _load_refine_table
    table = load_table(discover_cache)
    refine = _load_refine_table(discover_cache + ".refine.json")
    return PrecomputedBackend(table, LocalHeuristicBackend(ontology=ont),
                              refine_table=refine)


# ---------------------------------------------------------------------------
# 查询构造（by-construction 金标）
# ---------------------------------------------------------------------------
def chunk_ids_of(edge) -> List[str]:
    return sorted({s.chunk_id for s in edge.chunk_spans})


def build_queries(shg, ont) -> dict:
    """返回 {"q_ext": [(query, gold_set)], "q_self": [...], "q_cas": [...]}。"""
    q_ext, q_self, q_cas = [], [], []
    seen_ext: set = set()
    for e in shg.edges:
        trig = [t for t in e.triggers if t]
        if not trig:
            continue
        query = "，".join(dict.fromkeys(trig))
        if e.is_extended:
            gold = set(chunk_ids_of(e))
            if len(gold) >= 2 and query not in seen_ext:
                seen_ext.add(query)
                q_ext.append((query, gold))
        else:
            g = set(chunk_ids_of(e))
            q_self.append((query, g))
            # 级联查询：金标 = 同框架全部 chunk（含自身）
            if e.frame_id:
                cas_gold = set()
                for o in shg.edges:
                    if not o.is_extended and o.frame_id == e.frame_id:
                        cas_gold |= set(chunk_ids_of(o))
                if len(cas_gold) >= 2:
                    q_cas.append((query, cas_gold))
    return {"q_ext": q_ext, "q_self": q_self, "q_cas": q_cas}


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-size", type=int, default=10,
                    help="伪文档包含的连续句数（K）")
    ap.add_argument("--ontology", default=DEFAULT_ONTOLOGY_JSON,
                    help="本体 JSON（默认用清洗后的生产本体 ontology_default.json）")
    ap.add_argument("--discover-cache", default=DEFAULT_DISCOVER_CACHE)
    ap.add_argument("--llm-conf", type=float, default=0.85,
                    help="LLM 开放发现通道置信门槛（对齐 §6.7 达标配置）")
    ap.add_argument("--embedder", choices=("default", "ngram", "real"),
                    default="default",
                    help="real=用 EMBED_API_KEY 注入真实句向量（检索层专用）")
    ap.add_argument("--weak-refine", action="store_true",
                    help="附加 A7-weak 对照：排序器改用 refine 缓存的 LLM 弱监督"
                         "标签训练（build_weak_refine_set），检验 clue 泄漏天花板"
                         "是否被打破（P3 路线图「排序器收口」）。")
    args = ap.parse_args()

    from metaphor_graph import embeddings as _emb
    if args.embedder == "real":
        emb_real = _emb.embedder_from_env()
        if emb_real is None:
            raise SystemExit("需要 EMBED_API_KEY（见 embeddings.embedder_from_env）")
        _emb.set_embedder(emb_real, propagate=False)
        print(f"向量器：{emb_real.model}（真实句向量）")
    elif args.embedder == "ngram":
        _emb.set_embedder(_emb.NgramEmbedder(), propagate=False)
        print("向量器：NgramEmbedder")
    ont, n_frames = build_replay_ontology(args.ontology)
    backend = build_replay_backend(ont, args.discover_cache)
    samples = load_ccl2018()
    print("=" * 84)
    print(f"全量 CCL2018 建图 —— A7/A8/A9 更大基准复验（n={len(samples)} 句，"
          f"伪文档 K={args.doc_size}，本体 {n_frames} 框架）")
    print("=" * 84)

    k = args.doc_size
    n_docs = (len(samples) + k - 1) // k

    agg = {c: {"mrr": 0.0, "hits@3": 0, "hits@10": 0, "n": 0}
           for c in ("trained", "trained_no_role", "hand_weighted",
                     "trained_weak")}
    a8 = {"on_rec": 0.0, "off_rec": 0.0, "on_h3": 0, "off_h3": 0, "n": 0}
    n_q = {"q_ext": 0, "q_self": 0, "q_cas": 0}
    gstats = dict(docs_with_ext=0, total_edges=0, total_ext=0, dens=0.0,
                  docs_used=0, leak_flags=0, n_train_reports=0,
                  weak_leak_flags=0, weak_auc_clue=[], weak_stats=[])

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=args.llm_conf)
        builder = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=backend)
        shg = builder.build(chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        ext = [e for e in shg.edges if e.is_extended]
        gstats["total_edges"] += len(l1)
        gstats["total_ext"] += len(ext)
        if ext:
            gstats["docs_with_ext"] += 1
        if not l1:
            continue
        gstats["docs_used"] += 1
        gstats["dens"] += shg_density(shg)

        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        scorer, ds = train_from_shg(shg, chunk_order=chunk_order,
                                    chunks=chunk_map, ontology=ont)
        gstats["n_train_reports"] += 1
        gstats["leak_flags"] += len(leakage_report(ds))

        # A7-weak：refine 缓存弱监督排序器（可选对照）
        weak_scorer = None
        if args.weak_refine:
            from metaphor_graph.training import build_weak_refine_set, feature_auc
            ds_w, st = build_weak_refine_set(
                shg, chunk_order=chunk_order, chunks=chunk_map, ontology=ont,
                refine_path=args.discover_cache + ".refine.json")
            if len(ds_w) > 0:
                weak_scorer = MetaphorScorer().fit(ds_w)
                aucs = feature_auc(ds_w)
                if aucs.get("clue") == aucs.get("clue"):
                    gstats["weak_auc_clue"].append(aucs["clue"])
                gstats["weak_stats"].append(st)
                gstats["weak_leak_flags"] += len(leakage_report(ds_w))

        queries = build_queries(shg, ont)
        for typ, items in queries.items():
            n_q[typ] += len(items)
        # --- A7 / A9：排序质量（Q_ext + Q_self）---
        for query, gold in queries["q_ext"] + queries["q_self"]:
            gold_ids = sorted(gold)
            ranked_map = score_conditions(eng, scorer, query)
            if weak_scorer is not None:
                wk = score_conditions(eng, weak_scorer, query)
                ranked_map["trained_weak"] = wk["trained"]
            for cfg, ranked in ranked_map.items():
                m = _mrr_hits(ranked, gold_ids)
                agg[cfg]["mrr"] += m["mrr"]
                agg[cfg]["hits@3"] += m["hits@3"]
                agg[cfg]["hits@10"] += m["hits@10"]
                agg[cfg]["n"] += 1
        # --- A8：自适应阈值（Q_cas，跨域通路）---
        for query, gold in queries["q_cas"]:
            if not any(t in query for t in ont._trigger_index):
                continue
            on = eng.cross_domain_retrieve(query, adaptive=True).chunk_ids
            off = eng.cross_domain_retrieve(query, adaptive=False).chunk_ids
            for cid, onoff in ((on, "on"), (off, "off")):
                top10 = set(cid[:10])
                hit10 = len(gold & top10) / len(gold) if gold else 1.0
                a8[f"{onoff}_rec"] += hit10
                a8[f"{onoff}_h3"] += 1 if any(c in gold for c in cid[:3]) else 0
            a8["n"] += 1

    # ---- 汇总 ----
    print(f"\n图规模：使用 {gstats['docs_used']}/{n_docs} 个伪文档（其余无 L1 边），"
          f"L1 边 {gstats['total_edges']} 条，扩展边 {gstats['total_ext']} 条"
          f"（含扩展边文档 {gstats['docs_with_ext']} 个），"
          f"平均密度 Δ={gstats['dens'] / max(1, gstats['docs_used']):.3f}")
    print(f"查询数：Q_ext 扩展链={n_q['q_ext']}  Q_self 基础排序={n_q['q_self']}  "
          f"Q_cas 级联={n_q['q_cas']}")

    n = agg["trained"]["n"]
    print(f"\n【A7/A9】检索排序质量（MRR@10 / Hits@3 / Hits@10，n={n} 查询）")
    print(f"{'配置':26s} {'MRR@10':>9s} {'Hits@3':>8s} {'Hits@10':>9s}")
    for cfg, label in (("trained", "训练后(7维)"),
                       ("trained_weak", "训练后-LLM弱监督(A7-weak)"),
                       ("trained_no_role", "训练后-去角色特征(A9)"),
                       ("hand_weighted", "人工加权(A7关闭训练)")):
        a = agg[cfg]
        if a["n"] == 0:
            continue
        print(f"{label:26s} {a['mrr'] / a['n']:>9.3f} {a['hits@3'] / a['n']:>8.3f} "
              f"{a['hits@10'] / a['n']:>9.3f}")

    na = a8["n"]
    if na:
        print(f"\n【A8】自适应阈值（跨域通路 Recall@10，n={na} 级联查询）")
        print(f"  开阈值 {a8['on_rec'] / na:.3f}  vs  关阈值 {a8['off_rec'] / na:.3f}"
              f"   (Hits@3 {a8['on_h3'] / na:.3f} vs {a8['off_h3'] / na:.3f})")

    # ---- 结论 ----
    print("\n【结论】")
    t, hr, hw = agg["trained"], agg["trained_no_role"], agg["hand_weighted"]
    d7 = (t["mrr"] - hw["mrr"]) / n
    d9 = (t["mrr"] - hr["mrr"]) / n
    print(f"  A7 (训练 vs 人工加权): MRR@10 差 {d7:+.3f} → "
          f"{'H5 成立✅（训练有增益）' if d7 > 0.02 else
             ('与 2 文档结论一致：H5 不成立❌' if abs(d7) <= 0.02 else
              '训练反而更差（H5 不成立❌，与 2 文档结论一致）')}")
    print(f"  A9 (去角色特征):       MRR@10 差 {d9:+.3f} → "
          f"{'H7 有证据✅' if d9 > 0.02 else '与 2 文档结论一致：H7 不成立❌'}")
    if na:
        d8 = a8["on_rec"] / na - a8["off_rec"] / na
        print(f"  A8 (自适应阈值):       Recall@10 差 {d8:+.3f} → "
              f"{'阈值有增益✅' if d8 > 0.02 else
                 ('无差异（稠密图上仍测不出，A8 中性结论扩大到更大集）' if abs(d8) <= 0.02
                  else '关阈值更好 ⚠️ 需人工核查查询构造')}")
    print(f"  泄漏自检：{gstats['n_train_reports']} 个训练集中 "
          f"leakage_report 共标记 {gstats['leak_flags']} 处"
          f"（clue 单特征可分是已知自监督天花板，见 training.py docstring）")
    if args.weak_refine and gstats["weak_stats"]:
        import numpy as _np
        tot = {k: sum(st.get(k, 0) for st in gstats["weak_stats"])
               for k in ("pos", "neg_llm", "neg_random")}
        clue = gstats["weak_auc_clue"]
        clue_mean = sum(clue) / len(clue) if clue else float("nan")
        a7w = agg["trained_weak"]
        d7w = (a7w["mrr"] - agg["hand_weighted"]["mrr"]) / max(1, n)
        print(f"  A7-weak（refine 弱监督）：弱监督负样本 {tot['neg_llm']} 条"
              f"（随机负样本 {tot['neg_random']}），clue 平均 AUC {clue_mean:.3f}"
              f"（自监督为 ≈1.0），leakage 标记 {gstats['weak_leak_flags']} 处，"
              f"MRR@10 {a7w['mrr'] / max(1, a7w['n']):.3f}（vs 人工加权差 {d7w:+.3f}）")
    print("\n【诚实边界】金标为 by-construction（构造即金标），继承自 train_from_shg "
          "的自监督口径：结论只对排序/阈值组件有效，不测端到端抽取召回；"
          "伪文档为连续 K 句受控分组，非语料原生结构。")
    if args.embedder in ("real", "ngram"):
        _emb.set_embedder(None)
        print("向量器已恢复默认哈希编码")
    return 0


if __name__ == "__main__":
    sys.exit(main())
