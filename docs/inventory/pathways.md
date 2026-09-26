# 全量通路目录（pathways）

> 本文深化 `docs/inventory/_extracted.json` 的 77 条机械候选，补齐**未被正则覆盖**的通路。
> 全部结论基于**读代码 + AST 调用点扫描 + 运行时探针**，不基于 docstring。
> 代码只读；本文件为唯一写入产物。
>
> 骨架来源：`metaphor_graph/inventory.py::pathways`（`PATHWAY_PAT` 正则 + 非下划线开头 + 有 docstring 才收）。
> 该正则**系统性漏掉三类**：① 下划线开头的内部数据流（`_ensure_cascades`、`_pair_features`、`_llm_cluster_fallback` 等）；
> ② 名词性入口（`gate_by` 命中，但 `main`/`stage_*`/`precompute_all`/`forward`/`pack` 不命中）；③ 同名方法跨实现重复计数。
>
> **本次逐条核实后的条目数（可核对 §1 汇总表与 §14 映射附录）**：
>
> | 口径 | 数量 |
> |---|---|
> | 骨架候选条目 | **77** |
> | 骨架去重后的 `(module, func)` 对 | **66**（`llm_backend.py::discover` ×6、`::refine` ×6、`observability.py::measure` ×2 → 去重 11 条） |
> | 本目录通路条目（§1 汇总表行数） | **98** |
> | 其中**能追溯到骨架条目**的行 | **43** |
> | 其中**骨架完全未收录**的新通路 | **55** |
>
> 骨架 66 个去重条目**全部被本文覆盖**（逐条归属见 §14，无遗漏）。
> 新增的 55 条主要来自：内部下划线流程（`_ensure_cascades`/`_pair_features`/`_llm_cluster_fallback` 等 12 条）、
> 评测流水线（`stage_*`/`build_global_graph`/`pathway_rankings` 等 14 条）、
> 信号与测量（`measure_signal`/`reachable_structure`/`graph_health` 等 8 条）、
> 构建（`_canonicalize`/`_build_variant` 等 6 条）、检索（`pack_context`/`reliability_factor` 等 10 条）、
> 抽取（`_refine`/`_type_coherent`/`_fuzzy_match_frame` 等 8 条）、LLM 批处理（`precompute_all`/`batch_refine` 等 6 条）、
> 存储与演化（`resolve_conflict`/`describe` 等 5 条）——**去重合并后计**。
> 逐族分布见 §13 第 1 条。

---

## 0. 阅读约定

| 标记 | 含义 |
|---|---|
| ✅ 生产 | 在已上报数字的生产路径上，有非测试调用点 |
| 🔧 可选 | 生产可达但默认关闭 / 需显式参数 |
| 📊 评测 | 只在评测脚本内跑，不参与抽取-构建-检索主干 |
| ⚠️ 存在但未接入 | 代码存在、有测试，但**生产路径从不调用** |
| 💀 死代码 | 连测试都不调用，或逻辑上不可达 |
| ⚪ 工具 | 不是通路（见 §11 排除清单） |

**行号约定**：`file.py::func` 后的 `L<n>` 指**该通路所在的代码块行号**（通常是函数体内的一段），
不一定等于 `def` 所在行。例：`extractor.py::extract` L232-242 指 `extract`（def 在 L170）内的**通道一代码块**。
若一处行号歧义（如同名函数），文中会显式区分（如 `observability.py::measure` L229 是模块函数、L282 是 `ObservabilityMeter.measure` 方法）。
本文档所有 `file.py::func` 引用（85 个去重后）已用 AST 逐条核对存在性。

「实测状态」列引用：`experiments/实验结论汇总.md`、`experiments/gen2/REPORT.md`、`experiments/gen3/REPORT.md`、
`experiments/REPORT_exp-{source,cascade,degrade,dynamics}.md`、`experiments/三通路重测_修复后基准.md`、
`experiments/A6预算对等修正.md`、`experiments/三臂对等审计.md`、`experiments/组件处置决策.md`、
`experiments/REPORT_benchmark_repair.md`、`metaphor_graph/README.md`、`论文初稿.md`。

**本文档结构**：§1 汇总表（98 条，逐族）｜§2-§8 分族详解｜§9「存在但未接入」+ 文档口径不一致｜
§10 骨架未覆盖的通路（按漏因归类）｜§11 排除清单（26 项不是通路的东西）｜§12 复现命令与探针脚本正文｜
§13 关键观察｜§14 骨架 77 条 → 本目录 ID 的逐条映射附录。

---

## 1. 汇总表

### A. 抽取通道与双防线（11 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| A1 | 通道一 触发词匹配 | `extractor.py::extract` L232-242 | ✅ 生产 | 召回 7.6%（纯规则侧天花板，README §6.9） |
| A2 | 通道二 MIPVU 语义域失谐 | `extractor.py::extract` L244-255 → `mipvu.py::mipvu_candidates` L63 | 🔧 可选（`use_semfield`，默认 False；**所有生产脚本显式传 True**） | 边际贡献 **+0.6pp** 召回（12.4%−11.8%），README §7.1 A3 |
| A3 | 通道三 LLM 开放发现 | `extractor.py::extract` L257-275 → `llm_backend.py::OpenAIBackend.discover` L311 / `discover_batch` L331 | 🔧 可选（`llm_backend`） | **+55.9pp 召回**（0.696−0.137），README §6.7；P1 7.9%→9.2% |
| A4 | 防线一 置信阈值（双门槛） | `extractor.py::extract` L200（`conf_threshold`）+ L262（`llm_conf_threshold`） | ✅ 生产 | 0.85 是达标拐点：0.85→召回 69.1%/P1 14.5%；0.90→54.7%/11.8%（README §6.7） |
| A5 | 防线二 refine 校验 | `extractor.py::_refine` L66 → `llm_backend.refine` L404 / `refine_batch` L370 | ✅ 生产（接后端时） | **决定性**：关 refine → P1 43.4%；开 refine → P1 **0.0%**（README §7.1 A3） |
| A6 | 类型安全约束（枚举） | `ontology.py::type_valid` L409 ← `extractor.py::emit` L177 | ✅ 生产 | **拦下 0 个**（本体构建时已保证合法）→ A1/H1 证伪（README §7.1） |
| A7 | 类型连贯性检查 | `extractor.py::_type_coherent` L126 ← `_frame_for_candidate` L81 | ✅ 生产 | 拦下 **24** 个错误绑定，但 **P1 纹丝不动**（候选退化为 `F_LLM_*` 后照样出边） |
| A8 | 模糊匹配绑定（三级） | `extractor.py::_fuzzy_match_frame` L140 | ✅ 生产 | 无它 L3 覆盖率崩到 **2.4%**；有它 → 100%（README §6.9） |
| A9 | GENERIC 通道（新喻体放行） | `extractor.py::_frame_for_candidate` L110-124 | ✅ 生产 | 开放发现换召回的代价载体；框架 id = `md5(src|tgt)` |
| A10 | 字面干扰词表 | `extractor.py::emit` L180-182 + `LITERAL_STOPWORDS` L34 | ✅ 生产 | 4 词表（苹果/水/火/路），只覆盖演示用例 |
| A11 | 确定性边 id | `extractor.py::emit` L207-209（md5） | ✅ 生产 | **踩坑修复**：uuid4 导致缓存重放金标全零（README §7.5 工程注记） |

### B. LLM 批处理与预取（6 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| B1 | 两趟预取管线 | `llm_backend.py::precompute_all` L695 | ✅ 生产（`evaluate_real --llm-batch>1`、`evaluate_document_corpus`） | 请求 1100→55，输入 token 省 ~86%（README §6.8） |
| B2 | 批量 discover + 断点续跑 | `llm_backend.py::batch_discover` L820 / `_batch_discover_uncached` L855 | ✅ 生产 | 整批全空自动重试+拆半（防静默丢批） |
| B3 | refine 请求收集器 | `llm_backend.py::_RefineCollector` L629 | ✅ 生产（`precompute_all` 内部） | 让 refine 从 2297 次降到 ~115 次 |
| B4 | 批量 refine | `llm_backend.py::batch_refine` L647 | ✅ 生产 | 同 B3 |
| B5 | 缓存重放后端 | `llm_backend.py::PrecomputedBackend` L586 + `save_table`/`load_table` L725/L733 | ✅ 生产（全部评测） | 零 API 重放全部已上报数字 |
| B6 | 致命错误不降级 | `llm_backend.py::_chat` L293-305（`LLMFatalError` L53） | ✅ 生产 | 402 欠费曾被吞成空结果 → 本体碎片化 2656 框架（README §7.2） |

### C. 构建路线（16 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| C1 | 四层构建 L0→L3 | `builder.py::build` L55 | ✅ 生产 | 主干；856 条 L1 边 / 110 伪文档 |
| C2 | L2 框架归属（查表） | `builder.py::build` L104-118 | ✅ 生产 | 查表 0 次 LLM 调用 |
| C3 | L3 级联归属（查表） | `builder.py::build` L120-138 | ✅ 生产 | 同上 |
| C4 | L1.5 跨 chunk 扩展链接 | `extended.py::link_extended_metaphors` L36 ← `builder.py` L66 | ✅ 生产 | P3 F1 **1.000**（精选集）；A5：关掉→F1 **0.000**（README §7.3） |
| C5 | L1.5 延续性判据 `vehicle_repeat` | `extended.py` L72-77 | 🔧 可选（`extended_continuity`） | **无效**：密度 52→49，存活链不变（README §7.1 改进闭环） |
| C6 | L1.5b LLM 逐链校验（构建器内） | `builder.py::build` L74-101 | ⚠️ **存在但未接入** | `llm_verify_extended` **无任何调用点**（全仓 grep 仅 builder 自身） |
| C7 | 孤儿框架兜底 | `builder.py::_ensure_cascades` L150 | ✅ 生产（`orphan_cascade_rule="target"` 默认） | 覆盖率 0.78→**1.000**；但补出 399 个 `C_ADHOC_`，size 中位数 1 |
| C8 | 未匹配回退 LLM 聚类 | `builder.py::_llm_cluster_fallback` L245 | 💀 **死代码** | 前置条件 `not e.frame_id` 在 extractor 产出中**恒为假**（探针实测 0 条）；仅手工注入边可触发 |
| C9 | 级联构造规则替换 | `cascade_rules.py::build_cascades` L164 / `apply_rule` L213 | 🔧 可选（`cascade_rule=`） | **度量中性**：7 种规则下主指标逐位相同（gen2） |
| C10 | 本体自举回流 | `llm_ontology.py::main` L372（`collect_pairs`→`_canonicalize`→`build_specs`→`filter_triggers_by_lift`→`save_specs`） | 📊 离线构建（一次性） | P0 31→**2222** 框架；P2 覆盖率 2.4%→100%（README §6.9） |
| C11 | 触发词 lift 过滤（自举侧） | `llm_ontology.py::filter_triggers_by_lift` L241 | 📊 离线构建 | 不过滤 P1 飙到 **60.5%**；过滤后 9.2% |
| C12 | 本体清洗沉淀 | `ontology_clean.py::clean` L156（`recompute_support`→`clean_frames`→`rebuild_cascades`） | 📊 离线构建 | V1 与 V0 **逐指标持平**（纯质量提升，README §6.10） |
| C13 | 清洗三变体验证 | `ontology_clean.py::verify` L267 | 📊 评测 | refine 缓存命中 **100%**（对照干净）；longtail 有 +1.2pp 召回价值 |
| C14 | 自举触发词挖掘 | `bootstrap_triggers.py::mine_triggers` L179 → `build_bootstrap_ontology` L260 | 🔧 可选（`--use-bootstrap`） | 等比模式串 + lift≥3.0；`F_BOOTSTRAP_NOUN` 触发词 |
| C15 | MetaNet 迁移种子 | `metanet_migrate.py::build_metanet_ontology` L126 | ✅ 生产（作为底座，`ontology_clean._build_variant` L241 必调） | 25 个种子框架 + 扩展 TYPE_CONSTRAINTS |
| C16 | 双语对齐 | `ontology_bilingual.py::build_bilingual` L189 / `llm_complete` L242 / `spot_check` L348 | 📊 离线资源 | 2177 框架对齐率 **100%**（curated 2 / auto_gloss 2175） |

### D. 检索通路（14 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| D1 | 字面通路（子串） | `retrieval.py::rrf_fusion` L347；`evaluate_repaired.py::pathway_rankings` L293 | ✅ 生产（作对照臂） | 改写型查询非空率 **0/777**；重叠型 Recall@10 0.8833 |
| D2 | 触发词级联通路 | `retrieval.py::cross_domain_retrieve` L138 | ✅ 生产 | 改写型 Hits@10 **0.0206**、非空率 0.192；重叠型 0.2000 |
| D3 | 级联语义回退 | `retrieval.py` L177-195 + `_cascade_index` L111 | 🔧 可选（`semantic_fallback`，默认 False） | 使级联通路 Recall 翻倍（0.020→0.042，README §7.5） |
| D4 | 语义超图通路（7 维排序） | `retrieval.py::rank_mappings` L314 → `metaphor_retriever_score` L264 → `_pair_features` L253 | ✅ 生产 | 改写型 MRR 0.1183（**随机 17.1×**）；重叠型 0.9200 |
| D5 | 查询侧超边锚定 | `retrieval.py::_query_edges` L227 | ✅ 生产（`_pair_features` 内） | 改写查询下 632 条中仅 **15 条**能形成查询侧边（gen3） |
| D6 | 文本锚点兜底 | `retrieval.py::_text_features` L244 | ✅ 生产（`_query_edges` 空时） | 与训练期口径统一（防特征漂移） |
| D7 | U-Retrieval（方案 B） | `metagraph.py::MetaphorURetrieval.retrieve` L112 + `_literal_retrieve` L103 | ⚠️ **存在但未接入** | 只被 `demo.py` 与单测调用；**任何评测脚本都不用** |
| D8 | 元图构建（L0/L1/L2） | `metagraph.py::MetaphorMetagraph.build_from_shg` L56 | ⚠️ **存在但未接入** | 只被 `demo.py:89` 调用 |
| D9 | 多线索汇聚 | `retrieval.py::multi_clue_retrieval` L217 | ⚠️ **存在但未接入** | 只被 `demo.py:110` 与单测调用 |
| D10 | RRF 融合 | `retrieval.py::rrf_fusion` L346 | ⚠️ **存在但未接入** | **只被单测调用**（`test_metaphor_graph.py:193`）；demo 用的是 cross_domain 而非 rrf |
| D11 | HL-index 可达性 | `hlindex.py::HLIndex.query` L53 / `reachable_targets` L60 | ⚠️ **存在但未接入** | 只被 `demo.py:141` 与单测调用；`_build` 是 O(V·E) 朴素实现 |
| D12 | 上下文预算打包 50/30/20 | `retrieval.py::pack_context` L334 → `context_budget.py::ContextBudget.pack` L157 | 📊 生成侧 | glm judge 下当前打包胜出（26.50 vs 21.12）；deepseek judge 下**反转**（6:1 对照胜） |
| D13 | 自适应阈值 | `context_budget.py::AdaptiveThreshold.select` L80 ← `cross_domain_retrieve` L203 / `rank_mappings` L323 | ✅ 生产 | 小语料 **无差异**（0.500 vs 0.500）；全量 1100 句 A8 亦无差异（中性结论扩大） |
| D14 | 溯源可靠性折扣 | `retrieval.py::reliability_factor` L91 → `provenance.reliability_factor` L88 | ✅ 生产（**默认 floor=0.5，即通道默认开启**） | **负面**：P1 效应恒为 0；人工加权 MRR −0.1025；全档位单调劣化（exp/degrade） |

### E. 校验路径（7 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| E1 | HGNN 跨层传播 | `hgnn.py::forward` L170 / `_conv` L123 | ⚠️ **存在但未接入** | 检索打分路径**从不调用**；flat≡HGNN（\|ΔAUC\|≤0.005，18 配置） |
| E2 | `metaphor_coherence` 图结构判据 | `hgnn.py::metaphor_coherence` L221 | 🔧 可选 | 真边 0.669 vs 负样本 0.197，配对判别 0.95；**但 flat 也 0.950 → 信号来自 L1 n 元共现** |
| E3 | HGNN 图感知检索 | `hgnn.py::retrieve` L234 / `retrieve_raw` L251 | 📊 评测 | P4-A：哈希向量下 HGNN 0.896 vs raw 1.000（**−0.104**）；真实向量下**翻案**（1.000 vs 0.938） |
| E4 | HGNN 谱分析接口 | `hgnn.py::propagation_matrix` L152 | 💀 **死代码**（生产） | 只被单测调用（7 处）；`experiments/_common.py` 另写了一份等价实现 |
| E5 | LLM 逐链校验（独立函数） | `llm_backend.py::verify_chains_batch` L757 | 📊 评测（构建器侧 ⚠️ 未接入） | 52 条候选通过 11 条（21.1%）；保留集精度 63.6%（vs 未过滤 16.7%） |
| E6 | 链质量评审（跨模型 judge） | `evaluate_chain_quality.py::main` L93 | 📊 评测 | 严格口径精度 **16.7%**；`--llm-verify` 后 71.4%（n=7，跨模型） |
| E7 | coherence 过滤（第三道校验） | `evaluate_chain_quality.py` L144-160 | 🔧 可选（`--coherence-threshold`，默认 0） | 阈值 0.5 时保留 **52/52**（中位连贯度 0.820）→ **零过滤力** |

### F. 评估路径（21 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| F1 | P1 抽取评测 | `evaluate_real.py::eval_split` L81 | 📊 评测 | P1 0.092 / 召回 0.696 / P/R/F1 0.990/0.696/0.818 |
| F2 | LLM 后端构造（含回落告警） | `evaluate_real.py::build_llm_backend` L36 | ✅ 生产（评测基础设施） | 无 key 静默回落曾产出**假性 P1 0.434**（真值 0.092）→ 已加显式告警 |
| F3 | A1/A2/A3/A4 消融 | `ablation.py::run_a1` L98 / `run_a2` L163 / `run_a3` L194 / `run_a4` L215 | 📊 评测 | A1 证伪；A2 34% 框架需回退聚类；A4 召回 −1.8pp |
| F4 | P3 + H3/A5/A8/A7/A9 | `evaluate_retrieval.py::measure_p3` L68 / `measure_h3` L109 / `measure_p3_flag` L142 / `measure_a8` L164 | 📊 评测 | P3 F1 1.000；H3 成立；A5 成立（关掉 F1=0）；A8 无差异；A7/A9 不成立（小集） |
| F5 | 全量建图 A7/A8/A9 复验 | `evaluate_fullcorpus.py` L132-329（`build_replay_ontology` L69 / `build_replay_backend` L86 / `build_queries` L103） | 📊 评测 | 856 边 / 861 查询；A7 证伪→gen1 翻转为成立→gen3 归因修正为 +0.29pp |
| F6 | 排序臂共享打分 | `evaluate_retrieval.py::score_conditions` L200 | 📊 评测 | 四臂（trained / no_role / hand_recalibrated / hand_legacy）；**所有 §6.2 数字的真源** |
| F7 | P4-A / P4-B / H4 | `evaluate_hgnn.py::measure_p4a` L81 / `measure_p4b` L113 / `measure_h4` L225 | 📊 评测 | P4-A 无增益（哈希）/ 翻案（真实）；H4：flat 0.910 ≈ HGNN 0.915，raw 0.550 |
| F8 | LLM 非构造金标三阶段 | `evaluate_llmgold.py::stage_gen` L144 / `filter_violations` L186 / `stage_judge` L222 / `stage_eval` L274 | 📊 评测 | 红线剔除 26.7%；构造金标一致性 96.8%；**但 632/632 金标仍含产出 chunk（锚定未解除）** |
| F9 | 修复版基准（全局池+去锚定） | `evaluate_repaired.py::build_global_graph` L65 / `build_query_sets` L198 / `rank_all` L254 / `pathway_rankings` L277 | 📊 评测 | anchored MRR 0.8956 / deanchor 0.2330（随机 33×）；锚定抬高 **+0.66** |
| F10 | 三通路四族分解 | `evaluate_repaired.py::pathway_rankings` L277 | 📊 评测 | 语义 0.1183 vs 级联 0.0206 vs 字面 0.0000（改写型 anchored） |
| F11 | 改写型查询映射 | `evaluate_repaired.py::build_paraphrased_sets` L164 | 📊 评测 | 用 LLM 改写缓存把改写查询映射到全局池金标 |
| F12 | 真实句向量复测 | `evaluate_repaired_real.py::main` L99（`CachedRealEmbedder` L45） | 📊 评测 | 锚定效应与向量器**正交**（+0.66 vs +0.69）；子集覆盖 81.9% |
| F13 | 连贯文档语料 L1.5 验证 | `evaluate_document_corpus.py::build_chunks` L106 / `run_pipeline` L121 / `report` L222 | 📊 评测 | 106 篇/1050 chunk；链/百 L1 从 0.6%→**6.3%**（10×） |
| F14 | A6 常识替代消融 | `evaluate_a6.py::build_cs_neighbors` L87 + `main` L129 | 📊 评测 | 隐喻 1.000 vs 常识 0.095（**10.5×**，预算对等修正后）；但隐喻臂 1.000 亦饱和 |
| F15 | LLM-as-judge 预演 | `evaluate_llmasjudge.py::main` L90 | 📊 评测 | 4 维度盲评；结论对 judge 模型**高度敏感** |
| F16 | 上下文打包消融 | `evaluate_packing_ablation.py::main` L115 | 📊 评测 | 4 变体盲评；glm 与 deepseek judge **结论相反** |
| F17 | 金标跨模型交叉审核 | `evaluate_gold_audit.py::main` L62 | 📊 评测 | 同模型换序 κ=**0.912**（n=50 / 420 对） |
| F18 | 比较公平性审计 | `audit_fairness.py::scan` L70 | 📊 工具门 | 抓出三处预算/池/口径不对等（已加单测护栏） |
| F19 | 论文图表生成 | `make_figures.py::main` L148 | 📊 工具链 | 数字硬编码在脚本内，重跑实验须同步更新 |
| F20 | 资源与基准打包 | `package_release.py::main` L98 | 📊 工具链 | 产出 `release/metaphor_resources` + `MetaphorRAG-Bench` |
| F21 | 论文中→英翻译 | `translate_paper.py::main` L89 | 📊 工具链 | 分节翻译 + 缓存 |

### G. 信号 / 测量通路（17 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| G1 | Ω 查询侧可观测性 | `observability.py::measure` L229 | 📊 测量（**不接检索**） | ρ(Ω, n_seed)=**0.9949**；Ω>0 ⟺ n_seed≥1 逐条一致 → 退化为 1-bit |
| G2 | Ω 激活结构分解 | `observability.py::activated_structure` L122 | 📊 测量 | 涌现目标域恒为空集（99.2% 级联单目标域） |
| G3 | Ω 门控 | `observability.py::ObservabilityMeter.gate` L294 | ⚠️ **存在但未接入** | 只被单测调用；实测**严格弱于**现有 `if not agg` 判据（漏 66 条） |
| G4 | S_query 查询侧标量 | `query_signal.py::measure_signal` L278 | 📊 测量 | 最强候选（source 规则 0.8243），但**控制集合大小后 AUC 覆盖 0.5** |
| G5 | 合成开关器 compose | `query_signal.py::compose` L140 | 📊 测量（机制归因） | 64 组合全落在 0.50–0.62（json）；元凶是 Ω_N 的 `min(1,·)` 截断 |
| G6 | 可达结构（两种口径） | `query_signal.py::reachable_structure` L79 | 📊 测量 | `n_emergent`（仅目标域）vs `n_new_domains`（目标∪源域） |
| G7 | 分层归一化 | `query_signal.py::StratifiedNormalizer.fit` L341 | 📊 测量 | gen2 的 0.836 是**集合大小伪影**（控制后 0.4625，低于随机） |
| G8 | 通用门控 gate_by | `query_signal.py::gate_by` L381 | 💀 **死代码** | **零调用点**（含测试）；docstring 自称「不接检索路径」 |
| G9 | 图健康度 | `health.py::graph_health` L109 | ✅ 生产（运维信号） | 密度 Δ、孤儿率 84.8%、元数 3.58 |
| G10 | 诚实覆盖率（双口径） | `health.py` L174-219 | ✅ 生产（`ontology=...` 时） | 报出 1.000 vs 诚实 **0.776**（低于 85% 门槛） |
| G11 | 溯源可靠性派生 | `provenance.py::frame_reliability` L51 / `edge_reliability` L73 | ✅ 生产 | 判据必须是「本体有无条目」而非 `F_LLM_` 前缀（98.6% 正式框架是该前缀） |
| G12 | 7 维特征抽取（两路径） | `training.py::extract_features` L148 / `extract_text_features` L106 | ✅ 生产 | 曾**特征漂移**（1.0 vs 0.0，22.0% 候选对分歧）→ 已统一到 `type_reliability_of` |
| G13 | 自监督训练集构造 | `training.py::build_training_set` L342 / `_build_from_chunks` L244 / `_chain_pairs` L315 | ✅ 生产 | chunk 模式**不泄漏**；chain/cascade 模式**有泄漏**（`same_cascade` 即标签） |
| G14 | LLM 弱监督训练集 | `training.py::build_weak_refine_set` L570 | 🔧 可选（`--weak-refine`） | 打破 clue-AUC≈1.0 天花板；排序收益未证明（MRR −0.013） |
| G15 | 排序器训练 | `training.py::MetaphorScorer.fit` L485 / `score_features` L542 | ✅ 生产 | 训练增益**仅 anchored 口径为正，去锚定一致为负**（四族） |
| G16 | 人工加权打分 | `training.py::hand_weighted_score` L79 + `HAND_WEIGHTS` L76 / `HAND_WEIGHTS_LEGACY` L62 | ✅ 生产 | 原 `struct` 过权 **37–49×**、`type` 12–19× → 重标定后 anchored +0.0565 |
| G17 | 泄漏自检门 | `training.py::feature_auc` L194 / `leakage_report` L216 / `trivial_separators` L225 | ✅ 生产（评测门） | `leakage_report` 在 `evaluate_fullcorpus` 每文档调用并计数 |

### H. 存储 / 导出 / 演化（6 条）

| # | 名称 | 位置 | 状态 | 实测 |
|---|---|---|---|---|
| H1 | Cypher 导出 | `storage.py::shg_to_cypher` L65 | 🔧 可选 | 只被 `demo.py:146` 与单测调用 |
| H2 | JSON 导出 | `storage.py::shg_to_json` L161 | 🔧 可选 | 同上（demo 会重写 `export_shg.json`） |
| H3 | Neo4j 写入 | `storage.py::Neo4jStore.load_shg` L258 | ⚠️ **未接入** | 有 mock 单测；**真库连通验证待本机 Neo4j**（README §8.1） |
| H4 | 证据链合并 | `models.py::merge_evidence` L212 | ⚠️ **存在但未接入** | 只被单测调用 |
| H5 | 冲突消解 | `models.py::resolve_conflict` L227 | ⚠️ **存在但未接入** | 只被单测调用（4 处） |
| H6 | 超边自然语言渲染 | `models.py::describe` L108 | ✅ 生产 | 向量化与生成上下文的唯一入口（HyperGraphRAG 做法） |

---

## 2. 抽取通道与双防线（详细）

### A1 通道一：触发词匹配

- **位置**：`metaphor_graph/extractor.py::MetaphorExtractor.extract` L232-242
- **输入 → 输出**：`chunk:str` + `self.ont._trigger_index` → `List[MetaphorHyperedge]`（经 `emit`）
- **机制**：先取本体全部触发词做**子串包含**判断（`t in chunk`，O(#triggers)），命中的 token 交给 `ont.match_by_triggers`（按命中数排序）→ 每个候选框架用 `_locate_triggers` 在原文里定位所有出现位置 → 交给闭包 `emit` 过三道关（类型/字面词/置信）。
- **是否被采用**：✅ 生产。所有抽取入口（`evaluate_real.eval_split`、`evaluate_fullcorpus`、`builder.build`）都走这里。
- **实测状态**：**正向但受限**。纯规则侧召回天花板 **7.6%**（P1 7.9%，README §6.9 表）；接入 LLM 后触发词通道仍是 refine 校验的必经之路。
- **依赖/被依赖**：依赖 `ontology._trigger_index`（本体自举 C10 提供触发词）；被 A5（refine）、A6/A7（类型）消费。

### A2 通道二：MIPVU + Wmatrix 语义域失谐

- **位置**：`extractor.py::extract` L244-255 → `mipvu.py::mipvu_candidates` L63
- **输入 → 输出**：`chunk:str`, `ontology` → `List[{"frame_id","cascade_id","start","end","vehicle","conf"}]` → 超边
- **机制**：jieba 分词 → 每个词打 USAS 风格语义域（`semfield.tag_token`，**纯词表查表，6 个域**）→ 两条判据取其一：(a) 喻体词 ±2 token 内有等比标记（`是/像/如/如同/成为…`，作为独立 token 匹配以免「如」误中「栩栩如生」）conf=0.5；(b) 语义失谐（词域≠语篇主导域）且该域词在 chunk 中稀有（count≤1）conf=0.45/0.4。另有**域内字面护栏**：同域词≥2 且即主导域 → 跳过。
- **是否被采用**：🔧 `use_semfield` **默认 False**，但**全部生产评测脚本显式传 True**（`evaluate_real --use-semfield`、`evaluate_fullcorpus` L195、`evaluate_llmgold` L454、`evaluate_repaired` L84、`demo_llm` L53 等 40+ 处）。因此实际是生产开启的。
- **实测状态**：**弱正**。边际召回贡献 **+0.6pp**（12.4%−11.8%，README §7.1 A3），远低于早期纯规则配置下的估计。
- **依赖/被依赖**：依赖 `semfield` 词表 + `FIELD_TO_FRAME/FIELD_TO_CASCADE` 桥接；被 A5（refine）与 A6（类型约束）消费。
- **⚠️ 已修缺陷（gen2）**：原实现把整条通道**门控在 6 个硬编码级联 ID** 上，任何替换级联构造规则的实验都会**静默关掉该通道**（丢 7 条 L1 边）。现改为「框架存在 + 框架有级联归属」，默认路径逐位不变。

### A3 通道三：LLM 开放发现

- **位置**：`extractor.py::extract` L257-275 → `llm_backend.py::OpenAIBackend.discover` L311（逐句）/ `discover_batch` L331（20 句/批）
- **输入 → 输出**：`chunk:str` → `List[LLMCandidate]{source_domain, target_domain, ground, triggers, confidence}` → 超边
- **机制**：提示词内嵌 **MIPVU 判据**（基本义≠语境义 + 三类排除项：词汇化成语、描写性美称、字面身份判断句），并要求模型先输出 `basic_meaning` 字段（逼它走一遍判据）。产出候选后：置信门槛（A4）→ `_frame_for_candidate`（A8/A9）→ 触发词**必须能在原文定位**（否则当「悬空候选」丢弃）→ `emit(skip_refine=True)`。
- **是否被采用**：🔧 `llm_backend is not None` 时才走；`PrecomputedBackend` 让它在零 API 成本下全量重放。
- **实测状态**：**决定性正增益**。召回 13.7%→**69.6%**（**+55.9pp**）；代价 P1 7.9%→9.2%。去掉 MIPVU 判据段，P1 飙到 **28.9%**（`llm_backend.py` L129-131 注释）。
- **依赖/被依赖**：依赖 B1-B5（预取/缓存）；产出的 `F_LLM_*` 临时框架喂给 C7（孤儿兜底）与 G11（可靠性）。

### A4 防线一：置信阈值（双门槛）

- **位置**：`extractor.py::extract` L200（`base < self.conf_threshold`）+ L262（`cand.confidence < self.llm_conf_threshold`）
- **输入 → 输出**：`base:float`（触发词命中数换算 `min(1, 0.4+0.2n)` 或通道 hint 或 refine 置信度）→ 通过/丢弃
- **机制**：**两个独立门槛**。基础门槛 `conf_threshold=0.35` 管触发词/语义域通道；LLM 通道用更严的 `llm_conf_threshold=0.5`（生产用 0.85）单独把关，因为 GENERIC 通道绕过了类型护栏。
- **是否被采用**：✅ 生产。
- **实测状态**：0.85 是**达标拐点**：0.85→召回 69.1%/P1 14.5%（勉强达标）；0.90→54.7%/11.8%（留余量）。见 README §6.7。
- **依赖/被依赖**：与 A5（refine）构成「双防线」；单独关 refine 时 P1 43.4%，说明**阈值不足以替代 refine**。

### A5 防线二：refine 校验

- **位置**：`extractor.py::_refine` L66 → `llm_backend.refine` L404 / `refine_batch` L370 / `LocalHeuristicBackend.refine` L572
- **输入 → 输出**：`(chunk:str, frame:FrameSpec)` → `Optional[{"confidence":float,"ground":List[str]}]`
- **机制**：对触发词/语义域通道已命中的候选做**二次是/否判断**。返回 `None` 有**两种含义**（代码刻意区分）：① 后端判为非隐喻；② **没有接后端**——此时调用方 `if self.llm_backend is not None or self.llm_fn is not None: return None` 才视为否定判断。
- **是否被采用**：✅ 生产（接后端时）。
- **实测状态**：**压 P1 的主力**。触发词+语义域、**无** refine → P1 **43.4%**；**有** refine → P1 **0.0%**（README §7.1 A3）。这条也是 exp/degrade 独立证实的：7 条 FP 句的边全部来自 discover 通道（`skip_refine=True`），**从未过 refine**。
- **依赖/被依赖**：被 A4 的 LLM 通道**绕过**（`skip_refine=True`）——这是 7 条 FP 的成因，也是「让 discover 候选也过 refine」这条建议的依据。
- **⚠️ 消融陷阱**：`llm_backend=None` 会**顺带关掉 refine**，两个变量一起变 → 实测 P1 假性飙到 0.434。`ablation.run_a3` 用 `TrackedBackend` 隔离此变量。

### A6 类型安全约束（枚举式）

- **位置**：`ontology.py::type_valid` L409 ← `extractor.py::emit` L177
- **输入 → 输出**：`(source_type, mapping_type)` → `bool`
- **机制**：查 `TYPE_CONSTRAINTS` 白名单字典（17 个 source_type 键）。
- **是否被采用**：✅ 生产。
- **实测状态**：**拦下 0 个候选，P1 0.092→0.092**（A1/H1 **证伪**）。根因：本体构建时已保证所有 `(source_type, mapping_type)` 合法；且自举框架 98.6% 是 `GENERIC_VEHICLE → GENERIC_VEHICLE_MAP`（无条件合法）。
- **依赖/被依赖**：被 `metanet_migrate`（C15）与 `llm_ontology.build_llm_ontology`（C10 L353-355）**动态扩充**——每接受一个新映射类型就必须扩一次类型系统。

### A7 类型连贯性检查（开放式发现的真护栏）

- **位置**：`extractor.py::_type_coherent` L126 ← `_frame_for_candidate` L81（4 个调用点：L85/L90/L97/L104）
- **输入 → 输出**：`(cand_src_domain:str, frame:FrameSpec)` → `bool`
- **机制**：用 `infer_source_type(cand_src_domain)`（关键词表推断）与 `frame.source_type` 交叉验证。**任一边推断不出（GENERIC_VEHICLE）则放行**——信息不足时不拦。这是模糊匹配（A8，为覆盖率用子串包含）的必要对冲。
- **是否被采用**：✅ 生产。
- **实测状态**：拦下 **24** 个错误绑定；但 **P1 纹丝不动**（0.092→0.092）。根因：被拒绑的候选**没有被丢弃**——它退化成临时框架 `F_LLM_*` 后照样产出超边。这是 exp/degrade 的起点。
- **依赖/被依赖**：依赖 `infer_source_type`（`ontology.py` L70，`_SOURCE_TYPE_RULES` L30 关键词表）；与 G11（可靠性）、A6 共同构成「类型护栏三件套」。

### A8 模糊匹配绑定（三级）

- **位置**：`extractor.py::_fuzzy_match_frame` L140，调用 L96（源+目标）/ L102（仅源域）
- **输入 → 输出**：`(src:str, tgt:str, require_target:bool)` → `Optional[FrameSpec]`
- **机制**：**子串包含**（`f.source_domain in src or src in f.source_domain`）双向匹配，取重叠长度最大者；命中两侧额外加权。三级降级：精确 → 源+目标模糊 → 仅源域模糊（目标域作排序依据）。
- **是否被采用**：✅ 生产（LLM 通道必经）。
- **实测状态**：**覆盖率的关键**。模型说「水流漩涡」、本体写「水流」，字符串永不相等 → 全靠精确匹配时 L3 覆盖率崩到 **2.4%**；只靠「源+目标」时停在 **62.3%**；加三级后 → **100%**（门槛 85%）。见 README §6.9。
- **依赖/被依赖**：与 A7 强耦合（模糊匹配天然可能绑到语义不相干框架）；被 G11（`frame_reliability`）间接度量。

### A9 GENERIC 通道

- **位置**：`extractor.py::_frame_for_candidate` L110-124
- **输入 → 输出**：`LLMCandidate` → `FrameSpec`（`id="F_LLM_"+md5(src|tgt)[:8]`, `mapping_type="GENERIC_VEHICLE_MAP"`, `source_type="GENERIC_VEHICLE"`）
- **机制**：三级匹配都失败时**不丢弃候选**，而是造一个临时框架放行（类型护栏对 GENERIC 无条件合法），由更严的 `llm_conf_threshold` 单独把关。
- **是否被采用**：✅ 生产。
- **实测状态**：**这是 +55.9pp 召回的载体**，也是 P2 覆盖率注水的来源（诚实覆盖率 0.776 vs 报出 1.000）。
- **依赖/被依赖**：喂给 C7（`_ensure_cascades` 补 `C_ADHOC_`）与 G11（可靠性封顶 0.5）。
- **⚠️ id 空间陷阱**：`extractor.py:113` 用 `md5("src|tgt")`，`llm_ontology.py:201` 用 `md5("src||tgt")`（**双竖线**）——两套 id 空间不相交但**共用 `F_LLM_` 前缀**。实测 856 条边里 90.5% 以 `F_LLM_` 开头，但只有 188 条（22.0%）真正未注册。

### A10 字面干扰词表

- **位置**：`extractor.py::emit` L180-182 + `LITERAL_STOPWORDS` L34
- **机制**：`{"苹果":"水果公司名","水":"饮品","火":"物理明火","路":"物理道路"}`，命中即丢弃（除非框架源域是「水果/自然物」）。
- **是否被采用**：✅ 生产但**覆盖极窄**（4 词，服务于 `demo.py` 的 chunk7 演示）。
- **实测状态**：`demo.py` 环节 3 验证 chunk7（苹果发布手机）无字面误判 ✅。
- **依赖/被依赖**：无。是 P1 门槛的**玩具级**保障，真正的保障是 A5。

### A11 确定性边 id

- **位置**：`extractor.py::emit` L207-209（`md5(chunk_id|start|end|src|tgt)`）；`extended.py` L87；`training.py` L644
- **输入 → 输出**：跨度键 → `"L1_" + md5[:8]`
- **机制**：**不用 uuid4**。同一 `(chunk, span, source, target)` 永远得到同一 id。
- **是否被采用**：✅ 生产。
- **实测状态**：**踩坑修复**。首轮 judge 缓存重放时金标全零——L1 边 id 原为 uuid4，跨进程对不上号。有回归护栏 `TestDeterministicIds`。
- **依赖/被依赖**：被 F8（`stage_judge`）、F9（全局池）、H3（Neo4j）等**所有跨进程引用边 id** 的通路依赖。

---

## 3. 构建路线（详细）

### C1-C3 四层构建 L0→L3（含 L2/L3 查表）

- **位置**：`builder.py::MetaphorSHGBuilder.build` L55；L1 段 L56-63；L1.5 段 L65-101；L2 段 L103-118；L3 段 L120-138
- **输入 → 输出**：`(chunks:List[str], doc_id:str)` → `MetaphorSHG{edges, frames, cascades}`
- **机制**：
  - **L1**：逐 chunk 调 `extractor.extract`（`chunk_id = f"{doc_id}_c{i}"`），汇总所有边。
  - **L1.5**：`link_extended_metaphors`（C4）。
  - **L2**：`frames_by_id[e.frame_id]` 分组 → `MetaphorFrame`。**纯字典查表，非聚类**。
  - **L3**：`ont.get_cascade(f.id)` → `cascades_by_id` → `MetaphorCascade`。**同样是查表**。
- **是否被采用**：✅ 生产主干。
- **实测状态**：成本主张成立——查表 **0 次** LLM 调用，需回退聚类的框架占 34.0%（→ 187 次/千边 vs embedding 聚类的 ~200 次）；见 README §7.1 A2。
- **依赖/被依赖**：依赖 A1-A9（抽取）、C4（L1.5）、C7（兜底）、本体（C10-C15）。

### C4 L1.5 跨 chunk 扩展链接

- **位置**：`extended.py::link_extended_metaphors` L36 ← `builder.py:66`
- **输入 → 输出**：`(edges, chunk_order:Dict[str,int], max_gap=3, continuity="ground1")` → `List[MetaphorHyperedge]`（`is_extended=True, layer=1.5`）
- **机制**：按 `(frame_id, source_domain)` 分组 → 组内按 chunk 序排序 → **贪心链式合并**：相邻两条的 chunk 间距 `< 3` **且** 喻底交集 ≥1 才合并（`continuity="vehicle_repeat"` 时还要求同触发词跨 chunk 复现或喻底交集≥2）。合并后：喻底/触发词取并集，置信度取 max，**`provenance_reliability` 取链上 `min`**（退化边不得借合并洗白），id = `"EXT_"+md5(frame|src|chunk_ids)`。
- **是否被采用**：✅ 生产（`use_extended=True` 默认）。
- **实测状态**：**A5 成立**——关掉后 P3 F1 从 **1.000 → 0.000**（扩展边是 P3 的唯一来源）。但质量维度：严格 MIPVU 口径精度仅 **16.7%**（失败主因是词化惯用语「基础上/聚焦/扎根」被计为隐喻提及）。
- **依赖/被依赖**：被 C5/C6/E5/E7 三种「延续性判据」增强；被 D4 的 `ground_jaccard`/`same_frame` 特征与 G13（`_chain_pairs`）消费。

### C5 `vehicle_repeat` 延续性判据

- **位置**：`extended.py` L72-77；参数入口 `builder.py` L53（`extended_continuity`）
- **是否被采用**：🔧 可选（`--continuity vehicle_repeat`，默认 `ground1`）。
- **实测状态**：**无效**。密度 52→49，**存活链完全不变**（README §7.1 改进闭环①）。
- **依赖/被依赖**：被 C6/E5/E7（语义级方案）替代。

### C6 L1.5b LLM 逐链校验（构建器内）⚠️ 存在但未接入

- **位置**：`builder.py::build` L74-101（`llm_verify_extended` L31 + `verify_cache_path` L32）
- **机制**：对每条扩展边构造 `key = f"{doc_id}|{source}|{'、'.join(sorted(ground)[:4])}"` → `verify_chains_batch`（E5）→ 未通过的边从 `all_edges` 中剔除。**失败纪律**：校验缺失（批次失败不写缓存）按**未校验剔除**（严格口径优先）。
- **是否被采用**：⚠️ **存在但未接入**。全仓 grep：`llm_verify_extended` 只出现在 `builder.py` 自身（L31/L35/L74）。**没有任何调用点传它**——`evaluate_document_corpus`（F13）走的是**脚本内后过滤**（L167-194），不是这条构建器内通路。
- **实测状态**：**未实测**（该代码路径从未执行过）。脚本侧的等价后过滤实测：52 条候选通过 11 条（21.1%），保留集精度 63.6%。
- **依赖/被依赖**：依赖 E5（`verify_chains_batch`）；`后续待办.md` B1 明确把它列为待接入项。
- **⚠️ 附带死代码**：L94-96 有一个空 `for e in kept: if e in all_edges: pass` 循环——无任何作用。

### C7 孤儿框架兜底

- **位置**：`builder.py::_ensure_cascades` L150 ← `build` L146
- **输入 → 输出**：`(all_edges, frame_objs, cascade_objs)` → 就地追加 `C_ADHOC_*` / `C_ADHOC_SOURCE_*` 级联
- **机制**：找出不属于任何级联的框架（`F_LLM_*` 临时框架）→ 按 `orphan_cascade_rule` 分组（默认 `"target"` = 按目标域；可选 `source`/`ground`/`source_type`/`none`）→ 每组造一个 `C_ADHOC_<TAG>_<md5(key)[:8]>` 级联（已存在则合并成员）。
- **是否被采用**：✅ 生产（默认 `target`）。
- **实测状态**：**覆盖率注水的来源**。它唯一的量化收益是 `graph_health.cascade_coverage` 从 ~0.78 抬到 **1.000**；但补出的级联与本体级联**结构同构**（成员共享单一目标域），跨域扩展能力为零（110 次 build 共补 399 个 `C_ADHOC_`，size 中位数 1、max 1）。关掉后覆盖率 **1.000 → 0.767**，跌破 85% 门槛。
- **依赖/被依赖**：依赖 A9（GENERIC 通道产生孤儿框架）；产出喂给 G9/G10（覆盖率）与 gen2 的 `orphan_cascade_rule` 对照实验。
- **⚠️ 结构缺陷（gen2 已定案）**：`_ensure_cascades` **不回写 `edge.cascade_id`** —— 实测 `edge.cascade_id` 以 `C_ADHOC_` 开头的边数 = **0**。所以「级联覆盖率」在 `shg.cascades`（1.000）与 `edge.cascade_id`（0.780）两个口径下是两个数字。

### C8 未匹配回退 LLM 聚类 💀 死代码

- **位置**：`builder.py::_llm_cluster_fallback` L245 ← `build` L141-143
- **机制**：`unmatched = [e for e in all_edges if not e.frame_id]` → 按 `source_domain` 分组 → 造 `F_NOVEL_{uuid4[:6]}` 框架 → 若有 LLM 后端则请它命名。
- **是否被采用**：💀 **逻辑上不可达**。前置条件要求存在 `frame_id` 为空的边，而 **extractor 产出的每条边都必然有 `frame_id`**（通道一/二走 `ont.match_by_triggers`/`get_frame` 拿到的 `FrameSpec`；通道三走 `_frame_for_candidate` 必有返回值）。运行时探针实测：**0 条**无 frame_id 的边（48 条边的生产重放 / 186 条边的 200 句重放，均为 0）。手工注入一条 `frame_id=None` 的边可以触发它（探针已验证），但生产中永不发生。
- **实测状态**：未实测（不可达）。**它承诺的「~20 次/千边」成本主张实际由 C1-C3 的查表完成，与本函数无关。**
- **依赖/被依赖**：依赖 `F_NOVEL_` id 前缀——该前缀在 `ontology.py:427` 的注释里被引用，`test_metaphor_graph.py:1988` 有类型可靠性测试，但**没有代码产生它**。

### C9 级联构造规则替换

- **位置**：`cascade_rules.py::build_cascades` L164 / `apply_rule` L213 / `group_by_target` L64 / `group_by_source` L69 / `group_by_source_type` L78 / `group_by_ground` L83 / `group_by_metanet` L115 / `cascade_stats` L231
- **输入 → 输出**：`(frames:Sequence[FrameSpec], rule:str, base_cascades)` → `Dict[str,CascadeSpec]`
- **机制**：7 种规则（`json`/`target`/`source`/`ground`/`metanet`/`source_type`/`none`）。`ground` 规则用喻底集合的 **Jaccard 连通分量**（阈值 0.34 ≈「3 个喻底里至少重叠 1 个」）；`metanet` 保留非 `C_LLM_` 前缀的级联，孤儿按 fallback 重组。`apply_rule` **必须重建 `_frame_to_cascade` 反向索引**（否则 `get_cascade()` 拿到旧归属）。
- **是否被采用**：🔧 可选（`--cascade-rule`，默认 `json` = 原样载入，与改动前逐位一致）。
- **实测状态**：**度量中性（决定性负面结果）**。全单例对照（结构上最退化的非空构造）与生产配置 MRR **逐位相同 0.5025**；只有彻底移除 L3 才降到 0.4681（−0.034）。→ **级联层的唯一因果通道是 `cascade_id` 非空这一布尔位**（被 `struct` 特征读到），与分组质量无关。
- **依赖/被依赖**：被 `evaluate_fullcorpus` L82、`ablation` L90、`evaluate_hgnn`/`evaluate_retrieval`/`evaluate_a6` 的 `set_ontology` 消费。

### C10-C13 本体自举与清洗（离线构建链）

**C10 自举回流** `llm_ontology.py::main` L372
- 流程：LLM 预取缓存 → `collect_pairs(min_conf=0.85)` L75 → `_canonicalize` L100（LLM 把杂乱域描述归并成 1–4 字规范标签，**含归并率自检**：归并后仍 ≥95% 则 `logger.error`）→ `build_specs` L159（按 (源域,目标域) 聚合；触发词剔单字与跨框架多义词；**按目标域打包级联**）→ `filter_triggers_by_lift` L241（用 **train.xml 标注**算 lift）→ `save_specs` L301。
- 实测：P0 框架 31→**2222**；P2 覆盖率 2.4%→**100%**；召回 66.3%→69.1%。**只吃 train.xml**（用测试集建属标签泄漏）。
- **负面结论**：自举触发词写回本体的路**走不通**——min_df=2 时规则侧 P1 飙到 **32.9%**；min_df=20（仅 3 词）才回到基线水平。「清空触发词」对照组与基线**完全一致** → **框架本身是中性的**，只对 L3 覆盖率有贡献。

**C11 lift 过滤** `llm_ontology.py::filter_triggers_by_lift` L241
- 判据：`df_met≥min_df=2` **且** `lift≥3.0`。不过滤 → P1 **60.5%**。
- **触发词被清空也保留框架**（框架仍承担 L3 归属职责）。

**C12 清洗沉淀** `ontology_clean.py::clean` L156
- 三步：`recompute_support` L77（从 train 缓存重放聚合，**键必须与 `_stable_id("F_LLM", s, t)` 一致**）→ `clean_frames` L105（R1 删自环 8 个 / R2 清喻底明喻标记 50 处 / R3 支持度分层 core 299 vs longtail 1878）→ `rebuild_cascades` L145（**与 `llm_ontology.build_specs` 同规则、同稳定 id**）。
- **刻意不做**：按词性删动词源域（「源域词出现在触发词/喻底」是名词隐喻的正常形态）。

**C13 三变体验证** `ontology_clean.py::verify` L267
- V0 原始 / V1 清洗全量 / V2 core-only。**refine 缓存命中率实测 100%** → 评估差异全部来自本体本身。
- 结论：V1 与 V0 **逐指标持平**（清洗是指标中性的纯质量提升）；V2 召回 −1.2pp（**longtail 层有真实价值**：单例框架是模糊匹配锚点）。

### C14 自举触发词挖掘

- **位置**：`bootstrap_triggers.py::mine_triggers` L179 / `extract_equative_pattern` L144 / `build_bootstrap_ontology` L260 / `parse_train_xml` L77
- **机制**：对 train.xml 的隐喻句与中性句分别用 `extract_equative_pattern` 抽「标记+喻体」**模式串**（如 `是舞台`/`像棉花糖`/`花般`）→ 按 `lift = (df_met/n_met)/(df_neu/n_neu)` 软过滤（`min_df=3, min_lift=3.0`）。产物灌进 `F_BOOTSTRAP_NOUN`/`F_BOOTSTRAP_VERB` 框架 + `C_BOOTSTRAP` 级联。
- **是否被采用**：🔧 `--use-bootstrap`；同时是 `ontology_clean._build_variant` L241 的**必备底座**（生产本体组装必调）。
- **实测状态**：**核心设计是「模式串而非裸名词」**——字面句「我在舞台上」不含「是舞台」，故不误触。这是把 P1 压回门槛的手段（`extract_equative_pattern` docstring）。
- **依赖/被依赖**：依赖 jieba 词性标注；被 C10/C11（lift 口径同源）与 C15 消费。

### C15 MetaNet 迁移种子

- **位置**：`metanet_migrate.py::build_metanet_ontology` L126 / `_seeds_from_list` L95 / `MetaNetImporter.from_dump` L188
- **机制**：内置经典概念隐喻清单（已人工对齐中文 source/target + 中文触发词）→ `FrameSpec` + 单成员 `CascadeSpec`；**副作用：把新增 mapping_type 写进全局 `TYPE_CONSTRAINTS`**（否则 `type_valid` 会把新框架全判非法）。
- **是否被采用**：✅ 生产（`ontology_clean._build_variant` L241 = `build_bootstrap_ontology(build_metanet_ontology())`，是**所有评测本体的底座**）。
- **实测状态**：25 个种子框架（`C_ARG_WAR` 等手工级联亦由此并入）；**唯一的跨目标域级联全部来自这里**（6 个，gen2 实测）。
- **`MetaNetImporter.from_dump`**：💀 **无调用点**（含测试）。

### C16 双语对齐

- **位置**：`ontology_bilingual.py::build_bilingual` L189 / `llm_complete` L242 / `spot_check` L348
- **机制**：三级标注——`curated`（MetaNet 内置一致）/ `auto_gloss`（词汇级转写）/ `unmapped`；`llm_complete` 用 LLM 补长尾。
- **是否被采用**：📊 离线资源（`package_release.py` L87 读它打包）。
- **实测状态**：2177 框架对齐率 **100%**（curated 2 / auto_gloss 2175 / unmapped 0）；`spot_check` 抽检 84 条。
- **依赖/被依赖**：依赖 C12 的 `ontology_default.json`；被 H3/H2 打包消费。

---

## 4. 检索通路（详细）

### D1 字面通路

- **位置**：`retrieval.py::rrf_fusion` L347（内联 `query in c`）；`evaluate_repaired.py::pathway_rankings` L291-299；`evaluate_retrieval.py::measure_h3` L124；`evaluate_llmgold.py::stage_eval` L311
- **机制**：`query in chunk_text` 子串命中，score 恒 1.0。
- **是否被采用**：✅ 生产（作为**对照臂**，不是主通路）。
- **实测状态**：**改写型查询下完全失效**（非空率 **0/777**）；重叠型 anchored Recall@10 0.8833、deanchor 0.2206。
- **依赖/被依赖**：H3 消融的对照臂。

### D2 触发词级联通路

- **位置**：`retrieval.py::cross_domain_retrieve` L138
- **输入 → 输出**：`(query:str, top_k=10, adaptive=True, semantic_fallback=False)` → `RetrieverResult{chunk_ids, scores, trace, path}`
- **机制**：查询触发词 → `match_by_triggers` → 每个候选框架取 `{target_domain, source_domain}` ∪ **沿级联展开成员框架的两个域** → 遍历 `live_edges()`，命中目标域/源域的边的 chunk 累加 `(confidence + 0.3·len(ground)) × reliability_factor`。空则返回空（或走 D3）。
- **是否被采用**：✅ 生产（全部检索评测）。
- **实测状态**：**脆弱**。改写型 Hits@10 **0.0206**、非空率 **0.192**（149/777）；重叠型 0.2000。**级联展开段实际取不到新目标域**（99.2% 级联单目标域，96.6% 的边扩展后 +0）。
- **依赖/被依赖**：依赖本体级联（C10-C12）与 C7 兜底；被 A8 消融（`adaptive`）与 D3（`semantic_fallback`）修饰。

### D3 级联语义回退（U-Retrieval 自顶向下思想的落地）

- **位置**：`retrieval.py` L177-195 + `_cascade_index` L111
- **机制**：`if not agg and semantic_fallback:` → 对**级联描述**（`f"{spec.name}：{前 8 个成员框架的 src→tgt}"`）建向量索引（懒建、缓存）→ 查询向量余弦取 top-2 级联 → 回收这些级联成员框架的超边 chunk。
- **是否被采用**：🔧 `semantic_fallback` **默认 False**；`evaluate_llmgold --cross-fallback` 可开。
- **实测状态**：**正但有限**——使级联通路 Recall 翻倍（0.020→0.042，README §7.5）。粗筛 733 个级联比逐边匹配便宜一个量级。
- **依赖/被依赖**：依赖 `embeddings.embed`；被 G3（Ω 门控等价性）作为对照判据。

### D4 语义超图通路（7 维特征排序）

- **位置**：`retrieval.py::rank_mappings` L314 → `metaphor_retriever_score` L264 → `_pair_features` L253 → `training.extract_features` L148
- **输入 → 输出**：`(query:str, mappings, adaptive=True, top_k=20)` → `(List[MetaphorHyperedge], ThresholdDecision)`
- **机制**：
  1. `_query_edges(query)`：查询触发词命中的框架下的超边（**训练期口径一致性的关键**——训练时正样本是链上超边对，推理时是「查询触发的框架下的超边 vs 候选」）。
  2. `_pair_features`：对每个查询侧超边抽 7 维，取**逐维 max 聚合**；无查询侧超边则退到 `_text_features`（D6）。
  3. `metaphor_retriever_score`：有 `scorer` → `score_features`；否则 → `hand_weighted_score`（**单一真源**，`training.HAND_WEIGHTS`）。两条路都乘 `reliability_factor`（D14）。
  4. `AdaptiveThreshold.select`（D13）筛选 → 取 top_k。
- **是否被采用**：✅ 生产（论文 §6.2 的全部数字）。
- **实测状态**：**唯一有效通路**。改写型 anchored MRR 0.1183（**随机 17.1×**）、Hits@10 0.1918；重叠型 anchored MRR 0.9200。但**能力高度依赖查询是否含触发词**（重叠型 vs 改写型差 7.8×）——改写切断了触发词 → 查询侧结构无法激活 → 7 维中 `same_frame`/`same_cascade`/`ground_jaccard` 全部失效，只剩 `sem`（AUC 0.62）在起作用。
- **依赖/被依赖**：依赖 D5/D6、G12（特征）、G15/G16（打分器）、D13（阈值）、D14（折扣）。

### D5 查询侧超边锚定 / D6 文本锚点兜底

- **位置**：`retrieval.py::_query_edges` L227（缓存 256 条）/ `_text_features` L244
- **实测状态**：**D5 在改写查询下几乎失效**——632 条改写查询里只有 **15 条**能形成查询侧边（gen3）。此时全部落到 D6（文本锚点），这就是 D4 在改写型上退化为纯语义相似度检索的机制。

### D7/D8 方案 B 元图 + U-Retrieval ⚠️ 存在但未接入

- **位置**：`metagraph.py::MetaphorURetrieval.retrieve` L112 / `_literal_retrieve` L103 / `MetaphorMetagraph.build_from_shg` L56
- **机制**：三层元图（L0 chunk 子图 / L1 文档图 / L2 主题图）；检索时「触发词 → 取 `triggers[0]` 的框架 → 级联 → 兄弟框架目标域 ∪ 喻底 → 打分（目标域词 +0.5 / 源域词与触发词 +0.3 / 向量余弦 ×0.4）」。
- **是否被采用**：⚠️ **存在但未接入**。调用点只有 `demo.py:89`（元图构建）与 `demo.py:94`（U-Retrieval）+ 单测 2 处。**任何评测脚本都不用**。
- **实测状态**：未实测（只有 demo 打印 trace）。
- **备注**：`_literal_retrieve` 在无触发词时退化为字面通路；`retrieve` 的第 5 步「自底向上精炼」在 docstring 里声明了但**代码里没有实现**（只有注释）。`baselines.py` 把 `MetaphorMG` 列为 B8 基线，但**该基线从未被真正评测**。

### D9 多线索汇聚 ⚠️ 存在但未接入

- **位置**：`retrieval.py::multi_clue_retrieval` L217
- **机制**：`candidate_scores[m.target_domain] += m.confidence`，返回 `≥ 2×threshold(0.3)` 的 `(target_domain, score)`。
- **是否被采用**：⚠️ 只被 `demo.py:110` 与 `test:187` 调用。
- **实测状态**：未实测。**注意返回的是 target_domain 字符串而非 chunk_id**——它不是检索通路，是「目标概念投票」信号，无法直接接入 chunk 召回。

### D10 RRF 融合 ⚠️ 存在但未接入

- **位置**：`retrieval.py::rrf_fusion` L346（`_rrf` L32，k=60）
- **机制**：字面通路 + `cross_domain_retrieve` 的 chunk 排名做倒数排名融合。
- **是否被采用**：⚠️ **只被单测调用**（`test_metaphor_graph.py:193`）。`demo.py` 用的是 `cross_domain_retrieve` 而非 `rrf_fusion`——尽管 demo 的 banner 写着「跨域通路 + RRF 融合」。
- **实测状态**：未实测。论文 §3.4 把 RRF 列为检索层能力之一，但**无任何数字支撑**。

### D11 HL-index ⚠️ 存在但未接入

- **位置**：`hlindex.py::HLIndex.query` L53 / `reachable_targets` L60 / `_build` L37
- **机制**：节点（含触发词）→ 超边邻接 → `_build` 用**朴素栈 BFS**（内层还遍历全部 `shg.edges` 找匹配 id，实际是 O(V·E·n)）→ 预计算 `node → 可达超边集合`；`query(trigger)` 返回 `{超边id: [目标概念]}`。
- **是否被采用**：⚠️ 只被 `demo.py:141` 与 `test:236` 调用。
- **实测状态**：未实测。`_build` 的复杂度使它在真实规模（856 边）上不实用。

### D12 上下文预算打包 50/30/20

- **位置**：`retrieval.py::pack_context` L334 → `context_budget.py::ContextBudget.pack` L157
- **机制**：按 `(0.5, 0.3, 0.2)` 分配 token 预算给（超边描述 / 实体 / 源文本块）；**某一类没用完的额度顺延给下一类**（`carry`）。成本估算 `len(text)/1.6` chars/token。
- **是否被采用**：📊 生成侧（`demo_rag` L139、`evaluate_llmasjudge` L133、`evaluate_packing_ablation` L183）。
- **实测状态**：**judge 模型敏感**。glm judge 下当前打包胜出（26.50 vs 对照 21.12，最优率 50%）；**deepseek judge 下对照 6:1 胜**。→ 生成质量主张须真人评估仲裁。
- **依赖/被依赖**：依赖 D4（`rank_mappings`）的输出。

### D13 自适应阈值

- **位置**：`context_budget.py::AdaptiveThreshold.select` L80 ← `cross_domain_retrieve` L203 / `rank_mappings` L323
- **机制**：`τ₀=0.5` 起，若选中数 < `min(min_keep=50, len(items))` 则按 `decay=0.1` 降阈值（最多 5 次）；再按图密度 Δ 分档（`≤2.35` low / `≤5.0` mid / `>5.0` high）——**低密度不设上限**（避免通路断裂），**高密度截断至 `max(min_keep×3, 1)`**（避免上下文爆炸）。
- **是否被采用**：✅ 生产（`adaptive=True` 默认）。
- **实测状态**：**无差异**。小语料 8 查询 0.500 vs 0.500；全量 1100 句 A8 亦无差异（"中性结论扩大到更大集"）。设计预期是解决稠密图爆炸/稀疏图断裂，而本基底图很稀疏、级联路径候选本就极少，阈值无发挥空间。
- **依赖/被依赖**：依赖 `shg_density`（`retrieval.py:39`，Δ = 总关联数/端点数）。

### D14 溯源可靠性折扣

- **位置**：`retrieval.py::reliability_factor` L91 / `_reliability` L82 → `provenance.reliability_factor` L88 / `edge_reliability` L73 / `frame_reliability` L51
- **机制**：`factor = floor + (1-floor) × r`，`r ∈ {1.0 本体登记, 0.5 未登记回退}`，`floor` 默认 `RELIABILITY_FLOOR = 0.5`。**乘性**（加性不改次序）、**有下界**（不丢候选）。消费点 4 处：`cross_domain_retrieve` L171/L192、`metaphor_retriever_score` L287、`evaluate_retrieval.score_conditions` L218。
- **是否被采用**：✅ **生产且默认开启**（`RetrievalEngine.__init__` 默认 `reliability_floor=provenance.RELIABILITY_FLOOR` = **0.5**）。
- **实测状态**：**负面（结构性）**。
  - P1 效应**恒为 0**（`pred = bool(edges)`，软通道够不到存在性布尔指标）；实测 7/7 条 FP 句的边**全部来自本体登记框架**，0/7 是退化边 → 句级判别 AUC **0.3913（反相关）**。
  - 排序**受损**：人工加权 MRR@10 **0.9948 → 0.8922（−0.1025）**；floor 全档位（1.0/0.9/0.75/0.5）单调劣化，无一档优于基线。
  - 唯一正面产出：暴露 P2 覆盖率注水（诚实口径 0.776）。
- **依赖/被依赖**：依赖 G11（可靠性派生）；被 D2/D4/D13 消费。
- **⚠️ 与报告不符的口径**：`experiments/REPORT_exp-degrade.md` §5.5 写「通道本身保留（代码已入库、**默认关闭**、测试齐备）……默认 `reliability_floor=1.0` 语义等价于关闭」，但**代码默认值是 0.5（开启）**，且从引入该参数的 commit（`078d099`）起就是如此。本地探针（200 句生产重放，186 条边中 36 条被折扣）：
  - `rank_mappings`（D4，**A6 臂经此**）的 top-20 集合在 **55/186** 查询上不同、次序在 **66/186** 上不同；
  - `cross_domain_retrieve`（D2）召回在 **3/186** 查询上不同；
  - `evaluate_retrieval.score_conditions`（F6，**§6.2 全部数字的真源**）的折扣臂是**显式 opt-in**（`reliability=False` 默认），因此 **§6.2 未被影响**。
  即：**受影响的是 A6 臂与 D2**，而报告把整个通道当成已关闭。这是本文发现的第 2 处「文档与代码口径不一致」（第 1 处见 C6）。

---

## 5. 校验路径（详细）

### E1 HGNN 跨层传播 ⚠️ 存在但未接入

- **位置**：`hgnn.py::MetaphorHGNN.__init__` L26 / `_build_nodes` L77 / `_build_hyperedges` L86 / `_init_features` L114 / `_conv` L123 / `forward` L170
- **输入 → 输出**：`shg:MetaphorSHG` → `H: np.ndarray (num_nodes, 512)`
- **机制**：三类超边（L1 喻底超边 / 框架↔成员实体 / 级联↔框架）→ 节点→超边均值聚合 → 超边→节点均值广播 → 残差 `0.5(X + (1-ε)newX)`；`forward` 是驱动迭代 `X ← (1-α)X0 + α·M·X`（α=1 退化为 `M^layers·X0`，与历史实现逐位一致）。
- **是否被采用**：⚠️ **存在但未接入**。代码审计（`组件处置决策.md` §1）：检索评分路径 `_pair_features → extract_features(qe, mapping, centrality)`，其中 `centrality = 0.5·len(ground) + 0.5·[cascade_id 非空]`——**完全不依赖 HGNN**。全仓 hgnn 引用只有三处：`__init__.py`（导出）、`evaluate_hgnn.py`（评测）、`evaluate_chain_quality.py`（可选 coherence 过滤，默认关闭）。
- **实测状态**：**负面（决定性）**。
  - P4-A：哈希向量下 HGNN MRR 0.896 vs 原始嵌入 **1.000**（−0.104，传播损害检索）；真实句向量下**翻案**（1.000 vs 0.938，+0.062）。
  - H4：`flat`（仅 L1 超边，关跨层）**0.910 ≈ HGNN 0.915**，全量 AUC \|Δ\|≤0.005（18 个 α/ε 配置）→ **信号来自 L1 喻底 n 元共现，跨层层级零贡献**。
  - 算子退化（500 轮后同分量余弦 1.000000）**不是**平局的原因——H4 工作在 `layers=2`，此时余弦仅 0.388。
- **依赖/被依赖**：被 E2/E3/E4 依赖；**不被任何检索通路依赖**。

### E2 `metaphor_coherence` 图结构判据

- **位置**：`hgnn.py::metaphor_coherence` L221 → `entity_vec` L201 → `encode` L183 → `edge_repr` L209
- **机制**：两实体在 H 空间的余弦；未知节点用「最近实体节点的 H」兜底（`encode` L190-199，朴素线性扫描）。
- **是否被采用**：🔧 可选——`evaluate_chain_quality.py --coherence-threshold`（默认 0 = 关闭）+ `evaluate_hgnn` 评测。
- **实测状态**：真 L1 边 0.669 vs 跨框架负样本 0.197，配对判别 **0.950**；**但 flat（无跨层）也是 0.950、GRU 甚至 1.000** → 判据有效，**但不是层级的功劳**。真实向量下判别力降到 0.850（负样本也变近）。
- **⚠️ 预期用途未落地**：`README §7.4` 建议把它作为「触发词 / LLM 之外的**第三道校验**」，但实测（`data/chain_quality_coh.log`）阈值 0.5 时保留 **52/52** 条链（中位连贯度 0.820）——**零过滤力**，不能承担校验职责。

### E3 HGNN 图感知检索

- **位置**：`hgnn.py::retrieve` L234 / `retrieve_raw` L251
- **是否被采用**：📊 只被 `evaluate_hgnn.measure_p4a` L96/L99 调用（+ 单测 1 处）。
- **实测状态**：见 E1 的 P4-A。

### E4 HGNN 谱分析接口 💀 死代码（生产）

- **位置**：`hgnn.py::propagation_matrix` L152
- **机制**：稠密算子 `M = 0.5(I + (1-ε)·Dv⁻¹HDe⁻¹Hᵀ)`，与 `_conv` 的循环实现逐元素等价。
- **是否被采用**：💀 生产零调用（只被单测 7 处调用）。`experiments/_common.py::incidence`/`S_matrix`/`M_matrix` **另写了一份等价实现**（L36-60），实验侧不用它。
- **实测状态**：单测验证 `propagation_matrix ≡ _conv`、`ρ(S)=1.0`、`ρ(M_ε) ≤ 1-ε/2`。

### E5 LLM 逐链校验

- **位置**：`llm_backend.py::verify_chains_batch` L757（提示词 `_VERIFY_SYSTEM` L743）
- **输入 → 输出**：`(backend, chains:[{key,doc_title,source,target,ground,texts}], batch_size=8, cache_path)` → `{chain_key: bool}`
- **机制**：把链上各 chunk 原文（每段截 150 字）+ 源域/目标域/喻底喂给 LLM，要求逐条输出 `{"i":k,"verdict":0/1}`。**失败纪律**：整批解析失败重试一次，仍失败则该批**不写入缓存**并在返回值中缺失——调用方必须把「缺失」当**未校验**处理。
- **是否被采用**：📊 评测侧（`evaluate_document_corpus` L182 后过滤、`evaluate_chain_quality` L182 前置过滤）；构建器侧 C6 ⚠️ 未接入。
- **实测状态**：52 条候选通过 **11 条（21.1%）**；保留集全量评审精度 **63.6%**（7/11），跨模型配对子集 **71.4%**——相对未过滤 16.7% 约 **4 倍**。「生成候选 → 语义校验过滤」双段管线成立。
- **依赖/被依赖**：依赖 LLM 后端 `_chat`（要求后端实现 `discover_batch` 才批量）。

### E6 链质量评审（跨模型 judge）

- **位置**：`evaluate_chain_quality.py::main` L93 / `_judge_cached` L69（5 次退避重试）
- **实测状态**：严格 MIPVU 口径精度 **16.7%**（文学 38% / 政报 17% / 财经 6%）；`--llm-verify` 后 71.4%（n=7，跨模型 glm-4.7）。失败主因：词化惯用语（"基础上/聚焦/扎根"）被计为隐喻提及 + 合并判据缺「跨段延续」检验。

### E7 coherence 过滤（第三道校验）🔧 可选

- **位置**：`evaluate_chain_quality.py` L144-160（`--coherence-threshold`，默认 0）
- **机制**：在 **L1-only 图**（不含扩展边，避免自证）上 `MetaphorHGNN(base, layers=2, cross_layer=False).forward()`，算每条候选链 `(源域,目标域)` 的连贯度，低于阈值剔除。
- **实测状态**：阈值 0.5 → 保留 **52/52**，零过滤力（见 E2）。

---

## 6. 评估路径（详细）

### F1 P1 抽取评测

- **位置**：`evaluate_real.py::eval_split` L81
- **输入 → 输出**：`(samples, ontology, conf, use_semfield, llm_backend, llm_conf)` → `{tp,fp,tn,fn,precision,recall,f1,literal_error_rate,fp_examples,tp_examples}`
- **机制**：逐句 `pred = bool(ex.extract(text))`；**句级二分类**。`P1 = fp/(fp+tn)`。
- **是否被采用**：📊 评测（被 `ontology_clean.verify` L307、`ablation`、`baseline_eval_real` 复用）。
- **实测状态**：P1 **0.092**（门槛 <0.15 ✅）/ 召回 0.696 / P/R/F1 0.990/0.696/0.818（n=1100）。
- **⚠️ 口径警示**：`bool(edges)` 的存在性判据使**任何软通道的效应上界恒为 0**（exp/degrade 的核心论证）。

### F2 LLM 后端构造（含回落告警）

- **位置**：`evaluate_real.py::build_llm_backend` L36
- **机制**：有 `LLM_API_KEY` → `OpenAIBackend`（glm-5 系列自动带 `reasoning_effort="low"`；`LLM_EXTRA_JSON` 可覆盖）；无 key → `LocalHeuristicBackend` + **显式告警**。
- **实测状态**：**踩坑修复**。无 key 静默回落时 `LocalHeuristicBackend` 不实现 `discover_batch`/`batch_refine` → `--llm-cache` **根本不被消费** → 产出**假性 P1 = 0.434**（真值 0.092）。
- **依赖/被依赖**：被 `evaluate_a6` L188、`evaluate_chain_quality` L116/L192、`evaluate_document_corpus` L136、`evaluate_gold_audit` L78、`ontology_bilingual` L276/L367、`translate_paper` L92 复用。

### F3 A1-A4 消融

- **位置**：`ablation.py::run_a1` L98 / `run_a2` L163 / `run_a3` L194 / `run_a4` L215（`measure` L58 / `make_ontology` L81 / `TrackedBackend` L44）
- **机制**：A1 用**实例级打补丁**（`ont.type_valid = counting` / `MetaphorExtractor._type_coherent = _coher_true`，**保存原方法并还原**——`del` 会把类上的真方法一并删掉）；A2 **不真调 LLM**，只数「需回退聚类的框架占比」；A3 用 `TrackedBackend({}, None, refine_table)` 隔离 refine；A4 对比有无自举本体。
- **实测状态**：A1 **证伪**（拦 0 + 24，P1 0.092→0.092）；A2 34.0% 框架需聚类（→187 次/千边）；A3 见 A5 条目；A4 召回 −1.8pp（价值在 P0 资源而非召回）。
- **依赖/被依赖**：依赖 `PrecomputedBackend` 与 refine 缓存；**refine 缓存缺失时 P1 会虚高**（脚本已告警）。

### F4 P3 + H3/A5/A8/A7/A9

- **位置**：`evaluate_retrieval.py::measure_p3` L68 / `measure_h3` L109 / `measure_p3_flag` L142 / `measure_a8` L164
- **机制**：P3 用 `GOLD_EXTENDED`（人工判定「应合并的 chunk 集合」）做**集合精确匹配**（`p == g`，一对一贪心）；另统计「间距≥3 却被合并」的 `spurious`。
- **实测状态**：P3 宏平均 F1 **1.000**（门槛 0.70 ✅，跨距误并 0）；H3 成立（隐喻 0.500 vs 字面 0.000）；A5 成立（1.000 → 0.000）；A8 无差异；A7/A9 不成立（小集）。
- **⚠️ 精选诊疗集**：语料即按可检测隐喻设计 → 数字应读作「机制可用」而非「泛化上界」。

### F5 全量建图 A7/A8/A9 复验

- **位置**：`evaluate_fullcorpus.py` L132-329（`build_replay_ontology` L69 / `build_replay_backend` L86 / `build_queries` L103）
- **机制**：`build_replay_ontology` 复用 `ontology_clean._build_variant`（**单一实现，避免漂移**）+ 可选 `apply_rule`；`build_replay_backend` = `PrecomputedBackend(discover 缓存, LocalHeuristicBackend, refine 缓存)`；`build_queries` 造三类 by-construction 查询（`q_ext` 扩展链 / `q_self` 基础排序 / `q_cas` 级联）。
- **实测状态**：110 伪文档 / 856 L1 边 / 密度 Δ=1.071 / 861 查询。A7 在原口径"证伪"，经 exp/source 翻转"+9.5pp 成立"，再经 gen3 归因修正为真实增量 **+0.29pp**（+9.18pp 全来自人工硬编码 0.20）。
- **依赖/被依赖**：**被 40+ 处实验脚本复用的基础设施**（`build_replay_ontology` 51 个调用点、`build_replay_backend` 35 个）。

### F6 排序臂共享打分

- **位置**：`evaluate_retrieval.py::score_conditions` L200
- **机制**：对全部 `live_edges()` **预计算一次 7 维特征**（`_pair_features`），然后四臂共享：`trained`（`scorer.score_features`）/ `trained_no_role`（`ROLE_IDX` 置零）/ `hand_weighted`（`training.hand_weighted_score` 单一真源）/ 可选 `hand_weighted_legacy`（`HAND_WEIGHTS_LEGACY`）；映射→chunk 取**最高分**。`reliability=True` 时额外返回叠加折扣的 `*_reliab` 臂。
- **是否被采用**：📊 评测（**论文 §6.2 全部数字的真源**，经 `evaluate_fullcorpus` L241 / `evaluate_llmgold` L299 / `evaluate_retrieval` L380）。
- **实测状态**：四族对比（`experiments/三通路重测_修复后基准.md` §5）：
  | 查询族/口径 | 人工(重标定) | 人工(历史) | 训练后 | 训练−重标定 |
  |---|---|---|---|---|
  | 重叠型 anchored | 0.8956 | 0.8390 | 0.9006 | +0.0050 |
  | 重叠型 deanchor | 0.2330 | 0.2307 | 0.2211 | −0.0119 |
  | 改写型 anchored | 0.1172 | 0.0775 | 0.1341 | +0.0169 |
  | 改写型 deanchor | 0.0882 | 0.0935 | 0.0809 | −0.0073 |
  → **训练增益只在 anchored 为正，去锚定后一致为负，且与查询族无关**。
- **⚠️ 回归护栏**：`legacy_arm` **必须 opt-in**——无条件加 legacy 臂会让 `evaluate_fullcorpus` 的固定键列表 KeyError 崩溃（合并期回归，已有单测）。

### F7 P4-A / P4-B / H4

- **位置**：`evaluate_hgnn.py::measure_p4a` L81 / `measure_p4b` L113 / `measure_h4` L225 / `_auc_full` L316 / `_NumpyGRU` L172 / `_l1_comembers` L205
- **机制**：
  - P4-A：HGNN `retrieve` vs `retrieve_raw` 的 chunk 排序，指标 MRR@10 / Hits@3 / Hits@10。
  - P4-B：真 L1 边 `(src,tgt)` vs **跨框架负样本** `(src, 同 doc 里另一个不同框架的实体)` 的 `metaphor_coherence` 分离度。
  - H4：同一批配对样本上比较 6 种表示（`hgnn`/`flat`/`raw`/`flat_gru`/`hgnn_driven`/`flat_driven`），主指标换成**全量负样本 ROC-AUC**（`_auc_full` 正确处理并列）。
- **实测状态**：见 E1/E2。**方法论修正**：`raw = 0.150` 是口径产物（94.6% 并列率 + 配对准确率把并列计为错误），真实 AUC = **0.550 = 无信息**；n=20 的配对准确率**功效不足**（结论字符串随 α 抖动翻转）。
- **依赖/被依赖**：`build_shg` L54 是**统一建图入口**（`set_ontology` L48 注入本体与孤儿规则，避免口径漂移）。

### F8 LLM 非构造金标三阶段

- **位置**：`evaluate_llmgold.py::stage_gen` L144 / `filter_violations` L186 / `stage_judge` L222 / `stage_eval` L274 / `build_queries_rich` L119
- **机制**：
  1. **gen**：把 `build_queries_rich` 的触发词查询改写成自然问题（提示词带 chunk 前 60 字 + 映射描述）。
  2. **红线过滤**：改写不得含原触发词/源域/目标域（`any(b and b in text for b in banned)`）→ 切断 clue 捷径。实测剔除 **26.7%**。
  3. **judge**：LLM 在每文档**全部候选映射**上做 listwise 判定（键不全过半则整问跳过）。
  4. **eval**：对 LLM 金标与构造金标**两套**金标，跑 `score_conditions` 全部臂 + 三条检索通路。
- **实测状态**：n=632 改写查询；构造金标一致性 **96.8%**；`trained_weak`/`trained_comb` 弱监督与联合训练均无定论。
- **⚠️ 基准自我审计（gen3 决定性）**：**632/632 的金标都包含产出该问题的 chunk，619/632（97.9%）只包含它** → 论文称的「非构造金标」**不成立**；LLM 只做过滤，**未解除锚定**。

### F9-F11 修复版基准（全局池 + 去锚定 + 三通路）

- **位置**：`evaluate_repaired.py::build_global_graph` L65 / `global_engine` L139 / `build_query_sets` L198 / `build_paraphrased_sets` L164 / `rank_all` L254 / `pathway_rankings` L277 / `metrics` L311 / `random_baseline` L327
- **机制**：
  - `build_global_graph`：把 110 个伪文档合并成**一张全局图**，chunk id 重映射为 `global_c<i>`（**必须与 `RetrievalEngine` 的 `f"{doc_id}_c{i}"` 命名一致**，否则候选被 `_chunk_text` 过滤干净、指标恒为 0——`global_engine` 里有 assert 守卫）。
  - `build_query_sets`：`anchored`（金标=产出 chunk）/ `deanchor`（**产出 chunk 移出池**，金标改为同框架的其它 chunk，无则退到同级联，再退则丢弃）。
  - `pathway_rankings`：三条通路在**同一全局池**上比较（literal / cascade / semantic）。
  - `random_baseline`：解析计算随机排序下各指标期望（含组合数公式）。
- **实测状态**：
  | 口径 | 池 | 查询 | 人工(重标定) | 人工(历史) | 训练后 | 随机 |
  |---|---|---|---|---|---|---|
  | anchored | 1100 | 634 | **0.8956** | 0.8390 | 0.9006 | 0.0069 |
  | deanchor | 1100 | 385 | **0.2330** | 0.2307 | 0.2211 | 0.0069 |
  → **锚定抬高 ≈ +0.66 MRR**（原基准约 74% 的数字来自「把已知答案排到前面」）；**但 deanchor MRR 0.2330 = 随机的 34 倍**，排除「架构完全无效」。
- **三通路（改写型 anchored）**：语义 0.1183 / 级联 0.0206 / 字面 0.0000（随机 0.0069）→ 语义是**唯一有效通路**（17.1× 随机），但**原文的 1.000 是池≤10 的平凡饱和**，须下修 5.2×。
- **依赖/被依赖**：`_run` L448 三臂共享同一份特征（原实现每臂各算一次 = 3 倍开销）。

### F12 真实句向量复测

- **位置**：`evaluate_repaired_real.py::main` L99 / `CachedRealEmbedder` L45 / `_run_arm` L65
- **机制**：只读 `data/embed_cache.json`（未命中返回 `None`，由调用方跳过）→ 在**查询文本已缓存的子集**上重跑三臂。
- **实测状态**：**锚定效应与向量器正交**（+0.66 哈希 vs +0.69 真实）；去锚定下均为随机 30 倍以上；查询文本缓存命中 **81.9%**（已在论文标注限制）。

### F13 连贯文档语料 L1.5 验证

- **位置**：`evaluate_document_corpus.py::chunk_text` L83 / `build_chunks` L106 / `run_pipeline` L121 / `report` L222
- **机制**：段落级分块（500 字 + 10% 重叠，超长兜底切分，每文档封顶 40 chunk）→ `batch_discover` + `_RefineCollector` + `batch_refine`（真实调用，落盘缓存）→ 逐文档建图 → 统计扩展链密度与跨度。**可选 LLM 链校验**（L167-194，脚本内后过滤）。
- **实测状态**：106 篇 / 1050 chunk（财经 40 / 政报 6 / 鲁迅 60）；含链文档占比 4.5%→**30%**；链/百 L1 0.6%→**6.3%**（财经 8.2% / 政报 4.3% / 鲁迅 5.2%）→ 连贯文档上密度是独立短句的 **10 倍**（L1.5 价值域假设定量证实）。
- **边界**：鲁迅（1920 年代白话）L1 基数低（现代触发词表覆盖不足），跨时代泛化是已知边界。

### F14 A6 常识替代消融

- **位置**：`evaluate_a6.py::build_cs_neighbors` L87 + `main` L129
- **机制**：对隐喻图 vocabulary 里每个概念域，让**同一 LLM** 列出 12 个「日常常识相关概念」（明确要求非隐喻用法）→ 常识通路 = 问题中出现的概念词 → 常识邻居 → chunk **字面匹配**；与隐喻通路（`rank_mappings`）在同一金标上对比。
- **实测状态**：**预算对等修正后** 隐喻 **1.000** vs 常识 **0.095**（**10.5×**，修正前 8.2–8.7×）。原实现隐喻臂硬编码 `top_k=5` 而常识臂**无上限** → 低估隐喻臂约 **17pp**（0.8287→1.0000）。**两臂的 1.000 都是池 ≤10 的平凡饱和**，但结论是**相对比较**，不受影响。
- **局限**：常识源为同厂商 LLM 生成（ConceptNet 公开 API 实测 502 阻塞），结论强度弱于原设计。

### F15-F17 生成侧与金标审计

- **F15 `evaluate_llmasjudge.py::main` L90**：8 查询 × 2 系统（隐喻结构上下文 vs 纯向量），A/B 顺序随机化盲评，4 维度（正确性/引用精确度/框架一致性/可读性）。实测结论对 judge 模型**高度敏感** → 不能作为最终仲裁。
- **F16 `evaluate_packing_ablation.py::main` L115**：4 种打包变体（ctrl / 当前 50-30-20 / 轻量 `(0.2,0.1,0.7)` / chunk 优先 `(0.0,0.1,0.9)`）盲评。glm judge 下当前打包胜（26.50 vs 21.12）；deepseek judge 下**对照 6:1 胜**。
- **F17 `evaluate_gold_audit.py::main` L62**：抽 50 条查询由**第二标注者**（默认跨模型 glm-4.7）独立重判全部候选，算 Cohen's κ。实测同模型换序 **κ=0.912**（n=50 / 420 对）。

### F18 比较公平性审计

- **位置**：`audit_fairness.py::scan` L70 / `TARGETS` L37
- **机制**：**剥离注释后**扫描各评测脚本的预算类参数，报告硬编码调用（应走 argparse）与可调参数。
- **实测状态**：抓出三处同类缺陷（候选池 ≤10 饱和 / 权重错配+锚定 / A6 两臂预算不对等）；已加单测护栏 `test_no_hardcoded_budget_in_comparisons`。
- **⚠️ 工具自身的坑**：首版未剥离注释，把 A6 修复注释里的「原实现用 top_k=5」误报为硬编码。

### F19-F21 论文工具链

- **F19 `make_figures.py::main` L148**：从**硬编码数值**生成 5 张 PNG（fig1 pareto / fig2 paths / fig3 a6 / fig4 ranker / fig5 chain）。重跑实验须同步更新脚本内数值。
- **F20 `package_release.py::main` L98**：产出 `release/metaphor_resources/`（本体 + 双语 + 自举触发词 + 数据卡 + 一键加载脚本）与 `release/MetaphorRAG-Bench/`（诊疗集文档 + 652 改写查询金标 + 52 条候选扩展链 + 基准说明）。全部离线。
- **F21 `translate_paper.py::main` L89**：按 `\n## ` 切章节（超长再按 4500 字符二次切分），GLM 分节翻译 + md5 缓存 + 结构保持。

---

## 7. 信号 / 测量通路（详细）

### G1 Ω 查询侧可观测性泛函

- **位置**：`observability.py::measure` L229（分量函数 `matched_triggers` L112 / `activated_structure` L122 / `normalized_entropy` L164 / `geometric_mean` L185 / `completeness` L201 / `regime_of` L218）
- **输入 → 输出**：`(query:str, ontology)` → `QueryObservability{omega, omega_geo, omega_e, omega_n, omega_f, completeness, regime, ...诊断快照}`
- **机制**：`Ω_E = min(1, |点亮的框架| / |种子触发词|)`；`Ω_N = min(1, |级联涌现目标域| / |种子触发词|)`；`Ω_F` = 激活权重分布的归一化熵（无流量 0 / 单条 0.5 / n>1 归一化熵）；`Ω = (Ω_E·Ω_N·Ω_F)^(1/3) × 完备度`，各分量带 ε=1e-3 下界；**完全无激活时 Ω 严格为 0**（特判，不走 ε）。
- **是否被采用**：📊 **纯测量，不接检索**（docstring 明确「不接入任何检索排序，不改变已上报数字」）。
- **实测状态**：**三代连续负面**。
  - 「只读查询」不变式 ✅ 成立（结构性：签名里没有候选池；632 查询 × 4 种候选池扰动 → **0/632** 变化）。
  - ρ(Ω, n_seed) = **0.9949**；「Ω>0 ⟺ n_seed≥1」逐条一致 **632/632** → **退化为 1-bit 指示器**。
  - 去掉 Ω=0 的 518 条后，预测「级联通路失败」的 AUC = **0.589**（CI 含 0.5）→ 无区分力。
  - 门控**严格更弱**：漏掉 66 条「有触发词但通路仍空」的查询。
  - 根因：Ω_N 是**死分量**（99.2% 级联单目标域 → 涌现恒空集）。
- **依赖/被依赖**：被 G4（`measure_signal` 内部调用 `measure`）与 gen2/gen3 全部实验依赖。

### G3 Ω 门控 ⚠️ 存在但未接入

- **位置**：`observability.py::ObservabilityMeter.gate` L294（`measure_many` L290 / `stats` L303）
- **机制**：`return self.measure(query).omega >= theta`。docstring 自称「参考设计只声称 Ω『能门控』，故此处只提供判据，不接检索」。
- **是否被采用**：⚠️ 只被单测 3 处调用（L1478-1480）。
- **实测状态**：**严格弱于现有判据**——θ=0 的退化用法等价于 `cross_domain_retrieve` 里的 `if not agg: semantic_fallback`，但 Ω 门控漏掉 66 条「有触发词但通路仍空」的查询，而现有判据全部拦下。

### G4-G7 gen3 查询侧结构信号

- **G4 `query_signal.py::measure_signal` L278** → `QuerySignal{n_seed, n_frames, n_cascades, n_emergent, n_new_domains, n_reachable_targets, completeness, omega*, signals{10 个标量}}`
  - 与 Ω 同一纪律：签名里没有候选池（单测 `test_measure_signal_signature_has_no_candidate_argument` 反射检查）。
  - **两种「可达目标域」口径必须区分**：`n_emergent`（gen2/Ω 口径，**仅 target_domain**）vs `n_new_domains`（检索口径，**目标域∪源域**）——后者才是通路非空与否的充分统计量。
- **G5 `compose` L140**：把 Ω 的四个设计选择（`normalize` 除 n_seed / `floor` ε 下界 / `use_completeness` 乘完备度 / `outer_zero` 外层特判）做成**正交开关**。实测 64 组合的 AUC 区间：`json` [0.5000, 0.6188] / `source` [0.5000, **0.8483**] / `metanet` [0.5000, 0.8040] / `source_type` [0.5000, **0.9290**] → 元凶在**分量定义层**而非合成层。
- **G6 `reachable_structure` L79**：直接/扩展/涌现域集合 + `n_cross_cascades`。
- **G7 `StratifiedNormalizer` L321**：按 `n_seed` 分层 z 分数（层内 sd=0 时回退为层内偏差 / 全局 sd）。
- **实测状态（三代结论）**：**不存在可用的查询侧标量**。`n_emergent` 的 0.836 是**集合大小伪影**（控制后层内 AUC **0.4625**，低于随机；且只在非默认的 `source` 规则下成立，`json` 下本来就 0.4834）。`S_query`（去掉 Ω_N 的 `min(1,·)` 截断）是全表最强非图标量，但**它预测的目标是定理**（`cascade_nonempty ⟺ reachable ∩ live ≠ ∅`，逐条一致 635/635），且**尺寸匹配随机对照同级**（0.9640 vs 0.9739）。**唯一在控制集合大小后仍保持判别力的是读图判据（条件 AUC 1.0000）**——而读图就放弃了「只读查询」不变式。

### G8 通用门控 `gate_by` 💀 死代码

- **位置**：`query_signal.py::gate_by` L381
- **机制**：`signal[name] >= theta`，未知名抛 `KeyError`。
- **是否被采用**：💀 **零调用点**（含测试与实验脚本）。已从 `__init__.py` 导出但无人使用。docstring 自称「不改变任何已上报数字」。

### G9 图健康度

- **位置**：`health.py::graph_health` L109 / `GraphHealth.report` L73 / `healthy` L70
- **输入 → 输出**：`(shg, unmatched_pool=0, dirty_summaries=0, arity_floor=2.2, orphan_ceiling=0.8, coverage_floor=0.85, ontology=None)` → `GraphHealth`
- **机制**：端点度分布（**先去重再计度**）→ 元数 → 覆盖率（`min(frame_coverage, cascade_coverage)`）→ 演化与溯源 → 6 条告警阈值。
- **是否被采用**：✅ 生产（运维信号）；被 `evaluate_real` L244、`ontology_clean` L314、`ablation` L229、gen2 全部实验调用。
- **实测状态**：本地探针（200 句生产重放）：元数 **3.583**、孤儿率 **84.8%**、密度 **1.186**、证据链覆盖 **0.0%**、软删除率 0.0%。告警命中 4 条（诚实覆盖率 81.2% / 孤儿率 / 证据链为 0 / 诚实框架覆盖率）。

### G10 诚实覆盖率（双口径）

- **位置**：`health.py` L174-194（第一段）+ L201-219（第二段，用 `provenance.frame_reliability` 重算）
- **机制**：只在**传入 `ontology`** 时计算 `registered_frame_coverage` / `registered_cascade_coverage` / `registered_hierarchy_coverage` / `n_fallback_edges` / `adhoc_cascades`；**不传时全部为 `None`、报告文本不含该行**（历史口径逐位不变）。
- **实测状态**：报出 **1.000** vs 诚实 **0.776**（1100 句评测集：883 边，本体登记 685）；`C_ADHOC_` 占 45.1%（408 个级联里 184 个事后补）。**低于 P2 的 85% 门槛** → 论文附录 B 从 ✅ 改为**条件性达标**。
- **⚠️ 判据陷阱**：必须是「本体有无条目」而**不是** `F_LLM_` 前缀——生产本体 **98.6%** 的框架以 `F_LLM_` 开头（自举沉淀的正式框架），按前缀判定会把整个本体误判为退化。有回归护栏 `test_judgement_is_registration_not_prefix`。

### G11 溯源可靠性派生

- **位置**：`provenance.py::frame_reliability` L51 / `frame_provenance` L66 / `edge_reliability` L73 / `reliability_factor` L88；常量 L39-48
- **机制**：`frame_reliability` = 本体登记 ? 1.0 : 0.5（`RELIABILITY_FALLBACK_CAP`），无 ontology 时返回 1.0（信息不足不降级）。`edge_reliability` 取**存储值与派生值的较小者**（`min(stored, derived)`，防伪升级、允许显式降级）。`reliability_factor(r, floor) = floor + (1-floor)·r`。
- **是否被采用**：✅ 生产（`extractor.emit` L228 写入边；`health` L206-219 用于诚实覆盖率；`retrieval` D14 用于折扣）。
- **实测状态**：见 D14（负面）。**唯一可上报的正面产出是它暴露了 P2 覆盖率注水。**
- **`frame_provenance` L66**：⚠️ 生产零调用（只被 `__init__.py` 导出 + 单测 1 处）。

### G12 7 维特征抽取（两条路径）

- **位置**：`training.py::extract_features` L148（查询**超边** vs 候选）/ `extract_text_features` L106（查询**文本** vs 候选）；`FEATURE_NAMES` L41
- **输入 → 输出**：`(query_edge|query_text, cand, centrality, ontology)` → `List[float]`（7 维：sem/struct/clue/type/same_frame/same_cascade/ground_jaccard）
- **机制**：
  - `sem`：`max(0, cosine(embed(query.describe()), embed(cand.describe())))`——**超边必须渲染成自然语言再嵌入**（`models.describe` L108，HyperGraphRAG 做法）。
  - `struct`：`min(1, centrality[cand.id])`，其中 `centrality = 0.5·len(ground) + 0.5·[cascade_id 非空]`——**这是 L3 层唯一的因果通道**。
  - `clue`：`min(1, 0.5·|triggers ∩ query|)`。
  - `type`：`ont.type_reliability_of(frame_id, source_type)` → 1.0 注册 / **0.5 未注册回退** / 0.0 无归属或非法。
  - `same_frame` / `same_cascade` / `ground_jaccard`：角色感知结构信号（角色保留的结构邻近度，替代 HyperRAG 的同质 DDE 假设）。
- **是否被采用**：✅ 生产。
- **实测状态**：单特征配对 AUC（gen3 全量审计）——`sem` **0.6277**（唯一有真实判别力）/ `ground_jaccard` 0.5300 / `type` 0.5249 / `struct` 0.5197 / `clue` 0.5087 / `same_cascade` 0.5070 / `same_frame` 0.5053。**无任何维度达到 `dead` 或 `harmful` 判定**；全部处置（删除/替换 6 个替代信号）ΔMRR **CI 全部覆盖 0**。
- **⚠️ 历史 bug（已修）**：`type` 曾有两条不一致表达式（`1.0 if cand.frame_id else 0.0` vs 查本体后 `type_valid`），对未注册 `F_LLM_*` 给出 1.0 vs 0.0，**22.0% 的候选对分歧**。已统一到 `ontology.type_reliability_of`（单一真源）。
- **⚠️ `ground_jaccard` 口径分歧（未修）**：两处定义不同（包含比 vs 真 Jaccard），**4.76%** 的候选对不同（`experiments/实验结论汇总.md`）。

### G13 自监督训练集构造

- **位置**：`training.py::build_training_set` L342 / `_build_from_chunks` L244（chunk 模式）/ `_chain_pairs` L315（chain 模式）
- **机制**：四种 `positive_mode`：
  - **`chunk`（默认，唯一不泄漏）**：查询 = chunk 原文，正样本 = 该 chunk **实际抽出**的超边，负样本优先**困难负样本**（同框架或同源域但不在本 chunk）。标签不直接编码在任何特征里。
  - `chain`：正样本 = 同一条扩展隐喻链上的超边对（复现 `link_extended_metaphors` 的合并判据）→ **目标泄漏**（`same_frame`/`ground_jaccard` 单特征即可完美分类）。
  - `cascade`：正样本 = 同级联超边对 → **同样泄漏**（`same_cascade` 即标签本身）。
  - `both`：chain ∪ cascade（继承同样泄漏）。
- **是否被采用**：✅ 生产（`train_from_shg` L677 默认 `"chunk" if chunks else "cascade"`）。
- **实测状态**：**已知天花板**——本体召回率 ~7% 量级下候选池只有几十条，`clue` 单特征 AUC ≈ **1.0**（抽取器本来就靠触发词命中产边）→ **自监督只能教会模型模仿抽取器的判定规则，不是学会检索**。这就是 `evaluate_fullcorpus` 里 `leakage_report` 每文档计数的原因。
- **依赖/被依赖**：依赖 `extract_text_features`（G12）；产出喂给 G15（训练）。

### G14 LLM 弱监督训练集

- **位置**：`training.py::build_weak_refine_set` L570
- **机制**：**从 refine 缓存里回收真金白银买来的标签**——`is_metaphor=False` / `None` 的候选是「同 chunk、同触发词、但被模型否决」的**天然困难负样本**。伪超边 id = `"REF_" + md5(cid|src|tgt)[:8]`；绑得上本体框架就复用其 ground/triggers，绑不上用 `[源域]` 兜底。
- **是否被采用**：🔧 `evaluate_fullcorpus --weak-refine` / `evaluate_llmgold`（`trained_weak` / `trained_comb` 臂）。
- **实测状态**：**机制成立，收益未证明**。打破了 clue-AUC≈1.0 天花板（弱监督集 clue AUC 下降），但排序 MRR −0.013 / Hits@3 +0.005（无定论）。

### G15 排序器训练

- **位置**：`training.py::MetaphorScorer.fit` L485 / `predict_proba` L538 / `score_features` L542 / `weights` L545 / `save` L548 / `load` L558
- **机制**：纯 numpy logistic 回归；BCE + 小批量梯度下降 + **早停**（patience=10）；类别不平衡按 `w_pos=(n_pos+n_neg)/(2·n_pos)` 加权；**标准化**（`_fit_scaler`/`_scale`，因 `sem∈[0,1]` vs `struct∈[0,3]` 量纲差异大）；L2 正则 1e-4。
- **是否被采用**：✅ 生产（`RetrievalEngine.scorer` 参数）。
- **实测状态**：见 F6 四族表。学到的权重（110 个伪文档均值）：`clue` 1.2543 / `sem` 0.6911 / `ground_jaccard` 0.4965 / `same_cascade` 0.1958 / `same_frame` 0.1953 / `type` 0.0487 / `struct` **0.0195**。

### G16 人工加权打分

- **位置**：`training.py::hand_weighted_score` L79 / `HAND_WEIGHTS` L76 / `_LEARNED_SHARE` L65 / `HAND_WEIGHTS_LEGACY` L62
- **机制**：**单一真源**——`retrieval.metaphor_retriever_score` L305 与 `evaluate_retrieval.score_conditions` L229 都调它。`struct`/`clue` 按历史口径**截断到 1**。
- **是否被采用**：✅ 生产。
- **实测状态**：**权重错配是本项目最重要的口径缺陷之一**。原 `0.35/0.25/0.20/0.20` vs 学到权重 → `struct` **过权 37–49 倍**、`type` **12–19 倍**。仅把人工权重按学到比例重标定（**不训练任何模型**），anchored MRR 从 0.8390 → 0.8956（+0.0565）→ **「训练增益」主要是配错权重的产物**。保留 `HAND_WEIGHTS_LEGACY` 使历史数字可重放。

### G17 泄漏自检门

- **位置**：`training.py::feature_auc` L194 / `leakage_report` L216 / `trivial_separators` L225
- **机制**：`feature_auc` 算每维单特征配对 AUC（含并列 0.5 权重）；`leakage_report` 返回 AUC ≥ 0.98 的特征名；`trivial_separators` 抓**完美**可分（`pos_min > neg_max + 1e-9`）。
- **是否被采用**：✅ 生产门（`evaluate_fullcorpus` L218/L233 每文档调用并计数，L309 打印）。
- **实测状态**：chunk 模式返回空 ✅；chain/cascade 模式会标出 `same_cascade`（符合设计预期）。**这是唯一阻止「上报自我实现指标」的机制**。
- **⚠️ 覆盖不足**：`trivial_separators` 只抓完美可分（AUC=1.0），抓不住 AUC=0.99 这种实质已被单特征决定的样本集——`feature_auc` 是补充。

---

## 8. 存储 / 导出 / 演化（详细）

| # | 通路 | 位置 | 状态 | 说明 |
|---|---|---|---|---|
| H1 | Cypher 导出 | `storage.py::shg_to_cypher` L65（`constraints_cypher` L39 / `_ensure_domain` L59） | 🔧 可选 | 超边实体化建模（`HAS_SOURCE`/`HAS_TARGET`/`HAS_GROUND`/`IN_FRAME`/`IN_CASCADE`）；**确定性**（有单测对比两次调用一致）；调用点只有 `demo.py:146` |
| H2 | JSON 导出 | `storage.py::shg_to_json` L161 | 🔧 可选 | `demo.py:151` 会**重写仓库内 `export_shg.json`** |
| H3 | Neo4j 写入 | `storage.py::Neo4jStore` L182 / `execute` L218 / `load_shg` L258 / `run` L253 / `counts` L286 / `clear` L283 | ⚠️ **未接入** | stdlib HTTP 事务端点（`POST /db/{db}/tx/commit`），零额外依赖；401/403 → `Neo4jFatalError`（不重试不降级）；有 mock 单测（`test_metaphor_graph.py:1190`）；**真库连通验证待本机 Neo4j 实例**（README §8.1） |
| H4 | 证据链合并 | `models.py::merge_evidence` L212 | ⚠️ **存在但未接入** | 只被单测调用。`Evidence` 数据类（L21）带 `authority`/`timestamp`/`extractor_version`/`snippet` |
| H5 | 冲突消解 | `models.py::resolve_conflict` L227 | ⚠️ **存在但未接入** | 只被单测 4 处调用。四策略（`authority`/`recent`/`vote`/`hybrid`）；**刻意不用 `confidence` 决胜**（跨 `extractor_version` 不可比） |
| H6 | 超边自然语言渲染 | `models.py::describe` L108 | ✅ 生产 | `f"{src}→{tgt}：把{tgt}比作{src}，强调{grounds}。触发词：{trig}。"`；被 `embeddings`（sem 特征）、`pack_context`、`hgcn.retrieve_raw` 消费 |

---

## 9. 「存在但未接入」的通路（汇总）

> 判定标准：代码存在 + 有非测试定义，但**生产路径（抽取→构建→检索→评测）从不调用**；或逻辑上不可达。每条的验证命令见 §12。

| # | 通路 | 位置 | 未接入的证据 | 影响 |
|---|---|---|---|---|
| 1 | **HGNN 跨层传播** | `hgnn.py::forward` L170 / `_conv` L123 | 全仓 hgnn 引用仅 `__init__.py`（导出）/ `evaluate_hgnn.py`（评测）/ `evaluate_chain_quality.py`（可选过滤，默认关） | **决定性**：这解释了 flat ≡ HGNN；论文 §6.3 已加附加条件，`组件处置决策.md` 已把该层「从检索路径移除」（文档层面） |
| 2 | **L1.5b 构建器内 LLM 链校验** | `builder.py::build` L74-101 | `llm_verify_extended` 全仓只出现在 `builder.py` 自身（L31/L35/L74），**无任何调用点传参** | 双段管线在构建期**未生效**；只有评测脚本的后过滤版；`后续待办.md` B1 列为待接入 |
| 3 | **`_llm_cluster_fallback`** | `builder.py` L245 | 前置条件 `not e.frame_id` 在生产产出中**恒为假**（运行时探针：0 条无 frame_id 的边） | **死代码**；「~20 次/千边」的成本主张实际由 C1-C3 查表完成 |
| 4 | **U-Retrieval + 元图** | `metagraph.py::retrieve` L112 / `build_from_shg` L56 | 只被 `demo.py:89/94` 与单测调用 | `baselines.py` 把 MetaphorMG 列为 B8 基线，但**该基线从未被评测** |
| 5 | **多线索汇聚** | `retrieval.py::multi_clue_retrieval` L217 | 只被 `demo.py:110` 与单测调用 | 返回 target_domain 而非 chunk_id，**结构上无法接入 chunk 召回** |
| 6 | **RRF 融合** | `retrieval.py::rrf_fusion` L346 | **只被单测调用**（`test:193`） | demo 的 banner 写着「+ RRF 融合」但实际未用；论文 §3.4 列了该能力，**无数字支撑** |
| 7 | **HL-index** | `hlindex.py::query` L53 | 只被 `demo.py:141` 与单测调用 | `_build` 是 O(V·E·n) 朴素实现，真实规模不实用 |
| 8 | **Ω 门控** | `observability.py::gate` L294 | 只被单测 3 处调用 | 实测**严格弱于**现有判据（漏 66 条） |
| 9 | **`gate_by`** | `query_signal.py` L381 | **零调用点**（含测试） | 死代码 |
| 10 | **`propagation_matrix`** | `hgnn.py` L152 | 只被单测 7 处调用；实验侧另写一份（`experiments/_common.py` L36-60） | 生产死代码 |
| 11 | **`frame_provenance`** | `provenance.py` L66 | 只被 `__init__.py` 导出 + 单测 1 处 | 分级标签无人消费 |
| 12 | **`MetaNetImporter.from_dump`** | `metanet_migrate.py` L188 | 零调用点（含测试） | 外部 MetaNet 数据接入通道**从未启用** |
| 13 | **`Neo4jStore`** | `storage.py` L182 | 有 mock 单测，无生产调用 | 真库连通待外部条件 |
| 14 | **`merge_evidence` / `resolve_conflict`** | `models.py` L212 / L227 | 只被单测调用 | 知识演化/冲突消解**只有数据模型，没有通路** |
| 15 | **`MetaphorSHG.incidence` 属性** | `models.py` L175 | **零调用点**（含测试） | 关联矩阵在模型层是死代码；实验侧用 `_common.incidence(g)` |
| 16 | **`semfield.EMBEDDER` 精化** | `semfield.py` L68/L71/L110 | `set_embedder` 被 `embeddings.set_embedder(propagate=True)` 调用，但 **`incongruity_score` 只读 `tag_token`/`discourse_field`，从不读 `EMBEDDER`** | **docstring 承诺的「用语义相似度精化失谐强度」从未实现**（运行时探针：设了 embedder 后返回值不变） |
| 17 | **`get_embedder()`** | `embeddings.py` L77 | 零调用点 | 死代码 |
| 18 | **`evaluate_repaired.rank_all` 的 `weights` 参数** | `evaluate_repaired.py` L254 | 只在 `pathway_rankings` L307 以 `scorer=None` 调用（用默认 `HAND_WEIGHTS`） | `HAND_WEIGHTS_LEGACY` 臂在 `_run` L486 另起实现 |

### 文档与代码口径不一致（2 处，本次新发现）

| # | 文档声称 | 代码实际 | 验证 |
|---|---|---|---|
| 1 | `experiments/REPORT_exp-degrade.md` §5.5：「通道本身保留（代码已入库、**默认关闭**、测试齐备）……默认 `reliability_floor=1.0` 语义等价于关闭」 | `RetrievalEngine.__init__`（`retrieval.py` L55）默认 **`provenance.RELIABILITY_FLOOR` = 0.5** → 通道**默认开启**。`RELIABILITY_FLOOR_OFF = 1.0` 是「关闭开关」，但没有被用作默认值 | 探针（200 句生产重放，186 条边中 **36 条被折扣**）：<br>· `rank_mappings`（D4，**A6 臂**经此）top-20 集合在 **55/186** 查询上不同、次序在 **66/186** 上不同<br>· `cross_domain_retrieve`（D2）召回在 **3/186** 查询上不同<br>· 该 commit（`078d099`）起就是这样，非后续引入 |
| 2 | `builder.py` C6 的 `llm_verify_extended` 参数在 `后续待办.md` B1 被描述为「当前只在评测脚本后过滤」 | 更准确：**构建器内通路从未被调用过**（不只是「未默认开启」） | grep 全仓 `llm_verify_extended` → 3 处全在 `builder.py` 自身 |

> 第 1 条有实际影响：**A6 臂**（经 `rank_mappings`）与 **D2 级联通路**都在默认 floor=0.5 下运行。
> `evaluate_retrieval.score_conditions`（F6，§6.2 的真源）的折扣臂是显式 opt-in，**未被影响**。
> 这与 exp/degrade「人工加权 MRR −0.1025」的结论一致（人工加权路径会被咬到头部），
> 但**报告把整个通道当成了已关闭状态**，故该影响范围此前未被记录。

---

## 10. 未被骨架覆盖的通路（按漏因归类）

`PATHWAY_PAT` 正则漏掉的通路，按漏因分类：

| 漏因 | 通路 | 位置 |
|---|---|---|
| **下划线开头** | `_ensure_cascades` | `builder.py` L150 |
| | `_llm_cluster_fallback` | `builder.py` L245 |
| | `_refine` | `extractor.py` L66 |
| | `_frame_for_candidate` | `extractor.py` L81 |
| | `_type_coherent` | `extractor.py` L126 |
| | `_fuzzy_match_frame` | `extractor.py` L140 |
| | `_pair_features` / `_text_features` / `_query_edges` / `_cascade_index` / `_reliability` / `_compute_centrality` / `live_edges` | `retrieval.py` L253/L244/L227/L111/L82/L74/L106 |
| | `_build_from_chunks` / `_chain_pairs` / `_s_log` / `_s_struct` / `_s_query` / `_auc_full` / `_mrr_hits` / `_rrf` | `training.py` L244/L315；`query_signal.py` L218/L230/L249；`evaluate_hgnn.py` L316；`evaluate_retrieval.py` L257；`retrieval.py` L32 |
| | `_conv` / `_build_nodes` / `_build_hyperedges` / `_init_features` / `_build`（HLIndex） | `hgnn.py` L123/L77/L86/L114；`hlindex.py` L37 |
| | `_canonicalize` / `_filter_triggers` / `_stable_id` / `_build_variant` / `_quick_hit` / `_load_refine_table` | `llm_ontology.py` L100/L137/L66；`ontology_clean.py` L235/L343/L228 |
| | `_seeds_from_list` / `_dump_seeds` / `_vehicle_after` / `_vehicle_before` / `_verb_candidates` | `metanet_migrate.py` L95/L156；`bootstrap_triggers.py` L111/L130/L170 |
| | `_equative_vehicles` / `_bind` / `_within_domain_literal` / `_batch_discover_uncached` / `_RefineCollector` / `_judge_cached` / `_cached` / `_raw_chat` | `llm_backend.py` L492/L467/L535/L855/L629；`evaluate_chain_quality.py` L69；`evaluate_llmasjudge.py` L77 |
| **名词性/不含动词前缀** | `main`（14 个模块的 CLI 入口） | 各模块 |
| | `stage_gen` / `stage_judge` / `stage_eval` | `evaluate_llmgold.py` L144/L222/L274 |
| | `precompute_all` | `llm_backend.py` L695 |
| | `batch_discover` / `batch_refine` | `llm_backend.py` L820/L647 |
| | `forward` | `hgnn.py` L170 |
| | `pack`（ContextBudget） | `context_budget.py` L157 |
| | `fit` / `predict_proba` / `weights`（MetaphorScorer） | `training.py` L485/L538/L545 |
| | `query` / `reachable_targets`（HLIndex） | `hlindex.py` L53/L60 |
| | `report`（文档语料） | `evaluate_document_corpus.py` L222 |
| | `load_ccl2018` / `load_vua_csv` | `data_loader.py` L37/L68 |
| | `parse_train_xml` | `bootstrap_triggers.py` L77 |
| **类方法被 `ast.walk` 收但正则不匹配** | `discover` / `refine` / `cluster`（`OpenAIBackend` L311/L404/L418；`LocalHeuristicBackend` L545/L572/L579） | 骨架已收但**丢了类归属**（6 条同名 `discover`/`refine` 被当成 6 个独立通路） |
| **骨架收了但属工具函数**（应合并/排除） | `ablation.measure`（= `evaluate_real.eval_split` 的简化副本） | `ablation.py` L58 |
| | `ablation.refine`（类方法，`TrackedBackend.refine`） | `ablation.py` L51 |
| | `observability.measure` / `ObservabilityMeter.measure`（同一实现的包装） | `observability.py` L229/L282 |
| | `llm_backend.py` 的 6 组同名 `discover`/`refine`/`cluster`（应合并为 3 条） | L74-78 / L311-418 / L545-579 / L605-621 / L636-643 / L905-913 |

**合并说明**（骨架 77 条候选 → 去重后 **66** 个 `(module, func)` 对，去重 11 条）：
- `llm_backend` 的 15 条里，**9 条是 3 个方法的 Protocol 声明 + 5 个实现的重复** → 归并为「discover 通道（3 实现）」「refine 通道（4 实现）」2 条通路 + 1 条 Protocol。
- `observability.measure` / `ObservabilityMeter.measure` / `measure_many` → 1 条（G1）+ 1 条缓存包装。
- `evaluate_hgnn` 的 `measure_p4a`/`measure_p4b`/`measure_h4` → 1 条评测通路（F7）的 3 个子测量。
- `ontology_clean` 的 `clean_ground`/`clean_frames`/`rebuild_cascades`/`recompute_support` → C12 的内部步骤。
- `llm_ontology` 的 `build_specs`/`filter_triggers_by_lift`/`build_llm_ontology` → C10/C11。

**新增通路（骨架正则完全未收录）—— 下表列出代表性条目**：

> 口径说明：§1 汇总表里**无法追溯到任何骨架条目**的行共 **55** 条（脚本逐行统计，见 §12）；
> 下表 31 条是其中**属于「通路」而非「骨架条目的再分组」**的那一批。
> 差额来自两类：① 骨架条目被拆分到多行（如 `llm_backend.refine` 的骨架条目 → A5 + B4 两行）；
> ② 同一骨架条目在不同族的重新表述（如 `retrieval.rank_mappings` → D4 一行，其内部步骤另立 D5/D6）。
> 完整的双向映射见 **§14 附录**（66 条骨架条目逐条归属，无遗漏）。

| # | 通路 | 位置 |
|---|---|---|
| 1 | `_ensure_cascades` 孤儿兜底 | `builder.py` L150 |
| 2 | `_llm_cluster_fallback` | `builder.py` L245 |
| 3 | `_refine` 校验 | `extractor.py` L66 |
| 4 | `_frame_for_candidate` 绑定 | `extractor.py` L81 |
| 5 | `_type_coherent` 连贯性检查 | `extractor.py` L126 |
| 6 | `_fuzzy_match_frame` 模糊匹配 | `extractor.py` L140 |
| 7 | `_pair_features` | `retrieval.py` L253 |
| 8 | `_query_edges` | `retrieval.py` L227 |
| 9 | `_text_features` | `retrieval.py` L244 |
| 10 | `_cascade_index` 语义索引 | `retrieval.py` L111 |
| 11 | `_reliability` 缓存 | `retrieval.py` L82 |
| 12 | `live_edges` | `retrieval.py` L106 |
| 13 | `forward` HGNN 传播 | `hgnn.py` L170 |
| 14 | `_build_from_chunks` chunk 模式训练集 | `training.py` L244 |
| 15 | `_chain_pairs` 链正样本对 | `training.py` L315 |
| 16 | `MetaphorScorer.fit` 训练循环 | `training.py` L485 |
| 17 | `precompute_all` 两趟预取 | `llm_backend.py` L695 |
| 18 | `batch_discover` | `llm_backend.py` L820 |
| 19 | `batch_refine` | `llm_backend.py` L647 |
| 20 | `stage_gen` / `stage_judge` / `stage_eval` | `evaluate_llmgold.py` L144/L222/L274 |
| 21 | `filter_violations` 红线过滤 | `evaluate_llmgold.py` L186 |
| 22 | `build_global_graph` 全局池 | `evaluate_repaired.py` L65 |
| 23 | `build_query_sets` / `build_paraphrased_sets` | `evaluate_repaired.py` L198/L164 |
| 24 | `pathway_rankings` 三通路 | `evaluate_repaired.py` L277 |
| 25 | `rank_all` | `evaluate_repaired.py` L254 |
| 26 | `random_baseline` 随机基线 | `evaluate_repaired.py` L327 |
| 27 | `run_pipeline` 连贯文档 | `evaluate_document_corpus.py` L121 |
| 28 | `build_cs_neighbors` 常识邻居 | `evaluate_a6.py` L87 |
| 29 | `scan` 公平性审计 | `audit_fairness.py` L70 |
| 30 | `_build_variant` 本体变体组装 | `ontology_clean.py` L235 |
| 31 | `_canonicalize` 域归并 | `llm_ontology.py` L100 |

---

## 11. 排除清单（不是通路）

| 被排除项 | 位置 | 为什么不是通路 |
|---|---|---|
| `training._jaccard` | `training.py` L99 | 纯工具（集合相似度），无数据流方向 |
| `retrieval._rrf` | `retrieval.py` L32 | 纯工具（倒数排名求和）；`rrf_fusion` 才是通路 |
| `extractor._locate_triggers` / `_dedup` / `_heuristic_sentiment` | `extractor.py` L58/L280/L297 | 工具/后处理，不独立构成数据流 |
| `extended._min_span_gap` | `extended.py` L22 | 工具（被 `link_extended_metaphors` 与 `training._chain_pairs` 共用） |
| `mipvu._segment_with_pos` / `_marker_near_token` | `mipvu.py` L41/L55 | 工具 |
| `semfield.tag_token` / `segment` / `discourse_field` / `incongruity_score` | `semfield.py` L77-L118 | **信号函数**，被 A2 消费；自身不移动数据到决策 |
| `embeddings.embed` / `cosine` / `_char_ngrams` / `_hash_bucket` | `embeddings.py` L105/L126/L92/L101 | 工具 |
| `ontology.match_by_triggers` / `match_frame` / `get_frame` / `get_cascade` / `type_valid` / `type_reliability_of` / `infer_source_type` | `ontology.py` L377-L462 | **查表层**，是 A1/A6/A7/A8 的组件 |
| `cascade_rules._group_by` / `_sid` | `cascade_rules.py` L56/L47 | 工具 |
| `health.GraphHealth.report` / `healthy` | `health.py` L73/L70 | 输出格式化，非独立数据流 |
| `context_budget.graph_density` / `AdaptiveThreshold.regime` | `context_budget.py` L32/L73 | 工具 |
| `observability.normalized_entropy` / `geometric_mean` / `completeness` / `regime_of` / `matched_triggers` | `observability.py` L164-L223 | Ω 的分量函数 |
| `query_signal._domains_of` | `query_signal.py` L65 | 工具 |
| `llm_backend._parse_json_blob` / `_refine_key` | `llm_backend.py` L101/L625 | 工具 |
| `evaluate_*._mrr_hits` / `metrics` / `_chunk_of` / `_norm_keys` / `_load_json` / `_save_json` | 各评测脚本 | 指标计算工具（被评测通路消费） |
| `models.member_entities` / `authority` / `support` | `models.py` L104/L121/L127 | 属性/工具 |
| `storage._esc` / `_jlist` | `storage.py` L28/L34 | 转义工具 |
| `bootstrap_triggers._self_check` | `bootstrap_triggers.py` L312 | `__main__` 自检打印 |
| `audit_fairness._strip_comments` | `audit_fairness.py` L55 | 工具 |
| `baselines.render_plan` / `BASELINES` / `ABLATIONS` / `EVAL_SUITES` | `baselines.py` L156/L38/L115/L134 | **声明式数据**，不是可执行数据流 |
| `eval_corpus.DOCS` / `GOLD_EXTENDED` / `GOLD_RETRIEVAL` / `THRESHOLD_P3_ACC` | `eval_corpus.py` | **金标数据**，被 F4/F6/F7/F15/F16 消费 |
| `data_loader.MetaphorSample` | `data_loader.py` L21 | 数据类 |
| `inventory.py` 自身（`pathways`/`criteria`/`refactors`/`concepts`） | `inventory.py` | **清单提取工具**（SKIP 列表已排除） |
| `test_metaphor_graph.py` 全部 | — | 测试（SKIP 列表已排除） |
| `audit_fairness.py`（骨架已 SKIP） | — | 审计工具；本次作为 F18 收录（它有明确的数据流：源码 → 预算报告） |
| `metaphor_graph/rmtop.rs`（99,681 字节） | `metaphor_graph/rmtop.rs` | **外部项目（RiverMemo topology v3）的 Rust 源码，零引用**（全仓 grep `rmtop` 无命中）；不属本项目的 Python 通路 |

---

## 12. 复现命令（验证调用点用的确切命令）

```bash
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"
cd "E:/02_AI项目/元图隐喻分析"

# 1) 骨架总览
$PY -m metaphor_graph.inventory
$PY -c "import json;d=json.load(open('docs/inventory/_extracted.json',encoding='utf-8'));print({k:len(v) for k,v in d.items()})"
# → {'pathway': 77, 'criterion': 17, 'refactor': 19, 'concept': 56}

# 2) AST 调用点扫描（本文档使用的脚本，见下）
$PY /tmp/callscan.py <name1> <name2> ...     # 见下方脚本正文
$PY /tmp/kwscan.py <kwarg1> <kwarg2> ...     # 关键字参数调用点

# 3) 关键「未接入」判定（每条都是全仓 grep，含 experiments/ 与 release/，排除 .wt/）
grep -rn "llm_verify_extended\|verify_cache_path" --include=*.py . | grep -v "\.wt/"
# → 3 处，全在 metaphor_graph/builder.py（L31/L35/L74）→ C6 未接入
grep -rn "rrf_fusion" --include=*.py . | grep -v "\.wt/"
# → 定义 1 + 单测 1 → D10 未接入
grep -rn "multi_clue_retrieval" --include=*.py . | grep -v "\.wt/"
# → 定义 1 + demo 1 + 单测 1 → D9 未接入
grep -rn "MetaphorURetrieval\|MetaphorMetagraph" --include=*.py . | grep -v "\.wt/"
# → 定义 2 + demo 2 + 单测 2 + __init__ 2 → D7/D8 未接入
grep -rn "gate_by" --include=*.py . | grep -v "\.wt/"
# → 定义 1 + __init__ 导出 1 → G8 死代码
grep -rn "propagation_matrix" --include=*.py . | grep -v "\.wt/"
# → 定义 1 + 单测 7 → E4 生产死代码
grep -rn "frame_provenance" --include=*.py . | grep -v "\.wt/"
# → 定义 1 + __init__ 2 + 单测 1 → 生产死代码
grep -rn "merge_evidence\|resolve_conflict" --include=*.py . | grep -v "\.wt/"
# → 定义 2 + 单测 5 + __init__ 4 → H4/H5 未接入
grep -rn "F_NOVEL_" --include=*.py . | grep -v "\.wt/"
# → builder 注释 1 + builder L253 生成 1 + 单测 1 + ontology 注释 1 → C8 不可达
grep -rn "get_embedder()" --include=*.py . | grep -v "\.wt/"     # → 定义 1，零调用
grep -rn "MetaNetImporter" --include=*.py . | grep -v "\.wt/"    # → 定义 1，零调用
grep -rn "rmtop" . 2>/dev/null | grep -v "\.wt/"                 # → 零命中（外部文件）
grep -rn "\.incidence" --include=*.py . | grep -v "\.wt/"        # → 零命中（models L175 死代码）

# 4) 运行时探针（判定 C8 不可达 + D14 默认开启）
$PY /tmp/probe7.py    # C8：手工注入 frame_id=None 的边可触发；正常 build 产出 0 条无 frame_id 边
$PY /tmp/probe8.py    # D14：200 句图上 36/186 边被折扣；rank_mappings top-20 集合 55/186 不同
$PY /tmp/probe5.py    # D14：eval_corpus 上 reliability_factor 全为 1.0（该语料无退化边）

# 5) 交叉核对实验报告
grep -n "reliability_floor" experiments/REPORT_exp-degrade.md   # §5.5 声称默认 1.0
sed -n '50,56p' metaphor_graph/retrieval.py                      # 实际默认 RELIABILITY_FLOOR=0.5
```

### `/tmp/callscan.py` 正文（AST 调用点扫描器）

```python
import ast, os, sys, json
ROOT = os.path.abspath(".")
SKIP_DIRS = {".git", "__pycache__", ".wt", "release", "node_modules",
             "output", "figures"}
def iter_py():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)
def rel(p): return os.path.relpath(p, ROOT).replace("\\", "/")
defs, calls = {}, {}
for p in iter_py():
    try:
        src = open(p, encoding="utf-8").read(); tree = ast.parse(src)
    except Exception:
        continue
    lines = src.split("\n")
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(n.name, []).append((rel(p), n.lineno))
        if isinstance(n, ast.Call):
            fn = n.func
            nm = fn.id if isinstance(fn, ast.Name) else (
                 fn.attr if isinstance(fn, ast.Attribute) else None)
            if nm:
                calls.setdefault(nm, []).append(
                    (rel(p), n.lineno, lines[n.lineno-1].strip()[:110]))
out = {nm: {"defs": defs.get(nm, []), "calls": calls.get(nm, [])}
       for nm in sys.argv[1:]}
print(json.dumps(out, ensure_ascii=False, indent=1))
```

### `/tmp/kwscan.py` 正文（关键字参数扫描器）

```python
import ast, os, sys
ROOT = os.path.abspath(".")
SKIP = {".git","__pycache__",".wt","release","node_modules","output","figures"}
names = set(sys.argv[1:]); hits = []
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in SKIP]
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        try: tree = ast.parse(open(p, encoding="utf-8").read())
        except Exception: continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                for kw in n.keywords:
                    if kw.arg in names:
                        hits.append((os.path.relpath(p, ROOT).replace("\\","/"),
                                     n.lineno, kw.arg, ast.unparse(kw.value)[:60]))
for h in sorted(hits):
    print(f"{h[0]}:{h[1]}  {h[2]}={h[3]}")
```

### `/tmp/probe7.py` 正文（C8 可达性判定）

```python
import sys, logging; sys.path.insert(0, '.'); logging.disable(logging.CRITICAL)
from metaphor_graph.models import MetaphorHyperedge, ChunkSpan
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.llm_backend import MockBackend

e = MetaphorHyperedge(id="X1", source_domain="测试域", target_domain="测试目标",
                      ground=["g"], triggers=["t"],
                      chunk_spans=[ChunkSpan("d_c0", 0, 1, "x")], frame_id=None)
shg = MetaphorSHGBuilder(llm_backend=MockBackend()).build(["无关文本"], doc_id="d")
print("normal build frames:", len(shg.frames))          # → 0

class Ex:
    def extract(self, c, doc_id="doc0", chunk_id=None): return [e]
b2 = MetaphorSHGBuilder(llm_backend=MockBackend()); b2.extractor = Ex()
shg2 = b2.build(["无关文本"], doc_id="d")
print("injected unmatched -> frames:", len(shg2.frames), [f.name for f in shg2.frames])
# → 1 ['NOVEL::测试域']  ⇒ 逻辑可达，但 extractor 永不产出 frame_id=None 的边
```

### `/tmp/probe8.py` 正文（D14 默认开启量化）

```python
import sys, logging; sys.path.insert(0, '.'); logging.disable(logging.CRITICAL)
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology, build_replay_backend
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.retrieval import RetrievalEngine

ont, _ = build_replay_ontology(); pre = build_replay_backend(ont)
texts = [s.text for s in load_ccl2018()[:200]]
ex = MetaphorExtractor(ontology=ont, use_semfield=True, llm_backend=pre,
                       llm_conf_threshold=0.85)
shg = MetaphorSHGBuilder(ontology=ont, extractor=ex, llm_backend=pre).build(
    texts, doc_id='fc0')
on  = RetrievalEngine(shg, texts, doc_id='fc0', ontology=ont)                        # floor=0.5（默认）
off = RetrievalEngine(shg, texts, doc_id='fc0', ontology=ont, reliability_floor=1.0)  # 关闭
n_set = n_ord = n_q = 0
for e in shg.edges:
    if not e.triggers: continue
    q = "，".join(dict.fromkeys(e.triggers))
    a, _ = on.rank_mappings(q, top_k=20, adaptive=False)
    b, _ = off.rank_mappings(q, top_k=20, adaptive=False)
    n_q += 1
    if {x.id for x in a} != {x.id for x in b}: n_set += 1
    if [x.id for x in a] != [x.id for x in b]: n_ord += 1
print(f"edges={len(shg.edges)} queries={n_q}")
print(f"top-20 set differs: {n_set}/{n_q}; order differs: {n_ord}/{n_q}")
print("discounted:", sum(1 for e in shg.edges if on.reliability_factor(e) < 1.0))
# → edges=186 queries=186; set 55/186; order 66/186; discounted 36/186
```

---

## 13. 关键观察（供后续深化）

1. **通路总数**：**98 条**（骨架去重 66 条中 43 条对应到本目录的行，另新增 55 条骨架未收录的通路）。
   逐族：抽取 11 / LLM 批处理 6 / 构建 16 / 检索 14 / 校验 7 / 评测 21 / 信号 17 / 存储 6。
   按采用状态（脚本按 §1 汇总表逐行统计，**合计 98**）：
   ✅ 生产 **38** / 📊 评测或测量 **35** / 🔧 可选 **11** / ⚠️ 存在但未接入 **11** / 💀 死代码 **3**。
2. **「存在但未接入」密度极高**：18 条（§9），其中 **5 条是论文/README 曾声称的能力**（RRF 融合、U-Retrieval/元图、多线索汇聚、HL-index、Ω 门控）。这不是零散的疏漏——它集中在「论文 §3 方法章列了但评测章没测」的那一批。
3. **一条结构性的模式**：本项目所有「软信号通道」（溯源可靠性 D14、Ω G1/G3、HGNN 跨层 E1）都**无法影响 P1**，因为 P1 是**存在性布尔指标**（`pred = bool(edges)`），而软通道只作用于排序层。exp/degrade 已把这条论证钉死（"上界恒等于 0，不是调参问题"）。唯一的例外是 `struct` 特征里的 `cascade_id` 非空布尔位——它也是布尔而非软量。
4. **两处文档与代码不一致**（§9 末表）：`reliability_floor` 默认值（0.5 而非 1.0，**有实际指标影响**）、`llm_verify_extended` 的接入状态（从未调用而非"未默认开启"）。
5. **一个被 docstring 承诺但从未实现的机制**：`semfield.EMBEDDER` 的「语义相似度精化失谐强度」（§9 #16）——运行时探针确认设了 embedder 后 `incongruity_score` 返回值不变。
6. **骨架正则的三类系统漏检**已在 §10 按漏因归类，可直接用于改进 `inventory.py` 的 `PATHWAY_PAT`（建议：加 `_` 前缀白名单、加 `stage_|batch_|precompute|forward|pack|fit|scan|load_|parse_`、按类归属去重同名方法）。

---

## 14. 附录：骨架 77 条 → 本目录的逐条映射（可核对）

`docs/inventory/_extracted.json` 的 77 条 pathway 候选去重后为 **66 个 `(module, function)` 对**
（`llm_backend.py::discover` ×6、`::refine` ×6、`observability.py::measure` ×2 → 共去重 11 条）。
下表逐条给出它在本目录的归属，**无一条遗漏**：

| 骨架条目 (`module.py::func`) | 行 | 本目录 ID | 说明 |
|---|---|---|---|
| `ablation.py::measure` | 58 | F3 | = eval_split 的简化副本（§11 工具：与 F1 重复，应合并） |
| `ablation.py::refine` | 51 | F3 | TrackedBackend.refine —— 隔离 refine 变量的关键件 |
| `bootstrap_triggers.py::extract_equative_pattern` | 144 | C14 | 等比模式串抽取（P1 核心手段） |
| `bootstrap_triggers.py::build_bootstrap_ontology` | 260 | C14 | 自举本体叠加 |
| `builder.py::build` | 55 | C1-C3 | 四层构建主入口 |
| `cascade_rules.py::build_cascades` | 164 | C9 | 级联规则统一入口 |
| `context_budget.py::select` | 80 | D13 | 自适应阈值 |
| `evaluate_a6.py::build_cs_neighbors` | 87 | F14 | 常识邻居生成 |
| `evaluate_document_corpus.py::build_chunks` | 106 | F13 | 段落级分块 |
| `evaluate_fullcorpus.py::build_replay_ontology` | 69 | F5/C9 | 重放本体组装（51 个调用点） |
| `evaluate_fullcorpus.py::build_replay_backend` | 86 | F5 | 重放后端（35 个调用点） |
| `evaluate_fullcorpus.py::build_queries` | 103 | F5 | 三类 by-construction 查询 |
| `evaluate_hgnn.py::build_shg` | 54 | F7 | 统一建图入口（防口径漂移） |
| `evaluate_hgnn.py::measure_p4a` | 81 | F7/E3 | 跨层检索增益 |
| `evaluate_hgnn.py::measure_p4b` | 113 | F7/E2 | 检测器判别力 |
| `evaluate_hgnn.py::measure_h4` | 225 | F7/E1 | 信号来源分解 |
| `evaluate_llmgold.py::build_queries_rich` | 119 | F8 | 携带边与原文的查询 |
| `evaluate_llmgold.py::filter_violations` | 186 | F8 | 程序化红线（切断 clue 捷径） |
| `evaluate_real.py::build_llm_backend` | 36 | F2 | 后端构造 + 回落告警 |
| `evaluate_repaired.py::build_global_graph` | 65 | F9 | 全局候选池 |
| `evaluate_repaired.py::build_paraphrased_sets` | 164 | F11 | 改写型查询映射 |
| `evaluate_repaired.py::build_query_sets` | 198 | F9 | anchored / deanchor 口径 |
| `evaluate_repaired.py::rank_all` | 254 | F9 | 全池打分排序 |
| `evaluate_retrieval.py::measure_p3` | 68 | F4 | P3 跨 chunk 消歧 |
| `evaluate_retrieval.py::measure_h3` | 109 | F4 | H3 隐喻通路 vs 字面 |
| `evaluate_retrieval.py::measure_p3_flag` | 142 | F4 | A5 扩展边消融 |
| `evaluate_retrieval.py::measure_a8` | 164 | F4 | A8 自适应阈值消融 |
| `evaluate_retrieval.py::score_conditions` | 200 | F6 | 四臂共享打分（§6.2 真源） |
| `extended.py::link_extended_metaphors` | 36 | C4 | L1.5 扩展链接 |
| `extractor.py::extract` | 170 | A1+A2+A3 | 三通道同一入口 |
| `hgnn.py::retrieve` | 234 | E3 | 图感知检索 |
| `hgnn.py::retrieve_raw` | 251 | E3 | 原始嵌入对照 |
| `llm_backend.py::verify_chains_batch` | 757 | E5 | LLM 逐链校验 |
| `llm_backend.py::discover` | 74 | A3/B1-B2 | 开放发现（Protocol 1 + 5 实现 → 归 1 条） |
| `llm_backend.py::refine` | 76 | A5/B1-B4 | 细化确认（Protocol 1 + 4 实现 → 归 1 条） |
| `llm_backend.py::discover_batch` | 331 | A3/B2 | 批量开放发现 |
| `llm_backend.py::refine_batch` | 370 | A5/B4 | 批量细化 |
| `llm_ontology.py::build_specs` | 159 | C10 | (源域,目标域) → FrameSpec/CascadeSpec |
| `llm_ontology.py::filter_triggers_by_lift` | 241 | C11 | train.xml lift 过滤 |
| `llm_ontology.py::build_llm_ontology` | 334 | C10 | 本体载入 + 类型系统登记 |
| `metagraph.py::build_from_shg` | 56 | D8 | 元图三层构建（⚠️ 未接入） |
| `metagraph.py::retrieve` | 112 | D7 | U-Retrieval（⚠️ 未接入） |
| `metanet_migrate.py::build_metanet_ontology` | 126 | C15 | MetaNet 种子迁移 |
| `models.py::merge_evidence` | 212 | H4 | 证据链合并（⚠️ 未接入） |
| `observability.py::matched_triggers` | 112 | G1 | Ω 分量：触发词匹配（与 D2 逐字同口径） |
| `observability.py::measure` | 229 | G1 | Ω 测量入口（模块函数 + Meter 缓存包装 = 同一实现的 2 条） |
| `observability.py::measure_many` | 290 | G1 | 批量包装（内部只调 measure） |
| `observability.py::gate` | 294 | G3 | Ω 门控（⚠️ 未接入） |
| `ontology.py::match_by_triggers` | 377 | A1 | 查表组件（§11 工具） |
| `ontology.py::match_frame` | 387 | A8/A9 | 查表组件（§11 工具） |
| `ontology_bilingual.py::build_bilingual` | 189 | C16 | 双语对齐 |
| `ontology_clean.py::clean_ground` | 99 | C12 | R2 清喻底明喻标记 |
| `ontology_clean.py::clean_frames` | 105 | C12 | R1 自环 + R2 + R3 分层 |
| `ontology_clean.py::clean` | 156 | C12 | 清洗主流程 |
| `ontology_clean.py::verify` | 267 | C13 | 三变体对照验证 |
| `ontology_clean.py::discover` | 212 | C13 | _CountingPrecomputed.discover（缓存重放） |
| `ontology_clean.py::refine` | 215 | C13 | _CountingPrecomputed.refine（计命中率） |
| `query_signal.py::compose` | 140 | G5 | 合成开关器 |
| `query_signal.py::measure_signal` | 278 | G4 | S_query 测量入口 |
| `query_signal.py::gate_by` | 381 | G8 | 通用门控（💀 死代码） |
| `retrieval.py::rank_mappings` | 314 | D4 | 语义超图通路入口 |
| `training.py::extract_text_features` | 106 | G12 | 文本锚点 7 维特征 |
| `training.py::extract_features` | 148 | G12 | 超边锚点 7 维特征 |
| `training.py::build_training_set` | 342 | G13 | 自监督训练集 |
| `training.py::build_weak_refine_set` | 570 | G14 | LLM 弱监督训练集 |
| `training.py::score_features` | 542 | G15 | 打分器推理（归入 G15） |
