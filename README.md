# MetaphorSHG：隐喻超超图的知识表示与检索增强生成

> 把认知语言学已发现的隐喻层级结构（基础隐喻 → 一般隐喻 → 隐喻级联）翻译为
> **超超图**（hyper-hypergraph）的数学结构，并测量这种翻译能否转化为可度量的
> 检索增强生成收益。

**MetaphorSHG** 用四层结构表示隐喻的高阶性与层级性：

```
L0  触发词层    语言形式（"泥潭""发条"）
L1  映射层      隐喻超边 (源域, 目标域, 喻底集合, 触发词, 情感, 语境跨度)
L2  框架层      一般隐喻 = 超顶点（L1 超边的集合，如 OBSTACLE_IS_TERRAIN）
L3  级联层      隐喻级联 = 超超顶点（L2 框架的集合，围绕同一目标概念组织）
```

关键设计：**L1 超边承载 n 元喻底集合**（喻底是集合而非单值，这正是超边的定义特征），
**L2/L3 的分组判据是级联归属**（认知语言学的自然结构），而非工程聚类。

---

## 主要结果

| 维度 | 结果 |
|---|---|
| 抽取（LLM 开放发现 + 双防线） | 隐喻句召回 **9.7% → 69.6%**，字面误判率 **9.2%**（硬门槛 15%） |
| 构建（级联本体查表） | L2/L3 覆盖率 **100%（报出口径）/ 82.4%（诚实口径）**；成本比 LLM 聚类低一个数量级（~20 vs ~187 次/千边） |
| 双语资源 | **2,177 框架**，英文概念域对齐率 **100%** |
| **检索（修复后基准，去锚定）** | **去锚定 MRR 0.2330 = 随机基线（0.0069）的 34 倍**；anchored 0.8956 |
| ~~检索（原口径）~~ | ~~语义超图通路召回 1.000~~ —— **平凡饱和**（池 ≤10 时恒为 1.0），见下 |
| 知识源消融（A6） | 专属隐喻级联 **0.783** vs 通用常识关联 **0.095**（跨域映射不可被常识替代） |
| 连贯文档扩展链 | 密度为独立短句语料的 **10×**；双段管线精度 **16.7% → 63.6%** |
| 复现护栏 | **224 项单元测试**；全部 LLM 调用落盘缓存，可零 API 费用重放 |

> **⚠️ 评测口径修正（2026-09-25）**：原检索基准有两处方法论缺陷，已修复并量化：
> ① **构造锚定**——"非构造金标"标签不成立（632/632 的金标都含产出该问题的 chunk，
> 97.9% 只含它）；② **候选池过小**（median 7–8）使 Hits@10 平凡饱和、随机排序
> MRR 期望即达 0.37。修复后（全局池 1,100 + 去锚定口径）测出：**锚定抬高 ≈ +0.66 MRR，
> 但去锚定下 MRR 仍是随机的 34 倍** —— 架构具备真实跨域检索能力。
> 两处缺陷在 IR 文献中分别对应 **pooling bias** 与 **test collection 规模不足**。
> 详见 [论文初稿.md](论文初稿.md) §4.1/§6.7 与
> [experiments/实验结论汇总.md](experiments/实验结论汇总.md)。

**同样重要的边界**（本项目如实报告 12 项负面结果）：层级传播的检索收益以语义表示
质量为前提（哈希向量 −0.104 → 真实句向量 +0.062）；训练排序器的增益以查询分布为
条件；类型安全约束承担的是**结构正确性**而非精度；LLM-as-judge 的结论随 judge 模型
反转。详见 [论文初稿.md](论文初稿.md) §7。

---

## 快速开始

```bash
pip install -r requirements.txt

# 全部单测（224 项，离线，无需 API）
python -m unittest metaphor_graph.test_metaphor_graph

# 抽取评测（离线规则侧）
python -m metaphor_graph.evaluate_real --use-metanet --use-bootstrap --use-semfield

# 接入 LLM 开放发现（需 LLM_API_KEY，结果落盘缓存）
python -m metaphor_graph.evaluate_real --use-llm --llm-conf 0.85 --llm-cache data/llm_cache_deepseek.json

# 检索评测（离线，哈希向量）
python -m metaphor_graph.evaluate_fullcorpus
python -m metaphor_graph.evaluate_llmgold --stage eval
```

**离线可复现**：所有需要真实 LLM 的阶段（discover / refine / 改写 / 判定 / 校验 /
关联 / 生成）均已落盘缓存，重放零请求；缓存键为确定性 id（md5），跨进程可复现，
并有单测护栏。

完整复现命令表见 [论文初稿.md](论文初稿.md) 附录 A。

---

## 仓库结构

```
metaphor_graph/           核心实现
  models.py               L1 超边 / L2 框架 / L3 级联 数据结构
  extractor.py            三通道抽取 + 双防线（类型约束 / refine 校验）
  mipvu.py                MIPVU-lite 候选通道
  semfield.py             USAS 风格中文语义域失谐通道
  ontology.py             级联本体与类型安全约束
  ontology_bilingual.py   双语本体（2,177 框架英文对齐）
  builder.py              四层构建 + 孤儿框架级联补全
  extended.py             L1.5 跨 chunk 扩展隐喻链接
  hgnn.py                 跨层超图消息传递 + metaphor_coherence 校验信号
  retrieval.py            跨域检索 / 多线索汇聚 / 三通路 / RRF 融合
  training.py             7 维特征与可训练排序器
  context_budget.py       上下文预算与自适应阈值
  evaluate_*.py           各实验评测入口
  test_metaphor_graph.py  224 项单元测试
release/                  可发布资源
  metaphor_resources/     中文级联本体（2,177 框架，双语对齐）
  MetaphorRAG-Bench/      四类任务检索基准
论文初稿.md                中文论文稿（v0.2）
论文初稿_en.md             英文论文稿
知识隐喻分析任务方案.md      研究方案（完整版）
效果对比.md                对比底稿
```

---

## 数据与许可

**本仓库不包含语料数据。** `data/` 被 `.gitignore` 排除，原因与获取方式见
[DATA.md](DATA.md)。代码与本体资源的许可边界同样在 [DATA.md](DATA.md) 中说明。

---

## 引用

```bibtex
@misc{metaphorshg2026,
  title  = {MetaphorSHG: Hyper-Hypergraph Representation for Metaphor-Aware Retrieval-Augmented Generation},
  author = {Baishen-huang},
  year   = {2026},
  note   = {Preprint. Code and Chinese cascade ontology released.}
}
```

---

## English Summary

**MetaphorSHG** represents metaphor as a **hyper-hypergraph** rather than binary
triples: L1 hyperedges carry the n-ary *ground* set (the defining feature of a
hyperedge), while L2 frames and L3 cascades are typed subsets corresponding to
linguistically motivated *metaphor cascades* — not engineered clusters.

On Chinese metaphor benchmarks: extraction recall **9.7% → 69.6%** at **9.2%**
literal-misclassification (gate: 15%); L2/L3 coverage **100%** with an
order-of-magnitude lower construction cost; on trigger-severed paraphrased
queries (n=632) the semantic hypergraph path recalls **1.000** versus **0.042**
(cascade) and **0.000** (literal). Replacing the dedicated cascade with generic
commonsense associations drops recall to **0.095** — cross-domain mappings are
not substitutable by commonsense. We report 12 negative/conditionalized results,
including that hierarchical propagation only pays off given adequate semantic
representations, and that LLM-as-judge conclusions flip with the judge model.

All LLM stages are cached for zero-cost replay; **116 unit tests** guard
reproducibility.
