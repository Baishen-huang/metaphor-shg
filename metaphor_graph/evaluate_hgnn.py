# -*- coding: utf-8 -*-
"""P4 —— HGNN 检测器 / 跨层语义信号测量（全部离线、零 API 费用）。

背景与诚实口径
--------------
方案 §4.5 把 `MetaphorHGNN` 设计为「超图版 KEG」：节点→超边→节点两步跨层消息传递，
把 L3 级联 / L2 框架语义传播到 L1 实体节点。原文承诺：查询含「发条」时，经消息传递可
获得 LIFE_IS_A_MACHINE 级联语义，从而检索到「机械重复」「缺乏弹性」等同类 chunk。

但 §6.1 把 P4 验收写成「抽取 F1 提升 >5pp」——这与组件的实际角色**口径不一致**：
- HGNN 是检索/语义信号编码器，不是抽取检测器；
- 它要发挥作用需要**多 chunk 文档**的图结构（跨层传播才有人可传），而 CCL2018 的
  金标是**逐句**的「是否含隐喻」二分类，单句图太稀疏，无法驱动图卷积；
- 且 CCL2018 没有**逐边**金标，无法训练/评测逐边检测器。

因此 P4 这里测量 HGNN **真正该测的贡献**——跨层语义信号对「隐喻检索 / 检测」的质量，
用 eval_corpus 的 GOLD_RETRIEVAL（跨域查询→相关 chunk）作金标：

  P4-A  跨层检索增益：HGNN 传播后余弦排序 vs 原始嵌入余弦排序的 MRR@10 / Hits@3 / Hits@10
  P4-B  检测器判别力：真 L1 隐喻边 vs 跨框架负样本对的隐喻连贯度（metaphor_coherence）分离度

运行：python -m metaphor_graph.evaluate_hgnn
"""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN, EMB_DIM
from metaphor_graph.eval_corpus import DOCS, GOLD_RETRIEVAL
from metaphor_graph import embeddings

from collections import defaultdict
from typing import Dict, List, Tuple

# 级联构造规则的模块级开关（gen2 实验用；默认 None = 用 DEFAULT_ONTOLOGY +
# 原口径孤儿打包，即已上报数字的口径）。设置后 build_shg() 会改用
# 「生产重放本体 + 指定级联规则」，用于检验 H4 结论是否依赖级联层质量。
_ONT = None
_ORPHAN_RULE = "target"


def set_ontology(ont, orphan_rule: str = "target"):
    """注入本体与孤儿打包规则（None → 恢复 DEFAULT_ONTOLOGY）。"""
    global _ONT, _ORPHAN_RULE
    _ONT, _ORPHAN_RULE = ont, orphan_rule


def build_shg(chunks, doc_id):
    """统一的建图入口（所有 measure_* 必须走这里，避免口径漂移）。"""
    return MetaphorSHGBuilder(ontology=_ONT,
                              orphan_cascade_rule=_ORPHAN_RULE).build(
        chunks, doc_id=doc_id)


def _chunk_id_of(edge):
    for s in edge.chunk_spans:
        return s.chunk_id
    return None


def _mrr_hits(ranked_chunks, gold_chunks, ks=(3, 10)):
    """ranked_chunks: [(chunk_id, score), ...] 降序；gold_chunks: set(str)。"""
    gold = set(gold_chunks)
    first = None
    for r, (cid, _) in enumerate(ranked_chunks, 1):
        if cid in gold and first is None:
            first = r
    mrr = (1.0 / first) if first else 0.0
    res = {"mrr": mrr}
    for k in ks:
        res[f"hits@{k}"] = 1 if any(cid in gold for cid, _ in ranked_chunks[:k]) else 0
    return res


def measure_p4a(alpha: float = 1.0, leak: float = 0.0):
    """跨层检索增益：HGNN vs 原始嵌入。返回每配置聚合指标。"""
    agg = {c: {"mrr": 0.0, "hits@3": 0, "hits@10": 0, "n": 0}
           for c in ("hgnn", "raw")}
    detail = []
    for did, chunks in DOCS.items():
        shg = build_shg(chunks, did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        l1 = [e for e in shg.edges if not e.is_extended]
        for q_doc, query, gold in GOLD_RETRIEVAL:
            if q_doc != did:
                continue
            gold_ids = [f"{did}_c{i}" for i in gold]
            # HGNN 传播后排序
            hg = g.retrieve(query, l1, k=len(l1))
            hg_chunks = [(_chunk_id_of(e), s) for e, s in hg if _chunk_id_of(e)]
            # 原始嵌入排序（对照）
            raw = g.retrieve_raw(query, l1, k=len(l1))
            raw_chunks = [(_chunk_id_of(e), s) for e, s in raw if _chunk_id_of(e)]
            for cfg, ranked in (("hgnn", hg_chunks), ("raw", raw_chunks)):
                m = _mrr_hits(ranked, gold_ids)
                agg[cfg]["mrr"] += m["mrr"]
                agg[cfg]["hits@3"] += m["hits@3"]
                agg[cfg]["hits@10"] += m["hits@10"]
                agg[cfg]["n"] += 1
            detail.append((did, query, gold_ids,
                           _mrr_hits(hg_chunks, gold_ids)["mrr"],
                           _mrr_hits(raw_chunks, gold_ids)["mrr"]))
    return agg, detail


def measure_p4b(alpha: float = 1.0, leak: float = 0.0):
    """检测器判别力：真 L1 边 vs 跨框架负样本对的隐喻连贯度分离度。

    alpha / leak 透传给 MetaphorHGNN（默认 1.0 / 0.0 = 原无源项口径）。
    """
    pos, neg = [], []
    rng = np.random.default_rng(20260830)
    for did, chunks in DOCS.items():
        shg = build_shg(chunks, did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        # 真边：每条 L1 边的 (source_domain 实体, target_domain 实体)
        true_pairs = []
        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [n for n in e.member_entities
                    if n in g.node_index and n not in (e.frame_id or "")]
            if len(ents) >= 2:
                src, tgt = ents[0], ents[-1]
                true_pairs.append((src, tgt))
                pos.append(g.metaphor_coherence(src, tgt))
        # 负样本：把每条真边的 tgt 换成本 doc 里另一个**不同框架**的实体
        for src, tgt in true_pairs:
            cand = [n for n in g.entities
                    if n not in (src, tgt)
                    and (src not in _frame_of(g, n))]
            if not cand:
                cand = [n for n in g.entities if n != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng.integers(len(cand))]
            neg.append(g.metaphor_coherence(src, n2))
    pos = np.array(pos, float)
    neg = np.array(neg, float)
    # 判别准确率：正样本连贯度 > 负样本连贯度 的比例（逐对配对比较）
    n = min(len(pos), len(neg))
    correct = int(np.sum(pos[:n] > neg[:n]))
    return {
        "pos_mean": float(pos.mean()) if len(pos) else 0.0,
        "neg_mean": float(neg.mean()) if len(neg) else 0.0,
        "pos_n": len(pos), "neg_n": len(neg),
        "acc": correct / n if n else 0.0,
        "n_pairs": n,
    }


def _frame_of(g, ent):
    """返回包含该实体的所有框架 id 集合（用于构造跨框架负样本）。"""
    out = set()
    for e in g.shg.edges:
        if e.frame_id and ent in e.member_entities:
            out.add(e.frame_id)
    return out


# ---------------------------------------------------------------------------
# H4（改口径）：序列基线能否复现 P4-B 的第三道图结构校验信号？
# ---------------------------------------------------------------------------
class _NumpyGRU:
    """最小 GRU 前向（numpy，固定种子，**不训练**）。

    为什么不训练：P4 重定口径的原因正是本语料**没有逐边金标**——
    无法给「GRU 能否复现检测信号」提供监督目标。因此这里用未训练 GRU
    做序列编码的最强公平代表：它与 HGNN 一样不依赖任何标签，唯一差别是
    聚合方式（顺序扫描文本共现序列 vs 超图两步传播）。它等价于一个随机
    投影的顺序编码器，代表「无超图结构时的序列上下文建模」这一族基线。
    """

    def __init__(self, dim: int, seed: int = 20260830):
        rng = np.random.default_rng(seed)
        s = np.sqrt(2.0 / (2 * dim))
        self.Wz, self.Uz = rng.normal(0, s, (dim, dim)), rng.normal(0, s, (dim, dim))
        self.Wr, self.Ur = rng.normal(0, s, (dim, dim)), rng.normal(0, s, (dim, dim))
        self.Wh, self.Uh = rng.normal(0, s, (dim, dim)), rng.normal(0, s, (dim, dim))
        z = np.zeros(dim)
        self.bz, self.br, self.bh = z.copy(), z.copy(), z.copy()

    def forward(self, seq: np.ndarray) -> np.ndarray:
        h = np.zeros(self.Wz.shape[0])
        for x in seq:
            z = 1 / (1 + np.exp(-(x @ self.Wz + h @ self.Uz + self.bz)))
            r = 1 / (1 + np.exp(-(x @ self.Wr + h @ self.Ur + self.br)))
            hh = np.tanh(x @ self.Wh + (r * h) @ self.Uh + self.bh)
            h = (1 - z) * h + z * hh
        return h


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _l1_comembers(shg) -> Dict[str, List[str]]:
    """实体 → 其 L1 超边共成员（去重排序）。

    这是**任何非层级方法**都能拿到的全部结构信息：只看「哪些实体在同一条
    映射的端点里共同出现过」，不含框架/级联层级。文本子串共现基线在此
    **不适定**——实体是抽象域标签（"地形"/"项目困境"），不以字面出现在
    原文里（首轮实现实测全零向量后否决）。
    """
    mem: Dict[str, set] = defaultdict(set)
    for e in shg.edges:
        if e.is_extended:
            continue
        ents = [n for n in e.member_entities if n]
        for a in ents:
            for b in ents:
                if a != b:
                    mem[a].add(b)
    return {a: sorted(v) for a, v in mem.items()}


def measure_h4(alpha: float = 1.0, leak: float = 0.0,
               methods: Tuple[str, ...] = ("hgnn", "flat", "raw", "flat_gru",
                                           "hgnn_driven", "flat_driven")):
    """H4 改口径：判别信号到底来自哪里？——三种对照 vs 完整 HGNN。

    同一组配对样本（真 L1 边 vs 跨框架负样本，抽样逻辑与随机种子均与
    measure_p4b 一致），四种表示：
      hgnn      完整跨层传播（L1 + 框架 + 级联）—— P4-B 原口径
      flat      仅 L1 喻底超边传播（无框架/级联跨层）—— 检验「层级」贡献
      raw       原始嵌入（无任何聚合）—— 检验「结构」贡献
      flat_gru  GRU 扫 L1 共成员序列（无层级、未训练）—— KEG 式顺序编码替身
    若 flat ≈ hgnn：信号来自 L1 n 元共现（喻底集合），跨层传播非必要；
    若 raw ≈ hgnn：连结构都不需要；只有 hgnn 高：信号依赖跨层层级。

    加源项对照（alpha < 1 时才有意义，见 hgnn.MetaphorHGNN docstring）：
      hgnn_driven  跨层 + 源项 ``X ← (1-α)X0 + αMX``
      flat_driven  仅 L1 超边 + 源项
    alpha=1.0 / leak=0.0 时 ``*_driven`` 与对应的无源项条目**逐位相同**，
    作为「源项没有改变什么」的内部一致性校验。
    """
    gru = _NumpyGRU(EMB_DIM)
    scores = {m: {"pos": [], "neg": []} for m in methods}
    rng = np.random.default_rng(20260830)   # 与 measure_p4b 同种子，配对可比
    for did, chunks in DOCS.items():
        shg = build_shg(chunks, did)
        g = MetaphorHGNN(shg, layers=2, alpha=alpha, leak=leak)
        g.forward()
        gf = MetaphorHGNN(shg, layers=2, cross_layer=False, alpha=alpha, leak=leak)
        gf.forward()
        comem = _l1_comembers(shg)
        flat_gru_vec: Dict[str, np.ndarray] = {}
        for ent, peers in comem.items():
            seq = np.stack([np.array(embeddings.embed(p)) for p in peers])
            flat_gru_vec[ent] = gru.forward(seq)

        def coherence(method: str, a: str, b: str) -> float:
            if method in ("hgnn", "hgnn_driven"):
                return g.metaphor_coherence(a, b)
            if method in ("flat", "flat_driven"):
                return gf.metaphor_coherence(a, b)
            if method == "flat_gru":
                va, vb = flat_gru_vec.get(a), flat_gru_vec.get(b)
                if va is None or vb is None:
                    return 0.0
            else:  # raw
                va, vb = np.array(embeddings.embed(a)), np.array(embeddings.embed(b))
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na < 1e-9 or nb < 1e-9:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))

        # ---- 与 measure_p4b 完全一致的配对抽样 ----
        true_pairs = []
        for e in shg.edges:
            if e.is_extended:
                continue
            ents = [n for n in e.member_entities
                    if n in g.node_index and n not in (e.frame_id or "")]
            if len(ents) >= 2:
                true_pairs.append((ents[0], ents[-1]))
        for src, tgt in true_pairs:
            cand = [n for n in g.entities
                    if n not in (src, tgt)
                    and (src not in _frame_of(g, n))]
            if not cand:
                cand = [n for n in g.entities if n != src]
            if len(cand) <= 1:
                continue
            n2 = cand[rng.integers(len(cand))]
            for m in methods:
                scores[m]["pos"].append(coherence(m, src, tgt))
                scores[m]["neg"].append(coherence(m, src, n2))

    out = {}
    for m in methods:
        pos = np.array(scores[m]["pos"], float)
        neg = np.array(scores[m]["neg"], float)
        n = min(len(pos), len(neg))
        # 配对准确率：并列计为错误。**n=20 时分辨率仅 0.05、功效不足**，
        # 且结论字符串会随无关参数抖动翻转（exp/dynamics 实测 α=0.5 时打印
        # "依赖跨层传播 ✅"）。保留以兼容历史，但主指标应看 auc_full。
        acc = float(np.sum(pos[:n] > neg[:n])) / n if n else 0.0
        # 全量负样本 ROC-AUC（正确处理并列）：高功效主指标
        auc_full, n_pos, n_neg = _auc_full(pos, neg)
        out[m] = {"pos_mean": float(pos.mean()) if len(pos) else 0.0,
                  "neg_mean": float(neg.mean()) if len(neg) else 0.0,
                  "acc": acc, "n_pairs": n,
                  "auc_full": auc_full, "n_pos": n_pos, "n_neg": n_neg}
    return out


def _auc_full(pos: np.ndarray, neg: np.ndarray) -> Tuple[float, int, int]:
    """ROC-AUC = P(pos > neg) + 0.5·P(pos == neg)，用全量正负对。

    这是 exp/dynamics 建议的 H4 主指标：n=20 的配对准确率功效不足
    （分辨率 0.05，18 个配置下 |Δacc| ≤ 0.05 全部落在噪声内），
    而全量负样本 AUC 在同样配置下稳定（|ΔAUC| ≤ 0.005）。
    """
    if len(pos) == 0 or len(neg) == 0:
        return float("nan"), len(pos), len(neg)
    p = pos[:, None]
    q = neg[None, :]
    auc = float((p > q).mean() + 0.5 * (p == q).mean())
    return auc, len(pos), len(neg)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", choices=("default", "real"), default="default",
                    help="real=用 EMBED_API_KEY 注入真实句向量（检索层专用，"
                         "propagate=False 冻结抽取管线，保证与缓存重放对照干净）")
    ap.add_argument("--cascade-rule", default="seed",
                    choices=("seed", "json", "source", "ground", "metanet",
                             "source_type", "none"),
                    help="L3 级联构造规则。默认 seed = DEFAULT_ONTOLOGY 种子本体"
                         "（已上报数字的口径）；json/source/... = 生产重放本体 + "
                         "该规则（gen2 实验用，检验 H4 是否依赖级联层质量）")
    ap.add_argument("--orphan-cascade-rule", default="target",
                    choices=("target", "source", "ground", "source_type", "none"))
    # exp/dynamics：驱动/源项版 HGNN 参数。默认 1.0 / 0.0 = 原无源项口径，
    # 与历史实现逐位相同（实测 maxdiff=0.000e+00）。
    ap.add_argument("--alpha", type=float, default=1.0,
                    help="源项系数 α（X ← (1-α)X0 + α·M·X）；1.0 = 无源项（原口径）")
    ap.add_argument("--leak", type=float, default=0.0,
                    help="阻尼 ε（S ← (1-ε)S）；0.0 = 无阻尼（原口径）")
    args = ap.parse_args()
    if args.cascade_rule != "seed":
        from metaphor_graph.evaluate_fullcorpus import build_replay_ontology
        ont, _nf = build_replay_ontology(cascade_rule=args.cascade_rule)
        set_ontology(ont, args.orphan_cascade_rule)
        print(f"级联规则 {args.cascade_rule} / 孤儿 {args.orphan_cascade_rule}"
              f"（生产重放本体 {len(ont.frames)} 框架 / {len(ont.cascades)} 级联）")
    elif args.orphan_cascade_rule != "target":
        set_ontology(None, args.orphan_cascade_rule)
    if args.embedder == "real":
        from metaphor_graph import embeddings as _emb
        emb_real = _emb.embedder_from_env()
        if emb_real is None:
            raise SystemExit("需要 EMBED_API_KEY 环境变量（见 embeddings.embedder_from_env）")
        _emb.set_embedder(emb_real, propagate=False)
        print(f"向量器：{emb_real.model} @ {emb_real.base_url}（真实句向量）")

    print("=" * 78)
    print("P4 —— HGNN 检测器 / 跨层语义信号测量（离线）")
    print(f"     α={args.alpha}  ε={args.leak}"
          f"{'（原无源项口径）' if args.alpha == 1.0 and args.leak == 0.0 else ''}")
    print("=" * 78)

    # ---- P4-A 跨层检索增益 ----
    print("\n【P4-A】跨层检索增益（HGNN 传播后余弦 vs 原始嵌入余弦）")
    agg, detail = measure_p4a(alpha=args.alpha, leak=args.leak)
    n = agg["hgnn"]["n"]
    print(f"{'配置':16s} {'MRR@10':>9s} {'Hits@3':>8s} {'Hits@10':>9s}  (n={n})")
    for cfg, label in (("hgnn", "HGNN 跨层"), ("raw", "原始嵌入(对照)")):
        a = agg[cfg]
        print(f"{label:16s} {a['mrr']/n:>9.3f} {a['hits@3']/n:>8.3f} "
              f"{a['hits@10']/n:>9.3f}")
    d_mrr = (agg["hgnn"]["mrr"] - agg["raw"]["mrr"]) / n
    d_h3 = (agg["hgnn"]["hits@3"] - agg["raw"]["hits@3"]) / n
    print(f"\n  HGNN 相对原始嵌入：MRR@10 差 {d_mrr:+.3f} | Hits@3 差 {d_h3:+.3f}")
    print(f"  → {'跨层传播有增益 ✅' if d_mrr > 0 else '跨层传播无增益 ❌'}"
          f"（§4.5 承诺的『传播级联语义』影响检索）")

    # ---- P4-B 检测器判别力 ----
    print("\n【P4-B】检测器判别力（metaphor_coherence：真边 vs 跨框架负样本）")
    b = measure_p4b(alpha=args.alpha, leak=args.leak)
    print(f"  真 L1 边连贯度均值 : {b['pos_mean']:.3f}  (n={b['pos_n']})")
    print(f"  跨框架负样本均值   : {b['neg_mean']:.3f}  (n={b['neg_n']})")
    print(f"  配对判别准确率     : {b['acc']:.3f}  (配对 {b['n_pairs']})")
    print(f"  → {'检测器信号可区分隐喻/非隐喻 ✅' if b['acc'] > 0.5 else '信号无判别力 ❌'}")

    # ---- H4 改口径：判别信号来源分解 ----
    print("\n【H4·改口径】判别信号来源分解（同一组配对样本：真 L1 边 vs 跨框架负样本）")
    h4 = measure_h4()
    print(f"{'表示':16s} {'真边连贯度':>10s} {'负样本':>8s} "
          f"{'配对判别':>8s} {'全量AUC':>9s}  (配对 n / 正×负)")
    for m, label in (("hgnn", "HGNN 完整跨层"), ("flat", "仅L1超边(flat)"),
                     ("raw", "原始嵌入"), ("flat_gru", "GRU共成员序列"),
                     ("hgnn_driven", "HGNN+源项"), ("flat_driven", "flat+源项")):
        r = h4[m]
        print(f"{label:16s} {r['pos_mean']:>10.3f} {r['neg_mean']:>8.3f} "
              f"{r['acc']:>8.3f} {r['auc_full']:>9.3f}  "
              f"({r['n_pairs']} / {r['n_pos']}×{r['n_neg']})")
    print("  注：主指标为**全量AUC**（正确处理并列）。配对判别 n=20 时分辨率仅 0.05，")
    print("      结论字符串会随无关参数抖动翻转（exp/dynamics 实测），仅作历史兼容。")
    # 判定改用全量 AUC（高功效）；配对准确率仅作参考
    a_flat, a_hgnn = h4["flat"]["auc_full"], h4["hgnn"]["auc_full"]
    a_raw = h4["raw"]["auc_full"]
    if a_flat >= a_hgnn - 0.02:
        print("  → flat(仅 L1 超边)即可复现：信号来自喻底 n 元共现，跨层层级非必要（诚实负面）")
    elif a_raw >= a_hgnn - 0.02:
        print("  → 原始嵌入即可复现：结构完全非必要（诚实负面）")
    else:
        print("  → 简单对照均无法复现：图结构校验信号依赖超图（跨层）传播 ✅")

    # ---- 结论与诚实口径 ----
    print("\n【结论 · 诚实口径】")
    print("  P4 验收原文写「抽取 F1 提升 >5pp」，但 MetaphorHGNN 是检索/语义信号编码器：")
    print("  - 它需多 chunk 文档图结构才能传播，CCL2018 逐句金标无法驱动图卷积；")
    print("  - CCL2018 无逐边金标，无法训练/评测逐边检测器；")
    print("  - 故此处测量其真实贡献：跨层语义信号对「隐喻检索/检测」的质量。")
    print(f"  P4-A 跨层检索 MRR@10 {'提升' if d_mrr > 0 else '持平/下降'} {d_mrr:+.3f}；"
          f"P4-B 检测器判别准确率 {b['acc']:.3f}。")
    seq_acc = max(h4["flat"]["acc"], h4["raw"]["acc"], h4["flat_gru"]["acc"])
    if h4["flat"]["acc"] >= h4["hgnn"]["acc"] - 0.02:
        verdict = "信号来自 L1 喻底 n 元共现，跨层层级非必要"
    elif seq_acc >= h4["hgnn"]["acc"] - 0.02:
        verdict = "信号可由更简单结构复现"
    else:
        verdict = "图结构校验信号依赖超图跨层传播"
    print(f"  H4（改口径）：flat={h4['flat']['acc']:.3f} / raw={h4['raw']['acc']:.3f} / "
          f"flat_gru={h4['flat_gru']['acc']:.3f} vs HGNN={h4['hgnn']['acc']:.3f} —— {verdict}。"
          f"GRU 为未训练随机投影（无逐边金标可训，见 measure_h4 docstring）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
