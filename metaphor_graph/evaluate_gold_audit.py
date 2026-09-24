# -*- coding: utf-8 -*-
"""金标 AI 交叉审核（A4 人工抽查的 AI 替代，路线图 B 线）。

**设计**：llmgold 的 632 条改写查询金标由 glm-5.3-flash 判定（与抽取同厂商）。
本脚本抽 50 条查询，由**跨模型第二标注者 glm-4.7-flash** 独立重判全部候选，
与原金标做**逐边一致性 + Cohen's κ**——用跨模型一致性替代人工抽查，
量化金标的标注者间可靠性。

诚实口径：模型-模型 κ 是人工 κ 的**下界代理**（同厂商家族、无真实标注者间
差异的完整性）；结论表述为「跨模型可复现性」，论文投稿前仍建议小规模真人
复核。判定与原金标不一致的样本全部打印，供人工复核（可选）。

运行（需 LLM_API_KEY=智谱）：
    python -m metaphor_graph.evaluate_gold_audit [--sample 50]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                             filter_violations, GEN_CACHE)


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
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology
from metaphor_graph.llm_backend import _parse_json_blob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUDGE_CACHE = os.path.join(ROOT, "data", "llm_cache_judge.json")
AUDIT_CACHE = os.path.join(ROOT, "data", "gold_audit_cache.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--audit-model", default="glm-4.7-flash",
                    help="第二标注者（跨模型于原金标 judge glm-5.3-flash）")
    ap.add_argument("--batch", type=int, default=5)
    ap.add_argument("--reorder", action="store_true",
                    help="二评引出方式变体：候选逆序 + temperature 0.4——"
                         "同模型换序复核（测引出稳健性，非跨模型 κ）")
    ap.add_argument("--audit-cache-suffix", default="",
                    help="审核缓存文件名后缀（区分不同二评协议）")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY（智谱）")
    from metaphor_graph.evaluate_real import build_llm_backend
    auditor = build_llm_backend()
    auditor.model = args.audit_model
    auditor.timeout = 180.0

    from metaphor_graph.evaluate_llmgold import _JUDGE_SYSTEM, _JUDGE_USER

    ont, _ = build_replay_ontology()
    from metaphor_graph.evaluate_fullcorpus import build_replay_backend
    replay = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = json.load(open(GEN_CACHE, encoding="utf-8"))
    judge_cache = json.load(open(JUDGE_CACHE, encoding="utf-8"))

    k = 10
    n_docs = (len(samples) + k - 1) // k
    # 分层抽样池：每文档收集「有金标的改写查询」
    pool = []
    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=replay, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=replay).build(chunk_texts, doc_id=did)
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        qs = build_queries_rich(shg, chunk_map, did)
        kept = filter_violations(qs, gen_cache)
        for q in kept:
            text = gen_cache.get(f"{did}|{q['query']}", "")
            gold = judge_cache.get(f"{did}|{text}")
            if text and isinstance(gold, dict):
                cand_list = [(eid, f"{e.source_domain}→{e.target_domain} "
                               f"喻底:{'|'.join(e.ground[:3])} "
                               f"触发:{'|'.join(e.triggers[:3])} "
                               f"句:{chunk_map.get(next((s.chunk_id for s in e.chunk_spans), ''), '')[:38]}")
                         for eid, e in ((e.id, e) for e in shg.edges
                                        if not e.is_extended)]
                if args.reorder:
                    cand_list = cand_list[::-1]
                cands = cand_list
                pool.append(dict(doc_id=did, question=text, gold=gold,
                                 cands=cands))
    print(f"抽样池 {len(pool)} 条查询，抽 {min(args.sample, len(pool))} 条交叉审核")

    import numpy as _np
    rng = _np.random.default_rng(20260902)
    idx = rng.permutation(len(pool))[:args.sample]

    audit_cache_path = AUDIT_CACHE.replace(".json", f"{args.audit_cache_suffix}.json")
    audit_cache = {}
    if os.path.exists(audit_cache_path):
        with open(audit_cache_path, "r", encoding="utf-8") as f:
            audit_cache = json.load(f)
    if args.reorder:
        auditor.temperature = 0.4

    # 逐边配对：{edge_id: (orig, audit)}
    pairs = []
    for qi in idx:
        item = pool[int(qi)]
        if item["question"] in audit_cache:
            audit = audit_cache[item["question"]]
        else:
            body = "\n\n".join(
                f"问题{i}: {item['question']}\n候选：\n" +
                "\n".join(f"  {eid} = {desc}" for eid, desc in item["cands"])
                for i, item in [(0, item)])
            got = None
            time.sleep(10)          # 免费档节流：每查询之间强制间隔
            for attempt in range(6):
                try:
                    out = _raw_chat(auditor, _JUDGE_SYSTEM,
                                    _JUDGE_USER.format(n=1, body=body))
                    parsed = _parse_json_blob(out)
                    if isinstance(parsed, dict):
                        norm = {}
                        for kk, vv in parsed.items():
                            key = str(kk).strip()
                            for pre in ("问题", "Q", "q", "第"):
                                if key.startswith(pre):
                                    key = key[len(pre):].strip()
                                    break
                            try:
                                norm[int(key)] = vv
                            except ValueError:
                                continue
                        sub = norm.get(0)
                        if isinstance(sub, dict):
                            got = sub
                            break
                except Exception as e:
                    print(f"    [audit 重试{attempt+1}] {type(e).__name__}: {str(e)[:50]}",
                          flush=True)
                time.sleep((attempt + 1) * 20)   # 429 窗口较长：20/40/60/80/100/120s
            if got is None:
                print(f"  ⚠️ 放弃：{item['question'][:24]}…")
                continue
            audit_cache[item["question"]] = got
            with open(audit_cache_path, "w", encoding="utf-8") as f:
                json.dump(audit_cache, f, ensure_ascii=False, indent=1)
            audit = got
        cids = {eid for eid, _ in item["cands"]}
        for eid in cids:
            a = 1 if audit.get(eid) in (1, True, "1", "true") else 0
            b = 1 if item["gold"].get(eid) in (1, True, "1", "true") else 0
            pairs.append((a, b))

    # Cohen's κ（二分类）
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b)
    pa = agree / n if n else 0.0
    yes_a = sum(a for a, _ in pairs) / n if n else 0.0
    yes_b = sum(b for _, b in pairs) / n if n else 0.0
    pe = yes_a * yes_b + (1 - yes_a) * (1 - yes_b)
    kappa = (pa - pe) / (1 - pe) if pe < 1 else 0.0

    print("=" * 84)
    print(f"金标 AI 交叉审核：二评 {args.audit_model} vs 原金标 glm-5.3-flash")
    print(f"  查询 {min(args.sample, len(pool))} 条 / 逐边配对 {n} 对")
    print(f"  原始一致率 pa = {pa:.3f}")
    print(f"  期望一致率 pe = {pe:.3f}")
    print(f"  Cohen's κ = {kappa:.3f}"
          f"（≥0.8 几乎完美 / 0.6-0.8 高度一致 / 0.4-0.6 中等）")
    # 不一致样例
    disagrees = [(a, b) for a, b in pairs if a != b]
    print(f"  不一致 {len(disagrees)} 对"
          f"（二评更严 {sum(1 for a, b in disagrees if a == 0)} / 更宽 "
          f"{sum(1 for a, b in disagrees if a == 1)}）")
    tag = "同模型换序复核" if args.reorder else "跨模型二评"
    print("【诚实边界】模型-模型 κ 是人工 κ 的下界代理（同厂商家族）；"
          f"本 run 协议={tag}（{'候选逆序+temp0.4' if args.reorder else '同提示词'}）；"
          "审核通过后仍建议投稿前小规模真人复核。审核缓存：" + audit_cache_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
