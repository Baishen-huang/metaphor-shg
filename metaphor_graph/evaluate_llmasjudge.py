# -*- coding: utf-8 -*-
"""LLM-as-judge 模拟人工评估预演（方案 §6.4 的降级版，投稿前需真人复验）。

方案 §6.4 设计了 7 分 Likert 人工评估（正确性 / 引用精确度 / 框架一致性 / 可读性，
3 语言学 + 3 领域 + 5 普通用户），但凑齐评估者前可以先用 LLM 盲评拿到一版
**模拟数据**——本脚本即是该预演：

1. 对 eval_corpus 两篇文档的 8 个跨域查询，分别用两种上下文生成答案：
   A=隐喻结构上下文（rank_mappings → ContextPack 50/30/20）
   B=纯向量对照（真实句向量 top-3 chunk，无隐喻结构；EMBED_API_KEY 可选但推荐）
2. **盲评**：答案匿名化（A/B 顺序按固定种子随机），LLM 按 4 维度各打 1-7 分；
   评卷时向 judge 提供金标 chunk 作参考（判正确性所需）。
3. 汇总两系统的维度均分与胜率。

诚实边界：生成与评判同用 LLM（deepseek-v4-flash），存在自偏好风险；样本仅 8 查询
（诊疗集）；本预演不替代人工评估，只用于尽早暴露生成质量问题。

运行（需 LLM_API_KEY；生成与判定均落盘缓存，重跑零请求）：
    python -m metaphor_graph.evaluate_llmasjudge
"""

from __future__ import annotations

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
from metaphor_graph import embeddings
from metaphor_graph.eval_corpus import DOCS, GOLD_RETRIEVAL
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.llm_backend import OpenAIBackend

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "llm_cache_llmasjudge.json")

_GEN_SYSTEM = ("你是严谨的问答助手。只依据给定材料回答问题；材料中的【隐喻映射】"
               "是系统从文档抽取的隐喻结构。材料不足以回答时明确说不。回答不超过 100 字。")
_JUDGE_SYSTEM = (
    "你是严格的问答质量评估专家。给你一个问题、参考材料、两个匿名答案（A/B）。"
    "按四个维度各打 1-7 分（7 最好）：正确性（与参考材料一致、无编造）、"
    "引用精确度（明确指出依据出自何处）、框架一致性（是否沿用材料的概念框架表述）、"
    "可读性。只输出 JSON：{\"A\": {\"正确性\": n, \"引用精确度\": n, \"框架一致性\": n, "
    "\"可读性\": n}, \"B\": {...}}，不要输出其它文字。"
)

DIMS = ["正确性", "引用精确度", "框架一致性", "可读性"]


def _raw_chat(backend, system, user) -> str:
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


def _cached(cache, key, fn):
    if key in cache:
        return cache[key]
    try:
        val = fn()
    except Exception as e:
        val = f"（调用失败：{type(e).__name__}: {str(e)[:60]}）"
    cache[key] = val
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    return val


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--base-url", default="https://api.deepseek.com")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY")
    ont, n_frames = build_replay_ontology()
    replay = build_replay_backend(ont)
    backend = OpenAIBackend(model=args.model, base_url=args.base_url,
                            timeout=120.0,
                            extra_body={"thinking": {"type": "disabled"}}
                            if args.model.startswith("deepseek") else None)
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    import numpy as _np
    rng = _np.random.default_rng(20260830)

    print("=" * 84)
    print("LLM-as-judge 模拟人工评估预演（隐喻结构上下文 vs 纯向量对照，盲评）")
    print("=" * 84)

    scores = defaultdict(lambda: defaultdict(list))   # system -> dim -> [scores]
    wins = defaultdict(int)
    n_q = 0
    for did, chunks in DOCS.items():
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=replay, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=replay).build(chunks, doc_id=did)
        eng = RetrievalEngine(shg, chunks, doc_id=did, ontology=ont)
        for q_doc, query, gold in GOLD_RETRIEVAL:
            if q_doc != did:
                continue
            gold_ids = [f"{did}_c{i}" for i in gold]
            # A：隐喻结构上下文
            ranked, _ = eng.rank_mappings(query, top_k=5)
            top_ids = [s.chunk_id for m in ranked for s in m.chunk_spans]
            pack = eng.pack_context(ranked, top_ids)
            ans_meta = _cached(cache, f"gen|meta|{query}",
                               lambda: _raw_chat(backend, _GEN_SYSTEM,
                                                 f"材料：\n{pack.text}\n\n问题：{query}\n\n回答："))
            # B：纯向量对照（真实句向量若可用，否则哈希）
            vec_top = [cid for _, cid in sorted(
                ((embeddings.cosine(embeddings.embed(query),
                                    embeddings.embed(c)), f"{did}_c{i}")
                 for i, c in enumerate(chunks)), key=lambda x: -x[0])[:3]]
            ctx_vec = "【文档片段】\n" + "\n".join(
                f"- {chunks[int(c.split('_c')[-1])]}" for c in vec_top)
            ans_vec = _cached(cache, f"gen|vec|{query}",
                              lambda: _raw_chat(backend, _GEN_SYSTEM,
                                                f"材料：\n{ctx_vec}\n\n问题：{query}\n\n回答："))
            reference = "\n".join(f"- {chunks[int(c.split('_c')[-1])]}"
                                  for c in gold_ids)
            # 盲评：A/B 顺序按种子随机
            order = ["meta", "vec"] if rng.random() < 0.5 else ["vec", "meta"]
            answers = {"meta": ans_meta, "vec": ans_vec}
            body = (f"问题：{query}\n参考材料：\n{reference}\n\n"
                    f"答案A：\n{answers[order[0]]}\n\n答案B：\n{answers[order[1]]}")
            def _judge():
                out = _raw_chat(backend, _JUDGE_SYSTEM, body)
                from metaphor_graph.llm_backend import _parse_json_blob
                return _parse_json_blob(out)
            verdict = _cached(cache, f"judge|{query}", _judge)
            if not isinstance(verdict, dict):
                print(f"  ⚠️ 判定解析失败：{query[:20]}…")
                continue
            n_q += 1
            pos = {"A": order[0], "B": order[1]}
            tot = {"meta": 0.0, "vec": 0.0}
            for anon, sysname in pos.items():
                sub = verdict.get(anon, {})
                for dim in DIMS:
                    v = sub.get(dim, sub)
                    try:
                        v = float(str(v).replace("分", "")[:2])
                    except (TypeError, ValueError):
                        v = 0.0
                    scores[sysname][dim].append(v)
                    tot[sysname] += v
            if tot["meta"] > tot["vec"]:
                wins["meta"] += 1
            elif tot["vec"] > tot["meta"]:
                wins["vec"] += 1

    print(f"\n有效查询 n={n_q}｜总分胜率：隐喻结构 {wins['meta']} : 对照 {wins['vec']}")
    print(f"\n{'维度':10s} {'隐喻结构':>10s} {'纯向量对照':>10s}")
    for dim in DIMS:
        m = (sum(scores["meta"][dim]) / len(scores["meta"][dim])
             if scores["meta"][dim] else 0.0)
        v = (sum(scores["vec"][dim]) / len(scores["vec"][dim])
             if scores["vec"][dim] else 0.0)
        print(f"{dim:10s} {m:>10.2f} {v:>10.2f}")
    print("\n【诚实边界】生成与评判同用 LLM（自偏好风险）；n=8 诊疗集查询；"
          "本预演仅用于尽早暴露生成质量问题，投稿前须以真人评估复验（方案 §6.4）。")
    print(f"缓存：{CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
