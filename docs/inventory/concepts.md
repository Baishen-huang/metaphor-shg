# 隐喻超超图项目 · 概念词典（concepts.md）

> **本文件要回答的问题**：`docs/inventory/_extracted.json` 里的 56 个类/别名只是**符号**，
> 不是**概念**。一个概念的价值不在它是否被写进代码，而在它**提出了什么、被什么检验、结论如何**。
> 本词典把「提出」与「成立」严格分开：**被证伪的概念同样入册**——它界定了设计空间。
>
> **口径**：所有公式均以**代码实现**为准（不采信文档表述），关键处给出实测复核记录。
> 已发现 3 处「文档 ≠ 代码」的实质分歧，均在对应条目下标注 `⚠️ 实现分歧`。
>
> **来源标注**：`自创` / `借用·认知语言学` / `借用·IR 文献` / `借用·外部系统对照`（VCP-RiverMemo）
> / `借用·图 RAG 文献`。
>
> 生成日期：2026-09-27 ｜ 代码基线：`metaphor_graph/`（main）

---

## 0. 汇总表

> 「是否在用」三档：**生产路径**（参与已上报指标/默认行为）｜**可选/分析**（开关或对照，默认关闭）
> ｜**退役/降级**（不再参与，或定位被降级）。

### 0.1 结构概念（14）

| # | 名称 | 来源 | 实证状态 | 是否在用 |
|---|---|---|---|---|
| S1 | 超超图 hyper-hypergraph / `MetaphorSHG` | 自创 | 表示成立；"层级性"部分被证伪为零结构贡献 | 生产路径（容器） |
| S2 | L0 触发词层 trigger-word layer | 借用·认知语言学（MIPVU 语言单位） | 成立（抽取的召回主通道） | 生产路径 |
| S3 | L1 映射超边 `MetaphorHyperedge` | 自创 | 成立；**信号载体**（H4：判别力来自 n 元共现） | 生产路径 |
| S4 | L1.5 跨 chunk 扩展超边 extended hyperedge | 借用·认知语言学（延伸比喻）+ 自创合并判据 | 成立但**限定价值域**（连贯文档）；A5 证明为 P3 的必要条件 | 生产路径（可关） |
| S5 | L2 框架超顶点 `MetaphorFrame`/`FrameSpec` | 借用·认知语言学（FrameNet/MetaNet frame） | 未独立验证；与 L1 等价（H4 关掉不变） | 生产路径（索引/可解释性） |
| S6 | L3 级联超超顶点 `MetaphorCascade`/`CascadeSpec` | 借用·认知语言学（cascade） | **零结构贡献**（全单例对照 MRR 逐位相同） | 生产路径（降级为组织/可解释性） |
| S7 | 喻底集合 ground set | 借用·认知语言学（ground） | 成立——**n 元性的载体**，被证明是判别信号来源 | 生产路径 |
| S8 | 成员端点 / 超边元数 member entities / arity | 自创（超图标准记号） | 成立；`avg_arity < 2.2` 触发"超边退化为普通边"告警 | 生产路径（健康度） |
| S9 | 关联矩阵 H incidence | 借用·图 RAG 文献（HGNN） | 实现正确，但只在 HGNN 内使用（而 HGNN 不在检索路径） | 可选/分析 |
| S10 | 证据链 Evidence / 支持度 support / 权威度 authority | 自创（知识管理） | 未验证；`evidence_coverage` 实测恒为 0（无人写入） | 可选（接口就绪、数据未接） |
| S11 | 冲突消解 resolve_conflict（authority/recent/vote/hybrid） | 自创 | 未验证（无调用方，无数据） | 可选/未接入 |
| S12 | 软删除 deprecated | 自创（知识演化） | 未验证（`deprecated_rate` 恒 0） | 可选/未接入 |
| S13 | 语境跨度 ChunkSpan | 自创 | 成立（L1.5 合并与溯源的基础） | 生产路径 |
| S14 | 方案 B：隐喻元图 `MetaphorMetagraph` + U-Retrieval | 借用·图 RAG 文献（MedGraphRAG U 型检索） | 未验证（仅 demo/单测） | 退役（论文只作对照提及） |

### 0.2 语言学概念（借用并操作化）（11）

| # | 名称 | 来源 | 实证状态 | 是否在用 |
|---|---|---|---|---|
| L1 | 概念隐喻理论 CMT | 借用·认知语言学 | 作为前提，未被检验 | 生产路径（框架设定） |
| L2 | 隐喻级联 cascade | 借用·认知语言学 | **构造规则度量中性**；99.2% 成员共享单一目标域 | 生产路径（降级） |
| L3 | 框架 frame | 借用·认知语言学 | 与 L1 等价（H4） | 生产路径 |
| L4 | MIPVU / MIPVU-lite | 借用·认知语言学 | 提示词口径成立（去掉 P1 飙至 28.9%）；MIPVU-lite 通道边际 +0.6pp | 生产路径 |
| L5 | 喻底 ground | 借用·认知语言学 | 见 S7 | 生产路径 |
| L6 | 扩展隐喻 / 延伸比喻 extended metaphor | 借用·认知语言学 | 密度假设成立（连贯文档 10×） | 生产路径 |
| L7 | 源域 / 目标域 source/target domain | 借用·认知语言学 | 成立（本体与特征的基本坐标） | 生产路径 |
| L8 | 语义域失谐 semantic incongruity（Wmatrix keyness） | 借用·认知语言学 + 语料库语言学 | 边际贡献仅 **+0.6pp**（LLM 在场时） | 生产路径（默认关闭） |
| L9 | 词化惯用语 lexicalized idiom | 借用·认知语言学 | 成立——扩展链精度的主要失败模式（"基础上""聚焦"） | 概念（无代码） |
| L10 | 自举触发词 + lift | 自创（IR 的 lift 统计量） | 成立但 train→test 泛化差；不过滤则 P1 飙到 60.5% | 生产路径 |
| L11 | 类型安全约束 type safety constraint + `source_type` | 自创（方案 §4.1.3） | **H1 证伪**：管结构正确性，不管精度（P1 效应恒 0） | 生产路径（降级为结构校验） |

### 0.3 度量概念（21）

| # | 名称 | 来源 | 实证状态 | 是否在用 |
|---|---|---|---|---|
| M1 | Ω 可观测泛函（Ω_E/Ω_N/Ω_F/completeness/regime） | 借用·外部系统对照（VCP-RiverMemo） | **证伪**：退化为 1-bit 触发词指示器（ρ=0.9949） | 可选/分析（不接检索） |
| M2 | 查询侧不变式 query-side invariant | 借用·外部系统对照 | 成立（API 形状保证，632/632 扰动 0 变化） | 生产路径（护栏） |
| M3 | S_query | 自创（gen3 单点修改） | AUC 提升真实（0.654→0.824）但**目标是定理**；控制集合大小后 AUC≈0.5 | 可选/分析 |
| M4 | S_log / S_struct | 自创（gen3 对照标量） | 无显著优势（64 组合全在 0.50–0.93，合成层不是元凶） | 可选/分析 |
| M5 | n_emergent / n_new_domains / n_reach（两种可达口径） | 自创 | **集合大小伪影**：控制尺寸后增量 AUC 0.4897（CI 覆盖 0.5） | 可选/分析 |
| M6 | StratifiedNormalizer（n_seed 分层 z） | 自创 | 有效作为检验工具；作为部署量无下游价值（ρ≈0.10） | 可选/分析 |
| M7 | `compose()` 四开关 | 自创（机制归因工具） | 工具成立；**但 `outer_zero` 是死开关** ⚠️ | 可选/分析 |
| M8 | 溯源可靠性 provenance reliability + `reliability_factor` | 借用·外部系统对照（封顶可靠度通道） | 机制实现正确，但**对 P1 数学上界为 0**；排序净增益为零 | 生产路径（默认开，floor=0.5） |
| M9 | 诚实覆盖率 honest coverage | 自创 | **成立且重要**：暴露 P2 覆盖率 22.4pp 注水 | 生产路径（需传 ontology） |
| M10 | 隐喻连贯度 metaphor_coherence | 自创（HGNN 检测器） | 全量 AUC 0.915 成立，但信号来自 **n 元共现**非层级；作为过滤器无效（52→52） | 可选/分析 |
| M11 | 图密度 Δ | 借用·图 RAG 文献（HyperRAG） | 实现正确；生产图实测 Δ≈2.58（mid 档） | 生产路径 |
| M12 | 超边元数 avg_arity / 孤立端点率 orphan_rate / 层级覆盖率 hierarchy_coverage | 自创（运维信号） | 成立；生产图 avg_arity≈3.92、orphan≈0.64 | 生产路径 |
| M13 | 证据链覆盖率 / 软删除占比 / 退化边占比 | 自创 | 前两者恒 0（未接入）；退化边占比 ≈24% | 生产路径（部分空转） |
| M14 | 7 维特征（sem/struct/clue/type/same_frame/same_cascade/ground_jaccard） | 自创（部分借用 HyperRAG 的 DDE 思路） | 仅 `sem` 有真实判别力（AUC 0.628）；其余 CI 接近 0.5 | 生产路径 |
| M15 | 人工权重 HAND_WEIGHTS / LEGACY | 自创 | **原权重错配**（struct 过权 37–49×）；重标定 +5.7pp | 生产路径（已重标定） |
| M16 | RRF 融合 | 借用·IR 文献 | 实现正确（k=60）；未被任何已上报指标使用 | 可选（demo/单测） |
| M17 | 链密度（链/百 L1）+ 含链文档占比 | 自创 | 成立：连贯文档 6.3% vs 独立短句 0.6%（10×） | 生产路径 |
| M18 | P1 字面误判率 / 召回 / 精确率 / F1 | 借用·评测惯例 | P1 是**句级布尔存在性指标**——这一定义导致 M8 结构性失效 | 生产路径 |
| M19 | MRR / Hits@k / Recall@k + 随机基线 + MRR 量程 | 借用·IR 文献 | 成立；随机基线是发现"平凡饱和"的关键工具 | 生产路径 |
| M20 | 全量 AUC（`_auc_full`，并列计 0.5） | 借用·IR/ML 文献 | **成立且取代了配对准确率**（n=20 功效不足，结论会抖动翻转） | 生产路径（H4 主指标） |
| M21 | targeting excess（命中率 / 随机期望） | 自创 | **子集内弱真实效应**（1.73–1.78×），全样本与尺寸匹配对照同级 | 可选/分析 |

### 0.4 工程概念（24）

| # | 名称 | 来源 | 实证状态 | 是否在用 |
|---|---|---|---|---|
| E1 | 双防线 double defense（阈值 0.85 + refine） | 自创 | **成立且缺一不可**：仅阈值 P1 14.5% → 加 refine 9.2% | 生产路径 |
| E2 | 双段管线 two-stage pipeline | 借用·外部系统对照（宽松生成→严格过滤） | **成立**：精度 16.7%→63.6%（约 4×），密度 10× 保住 | 生产路径 |
| E3 | 级联查表 cascade lookup | 自创 | 成本成立（~20 vs ~187 次/千边）；**但覆盖率归因需改为"查表 + 目标域兜底"** | 生产路径 |
| E4 | 孤儿框架兜底 `_ensure_cascades` / `C_ADHOC_*` | 自创 | 覆盖率 0.767→1.000，但**是注水来源**；可换规则 | 生产路径（默认 target） |
| E5 | 自适应阈值 AdaptiveThreshold + 密度分档 | 借用·图 RAG 文献（HyperRAG） | **中性**：A8 实测稀疏/稠密图均无差异 | 生产路径（默认开，无实测收益） |
| E6 | 上下文预算 50/30/20 `ContextBudget` | 借用·图 RAG 文献（HyperRAG） | 未做定量验证；打包消融被 judge 敏感性阻断 | 生产路径（生成层） |
| E7 | 候选超集 candidate superset | 借用·外部系统对照（RiverMemo 六路） | 概念成立（三通道 = 本项目版本） | 概念（无同名代码） |
| E8 | 构造锚定 construction anchoring | 自创（诊断）；概念对应 IR 的 pooling bias | **成立且是本项目最重要的方法论发现**：抬高 ≈+0.66 MRR | 概念 + 审计工具 |
| E9 | 去锚定口径 de-anchored setting | 自创 | 成立：deanchor MRR 0.2330 = 随机 34×（架构有效），但训练增益反转 | 生产路径（评测） |
| E10 | pooling bias | 借用·IR 文献（2007） | 成立（诊断标签） | 概念 |
| E11 | 公平性声明 fairness declaration + `audit_fairness` | 自创（机器检查） | 成立：发现 3 处同类缺陷；工具自身踩过注释误报坑 | 生产路径（护栏） |
| E12 | 三通道抽取 three-channel extraction | 自创 | 成立：LLM 开放发现把召回 9.7%→69.6%，P1 不升（帕累托外推） | 生产路径 |
| E13 | 三通路检索 three-pathway retrieval | 自创 | **相对成立，绝对下修**：改写型 0.1918 vs 级联 0.0206 vs 字面 0.000 | 生产路径 |
| E14 | 语义回退 semantic_fallback | 借用·图 RAG 文献（U-Retrieval 自顶向下） | 级联通路 Recall 0.020→0.042 翻倍但仍低；默认关闭 | 可选（默认关） |
| E15 | 静默失败防护（`LLMFatalError`/`EmbedderFatalError`/`Neo4jFatalError`） | 自创 | 成立：曾因 402 被"优雅降级"吞掉而产出全错结论 | 生产路径 |
| E16 | 确定性 id（md5 稳定 id） | 自创 | 成立：随机 id 曾导致缓存重放对不上号 | 生产路径 |
| E17 | 缓存重放 cache replay / 零 API 复现 | 自创（工程纪律） | 成立：全部表格可零费用重放 | 生产路径 |
| E18 | 单测护栏 regression guard | 自创 | 成立（116→224 项）；但 222 项全绿仍漏掉合并回归 → 补 CLI/导入护栏 | 生产路径 |
| E19 | 特征漂移 feature drift + 单一真源 | 自创 | **真实 bug 已修**：同一候选在两条路径得 type=1.0 vs 0.0 | 生产路径 |
| E20 | 弱监督（refine 否决负样本）`build_weak_refine_set` | 自创 | 机制成立（clue AUC 1.0→0.931、leakage 136→23）；**排序增益未证实**（−0.013） | 可选 |
| E21 | 评测自检 `trivial_separators` / `leakage_report` | 自创 | 成立（抓住了 self-implementation 的评测） | 生产路径（工具） |
| E22 | 源项/阻尼 α/ε（HGNN dynamics） | 借用·外部系统对照（resolvent 谱性质） | **证伪**：加源项不打破 flat/HGNN 平局（\|ΔAUC\|≤0.005） | 可选（默认 α=1/ε=0 逐位兼容） |
| E23 | 触发词 lift 过滤 | 借用·IR 文献（lift） | 成立：min_lift=3.0，不过滤 P1 飙到 60.5% | 生产路径 |
| E24 | 本体清洗三规则（自环/喻底明喻标记/tier 分层） | 自创 | **指标中性**的纯质量提升；core-only 召回 −1.2pp | 生产路径 |

### 0.5 评测概念（12）

| # | 名称 | 来源 | 实证状态 | 是否在用 |
|---|---|---|---|---|
| T1 | 改写型 vs 重叠型查询 | 自创 | 成立且**是本项目最锋利的自变量**：相差 5.2×–7.8× | 生产路径 |
| T2 | 非构造金标（已证伪的标签） | 自创（后被自己证伪） | ❌ **标签不成立**：632/632 金标含产出 chunk，97.9% 只含它 | 退役（论文须改写） |
| T3 | 平凡饱和 trivial saturation | 借用·IR 文献（test collection 规模不足） | 成立：池 ≤10 → Hits@10 恒 1.000 | 概念 + 检查项 |
| T4 | 全量 AUC | 见 M20 | 成立 | 生产路径 |
| T5 | 泄漏天花板 clue AUC≈1.0 | 自创（训练信号病理） | 成立且已定位机制；弱监督缓解但未消除 | 生产路径（自检项） |
| T6 | 四族对比 four-family comparison | 自创 | 成立：{重叠型,改写型}×{anchored,deanchor} 是训练增益结论的必要分辨率 | 生产路径 |
| T7 | 程序化红线 filter_violations | 自创 | 成立：改写禁用触发词/源域/目标域（违规剔除 26.7%） | 生产路径 |
| T8 | 诊疗集 diagnostic set | 自创（诚实标注的小样本） | 成立但**不可外推**（P3 F1=1.000 是精选语料） | 生产路径（机制验证） |
| T9 | LLM-as-judge 敏感性 | 自创（实测发现） | 成立：同一查询集，deepseek 判对照胜 6:1，glm 判当前打包最优 → **结论随 judge 反转** | 概念（方法论结论） |
| T10 | 金标稳健性双协议审核（κ） | 借用·标注一致性文献 | 成立：跨模型 κ=0.965、同模型换序 κ=0.912 | 生产路径（附录 C） |
| T11 | 池外文档比例 pool-external rate | 借用·IR 文献（SIGIR 1998/2007 要求的自审字段） | 成立（评测自我审计字段） | 生产路径 |
| T12 | 构造金标一致性 96.8% | 自创 | 成立但**不足以排除锚定**（见 T2） | 退役（被 T2 取代） |

---

## 1. 结构概念

### S1 超超图 hyper-hypergraph / `MetaphorSHG`

- **位置**：`metaphor_graph/models.py:167`（`MetaphorSHG`）；`论文初稿.md` §3.1；`README.md` 开篇
- **定义**：四层嵌套的图结构 L0→L1→L1.5→L2→L3，其中 L2 是超顶点（hypervertex，一组 L1 超边）、
  L3 是超超顶点（hyper-hypervertex，一组 L2 超顶点）。形式化为
  `SHG = (E, F, C)`，`E` = L1/L1.5 超边集，`F` = L2 框架，`C` = L3 级联。
- **动机**：二元三元组在隐喻场景下有两重失真——(a) 喻底是**集合**，拆成二元边会割裂语义整体性
  并引发路径爆炸；(b) 层级（基础隐喻→一般隐喻→级联）是认知语言学的**自然结构**，二元图无法表达
  「超顶点的超顶点」。
- **来源**：自创（把 CMT/MetaNet 的层级结构翻译为超超图数学结构）。
- **实证**：表示层成立（能装下 n 元与层级）；但**「层级性」的收益被证伪**——
  H4 显示关掉框架/级联判别力不变（全量 AUC 0.915 vs 0.910），
  L3 全单例对照与生产配置 MRR 逐位相同（0.5025）。
  论文摘要因此把主张改为「n 元性承担可检验信号，层级性价值在检索组织与可解释性」。
- **状态**：生产路径（作为容器对象），但**两半的实证地位不对称**，这是本项目最重要的边界之一。

### S2 L0 触发词层 trigger-word layer

- **位置**：`models.py:5`（注释定义）；`ontology.CascadeOntology._trigger_index:366`
- **定义**：隐喻的**语言形式**层，即"泥潭""发条"这类可被字符串匹配的触发词。查询侧的一切结构激活
  都从这一层开始：`[t for t in ont._trigger_index if t in query]`。
- **动机**：需要一个不依赖 LLM 的**免费、确定性、可复现**入口，也是降本的核心来源。
- **来源**：借用·认知语言学（MIPVU 的「语言单位切分」步骤的轻量操作化）。
- **实证**：**成立且是整个系统的天花板与瓶颈**——Ω 相对 n_seed 的 ρ=0.9949；
  「触发词命中数」被判定为查询侧标量的天花板（gen3 §7.2）；
  改写型查询切断触发词后语义通路从 0.9200 跌到 0.1183。
- **状态**：生产路径。

### S3 L1 映射超边 `MetaphorHyperedge`

- **位置**：`models.py:66`；`member_entities:104`；`describe:108`；`authority:121`；`support:127`
- **定义**：一条隐喻映射 = 一条超边，携带
  `(id, source_domain, target_domain, ground: List[str], triggers: List[str], chunk_spans,
  cascade_id, frame_id, novelty, sentiment, confidence, source_type,
  provenance_reliability, is_extended, layer, evidence, extractor_version, deprecated)`。
  超边性来自 `member_entities = [source, target] + ground`（≥3 个端点）。
- **动机**：把"时间是金钱"这类映射的**喻底集合**整体保留在一条边里，而不是拆成
  `时间-稀缺`、`时间-可浪费`… 一堆二元边。
- **来源**：自创（结构），喻底概念借用·认知语言学。
- **实证**：**成立，且被证明是信号载体**——H4 分解：仅 L1 超边传播 0.950 ≈ 完整跨层 0.950
  ≫ 原始嵌入 0.550（全量 AUC）。
- **状态**：生产路径。

### S4 L1.5 跨 chunk 扩展超边 extended hyperedge

- **位置**：`extended.py:36`（`link_extended_metaphors`）；`models.py:90`（`is_extended`）
- **定义**：合并判据（**逐字**，`extended.py:71-77`）：
  ```
  同 frame_id ∧ 同 source_domain ∧ gap < max_gap(默认3) ∧ |ground_a ∩ ground_b| ≥ 1
  可选加强判据 continuity="vehicle_repeat"：
      (同一触发词跨 chunk 词面复现) ∨ (|ground_a ∩ ground_b| ≥ 2)
  ```
  合并产物的 `provenance_reliability = min(链上各边)`（**退化边不得借合并"洗白"**）。
  链式合并为贪心、按 chunk 顺序。
- **动机**：延伸比喻的延伸部分是比喻的有机组成部分；同一源域隐喻在文本中成簇出现即构成扩展隐喻。
  填补向量检索在延伸隐喻上的结构性盲区。
- **来源**：借用·认知语言学（扩展隐喻）+ 自创（四判据的可执行化）。
- **实证**：**成立但严格限定价值域**——
  ① A5 消融：关掉扩展边后 P3 F1 从 1.000 → 0.000（**必要条件**证明）；
  ② 连贯文档语料上链密度 6.3 条/百 L1、30% 文档含链 = 独立短句语料的 **10×**；
  ③ 但在 CCL2018 独立短句上天然稀疏（5 条/110 伪文档），**不主张句级泛化增益**；
  ④ 候选链严格口径精度仅 16.7% → 必须靠第二段语义校验（见 E2）。
- **状态**：生产路径（`builder.use_extended` 默认 True，可关）。

### S5 L2 框架超顶点 `MetaphorFrame` / `FrameSpec`

- **位置**：`models.py:133`（运行时对象）；`ontology.py:137`（本体条目 `FrameSpec`）
- **定义**：一般隐喻 = 超顶点 = **L1 超边的类型化子集**，按框架分组。
  `FrameSpec` 携带 `mapping_type`（映射到 `TYPE_CONSTRAINTS` 的键）、`source_type`、
  `ground`（典型喻底）、`triggers`、`support`、`tier`。
- **动机**：把 L1 实例抽象成可复用的类型，是 L3 归属与类型安全约束的载体。
- **来源**：借用·认知语言学（FrameNet / MetaNet frame）。
- **实证**：**未独立验证，且 H4 显示与 L1 等价**——"仅 L1 超边（无框架/级联）"的
  全量 AUC 0.910 vs 完整跨层 0.915（同一批样本上配对准确率 0.950 = 0.950）。
- **状态**：生产路径（作为索引层与类型约束的宿主），但**不承担检测/排序信号**。

### S6 L3 级联超超顶点 `MetaphorCascade` / `CascadeSpec`

- **位置**：`models.py:148`（`MetaphorCascade`，docstring 明确"是认知语言学发现的自然结构，
  而非工程构造"）；`ontology.py:155`（`CascadeSpec`）
- **定义**：隐喻级联 = 超超顶点 = L2 框架的集合，围绕同一目标概念组织，共同出现。
- **动机**：CMT 的层级性主张的可执行化；也是跨域检索的跳板（`member_frames → targets`）。
- **来源**：借用·认知语言学（cascade）。
- **实证**：❌ **零结构贡献**（本项目最干净的负面结果之一）：
  - 生产本体 758 个级联中 **752（99.2%）成员共享单一目标域**，规模中位 **1**、**54.4% 单例**；
  - **全单例对照**（每条边唯一 `cascade_id`，结构上最退化）与生产配置 MRR **逐位相同 0.5025**；
    只有彻底移除 L3 归属才降到 **0.4681（−0.034）**；
  - 唯一因果通道是 `cascade_id` 非空这一**布尔位**（被 `struct` 特征读到），不是分组质量；
  - 换规则（source / ground / source_type）使跨目标域率 0.8%→51.6%，但**不移动任何主指标**。
- **状态**：生产路径但**定位已降级**为"检索组织与可解释性"（`组件处置决策.md` §2）。

### S7 喻底集合 ground set

- **位置**：`models.py:76`（`ground: List[str]`）；`ontology_clean.clean_ground:99`
- **定义**：一条隐喻映射中被强调的**共有属性集合**（"时间是金钱"的 ground = 稀缺、可花费、
  可浪费、有预算、可投资）。是超边 n 元性的来源。
- **动机**：`MetaphorHyperedge` docstring：「喻底是集合而非单值——这正是超边的定义特征。
  强行拆成二元边会割裂语义整体性并引发路径爆炸」。
- **来源**：借用·认知语言学（ground / 喻底）。
- **实证**：**成立，且是判别信号的实际载体**——
  ① H4：信号来自 n 元喻底共现而非层级传播；
  ② `ground_jaccard` 是 7 维特征中仅次于 `sem` 的弱正向维（配对 AUC 0.530）；
  ③ 清洗规则发现 50 处喻底被明喻标记（"如/像/似/般"）污染，说明抽取端易混入非喻底词。
- **状态**：生产路径。

### S8 成员端点 / 超边元数 member entities / arity

- **位置**：`models.py:104`；`health.py:149`（`arities = [len(set(e.member_entities))]`）
- **定义**：`member_entities = [source_domain, target_domain] + ground`（**未去重**）；
  元数 arity 取 `len(set(member_entities))`。
- **动机**：超图的关联矩阵与消息传递需要端点列表；arity 是"超边是否已退化为普通边"的运维信号。
- **来源**：自创（超图标准记号的操作化）。
- **实证**：成立。实测生产图 `avg_arity ≈ 3.92`（>2.2 门槛，健康）；
  `health.py` 在 `<2.2` 时告警"喻底集合未抽出，超图表示失去意义"。
  ⚠️ **实现细节**：`member_entities` 不去重，当 `source_domain ∈ ground`（生产本体
  **19.4%** 的框架如此，实测）时会产生重复端点——见 S9 的实测分歧。
- **状态**：生产路径。

### S9 关联矩阵 H incidence matrix

- **位置**：`models.py:174`（`MetaphorSHG.incidence`）；`hgnn.py:158`
- **定义**：`H[i, j] = 1` iff 端点 i 属于超边 j；形状 `(|nodes|, |edges|)`。
- **动机**：HGNN 的两步消息传递（节点→超边→节点）的矩阵形式；也是"谱性质"分析的入口。
- **来源**：借用·图 RAG 文献（HGNN / HyperC2Net）。
- **实证**：⚠️ **`_conv` 与 `propagation_matrix()` 在存在重复端点时不严格等价**（实测分歧）：
  构造一个 `source_domain ∈ ground` 的超边，两者 maxdiff = **0.048**；
  真实 60 句图上（68 边中 14 条含重复端点，20.6%）maxdiff = **0.042**；
  无重复端点时 maxdiff = 0（单测 `test_propagation_matrix_matches_conv` 用的是无重复的
  测试图，故未捕获）。
  原因：`_conv` 的循环把重复成员**重复累加**，而 `propagation_matrix` 构造的 `H` 每格只记 1。
  影响面：`propagation_matrix()` 只被单测与谱分析使用，**不在检索路径**，故不污染已上报数字。
- **状态**：可选/分析。

### S10 证据链 Evidence / 支持度 support / 权威度 authority

- **位置**：`models.py:24`（`Evidence`）、`:121`（`authority`）、`:127`（`support`）、`:212`（`merge_evidence`）
- **定义**：`Evidence = (chunk_id, doc_id, timestamp, authority ∈[0,1], extractor_version, snippet)`。
  `authority()` = 证据权威度均值（无证据回落 0.5）；`support()` = 独立 `chunk_id` 条数（无证据为 1）。
- **动机**：docstring 原话——「标量只能回答『这次抽取有多确定』，回答不了『两条矛盾的映射信哪个』」。
  证据链让超边可审计、可比较、可按权威度/时间/票数消解。
- **来源**：自创（知识管理/演化治理）。
- **实证**：**未验证**——`health.evidence_coverage` 实测恒为 **0.0**（`extractor` 从不写 `evidence`），
  并触发告警"超边不可溯源，冲突消解无依据"。接口就绪，数据未接。
- **状态**：可选（接口存在，生产路径不写入）。

### S11 冲突消解 resolve_conflict

- **位置**：`models.py:227`
- **定义**：在互相矛盾的超边中选胜者，四种策略：
  ```
  authority : argmax (authority(e), support(e))
  recent    : argmax (0.5^(age/half_life), authority(e))   age = 最新证据的天数, half_life=365d
  vote      : argmax (support(e), authority(e))
  hybrid    : argmax (authority(e) × 0.5^(age/half_life) × log1p(support(e)))   ← 默认
  ```
  **刻意不使用 `confidence` 决胜**——跨 `extractor_version` 的置信度不可比。
- **动机**：知识会演化，同一映射可能被多条互相矛盾的证据支持。
- **来源**：自创。
- **实证**：未验证（无生产调用方；与 S10 同一缺口）。
- **状态**：可选/未接入。

### S12 软删除 deprecated

- **位置**：`models.py:95`；`retrieval.py:106`（`live_edges`）；`health.py:197`
- **定义**：`deprecated=True` 的超边保留在图里（保溯源）但不参与检索。
- **动机**：知识时效治理——"删掉就丢了证据链"。
- **来源**：自创。
- **实证**：未验证（`deprecated_rate` 生产恒 0，无写入方）。
- **状态**：可选/未接入。

### S13 语境跨度 ChunkSpan

- **位置**：`models.py:48`
- **定义**：`(chunk_id, start, end, text, doc_id)`——一个隐喻片段在原文中的字符级定位。
  `chunk_id` 供 L1.5 判断"跨 chunk"，`start/end` 供高亮与溯源。
- **动机**：扩展隐喻合并判据需要"间距"这个几何量；溯源需要字符偏移。
- **来源**：自创。
- **实证**：成立（L1.5 与 chunk 级排序的基础设施）。
- **状态**：生产路径。

### S14 方案 B：隐喻元图 `MetaphorMetagraph` + U-Retrieval

- **位置**：`metagraph.py:43`（三层元图）、`:87`（`MetaphorURetrieval`）
- **定义**：L0 chunk 级隐喻子图（触发→映射→框架）→ L1 文档级图 → L2 主题级图（按级联聚类）。
  U-Retrieval：检测触发词 → 自顶向下从级联匹配 → 逐层下钻 → 用目标域召回 chunk →
  自底向上用框架约束精炼。
- **动机**：方案 A（超超图）之外的对照实现，直接移植 MedGraphRAG 的三层图谱 + U 型检索，
  把"医学标签"换成"隐喻级联/框架标签"。
- **来源**：借用·图 RAG 文献（MedGraphRAG）。
- **实证**：未验证（只在 `demo.py` 与单测中出现；论文只在基线表 B5 列为"已实现的对照"）。
- **状态**：**退役/降级**——论文中不参与任何已上报数字。

---

## 2. 语言学概念（借用并操作化）

### L1 概念隐喻理论 CMT

- **位置**：`论文初稿.md` §1、§2；`README.md` 开篇
- **定义**：人们用具体概念（源域）理解抽象概念（目标域），且映射系统性地层级组织为
  一般隐喻与隐喻级联（Lakoff & Johnson 1980 / Kövecses / MetaNet）。
- **动机**：整个项目的**前提假设**。
- **来源**：借用·认知语言学。
- **实证**：作为前提未被检验；但 CMT 的**两个推论被分别检验且结论相反**——
  「n 元映射」成立（喻底集合是信号载体），「层级组织对检索有增益」证伪（L3 零结构贡献）。
- **状态**：生产路径（框架设定）。

### L2 隐喻级联 cascade

- **位置**：`models.py:148`；`ontology.py:155`；`cascade_rules.py:45`
- **定义**：预先存在的、层级组织好的基础隐喻与一般隐喻的**打包集合**，它们共同出现。
  构造规则共 7 条可选（`cascade_rules.CASCADE_RULES`）：
  `json`（默认，原样载入）｜`target`（按目标域，= JSON 的构造规则）｜`source`（按源域，
  经典 cascade 形态）｜`ground`（按喻底 Jaccard ≥0.34 连通分量）｜`metanet`（种子级联保留 +
  其余按 source）｜`source_type`（按 16 个喻体大类）｜`none`（L3 消融）。
- **动机**：级联是认知语言学发现的自然结构，不是工程聚类——这是"语言学合法性"主张的来源。
- **来源**：借用·认知语言学（MetaNet cascades）。
- **实证**：**构造规则度量中性**（见 S6）。另：同一"按目标域分组"规则被**实现了四遍**
  （`llm_ontology.py`、`ontology_clean.rebuild_cascades`、`builder._ensure_cascades` ×2），
  这是缺陷扩散的机制原因。
- **状态**：生产路径（默认 `json`）。

### L3 框架 frame

- **位置**：`ontology.py:137`；`metanet_migrate.py`（FrameNet 框架名字段）
- **定义**：一般隐喻的命名单位（如 `OBSTACLE_IS_TERRAIN`），带 `source_frame`/`target_frame`
  （FrameNet 名，如 `Terrain`/`Difficulty`）。
- **来源**：借用·认知语言学。
- **实证**：见 S5。
- **状态**：生产路径。

### L4 MIPVU / MIPVU-lite

- **位置**：`mipvu.py:30`（`MARKERS`）、`:63`（`mipvu_candidates`）；`extractor.py` 提示词
- **定义**：MIPVU 判据 = 「基本义 ≠ 语境义」+ 三类排除项。本项目的两条操作化：
  ① **提示词口径**：写进 LLM refine/校验的提示词；② **MIPVU-lite 通道**：对 chunk 分词，
  给内容词打 USAS 风格语义域，用「等比标记邻近」（是/像/如/似/若 + 复合词，±2 token 窗口）
  或「语义失谐 + 稀有」（`incongruity_score ≥ 0.6` 且域内 count ≤1）产出候选。
- **动机**：不依赖触发词表的第二条候选通道，突破"触发词天花板"。
- **来源**：借用·认知语言学（MIPVU）+ 语料库语言学（Wmatrix/USAS）。
- **实证**：① 提示词口径**成立**——去掉 MIPVU 判据 P1 飙至 28.9%；
  ② MIPVU-lite 通道**边际贡献仅 +0.6pp**（LLM 在场时），远低于纯规则配置下的估计；
  ③ 曾有一个真实 bug：`mipvu.py:91` 把整条通道门控在 **6 个硬编码级联 ID** 上，
  任何替换级联构造规则的实验都会**静默关掉整条通道**（丢 7 条 L1 边）——已修为
  「框架存在 + 框架有级联归属」。
- **状态**：提示词口径生产路径；MIPVU-lite 通道默认关闭（`use_semfield=False`）。

### L5 喻底 ground

- 见 S7。

### L6 扩展隐喻 / 延伸比喻 extended metaphor

- **位置**：`extended.py:1-10`（语言学依据）
- **定义**：同一源域的隐喻表达跨段落持续出现、共同建构一个目标概念。
- **动机**：docstring 原话——「延伸比喻的延伸部分是比喻的有机组成部分，没有它绝大多数比喻
  根本不能成立」。
- **来源**：借用·认知语言学。
- **实证**：密度假设成立（10×）；但**判据的语言学充分性不足**——
  失败模式是「词化惯用语（"基础上""聚焦"）被计为隐喻提及」与「单点隐喻相邻重复即被合并」，
  文本级信号区分不了，必须语义级校验（E2）。
- **状态**：生产路径。

### L7 源域 / 目标域 source / target domain

- **位置**：`models.py:74-75`
- **定义**：隐喻的两个端点概念域（如 `地形 → 项目困境`）。
- **来源**：借用·认知语言学。
- **实证**：成立（本体、特征、检索都以它为坐标）。但**端点带角色**这一事实导致
  「不能直接照搬 HyperRAG 的 DDE——它的伪三元组展开假设端点同质」（`training.py` docstring），
  催生了 `same_frame`/`same_cascade`/`ground_jaccard` 三个"角色感知结构信号"（M14）。
- **状态**：生产路径。

### L8 语义域失谐 semantic incongruity（Wmatrix keyness）

- **位置**：`semfield.py:30`（`FIELDS`）、`:49`（`FIELD_TO_CASCADE`）、`:57`（`FIELD_TO_FRAME`）；
  `mipvu.py:114`（判据 b）
- **定义**：候选判据 = `词域 ≠ chunk 主导语义域` ∧ `该域词在 chunk 中 count ≤ 1`
  ∧ `incongruity_score ≥ 0.6`。域内字面护栏：同域词 ≥2 且该域即语篇主导域 → 跳过。
  语义域 → 级联/框架的桥接是**写死的映射表**（6 个域）。
- **动机**：用 USAS 风格语义场替代英文 Wmatrix（中文不可直接用），且语义场与级联本体的
  `source_domain` 同源（本体 ground 词表本来就是语义场种子）。
- **来源**：借用·认知语言学 + 语料库语言学。
- **实证**：边际贡献 **+0.6pp**（12.4% − 11.8%），远低于预期。桥接表的 6 个域也带来
  「通道被级联 ID 门控」的 bug（见 L4）。
- **状态**：生产路径但**默认关闭**（`use_semfield=False`）。

### L9 词化惯用语 lexicalized idiom

- **位置**：`论文初稿.md` §6.6；`evaluate_chain_quality.py`
- **定义**：已词汇化、不再有隐喻解读的固定表达（"基础上""聚焦""扎根"）。
- **动机**：解释扩展链精度只有 16.7% 的主要失败模式。
- **来源**：借用·认知语言学。
- **实证**：成立。**重要结论**：词化惯用语与真隐喻的判别信息在**语境级语义**中——
  词面信号（触发词复现/喻底交集≥2）与图连贯度（`metaphor_coherence` 中位 0.820，
  阈值 0.5 保留 52/52）**都不可见**，只有读得懂上下文的 LLM 能判别。
- **状态**：概念（无代码，但是 E2 的设计依据）。

### L10 自举触发词 + lift

- **位置**：`bootstrap_triggers.py`；`llm_ontology.filter_triggers_by_lift:241`
- **定义**：
  ```
  lift(w) = (df_met(w) / (n_met + ε)) / (df_neu(w) / (n_neu + ε) + ε)
  保留条件：df_met(w) ≥ min_df(=2) 且 lift ≥ min_lift(=3.0)   （动词通道阈值 20）
  ```
  **只用 train.xml 标注**计算（用测试集挑触发词属于标签泄漏）。
- **动机**：种子本体的触发词是"动词型"（推进/攻击/沸腾），对中文「X是Y/X像Y」式
  **名词喻体**（舞台/宝石/泥潭）覆盖极差 → 召回 <5%。用真实标注数据挖高频喻体回填，
  是成本最低的自举手段。
- **来源**：自创（方法）+ 借用·IR 文献（lift 统计量）。
- **实证**：① 召回从 3.1% → 7.6%（+MetaNet 迁移 + 自举模式串）；
  ② **不过滤则 P1 飙到 60.5%**（门槛 15%）——"自举反而毁掉规则侧"；
  ③ train→test 泛化差：召回涨 4.5 倍、误判同步涨 4 倍；**自举的真正价值在框架/级联结构**，
  不在触发词本身（A4：去掉自举本体召回仅 −1.8pp）。
- **状态**：生产路径。

### L11 类型安全约束 type safety constraint + `source_type`

- **位置**：`ontology.py:88`（`TYPE_CONSTRAINTS`）、`:30`（`_SOURCE_TYPE_RULES`）、
  `:70`（`infer_source_type`）、`:409`（`type_valid`）；`extractor._type_coherent:126`
- **定义**：`source_type(源域类型) → 允许出现的映射类型集合`；
  `type_valid(st, mt) ⟺ mt ∈ TYPE_CONSTRAINTS.get(st, [])`。类型不匹配 → 大概率字面误判，丢弃。
- **动机**：方案 §4.1.3 的"结构化过滤器，不依赖 LLM 判断"——原本被寄望为 P1 硬门槛的主要保障。
- **来源**：自创（方案 §4.1.3）。
- **实证**：❌ **H1 证伪，且是结构性的**：
  - 修好两处前置缺陷后（`source_type` 从 98.6% 全是 `GENERIC_VEHICLE` 降到 32.8%；
    新增类型连贯性检查），实测**枚举约束拦 0 个、连贯性检查拦 24 个，P1 纹丝不动（0.092）**；
  - 根因：连贯性检查拒绝的是"绑定到某个框架"，**候选并没有被丢弃**——它退化为临时框架
    `F_LLM_*` 后照样产出超边。要让它影响 P1 就必须丢弃候选，那等于关掉开放发现
    （开放发现贡献 +55.8pp 召回）；
  - 更深一层：**P1 是句级布尔存在性指标**，而类型约束只作用于"挂哪个框架"，
    数学上界就是 0。
- **状态**：生产路径但**定位已降级**为"保证 L2/L3 结构正确性与跨框架一致性"；
  其可观测接口变成 `type_reliability_of`（见 M8）。

---

## 3. 度量概念

### M1 Ω 可观测泛函（Ω_E / Ω_N / Ω_F / completeness / regime）

- **位置**：`observability.py:229`（`measure`）、`:51-56`（常量）、`:60`（`QueryObservability`）
- **定义**（**逐字对齐代码**）：
  ```
  Ω_E  = min(1, n_frames / n_seed)                      # 点亮的框架数 / 种子触发词数
  Ω_N  = min(1, |emergent| / n_seed)                     # 级联涌现目标域数 / 种子触发词数
         emergent = (⋃_{cid ∈ cascades} ⋃_{f ∈ member_frames(cid)} target(f)) − direct_targets
  Ω_F  = normalized_entropy(flow)                        # flow[fid] = 该框架被几个触发词命中
         无正流量 → 0.0 ； 仅一条正流量 → 0.5（约定值） ； n>1 → H/log2(n)
  Ω_geo = (max(Ω_E,ε) · max(Ω_N,ε) · max(Ω_F,ε))^(1/3)   ε = EPS = 1e-3
  comp  = min(1, Σ_t len(t)·count(t, query) / len(query))  # 观测完备度
  Ω     = Ω_geo × comp
  特判：n_seed == 0 或 n_frames == 0 → Ω = Ω_geo = Ω_E = Ω_N = Ω_F = comp = 0
  regime: collapsed (n_frames≤0 ∨ Ω≤0) / sparse (Ω < 0.5) / dense (Ω ≥ 0.5)
  ```
  **实测复核**（`'项目推进不动，陷在泥潭里'`）：Ω=0.2646、Ω_geo=0.7937、
  Ω_E=1.0、Ω_N=0.5、Ω_F=1.0、comp=0.3333；恒等式 `Ω = Ω_geo × comp` 与
  `Ω_geo = (Ω_E·Ω_N·Ω_F)^(1/3)` 均逐位成立。
- **动机**：项目原有全部验证信号都是**候选侧**的（`metaphor_coherence`、LLM 逐链判定、
  7 维特征）——没有任何标量回答"**查询侧**激活了多少隐喻结构"。语料密度（6.3 链/百 L1）
  是**语料**属性，不是**查询**属性。
- **来源**：**借用·外部系统对照**（VCPToolBox 的 RiverMemo 拓扑 V3 的查询侧可观测泛函）。
  见 `experiments/对照分析_RiverMemo.md`。
- **实证**：❌ **方向不可行**（三代实验连续证伪）：
  | 命题 | 裁决 | 数字 |
  |---|---|---|
  | Ω 只读查询（对候选池不变） | ✅ 成立 | 632 查询 × 4 种池扰动 → **0/632** 变化 |
  | Ω 比"触发词命中数"更有信息 | ❌ 否 | Spearman **ρ(Ω, n_seed)=0.9949**；`Ω>0 ⟺ n_seed≥1` **632/632** 一致 |
  | 低 Ω 预测级联通路失败 | ❌ 近乎同义反复 | 全样本 AUC 0.941；**去掉 Ω=0 的 518 条后 AUC 0.589**（CI 含 0.5） |
  | Ω 门控优于现有判据 | ❌ 严格更弱 | 漏掉 66 条"有触发词但通路仍空"的查询 |
  | Ω_N 分量有用 | ❌ **死分量** | 生产本体下 99.2% 级联成员共享单一目标域 → 涌现集恒空 |
  另外：**Ω 对触发词数非单调**（这是被单测钉住的已知局限）。
- **状态**：可选/分析。**从不接入任何检索排序**，不改变任何已上报数字——
  「Ω 是观测量，不是打分器」。

### M2 查询侧不变式 query-side invariant

- **位置**：`observability.py:229` 与 `query_signal.py:278` 的函数签名；单测
  `test_measure_signature_has_no_candidate_argument`
- **定义**：`measure(query, ontology)` 的签名里**没有** `shg` / 候选边 / 检索结果 / 排序器。
  「Ω 对候选池不变」是**结构性**成立的（由 API 形状保证），不是实验发现。
- **动机**：防止后来者为了刷指标"顺手"把候选信号混进来。
- **来源**：借用·外部系统对照（RiverMemo 的同一纪律）。
- **实证**：成立（扰动实验 0/632；反射检查签名禁词表）。
- **状态**：生产路径（回归护栏）。

### M3 S_query

- **位置**：`query_signal.py:249`（`_s_query`）；`SIG_S_QUERY` 常量 `:53`
- **定义**：Ω 的**单点修改**版本——**只去掉 Ω_N 分量的 `min(1, ·)` 截断**：
  ```
  Ω       = (Ω_E · min(1, n_em/n_seed) · Ω_F)^(1/3) × comp
  S_query = (max(Ω_E,ε) · max(n_em/n_seed,ε) · max(Ω_F,ε))^(1/3) × comp
  ```
- **动机**：gen3 的因子分解证明 `min(1,·)` 截断是信号被毁掉的**主要**原因
  （`n_seed=1` 层 82/102 条被截到 1.0，23 档取值塌成 2 档）。
- **来源**：自创（gen3）。
- **实证**：⚠️ **AUC 变高 ≠ 有用**：
  - 去掉截断后 Ω>0 子集内 AUC 0.654 → **0.824**（`source`）/ 0.593 → 0.609（`json`）；
  - **但它预测的目标是定理**：`cascade_nonempty ⟺ reachable_domains ∩ live_domains ≠ ∅`
    逐条一致 **635/635 = 1.0000**；
  - **决定性对照**：同一个"可达集合大小"标量预测"随机非空"的 AUC = **0.9739**
    vs 预测真实非空的 0.9640 —— **同级**，判别力主要来自"集合更大"这个机械效应；
  - 下游：查询侧标量对 per-query MRR 的文档内 ρ 最多 0.10–0.21（`n_gold` 上界 0.4981）。
- **状态**：可选/分析（作为 Ω 实现缺陷的修正记录，不作部署）。

### M4 S_log / S_struct

- **位置**：`query_signal.py:218`（`_s_log`）、`:230`（`_s_struct`）
- **定义**：
  ```
  S_log    = log1p(n_frames) + log1p(n_cascades) + log1p(n_new_domains)
             （无 ε 下界、无分母；退化分量在 log 空间贡献 0）
  S_struct = exp( Σ log(v_i) / |parts| )，parts 按"基底是否可能非退化"入选：
             parts = [min(1, n_frames/n_seed)] ∪ ([min(1, n_new/n_seed)] if n_cas>0 ∧ n_new>0)
  ```
- **动机**：把 Ω 的四个合成设计选择拆成可单独开关的对照，定位"信号在哪一步丢的"。
- **来源**：自创（gen3）。
- **实证**：64 个合成组合（分量定义 4 档 × 合成算子 4 档 × ε 2 档 × 完备度 2 档）的 AUC
  全落在 0.50–0.93，**合成层不是元凶**；`floor=False`（结构化丢弃）在 `source` 上**反而更差**
  （0.571 vs 0.654）。
- **状态**：可选/分析。

### M5 n_emergent / n_new_domains / n_reach（两种可达口径）

- **位置**：`query_signal.reachable_structure:79`；`SIG_N_EMERGENT:46`、`SIG_N_NEW_DOMAINS:47`、`SIG_N_REACH:48`
- **定义**：**必须区分的两种口径**：
  ```
  n_emergent    (gen2/Ω 口径)：级联成员框架的 target_domain 集合 − 直接命中框架的 target_domain 集合
                              （**只算目标域**）
  n_new_domains (检索口径)   ：在「目标域 ∪ 源域」空间上算的 (直接 ∪ 扩展) − 直接
                              ——这才是 cross_domain_retrieve 真正构造的 targets 空间
  n_reach       (检索口径)   ：|直接 ∪ 扩展|（目标域 ∪ 源域）
  ```
- **动机**：`cross_domain_retrieve` 实际用的是「目标域 ∪ 源域」且包含直接命中框架自己的两个域，
  与 Ω 口径不同——不区分则"数字对不上"。
- **来源**：自创。
- **实证**：❌ **集合大小伪影**：
  | 规则 | n_emergent 增量 AUC | 层内加权 AUC |
  |---|---|---|
  | `json`（生产默认） | 0.4897 [0.459, 0.509] | **0.4625**（低于随机） |
  | `source` | 0.4861 | — |
  且 gen2 报告的 0.836 **只在非默认的 `source` 规则下成立**（`json` 下是 0.4834，本来就无信号）——
  gen2 报告未标明这一点，是对该代结论的必要澄清。
- **状态**：可选/分析。

### M6 StratifiedNormalizer（n_seed 分层 z 分数）

- **位置**：`query_signal.py:321`
- **定义**：`z = (x − μ_{stratum(n_seed)}) / σ_{stratum}`；`fit()` 只在 `n_seed ≥ 1` 的样本上统计；
  层内 sd=0 时回退为 `(x − μ)/σ_global`（避免整层被清零）；未见过的层用 μ 的均值。
- **动机**：触发词命中数是查询的"体量"，任何随体量增长的计数都与它正相关。
  **把"条件判别"从检验方式变成可部署的量。**
- **来源**：自创（gen3）。
- **实证**：作为**检验工具有效**（正是它揭示了 n_emergent 的信号是尺寸伪影）；
  作为**部署量无下游价值**（文档内 ρ 最多 0.10–0.21）。
- **状态**：可选/分析。

### M7 `compose()` 四开关

- **位置**：`query_signal.py:140`
- **定义**：把 Ω 的四个合成设计选择做成显式开关，按与 Ω 实现相同的顺序应用：
  ① `normalize`（分量 ÷ n_seed）② `floor`（ε 下界 vs 结构化丢弃）③ 几何平均（固定）
  ④ `use_completeness`（乘完备度）⑤ `outer_zero`（无激活时严格为 0）。
- **动机**：「Ω 的信号是哪一步丢的」不应是论证，而应是**逐开关的实测对照**。
- **来源**：自创（gen3 机制归因工具）。
- **实证**：⚠️ **`outer_zero` 是死开关**（实测分歧）：实现为
  `return geo if not outer_zero or n_seed > 0 else 0.0`，但函数开头已有
  `if n_seed <= 0: return 0.0`，故该条件在到达时恒为 True。
  实测 `outer_zero=True` 与 `False` 给出**完全相同**的结果。
  **后果**：gen3 报告的"2⁴ 全因子对照"实际是 2³；不影响结论方向（那 16/64 个组合
  全部覆盖同一结论），但报告措辞应改为 2³。
- **状态**：可选/分析。

### M8 溯源可靠性 provenance reliability + `reliability_factor`

- **位置**：`provenance.py:39-44`（常量）、`:51`（`frame_reliability`）、`:73`（`edge_reliability`）、
  `:88`（`reliability_factor`）；`retrieval.py:91`
- **定义**（**逐字对齐代码**）：
  ```
  frame_reliability(ont, fid) = 1.0  若 ont.get_frame(fid) is not None
                              = 0.5  若未登记（回退框架，RELIABILITY_FALLBACK_CAP）
                              = 1.0  若 ontology is None 或 fid 为空（信息不足时不降级）
  edge_reliability(edge, ont) = min(stored, derived)     # 只采信"更保守"的那个（防伪升级）
  reliability_factor(r, floor) = floor + (1 − floor) · r  ∈ [floor, 1]
                                 floor 默认 RELIABILITY_FLOOR = 0.5；floor=1.0 → 恒为 1.0（关闭通道）
  ```
  **实测复核**：`reliability_factor(0.5) = 0.75`；`reliability_factor(0.5, floor=1.0) = 1.0`。✅
- **动机**：README §7.1 结论 1 的张力——类型连贯性检查拦下 24 个错误绑定，P1 却纹丝不动。
  根因是**被拒绑的候选没有被丢弃**，它退化成临时框架后照样产出超边。要让约束影响精度就必须
  丢弃候选——那等于关掉开放发现（+55.8pp 召回）。参考系统的处理方式是**不丢候选**，
  而是给它一条**独立且封顶的可靠性通道**。
- **来源**：**借用·外部系统对照**（VCP/RiverMemo 的"降级来源封顶可靠度通道"）。
- **实证**：❌ **对 P1 结构性不可能，排序净增益为零**：
  - P1 是句级布尔指标（`pred = bool(edges)`），软通道只作用于排序 → **数学上界为 0**；
  - 更关键：**7/7 条字面误判句全部由本体正式框架支撑，0/7 来自降级边**；
    句级判别 AUC = **0.3913**（反相关）；
  - 实测：召回 0.696 → 0.696（逐位不变，通道实现正确），但人工加权 MRR@10
    **0.9948 → 0.8922（−0.1025）**——by-construction 金标与通道前提直接冲突
    （26.6% 的金标 chunk 含降级边，降权即惩罚金标自身）；
  - **人工金标检索集（唯一不与通道前提冲突的尺子）效应恰为 ±0.0000**；floor 全档位扫描无一档优于基线。
- **设计论证（保留）**：为什么是**乘性且有下界的折扣**——加性 bonus 不改变相对次序（对排序无效），
  硬过滤会丢候选（召回崩），只有"有下界的乘性折扣"能在不丢任何候选的前提下改变排序。
- **⚠️ 实现陷阱（已钉成单测）**：判据必须是「本体有无条目」，**不是 `F_LLM_` 前缀**——
  `llm_ontology._stable_id("F_LLM", ...)` 给**自举沉淀的正式框架**也用这个前缀，
  生产本体 **98.6%** 的框架以 `F_LLM_` 开头；按前缀判定会把整个生产本体误判为"退化"。
- **状态**：生产路径（`RetrievalEngine.reliability_floor` 默认 0.5，即通道开启）。

### M9 诚实覆盖率 honest coverage

- **位置**：`health.py:174-194`（分支一）、`:205-219`（分支二）、`:42-59`（字段）
- **定义**：报出的 `hierarchy_coverage` 里，有多少是**本体登记框架 + 本体登记级联**撑起来的？
  ```
  分支一（:174-194）：
    reg        = {e : e.frame_id ∧ ont.get_frame(e.frame_id) is not None}
    registered_frame_coverage   = |reg| / |E|
    registered_cascade_coverage = |{e ∈ reg : ont.get_cascade(e.frame_id) ∈ ont.cascades}| / |E|
    registered_hierarchy_coverage = min(frame, cascade)
    n_fallback_edges = |E| − |reg|；adhoc_cascades = #{c : c.id.startswith("C_ADHOC_")}
  分支二（:205-219，**覆盖分支一的 frame/cascade 字段**）：
    registered_frame_coverage   = |{e : frame_reliability(ont, e.frame_id) ≥ 1.0}| / |E|
    registered_cascade_coverage = |{e : _in_reg_cascade(e)}| / |E|
  ```
- **动机**：报出的 100% 覆盖率含"注水"——抽取器为未知喻体临时建的回退框架（未在本体登记）
  靠 `builder._ensure_cascades` 按目标域事后补的 `C_ADHOC_*` 级联才够到 100%。
- **来源**：自创（`exp/degrade` 的发现）。
- **实证**：✅ **成立，是本项目最有价值的方法论产出之一**：
  | 语料 | 报出 | 诚实 | 来源 |
  |---|---|---|---|
  | 1100 句评测集（883 边） | 1.000 | **0.776** | `exp/degrade`（已独立复核） |
  | 120 句子集（108 边） | 1.000 | **0.824** | 论文 §5.2 |
  | 独立复跑（1100 句，1088 边） | 1.000 | **0.756** | 本次审计 |
  三者**全部低于 P2 的 85% 门槛** → 论文附录 B 的 P2 从 ✅ 改为**条件性达标**。
- **⚠️ 实现分歧**：`graph_health` 里 `registered_frame_coverage` 被**算了两遍**，
  分支二的 `frame_reliability` 对 `frame_id is None` 的边返回 **1.0**（"信息不足时不降级"），
  而分支一把它算作未登记。于是同一份报告里 `registered_frame_coverage`（来自分支二）
  与 `registered_hierarchy_coverage`（来自分支一）**可能互相矛盾**。
  实测：一条无 `frame_id` 的边 + 一条已登记边 → 报出 frame cov = **1.0**，
  但 hierarchy cov = **0.5**、`n_fallback_edges` = 1。
  生产语料上恰好无 `frame_id` 为空的边，故两分支数值相同（实测 0.756 = 0.756），
  但这是**巧合而非设计**。
- **状态**：生产路径（`graph_health(ontology=...)`；**不传 ontology 时字段为 None，历史口径逐位不变**）。

### M10 隐喻连贯度 metaphor_coherence

- **位置**：`hgnn.py:221`
- **定义**：`cos(entity_vec(src), entity_vec(tgt))`，其中 `entity_vec` 是跨层消息传递后的节点表示。
- **动机**：作为触发词与 LLM 之外的**第三道校验信号**——「对『字面误判』与『跨框架串味』的
  图结构判据，独立于触发词与 LLM」。
- **来源**：自创（HGNN 检测器）。
- **实证**：⚠️ **信号成立但载体被误认，且作为过滤器无效**：
  - H4：完整跨层 HGNN 全量 AUC **0.915** vs 仅 L1 超边 **0.910** → **信号来自 n 元喻底共现，
    不是层级传播**；原始嵌入 0.550（=无信息，原报告的 0.150 是并列计错的口径产物）；
  - 作为扩展链过滤器**无效**：阈值 0.5 保留 52/52，精度不变（16.7%）——
    候选链的域对本就通过自身框架相连，抽象域标签的图连贯度对"词化惯用语 vs 真隐喻"不敏感；
  - 算子退化假设**被证伪**：`M=½(I+S)` 在 500 轮后确实坍缩到分量平稳分布（同分量余弦 1.000000），
    但 H4 工作在 `layers=2`（同分量余弦 0.388，源保留 0.840），且完美同分量指示器的准确率上限
    只有 0.8057 < 实测 0.950。
- **状态**：可选/分析（`evaluate_chain_quality --coherence-threshold`，默认关闭；
  评分路径**从不调用** hgnn）。

### M11 图密度 Δ

- **位置**：`context_budget.py:32`（`graph_density`）、`:27-28`（`DENSITY_LOW=2.35`/`DENSITY_HIGH=5.0`）；
  `retrieval.py:39`（`shg_density`）；`health.py:144`
- **定义**：`Δ = 总关联数 / 端点数`（`incidences = Σ_e |set(e.member_entities)|`）。
  分档：`Δ ≤ 2.35` → low；`≤ 5.0` → mid；`> 5.0` → high。
- **动机**：与 HyperRAG 的 `Δ(G)` 同义——「低密度图遍历容易断，高密度图遍历容易爆」。
- **来源**：借用·图 RAG 文献（HyperRAG）。
- **实证**：实现正确（`graph_density(10,4)=2.5` ✅）。生产全量图实测 `Δ ≈ 2.578`（**mid 档**）；
  小测试图 `Δ = 1.0`（low 档）。**但由它驱动的策略切换实测无收益**（见 E5）。
- **状态**：生产路径。

### M12 超边元数 avg_arity / 孤立端点率 orphan_rate / 层级覆盖率 hierarchy_coverage

- **位置**：`health.py:109`（`graph_health`）、`:149`、`:145`、`:162`
- **定义**：
  ```
  avg_arity        = mean_e |set(e.member_entities)|         门槛：< 2.2 告警
  orphan_rate      = |{n : degree(n) ≤ 1}| / |nodes|         上限：> 0.8 告警
  frame_coverage   = |{e : e.frame_id}| / |E|
  cascade_coverage = |{f ∈ frames : f ∈ ⋃ cascade.member_frame_ids}| / |frames|
  hierarchy_coverage = min(frame_coverage, cascade_coverage) 门槛：< 0.85 告警（对齐方案 §7 的 P2）
  ```
- **动机**：「知识管理需要的是**运维信号**——图是否在退化、本体是否跟不上语料、层级是否还成立。
  这些信号必须在系统上线后持续可观测，否则『图悄悄烂掉』是不会有报错的。」
- **来源**：自创（运维信号）。
- **实证**：成立且**抓到过真实问题**——生产全量图实测 `avg_arity ≈ 3.92`（健康）、
  `orphan_rate ≈ 0.64`、`hierarchy_coverage = 1.000`（注水，见 M9）；
  `orphan_rate > 0.8` 的告警在小图上触发过，解释了"扩展隐喻合并判据难以成立"。
- **状态**：生产路径。

### M13 证据链覆盖率 / 软删除占比 / 退化边占比

- **位置**：`health.py:197-204`
- **定义**：`evidence_coverage = |{e : e.evidence}|/|E|`；`deprecated_rate = |{e : e.deprecated}|/|E|`；
  `degraded_edge_rate = |{e : provenance_reliability < 1.0}|/|E|`；
  `avg_provenance_reliability` 同理取均值。
- **动机**：把 S10/S12/M8 三个"知识治理"机制的运行状态暴露出来。
- **来源**：自创。
- **实证**：前两者**恒为 0**（空转：`evidence` 从不写入、`deprecated` 从不置位，
  `evidence_coverage == 0` 会触发"超边不可溯源"告警）；
  退化边占比实测 **22.0%–24.4%**（随语料规模）。
- **状态**：生产路径（部分空转）。

### M14 7 维特征 sem / struct / clue / type / same_frame / same_cascade / ground_jaccard

- **位置**：`training.py:41`（`FEATURE_NAMES`）、`:106`（文本锚点版 `extract_text_features`）、
  `:148`（超边锚点版 `extract_features`）
- **定义**（**逐字对齐代码**）：
  ```
  sem            = max(0, cos(embed(query), embed(cand.describe())))
  struct         = min(1, centrality[cand.id])，centrality = 0.5·len(ground) + 0.5·[cascade_id 非空]
                   （无 centrality 时同式现算）
  clue           = min(1, 0.5 × |{t ∈ cand.triggers : t ∈ query_text}|)      # 文本版
                   min(1, 0.5 × |query.triggers ∩ cand.triggers|)            # 超边版
  type           = ontology.type_reliability_of(cand.frame_id, cand.source_type)
                   1.0 已注册 / 0.5 未注册回退 / 0.0 无归属或非法
  same_frame     = 1.0 if cand.frame_id ∈ 查询触发框架集 / query.frame_id == cand.frame_id
  same_cascade   = 1.0 if cand.cascade_id ∈ 查询触发级联集 / query.cascade_id == cand.cascade_id
  ground_jaccard = |query.ground ∩ cand.ground| / |query.ground ∪ cand.ground|   （超边版，真 Jaccard）
                   文本版：|{w ∈ cand.ground : w ∈ query_text}| / |cand.ground|（**包含率，非 Jaccard**）
  ```
- **动机**：原实现是 4 维（sem/struct/clue/type）人工加权走一个"MLP"，但**没有训练数据、
  没有训练循环**——「它是装饰，不是检索器」。补两个**角色感知的结构信号**：
  「不能直接照搬 HyperRAG 的 DDE——它的伪三元组展开假设端点同质，而我们的端点带角色」。
- **来源**：自创（前 4 维借鉴 HyperRAG 的 HyperRetriever 特征思路，后 3 维自创）。
- **实证**：全量审计（gen3）——
  | 特征 | 配对 AUC | 学到权重 | 人工权重（历史） | 裁决 |
  |---|---|---|---|---|
  | `sem` | **0.6277** [0.6023,0.6522] | +0.6911 | 0.35 | **唯一有真实判别力** |
  | `struct` | 0.5197 | +0.0195 | **0.25** | 弱；**人工过权 37–49 倍** |
  | `clue` | 0.5087 | +1.2543 | 0.20 | 弱（评测口径；训练集口径 0.9985 系饱和） |
  | `type` | 0.5249 [0.5092,0.5401] | +0.0487 | 0.20 | 弱正向（**非死维**；gen1 的 0.497 是训练集口径误读） |
  | `same_frame` | 0.5053 | +0.1953 | 0.00 | 接近随机 |
  | `same_cascade` | 0.5070 | +0.1958 | 0.00 | 接近随机；与 `same_frame` **冗余 51.7%** |
  | `ground_jaccard` | 0.5300 | +0.4965 | 0.00 | 弱 |
  **全部处置（删除/替换 6 个替代信号）的 ΔMRR 95% CI 全部覆盖 0** → 删不删都一样；
  处置标准因此从"能否提升指标"改为"是否减少认知负担而不损失能力"。
  ⚠️ 两条**定义分歧**（已在代码注释标注，未修）：`ground_jaccard` 文本版是包含率而非 Jaccard
  （实测 4.76% 的候选对因此不同）；`sem` 的 clamp 不一致（训练版 `max(0, cos)`，检索人工加权版无 clamp）。
- **状态**：生产路径。

### M15 人工权重 HAND_WEIGHTS / HAND_WEIGHTS_LEGACY

- **位置**：`training.py:62`（`HAND_WEIGHTS_LEGACY`）、`:65`（`_LEARNED_SHARE`）、`:76`（`HAND_WEIGHTS`）、
  `:79`（`hand_weighted_score`）
- **定义**：
  ```
  HAND_WEIGHTS_LEGACY = {sem:0.35, struct:0.25, clue:0.20, type:0.20}     # 原 4 维，复现历史数字
  _LEARNED_SHARE      = {sem:0.6911, struct:0.0195, clue:1.2543, type:0.0487,
                         same_frame:0.1953, same_cascade:0.1958, ground_jaccard:0.4965}
  HAND_WEIGHTS        = normalize(_LEARNED_SHARE)   # 按学到比例归一化，7 维（实测 {0.2382, 0.0067,
                                                    # 0.4323, 0.0168, 0.0673, 0.0675, 0.1711}）
  hand_weighted_score = Σ_i w_i · f_i，其中 struct 与 clue 截断到 1（历史口径）
  ```
- **动机**：原实现把权重**硬编码在两个地方**（`retrieval.py` 与 `evaluate_retrieval.py`），
  且与学到权重严重错配。
- **来源**：自创。
- **实证**：**这是"训练增益"归因的关键**——
  - 错配：`struct` 人工 0.25 vs 学到 0.0195 → **过权 37–49 倍**；`type` 0.20 vs 0.0487 → **12–19 倍**；
  - 仅把人工权重按学到比例重标定（**不训练任何模型**），anchored MRR 从 0.8390 → **0.8956（+5.7pp）**，
    改写型 anchored +3.97pp；
  - 重标定后**训练增益降为 +0.49pp [−0.89, +1.84]（CI 覆盖 0）**；
    1 维 `sem` 单信号 = 0.5474，与 7 维训练后 0.5449 无差异（Δ=+0.0025，CI 覆盖 0）；
  - **真实句向量下 1 维 `sem` 显著优于训练后 7 维（+1.76pp，p=0.003）**；
  - deanchor 下重标定效应仅 **+0.0023** → **只在锚定口径下"有效"**。
- **状态**：生产路径（`HAND_WEIGHTS` 为默认；`LEGACY` 保留供历史口径重放）。

### M16 RRF 融合

- **位置**：`retrieval.py:32`（`_rrf`）、`:346`（`rrf_fusion`）
- **定义**：`score(c) = Σ_{r ∈ ranklists} 1 / (k + rank_r(c) + 1)`，`k = 60`（rank 从 0 起）。
  **实测复核**：`_rrf(['a','b','c']) = {a: 1/61, b: 1/62, c: 1/63}` ✅。
- **动机**：字面通路与隐喻通路的分数**量纲不可比**，需要一种只用排名信息的融合方式。
- **来源**：借用·IR 文献（Reciprocal Rank Fusion）。
- **实证**：实现正确；但 `rrf_fusion` 只被 `demo.py` 与单测调用，
  **未参与任何已上报指标**（三通路分解是分别报告的，不做融合）。
- **状态**：可选（默认不启用）。

### M17 链密度（链/百 L1）+ 含链文档占比

- **位置**：`evaluate_document_corpus.py:240-252`；`论文初稿.md` §6.6
- **定义**：`链/百 L1 = 100 × |扩展链| / |L1 超边|`；`含链文档占比 = |{doc : doc 至少一条链}| / |docs|`。
- **动机**：L1.5 的**价值域假设**需要一个可量化的密度指标——它衡量"连贯文档上扩展隐喻到底多常见"。
- **来源**：自创。
- **实证**：✅ 成立：连贯文档 **6.3 链/百 L1、30% 文档含链** vs 独立短句 **0.6%、4.5%** = **10×**。
  分语料：财经 8.2%、政报 4.3%、鲁迅 5.2%（鲁迅是在低 L1 基数下取得——跨语时代泛化是已知边界）。
- **状态**：生产路径。

### M18 P1 字面误判率 / 召回 / 精确率 / F1

- **位置**：`extractor.literal_false_positive_rate:307`；`ablation.measure:58`
- **定义**：
  ```
  P1 = |{literal 句 : extract(text) ≠ ∅}| / |literal 句|      硬门槛 < 15%（Go/No-Go）
  ```
  注意 `pred = bool(edges)` 是**句级布尔存在性**判断。
- **动机**：方案 §6.5 的硬门槛。
- **来源**：借用·评测惯例（字面误判率是本任务的自定义指标）。
- **实证**：达标（9.2%）。**但它的定义本身导致了一个结构性结论**：
  因为是句级布尔指标，任何"只改分数不改产出"的软通道（如 M8 溯源可靠性）对它
  **数学上界为 0**——这是 `exp/degrade` 最有价值的发现。
- **状态**：生产路径（且是理解多个负面结果的关键）。

### M19 MRR / Hits@k / Recall@k + 随机基线 + MRR 量程

- **位置**：`evaluate_repaired.metrics:311`、`random_baseline:327`
- **定义**：
  ```
  MRR        = 1 / (第一个金标 chunk 的排名)
  Hits@k     = 1 if top-k ∩ gold ≠ ∅ else 0
  Recall@k   = |top-k ∩ gold| / |gold|
  random_baseline：MRR 用解析期望
             Σ_r [ C(n−g, r−1)/C(n, r−1) × g/(n−r+1) ] / r
             Hits@k = 1 − C(n−g, k)/C(n, k)；Recall@k = min(1, k·g/n)/g
  ```
  **MRR 量程** = 1 − 随机基线（判断指标是否被吃掉一半）。
- **动机**：原基准候选池 median 7–8，随机排序 MRR 期望就有 0.37（量程 0.63），
  指标已失去区分力。
- **来源**：借用·IR 文献；**随机基线随指标一并报告**是 SIGIR 1998/2007 的要求。
- **实证**：成立。实测 `random_baseline(1100, 1)["mrr"] = 0.0069`、`hits@10 = 0.0091` ✅；
  池 ≤10 时 `hits@10 = 1.0`（平凡饱和，见 T3）。
- **状态**：生产路径。

### M20 全量 AUC（`_auc_full`）

- **位置**：`evaluate_hgnn.py:316`
- **定义**：`AUC = P(pos > neg) + 0.5·P(pos == neg)`，**用全量正负对**（正确处理并列）。
- **动机**：n=20 的配对准确率**统计功效不足**——其"结论字符串"会随无关参数（α）抖动翻转
  （α=0.5 时打印"依赖跨层传播 ✅"），而同期 AUC 完全稳定。并列率高达 94.6%（哈希向量下
  抽象域标签几乎无共享 n-gram），配对准确率把并列计为**错误**，产出 `raw = 0.150`
  这种"反向判别"的假象。
- **来源**：借用·IR/ML 文献（ROC-AUC）。
- **实证**：✅ 成立并已成为 H4 主指标。修正后的表述：原始嵌入 **AUC 0.550 = 无信息**
  （而非"远低于随机"）。
- **状态**：生产路径。

### M21 targeting excess（命中率 / 随机期望）

- **位置**：`experiments/gen3/exp_g3_4_downstream.py`；`实验结论汇总.md` §"一个正面发现"
- **定义**：`激活框架命中真实候选的比率 ÷ 尺寸匹配随机对照的命中率`。
- **动机**：在"控制集合大小"之后，检验查询侧激活结构是否仍与候选侧有统计关联。
- **来源**：自创（gen3）。
- **实证**：**子集内的弱真实效应**：`json` 1.7339 / `source` 1.7723 / `metanet` 1.7802
  （CI 不含 1.0）；`source_type` 仅 1.0489。
  **限定**：全样本上与尺寸匹配随机对照**同级**（0.9640 vs 0.9739），
  仅在 `n_seed ≥ 1` 子集内显现（0.6799 vs 0.5856）。
  **最有价值的推论**：查询侧信息是**多维分布式的**，标量化会丢失它。
- **状态**：可选/分析。

---

## 4. 工程概念

### E1 双防线 double defense

- **位置**：`extractor.py:1-17`（模块 docstring）；`论文初稿.md` §3.2、§5.1
- **定义**：字面误判过滤由两道防线承担：① **LLM 置信阈值**（实测达标拐点 **0.85**）
  ② **refine 校验**（对触发词/语义域通道候选做二次判断）。MIPVU 判据写进提示词。
- **动机**：单一阈值无法同时优化召回与精度。
- **来源**：自创。
- **实证**：✅ **成立且缺一不可**：
  | 配置 | 召回 | P1 |
  |---|---|---|
  | 规则侧天花板 | 9.7% | 7.9% |
  | + 阈值 0.85（**无 refine**） | 69.1% | **14.5%** |
  | + 阈值 0.85 + refine | 66.3% | **9.2%** |
  | 阈值 0.5 不设防 | 89.6% | **32.9%** ❌ |
  A3 通道消融：无 refine 时 P1 **43.4%** → 有 refine **0.0%**（在触发词+语义域配置下）。
- **状态**：生产路径。

### E2 双段管线 two-stage pipeline

- **位置**：`extended.py`（第一段）+ `llm_backend.verify_chains_batch:757` + `builder.llm_verify_extended`
- **定义**：**第一段"候选生成"**以宽松判据（同框架 + 同源域 + 喻底交集 + 间距<3）快速合并出候选链
  （保密度）；**第二段"语义校验"**以 LLM 逐链判定跨段延续性（MIPVU 严格口径提示词）过滤（保精度）。
  失败纪律：整批解析失败则该批链**不写入缓存**并在返回值中缺失——调用方必须把"缺失"当未校验处理。
- **动机**：与抽取侧 discover→refine 对称。结构信号的**召回与精度不可由单一阈值同时优化**。
- **来源**：**借用·外部系统对照**（RiverMemo 的"六路候选超集 → Ω 门控的条件创新过滤"）。
- **实证**：✅ **成立**：候选链 52 → 保留 11（21.1%），保留集精度 **16.7% → 63.6%**（7/11，
  跨模型配对子集 71.4%）≈ **4×**；同时密度 10× 保住。
  **三方消融**（同一候选集、同一 judge）：无过滤 52/16.7% ｜ 文本级判据 49/不变 ｜
  图连贯度阈值 0.5 → 52/不变 ｜ **LLM 语义校验 11/63.6%**。
- **状态**：生产路径（`MetaphorSHGBuilder(llm_verify_extended=..., verify_cache_path=...)`）。

### E3 级联查表 cascade lookup

- **位置**：`builder.py:103-138`（L2 按框架归属、L3 按级联归属）；`ontology.CascadeOntology`
- **定义**：L2/L3 归属通过**本体查表**完成（`get_frame` / `get_cascade`），
  未匹配项仅少量回退 LLM 聚类。
- **动机**：原方案用 embedding 聚类 + LLM 逐组验证，成本 ~200 次调用/千边。
- **来源**：自创。
- **实证**：成本主张 ✅（~20 vs ~187 次/千边）；
  **但覆盖率归因需要更正**——报出的 100% 由 `builder._ensure_cascades` 的目标域兜底产生，
  **不是本体级联查表的结果**（关掉兜底后覆盖率 = 0.767，低于 0.85 门槛）。
  论文措辞应改为"级联查表 **+ 目标域兜底**"。
- **状态**：生产路径。

### E4 孤儿框架兜底 `_ensure_cascades` / `C_ADHOC_*` / `orphan_cascade_rule`

- **位置**：`builder.py:150`
- **定义**：给"不属于任何级联"的孤儿框架补 L3 归属。规则可选
  `target`（默认，按目标域打包，= 改动前行为）｜`source`｜`ground`｜`source_type`｜`none`（L3 消融）。
  级联 id 用 `C_{tag}_{md5(key)[:8]}`（md5 而非内置 hash——后者受 `PYTHONHASHSEED` 随机化影响）。
- **动机**：LLM 开放发现遇到本体没有的新喻体时会临时建 `F_LLM_*` 框架，这些框架 `get_cascade()`
  恒为 None——实测 L3 覆盖率因此卡在 67%（P2 门槛 85%）。
- **来源**：自创。
- **实证**：⚠️ **它是覆盖率注水的来源**（M9）：
  - 默认规则与 `llm_ontology.build_specs` 的构造规则**完全相同**，因此补出来的级联与本体级联
    **结构同构**——成员共享单一目标域，跨域扩展能力为零（110 次 build 共补出 399 个 `C_ADHOC_`，
    size 中位数 1、max 1）；
  - 唯一量化收益是 `cascade_coverage` 从 ~0.78 抬到 1.000；
  - 替代规则可恢复组织力（`source_type` 下 ad-hoc 级联 size 中位 2 / max 6），
    **但不改变任何主检索指标**，故**不改默认**（改默认会重写 733 个稳定 ID）。
- **状态**：生产路径（默认 `target`）。

### E5 自适应阈值 AdaptiveThreshold + 密度分档

- **位置**：`context_budget.py:58`（类）、`:80`（`select`）、`:44`（`ThresholdDecision`）
- **定义**：
  ```
  τ ← τ0 = 0.5；selected = {items : score ≥ τ}
  while |selected| < min(min_keep=50, |items|) and decays < max_decays=5:
      τ ← τ − decay(0.1)；decays += 1；重筛
  分档：regime = low (Δ ≤ 2.35) → 不设上限（"宁多勿少"）
                high (Δ > 5.0) → 截断至 max_keep or max(min_keep·3, 1)
                mid           → 常规
  ```
- **动机**：固定阈值在稀疏图上召回为空、在稠密图上召回爆炸；本项目原用固定 top_k，
  "在稀疏隐喻图上会硬凑噪声，在稠密图上又会截断"。
- **来源**：借用·图 RAG 文献（HyperRAG：τ₀=0.5, c=0.1, 最多降 5 次；密度分档边界 2.35/5）。
- **实证**：⚠️ **中性**：A8 消融实测"稀疏/稠密图均无差异"（0.500/0.500；0.250/0.250），
  在密度 1.071 的更大图上仍无差异。**机制实现正确，但未带来可测收益。**
  实测复核：3 候选 / Δ=1.0 → τ 0.5→0.1（降 4 次），选 3 条，不设上限 ✅；
  20 候选 / Δ=9.0 → τ 0.5→0.0（降 5 次），选 18 条后截断 ✅。
- **状态**：生产路径（默认开；**但"是否该开"无实测支持**）。

### E6 上下文预算 50/30/20 `ContextBudget` / `ContextPack`

- **位置**：`context_budget.py:138`（类）、`:121`（`ContextPack`）、`:157`（`pack`）
- **定义**：
  ```
  budgets = [max_tokens × 0.5, × 0.3, × 0.2]      # 顺序固定：(超边, 实体, 源文本块)
  cost(text) = max(1.0, len(text) / chars_per_token(=1.6))
  逐类填充，装不下就跳过；carry = room − used 顺延给下一类
  ```
- **动机**：原项目只有 `top_k=60/120` 这类粗粒度设定，**没有预算概念**——结果是
  "召回到但塞不进上下文"和"噪声挤掉关键超边"同时发生。
- **来源**：借用·图 RAG 文献（HyperRAG 的 50/30/20）。
- **实证**：**未做定量验证**——打包消融（`evaluate_packing_ablation`）被 **judge 敏感性**阻断：
  同一查询集、同一生成模型、4 种打包变体，deepseek judge 判纯向量对照 6:1 胜，
  glm judge 判当前打包最优（26.50 vs 21.12）。**结论随 judge 模型反转。**
- **状态**：生产路径（生成层；但主张需真人评估仲裁）。

### E7 候选超集 candidate superset

- **位置**：`experiments/对照分析_RiverMemo.md` §3.1
- **定义**：宽松生成一大票候选，再由严格过滤挑选——"宁可多召"。
- **动机**：「结构信号的召回与精度不可由单一阈值同时优化」这一判断的工程实现。
- **来源**：**借用·外部系统对照**（RiverMemo 的"六路候选超集"）。
- **实证**：概念成立，本项目的两个实例（三通道抽取、双段管线）都独立验证了它。
- **状态**：概念（本项目无同名代码；落地形态是 E12 与 E2）。

### E8 构造锚定 construction anchoring

- **位置**：`evaluate_repaired.py:1-31`（模块 docstring）；`三臂对等审计.md`；`论文初稿.md` §4.1
- **定义**：查询由金标边的触发词拼成、金标即该边所在 chunk——于是"复现锚点"成为一条捷径，
  指标被系统性抬高。
- **动机**：诊断出的评测基准缺陷。
- **来源**：自创（诊断）；概念对应 IR 的 **pooling bias**（T10/E10）。
- **实证**：✅ **成立且是本项目最重要的方法论发现**：
  - 632/632 = **100%** 的"非构造金标"都包含产出该问题的 chunk；619/632 = **97.9%** 只包含它；
  - **锚定抬高 ≈ +0.66 MRR**（人工加权口径 0.8956 vs 0.2330）→ 原报告数字约 **74%** 来自锚定；
  - MRR 来源分解：训练增益 +6.44pp **全部落在"产出 chunk"列**，非产出列（n=13）为 **−0.64pp**；
  - 锚定效应与向量器**正交**（哈希 +0.6626 / 真实 +0.6875）。
- **状态**：概念 + 审计工具（`audit_fairness`）。

### E9 去锚定口径 de-anchored setting

- **位置**：`evaluate_repaired.build_query_sets:198`
- **定义**：
  ```
  anchored : 金标 = 产出 chunk（现行口径，池已全局化）
  deanchor : **把产出 chunk 从候选池中移除**，金标 = 同框架的**其它** chunk；
             无同框架其它 chunk 则退到同级联；再退则丢弃该查询
  ```
- **动机**：物理切断"复现锚点"这条捷径，把"架构能力"与"锚定效应"分离。
- **来源**：自创。
- **实证**：✅ **成立，且是本项目最强的一组检索数字**：
  - deanchor MRR **0.2330 = 随机基线 0.0069 的 34×**，Recall@10 = 0.3357（随机期望 ≈0.009）
    → **排除了"架构完全无效"**；
  - 可构造 deanchor 查询 385/634（其余无同框架其它 chunk）；金标规模 min=1/median=3/max=37
    （比 anchored 恒为 1 更真实）；
  - **训练增益在去锚定后反转**（anchored +0.005 → deanchor −0.012），与查询族无关；
  - **诚实标注的限制**：deanchor 的金标仍由图结构定义（"同框架其它 chunk"），
    不是人工判断的"相关证据"——它是**去锚定的检验**，不是独立金标。
- **状态**：生产路径（评测口径）。

### E10 pooling bias

- **位置**：`evaluate_repaired.py:14`；`论文初稿.md` §4（引 Bias and the limits of pooling, 2007）
- **定义**：检索评测中，只有被纳入 pool 的文档才可能被判定相关，导致对未纳入文档的系统性偏差。
- **动机**：给 E8 的缺陷一个 IR 文献中的标准名字，便于审稿人定位。
- **来源**：借用·IR 文献。
- **实证**：作为诊断标签成立。配套的第二个标签是 **test collection 规模不足**
  （Efficient construction of large test collections, SIGIR 1998）对应 T3。
- **状态**：概念。

### E11 公平性声明 fairness declaration + `audit_fairness`

- **位置**：`audit_fairness.py:1`；`论文初稿.md` §4.1；单测 `test_no_hardcoded_budget_in_comparisons`
- **定义**：三条规则——① 两臂的搜索预算须显式声明并尽量对等；② 候选池规模须报告，
  并检查指标是否平凡饱和；③ 金标口径须一致。配套**机器检查**：剥离注释后扫描各评测脚本的
  预算类参数（`top_k|max_gap|max_results|n_pairs|negatives_per_positive`），报告硬编码调用。
- **动机**：人工审查**三次都漏掉了下一处**——三处缺陷分别在不同脚本、不同抽象层
  （基准构造 / 权重定义 / 函数调用），每一处单看都"合理"。
- **来源**：自创。
- **实证**：✅ 成立，抓出三处同类缺陷（§6.1 池饱和 / §6.2 权重错配 + 锚定 / §6.4 A6 预算不对等）。
  **工具自身踩过坑**：首版未剥离注释，把 A6 修复注释里的"原实现用 top_k=5"误报为硬编码——
  已修正并把教训留在 docstring。
- **状态**：生产路径（护栏）。

### E12 三通道抽取 three-channel extraction

- **位置**：`extractor.py:232`（通道一触发词）、`:246`（通道二 MIPVU+语义域）、`:260`（通道三 LLM 开放发现）
- **定义**：① 触发词通道（自举模式串 + lift 过滤）；② MIPVU-lite + Wmatrix 式语义域失谐通道；
  ③ **LLM 开放发现**（开放文本直接发现隐喻，不依赖词表）。全部候选经类型安全约束与置信过滤。
- **动机**：规则侧在 P1<15% 约束下的召回天花板只有 ~9.7%；裸名词触发能到 ~50% 但 P1 爆到 60%+。
- **来源**：自创。
- **实证**：✅ 成立：LLM 开放发现把召回 **9.7% → 69.6%** 而 P1 **不升**（9.2%）——**帕累托前沿整体外推**；
  语义域通道边际 +0.6pp；A4 去自举本体召回 −1.8pp。
- **状态**：生产路径。

### E13 三通路检索 three-pathway retrieval

- **位置**：`evaluate_repaired.pathway_rankings:277`（统一在同一全局候选池上比较）
- **定义**：`literal`（查询词面子串命中 chunk 原文）｜`cascade`（触发词 → 框架/级联 → 目标域 → chunk）｜
  `semantic`（超边渲染后向量化 + 7 维特征排序）。
- **动机**：把"隐喻结构到底带来什么"分解为三条可独立测量的通路。
- **来源**：自创。
- **实证**：**相对结论成立，绝对数字需大幅下修**：
  | 查询族 | 字面 Hits@10 | 级联 Hits@10 | 语义 Hits@10 | 语义 MRR / 随机 |
  |---|---|---|---|---|
  | 重叠型 anchored（n=60） | 0.8833 | 0.2000 | **1.0000** | 133× |
  | 重叠型 deanchor（n=60） | 0.2667 | 0.1500 | **0.5667** | 36× |
  | **改写型 anchored（n=777）** | **0.0000** | **0.0206** | **0.1918** | **17.1×** |
  | **改写型 deanchor（n=508）** | **0.0000** | 0.0295 | **0.1752** | **12.8×** |
  - 字面通路在改写型上**非空率 0/777**（通路完全失效，不是排序差）；
  - 级联通路非空率仅 **0.192**（149/777）——0.0206 是在 19.2% 的查询上取得的；
  - 原报告的 1.000 是**平凡饱和**，高估约 5.2×。
- **状态**：生产路径。

### E14 语义回退 semantic_fallback

- **位置**：`retrieval.py:138`（`cross_domain_retrieve(..., semantic_fallback=False)`）、`:111`（`_cascade_index`）
- **定义**：触发词全未命中时，退到"查询向量 vs **级联描述**"的语义粗筛
  （U-Retrieval 自顶向下），取 top-2 级联，回收其成员框架的超边 chunk。
- **动机**：改写/近义查询下级联通路断链（实测 Recall 0.043）。粗筛 733 个级联比逐边匹配便宜一个量级。
- **来源**：借用·图 RAG 文献（U-Retrieval 的自顶向下思想）。
- **实证**：级联通路 Recall **0.020 → 0.042**（翻倍但仍极低）；
  "哈希级级联粗筛太糙，语义超图通路仍是正解"。**默认关闭**（不改变已上报行为）。
- **状态**：可选（默认关）。

### E15 静默失败防护

- **位置**：`llm_backend.LLMFatalError:53`、`embeddings.EmbedderFatalError:81`、`storage.Neo4jFatalError:174`
- **定义**：认证/计费类致命错误（401/402/403）**抛异常，绝不降级**；网络/超时/解析类错误由调用方
  决定降级策略。同一纪律贯穿三条外部依赖线（LLM / embedder / Neo4j）。
- **动机**：真实事故——「账户欠费 402 被『优雅降级』吞掉 → 域归并 100% 恒等 → 本体碎片化成 2656 框架，
  流程却一路报成功」。
- **来源**：自创（工程纪律）。
- **实证**：✅ 成立。另有同族陷阱：`evaluate_real.py` 无 API key 时回落到 `LocalHeuristicBackend`，
  而它不实现 `discover_batch`/`batch_refine`，于是 `--llm-cache` **根本没被消费**，
  产出**假性 P1 = 0.434**（正确做法是用 `PrecomputedBackend` 喂真实缓存重放）。
- **状态**：生产路径。

### E16 确定性 id（md5 稳定 id）

- **位置**：`extractor.py:207`（`L1_{md5(span_key)[:8]}`）、`llm_ontology._stable_id`、
  `builder.py:230`、`extended.py:87`（`EXT_{md5(...)[:8]}`）、`cascade_rules._sid`
- **定义**：所有持久化 id 用 `hashlib.md5(...).hexdigest()[:8]`，**禁用内置 `hash()`**
  （受 `PYTHONHASHSEED` 随机化影响）。
- **动机**：随机 id 会让缓存重放时对不上号（实测踩坑）；本体是长期资产，id 必须跨进程可复现。
- **来源**：自创。
- **实证**：成立，且有单测护栏。
- **状态**：生产路径。

### E17 缓存重放 cache replay / 零 API 复现

- **位置**：`llm_backend.PrecomputedBackend:586`；`data/llm_cache_*.json`
- **定义**：把"批量预取"的 LLM 结果当作后端喂给抽取器；所有需要真实 LLM 的阶段
  （discover / refine / 改写 / 判定 / 校验 / 关联 / 生成）均落盘缓存，重放零请求。
- **动机**：让全部表格可零 API 费用复现，且消融只改一个变量。
- **来源**：自创（工程纪律）。
- **实证**：成立（`ablation.TrackedBackend` 还会记录**查不到的 refine 键**——
  "消融不该偷偷多花 API 钱，也该知道数据缺口"）。
- **状态**：生产路径。

### E18 单测护栏 regression guard

- **位置**：`test_metaphor_graph.py`（116 → 224 项）
- **定义**：把"已知局限"也钉成护栏——例如 `test_omega_zero_iff_cascade_path_would_be_empty`、
  `test_omega_is_not_monotone_in_trigger_count`、`test_judgement_is_registration_not_prefix`、
  `test_measure_signature_has_no_candidate_argument`、`test_no_hardcoded_budget_in_comparisons`。
- **动机**：防止后来者"顺手"把候选信号混进来刷指标，或重新踩已踩过的坑。
- **来源**：自创。
- **实证**：成立；但**224 项全绿不足以保证合并正确**——合并过程引入 3 处回归
  （`score_conditions` 无条件加 legacy 臂、冲突解决遗漏 argparse 定义、冲突标记未清），
  单测不覆盖 CLI 入口与 `evaluate_fullcorpus`。已补 2 项护栏
  （`test_eval_cli_args_present`、`test_all_eval_modules_importable`）。
- **状态**：生产路径。

### E19 特征漂移 feature drift + 单一真源

- **位置**：`ontology.type_reliability_of:445`；`training.extract_features:148`；
  `retrieval.metaphor_retriever_score:264`
- **定义**：训练期与推理期对同一维特征给出不同取值 = 特征漂移；修法是让两条路径
  **调用同一个函数**（单一真源）。
- **动机**：真实 bug——`training.py` 用 `1.0 if cand.frame_id else 0.0`，而 `retrieval.py`
  查本体后对未注册的 `F_LLM_*` 返回 0.0。同一候选在两条路径得 1.0 vs 0.0。
- **来源**：自创（诊断）。
- **实证**：**bug 真实存在**（856 条 L1 边中 **188 条（22.0%）真正分歧**——
  注意 `F_LLM_` 前缀被两个互不相交的 id 空间共用：`extractor` 用 `md5("src|tgt")`，
  `llm_ontology` 用 `md5("src||tgt")`，故 587 条回退边其实已注册）；
  **但因果链推断错了**：§6.2 的 manual weighting 根本不调用 `metaphor_retriever_score`，
  它走共享 7 维特征且该候选池中 `type` 恒为 1.0（死维度）。修复后增益**反而增大**
  （+4.5pp → +6.4pp），因为把一个"无害常数"变成了"有害噪声"。
  **教训**：不能据"两处表达式不同"直接推断"已上报数字被污染"，须先确认被上报的路径实际调用哪段代码。
- **状态**：生产路径（已统一）。

### E20 弱监督（refine 否决负样本）

- **位置**：`training.build_weak_refine_set:570`
- **定义**：从 refine 缓存里取**真金白银买来的标签**——`batch_refine` 中 `is_metaphor=False`/`None`
  的候选是"同 chunk、同触发词、但被模型否决"的**天然困难负样本**。它们的 `clue` 特征与正样本
  几乎相同，所以 `clue` 不再完美可分。正样本 = chunk 模式同款。
- **动机**：突破自监督的 `clue-AUC≈1.0` 天花板（T5）。
- **来源**：自创。
- **实证**：机制 ✅（clue 平均 AUC **1.0 → 0.931**、leakage 标记 **136 → 23**）；
  **但相对自监督的排序增益仍未证实（−0.013 MRR）**。
- **状态**：可选（`evaluate_fullcorpus --weak-refine`）。

### E21 评测自检 `trivial_separators` / `leakage_report` / `feature_auc`

- **位置**：`training.py:194/216/225`
- **定义**：
  ```
  feature_auc(ds)      = 每维单特征 AUC（并列计 0.5）
  leakage_report(ds)   = 单特征 AUC ≥ 0.98 的特征名列表（非空 = 该样本集不适合上报指标）
  trivial_separators(ds) = 单特征即可**完美**分类的特征名（pos_min > neg_max + ε 等）
  ```
- **动机**：docstring 原话——「trivial_separators 只抓**完美**可分（AUC=1.0），抓不住 AUC=0.99
  这种实质上已被单特征决定的样本集。报告指标前必须看这个。」
- **来源**：自创。
- **实证**：成立，抓到了自监督的 `clue` 泄漏（110 个训练集共标记 136 处）。
- **状态**：生产路径（工具）。

### E22 源项/阻尼 α / ε（HGNN dynamics）

- **位置**：`hgnn.py:26`（`MetaphorHGNN.__init__`）、`:152`（`propagation_matrix`）、`:170`（`forward`）
- **定义**：
  ```
  传播算子 M_ε = 0.5 · (I + (1−ε)·S)，S = D_v^{-1} H D_e^{-1} H^T
  驱动迭代 X ← (1−α)·X0 + α·M_ε·X，迭代 layers 次
  α=1.0, ε=0.0  → 退化为历史实现 X ← M·X（**逐位相同**，maxdiff = 0.000e+00）
  ε>0 → M 行和 = 1 − ε/2 < 1 严格成立，ρ(M) ≤ 1 − ε/2
  合法性：α∈[0,1] 一律允许；α>1 需 α·(1−ε/2) < 1（否则 Neumann 级数发散）
  ```
- **动机**：RiverMemo 式算子的 resolvent `(I − αT)^{-1}` 要求 Σ_j P_ij < 1 严格成立才能对任意 α 收敛。
  同时检验一个假设：`M=½(I+S)` 无源项 → 迭代收敛到连通分量平稳分布 → `metaphor_coherence`
  退化为同分量指示器 → **这解释了 GRU 与 HGNN 打平**。
- **来源**：**借用·外部系统对照**（RiverMemo 的谱性质要求 + 源项机制）。
- **实证**：❌ **假设证伪**：
  - 退化只在**渐近**意义成立（500 轮同分量余弦 1.000000），而 H4 工作在 `layers=2`
    （同分量余弦 0.388，源保留 0.840）；
  - **决定性证据**：完美同分量指示器的准确率上限 = (20+602)/772 = **0.8057**，**低于** H4 实测的 0.950；
  - 18 个 (α,ε) 配置下 `|ΔAUC| ≤ 0.005`，95% CI 跨 0 → **加源项不打破 flat/HGNN 平局**；
  - 源项的真实价值：让**深层迭代**（layers ≥ 50）不再坍缩，而非改善 layers=2。
- **状态**：可选（默认 α=1.0/ε=0.0，与历史逐位兼容）。

### E23 触发词 lift 过滤

- 见 L10。

### E24 本体清洗三规则（自环 / 喻底明喻标记 / tier 分层）

- **位置**：`ontology_clean.py:99`（`clean_ground`）、`:105`（`clean_frames`）、`:156`（`clean`）、`:267`（`verify`）
- **定义**：三类可度量的质量问题与对应规则：
  ① **自环框架**（`source_domain == target_domain`）→ 删；
  ② **喻底被明喻标记污染**（ground 里混着"如/像/似/般"）→ 剔；
  ③ **支持度无分层**（86% 框架 count==1）→ 打 `tier` 标签（`core` count≥2 / `longtail` 单例），
  生产默认两级全载。
  **刻意不做的规则**：「源域出现在自己的 triggers/ground 里 → 删」（探查发现这是名词隐喻的正常形态，
  删掉会误伤最经典的概念隐喻）；「动词当源域 → 删」（无可靠词性标注环境，不做脆弱的词性猜测）。
- **动机**：`llm_ontology_train.json` 的 2185 个框架是 LLM 一次性沉淀的原始产物，需清洗去重后
  沉淀为生产默认本体。
- **来源**：自创。
- **实证**：✅ **指标中性的纯质量提升**——缓存重放三变体对照**逐指标持平**
  （P1 9.2%、召回 69.6%、覆盖率 100%），refine 缓存命中率 100%；
  core-only 消融显示 longtail 单例框架贡献 **+1.2pp 召回**（模糊匹配锚点价值）。
- **状态**：生产路径（2177 框架 = core 299 + longtail 1878）。

---

## 5. 评测概念

### T1 改写型 vs 重叠型查询

- **位置**：`evaluate_repaired.build_paraphrased_sets:164`（改写型）、`build_query_sets:198`（重叠型）；
  `evaluate_llmgold.filter_violations:186`（红线）
- **定义**：
  ```
  重叠型 (overlap)    ：query = "，".join(edge.triggers) —— 触发词直接出现在查询里
  改写型 (paraphrased)：LLM 把查询改写成自然问题，**程序化红线禁用**触发词/源域/目标域
                       （"clue 捷径必须被切断"）
  ```
- **动机**：原 §6.1 的结论建立在**改写型**查询上，而修复后基准最初只测了**重叠型**——
  "两者是不同查询族，不可直接对比"。
- **来源**：自创。
- **实证**：✅ **成立，且是本项目最锋利的自变量**：
  - 语义通路 MRR 重叠型 0.9200 vs 改写型 0.1183（**7.8×**）；Hits@10 1.0000 vs 0.1918（5.2×）；
  - 改写切断触发词后，7 维特征中的 `same_frame`/`same_cascade`/`ground_jaccard` **全部失效**
    （AUC 0.505–0.530），只剩 `sem`（AUC 0.62）——**语义通路退化为纯语义相似度检索**；
  - 训练增益的符号与查询族无关（两族都在 deanchor 下反转）→ 说明训练器学到的是"复现构造锚点"。
- **状态**：生产路径。

### T2 非构造金标（**已证伪的标签**）

- **位置**：`evaluate_llmgold.py`（原始设计）；证伪见 `experiments/gen3/REPORT.md` §4
- **定义**（原主张）：LLM 在该文档全部候选映射中做 listwise 相关性判定 →
  与抽取构造无关的**独立**金标，"构造即金标的循环被打破"。
- **动机**：by-construction 金标使 clue 特征恒命中、四种排序器全部饱和在 0.995+，测不出排序增益。
- **来源**：自创。
- **实证**：❌ **标签不成立**（被本项目自己的审计推翻）：
  - **632/632 = 100%** 的查询，LLM 金标都包含"产出该问题的 chunk"；
  - **619/632 = 97.9%** 只有那一个 chunk；
  - 可真正检验非构造检索的查询仅 **13/632 = 2.1%**；
  - **机制**：LLM 的作用是**过滤**（筛掉不相关候选），**没有解除锚定**；
  - 旁证：构造金标一致性 96.8% 只是"两个构造口径互相一致"，不能证明非构造性。
- **状态**：**退役**（论文 §4 的标签必须改写；被 E9 去锚定口径取代）。
  这是本词典里最重要的"被证伪的概念"——它界定了"自建检索基准"这一类工作的设计空间。

### T3 平凡饱和 trivial saturation

- **位置**：`audit_fairness.py`；`evaluate_repaired.py:11`；`A6预算对等修正.md`
- **定义**：当候选池规模 ≤ k 时，`Hits@k`（甚至 `Recall@k`）对**任何返回全候选的排序器恒为 1.0**——
  指标失去区分力，"1.000"不是性能成就。
- **动机**：原基准按伪文档切分，候选池 min=5 / median=8 / max=10（**100% ≤10**）。
- **来源**：借用·IR 文献（test collection 规模不足，SIGIR 1998）。
- **实证**：✅ 成立，三处命中：
  ① §6.1 三通路"语义超图 1.000"（池 ≤10）——修复后改写型只有 0.1918；
  ② §6.4 A6"隐喻通路 1.000"——同一原因；
  ③ §7 的 A7/A9 三臂结果**完全相同**（均 0.998），**该表结论不可用于判定训练/特征的价值**。
  **重要限定**：重叠型查询在池=1,100 下的 1.000 **不是平凡饱和**（随机 Hits@10 仅 0.0091），
  但仍**受构造锚定支配**——两种缺陷必须分开诊断。
- **状态**：概念 + 检查项（E11）。

### T4 全量 AUC

- 见 M20。

### T5 泄漏天花板 clue AUC≈1.0

- **位置**：`training.py:256-265`（`_build_from_chunks` docstring）；`leakage_report`
- **定义**：自监督信号中，`clue`（触发词是否出现在句中）的**单特征 AUC 接近 1.0**——
  因为抽取器本来就是靠触发词命中产出这条边的。模型因此退化为"**复读抽取器**"。
- **动机**：解释 A7/H5 的"训练无增益"。
- **来源**：自创（训练信号病理）。
- **实证**：✅ 成立，且**机制已被定位并部分修复**：
  - 110 个训练集共标记 **136 处** leakage；学到的权重 `clue = 1.2543`，其余 ≈0；
  - 弱监督把 clue AUC 压至 **0.931**、泄漏标记 **136 → 23**；
  - **但排序增益仍未证实**（相对自监督 −0.013 MRR）；
  - **平行发现的同类病**：RiverMemo 的 $I_e$ 项（降低候选自身对关系证据的循环自证）
    与这里的 clue 泄漏是同一个病——「打分信号其实来自生成该候选的那个捷径本身」。
- **状态**：生产路径（自检项）。

### T6 四族对比 four-family comparison

- **位置**：`三通路重测_修复后基准.md` §5；`evaluate_repaired.py` 主流程
- **定义**：`{重叠型, 改写型} × {anchored, deanchor}` 共 4 组 × 3 通路。
- **动机**：原 §6.2 的结论基于**改写型**查询，但修复后基准的排序器表最初用的是**重叠型**——
  **查询族不匹配**。补齐四族才能判定训练增益的符号来源。
- **来源**：自创。
- **实证**：✅ 成立且是结论的必要分辨率：
  | 查询族 / 口径 | 查询数 | 人工（重标定） | 训练后 | 训练 − 重标定 |
  |---|---|---|---|---|
  | 重叠型 anchored | 634 | 0.8956 | 0.9006 | **+0.0050** |
  | 重叠型 deanchor | 385 | 0.2330 | 0.2211 | **−0.0119** |
  | 改写型 anchored | 777 | 0.1172 | 0.1341 | **+0.0169** |
  | 改写型 deanchor | 508 | 0.0882 | 0.0809 | **−0.0073** |
  → **训练增益只在 anchored 下为正，去锚定后一致为负，且与查询族无关**。
- **状态**：生产路径。

### T7 程序化红线 filter_violations

- **位置**：`evaluate_llmgold.py:186`
- **定义**：改写查询不得含原触发词/源域/目标域——`banned = edge.triggers + [source_domain, target_domain]`，
  命中即丢弃该查询。
- **动机**：「clue 捷径必须被切断」——否则改写查询退化为重叠型查询。
- **来源**：自创。
- **实证**：成立（违规剔除率约 26.7%——"模型总想偷用触发词"）。
- **状态**：生产路径。

### T8 诊疗集 diagnostic set

- **位置**：`eval_corpus.py`（2 篇文档 / 7 条人工金标扩展隐喻 / 8 条跨域检索查询）
- **定义**：**人工设计**的小样本评测语料，刻意制造跨 chunk 扩展隐喻、字面干扰句、
  以及只能用隐喻通路召回的跨域查询。
- **动机**：金标与内部实现无关（"评测只比较系统输出 vs 金标"），零标注成本、完全离线、确定性。
- **来源**：自创。
- **实证**：机制验证成立（P3 F1 = 1.000、跨距误并 = 0），**但不可外推**——
  README 原话："这是**精选诊疗集**（语料即按可检测隐喻设计），证明机制在干净案例上正确重构；
  不是大规模基准，数字应读作『机制可用』而非『泛化上界』"。
- **状态**：生产路径（机制验证）；结论外推需用 E9/T6 的全量口径。

### T9 LLM-as-judge 敏感性

- **位置**：`demo_rag.py`、`evaluate_packing_ablation.py`、`evaluate_llmasjudge.py`；`论文初稿.md` §6.5
- **定义**：同一查询集、同一生成模型、4 种打包变体，**结论随 judge 模型反转**。
- **动机**：原计划用 LLM-as-judge 做生成质量评估。
- **来源**：自创（实测发现）。
- **实证**：✅ 成立：deepseek judge 判**纯向量对照 6:1 胜**；glm judge 判**当前打包最优**
  （26.50 vs 21.12，最优率 50%）。
  **方法论结论**：「组件级检索结论（§6.1–6.4）不受影响，但一切生成质量主张必须由**真人评估仲裁**」——
  这把"需要人工评估"从程序性要求变成了**实测结论**。
- **状态**：概念（方法论结论）；E6 的验证因此被阻断。

### T10 金标稳健性双协议审核（κ）

- **位置**：`论文初稿.md` §6.5、附录 C
- **定义**：两项无人工审核的稳健性检验：① **跨模型二评**（glm-4.7 重判 13 查询/114 边对）→
  Cohen's κ = **0.965**；② **同模型换序二评**（候选逆序 + temp 0.4，全量 50 查询/420 边对）→
  κ = **0.912**（pa = 0.976，10 处不一致全部为二评更宽）。
- **动机**：A4（人工抽查）的 AI 替代方案；LLM 生成金标需要可复现性证据。
- **来源**：借用·标注一致性文献。
- **实证**：成立（金标对模型更换与引出顺序/温度均稳健）；
  **但不替代锚定审计**（T2）——κ 高只说明金标**可复现**，不说明它**非构造**。
  全量真人复核仍建议作为投稿前最后一步。
- **状态**：生产路径（附录）。

### T11 池外文档比例 pool-external rate

- **位置**：`evaluate_repaired.py` 模块 docstring；`REPORT_benchmark_repair.md` §1.3
- **定义**：评测自我审计字段之一——候选池外文档所占比例，与**随机排序基线**、**MRR 量程**并列。
- **动机**：IR 文献（SIGIR 1998；2007）要求这类字段随指标一并报告。
- **来源**：借用·IR 文献。
- **实证**：成立（评测自我审计的标准配置）。
- **状态**：生产路径。

### T12 构造金标一致性 96.8%

- **位置**：`论文初稿.md` §4；`metaphor_graph/README.md` §7.5
- **定义**：LLM 判定的金标与抽取构造的金标之间的一致率。
- **动机**：作为"非构造金标"主张的旁证。
- **来源**：自创。
- **实证**：❌ **作为非构造性的证据无效**——两个构造口径**互相一致**不等于**非构造**；
  实测 100% 的金标仍含产出 chunk（T2）。
- **状态**：**退役**（数字仍可报告，但不得用作非构造性的证据）。

---

## 6. 已证伪 / 已退役的概念

> 这一节是本词典最有价值的部分：**被证伪的概念界定了设计空间**。

| 概念 | 证伪方式 | 关键数字 | 处置 |
|---|---|---|---|
| **Ω 作为查询侧标量** | 三代连续实验 | ρ(Ω, n_seed)=0.9949；去掉 Ω=0 块后 AUC 0.589；控制集合大小后所有标量 AUC 覆盖 0.5；64 种合成组合全在 0.50–0.93 | 保留为观测量，**正式关闭该方向**（论文 §7） |
| **Ω_N 分量** | 构造性恒空 | 生产本体 99.2% 级联成员共享单一目标域 → 涌现集恒空；几何平均下 Ω 被迫由 ε 下界决定 | 保留代码，标注为死分量 |
| **n_emergent 作为信号** | 集合大小伪影 | 控制尺寸后增量 AUC 0.4897 [0.459,0.509]；层内加权 AUC 0.4625（低于随机）；gen2 的 0.836 **只在非默认 `source` 规则下成立** | 保留为诊断计数 |
| **S_query** | 目标是定理 | `cascade_nonempty` 逐条一致 635/635；尺寸匹配随机对照 AUC 0.9739 vs 真实 0.9640 | 保留为"Ω 实现缺陷的修正记录" |
| **溯源可靠性通道对 P1 的作用** | 数学上界为 0 | P1 效应恒 0；**7/7 条误判句全部由本体正式框架支撑**；人工金标检索集效应 ±0.0000 | 通道保留（默认开），**主张撤回** |
| **类型安全约束过滤字面误判（H1）** | 结构性不可能 | 枚举约束拦 0 + 连贯性拦 24，P1 纹丝不动（0.092）；要影响 P1 必须丢弃候选 = 关掉开放发现（−55.8pp 召回） | 定位降级为"结构正确性" |
| **L3 级联层的结构贡献** | 全单例对照 | 生产 = source = 全单例 MRR **逐位相同 0.5025**；仅彻底移除降到 0.4681 | 保留但定位降级为"组织/可解释性" |
| **HGNN 跨层传播的检索收益（哈希向量下）** | 代码审计 + 18 配置扫描 | 评分路径**从不调用** hgnn；flat ≡ HGNN 的 \|ΔAUC\| ≤ 0.005 | 从检索路径移除（保留为分析工具） |
| **加源项能打破 flat/HGNN 平局** | 高功效 AUC | 18 个 (α,ε) 配置 \|ΔAUC\| ≤ 0.005，95% CI 跨 0；完美同分量指示器上限 0.8057 < 实测 0.950 | 参数保留（默认兼容），假设撤回 |
| **非构造金标（标签）** | 直接复核 | 632/632 = 100% 含产出 chunk；97.9% 只含它；可真正检验的仅 13/632 = 2.1% | **论文标签必须改写** |
| **构造金标一致性 96.8% 作为非构造性证据** | 逻辑 | 两口径互相一致 ≠ 非构造 | 数字保留，用途撤回 |
| **人工权重配错造成的"训练增益"** | 重标定对照（不训练任何模型） | 重标定后人工加权 0.4809→**0.5496**，**反超**训练后 0.5447；训练增益降为 +0.49pp [−0.89,+1.84]；1 维 `sem` = 7 维训练后（真实向量下甚至 +1.76pp 显著更优） | 权重已重标定，结论改写为"条件化" |
| **角色感知结构特征（A9/H7）** | 消融 | 去角色特征 MRR 完全不变（0.906→0.906；0.998→0.998）；`same_cascade` 与 `same_frame` 冗余 51.7%–100% | 全部保留（删除无收益也无损失） |
| **自适应阈值（A8）** | 消融 | 稀疏/稠密图均无差异（0.500/0.500；0.250/0.250）；密度 1.071 的更大图上仍无差异 | 保留（默认开，无实测收益） |
| **MIPVU-lite 语义域通道的边际贡献** | 消融 | **+0.6pp**（12.4% vs 11.8%），远低于纯规则配置下的估计 | 保留，默认关闭 |
| **图连贯度作为扩展链过滤器** | 三方消融 | 阈值 0.5 保留 **52/52**，精度不变 16.7%；中位连贯度 0.820 | 保留为可选开关 |
| **文本级延续性判据（vehicle_repeat）** | 消融 | 密度 52→49，**存活链不变**；区分不了词化惯用语与单点共现 | 保留为可选，需语义级校验 |
| **MIPVU 硬编码 6 个级联 ID 门控** | bug 修复 | 任何替换级联规则的实验会**静默关掉整条通道**（丢 7 条 L1 边，856→849） | 已修为"框架存在 + 框架有级联归属" |
| **`outer_zero` 合成开关** | 实测（本次审计） | 函数开头已 `return 0.0`，该条件恒 True → **开关无效**；gen3 的"2⁴ 全因子"实为 2³ | 保留（结论方向不受影响），措辞应更正 |
| **`propagation_matrix` 与 `_conv` 严格等价** | 实测（本次审计） | 含重复端点时 maxdiff = 0.048（单边）/ 0.042（真实图 20.6% 的边）；无重复时为 0 | 保留（不在检索路径），需补单测 |
| **`registered_frame_coverage` 单一定义** | 实测（本次审计） | 同一函数内算两遍，分支二的 `frame_reliability(None)=1.0` 与分支一矛盾；实测 1 条无 frame 边时 frame cov=1.0 而 hierarchy cov=0.5 | 需修（生产语料上恰好同值，属巧合） |
| **`S_conditional`** | 代码审计 | 只在 `query_signal.py` 模块 docstring 中出现，**无实现**（对应物是 `StratifiedNormalizer`） | 文档应更正 |

---

## 7. 借用并改造的概念

> 每一行说明**保留了什么 / 丢弃了什么 / 为什么**。核心原则：
> **「只借机制，不借基质」**（`experiments/对照分析_RiverMemo.md` §5）。

### 7.1 从外部系统（VCPToolBox / RiverMemo 拓扑 V3）借用

| 概念 | 基质差异 | **保留** | **丢弃** | 结果 |
|---|---|---|---|---|
| **Ω 可观测泛函** | RiverMemo：Tag 图上的守恒传输，边是二元 Tag→Tag 加传输率 $P_{ij}$；本项目：超边 + 级联归属，无流量 | 几何平均合成的可观测泛函 + 观测完备度因子 + **只读查询不读候选**的 API 形状纪律 + 工况分档 | **守恒传输 / 严格次随机 $P_{ij}$ 边权**（"超边是静态文本事实，硬造边权既无语言学依据也拿不到额外信号"）；**双尺度场 / resolvent 分类**；**Atomic/Propositional/Narrative 形态 Softmax**（"依赖流量图的查询形状分类；本项目查询侧只有三层且很浅，映射过去等于凭空造分类法"）；**批级条件创新 $\mathbb E(G\mid Z_i)$**（"需定义候选条件协变量并要足够批统计量；收益最不确定"） | ❌ Ω 证伪（退化为 1-bit）；但**机制纪律（只读查询）成立并被钉成护栏** |
| **$\Omega^\gamma$ 门控结构证据** | 同上 | 概念（"结构增量不是无条件正收益"） | 具体门控实现（Ω 不可用） | ⚠️ 借到的机制解释了本项目的负面结果（§6.6 连贯度阈值无效——$B_G$ 单独本就不承担判别职责，必须乘 $\Omega^\gamma$） |
| **降级来源封顶可靠度通道** | RiverMemo：文档标注"不具备与主通道同等的事实强度"；本项目：隐喻超边 | **不丢候选 + 独立封顶通道**（本体登记 1.0 / 回退框架封顶 0.5）；**有下界的乘性折扣**（不是过滤器） | 参考系统的"事实强度"语义（本项目落到"排序权限"） | ⚠️ 实现正确，但**对 P1 结构性无效**（P1 是布尔存在性指标，不是排序指标）——**这是与参考系统场景的关键结构差异，也是该实验最有价值的发现** |
| **宽松生成 → 严格过滤的双段架构** | 基质无关（同一类问题的通解） | 完整保留（第一段保密度、第二段保精度） | — | ✅ 成立（16.7%→63.6%） |
| **循环自证（circular self-justification）/ $I_e$ 项** | 一个从图结构侧、一个从特征侧 | 诊断框架（"打分信号来自生成该候选的那个捷径本身"） | 具体 $I_e$ 实现 | ✅ 两侧撞上同一个病（本项目的 clue 泄漏天花板） |
| **源项 / resolvent 谱性质** | 同上 | 谱性质检验（$S$ 行随机、$\rho(S)=1$）+ 源项机制 | $P_{ij}$ 边权；双场分类 | ❌ 假设证伪（源项不打破平局），但**顺带定位了一个真实 bug**（`_conv` 无源项扩散的渐近坍缩） |

**关键差异（保留的诚实限定）**：
- **表示层本项目更丰富**：L1 超边是真正的 n 元结构；RiverMemo 的边是二元 Tag→Tag，无 n 元性。
  本项目"信号载体是 n 元性、不是层级性"这一结论，在 RiverMemo 框架里**无法表述**。
- **动力学层 RiverMemo 更丰富**：守恒传输、同一算子生成双尺度场、"节点势 vs 实际边流"的区分。
  本项目的级联查表是 O(1) 离散归属，**没有"多少信息真的流过去了"这个变量**。
- **参考设计自己承认的边界**：RiverMemo 文档 §15 只声称 Ω"**可以**测量、**可以**授权"，
  **没有**声称它带来下游指标增益。本项目严格遵守同一纪律（Ω 不接入任何检索排序）。

### 7.2 从图 RAG 文献借用

| 概念 | 保留 | 丢弃 / 改造 |
|---|---|---|
| **超边自然语言渲染**（HyperGraphRAG, NeurIPS 2025） | `describe()` 把超边渲染成完整句子再嵌入（"JSON 数组形式的 ground / 短字符串的 source/target 无法直接嵌入"） | 原样保留，是本项目的关键补环 |
| **HGNN 两步消息传递**（节点→超边→节点） | 传递算子 + 残差 | 加 `alpha`/`leak` 参数（默认逐位兼容）；**从检索路径移除**（从未被调用） |
| **U-Retrieval**（MedGraphRAG 标签粗筛→逐层下钻→自底向上约束） | 自顶向下粗筛思想 → `semantic_fallback` | 只在触发词全未命中时启用（默认关闭）；方案 B 的完整 U-Retrieval 退役 |
| **上下文预算 50/30/20 + 自适应阈值 + 密度分档**（HyperRAG, WWW 2026） | 完整保留（阈值 τ₀=0.5/c=0.1/最多 5 次；密度边界 2.35/5.0） | 无（但自适应阈值实测中性） |
| **HyperRetriever 的可训练排序器**（HyperRAG） | "有监督信号才有效"的判断；7 维特征 + logistic 排序器 | **DDE 的伪三元组展开被弃用**——"它假设端点同质，而我们的端点带角色（源域/目标域/喻底）"；改用同框架/同级联/喻底 Jaccard 作为角色保留的邻近度 |
| **HL-index 超图可达性索引** | 概念（触发词→超边→目标域的 O(1) 查表 + BFS 兜底） | 未接入生产（只在 demo/单测） |
| **RRF**（IR 文献） | `1/(k+rank+1)`, k=60 | 未接入已上报指标 |

### 7.3 从认知语言学 / 语料库语言学借用

| 概念 | 保留 | 改造 |
|---|---|---|
| **概念隐喻理论 / 源域-目标域** | 作为基本坐标 | 端点上**加角色标记**（源域/目标域/喻底），因为"端点带角色"是后续所有结构特征的前提 |
| **框架（FrameNet / MetaNet）** | 框架名、source_frame/target_frame | 增加 `mapping_type`（接类型安全约束）、`source_type`（接护栏）、`support`/`tier`（清洗分层） |
| **隐喻级联（MetaNet cascades）** | "预先组织好的打包集合"这一定义 | **构造规则被替换为工程规则**（按目标域打包）→ 这正是缺陷来源；已抽出 7 条可选规则（`cascade_rules.py`）以恢复可度量性 |
| **喻底 ground** | 集合语义（n 元性的来源） | 增加清洗规则（剔明喻标记）；增加 `ground_jaccard` 作为合并判据与特征 |
| **MIPVU** | 「基本义 ≠ 语境义」+ 三类排除项 | ① 提示词口径（原样写入）；② MIPVU-lite：**中文自建 USAS 词表**替代英文 Wmatrix（"Wmatrix 是英文 web 工具，中文不可直接用"），±2 token 窗口、分词 token 匹配（"避免『如』误中『栩栩如生』"） |
| **Wmatrix 语义域 / keyness** | 语义失谐判据 | 用「域 ≠ 语篇主导域 ∧ 域内稀有」近似 keyness；增加"域内字面护栏" |
| **扩展隐喻 / 延伸比喻** | 语言学依据 | 操作化为四判据（同框架 + 同源域 + 喻底交集≥1 + 间距<3）——**判据的充分性不足**（词化惯用语问题），故必须加第二段语义校验 |

### 7.4 从 IR 文献借用

| 概念 | 保留 | 说明 |
|---|---|---|
| **pooling bias**（2007） | 完整借用为诊断标签 | 对应 E8 构造锚定 |
| **test collection 规模不足**（SIGIR 1998） | 完整借用为诊断标签 | 对应 T3 平凡饱和 |
| **lift** | `(df_met/n_met)/(df_neu/n_neu)` | 用于触发词过滤（阈值 3.0 / 动词通道 20） |
| **RRF** | `1/(k+rank+1)` | 未接入生产 |
| **MRR / Hits@k / Recall@k / ROC-AUC** | 标准定义 | 全量 AUC 取代配对准确率是本项目的方法学修正 |
| **Cohen's κ** | 标准定义 | 用于金标稳健性双协议 |

---

## 8. 机械提取遗漏的概念

> `_extracted.json` 的 `concept` 类只抓 `class` 与模块级类型别名（56 项），
> 抓不到**活在散文、公式与注释里的概念**。以下概念**在代码里没有对应的类/类型**，
> 但都是项目的一等概念。

### 8.1 纯散文/公式概念（无类）

| 概念 | 载体 | 为什么机械提取抓不到 |
|---|---|---|
| **双防线 double defense** | `extractor.py` docstring、论文 §3.2 | 是**两个已存在机制的组合命名**（`llm_conf_threshold` + `_refine`），不是新类 |
| **双段管线 two-stage pipeline** | `extended.py` + `builder.llm_verify_extended` | 是**跨模块的流程**，没有类 |
| **构造锚定 construction anchoring** | `evaluate_repaired.py` docstring | 是**评测口径的属性**，不是实体 |
| **去锚定口径 de-anchored setting** | `build_query_sets` 的一个分支 | 是函数内的一个 `if` 分支 |
| **平凡饱和 trivial saturation** | `audit_fairness.py` 文本 | 是**指标的失效模式** |
| **非构造金标** | `evaluate_llmgold.py` docstring | 是**主张/标签**，后被证伪 |
| **诚实覆盖率 honest coverage** | `health.py` 的字段名 | 字段存在，但概念名只在注释/论文里 |
| **泄漏天花板 clue AUC≈1.0** | `training.py` docstring | 是**训练信号的病理描述** |
| **候选超集 candidate superset** | `对照分析_RiverMemo.md` | 只出现在对照文档里 |
| **级联查表 cascade lookup** | `builder.py` docstring | 是"查表"这个动作的命名，无类 |
| **孤儿框架兜底** | `builder._ensure_cascades` | 方法名是 `_ensure_cascades`，"孤儿框架"是注释里的概念 |
| **pooling bias** | 论文 §4 引用 | 外部文献概念 |
| **四族对比 four-family comparison** | `evaluate_repaired` 主流程 | 是**实验设计**，不是代码实体 |
| **改写型 vs 重叠型查询** | 两个 build 函数 | 查询族的命名只在 docstring 里 |
| **全量 AUC** | `_auc_full`（私有函数） | 私有函数名 + 方法学主张 |
| **特征漂移 feature drift** | 多处注释 | 是**缺陷类型的命名** |
| **单一真源 single source of truth** | `training.py:52` 注释 | 是**设计纪律**的命名 |
| **静默失败防护** | 三个 `*FatalError` 类 | 概念是"纪律"，类是它的载体 |
| **确定性 id / 缓存重放** | 多处 | 是**工程纪律** |
| **程序化红线** | `filter_violations` docstring | 是函数的行为描述 |
| **诊疗集 diagnostic set** | `eval_corpus.py` docstring | 是**语料的性质** |
| **LLM-as-judge 敏感性** | 论文 §6.5 | 是**实测结论** |
| **词化惯用语 lexicalized idiom** | 论文 §6.6 | 语言学概念，无代码 |
| **targeting excess** | gen3 实验 | 是**分析量的命名** |
| **查询侧不变式** | 两个 measure 函数的签名 | 是**API 形状的性质** |
| **双尺度场 / resolvent / 守恒传输** | `对照分析_RiverMemo.md` §5 | **明确决定不借**的机制（记录了"不借什么"） |

### 8.2 只作为**常量**存在的概念（机械提取归到 `criterion` 而非 `concept`）

| 概念 | 常量 | 值 | 说明 |
|---|---|---|---|
| 几何平均分量下界 ε | `observability.EPS` | 1e-3 | Ω 的"防与门退化"设计 |
| 单条流量的约定熵 | `SINGLE_FLOW_ENTROPY` | 0.5 | 退化情形的**约定值**（不给 0 也不给 1） |
| Ω 的稀疏/稠密分界 | `SPARSE_MAX` | 0.5 | regime 分档 |
| 类型护栏可靠性三档 | `TYPE_RELIABILITY_{REGISTERED,FALLBACK,INVALID}` | 1.0 / 0.5 / 0.0 | 与 M8 的 provenance 三档**语义不同**（一个是"类型可否核验"，一个是"框架是否登记"） |
| 溯源可靠性三档 | `RELIABILITY_{ONTOLOGY,FALLBACK_CAP,FLOOR}` | 1.0 / 0.5 / 0.5 | 注意 `FALLBACK_CAP` 与 `FLOOR` **同为 0.5** 但语义完全不同（一个封顶候选可靠性，一个给打分折扣设下界）——易混 |
| 图密度分档边界 | `DENSITY_LOW` / `DENSITY_HIGH` | 2.35 / 5.0 | 借用 HyperRAG |
| P1 硬门槛 | `THRESHOLD_P3_ACC` / 论文 §5.1 | 0.70 / 0.15 | P3 跨 chunk 消歧 >70%；P1 <15% |
| chunk 参数 | `CHUNK_SIZE` / `CHUNK_OVERLAP` / `MAX_CHUNKS_PER_DOC` | 500 / 50 / 40 | 对齐方案 §4.6（400–600 字） |
| 嵌入维度 | `embeddings.DIM` | 512 | 全链路统一 |
| 人工权重的学到比例 | `_LEARNED_SHARE` | 见 M15 | 7 维的重标定来源 |

### 8.3 只作为**方法/函数**存在的概念（机械提取归到 `pathway`）

`extract_equative_pattern`（等比模式串挖掘）、`build_bootstrap_ontology`（自举回流）、
`build_cascades`（级联构造规则）、`link_extended_metaphors`（L1.5 合并）、
`clean_ground`/`clean_frames`（本体清洗）、`filter_triggers_by_lift`（lift 过滤）、
`build_specs`（域归并 → 框架聚合）、`build_training_set`/`build_weak_refine_set`（训练集构造）、
`feature_auc`/`leakage_report`/`trivial_separators`（评测自检）、
`build_query_sets`/`build_paraphrased_sets`（评测口径）、`pathway_rankings`（三通路分解）、
`graph_health`/`shg_density`/`graph_density`（运维信号）、
`verify_chains_batch`（语义校验）、`compose`/`measure_signal`（查询侧信号）。

### 8.4 机械提取到的**类**里，哪些其实不是"项目概念"

> 诚实标注：56 项里有相当一部分是**工程脚手架**，不是概念。列出来避免"56 个新概念"的误读。

| 类别 | 成员 | 为什么不算概念 |
|---|---|---|
| 后端适配器 | `OpenAIBackend`、`LocalHeuristicBackend`、`PrecomputedBackend`、`MockBackend`、`_RefineCollector`、`TrackedBackend`、`_CountingPrecomputed`、`CachedRealEmbedder`、`OpenAICompatibleEmbedder`、`NgramEmbedder`、`Neo4jStore`、`MetaNetImporter` | 外部依赖的接入层；其中 `PrecomputedBackend`（缓存重放）与 `TrackedBackend`（记录数据缺口）**有概念价值**，其余是管道 |
| 异常类型 | `LLMFatalError`、`EmbedderFatalError`、`EmbedderError`、`Neo4jFatalError`、`Neo4jError` | 概念是"静默失败防护"这一**纪律**（E15），异常类只是载体 |
| 数据载体 | `TrainingSet`、`RetrieverResult`、`MetaphorSample`、`_NumpyGRU`、`_Handler` | 纯容器/测试替身 |
| 注册表 | `Baseline`、`Ablation`、`EvalSuite` + `BASELINES`/`ABLATIONS`/`EVAL_SUITES` | 是**方案文档的可执行化**；其价值在于"打哪个基线是为了分离出什么贡献"这个**元信息**字段（`isolates`），而非数据结构本身 |

---

## 9. 关键公式速查（已逐一对照代码复核）

```
【Ω】observability.py:229
  Ω_E = min(1, n_frames / n_seed)
  Ω_N = min(1, |emergent_targets| / n_seed)
  Ω_F = normalized_entropy(flow)      # 无正流量→0；单条正流量→0.5；n>1→H/log2(n)
  Ω   = (max(Ω_E,1e-3)·max(Ω_N,1e-3)·max(Ω_F,1e-3))^(1/3) × completeness
  特判：n_seed==0 ∨ n_frames==0 → Ω = 0
  实测：'项目推进不动，陷在泥潭里' → Ω=0.2646, Ω_geo=0.7937, E=1.0, N=0.5, F=1.0, comp=0.3333 ✅

【S_query】query_signal.py:249（与 Ω 的唯一差别：Ω_N 无 min(1,·)）
  S_query = (max(Ω_E,ε)·max(n_em/n_seed,ε)·max(Ω_F,ε))^(1/3) × comp

【S_log / S_struct】query_signal.py:218/230
  S_log    = log1p(n_frames) + log1p(n_cascades) + log1p(n_new_domains)
  S_struct = exp(Σ log(v_i)/|parts|), parts ⊆ {min(1,n_frames/n_seed), min(1,n_new/n_seed)}

【溯源可靠性】provenance.py:51/73/88
  frame_reliability = 1.0 if ont.get_frame(fid) is not None else 0.5   (fid 为空或 ont 为 None → 1.0)
  edge_reliability  = min(stored, derived)
  reliability_factor(r, floor) = floor + (1−floor)·r        # floor=0.5 默认；floor=1.0 关闭
  实测：factor(0.5)=0.75；factor(0.5, 1.0)=1.0 ✅

【隐喻连贯度】hgnn.py:221
  metaphor_coherence(src,tgt) = cos(H[src], H[tgt])
  H = (M_ε)^layers · X0（α=1 时）；M_ε = 0.5(I + (1−ε)·D_v^{-1} H D_e^{-1} H^T)

【图密度】context_budget.py:32 / retrieval.py:39 / health.py:144
  Δ = Σ_e |set(e.member_entities)| / |nodes|        分档：≤2.35 low / ≤5.0 mid / >5.0 high
  实测：graph_density(10,4)=2.5 ✅；生产全量图 Δ≈2.578（mid）

【RRF】retrieval.py:32
  score(c) = Σ_r 1/(k + rank_r(c) + 1),  k=60,  rank 从 0 起
  实测：_rrf(['a','b','c']) = {1/61, 1/62, 1/63} ✅

【7 维特征】training.py:41/106/148  →  见 M14

【人工加权】training.py:79
  hand_weighted_score = Σ w_i·f_i（struct/clue 截断到 1）
  HAND_WEIGHTS = normalize({sem .6911, struct .0195, clue 1.2543, type .0487,
                            same_frame .1953, same_cascade .1958, ground_jaccard .4965})
  实测：{sem .2382, struct .0067, clue .4323, type .0168, same_frame .0673,
        same_cascade .0675, ground_jaccard .1711} ✅

【L1.5 合并判据】extended.py:71-77
  同 frame_id ∧ 同 source_domain ∧ min_span_gap < 3 ∧ |ground_a ∩ ground_b| ≥ 1
  [可选 vehicle_repeat] ∧ (shared_triggers ≠ ∅ ∨ |ground_a ∩ ground_b| ≥ 2)

【lift】bootstrap_triggers.py:216 / llm_ontology.py:241
  lift(w) = (df_met(w)/(n_met+ε)) / (df_neu(w)/(n_neu+ε) + ε)
  保留：df_met ≥ 2 ∧ lift ≥ 3.0（动词通道 20）

【自适应阈值】context_budget.py:80
  τ 从 0.5 起，每次 −0.1，直到 |selected| ≥ min(50, |items|) 或降满 5 次

【上下文预算】context_budget.py:157
  budgets = [0.5, 0.3, 0.2] × max_tokens；cost = max(1, len/1.6)；未用完顺延

【全量 AUC】evaluate_hgnn.py:316
  AUC = P(pos > neg) + 0.5·P(pos == neg)

【诚实覆盖率】health.py:174-219  →  见 M9（含双分支分歧的标注）

【随机基线 MRR】evaluate_repaired.py:327
  E[MRR] = Σ_r [C(n−g, r−1)/C(n, r−1) × g/(n−r+1)] / r
  实测：random_baseline(1100, 1)["mrr"] = 0.0069 ✅
```

---

## 10. 本次审计新发现的实现分歧（汇总）

> 这几条是「文档/主张 ≠ 代码」的实质分歧，**均在本次审计中通过实际运行发现**。

| # | 分歧 | 影响面 | 建议 |
|---|---|---|---|
| 1 | **`compose(outer_zero=...)` 是死开关**：函数开头已 `return 0.0`，末行的条件恒 True | gen3 报告的"2⁴ 全因子对照"实为 2³；**结论方向不受影响** | 措辞更正为 2³；或删掉该形参 |
| 2 | **`propagation_matrix()` 与 `_conv()` 在含重复端点时不严格等价**（实测 maxdiff 0.048 单边 / 0.042 真实图；生产图 20.6% 的边含 `source_domain ∈ ground`） | 单测 `test_propagation_matrix_matches_conv` 用的是无重复的测试图故未捕获；两者都不在检索路径 | 补一条"含重复端点"的单测；或让 `_conv` 用 `set(members)` |
| 3 | **`health.registered_frame_coverage` 在同一函数内被算两遍**，分支二的 `frame_reliability(None) = 1.0` 与分支一矛盾；报出的 frame/cascade 字段来自分支二，而 `registered_hierarchy_coverage` 来自分支一 | 生产语料上恰好同值（0.756 = 0.756，实测），**属巧合**；有 `frame_id` 为空的边时两值矛盾（实测 1.0 vs 0.5） | 统一到单一分支；或明确 `None` 的语义 |
| 4 | **`S_conditional` 只在 `query_signal.py` 模块 docstring 中出现，无实现**（对应物是 `StratifiedNormalizer`） | 文档误导 | 更正 docstring |
| 5 | **`QuerySignal.summary()` 把 `S_log` 标成 `S_query`**（实测打印 `S_query=2.8904` 而真值 0.2646） | 诊断输出误导 | 修格式化字符串 |
| 6 | **`ground_jaccard` 两条路径定义不同**：文本版是包含率 `|g∩text|/|g|`，超边版是真 Jaccard（实测 4.76% 的候选对不同） | 已在 `probe_formula_divergence.py` 标注，未修 | 决策：统一 or 保留并文档化 |
| 7 | **`sem` 的 clamp 不一致**：训练版 `max(0, cos)`，检索人工加权版无 clamp | 此数据上余弦非负，未触发 | 统一 |

---

## 附录：概念计数

| 家族 | 条目数 | 其中已证伪/退役 | 其中生产路径 |
|---|---|---|---|
| 结构概念 | 14 | 1（S6 定位降级）；3 未验证（S10/S11/S12） | 9 |
| 语言学概念 | 11 | 1（L11 降级） | 9 |
| 度量概念 | 21 | 5（M1/M3/M5 + M4/M21 部分） | 12 |
| 工程概念 | 24 | 6（E5/E6/E14/E20/E22 部分 + E1 强成立） | 17 |
| 评测概念 | 12 | 3（T2/T12 + T3 概念性） | 8 |
| **合计** | **82** | **约 16** | **约 55** |

> **给论文的一句话**：这 82 个概念里，**约 16 个被本项目自己的实验推翻或降级**，
> 其中包括 4 个由作者本人提出并寄予厚望的核心设计（Ω、类型约束压 P1、L3 层级、源项）。
> 这 16 条负面结果不是项目的失败清单，而是**隐喻结构化检索的可行边界**——
> 也是本词典存在的主要理由。
