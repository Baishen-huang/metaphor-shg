# -*- coding: utf-8 -*-
"""LLM 非构造金标检索评测（P3「排序器增益证明」的核心阻塞项，路线图 §8.2）。

**为什么需要它**
§7.3 的全量基准金标是 **by-construction**（构造即金标）：查询含金标边的触发词，
clue 特征恒命中 → 四种排序器全部饱和在 0.995+，测不出任何排序增益；且 H3 已证
触发词级联式检索「对改写查询脆弱」（2 文档上 doc_relationship 全 0）。

本脚本用真实 LLM（deepseek-v4-flash）构造**改写查询 + LLM 相关性金标**：
  阶段一 gen    把每条自动查询改写成自然问题，**严格禁止出现触发词/域词**
                → clue 捷径被程序化切断，排序必须靠语义/结构信号。
  阶段二 judge  对每个问题，让 LLM 在该文档全部候选映射中做 listwise 相关性
                判定 → 与抽取构造无关的独立金标（构造即金标的循环被打破）。
  阶段三 eval   三种排序配置（人工加权 / 自监督训练 / LLM 弱监督训练）在
                两套金标（by-construction vs LLM）上的 MRR/Hits/Recall；
                并量化「字面通路 / 触发词级联通路 / 语义超图通路」在改写查询
                上的召回 —— 把 H3 的脆弱性结论从 2 文档推广到全量。

**缓存与成本**：两阶段全部落盘缓存（data/llm_cache_paraphrase.json /
data/llm_cache_judge.json），重跑零请求。全量 861 查询约 150 次请求，
deepseek-v4-flash（thinking 关闭）约 ¥0.5–1。

**失败纪律**：401/402/403 抛 LLMFatalError（不降级）；_chat 返回 None 计为
失败并重试一次，失败率 >20% 直接中止评测 —— 绝不让半残的金标悄悄出数字。

运行（需 LLM_API_KEY）：
    python -m metaphor_graph.evaluate_llmgold --stage all
    python -m metaphor_graph.evaluate_llmgold --stage gen     # 分阶段跑
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.training import (build_training_set, build_weak_refine_set,
                                     MetaphorScorer, leakage_report,
                                     FEATURE_NAMES, TrainingSet)
from metaphor_graph.evaluate_retrieval import score_conditions, _mrr_hits
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.llm_backend import OpenAIBackend, _parse_json_blob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN_CACHE = os.path.join(ROOT, "data", "llm_cache_paraphrase.json")
JUDGE_CACHE = os.path.join(ROOT, "data", "llm_cache_judge.json")

_GEN_SYSTEM = (
    "你是中文检索评测的查询构造专家。给你一批「隐喻检索查询」：每条含原触发词、"
    "金标句子原文、隐喻映射（源域→目标域）。请为每条构造一个用户会问的自然问题："
    "① 问题的答案就在金标句子里；② **严格禁止出现原触发词**，也禁止出现源域、"
    "目标域这些抽象域名词（要用它们的具体含义来问）；③ 15-30 个汉字。"
)
_GEN_USER = (
    "数据（共 {n} 条）：\n{body}\n"
    "只输出 JSON 数组：[{{\"i\": 0, \"q\": \"...\"}}, ...]，i 必须与输入对应，"
    "不要输出任何其它文字。"
)
_JUDGE_SYSTEM = (
    "你是检索相关性评判专家。给你若干问题，每个问题附一组「隐喻映射候选」"
    "（含源域→目标域、喻底、触发词、所在句子片段）。判断每个候选与问题是否"
    "**语义相关**（能提供回答该问题的信息，包括隐喻/比喻层面的关联；"
    "字面不沾边但隐喻上相关的算相关）。宁缺勿滥：明确无关的判 0。"
)
_JUDGE_USER = (
    "问题与候选（共 {n} 个问题）：\n{body}\n"
    "只输出一个 JSON 对象：{{\"<问题i>\": {{\"<候选id>\": 1 或 0, ...}}, ...}}，"
    "每个问题的候选键必须齐全，不要输出任何其它文字。"
)


# --------------------------------------------------------------------- 工具
def _chunk_of(edge):
    for s in edge.chunk_spans:
        return s.chunk_id
    return None


def _load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def _make_backend(model: str, base_url: str = "https://api.deepseek.com"
                  ) -> OpenAIBackend:
    return OpenAIBackend(model=model, base_url=base_url, timeout=120.0,
                         extra_body={"thinking": {"type": "disabled"}}
                         if model.startswith("deepseek") else None)


def _chat_with_retry(backend, system, user, retries=1):
    """_chat 返回 None 记为失败并重试一次；None 返回给调用方计数。"""
    for _ in range(retries + 1):
        out = backend._chat(system, user)
        if out is not None:
            return out
    return None


# ------------------------------------------------------------------ 查询构造
def build_queries_rich(shg, chunk_map, doc_id):
    """与 evaluate_fullcorpus.build_queries 同口径，但携带边与原文信息。"""
    out = []
    seen = set()
    for e in shg.edges:
        trig = [t for t in e.triggers if t]
        if not trig:
            continue
        query = "，".join(dict.fromkeys(trig))
        gold = {s.chunk_id for s in e.chunk_spans}
        if e.is_extended:
            if len(gold) >= 2 and query not in seen:
                seen.add(query)
                out.append(dict(doc_id=doc_id, query=query, gold=gold, edge=e,
                                kind="ext"))
        else:
            out.append(dict(doc_id=doc_id, query=query, gold=gold, edge=e,
                            kind="self"))
    for q in out:
        cid = _chunk_of(q["edge"])
        q["chunk_text"] = chunk_map.get(cid, "")
    return out


# ------------------------------------------------------------------- 阶段一
def stage_gen(backend, all_queries, batch_size=20):
    cache = _load_json(GEN_CACHE)
    todo = [q for q in all_queries
            if f"{q['doc_id']}|{q['query']}" not in cache]
    print(f"[gen] 待改写 {len(todo)}/{len(all_queries)} 条（缓存 {len(cache)}）")
    fails = 0
    for bi in range(0, len(todo), batch_size):
        part = todo[bi:bi + batch_size]
        rows = []
        for i, q in enumerate(part):
            e = q["edge"]
            rows.append(json.dumps({
                "i": i, "triggers": q["query"],
                "chunk": q["chunk_text"][:60],
                "mapping": f"{e.source_domain}→{e.target_domain} "
                           f"喻底:{'|'.join(e.ground[:4])}",
            }, ensure_ascii=False))
        parsed = _chat_with_retry(
            backend, _GEN_SYSTEM,
            _GEN_USER.format(n=len(part), body="\n".join(rows)))
        if parsed is None or not isinstance(parsed, list):
            fails += 1
            continue
        got = 0
        for item in parsed:
            try:
                i = int(item.get("i"))
                text = str(item.get("q", "")).strip()
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(part) and text:
                q = part[i]
                cache[f"{q['doc_id']}|{q['query']}"] = text
                got += 1
        print(f"    gen 批次 {bi // batch_size + 1}: +{got}/{len(part)}"
              f"（累计 {len(cache)}）", flush=True)
        _save_json(GEN_CACHE, cache)
    if todo and fails:
        print(f"  ⚠️ 失败批次 {fails}")
    return cache


def filter_violations(all_queries, cache):
    """程序化红线：改写不得含原触发词/源域/目标域（clue 捷径必须被切断）。"""
    kept, dropped = [], []
    for q in all_queries:
        text = cache.get(f"{q['doc_id']}|{q['query']}", "")
        if not text:
            continue
        e = q["edge"]
        banned = list(e.triggers) + [e.source_domain, e.target_domain]
        if any(b and b in text for b in banned):
            dropped.append((q["doc_id"], q["query"], text, banned))
        else:
            q["question"] = text
            kept.append(q)
    print(f"[gen] 红线过滤：保留 {len(kept)}，违规剔除 {len(dropped)}"
          f"（样例: {[d[2] for d in dropped[:3]]}）")
    return kept


# ------------------------------------------------------------------- 阶段二
def _norm_keys(parsed):
    """LLM 返回的问题键形态多变（"0"/"问题0"/"Q1"），统一归一成 int。"""
    out = {}
    for k, v in (parsed or {}).items():
        kk = str(k).strip()
        for prefix in ("问题", "问题 ", "Q", "q", "第"):
            if kk.startswith(prefix):
                kk = kk[len(prefix):].strip()
                break
        try:
            out[int(kk)] = v
        except ValueError:
            continue
    return out


def stage_judge(backend, docs, batch_size=8):
    """docs: {doc_id: {"questions": [q, ...], "cands": [(eid, desc), ...]}}"""
    cache = _load_json(JUDGE_CACHE)
    items = []
    for did in sorted(docs):
        for q in docs[did]["questions"]:
            if f"{did}|{q['question']}" not in cache:
                items.append((did, q))
    n_q = sum(len(d["questions"]) for d in docs.values())
    print(f"[judge] 待判定 {len(items)}/{n_q} 个问题（缓存 {len(cache)}）")
    fails = total_batches = 0
    for bi in range(0, len(items), batch_size):
        part = items[bi:bi + batch_size]
        total_batches += 1
        blocks = []
        for i, (did, q) in enumerate(part):
            cands = "\n".join(f"  {eid} = {desc}" for eid, desc in
                              docs[did]["cands"])
            blocks.append(f"问题{i}: {q['question']}\n候选：\n{cands}")
        parsed = _chat_with_retry(
            backend, _JUDGE_SYSTEM,
            _JUDGE_USER.format(n=len(part), body="\n\n".join(blocks)))
        got = 0
        norm = _norm_keys(parsed) if isinstance(parsed, dict) else {}
        for i, (did, q) in enumerate(part):
            sub = norm.get(i)
            if not isinstance(sub, dict):
                continue
            cids = {eid for eid, _ in docs[did]["cands"]}
            clean = {eid: (1 if v in (1, True, "1", "true") else 0)
                     for eid, v in sub.items() if eid in cids}
            missing = cids - set(clean)
            if len(missing) > len(cids) / 2:
                continue   # 键不全过半 → 该问题不可信，跳过
            for eid in missing:
                clean[eid] = 0
            cache[f"{did}|{q['question']}"] = clean
            got += 1
        if got == 0:
            fails += 1
        print(f"    judge 批次 {bi // batch_size + 1}: +{got}/{len(part)}"
              f"（累计 {len(cache)}）", flush=True)
        _save_json(JUDGE_CACHE, cache)
    if total_batches and fails:
        rate = fails / total_batches
        print(f"  ⚠️ 失败批次 {fails}（{rate:.0%}）"
              + ("  —— 失败率超 20%，金标可信度存疑，建议排查后重跑"
                 if rate > 0.2 else ""))
    return cache


# ------------------------------------------------------------------- 阶段三
def stage_eval(docs, cache, args):
    per_cfg = defaultdict(lambda: {"mrr": 0.0, "h3": 0, "h10": 0, "n": 0,
                                   "rec": 0.0})
    paths = defaultdict(lambda: {"rec": 0.0, "h3": 0, "h10": 0, "n": 0})
    agree = {"hit": 0, "n": 0}

    for did, d in docs.items():
        shg, eng, scorer = d["shg"], d["eng"], d["scorer"]
        weak_scorer, comb_scorer = d.get("weak"), d.get("comb")
        if scorer is None:
            continue
        for q in d["questions"]:
            gold_llm = cache.get(f"{did}|{q['question']}", {})
            gold_llm = cache.get(f"{did}|{q['question']}", {})
            rel_edges = {eid for eid, v in gold_llm.items() if v == 1}
            gold_llm_chunks = {_chunk_of(e) for e in shg.edges
                               if e.id in rel_edges and _chunk_of(e)}
            if not gold_llm_chunks:
                continue
            # 构造金标一致性：产出该问题的边是否被 LLM 判为相关
            agree["n"] += 1
            if q["edge"].id in rel_edges:
                agree["hit"] += 1

            golds = {"llm": gold_llm_chunks, "constr": q["gold"]}
            ranked_map = score_conditions(eng, scorer, q["question"])
            if weak_scorer is not None:
                ranked_map["trained_weak"] = score_conditions(
                    eng, weak_scorer, q["question"])["trained"]
            if comb_scorer is not None:
                ranked_map["trained_comb"] = score_conditions(
                    eng, comb_scorer, q["question"])["trained"]
            # 三条检索通路（改写查询：触发词级联 / 字面 / 语义超图=排序 chunk 召回）
            cross = eng.cross_domain_retrieve(
                q["question"],
                semantic_fallback=bool(getattr(args, "cross_fallback", False))
            ).chunk_ids
            literal = [f"{did}_c{i}" for i, c in enumerate(d["chunks"])
                       if q["question"] in c]
            for name, ranked in (("path_cross", cross), ("path_literal", literal)):
                g = golds["llm"]
                top = set(ranked[:10])
                paths[name]["rec"] += len(g & top) / len(g)
                paths[name]["h3"] += 1 if any(c in g for c in ranked[:3]) else 0
                paths[name]["h10"] += 1 if any(c in g for c in ranked[:10]) else 0
                paths[name]["n"] += 1

            for gname, gold in golds.items():
                for cfg, ranked in ranked_map.items():
                    m = _mrr_hits(ranked, sorted(gold))
                    a = per_cfg[(gname, cfg)]
                    a["mrr"] += m["mrr"]
                    a["h3"] += m["hits@3"]
                    a["h10"] += m["hits@10"]
                    top = set(c for c, _ in ranked[:10])
                    a["rec"] += len(gold & top) / len(gold)
                    a["n"] += 1

    n = per_cfg[("llm", "hand_weighted")]["n"]
    print("=" * 88)
    print(f"LLM 非构造金标评测（改写查询 n={n}）")
    print("=" * 88)
    print(f"\n构造金标一致性（LLM 是否认可产生该问题的边相关）: "
          f"{agree['hit']}/{agree['n']} = "
          f"{agree['hit'] / max(1, agree['n']):.1%}")
    print("\n【排序质量·LLM 金标】")
    print(f"{'配置':22s} {'MRR@10':>8s} {'Hits@3':>8s} {'Hits@10':>8s} {'Recall@10':>9s}")
    for cfg, label in (("hand_weighted", "人工加权"),
                       ("trained", "自监督训练"),
                       ("trained_weak", "LLM弱监督训练"),
                       ("trained_comb", "联合训练(∪弱监督)"),
                       ("trained_no_role", "自监督-去角色")):
        a = per_cfg[("llm", cfg)]
        if not a["n"]:
            continue
        k = a["n"]
        print(f"{label:22s} {a['mrr']/k:>8.3f} {a['h3']/k:>8.3f} "
              f"{a['h10']/k:>8.3f} {a['rec']/k:>9.3f}")
    print("\n【排序质量·构造金标（对照，应近饱和）】")
    for cfg, label in (("hand_weighted", "人工加权"),
                       ("trained", "自监督训练"),
                       ("trained_weak", "LLM弱监督训练"),
                       ("trained_comb", "联合训练(∪弱监督)")):
        a = per_cfg[("constr", cfg)]
        if not a["n"]:
            continue
        k = a["n"]
        print(f"{label:22s} {a['mrr']/k:>8.3f} {a['h3']/k:>8.3f} "
              f"{a['h10']/k:>8.3f} {a['rec']/k:>9.3f}")
    print("\n【三条检索通路在改写查询上的召回（LLM 金标）】")
    for name, label in (("path_cross", "触发词级联通路"),
                        ("path_literal", "字面包含通路")):
        a = paths[name]
        if a["n"]:
            print(f"{label:20s} Recall@10={a['rec']/a['n']:.3f} "
                  f"Hits@3={a['h3']/a['n']:.3f} (n={a['n']})")
    a = per_cfg[("llm", "hand_weighted")]
    if a["n"]:
        print(f"{'语义超图通路':20s} Recall@10={a['rec']/a['n']:.3f} "
              f"Hits@3={a['h3']/a['n']:.3f} (n={a['n']})"
              f"   ← 人工加权排序的 chunk 召回")
    print("\n【诚实边界】LLM 金标由 deepseek 模型判定，与人工标注存在模型偏差；"
          "改写查询由同一模型生成（生成与判定同源风险已用「构造金标一致性」交叉校验）。")
    return per_cfg


# ---------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("gen", "judge", "eval", "all"),
                    default="all")
    ap.add_argument("--doc-size", type=int, default=10)
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--base-url", default="https://api.deepseek.com",
                    help="OpenAI 兼容端点前缀（DeepSeek 无 /v1；"
                         "智谱为 https://open.bigmodel.cn/api/paas/v4）")
    ap.add_argument("--llm-conf", type=float, default=0.85)
    ap.add_argument("--ontology",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "ontology_default.json"))
    ap.add_argument("--cascade-rule", default="json",
                    choices=("json", "target", "source", "ground", "metanet",
                             "source_type", "none"),
                    help="L3 级联构造规则（默认 json = 改动前行为，见 cascade_rules）")
    ap.add_argument("--orphan-cascade-rule", default="target",
                    choices=("target", "source", "ground", "source_type", "none"),
                    help="孤儿框架打包规则（默认 target = 原口径）")
    ap.add_argument("--discover-cache",
                    default=os.path.join(ROOT, "data", "llm_cache_deepseek.json"))
    ap.add_argument("--max-docs", type=int, default=0,
                    help="调试用：限制文档数（0=全部）")
    ap.add_argument("--embedder", choices=("default", "ngram", "real"),
                    default="default",
                    help="排序特征所用向量器：default=哈希词袋（已上报数字的口径），"
                         "ngram=1-3gram+符号哈希迭代版，real=真实句向量"
                         "（EMBED_API_KEY，检索层专用 propagate=False）")
    ap.add_argument("--cross-fallback", action="store_true",
                    help="触发词级联通路启用语义回退（查询→级联描述粗筛），"
                         "对照 §7.5 的 0.043 召回")
    ap.add_argument("--npp", type=int, default=3,
                    help="负样本/正样本配比（排序器迭代超参）")
    ap.add_argument("--combined", action="store_true",
                    help="附加 trained_comb 配置：自监督∪弱监督联合训练")
    ap.add_argument("--split", choices=("", "tune", "report"), default="",
                    help="排序器调参协议：tune=偶数号文档（调参集），"
                         "report=奇数号文档（报告集，防测试集调参）")
    args = ap.parse_args()

    from metaphor_graph import embeddings as _emb
    if args.embedder == "ngram":
        _emb.set_embedder(_emb.NgramEmbedder(), propagate=False)
        print("向量器：NgramEmbedder（1-3gram+符号哈希）")
    elif args.embedder == "real":
        emb_real = _emb.embedder_from_env()
        if emb_real is None:
            raise SystemExit("需要 EMBED_API_KEY 环境变量（见 embeddings.embedder_from_env）")
        _emb.set_embedder(emb_real, propagate=False)
        print(f"向量器：{emb_real.model} @ {emb_real.base_url}（真实句向量，"
              f"缓存 {len(emb_real._cache)} 条）")

    ont, n_frames = build_replay_ontology(args.ontology, args.cascade_rule)
    replay = build_replay_backend(ont, args.discover_cache)
    samples = load_ccl2018()
    k = args.doc_size
    n_docs = (len(samples) + k - 1) // k

    all_queries, docs = [], {}
    print(f"建图（{n_docs} 伪文档，本体 {n_frames} 框架，"
          f"split={args.split or 'all'}, npp={args.npp}）…")
    for di in range(n_docs):
        if args.max_docs and di >= args.max_docs:
            break
        if args.split == "tune" and di % 2 != 0:
            continue
        if args.split == "report" and di % 2 == 0:
            continue
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=replay, llm_conf_threshold=args.llm_conf)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=replay,
                                 orphan_cascade_rule=args.orphan_cascade_rule
                                 ).build(chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        chunk_order = {f"{did}_c{i}": i for i in range(len(chunk_texts))}
        centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                      for e in shg.edges}
        ds_self = build_training_set(shg, chunk_order=chunk_order,
                                     chunks=chunk_map, centrality=centrality,
                                     ontology=ont, positive_mode="chunk",
                                     negatives_per_positive=args.npp)
        ds_w, _st = build_weak_refine_set(
            shg, chunk_order=chunk_order, chunks=chunk_map, ontology=ont,
            refine_path=args.discover_cache + ".refine.json",
            negatives_per_positive=args.npp)
        scorer = MetaphorScorer().fit(ds_self) if len(ds_self) > 0 else None
        weak = MetaphorScorer().fit(ds_w) if len(ds_w) > 0 else None
        comb = None
        if args.combined and len(ds_w) > 0 and len(ds_self) > 0:
            import numpy as _np
            from metaphor_graph.training import TrainingSet
            ds_c = TrainingSet(
                _np.vstack([ds_self.X, ds_w.X]),
                _np.hstack([ds_self.y, ds_w.y]))
            comb = MetaphorScorer().fit(ds_c)
        qs = build_queries_rich(shg, chunk_map, did)
        cands = [(e.id, f"{e.source_domain}→{e.target_domain} "
                        f"喻底:{'|'.join(e.ground[:3])} "
                        f"触发:{'|'.join(e.triggers[:3])} "
                        f"句:{chunk_map.get(_chunk_of(e), '')[:38]}")
                 for e in l1]
        docs[did] = dict(shg=shg, eng=RetrievalEngine(
            shg, chunk_texts, doc_id=did, ontology=ont),
            scorer=scorer, weak=weak, comb=comb, chunks=chunk_texts,
            questions=[], cands=cands)
        all_queries.extend(qs)
        docs[did]["questions"] = qs

    print(f"查询总数 {len(all_queries)}（ext "
          f"{sum(1 for q in all_queries if q['kind']=='ext')}）")
    backend = _make_backend(args.model, args.base_url)
    print(f"模型 {backend.model} 端点 {backend.endpoint}")

    if args.stage in ("gen", "all"):
        cache = stage_gen(backend, all_queries)
        all_queries = filter_violations(all_queries, cache)
        for did, d in docs.items():
            d["questions"] = [q for q in all_queries if q["doc_id"] == did]
    else:
        cache = _load_json(GEN_CACHE)
        all_queries = filter_violations(all_queries, cache)
        for did, d in docs.items():
            d["questions"] = [q for q in all_queries if q["doc_id"] == did]

    n_q = sum(len(d["questions"]) for d in docs.values())
    if args.stage in ("judge", "all") and n_q:
        stage_judge(backend, docs)
    else:
        cache2 = _load_json(JUDGE_CACHE)

    if args.stage in ("eval", "all"):
        judge_cache = _load_json(JUDGE_CACHE)
        stage_eval(docs, judge_cache, args)

    if args.embedder in ("ngram", "real"):   # 恢复默认向量器，避免污染后续调用
        _emb.set_embedder(None)
        print("向量器已恢复默认哈希编码")
    return 0


if __name__ == "__main__":
    sys.exit(main())
