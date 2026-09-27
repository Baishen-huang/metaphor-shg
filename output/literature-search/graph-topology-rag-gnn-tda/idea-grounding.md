# Idea-Grounding Packet

## Scope And Evidence Boundary

- Topic / seed: 将非结构化文本映射为图结构/高维拓扑空间；GNN 学习图表示；拓扑不变量（持久同调、Betti 数）捕捉语料全局形状；应用于 RAG。
- Search date: 2026-09-27
- Source-supported facts: 拓扑×RAG 的直接交点目前仅 1 篇在审稿件（HPT-TRACE，reranking 层）；GNN×RAG 有成熟方法（GNN-RAG）；图 RAG 主线有两篇高引综述；TDA×NLP 有 2024 综述（137 篇）且结论为「远未拥挤」；存在一条未回应的负结果（Michel 2017）。
- Searcher inferences: 拓扑不变量在 RAG 的「索引组织/诊断/可解释」层为空白；Michel 负结果的原因（任务与粒度不匹配）是可检验的。
- Unknowns: HPT-TRACE 正式版本与实验细节；拓扑特征在大规模语料上的计算成本上限。

## Evidence Cards

| Source | Supported observation | Reported limitation | Mechanism primitive | Protocol anchor | Transfer condition | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| HPT-TRACE（OpenReview 在审）◇ | 拓扑空间+分层划分树+证据路径求交已用于多查询 RAG reranking | 在审，细节未公开核实 | HPT 由自顶向下分裂聚类构建、不依赖 LLM | 多查询 RAG / reranking | 若换层（索引/诊断）则不冲突 | 中（摘要级） |
| Edge et al. 2024（GraphRAG）✅ | LLM 抽取实体图+社区层次摘要可答全语料级问题 | 构建成本高；社区=层次但非拓扑 | 图划分→层次摘要 | 全局 QA | 其「社区层次」可用持久性替代/对齐 | 高 |
| HippoRAG 2（2502.14802）✅ | PPR 图检索=非参数持续学习，多跳/联想任务领先 | 依赖 KG 抽取质量 | PPR on KG index | MuSiQue/2Wiki 等 | 拓扑先验可注入其排序信号 | 高 |
| GNN-RAG（2405.20139）✅ | GNN 图推理可直接产出检索候选 | 仅实体关系图；全局形状未建模 | GNN 打分→候选→LLM | KGQA | 拓扑特征作为 GNN 输入是新增量 | 高 |
| Uchendu & Le 2024/26 综述 ✅ | TDA×NLP 收录 137 篇、远落后于 CV；PH+Mapper 两条主线 | 综述确认的空白=检索方向 | PH/Mapper 特征提取 | — | NLP 采纳率低=定位证据 | 高 |
| Zhu 2013（IJCAI）✅ | 文本点云 PH 多尺度分析自 2013 年可行 | 停留在表示/分类 | 点云→VR 复形→PH | 文本表示 | 粒度从词级升到块级/语料级是自由度 | 高 |
| Michel et al. 2017 ✅ | PH 文档表示未带来分类增益（负结果） | 仅分类任务、文档级 | PH 签名作特征 | 文档分类 | 换用途（检索决策/诊断）需重做边界条件实验 | 高 |
| Hiraoka et al. JMLR 2024 ✅ | PH 信号可微分接入嵌入训练（word2vec 式） | 图嵌入场景，非文本检索 | PH 损失项 | 图嵌入基准 | 迁移到检索索引训练需自证 | 高 |

## Cross-Source Relations

| Source pair | Relation | Open gap or conflict | Why it matters | Evidence needed next |
| --- | --- | --- | --- | --- |
| Michel 2017 ↔ Hiraoka 2024 | 冲突后和解：分类无增益 vs 训练正则有增益 | 拓扑信号何时有效 | 决定「特征」还是「正则/信号」的路线选择 | 检索场景消融 |
| GraphRAG 社区层次 ↔ HPT-TRACE 划分树 | leaves-open：两种层次组织并存 | 持久性驱动的层次未被尝试 | 拓扑可成为层次构建的第三原则 | 与 RAPTOR/HPT 对照实验 |
| GNN-RAG ↔ 网络 PH 工具箱（E1–E6） | depends-on：工具现成，从未合流 | 拓扑签名作 GNN 输入 | 低成本新机制 | 小规模可行性实验 |
| HippoRAG 2 ↔ PH 评估 KG 补全（E7） | evaluated-by：PH 可评估图质量 | RAG 图的拓扑健康度诊断不存在 | 诊断/失败预测新问题 | 语料 PH ↔ QA 成败相关性 |

## Idea Constraints

- Already covered central claims: 图 RAG 变体（A 系列）；拓扑 RAG reranking（G1）；文本→图的 GNN 分类（C 系列）。
- Transferable mechanism primitives: VR/网络复形上的 PH（E1）、持久图向量化 PersLay（F2）、可微拓扑损失（F1/F3）、PPR 图检索（A4/A5）、分裂树划分（G1）。
- Protocols suitable for direct comparison: MuSiQue / 2WikiMultiHopQA / QuALITY + HippoRAG 2 / LightRAG / SubgraphRAG / RAPTOR 对照系。
- Stale or overcrowded routes: 新图 RAG 变体；「PH 特征做文本分类」（2013–2020 已做尽且有负结果）。
- Minimum viable research questions: ① GraphRAG 构建图的持久同调签名能否预测多跳检索成败（诊断型 MVRQ，直接回应机制 gap）？② 持久性驱动的块层次组织是否优于聚类相似度（RAPTOR 对照）？③ 拓扑签名作为 GNN 检索器先验是否带来增益（GNN-RAG 对照）？
