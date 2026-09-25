# -*- coding: utf-8 -*-
"""gen2 实验 2：级联层到底被谁消费？（消费点审计）

区分两类级联：
  (A) **本体级联** `ont.cascades`（ontology_default.json 733 + 种子/MetaNet 25 = 758）
      —— 抽取期写进 `edge.cascade_id`，检索期 `cross_domain_retrieve` 读它做目标域扩展，
      训练期 `same_cascade` 特征读它，Ω_N 读它。
  (B) **构建期 ad-hoc 级联** `shg.cascades`（builder._ensure_cascades 运行时新建的
      `C_ADHOC_*`）—— 只进 `MetaphorSHG.cascades`，**不回写本体、不回写 edge.cascade_id**。

本实验用真实建图逐条核对 (B) 的隔离性，并统计 (A) 的消费量。

运行：<python> experiments/gen2/exp_g2_2_consumers.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.retrieval import RetrievalEngine              # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.health import graph_health                    # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)

OUT = os.path.join(HERE, "exp_g2_2_consumers.json")
DOC_SIZE, LLM_CONF = 10, 0.85


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k

    audit = Counter()
    adhoc_member_frames = set()
    adhoc_edge_cascade_ids = Counter()
    shg_cascade_ids = Counter()
    health_cov = []
    n_edges_total = 0
    # 本体级联的"扩展目标域"能力：查询触发词命中的框架所属级联能带来多少新目标域
    expand_gain = []

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=LLM_CONF)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        n_edges_total += len(l1)
        for e in l1:
            audit["l1_edges"] += 1
            if e.cascade_id:
                audit["l1_with_ont_cascade"] += 1
                if e.cascade_id.startswith("C_ADHOC_"):
                    audit["l1_with_adhoc_id"] += 1
                    adhoc_edge_cascade_ids[e.cascade_id] += 1
            else:
                audit["l1_without_cascade"] += 1
        for c in shg.cascades:
            shg_cascade_ids[c.id] += 1
            if c.id.startswith("C_ADHOC_"):
                adhoc_member_frames |= set(c.member_frame_ids)
        h = graph_health(shg)
        health_cov.append(h.cascade_coverage)

        # 级联扩展带来的目标域增益（cross_domain_retrieve 的核心机制）
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        for e in l1:
            cid = ont.get_cascade(e.frame_id) if e.frame_id else None
            direct = {e.target_domain}
            if cid:
                spec = ont.get_cascade_spec(cid)
                if spec:
                    for fid in spec.member_frames:
                        fs = ont.get_frame(fid)
                        if fs:
                            direct.add(fs.target_domain)
            expand_gain.append(len(direct) - 1)

    out = dict(
        audit=dict(audit),
        n_adhoc_ids_seen=len(shg_cascade_ids),
        n_adhoc_member_frames=len(adhoc_member_frames),
        adhoc_member_frames_in_ont=sum(
            1 for f in adhoc_member_frames if f in ont.frames),
        health_cascade_coverage_min=min(health_cov),
        health_cascade_coverage_mean=sum(health_cov) / len(health_cov),
        expand_gain_hist={str(k2): v for k2, v in
                          sorted(Counter(expand_gain).items())},
        expand_gain_mean=sum(expand_gain) / max(1, len(expand_gain)),
        expand_gain_gt0=sum(1 for g in expand_gain if g > 0),
        n_edges_total=n_edges_total,
    )
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("=" * 78)
    print("gen2 实验 2：级联层消费点审计（110 伪文档，856+ 条 L1 边）")
    print("=" * 78)
    a = audit
    print(f"L1 边 {a['l1_edges']} 条：有本体级联 {a['l1_with_ont_cascade']}"
          f"（{a['l1_with_ont_cascade'] / a['l1_edges'] * 100:.1f}%）/"
          f"无级联 {a['l1_without_cascade']}"
          f"（{a['l1_without_cascade'] / a['l1_edges'] * 100:.1f}%）")
    print(f"  ⚠️ 其中 cascade_id 是 C_ADHOC_* 的：{a['l1_with_adhoc_id']}"
          f"  ← builder._ensure_cascades 只写 shg.cascades，**不回写 edge.cascade_id**")
    print(f"shg.cascades 里出现的 ad-hoc id 数（110 次 build 累计 distinct）："
          f"{out['n_adhoc_ids_seen']}")
    print(f"  ad-hoc 成员框架去重 {out['n_adhoc_member_frames']} 个"
          f"（其中 {out['adhoc_member_frames_in_ont']} 个存在于本体）")
    print(f"health.cascade_coverage：min={out['health_cascade_coverage_min']:.3f}"
          f" mean={out['health_cascade_coverage_mean']:.3f}"
          f"  ← 这是 _ensure_cascades 唯一的量化收益")
    print(f"\n[本体级联的检索扩展力] 单条 L1 边经级联能多拿到几个目标域："
          f"mean={out['expand_gain_mean']:.3f}"
          f"，>0 的边 {out['expand_gain_gt0']}/{len(expand_gain)}"
          f"（{out['expand_gain_gt0'] / max(1, len(expand_gain)) * 100:.1f}%）")
    print("  扩展增益直方图（+N 个目标域 → 边数）:")
    for kk, vv in sorted(out["expand_gain_hist"].items(), key=lambda x: int(x[0])):
        print(f"    +{kk:>3s} : {vv:>4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
