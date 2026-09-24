# -*- coding: utf-8 -*-
"""上下文打包消融（针对 LLM-as-judge 预演的警示：检索召回优势未转化为生成优势）。

**假设**：当前 50/30/20（超边/实体/chunk）打包把大量框架描述注入上下文，
稀释了生成端注意力。本脚本在**同一 judge、同一查询集**下盲评 4 种打包变体：

  ctrl_vec   纯向量对照：向量 top-3 chunk，无隐喻结构（强基线）
  curr       当前打包：top-5 超边，0.5/0.3/0.2
  light      轻量隐喻：top-2 超边，0.2/0.1/0.7（chunk 为主，框架点到为止）
  chunk_only chunk 优先：0/0.1/0.9（只保留极少量实体，无超边描述）

**盲评设计**：每查询 4 个答案匿名化（A–D，顺序按固定种子随机），judge 用
glm-4.7-flash（**与生成模型 glm-5.3-flash 不同**，降低自偏好），按 4 维度打
1–7 分。判定与生成都落盘缓存，重跑零请求。

诚实边界：n=8 诊疗集查询；judge 与生成同厂商（跨模型降低但不消除自偏好）；
结论须真人评估复验。

运行（需 LLM_API_KEY=智谱）：
    python -m metaphor_graph.evaluate_packing_ablation
"""

from __future__ import annotations

import hashlib
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
from metaphor_graph.context_budget import ContextBudget
from metaphor_graph.eval_corpus import DOCS, GOLD_RETRIEVAL
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)
from metaphor_graph.llm_backend import OpenAIBackend, _parse_json_blob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "llm_cache_packing.json")
CACHE_TPL = os.path.join(ROOT, "data", "llm_cache_packing_{tag}.json")

VARIANTS = ["ctrl_vec", "curr", "light", "chunk_only"]
DIMS = ["正确性", "引用精确度", "框架一致性", "可读性"]

_GEN_SYSTEM = ("你是严谨的问答助手。只依据给定材料回答问题；材料中的【隐喻映射】"
               "是系统抽取的隐喻结构，可参考但不必逐条复述。材料不足以回答时明确说不。"
               "回答不超过 100 字。")
_JUDGE_SYSTEM = (
    "你是严格的问答质量评估专家。给你一个问题、参考材料、四个匿名答案（A/B/C/D）。"
    "按四个维度各打 1-7 分（7 最好）：正确性（与参考材料一致、无编造）、"
    "引用精确度（明确指出依据出处）、框架一致性（是否沿用材料的概念框架表述）、"
    "可读性。只输出 JSON：{\"A\": {\"正确性\": n, \"引用精确度\": n, \"框架一致性\": n, "
    "\"可读性\": n}, \"B\": {...}, \"C\": {...}, \"D\": {...}}，四个键必须齐全。"
)


def _raw_chat(backend, system, user) -> str:
    import time as _t
    import urllib.error
    import urllib.request
    for attempt in range(5):           # 429 退避重试（免费档限流）
        try:
            return _raw_chat_once(backend, system, user)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            _t.sleep(5 * (attempt + 1))


def _raw_chat_once(backend, system, user) -> str:
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
    val = None
    for _ in range(3):          # 瞬时超时重试（结果仍落缓存）
        try:
            val = fn()
            break
        except Exception as e:
            val = f"（调用失败：{type(e).__name__}: {str(e)[:50]}）"
    if val and str(val).startswith("（调用失败"):
        val = None               # 失败不入缓存，下次重试
        return val
    cache[key] = val
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    return val


def main():
    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY（智谱）")
    gen = OpenAIBackend(model="glm-5.3-flash",
                        base_url="https://open.bigmodel.cn/api/paas/v4",
                        timeout=240.0, extra_body={"reasoning_effort": "low"})
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-model", default="glm-5.3-flash",
                    help="judge 模型；缓存按模型分文件，支持多 judge 交叉")
    args = ap.parse_args()
    judge = OpenAIBackend(model=args.judge_model,
                          base_url="https://open.bigmodel.cn/api/paas/v4",
                          timeout=240.0,
                          extra_body={"reasoning_effort": "low"}
                          if args.judge_model.startswith("glm-5") else None)
    cache_file = CACHE_TPL.format(tag=args.judge_model.replace(".", "_"))
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)

    ont, _ = build_replay_ontology()
    replay = build_replay_backend(ont)

    import numpy as _np
    rng = _np.random.default_rng(20260831)

    scores = {v: defaultdict(list) for v in VARIANTS}
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
            reference = "\n".join(f"- {chunks[int(c.split('_c')[-1])]}"
                                  for c in gold_ids)
            ranked, _ = eng.rank_mappings(query, top_k=5)
            top_ids = [s.chunk_id for m in ranked for s in m.chunk_spans]
            he_texts = [m.describe() for m in ranked]
            ents = []
            for m in ranked:
                ents.extend([m.source_domain, m.target_domain])
                ents.extend(m.ground)
            chunk_texts = [eng._chunk_text[c] for c in top_ids
                           if c in eng._chunk_text]

            def gen_for(ctx):
                return _cached(cache, f"gen|{hashlib.md5(ctx.encode()).hexdigest()[:8]}|{query}",
                               lambda: _raw_chat(gen, _GEN_SYSTEM,
                                                 f"材料：\n{ctx}\n\n问题：{query}\n\n回答："))

            answers = {}
            # ctrl_vec：向量 top-3 chunk
            vec_top = [cid for _, cid in sorted(
                ((embeddings.cosine(embeddings.embed(query),
                                    embeddings.embed(c)), f"{did}_c{i}")
                 for i, c in enumerate(chunks)), key=lambda x: -x[0])[:3]]
            answers["ctrl_vec"] = gen_for("【文档片段】\n" + "\n".join(
                f"- {chunks[int(c.split('_c')[-1])]}" for c in vec_top))
            # curr：当前打包
            pack = eng.pack_context(ranked, top_ids)
            answers["curr"] = gen_for(pack.text)
            # light：轻量隐喻
            pack_l = ContextBudget(ratios=(0.2, 0.1, 0.7)).pack(
                he_texts[:2], ents[:8], chunk_texts)
            answers["light"] = gen_for(pack_l.text)
            # chunk_only：chunk 优先
            pack_c = ContextBudget(ratios=(0.0, 0.1, 0.9)).pack(
                [], [], chunk_texts)
            answers["chunk_only"] = gen_for(pack_c.text)

            # 盲评（A-D 随机顺序）
            order = list(VARIANTS)
            rng.shuffle(order)
            body = (f"问题：{query}\n参考材料：\n{reference}\n\n" +
                    "\n\n".join(f"答案{chr(65 + i)}：\n{answers[v]}"
                                for i, v in enumerate(order)))
            import time as _t2
            _t2.sleep(1.2)

            def _judge():
                out = _raw_chat(judge, _JUDGE_SYSTEM, body)
                return _parse_json_blob(out)
            verdict = _cached(cache, f"judge|{query}", _judge)
            if not isinstance(verdict, dict):
                print(f"  ⚠️ 判定解析失败：{query[:18]}…")
                continue
            n_q += 1
            pos = {chr(65 + i): v for i, v in enumerate(order)}
            tot = {v: 0.0 for v in VARIANTS}
            for anon, v in pos.items():
                sub = verdict.get(anon, {})
                for dim in DIMS:
                    val = sub.get(dim, 0)
                    try:
                        val = float(str(val).replace("分", "")[:2])
                    except (TypeError, ValueError):
                        val = 0.0
                    scores[v][dim].append(val)
                    tot[v] += val
            best = max(tot, key=lambda v: tot[v])
            wins[best] += 1

    print("=" * 84)
    print(f"上下文打包消融 · 盲评（judge={judge.model} ≠ 生成={gen.model}，n={n_q}）")
    print("=" * 84)
    print(f"{'变体':12s} " + " ".join(f"{d:>7s}" for d in DIMS) + f" {'总均分':>8s} {'最优胜率':>8s}")
    for v in VARIANTS:
        means = [sum(scores[v][d]) / len(scores[v][d]) if scores[v][d] else 0
                 for d in DIMS]
        total = sum(means)
        print(f"{v:12s} " + " ".join(f"{m:>7.2f}" for m in means)
              + f" {total:>8.2f} {wins[v] / max(1, n_q):>8.2f}")
    print("\n【诚实边界】n=8 诊疗集查询；judge 与生成同厂商（跨模型降低但不消除"
          "自偏好）；结论须真人评估复验。缓存：" + CACHE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
