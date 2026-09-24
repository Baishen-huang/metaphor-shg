# -*- coding: utf-8 -*-
"""可执行消融实验（方案 §6.3 / §八 P5）。

`baselines.py` 里的 ABLATIONS 只是**声明**（假设与预期），本模块负责**真跑**，
把「预期」填成「实测」，用于论文 RQ1–RQ4 的因果论证。

当前可跑的消融（都不依赖 training.py）：
  A1  去掉类型安全约束        → 验证 H1：字面误判率应回升至 >30%
  A2  L2/L3 改回 LLM 聚类     → 验证 H2：成本应显著上升（按调用次数核算）
  A3  三通道逐个关闭          → 触发词 / 语义域 / LLM 开放发现 各自的边际贡献
  A4  去掉 LLM 自举本体       → 验证 P0 产物对召回与 L3 覆盖率的贡献

尚不可跑（依赖并行开发中的 training.py）：A4(HGNN)、A7(训练排序器)、A9(角色特征)，
以及需要跨域检索评测集的 A3(隐喻通路)、A5(跨 chunk 超边)。

运行（LLM 结果已缓存，A1/A3/A4 基本零额外调用）：
    python -m metaphor_graph.ablation --cache data/llm_cache_deepseek.json ^
           --ontology metaphor_graph/llm_ontology_train.json
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.metanet_migrate import build_metanet_ontology
from metaphor_graph.bootstrap_triggers import build_bootstrap_ontology
from metaphor_graph.llm_ontology import build_llm_ontology
from metaphor_graph.llm_backend import (
    PrecomputedBackend, load_table, _refine_key)
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.health import graph_health


class TrackedBackend(PrecomputedBackend):
    """记录查不到的 refine 键 —— 消融不该偷偷多花 API 钱，也该知道数据缺口。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.missing: set = set()

    def refine(self, chunk, frame):
        if self.refine_table is not None and \
                _refine_key(chunk, frame) not in self.refine_table:
            self.missing.add(_refine_key(chunk, frame))
        return super().refine(chunk, frame)


def measure(ex, samples) -> Dict[str, float]:
    """跑一遍抽取，返回 P/R/F1/P1。"""
    tp = fp = tn = fn = 0
    for s in samples:
        pred = bool(ex.extract(s.text))
        if s.gold_metaphor:
            tp += pred
            fn += (not pred)
        else:
            fp += pred
            tn += (not pred)
    R = tp / (tp + fn) if (tp + fn) else 0.0
    P1 = fp / (fp + tn) if (fp + tn) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = 2 * prec * R / (prec + R) if (prec + R) else 0.0
    return {"recall": R, "p1": P1, "precision": prec, "f1": f1,
            "tp": tp, "fp": fp}


def make_ontology(use_llm_ontology: bool, path: Optional[str]):
    base = build_bootstrap_ontology(build_metanet_ontology())
    if use_llm_ontology:
        return build_llm_ontology(path=path, base=base) if path \
            else build_llm_ontology(base=base)
    return base


def row(label: str, m: Dict[str, float], expected: str, note: str = ""):
    return {"label": label, **m, "expected": expected, "note": note}


def run_a1(samples, table, backend, path, rows):
    """A1 去掉类型安全约束 —— 验证 H1（本方案宣称的核心创新之一）。

    注意：类型约束只在**候选框架来自本体**时才有机会拒绝。而本体在构建时
    已保证所有 (source_type, mapping_type) 合法，且 LLM 自举出的框架
    98.6% 是 GENERIC_VEHICLE → GENERIC_VEHICLE_MAP（无条件合法），
    所以这里预期是「去掉约束 = 没有变化」。这本身就是需要报告的结论。
    """
    from metaphor_graph.ontology import CascadeOntology

    ont = make_ontology(True, path)
    n_bad = sum(1 for f in ont.frames.values()
                if not CascadeOntology.type_valid(f.source_type, f.mapping_type))

    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    full = measure(ex, samples)

    # 统计运行时真正被约束拦下的候选数（用计数器包住原方法）
    rejected = [0]
    coher_rej = [0]
    orig = ont.type_valid

    def counting(sd, mt, _o=orig):
        ok = _o(sd, mt)
        if not ok:
            rejected[0] += 1
        return ok

    ont.type_valid = counting
    try:
        ex_on = MetaphorExtractor(ontology=ont, use_semfield=True,
                                  llm_backend=backend, llm_conf_threshold=0.85)
        measure(ex_on, samples)
        coher_rej[0] = ex_on._type_rejects   # 类型连贯性检查拦下的候选数
    finally:
        del ont.type_valid

    # 关闭**全部**类型检查：枚举约束 type_valid + 类型连贯性检查 _type_coherent
    def _coher_true(self, *a, **k):
        return True

    # 打补丁后必须**保存原方法并还原**，不能 del ——
    # _type_coherent 本身就定义在类上，del 会把真方法一并删掉，
    # 导致后续 A2/A3/A4 全部 AttributeError（本次就这么坏的）。
    _orig_coherent = MetaphorExtractor._type_coherent
    MetaphorExtractor._type_coherent = _coher_true
    ont.type_valid = lambda *a, **k: True
    try:
        ex2 = MetaphorExtractor(ontology=ont, use_semfield=True,
                                llm_backend=backend, llm_conf_threshold=0.85)
        off = measure(ex2, samples)
    finally:
        del ont.type_valid                    # 这个是实例属性，del 是对的
        MetaphorExtractor._type_coherent = _orig_coherent

    rows.append(row("A1 完整系统（类型检查开）", full,
                    "—", f"本体非法框架 {n_bad}"))
    rows.append(row("A1 去掉全部类型检查", off,
                    "H1: P1 回升 >30%",
                    f"枚举拦 {rejected[0]} + 连贯性拦 {coher_rej[0]} → "
                    f"P1 {full['p1']:.3f} → {off['p1']:.3f}"))
    return full, off, rejected[0]


def run_a2(samples, table, backend, path, rows):
    """A2 L2/L3 改回 LLM 聚类 —— 验证 H2（成本）。

    不真去调 LLM 聚类，而是**数出需要聚类的量**：查表法下已在本体中的框架零调用，
    只有「本体没有的新框架」才需要聚类。用这个比例核算成本差异。
    """
    ont = make_ontology(True, path)
    ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                           llm_backend=backend, llm_conf_threshold=0.85)
    n_lookup, n_cluster = 0, 0
    seen = set()
    for s in samples:
        for e in ex.extract(s.text):
            key = (e.frame_id, e.source_domain, e.target_domain)
            if key in seen:
                continue
            seen.add(key)
            if e.frame_id and ont.cascades.get(ont.get_cascade(e.frame_id) or ""):
                n_lookup += 1                      # 查表命中：0 次调用
            else:
                n_cluster += 1                     # 需回退聚类：≥1 次调用
    total = n_lookup + n_cluster
    ratio = (n_cluster / total) if total else 0.0
    rows.append(row("A2 L2/L3 cascade 查表（本方案）",
                    {"recall": 0, "p1": 0, "precision": 0, "f1": 0,
                     "tp": n_lookup, "fp": n_cluster},
                    "H2: 成本升 10×",
                    f"需聚类框架占比 {ratio:.1%}；查表{n_lookup}个零调用，"
                    f"聚类需{n_cluster}次调用"))


def run_a3(samples, table, backend, path, rows):
    """A3 三通道消融：触发词 / 语义域 / LLM 开放发现。

    **必须隔离 refine**：extractor 里 `llm_backend is None` 被解释为
    「未接后端 → 不做否定判断」，于是关闭 LLM 发现通道会**顺带关掉 LLM 校验**，
    两个变量一起变，消融就不干净 —— 实测会让 P1 从 0.092 假性飙到 0.434。
    因此前两档用 refine_only 后端：discover 恒空，但 refine 照常查表。
    """
    ont = make_ontology(True, path)
    refine_only = TrackedBackend({}, None, getattr(backend, "refine_table", None))
    combos = [
        ("仅通道一 触发词（refine 仍在）", dict(use_semfield=False), refine_only),
        ("通道一+二 +语义域（refine 仍在）", dict(use_semfield=True), refine_only),
        ("三通道全开（+LLM开放发现）", dict(use_semfield=True), backend),
    ]
    for label, kw, be in combos:
        ex = MetaphorExtractor(ontology=ont, llm_backend=be,
                               llm_conf_threshold=0.85, **kw)
        rows.append(row(label, measure(ex, samples), "—"))


def run_a4(samples, table, backend, path, rows):
    """A4 去掉 LLM 自举本体 —— 验证 P0 产物的贡献。"""
    for label, use in (("有 LLM 自举本体（P0 产物）", True),
                       ("去掉自举本体（仅 MetaNet+自举触发词）", False)):
        ont = make_ontology(use, path)
        ex = MetaphorExtractor(ontology=ont, use_semfield=True,
                               llm_backend=backend, llm_conf_threshold=0.85)
        m = measure(ex, samples)
        # 覆盖率：用被判定为隐喻的句子建图后测
        pos = [s.text for s in samples if ex.extract(s.text)]
        cov = 0.0
        if pos:
            shg = MetaphorSHGBuilder(ontology=ont, llm_backend=backend).build(
                pos, doc_id="ab")
            cov = graph_health(shg).hierarchy_coverage
        m2 = dict(m)
        m2["coverage"] = cov
        rows.append(row(label, m2, "—", f"框架{len(ont.frames)}个，L2/L3覆盖率{cov:.3f}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join("data", "llm_cache_deepseek.json"))
    ap.add_argument("--ontology", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "llm_ontology_train.json"))
    args = ap.parse_args()

    samples = load_ccl2018()
    print(f"测试集 {len(samples)} 句（中性 "
          f"{sum(1 for s in samples if not s.gold_metaphor)} 句）")

    if not os.path.exists(args.cache):
        print(f"未找到 LLM 缓存 {args.cache}，A1/A3/A4 将在无 LLM 通道下运行")
        table, backend = {}, None
    else:
        table = load_table(args.cache)
        # refine 结果必须一并载入：否则所有触发词候选都会被当成"通过"，
        # P1 会虚高到 0.447（真值 0.092）—— 消融就失去了意义。
        rpath = args.cache + ".refine.json"
        rtable = None
        if os.path.exists(rpath):
            import json as _json
            from metaphor_graph.llm_backend import LLMRefine
            with open(rpath, "r", encoding="utf-8") as f:
                rtable = {tuple(k): (LLMRefine(**v) if v else None)
                          for k, v in _json.load(f)}
            print(f"已载入 refine 缓存 {rpath}（{len(rtable)} 条）")
        else:
            print(f"⚠️ 未找到 refine 缓存 {rpath}，P1 会虚高")
        backend = TrackedBackend(table, None, rtable)

    rows: List[dict] = []
    print("\n运行消融…")
    run_a1(samples, table, backend, args.ontology, rows)
    a1_missing = len(getattr(backend, "missing", ()))
    run_a2(samples, table, backend, args.ontology, rows)
    run_a3(samples, table, backend, args.ontology, rows)
    run_a4(samples, table, backend, args.ontology, rows)

    print("\n" + "=" * 96)
    print(f"{'配置':34s} {'召回':>7} {'P1误判':>8} {'精确率':>7} {'F1':>7}  预期 / 备注")
    print("=" * 96)
    for r in rows:
        if r["tp"] == 0 and r["fp"] == 0 and not r.get("recall"):
            print(f"{r['label']:34s} {'-':>7} {'-':>8} {'-':>7} {'-':>7}  {r['note']}")
            continue
        cov = f"  覆盖{r['coverage']:.2f}" if "coverage" in r else ""
        print(f"{r['label']:34s} {r['recall']:>7.3f} {r['p1']:>8.3f} "
              f"{r['precision']:>7.3f} {r['f1']:>7.3f}  {r['expected']}{cov}"
              + (f" | {r['note']}" if r["note"] else ""))
    print("=" * 96)
    if backend is not None and getattr(backend, "missing", None):
        print(f"⚠️ 有 {len(backend.missing)} 条 refine 键未命中缓存（被判为通过），"
              f"A1 的 P1 可能偏乐观")
    return 0


if __name__ == "__main__":
    sys.exit(main())
