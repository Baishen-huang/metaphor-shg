# -*- coding: utf-8 -*-
"""Ω 实验 1：分布分离（改写型 vs 重叠型）+ 级联通路成功相关 + regime 分布。

全部离线、$0：本体重放（ontology_default.json）+ LLM 缓存重放
（data/llm_cache_paraphrase.json 改写、data/llm_cache_judge.json 金标），
零 API 请求。复刻 evaluate_llmgold.main() 的建图与查询构造口径。

产物：experiments/exp1_omega.json（逐查询明细）+ stdout 汇总。

运行（在 .wt/omega 下）：
    <python> experiments/exp1_omega_distribution.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
logging.disable(logging.CRITICAL)

import _stats as S  # noqa: E402

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine              # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.observability import ObservabilityMeter       # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)
from metaphor_graph.evaluate_llmgold import (                     # noqa: E402
    build_queries_rich, filter_violations, _load_json, _chunk_of,
    GEN_CACHE, JUDGE_CACHE)

DOC_SIZE = 10
LLM_CONF = 0.85
OUT = os.path.join(HERE, "exp1_omega.json")


def build_world():
    """复刻 evaluate_llmgold.main() 的建图（重放，零请求）。"""
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    docs, all_queries = {}, []
    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        docs[did] = dict(shg=shg, chunks=chunk_texts,
                         eng=RetrievalEngine(shg, chunk_texts, doc_id=did,
                                             ontology=ont),
                         chunk_map=chunk_map)
        qs = build_queries_rich(shg, chunk_map, did)
        for q in qs:
            q["doc_id"] = did
        all_queries.extend(qs)
        docs[did]["questions"] = qs
    return ont, n_frames, docs, all_queries


def recall_at_k(ranked, gold, k=10):
    if not gold:
        return None
    return len(set(ranked[:k]) & gold) / len(gold)


def main():
    ont, n_frames, docs, all_queries = build_world()
    meter = ObservabilityMeter(ont)
    gen_cache = _load_json(GEN_CACHE)
    judge_cache = _load_json(JUDGE_CACHE)

    n_l1 = sum(len([e for e in d["shg"].edges if not e.is_extended])
               for d in docs.values())
    print("=" * 92)
    print(f"Ω 实验 1：查询侧可观测性分布与级联通路失败归因")
    print("=" * 92)
    print(f"世界：{len(docs)} 伪文档 / {n_l1} 条 L1 边 / 本体 {n_frames} 框架 "
          f"/ {len(ont._trigger_index)} 触发词 / {len(ont.cascades)} 级联")
    print(f"缓存：改写 {len(gen_cache)} 条，judge 金标 {len(judge_cache)} 条")
    print(f"查询池：{len(all_queries)} 条自动查询（ext "
          f"{sum(1 for q in all_queries if q['kind'] == 'ext')}）")

    # ---- 复刻 evaluate_llmgold.main() 的查询构造 ----
    kept = filter_violations([dict(q) for q in all_queries], gen_cache)
    print(f"红线过滤后改写查询：{len(kept)}")

    rows = []
    for q in kept:
        did = q["doc_id"]
        d = docs[did]
        gold_llm = judge_cache.get(f"{did}|{q['question']}", {})
        rel_edges = {eid for eid, v in gold_llm.items() if v == 1}
        gold_chunks = {_chunk_of(e) for e in d["shg"].edges
                       if e.id in rel_edges and _chunk_of(e)}
        if not gold_chunks:
            continue        # 与 stage_eval 同口径：无 LLM 金标 chunk 不计入

        para = q["question"]
        over = q["query"]

        # --- 三条通路（与 stage_eval 逐字同口径）---
        cross = d["eng"].cross_domain_retrieve(para, semantic_fallback=False).chunk_ids
        literal = [f"{did}_c{i}" for i, c in enumerate(d["chunks"])
                   if para in c]
        cross_over = d["eng"].cross_domain_retrieve(over, semantic_fallback=False).chunk_ids
        literal_over = [f"{did}_c{i}" for i, c in enumerate(d["chunks"])
                        if over in c]

        mp = meter.measure(para)
        mo = meter.measure(over)
        rows.append(dict(
            doc_id=did, kind=q["kind"], overlap_query=over, paraphrase=para,
            n_gold=len(gold_chunks),
            # 改写型
            omega_p=mp.omega, omega_geo_p=mp.omega_geo, omega_e_p=mp.omega_e,
            omega_n_p=mp.omega_n, omega_f_p=mp.omega_f, comp_p=mp.completeness,
            regime_p=mp.regime, n_seed_p=mp.n_seed_triggers,
            n_frames_p=mp.n_activated_frames,
            trig_p=list(mp.matched_triggers),
            cascade_recall_p=recall_at_k(cross, gold_chunks),
            literal_recall_p=recall_at_k(literal, gold_chunks),
            cascade_hit_p=bool(set(cross[:10]) & gold_chunks),
            cascade_nonempty_p=bool(cross),
            # 重叠型（同一查询对象的触发词拼接）
            omega_o=mo.omega, omega_geo_o=mo.omega_geo, omega_e_o=mo.omega_e,
            omega_n_o=mo.omega_n, omega_f_o=mo.omega_f, comp_o=mo.completeness,
            regime_o=mo.regime, n_seed_o=mo.n_seed_triggers,
            n_frames_o=mo.n_activated_frames,
            cascade_recall_o=recall_at_k(cross_over, gold_chunks),
            cascade_hit_o=bool(set(cross_over[:10]) & gold_chunks),
        ))

    n = len(rows)
    print(f"评测查询（有 LLM 金标 chunk）：n={n}"
          f"（论文上报 n=632，缓存重放可复现 {n} 条）")

    # =================================================== 通路复现
    print("\n" + "-" * 92)
    print("【0】通路召回复现（确认 0.042 失败可复现）")
    print("-" * 92)
    for name, key in (("触发词级联通路（改写型）", "cascade_recall_p"),
                      ("字面包含通路（改写型）", "literal_recall_p"),
                      ("触发词级联通路（重叠型）", "cascade_recall_o")):
        vals = [r[key] for r in rows if r[key] is not None]
        print(f"  {name:26s} Recall@10 = {S.mean(vals):.4f}  (n={len(vals)})")

    # =================================================== 分布分离
    print("\n" + "-" * 92)
    print("【1】Ω 分布：改写型 vs 重叠型")
    print("-" * 92)
    op = [r["omega_p"] for r in rows]
    oo = [r["omega_o"] for r in rows]
    dp, do = S.describe(op), S.describe(oo)
    print(f"{'':10s} {'n':>5s} {'mean':>8s} {'sd':>7s} {'median':>8s} "
          f"{'q25':>7s} {'q75':>7s} {'=0 占比':>9s} {'max':>7s}")
    for label, d in (("改写型", dp), ("重叠型", do)):
        print(f"{label:10s} {d['n']:>5d} {d['mean']:>8.4f} {d['sd']:>7.4f} "
              f"{d['median']:>8.4f} {d['q25']:>7.4f} {d['q75']:>7.4f} "
              f"{d['zero_frac']:>9.1%} {d['max']:>7.4f}")

    u, z, p_mwu = S.mann_whitney(op, oo)
    z_w, p_w, n_nz = S.wilcoxon_paired(op, oo)
    print(f"\n  独立样本 Mann-Whitney U={u:.1f} z={z:.3f} p={p_mwu:.3e}（双尾，并列修正）")
    print(f"  配对 Wilcoxon z={z_w:.3f} p={p_w:.3e}（n_nonzero={n_nz}）")
    print(f"  Cliff's δ = {S.cliffs_delta(op, oo):.4f}   "
          f"AUC(P(Ω_改 < Ω_重)) = {S.auc(op, oo):.4f}")
    print(f"  Spearman ρ(改写, 重叠) = {S.spearman(op, oo)[0]:.4f}")
    d_mean = dp['mean'] - do['mean']
    pooled = S.stdev(op + oo)
    print(f"  均值差 = {d_mean:+.4f}；Cohen's d = {d_mean / pooled:.3f}（合并 sd={pooled:.4f}）")

    # ---- 分量分解（分离由哪个分量造成？）----
    print("\n  分量分解（均值）：")
    print(f"  {'分量':16s} {'改写型':>10s} {'重叠型':>10s} {'差':>10s} {'AUC':>7s}")
    for label, kp, ko in (("Ω_E 边激活", "omega_e_p", "omega_e_o"),
                          ("Ω_N 涌现", "omega_n_p", "omega_n_o"),
                          ("Ω_F 流量熵", "omega_f_p", "omega_f_o"),
                          ("观测完备度", "comp_p", "comp_o"),
                          ("Ω_geo", "omega_geo_p", "omega_geo_o")):
        a = [r[kp] for r in rows]
        b = [r[ko] for r in rows]
        print(f"  {label:16s} {S.mean(a):>10.4f} {S.mean(b):>10.4f} "
              f"{S.mean(a) - S.mean(b):>+10.4f} {S.auc(a, b):>7.4f}")

    # ---- 自批判：分离有多少是「构造性必然」？----
    print("\n" + "-" * 92)
    print("【2】自批判：分离有多少是构造性必然（红线过滤直接删触发词）？")
    print("-" * 92)
    zero_p = sum(1 for v in op if v == 0.0)
    zero_o = sum(1 for v in oo if v == 0.0)
    print(f"  Ω=0 占比：改写型 {zero_p}/{n} = {zero_p / n:.1%}；"
          f"重叠型 {zero_o}/{n} = {zero_o / n:.1%}")
    print("  （改写型的 Ω=0 ⟺ 查询无任何本体触发词 ⟺ 级联通路必然空手而归："
          "这是定义性等价，不是发现）")

    # 条件分布：仅在 Ω>0 的查询上比较
    cond = [r for r in rows if r["omega_p"] > 0 and r["omega_o"] > 0]
    if cond:
        a = [r["omega_p"] for r in cond]
        b = [r["omega_o"] for r in cond]
        print(f"\n  条件化（两侧 Ω>0，n={len(cond)}）：改写型 mean={S.mean(a):.4f} "
              f"median={S.median(a):.4f}；重叠型 mean={S.mean(b):.4f} "
              f"median={S.median(b):.4f}")
        print(f"    AUC={S.auc(a, b):.4f}  δ={S.cliffs_delta(a, b):+.4f}  "
              f"MWU p={S.mann_whitney(a, b)[2]:.3e}")

    # 控制种子触发词数：改写型中「有触发词」的子集 vs 重叠型中相同词数的子集
    print("\n  按种子触发词数分层的 Ω 均值（改写型 / 重叠型）：")
    byseed = defaultdict(lambda: ([], []))
    for r in rows:
        byseed[r["n_seed_p"]][0].append(r["omega_p"])
        byseed[r["n_seed_o"]][1].append(r["omega_o"])
    for k in sorted(byseed)[:8]:
        a, b = byseed[k]
        print(f"    n_seed={k}: 改写 n={len(a):4d} mean={S.mean(a):.4f} | "
              f"重叠 n={len(b):4d} mean={S.mean(b):.4f}")

    # 控制「种子触发词数」的配对比较：只在同词数内比 Ω
    print("\n  同词数配对的 Ω 比较（n_seed 相同才配对，控制词数混杂）：")
    pairs_p, pairs_o = [], []
    by_seed_p = defaultdict(list)
    for r in rows:
        by_seed_p[r["n_seed_p"]].append(r)
    for k, grp in sorted(by_seed_p.items()):
        a = [r["omega_p"] for r in grp]
        b = [r["omega_o"] for r in grp if r["n_seed_o"] == k]
        if len(a) >= 5 and len(b) >= 5:
            print(f"    n_seed={k}: 改写 mean={S.mean(a):.4f} (n={len(a)}) | "
                  f"重叠 mean={S.mean(b):.4f} (n={len(b)})")
        pairs_p.extend(a)
        pairs_o.extend(b)
    if pairs_p and pairs_o:
        print(f"    合并：改写 mean={S.mean(pairs_p):.4f} (n={len(pairs_p)}) | "
              f"重叠 mean={S.mean(pairs_o):.4f} (n={len(pairs_o)})  "
              f"AUC={S.auc(pairs_p, pairs_o):.4f}")

    # =================================================== 级联失败归因
    print("\n" + "-" * 92)
    print("【3】低 Ω 是否预测级联通路失败？")
    print("-" * 92)
    succ = [1 if r["cascade_hit_p"] else 0 for r in rows]
    print(f"  改写型级联通路成功率（Hits@10）= {sum(succ)}/{n} = {sum(succ) / n:.4f}")
    r_pb, p_pb, _ = S.point_biserial(succ, op)
    rho, p_rho, _ = S.spearman(op, succ)
    print(f"  Ω × 成功：点二列 r={r_pb:.4f} p={p_pb:.3e}；"
          f"Spearman ρ={rho:.4f} p={p_rho:.3e}")
    a = [r["omega_p"] for r in rows if r["cascade_hit_p"]]
    b = [r["omega_p"] for r in rows if not r["cascade_hit_p"]]
    print(f"  成功组 Ω mean={S.mean(a):.4f} median={S.median(a):.4f} (n={len(a)}) | "
          f"失败组 Ω mean={S.mean(b):.4f} median={S.median(b):.4f} (n={len(b)})")
    print(f"  AUC(成功 > 失败) = {S.auc(a, b):.4f}")

    # 门控视角：Ω=0 门控的混淆矩阵
    print("\n  门控混淆矩阵（Ω>0 放行，Ω=0 阻断）——改写型：")
    tp = sum(1 for r in rows if r["omega_p"] > 0 and r["cascade_hit_p"])
    fp = sum(1 for r in rows if r["omega_p"] > 0 and not r["cascade_hit_p"])
    fn = sum(1 for r in rows if r["omega_p"] == 0 and r["cascade_hit_p"])
    tn = sum(1 for r in rows if r["omega_p"] == 0 and not r["cascade_hit_p"])
    print(f"    放行且成功 TP={tp}  放行但失败 FP={fp}  "
          f"阻断但会成功 FN={fn}  阻断且失败 TN={tn}")
    print(f"    门控召回（成功中被放行的比例）= {tp / max(1, tp + fn):.4f}；"
          f"阻断精度 = {tn / max(1, tn + fn):.4f}")
    print(f"    → 门控只能拦住「本来就零收益」的查询，"
          f"拦不住 {fp} 条『有激活但级联仍失败』的查询")

    # 非平凡测试：仅 Ω>0 子集内，Ω 是否仍预测成功？
    sub = [r for r in rows if r["omega_p"] > 0]
    if sub:
        su = [1 if r["cascade_hit_p"] else 0 for r in sub]
        so = [r["omega_p"] for r in sub]
        rr, pp, _ = S.point_biserial(su, so)
        rho2, pp2, _ = S.spearman(so, su)
        print(f"\n  **非平凡子集**（Ω>0，n={len(sub)}，"
              f"成功率 {sum(su) / len(sub):.4f}）：")
        print(f"    点二列 r={rr:.4f} p={pp:.3e}；Spearman ρ={rho2:.4f} p={pp2:.3e}")
        aa = [r["omega_p"] for r in sub if r["cascade_hit_p"]]
        bb = [r["omega_p"] for r in sub if not r["cascade_hit_p"]]
        print(f"    成功组 Ω mean={S.mean(aa):.4f} median={S.median(aa):.4f} "
              f"(n={len(aa)}) | 失败组 mean={S.mean(bb):.4f} "
              f"median={S.median(bb):.4f} (n={len(bb)})")
        print(f"    AUC = {S.auc(aa, bb):.4f}  MWU p={S.mann_whitney(aa, bb)[2]:.3e}")
        # 按 Ω 分箱看成功率（单调性）
        print(f"    按 Ω 分箱的成功率（检验是否单调）：")
        edges = [0.0, 1e-9, 0.05, 0.15, 0.3, 0.5, 1.01]
        for lo, hi in zip(edges[:-1], edges[1:]):
            grp = [r for r in sub if lo < r["omega_p"] <= hi]
            if not grp:
                continue
            hit = sum(1 for r in grp if r["cascade_hit_p"])
            print(f"      ({lo:.2f}, {hi:.2f}]  n={len(grp):4d}  "
                  f"成功率={hit / len(grp):.4f}  "
                  f"mean Ω={S.mean([r['omega_p'] for r in grp]):.4f}")

    # 重叠型对照（级联通路在重叠型上应该好得多）
    succ_o = [1 if r["cascade_hit_o"] else 0 for r in rows]
    r_pb_o, p_pb_o, _ = S.point_biserial(succ_o, oo)
    print(f"\n  对照·重叠型：成功率 {sum(succ_o)}/{n} = {sum(succ_o) / n:.4f}；"
          f"Ω×成功 点二列 r={r_pb_o:.4f} p={p_pb_o:.3e}")
    print(f"    重叠型 Recall@10 均值 = "
          f"{S.mean([r['cascade_recall_o'] for r in rows if r['cascade_recall_o'] is not None]):.4f}")

    # =================================================== regime
    print("\n" + "-" * 92)
    print("【4】regime 分布（collapsed / sparse / dense）")
    print("-" * 92)
    for label, key in (("改写型", "regime_p"), ("重叠型", "regime_o")):
        c = Counter(r[key] for r in rows)
        print(f"  {label}: " + "  ".join(
            f"{k}={c.get(k, 0)} ({c.get(k, 0) / n:.1%})"
            for k in ("collapsed", "sparse", "dense")))
    # 重叠型全量（含未进入改写池的查询）
    all_over = [meter.measure(q["query"]).regime for q in all_queries]
    c = Counter(all_over)
    print(f"  重叠型·全量查询池（n={len(all_over)}）: " + "  ".join(
        f"{k}={c.get(k, 0)} ({c.get(k, 0) / len(all_over):.1%})"
        for k in ("collapsed", "sparse", "dense")))
    # regime × 级联成功
    print("\n  regime × 级联通路成功（改写型）：")
    for reg in ("collapsed", "sparse", "dense"):
        grp = [r for r in rows if r["regime_p"] == reg]
        if not grp:
            continue
        hit = sum(1 for r in grp if r["cascade_hit_p"])
        print(f"    {reg:10s} n={len(grp):4d}  成功 {hit:4d}  "
              f"= {hit / len(grp):.4f}   mean Ω="
              f"{S.mean([r['omega_p'] for r in grp]):.4f}")
    print("  regime × 级联通路成功（重叠型）：")
    for reg in ("collapsed", "sparse", "dense"):
        grp = [r for r in rows if r["regime_o"] == reg]
        if not grp:
            continue
        hit = sum(1 for r in grp if r["cascade_hit_o"])
        print(f"    {reg:10s} n={len(grp):4d}  成功 {hit:4d}  "
              f"= {hit / len(grp):.4f}   mean Ω="
              f"{S.mean([r['omega_o'] for r in grp]):.4f}")

    # =================================================== 其他口径
    print("\n" + "-" * 92)
    print("【5】其他相关口径（避免单一指标误判）")
    print("-" * 92)
    print(f"  改写型：级联通路非空率 = "
          f"{S.mean([1.0 if r['cascade_nonempty_p'] else 0.0 for r in rows]):.4f}")
    ne = [r for r in rows if r["cascade_nonempty_p"]]
    if ne:
        print(f"    非空子集（n={len(ne)}）：Recall@10 = "
              f"{S.mean([r['cascade_recall_p'] for r in ne]):.4f}，"
              f"成功率 = {S.mean([1.0 if r['cascade_hit_p'] else 0.0 for r in ne]):.4f}，"
              f"mean Ω = {S.mean([r['omega_p'] for r in ne]):.4f}")
        su2 = [1 if r["cascade_hit_p"] else 0 for r in ne]
        rr2, pp2, _ = S.point_biserial(su2, [r["omega_p"] for r in ne])
        print(f"    非空子集内 Ω × 成功：r={rr2:.4f} p={pp2:.3e}")
    # 触发词数 vs 成功
    print("\n  触发词数 n_seed 与成功（改写型）：")
    for k in sorted(set(r["n_seed_p"] for r in rows))[:8]:
        grp = [r for r in rows if r["n_seed_p"] == k]
        hit = sum(1 for r in grp if r["cascade_hit_p"])
        print(f"    n_seed={k}: n={len(grp):4d} 成功率={hit / len(grp):.4f} "
              f"mean Ω={S.mean([r['omega_p'] for r in grp]):.4f}")

    # ---- 落盘 ----
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(n=n, n_docs=len(docs), n_l1=n_l1, n_frames=n_frames,
                       rows=rows), f, ensure_ascii=False)
    print(f"\n逐查询明细已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
