# -*- coding: utf-8 -*-
"""P3 跨 chunk 消歧测量 + H3/A5/A7/A9 检索消融（全部离线、零 API 费用）。

测量项：
  P3  跨 chunk 扩展隐喻消歧准确率（precision / recall / F1）
      金标：eval_corpus.GOLD_EXTENDED（人工判定的「应合并的 chunk 集合」）
  H3  去掉隐喻通路、仅留字面通路 → 验证「隐喻通路带来跨域 Recall 增益」
      配置：跨域隐喻通路 cross_domain_retrieve vs 纯字面「query in chunk」
      金标：eval_corpus.GOLD_RETRIEVAL（查询字面不含答案词，只能经隐喻通路召回）
  A5  去掉跨 chunk 扩展超边（关 builder.use_extended）→ 验证扩展边对 P3 的贡献
      配置：P3 F1（开扩展边）vs P3 F1（关扩展边）
  A7  排序器改为人工加权（关闭训练）→ 验证 H5（训练确有增益）
      配置：trained（可训练评分器） vs hand_weighted（0.35/0.25/0.20/0.20 人工加权）
  A9  去掉角色感知结构特征 → 验证 H7（角色信息不可被同质 DDE 替代）
      配置：trained_full（7 维）vs trained_no_role（same_frame/same_cascade/
      ground_jaccard 置零，仅留 sem/struct/clue/type）

检索指标：对每个查询，用 RetrieverResult 风格的「映射→chunk」映射计算
  MRR@k、Hits@k（k=3,10）。金标：eval_corpus.GOLD_RETRIEVAL。

运行：python -m metaphor_graph.evaluate_retrieval
"""
import os
import sys
import logging
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.training import (train_from_shg, FEATURE_NAMES,
                                     hand_weighted_score,
                                     HAND_WEIGHTS_LEGACY)
from metaphor_graph.eval_corpus import (
    DOCS, GOLD_EXTENDED, GOLD_RETRIEVAL, THRESHOLD_P3_ACC,
)

ROLE_IDX = [FEATURE_NAMES.index(n) for n in
            ("same_frame", "same_cascade", "ground_jaccard")]


# ---------------------------------------------------------------------------
# 级联构造规则开关（gen2 实验用）
# ---------------------------------------------------------------------------
# 默认 None = DEFAULT_ONTOLOGY + 原口径孤儿打包（已上报数字的口径）。
# 注入后所有 measure_* 走同一入口，避免各函数各写一份 builder 调用而漂移。
_ONT = None
_ORPHAN_RULE = "target"


def set_ontology(ont, orphan_rule: str = "target"):
    """注入本体与孤儿打包规则（None → 恢复 DEFAULT_ONTOLOGY）。"""
    global _ONT, _ORPHAN_RULE
    _ONT, _ORPHAN_RULE = ont, orphan_rule


def _build_shg(chunks, doc_id):
    """统一的建图入口。"""
    return MetaphorSHGBuilder(ontology=_ONT,
                              orphan_cascade_rule=_ORPHAN_RULE).build(
        chunks, doc_id=doc_id)


# --------------------------------------------------------------------------- P3
def measure_p3(doc_id, chunks):
    """返回 (precision, recall, f1, n_pred, n_gold, spurious)。"""
    shg = _build_shg(chunks, doc_id)
    ext = [e for e in shg.edges if e.is_extended]
    pred = [frozenset(int(s.chunk_id.split("_c")[-1]) for s in e.chunk_spans)
            for e in ext]
    gold = [frozenset(g) for g in GOLD_EXTENDED[doc_id]]

    used = set()
    hit = 0
    for p in pred:
        for i, g in enumerate(gold):
            if i not in used and p == g:
                hit += 1
                used.add(i)
                break
    n_pred, n_gold = len(pred), len(gold)
    # 负样本检查：是否存在「间距≥3 却被合并」的扩展边（应=0）
    chunk_order = {f"{doc_id}_c{i}": i for i in range(len(chunks))}
    spurious = 0
    for e in ext:
        ids = sorted(int(s.chunk_id.split("_c")[-1]) for s in e.chunk_spans)
        if ids[-1] - ids[0] >= 3:
            spurious += 1
    prec = hit / n_pred if n_pred else (1.0 if n_gold == 0 else 0.0)
    rec = hit / n_gold if n_gold else 1.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return prec, rec, f1, n_pred, n_gold, spurious


# ------------------------------------------------------------------------ H3 / A5
def _recall_metrics(ranked: List[str], gold: set, doc_id: str) -> Tuple[float, int, int]:
    """ranked: 已排序的 chunk_id 列表；gold: 金标 chunk 索引集合。"""
    gset = {f"{doc_id}_c{i}" for i in gold}
    top10 = set(ranked[:10])
    rec = len(gset & top10) / len(gset) if gset else 1.0
    hits3 = 1 if any(c in gset for c in ranked[:3]) else 0
    hits10 = 1 if any(c in gset for c in ranked[:10]) else 0
    return rec, hits3, hits10


def measure_h3(doc_id: str, chunks: List[str],
               gold_items: List[Tuple[str, set]]) -> dict:
    """H3：去掉隐喻通路、仅留字面通路 → 跨域 Recall 应跌至 B1（基线）水平。

    金标查询字面均不含答案词，纯字面通路「query in chunk」应几乎召回不到；
    隐喻通路 cross_domain_retrieve 沿级联/框架才能命中。两路对比量化隐喻通路增益。
    """
    shg = _build_shg(chunks, doc_id)
    eng = RetrievalEngine(shg, chunks, doc_id=doc_id)

    agg = dict(meta_rec=0.0, lit_rec=0.0, meta_h3=0, lit_h3=0,
               meta_h10=0, lit_h10=0, n=0)
    per = []
    for query, gold in gold_items:
        meta = eng.cross_domain_retrieve(query).chunk_ids
        lit = [f"{doc_id}_c{i}" for i, c in enumerate(chunks) if query in c]
        mr, mh3, mh10 = _recall_metrics(meta, gold, doc_id)
        lr, lh3, lh10 = _recall_metrics(lit, gold, doc_id)
        agg["meta_rec"] += mr; agg["lit_rec"] += lr
        agg["meta_h3"] += mh3; agg["lit_h3"] += lh3
        agg["meta_h10"] += mh10; agg["lit_h10"] += lh10
        agg["n"] += 1
        per.append((query, mr, lr))
    n = agg["n"]
    if n:
        for k in ("meta_rec", "lit_rec"):
            agg[k] /= n
        for k in ("meta_h3", "lit_h3", "meta_h10", "lit_h10"):
            agg[k] /= n
    agg["per"] = per
    return agg


def measure_p3_flag(doc_id: str, chunks: List[str],
                    use_extended: bool) -> Tuple[float, float, float, int, int]:
    """A5：跨 chunk 扩展超边对 P3 的贡献（关 builder.use_extended 后重测 P3 F1）。"""
    shg = MetaphorSHGBuilder(use_extended=use_extended).build(chunks, doc_id=doc_id)
    ext = [e for e in shg.edges if e.is_extended]
    pred = [frozenset(int(s.chunk_id.split("_c")[-1]) for s in e.chunk_spans)
            for e in ext]
    gold = [frozenset(g) for g in GOLD_EXTENDED[doc_id]]
    used, hit = set(), 0
    for p in pred:
        for i, g in enumerate(gold):
            if i not in used and p == g:
                hit += 1
                used.add(i)
                break
    n_pred, n_gold = len(pred), len(gold)
    prec = hit / n_pred if n_pred else (1.0 if n_gold == 0 else 0.0)
    rec = hit / n_gold if n_gold else 1.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return prec, rec, f1, n_pred, n_gold


def measure_a8(doc_id: str, chunks: List[str],
               gold_items: List[Tuple[str, set]]) -> dict:
    """A8：关自适应阈值 → 检索质量/稳定性变化。

    对比 cross_domain_retrieve(adaptive=True) vs (adaptive=False)
    （阈值开关见 context_budget.AdaptiveThreshold）。
    """
    shg = _build_shg(chunks, doc_id)
    eng = RetrievalEngine(shg, chunks, doc_id=doc_id)
    agg = dict(on_rec=0.0, off_rec=0.0, on_h3=0, off_h3=0,
               on_h10=0, off_h10=0, n=0)
    for query, gold in gold_items:
        on = eng.cross_domain_retrieve(query, adaptive=True).chunk_ids
        off = eng.cross_domain_retrieve(query, adaptive=False).chunk_ids
        or_, oh3, oh10 = _recall_metrics(on, gold, doc_id)
        fr_, fh3, fh10 = _recall_metrics(off, gold, doc_id)
        agg["on_rec"] += or_; agg["off_rec"] += fr_
        agg["on_h3"] += oh3; agg["off_h3"] += fh3
        agg["on_h10"] += oh10; agg["off_h10"] += fh10
        agg["n"] += 1
    n = agg["n"]
    if n:
        for k in ("on_rec", "off_rec"):
            agg[k] /= n
        for k in ("on_h3", "off_h3", "on_h10", "off_h10"):
            agg[k] /= n
    return agg


# ----------------------------------------------------------------------- 检索评分
def _chunk_of(mapping):
    for s in mapping.chunk_spans:
        return s.chunk_id
    return None


def score_conditions(eng, scorer, query, legacy_arm: bool = False,
                     reliability: bool = False, floor=None):
    """返回打分配置下，候选映射→chunk 的排序得分表。

    legacy_arm=True 时额外返回 `hand_weighted_legacy`（原 0.35/0.25/0.20/0.20
    权重），用于量化权重错配的影响。**默认关闭** —— 调用方（如
    evaluate_fullcorpus）按固定键列表聚合，多出的键会导致 KeyError。

    reliability=True 时额外返回叠加**溯源可靠性折扣**的配置（`*_reliab`）：
    分数乘上 [floor,1] 的因子，退化框架来源的候选被降权但**不消失**
    （floor 见 provenance.RELIABILITY_FLOOR，默认 0.5）。
    原三组配置逐位不变 —— 保证 before/after 可比。
    """
    from metaphor_graph import provenance
    cands = eng.live_edges()
    # 预计算 7 维特征
    feats = {m.id: eng._pair_features(query, m) for m in cands}
    fl = provenance.RELIABILITY_FLOOR if floor is None else floor
    rel = ({m.id: provenance.reliability_factor(
        provenance.edge_reliability(m, eng.ont), fl) for m in cands}
        if reliability else {})
    out = {}
    arms = [
        ("trained", lambda f: scorer.score_features(f)),
        ("trained_no_role", lambda f: scorer.score_features(
            [0.0 if i in ROLE_IDX else v for i, v in enumerate(f)])),
        # 人工加权改为调用单一真源（training.hand_weighted_score）。
        # 原实现硬编码 0.35/0.25/0.20/0.20，与学到权重严重错配
        # （struct 过权 37 倍、type 12 倍），使"训练增益"成为配错权重的产物。
        ("hand_weighted", lambda f: hand_weighted_score(f)),
    ]
    if legacy_arm:
        arms.append(("hand_weighted_legacy",
                     lambda f: hand_weighted_score(f, weights=HAND_WEIGHTS_LEGACY)))
    for name, fn in arms:        # 映射→chunk 取最高分
        chunk_score = {}
        for m in cands:
            cid = _chunk_of(m)
            if cid is None:
                continue
            s = fn(feats[m.id])
            chunk_score[cid] = max(chunk_score.get(cid, -1e9), s)
        out[name] = sorted(chunk_score.items(), key=lambda x: -x[1])
        if not reliability:
            continue
        chunk_score_r = {}
        for m in cands:
            cid = _chunk_of(m)
            if cid is None:
                continue
            s = fn(feats[m.id]) * rel[m.id]
            chunk_score_r[cid] = max(chunk_score_r.get(cid, -1e9), s)
        out[name + "_reliab"] = sorted(chunk_score_r.items(),
                                       key=lambda x: -x[1])
    return out


def _mrr_hits(ranked, gold, ks=(3, 10)):
    gold = set(f"{g}" for g in gold)  # chunk_id 形如 doc_c3
    # ranked 的 cid 是完整 chunk_id
    res = {}
    first_rank = None
    for r, (cid, _) in enumerate(ranked, 1):
        if cid in gold and first_rank is None:
            first_rank = r
    mrr = (1.0 / first_rank) if first_rank else 0.0
    res["mrr"] = mrr
    for k in ks:
        res[f"hits@{k}"] = 1 if any(cid in gold for cid, _ in ranked[:k]) else 0
    return res


# --------------------------------------------------------------------------- 主流程
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", choices=("default", "real"), default="default",
                    help="real=用 EMBED_API_KEY 注入真实句向量（检索层专用）")
    ap.add_argument("--cascade-rule", default="seed",
                    choices=("seed", "json", "source", "ground", "metanet",
                             "source_type", "none"),
                    help="L3 级联构造规则（默认 seed = 种子本体，已上报口径）")
    ap.add_argument("--orphan-cascade-rule", default="target",
                    choices=("target", "source", "ground", "source_type", "none"))
    args = ap.parse_args()
    if args.cascade_rule != "seed":
        from metaphor_graph.evaluate_fullcorpus import build_replay_ontology
        ont, _nf = build_replay_ontology(cascade_rule=args.cascade_rule)
        set_ontology(ont, args.orphan_cascade_rule)
        print(f"级联规则 {args.cascade_rule} / 孤儿 {args.orphan_cascade_rule}"
              f"（生产重放本体 {len(ont.frames)} 框架 / {len(ont.cascades)} 级联）")
    elif args.orphan_cascade_rule != "target":
        set_ontology(None, args.orphan_cascade_rule)
    if args.embedder == "real":
        from metaphor_graph import embeddings as _emb
        emb_real = _emb.embedder_from_env()
        if emb_real is None:
            raise SystemExit("需要 EMBED_API_KEY 环境变量")
        _emb.set_embedder(emb_real, propagate=False)
        print(f"向量器：{emb_real.model}（真实句向量）")

    print("=" * 78)
    print("P3 跨 chunk 消歧测量 + A7/A9 检索消融（离线）")
    print("=" * 78)

    # ---- P3 ----
    print("\n【P3】跨 chunk 扩展隐喻消歧")
    print(f"{'文档':16s} {'预测':>5s} {'金标':>5s} {'命中':>5s} "
          f"{'精确':>7s} {'召回':>7s} {'F1':>7s} {'跨距误并':>8s}")
    p3_rows = []
    for did, chunks in DOCS.items():
        prec, rec, f1, np_, ng, sp = measure_p3(did, chunks)
        p3_rows.append((did, prec, rec, f1))
        print(f"{did:16s} {np_:>5d} {ng:>5d} {int(prec*ng):>5d} "
              f"{prec:>7.3f} {rec:>7.3f} {f1:>7.3f} {sp:>8d}")
    macro_f1 = sum(r[3] for r in p3_rows) / len(p3_rows)
    status = "✅ 通过" if macro_f1 >= THRESHOLD_P3_ACC else "❌ 未达门槛"
    print(f"{'宏平均 F1':16s} {'':>5s} {'':>5s} {'':>5s} {'':>7s} {'':>7s} "
          f"{macro_f1:>7.3f} {'':>8s}  (门槛>{THRESHOLD_P3_ACC:.2f}) {status}")

    # ---- H3：去掉隐喻通路，仅留字面通路 ----
    print("\n【H3】去掉隐喻通路 vs 仅字面通路（跨域 Recall，n=8 查询）")
    print(f"{'文档':16s} {'隐喻通路Recall@10':>16s} {'字面通路Recall@10':>17s}")
    h3_rows = []
    for did, chunks in DOCS.items():
        items = [(q, g) for (qd, q, g) in GOLD_RETRIEVAL if qd == did]
        a = measure_h3(did, chunks, items)
        h3_rows.append((did, a))
        print(f"{did:16s} {a['meta_rec']:>16.3f} {a['lit_rec']:>17.3f}")
    n_h3 = sum(r[1]["n"] for r in h3_rows) or 1
    m_rec = sum(r[1]["meta_rec"] * r[1]["n"] for r in h3_rows) / n_h3
    l_rec = sum(r[1]["lit_rec"] * r[1]["n"] for r in h3_rows) / n_h3
    m_h3 = sum(r[1]["meta_h3"] * r[1]["n"] for r in h3_rows) / n_h3
    l_h3 = sum(r[1]["lit_h3"] * r[1]["n"] for r in h3_rows) / n_h3
    print(f"{'宏平均':16s} {m_rec:>16.3f} {l_rec:>17.3f}")
    print(f"  隐喻通路 Hits@3={m_h3:.3f} ｜ 字面通路 Hits@3={l_h3:.3f}")

    # ---- A5：去掉跨 chunk 扩展超边 ----
    print("\n【A5】去掉跨 chunk 扩展超边（P3 F1 对照）")
    print(f"{'文档':16s} {'开扩展边F1':>11s} {'关扩展边F1':>12s} {'预测边(开)':>10s} "
          f"{'预测边(关)':>10s}")
    a5_rows = []
    for did, chunks in DOCS.items():
        on = measure_p3_flag(did, chunks, True)
        off = measure_p3_flag(did, chunks, False)
        a5_rows.append((did, on, off))
        print(f"{did:16s} {on[2]:>11.3f} {off[2]:>12.3f} {on[3]:>10d} {off[3]:>10d}")
    on_f1 = sum(r[1][2] for r in a5_rows) / len(a5_rows)
    off_f1 = sum(r[2][2] for r in a5_rows) / len(a5_rows)
    print(f"{'宏平均 F1':16s} {on_f1:>11.3f} {off_f1:>12.3f}")

    # ---- A8：关自适应阈值 ----
    print("\n【A8】关自适应阈值（跨域检索质量对照，n=8 查询）")
    print(f"{'文档':16s} {'开阈值Recall@10':>15s} {'关阈值Recall@10':>15s}")
    a8_rows = []
    for did, chunks in DOCS.items():
        items = [(q, g) for (qd, q, g) in GOLD_RETRIEVAL if qd == did]
        a = measure_a8(did, chunks, items)
        a8_rows.append((did, a))
        print(f"{did:16s} {a['on_rec']:>15.3f} {a['off_rec']:>15.3f}")
    a8_on = sum(r[1]["on_rec"] * r[1]["n"] for r in a8_rows) / n_h3
    a8_off = sum(r[1]["off_rec"] * r[1]["n"] for r in a8_rows) / n_h3
    a8_on_h3 = sum(r[1]["on_h3"] * r[1]["n"] for r in a8_rows) / n_h3
    a8_off_h3 = sum(r[1]["off_h3"] * r[1]["n"] for r in a8_rows) / n_h3
    print(f"{'宏平均':16s} {a8_on:>15.3f} {a8_off:>15.3f}")

    # ---- 检索消融（A7 / A9）----
    print("\n【A7/A9】检索排序质量（MRR@10 / Hits@3 / Hits@10）")
    agg = {k: {"mrr": 0.0, "hits@3": 0, "hits@10": 0, "n": 0}
           for k in ("trained", "trained_no_role", "hand_weighted")}
    per_query = []
    for did, chunks in DOCS.items():
        shg = _build_shg(chunks, did)
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunks))}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunks)}
        scorer, _ = train_from_shg(shg, chunk_order=chunk_order, chunks=chunk_map)
        eng = RetrievalEngine(shg, chunks, doc_id=did, scorer=scorer)
        for q_doc, query, gold in GOLD_RETRIEVAL:
            if q_doc != did:
                continue
            ranked_map = score_conditions(eng, scorer, query)
            gold_ids = [f"{did}_c{i}" for i in gold]
            for cfg, ranked in ranked_map.items():
                m = _mrr_hits(ranked, gold_ids)
                agg[cfg]["mrr"] += m["mrr"]
                agg[cfg]["hits@3"] += m["hits@3"]
                agg[cfg]["hits@10"] += m["hits@10"]
                agg[cfg]["n"] += 1
            per_query.append((did, query, gold_ids,
                              {c: _mrr_hits(ranked_map[c], gold_ids)["mrr"]
                               for c in ranked_map}))

    n = agg["trained"]["n"]
    print(f"{'配置':18s} {'MRR@10':>9s} {'Hits@3':>8s} {'Hits@10':>9s}  (n={n})")
    for cfg, label in (("trained", "训练后(7维)"),
                       ("trained_no_role", "训练后-去角色特征(A9)"),
                       ("hand_weighted", "人工加权(A7关闭训练)")):
        a = agg[cfg]
        print(f"{label:18s} {a['mrr']/n:>9.3f} {a['hits@3']/n:>8.3f} "
              f"{a['hits@10']/n:>9.3f}")

    # ---- 结论 ----
    print("\n【结论】")
    t, hr, hw = (agg["trained"], agg["trained_no_role"], agg["hand_weighted"])
    d_mrr_a7 = (t["mrr"] - hw["mrr"]) / n
    d_mrr_a9 = (t["mrr"] - hr["mrr"]) / n
    print(f"  P3 宏平均 F1 = {macro_f1:.3f}  {status}")
    print(f"  H3 (去隐喻通路→仅字面): 跨域 Recall@10 {m_rec:.3f} → {l_rec:.3f} "
          f"（字面通路命中 {l_h3:.0%} 查询）→ "
          f"{'H3 成立✅' if (m_rec - l_rec) > 0.2 else 'H3 不成立❌'}")
    print(f"  A5 (去跨 chunk 超边):    P3 F1 {on_f1:.3f} → {off_f1:.3f} "
          f"→ {'A5 成立✅' if (on_f1 - off_f1) > 0.2 else 'A5 不成立❌'}")
    print(f"  A8 (关自适应阈值):       Recall@10 {a8_on:.3f} → {a8_off:.3f} "
          f"→ {'A8 有增益✅' if (a8_on - a8_off) > 0.05 else 'A8 无差异/待更大集复验'}")
    print(f"  A7 (训练 vs 人工加权): MRR@10 差 {d_mrr_a7:+.3f} "
          f"→ {'H5 成立✅' if d_mrr_a7 > 0 else 'H5 不成立❌'}")
    print(f"  A9 (去角色特征):       MRR@10 差 {d_mrr_a9:+.3f} "
          f"→ {'H7 成立✅' if d_mrr_a9 > 0 else 'H7 不成立❌'}")
    print(f"\n  排序器学到的权重: {scorer.weights()}")
    if args.embedder == "real":
        from metaphor_graph import embeddings as _emb
        _emb.set_embedder(None)
        print("向量器已恢复默认哈希编码")
    return 0


if __name__ == "__main__":
    sys.exit(main())
