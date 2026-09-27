# Literature Search: 图论/拓扑在 RAG 中的应用（GNN + TDA）

Date: 2026-09-27
Search purpose: 方向侦察——为「将非结构化文本映射为图结构 / 高维拓扑空间，用 GNN 学习图表示、用拓扑不变量（持久同调、Betti 数等）刻画语料全局形状特征，服务 RAG 检索」的设想做相关工作扫描与机会定位。
Target venue/family: NeurIPS / ICLR / ICML / ACL / AAAI / KDD / TOIS / JMLR + arXiv 一手页面
Source-quality policy: applied（MDPI 及不可溯源来源已排除；证据分级见 search-notes.md）

## Summary

- 最接近工作的聚类：① GraphRAG 主线（实体图+图检索，两篇高引综述）；② GNN×RAG 直接交点（GNN-RAG、SubgraphRAG）；③ 文本→图/单纯复形的 GNN（TextGCN、SAN）；④ TDA×NLP（嵌入空间拓扑，2024 综述收录 137 篇）；⑤ 图/网络持久同调工具箱；⑥ 可微拓扑表示学习（TopoAE、PersLay）；⑦ 拓扑×LLM 潜空间（对抗分析）；⑧ 拓扑×RAG 直接交点——仅 1 篇在审稿件（HPT-TRACE）+ 1 篇树分层 RAG（T-Retriever）。
- Opportunity map：图 RAG 变体本身 = covered central claim；拓扑不变量 × RAG 的索引/组织/诊断层 ≈ 空白（mechanism gap + benchmark gap）；拓扑作为「全局形状→检索质量」的可解释桥梁是未被占据的机制故事。
- Strongest baselines: HippoRAG 2、LightRAG、SubgraphRAG、RAPTOR、GNN-RAG。
- Benchmark/dataset candidates: GraphRAG-Bench、MuSiQue、2WikiMultiHopQA、QuALITY、HotpotQA（详见下表，部分为摘要级证据）。
- Novelty risks: HPT-TRACE（OpenReview 在审）已占「拓扑空间+分层划分树+证据路径求交」的 reranking 位置；Michel et al. 2017 的负结果提示：PH 特征并不必然带来下游任务增益。
- Recommended next action: 不要做「又一个图 RAG 变体」；把拓扑定位在诊断层/组织层/可解释层，并与 HPT-TRACE 明确差异化。

## Paper Table

> 证据等级：✅ = 已打开一手页面核实（arXiv abs / ACL Anthology / JMLR / IJCAI / Springer）；◇ = 仅检索摘要级证据，引用前需打开原文。

### A. 图结构 RAG（GraphRAG 主线）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | From Local to Global: A Graph RAG Approach to Query-Focused Summarization（微软 GraphRAG） | 2024 | arXiv | https://arxiv.org/abs/2404.16130 | pure method | 奠基作：LLM 抽取实体知识图谱+社区层次摘要，回答全语料级问题；「图结构进 RAG」的起点 |
| A2 | Graph Retrieval-Augmented Generation: A Survey（Peng et al.） | 2024 | arXiv / ACM TOIS 2025 | https://arxiv.org/abs/2408.08921 | survey | 被引 ~885 的权威综述：图索引、图增强检索、图增强生成三段式梳理 |
| A3 | Retrieval-Augmented Generation with Graphs (GraphRAG)（Han et al.） | 2024 | arXiv | https://arxiv.org/abs/2501.00309 | survey | 另一篇综述：query processor / retriever / organizer / generator / data source 五组件框架 + 分领域综述 |
| A4 | HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs | 2024 | arXiv / NeurIPS 2024 | https://arxiv.org/abs/2405.14831 | pure method | KG 作海马体索引 + Personalized PageRank 单步多跳检索；图上经典算法做检索的代表作 |
| A5 | From RAG to Memory: Non-Parametric Continual Learning for LLMs（HippoRAG 2） | 2025 | arXiv | https://arxiv.org/abs/2502.14802 | pure method | 把检索重新定义为非参数持续学习；PPR 检索 + 段落级记忆巩固 |
| A6 | RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval | 2024 | arXiv（Stanford） | https://arxiv.org/abs/2401.18059 | pure method | 递归聚类+摘要成树，多抽象层级检索（QuALITY 上 GPT-4 +20% 绝对提升）——「分层结构组织语料」的非图代表 |
| A7 | LightRAG: Simple and Fast Retrieval-Augmented Generation | 2024 | arXiv | https://arxiv.org/abs/2410.05779 | pure method | 图文本索引 + 双层（低/高层实体）检索 + 增量更新 |
| A8 | Simple Is Effective: … KG-Based RAG（SubgraphRAG） | 2024 | arXiv | https://arxiv.org/abs/2410.20724 | pure method | 轻量 MLP 并行三元组打分子图检索，强调检索效率与子图大小可控 |

### B. GNN × RAG 交点

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | GNN-RAG: Graph Neural Retrieval for LLM Reasoning（Mavromatis & Karypis） | 2024 | arXiv | https://arxiv.org/abs/2405.20139 | pure method | ★ 最直接的 GNN×RAG 交点：GNN 在 KG 上做图推理检索候选答案实体，再交 LLM 复述推理 |
| B2 | Graph of Records: Boosting RAG for Long-context Summarization with Graphs | 2024 | arXiv | https://arxiv.org/abs/2410.11001 | pure method | 用 GNN 学习「检索块—历史响应」图；GNN 出现在 RAG 的组织层而非检索层 |
| B3 | T-Retriever: Tree-based Hierarchical RAG for Textual Graphs | 2026 | arXiv（编号待核） | （InsightArxiv/alphaXiv 收录记录）◇ | pure method | 在文本图上做树分层检索、显式优先拓扑结构的 RAG（细节未核实） |

### C. 文本 → 图 / 单纯复形（把非结构化文本映射为图结构的基础设施）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Graph Convolutional Networks for Text Classification（TextGCN） | 2018 | AAAI 2019 | https://arxiv.org/abs/1809.05679 | pure method | 奠基：语料级词-文档异构图 + GCN 联合学习词/文档嵌入 |
| C2 | Simplicial Attention Neural Networks（SAN，Giusti et al.） | 2022 | arXiv（高阶拓扑信号处理） | https://arxiv.org/abs/2203.07485 | pure method | ★ 单纯复形（节点/边/三角形）上的注意力机制，文本分类验证；「高维拓扑空间上的神经网络」代表 |
| C3 | Generalized Simplicial Attention Neural Networks（GSAN） | 2023 | arXiv | https://arxiv.org/abs/2309.02138 | pure method | SAN 的推广族（◇ 摘要级证据） |
| C4 | Architectures of Topological Deep Learning: A Survey of Message-Passing Topological Neural Networks（Hajij et al.） | 2023 | arXiv | https://arxiv.org/abs/2304.10031 | survey | 拓扑神经网络架构综述：单纯复形/胞腔复形/超图上的消息传递 |

### D. TDA × NLP（嵌入空间的拓扑分析）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | Topological Data Analysis Applications in NLP: A Survey（Uchendu & Le） | 2024 | arXiv / ACM SIGKDD Explorations 2026 | https://arxiv.org/abs/2411.10298 | survey | ★ 领域边界权威：收录 137 篇，PH+Mapper 两大技术线，结论是 NLP 对 TDA 的采纳显著落后于 CV |
| D2 | Persistent Homology: An Introduction and a New Text Representation for NLP（Xin Zhu） | 2013 | IJCAI 2013 | https://www.ijcai.org/Proceedings/13/Papers/288.pdf | pure method | 奠基：对文本点云做多尺度持久同调分析得拓扑特征表示 |
| D3 | Does the Geometry of Word Embeddings Help Document Classification? A Case Study on Persistent Homology-Based Representations（Michel et al.） | 2017 | NoDaLiDa 2017 Workshop（ACL Anthology W17-2628） | https://aclanthology.org/anthology-files/anthology-files/pdf/W/W17/W17-2628.pdf | method（负结果） | ★ 重要负结果：PH 文档表示未在传统 NLP 任务上带来增益——直接约束拓扑特征的价值定位 |
| D4 | Topology of Word Embeddings: Singularities Reflect Semantics（Jakubowski et al.） | 2020 | *SEM 2020 | https://aclanthology.org/2020.starsem-1.11.pdf | analysis | 词嵌入的奇点结构（拓扑分析）反映语义 |
| D5 | The Shape of Word Embeddings: …（语言对几何/拓扑距离） | 2024 | arXiv | https://arxiv.org/abs/2404.00500 ◇ | analysis | 用 PH 比较不同语言词嵌入形状（标题/内容仅摘要级证据） |
| D6 | Enhanced Graph Embedding via Persistent Homology（Hiraoka et al.） | 2023/2024 | JMLR 25 | https://arxiv.org/abs/2309.08241 | pure method | ★ 把 PH 信号接进 word2vec 式图嵌入训练——「拓扑不变量进表示学习」的成熟范例 |

### E. 图/网络的持久同调（拓扑不变量工具箱）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Persistent Homology of Complex Networks（Horak, Maletic, Rajkovic） | 2008 | arXiv | https://arxiv.org/abs/0811.2203 | theory/analysis | 奠基：把 PH 当作参数化 Betti 数，刻画网络鲁棒性相关的长寿命拓扑特征 |
| E2 | Persistence Homology of Networks: Methods and Applications（Aktas et al.） | 2019 | Applied Network Science（Springer） | https://link.springer.com/article/10.1007/s41109-019-0179-3 | survey | 网络 PH 方法与应用综述 |
| E3 | PH of Complex Networks for Dynamic State Detection（Myers et al.） | 2019 | arXiv | https://arxiv.org/abs/1904.07403 | pure method | 用网络 PH 做动力系统状态检测 |
| E4 | PH of Unweighted Complex Networks via Discrete Morse Theory（Kannan et al.） | 2019 | arXiv | https://arxiv.org/abs/1901.00395 | pure method | 离散 Morse 理论加速大规模网络 PH 计算（可扩展性入口） |
| E5 | Persistent Homology and Graphs Representation Learning（Hajij et al.） | 2021 | arXiv | https://arxiv.org/abs/2102.12926 | pure method | PH 特征 × 图表示学习的桥接 |
| E6 | Persistent Homology of Graph Embeddings（Solanki et al.） | 2019 | arXiv | https://arxiv.org/abs/1912.10238 | theory/analysis | 图嵌入的一致性 + 区分嵌入模型的拓扑假设检验 |
| E7 | Can Persistent Homology Provide an Efficient Alternative? Knowledge Persistence（Bastos et al.） | 2023 | arXiv | https://arxiv.org/abs/2301.12929 | pure method | ★ 用 PH 加速/替代 KG 补全的评估——「拓扑不变量评估知识图谱」的先例 |

### F. 可微拓扑 / 拓扑深度学习（把拓扑不变量接进训练回路）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Topological Autoencoders（Moor et al.） | 2020 | ICML 2020（PMLR） | https://proceedings.mlr.press/v119/moor20a.html ◇ | pure method | 可微持久同调损失，约束潜空间与输入拓扑一致 |
| F2 | PersLay: A Neural Network Layer for Persistence Diagrams（Carrière et al.） | 2020 | NeurIPS 2020 | https://arxiv.org/abs/2004.02797 ◇ | pure method | 持久图→向量的通用可学习层（拓扑特征进深度网络的标准接口） |
| F3 | Topologically Regularized Data Embeddings（Heiter et al.） | 2023 | arXiv | https://arxiv.org/abs/2301.03338 | pure method | 嵌入损失 + 拓扑损失联合优化 |
| F4 | Challenges and Opportunities in Topological Deep Learning（Papamarkou et al.，position） | 2024 | arXiv | https://arxiv.org/abs/2402.08871 | survey（立场文） | TDL 路线图：机遇与瓶颈（含可扩展性） |

### G. 拓扑 × LLM / RAG 直接交点（最贴近设想的工作）

| # | 标题 | 年份 | 出处 | 链接 | 类型 | 与主题的关系 |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | Topological Retrieval-Augmented Generation via Intersecting Evidence Paths（HPT-TRACE，Zheng et al.） | 2025/26 | OpenReview 在审 | https://openreview.net/forum?id=qSaRIuBuYx ◇ | pure method | ★ 目前最直接交点：Hierarchical Partition Tree（自顶向下分裂聚类、不依赖 LLM）定义语料拓扑空间，多查询检索时对证据路径求交做 reranking；细节为评审页摘要级证据 |
| G2 | Holes in Latent Space: Topological Signatures Under Adversarial Influence | 2025 | arXiv | https://arxiv.org/abs/2505.20435 | analysis | 逐层 TDA 分析 LLM 潜空间：对抗干预压缩拓扑复杂度——拓扑签名用作 LLM 诊断信号 |
| G3 | Detecting Short LLM-generated Text with TDA | 2025 | （检索摘要级证据）◇ | — | analysis | PH + 检索/解码特征做 LLM 生成文本检测（出处待核，暂不引用） |

## Clusters

### Cluster 1: 图结构 RAG（GraphRAG 主线）

- Representative papers: A1–A8。
- What this cluster already solves: 语料→实体知识图的构建（LLM 抽取）、图索引、图上的检索算法（PPR、子图选择、社区摘要）、双层/多跳检索、增量更新；并有两篇成熟综述给出完整分类。
- Remaining gap: 图由 LLM 抽取，昂贵且不稳定；图的构建质量、鲁棒性、评估协议是公认痛点；「为什么图 RAG 有效」缺机制解释。
- Possible rescue or differentiation route: 不做新变体；把拓扑不变量用作该类图的全局质量诊断与组织信号。
- How it affects the user's paper: 主线必须作为 baseline 与相关工作背景引用（A2/A3 之一 + A1 + 最强 2–3 个方法）。

### Cluster 2: GNN × RAG

- Representative papers: B1–B3。
- What this cluster already solves: GNN 在 KG/文本图上做检索打分与推理（B1），GNN 组织历史响应图（B2）。
- Remaining gap: GNN 在这里全部运行在「实体关系图」上，图的拓扑本身从未被用拓扑不变量刻画；GNN 学的是局部消息传递，全局形状信息靠 pooling 隐式获得。
- Possible rescue or differentiation route: 「拓扑特征作为 GNN 检索器的输入/先验」或「拓扑签名约束 GNN 表示」——两条均未见成熟工作。
- How it affects the user's paper: B1 是「引入 GNN」设想的最近邻，必须差异化。

### Cluster 3: 文本 → 图/单纯复形

- Representative papers: C1–C4。
- What this cluster already solves: 非结构化文本→图（词-文档图）→GCN（C1）；文本表示提升到单纯复形、高阶消息传递与注意力（C2/C3）；架构全景（C4）。
- Remaining gap: 这些工作全部做分类任务，不做检索/RAG；单纯复形的构建是启发式的（共现窗口、依存树）。
- How it affects the user's paper: 提供「文本映射为图/拓扑结构」的技术合法性引用；SAN 的 TMLR 后续与 ICLR 版本引用前需再核。

### Cluster 4: TDA × NLP

- Representative papers: D1–D6。
- What this cluster already solves: 文本点云的 PH 分析（D2，2013 奠基）、词嵌入奇点/形状分析（D4/D5）、PH 进图嵌入训练（D6）、领域全景（D1，结论：NLP×TDA 远未拥挤）。
- Remaining gap: 几乎全部停留在分类/分析层面，未进入检索；D3 的负结果未被后续系统性地回应（什么样的任务/粒度上拓扑信号才有增益，是开放问题）。
- Possible rescue or differentiation route: 把拓扑信号用在「检索决策」而非「分类特征」——正好回应 D3 负结果并提出边界条件。
- How it affects the user's paper: D1 是定位「TDA 在 NLP 尚属早期」的直接证据；D3 是必须正面引用的负结果。

### Cluster 5: 图/网络的持久同调工具箱

- Representative papers: E1–E7。
- What this cluster already solves: 网络上的 PH 计算（加权/无权、动态、Morse 理论加速）、PH×图学习桥接、PH 评估 KG 补全（E7）。
- Remaining gap: 工具成熟但从未套用到 RAG 构建的实体图/块图上。
- How it affects the user's paper: 这是「拓扑不变量捕捉全局形状」设想的现成工具箱，方法部分可直接引用。

### Cluster 6: 可微拓扑 / 拓扑深度学习 + 拓扑×LLM

- Representative papers: F1–F4, G2–G3。
- What this cluster already solves: 拓扑损失进训练（F1/F3）、持久图向量化（F2）、TDL 路线图（F4）、LLM 潜空间拓扑诊断（G2）。
- Remaining gap: 没有工作把可微拓扑用于检索器/检索索引；LLM 拓扑分析集中在对抗鲁棒性，不在检索质量。
- How it affects the user's paper: F1/F2 提供「拓扑不变量可微化」的技术入口；G2 提供「拓扑签名作为模型诊断」的先例。

### Cluster 7（关键）: 拓扑 × RAG 直接交点

- Representative papers: G1（HPT-TRACE）；沾边：A6（树分层）、B3（T-Retriever）。
- What this cluster already solves: G1 已把「拓扑空间 + 层次划分树 + 证据路径求交」用于多查询 RAG 的 reranking，且强调不依赖 LLM 构建、构造高效。
- Remaining gap: 仅覆盖 reranking 一层；索引构建、语料诊断、检索失败预测、可解释性均未触及；且为在审稿件，方法细节与结果尚待正式版本核实。
- Possible rescue or differentiation route: ① 拓扑驱动的索引/组织层（持久性决定层级，对比 RAPTOR 的聚类相似度）；② 拓扑健康度诊断（GraphRAG 图的 PH ↔ 多跳 QA 成败相关）；③ 可微拓扑检索器。三条都留有位置，但必须引用 G1。
- How it affects the user's paper: 这是新颖性论证的第一道关：设想中最接近的既有工作。

## Opportunity Map

| Cluster | Status | Open gap | Possible direction | Evidence needed | Risk |
| --- | --- | --- | --- | --- | --- |
| 图 RAG 主线 | covered central claim | 图构建昂贵不稳、缺机制解释 | 拓扑作为图质量诊断信号 | 大规模相关性实验 | 直接做变体=红海 |
| GNN×RAG | crowded but open | GNN 只学局部消息传递，全局形状未显式建模 | 拓扑签名作 GNN 检索器先验 | 与 B1 的对照 | 差异化窗口收窄中 |
| 文本→图/复形 | covered central claim（分类任务内） | 未进入检索场景 | 复形上的检索结构 | 检索协议设计 | 需自建评测 |
| TDA×NLP | crowded but open（分析类）+ benchmark gap | 拓扑信号在何种任务/粒度有增益未解决（D3 负结果未回应） | 拓扑信号用于检索决策 | 消融+边界条件实验 | 沿用 D3 路线会复现负结果 |
| 网络 PH 工具箱 | 成熟（transferable） | 未套用到 RAG 图 | 直接迁移，贡献=问题定义 | 可扩展性（语料 10^5–10^6 块） | 无 |
| 拓扑×RAG 交点 | benchmark gap + mechanism gap（近空白） | 仅 reranking 被占（G1，在审） | 索引/组织/诊断/可解释层 | G1 正式版对比 | G1 后续版本可能扩展覆盖面 |
| 机制解释（为何图 RAG 有效） | theory/analysis gap | 无定量全局结构→检索质量理论 | PH 签名预测检索成败 | 因果/干预实验 | 或需自建 benchmark |

## Benchmark And Dataset Candidates

| Name | 链接/出处 | Task | Metrics | 备注 |
| --- | --- | --- | --- | --- |
| GraphRAG-Bench | OpenReview 收录记录 ◇ | 领域推理 | — | 专测图 RAG；引用前需核原文 |
| MuSiQue / 2WikiMultiHopQA | HippoRAG 系论文所用 | 多跳 QA | EM/F1 | 多跳检索标准评测（摘要级证据， HippoRAG 页面提及） |
| QuALITY | RAPTOR 论文所用 ✅ | 长文档全局 QA | 准确率 | RAPTOR 报告 GPT-4 +20% 绝对提升 |
| HotpotQA | 常用 | 多跳 QA | EM/F1 | 常规背景 |

## Citation And Positioning Cautions

- Claims that need direct citation: 「TDA 在 NLP 尚属早期」→ D1；「拓扑不变量刻画全局形状」→ E1/E2；「GNN 用于 RAG 检索」→ B1；「图 RAG 谱系」→ A1/A2/A3。
- Papers that may weaken novelty: G1（HPT-TRACE）——设想中最接近的占位者，必须引用并差异化；B1（GNN-RAG）——GNN 设想的最近邻；A6（RAPTOR）——若主张「层次化语料组织」，树结构已被占；D3——若主张「拓扑特征提升下游任务」，需先回应此负结果。
- Papers that only support background: C1、E1–E5、F1–F4。
- 证据分级提示：标 ◇ 的条目（G1 细节、B3、D5、GraphRAG-Bench 等）仅基于检索摘要，正式引用前必须打开原文；G3 建议暂不引用。
