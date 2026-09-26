# 重构与更正全量目录（refactors.md）

> 生成日期：2026-09-27 ｜ 只读审计，未改动任何生产代码
> 证据基线：`main` @ `c0b74fa`（`git rev-parse HEAD`）
> 机械提取基线：`docs/inventory/_extracted.json` 的 `refactor` 段 **19 行**
> 本目录实收：**49 项**（19 行去重后只覆盖其中 **9 项**，另 **40 项**从 git 历史、
> 分支报告与更正文档补出 —— 机械提取的漏报率约 **82%**）

---

## 0. 摘要

### 0.1 计数

| 性质 | 项数 | 编号 |
|---|---|---|
| `缺陷修复` | 11 | R-01…R-11 |
| `口径修正` | 9 | C-01…C-09 |
| `指标替换` | 3 | M-01…M-03 |
| `假设证伪` | 10 | F-01…F-10 |
| `组件处置` | 6 | K-01…K-06 |
| `基准重建` | 2 | B-01…B-02 |
| `公平性修正` | 3 | A-01…A-03 |
| `编排者自身错误`（单列） | 5 | O-01…O-05 |
| **合计** | **49** | — |

> 机械提取的 19 行去重后是 **13 条注释**，其中 **6 行是同一条注释的重复行**
> （如同一多行注释被逐行匹配）。13 条中 **1 条**（`context_budget.py:102`）是
> 策略说明而非重构；其余 12 条指向 **8 条独立修正**
> （R-01、R-02×3、R-03/K-05×2、R-04、R-06、R-10×2、R-11、A-01）。
> 逐行映射见 §3。

### 0.2 三个必须分开的东西

- **缺陷修复** = 代码写错了。不修就会继续产出错数字（如 `mipvu` 硬编码门控、
  `type` 特征 1.0/0.0 漂移、`evaluate_real` 静默回落）。
- **口径修正** = 代码没错，但**测量被误读**（如 raw 0.150 其实是并列惩罚、
  覆盖率 100% 其实是"有归属"而非"本体登记"、`type` AUC 0.497 其实是训练集口径）。
- **假设证伪** = 设计想法本身错了（Ω、源项、封顶可靠度通道、查询侧标量）。
  这三类对论文的含义完全不同：第一类要改代码，第二类要改表述，第三类要写进 §7 负面结果。

### 0.3 合并状态总览

```
git merge-base --is-ancestor exp/<name> main
→ exp/source  exp/cascade  exp/dynamics  exp/degrade
  exp/typefeat exp/emergent exp/repair   exp/omega
  八个分支全部返回 0（全部是 main 的祖先）
git log --oneline --all --not main   →  空输出
```

**所有代码类修正均已入 main。** 但发现 **5 项文档级遗留**（§5.2）——
其中 D-1（A6 的 0.783 未同步为 1.000）会让论文内部自相矛盾。

### 0.4 护栏覆盖

`metaphor_graph/test_metaphor_graph.py` 现 **228 项**（`python -m unittest
metaphor_graph.test_metaphor_graph` → `Ran 228 tests ... OK`）。
49 项中有 **10 项无护栏**（另有 1 项文档级遗留），见 §6。

---

## 1. 汇总表

| 编号 | 名称 | 性质 | 影响数字 | 护栏 | 已合并 |
|---|---|---|---|---|---|
| R-01 | `mipvu` 硬编码 6 个级联 ID 门控整条通道 | 缺陷修复 | 否（默认路径逐位不变） | `test_production_ontology_defect_is_pinned`（间接）、`TestCascadeConstructionRules`（17 项） | ✅ `33601b6`→`9b150cb` |
| R-02 | `type` 特征双路径漂移（1.0 vs 0.0） | 缺陷修复 | 是（A6 少报 1.8pp；§6.2 由 +4.5pp→+6.4pp） | `test_both_paths_agree_on_type_for_fallback_edge` 等 `TestTypeReliability` 8 项 | ✅ `64872c4`→`8bc5fed` |
| R-03 | 人工权重硬编码两处且与学到权重错配 | 缺陷修复 | 是（§6.2 anchored 0.8390→0.8956） | `test_hand_weights_single_source`、`test_manual_weights_come_from_single_source` | ✅ `012a00e`→`fd2a991` |
| R-04 | 两条打分路径特征维数不一致（4 维 vs 7 维） | 缺陷修复 | 是（A6、§6.2 口径） | `test_two_scoring_paths_share_feature_schema`、`test_manual_type_component_matches_feature` | ✅ `012a00e`→`fd2a991` |
| R-05 | `evaluate_real` 无 key 静默回落 → 假性 P1=0.434 | 缺陷修复 | 否（是告警，不是数字） | **无** | ✅ `245c860` |
| R-06 | `evaluate_a6` 初版用语料库文档（键对不上，n=0） | 缺陷修复 | 否（n=0 无数字） | **无** | ✅ 随首提交 `afa39ae` |
| R-07 | 合并丢失：`evaluate_hgnn` 的 `--alpha/--leak` | 缺陷修复（合并回归） | 否 | `test_eval_cli_args_present` | ✅ `cb8d81d`+`3ac9f2a` |
| R-08 | `score_conditions` 无条件加 legacy 臂 → KeyError | 缺陷修复（合并回归） | 否 | `test_score_conditions_default_arms_stable`、`test_legacy_weights_reproducible` | ✅ `db29ac8` |
| R-09 | 多处 auto-merge 冲突标记未清（语法错误） | 缺陷修复（合并回归） | 否 | `test_all_eval_modules_importable` | ✅ `3ac9f2a` |
| R-10 | `llm_ontology` 一律给 `GENERIC_VEHICLE` → 类型约束恒真 | 缺陷修复 | 是（A1/H1 的机制前提） | **无**（仅 README §7.1 记录） | ✅ 随首提交 `afa39ae` |
| R-11 | `extractor` 开放发现通道二次调用 refine（浪费+可能误否） | 缺陷修复 | 否 | **无** | ✅ 随首提交 `afa39ae` |
| C-01 | `raw = 0.150` 是并列惩罚，实为「无信息」 | 口径修正 | 是（§6.3 表 + 结论 2） | `test_h4_auc_full_handles_ties` | ✅ `48fc56f`→`95b958b` |
| C-02 | P2 覆盖率 100% 含注水（诚实口径 77.6% / 82.4%） | 口径修正 | 是（§5.2、附录 B P2） | `test_honest_coverage_backward_compatible`、`test_honest_coverage_not_above_reported`、`test_judgement_is_registration_not_prefix` | ✅ `078d099`→`1c0ed64` |
| C-03 | 覆盖率归因错误：100% 来自兜底函数而非本体查表 | 口径修正 | 是（§5.2 措辞） | `test_health_flags_adhoc_coverage_inflation` | ✅ `33601b6`→`9b150cb` |
| C-04 | `type` AUC 0.497 是训练集口径，评测口径 0.5249 | 口径修正 | 是（推翻 gen1「死维」判决） | `test_type_auc_is_near_noise_on_training_set` | ✅ `77a07b0`→`c85103d` |
| C-05 | 「LLM 非构造金标」标签不成立（100% 锚定） | 口径修正 | 是（§4/§6.1/§6.2/§8） | `test_paraphrased_sets_map_onto_global_pool` | ✅ `77a07b0`→`c85103d` |
| C-06 | A7/A9 三臂相同系池饱和，非「无差异」 | 口径修正 | 是（§7 表加警告） | **无** | ✅ `319338c` |
| C-07 | `ground_jaccard` 两路径定义不同（包含率 vs Jaccard） | 口径修正 | 否（已标注未改） | **无** | ✅ 报告 `REPORT_exp-source.md` §5.1 |
| C-08 | `sem` 的 clamp 两路径不一致（潜在隐患） | 口径修正 | 否（当前数据未触发） | **无** | ✅ 报告 §5.2（标注未改） |
| C-09 | 权重错配倍数 37/12（归一化）vs 49/19（原始口径） | 口径修正 | 是（§6.2 表述） | `test_hand_weights_single_source`（断言 >10 倍） | ✅ `c85103d` + `da5971f` |
| M-01 | H4 主指标：n=20 配对准确率 → 全量负样本 AUC | 指标替换 | 是（§6.3 表加列） | `test_h4_auc_full_handles_ties` | ✅ `48fc56f`→`95b958b` |
| M-02 | §6.1 通路指标：池 ≤10 饱和 → 全局池 1,100 | 指标替换 | 是（1.000→0.1918） | `test_random_baseline_improves_with_pool`、`test_pathway_rankings_three_paths` | ✅ `245c860`→`fd2a991` |
| M-03 | §6.2 排序器表：重叠型 → 四族（含改写型） | 指标替换 | 是（+4.5pp 对应改写型行） | `test_paraphrased_sets_map_onto_global_pool` | ✅ `0194b8d` |
| F-01 | Ω 无额外信息量（退化为 1-bit 触发词指示器） | 假设证伪 | 否（新增负面结果） | `TestQueryObservability` 21 项（含 2 项局限护栏） | ✅ `4cbf5d6`→`9b150cb` |
| F-02 | 无源项算子退化解释 H4 平局 | 假设证伪 | 否（原结论反而加强） | `TestHGNDriven` 13 项 | ✅ `48fc56f`→`95b958b` |
| F-03 | 封顶可靠度通道让类型约束影响 P1 | 假设证伪 | 否（新增负面结果） | `TestProvenanceReliability` 13 项 | ✅ `078d099`→`1c0ed64` |
| F-04 | 查询侧标量可预测检索行为（Ω → `S_query`） | 假设证伪 | 否（§7 新增负面结果） | `TestQuerySignal` 15 项 | ✅ `0216dcd`→`b6599bd` |
| F-05 | `n_emergent` 的 0.836 是真实信号 | 假设证伪 | 否（但澄清 gen2 结论） | `test_s_query_is_not_a_proxy_for_trigger_count_alone` | ✅ `0216dcd`→`b6599bd` |
| F-06 | 更换级联构造规则能移动检索指标 | 假设证伪 | 否（度量中性） | `TestCascadeConstructionRules` 17 项 | ✅ `33601b6`→`9b150cb` |
| F-07 | `type` 是死维（单特征 AUC 0.497） | 假设证伪 | 是（推翻前两代表述） | `test_type_auc_is_near_noise_on_training_set` | ✅ `77a07b0`→`c85103d` |
| F-08 | 训练增益来自「训练学到了隐喻结构信号」 | 假设证伪 | 是（§6.2/摘要(6)/§9 重述） | `test_trained_weight_of_type_is_near_zero`、`test_manual_weighting_float_order_matters` | ✅ `77a07b0`→`c85103d` |
| F-09 | 特征删除/替换能提升排序 | 假设证伪 | 否（9 个处置 CI 全覆盖 0） | `test_same_cascade_can_be_redundant_with_same_frame` | ✅ `77a07b0`→`c85103d` |
| F-10 | A7/H5「+9.5pp 翻转」的归因 | 假设证伪 | 是（真实增量 +0.29pp） | **无**（见 §6） | ✅ `77a07b0`→`c85103d` |
| K-01 | HGNN 从检索路径移除（从未被调用） | 组件处置 | 否（本来就不在路径上） | **无**（代码审计结论，非可测断言） | ✅ `1311949`（文档） |
| K-02 | L3 级联层保留但降级为「组织/可解释性」 | 组件处置 | 是（§6.3 加附加条件） | `test_production_ontology_defect_is_pinned` | ✅ `1311949` + `da5971f` |
| K-03 | `type` 特征保留（非死维但弱） | 组件处置 | 否 | `TestTypeReliability` 8 项 | ✅ `1311949` |
| K-04 | `same_cascade` 保留（删除无收益） | 组件处置 | 否 | `test_same_cascade_can_be_redundant_with_same_frame` | ✅ `1311949` |
| K-05 | 人工权重重标定（保留 `HAND_WEIGHTS_LEGACY`） | 组件处置 | 是（§6.2 anchored Δ+0.0565） | `test_legacy_weights_reproducible` | ✅ `012a00e`→`fd2a991` |
| K-06 | 级联默认构造规则不改（改则重写 733 个稳定 ID） | 组件处置 | 否（无指标收益） | `test_builder_default_orphan_rule_is_target` | ✅ `33601b6`→`9b150cb` |
| B-01 | 检索基准重建：全局池 1,100 | 基准重建 | 是（全部 §6.1/§6.2 数字） | `test_random_baseline_improves_with_pool` | ✅ `245c860`→`fd2a991` |
| B-02 | 检索基准重建：去锚定口径（deanchor） | 基准重建 | 是（锚定抬高 ≈+0.66） | `test_paraphrased_sets_map_onto_global_pool` | ✅ `245c860`→`fd2a991` |
| A-01 | A6 两臂预算不对等（`top_k=5` vs 无上限） | 公平性修正 | 是（0.8287→1.0000） | `test_no_hardcoded_budget_in_comparisons`、`test_a6_metaphor_arm_has_adjustable_budget` | ✅ `b21b5e6` |
| A-02 | 公平性未系统检查（三处同类缺陷） | 公平性修正 | 是（新增 §4.1 声明） | `metaphor_graph/audit_fairness.py` + 上述 2 项 | ✅ `dfa98a0` |
| A-03 | `audit_fairness` 首版未剥离注释 → 误报 | 公平性修正（工具自身） | 否 | 工具 docstring 留痕 | ✅ `dfa98a0` |
| O-01 | 编排者代写草稿：把 `json` 区间外推为四规则 | 编排者自身错误 | 是（推翻 gen2 的机制归因） | `TestQuerySignal.test_compose_switch_semantics` | ✅ `9c762a7` + `0216dcd` |
| O-02 | 编排者代写草稿：把 ε 下界当作坍缩来源 | 编排者自身错误 | 否（机制归因更正） | 同上 | ✅ `9c762a7` + `0216dcd` |
| O-03 | 编排者因果链错误：§6.2 被 `type` 口径污染 | 编排者自身错误 | 是（避免了一次错误的论文修改） | — | ✅ 报告 §0 自我更正 |
| O-04 | 编排者推断错误：级联 0.836 可迁移到生产默认规则 | 编排者自身错误 | 是（澄清 gen2 结论） | — | ✅ `702d7ca` |
| O-05 | 编排者推断错误：算子退化解释 H4 平局 | 编排者自身错误 | 否 | `test_source_term_prevents_collapse` | ✅ `48fc56f`→`95b958b` |

---

## 2. 详细块（按性质分组）

### 2.1 `缺陷修复`（11 项）

#### R-01 `mipvu` 硬编码 6 个级联 ID 门控整条通道

- **触发发现**：`exp/cascade`（gen2）。替换级联构造规则后 L1 边从 856 掉到 849，
  丢 7 条边。证据：`experiments/gen2/REPORT.md:79`（§1.5 根因 file:line）、
  `:364-378`（§7.2 修改表）、`.wt/cascade/experiments/gen2/REPORT.md` 同节。
- **原状 → 现状**：
  ```python
  # 原（mipvu.py:91）
  if ont.cascades.get(cascade_id) is None:
      continue
  # 现（mipvu.py:96-100）
  if ont.get_frame(frame_id) is None:
      continue
  if ont.cascades.get(cascade_id) is None and \
          ont.get_cascade(frame_id) is None:
      continue
  ```
  注释留痕在 `metaphor_graph/mipvu.py:92-95`。
- **性质**：`缺陷修复`。这是**实验污染陷阱**——不修则所有级联规则对照表都被污染
  （"级联规则"与"抽取通道开关"两个变量混在一起）。
- **影响已上报数字**：否。默认 `json` 规则下 6 个硬编码 id 都存在，两条件等价，
  实测 856 条边逐位不变。
- **护栏**：`TestCascadeConstructionRules` 17 项覆盖规则性质与默认行为；
  `test_production_ontology_defect_is_pinned`（`test_metaphor_graph.py:2501`）
  把缺陷本身钉住。**但没有一条测试直接断言"换规则后 MIPVU 通道仍开启"**。
- **合并**：`33601b6`（分支）→ `9b150cb`（合并入 main）。
  `git branch --contains 33601b6` → `+ exp/cascade + exp/emergent * main`。

#### R-02 `type` 特征双路径漂移（1.0 vs 0.0）

- **触发发现**：`exp/source`（gen1）。假设为「`F_LLM_*` 降级边在两条路径上
  type 取值不同，可能污染 §6.2 的 +4.5pp」。证据：`experiments/REPORT_exp-source.md:37-65`
  （§1.1 两条不一致的表达式）、`:67-82`（§1.2 量化 22.0% 分歧）。
- **原状 → 现状**：
  | 位置 | 原 | 现 |
  |---|---|---|
  | `training.py:81`（原）| `type_ok = 1.0 if cand.frame_id else 0.0` | `ont.type_reliability_of(...)` @ `training.py:133` |
  | `training.py:112-113`（原）| `type_ok = 1.0 if fspec_type else 0.0` | `training.py:171` |
  | `retrieval.py:250-252`（原）| `get_frame()`+`type_valid()` 手写分支 | 删除，改走 `_pair_features` → 同一函数 |
  单一真源：`ontology.py:413`（`type_reliability`）/ `:445`（`type_reliability_of`），
  常量 `ontology.py:130-133`（1.0 已注册 / 0.5 未注册回退 / 0.0 无归属或非法）。
- **性质**：`缺陷修复`。**设计选择是"封顶 0.5 而非 0.0"**——`F_LLM_*` 边是开放发现
  换来 +55.8pp 召回的载体，判 0.0 等于关掉开放发现。
- **影响已上报数字**：**是**。§6.2 人工加权 0.502→0.481、训练增益 +4.5pp→+6.4pp；
  真实句向量 +5.2pp→+7.8pp；A6 曾静默低估 1.8pp（0.783 应为 0.801）。
  论文 §6.2、§7.3、摘要。
- **护栏**：`TestTypeReliability`（8 项，`test_metaphor_graph.py:1966`）+
  `TestManualWeightedTypeConsistency`（1 项，`:2247`）。核心是
  `test_both_paths_agree_on_type_for_fallback_edge`（`:2009`）与
  `test_fallback_not_dropped`（`:2038`，钉住 `FALLBACK > 0` 的设计意图）。
- **合并**：`64872c4`（分支）→ `8bc5fed`（合并）。
  `git branch --contains 64872c4` → `+ exp/source + exp/typefeat * main`。

#### R-03 人工权重硬编码两处且与学到权重错配

- **触发发现**：`exp/typefeat`（gen3）§3.2「本代最大发现」：
  `experiments/gen3/REPORT.md:252-267`。仅把人工权重按学到比例重配（不训练模型），
  MRR 0.4809 → 0.5496（+6.87pp，p=0.0000），**反超**训练后 0.5447。
- **原状 → 现状**：权重原硬编码在 `retrieval.py` 与 `evaluate_retrieval.py` 两处
  （`0.35/0.25/0.20/0.20`）。现为单一真源 `training.py:62`（`HAND_WEIGHTS_LEGACY`）
  与 `training.py:76`（`HAND_WEIGHTS = _normalized(_LEARNED_SHARE)`），
  函数 `training.py:79`（`hand_weighted_score`）；调用点 `retrieval.py:305`
  与 `evaluate_retrieval.py:232`。
- **性质**：`缺陷修复`（同一常量两处定义 = 必然漂移）+ 超参未校准。
- **影响已上报数字**：**是**。anchored MRR 0.8390→0.8956（Δ+0.0565）；
  §6.2 全部数字；摘要 (6)。
- **护栏**：`test_hand_weights_single_source`（`:1743`，断言
  `HAND_WEIGHTS_LEGACY["struct"] / HAND_WEIGHTS["struct"] > 10`，防止有人
  "顺手改回拍脑袋的值"）；`test_manual_weights_come_from_single_source`（`:2117`）；
  `test_manual_weighting_float_order_matters`（`:2148`，钉住逐项顺序累加）。
- **合并**：`012a00e` → `fd2a991`。

#### R-04 两条打分路径特征维数不一致（4 维手写公式 vs 7 维共享特征）

- **触发发现**：`exp/source` 的 `probe_feature_paths.py`（`experiments/REPORT_exp-source.md:111-143`）。
- **原状 → 现状**：`retrieval.metaphor_retriever_score` 原走
  `0.35·sem + 0.25·struct + 0.20·clue + 0.20·type`（4 维手写），
  现改为 `_pair_features` + `hand_weighted_score`（`retrieval.py:305`）。
- **性质**：`缺陷修复`。
- **影响已上报数字**：**是**（与 R-02 同源；A6 经 `rank_mappings` 走此路径）。
- **护栏**：`test_two_scoring_paths_share_feature_schema`（`:1766`）、
  `test_manual_type_component_matches_feature`（`:2255`）、
  `test_feature_index_contract`（`:2095`）。
- **合并**：`012a00e` → `fd2a991`。

#### R-05 `evaluate_real` 无 key 静默回落 → 假性 P1 = 0.434

- **触发发现**：`exp/degrade` §1.1 口径陷阱（`experiments/REPORT_exp-degrade.md:27-44`）。
  直接跑 `evaluate_real.py --use-llm` 无 key 时回落到 `LocalHeuristicBackend`，
  它不实现 `discover_batch`/`batch_refine`，于是 `--llm-cache` **根本没被消费**，
  产出假性 P1 = 0.434（真实 0.092）。
- **原状 → 现状**：`evaluate_real.py:36`（`build_llm_backend`）现打印 6 行显式告警
  （`evaluate_real.py:48-59`），指向 `PrecomputedBackend`（`evaluate_fullcorpus.py:86`）。
  注释留痕 `evaluate_real.py:50-53`。
- **性质**：`缺陷修复`。README §7.1 称其为"本项目最危险的静默陷阱"。
- **影响已上报数字**：否（告警而非改数字）。但若有人据 0.434 上报则会。
- **护栏**：**无**。`test_metaphor_graph.py` 只在 `:1956` 的
  `test_all_eval_modules_importable` 里 import 该模块，不断言告警存在。
  同类防护只有 `test_injected_error_propagates_no_silent_fallback`（`:1088`，
  针对 embedder，不针对 LLM 后端）。
- **合并**：`245c860` → `fd2a991`。

#### R-06 `evaluate_a6` 初版用语料库文档（键对不上，n=0）

- **触发发现**：A6 实验初版。证据：代码注释
  `metaphor_graph/evaluate_a6.py:145`：「（初版误用语料库文档 cj/gov/lx，键对不上，
  n=0，已修正）」。
- **原状 → 现状**：改为 `fc{i//10}` 伪文档，与改写查询/LLM 金标缓存键对齐
  （`evaluate_a6.py:141-148`）。
- **性质**：`缺陷修复`。
- **影响已上报数字**：否（n=0 时没有可上报数字）。
- **护栏**：**无**。`test_paraphrased_sets_map_onto_global_pool`（`:1905`）
  覆盖 `evaluate_repaired` 的同类键对齐，不覆盖 A6。
- **合并**：随首提交 `afa39ae`（main 基线即含修复）。

#### R-07 合并丢失：`evaluate_hgnn` 的 `--alpha/--leak`

- **触发发现**：合并 `exp/dynamics` 时冲突解决遗漏 argparse 定义，
  运行时 `AttributeError: 'Namespace' object has no attribute 'alpha'`。
  证据：commit `cb8d81d` 消息。
- **原状 → 现状**：`evaluate_hgnn.py` 补回 6 行 argparse（`cb8d81d` 净 +6 行）。
- **性质**：`缺陷修复`（**合并引入的回归，非原有缺陷**）。
- **影响已上报数字**：否。
- **护栏**：`test_eval_cli_args_present`（`:1863`）——解析 `evaluate_hgnn.main`
  源码，钉住 `--alpha/--leak/--embedder/--cascade-rule` 在 `parse_args()` 之前注册。
- **合并**：`cb8d81d`（直接提交在 main）→ `3ac9f2a` 补护栏。
  `git branch --contains cb8d81d` → `* main`。

#### R-08 `score_conditions` 无条件加 legacy 臂 → KeyError

- **触发发现**：`012a00e` 把 `hand_weighted_legacy` 无条件加入返回字典，
  `evaluate_fullcorpus` 按固定键列表聚合时 KeyError（实测崩溃）。
  证据：commit `db29ac8` 消息。
- **原状 → 现状**：改为 `legacy_arm: bool = False` 参数（`evaluate_retrieval.py:200`），
  默认只返回 3 个臂；`HAND_WEIGHTS_LEGACY` 臂在 `:233-235` 显式 opt-in。
- **性质**：`缺陷修复`（合并引入的回归）。
- **影响已上报数字**：否。
- **护栏**：`test_score_conditions_default_arms_stable`（`:1841`）、
  `test_legacy_weights_reproducible`（`:1854`）。
- **合并**：`db29ac8`（直接提交在 main）。

#### R-09 多处 auto-merge 冲突标记未清（语法错误）

- **触发发现**：合并七个分支时多处 git 未标记的 auto-merge 冲突
  （commit `1c0ed64` 消息记录"5 个文件，含 git 未标记的 auto-merge 冲突"）。
- **原状 → 现状**：清理冲突标记；新增 `test_all_eval_modules_importable`
  （`:1950`）覆盖 10 个评测模块的 import。
- **性质**：`缺陷修复`（合并引入的回归）。
- **影响已上报数字**：否。
- **护栏**：`test_all_eval_modules_importable`（`:1950`）。
- **合并**：`3ac9f2a`（直接提交在 main）。
- **⚠️ 同类残留**：`experiments/gen3/REPORT.md` **仍有未清理的冲突标记**
  （`:1` `<<<<<<< HEAD`、`:634` `=======`、`:1274` `>>>>>>> exp/emergent`），
  且是**已提交状态**（`git log -1 -- experiments/gen3/REPORT.md` → `b6599bd`）。
  该文件是两个分支报告（typefeat 与 emergent）的**未合并拼接**。见 §5.1。

#### R-10 `llm_ontology` 一律给 `GENERIC_VEHICLE` → 类型约束恒真

- **触发发现**：README §7.1 结论 1 的根因分析：「H1 失效的表面根因是自举框架
  全是 `GENERIC_VEHICLE`」（`metaphor_graph/README.md:731-739`）。
  `GENERIC_VEHICLE → GENERIC_VEHICLE_MAP` 在 `TYPE_CONSTRAINTS` 里无条件合法，
  故 `type_valid` 从不拒绝任何候选（实测拦下 0 个）。
- **原状 → 现状**：
  - 新增 `ontology.py:70`（`infer_source_type`）+ 关键词规则表
    （`ontology.py:29-68`），注释留痕 `ontology.py:25-28`；
  - `llm_ontology.py:208`（`stype = infer_source_type(s)`），注释留痕 `:207`；
  - `mapping_type` 改为可区分的 `DISCOVERED::{source_type}_TO_{target}`
    （`llm_ontology.py:211-212`）；
  - 效果：`GENERIC_VEHICLE` 占比 **98.6% → 32.8%**（README §7.1）。
- **性质**：`缺陷修复`。**但注意**：修复后 H1 **仍然证伪**——类型约束拦下 24 个
  错误绑定，P1 纹丝不动（约束管"挂哪个框架"，不管"要不要这条边"）。
  这是一个"修了 bug 但假设仍不成立"的典型案例。
- **影响已上报数字**：**是**（A1/H1 的机制前提；P1 与召回不变，但"类型约束是否有效"
  的论证链变了）。
- **护栏**：**无**。没有测试断言 `GENERIC_VEHICLE` 占比低于某阈值。
- **合并**：随首提交 `afa39ae`（main 基线即含）。

#### R-11 `extractor` 开放发现通道二次调用 refine

- **触发发现**：成本与正确性双重问题（注释
  `metaphor_graph/extractor.py:187`：「LLM 开放发现通道：结论已由 discover 给出，
  不再二次调用 refine」）。
- **原状 → 现状**：`extractor.py:186-189` 新增 `skip_refine` 分支，
  `:273`（`skip_refine=True`）由发现通道传入。
- **性质**：`缺陷修复`（避免对已判定候选再判一次，可能被 refine 误否 + 多花 API）。
- **影响已上报数字**：否。
- **护栏**：**无**（无测试断言 `skip_refine` 路径不调 refine）。
- **合并**：随首提交 `afa39ae`。

---

### 2.2 `口径修正`（9 项）

#### C-01 `raw = 0.150` 是并列惩罚，实为「无信息」

- **触发发现**：`exp/dynamics` §6.1（`experiments/REPORT_exp-dynamics.md:291-310`）。
  默认哈希编码器下抽象域标签几乎无共享 n-gram，实测**全体并列率 94.6%**
  （正样本 85.0%、负样本 94.8% 的余弦恰为 0）；配对准确率把并列计为错误。
- **原状 → 现状**：原表述「原始嵌入 0.150，远低于随机/显著更差」→
  现表述「AUC 0.550 = 无信息；0.150 系并列计错的口径产物」。
  论文 §6.3 表（`论文初稿.md:367-395`）+ 结论 2。
- **性质**：`口径修正`。**代码没错，指标读错了。**
- **影响已上报数字**：**是**。§6.3 表与结论 2。
- **护栏**：`test_h4_auc_full_handles_ties`（`:1821`）——断言全并列时
  `_auc_full` 返回 0.5 而非 0（"这正是原 acc 口径把 raw 报成 0.150 的原因"）。
- **合并**：`48fc56f` → `95b958b`。

#### C-02 P2 覆盖率 100% 含注水

- **触发发现**：`exp/degrade` §5.4（`experiments/REPORT_exp-degrade.md:341-371`）
  + §3.3（`:156-173`）。重跑 `probe_provenance2.py`：超边 883 条，
  报出覆盖率 1.000，但**本体正式登记**的只有 685/883 = **0.776**；
  级联 408 其中 184（45.1%）为事后补的 `C_ADHOC_*`。
  `exp/cascade` 独立确认（`experiments/gen2/REPORT.md:283-307`）。
- **原状 → 现状**：
  - `health.py:109`（`graph_health(..., ontology=None)`）新增
    `registered_frame_coverage` / `registered_cascade_coverage` /
    `registered_hierarchy_coverage`（`:177-192`）；**不传 ontology 时字段为 `None`**，
    历史口径逐位不变；
  - 论文附录 B P2 由 ✅ 改为 **⚠️ 条件性达标**（`论文初稿.md:641`）；
    §5.2 双口径表（`:269-295`）。
- **性质**：`口径修正`。现报口径度量"每条边是否都有层级归属"，
  诚实口径度量"层级归属是否来自本体"——**两个都该报**。
- **影响已上报数字**：**是**。§5.2、附录 B P2、摘要 (2)。
- **⚠️ 数字不一致（本审计新发现）**：**同一份文档里有 82.4% 与 77.6% 两个诚实口径值。**
  - `论文初稿.md:275` / `README.md:26` / `DATA.md:123` / `论文初稿_en.md:180` → **82.4%**
  - `experiments/REPORT_exp-degrade.md:161` / `实验结论汇总.md:155` / `论文修正建议.md:21` → **77.6%**
  实测复现（本审计，120 句子集）：`edges=108, registered_frame_coverage=0.8241,
  n_fallback_edges=19, n_cascades=89, adhoc=19` → **82.4%**。
  即 **82.4% 来自 120 句子集（19/108 回退边），77.6% 来自 1,100 句全量集（198/883）**。
  两者都对，但是**不同样本量**，论文只报了其中一个而未标注 n。
  论文正文写的"实测（120 句子集）"与数值 82.4% 一致，**数值本身正确**；
  但 `experiments/` 三份文档报 77.6% 且未标 n，读者会认为矛盾。
- **护栏**：`test_honest_coverage_backward_compatible`（`:1785`）、
  `test_honest_coverage_not_above_reported`（`:1795`）、
  `test_coverage_judgement_is_registration_not_prefix`（`:1807`）、
  `test_health_reports_honest_coverage_only_with_ontology`（`:2657`）、
  `test_health_flags_adhoc_coverage_inflation`（`:2669`）。
- **合并**：`078d099` → `1c0ed64`。

#### C-03 覆盖率归因错误：100% 来自兜底函数而非本体查表

- **触发发现**：`exp/cascade` §5（`experiments/gen2/REPORT.md:283-307`）。
  关掉 `builder._ensure_cascades` 后覆盖率 **1.000 → 0.767**（跌破 0.85 门槛）。
- **原状 → 现状**：`builder.py:150-166` docstring 显式记录"已知结构缺陷"：
  「按目标域打包与 `llm_ontology.build_specs` 的构造规则完全相同……
  它唯一的量化收益是 `graph_health.cascade_coverage` 从 ~0.78 抬到 1.000」。
  论文 §5.2 措辞改为「级联查表 **+ 目标域兜底**」。
- **性质**：`口径修正`（归因错，非代码错）。
- **影响已上报数字**：**是**（§5.2 成本主张与覆盖率来源的表述）。
  但**成本主张不受影响**：两种方式都是查表式（零 LLM 调用），
  ~20 vs ~187 次/千边仍成立。
- **护栏**：`test_health_flags_adhoc_coverage_inflation`（`:2669`）。
- **合并**：`33601b6` → `9b150cb`。

#### C-04 `type` AUC 0.497 是训练集口径，评测口径 0.5249

- **触发发现**：`exp/typefeat` §1.1（`experiments/gen3/REPORT.md:33-63`）。
  gen1 报的 0.4973 来自 `feature_auc(ds)`，`ds` 是**自监督训练集**，
  **不是评测候选对**。评测金标上 `type` 配对 AUC = **0.5249 [0.5092, 0.5401]**（CI 不含 0.5）。
- **原状 → 现状**：裁决从 `dead` 改为 `useful（弱）+ redundant(struct)`
  （`实验结论汇总.md:361-383`）；论文表述修正建议见 `论文修正建议.md` 修正 11。
- **性质**：`口径修正`。**三个 gen1 数字（0.4973 / +0.0487 / 0.20）全部逐位复现**，
  只是口径标签错了。
- **影响已上报数字**：**是**（推翻前两代的"死维"表述）。
- **护栏**：`test_type_auc_is_near_noise_on_training_set`（`:2163`）、
  `test_type_and_struct_are_not_independent`（`:2216`）。
- **合并**：`77a07b0` → `c85103d`。

#### C-05 「LLM 非构造金标」标签不成立

- **触发发现**：`exp/typefeat` §4.1 缺陷 2（`experiments/gen3/REPORT.md:343-375`）。
  实测：LLM 金标包含「产出该问题的 chunk」**632/632 = 100%**；
  恰好只等于它 **619/632 = 97.9%**；可真正检验非构造检索的查询**仅 13/632 = 2.1%**。
- **原状 → 现状**：论文 §4 的「非构造金标」标签删除；§4.2 新增基准自我审计；
  §6.1 加修正段；§8 限制。
- **性质**：`口径修正`。LLM 的作用是**过滤**（筛掉 3.2% 不认可），**没有解除锚定**。
- **影响已上报数字**：**是**（§6.1/§6.2 全部检索数字的**解释**，非数值）。
- **护栏**：`test_paraphrased_sets_map_onto_global_pool`（`:1905`）。
- **合并**：`77a07b0` → `c85103d`。

#### C-06 A7/A9 三臂相同系池饱和

- **触发发现**：`evaluate_fullcorpus` 上 A7/A9 三臂结果**完全相同**（均 0.998），
  但该基准每查询候选池 min=5 / median=8 / max=10（**100% ≤10**）。
  证据：commit `319338c` 消息 + `db29ac8` 消息。
- **原状 → 现状**：论文 §7 表加 provenance 警告（`论文初稿.md:552-557`）：
  「该表上的 A7/A9 结论**不可用于判定训练/特征的价值**；有效数字应取
  §4.1/§6.7 的修复后基准（全局池 1,100）」。
- **性质**：`口径修正`。
- **影响已上报数字**：**是**（§7 表的可用性判定）。
- **护栏**：**无**（文档级修正）。
- **合并**：`319338c`（直接提交在 main）。

#### C-07 `ground_jaccard` 两路径定义不同

- **触发发现**：`exp/source` §5.1（`experiments/REPORT_exp-source.md:394-405`）。
  实测 4.76%（113/2375）分歧：`extract_text_features:98` 用**包含率**
  `|g ∩ text| / |g|`，`extract_features:130` 用**真 Jaccard** `|gq ∩ gc| / |gq ∪ gc|`。
  包含率均值 0.125 vs Jaccard 均值 0.150。
- **原状 → 现状**：**已标注，未改动**。理由：文本没有喻底集合，无法算 Jaccard，
  这是设计内的锚点差异；改动会波及所有历史数字且无明确更优选择。
- **性质**：`口径修正`（标注为已知差异，非 bug）。
- **影响已上报数字**：否（标注）。
- **护栏**：**无**。
- **合并**：`64872c4` → `8bc5fed`（报告随分支合并）。

#### C-08 `sem` 的 clamp 两路径不一致（潜在隐患）

- **触发发现**：`exp/source` §5.2（`experiments/REPORT_exp-source.md:407-416`）。
  `training.py:72/104` 用 `max(0.0, cosine(...))`，
  `retrieval.py:246-247`（原人工加权）用 `cosine(...)` **无 clamp**。
- **原状 → 现状**：**已标注为隐患，未改**。本次语料下 cos 恒非负
  （7437 样本中 0 个负值），**当前无影响**；但换 `NgramEmbedder` / 真实句向量后
  cos 可为负，届时人工加权会给出负 `sem`（惩罚）而训练路径为 0。
- **性质**：`口径修正`（隐患标注）。注意 R-04 统一到 `_pair_features` 后，
  该不一致**在结构上已被消除**（两条路径共用同一函数）——但报告写于修复前，
  未回写此推论。
- **影响已上报数字**：否（当前未触发）。
- **护栏**：**无**。
- **合并**：报告随 `8bc5fed` 入 main。

#### C-09 权重错配倍数：37/12（归一化）vs 49/19（原始口径）

- **触发发现**：`exp/typefeat` §6.3 错配清单（`experiments/gen3/REPORT.md:472-502`）：
  `struct` 人工 0.250 vs 应为 0.005 → **高估 49×**；`type` 0.200 vs 0.011 → **19×**。
  而 `exp/repair` 的报告写 **37 倍 / 12 倍**。
- **原状 → 现状**：论文 §6.2 现写「**struct 过权 37 倍、type 12 倍**
  （归一化后；原始口径 49/19 倍）」（`论文初稿.md:347-349`）——两个口径都标注了。
- **性质**：`口径修正`（同一错配的两个计量口径：归一化后 vs 原始空间有效权重）。
- **影响已上报数字**：**是**（§6.2 表述；数值本身不变）。
- **护栏**：`test_hand_weights_single_source`（`:1743`）断言比值 > 10，两个口径都过。
- **合并**：`c85103d` + `da5971f`。

---

### 2.3 `指标替换`（3 项）

#### M-01 H4 主指标：n=20 配对准确率 → 全量负样本 AUC

- **触发发现**：`exp/dynamics` §6.2（`experiments/REPORT_exp-dynamics.md:311-331`）。
  n=20 配对分辨率仅 0.05，其「结论字符串」会随无关参数抖动翻转
  （α=0.5 时打印"依赖跨层传播 ✅"），而同期 AUC 完全稳定；
  逐对严格检验显示 α=1 时 flat 与 HGNN 的判对模式**完全相同**（McNemar b=c=0，p=1.000）。
- **原状 → 现状**：`evaluate_hgnn.py:316` 新增 `_auc_full`（正确处理并列）；
  `evaluate_hgnn.py:398-419` 判定改用 `h4["flat"]["auc_full"]` / `h4["hgnn"]["auc_full"]`；
  配对准确率降为历史兼容列（`:407-408` 打印说明）。
  论文 §6.3 表加「**全量 AUC**」列（`论文初稿.md:367-372`）。
- **性质**：`指标替换`。
- **影响已上报数字**：**是**。§6.3 表由 4 列变 5 列；HGNN 0.915 / flat 0.910 /
  raw 0.550 / GRU 0.945。
- **护栏**：`test_h4_auc_full_handles_ties`（`:1821`）。
- **合并**：`48fc56f` → `95b958b`。

#### M-02 §6.1 通路指标：池 ≤10 饱和 → 全局池 1,100

- **触发发现**：`exp/typefeat` §4.1 缺陷 1（`experiments/gen3/REPORT.md:343-360`）：
  候选池 min=2 / median=7 / max=10，**池 ≤10 的查询占 100%** →
  Hits@10 在 100% 的查询上平凡为 1.000；随机排序期望 MRR = 0.2622（指标真实地板）。
- **原状 → 现状**：`evaluate_repaired.py` 全局池 1,100；`pathway_rankings()`
  （`evaluate_repaired.py:277`）三通路同池比较。论文 §6.7 按查询族分列表。
- **性质**：`指标替换` + `基准重建`（与 B-01/B-02 同源，此处单列指标口径变化）。
- **影响已上报数字**：**是**。语义超图 Hits@10 **1.000 → 0.1918**（↓5.2×）；
  级联 0.042 → 0.0206。
- **护栏**：`test_random_baseline_improves_with_pool`（`:1833`）、
  `test_pathway_rankings_three_paths`（`:1886`）。
- **合并**：`245c860` → `fd2a991`，四族补测 `e014e37`/`d233e9a`/`087afe8`。

#### M-03 §6.2 排序器表：重叠型 → 四族（含改写型）

- **触发发现**：修复后基准的排序器表最初用**重叠型**查询，而 §6.2 的结论
  基于**改写型**——查询族不匹配。证据：commit `0194b8d` 消息。
- **原状 → 现状**：补四族（重叠/改写 × anchored/deanchor）：
  `experiments/三通路重测_修复后基准.md:141-146`；论文 §6.2 表（`论文初稿.md:333-343`）。
- **性质**：`指标替换`（口径匹配修正）。
- **影响已上报数字**：**是**。原 §6.2 的 +4.5pp 对应"改写型 anchored"一行（+0.0169）。
- **护栏**：`test_paraphrased_sets_map_onto_global_pool`（`:1905`）。
- **合并**：`0194b8d`（直接提交在 main）。

---

### 2.4 `假设证伪`（10 项）

> 这一组的共同含义：**设计想法本身错了**。每一项都产出了论文 §7 的负面结果。

#### F-01 Ω 无额外信息量

- **触发发现**：`exp/omega`（`experiments/REPORT_exp-cascade.md`，注意该文件名
  与内容不符，见 §5.1）§0/§3–§4。ρ(Ω, n_seed) = **0.9949**；
  去掉 Ω=0 的 518 条后 AUC = **0.589**（CI 含 0.5，p=0.163）；
  Ω 门控漏掉 66 条"有触发词但通路仍空"的查询。
- **原状 → 现状**：`observability.py`（305 行）保留作为负面结论的可复现证据；
  Ω **未接入任何检索路径**，已上报数字全部未变。
- **性质**：`假设证伪`。
- **影响已上报数字**：否（新增负面结果，论文 §7）。
- **护栏**：`TestQueryObservability` 21 项，含两项**局限护栏**
  （`test_omega_zero_iff_cascade_path_would_be_empty` @`:1483`、
  `test_omega_is_not_monotone_in_trigger_count` @`:1496`）。
- **合并**：`4cbf5d6` → `9b150cb`。

#### F-02 无源项算子退化解释 H4 平局

- **触发发现**：`exp/dynamics` §2 事实 3 + §7 判定表
  （`experiments/REPORT_exp-dynamics.md:90-110`、`:349-376`）。
  两条独立证据：(a) `layers=2` 时同分量余弦仅 0.383（距 1.0 很远），
  源信息保留 0.840——退化只在 k→∞ 渐近成立；
  (b) 完美同分量指示器准确率上限 = **16/20 = 0.8000**（报告版）/ 0.8057（汇总版），
  **低于**实测 0.950。**这一条单独就足以排除退化解释。**
- **原状 → 现状**：`hgnn.py:26-28` 新增 `alpha`（源项系数，默认 1.0）与
  `leak`（阻尼 ε，默认 0.0）；`hgnn.py:152`（`propagation_matrix()`）供谱分析。
  **α=1.0, ε=0.0 与历史实现逐位相同**（`maxdiff = 0.000e+00`，4/4 组合）。
- **性质**：`假设证伪`。
- **影响已上报数字**：否，但**新增 2 项负面结果**（源项不打破平局；源项只在
  layers ≥ 50 有意义），且**加强了**"信号来自 L1 n 元共现"的结论。
- **护栏**：`TestHGNDriven` 13 项（`:1519`），含
  `test_default_is_undriven_and_unchanged`（`:1531`）、
  `test_source_term_prevents_collapse`（`:1593`）、
  `test_S_rowsum_is_exactly_one`（`:1563`）。
- **合并**：`48fc56f` → `95b958b`。

#### F-03 封顶可靠度通道让类型约束影响 P1

- **触发发现**：`exp/degrade` §4.1/§5.1（`experiments/REPORT_exp-degrade.md:188-232`、
  `:305-340`）。**P1 是句级布尔指标**（`pred = bool(edges)`），
  软可靠度通道只作用于打分/排序，**数学上界就是 0**；
  且 7/7 条字面误判句**全部**由本体正式登记的框架支撑（**0/7** 来自降级边）；
  句级判别 AUC = **0.3913**（反相关）。
- **原状 → 现状**：`provenance.py`（95 行）保留；`models.py:89` 加
  `provenance_reliability: float = 1.0`（默认值保证旧数据不受影响）；
  `extended.py:104-105` 扩展边取链上 `min(...)`（退化边不得借合并洗白）；
  `retrieval.py` 两条路径都乘折扣（`reliability_floor=1.0` 时逐位复原历史口径）。
- **性质**：`假设证伪`（**结构性不可能**，不是调参问题）。
- **影响已上报数字**：否（新增负面结果），但**揭露 C-02 覆盖率注水**。
- **护栏**：`TestProvenanceReliability` 13 项（`:2528`），含
  `test_judgement_is_registration_not_prefix`（`:2544`）、
  `test_reliability_floor_one_reproduces_history`（`:2630`）。
- **合并**：`078d099` → `1c0ed64`。

#### F-04 查询侧标量可预测检索行为

- **触发发现**：`exp/emergent`（gen3）§0.1 裁决表
  （`experiments/gen3/REPORT.md:675` 起，emergent 段）。控制集合大小后
  `n_emergent` 增量 AUC = **0.4897 [0.459, 0.509]**（生产规则）；
  层内加权 AUC = **0.4625（低于随机）**；跨 4 种级联规则全部 CI 覆盖 0.5。
  下游 per-query MRR 文档内 ρ = +0.1116（p=0.0665，不显著）。
- **原状 → 现状**：`query_signal.py`（385 行）保留作为可复现证据；
  论文 §7 新增负面结果行 + §9 收窄。
- **性质**：`假设证伪`（三代连续负面结论的收口）。
- **影响已上报数字**：否（§7 新增），但**为 §9"下一个问题"提供了明确排除项**。
- **护栏**：`TestQuerySignal` 15 项（`:2678`），含
  `test_query_signal_invariant_to_candidate_pool`（`:2695`）、
  `test_measured_signal_cannot_predict_mrr_by_construction`（`:2903`）。
- **合并**：`0216dcd` → `b6599bd`。

#### F-05 `n_emergent` 的 0.836 是真实信号

- **触发发现**：`exp/emergent`（gen3）关键证据一/二
  （`experiments/gen3/REPORT.md:756-790`）。控制集合大小后信号消失；
  **gen2 报告 0.836 时未标明它只在非默认的 `source` 规则下成立**——
  生产默认 `json` 规则下该量从一开始就只有 **0.4834**。
- **原状 → 现状**：澄清写入 `实验结论汇总.md:499-507`；
  论文 §7 负面结果表措辞为"穷举 64 种合成组合 AUC 均落在 0.50–0.93"（按规则分列）。
- **性质**：`假设证伪`（集合大小伪影）。
- **影响已上报数字**：**是**（澄清 gen2 结论的适用范围）。
- **护栏**：`test_s_query_is_not_a_proxy_for_trigger_count_alone`（`:2889`）、
  `test_clip_collapses_levels_theorem`（`:2815`，钉住 23 档→2 档塌缩）。
- **合并**：`0216dcd` → `b6599bd`。

#### F-06 更换级联构造规则能移动检索指标

- **触发发现**：`exp/cascade`（gen2）§3/§4（`experiments/gen2/REPORT.md:154-282`）。
  **全单例对照**：生产现状 / 按源域 / **全单例（最退化）** 三者 MRR
  **逐位相同 0.5025**；只有 L3 全消融（`cascade_id` 全空）才降到 **0.4681**（−0.034）。
- **原状 → 现状**：`cascade_rules.py`（298 行，7 条规则）保留为**可选**；
  `builder.py:33` 加 `orphan_cascade_rule="target"` 参数（**默认不变**）；
  **默认构造规则不改**（见 K-06）。
- **性质**：`假设证伪`（缺陷真实但**度量中性**）。
- **影响已上报数字**：否（主指标逐位不变），但**§6.3 需加附加条件**（见 K-02）。
- **护栏**：`TestCascadeConstructionRules` 17 项（`:2286`），含
  `test_production_ontology_defect_is_pinned`（`:2501`）。
- **合并**：`33601b6` → `9b150cb`。

#### F-07 `type` 是死维

- **触发发现**：`exp/typefeat`（gen3）——**证伪的是 gen1 自己的结论**。
  §1.1（`experiments/gen3/REPORT.md:33-63`）：gen1 的 0.4973 是训练集口径；
  评测口径 0.5249 [0.5092, 0.5401]（CI 不含 0.5）。
- **原状 → 现状**：裁决 `dead` → `useful（弱）+ redundant(struct)`
  （与 `struct` 二值重叠 1.000、秩相关 +0.836）。
- **性质**：`假设证伪` + `口径修正`（C-04 是它的口径侧）。
- **影响已上报数字**：**是**（推翻前两代的"死维"表述）。
- **护栏**：`test_type_auc_is_near_noise_on_training_set`（`:2163`）。
- **合并**：`77a07b0` → `c85103d`。

#### F-08 训练增益来自「训练学到了隐喻结构信号」

- **触发发现**：`exp/typefeat` §3.3/§4.3/§6.4
  （`experiments/gen3/REPORT.md:268-340`、`:388-405`、`:504-516`）。
  四条独立证据：
  1. 人工权重调对后训练增益 **+0.49pp [−0.89, +1.84]（CI 覆盖 0）**；
  2. **1 维 `sem` = 7 维训练后**（Δ=+0.0025，CI 覆盖 0）；
  3. 真实句向量下 **纯 `sem` 显著优于训练后 7 维**（+1.76pp，p=0.003）；
  4. MRR 来源分解：+6.44pp **全部**落在「产出 chunk」列，非产出列 **−0.64pp**。
- **原状 → 现状**：论文 §6.2 结论 2 改写为"训练增益主要是人工权重配错的产物"
  （`论文初稿.md:345-355`）；摘要 (6)。
- **性质**：`假设证伪`。**不否定"可训练排序器"的工程价值**（它能自动校准权重），
  否定的是"训练学到了隐喻结构信号"这个解释。
- **护栏**：`test_trained_weight_of_type_is_near_zero`（`:2179`）、
  `test_manual_weighting_float_order_matters`（`:2148`）。
- **合并**：`77a07b0` → `c85103d`。

#### F-09 特征删除/替换能提升排序

- **触发发现**：`exp/typefeat` §3.1（`experiments/gen3/REPORT.md:227-251`）。
  9 个处置（3 个去维 + 6 个替代信号）**CI 全部覆盖 0**；最大的一次 D8
  （`type`→`frame_support_norm`）Δ=+0.0082，CI [−0.0046, +0.0207]。
- **原状 → 现状**：**全部保留，只重标定权重**（见 K-03/K-04）。
- **性质**：`假设证伪`（"不显著"≠"为零"，但**没有证据支持删除**）。
- **影响已上报数字**：否。
- **护栏**：`test_same_cascade_can_be_redundant_with_same_frame`（`:2229`）、
  `test_struct_saturates_at_one`（`:2194`）。
- **合并**：`77a07b0` → `c85103d`。

#### F-10 A7/H5「+9.5pp 翻转」的归因

- **触发发现**：`exp/typefeat` §5（`experiments/gen3/REPORT.md:406-436`）。
  实测：人工侧把 `type` 权重置 0 的收益 = **+9.18pp**；
  训练侧去 `type` 的效应 = **+0.00pp**（逐条排序 32.5% 不同但 MRR 差恰为 0.0000）。
  真实增量 **+0.29pp**，而非 +9.5pp。
- **原状 → 现状**：论文 §7 A7 行改为「条件化（§6.2）」；
  `evaluate_fullcorpus` 的 A7/A9 结论加池饱和警告（C-06）。
- **性质**：`假设证伪`（翻转是真的，**归因是错的**）。
- **影响已上报数字**：**是**（gen1 曾标记为"需人工复核的重大结论变更"，
  gen3 复核后否决了该变更）。
- **护栏**：**无**（这是 fullcorpus 表上的结论，无对应单测）。
- **合并**：`77a07b0` → `c85103d`。

---

### 2.5 `组件处置`（6 项）

> 依据：`experiments/组件处置决策.md`（提交 `1311949`）。
> **核心原则：删除是安全的，但没有收益。** 处置标准因此不是"能否提升指标"
> （证据显示不能），而是"是否减少认知负担与维护成本而不损失能力"。

#### K-01 HGNN 从检索路径移除（从未被调用）

- **触发发现**：**代码审计（决定性）**：检索评分路径
  `_pair_features` → `extract_features(qe, mapping, self._centrality)`，
  其中 `centrality = 0.5·len(ground) + 0.5·[cascade_id 非空]`（`retrieval.py:73`）
  ——**完全不依赖 HGNN**。全仓 hgnn 的引用只有三处：`__init__.py`（导出）、
  `evaluate_hgnn.py`（评测）、`evaluate_chain_quality.py`（可选 coherence 过滤，
  默认关闭）。证据：`experiments/组件处置决策.md:23-54`。
- **原状 → 现状**：**保留 `hgnn.py`**（它是 `metaphor_coherence` 的实现载体，
  §6.3 结论需要它作对照），但**文档与论文中不再暗示 HGNN 是检索架构的一部分**。
  **无需改动代码**（因为从未被调用）。
- **性质**：`组件处置`。这解释了 flat ≡ HGNN 的**真正原因**——
  不是"层级无信息"，而是**该层根本不在打分路径上**。
- **影响已上报数字**：否（本来就不在路径上），但**改变了 §6.3 的解释**。
- **护栏**：**无**（"从未被调用"是代码审计结论，不是可测断言；
  若有人把 HGNN 接进打分路径，没有测试会报警）。
- **合并**：`1311949`（文档）已在 main。

#### K-02 L3 级联层保留但降级定位

- **触发发现**：全单例对照（见 F-06）。
- **原状 → 现状**：论文 §6.3 由「层级（L2/L3）的价值应表述为**检索组织与
  可解释性**」→ 加附加条件：「当前构造下该层**对检索指标零结构贡献**……
  唯一因果通道是 `cascade_id` 非空这一布尔位」（`论文初稿.md:388-396`）。
- **性质**：`组件处置`（保留但降级）。
- **影响已上报数字**：**是**（§6.3 主张加条件；§9 结论）。
- **护栏**：`test_production_ontology_defect_is_pinned`（`:2501`）——把
  "生产本体级联仍是单目标域主导"钉住，若未来修好本体该测试会失败并提示
  同步更新论文 §6.3。
- **合并**：`1311949` + `da5971f`。

#### K-03 `type` 特征保留

- **触发发现**：F-07（非死维但弱）+ F-09（删除 CI 覆盖 0）。
- **原状 → 现状**：保留，权重降至 `training.py:76` 的 0.0168（原 0.20）。
  论文表述（`论文修正建议.md` 修正 11）：「不是死维，而是**弱维且与 `struct` 共线**……
  保留但不应赋予高权重」。
- **性质**：`组件处置`。
- **影响已上报数字**：否。
- **护栏**：`TestTypeReliability` 8 项 + `test_type_feature_is_not_constant_on_mixed_pool`（`:2048`）。
- **合并**：`1311949`。

#### K-04 `same_cascade` 保留

- **触发发现**：`exp/cascade` 实测：当前构造下 `same_cascade` 有 **51.7%**
  与 `same_frame` 重复（全单例时 100% 重复，即完全冗余）。
  证据：`experiments/组件处置决策.md:95`、`论文修正建议.md` 修正 8。
- **原状 → 现状**：保留（删除 ΔMRR CI 覆盖 0，无收益；且它在 `cascade_id`
  非空时才有值，移除会改变特征维度、破坏历史对照）。
- **性质**：`组件处置`。
- **影响已上报数字**：否（§6.2 加机制注脚）。
- **护栏**：`test_same_cascade_can_be_redundant_with_same_frame`（`:2229`）。
- **合并**：`1311949`。

#### K-05 人工权重重标定

- **触发发现**：`exp/typefeat` §3.2（见 R-03）。
- **原状 → 现状**：`HAND_WEIGHTS` 改为按学到比例（`training.py:76`），
  同时**保留 `HAND_WEIGHTS_LEGACY`** 使历史口径仍可重放（`training.py:62`）。
  重标定后权重（`组件处置决策.md:89-97`）：
  `sem` 0.2382 / `clue` 0.4323 / `ground_jaccard` 0.1711 / `same_frame` 0.0673 /
  `same_cascade` 0.0675 / `type` 0.0168 / `struct` 0.0067。
- **性质**：`组件处置` + `缺陷修复`（R-03 是缺陷侧）。
- **影响已上报数字**：**是**（anchored Δ +0.0565 / +0.054）。
- **护栏**：`test_legacy_weights_reproducible`（`:1854`）。
- **合并**：`012a00e` → `fd2a991`。

#### K-06 级联默认构造规则不改

- **触发发现**：F-06（度量中性）+ 稳定 ID 代价。
- **原状 → 现状**：保持 `target` 规则。理由：改规则会重写 **733 个稳定 ID**
  （缓存键、导出、Neo4j、双语对齐），而无指标收益。若需运行时组织力，
  可用 `orphan_cascade_rule="source_type"`——一行、零风险、不动本体、
  覆盖率保持 1.000，ad-hoc 级联从 size≡1 变为中位 2 / 最大 6。
- **性质**：`组件处置`。
- **影响已上报数字**：否（保持默认即保持数字）。
- **护栏**：`test_builder_default_orphan_rule_is_target`（`:2417`，防静默改默认）。
- **合并**：`33601b6` → `9b150cb`。

---

### 2.6 `基准重建`（2 项）

#### B-01 全局候选池 1,100

- **触发发现**：`exp/typefeat` §4.1 缺陷 1（池 ≤10 使 Hits@10 平凡饱和）。
- **原状 → 现状**：`evaluate_repaired.py`（510 行）把 110 个伪文档合并为
  **一张全局图**，候选池 = **1,100 个 chunk**。
  | 指标 | 原基准（池=7） | 修复后（池=1,100） |
  |---|---|---|
  | 随机排序 MRR 期望 | ≈0.3704 | **0.0069** |
  | 随机 Hits@10 | 1.0000（平凡饱和） | 0.0091 |
  | MRR 可用量程 | 0.63 | **0.99** |
- **性质**：`基准重建`。
- **影响已上报数字**：**是**（§4.2 新增、§6.1/§6.2/§6.7 全部检索数字）。
- **护栏**：`test_random_baseline_improves_with_pool`（`:1833`）。
- **合并**：`245c860` → `fd2a991`。

#### B-02 去锚定口径（deanchor）

- **触发发现**：C-05（100% 锚定）。
- **原状 → 现状**：`deanchor` 口径把**产出 chunk 从候选池中移除**，
  金标改为「同框架/同级联的**其它** chunk」。可构造 deanchor 查询 **385/634**；
  金标规模 min=1 / median=3 / max=37（比 anchored 的恒为 1 更真实）。
- **性质**：`基准重建`。
- **影响已上报数字**：**是**。锚定抬高 **≈+0.66 MRR**（0.8956 vs 0.2330），
  即原基准约 **74%** 的数字来自"把已知答案排到前面"；
  但 deanchor MRR 0.2330 = 随机的 **34 倍** → **架构确有真实跨域检索能力**。
- **护栏**：`test_paraphrased_sets_map_onto_global_pool`（`:1905`）。
- **合并**：`245c860` → `fd2a991`。

---

### 2.7 `公平性修正`（3 项）

#### A-01 A6 两臂预算不对等（`top_k=5` vs 无上限）

- **触发发现**：`experiments/A6预算对等修正.md`（提交 `b21b5e6`）。
  常识通路**无上限**（全池扫描），隐喻通路硬编码 `top_k=5`。
  实测同一查询集（n=652）：`top_k=5` → Recall@10 **0.8287**；
  `top_k=20` → **1.0000**（与无上限等价）。**原数字低估隐喻通路约 17pp。**
- **原状 → 现状**：`evaluate_a6.py:136` 新增 `--meta-top-k`（**默认 20**），
  `:222` 传入；注释留痕 `:216-220`。保留 `--meta-top-k 5` 可复现旧口径。
  论文 §6.4 加两处口径修正段（`论文初稿.md:407-416`）。
- **性质**：`公平性修正`。
- **影响已上报数字**：**是**。A6 隐喻通路 0.783/0.829 → **1.000**；
  两臂差距从 8.2× 扩大到 **10.5×**（**结论反而加强**）。
- **⚠️ 未同步（本审计发现）**：论文 §7 表（`论文初稿.md:550`）与
  `论文初稿_en.md:382` 仍写「常识通路 0.095 vs 隐喻通路 **0.783**（n=652）」，
  与同文档 §6.4 的 1.000 不一致。见 §5.1。
- **护栏**：`test_no_hardcoded_budget_in_comparisons`（`:1923`）、
  `test_a6_metaphor_arm_has_adjustable_budget`（`:1942`）。
- **合并**：`b21b5e6`（直接提交在 main）。

#### A-02 公平性未系统检查（三处同类缺陷）

- **触发发现**：逐节复核后发现**三处同类缺陷**，分别在**不同脚本、不同抽象层**
  （基准构造 / 权重定义 / 函数调用），且每一处单看都"合理"——
  只有把"两臂是否对等"作为**统一检查项**才会暴露。
  证据：`experiments/三臂对等审计.md`（提交 `dfa98a0`）。
- **原状 → 现状**：新增机器检查 `metaphor_graph/audit_fairness.py`：
  剥离注释后扫描各评测脚本的预算类参数，报告硬编码调用与可调参数。
  实测输出「未发现硬编码的预算调用」。论文新增 §4.1「比较公平性声明」
  （`论文初稿.md:193-208`），明确三条规则。
- **性质**：`公平性修正`（从人工审查改为机器检查）。
- **影响已上报数字**：**是**（新增 §4.1，三处缺陷的汇总入口）。
- **护栏**：`test_no_hardcoded_budget_in_comparisons`（`:1923`）+
  `test_a6_metaphor_arm_has_adjustable_budget`（`:1942`）。
- **合并**：`dfa98a0`（直接提交在 main）。

#### A-03 `audit_fairness` 首版未剥离注释 → 误报

- **触发发现**：工具首版把 A6 修复注释里的"原实现用 top_k=5"**误报为硬编码**。
  证据：`experiments/三臂对等审计.md:56-58`（"工具本身也踩过一次坑"）。
- **原状 → 现状**：加注释剥离；教训保留在 `audit_fairness.py` docstring 中。
- **性质**：`公平性修正`（工具自身的修正）。
- **影响已上报数字**：否。
- **护栏**：工具 docstring 留痕（**无单测**）。
- **合并**：`dfa98a0`。

---

## 3. 机械提取 19 行 vs 本目录 49 项

`docs/inventory/_extracted.json` 的 `refactor` 段逐项映射：

| # | 提取项 | 归属 | 备注 |
|---|---|---|---|
| 1 | `context_budget.py:102` | **未单列** | 低密度不设上限——**策略说明，非重构**；首提交即如此，无"原状"可言 |
| 2 | `evaluate_a6.py:145` | R-06 | ✅ |
| 3 | `evaluate_a6.py:216` | A-01 | ✅ |
| 4 | `evaluate_retrieval.py:226` | R-03/K-05 | ✅ |
| 5 | `evaluate_retrieval.py:227` | R-03 | 与 #4 同属一条注释 |
| 6 | `extractor.py:187` | R-11 | ✅ |
| 7 | `llm_ontology.py:207` | R-10 | ✅ |
| 8 | `mipvu.py:92` | R-01 | ✅ |
| 9 | `mipvu.py:94` | R-01 | 与 #8 同属一条注释 |
| 10 | `ontology.py:25` | R-10 | 与 #7 同源（同一修复的另一处注释） |
| 11 | `ontology.py:114` | R-02 | ✅ |
| 12 | `ontology.py:123` | R-02 | 与 #11 同属一条注释 |
| 13 | `retrieval.py:293` | R-04 | ✅ |
| 14 | `retrieval.py:295` | R-04 | 与 #13 同属一条注释 |
| 15 | `retrieval.py:302` | R-04/K-05 | 与 #13 同属一条注释 |
| 16 | `retrieval.py:307` | R-02 | ✅ |
| 17 | `retrieval.py:308` | R-02 | 与 #16 同属一条注释 |
| 18 | `training.py:52` | R-03/K-05 | ✅ |
| 19 | `training.py:128` | R-02 | ✅ |

**去重后 19 行 → 13 条注释 → 8 条独立修正**
（R-01、R-02、R-03/K-05、R-04、R-06、R-10、R-11、A-01），
另有 1 行（`context_budget.py:102`）是策略说明而非重构。
本目录 49 项中，机械提取只覆盖 8 项，**41 项（84%）无任何代码注释**——
全部来自 git 提交消息、分支报告与更正文档。典型漏报：
- 三处合并回归（R-07/R-08/R-09）——提交在 main 上，无代码注释；
- 全部 10 项假设证伪——产出在实验脚本与报告，不在生产代码；
- 全部 3 项指标替换、2 项基准重建、3 项公平性修正；
- 5 项编排者自身错误。

**blame 交叉验证**（`git blame -L <line>,<line>`，原始输出见 §4.1）：
19 行按提交归属为 —— `afa39ae` **5 行**（首提交，main 基线自带：
`context_budget.py:102`、`evaluate_a6.py:145`、`extractor.py:187`、
`llm_ontology.py:207`、`ontology.py:25`）、`012a00e` **6 行**（R-03/R-04 系列）、
`64872c4` **3 行**（R-02 系列）、`33601b6` **2 行**（R-01）、
`8bc5fed` **2 行**（R-02 合并时补写 `retrieval.py:307-308`）、
`b21b5e6` **1 行**（A-01）。合计 19。✅

---

## 4. Git 命令与原始输出

### 4.1 使用的命令

```bash
# 分支合并状态（权威判定）
for b in exp/source exp/cascade exp/dynamics exp/degrade \
         exp/typefeat exp/emergent exp/repair exp/omega; do
  git merge-base --is-ancestor $b main && echo "$b MERGED" || echo "$b NOT merged"
done
# → 八个分支全部 MERGED

git log --oneline --all --not main
# → 空输出（不存在任何未入 main 的提交）

# 逐分支差异（双重检查）
for b in exp/...; do
  echo "=== main..$b ==="; git log --oneline main..$b
  echo "=== $b..main ==="; git log --oneline $b..main | head -30
done
# → 所有 main..exp/* 为空；所有 exp/*..main 为 main 的历史

# 关键修复提交的所属分支
git branch --contains 33601b6   # → + exp/cascade + exp/emergent * main
git branch --contains 64872c4   # → + exp/source + exp/typefeat * main
git branch --contains 078d099   # → + exp/degrade * main
git branch --contains 48fc56f   # → + exp/dynamics * main
git branch --contains 4cbf5d6   # → + exp/cascade + exp/emergent + exp/omega * main
git branch --contains 77a07b0   # → + exp/typefeat * main
git branch --contains 0216dcd   # → + exp/emergent * main
git branch --contains 15c66d7   # → + exp/repair * main
git branch --contains db29ac8   # → * main
git branch --contains cb8d81d   # → * main
git branch --contains 3ac9f2a   # → * main
git branch --contains b21b5e6   # → * main
git branch --contains dfa98a0   # → * main

# 注释行的归属（19 项机械提取的 blame 交叉验证）
for spec in "context_budget.py 102" "evaluate_a6.py 145" "evaluate_a6.py 216" \
            "evaluate_retrieval.py 226" "evaluate_retrieval.py 227" \
            "extractor.py 187" "llm_ontology.py 207" "mipvu.py 92" "mipvu.py 94" \
            "ontology.py 25" "ontology.py 114" "ontology.py 123" \
            "retrieval.py 293" "retrieval.py 295" "retrieval.py 302" \
            "retrieval.py 307" "retrieval.py 308" "training.py 52" \
            "training.py 128" "evaluate_real.py 50" "health.py 168"; do
  set -- $spec
  echo "$1:$2 -> $(git blame -L $2,$2 --date=short metaphor_graph/$1 | head -1 | awk '{print $1}')"
done

# 提交消息全文（含冲突解决记录、测试计数、影响说明）
git show -s --format="%s%n%b" <sha>      # 用于 8bc5fed 9b150cb 95b958b 1c0ed64
                                          # c85103d b6599bd fd2a991 db29ac8
                                          # cb8d81d 3ac9f2a b21b5e6 dfa98a0
                                          # 319338c 295cbe2 d6d53b6 553925a
                                          # 087afe8 d233e9a 0194b8d e014e37
                                          # da5971f 288cb2f 43426a0

# 全仓冲突标记扫描
grep -rn "^<<<<<<< \|^>>>>>>> " --include="*.md" --include="*.py" \
     --include="*.json" --include="*.txt" . | grep -v "^./.git/"
# → experiments/gen3/REPORT.md:1 和 :1274（已提交状态）

# worktree 清单与脏状态
git worktree list
for w in cascade degrade dynamics emergent omega repair source typefeat; do
  git -C ".wt/$w" status --porcelain | wc -l
done
# → 仅 .wt/repair 有 2 个未跟踪文件（experiments/fullcorpus_after_repair.log、
#   experiments/repaired_real.log），其余全部干净；主仓工作区干净

# 推送状态
git rev-list --left-right --count origin/main...main   # → 0  1
git log --oneline origin/main..main                    # → c0b74fa（未推送）
```

### 4.2 复核命令

```bash
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"

# 测试套件（228 项）
$PY -m unittest metaphor_graph.test_metaphor_graph
# → Ran 228 tests in 11.900s / OK

# 公平性审计工具
$PY -m metaphor_graph.audit_fairness
# → 未发现硬编码的预算调用。

# 诚实覆盖率复现（120 句子集）
$PY -c "
import sys; sys.path.insert(0,'.')
import logging; logging.disable(logging.CRITICAL)
from metaphor_graph.data_loader import load_ccl2018
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology, build_replay_backend
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.extractor import MetaphorExtractor
from metaphor_graph.health import graph_health
ont,_ = build_replay_ontology(); samples = load_ccl2018()
texts=[s.text for s in samples[:120]]; pre=build_replay_backend(ont)
ex=MetaphorExtractor(ontology=ont,use_semfield=True,llm_backend=pre,llm_conf_threshold=0.85)
shg=MetaphorSHGBuilder(ontology=ont,extractor=ex,llm_backend=pre).build(texts,doc_id='sub120')
h=graph_health(shg,ontology=ont)
print(len(shg.edges), h.hierarchy_coverage, h.registered_frame_coverage, h.n_fallback_edges)
"
# → 108 1.0 0.8241 19   （即论文的 82.4%）

# 本体 source_type 分布（R-10 的 98.6% → 32.8%）
$PY -c "
import json,collections
d=json.load(open('metaphor_graph/ontology_default.json',encoding='utf-8'))
st=collections.Counter(f.get('source_type') for f in d)
tot=sum(st.values())
print(tot, st.most_common(4), st['GENERIC_VEHICLE']/tot)
"
# → 2177 [('GENERIC_VEHICLE', 793), ('NATURAL_PHENOMENON', 358), ...] 0.3643
```

---

## 5. 尚未合并入 main 的修正

### 5.1 代码级：**空**

```
git log --oneline --all --not main   →  （无输出）
git merge-base --is-ancestor exp/<name> main  →  八个分支全部返回 0
```

**八个实验分支（含 `exp/omega`）的代码改动全部已在 main 上。**
用户提示的"分支修复从未合并"这一历史问题**已被解决**：
`experiments/实验结论汇总.md:667-703` 记录了合并过程，commit `553925a` 是登记提交。

### 5.2 文档级：**5 项遗留**（本审计发现）

> 这些不影响代码，但会让读者读到互相矛盾的结论。

| # | 遗留 | 位置 | 问题 |
|---|---|---|---|
| D-1 | **A6 隐喻通路 0.783 未同步为 1.000** | `论文初稿.md:550`（§7 表）、`论文初稿_en.md:382`、`README.md:30`、`效果对比.md:105` | 同一文档 §6.4 已写 1.000（预算修正后），§7 表仍写 0.783，**同一篇论文内自相矛盾**。摘要 (3) 已改为"1.000（预算修正后）"。 |
| D-2 | **诚实覆盖率 82.4% vs 77.6% 未标样本量** | 82.4%：`论文初稿.md:275,280,283`、`README.md:26`、`DATA.md:123`、`论文初稿_en.md:180,451`、`组件处置决策.md:71`；77.6%：`REPORT_exp-degrade.md:17,161,169,348`、`实验结论汇总.md:17,155,163,165,444,719`、`论文修正建议.md:21,29,32` | 实测两者都对：**82.4% = 120 句子集（19/108 回退边）；77.6% = 1,100 句全量集（198/883）**。论文写了"120 句子集"故数值自洽；`experiments/` 三份文档报 77.6% 未标 n，读者会认为矛盾。 |
| D-3 | **`experiments/gen3/REPORT.md` 含已提交的冲突标记** | `experiments/gen3/REPORT.md:1`（`<<<<<<< HEAD`）、`:634`（`=======`）、`:1274`（`>>>>>>> exp/emergent`） | 该文件是两个分支报告的**未合并拼接**：`:2`–`:633` 是 typefeat 报告，`:635`–`:1273` 是 emergent 报告，两侧被冲突标记夹住。提交 `b6599bd` 引入。**这是 R-09 同类缺陷的漏网之鱼**（`test_all_eval_modules_importable` 只检查 `.py`，不检查 `.md`）。 |
| D-4 | **报告索引指向不存在的文件** | `experiments/REPORT.md:9` 引用 `REPORT_exp-typefeat.md`，但该文件不存在 | 另有两份报告命名与内容不符：`experiments/REPORT_exp-cascade.md` 的**内容是 Ω/omega 报告**（首行「Ω 查询侧可观测泛函」），`.wt/cascade/experiments/REPORT.md` 同样内容是 Ω 报告。cascade 自己的报告在 `experiments/gen2/REPORT.md`。emergent 报告无独立文件（在 `experiments/gen3/REPORT.md` 后半）。 |
| D-5 | **`实验结论汇总.md:663` 的测试计数过时** | `实验结论汇总.md:663` 写「**124 项全绿**（224 项：116 基线 + …）」，同文件 `:801` 写「126 项单测」，实际为 **228 项** | 括号内 224 是当时正确值；现为 228。`README.md`/`DATA.md` 已更新为 224，仍非 228。 |

**另两项状态**（非修正，供完整性）：

- **未推送**：`main` 比 `origin/main` 领先 1 个提交
  （`c0b74fa`，即清单提取工具本身）——`git rev-list --left-right --count
  origin/main...main` → `0  1`。
- **worktree 脏状态**：仅 `.wt/repair` 有 2 个未跟踪日志
  （`experiments/fullcorpus_after_repair.log`、`experiments/repaired_real.log`）；
  其余 7 个 worktree 与主仓工作区全部干净。
  `repaired_full.log` / `repaired_3arm.log` 已在 main，另两个未入
  （它们只是 `evaluate_repaired_real.py` 的运行日志，不影响可复现性）。

---

## 6. 无护栏的修正

> 判定标准：`metaphor_graph/test_metaphor_graph.py` 中**没有**任何测试会在该修正
> 被回退/被违反时失败。

| 编号 | 修正 | 为什么无护栏 | 风险 |
|---|---|---|---|
| R-05 | `evaluate_real` 静默回落告警 | 告警是 `print`，无法断言"必须存在"；同类防护 `test_injected_error_propagates_no_silent_fallback`（`:1088`）只覆盖 embedder | **高**：README 称其为"本项目最危险的静默陷阱"；告警可被后人删除而无测试拦截 |
| R-06 | `evaluate_a6` 文档键对齐（n=0） | 无测试覆盖 A6 的缓存键 | 中：键再次错位会静默得到 n=0 |
| R-10 | `llm_ontology` 的 `source_type` 推断 | 无测试断言 `GENERIC_VEHICLE` 占比；`infer_source_type` 本身也无单测 | 中：回退到"一律 GENERIC"会使类型约束静默恒真 |
| R-11 | `extractor` 的 `skip_refine` | 无测试覆盖该分支 | 低：最坏是多花 API + 可能误否 |
| C-06 | A7/A9 池饱和警告 | 纯文档修正 | 低 |
| C-07 | `ground_jaccard` 定义差异（标注未改） | 有意不改，故无护栏 | 低（已知） |
| C-08 | `sem` 的 clamp 不一致（标注未改） | 同上 | **中**：换真实句向量/负余弦时会触发 |
| F-10 | A7/H5 归因修正（+9.5pp → +0.29pp） | 无 fullcorpus 表的单测 | 中：该结论易被误引用 |
| K-01 | HGNN 不在打分路径 | "从未被调用"是审计结论，不可测 | **高**：若有人把 HGNN 接进 `_pair_features`，flat≡HGNN 的结论立刻失效而无测试报警 |
| A-03 | `audit_fairness` 首版误报 | 教训只在 docstring | 低 |
| D-3 | `gen3/REPORT.md` 冲突标记 | 护栏只扫 `.py`（`test_all_eval_modules_importable`） | 低（文档级），但**说明护栏有盲区** |

（表中前 10 行属 §1 汇总表的 49 项；最后一行 D-3 是 §5.2 的文档级遗留。）

**已有护栏的修正**（10 项无护栏之外，其余 39 项均有对应测试）：
主要护栏类为 `TestTypeReliability`(8)、`TestProvenanceReliability`(13)、
`TestCascadeConstructionRules`(17)、`TestQuerySignal`(15)、`TestQueryObservability`(21)、
`TestHGNDriven`(13)、`TestRepairs`(16)、`TestFeatureSetAudit`(8)、
`TestManualWeightedTypeConsistency`(1)。

---

## 7. 编排者自身的错误与更正

> 用户特别要求单列。这些错误的共同模式是：**编排者据"表达式不同/机制看似被替换/
> 某规则下的区间"直接推断结论，而未先确认被推断的对象是否真在生效路径上。**
> 项目已把教训写入 `experiments/README.md` 的演化规则 4/5。

### O-01 代写草稿把 `json` 规则的区间外推为四条规则的结论

- **错误**：`exp/emergent` 的 agent 完成实验后撰写阶段中断（最后输出距今 12 小时），
  主控据此**代为整理报告**（commit `702d7ca` 中的版本）。草稿称
  「全部 64 个组合的 AUC 子集都落在 **0.50–0.62** 区间」。
- **实测**：`json` 是 [0.5000, 0.6188]（草稿只对了这一条规则）；
  **`source` 是 [0.5000, 0.8483]**、`metanet` [0.5000, 0.8040]、
  `source_type` [0.5000, **0.9290**]。
- **更正**：agent 恢复后指出该错误；主控逐条复核确认。
  证据：`.wt/emergent/experiments/gen3/REPORT.md:41-52`（§0.3）、
  `experiments/实验结论汇总.md:509-529`、commit `9c762a7`（"更正：exp/emergent
  最终版指出主控代写草稿的两处错误"）。
- **为什么重要**：**正因为 `source` 下能到 0.848，才暴露出元凶在"分量定义层"
  而非"合成层"** —— 草稿的错误区间恰好掩盖了真机制。
- **教训（已入演化规则 5）**：「不可把'某规则下的区间'外推为'所有规则的区间'」。
- **合并**：`9c762a7` + `0216dcd` 均在 main。

### O-02 代写草稿把 ε 下界当作坍缩来源

- **错误**：同一份草稿称「根因是 Ω_N 结构性恒空叠加 **ε 下界替换**（90.5% 查询）」。
- **实测**：ε 下界恒等式在 `source` 上 **20/20 = 1.0000** 成立，
  即 ε 下界**完全按设计工作**——它只把 0/1 台阶变成 ε^(1/3) 台阶，
  信息量同为 1 bit，**不是坍缩来源**。真元凶是 `Ω_N = min(1, n_emergent/n_seed)`
  内部的截断：`n_seed=1` 层（n=102）里 `n_emergent` 的 **23 档取值塌成 2 档**，
  82 条顶到上限 1.0；仅去掉这一处 `min(1,·)`（其余逐字不变），
  AUC **0.6539 → 0.8243**。
- **更正**：同上，`9c762a7` + `0216dcd`。
- **教训（已入演化规则 5）**：「'某机制看似被替换'不等于'该机制是失效原因'，
  需有逐项开关对照才能归因」。
- **合并**：`0216dcd`。

### O-03 因果链错误：§6.2 的 +4.5pp 被 `type` 口径污染

- **错误**：主控依据「`training.py:81` 与 `retrieval.py:250` 两处表达式不同」
  直接推断「已上报的 §6.2 数字被口径差污染」，并据此写了论文修正建议 4。
- **实测**：**§6.2 的 "manual weighting" 根本不调用 `metaphor_retriever_score`。**
  它走 `evaluate_retrieval.score_conditions`，用**共享的 7 维特征**；
  该候选池中 `type` **恒为 1.0**（7437/7437，已独立复核）——是**死维**，被偏置吸收。
  §6.2 两侧 `type` 都是 1.0，**从未受口径差影响**。
  修复后增益反而**增大**（+4.5pp → +6.4pp）。
- **更正**：`exp/source` 报告 §0/§1.4/§8 逐条更正；
  `experiments/REPORT_exp-source.md:570-582`（自我更正记录）留痕。
- **教训（写入汇总 §0）**：「我依据『两处表达式不同』直接推断『已上报数字被污染』，
  未先确认**被上报的那条路径实际调用的是哪段代码**。」
- **副作用（正面）**：虽然因果链错了，但**bug 是真的**（R-02），
  且发现 A6 曾静默低估 1.8pp（唯一真正调用该表达式已上报指标）。
- **合并**：`64872c4`。

### O-04 推断错误：级联的 0.836 可迁移到生产默认规则

- **错误**：`exp/cascade`（gen2）报告 `n_emergent` 的条件 AUC **0.836
  [0.759, 0.909]**，主控据此在 gen3 假设中认为"该信号值得跟进"，
  并把它写入了 `实验结论汇总.md` 的"找到的新信号（值得跟进）"。
- **实测**：gen2 报告 0.836 时**未标明它只在非默认的 `source` 规则下成立**；
  生产默认 `json` 规则下该量从一开始就只有 **0.4834** [0.435, 0.531]。
  控制集合大小后增量 AUC = 0.4897 [0.459, 0.509]，层内加权 AUC = **0.4625**（低于随机）。
- **更正**：`exp/emergent` §关键证据二；`实验结论汇总.md:499-507` 明确写
  「这是对第二代结论的必要澄清」。
- **教训**：**报告一个数字时必须同时标明它成立的条件（规则/口径/子集）**。
- **合并**：`702d7ca` → `0216dcd` → `b6599bd`。

### O-05 推断错误：算子退化解释 H4 平局

- **错误**：主控提出的假设「`M=½(I+S)` 无源项 → 迭代收敛到连通分量平稳分布
  → `metaphor_coherence` 退化为同分量指示器 → 这解释了 GRU 与 HGNN 打平」。
  该假设源于 500 轮收敛值的测量（分量内余弦 1.000000）。
- **实测**：**H4 实际工作在 `layers=2`，同分量余弦仅 0.383**，
  源信息保留 0.840 —— "退化"是 `k→∞` 的渐近命题，两者不在同一 regime。
  决定性证据：完美同分量指示器的准确率上限只有 **0.80**，**低于** H4 实测的 0.950。
- **更正**：`exp/dynamics` §2 事实 3；`experiments/README.md` 称其为
  "**第一代最重要的自我纠错**"；汇总 §exp/dynamics。
- **附带**：主控在 `_common.py` 的分析脚本中**第一版只覆盖实体节点**，
  涉及框架/级联节点的节点对静默取 0.0，把"分量内离散度"污染成虚高值；
  且 Spearman 未做分量内中心化，把"分量间差异"误读成"分量内梯度"
  （修正后 ρ 从 −0.85 变为 −0.78）。证据：
  `experiments/REPORT_exp-dynamics.md:335-345`（§6.4 一个分析陷阱）。
- **合并**：`48fc56f` → `95b958b`。

### 7.1 编排者错误的模式总结

| 错误 | 推断依据 | 实际需要确认的 |
|---|---|---|
| O-01 | 某规则下的区间 | 该区间是否跨规则成立 |
| O-02 | 某机制看似被替换 | 该机制是否真是失效原因（需逐项开关对照） |
| O-03 | 两处表达式不同 | **被上报的路径实际调用哪段代码** |
| O-04 | 一个 AUC 数字 | 该数字成立的条件（规则/子集） |
| O-05 | 渐近性质 | **实际工作点在哪个 regime** |

**共同点：全部是"未先确认适用条件就外推"。** 项目已把三条写入
`experiments/README.md` 演化规则 4/5（主控必须独立复核子方向结论；
代写结论的边界），并记录了"三代据此发现三处需要修正的推断"。

### 7.2 子方向 agent 自身的更正（同样留痕）

| 分支 | 错误 | 更正 |
|---|---|---|
| `exp/source` | 初稿称"A6 的 buggy 与 fixed top-5 不变，因为两者对未注册边都是同一常量" | **错**：buggy 给 0.0、fixed 给 0.5，未注册边整体 +0.1 分会改变组间相对排序。实测 top-5 有 **19/652 = 2.9%** 不同。指标不变的原因是"只看 chunk 并集命中"，不是"排序不变"。`REPORT_exp-source.md:578-582` |
| `exp/source` | `check_embed_cache_coverage.py` 前两版把"查询原文"全部计入待嵌入集合，得出 14 条未命中的错误结论 | 修正为精确复刻 `_pair_features` 的调用条件（**仅当查询侧无超边命中时才嵌入查询原文**）→ 命中率 **100.00%**（1348/1348）。`REPORT_exp-source.md:584-587` |
| `exp/typefeat` | 初版把 gen1 的 0.4973 当成"评测 AUC"，据此得出"`type` 是死维" | `feature_auc(ds)` 的 `ds` 是**自监督训练集**；评测口径 0.5249。裁决 `dead` → `useful（弱）+redundant(struct)`。`gen3/REPORT.md:611-614` |
| `exp/typefeat` | 初版人工加权用 numpy 点积 `F @ w`，与已上报数字差 0.0003 | `score_conditions` 是**逐项顺序累加**，浮点结合序不同，632 条查询里 1 条完整排序不同。改用顺序累加后逐位一致。护栏 `test_manual_weighting_float_order_matters`。`gen3/REPORT.md:616-620` |
| `exp/typefeat` | 初版新测试在模块级 import `evaluate_retrieval` 拿 `ROLE_IDX`，导致 5 个用例失败（该模块**模块级** `logging.disable(CRITICAL)` 全局静音） | 改为延迟 import + 保存/恢复全局日志级别。`gen3/REPORT.md:621-625` |
| `exp/typefeat` | 初版把 `struct` 与 `type` 的重叠写成"近乎完全共线"，构造断言 `fa[1] > fb[1]` 失败 | 实测 `struct` 在喻底 ≥1 且级联非空时**饱和到恰好 1.0**（85.1% 候选对）。测试改为断言饱和行为本身（`test_struct_saturates_at_one`）——**饱和是审计发现，不是测试的麻烦**。`gen3/REPORT.md:626-630` |
| `exp/typefeat` | 初版把 D8（+0.82pp，9 个处置中最大）写成"候选的最佳替代" | 加注：多重比较下的选择偏差，CI 下界 −0.46pp，**不应上报为增益**。`gen3/REPORT.md:631-633` |
| `exp/omega` | `probe_provenance.py` 的判据是错的（按 `F_LLM_` 前缀判定） | 被 `probe_provenance2.py` 取代，保留作反面教材，日志勿引用。`REPORT_exp-degrade.md:417-418` |
| `exp/dynamics` | `_common.py` 的 `coherence_lookup` 第一版只覆盖实体节点 | 涉及框架/级联节点的节点对静默取 0.0，污染成虚高值；Spearman 需分量内中心化。`REPORT_exp-dynamics.md:335-345` |
| 主控（工具） | `audit_fairness` 首版未剥离注释，误报 A6 修复注释 | 加注释剥离。`三臂对等审计.md:56-58`（A-03） |
| 主控（评审） | 文献检索的"可借用查询来源"判断有误（认为 MiQA/ANALOGICAL 可作检索查询源） | 核实后**不适用**：MiQA 是二选一推理任务、ANALOGICAL 是长文本类比评测，**都不是检索基准**。`实验结论汇总.md:784-791` |

---

## 8. 附：`docs/inventory/_extracted.json` 的其它段

机械提取共 169 项：**通路 77 / 准则 17 / 重构 19 / 新概念 56**（`inventory.py`，
提交 `c0b74fa`）。本文件只覆盖 `refactor` 段（19 项）并补出其漏报的 28 项。
`pathway`(77) / `criterion`(17) / `concept`(56) 三段不在本次任务范围内。
