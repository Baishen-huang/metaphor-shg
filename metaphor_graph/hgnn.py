"""超图版 KEG 与跨层消息传递（方案 §4.5）。

§4.5.2 借鉴 HyperC2Net 跨层设计：把不同层次的特征拼接/聚合，再通过超图
卷积让不同层级的特征点相互传递信息。本实现用 numpy 完成一个可运行的
跨层 HGNN：节点→超边→节点两步消息传递。

预期效果（方案原文）：查询含「发条」时，系统不仅检索「发条→紧绷」L1 映射，
还能经消息传递获得 L3 级联 LIFE_IS_A_MACHINE 的语义，从而主动检索
「机械重复」「缺乏弹性」相关 chunk。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import numpy as np

from . import embeddings
from .models import MetaphorCascade, MetaphorFrame, MetaphorHyperedge, MetaphorSHG

EMB_DIM = embeddings.DIM


class MetaphorHGNN:
    def __init__(self, shg: MetaphorSHG, layers: int = 2,
                 cross_layer: bool = True,
                 alpha: float = 1.0, leak: float = 0.0):
        """cross_layer=False 时只保留 L1 喻底超边，跳过框架/级联跨层边 ——
        用于 H4 消融：检验「图结构校验信号」是来自 L1 n 元共现还是跨层传播。

        alpha（源项/驱动系数，默认 1.0 = 原无源项行为）
        ------------------------------------------------
        迭代式： ``X ← (1-α)·X0 + α·M·X``，其中 M 为 ``_conv`` 的传播算子。
        - α = 1.0（默认）：退化为原实现 ``X ← M·X`` 迭代 layers 次，即
          ``M^layers·X0`` —— **既有数字与既有测试完全不变**；
        - α = 0.0：不做任何传播（H == X0）；
        - 0 < α < 1：驱动/阻尼形式。**注意这不是无源项迭代的近似**：
          S 行和恰为 1（行随机），无源项时 ``M^k X0`` 收敛到连通分量的
          平稳分布，同分量节点最终向量相同 → ``metaphor_coherence`` 退化为
          「是否同分量」的近似二值指示。加上 ``(1-α)X0`` 源项后，不动点
          ``u* = (1-α)(I - αM)^{-1} X0`` 保留了各自的源身份，不再坍缩。

        leak（严格次随机阻尼 ε，默认 0.0）
        -----------------------------------
        把 ``S`` 替换为 ``(1-ε)S``，于是 ``M_ε = 0.5(I + (1-ε)S)`` 行和
        ``= 1 - ε/2 < 1`` 严格成立（谱半径 ``ρ(M_ε) ≤ 1 - ε/2``）。
        RiverMemo 式算子的 resolvent ``(I - αT)^{-1}`` 要求 ``Σ_j P_ij < 1``
        严格成立才能对**任意** α 收敛；ε=0 时 ρ(M)=1，α 必须 < 1。
        代价：ε>0 时无源项迭代本身会几何衰减到 0（信息随层数流失），
        因此 ε 只在**配合源项**时才有意义。

        合法性：α ∈ [0, 1] 一律允许（α=1、ε=0 是非收缩边界，截断迭代仍有界）；
        α > 1 需要 ``α·(1-ε/2) < 1`` 严格成立（否则 Neumann 级数发散）。
        """
        if not (0.0 <= leak < 1.0):
            raise ValueError(f"leak 须在 [0, 1) 内，得到 {leak}")
        if alpha < 0.0:
            raise ValueError(f"alpha 须 >= 0，得到 {alpha}")
        if alpha > 1.0 and alpha * (1.0 - leak / 2.0) >= 1.0:
            raise ValueError(
                f"alpha={alpha} 且 leak={leak} 时 α·(1-ε/2)={alpha*(1-leak/2.0):.4f} >= 1，"
                "Neumann 级数 (I-αM)^{-1} 不收敛；请增大 leak 或减小 alpha")
        self.shg = shg
        self.layers = layers
        self.cross_layer = cross_layer
        self.alpha = float(alpha)
        self.leak = float(leak)
        # 节点集合：实体节点（源域/目标域/喻底）+ 框架节点 + 级联节点
        self.entities: List[str] = []
        self.frames: List[str] = []
        self.cascades: List[str] = []
        self._build_nodes()
        self._build_hyperedges()
        self._init_features()

    def _build_nodes(self):
        ent = set()
        for e in self.shg.edges:
            for n in e.member_entities:
                ent.add(n)
        self.entities = sorted(ent)
        self.frames = [f.id for f in self.shg.frames]
        self.cascades = [c.id for c in self.shg.cascades]

    def _build_hyperedges(self):
        """三类超边：① L1 喻底超边 ② 跨层(框架↔其成员映射实体) ③ 跨层(级联↔其框架)。"""
        self.he_members: List[List[int]] = []  # 每条超边包含的节点全局索引
        self.node_index: Dict[str, int] = {}
        all_nodes = self.entities + self.frames + self.cascades
        for i, n in enumerate(all_nodes):
            self.node_index[n] = i
        self.num_nodes = len(all_nodes)

        # ① L1 超边：连接该映射的所有实体端点
        for e in self.shg.edges:
            members = [self.node_index[n] for n in e.member_entities]
            self.he_members.append(members)
        # ② 跨层：框架节点 ↔ 其成员映射的实体（H4 消融可关）
        ent_by_frame: Dict[str, set] = defaultdict(set)
        for e in self.shg.edges:
            if e.frame_id:
                for n in e.member_entities:
                    ent_by_frame[e.frame_id].add(n)
        if self.cross_layer:
            for fid, ents in ent_by_frame.items():
                members = [self.node_index[fid]] + [self.node_index[n] for n in ents]
                self.he_members.append(members)
            # ③ 跨层：级联节点 ↔ 其框架节点
            for c in self.shg.cascades:
                members = [self.node_index[c.id]] + [self.node_index[fid] for fid in c.member_frame_ids]
                self.he_members.append(members)

    def _init_features(self):
        self.X = np.zeros((self.num_nodes, EMB_DIM), dtype=float)
        for n in self.entities:
            self.X[self.node_index[n]] = np.array(embeddings.embed(n))
        for fid in self.frames:
            self.X[self.node_index[fid]] = np.array(embeddings.embed(fid))
        for cid in self.cascades:
            self.X[self.node_index[cid]] = np.array(embeddings.embed(cid))

    def _conv(self, X: np.ndarray) -> np.ndarray:
        """两步空间域超图卷积：节点→超边聚合，超边→节点广播。

        返回 ``M·X``，其中 ``M = 0.5(I + (1-ε)S)``，``ε = self.leak``。
        源项在 ``forward`` 里加（``_conv`` 保持「纯传播算子」语义）。
        """
        # 空超边图（全零边文档）直接返回，避免 np.stack 空列表崩溃
        if not self.he_members:
            return X
        # 节点→超边：每条超边取成员节点的均值
        he_feat = []
        for members in self.he_members:
            if not members:
                he_feat.append(np.zeros(EMB_DIM))
            else:
                he_feat.append(X[members].mean(axis=0))
        he_feat = np.stack(he_feat)  # (E, D)
        # 超边→节点：每个节点聚合其所属超边的均值
        newX = np.zeros_like(X)
        counts = np.zeros(self.num_nodes)
        for j, members in enumerate(self.he_members):
            for i in members:
                newX[i] += he_feat[j]
                counts[i] += 1
        counts[counts == 0] = 1
        newX /= counts[:, None]
        # 残差连接（HyperC2Net 风格）+ 可选严格次随机阻尼 ε
        return 0.5 * (X + (1.0 - self.leak) * newX)

    def propagation_matrix(self) -> np.ndarray:
        """稠密传播算子 M = 0.5(I + (1-ε)·Dv^{-1} H De^{-1} H^T)。

        与 ``_conv`` 的循环实现逐元素等价，供谱分析 / 单元测试使用。
        孤立节点（度 0）行全 0，与 ``_conv`` 的 ``counts[counts==0]=1`` 一致。
        """
        H = np.zeros((self.num_nodes, len(self.he_members)))
        for j, members in enumerate(self.he_members):
            for i in members:
                H[i, j] = 1.0
        dv = H.sum(axis=1)
        de = H.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            dv_inv = np.where(dv > 0, 1.0 / np.where(dv > 0, dv, 1.0), 0.0)
            de_inv = np.where(de > 0, 1.0 / np.where(de > 0, de, 1.0), 0.0)
        S = (dv_inv[:, None] * H) @ (de_inv[:, None] * H.T)
        return 0.5 * (np.eye(self.num_nodes) + (1.0 - self.leak) * S)

    def forward(self) -> np.ndarray:
        """驱动迭代：``X ← (1-α)·X0 + α·M·X``，迭代 ``layers`` 次。

        α = 1.0（默认）时与历史实现逐位一致（``X ← M·X``）；α < 1 时
        X0（各节点自身的嵌入）作为源项被持续注入，避免同分量坍缩。
        """
        X0 = self.X.copy()
        X = X0.copy()
        for _ in range(self.layers):
            X = (1.0 - self.alpha) * X0 + self.alpha * self._conv(X)
        self.H = X
        return X

    def encode(self, node_name: str) -> np.ndarray:
        """返回某节点经跨层消息传递后的表示（含其级联语义）。"""
        if not hasattr(self, "H"):
            self.forward()
        if node_name in self.node_index:
            return self.H[self.node_index[node_name]]
        # 未知词：用其自身嵌入初始化后做一次传播估计
        v = np.array(embeddings.embed(node_name))
        # 简单回退：返回最近实体节点的 H
        best, best_sim = None, -1
        q = v / (np.linalg.norm(v) + 1e-9)
        for n in self.entities:
            h = self.H[self.node_index[n]]
            sim = float(np.dot(q, h / (np.linalg.norm(h) + 1e-9)))
            if sim > best_sim:
                best_sim, best = sim, n
        return self.H[self.node_index[best]] if best else v

    def entity_vec(self, name: str) -> np.ndarray:
        """某实体节点经跨层消息传递后的表示（已知节点直接取，未知走回退）。"""
        if not hasattr(self, "H"):
            self.forward()
        if name in self.node_index:
            return self.H[self.node_index[name]]
        return self.encode(name)

    def edge_repr(self, edge: "MetaphorHyperedge") -> np.ndarray:
        """一条超边（隐喻映射）的图表示：其成员实体表示的均值。

        用于把「映射」投影到与查询相同的 H 空间，从而用余弦做图感知检索。
        """
        if not hasattr(self, "H"):
            self.forward()
        vecs = [self.entity_vec(n) for n in edge.member_entities]
        if not vecs:
            return self.encode(edge.describe())
        return np.mean(vecs, axis=0)

    def metaphor_coherence(self, src: str, tgt: str) -> float:
        """检测器核心：两个实体在跨层图空间中的隐喻连贯度（余弦）。

        高 → 二者在图里通过同一框架/级联紧密相连，构成连贯隐喻；
        低 → 跨框架/无结构关联。这是对「字面误判」与「跨框架串味」的
        图结构判据，独立于触发词与 LLM。
        """
        a, b = self.entity_vec(src), self.entity_vec(tgt)
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def retrieve(self, query_text: str, edges, k: int = 10) -> list:
        """图感知检索：按「查询 vs 各超边」的跨层余弦降序返回 (边, 分)。

        baseline 对照（原始嵌入空间）见 `retrieve_raw`。
        """
        if not hasattr(self, "H"):
            self.forward()
        q = self.encode(query_text)
        scored = []
        for e in edges:
            r = self.edge_repr(e)
            nr = np.linalg.norm(r)
            sim = float(np.dot(q, r) / (np.linalg.norm(q) * nr + 1e-9)) if nr > 1e-9 else 0.0
            scored.append((e, sim))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def retrieve_raw(self, query_text: str, edges, k: int = 10) -> list:
        """原始嵌入空间检索（无跨层传播），作为 HGNN 的对照基线。"""
        q = np.array(embeddings.embed(query_text))
        scored = []
        for e in edges:
            r = np.array(embeddings.embed(e.describe()))
            nr = np.linalg.norm(r)
            sim = float(np.dot(q, r) / (np.linalg.norm(q) * nr + 1e-9)) if nr > 1e-9 else 0.0
            scored.append((e, sim))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
