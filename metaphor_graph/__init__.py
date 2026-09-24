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
from . import baselines

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
]
