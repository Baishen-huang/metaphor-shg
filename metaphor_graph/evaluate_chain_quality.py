# -*- coding: utf-8 -*-
"""扩展链质量 LLM 评审（连贯文档语料验证的质量维度，密度之外补精度）。

**动机**：`evaluate_document_corpus` 测得连贯文档上扩展链密度 6.3%（10× 独立
短句），但密度不含质量——链是否真是「同一源域的隐喻跨段落延续」需要语义评审。
本脚本重建语料图（全部走 LLM 缓存，零请求），抽取扩展链的 chunk 原文，
交给 **跨模型 judge**（抽取用 glm-5.3-flash，评审用 glm-4.7-flash，降低
自偏好）逐链判定「是否构成连贯的跨 chunk 扩展隐喻」，输出链精度与分语料
精度，并打印带判定的样例供人工复核。

运行（需 LLM_API_KEY=智谱）：
    python -m metaphor_graph.evaluate_chain_quality [--sample 30]
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

from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.models import MetaphorSHG
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology
from metaphor_graph.evaluate_real import build_llm_backend
from metaphor_graph.llm_backend import (PrecomputedBackend, batch_discover,
                                        batch_refine, _RefineCollector,
                                        _parse_json_blob)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "data", "corpus")
DISCOVER_CACHE = os.path.join(CORPUS, "llm_cache_corpus.json")
REFINE_CACHE = DISCOVER_CACHE + ".refine.json"
CACHE = os.path.join(CORPUS, "chain_judge_cache.json")

JUDGE_SYSTEM = ("你是认知语言学标注专家。给你同一篇文档中的若干相邻段落，以及系统"
                "合并出的一条「扩展隐喻链」（源域、喻底）。判断这些段落是否构成"
                "**连贯的扩展隐喻**：同一源域的隐喻表达跨越段落持续出现并共同"
                "建构一个目标概念。孤立的单句隐喻、或源域词仅字面出现，都算否。"
                "只输出 JSON：{\"verdict\": 1 或 0, \"reason\": \"不超过 20 字\"}。")


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


def _judge_cached(cache, key, backend, user):
    if key in cache:
        return cache[key]
    last_err = None
    for attempt in range(5):
        try:
            out = _raw_chat(backend, JUDGE_SYSTEM, user)
            parsed = _parse_json_blob(out)
            if isinstance(parsed, dict) and "verdict" in parsed:
                cache[key] = parsed
                with open(CACHE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=1)
                time.sleep(0.8)
                return parsed
            last_err = f"解析失败: {str(out)[:60]}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:60]}"
        # 失败必须可见（§7.2 纪律），退避后重试
        print(f"    [judge 尝试{attempt + 1}失败] {last_err}", flush=True)
        time.sleep(3 * (attempt + 1))
    print(f"    [judge 最终失败] {last_err}", flush=True)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=30, help="评审的链数上限")
    ap.add_argument("--judge-model", default="glm-4.7-flash",
                    help="judge 模型（默认跨模型：抽取为 glm-5.3-flash）")
    ap.add_argument("--continuity", choices=("ground1", "vehicle_repeat"),
                    default="ground1",
                    help="L1.5 合并的延续性判据（对照精度/密度权衡）")
    ap.add_argument("--llm-verify", action="store_true",
                    help="只评审通过 LLM 链校验（verify_chains_batch）的链——"
                         "测量「校验器保留集」在跨模型 judge 下的精度")
    ap.add_argument("--coherence-threshold", type=float, default=0.0,
                    help=">0 时启用 metaphor_coherence 图结构过滤（第三道校验信号的"
                         "预期用途）：在 L1-only 图上计算链的 (源域,目标域) 连贯度，"
                         "低于阈值的链剔除（免费/离线/无需 LLM）")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        raise SystemExit("需要 LLM_API_KEY（智谱）")

    rows = [json.loads(l) for l in open(os.path.join(CORPUS, "chunks.jsonl"),
                                        encoding="utf-8")]
    ont, _ = build_replay_ontology()
    replay = build_llm_backend()
    replay.timeout = 120.0
    # 重建预取后端（全部命中缓存，零请求）
    table = batch_discover(replay, [r["text"] for r in rows], 20, False,
                           DISCOVER_CACHE)
    collector = _RefineCollector(table)
    ex0 = MetaphorExtractor(ontology=ont, use_semfield=True,
                            llm_backend=collector, llm_conf_threshold=0.85)
    for t in [r["text"] for r in rows]:
        ex0.extract(t, doc_id="pre", chunk_id="pre")
    refine_table = batch_refine(replay, list(dict.fromkeys(collector.pairs)),
                                20, False, REFINE_CACHE)
    pre = PrecomputedBackend(table, replay, refine_table=refine_table)

    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r)
    ex = MetaphorExtractor(ontology=ont, use_semfield=True, llm_backend=pre,
                           llm_conf_threshold=0.85)

    chains = []
    coherence_of = {}
    for did, rs in sorted(by_doc.items()):
        chunk_texts = [r["text"] for r in rs]
        builder = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=pre,
                                     extended_continuity=args.continuity)
        shg = builder.build(chunk_texts, doc_id=did)
        # coherence 过滤（可选）：在 **L1-only 图**（不含扩展边，避免自证）上
        # 计算每条候选链 (源域,目标域) 的 metaphor_coherence
        if args.coherence_threshold > 0:
            from metaphor_graph.hgnn import MetaphorHGNN
            l1_edges = [e for e in shg.edges if not e.is_extended]
            base = MetaphorSHG(edges=l1_edges, frames=shg.frames,
                               cascades=shg.cascades)
            g = MetaphorHGNN(base, layers=2, cross_layer=False)
            g.forward()
        for e in shg.edges:
            if not e.is_extended:
                continue
            if args.coherence_threshold > 0:
                coh = g.metaphor_coherence(e.source_domain, e.target_domain)
                coherence_of[(did, e.source_domain, e.target_domain)] = coh
                if coh < args.coherence_threshold:
                    continue
            spans = sorted({s.chunk_id for s in e.chunk_spans})
            # 按 chunk 索引取链上原文
            idxs = sorted(int(c.split("_c")[-1]) for c in spans)
            texts = [chunk_texts[i] for i in idxs if 0 <= i < len(chunk_texts)]
            chains.append(dict(doc_id=did, source=rs[0]["source"],
                               title=rs[0]["title"], frame=e.frame_id or "",
                               src=e.source_domain, tgt=e.target_domain,
                               ground=list(e.ground)[:4], texts=texts))
    if args.coherence_threshold > 0:
        import statistics as _st
        all_c = list(coherence_of.values())
        print(f"coherence 过滤：阈值 {args.coherence_threshold}，保留 "
              f"{len(chains)}/{len(all_c)} 条候选链"
              f"（全体连贯度中位数 {_st.median(all_c):.3f}）")
    print(f"重建图完成：扩展链 {len(chains)} 条，评审前 {min(args.sample, len(chains))} 条")
    if args.llm_verify:
        # 只评审「LLM 链校验器保留集」——测量校验后管线的跨模型精度。
        # 校验缓存复用 corpus 运行（deterministic key），零请求。
        from metaphor_graph.llm_backend import verify_chains_batch
        vchains = [dict(key=f"{c['doc_id']}|{c['src']}|{'、'.join(sorted(c['ground'])[:4])}",
                        doc_title=c["title"], source=c["src"], target=c["tgt"],
                        ground=c["ground"], texts=c["texts"]) for c in chains]
        vres = verify_chains_batch(replay, vchains, 8, True,
                                   DISCOVER_CACHE + ".verify.json")
        before = len(chains)
        chains = [c for c in chains
                  if vres.get(f"{c['doc_id']}|{c['src']}|{'、'.join(sorted(c['ground'])[:4])}")]
        print(f"LLM 链校验过滤：{before} → {len(chains)} 条进入评审")
    import numpy as _np
    rng = _np.random.default_rng(20260901)
    order = rng.permutation(len(chains))[:args.sample]

    judge = build_llm_backend()   # judge（默认同厂商；--judge-model 可跨模型）
    judge.model = args.judge_model
    judge.timeout = 180.0
    # build_llm_backend 的 endpoint 已含 /chat/completions，勿再拼接（实测拼接会 404）
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    verdicts = []
    for k in order:
        ch = chains[int(k)]
        key = f"{ch['doc_id']}|{ch['src']}|{ch['ground']}"
        paras = "\n\n".join(f"[段落{i+1}] {t[:180]}" for i, t in
                            enumerate(ch["texts"]))
        user = (f"源域：{ch['src']}　目标域：{ch['tgt']}　喻底：{'、'.join(ch['ground'])}\n"
                f"文档：{ch['title'][:20]}\n{paras}")
        v = _judge_cached(cache, key, judge, user)
        if v is None:
            print(f"  ⚠️ 判定失败跳过：{ch['doc_id']} {ch['src']}→{ch['tgt']}")
            continue
        verdicts.append((ch, int(v["verdict"]), str(v.get("reason", ""))))
        print(f"  [{ch['doc_id']} {ch['src']}→{ch['tgt']}] verdict={v['verdict']} "
              f"{str(v.get('reason', ''))[:20]}", flush=True)

    if not verdicts:
        print("无有效判定")
        return 1
    n_yes = sum(1 for _, v, _ in verdicts if v == 1)
    print("=" * 84)
    print(f"扩展链质量评审：精度 {n_yes}/{len(verdicts)} = {n_yes / len(verdicts):.1%}"
          f"（judge={args.judge_model}，跨模型于抽取 glm-5.3-flash）")
    by_src = defaultdict(lambda: [0, 0])
    for ch, v, _ in verdicts:
        by_src[ch["source"]][0] += v
        by_src[ch["source"]][1] += 1
    for src, (y, n) in by_src.items():
        print(f"  {src}: {y}/{n} = {y / n:.0%}")
    print("【诚实边界】judge 为 LLM（跨模型降低但不消除同源偏差），n≤30 抽样；"
          "结论须人工抽查复验。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
