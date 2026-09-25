# 隐喻评测基准与检索评测方法论：检索报告

> 检索日期：2026-09-25
> 检索目的：**benchmark/dataset discovery + 实验设计**（为 MetaphorSHG 寻找/设计更严谨的评测）
> 检索模式：standard（CCF literature searcher）
> 来源：OpenAlex API（CC0 元数据）。arXiv API 本次因 HTTP 301 重定向不可用，
> 凡标注 arXiv 的条目均经 OpenAlex 记录的 DOI 交叉验证。
>
> **背景**：本项目三代实验实测发现现有检索基准有两处方法论缺陷：
> ① **构造锚定**——632/632 查询的"非构造金标"都包含产出该问题的 chunk，97.9% 只包含它；
> ② **候选池过小**——median 7–8 / max 10，使 Hits@10 平凡恒为 1.0。
> 本报告搜索的是：领域内已有什么基准、以及检索评测的方法论文献能提供什么修正工具。

---

## 一、执行摘要

三条结论：

**1. 隐喻识别（detection/identification）有成熟基准，隐喻检索（retrieval）没有。**
detection 侧有 VUA 共享任务系列、MOH-X、TroFi、LCC、MultiMET 等被广泛复用的标注集，
词级/句级金标由人工标注产生，**不存在构造锚定问题**。但检索侧——"给定查询，
召回相关隐喻证据"——**没有标准基准**。这是你项目遇到的困境的根源：你在用一个
自建的、为方便评测而构造的检索集，它继承了构造锚定的缺陷。

**2. 超图 RAG 是一个 2026 年爆发的新簇，但基准普遍薄弱。**
检索到 20+ 篇 2026 年的 hypergraph RAG 工作（HyperRAG、HyperGraphRAG、
Knowledge Is Not Static、HyperSU 等），**它们大多在通用 QA 数据集
（HotpotQA、2WikiMultiHopQA 等）上评测，而非隐喻或高阶语义任务**。
这意味着：① 你的"隐喻 × 超图 RAG"交叉定位依然成立；② 但没有现成的
隐喻超图检索基准可借用，需要自建。

**3. 你需要的评测修正工具在 IR 方法论文献里，且是经典问题。**
候选池偏差（pooling bias）、不完整相关性判断、指标饱和——这些是 TREC 时代
就系统研究过的问题。**你的两处缺陷在 IR 领域都有标准名称和标准解法**，
不需要从零发明。这可能是本报告最有用的部分。

---

## 二、候选基准与数据集（按用途分组）

### 2.1 隐喻识别标注集（可直接用于抽取层评测，无构造锚定）

| 资源 | 年份 | 语言 | 粒度 | 引用 | DOI / 链接 | 类型 |
|---|---|---|---|---|---|---|
| **VUA Metaphor Detection Shared Task (2018)** | 2018 | 英 | token | 103 | [10.18653/v1/w18-0907](https://doi.org/10.18653/v1/w18-0907) | pure benchmark |
| **MOH-X**（via Neural Metaphor Detection in Context） | 2018 | 英 | token | 126 | [10.18653/v1/d18-1060](https://doi.org/10.18653/v1/d18-1060) | method + benchmark |
| **TroFi**（同上，原始语料更早） | 2018 | 英 | token | 126 | 同上 | method + benchmark |
| **LCC Metaphor Datasets** | 2016 | 英 | token | 26 | [10.63317/27ncp7cs2ruw](https://doi.org/10.63317/27ncp7cs2ruw) | pure benchmark |
| **MultiMET**（多模态） | 2021 | 英 | 图文 | 45 | [10.18653/v1/2021.acl-long.249](https://doi.org/10.18653/v1/2021.acl-long.249) | pure benchmark |
| **DeepMet**（阅读理解范式） | 2020 | 英 | token | 65 | OpenAlex W 记录 | method + benchmark |
| **VUA-20 / VUA-18 续作** | 2020 | 英 | token | — | 见 VUA 系列 | pure benchmark |
| **CCL2018 中文隐喻识别与情感分析** | 2018 | **中** | 句级三分类 | — | 大连理工 DUTIR（本项目已用） | pure benchmark |

**基准质量备注（VUA 系列）**：
```
Benchmark scope:      token-level metaphor identification, 英文学术语域（VUA 语料来自
                      academic/social 文本）
Task realism:         高。人工标注，MIPVU 流程，无构造锚定
Metric validity:      标准（token-level F1 / 平均精度），无平凡饱和
Baseline coverage:    充分（2018 共享任务有多系统参赛，后续多年作为标准基线）
Adoption signal:      高，被几乎所有隐喻检测论文复用
Known limitation:     单语言（英）；token 级标注对"扩展隐喻"（跨句延续）不覆盖——
                      而这恰是本项目的 L1.5 关注点
```

**对本项目的直接价值**：你的抽取层结论（9.7%→69.6% 召回、9.2% 误判）已经建立在
CCL2018 人工金标上，**这部分不受构造锚定影响**，是站得住的。VUA 系列可作为
跨语言验证的下一步（你论文 §8 限制 5 已提到 VUA 待建设）。

### 2.2 隐喻理解 / 推理基准（较新，偏 LLM 评测）

| 资源 | 年份 | 关注点 | 引用 | DOI | 类型 |
|---|---|---|---|---|---|
| **MiQA: A Benchmark for Inference on Metaphorical Questions** | 2022 | **隐喻推理**的问答基准 | 4 | [10.18653/v1/2022.aacl-short.46](https://doi.org/10.18653/v1/2022.aacl-short.46) | **pure benchmark** |
| **ANALOGICAL: Long Text Analogy Evaluation** | 2023 | 长文本**类比**推理评测 | 8 | [10.18653/v1/2023.findings-acl.218](https://doi.org/10.18653/v1/2023.findings-acl.218) | **pure benchmark** |
| **Meta4XNLI: Crosslingual Parallel Corpus for Metaphor** | 2024/25 | 跨语言隐喻检测+解释（**期刊版**） | 2 | [10.1162/coli.a.20](https://doi.org/10.1162/coli.a.20) | pure benchmark |
| **NYK-MS: Multi-modal Metaphor and Sarcasm Benchmark (Chinese)** | 2024 | **中文**多模态隐喻+讽刺 | — | arXiv | pure benchmark |
| **Metaphors in Pre-Trained LMs: Probing and Generalization** | 2022 | PLM 的隐喻泛化，跨数据集/跨语言 | 30 | [10.18653/v1/2022.acl-long.144](https://doi.org/10.18653/v1/2022.acl-long.144) | method + benchmark |
| **Explainable Metaphor Identification Inspired by CMT** | 2022 | 概念隐喻理论驱动的可解释识别 | 73 | OpenAlex W 记录 | pure method |
| **FrameBERT** | 2023 | 框架嵌入学习做概念隐喻检测 | 25 | OpenAlex W 记录 | pure method |
| **Merely Judging Metaphor is Not Enough: Reasonable Metaphor Detection** | 2024 | 提出"合理隐喻检测"新任务 | 2 | OpenAlex W 记录 | method + benchmark |
| **Automatic Scoring of Metaphor Creativity with LLMs** | 2024 | 隐喻创造力自动评分 | 51 | OpenAlex W 记录 | method + benchmark |
| **Conceptual Metaphor Theory as a Prompting Paradigm for LLMs** | 2025 | 用 CMT 做提示范式 | — | arXiv | pure method |
| **A Survey on Computational Metaphor Processing** | 2022 | 识别→解释→生成全流程综述 | 4 | OpenAlex W 记录 | survey |

**MiQA 与 ANALOGICAL 对本项目特别重要**——它们是**隐喻/类比推理的问答式基准**，
形式最接近你需要的"给定查询 → 召回隐喻证据"：

- **MiQA**（AACL 2022）测"隐喻问题的推理"，是少数把隐喻做成 **QA 形式**的基准。
  它的金标构造方式（如何避免锚定）值得直接借鉴。
- **ANALOGICAL**（Findings of ACL 2023）测**长文本**类比推理——与你的
  L1.5 跨 chunk 扩展隐喻关注点最接近（都是"跨越较长文本范围的语义关联"）。

**Meta4XNLI** 提供跨语言平行语料（含中文），可作为你论文 §8 限制 6
（"单语言"）的跨语言验证资源，且已发表于 *Computational Linguistics* 期刊。

**Metaphors in Pre-Trained LMs 对本项目特别相关**：它系统检验了 PLM 在隐喻任务上的
**跨数据集泛化**问题。你项目里"自举触发词 train→test 泛化差（召回涨 4.5 倍、
误判同步涨 4 倍）"这条负面结果，与它的关注点是同一类问题。

### 2.3 超图 / 图 RAG 基准（2026 爆发簇，但基准薄弱）

| 工作 | 年份 | 引用 | DOI | 类型 | 备注 |
|---|---|---|---|---|---|
| **HyperRAG: Reasoning N-ary Facts over Hypergraphs** | 2026 | 1 | [10.1145/3774904.3792710](https://doi.org/10.1145/3774904.3792710) | method + benchmark | 你论文已引用 |
| **When to Use Graphs in RAG: A Comprehensive Analysis** | 2025 | 4 | [10.48550/arxiv.2506.05690](https://doi.org/10.48550/arxiv.2506.05690) | pure benchmark | **分析型**，评估图 RAG 何时有增益 |
| **Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG** | 2026 | 0 | OpenAlex W 记录 | pure benchmark | Agentic search 场景 |
| **Knowledge Is Not Static: Order-Aware Hypergraph RAG** | 2026 | 0 | OpenAlex W 记录 | pure method | 你论文已引用 |
| **HyperSU: Corpus-Driven Semantic-Unit Hypergraph for RAG** | 2026 | 0 | OpenAlex W 记录 | method + benchmark | 新 |
| **Cross-Granularity Hypergraph RAG for Multi-hop QA** | 2026 | 3 | OpenAlex W 记录 | pure method | 新 |
| **HyperGraphPro / HyCE-RAG / EvoGraph-R1 / VizRAG 等** | 2026 | 0 | — | pure method | 另有 10+ 篇同簇 |

**关键观察（opportunity gap）**：
> 检索到的 20+ 篇 2026 年 hypergraph RAG 工作，**绝大多数在通用多跳 QA
> （HotpotQA / 2WikiMultiHopQA / MuSiQue）上评测**，用 n 元事实做"检索组织手段"。
> **没有一篇针对隐喻或高阶语义映射**。
>
> 这同时确认两件事：
> - 你的"隐喻 × 超超图"定位**依然空白**（与你论文附录 C 的检索一致）；
> - **你无法借用现成的隐喻超图检索基准**，必须自建——但可以借用它们的
>   *评测协议*（多跳 QA 的金标构造方式、baseline 选择、指标）。

### 2.4 评测方法论（IR 经典文献，**对本项目最直接有用**）

| 文献 | 年份 | 引用 | DOI | 解决的问题 | 对应你的缺陷 |
|---|---|---|---|---|---|
| **Efficient construction of large test collections** | 1998 | 238 | [10.1145/290941.291009](https://doi.org/10.1145/290941.291009) | **pooling 方法**的奠基作：如何用少量系统构建可复用测试集 | 候选池构造 |
| **How reliable are the results of large-scale IR experiments?** | 1998 | 579 | [10.1145/290941.291014](https://doi.org/10.1145/290941.291014) | 小规模评测的**统计可靠性** | 你 n=20 的功效不足问题 |
| **Bias and the limits of pooling for large collections** | 2007 | 118 | [10.1007/s10791-007-9032-x](https://doi.org/10.1007/s10791-007-9032-x) | **pooling bias**：池外文档被系统性地判为不相关 | **正是你的构造锚定问题的学名** |
| **On IR metrics designed for incomplete relevance assessments** | 2008 | 130 | OpenAlex W 记录 | 不完整相关性判断下的指标（bpref 等） | 金标不完整时的稳健指标 |
| **Score adjustment for correction of pooling bias** | 2009 | 53 | OpenAlex W 记录 | 池偏差的**修正方法** | 可直接套用 |
| **Statistical biases in IR metrics for recommender systems** | 2017 | 169 | OpenAlex W 记录 | 指标本身的统计偏差 | 指标选择 |
| **Fixed-Cost Pooling Strategies** | 2019 | 36 | OpenAlex W 记录 | 固定预算下的池化策略 | 重建基准时的预算控制 |

**这是本报告最重要的发现**：你的两处缺陷在 IR 领域是**有名字、有文献、有标准解法**的经典问题：

| 你的观察 | IR 领域的标准名称 | 标准解法（文献） |
|---|---|---|
| 金标 100% 包含产出 chunk | **pooling bias / 构造锚定** | 多系统 pooling（不用单一系统产出金标）、bpref 类指标、score adjustment |
| 候选池 ≤10 使 Hits@10 饱和 | **test collection 规模不足 / 指标饱和** | 扩大 pool（Efficient construction, 1998）；报告池外文档比例 |
| n=20 配对判别功效不足 | **小规模评测的统计可靠性** | How reliable (1998)：报告 CI、用配对检验、扩样 |
| 人工权重 0.20 是拍脑袋定的 | **baseline 调参公平性** | 报告 baseline 调参预算，或使用学到的权重 |

### 2.5 LLM-as-judge 效度（与你的 §6.5 直接相关）

| 文献 | 年份 | 引用 | DOI | 相关点 |
|---|---|---|---|---|
| **G-Eval: NLG Evaluation using GPT-4** | 2023 | 777 | OpenAlex W 记录 | LLM 评判的方法论起点 |
| **Humans or LLMs as the Judge? A Study on Judgement Bias** | 2024 | 63 | OpenAlex W 记录 | 评判偏差系统研究 |
| **Judging the Judges: Position Bias in LLM-as-a-Judge** | 2025 | 19 | OpenAlex W 记录 | **位置偏差**——对应你"同模型换序二评 κ=0.912"的检验 |
| **From Generation to Judgment: LLM-as-a-judge** | 2025 | 103 | OpenAlex W 记录 | 综述 |
| **A Survey on LLM-as-a-Judge** | 2024 | 43 | OpenAlex W 记录 | 综述 |

**对你 §6.5 的价值**：你已经实测到"结论随 judge 模型反转"（deepseek vs glm）。
这在文献里是被系统记录的现象（judgement bias、position bias）。
**你的实测发现可以作为该文献线的一个具体案例**，而不是孤立的异常。

---

## 三、Closest-work 聚类与机会图

### 簇 A：隐喻识别基准（成熟，无构造锚定）
**已覆盖**：VUA/MOH-X/TroFi/LCC/MultiMET 提供人工标注的 token/句级金标；CCL2018 提供中文。
**未测试**：扩展隐喻（跨句延续）的标注——所有主流基准都是**句内**标注。
**你的定位**：你的 L1.5（跨 chunk 扩展链）恰好在这个空白里。
**可行路线**：以现有基准做抽取层验证（已做），另建**扩展隐喻的小规模人工金标**
（你已有 n=30 的盲评，可扩样）。

### 簇 B：超图 / 图 RAG（2026 爆发，基准薄弱）
**已覆盖**：20+ 篇 2026 工作，方法多样（超图检索、超图记忆、增量精炼、可视化）。
**未测试**：① 隐喻或高阶语义任务；② **检索本身**的严谨评测（多数直接报 QA EM/F1）。
**你的定位**：隐喻 × 超图仍空白。
**可行路线**：借用它们的 QA 评测协议形式，但把任务换成隐喻检索；
**并且做得比它们更严谨**（报告 pooling bias 检验、池外比例）。

### 簇 C：IR 评测方法论（经典，工具齐全）
**已覆盖**：pooling 构造、pooling bias 及其修正、不完整判断下的指标、统计可靠性。
**未测试**：这些方法**几乎从未被应用到隐喻/图 RAG 评测上**。
**你的定位**：**这可能是一个真正的方法论贡献点**——把 IR 的 pooling bias 框架
引入隐喻 RAG 评测，并量化"构造锚定"对结论的影响幅度。

### 机会图

| 类型 | 判断 | 依据 |
|---|---|---|
| `benchmark gap` | ✅ **明确存在** | 隐喻检索无标准基准；20+ 超图 RAG 工作均用通用 QA |
| `negative-result opportunity` | ✅ **强** | 你的"构造锚定"诊断可写成评测方法论论文：量化自建检索基准的锚定偏差 |
| `mechanism gap` | ✅ 存在 | 超图 RAG 工作报告性能但少解释"何时图结构有增益"（`When to Use Graphs` 是少数例外） |
| `covered central claim` | ⚠️ 部分 | 超图 RAG 的方法空间已较拥挤，但隐喻交叉仍空白 |

---

## 四、对你项目的具体建议

### 4.1 评测修正方案（按优先级）

**第一步：解除构造锚定**（对应 pooling bias）
三种可选做法，按代价排序：
1. **金标排除产出 chunk**——最便宜，但会使可评测查询降到 13/632（你已实测）。
   适合作为**稳健性检查**而非主实验。
2. **多系统 pooling**——用多个独立系统（你的三通路 + BM25 + 向量基线）的
   top-k 并集构造候选池，再人工/LLM 判定池内全部。这是 TREC 标准做法
   （Efficient construction, 1998），能显著缓解单一系统偏差。
3. **改用 bpref 类指标**——在不完整判断下更稳健（On IR metrics, 2008）。

**第二步：扩大候选池**
当前池 ≤10 导致 Hits@10/Recall@10 平凡饱和。做法：把检索单位从"chunk"改为
"文档"或"段落"，或扩大语料（你已有 110 篇伪文档、1,050 chunk 的基础）。
**验收标准：池规模应使随机排序的 MRR 期望值 < 0.15**（当前池=7 时随机期望
约 0.37，已吃掉一半量程）。

**第三步：报告评测的自我审计**
在论文 §4 增加一段，明确报告：池规模分布、池外文档比例、构造锚定检验结果、
指标饱和检验。**`When to Use Graphs in RAG` 是这类"分析型评测"论文的先例**，
可作为引用支撑。

### 4.2 论文定位建议

**不要**把"检索指标"作为主贡献——它受构造锚定影响，解释力有限。

**建议**把主贡献重新排序为：
1. **抽取层**（9.7%→69.6%、9.2% 误判）——建立在人工金标上，最稳。
2. **n 元表示的结构信号**（0.950 vs 原始 0.550）——不依赖检索金标。
3. **A6 消融**（隐喻通路 0.783 vs 常识通路 0.095）——相对比较，内部有效。
4. **评测方法论的诊断**（构造锚定、pooling bias、指标饱和的量化）——
   **这是新增的、可能是最有价值的贡献**，且与 IR 经典文献直接对话。

### 4.3 需要补的引用

- **IR 评测方法论**：Efficient construction (1998)、Bias and limits of pooling (2007)、
  Score adjustment (2009)、How reliable (1998)。
- **隐喻基准**：VUA 2018 报告、MOH-X/TroFi（Neural Metaphor Detection in Context）、
  LCC、MultiMET、**MiQA (2022)**、**ANALOGICAL (2023)**、**Meta4XNLI (2025)**。
- **LLM-as-judge 偏差**：Humans or LLMs as the Judge (2024)、Judging the Judges (2025)。
- **图 RAG 何时有增益**：When to Use Graphs in RAG (2025)。
- **超图 RAG 方法对照**：HyperGraphRAG (2025)、Hyper-RAG (Nature Comms)、
  Cog-RAG (2025)、HyperSU (2026)、PRoH (2025)。

### 4.4 一个具体的、低成本的高价值实验

结合本报告的检索结果，建议的下一步实验（**离线、$0、可立即执行**）：

**用 MiQA 或 ANALOGICAL 的金标构造方式，重建你的检索查询集**，然后重测
§6.1/6.2。理由：

- 你现有查询是**从边生成**的（`query = "，".join(e.triggers)`），这是构造锚定的根源；
- MiQA/ANALOGICAL 作为独立的隐喻推理基准，其查询**不是**从待检索的边生成，
  可用于检验"在非锚定查询上，你的三通路表现如何"；
- 若你的语义超图通路在非锚定查询上仍显著优于字面/级联通路，**那才是架构有效的
  有力证据**；若优势消失，则说明原结论确实由锚定造成。

这是把"基准修复"从"需要重建整个基准"降级为"换一个查询来源"的最小可行方案。

---

## 五、检索记录与覆盖说明

**查询（OpenAlex fulltext.search）**：
```
metaphor detection benchmark
metaphor detection dataset
metaphor retrieval augmented generation knowledge graph
metaphor understanding interpretation benchmark large language model
VUA metaphor shared task MOH-X TroFi dataset
GraphRAG hypergraph retrieval evaluation benchmark n-ary
Chinese metaphor identification corpus CCL
information retrieval evaluation pooling test collection bias
LLM as judge reliability validity evaluation bias
```
另对 12 篇关键候选做了 DOI/venue/年份的**逐条验证**（见正文链接）。

**来源政策**：排除 MDPI 及掠夺性 venue。本次检索未命中被排除来源。

**覆盖缺口（诚实标注）**：
1. ~~arXiv API 不可用~~ **已补**：改用 `https://export.arxiv.org` 直连成功
   （原脚本用 `http://` 触发 301）。已补检索三个簇，新增发现 MiQA、ANALOGICAL、
   Meta4XNLI、NYK-MS（中文多模态）等基准，均已经 OpenAlex DOI 交叉验证。
   **仍未做**：2026 年超图 RAG 工作的全文精读（仅凭标题+摘要判读评测数据集）。
2. **CCL2018 中文基准**未在 OpenAlex 命中独立记录（它是评测任务而非论文），
   信息来自本项目已有材料。
3. 未检索中文文献库（CNKI/万方）——若需中文隐喻基准的完整图景，需补充。
4. **未验证各基准的实际许可条款**——VUA/MOH-X/TroFi/LCC/MultiMET/MiQA/
   ANALOGICAL 的使用条款需逐一到其官方页面确认（本项目对 CCL2018 已做过此工作，
   结论是"仅限学术研究"）。

**下一步建议**：若要把"评测方法论诊断"发展为贡献点，建议专门检索
`pooling bias correction`、`test collection construction`、`metric saturation`
三条线，并与 experiment-designer 模块对接设计具体实验。
