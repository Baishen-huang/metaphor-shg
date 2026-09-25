"""隐喻超超图 / 元图（MetaphorSHG / MetaphorMG）知识表示与检索增强生成框架。

方案 A：MetaphorSHG  —— 四层隐喻超超图（触发词层-映射层-框架层-级联层）
方案 B：MetaphorMG    —— 三层隐喻元图 + U 型检索

核心模块：
  models     四层数据模型
  ontology   中文 cascade 本体 + 类型安全约束
  extractor  L1 隐喻抽取（MIPVU-lite + 双阶段过滤 + 类型约束）
  extended   L1.5 跨 chunk 扩展隐喻链接
  builder    L1→L2→L3 构建器（cascade 查表）
  metagraph  方案 B 元图 + U-Retrieval
  retrieval  跨域检索 / 多线索汇聚 / 隐喻版 HyperRetriever / RRF 融合
  hgnn       超图版 KEG 跨层消息传递
  hlindex    HL-index 超图可达性索引
  storage    Neo4j schema 导出 + JSON 导出
  llm_backend 可插拔 LLM 后端（OpenAIBackend / LocalHeuristicBackend / MockBackend）
"""

from .models import (
    ChunkSpan, Evidence, MetaphorHyperedge, MetaphorFrame, MetaphorCascade,
    MetaphorSHG, RetrieverResult, resolve_conflict, merge_evidence,
    EXTRACTOR_VERSION,
)
from .ontology import CascadeOntology, DEFAULT_ONTOLOGY, TYPE_CONSTRAINTS
from .extractor import MetaphorExtractor
from .llm_backend import (
    MetaphorLLMBackend, LLMCandidate, LLMRefine,
    OpenAIBackend, LocalHeuristicBackend, MockBackend,
)
from .extended import link_extended_metaphors
from .builder import MetaphorSHGBuilder
from .metagraph import MetaphorMetagraph, MetaphorURetrieval
from .retrieval import RetrievalEngine, shg_density
from .hgnn import MetaphorHGNN
from .hlindex import HLIndex
from . import storage
# ---- 本轮补齐：存储幂等 / 上下文预算 / 可训练排序器 / 健康度 / 基线 ----
from .context_budget import (AdaptiveThreshold, ContextBudget, ContextPack,
                             ThresholdDecision, graph_density,
                             DENSITY_LOW, DENSITY_HIGH)
from .training import (MetaphorScorer, TrainingSet, build_training_set,
                       extract_features, extract_text_features, train_from_shg,
                       trivial_separators, feature_auc, leakage_report,
                       FEATURE_NAMES)
from .health import graph_health, GraphHealth
# ---- 溯源可靠性通道（degraded-provenance，见 provenance.py）----
from . import provenance
from .provenance import (frame_reliability, frame_provenance, edge_reliability,
                         reliability_factor, RELIABILITY_FALLBACK_CAP,
                         RELIABILITY_ONTOLOGY, RELIABILITY_FLOOR)
from . import baselines
# ---- 查询侧可观测性泛函 Ω（只读查询，不读候选）----
from .observability import (QueryObservability, ObservabilityMeter, measure,
                            matched_triggers, activated_structure,
                            normalized_entropy, geometric_mean, regime_of,
                            EPS, SINGLE_FLOW_ENTROPY, SPARSE_MAX)
# ---- gen3 查询侧结构信号（只读查询；原始计数 + 可组合标量）----
from .query_signal import (QuerySignal, measure_signal, reachable_structure,
                           compose, StratifiedNormalizer, gate_by,
                           SIGNAL_NAMES, SIG_N_SEED, SIG_N_FRAMES,
                           SIG_N_CASCADES, SIG_N_EMERGENT, SIG_N_NEW_DOMAINS,
                           SIG_N_REACH, SIG_S_LOG, SIG_S_STRUCT, SIG_OMEGA,
                           SIG_S_QUERY)

__all__ = [
    "ChunkSpan", "Evidence", "MetaphorHyperedge", "MetaphorFrame", "MetaphorCascade",
    "MetaphorSHG", "RetrieverResult", "resolve_conflict", "merge_evidence",
    "EXTRACTOR_VERSION",
    "CascadeOntology", "DEFAULT_ONTOLOGY", "TYPE_CONSTRAINTS",
    "MetaphorExtractor", "link_extended_metaphors", "MetaphorSHGBuilder",
    "MetaphorMetagraph", "MetaphorURetrieval", "RetrievalEngine", "shg_density",
    "MetaphorHGNN", "HLIndex", "storage",
    # LLM 后端（§6.6）
    "MetaphorLLMBackend", "LLMCandidate", "LLMRefine",
    "OpenAIBackend", "LocalHeuristicBackend", "MockBackend",
    # 上下文预算与自适应阈值（移植 HyperRAG）
    "AdaptiveThreshold", "ContextBudget", "ContextPack", "ThresholdDecision",
    "graph_density", "DENSITY_LOW", "DENSITY_HIGH",
    # 可训练排序器 + 健康度 + 基线
    "MetaphorScorer", "TrainingSet", "build_training_set", "extract_features",
    "extract_text_features", "train_from_shg", "trivial_separators",
    "feature_auc", "leakage_report", "FEATURE_NAMES",
    "graph_health", "GraphHealth", "baselines",
    # 查询侧可观测性 Ω（只声称「能测 / 能门控」，不声称提升下游指标）
    "QueryObservability", "ObservabilityMeter", "measure",
    "matched_triggers", "activated_structure", "normalized_entropy",
    "geometric_mean", "regime_of", "EPS", "SINGLE_FLOW_ENTROPY", "SPARSE_MAX",
    # 溯源可靠性通道（degraded-provenance）
    "provenance", "frame_reliability", "frame_provenance", "edge_reliability",
    "reliability_factor", "RELIABILITY_FALLBACK_CAP", "RELIABILITY_ONTOLOGY",
    "RELIABILITY_FLOOR",
    # gen3 查询侧结构信号（原始计数 + 可组合标量；同样只读查询）
    "QuerySignal", "measure_signal", "reachable_structure", "compose",
    "StratifiedNormalizer", "gate_by", "SIGNAL_NAMES",
    "SIG_N_SEED", "SIG_N_FRAMES", "SIG_N_CASCADES", "SIG_N_EMERGENT",
    "SIG_N_NEW_DOMAINS", "SIG_N_REACH", "SIG_S_LOG", "SIG_S_STRUCT",
    "SIG_OMEGA", "SIG_S_QUERY",
]
