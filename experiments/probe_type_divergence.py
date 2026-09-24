# -*- coding: utf-8 -*-
"""诊断 1：真实评测图上，type 特征两条路径的分歧量化。

不改任何被测代码：只调用 training.extract_text_features / extract_features
与 RetrievalEngine.metaphor_retriever_score 的实际表达式，逐边核对。

运行：
    python experiments/probe_type_divergence.py
"""
from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.retrieval import RetrievalEngine
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.training import extract_text_features, extract_features
from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                build_replay_backend)


def retrieval_type_expr(eng, mapping) -> float:
    """逐字复刻 retrieval.py:250 的 type 计算（人工加权路径）。"""
    fspec = eng.ont.get_frame(mapping.frame_id) if mapping.frame_id else None
    mtype = fspec.mapping_type if fspec else mapping.frame_id or ""
    return 1.0 if eng.ont.type_valid(mapping.source_type, mtype) else 0.0


def main():
    ont, n_frames = build_replay_ontology()
    backend = build_replay_backend(ont)
    samples = load_ccl2018()
    k = 10
    n_docs = (len(samples) + k - 1) // k

    tot_edges = 0
    tot_fallback = 0
    tot_no_frame = 0
    disagreement = 0
    dis_examples = []
    # 训练路径（extract_text_features）的 type 值分布
    train_type_vals = defaultdict(int)
    # 检索路径（metaphor_retriever_score 表达式）的 type 值分布
    retr_type_vals = defaultdict(int)
    # 逐帧统计
    frame_kind = defaultdict(int)
    by_doc = []

    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        l1 = [e for e in shg.edges if not e.is_extended]
        if not l1:
            continue
        eng = RetrievalEngine(shg, chunk_texts, doc_id=did, ontology=ont)
        d_fb = 0
        for e in l1:
            tot_edges += 1
            fid = e.frame_id or ""
            if not fid:
                tot_no_frame += 1
                frame_kind["<empty>"] += 1
            elif fid.startswith("F_LLM_"):
                tot_fallback += 1
                d_fb += 1
                frame_kind["F_LLM_*"] += 1
            else:
                frame_kind["ontology"] += 1
            # 训练路径：文本锚点版本（自监督训练用的就是这个）
            t = extract_text_features(chunk_texts[0], e, None, ont)[3]
            # 训练路径：边锚点版本
            t2 = extract_features(e, e, None)[3]
            r = retrieval_type_expr(eng, e)
            train_type_vals[t] += 1
            train_type_vals[("edge", t2)] += 1
            retr_type_vals[r] += 1
            if t != r:
                disagreement += 1
                if len(dis_examples) < 8:
                    dis_examples.append(
                        (did, e.id, fid, e.source_type, t, r,
                         ont.get_frame(fid) is not None))
        by_doc.append((did, len(l1), d_fb))

    print("=" * 80)
    print(f"真实评测图（evaluate_fullcorpus 口径，K=10，本体 {n_frames} 框架）")
    print("=" * 80)
    print(f"L1 边总数            : {tot_edges}")
    print(f"F_LLM_* 回退框架边数  : {tot_fallback} "
          f"= {tot_fallback / max(1, tot_edges):.1%}")
    print(f"无 frame_id 的边      : {tot_no_frame} "
          f"= {tot_no_frame / max(1, tot_edges):.1%}")
    print(f"本体已注册框架的边     : {frame_kind['ontology']} "
          f"= {frame_kind['ontology'] / max(1, tot_edges):.1%}")
    print()
    print(f"type 特征分歧（文本锚点 vs 检索路径）: {disagreement}/{tot_edges} "
          f"= {disagreement / max(1, tot_edges):.1%}")
    print(f"  training.extract_text_features type 取值分布: "
          f"{dict(train_type_vals)}")
    print(f"  retrieval 人工加权路径 type 取值分布: {dict(retr_type_vals)}")
    print()
    print("分歧样例（doc, edge_id, frame_id, source_type, train_type, "
          "retr_type, in_ontology）:")
    for row in dis_examples:
        print("   ", row)

    # 关键交叉验证：回退框架的真实 mapping_type 是什么
    print()
    print("回退框架抽查（get_frame 返回 None，但真实 mapping_type 是 "
          "GENERIC_VEHICLE_MAP）:")
    shown = 0
    for di in range(min(20, n_docs)):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        if not chunk_texts:
            continue
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=backend).build(chunk_texts, doc_id=did)
        for e in shg.edges:
            if e.frame_id and e.frame_id.startswith("F_LLM_"):
                gf = ont.get_frame(e.frame_id)
                print(f"    {e.frame_id}  get_frame={gf}  "
                      f"source_type={e.source_type}  "
                      f"type_valid(GENERIC_VEHICLE,'{e.frame_id}')="
                      f"{ont.type_valid('GENERIC_VEHICLE', e.frame_id)}  "
                      f"type_valid(GENERIC_VEHICLE,'GENERIC_VEHICLE_MAP')="
                      f"{ont.type_valid('GENERIC_VEHICLE', 'GENERIC_VEHICLE_MAP')}")
                shown += 1
                break
        if shown >= 5:
            break
    print()
    print("逐文档回退边占比（前 20）:", by_doc[:20])
    return 0


if __name__ == "__main__":
    sys.exit(main())
