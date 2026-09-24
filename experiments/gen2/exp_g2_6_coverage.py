# -*- coding: utf-8 -*-
"""gen2 实验 6：L2/L3 覆盖率的归因矩阵（本体级联规则 × 孤儿打包规则）。

实验 4 已证：覆盖率 100% 是 `builder._ensure_cascades` 的功劳（关掉它掉到 0.767，
低于 >0.85 门槛）。本实验穷举组合，回答两个工程问题：

  Q1  换用替代的**本体**级联规则（source/ground）能否把覆盖率顶回 >0.85？
  Q2  换用替代的**孤儿打包**规则（source/ground）能否在保持覆盖率的同时
      让补出来的级联有真实规模（而不是现状的 size≡1）？

指标：覆盖率 min/mean、补出的 ad-hoc 级联数与其规模中位数/最大值、
有多少 L1 边落进「size≥2 的 ad-hoc 级联」。

产物：experiments/gen2/exp_g2_6_coverage.json + stdout
运行：<python> experiments/gen2/exp_g2_6_coverage.py
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
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.health import graph_health                    # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)

DOC_SIZE, LLM_CONF = 10, 0.85
OUT = os.path.join(HERE, "exp_g2_6_coverage.json")
ONT_RULES = ["json", "source", "ground", "source_type"]
ORPH_RULES = ["target", "source", "ground", "source_type", "none"]


def main():
    samples = load_ccl2018()
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    rows = []
    print("=" * 108)
    print("gen2 实验 6：覆盖率归因矩阵（本体级联规则 × 孤儿打包规则）")
    print("=" * 108)
    print(f"{'ont':>11s} {'orphan':>10s} | {'cov_min':>7s} {'cov_mean':>8s} "
          f"{'cov>=.85':>8s} | {'#adhoc':>6s} {'adhoc_med':>9s} {'adhoc_max':>9s} "
          f"{'edges_in_adhoc>=2':>17s}")
    print("-" * 108)
    for ont_rule in ONT_RULES:
        ont, n_frames = build_replay_ontology(cascade_rule=ont_rule)
        backend = build_replay_backend(ont)
        # 本体级联已固定，只有孤儿打包规则在变 → 每次重建本体副本
        for orph in ORPH_RULES:
            covs = []
            adhoc_sizes = []
            edges_adhoc_multi = edges_total = 0
            for di in range(n_docs):
                ct = [s.text for s in samples[di * k:(di + 1) * k]]
                if not ct:
                    continue
                did = f"fc{di}"
                ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                                       llm_backend=backend,
                                       llm_conf_threshold=LLM_CONF)
                shg = MetaphorSHGBuilder(
                    ontology=ont, extractor=ex, llm_backend=backend,
                    orphan_cascade_rule=orph).build(ct, doc_id=did)
                l1 = [e for e in shg.edges if not e.is_extended]
                if not l1:
                    continue
                covs.append(graph_health(shg).cascade_coverage)
                sizes = {}
                for c in shg.cascades:
                    if "_ADHOC_" in c.id or c.id.startswith("C_ADHOC_"):
                        adhoc_sizes.append(len(c.member_frame_ids))
                        sizes[c.id] = len(c.member_frame_ids)
                # 注意：edge.cascade_id 由**本体**决定，builder 的 ad-hoc 级联
                # 只进 shg.cascades，不回写 edge —— 因此这里必须按 frame_id
                # 反查 ad-hoc 归属（直接看 e.cascade_id 会恒为 0，是常见误读）。
                f2adhoc = {}
                for c in shg.cascades:
                    if "_ADHOC_" in c.id or c.id.startswith("C_ADHOC_"):
                        for fid in c.member_frame_ids:
                            f2adhoc[fid] = len(c.member_frame_ids)
                for e in l1:
                    edges_total += 1
                    if f2adhoc.get(e.frame_id, 0) >= 2:
                        edges_adhoc_multi += 1
            med = (sorted(adhoc_sizes)[len(adhoc_sizes) // 2]
                   if adhoc_sizes else 0)
            cov_min = min(covs) if covs else 0.0
            row = dict(ont_rule=ont_rule, orphan_rule=orph,
                       cov_min=cov_min, cov_mean=sum(covs) / max(1, len(covs)),
                       cov_gate=cov_min >= 0.85,
                       n_adhoc=len(adhoc_sizes), adhoc_median=med,
                       adhoc_max=max(adhoc_sizes or [0]),
                       adhoc_hist={str(a): b for a, b in
                                   sorted(Counter(adhoc_sizes).items())},
                       edges_adhoc_multi=edges_adhoc_multi,
                       edges_total=edges_total)
            rows.append(row)
            print(f"{ont_rule:>11s} {orph:>10s} | {cov_min:7.4f} "
                  f"{row['cov_mean']:8.4f} {'✅' if row['cov_gate'] else '❌':>8s} | "
                  f"{len(adhoc_sizes):6d} {med:9d} "
                  f"{max(adhoc_sizes or [0]):9d} {edges_adhoc_multi:17d}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
