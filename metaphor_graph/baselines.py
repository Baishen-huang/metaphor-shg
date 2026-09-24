"""基线注册表与评测矩阵（方案 §6.2 / §6.3 的可执行版本）。

为什么要单独补这个文件
----------------------
原方案的基线表（§6.2）缺三个关键对照，导致三件事无法回答：

  - 缺 **OG-RAG**：它是五个图 RAG 基线里唯一带**领域本体**的。
    不打它，审稿人无法区分「增益来自层级结构」还是「增益来自本体」。
  - 缺 **RAPTOR**：树结构摘要。**不打它，无法区分「增益来自层级」还是
    「增益来自图」**——RAPTOR 有层级但不是图。
  - 缺 **HyperGraphRAG**（NeurIPS 2025）：原表只列了 HyperRAG（WWW 2026，
    检索层）。但**表示层**的直接对标物是 HyperGraphRAG——它才是「用超边
    表达 n 元事实」这件事的首创工作。

另外补一条评测协议：**Binary Source / N-ary Source 分域报告**。
这是 HyperGraphRAG 最有力的论证方式——在 n 元问题上增益大、二元问题上
增益小，才能证明增益来自超边而不是来自「图」本身。

基线数据口径
-----------
HyperGraphRAG：五域（医学/农业/CS/法律/混合），F1 +7.45 over StandardRAG，
                +5.9 over GraphRAG；GPT-4o-mini + text-embedding-3-small；
                构图 $0.0063/1k tokens。
HyperRAG：WikiTopics 11 域 269,290 条 QA + HotpotQA/MuSiQue/2Wiki 各 1000；
          MRR +2.95%、Hits@10 +1.23%；2Wiki F1 +11.89%。
Hyper-RAG（Nature Communications）：9 数据集 / 6 LLM；关键知识缺失 -60.7%、
          幻觉 -48.5%。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Baseline:
    bid: str
    name: str
    structure: str           # chunk / tree / KG(binary) / hypergraph(n-ary) / metagraph
    unit: str                # 检索单元
    strategy: str
    ontology: bool = False   # 是否依赖领域本体
    ours: bool = False
    citation: str = ""
    isolates: str = ""       # 打这个基线是为了分离出什么贡献
    reported: str = ""       # 文献报告的数字（便于论文对标）


BASELINES: List[Baseline] = [
    Baseline("B1", "BM25 + 向量（RRF）", "chunk", "chunk",
             "关键词 + 稠密检索融合", False, False,
             "标准 RAG 基线",
             "分离「图/超图结构」本身的贡献", "—"),
    Baseline("B2", "GraphRAG", "KG(binary)", "实体-实体边",
             "社区摘要 + 图遍历", False, False,
             "Edge et al. 2024",
             "分离「二元 → n 元」的表示增益", "+5.9 F1（HyperGraphRAG 相对它）"),
    Baseline("B3", "HyperGraphRAG", "hypergraph(n-ary)", "超边（n 元事实）",
             "实体+超边双路向量检索 + 双向扩展", False, False,
             "Luo et al., NeurIPS 2025",
             "**表示层直接对标物**：分离「通用 n 元」与「隐喻跨域映射」",
             "F1 +7.45 over StandardRAG；Correctness 64.8"),
    Baseline("B4", "HyperRAG", "hypergraph(n-ary)", "伪三元组 (e_h, f^n, e_t)",
             "可训练 HyperRetriever / HyperMemory 束搜索", False, False,
             "Lien et al., WWW 2026",
             "**检索层直接对标物**：验证跨域场景下其「实体可匹配」前提失效",
             "MRR +2.95%、Hits@10 +1.23%；2Wiki F1 +11.89%"),
    Baseline("B5", "RAPTOR", "tree", "树节点（摘要）",
             "层次聚类 + 摘要树检索", False, False,
             "Sarthi et al. 2024",
             "分离「层级」与「图」——有层级但不是图", "—"),
    Baseline("B6", "OG-RAG", "object graph (mostly binary)", "对象-对象边",
             "以对象为中心的图游走", True, False,
             "Sharma et al. 2024",
             "分离「本体」与「层级」——**唯一带本体的基线，最关键**", "—"),
    Baseline("B7", "MetaphorBoost-style KG", "KG(binary)", "源域→目标域映射对",
             "隐喻映射图 + 多线索汇聚", False, False,
             "一阶隐喻图，无层级",
             "分离「隐喻语义」与「层级结构」", "—"),
    Baseline("B8", "MetaphorMG（方案 B）", "metagraph", "chunk/doc/主题 子图",
             "U 型检索：自顶向下粗筛 + 自底向上精炼", True, True,
             "本方案",
             "本方案元图路线（低成本路线）", "—"),
    Baseline("B9", "MetaphorSHG（方案 A）", "hyper-supergraph",
             "L1 超边 / L2 超顶点 / L3 超超顶点",
             "跨域通路 + 多线索汇聚 + 类型安全约束", True, True,
             "本方案",
             "本方案超超图路线（完整路线）", "—"),
]

BY_ID: Dict[str, Baseline] = {b.bid: b for b in BASELINES}


# --------------------------------------------------------------------- 消融
@dataclass
class Ablation:
    aid: str
    change: str
    hypothesis: str
    expected: str
    rq: str


ABLATIONS: List[Ablation] = [
    Ablation("A1", "去掉类型安全约束", "H1", "字面误判率回升至 >30%", "RQ1"),
    Ablation("A2", "L2/L3 改回 LLM 聚类", "H2", "成本升 10×，质量持平或下降", "RQ2"),
    Ablation("A3", "去掉隐喻通路，仅留字面通路", "H3", "跨域 Recall 降至 B1 水平", "RQ3"),
    Ablation("A4", "HGNN 改回普通 GRU（KEG 原版）", "H4", "F1 下降 >3pp", "RQ4"),
    Ablation("A5", "去掉跨 chunk 超边", "—", "扩展隐喻消歧准确率下降", "RQ1"),
    Ablation("A6", "换成 ConceptNet（通用常识图）", "—", "性能下降", "RQ1"),
    # ---- 本轮新增：对齐 HyperRAG 的可训练检索器 ----
    Ablation("A7", "排序器改为人工加权（关闭训练）", "H5",
             "MRR/Hits@10 下降，验证训练信号确有增益", "RQ3"),
    Ablation("A8", "关闭自适应阈值，改用固定 top_k", "H6",
             "稀疏图上 Recall 显著下降、稠密图上噪声上升", "RQ3"),
    Ablation("A9", "去掉角色感知结构特征（same_frame/same_cascade/ground_jaccard）",
             "H7", "排序质量下降，验证角色信息不可被同质 DDE 替代", "RQ1"),
]


# ----------------------------------------------------------------- 评测矩阵
@dataclass
class EvalSuite:
    name: str
    description: str
    metric: str
    expectation: str
    domain: str = "n-ary"   # n-ary / binary（用于分域报告）


EVAL_SUITES: List[EvalSuite] = [
    EvalSuite("跨域检索", "问「项目为什么推不动」，文档写「陷在泥潭」",
              "跨域 Recall@k", "隐喻通路命中；B3/B4 应接近 0（其实体匹配前提失效）",
              "n-ary"),
    EvalSuite("扩展隐喻", "「发条」指代什么，答案在 3 个 chunk 前",
              "跨 chunk 消歧准确率", ">70%", "n-ary"),
    EvalSuite("框架一致性", "通篇用战争框架的文档",
              "框架一致性评分（人工 7 分制）", "方案 A/B 显著高于基线", "n-ary"),
    EvalSuite("字面抗干扰", "「苹果发布了新手机」",
              "字面误判率 P1", "<15%（硬门槛）", "binary"),
    # ---- 新增中性对照：证明增益来自超边而非「图」----
    EvalSuite("字面事实检索（中性对照）",
              "纯二元可解的事实型问题，不含隐喻",
              "MRR / Hits@10",
              "我们的增益应**不显著**——若显著优于 B2，说明增益来自本体而非层级",
              "binary"),
    EvalSuite("N-ary 通用事实（跨域迁移对照）",
              "非隐喻的 n 元事实（如多因素疾病机制）",
              "F1",
              "应接近 B3；若显著更差，说明隐喻专属设计有代价，需在论文中说明",
              "n-ary"),
]


def render_plan() -> str:
    """打印完整实验设计（基线 × 消融 × 评测矩阵），便于直接贴进论文方法章。"""
    out: List[str] = []
    out.append("=" * 78)
    out.append("基线（含本轮补齐的 B3 / B5 / B6）")
    out.append("=" * 78)
    out.append(f"{'ID':<4}{'名称':<22}{'结构':<26}{'本体':<6}{'分离出什么贡献'}")
    out.append("-" * 78)
    for b in BASELINES:
        tag = " ours" if b.ours else ""
        out.append(f"{b.bid:<4}{b.name:<22}{b.structure:<26}"
                   f"{'✓' if b.ontology else '':<6}{b.isolates}{tag}")
    out.append("")
    out.append("=" * 78)
    out.append("评测矩阵（按 Binary / N-ary 分域报告）")
    out.append("=" * 78)
    for d in ("n-ary", "binary"):
        out.append(f"[ {d} ]")
        for s in EVAL_SUITES:
            if s.domain != d:
                continue
            out.append(f"  - {s.name}：{s.description}")
            out.append(f"    指标 {s.metric} ｜ 预期 {s.expectation}")
    out.append("")
    out.append("=" * 78)
    out.append("消融（新增 A7 / A8 / A9，对齐 HyperRAG 的可训练检索器）")
    out.append("=" * 78)
    for a in ABLATIONS:
        out.append(f"  {a.aid} [{a.rq}/{a.hypothesis}] {a.change} → 预期 {a.expected}")
    return "\n".join(out)


if __name__ == "__main__":
    print(render_plan())
