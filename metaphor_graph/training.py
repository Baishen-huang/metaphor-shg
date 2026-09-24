"""可训练的隐喻排序器 + 零标注成本的训练样本构造。

动机
----
`RetrievalEngine.metaphor_retriever_score` 此前是 4 个分数的人工加权
（0.35/0.25/0.20/0.20）走一个「MLP」，但**没有训练数据、没有训练循环**——
它是装饰，不是检索器。HyperRAG（WWW 2026）的 HyperRetriever 之所以有效，
关键在于它有监督信号：

    正样本 = 连接主题实体到答案的**最短路径**上的三元组
    负样本 = 同一头实体关联的、不在该路径上的其他三元组

我们的语料没有「检索路径」标注，但有一件等价的东西：**L1.5 扩展隐喻的
chunk 链**。同一条链上的两条超边互为对方的检索目标（扩展隐喻消歧正是
检索任务本身），同触发词但不同框架的超边则是天然负样本。于是监督信号
可以零标注成本构造。

特征
----
在原 4 维（sem / struct / clue / type）基础上，补两个**角色感知的结构信号**。
不能直接照搬 HyperRAG 的 DDE——它的伪三元组展开假设端点同质，而我们的
端点带角色（源域 / 目标域 / 喻底）。这里用「同框架 / 同级联 / 喻底 Jaccard」
作为角色保留的结构邻近度，等价于给伪三元组加了角色标记。
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import embeddings
from .extended import _min_span_gap
from .models import MetaphorHyperedge, MetaphorSHG
from .ontology import DEFAULT_ONTOLOGY

FEATURE_NAMES = [
    "sem",        # 查询超边与候选超边描述的语义相似度
    "struct",     # 候选超边中心性（喻底规模 + 级联归属）
    "clue",       # 触发词重合度
    "type",       # 类型安全约束（结构化防污染，本项目独有）
    "same_frame", # 角色感知结构信号：同框架
    "same_cascade",  # 角色感知结构信号：同级联
    "ground_jaccard",  # 喻底集合 Jaccard（扩展隐喻合并判据的连续化）
]


# ------------------------------------------------------------------ 特征抽取
def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def extract_text_features(query_text: str,
                          cand: MetaphorHyperedge,
                          centrality: Optional[Dict[str, float]] = None,
                          ontology=None) -> List[float]:
    """给定「查询文本」与「候选超边」，抽出同样的 7 维特征。

    与 extract_features 的区别只在语义锚点：后者比较两个超边（训练期），
    本函数比较一段文本与一个超边（推理期）。两者口径必须一致，
    否则就是典型的特征漂移。
    """
    q_emb = embeddings.embed(query_text)
    c_emb = embeddings.embed(cand.describe())
    sem = max(0.0, embeddings.cosine(q_emb, c_emb))

    if centrality is not None:
        struct = min(1.0, centrality.get(cand.id, 0.0))
    else:
        struct = min(1.0, 0.5 * len(cand.ground) + (0.5 if cand.cascade_id else 0.0))

    clue = min(1.0, 0.5 * sum(1 for t in cand.triggers if t in query_text))

    # 类型护栏：与 retrieval.metaphor_retriever_score 共用同一个封顶可靠性函数。
    # 此前这里是 `1.0 if cand.frame_id else 0.0`，而检索路径查本体后 type_valid
    # 会把未注册的 F_LLM_* 回退框架判 0.0 —— 同一候选在两条路径上得到不同的
    # type 值（特征漂移）。现统一走 ontology.type_reliability：
    # 注册框架 1.0 / 未注册回退框架 0.5 / 无归属或非法 0.0。
    ont = ontology if ontology is not None else DEFAULT_ONTOLOGY
    type_ok = ont.type_reliability_of(cand.frame_id, cand.source_type)

    same_frame = same_cas = 0.0
    if ontology is not None:
        toks = [t for t in ontology._trigger_index if t in query_text]
        frames = {f.id for f in ontology.match_by_triggers(toks)}
        cascades = {ontology.get_cascade(fid) for fid in frames} - {None}
        same_frame = 1.0 if cand.frame_id in frames else 0.0
        same_cas = 1.0 if cand.cascade_id in cascades else 0.0

    g = set(cand.ground)
    gj = (len({w for w in g if w in query_text}) / max(1, len(g))) if g else 0.0
    return [sem, struct, clue, type_ok, same_frame, same_cas, gj]


def extract_features(query_edge: MetaphorHyperedge,
                     cand: MetaphorHyperedge,
                     centrality: Optional[Dict[str, float]] = None,
                     ontology=None) -> List[float]:
    """给定「查询超边」与「候选超边」，抽出 7 维特征。

    ontology 用于 type 护栏的注册查询，必须与推理期（RetrievalEngine）传
    同一个本体实例，否则又回到特征漂移。省略时回落模块级默认本体。
    """
    q_emb = embeddings.embed(query_edge.describe())
    c_emb = embeddings.embed(cand.describe())
    sem = max(0.0, embeddings.cosine(q_emb, c_emb))

    if centrality is not None:
        struct = min(1.0, centrality.get(cand.id, 0.0))
    else:
        struct = min(1.0, 0.5 * len(cand.ground) + (0.5 if cand.cascade_id else 0.0))

    hits = len(set(query_edge.triggers) & set(cand.triggers))
    clue = min(1.0, 0.5 * hits)

    # 与 extract_text_features / retrieval 人工加权路径共用同一函数（见 ontology）
    ont = ontology if ontology is not None else DEFAULT_ONTOLOGY
    type_ok = ont.type_reliability_of(cand.frame_id, cand.source_type)

    same_frame = 1.0 if (query_edge.frame_id and query_edge.frame_id == cand.frame_id) else 0.0
    same_cas = 1.0 if (query_edge.cascade_id and query_edge.cascade_id == cand.cascade_id) else 0.0

    return [sem, struct, clue, type_ok, same_frame, same_cas,
            _jaccard(query_edge.ground, cand.ground)]


@dataclass
class TrainingSet:
    X: np.ndarray
    y: np.ndarray
    meta: List[dict] = field(default_factory=list)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    @property
    def positives(self) -> int:
        return int(self.y.sum())


def feature_auc(ds: TrainingSet) -> Dict[str, float]:
    """每个单特征的 AUC —— 用来抓「接近可分」的软泄漏。

    trivial_separators 只抓**完美**可分（AUC=1.0），抓不住 AUC=0.99 这种
    实质上已被单特征决定的样本集。报告指标前必须看这个。
    """
    if len(ds) == 0:
        return {}
    pos_mask = ds.y > 0.5
    out: Dict[str, float] = {}
    for j, name in enumerate(FEATURE_NAMES):
        col = ds.X[:, j]
        pos, neg = col[pos_mask], col[~pos_mask]
        if len(pos) == 0 or len(neg) == 0:
            out[name] = float("nan")
            continue
        gt = (pos[:, None] > neg[None, :]).mean()
        eq = (pos[:, None] == neg[None, :]).mean()
        out[name] = float(gt + 0.5 * eq)
    return out


def leakage_report(ds: TrainingSet, auc_threshold: float = 0.98) -> List[str]:
    """返回单特征 AUC ≥ 阈值的特征名。非空 = 该样本集不适合上报指标。"""
    if len(ds) == 0:
        return []
    aucs = feature_auc(ds)
    return [f"{k} (AUC={v:.3f})" for k, v in aucs.items()
            if v == v and v >= auc_threshold]


def trivial_separators(ds: TrainingSet, threshold: float = 1e-9) -> List[str]:
    """检出「单特征即可完美分类」的构造缺陷。

    典型场景：用 cascade 模式造正样本时，`same_cascade` 按定义就是标签本身
    （负样本 = 不同级联），于是任务线性可分、MRR=1.0——这是评测的自我实现，
    不是模型能力。本函数在这类情况下返回该特征名，供流水线拒绝上报数字。
    """
    if len(ds) == 0 or ds.positives == 0 or ds.positives == len(ds):
        return []
    out: List[str] = []
    for j, name in enumerate(FEATURE_NAMES):
        col = ds.X[:, j]
        pos_min, neg_max = col[ds.y > 0.5].min(), col[ds.y < 0.5].max()
        pos_max, neg_min = col[ds.y > 0.5].max(), col[ds.y < 0.5].min()
        if (pos_min > neg_max + threshold) or (neg_min > pos_max + threshold):
            out.append(name)
    return out


def _build_from_chunks(shg: MetaphorSHG,
                       chunks: Dict[str, str],
                       negatives_per_positive: int = 3,
                       centrality: Optional[Dict[str, float]] = None,
                       seed: int = 42,
                       ontology=None) -> TrainingSet:
    """不泄漏的构造：查询 = chunk 原文，正样本 = 该 chunk 实际抽出的超边。

    监督信号来自抽取流水线自身，无需人工标注；且标签（「这句产生了哪条超边」）
    不直接编码在 7 维特征里的任何一维——模型必须真的学会「文本 ↔ 隐喻映射」
    的匹配才能做对。

    **已知局限（实测）**：在本体召回率 ~7% 的量级下，候选超边只有几十条，
    `clue` 单特征（触发词是否出现在句中）的 AUC 就接近 1.0——因为抽取器
    本来就是靠触发词命中产出这条边的。也就是说，自监督信号只能教会模型
    **模仿抽取器的判定规则**，而不是学会检索。

    这不是 bug，是自监督的固有上限。要拿到真正有区分度的排序信号，需要：
      (a) 先提升 L1 召回（接 LLM 后端，见 README §6.1），把候选池做到千级；
      (b) 或引入人工/LLM 标注的 query→相关超边对；
      (c) 或用下游任务信号（QA 正确率）做弱监督。
    上报任何 MRR / Hits@k 之前，先跑 ``leakage_report(ds)``。
    """
    rng = np.random.default_rng(seed)
    base = [e for e in shg.edges if not e.is_extended]
    if len(base) < 2:
        return TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)))

    # chunk_id → 该 chunk 实际抽出的超边
    produced: Dict[str, List[MetaphorHyperedge]] = {}
    for e in base:
        for s in e.chunk_spans:
            produced.setdefault(s.chunk_id, [])
            if e not in produced[s.chunk_id]:
                produced[s.chunk_id].append(e)

    rows: List[List[float]] = []
    labels: List[int] = []
    meta: List[dict] = []

    for cid, gold in produced.items():
        text = chunks.get(cid)
        if not text:
            continue
        gold_ids = {e.id for e in gold}
        for g in gold:
            rows.append(extract_text_features(text, g, centrality, ontology))
            labels.append(1)
            meta.append({"query": cid, "cand": g.id, "label": 1})
        # 困难负样本优先：同框架或同源域但不在本 chunk 里
        hard = [e for e in base if e.id not in gold_ids
                and (e.frame_id in {x.frame_id for x in gold}
                     or e.source_domain in {x.source_domain for x in gold})]
        easy = [e for e in base if e.id not in gold_ids]
        pool = hard or easy
        for _ in range(max(1, negatives_per_positive) * len(gold)):
            if not pool:
                break
            pick = pool[int(rng.integers(0, len(pool)))]
            rows.append(extract_text_features(text, pick, centrality, ontology))
            labels.append(0)
            meta.append({"query": cid, "cand": pick.id, "label": 0})

    if not rows:
        return TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)))
    return TrainingSet(np.asarray(rows, dtype=float),
                       np.asarray(labels, dtype=float), meta)


# 注意别写成 `def _chain_pairs(  # noqa: E302shg: ...`：那样前两个形参会被吞进
# 注释，实际签名只剩 max_gap，调用时报 "got multiple values for argument 'max_gap'"。
def _chain_pairs(shg: MetaphorSHG, chunk_order: Dict[str, int],
                 max_gap: int = 3) -> set:
    """复现 link_extended_metaphors 的合并判据，得到「同一条链」的正样本对。"""
    from collections import defaultdict

    groups: Dict[tuple, List[MetaphorHyperedge]] = defaultdict(list)
    for e in shg.edges:
        if e.is_extended:
            continue
        groups[(e.frame_id, e.source_domain)].append(e)

    pairs: set = set()
    for (_, _), group in groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda e: min(
            chunk_order.get(s.chunk_id, 10 ** 9) for s in e.chunk_spans))
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                a, b = ordered[i], ordered[j]
                gap = _min_span_gap(a.chunk_spans, b.chunk_spans, chunk_order)
                if gap < max_gap and (set(a.ground) & set(b.ground)):
                    pairs.add((a.id, b.id))
                    pairs.add((b.id, a.id))
    return pairs


def build_training_set(shg: MetaphorSHG,
                       chunk_order: Optional[Dict[str, int]] = None,
                       max_gap: int = 3,
                       negatives_per_positive: int = 3,
                       centrality: Optional[Dict[str, float]] = None,
                       seed: int = 42,
                       positive_mode: str = "chunk",
                       chunks: Optional[Dict[str, str]] = None,
                       ontology=None) -> TrainingSet:
    """零标注成本构造监督信号。

    positive_mode:
      - ``chunk``    **默认，唯一不泄漏的构造**。
                     查询 = 一个 chunk 的原文；正样本 = 该 chunk **实际抽出**的
                     超边；负样本 = 其他 chunk 的超边（优先同框架/同源域的困难
                     负样本）。标签「这个句子产生了哪条超边」不直接编码在任何
                     特征里，因此不是自我实现的评测。

      - ``chain``    正样本 = 同一条**扩展隐喻链**上的超边对。
                     **存在目标泄漏**：正样本按定义「同框架 + 喻底交集≥1」，
                     于是 same_frame / ground_jaccard 单特征即可完美分类。
                     仅作对照，不可用于报告数字。
      - ``cascade``  正样本 = 同一**级联**下的超边对。
                     **同样泄漏**（same_cascade 即标签本身）。仅用于连通流水线。
      - ``both``     chain ∪ cascade（继承同样的泄漏问题）

    用 ``trivial_separators(ds)`` 自检：返回非空即说明该样本集不应上报指标。

    chunks（chunk_id → 原文）在 chunk 模式下必需。
    """
    if positive_mode not in ("chunk", "chain", "cascade", "both"):
        raise ValueError("positive_mode 必须是 chunk / chain / cascade / both")
    if positive_mode == "chunk":
        if not chunks:
            raise ValueError("chunk 模式必须提供 chunks（chunk_id → 原文）")
        return _build_from_chunks(shg, chunks, negatives_per_positive,
                                  centrality, seed, ontology)

    if not chunk_order:
        raise ValueError(f"{positive_mode} 模式需要 chunk_order")

    rng = np.random.default_rng(seed)
    base = [e for e in shg.edges if not e.is_extended]
    if len(base) < 2:
        return TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)))

    positives: set = set()
    if positive_mode in ("chain", "both"):
        positives |= _chain_pairs(shg, chunk_order or {}, max_gap=max_gap)
    if positive_mode in ("cascade", "both"):
        from collections import defaultdict as _dd
        by_cas: Dict[str, List[MetaphorHyperedge]] = _dd(list)
        for e in base:
            if e.cascade_id:
                by_cas[e.cascade_id].append(e)
        for _, group in by_cas.items():
            ids = sorted({e.id for e in group})
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    positives.add((ids[i], ids[j]))
                    positives.add((ids[j], ids[i]))

    # 触发词倒排，用于采困难负样本
    by_trigger: Dict[str, List[MetaphorHyperedge]] = {}
    for e in base:
        for t in e.triggers:
            by_trigger.setdefault(t, []).append(e)

    rows: List[List[float]] = []
    labels: List[int] = []
    meta: List[dict] = []

    def _add(a: MetaphorHyperedge, b: MetaphorHyperedge, label: int):
        rows.append(extract_features(a, b, centrality, ontology))
        labels.append(label)
        meta.append({"query": a.id, "cand": b.id, "label": label})

    def _neg_candidates(a: MetaphorHyperedge) -> List[MetaphorHyperedge]:
        """优先困难负样本（同触发词不同链），不足时回落到随机负样本。

        必须保证有负样本：只有正样本的话 BCE 会退化成「全预测为正」，
        训练出来的排序器毫无区分度。
        """
        hard = [e for t in a.triggers for e in by_trigger.get(t, [])]
        hard = [e for e in hard if e.id != a.id and (a.id, e.id) not in positives]
        if hard:
            return list(dict.fromkeys(hard))
        easy = [e for e in base if e.id != a.id and (a.id, e.id) not in positives]
        return easy

    for (aid, bid) in sorted(positives):
        a = next((e for e in base if e.id == aid), None)
        b = next((e for e in base if e.id == bid), None)
        if a is None or b is None:
            continue
        _add(a, b, 1)
        cands = _neg_candidates(a)
        for _ in range(max(1, negatives_per_positive)):
            if not cands:
                break
            pick = cands[int(rng.integers(0, len(cands)))]
            _add(a, pick, 0)

    if not rows:
        return TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)))
    return TrainingSet(np.asarray(rows, dtype=float),
                       np.asarray(labels, dtype=float), meta)


# ------------------------------------------------------------------ 打分器
def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class MetaphorScorer:
    """纯 numpy 的 logistic 排序器（对标 HyperRetriever 的可训练 MLP）。

    之所以不上 torch：本包只依赖 numpy，且特征只有 7 维，logistic 回归
    已足以验证「训练过的排序器是否优于人工加权」这一核心假设。
    若后续要换成真 MLP，只需替换本类的 forward/backward。
    """

    def __init__(self, n_features: int = len(FEATURE_NAMES), seed: int = 42):
        self.n_features = n_features
        self.w = np.zeros(n_features)
        self.b = 0.0
        self.mu: Optional[np.ndarray] = None
        self.sd: Optional[np.ndarray] = None
        self.rng = np.random.default_rng(seed)
        self.history: List[float] = []

    # ---- 标准化：不同特征量纲差异大（sem∈[0,1] vs struct∈[0,3]）----
    def _fit_scaler(self, X: np.ndarray):
        self.mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd < 1e-8] = 1.0
        self.sd = sd

    def _scale(self, X: np.ndarray) -> np.ndarray:
        if self.mu is None or self.sd is None:
            return X
        return (X - self.mu) / self.sd

    def fit(self, ds: TrainingSet, epochs: int = 50, batch_size: int = 32,
            lr: float = 0.1, patience: int = 10,
            l2: float = 1e-4, verbose: bool = False) -> "MetaphorScorer":
        """BCE + 小批量梯度下降 + 早停（超参口径与 HyperRAG 对齐）。"""
        if len(ds) == 0:
            return self
        X = np.asarray(ds.X, dtype=float)
        y = np.asarray(ds.y, dtype=float)
        if X.shape[0] < 2:
            return self

        self._fit_scaler(X)
        Xs = self._scale(X)
        # 类别不平衡时给正样本加权（正样本通常远少于负样本）
        n_pos = max(1.0, float(y.sum()))
        n_neg = max(1.0, float(len(y) - y.sum()))
        w_pos = (n_pos + n_neg) / (2.0 * n_pos)
        w_neg = (n_pos + n_neg) / (2.0 * n_neg)
        sample_w = np.where(y > 0.5, w_pos, w_neg)

        self.w = self.rng.normal(0, 0.01, size=self.n_features)
        self.b = 0.0
        best_loss, best_w, best_b, wait = float("inf"), self.w.copy(), 0.0, 0

        for ep in range(epochs):
            idx = self.rng.permutation(len(y))
            for start in range(0, len(idx), batch_size):
                bi = idx[start:start + batch_size]
                xb, yb, wb = Xs[bi], y[bi], sample_w[bi]
                p = _sigmoid(xb @ self.w + self.b)
                # BCE 对样本加权后的梯度
                g = (p - yb) * wb
                grad_w = (xb.T @ g) / max(1, len(bi)) + l2 * self.w
                grad_b = g.sum() / max(1, len(bi))
                self.w -= lr * grad_w
                self.b -= lr * grad_b

            p_all = _sigmoid(Xs @ self.w + self.b)
            eps = 1e-9
            loss = float(-(sample_w * (y * np.log(p_all + eps)
                                       + (1 - y) * np.log(1 - p_all + eps))).mean())
            self.history.append(loss)
            if verbose:
                print(f"epoch {ep + 1}/{epochs} loss={loss:.4f}")
            if loss < best_loss - 1e-6:
                best_loss, best_w, best_b, wait = loss, self.w.copy(), self.b, 0
            else:
                wait += 1
                if wait >= patience:
                    break
        self.w, self.b = best_w, best_b
        return self

    def predict_proba(self, X) -> np.ndarray:
        Xs = self._scale(np.atleast_2d(np.asarray(X, dtype=float)))
        return _sigmoid(Xs @ self.w + self.b)

    def score_features(self, features: Sequence[float]) -> float:
        return float(self.predict_proba([list(features)])[0])

    def weights(self) -> Dict[str, float]:
        return dict(zip(FEATURE_NAMES, [round(float(v), 4) for v in self.w]))

    def save(self, path: str):
        # numpy 数组不能用于 `or` 的真值判断，必须显式判 None
        mu = self.mu if self.mu is not None else np.zeros(self.n_features)
        sd = self.sd if self.sd is not None else np.ones(self.n_features)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"w": self.w.tolist(), "b": self.b,
                       "mu": np.asarray(mu).tolist(),
                       "sd": np.asarray(sd).tolist()},
                      fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "MetaphorScorer":
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        obj = cls(n_features=len(d["w"]))
        obj.w = np.asarray(d["w"], dtype=float)
        obj.b = float(d["b"])
        obj.mu = np.asarray(d["mu"], dtype=float)
        obj.sd = np.asarray(d["sd"], dtype=float)
        return obj


def build_weak_refine_set(shg: MetaphorSHG,
                          chunk_order: Dict[str, int] = None,
                          chunks: Dict[str, str] = None,
                          ontology=None,
                          refine_path: str = "",
                          negatives_per_positive: int = 3,
                          seed: int = 42) -> Tuple[TrainingSet, dict]:
    """LLM-refine **弱监督**训练集（P3「排序器收口」的离线迭代，路线图 §8.2）。

    自监督 chunk 模式的天花板（§7.3 A7）：负样本是随机抽的，其触发词与
    正样本几乎不重叠 → clue 单特征 AUC≈1.0，排序器退化成「复读抽取器」。

    refine 缓存里躺着**真金白银买来的标签**：`batch_refine` 把每个
    (chunk, 源域, 目标域) 候选的 LLM 判断落了盘 —— is_metaphor=False / None
    的候选是「同 chunk、同触发词、但被模型否决」的**天然困难负样本**。
    它们的 clue 特征与正样本几乎相同（触发词就在同一句里），所以 clue
    不再完美可分 —— 这正是突破 clue-AUC≈1.0 天花板的机制。

    构成：
      正样本  = chunk 模式同款（该 chunk 实际抽出的超边）。
      负样本  = ① 该 chunk 在 refine 缓存中被否决的候选（伪超边：绑得上
                本体框架就复用其 ground/triggers，绑不上用 [源域] 兜底）；
                ② 不足 negatives_per_positive 倍时用随机困难负样本补齐。

    返回 (TrainingSet, stats)；stats 记录 pos / neg_llm / neg_random 构成，
    供调用方报告「弱监督信号的纯度」。
    """
    import json as _json
    from collections import defaultdict as _dd

    rng = np.random.default_rng(seed)
    base = [e for e in shg.edges if not e.is_extended]
    centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                  for e in shg.edges}
    if len(base) < 2 or not chunks:
        return TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))), {}

    rejected_by_chunk: dict = _dd(list)
    if refine_path and os.path.exists(refine_path):
        with open(refine_path, "r", encoding="utf-8") as fh:
            for k, v in _json.load(fh):
                # v is None（哨兵）或 is_metaphor=False 都是模型否决
                if v is None or not v.get("is_metaphor", True):
                    rejected_by_chunk[k[0]].append((k[1], k[2]))

    produced: dict = _dd(list)
    for e in base:
        for s in e.chunk_spans:
            produced.setdefault(s.chunk_id, []).append(e)

    rows, labels, meta = [], [], []
    stats = {"pos": 0, "neg_llm": 0, "neg_random": 0, "n_chunks": 0}
    for cid, gold in produced.items():
        text = chunks.get(cid)
        if not text:
            continue
        stats["n_chunks"] += 1
        gold_ids = {e.id for e in gold}
        for g in gold:
            rows.append(extract_text_features(text, g, centrality, ontology))
            labels.append(1)
            meta.append({"query": cid, "cand": g.id, "label": 1})
            stats["pos"] += 1
        # ① LLM 否决的候选（与正样本同句同触发词 → 困难负样本）
        llm_negs = list(rejected_by_chunk.get(text, []))
        rng.shuffle(llm_negs)
        n_llm = min(len(llm_negs), negatives_per_positive * len(gold))
        for src, tgt in llm_negs[:n_llm]:
            frame = ontology.match_frame(src, tgt) if ontology is not None else None
            fs = ontology.get_frame(frame) if frame else None
            ground = list(fs.ground) if fs is not None else []
            triggers = list(fs.triggers) if fs is not None else [src]
            import hashlib as _hl
            pseudo = MetaphorHyperedge(
                id="REF_" + _hl.md5(f"{cid}|{src}|{tgt}".encode("utf-8")
                                    ).hexdigest()[:8],
                source_domain=src, target_domain=tgt, ground=ground,
                triggers=triggers)
            rows.append(extract_text_features(text, pseudo, centrality, ontology))
            labels.append(0)
            meta.append({"query": cid, "cand": pseudo.id, "label": 0,
                         "source": "refine_reject"})
            stats["neg_llm"] += 1
        # ② 随机困难负样本补齐（与 chunk 模式同池）
        need = max(0, negatives_per_positive * len(gold) - n_llm)
        hard = [e for e in base if e.id not in gold_ids
                and (e.frame_id in {x.frame_id for x in gold}
                     or e.source_domain in {x.source_domain for x in gold})]
        easy = [e for e in base if e.id not in gold_ids]
        pool = hard or easy
        for _ in range(need):
            if not pool:
                break
            pick = pool[int(rng.integers(0, len(pool)))]
            rows.append(extract_text_features(text, pick, centrality, ontology))
            labels.append(0)
            meta.append({"query": cid, "cand": pick.id, "label": 0,
                         "source": "random"})
            stats["neg_random"] += 1

    if not rows:
        return (TrainingSet(np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,))),
                stats)
    return (TrainingSet(np.asarray(rows, dtype=float),
                        np.asarray(labels, dtype=float), meta), stats)


def train_from_shg(shg: MetaphorSHG, chunk_order: Dict[str, int] = None,
                   chunks: Optional[Dict[str, str]] = None,
                   ontology=None, positive_mode: Optional[str] = None,
                   **kwargs) -> Tuple[MetaphorScorer, TrainingSet]:
    """一步到位：造样本 → 训练 → 返回打分器。

    提供 chunks（chunk_id → 原文）时默认走不泄漏的 chunk 模式；否则回落到
    cascade 结构模式（有泄漏，仅供连通性验证）。
    """
    centrality = {e.id: 0.5 * len(e.ground) + (0.5 if e.cascade_id else 0.0)
                  for e in shg.edges}
    mode = positive_mode or ("chunk" if chunks else "cascade")
    ds = build_training_set(shg, chunk_order=chunk_order, chunks=chunks,
                            centrality=centrality, ontology=ontology,
                            positive_mode=mode)
    scorer = MetaphorScorer().fit(ds, **kwargs)
    return scorer, ds
