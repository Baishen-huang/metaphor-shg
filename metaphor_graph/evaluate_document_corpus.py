# -*- coding: utf-8 -*-
"""连贯文档语料 L1.5 扩展隐喻验证（路线图「P3 扩展隐喻在连贯文档上复测」）。

**为什么需要它**
P3 的 F1=1.000 是精选诊疗集；全量 CCL2018（独立短句）上扩展链天然稀疏
（5 条/110 伪文档）。本脚本用**真实连贯文档**（多段落、真实 RAG 场景）验证
L1.5 跨 chunk 扩展超边的泛化：段落级分块 → LLM 预取（discover+refine，真实
调用、落盘缓存）→ 逐文档建图 → 统计扩展链密度与跨度，并抽样打印链内容供
人工检查。

语料（`data/corpus/`，采集脚本见仓库外 `fetch_corpus.py`，来源均为公开渠道）：
  - caijing_news.json   人民网经济频道财经新闻 150 篇（每篇 1–3 chunk）
  - gov_reports.json    政府工作报告 55 篇（中央+省级，每篇 20–40 chunk，封顶 40）
  - luxun_quanji.txt    鲁迅全集（公版），按空行切散文取前 N 篇

成本：真实 LLM 调用，批量 20 句/请求；~500 chunk ≈ ¥1–3（deepseek-v4-flash，
峰值价）。缓存后重跑零请求。

运行：
    python -m metaphor_graph.evaluate_document_corpus --stage build   # 分块
    python -m metaphor_graph.evaluate_document_corpus --stage run     # 预取+建图+测量
    python -m metaphor_graph.evaluate_document_corpus --stage report  # 只读缓存汇报
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "data", "corpus")
CHUNKS_PATH = os.path.join(CORPUS, "chunks.jsonl")
DISCOVER_CACHE = os.path.join(CORPUS, "llm_cache_corpus.json")

CHUNK_SIZE = 500       # 字符（方案 §4.6：400–600）
CHUNK_OVERLAP = 50     # 10% 重叠
MAX_CHUNKS_PER_DOC = 40


# ---------------------------------------------------------------- 语料加载
def load_caijing(n_docs: int) -> list:
    arts = json.load(open(os.path.join(CORPUS, "caijing_news.json"),
                          encoding="utf-8"))
    return [{"doc_id": f"cj{i}", "source": "人民网财经", "title": a["title"],
             "text": a["text"]} for i, a in enumerate(arts[:n_docs])]


def load_gov(n_docs: int) -> list:
    reps = json.load(open(os.path.join(CORPUS, "gov_reports.json"),
                          encoding="utf-8"))
    # 优先中央报告（标题含"国务院"），均匀取年份
    central = [r for r in reps if "国务院" in r["title"]]
    out = []
    for i, r in enumerate(central[:n_docs]):
        out.append({"doc_id": f"gov{i}", "source": "维基文库", "title": r["title"],
                    "text": r["text"]})
    return out


def load_luxun(n_docs: int) -> list:
    raw = open(os.path.join(CORPUS, "luxun_quanji.txt"), encoding="utf-8").read()
    # 以空行切段，聚合相邻段落成"篇"（连续非空块，长度>400 视为一篇的近似）
    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if len(b.strip()) > 200]
    out = []
    for i, b in enumerate(blocks):
        if len(out) >= n_docs:
            break
        out.append({"doc_id": f"lx{i}", "source": "鲁迅全集(公版)",
                    "title": (b.split("\n")[0][:24] if b else f"段{i}"),
                    "text": b})
    return out


# ---------------------------------------------------------------- 分块
def chunk_text(text: str) -> list:
    """段落级分块：~CHUNK_SIZE 字 + 10% 重叠（方案 §4.6）。"""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 1 <= CHUNK_SIZE or not buf:
            buf = (buf + "\n" + p).strip()
        else:
            chunks.append(buf)
            buf = (buf[-CHUNK_OVERLAP:] + "\n" + p).strip()
    if buf:
        chunks.append(buf)
    # 超长兜底切分
    out = []
    for c in chunks:
        while len(c) > CHUNK_SIZE * 1.6:
            out.append(c[:CHUNK_SIZE])
            c = c[CHUNK_SIZE - CHUNK_OVERLAP:]
        if c:
            out.append(c)
    return out[:MAX_CHUNKS_PER_DOC]


def build_chunks(n_caijing: int, n_gov: int, n_luxun: int) -> list:
    docs = (load_caijing(n_caijing) + load_gov(n_gov) + load_luxun(n_luxun))
    rows = []
    for d in docs:
        for ci, c in enumerate(chunk_text(d["text"])):
            rows.append({"doc_id": d["doc_id"], "chunk_id": f"{d['doc_id']}_c{ci}",
                         "source": d["source"], "title": d["title"],
                         "chunk_index": ci, "text": c})
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


# ---------------------------------------------------------------- 建图与测量
def run_pipeline(chunk_rows: list, llm_conf: float, batch_size: int,
                 ext_continuity: str = "ground1", llm_verify: bool = False):
    from metaphor_graph.evaluate_fullcorpus import (build_replay_ontology,
                                                    build_replay_backend)
    from metaphor_graph.llm_backend import (OpenAIBackend, precompute_all,
                                            batch_discover, batch_refine,
                                            _RefineCollector)
    from metaphor_graph.extractor import MetaphorExtractor
    from metaphor_graph.builder import MetaphorSHGBuilder

    ont, n_frames = build_replay_ontology()
    texts = [r["text"] for r in chunk_rows]
    # 用 evaluate_real 的环境驱动构造器：LLM_MODEL / LLM_EXTRA_JSON /
    # glm-5 系列 reasoning_effort=low 全部统一处理（避免端点/厂商参数漂移）
    from metaphor_graph.evaluate_real import build_llm_backend
    backend = build_llm_backend()
    backend.timeout = 120.0
    refine_cache = DISCOVER_CACHE + ".refine.json"
    table = batch_discover(backend, texts, batch_size, True, DISCOVER_CACHE)

    # 1.5 趟:收集 refine 请求(触发词/语义域通道的候选)再批量判定
    collector = _RefineCollector(table)
    ex0 = MetaphorExtractor(ontology=ont, use_semfield=True,
                            llm_backend=collector, llm_conf_threshold=llm_conf)
    for t in texts:
        ex0.extract(t, doc_id="pre", chunk_id="pre")
    refine_table = batch_refine(backend, list(dict.fromkeys(collector.pairs)),
                                batch_size, True, refine_cache)
    from metaphor_graph.llm_backend import PrecomputedBackend
    pre = PrecomputedBackend(table, backend, refine_table=refine_table)

    # 逐文档建图
    by_doc = defaultdict(list)
    for r in chunk_rows:
        by_doc[r["doc_id"]].append(r)
    ex = MetaphorExtractor(ontology=ont, use_semfield=True, llm_backend=pre,
                           llm_conf_threshold=llm_conf)
    doc_shgs = {}
    for did, rows in sorted(by_doc.items()):
        chunk_texts = [r["text"] for r in rows]
        builder = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=pre,
                                     extended_continuity=ext_continuity)
        doc_shgs[did] = builder.build(chunk_texts, doc_id=did)

    # L1.5 语义校验（可选）：LLM 逐链判定「跨段延续」，剔除未通过链。
    # 失败纪律：校验缺失（批次失败）的链按未校验剔除前先保留并单独报告。
    if llm_verify:
        from metaphor_graph.llm_backend import verify_chains_batch
        chains = []
        for did, shg in doc_shgs.items():
            rows = by_doc[did]
            for e in shg.edges:
                if not e.is_extended:
                    continue
                idxs = sorted({int(s.chunk_id.split("_c")[-1])
                               for s in e.chunk_spans})
                texts = [rows[i]["text"] for i in idxs if 0 <= i < len(rows)]
                chains.append(dict(
                    key=f"{did}|{e.source_domain}|{'、'.join(sorted(e.ground)[:4])}",
                    doc_title=rows[0]["title"], source=e.source_domain,
                    target=e.target_domain, ground=list(e.ground), texts=texts))
        vres = verify_chains_batch(backend, chains, 8, True,
                                   DISCOVER_CACHE + ".verify.json")
        dropped = 0
        for did, shg in doc_shgs.items():
            before = len(shg.edges)
            shg.edges = [e for e in shg.edges
                         if not e.is_extended or vres.get(
                             f"{did}|{e.source_domain}|{'、'.join(sorted(e.ground)[:4])}")]
            dropped += before - len(shg.edges)
        n_cand = len(chains)
        n_kept = sum(1 for c in chains if vres.get(c["key"]))
        print(f"LLM 链校验: 候选 {n_cand} 条, 通过 {n_kept} 条, "
              f"剔除 {dropped} 条（未校验按剔除计）", flush=True)

    results = []
    for did, rows in sorted(by_doc.items()):
        chunk_texts = [r["text"] for r in rows]
        shg = doc_shgs[did]
        ext = [e for e in shg.edges if e.is_extended]
        l1 = [e for e in shg.edges if not e.is_extended]
        span_info = []
        for e in ext:
            cids = sorted(int(s.chunk_id.split("_c")[-1]) for s in e.chunk_spans)
            span_info.append(dict(n_chunks=len(set(cids)), span=cids[-1] - cids[0],
                                  frame=e.frame_id or "",
                                  ground=list(e.ground)[:4]))
        results.append(dict(
            doc_id=did, title=rows[0]["title"], source=rows[0]["source"],
            n_chunks=len(rows), n_l1=len(l1), n_ext=len(ext),
            docs_with_ext=int(len(ext) > 0), spans=span_info))
        print(f"  {did} 「{rows[0]['title'][:16]}」 chunk={len(rows)} "
              f"L1={len(l1)} 扩展链={len(ext)}", flush=True)
    json.dump(results, open(os.path.join(CORPUS, "l15_results.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    real = getattr(backend, "fallback", backend)
    if hasattr(real, "usage_report"):
        print("LLM 用量:", real.usage_report())
    return results


def report():
    results = json.load(open(os.path.join(CORPUS, "l15_results.json"),
                             encoding="utf-8"))
    n_docs = len(results)
    n_ext_docs = sum(r["docs_with_ext"] for r in results)
    total_ext = sum(r["n_ext"] for r in results)
    total_l1 = sum(r["n_l1"] for r in results)
    print("=" * 84)
    print("L1.5 扩展隐喻 · 连贯文档语料验证")
    print("=" * 84)
    by_src = defaultdict(lambda: dict(docs=0, ext_docs=0, ext=0, l1=0, chunks=0))
    for r in results:
        b = by_src[r["source"]]
        b["docs"] += 1
        b["ext_docs"] += r["docs_with_ext"]
        b["ext"] += r["n_ext"]
        b["l1"] += r["n_l1"]
        b["chunks"] += r["n_chunks"]
    print(f"{'语料':16s} {'文档':>5s} {'含扩展链':>8s} {'扩展链':>6s} {'L1边':>6s} {'链/百L1':>8s}")
    for src, b in by_src.items():
        rate = b["ext"] / b["l1"] * 100 if b["l1"] else 0
        print(f"{src:16s} {b['docs']:>5d} {b['ext_docs']:>8d} {b['ext']:>6d} "
              f"{b['l1']:>6d} {rate:>7.1f}%")
    total = sum(b["ext"] for b in by_src.values())
    tl1 = sum(b["l1"] for b in by_src.values())
    print(f"{'合计':16s} {n_docs:>5d} {n_ext_docs:>8d} {total:>6d} {tl1:>6d} "
          f"{total / tl1 * 100 if tl1 else 0:>7.1f}%")
    print(f"\n对照（CCL2018 独立短句伪文档）: 5 条扩展链 / 110 文档 "
          f"(L1 856 条, 链/百L1 = 0.6%)")
    print(f"连贯文档: {total} 条 / {n_docs} 文档 ({n_ext_docs} 篇含链, "
          f"{n_ext_docs / n_docs:.0%}) —— 链/百L1 = "
          f"{total / tl1 * 100 if tl1 else 0:.1f}%")
    # 抽样打印链内容
    print("\n【扩展链抽样（前 8 条）】")
    shown = 0
    for r in results:
        for sp in r["spans"]:
            if sp["n_chunks"] >= 2 and shown < 8:
                print(f"  [{r['doc_id']} 「{r['title'][:12]}」] 跨 {sp['n_chunks']} chunk "
                      f"(跨度{sp['span']}) 喻底: {'、'.join(sp['ground'])}")
                shown += 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("build", "run", "report", "all"),
                    default="all")
    ap.add_argument("--n-caijing", type=int, default=40)
    ap.add_argument("--n-gov", type=int, default=6)
    ap.add_argument("--n-luxun", type=int, default=60)
    ap.add_argument("--llm-conf", type=float, default=0.85)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--continuity", choices=("ground1", "vehicle_repeat"),
                    default="ground1")
    ap.add_argument("--llm-verify", action="store_true",
                    help="L1.5 语义校验：LLM 逐链判定「跨段延续」，剔除未通过链"
                         "（延续性判据的语义级方案，真实调用落盘缓存）")
    args = ap.parse_args()

    if args.stage in ("build", "all"):
        rows = build_chunks(args.n_caijing, args.n_gov, args.n_luxun)
        print(f"分块完成: {len(rows)} chunk "
              f"({len({r['doc_id'] for r in rows})} 篇文档) → {CHUNKS_PATH}")
    if args.stage in ("run", "all"):
        rows = [json.loads(l) for l in open(CHUNKS_PATH, encoding="utf-8")]
        run_pipeline(rows, args.llm_conf, args.batch, args.continuity,
                     args.llm_verify)
    if args.stage in ("report", "all"):
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
