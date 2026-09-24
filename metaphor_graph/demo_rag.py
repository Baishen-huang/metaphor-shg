# -*- coding: utf-8 -*-
"""端到端隐喻 RAG demo（路线图 §8.2 长期项：检索→生成受隐喻结构约束）。

**它演示什么**
检索层的三条通路（跨域 / 语义超图 / RRF）此前都只测到「召回 chunk」为止。
本脚本把最后一步接上：用隐喻超图的**结构化上下文**（超边描述 50% + 实体 30%
+ 源文本 20%，ContextBudget 预算打包）约束 LLM 生成，并给出**对照组**——
同一问题用纯向量相似度选出的 chunk（不含隐喻结构）生成。

标杆案例（方案 §4.4.1）："为什么我们的项目推进不动？"——文档写的是"陷在泥潭"。
预期：
  隐喻上下文组 → 正确引用"泥潭/拔出腿"的隐喻映射作答；
  纯向量对照组 → 检索不到泥潭 chunk（向量空间不近），答案无从落地。
这就是「图结构的合法性来自它提供了向量检索无法表达的关系」的端到端演示。

运行（需 LLM_API_KEY；检索侧走 LLM 缓存重放，零额外费用）：
    python -m metaphor_graph.demo_rag
生成结果落盘缓存 data/llm_cache_rag.json，重跑零请求、可复现。
"""

from __future__ import annotations

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph import embeddings
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.eval_corpus import DOCS, GOLD_RETRIEVAL
from metaphor_graph.llm_backend import OpenAIBackend

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_CACHE = os.path.join(ROOT, "data", "llm_cache_rag.json")

_GEN_SYSTEM = (
    "你是严谨的问答助手。**只依据给定材料回答问题**；材料中的【隐喻映射】"
    "是系统从文档中抽取的隐喻结构（源域→目标域），回答时应点明文档使用的"
    "隐喻框架（例如用「泥潭」比喻项目困境）。材料不足以回答时明确说不。"
    "回答不超过 120 字。"
)
_GEN_USER = "材料：\n{context}\n\n问题：{query}\n\n回答："


def _raw_chat(backend: OpenAIBackend, system: str, user: str) -> str:
    """纯文本补全：不走 _chat 的 JSON 解析（回答是自然语言，不是结构化输出）。"""
    import urllib.request
    payload = {"model": backend.model,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "temperature": backend.temperature}
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


def _answer(backend, query: str, context: str, cache: dict, tag: str) -> str:
    key = f"{tag}|{query}"
    if key in cache:
        return cache[key]
    try:
        text = _raw_chat(backend, _GEN_SYSTEM,
                         _GEN_USER.format(context=context, query=query))
    except Exception as e:   # 生成失败要显眼，不静默
        text = f"（生成失败：{type(e).__name__}: {str(e)[:80]}）"
    cache[key] = text
    _save(RAG_CACHE, cache)
    return text


def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def main():
    ont, n_frames = build_replay_ontology()
    replay = build_replay_backend(ont)
    backend = OpenAIBackend(model="deepseek-v4-flash",
                            base_url="https://api.deepseek.com",
                            timeout=120.0,
                            extra_body={"thinking": {"type": "disabled"}})
    cache = {}
    if os.path.exists(RAG_CACHE):
        with open(RAG_CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    # 真实句向量（可选）：设 EMBED_API_KEY 即自动升级检索/对照组向量
    if os.environ.get("EMBED_API_KEY"):
        from metaphor_graph import embeddings as _emb
        emb_real = _emb.embedder_from_env()
        _emb.set_embedder(emb_real, propagate=False)
        print(f"向量器：{emb_real.model}（真实句向量，对照组变严格）")
        print()

    did = "doc_project"
    chunks = DOCS[did]
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=replay, llm_conf_threshold=0.85)
    shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                             llm_backend=replay).build(chunks, doc_id=did)
    eng = RetrievalEngine(shg, chunks, doc_id=did, ontology=ont)

    # 只演示跨域问题（答案不在问题字面上）
    demos = [(q, list(gold)) for qd, q, gold in GOLD_RETRIEVAL
             if qd == did and "推进不动" in q]

    print("=" * 84)
    print("端到端隐喻 RAG demo：隐喻结构上下文 vs 纯向量对照")
    print("=" * 84)
    print(f"图：{shg.summary()}  ｜  本体 {n_frames} 框架  ｜  生成 {backend.model}\n")

    for query, gold in demos:
        gold_ids = [f"{did}_c{i}" for i in gold]
        print(f"问题：{query}")
        print(f"金标 chunk：{gold_ids}\n")

        # ---- 隐喻通路：rank_mappings（自适应阈值+排序）→ 50/30/20 打包 ----
        ranked, decision = eng.rank_mappings(query, top_k=5)
        top_ids = []
        for m in ranked:
            for s in m.chunk_spans:
                top_ids.append(s.chunk_id)
        pack = eng.pack_context(ranked, top_ids)
        used_chunks = [c for c in top_ids if c in set(pack.chunks)]
        hit = "✅" if set(gold_ids) & set(top_ids[:3]) else "❌"
        print(f"[隐喻通路] 命中金标 {hit}  检索 top chunk: {top_ids[:3]}")
        print(f"  超边上下文 {len(pack.hyperedges)} 条 / 实体 {len(pack.entities)} 个 / "
              f"chunk {len(pack.chunks)} 条（50/30/20 预算内）")
        for h in pack.hyperedges[:3]:
            print(f"    · {h[:70]}")
        ans_m = _answer(backend, query, pack.text, cache, "metaphor")
        print(f"  回答（隐喻上下文）：{ans_m}\n")

        # ---- 对照组：纯向量相似度选 chunk（无隐喻结构，B1 基线）----
        sims = sorted(
            ((embeddings.cosine(embeddings.embed(query),
                                embeddings.embed(c)), f"{did}_c{i}")
             for i, c in enumerate(chunks)),
            key=lambda x: -x[0])
        vec_top = [cid for _, cid in sims[:3]]
        vec_hit = "✅" if set(gold_ids) & set(vec_top) else "❌"
        ctx_literal = "【文档片段】\n" + "\n".join(
            f"- {chunks[int(cid.split('_c')[-1])]}" for cid in vec_top)
        ans_v = _answer(backend, query, ctx_literal, cache, "vector")
        print(f"[纯向量对照] 命中金标 {vec_hit}  向量 top chunk: {vec_top}"
              f"（相似度 {sims[0][0]:.3f}）")
        print(f"  回答（无隐喻结构）：{ans_v}\n")
        print("-" * 84)

    print(f"\nLLM 用量：{backend.usage_report()}")
    print(f"生成缓存：{RAG_CACHE}（{len(cache)} 条，重跑零请求）")
    print("\n【诚实注记】对照组向量随 EMBED_API_KEY 自动升级：哈希向量共享字面"
          " n-gram；真实句向量（embedding-3）则从语义上把「推进不动/寸步难行」与困境"
          "场景连起来（本例相似度 0.725，也命中）。跨域差距的严格量化在 evaluate_llmgold："
          "改写查询下字面通路 Recall=0.000、触发词级联 0.042，语义超图 1.000 ——"
          "隐喻结构的增益体现在「字面与级联都断链」的查询分布上，而非与向量基线的单点对比。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
