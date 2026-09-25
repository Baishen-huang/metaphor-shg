# -*- coding: utf-8 -*-
"""真实句向量下的修复版基准复测（离线重放，$0）。

**目的**：`exp/source` 实测真实句向量使整体 MRR +21pp。本脚本检验
**锚定效应与向量器是否正交**——即 exp/repair 在哈希向量下测得的
"锚定抬高 ≈ +0.66 MRR、去锚定下 34 倍于随机"在真实向量下是否仍成立。

**离线可行性（已实测，诚实标注）**：
  data/embed_cache.json（embedding-3，512 维）3176 条。
  - **超边描述命中率 100%**（861/861）——评分的主信号完全可复放；
  - **查询文本命中率 81.9%**（519/634）——未命中的 115 条查询会被跳过。
  因此本脚本只在**查询文本已缓存**的子集上测，并显式报告子集规模。
  **这不是全量复测**；全量需 EMBED_API_KEY 重取 115 条查询向量。

运行：
    python -m metaphor_graph.evaluate_repaired_real
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph import embeddings
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_fullcorpus import (build_replay_backend,
                                                build_replay_ontology)
from metaphor_graph.evaluate_repaired import (build_global_graph,
                                              build_query_sets,
                                              global_engine, metrics,
                                              random_baseline)
from metaphor_graph.training import HAND_WEIGHTS_LEGACY, hand_weighted_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "embed_cache.json")


class CachedRealEmbedder:
    """只读真实句向量缓存；未命中返回 None（由调用方决定跳过策略）。"""

    def __init__(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.model = payload.get("model", "?")
        self._cache: Dict[str, List[float]] = payload.get("vectors", {})
        self.hits = 0
        self.misses = 0

    def __call__(self, text: str):
        v = self._cache.get(text)
        if v is None:
            self.misses += 1
            return None
        self.hits += 1
        return v


def _run_arm(eng, qset, scorer, cache_texts: Set[str], label: str):
    """在查询文本已缓存的子集上跑一个口径。返回 (指标, 用到的查询数)。"""
    agg = defaultdict(float)
    used = 0
    skipped = 0
    for q, gold in qset:
        if q not in cache_texts:
            skipped += 1
            continue
        used += 1
        cands = eng.live_edges()
        feats = {m.id: eng._pair_features(q, m) for m in cands}
        best: Dict[str, List[float]] = {}
        for m in cands:
            cid = next((s.chunk_id for s in m.chunk_spans
                        if s.chunk_id in eng._chunk_text), None)
            if cid is None:
                continue
            f = feats[m.id]
            if cid not in best or f[0] > best[cid][0]:
                best[cid] = list(f)
        arms = {"hand_recalibrated": lambda f: hand_weighted_score(f),
                "hand_legacy": lambda f: hand_weighted_score(
                    f, weights=HAND_WEIGHTS_LEGACY)}
        if scorer is not None:
            arms["trained"] = lambda f: scorer.score_features(f)
        for name, sc in arms.items():
            scored = sorted(((c, sc(f)) for c, f in best.items()),
                            key=lambda x: -x[1])
            for k, v in metrics(scored, gold).items():
                agg[f"{name}|{k}"] += v
    return agg, used, skipped


def main():
    emb = CachedRealEmbedder(CACHE)
    print("=" * 88)
    print(f"真实句向量下的修复版基准复测（离线重放 {emb.model}，"
          f"缓存 {len(emb._cache)} 条）")
    print("=" * 88)

    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    gshg, chunk_texts, chunk_order, _, gs = build_global_graph(
        load_ccl2018(), ont, backend, 10, 0.85)
    eng = global_engine(gshg, chunk_texts, ont)
    qs = build_query_sets(gshg)

    # 注入真实向量器（propagate=False：冻结抽取管线，保证与哈希口径对照干净）
    embeddings.set_embedder(emb, propagate=False)
    print(f"\n【全局图】chunk {gs['n_chunks']} ｜ L1 {gs['n_l1']} ｜ 扩展 {gs['n_ext']}")

    # 训练排序器（在真实向量下重新训练，口径与哈希版一致）
    scorer = None
    try:
        from metaphor_graph.training import train_from_shg
        cmap = {f"global_c{i}": t for i, t in enumerate(chunk_texts)}
        scorer, ds = train_from_shg(gshg, chunk_order=chunk_order,
                                    chunks=cmap, ontology=ont)
        print(f"【排序器】真实向量下训练集 n={len(ds)}")
    except Exception as e:
        print(f"【排序器】训练失败：{e}")

    cached = set(emb._cache)
    for key, title in (("anchored", "口径 A anchored（金标=产出 chunk）"),
                       ("deanchor", "口径 B deanchor（产出 chunk 移出池）")):
        print("\n" + "=" * 88)
        print(f"【{title}】")
        print("=" * 88)
        agg, used, skipped = _run_arm(eng, qs[key], scorer, cached, key)
        print(f"  用查询 {used} / 跳过（查询文本未缓存）{skipped}"
              f"  → 覆盖率 {used/max(1,used+skipped):.1%}")
        for name in ("hand_recalibrated", "hand_legacy", "trained"):
            k = f"{name}|mrr"
            if k not in agg:
                continue
            n = used
            print(f"    {name:<18} MRR={agg[k]/n:.4f}  "
                  f"Hits@3={agg[f'{name}|hits@3']/n:.4f}  "
                  f"Hits@10={agg[f'{name}|hits@10']/n:.4f}  "
                  f"Recall@10={agg[f'{name}|recall@10']/n:.4f}")
        if used:
            d = (agg["hand_recalibrated|mrr"] - agg["hand_legacy|mrr"]) / used
            print(f"    权重重标定效应 Δ MRR = {d:+.4f}")

    rnd = random_baseline(gs["n_chunks"], 1)
    print("\n" + "=" * 88)
    print("【自我审计】")
    print("=" * 88)
    print(f"  随机排序基线（池={gs['n_chunks']}）：MRR={rnd['mrr']:.4f}")
    print(f"  向量器命中：{emb.hits} 命中 / {emb.misses} 未命中"
          f"（{100*emb.hits/max(1,emb.hits+emb.misses):.1f}%）")
    print("\n  限制：本复测仅在**查询文本已缓存**的子集上进行（见脚本 docstring）。")
    print("  全量复测需 EMBED_API_KEY 重取未缓存的查询向量。")


if __name__ == "__main__":
    main()
