# -*- coding: utf-8 -*-
"""用真实数据集验证 L1 抽取（P1 字面误判率硬门槛，方案 §6.5）。

运行：
  python -m metaphor_graph.evaluate_real                # CCL2018 + 默认中文本体
  python -m metaphor_graph.evaluate_real --use-metanet  # 对比：迁移 MetaNet 后
  python -m metaphor_graph.evaluate_real --use-semfield # 叠加 MIPVU+Wmatrix 语义域通道
  python -m metaphor_graph.evaluate_real --vua path.tsv # 英文 VUA（需补英文本体）

核心指标：
  字面误判率 FP/(FP+TN) —— 即 P1 硬门槛，方案要求 < 15%
  隐喻召回   TP/(TP+FN)
  P/R/F1（隐喻类）

说明：当前抽取器是「触发词 + 类型安全约束」的启发式（方案 H1/H2 降本路径）。
召回受限于种子本体的触发词覆盖；字面误判率由类型安全约束兜住。两者权衡正是
方案要解决的痛点 —— 低召回提示需扩充本体（--use-metanet）或接入真实 LLM。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.ontology import DEFAULT_ONTOLOGY
from metaphor_graph.data_loader import load_ccl2018, load_vua_csv
from metaphor_graph.metanet_migrate import build_metanet_ontology
from metaphor_graph.bootstrap_triggers import build_bootstrap_ontology


def build_llm_backend():
    """按环境构造 LLM 后端（§6.6）。

    设了 LLM_API_KEY → 真实 OpenAI 兼容端点（OpenAIBackend）；
    否则 → 离线确定性近似 LocalHeuristicBackend（无密钥也能跑通，
    便于对照「接真实 LLM 之前」的基线）。

    GLM-5.3 / glm-5.3-flash 的 thinking 默认开启且**不可关闭**，思考 token 照常计费，
    因此这里对 glm-5 系列自动带上 reasoning_effort="low"（抽词是简单任务，
    无需深度推理，能明显压低输出 token）。可用 LLM_EXTRA_JSON 覆盖。
    """
    import json as _json
    from .llm_backend import OpenAIBackend, LocalHeuristicBackend
    if not os.environ.get("LLM_API_KEY"):
        return LocalHeuristicBackend()

    model = os.environ.get("LLM_MODEL", "")
    extra = None
    if model.startswith("glm-5"):
        extra = {"reasoning_effort": "low"}
    if os.environ.get("LLM_EXTRA_JSON"):
        extra = dict(extra or {})
        extra.update(_json.loads(os.environ["LLM_EXTRA_JSON"]))
    return OpenAIBackend(extra_body=extra)


def _describe_backend(backend) -> str:
    name = type(backend).__name__
    if name == "OpenAIBackend":
        return f"OpenAIBackend(model={backend.model}, endpoint={backend.endpoint})"
    return f"{name}（离线近似，无密钥；设 LLM_API_KEY 即切换为真实端点）"


def eval_split(samples, ontology, conf: float = 0.35, use_semfield: bool = False,
               llm_backend=None, llm_conf: float = 0.5):
    ex = MetaphorExtractor(ontology=ontology, conf_threshold=conf,
                           use_semfield=use_semfield, llm_backend=llm_backend,
                           llm_conf_threshold=llm_conf)
    tp = fp = tn = fn = 0
    fp_examples, tp_examples = [], []
    for i, s in enumerate(samples):
        edges = ex.extract(s.text, doc_id="eval", chunk_id=f"eval_{i}")
        pred = bool(edges)
        if s.gold_metaphor and pred:
            tp += 1
            tp_examples.append(s.text)
        elif (not s.gold_metaphor) and pred:
            fp += 1
            fp_examples.append(s.text)
        elif (not s.gold_metaphor) and (not pred):
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    literal_error_rate = fp / (fp + tn) if (fp + tn) else 0.0
    return dict(tp=tp, fp=fp, tn=tn, fn=fn, precision=precision, recall=recall,
                f1=f1, literal_error_rate=literal_error_rate,
                fp_examples=fp_examples, tp_examples=tp_examples)


def _report(name: str, r: dict):
    n = r["tp"] + r["fp"] + r["tn"] + r["fn"]
    print(f"\n[{name}]  n={n}")
    print(f"  TP={r['tp']}  FP={r['fp']}  TN={r['tn']}  FN={r['fn']}")
    print(f"  Precision={r['precision']:.3f}  Recall={r['recall']:.3f}  F1={r['f1']:.3f}")
    mark = "✅ <0.15 达标" if r["literal_error_rate"] < 0.15 else "⚠️ ≥0.15 未达标"
    print(f"  字面误判率(P1) = {r['literal_error_rate']:.3f}   {mark}")
    if r["fp_examples"]:
        print("  字面误判样例(应无隐喻却判出):")
        for t in r["fp_examples"][:5]:
            print(f"    - {t}")
    if r["tp_examples"]:
        print("  命中隐喻样例:")
        for t in r["tp_examples"][:5]:
            print(f"    + {t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-metanet", action="store_true",
                    help="底层本体用 MetaNet 迁移后的扩充版")
    ap.add_argument("--use-bootstrap", action="store_true",
                    help="在底层本体上叠加 CCL2018 自举触发词（方案 §9.1）")
    ap.add_argument("--use-semfield", action="store_true",
                    help="开启 MIPVU+Wmatrix 语义域失谐通道（方案 §6.5，轻量接入）")
    ap.add_argument("--use-llm-ontology", action="store_true",
                    help="并入 LLM 自举本体（P0 自举回流产物）："
                         "把模型见过的高置信 (源域→目标域) 沉淀为正式框架与级联，"
                         "修复 P2 的 L3 级联覆盖率。")
    ap.add_argument("--llm-ontology-path", default=None,
                    help="自举本体 JSON 路径。规范做法用 train.xml 建的本体"
                         "（默认 llm_ontology.json）；测试集语料建的仅作对照。")
    ap.add_argument("--use-llm", action="store_true",
                    help="开启 LLM 开放发现通道（方案 §6.6）：设了 LLM_API_KEY 走真实"
                         " OpenAI 兼容端点，否则走离线 LocalHeuristicBackend")
    ap.add_argument("--llm-batch", type=int, default=1,
                    help="真实端点时按批发送（默认 1=逐句）。建议 20："
                         "CCL2018 上可省约 86%% 输入 token、请求数 1100→55。"
                         "仅对支持 discover_batch 的后端生效。")
    ap.add_argument("--vua", default=None, help="VUA tsv 路径（英文评估）")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--llm-cache", default=None,
                    help="LLM 预取结果的落盘缓存路径（也可用环境变量 LLM_CACHE）。"
                         "调阈值/改本体/跑消融要反复重跑，开缓存后迭代零成本且可复现。")
    ap.add_argument("--llm-conf", type=float, default=0.5,
                    help="LLM 开放发现通道的置信门槛（默认 0.5）。接真实模型时建议调高："
                         "实测 deepseek-v4-flash 上 0.85→召回 69.1%%/P1 14.5%%(勉强达标)，"
                         "0.90→召回 54.7%%/P1 11.8%%(留足余量)。阈值扫描不需要重新调 LLM。")
    args = ap.parse_args()

    if args.vua:
        samples = load_vua_csv(args.vua)
        src = "VUA(英文)"
        base = build_metanet_ontology() if args.use_metanet else DEFAULT_ONTOLOGY
    else:
        samples = load_ccl2018()
        src = "CCL2018(中文)"
        base = build_metanet_ontology() if args.use_metanet else DEFAULT_ONTOLOGY
    ont = build_bootstrap_ontology(base) if args.use_bootstrap else base
    if args.use_llm_ontology:
        from .llm_ontology import build_llm_ontology
        ont = build_llm_ontology(path=args.llm_ontology_path, base=ont) if \
            args.llm_ontology_path else build_llm_ontology(base=ont)

    # ---- LLM 后端（§6.6）：有密钥走真实端点，否则走离线近似 ----
    backend = None
    if args.use_llm:
        backend = build_llm_backend()
        # 真实端点 + 批量：先把整批语料一次性问完，再让抽取器消费缓存结果。
        # 逐句调用时 91% 输入 token 是固定样板，批量可把这部分摊薄。
        if args.llm_batch > 1 and hasattr(backend, "discover_batch"):
            # 两趟预取：批量 discover + 批量 refine。
            # 本体扩充到 ~679 框架后 refine 请求会暴涨到 2297 次（串行 ~23 分钟），
            # 批量 + 缓存后降到 ~115 次，且二次运行零请求。
            from .llm_backend import precompute_all
            print(f"\nLLM 批量预取（每批 {args.llm_batch} 条）…")
            cache = args.llm_cache or os.environ.get("LLM_CACHE")
            refine_cache = ((cache + ".refine.json") if cache else None)
            backend = precompute_all(
                backend, [s.text for s in samples], ontology=ont,
                use_semfield=args.use_semfield, batch_size=args.llm_batch,
                discover_cache=cache, refine_cache=refine_cache)
            print(f"  预取完成，命中 "
                  f"{sum(1 for v in backend.table.values() if v)} 句有候选")

    label = []
    if args.use_metanet:
        label.append("MetaNet迁移")
    if args.use_bootstrap:
        label.append("自举触发词")
    if args.use_semfield:
        label.append("语义域失谐(MIPVU+Wmatrix)")
    if args.use_llm_ontology:
        label.append(f"LLM自举本体({len(ont.frames)}框架)")
    if backend is not None:
        label.append(f"LLM开放发现({type(backend).__name__})")
    if not label:
        label.append("默认(7级联/14框架)")
    print(f"数据集: {src}  样本数={len(samples)}")
    print(f"本体: {' + '.join(label)}")
    if backend is not None:
        print(f"LLM 后端: {_describe_backend(backend)}")

    r = eval_split(samples, ont, conf=args.conf,
                   use_semfield=args.use_semfield, llm_backend=backend,
                   llm_conf=args.llm_conf)
    _report("当前评估", r)

    # 对比基线（同本体、关闭全部可选通道）
    if args.use_semfield or backend is not None:
        r0 = eval_split(samples, ont, conf=args.conf,
                        use_semfield=False, llm_backend=None)
        _report("对比: 同本体(关语义通道/LLM)", r0)
        print(f"\n召回变化(开-关): {r['recall'] - r0['recall']:+.3f}  "
              f"字面误判率变化: {r['literal_error_rate'] - r0['literal_error_rate']:+.3f}")

    # ---- 真实用量（读厂商返回的 usage，精确核算成本，非估算）----
    real = getattr(backend, "fallback", backend)   # PrecomputedBackend 包了一层
    if hasattr(real, "usage_report"):
        print(f"\nLLM 真实用量: {real.usage_report()}")
        print(f"  模型: {getattr(real, 'model', '?')}  端点: {getattr(real, 'endpoint', '?')}")

    # 用被预测为隐喻的样本构建 SHG，展示真实文档进图
    pos = [s.text for s in samples
           if MetaphorExtractor(ontology=ont, conf_threshold=args.conf,
                                use_semfield=args.use_semfield,
                                llm_backend=backend)
           .extract(s.text, doc_id="eval", chunk_id="x")]
    if pos:
        builder = MetaphorSHGBuilder(ontology=ont, llm_backend=backend)
        shg = builder.build(pos, doc_id="real_eval")
        print(f"\n真实文档构建 SHG: {shg.summary()}")
        # P2 验收：L2/L3 层级覆盖率 >85%（方案 §八）
        from .health import graph_health
        h = graph_health(shg)
        ok = "✅ 达标" if h.hierarchy_coverage >= 0.85 else "⚠️ 未达标"
        print(f"  P2 层级覆盖率 L1→L2→L3 = {h.hierarchy_coverage:.3f}（门槛 >0.85）{ok}")
        print(f"      L2 框架覆盖={h.frame_coverage:.3f}  L3 级联覆盖={h.cascade_coverage:.3f}"
              f"  平均元数={h.avg_arity:.2f}  孤儿率={h.orphan_rate:.3f}")
        if h.hierarchy_coverage < 0.85:
            print("      提示：大量超边挂在临时框架上（未归入本体级联）→ 需做本体自举回流（P0）。")


if __name__ == "__main__":
    main()
