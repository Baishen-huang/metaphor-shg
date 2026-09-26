# -*- coding: utf-8 -*-
"""A6：通用常识图谱 vs 专属隐喻知识（方案 §6.3 最后一项消融）。

**口径说明（诚实优先）**：原设计用 ConceptNet——公开 API 实测 502（2026-08-30
多次复现），离线断言子图过重。本实现用**同一 LLM（GLM）生成的通用常识关联**
作替代知识源：对隐喻图 vocabulary 中的每个概念域，让模型列出「日常常识相关
概念」（明确要求非隐喻用法）——构建一张常识关联图，再走「查询 → 常识邻居 →
chunk 字面匹配」通路，与隐喻通路在同一金标（LLM 非构造金标，n=改写查询）上对比。

**方法学优势**：同一模型生成常识关联与抽取隐喻结构，把「知识类型」变量隔离
（常识关联 vs 隐喻级联结构），模型能力/语言风格被固定。
**局限**：替代源非外部独立知识库（ConceptNet 不可用的既定阻塞），结论强度
弱于原设计；ConceptNet 恢复后应复测。

**预期（方案引据）**：MetaphorBoost 消融显示换通用常识图谱性能下降——
常识关联覆盖近义/相关概念，但「推进不动→泥潭」这类跨域映射不是常识关联。

运行（需 LLM_API_KEY）：
    python -m metaphor_graph.evaluate_a6
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.evaluate_real import build_llm_backend
from metaphor_graph.llm_backend import (PrecomputedBackend, batch_discover,
                                        batch_refine, _RefineCollector,
                                        _parse_json_blob)
from metaphor_graph.evaluate_llmgold import build_queries_rich
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.llm_backend import load_table as _lt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "data", "corpus")
DISCOVER_CACHE = os.path.join(CORPUS, "llm_cache_corpus.json")
DEFAULT_DISCOVER_CACHE = os.path.join(ROOT, "data", "llm_cache_deepseek.json")
REFINE_CACHE = DISCOVER_CACHE + ".refine.json"
CS_CACHE = os.path.join(CORPUS, "cs_neighbors.json")
GEN_CACHE = os.path.join(ROOT, "data", "llm_cache_paraphrase.json")
JUDGE_CACHE = os.path.join(ROOT, "data", "llm_cache_judge.json")

_CS_SYSTEM = (
    "你是常识知识库构建者。对每个概念词，列出它在**日常常识**中相关联的 12 个"
    "通用概念词（1-4 字名词/动词均可）。要求：真实的常识关联（共现、类属、"
    "功能、因果），**不要隐喻或比喻义**。"
)
_CS_USER = (
    "概念词（共 {n} 个）：{terms}\n"
    "只输出 JSON 对象：{{\"词\": [\"相关概念\", ...], ...}}，键必须齐全，"
    "每个值恰好 12 个，不要输出其它文字。"
)


def _raw_chat(backend, system, user) -> str:
    import urllib.request
    payload = {"model": backend.model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "temperature": 0.2}
    if backend.extra_body:
        payload.update(backend.extra_body)
    req = urllib.request.Request(
        backend.endpoint, data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {backend.api_key}"})
    with urllib.request.urlopen(req, timeout=backend.timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    backend._accumulate_usage(data.get("usage"))
    return str(data["choices"][0]["message"]["content"]).strip()


def build_cs_neighbors(backend, terms: list, batch_size: int = 16) -> dict:
    """为概念词批量生成常识邻居（落盘缓存，重跑零请求）。"""
    cache = {}
    if os.path.exists(CS_CACHE):
        with open(CS_CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    todo = [t for t in terms if t not in cache]
    print(f"[常识图谱] 待生成 {len(todo)}/{len(terms)} 个概念词的邻居"
          f"（缓存 {len(cache)}）")
    fails = 0
    for bi in range(0, len(todo), batch_size):
        part = todo[bi:bi + batch_size]
        user = _CS_USER.format(n=len(part), terms="、".join(part))
        parsed = None
        for _ in range(2):
            try:
                out = _raw_chat(backend, _CS_SYSTEM, user)
                parsed = _parse_json_blob(out)
                if isinstance(parsed, dict) and parsed:
                    break
            except Exception as e:
                print(f"    [cs 批次失败] {type(e).__name__}: {str(e)[:60]}",
                      flush=True)
                time.sleep(3)
        if not parsed:
            fails += 1
            continue
        got = 0
        for t in part:
            v = parsed.get(t)
            if isinstance(v, list) and v:
                cache[t] = [str(x)[:6] for x in v[:12]]
                got += 1
        print(f"    cs 批次 {bi // batch_size + 1}: +{got}/{len(part)}"
              f"（累计 {len(cache)}）", flush=True)
        with open(CS_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    if fails:
        print(f"  ⚠️ 失败批次 {fails}")
    return cache


def main():
    import argparse
    ap = argparse.ArgumentParser(description="A6 知识源消融（离线缓存重放）")
    ap.add_argument("--cascade-rule", default="json",
                    choices=("json", "target", "source", "ground", "metanet",
                             "source_type", "none"),
                    help="L3 级联构造规则（默认 json = 改动前行为）")
    ap.add_argument("--meta-top-k", type=int, default=20,
                    help="隐喻通路的候选预算。原为硬编码 5，比常识通路"
                         "（无上限）小，实测低估 Recall@10 约 17pp；"
                         "20 已与无上限等价（1.0000）")
    ap.add_argument("--orphan-cascade-rule", default="target",
                    choices=("target", "source", "ground", "source_type", "none"))
    args = ap.parse_args()
    # ---- 重建 llmgold 同款文档图（CCL2018 伪文档 fc*，缓存重放零请求）----
    # 注意：改写查询与 LLM 金标缓存键都是 fc 文档 —— A6 必须在同一查询集上比较
    # （初版误用语料库文档 cj/gov/lx，键对不上，n=0，已修正）。
    ont, _ = build_replay_ontology(cascade_rule=args.cascade_rule)
    samples = load_ccl2018()
    pre = build_replay_backend(ont, DEFAULT_DISCOVER_CACHE)
    gen_cache = json.load(open(GEN_CACHE, encoding="utf-8"))         if os.path.exists(GEN_CACHE) else {}
    judge_cache = json.load(open(JUDGE_CACHE, encoding="utf-8"))         if os.path.exists(JUDGE_CACHE) else {}

    by_doc = defaultdict(list)
    for i, smp in enumerate(samples):
        by_doc[f"fc{i // 10}"].append(smp)
    ex = MetaphorExtractor(ontology=ont, use_semfield=True, llm_backend=pre,
                           llm_conf_threshold=0.85)

    questions, seeds, engines, doc_chunks = [], set(), {}, {}
    for did, ss in sorted(by_doc.items()):
        chunk_texts = [x.text for x in ss]
        doc_chunks[did] = chunk_texts
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=pre,
                                 orphan_cascade_rule=args.orphan_cascade_rule
                                 ).build(chunk_texts, doc_id=did)
        engines[did] = RetrievalEngine(shg, chunk_texts, doc_id=did,
                                       ontology=ont)
        for e in shg.edges:
            if not e.is_extended:
                seeds.add(e.source_domain)
                seeds.add(e.target_domain)
        qs = build_queries_rich(shg, {f"{did}_c{i}": c for i, c in
                                      enumerate(chunk_texts)}, did)
        for q in qs:
            text = gen_cache.get(f"{did}|{q['query']}", "")
            if not text:
                continue
            gold_llm = judge_cache.get(f"{did}|{text}", {})
            rel_edges = {eid for eid, v in gold_llm.items() if v == 1}
            gold_chunks = {c for e in shg.edges if e.id in rel_edges
                           for c in {s.chunk_id for s in e.chunk_spans}}
            if gold_chunks:
                questions.append(dict(doc_id=did, question=text,
                                      gold=gold_chunks))
    print(f"查询就绪：{len(questions)} 条改写查询（LLM 金标）；"
          f"概念词 {len(seeds)} 个")

    # ---- 常识邻居生成（真实调用，落盘缓存）----
    llm = build_llm_backend()
    llm.timeout = 180.0
    neighbors = build_cs_neighbors(llm, sorted(seeds))

    # ---- 三通路对比（同一组查询与金标）----
    agg = defaultdict(lambda: {"rec": 0.0, "h3": 0, "h10": 0, "n": 0})
    term_hit = 0
    examples = []
    for q in questions:
        did = q["doc_id"]
        chunk_texts = doc_chunks[did]
        gold = q["gold"]
        # ① 常识通路：问题中出现的概念词 → 常识邻居 → chunk 字面匹配
        hit_terms = [t for t in neighbors
                     if len(t) >= 2 and t in q["question"]]
        cand = defaultdict(float)
        if hit_terms:
            term_hit += 1
            pool = set()
            for t in hit_terms:
                pool |= set(neighbors.get(t, []))
            for i, c in enumerate(chunk_texts):
                sc = sum(1 for n in pool if n and n in c)
                if sc:
                    cand[f"{did}_c{i}"] += float(sc)
        cs_ranked = [c for c, _ in sorted(cand.items(), key=lambda x: -x[1])]
        # ② 隐喻通路（语义超图排序）
        #
        # ⚠️ 预算对等（实测修正）：原实现用 top_k=5，而常识通路**无上限** ——
        # 两臂搜索预算不对等，人为压低隐喻通路。实测同一查询集：
        #   top_k=5  → Recall@10 = 0.8287
        #   top_k=20 → Recall@10 = **1.0000**（与无上限一致）
        # 即原数字低估了隐喻通路约 17pp。改用与常识臂可比的预算。
        eng = engines[did]
        ranked, _dec = eng.rank_mappings(q["question"], top_k=args.meta_top_k,
                                         adaptive=False)
        meta_ranked = []
        for m in ranked:
            for s in m.chunk_spans:
                if s.chunk_id not in meta_ranked:
                    meta_ranked.append(s.chunk_id)
        for name, ranked in (("cs", cs_ranked), ("meta", meta_ranked)):
            top = set(ranked[:10])
            agg[name]["rec"] += len(gold & top) / len(gold)
            agg[name]["h3"] += 1 if any(c in gold for c in ranked[:3]) else 0
            agg[name]["h10"] += 1 if any(c in gold for c in ranked[:10]) else 0
            agg[name]["n"] += 1
        if len(examples) < 3 and cs_ranked and gold not in set(
                cs_ranked[:10]):
            examples.append((q["question"][:30], hit_terms[:3],
                             sorted(gold)[:2], cs_ranked[:3]))

    n = agg["cs"]["n"]
    print("=" * 84)
    print(f"A6 · 通用常识图谱（AI 生成替代）vs 专属隐喻知识 —— n={n} 改写查询")
    print("=" * 84)
    print(f"查询含概念词命中（常识通路入口）: {term_hit}/{len(questions)}")
    for name, label in (("cs", "常识通路（AI 生成关联）"),
                        ("meta", "隐喻通路（语义超图）")):
        a = agg[name]
        if a["n"]:
            print(f"{label:24s} Recall@10={a['rec']/a['n']:.3f} "
                  f"Hits@3={a['h3']/a['n']:.3f} (n={a['n']})")
    if examples:
        print("\n【常识通路失败样例】")
        for qtxt, terms, gold, got in examples:
            print(f"  「{qtxt}」 概念词={terms} → 命中 {got}，金标 {gold}")
    print("\n【诚实边界】常识源为同厂商 LLM 生成的关联（非外部 ConceptNet——502 阻塞），"
          "但与隐喻结构同模型生成，隔离了「知识类型」变量；结论须 ConceptNet 恢复后复测。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
