# -*- coding: utf-8 -*-
"""P5（驱动版 HGNN）实验公用工具：算子矩阵重建 / 谱分析 / 分量分析。

全部离线、零 API 费用。仅在 `.wt/dynamics/experiments/` 下写结果文件。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.hgnn import MetaphorHGNN, EMB_DIM
from metaphor_graph.eval_corpus import DOCS
from metaphor_graph import embeddings


def build_graph(doc_id: str, **kw) -> MetaphorHGNN:
    shg = MetaphorSHGBuilder().build(DOCS[doc_id], doc_id=doc_id)
    return MetaphorHGNN(shg, **kw)


def all_graphs(**kw):
    return {did: build_graph(did, **kw) for did in DOCS}


# ---------------------------------------------------------------------------
# 稠密算子重建（严格按 hgnn._conv 的定义，用于谱/行和验证）
# ---------------------------------------------------------------------------
def incidence(g: MetaphorHGNN):
    """返回 (H, Dv, De)：H 为 (V, E) 0/1 关联矩阵。"""
    V, E = g.num_nodes, len(g.he_members)
    H = np.zeros((V, E), float)
    for j, members in enumerate(g.he_members):
        for i in members:
            H[i, j] = 1.0
    dv = H.sum(axis=1)          # 节点度
    de = H.sum(axis=0)          # 超边基数
    return H, dv, de


def S_matrix(g: MetaphorHGNN) -> np.ndarray:
    """S = Dv^{-1} H De^{-1} H^T（与 _conv 的循环实现逐元素一致）。

    孤立节点（度 0）按 _conv 的 `counts[counts==0]=1` 处理 → 该行全 0。
    """
    H, dv, de = incidence(g)
    de_inv = np.where(de > 0, 1.0 / np.maximum(de, 1e-12), 0.0)
    dv_inv = np.where(dv > 0, 1.0 / np.maximum(dv, 1e-12), 0.0)
    return (dv_inv[:, None] * H) @ (de_inv[:, None] * H.T)


def M_matrix(g: MetaphorHGNN, leak: float = 0.0) -> np.ndarray:
    """M = 0.5(I + (1-eps)S)。"""
    S = S_matrix(g)
    return 0.5 * (np.eye(g.num_nodes) + (1.0 - leak) * S)


def components(g: MetaphorHGNN):
    """按超边成员关系求连通分量（返回 节点索引列表的列表）。"""
    parent = list(range(g.num_nodes))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for members in g.he_members:
        if not members:
            continue
        r = find(members[0])
        for m in members[1:]:
            rm = find(m)
            if rm != r:
                parent[rm] = r
    groups = {}
    for i in range(g.num_nodes):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def label(g: MetaphorHGNN, idx: int) -> str:
    names = g.entities + g.frames + g.cascades
    return names[idx]


def node_names(g: MetaphorHGNN):
    """全部节点名（实体 + 框架 + 级联），索引与 node_index 一致。"""
    return g.entities + g.frames + g.cascades


def coherence_lookup(g: MetaphorHGNN, X: np.ndarray):
    """返回 coh(a, b) -> 余弦，覆盖**全部**节点（实体+框架+级联）。

    重要：必须覆盖全部节点。若只覆盖实体，涉及框架/级联节点的节点对会
    静默取到 0.0，把「分量内一致性」的统计量污染成虚高的离散度。
    """
    names = node_names(g)
    norms = np.linalg.norm(X, axis=1)
    cm = {}
    live = [i for i in range(g.num_nodes) if norms[i] > 1e-12]
    for a in range(len(live)):
        for b in range(a + 1, len(live)):
            ia, ib = live[a], live[b]
            cm[(names[ia], names[ib])] = cos(X[ia], X[ib])

    def coh(a: str, b: str) -> float:
        if a == b:
            return 1.0
        v = cm.get((a, b))
        if v is None:
            v = cm.get((b, a))
        return 0.0 if v is None else v
    return coh


def hypergraph_hops(g: MetaphorHGNN) -> np.ndarray:
    """节点间超边跳数矩阵（二分图 BFS 步数 / 2 取整后的超边条数）。"""
    from collections import deque
    V = g.num_nodes
    inc = [[] for _ in range(V)]
    for j, members in enumerate(g.he_members):
        for i in members:
            inc[i].append(j)
    D = np.full((V, V), np.inf)
    for s in range(V):
        if not inc[s]:
            continue
        D[s, s] = 0.0
        seen = set()
        q = deque([(s, 0)])
        while q:
            u, d = q.popleft()
            for j in inc[u]:
                if j in seen:
                    continue
                seen.add(j)
                for v in g.he_members[j]:
                    if D[s, v] > d + 1:
                        D[s, v] = d + 1
                        q.append((v, d + 1))
    return D


def within_component_cosine(g: MetaphorHGNN, H: np.ndarray, exclude_isolated=True):
    """同分量节点对的平均余弦（衡量「源身份是否被抹平」）。

    exclude_isolated: 跳过度为 0 的孤立节点（其 H 向量恒为 0，余弦无定义）。
    """
    _, deg, _ = incidence(g)
    cos = []
    for comp in components(g):
        comp = [i for i in comp if (not exclude_isolated) or deg[i] > 0]
        for a in range(len(comp)):
            for b in range(a + 1, len(comp)):
                va, vb = H[comp[a]], H[comp[b]]
                na, nb = np.linalg.norm(va), np.linalg.norm(vb)
                if na < 1e-9 or nb < 1e-9:
                    continue
                cos.append(float(np.dot(va, vb) / (na * nb)))
    return (float(np.mean(cos)) if cos else float("nan")), len(cos)


def spectral_report(g: MetaphorHGNN, leak: float = 0.0) -> dict:
    S = S_matrix(g)
    M = M_matrix(g, leak)
    evS = np.linalg.eigvals(S)
    evM = np.linalg.eigvals(M)
    rs_S = S.sum(axis=1)
    rs_M = M.sum(axis=1)
    _, dv, _ = incidence(g)
    live = dv > 0
    return {
        "num_nodes": g.num_nodes,
        "num_hyperedges": len(g.he_members),
        "isolated_nodes": int((~live).sum()),
        "S_rowsum_min": float(rs_S.min()),
        "S_rowsum_max": float(rs_S.max()),
        "S_rowsum_max_live": float(rs_S[live].max()) if live.any() else float("nan"),
        "S_rowsum_min_live": float(rs_S[live].min()) if live.any() else float("nan"),
        "S_rowsum_exact_one_live": bool(np.allclose(rs_S[live], 1.0, atol=1e-12)) if live.any() else None,
        "S_rho": float(np.max(np.abs(evS))),
        "M_rowsum_max_live": float(rs_M[live].max()) if live.any() else float("nan"),
        "M_rowsum_min_live": float(rs_M[live].min()) if live.any() else float("nan"),
        "M_rho": float(np.max(np.abs(evM))),
        "M_sym": bool(np.allclose(M, M.T, atol=1e-12)),
        "num_components": len(components(g)),
    }


def cos(a, b) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def write_csv(path: str, rows, header=None):
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        for r in rows:
            w.writerow(r)


def write_json(path: str, obj):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
