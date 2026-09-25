# -*- coding: utf-8 -*-
"""gen2 实验 1：级联（L3）构造缺陷的精确复现与量化。

全部离线、$0：本体 JSON 重放（ontology_default.json + metanet 种子 +
bootstrap 底座）+ LLM 缓存重放（data/llm_cache_deepseek.json[.refine.json]）。

测量对象 = **生产口径的本体**（`ontology_clean._build_variant` 组装，
即 evaluate_fullcorpus / exp1_omega 实际用的那一个），而非裸 JSON：

  1. 级联规模直方图（成员框架数）
  2. 每个级联的 distinct target_domain 数 → 跨目标域比例
  3. 单例（size==1）级联数与占比
  4. 落在单例级联里的 L1 超边占比（用真实语料建图后统计）

产物：experiments/gen2/exp_g2_1_defect.json + stdout

运行（在 .wt/cascade 下）：
    <python> experiments/gen2/exp_g2_1_defect.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder            # noqa: E402
from metaphor_graph.extractor import MetaphorExtractor            # noqa: E402
from metaphor_graph.data_loader import load_ccl2018               # noqa: E402
from metaphor_graph.evaluate_fullcorpus import (                  # noqa: E402
    build_replay_ontology, build_replay_backend)

DOC_SIZE = 10
LLM_CONF = 0.85
OUT = os.path.join(HERE, "exp_g2_1_defect.json")


def cascade_stats(ont) -> dict:
    """对一个 CascadeOntology 计算级联层的全部结构统计。"""
    sizes, n_targets, singleton = [], [], 0
    no_frame, empty = 0, 0
    member_frames_all = set()
    for cid, spec in ont.cascades.items():
        fids = list(spec.member_frames)
        sizes.append(len(fids))
        tgts = set()
        found = 0
        for fid in fids:
            fs = ont.get_frame(fid)
            if fs is None:
                no_frame += 1
                continue
            found += 1
            tgts.add(fs.target_domain)
        member_frames_all |= set(fids)
        if not found:
            empty += 1
        n_targets.append(len(tgts))
        if len(fids) == 1:
            singleton += 1

    n = len(sizes)
    cross = sum(1 for k in n_targets if k >= 2)
    hist = Counter(sizes)
    srt = sorted(sizes)
    med = srt[n // 2] if n % 2 else 0.5 * (srt[n // 2 - 1] + srt[n // 2])
    return dict(
        n_cascades=n,
        n_frames=len(ont.frames),
        n_frames_in_cascade=len(member_frames_all & set(ont.frames)),
        frame_cascade_coverage=(
            len(member_frames_all & set(ont.frames)) / max(1, len(ont.frames))),
        size_hist={str(k): v for k, v in sorted(hist.items())},
        size_median=med, size_mean=sum(sizes) / max(1, n), size_max=max(sizes or [0]),
        n_singleton=singleton, singleton_rate=singleton / max(1, n),
        n_cross_target=cross, cross_target_rate=cross / max(1, n),
        n_multi_frame_cross_target=sum(
            1 for k, s in zip(n_targets, sizes) if k >= 2 and s >= 2),
        targets_hist={str(k): v for k, v in
                      sorted(Counter(n_targets).items())},
        n_missing_frames=no_frame, n_empty_cascades=empty,
    )


def build_world(ont, backend):
    """建图（重放）：返回 (shg_per_doc, all_l1_edges)。"""
    samples = load_ccl2018()
    k = DOC_SIZE
    n_docs = (len(samples) + k - 1) // k
    docs, all_l1 = {}, []
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
        docs[did] = shg
        all_l1.extend(l1)
    return docs, all_l1


def edge_cascade_distribution(ont, all_l1) -> dict:
    """L1 超边 → 级联归属：落在单例级联的边占比、落不进任何级联的边占比。"""
    sizes = {cid: len(spec.member_frames) for cid, spec in ont.cascades.items()}
    in_singleton = in_multi = orphan = 0
    frame_orphan = Counter()
    for e in all_l1:
        cid = e.cascade_id
        if not cid:
            orphan += 1
            frame_orphan[e.frame_id] += 1
            continue
        if sizes.get(cid, 0) <= 1:
            in_singleton += 1
        else:
            in_multi += 1
    n = len(all_l1)
    return dict(
        n_l1_edges=n,
        n_in_singleton_cascade=in_singleton,
        frac_in_singleton_cascade=in_singleton / max(1, n),
        n_in_multi_cascade=in_multi,
        frac_in_multi_cascade=in_multi / max(1, n),
        n_no_cascade=orphan, frac_no_cascade=orphan / max(1, n),
        n_distinct_orphan_frames=len(frame_orphan),
    )


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)

    prod = cascade_stats(ont)
    # 本体自身来源拆分：JSON 级联（LLM_TARGET::*）+ 种子/metanet 级联
    by_kind = Counter()
    for cid in ont.cascades:
        if cid.startswith("C_LLM_"):
            by_kind["C_LLM_ (JSON, 按目标域)"] += 1
        elif cid.startswith("C_ADHOC_"):
            by_kind["C_ADHOC_ (builder 运行时补)"] += 1
        else:
            by_kind["种子/MetaNet 手工"] += 1

    docs, all_l1 = build_world(ont, backend)
    edge_dist = edge_cascade_distribution(ont, all_l1)

    # builder 运行时补出来的 ad-hoc 级联（每次 build 都新建，不在本体里）
    adhoc_sizes = []
    for shg in docs.values():
        for c in shg.cascades:
            if c.id.startswith("C_ADHOC_"):
                adhoc_sizes.append(len(c.member_frame_ids))
    adhoc = dict(
        n_builds=len(docs),
        n_adhoc_total=len(adhoc_sizes),
        n_adhoc_distinct=len({c.id for shg in docs.values()
                              for c in shg.cascades
                              if c.id.startswith("C_ADHOC_")}),
        size_median=(sorted(adhoc_sizes)[len(adhoc_sizes) // 2]
                     if adhoc_sizes else 0),
        size_max=max(adhoc_sizes or [0]),
        size_hist={str(k): v for k, v in sorted(Counter(adhoc_sizes).items())},
    )

    out = dict(
        ontology_frames=n_frames,
        cascade_sources=dict(by_kind),
        production_ontology=prod,
        edge_distribution=edge_dist,
        adhoc=adhoc,
        n_docs=len(docs),
    )
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # ---------------- stdout ----------------
    print("=" * 78)
    print("gen2 实验 1：L3 级联构造缺陷复现（生产口径本体，缓存重放，$0）")
    print("=" * 78)
    print(f"本体：{prod['n_frames']} 框架 / {prod['n_cascades']} 级联")
    print(f"  级联来源：{dict(by_kind)}")
    print(f"\n[规模] median={prod['size_median']:.1f}  mean={prod['size_mean']:.2f}"
          f"  max={prod['size_max']}")
    print(f"[单例] {prod['n_singleton']}/{prod['n_cascades']} = "
          f"{prod['singleton_rate'] * 100:.1f}%")
    print(f"[跨目标域] {prod['n_cross_target']}/{prod['n_cascades']} = "
          f"{prod['cross_target_rate'] * 100:.1f}%"
          f"（size>=2 且跨域：{prod['n_multi_frame_cross_target']}）")
    print(f"[框架覆盖] {prod['frame_cascade_coverage'] * 100:.1f}%"
          f"（{prod['n_frames_in_cascade']} 框架挂上级联；空级联 {prod['n_empty_cascades']}）")
    print("\n规模直方图（size → 级联数）:")
    for k, v in sorted(prod["size_hist"].items(), key=lambda x: int(x[0])):
        print(f"  {k:>3s} : {v:>4d}  {'#' * min(60, v)}")
    print("\n每级联 distinct target_domain 数分布:")
    for k, v in sorted(prod["targets_hist"].items(), key=lambda x: int(x[0])):
        print(f"  {k:>3s} 个目标域 : {v:>4d} 个级联")

    print(f"\n[L1 边归属] n={edge_dist['n_l1_edges']} 条 L1 超边（{len(docs)} 伪文档）")
    print(f"  落在单例级联：{edge_dist['n_in_singleton_cascade']}"
          f" = {edge_dist['frac_in_singleton_cascade'] * 100:.1f}%")
    print(f"  落在多成员级联：{edge_dist['n_in_multi_cascade']}"
          f" = {edge_dist['frac_in_multi_cascade'] * 100:.1f}%")
    print(f"  无级联归属：{edge_dist['n_no_cascade']}"
          f" = {edge_dist['frac_no_cascade'] * 100:.1f}%")

    print(f"\n[builder 运行时 C_ADHOC_] 跨 {adhoc['n_builds']} 次 build，"
          f"共生成 {adhoc['n_adhoc_total']} 个 ad-hoc 级联"
          f"（distinct id {adhoc['n_adhoc_distinct']}），"
          f"size median={adhoc['size_median']} max={adhoc['size_max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
