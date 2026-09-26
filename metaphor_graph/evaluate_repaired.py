# -*- coding: utf-8 -*-
"""修复版检索基准：跨文档全局候选池 + 构造锚定量化（离线、$0）。

**为什么需要它（三代实验的共同结论）**

现有检索基准有两处方法论缺陷，由 `exp/typefeat` / `exp/degrade` / `exp/cascade`
独立确认：

1. **候选池过小导致指标平凡饱和**：池按「伪文档」切分，median 7–8 / max 10，
   于是 Hits@10 在 100% 的查询上平凡为 1.000，Recall@10 亦失去区分力。
   IR 文献称之为 test collection 规模不足（Efficient construction of large test
   collections, SIGIR 1998）。
2. **构造锚定（pooling bias）**：查询由边的触发词拼成、金标即该边所在 chunk，
   故 632/632 的金标都包含产出 chunk、619/632 只包含它。IR 文献称之为 pooling
   bias（Bias and the limits of pooling for large collections, 2007）。

**本模块做什么**

- 建**全局图**（全部伪文档合并），候选池 = 全部 chunk（约 1e3 量级），
  使 Hits@10/Recall@10 脱离平凡饱和。
- 提供**三种评测口径**，用于把"架构能力"与"构造锚定"分离：
  * `anchored`     —— 现行口径（金标=产出 chunk），但池已全局化；
  * `deanchor`     —— **把产出 chunk 从候选池中移除**，金标改为「同框架/同级联的
                       其它 chunk」。这是对跨域召回能力的**非锚定**检验；
  * `random`       —— 随机排序基线，给出各指标的量程下界（判断饱和程度）。
- 报告 **pool-external rate**（池外文档比例）与随机基线，作为评测自我审计字段。

**诚实声明**

`anchored` 口径仍然是构造性的（查询与金标同源），它的价值仅在于**与 deanchor
口径对照**：若某通路在 anchored 上强、在 deanchor 上无优势，则其增益来自锚定；
若两个口径都强，才是架构有效的证据。

运行：
    python -m metaphor_graph.evaluate_repaired                 # 全部三口径
    python -m metaphor_graph.evaluate_repaired --doc-size 10
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.models import ChunkSpan, MetaphorSHG, MetaphorHyperedge
from metaphor_graph.ontology import CascadeOntology
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.training import MetaphorScorer, train_from_shg

from metaphor_graph.evaluate_fullcorpus import (build_replay_backend,
                                                build_replay_ontology)


# --------------------------------------------------------------------- 全局图
def build_global_graph(samples, ont, backend, k: int, llm_conf: float):
    """把全部伪文档合并成**一张全局图**，chunk id 全局连续编号。

    返回 (shg, chunk_texts, chunk_order, doc_of_chunk, stats)。
    """
    all_edges: List[MetaphorHyperedge] = []
    all_frames: Dict[str, object] = {}
    all_cascades: Dict[str, object] = {}
    chunk_texts: List[str] = []
    chunk_order: Dict[str, int] = {}
    doc_of_chunk: Dict[str, str] = {}

    n_docs = (len(samples) + k - 1) // k
    docs_used = 0
    for di in range(n_docs):
        texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=llm_conf)
        builder = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                     llm_backend=backend)
        shg = builder.build(texts, doc_id=did)
        if not any(not e.is_extended for e in shg.edges):
            continue
        docs_used += 1

        # chunk id 重映射：fcN_cM -> global_c<global_index>
        # 必须与 RetrievalEngine 的 f"{doc_id}_c{i}" 命名一致（doc_id="global"）
        local_to_global: Dict[str, str] = {}
        for i, t in enumerate(texts):
            gid = f"global_c{len(chunk_texts)}"
            local_to_global[f"{did}_c{i}"] = gid
            chunk_texts.append(t)
            chunk_order[gid] = len(chunk_texts) - 1
            doc_of_chunk[gid] = did

        for e in shg.edges:
            spans = []
            for s in e.chunk_spans:
                gid = local_to_global.get(s.chunk_id)
                if gid is None:
                    continue
                spans.append(ChunkSpan(chunk_id=gid, start=s.start, end=s.end,
                                       text=s.text, doc_id="global"))
            if not spans:
                continue
            ne = MetaphorHyperedge(
                id=e.id, source_domain=e.source_domain,
                target_domain=e.target_domain, ground=list(e.ground),
                triggers=list(e.triggers), chunk_spans=spans,
                cascade_id=e.cascade_id, frame_id=e.frame_id,
                novelty=e.novelty, sentiment=dict(e.sentiment),
                confidence=e.confidence, source_type=e.source_type,
                is_extended=e.is_extended, layer=e.layer,
                deprecated=e.deprecated,
            )
            all_edges.append(ne)
        for f in shg.frames:
            all_frames[f.id] = f
        for c in shg.cascades:
            all_cascades[c.id] = c

    gshg = MetaphorSHG(edges=all_edges, frames=list(all_frames.values()),
                       cascades=list(all_cascades.values()))
    stats = dict(n_docs=n_docs, docs_used=docs_used,
                 n_edges=len(all_edges),
                 n_l1=sum(1 for e in all_edges if not e.is_extended),
                 n_ext=sum(1 for e in all_edges if e.is_extended),
                 n_chunks=len(chunk_texts))
    return gshg, chunk_texts, chunk_order, doc_of_chunk, stats


def global_engine(gshg, chunk_texts, ont) -> RetrievalEngine:
    """构造全局检索引擎。

    RetrievalEngine 内部按 `f"{doc_id}_c{i}"` 生成 chunk 键，因此这里必须让
    全局 chunk id 采用同一命名（`global_c0`、`global_c1`…），否则候选会被
    `_chunk_text` 过滤干净、所有指标恒为 0。
    """
    eng = RetrievalEngine(gshg, chunk_texts, doc_id="global", ontology=ont)
    edge_cids = {s.chunk_id for e in gshg.edges for s in e.chunk_spans}
    assert edge_cids <= set(eng._chunk_text), (
        f"有 {len(edge_cids - set(eng._chunk_text))} 个边的 chunk id "
        f"不在引擎候选池内（命名不一致会导致指标恒为 0）")
    return eng


# --------------------------------------------------------------------- 查询集
def _chunk_ids_of(edge) -> Set[str]:
    return {s.chunk_id for s in edge.chunk_spans}


PARAPHRASE_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "llm_cache_paraphrase.json")


def build_paraphrased_sets(gshg, max_q: int = 0
                           ) -> Dict[str, List[Tuple[str, Set[str]]]]:
    """改写型查询（含触发词被程序化禁用），映射到全局池上。

    原 §6.1 的"三通路分解"是在**改写型**查询上测的（字面 0.000 / 级联 0.042 /
    语义超图 1.000），而 `build_query_sets` 产出的是**重叠型**（查询=触发词拼接，
    字面通路天然占优）。两者是不同查询族，不可直接对比。

    本函数用 LLM 改写缓存（key = "<doc>|<原触发词查询>"）把改写查询映射到
    全局池的金标上，从而在修复后的池规模下重测改写型查询的三通路。
    """
    import json
    base = build_query_sets(gshg)
    if not os.path.exists(PARAPHRASE_CACHE):
        return {"anchored": [], "deanchor": []}
    with open(PARAPHRASE_CACHE, encoding="utf-8") as f:
        para = json.load(f)
    out: Dict[str, List[Tuple[str, Set[str]]]] = {"anchored": [], "deanchor": []}
    # 反向映射：改写问句 → 原触发词查询
    for key, rewritten in para.items():
        if not isinstance(rewritten, str):
            continue
        orig = key.split("|", 1)[1] if "|" in key else key
        for fam in ("anchored", "deanchor"):
            for q, gold in base[fam]:
                if q == orig:
                    out[fam].append((rewritten, gold))
                    break
    for fam in out:
        if max_q:
            out[fam] = out[fam][:max_q]
    return out


def build_query_sets(gshg, max_q: int = 0) -> Dict[str, List[Tuple[str, Set[str]]]]:
    """三种口径的查询/金标。

    anchored : 金标 = 产出 chunk（现行口径）
    deanchor : 金标 = 同框架的**其它** chunk，且**产出 chunk 被排除**
               （无其它同框架 chunk 则退到同级联；再退则丢弃该查询）

    注意：deanchor 的金标天然不含产出 chunk，故 `rank_all` 无需再排除
    （早期版本误把金标自身也排除，导致指标恒为 0）。
    """
    anchored: List[Tuple[str, Set[str]]] = []
    deanchor: List[Tuple[str, Set[str]]] = []
    seen: Set[str] = set()

    by_frame: Dict[str, Set[str]] = defaultdict(set)
    by_casc: Dict[str, Set[str]] = defaultdict(set)
    for e in gshg.edges:
        if e.is_extended:
            continue
        cids = _chunk_ids_of(e)
        if e.frame_id:
            by_frame[e.frame_id] |= cids
        if e.cascade_id:
            by_casc[e.cascade_id] |= cids

    for e in gshg.edges:
        if e.is_extended:
            continue
        trig = [t for t in e.triggers if t]
        if not trig:
            continue
        q = "，".join(dict.fromkeys(trig))
        if q in seen:
            continue
        seen.add(q)
        own = _chunk_ids_of(e)
        if not own:
            continue
        anchored.append((q, set(own)))

        # de-anchored：同框架其它 chunk（排除自身）
        alt: Set[str] = set()
        if e.frame_id:
            alt = by_frame.get(e.frame_id, set()) - own
        if not alt and e.cascade_id:
            alt = by_casc.get(e.cascade_id, set()) - own
        if alt:
            deanchor.append((q, alt))

    if max_q:
        anchored = anchored[:max_q]
        deanchor = deanchor[:max_q]
    return {"anchored": anchored, "deanchor": deanchor}


# --------------------------------------------------------------------- 指标
def rank_all(eng: RetrievalEngine, scorer, query: str,
             exclude: Set[str], weights: Optional[Dict[str, float]] = None
             ) -> List[Tuple[str, float]]:
    """对全部候选 chunk 打分排序（排除 exclude 中的 chunk）。

    weights=None 时用 training.HAND_WEIGHTS（重标定后）；传
    HAND_WEIGHTS_LEGACY 可复现历史口径，用于量化权重错配的影响。
    """
    from metaphor_graph.training import hand_weighted_score
    cands = eng.live_edges()
    feats = {m.id: eng._pair_features(query, m) for m in cands}
    chunk_score: Dict[str, float] = {}
    for m in cands:
        cid = next((s.chunk_id for s in m.chunk_spans
                    if s.chunk_id in eng._chunk_text), None)
        if cid is None or cid in exclude:
            continue
        s = (scorer.score_features(feats[m.id]) if scorer is not None
             else hand_weighted_score(feats[m.id], weights=weights))
        chunk_score[cid] = max(chunk_score.get(cid, -1e9), s)
    return sorted(chunk_score.items(), key=lambda x: -x[1])


def pathway_rankings(eng, query: str, exclude: Set[str]
                     ) -> Dict[str, List[Tuple[str, float]]]:
    """三条检索通路的排序（在**同一全局候选池**上比较）。

    §6.1 的核心主张是"三通路分解"，但原实现在池 ≤10 的基准上测，
    字面/级联两路的失效与语义超图路的 1.000 都无法与池规模解耦。
    本函数在修复后基准（池=1,100）上重测三路：

      literal  字面包含：查询词面子串命中候选 chunk 原文
      cascade  触发词级联：查询触发词 → 框架/级联 → 目标域 → chunk
      semantic 语义超图：超边渲染后向量化，7 维特征排序（= rank_all）
    """
    out: Dict[str, List[Tuple[str, float]]] = {}

    # ---- 字面通路：查询词在 chunk 原文中的子串命中 ----
    lit: Dict[str, float] = {}
    q = query.strip()
    for cid, text in eng._chunk_text.items():
        if cid in exclude:
            continue
        if q and q in text:
            lit[cid] = 1.0
    out["literal"] = sorted(lit.items(), key=lambda x: -x[1])

    # ---- 触发词级联通路 ----
    res = eng.cross_domain_retrieve(query)
    out["cascade"] = [(c, 1.0 - i * 1e-6) for i, c in enumerate(res.chunk_ids)
                      if c not in exclude]

    # ---- 语义超图通路 ----
    out["semantic"] = rank_all(eng, None, query, exclude)
    return out


def metrics(ranked: Sequence[Tuple[str, float]], gold: Set[str],
            ks=(3, 10)) -> Dict[str, float]:
    out: Dict[str, float] = {}
    first = None
    for r, (cid, _) in enumerate(ranked, 1):
        if cid in gold:
            first = r
            break
    out["mrr"] = (1.0 / first) if first else 0.0
    for k in ks:
        top = {cid for cid, _ in ranked[:k]}
        out[f"hits@{k}"] = 1.0 if (top & gold) else 0.0
        out[f"recall@{k}"] = len(top & gold) / max(1, len(gold))
    return out


def random_baseline(n_pool: int, n_gold: int, ks=(3, 10)) -> Dict[str, float]:
    """随机排序下各指标的解析期望（用于判断量程/饱和）。"""
    import math
    n = max(1, n_pool)
    g = min(n_gold, n)
    # MRR：金标中最早出现的期望排名
    exp_mrr = 0.0
    for r in range(1, n + 1):
        # 前 r-1 个位置都不是金标的概率 × 第 r 个是金标
        if r - 1 > n - g:
            break
        p = (math.comb(n - g, r - 1) / math.comb(n, r - 1)) * (g / (n - r + 1))
        exp_mrr += p / r
    out = {"mrr": exp_mrr}
    for k in ks:
        kk = min(k, n)
        out[f"hits@{k}"] = 1.0 - (math.comb(n - g, kk) / math.comb(n, kk)
                                  if n - g >= kk else 0.0)
        out[f"recall@{k}"] = min(1.0, kk * g / n) / max(1, g)
    return out


# --------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc-size", type=int, default=10)
    ap.add_argument("--llm-conf", type=float, default=0.85)
    ap.add_argument("--max-q", type=int, default=0,
                    help="限制查询数（0=全部）")
    ap.add_argument("--seed", type=int, default=20260925)
    args = ap.parse_args()

    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    print("=" * 88)
    print(f"修复版检索基准 —— 全局候选池 + 构造锚定量化（n={len(samples)} 句，"
          f"K={args.doc_size}，本体 {n_frames} 框架）")
    print("=" * 88)

    gshg, chunk_texts, chunk_order, doc_of_chunk, gs = build_global_graph(
        samples, ont, backend, args.doc_size, args.llm_conf)
    print(f"\n【全局图】文档 {gs['docs_used']}/{gs['n_docs']} 有边 ｜ "
          f"L1 边 {gs['n_l1']} ｜ 扩展边 {gs['n_ext']} ｜ chunk {gs['n_chunks']}")
    print(f"→ 候选池规模 = {gs['n_chunks']}（原基准 median 7–8 / max 10）")

    eng = global_engine(gshg, chunk_texts, ont)
    qs = build_query_sets(gshg, args.max_q)
    print(f"\n【查询集】anchored {len(qs['anchored'])} ｜ deanchor {len(qs['deanchor'])}")

    # 训练排序器（自监督 chunk 模式，与既有口径一致）
    # chunks 必须是 chunk_id → 原文；传错会导致训练集为空、排序器退化为常数
    scorer = None
    try:
        cmap = {cid: t for cid, t in zip(
            [f"global_c{i}" for i in range(len(chunk_texts))], chunk_texts)}
        scorer, ds = train_from_shg(gshg, chunk_order=chunk_order,
                                    chunks=cmap, ontology=ont)
        assert len(ds) > 0, "训练集为空 —— chunks 映射或 positive_mode 有误"
        print(f"【排序器】自监督训练集 n={len(ds)}")
    except Exception as e:
        print(f"【排序器】训练失败，仅测人工加权：{e}")
        scorer = None

    print("\n" + "=" * 88)
    print("【口径 A】anchored —— 金标=产出 chunk（现行口径，但池已全局化）")
    print("=" * 88)
    _run(qs["anchored"], eng, scorer, chunk_texts, exclude_own=False,
         n_chunks=gs["n_chunks"])

    print("\n" + "=" * 88)
    print("【口径 B】deanchor —— 产出 chunk 从池中移除，金标=同框架其它 chunk")
    print("=" * 88)
    _run(qs["deanchor"], eng, scorer, chunk_texts, exclude_own=True,
         n_chunks=gs["n_chunks"])

    print("\n" + "=" * 88)
    print("【三通路分解】同一全局候选池上比较（§6.1 的核心主张）")
    print("=" * 88)
    pq = build_paraphrased_sets(gshg)
    for key, title in (("anchored", "口径 A anchored（重叠型）"),
                       ("deanchor", "口径 B deanchor（重叠型）"),
                       ("anchored", "口径 A anchored（改写型）"),
                       ("deanchor", "口径 B deanchor（改写型）")):
        qset = pq[key] if "改写型" in title else qs[key]
        if not qset:
            continue
        agg = {p: defaultdict(float) for p in ("literal", "cascade", "semantic")}
        nonempty = {p: 0 for p in agg}
        n = 0
        for q, gold in qset:
            n += 1
            paths = pathway_rankings(eng, q, set())  # 每查询只算一次
            for pname, ranked in paths.items():
                if ranked:
                    nonempty[pname] += 1
                for k, v in metrics(ranked, gold).items():
                    agg[pname][k] += v
        print(f"  [{title}] n={n}")
        print(f"    {'通路':<10}{'MRR':>9}{'Hits@3':>10}{'Hits@10':>10}{'Recall@10':>12}")
        for pname, label in (("literal", "字面包含"), ("cascade", "触发词级联"),
                             ("semantic", "语义超图")):
            a = agg[pname]
            print(f"    {label:<10}{a['mrr']/n:>9.4f}{a['hits@3']/n:>10.4f}"
                  f"{a['hits@10']/n:>10.4f}{a['recall@10']/n:>12.4f}")
        for pname, label in (("literal", "字面包含"), ("cascade", "触发词级联"),
                             ("semantic", "语义超图")):
            print(f"    {label} 非空率 {nonempty[pname]}/{n} = "
                  f"{nonempty[pname]/n:.3f}")

    print("【评测自我审计】")
    print("=" * 88)
    rnd = random_baseline(gs["n_chunks"], 1)
    print(f"  随机排序基线（池={gs['n_chunks']}，金标=1）："
          f"MRR={rnd['mrr']:.4f}  Hits@3={rnd['hits@3']:.4f}  "
          f"Hits@10={rnd['hits@10']:.4f}")
    print(f"  原基准（池=7）随机基线：MRR≈0.3704  Hits@10=1.0000（平凡饱和）")
    print(f"  → 新基准下 Hits@10 不再是平凡值，MRR 量程从 0.63 扩展到 "
          f"{1 - rnd['mrr']:.2f}")


def _run(qset, eng, scorer, chunk_texts, exclude_own: bool, n_chunks: int):
    """跑一个口径。

    三臂共享同一份 7 维特征（每查询只算一次 `_pair_features`）。
    原实现每臂各算一次，3 臂 = 3 倍开销，全量 634 查询下不可接受。
    """
    from metaphor_graph.training import HAND_WEIGHTS_LEGACY, hand_weighted_score
    if not qset:
        print("  （无查询）")
        return
    arm_names = ["hand_recalibrated", "hand_legacy"]
    if scorer is not None:
        arm_names.append("trained")
    agg = {name: defaultdict(float) for name in arm_names}

    for q, gold in qset:
        cands = eng.live_edges()
        feats = {m.id: eng._pair_features(q, m) for m in cands}
        # 每个候选 chunk 取"最强支持"的超边分（与 score_conditions 口径一致）
        chunk_feats: Dict[str, List[float]] = {}
        for m in cands:
            cid = next((s.chunk_id for s in m.chunk_spans
                        if s.chunk_id in eng._chunk_text), None)
            if cid is None:
                continue
            prev = chunk_feats.get(cid)
            f = feats[m.id]
            if prev is None:
                chunk_feats[cid] = list(f)
            else:
                # 用 sem 维作为"支持强度"比较，保留更强的那条边
                if f[0] > prev[0]:
                    chunk_feats[cid] = list(f)

        for name in arm_names:
            if name == "hand_recalibrated":
                sc = lambda f: hand_weighted_score(f)
            elif name == "hand_legacy":
                sc = lambda f, _w=HAND_WEIGHTS_LEGACY: hand_weighted_score(f, weights=_w)
            else:
                sc = lambda f, _s=scorer: _s.score_features(f)
            scored = sorted(((cid, sc(f)) for cid, f in chunk_feats.items()),
                            key=lambda x: -x[1])
            m = metrics(scored, gold)
            for k, v in m.items():
                agg[name][k] += v

    n = len(qset)
    print(f"  查询数 {n}")
    for name in arm_names:
        a = agg[name]
        print(f"    {name:<18} MRR={a['mrr']/n:.4f}  Hits@3={a['hits@3']/n:.4f}  "
              f"Hits@10={a['hits@10']/n:.4f}  Recall@10={a['recall@10']/n:.4f}")
    if "hand_recalibrated" in agg and "hand_legacy" in agg:
        d = (agg["hand_recalibrated"]["mrr"] - agg["hand_legacy"]["mrr"]) / n
        print(f"  权重重标定效应 Δ MRR = {d:+.4f}")
    gold_sizes = [len(g) for _, g in qset]
    print(f"  金标规模：min={min(gold_sizes)} median="
          f"{sorted(gold_sizes)[len(gold_sizes)//2]} max={max(gold_sizes)}")


if __name__ == "__main__":
    main()
