# Literature Search: 凸几何 × 表示学习 ＆ 多 Agent LLM 写作

Date: 2026-09-27
Search purpose: 两个研究方向的文献整理（方向侦察 / Related Work 素材库）
Target venue/family: ACL/EMNLP/NAACL, ICML/ICLR/NeurIPS, Information & Inference
Source-quality policy: applied（排除 MDPI 等政策排除源；snippet 不作为最终依据）
Verification note: 标注 ⧖ 的条目为检索结果给出、但 venue 状态未逐条二次核验；其余 arXiv/ACL/PMLR 链接均经过本会话核验。

## Summary

- Closest-work clusters:
  - A1 表征空间的「形状」：凸包、锥、各向异性（词向量时代）
  - A2 线性表示假设与概念几何（LLM 残差流时代）
  - A3 网络函数的分段线性 / 凸几何理论（工具箱层）
  - B1 多 Agent LLM：综述与协作机制
  - B2 多 Agent 写作（叙事/长文）专门工作
  - B3 辩论 / 多实例聚合提升生成质量
  - B4 通用多 Agent 框架（基础设施）
  - B5 失败模式与写作评测
  - X 交汇带：凸几何视角看多 Agent 动态（观点动力学桥接，多为推断）
- Opportunity map: 见下方表格（机会判断均为推断，已标注）
- Strongest baselines: Agents' Room（多 Agent 叙事的中心工作）；Stolen Probability（词向量凸包分析的占坑工作）
- Benchmark/dataset candidates: Tell Me A Story、WritingBench、CollabStory 语料、LongWriter 长文场景、Marks 真伪数据集、MAST 失败轨迹
- Novelty risks: 「词向量凸包」已有 ACL 2020 占坑工作；「多 Agent 分解 + 编排器写故事」已被 Agents' Room 覆盖
- Recommended next action: 若做交汇方向（X），先跑一个最小信号实验——把若干多 Agent 写作轨迹映射进嵌入空间，测凸包收缩/重心漂移是否与成稿质量相关

## Paper Table

| # | Title | Year | Venue/Source | Link | Type | 定位与备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Stolen Probability: A Structural Weakness of Neural Language Models | 2020 | ACL 2020 | https://arxiv.org/abs/2005.02433 | theory/proof | 词向量凸包结构缺陷的占坑工作：softmax 点积偏置使凸包内部词的概率被包络词"偷走" |
| 2 | All Bark and No Bite: Rogue Dimensions in Transformer Language Models Obscure Representational Quality | 2021 | EMNLP 2021 | https://arxiv.org/abs/2109.04404 | pure method | 各向异性诊断：少数 rogue 维度支配相似度，窄锥分布；标准化可修正 |
| 3 | IsoScore: Measuring the Uniformity of Embedding Space Utilization | 2022 | Findings of ACL 2022 | https://arxiv.org/abs/2108.07344 | pure method | 各向同性度量标准件（后续有 IsoScore* 修订与正则化用法） |
| 4 | How Contextual are Contextualized Word Representations? Comparing the Geometry of BERT, ELMo, and GPT-2 Embeddings | 2019 | EMNLP-IJCNLP 2019 | https://aclanthology.org/D19-1006/ | theory/analysis | 各向异性议题的源头锚点之一（补充背景，链接凭知识填写，未本次核验） |
| 5 | Approximating the semantic space: word embedding …（convex hull 表征语义空间外沿） | 2024 | Humanities & Social Sciences Communications (Nature portfolio) ⧖ | https://www.nature.com/articles/s41537-024-00524-7 | pure method | 用凸包刻画语义嵌入空间的外沿范围；跨学科应用 |
| 6 | The Linear Representation Hypothesis and the Geometry of Large Language Models | 2024 | ICML 2024 | https://arxiv.org/abs/2311.03658 | theory/proof | LRH 理论化：一元属性=线性方向、二元关系=双线性结构，对偶空间与因果内积；1000+ 引用 |
| 7 | The Geometry of Truth: Emergent Linear Structure in Large Language Model Representations of True/False Datasets | 2023 | arXiv 2023（曾投 ICLR 2024，OpenReview 在案）⧖ | https://arxiv.org/abs/2310.06824 | theory/analysis | 真伪概念的涌现线性结构，可被简单探针提取 |
| 8 | Toy Models of Superposition | 2022 | Transformers Circuits Thread（Anthropic 技术报告）⧖ | https://transformer-circuits.pub/2022/toy_model/index.html | theory/analysis | 特征叠加的几何相变（点→圆环→多面体），叠加特征几何即"准凸几何" |
| 9 | On the Number of Linear Regions of Deep Neural Networks | 2014 | NeurIPS 2014 | https://papers.nips.cc/paper/5422-on-the-number-of-linear-regions-of-deep-neural-networks | theory/proof | 深度网络分段线性区域计数的开山工作（深度相对宽度的指数优势） |
| 10 | Bounding and Counting Linear Regions of Deep Neural Networks | 2018 | ICML 2018 | https://openreview.net/forum?id=Sy-tszZRZ | theory/proof | 更紧的区域数上界（MILP 式分析） |
| 11 | On the Number of Linear Functions Composing Deep Neural Networks | 2021 | ICML 2021 (PMLR v130) | https://proceedings.mlr.press/v130/takai21a.html | theory/proof | 以"线性函数拼合数"为复杂度度量的计数结果 |
| 12 | On the number of regions of piecewise linear neural networks | 2024 | EPFL（正式 venue 待核验）⧖ | https://infoscience.epfl.ch/bitstreams/73ec9a1c-ebce-4a78-9ace-51bd619b6166/download | theory/proof | CPWL 网络区域数的上下界新进展（Goujon、Etemadi 等） |
| 13 | Living on the edge: Phase transitions in convex programs with random data | 2014 | Information and Inference 3(2014) 224–294 | https://arxiv.org/abs/1303.6672 | theory/proof | 凸几何工具箱经典：锥内蕴体积、统计维度刻画凸优化相位转移 |
| 14 | Multi-Agent Collaboration Mechanisms: A Survey of LLMs | 2025 | arXiv 2025（综述，~800 引用）⧖ | https://arxiv.org/abs/2501.06322 | survey | 协作机制分类学：actor/type/structure/strategy 四维框架 |
| 15 | Large Language Model based Multi-Agents: A Survey of Progress and Challenges | 2024 | IJCAI 2024 | https://www.ijcai.org/proceedings/2024/890 | survey | 多 Agent 系统的进展与挑战综述 |
| 16 | Scaling Large Language Model-based Multi-Agent Collaboration (MacNet) | 2025 | ICLR 2025 | https://openreview.net/forum?id=K3n5jPkrU6 | pure method | 协作的 scaling law：Agent 数量/拓扑对协作效果的影响 |
| 17 | Agents' Room: Narrative Generation through Multi-step Collaboration | 2025 | ICLR 2025 | https://arxiv.org/abs/2410.02603 | method + benchmark | 多 Agent 写作的中心工作：叙事理论驱动的子任务分解 + 编排器；专家偏好显著优于单模型；附 Tell Me A Story 数据集 |
| 18 | Multi-Agent Based Character Simulation for Story Writing | 2025 | IN2WRITING Workshop @ ACL 2025 | https://aclanthology.org/2025.in2writing-1.9/ | pure method | 角色智能体模拟写故事：从叙事计划出发，用 character agents 增强可控性 |
| 19 | CollabStory: Multi-LLM Collaborative Story Generation and Authorship Tracking | 2025 | Findings of NAACL 2025 | https://arxiv.org/abs/2406.12665 | method + benchmark | 32k+ 多 LLM 协作故事语料 + 作者身份归属问题 |
| 20 | Collaborative Multi-Agent Simulation for Hybrid Bottom-Up Story Generation | 2025 | arXiv 2025 预印本 ⧖ | https://arxiv.org/html/2510.11618v3 | pure method | 自底向上：沙盒多智能体交互生成事件，再由 Storyteller 汇成叙事 |
| 21 | Improving Factuality and Reasoning in Language Models through Multiagent Debate | 2024 | ICML 2024 ⧖ | https://arxiv.org/abs/2305.14325 | pure method | 多实例辩论改进事实性/推理的奠基工作；终答=多轮聚合（本质是凸组合式投票） |
| 22 | Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate | 2024 | Findings of EMNLP 2024 | https://aclanthology.org/2024.findings-emnlp/（卷页链接；论文页 ID 待核验）⧖ | pure method | 辩论对抗同质化：以翻译/对抗样本验证发散观点的价值 |
| 23 | AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation | 2023 | arXiv 2023 | https://arxiv.org/abs/2308.08155 | system/tool | 会话式多 Agent 编程抽象的事实标准之一 |
| 24 | CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society | 2023 | NeurIPS 2023 | https://arxiv.org/abs/2303.17760 | pure method | 角色扮演 + inception prompting 的双 Agent 协作框架 |
| 25 | MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework | 2024 | ICLR 2024 | https://arxiv.org/abs/2308.00352 | system/tool | SOP 工作流注入多 Agent 协作的代表（软件公司隐喻） |
| 26 | Why Do Multi-Agent LLM Systems Fail? (MAST) | 2025 | arXiv 2025（据检索结果为 NeurIPS 2025）⧖ | https://arxiv.org/abs/2503.13657 | theory/analysis | 200+ 执行轨迹的失败分类学：specification / inter-agent misalignment / verification 三类 |
| 27 | WritingBench: A Comprehensive Benchmark for Generative Writing | 2025 | arXiv 2025（据检索结果为 NeurIPS 2025）⧖ | https://arxiv.org/abs/2503.05244 | pure benchmark | 1000 条真实写作查询 × 6 域 × 100 子域，query-aware 动态评审 |
| 28 | LongWriter: Unleashing 10,000+ Word Generation from Long Context LLMs | 2024 | arXiv 2024 ⧖ | https://arxiv.org/abs/2408.07055 | method + benchmark | 超长文本生成的能力边界与评测（单模型锚点，作对照背景） |
| 29 | Simulating Opinion Dynamics with Networks of LLM-based Agents | 2024 | Findings of NAACL 2024 | https://arxiv.org/abs/2311.09618 | pure method | 交汇桥接：LLM Agent 网络上的观点动力学（传统模型本质是凸组合迭代） |

## Clusters

### A1 表征空间的「形状」：凸包、锥、各向异性（词向量/静态嵌入时代）

- Representative papers: #1 Stolen Probability、#2 Rogue Dimensions、#3 IsoScore、#4 Ethayarajh 2019、#5 Palominos 2024
- What this cluster already solves: 嵌入空间几何的诊断指标（各向异性、窄锥、rogue 维度）与修正手段（标准化/白化）；softmax 点积归纳偏置的凸包机制刻画（#1 已证明凸包内部词的概率被包络词上界锁死）
- Remaining gap: 这些凸几何诊断基本停留在 word2vec/softmax LM 与静态嵌入时代；对现代 LLM 残差流（叠加状态下）的凸结构刻画很少；几何指标与下游生成质量的因果链薄弱
- Possible rescue or differentiation route: 把凸包/锥/各向同性诊断迁移到 LLM 残差流，并与生成任务（如写作质量）做因果而非相关分析
- How it affects the user's paper: 若做「嵌入的凸几何」必须引用 #1 并明确差异（对象、任务、机制三层）

### A2 线性表示假设与概念几何（LLM 表征时代）

- Representative papers: #6 LRH (ICML 2024)、#7 Geometry of Truth、#8 Toy Models of Superposition
- What this cluster already solves: 概念=线性方向、关系=双线性结构的理论框架与因果干预验证；真伪/属性概念的可探测线性结构；特征叠加的几何相变图景
- Remaining gap: LRH 以「单方向」为主；概念的凸结构（概念锥、正包络、单纯形组合封闭性）几乎没有形式化工作；非线性/多方向表征如何统一进几何框架是公开问题（推断）
- Possible rescue or differentiation route: 把 LRH 从线性方向推广为凸锥/单纯形结构并用因果干预验证；与隐喻等「非标准语义组合」结合——隐喻恰好是线性假设最容易破的地方（与本项目契合）
- How it affects the user's paper: #6 是必引的理论锚；任何"方向+干预"实验都要与 #7 的探针协议对齐

### A3 网络函数的分段线性 / 凸几何理论（工具箱层）

- Representative papers: #9 Montúfar 2014、#10 Serra 2018、#11 Takai 2021、#12 Goujon 2024、#13 Living on the edge
- What this cluster already solves: 线性区域计数的上下界体系；凸优化随机数据的相位转移理论（锥内蕴体积/统计维度——最完整的"凸几何应用范式"）
- Remaining gap: 线性区域理论与 LLM 表征几何几乎不对话；intrinsic volumes 这套工具没有被用于分析 Transformer 表征或生成行为（推断）
- Possible rescue or differentiation route: 用统计维度/内蕴体积给「表征可用维度」「叠加相变」提供严格量——把 A3 的工具接进 A2 的问题
- How it affects the user's paper: 作为方法论工具箱引用，不构成直接竞争

### B1 多 Agent LLM：综述与协作机制

- Representative papers: #14 Tran 2025 survey、#15 Guo IJCAI 2024 survey、#16 MacNet ICLR 2025
- What this cluster already solves: 协作机制的四维分类学；Agent 数量/拓扑扩展性的初步规律
- Remaining gap: 分类学偏描述性，缺「何种机制适合何种写作任务」的处方性结论（机制 gap）
- Possible rescue or differentiation route: 以写作为受控实验床做机制比较，产出可迁移的设计准则
- How it affects the user's paper: Related Work 骨架来源；不构成威胁

### B2 多 Agent 写作（叙事/长文）专门工作

- Representative papers: #17 Agents' Room（中心工作）、#18 Character Simulation、#19 CollabStory、#20 Hybrid Bottom-Up Simulation
- What this cluster already solves: 子任务分解 + 编排器 + 角色分工的范式（叙事理论驱动），专家偏好上已证优于单模型；协作语料与作者归属问题的提出
- Remaining gap: 评价几乎只看终稿偏好，缺过程级评测（谁贡献了什么、分工是否名实相符、编排策略的消融）；协作拓扑对写作质量的系统研究缺失
- Possible rescue or differentiation route: 过程级/贡献分解评测协议；把 A1/A2 的几何指标用作协作动态的过程度量（接 X 带）
- How it affects the user's paper: #17 是最直接的占坑对手：做"多 Agent 写作"必须在其子任务分解之外给出新维度（过程几何、失败诊断、或凸结构化编排）

### B3 辩论 / 多实例聚合提升生成

- Representative papers: #21 Du et al. (ICML 2024)、#22 Liang et al. (Findings EMNLP 2024)
- What this cluster already solves: 多轮辩论改进事实性与推理；发散思维对抗"身份坍缩"式同质化
- Remaining gap: 场景集中在 QA/推理/翻译；对开放式创意写作的收益与成本-收益曲线不清楚；聚合步骤本质是凸组合/投票，但无人从几何角度分析收敛（推断桥接）
- Possible rescue or differentiation route: 辩论 × 创意写作的对照实验；把"观点收敛"建模为嵌入空间中的凸组合轨迹并测量
- How it affects the user's paper: 提供最便宜的多 Agent 基线（无编排器，纯多实例）

### B4 通用多 Agent 框架（基础设施）

- Representative papers: #23 AutoGen、#24 CAMEL、#25 MetaGPT
- What this cluster already solves: 会话式编程抽象、角色扮演、SOP 工作流
- Remaining gap: 均非写作专用，缺写作任务的评估闭环；引用其协议时要注意与写作场景的适配成本
- How it affects the user's paper: 实现层选型参考（AutoGen 或 CAMEL 最省力）

### B5 失败模式与写作评测

- Representative papers: #26 MAST、#27 WritingBench、#28 LongWriter
- What this cluster already solves: MAS 失败三分类（specification / inter-agent misalignment / verification）；写作评测的域覆盖与 query-aware 评审；超长生成的能力边界
- Remaining gap: MAST 是通用 trace 分类学，写作专用 MAS 的失败模式（情节漂移、视角串写、风格平均化）未被单独刻画；多 Agent 写作尚无可复现的评测协议（benchmark gap）
- Possible rescue or differentiation route: 写作版失败分类学 + 过程级 benchmark；直接复用 WritingBench 作终稿质量 protocol anchor
- How it affects the user's paper: 若提出新系统，评审会拿 WritingBench/LongWriter 场景对标

### X 交汇带：凸几何视角看多 Agent 动态（多为推断）

- Representative papers: #29 Chuang et al.（唯一的既有桥接）；推断关系指向 #21（辩论聚合=凸组合）、#16（拓扑扩展）、#17（编排轨迹）
- What this cluster already solves: 证明「LLM Agent 网络 × 观点动力学」这条桥已被走过一半
- Remaining gap: 把多 Agent 写作过程显式建模为表征空间中的点集轨迹（草稿/意见/角色立场），用凸包收缩、重心漂移、各向同性变化度量协作动态——目前没有系统工作（推断，需查证最新 preprint）
- Possible rescue or differentiation route: 最小信号实验：跑 N 条 Agents' Room 式轨迹，测轨迹几何量与成稿质量（WritingBench 分）的相关性；有信号再做理论化（接 A3 的内蕴体积/统计维度工具）
- How it affects the user's paper: 这是两个方向唯一的天然交汇点，也是新颖性最强、风险最高的一档

## Opportunity Map

（机会判断均为检索后的推断，非源文结论）

| Cluster | Status | Open gap | Possible direction | Evidence needed | Risk |
| --- | --- | --- | --- | --- | --- |
| A1 | crowded but open | 几何诊断停在静态嵌入时代 | LLM 残差流的凸结构 + 因果分析 | 与下游质量的干预性证据 | 指标类工作同质化 |
| A2 | theory/analysis gap | LRH 缺凸结构形式化 | 概念锥/单纯形推广 + 因果干预 | 可复现的干预协议 | Park 组持续推进，窗口期短 |
| A3 | theory/analysis gap | 内蕴体积工具未进入表征分析 | 统计维度度量叠加/可用维度 | 与 #8 相变图景的对接实验 | 纯理论门槛高 |
| B1 | covered central claim | 描述性综述饱和 | 处方性机制比较 | 受控对比实验 | rescue 路线：新机制/新证据 |
| B2 | crowded but open | 只评终稿，不评过程 | 过程级评测 + 贡献分解 | 专家评审/消融设计 | Agents' Room 持续迭代 |
| B3 | mechanism gap | 辩论 × 创意写作未测 | 对照实验 + 几何收敛分析 | 成本-收益曲线数据 | 收益可能为零（负面结果也是机会） |
| B5 | benchmark gap | 写作专用 MAS 失败分类缺失 | 写作版 MAST + 协议 | 大规模轨迹收集 | 标注成本高 |
| X | 交叉空白（negative-result opportunity） | 协作动态的几何建模无人做 | 轨迹凸几何 ↔ 质量相关 | 最小信号实验 | 若无相关则方向失败，需预设止损 |

## Benchmark And Dataset Candidates

| Name | Link | Task | Metrics | Baselines | Fit | Risks |
| --- | --- | --- | --- | --- | --- | --- |
| Tell Me A Story | https://github.com/google-deepmind/tell_me_a_story | 长篇叙事生成（人写高质量故事集） | 专家偏好 | Agents' Room 论文基线 | 多 Agent 写作首选评测 | 规模小 |
| WritingBench | https://arxiv.org/abs/2503.05244 | 生成式写作 6 域 100 子域 | query-aware LLM 评审 | 各旗舰模型榜 | 终稿质量 protocol anchor | LLM 评审偏差 |
| CollabStory | https://arxiv.org/abs/2406.12665 | 多 LLM 协作故事 + 作者归属 | 归属准确率等 | 论文内 | 过程/贡献分解研究素材 | 场景较窄 |
| LongWriter 场景 | https://arxiv.org/abs/2408.07055 | 万字级生成 | 长度/质量评分 | 单模型 | 长文压力测试对照 | 非多 Agent 专用 |
| True/False 数据集（Marks） | https://arxiv.org/abs/2310.06824 | 真伪命题表征 | 探针准确率 | 线性探针/PCA | 表征几何实验复用 | 仅真伪维度 |
| MAST 轨迹 | https://arxiv.org/abs/2503.13657 | MAS 失败标注 | 分类一致性 | MAST 分类器 | 失败分析起点 | 通用非写作 |

## Citation And Positioning Cautions

- Claims that need direct citation:
  - 「词向量凸包内部概率受限」→ 必引 #1 Stolen Probability
  - 「概念=线性方向」→ 必引 #6 LRH；探针实验 → 对齐 #7 协议
  - 「多 Agent 分解写作优于单模型」→ 必引 #17 Agents' Room
  - 各向异性背景三件套：#4、#2、#3
- Papers that may weaken novelty:
  - #1（凸包占坑）、#17（多 Agent 写作占坑）、#16（协作拓扑已有 scaling 分析）、#29（Agent 网络观点动力学已存在）
- Papers that only support background:
  - #9–#13（理论工具箱）、#23–#25（框架）、#28（长文背景）
- 未二次核验项（⧖）：#5、#7、#8、#12、#14、#20、#21（venue）、#26–#28（venue 状态据检索结果）；引用前建议逐条打开链接确认。
