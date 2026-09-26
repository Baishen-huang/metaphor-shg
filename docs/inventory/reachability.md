# 静态可达性审计报告（metaphor_graph）

**工具**：`metaphor_graph/audit_reachability.py`（AST 静态分析，离线，退出码 0）
**生成命令**：`python -m metaphor_graph.audit_reachability`（机器可读：`--json`）
**回归护栏**：`metaphor_graph/test_metaphor_graph.py::TestReachabilityAudit`（15 条）
**数据快照**：`docs/inventory/_reachability.json`

---

## 0. 为什么做这件事

本项目已**三次**出现「代码存在，但生产路径上从不执行」的缺陷，人工审查
每次都漏掉了下一处：

| # | 缺陷 | 后果 | 为什么人工看不见 |
|---|---|---|---|
| ① | `hgnn.py` 跨层传播从未被检索打分路径调用 | 打分走 `training.extract_features` + 中心性字典，于是「flat ≡ HGNN」（\|ΔAUC\| ≤ 0.005），H4 对照的两臂其实是同一件事 | 代码写得完整、有测试、有调用方（`evaluate_hgnn.py`），只是不在**打分**路径上 |
| ② | `mipvu.py` 桥接门控写死 6 个级联 id | 任何替换级联构造规则（`cascade_rules`）的实验**静默关掉整条 MIPVU 通道**，实测丢 7 条 L1 边 | 门控在循环里、形态正常、注释还解释了为什么这么写 |
| ③ | `evaluate_real.py` 无 API key 时静默回落 `LocalHeuristicBackend` | 该后端不实现 `discover_batch`/`batch_refine`，`--llm-cache` 根本不被消费，却仍打印看似正常的指标 —— 假性 **P1 = 0.434**（真实 0.092） | 程序没崩、指标不是 NaN、还有一份「离线近似」的合理说法 |

三次都是「看起来跑通了」。故改为机器检查：把「谁被调用 / 从哪来 / 有没有
可疑形态」变成可执行、可回归的断言，而不是依赖人眼。

---

## 1. 计数（分类）

扫描范围：`metaphor_graph/` + `experiments/` + `release/` + 仓库根，
**排除** `.wt/`（git worktree 副本）、`__pycache__`、`output/`、`data/`。

| 项 | 数量 |
|---|---|
| 扫描文件 | 121 |
| 全部定义（含私有） | 1,166 |
| **被审公开定义** | **919** |
| 入口点：`prod_internal`（包内 `__main__` / 顶层 / 框架钩子） | 94 |
| 入口点：`prod_external`（`experiments/`、`release/` 等） | 129 |
| 入口点：`test` | 320 |

### 分类结果

| 分类 | 含义 | 数量 |
|---|---|---|
| **生产路径** | 可从非测试入口到达 | **582** |
| **仅测试** | 只从 `test_metaphor_graph.py` 可达 | **320** |
| **仅导出** | 在 `__init__.py` 导出但无任何调用点 | **2** |
| **孤立** | 无任何入口可达（含测试与导出） | **15** |
| 合计 | | **919** |

其中「生产路径」里 **231 个**仅由 `experiments/`、`release/` 等**外部脚本**可达，
包内自身没有任何调用方 —— 这一子集值得单独看（第 2.4 节）。

「仅测试」320 个里，**302 个是测试文件自身的方法**（它们本来就是测试入口）。
**真正有信息量的是剩下 18 个**：包内定义，生产路径上无人调用，只有测试在用
（第 3 节）。

---

## 2. 死代码清单

### 2.1 全部「孤立」（15 个）

**A. 包内（`metaphor_graph/`）—— 8 个，这是重点**

| 位置 | 符号 | 说明 |
|---|---|---|
| `embeddings.py:77` | `get_embedder` | 只有 `set_embedder` 被调用，读侧从未接线。写入注入的 embedder 只能通过模块私有 `_EMBEDDER` 间接生效 |
| `llm_backend.py:231` | `OpenAIBackend.from_env` | 类方法，docstring 完整，**零调用点**。构造走的是 `evaluate_real.build_llm_backend` 里的手写逻辑 —— 同一件事有两份实现，一份是死的 |
| `metanet_migrate.py:175` | `MetaNetImporter`（类） | 整个类无人实例化 |
| `metanet_migrate.py:188` | `MetaNetImporter.from_dump` | 上述类的静态方法，docstring 里明确写了「用于接入真实 MetaNet 数据」—— 即**声明了但没做** |
| `models.py:43` | `Evidence.age_days` | 证据时效属性，`resolve_conflict` 的 `strategy="recent"` 依赖时间衰减，但这里的时间戳换算从未被用到 |
| `models.py:175` | `MetaphorSHG.incidence` | `@property`，docstring 写「用于关联矩阵 / 消息传递」。`experiments/_common.py` 另写了一份 `incidence(g)` 函数 —— **重复实现，包内那份是死的** |
| `observability.py:290` | `ObservabilityMeter.measure_many` | 批量包装，只调 `measure`。无人调用 |
| `ontology.py:413` | `CascadeOntology.type_reliability`（**静态方法**） | ⚠️ 见下方说明 |

> ⚠️ **`type_reliability` 是本次审计发现的最值得注意的一处**
>
> `ontology.py` 里有**两个** `type_reliability`：
> - `type_reliability(...)` —— **静态方法**，L413，docstring 自称
>   「type 护栏的**封顶可靠性**——两条打分路径**唯一**的 type 口径」，
>   并明确要求 `training.extract_features` / `extract_text_features` 与
>   `retrieval.RetrievalEngine.metaphor_retriever_score` **都必须调它**；
> - `type_reliability_of(...)` —— **实例方法**，L445，是前者的包装。
>
> 实际调用点**全部**走 `type_reliability_of`（`training.py:133,171`、
> `retrieval.py` 注释、测试）。**静态版本零调用点。**
>
> 这不是缺陷（两条路径确实统一到了同一个口径，只是经由实例方法），
> 但它意味着 docstring 里的「唯一口径」在代码层面**有一份没人用的孪生实现**。
> 危险之处在于：若将来有人按 docstring 去调静态版（它接受 `frames=` 参数、
> 语义与实例版在 `self.type_valid` 可被实例级打补丁这点上不同），
> 就会**分叉出第二条 type 口径** —— 正是 docstring 想防的事。
> 建议：删除静态版，或让实例版显式转发并保留一个别名。

**B. 实验脚本（`experiments/`）—— 7 个**

| 位置 | 符号 | 说明 |
|---|---|---|
| `_common.py:152` | `within_component_cosine` | 组件内余弦一致性度量，定义了但没接进任何实验 |
| `_stats.py:191` | `sign_test` | 符号检验，统计工具箱里唯一没被用到的检验 |
| `auc_h4.py:135` | `boot_ci` | 该文件内定义的 bootstrap CI，**同文件未使用** |
| `gen3/exp_g3_5_verdict.py:50` | `boot_ci` | 同名重复实现，同样未使用（gen3 用的是 `g3_common` 里的版本） |
| `convergence_check.py:66` | `coherence_matrix` | 一致性矩阵，定义后未调用 |
| `gen3/g3_common.py:425` | `eval_rows` | gen3 公共库里的评测行构造，7 个 gen3 脚本都没用它 |
| `sweep_driven.py:101` | `hypergraph_distance` | 超图距离，定义后未调用 |

**共性**：7 个里有 6 个是**度量/统计工具函数**（`eval_rows` 除外，它是评测行
构造器）—— 写完、算过一次、结论进了报告，函数就留在原地。
这类死代码无害但会随轮次累积，且让「哪些工具真的被用过」变得不可判定。
另注意 `boot_ci` 在 `auc_h4.py` 与 `gen3/exp_g3_5_verdict.py` 各有一份
**同名独立实现**，两份都没被调用。

### 2.2 全部「仅导出」（2 个）

| 位置 | 符号 | 说明 |
|---|---|---|
| `llm_backend.py:65` | `MetaphorLLMBackend` | `Protocol` 接口类，在 `__all__` 里。作为类型契约存在是合理的（`@runtime_checkable`），但**无任何 `isinstance` 检查或类型标注引用它** —— 契约目前只是文档 |
| `query_signal.py:381` | `gate_by` | 见第 4.3 节（这是本次审计发现的第二处实质问题） |

### 2.3 「仅测试」中真正有信息量的 18 个（包内定义）

生产路径上无人调用，**只有测试覆盖**。测试通过 ≠ 生产可用：

| 位置 | 符号 | 备注 |
|---|---|---|
| `retrieval.py:346` | `RetrievalEngine.rrf_fusion` | RRF 融合，`__init__.py` 未导出，生产路径无调用方；**论文里 RRF 是三通路融合方案的一部分** |
| `models.py:212` | `merge_evidence` | `__init__.py` 导出，只有测试调 |
| `models.py:227` | `resolve_conflict` | 同上；证据冲突解决（authority/recent/vote）只在测试里跑过 |
| `provenance.py:66` | `frame_provenance` | 溯源通道，只有测试调 |
| `training.py:225` | `trivial_separators` | 平凡分离器自检 —— **它自己的 docstring 说「返回非空即说明该样本集不应上报指标」**，但生产评测路径从不调用它 |
| `training.py:548` | `MetaphorScorer.save` | 与 `load` 不对称：`load` 在生产路径（`evaluate_fullcorpus.py:228` 等），`save` 只在测试里 |
| `hgnn.py:152` | `MetaphorHGNN.propagation_matrix` | 只在谱分析测试里用 |
| `storage.py:182` / `storage.py:258` | `Neo4jStore` / `Neo4jStore.load_shg` | Neo4j 写入端到端只有测试覆盖 |
| `observability.py:294` | `ObservabilityMeter.gate` | 门控方法，只有测试调 |
| `query_signal.py:373` | `StratifiedNormalizer.transform` | 批量版只在测试；生产走 `transform_one` |
| `context_budget.py:58` | `AdaptiveThreshold` | 类只有测试实例化 |
| `extractor.py:307` | `MetaphorExtractor.literal_false_positive_rate` | 字面误判率自检，只在测试里跑 |
| `health.py:70` | `GraphHealth.healthy` | 只有测试调（`report()` 走生产） |
| `embeddings.py:81,85,235,243` | `EmbedderFatalError` / `EmbedderError` / `OpenAICompatibleEmbedder.embed` / `embed_batch` | 真实 embedder 的端到端只在测试里跑过；生产路径靠 `embedder_from_env` + 缓存重放 |

> **`trivial_separators` 与 `literal_false_positive_rate` 值得单独注意**：
> 这两个函数的存在意义是**自我检查**（「这个样本集不该上报指标」/
> 「字面误判率有多高」），而它们在生产评测路径上从不执行。
> 自检不接线，等于没有自检。

### 2.4 仅由外部脚本可达（231 个，非死代码但需知晓）

这些定义在包内**没有任何调用方**，只被 `experiments/`、`release/` 调用。
它们不是死代码（实验脚本是真实调用方），但意味着：

- 包自身的「生产路径」比 582 这个数字小得多；
- 若某天清理 `experiments/`，这 231 个会立刻变成死代码。

审计工具已在 `--json` 输出里用 `external_only: true` 标记，可随时筛出。

---

## 3. 可疑模式命中

### 3.1 硬编码门控（11 处：4 处需人工复核 / 7 处正常）

判定：`if` 条件里出现 `x in {字面量集合}` / `x == "字面量"`，
**且**分支体是 `continue`/`break`/`pass`/`return 空值` —— 即该门控能
**静默**丢弃工作。mipvu 的历史缺陷属于此类。

#### ⚠️ 需复核（4 处）

| 位置 | 函数 | 字面量 | 判断 |
|---|---|---|---|
| `builder.py:175` | `MetaphorSHGBuilder._ensure_cascades` | `'none'` | `orphan_cascade_rule == "none"` 时跳过兜底级联 —— 这是**刻意**的 L3 消融开关（见 `cascade_rules` 模块）。风险：字符串字面量比较，拼错 `"None"`/`"NONE"` 会静默走另一支。建议改为枚举常量 |
| `cascade_rules.py:179` | `build_cascades` | `'none'` | 同上，配套的规则分发 |
| `extractor.py:180` | `MetaphorExtractor.emit` | `'水果'`, `'自然物'` | **本次审计最值得看的一处**，见下 |

> ⚠️ **`extractor.py:180` 的字面干扰护栏**
>
> ```python
> if any(LITERAL_STOPWORDS.get(t) for t in triggers_found) and \
>    frame.source_domain not in ("水果", "自然物"):
>     return None
> ```
>
> 逻辑：触发词是字面用法（`LITERAL_STOPWORDS = {"苹果": "水果公司名", "水": "饮品",
> "火": "物理明火", "路": "物理道路"}`）时丢弃候选 —— **除非**源域是「水果」或
> 「自然物」。
>
> 这个白名单把「苹果/水/火/路」这四个词的字面/隐喻判定**与源域字符串绑定**。
> 它是可用的（测试 `test_literal_anti_interference` 覆盖），但与 mipvu 的
> 历史缺陷**同形**：判据是硬编码字符串，而不是查询本体的结构信息
> （例如「该源域是否已在本体注册且含该触发词」）。
> 后果与 mipvu 缺陷同构：**替换本体/级联构造规则时，这条护栏的行为会
> 静默漂移** —— 若某实验的本体里「水果」域不存在（或改名），
> 四个词的字面护栏会全部失效，P1 虚高且无人察觉。
>
> 当前 `LITERAL_STOPWORDS` 只有 4 个词，影响面小；但模式与已修缺陷一致。
> 建议：改为「该触发词在本体中的注册情况」判定，或至少把
> `("水果", "自然物")` 提为具名常量并在 `cascade_rules` 测试里钉住。

#### 正常实现（7 处，判为 low）

| 位置 | 函数 | 为什么正常 |
|---|---|---|
| `bootstrap_triggers.py:102` | `parse_train_xml` | `lab not in (0, 1, 2)` —— 纯数字标签域校验 |
| `bootstrap_triggers.py:117` | `_vehicle_after` | `_STOP_FUNC` 停用词表（名字带 `STOP` 语义提示） |
| `bootstrap_triggers.py:233` | `mine_triggers` | `_VERB_NOISE` 动词噪声表 |
| `llm_backend.py:516` | `LocalHeuristicBackend._equative_vehicles` | `_SKIP_WORDS` 虚词表 |
| `llm_backend.py:550` | `LocalHeuristicBackend.discover` | `GENERIC_VEHICLE` 字面（实体类型）与示例词表 |
| `evaluate_llmgold.py:446,448` | `main` | `args.split == 'tune'` / `'report'` —— CLI 分支 |

#### 已知修复保持修复

`mipvu.py` 命中数 **0** —— 这是护栏断言
（`test_no_hardcoded_gate_in_mipvu`）。负对照验证：把历史缺陷形态
（`HARDCODED_CASCADES = {"C_EVENT_IS_PLAY", ...}` + `if cascade_id not in ...: continue`）
喂给检测器，**判为 `review`**（识别为 id 清单型门控，即使它在循环内）。
即：该缺陷若复发，护栏会红。

### 3.2 静默回落（30 处，其中 **4 处「返回替身实现」**）

判定：`except` 体只有 `pass`/`continue`/`break` 或 `return 空值`，且无
`raise`/日志；或函数级 `if not <条件>: return <空值 / 替身实现>`。

#### ⚠️ 最危险：`guard 返回替身实现`（4 处）

调用方拿到一个**类型兼容、行为不同**的对象，指标看似正常但含义已变。

| 位置 | 函数 | 条件 | 返回 |
|---|---|---|---|
| **`evaluate_real.py:49`** | `build_llm_backend` | 无 `LLM_API_KEY` | `LocalHeuristicBackend()` |
| `retrieval.py:197` | `RetrievalEngine.cross_domain_retrieve` | `not agg` | `RetrieverResult(chunk_ids=[], scores={...})` |
| `training.py:307` | `_build_from_chunks` | `not rows` | `TrainingSet(np.zeros((0, N)))` |
| `training.py:445` | `build_training_set` | `not rows` | `TrainingSet(np.zeros((0, N)))` |

**`evaluate_real.py:49` 就是缺陷 ③ 本身。** 修复方式是加了一段显式告警
（打印「该后端不实现 `discover_batch`/`batch_refine`，指标不可比较」），
但**返回值仍是替身对象** —— 静态检查能看见形态，看不见告警。
审计把它单独标出来，正是为了让「告警」不成为唯一的防线。

另 3 处是「空输入 → 空结果」的对称处理，属于合理的边界行为，
但**与「真实计算得到空结果」不可区分**。若下游用 `len(x) == 0` 判断
「跑完了」，就会把「没数据」当成「没结果」。

#### 其余 26 处（吞异常 / 降级返回）

按性质分三类：

**A. 包内 `except` 空吞（10 处）**

| 位置 | 函数 | 异常 | 备注 |
|---|---|---|---|
| `llm_backend.py:108,114,120` | `_parse_json_blob` | `json.JSONDecodeError` ×3 | 三级容错解析（直接 / 去围栏 / 提取片段），逐级失败返回 `None`。**这是设计意图**，且调用方会检查 `None` |
| `llm_backend.py:351` | `OpenAIBackend.discover_batch` | `(TypeError, ValueError)` | 「整批降级为空」—— 实测会打印 `discover_batch: 响应不是 JSON 对象，整批降级为空。`（见测试输出）。**静默度中等**：有打印，但批量调用方拿到空列表会继续跑 |
| `llm_backend.py:392` | `OpenAIBackend.refine_batch` | `(TypeError, ValueError)` | 同上 |
| `llm_backend.py:807` | `verify_chains_batch` | `(TypeError, ValueError, IndexError)` | 同上 |
| `bootstrap_triggers.py:100` | `parse_train_xml` | `ValueError` | 单条标注解析失败即跳过 |
| `data_loader.py:60` | `load_ccl2018` | `ValueError` | 单条样本解析失败即跳过 |
| `evaluate_gold_audit.py:162` | `main` | `ValueError` | 单条金标读取失败即跳过 |
| `evaluate_llmgold.py:172` | `stage_gen` | `(TypeError, ValueError)` | 单条生成失败即跳过 |
| `evaluate_llmgold.py:217` | `_norm_keys` | `ValueError` | 键归一化失败即跳过 |
| `embeddings.py:49` | `set_embedder` | `ImportError` | 传播到 `semfield` 失败时忽略（可选依赖） |

> **`llm_backend.py` 的三个 `*_batch` 是本次审计新发现的系统性形态**：
> 它们与缺陷 ③ 是**同一个失效模式**（批量接口静默降级为空），
> 只是发生在 HTTP 响应解析层而非后端选择层。`evaluate_real` 的修复
> （加告警）没有覆盖这三处。建议统一：批量接口降级时**返回一个标记**，
> 或至少在调用方统计降级次数并写进报告。

**B. 包内 `guard 返回空值`（12 处）**

`builder.py:173`(`not orphans`)、`embeddings.py:44`(`not propagate`)、
`embeddings.py:64`(`not api_key`)、`evaluate_repaired.py:455`(`not qset`)、
`extractor.py:177` ×2(`type_valid` 不通过)、`llm_backend.py:103`(`text is None`)、
`llm_backend.py:266`(`not self.api_key`)、`llm_ontology.py:321,325,329`(`load_canon` 三级)、
`models.py:243`(`not live`)、`semfield.py:99`(`not counts`)、`storage.py:223`(`not statements`)

多数是合理的边界返回。**`llm_backend.py:266`（`OpenAIBackend._chat` 在无 api_key 时
返回 `None`）值得注意**：它与缺陷 ③ 同族 —— 「没配密钥」被降级成「调用失败」，
上层无法区分。

**C. 实验脚本（4 处）**：`experiments/` 内的同类形态，影响面限于分析脚本。

#### 已知修复的可见性

`evaluate_real.py` 的回落**被检出**（`guard 返回替身实现`），且是这一类里
唯一带显式告警的。这印证了审计的定位：它不替代告警，而是保证
「形态」在代码变动中始终可见 —— 即使有人删掉那段 print。

### 3.3 有 docstring 但零调用点的公开函数（1 个）

| 位置 | 符号 | 分类 |
|---|---|---|
| `query_signal.py:381` | `gate_by` | **仅导出** |

> ⚠️ **`gate_by` 是本次审计发现的第二处实质问题**
>
> ```python
> def gate_by(signal: Dict[str, float], name: str, theta: float) -> bool:
>     """通用门控：信号 ≥ theta 时放行。不改变任何已上报数字。"""
> ```
>
> 它位于 `query_signal.py` 的 `# 门控辅助（只提供判据，不接检索路径）` 分区，
> 在 `__init__.py` 的 `__all__` 里导出，**零调用点**。
> 注释已经诚实地说明了「不接检索路径」，但：
>
> 1. 它导出为**公开 API**，外部使用者会以为这是可用的门控；
> 2. `query_signal` 模块的整体主张是「查询侧结构信号可用于门控」，
>    而唯一的门控函数没有任何使用示例或测试；
> 3. 与 `compose`（四开关合成器，生产路径上被使用）职责重叠 ——
>    存在两条「如何用信号做决策」的路径，其中一条是死的。
>
> 建议：要么在某个评测脚本里真正用一次（哪怕作为对照臂），
> 要么从 `__all__` 移除并标注为「未接线」。

### 3.4 参数被忽略（16 个）

形参声明了但函数体内从未引用。

**A. 包内（10 个）**

| 位置 | 函数 | 未用参数 | 判断 |
|---|---|---|---|
| `ablation.py:98,163,194,215` | `run_a1`~`run_a4` | `table` | ⚠️ **四个消融函数都接收 `table` 却都不用**。调用方传的是 `args.ontology`（见 `ablation.py:276-280`，参数名 `table` 实际收到的是本体路径）。属命名误导 + 冗余参数，非功能缺陷 |
| `evaluate_fullcorpus.py:103` | `build_queries` | `ont` | 与 `evaluate_llmgold.build_queries_rich` 同口径的注释声称，但本体参数未参与查询构造 |
| `training.py:570` | `build_weak_refine_set` | `chunk_order` | 弱监督训练集的 chunk 排序参数未使用 —— 若排序影响负样本抽样，这里可能有隐患 |
| `llm_backend.py:418,572,579,643,905,913` | 各后端 `discover`/`refine`/`cluster` | `chunk` / `edges` | 协议实现签名占位（`LocalHeuristicBackend.cluster` 直接 `return None`），正常 |

**B. 实验脚本（6 个）**：`eval_degraded.py:70`(`floor`)、
`gen3/exp_g3_3_candidates.py:125`(`rows`)、`gen3/exp_g3_5_verdict.py:50`(`fn`,`n`)、
`gen3/g3_common.py:425`(`gold_key`) —— 其中后两个函数本身也是孤立的。

> **`ablation.py` 的 `table` 参数**：四个 A1~A4 消融函数签名统一为
> `(samples, table, backend, path, rows)`，但 `table` 从未使用，
> 而 `path` 被用作本体路径。若将来有人按签名理解、把缓存表传进 `table`，
> 会静默无效。建议改名或删除。

### 3.5 「仅靠名字兜底可达」——最需人工复核的一带

审计的保守规则：接收者不可解析的方法调用（`x.foo()` 且 `x` 是局部量）
按**方法名全局兜底**连边，置信标为 `low`。这类边**不是精确调用点**。

历史缺陷 ① 正落在这一带：`MetaphorHGNN` 的方法在静态图里「有调用方」，
但打分路径从不走它。审计报告用【五-b】小节单独列出**包内**仅靠兜底边
可达的定义（外部脚本的高频短名如 `mean`/`auc`/`g` 会大面积互相连边，
已排除）。

当前包内该集合以**协议实现方法**为主（`llm_backend.py` 的各后端
`discover`/`refine`/`cluster`、`models.py` 的 `to_dict` 族、
`ontology.py` 的查表族），属预期 —— 它们通过鸭子类型在运行期被调用。
**这是审计的置信度边界，不是死代码清单。**

---

## 4. 分析器的能力边界（它**不能**做什么）

以下限制是**方法本身**的，不是实现疏漏。审计的结论必须在这个边界内解读。

1. **不执行被审代码。** 所有结论来自 AST。运行期动态派发
   （`getattr(obj, name)`、注册表字典、插件式回调、装饰器改写、
   `__getattr__` 代理）一律看不见。

2. **方法名白名单是主要假阴性来源。** 接收者不可解析时，若方法名在
   `_BUILTIN_METHOD_NAMES`（`encode`/`get`/`append`/`to_dict`…）内
   且项目内**无同名方法**，则不连边 —— 否则
   `json.dumps(x).encode("utf-8")` 会把 `MetaphorHGNN.encode` 误判为已调用。
   代价：若项目某方法恰好叫这些名字且**只被动态调用**，会被漏报为不可达。
   （实现上做了两段式：项目内存在同名方法时**照常连边**，
   宁可高估可达性也不漏报。）

3. **不区分「可达」与「在关键路径上生效」。** 这是最重要的一条。
   审计只能回答「有没有调用方」，**不能**回答「检索打分路径是否走它」。
   `MetaphorHGNN.forward` 是可达的（`demo.py`、`evaluate_hgnn.py` 都调），
   但打分路径不走它 —— 这个区分需要**运行期插桩**（覆盖率 / 调用计数），
   不在静态分析能力范围内。
   为部分弥补，测试里加了 `test_hgnn_scoring_path_separation_is_visible`：
   它断言 `retrieval.py` 里不出现 HGNN 调用。**若将来有人把 hgnn 接进
   打分路径，该测试会失败**，提示重跑 H4 对照。这是一条「前提变更告警」，
   不是完整性保证。

4. **测试文件的全部定义都是根。** 因此「仅测试」是**上界**估计 ——
   测试辅助函数（如 `TestHGNDriven.find`）也被算作根，
   它们不会被判为孤立。

5. **每个模块的顶层语句都是入口**（导入即执行）。因此模块级调用链会把
   「仅被顶层执行一次」的代码判为可达。

6. **硬编码门控只认特定形态。** 只检「字面量集合 / 字符串字面量比较」
   且分支体为跳过。以下**不会**被完整捕获：
   - 数值阈值门控（`if x < 0.6: continue`）；
   - 「硬编码 id 写在模块常量里、再经 `.get()` 查表、查不到返回默认值」
     的间接形态（如 `CASCADES.get(cid, DEFAULT)`）；
   - 门控写在被调用的**辅助函数**里，而主函数只调用它。

7. **参数被忽略只做名字级检查。** 通过 `globals()`/`locals()`/`**kwargs`
   间接使用形参会**误报**为未使用。协议存根、`@abstractmethod`、
   `Protocol` 类的方法已显式排除。

8. **跨仓库调用不在扫描范围。** 本项目之外的调用方（外部文档、
   未纳入的脚本、下游用户代码）看不见。`release/` 已纳入，
   但 `release/MetaphorRAG-Bench` 只有 JSON 数据、无 Python 调用方。

9. **同名多解时放弃推断。** 类名/模块末段有多个候选时返回 `None`
   （走名字兜底或标为不可达），避免猜错。代价是可能低估可达性。

10. **不检查语义正确性。** 「函数被调用了」不等于「调用是对的」。
    例如 `ablation.py` 的 `table` 参数收了本体路径仍能跑通 ——
    审计只能报告「参数未被使用」，不能报告「参数名与实参不符」。

---

## 5. 回归护栏（怎么用）

`metaphor_graph/test_metaphor_graph.py::TestReachabilityAudit`，15 条，全部通过。

| 测试 | 作用 |
|---|---|
| `test_audit_runs_without_error` | (a) 审计能跑完，零解析失败，四分类覆盖全部定义 |
| `test_every_node_has_a_classification_and_confidence` | 每个节点都有分类与置信度；生产路径必有调用链 |
| `test_audit_is_deterministic` | 两次审计结果逐位相同（防集合迭代顺序泄漏） |
| `test_isolated_functions_do_not_exceed_baseline` | **(b)** 孤立数 ≤ 基线 15，超了就把清单打出来 |
| `test_exported_only_does_not_exceed_baseline` | 仅导出数 ≤ 基线 2 |
| `test_isolation_baseline_is_actually_pinned` | 棘轮必须是**紧的**：孤立数远低于基线时强制下调 |
| `test_known_dead_code_is_registered` | 已确认的 6 处死代码必须在清单里（防悄悄复活/消失） |
| `test_no_hardcoded_gate_in_mipvu` | **(c)** mipvu.py 硬编码门控命中数必须为 0 |
| `test_mipvu_uses_ontology_lookup_not_literal_ids` | AST 级：mipvu 里不得有 `C_*`/`F_*` 写死进 `.get()` |
| `test_mipvu_candidate_channel_is_reachable` | MIPVU 通道本身不能变成死代码 |
| `test_three_historical_defects_are_pinned` | 三个历史缺陷的位置必须仍被审计覆盖 |
| `test_hgnn_scoring_path_separation_is_visible` | `retrieval.py` 不得出现 HGNN 调用（前提变更告警） |
| `test_pattern_sections_are_populated_and_structured` | 四个模式小节结构完整；测试文件与工具自身不入清单 |
| `test_limitations_are_declared` | 能力边界必须显式声明（诚实性） |
| `test_json_payload_is_serializable` | `--json` 输出可序列化 |

### 棘轮约定

`ISOLATED_BASELINE = 15` 是**当前实测值**，不是理想值。

- 修掉死代码 → **必须同步下调**基线（`test_isolation_baseline_is_actually_pinned`
  会在偏差 > 3 时失败，强制这件事）；
- 新增死代码 → 测试变红；
- 上调基线 → 需要理由，并更新本报告。

### 完整测试套件

```
python -m unittest metaphor_graph.test_metaphor_graph
Ran 243 tests in 18.974s
OK
```

（本轮之前 228 条 → 新增 15 条，全绿。）

---

## 6. 本轮结论

### 与三个已知缺陷的关系

| 缺陷 | 审计能否检出 | 说明 |
|---|---|---|
| ① hgnn 跨层传播不在打分路径 | **部分** | 能证明 `forward` 可达、能断言 `retrieval.py` 无 HGNN 调用；**不能**自动证明「打分路径不走它」——那需要运行期插桩。已在测试里钉住前提（第 4.3 节） |
| ② mipvu 硬编码门控 | **能** | 直接命中（负对照验证：喂历史形态判 `review`）。护栏保证不复发 |
| ③ evaluate_real 静默回落 | **能** | 命中 `guard 返回替身实现`，且这是该类里唯一带告警的。护栏保证形态可见 |

### 新发现（按重要性）

1. **`ontology.py` 的静态 `type_reliability` 是死的孪生实现**（L413）。
   docstring 自称「两条打分路径唯一的 type 口径」，实际全部调用走
   `type_reliability_of`。风险不是当前行为，而是**将来有人按 docstring
   去调静态版会分叉出第二条口径** —— 正是它想防的事。建议删除或改为转发。

2. **`extractor.py:180` 的字面护栏是 mipvu 缺陷的同形形态**：
   把「苹果/水/火/路」四词的字面判定绑定到硬编码源域字符串
   `("水果", "自然物")`。当前影响面小（4 个词），但**替换本体时会静默漂移**，
   与已修缺陷的失效机制完全一致。

3. **`llm_backend.py` 的三个 `*_batch` 与缺陷 ③ 同族**：
   `discover_batch`/`refine_batch`/`verify_chains_batch` 在响应解析失败时
   「整批降级为空」，有打印但调用方拿到空列表会继续跑。
   `evaluate_real` 的修复（加告警）没有覆盖这三处。

4. **`query_signal.gate_by` 是导出但零调用的门控函数**：
   模块注释诚实（「不接检索路径」），但作为公开 API 导出会误导；
   且与生产在用的 `compose` 职责重叠。

5. **`trivial_separators` 与 `literal_false_positive_rate` 只在测试里跑**：
   两个**自检**函数（「该样本集不该上报指标」/「字面误判率」）
   在生产评测路径上从不执行。自检不接线等于没有自检。

6. **`models.MetaphorSHG.incidence`（@property）与
   `experiments/_common.incidence(g)` 是两份实现**，包内那份是死的。

7. **`ablation.py` 四个消融函数的 `table` 参数未被使用**
   （实参传的是本体路径，参数名与用法不符）。

### 数字速览

| | |
|---|---|
| 被审公开定义 | 919 |
| 生产路径 | 582（其中 231 仅由外部脚本可达） |
| 仅测试 | 320（其中 18 个是包内定义，302 个是测试方法自身） |
| 仅导出 | 2 |
| **孤立** | **15**（包内 8 / 实验脚本 7） |
| 硬编码门控 | 11（**review 4** / low 7；mipvu 命中 0） |
| 静默回落 | 30（**替身实现 4**） |
| 有 docstring 却零调用 | 1 |
| 参数被忽略 | 16 |
