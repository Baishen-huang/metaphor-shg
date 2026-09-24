# -*- coding: utf-8 -*-
"""资源与基准发布打包（D2/D3）——生成 `release/` 目录。

产物：
  release/metaphor_resources/
    ontology_default.json      清洗后的生产默认本体（2177 框架，双语 100%）
    ontology_bilingual.json    英文对齐（curated/auto_gloss/LLM 翻译三级）
    bootstrap_triggers.json    自举触发词（等比模式串）
    DATASET_CARD.md            数据卡（schema/来源/口径/许可/引用）
    load_metaphor_resources.py 一键加载脚本
  release/MetaphorRAG-Bench/
    bench_docs.json            诊疗集两文档 + chunk 文本
    bench_queries.json         652 条改写查询 + LLM 非构造金标（确定性边 id→chunk）
    bench_extended_chains.json 连贯文档语料 52 条候选扩展链（含 chunk 原文与判定缓存键）
    BENCHMARK.md               基准说明与评测协议
  release/metaphor_shg_release.zip

运行（本地，无网络/无 LLM）：python -m metaphor_graph.package_release
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.path.join(ROOT, "release")
RES = os.path.join(RELEASE, "metaphor_resources")
BENCH = os.path.join(RELEASE, "MetaphorRAG-Bench")
CORPUS = os.path.join(ROOT, "data", "corpus")

DATASET_CARD = """# MetaphorSHG 中文级联本体（v1.0）
- 来源：CCL2018 训练集 LLM 自举（glm-5.3-flash，置信≥0.85）→ 清洗（删自环/
  清喻底/支持度分层）→ 生产沉淀。构建脚本：`metaphor_graph/ontology_clean.py`。
- schema：FrameSpec{id, name, mapping_type, source_domain, target_domain, ground,
  triggers, source_type, support, tier}；CascadeSpec{id, name, member_frames,...}。
- 双语：ontology_bilingual.json 每框架含 en_name（curated=MetaNet 内置一致 /
  auto_gloss=词汇级转写，**不主张**该英文隐喻在 MetaNet 真实存在）。
- 口径：本体只用训练集构建，测试集仅评估；支持度与分层见 provenance.stats。
- 许可：语料与本体仅供研究使用；引用格式见仓库 README。
"""

BENCH_CARD = """# MetaphorRAG-Bench（v0.1）
1. bench_docs.json：2 篇诊疗文档（11/7 chunk，含字面干扰与跨距负样本）。
2. bench_queries.json：652 条改写查询（触发词红线过滤后）+ LLM 非构造金标
   （一致性 96.8%；按确定性边 id 映射到 chunk 集合）。
   评测协议：查询 → 语义超图排序 → Recall@10 / MRR@10（金标 chunk 集合）。
3. bench_extended_chains.json：106 篇连贯文档语料抽取的 52 条候选扩展链
   （含链上 chunk 原文），供扩展隐喻消歧研究；LLM 校验判定见
   chain_verify/llm_cache_corups.verify.json（21.1% 通过率）。
引用本基准请注明构建管线（MetaphorSHG v0.2，见论文附录 A）。
"""

LOAD_SCRIPT = '''"""一键加载 MetaphorSHG 资源包。"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

def load_resources():
    from metaphor_graph.ontology import CascadeOntology, CascadeSpec, FrameSpec, TYPE_CONSTRAINTS
    with open(os.path.join(HERE, "ontology_default.json"), encoding="utf-8") as f:
        payload = json.load(f)
    ont = CascadeOntology()
    for fd in payload["frames"]:
        spec = FrameSpec(**fd)
        TYPE_CONSTRAINTS.setdefault(spec.source_type, [])
        if spec.mapping_type not in TYPE_CONSTRAINTS[spec.source_type]:
            TYPE_CONSTRAINTS[spec.source_type].append(spec.mapping_type)
        ont.frames.setdefault(spec.id, spec)
    for cd in payload["cascades"]:
        ont.cascades.setdefault(cd["id"], CascadeSpec(**cd))
    ont._trigger_index = {}
    for fid, fr in ont.frames.items():
        for t in fr.triggers:
            ont._trigger_index.setdefault(t, []).append(fid)
    ont._frame_to_cascade = {}
    for cid, c in ont.cascades.items():
        for fid in c.member_frames:
            ont._frame_to_cascade[fid] = cid
    bilingual = json.load(open(os.path.join(HERE, "ontology_bilingual.json"),
                               encoding="utf-8"))
    return ont, bilingual

if __name__ == "__main__":
    ont, bilingual = load_resources()
    print(f"本体: {len(ont.frames)} 框架 / {len(ont.cascades)} 级联; "
          f"双语对齐 {sum(1 for a in bilingual['alignments'].values() if a['en_name'])} 条")
'''


def main():
    os.makedirs(RES, exist_ok=True)
    os.makedirs(BENCH, exist_ok=True)
    for fn in ("ontology_default.json", "ontology_bilingual.json"):
        shutil.copy2(os.path.join(HERE, fn), os.path.join(RES, fn))
    shutil.copy2(os.path.join(HERE, "bootstrap_triggers.json"),
                 os.path.join(RES, "bootstrap_triggers.json"))
    with open(os.path.join(RES, "DATASET_CARD.md"), "w", encoding="utf-8") as f:
        f.write(DATASET_CARD)
    with open(os.path.join(RES, "load_metaphor_resources.py"), "w",
              encoding="utf-8") as f:
        f.write(LOAD_SCRIPT)

    # ---- 基准导出 ----
    from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                    build_replay_backend)
    from metaphor_graph.extractor import MetaphorExtractor
    from metaphor_graph.builder import MetaphorSHGBuilder
    from metaphor_graph.evaluate_llmgold import (build_queries_rich,
                                                 filter_violations, GEN_CACHE)
    from metaphor_graph.data_loader import load_ccl2018
    from metaphor_graph.eval_corpus import DOCS, GOLD_EXTENDED, GOLD_RETRIEVAL
    ont, _ = build_replay_ontology()
    replay = build_replay_backend(ont)
    samples = load_ccl2018()
    gen_cache = json.load(open(GEN_CACHE, encoding="utf-8"))
    judge_cache = json.load(open(os.path.join(ROOT, "data",
                                              "llm_cache_judge.json"),
                                encoding="utf-8"))
    k, n_docs = 10, (len(samples) + 9) // 10
    bench = []
    for di in range(n_docs):
        chunk_texts = [s.text for s in samples[di * k:(di + 1) * k]]
        did = f"fc{di}"
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=replay, llm_conf_threshold=0.85)
        shg = MetaphorSHGBuilder(ontology=ont, extractor=ex,
                                 llm_backend=replay).build(chunk_texts, doc_id=did)
        edge_by_id = {e.id: e for e in shg.edges}
        chunk_map = {f"{did}_c{i}": c for i, c in enumerate(chunk_texts)}
        qs = filter_violations(build_queries_rich(shg, chunk_map, did), gen_cache)
        for q in qs:
            text = gen_cache.get(f"{did}|{q['query']}", "")
            gold = judge_cache.get(f"{did}|{text}")
            if not (text and isinstance(gold, dict)):
                continue
            gold_chunks = sorted({c for eid, v in gold.items() if v == 1
                                  and eid in edge_by_id
                                  for c in {s.chunk_id for s in edge_by_id[eid].chunk_spans}})
            if gold_chunks:
                bench.append(dict(doc_id=did, question=text,
                                  gold_chunks=gold_chunks))
    json.dump(bench, open(os.path.join(BENCH, "bench_queries.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    docs_out = {did: dict(chunks=chs, gold_extended=[sorted(g) for g in gs],
                          gold_retrieval=[[q, sorted(g)] for qd, q, g in
                                          GOLD_RETRIEVAL if qd == did])
                for did, chs in DOCS.items()
                for gs in [list(GOLD_EXTENDED[did])]}
    json.dump(docs_out, open(os.path.join(BENCH, "bench_docs.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    # 扩展链（重放建图）
    chain_out = []
    l15 = json.load(open(os.path.join(CORPUS, "l15_results.json"),
                         encoding="utf-8"))
    for r in l15:
        chain_out.append(dict(doc_id=r["doc_id"], title=r["title"],
                              source=r["source"], n_chunks=r["n_chunks"],
                              n_l1=r["n_l1"], n_ext=r["n_ext"],
                              spans=r["spans"]))
    json.dump(chain_out, open(os.path.join(BENCH, "bench_extended_chains.json"),
                              "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(BENCH, "BENCHMARK.md"), "w", encoding="utf-8") as f:
        f.write(BENCH_CARD)

    # ---- zip ----
    zpath = os.path.join(RELEASE, "metaphor_shg_release.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base in (RES, BENCH):
            for dirpath, _, files in os.walk(base):
                for fn in files:
                    full = os.path.join(dirpath, fn)
                    z.write(full, os.path.relpath(full, RELEASE))
    print(f"发布包完成 → {RELEASE}")
    print(f"  资源: {len(os.listdir(RES))} 文件 | 基准: {len(os.listdir(BENCH))} 文件"
          f" | 查询 {len(bench)} 条 | zip: {os.path.getsize(zpath)/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
