# 未接入的公开 API：分类与处置

> 来源：`python -m metaphor_graph.audit_reachability --section dead`
> 结论：**18 项"孤立"中，14 项是包内定义、4 项是测试文件自身定义。
> 14 项全部有明确存在理由，不建议删除。**

---

## 0. 为什么不删

这些 API 是**声明但未接线**的能力，不是缺陷。删除会造成两类损失：

1. **论文/README 声称的能力失去实现** —— 例如 RRF 融合、Neo4j 存储、
   Ω 门控都在论文里写过；删掉代码会让"已实现"变成"未实现"。
2. **自检与契约失去载体** —— `trivial_separators`（泄漏自检）、
   `EmbedderError`（错误分层）本身是质量保障设施。

**正确处置是标注，不是删除。** 本文件即为该标注。

---

## 1. 论文/README 声称的能力（7 项）

> ⚠️ **本节结论已更正（主控复核）**：我原先假设"论文声称了 RRF/Neo4j 但未接入"，
> 逐词核对论文全文后**该假设不成立** —— **论文从未提及 RRF、Neo4j、多线索汇聚**
> （`grep -c` 均为 0）。这些能力只出现在**方案文档**（`知识隐喻分析任务方案.md`）
> 与 `metaphor_graph/README.md`（开发日志）中。
> 论文实际提到的三个相关名词都**准确**：`HL-index`（§2 相关工作，引用他人工作）、
> `U-Retrieval`（§3.4，且 `cross_domain_retrieve` 确实被三个评测脚本调用）、
> `元图`（§1/§2 概念讨论）。
> **故无需在论文加任何"未接入"标注。** 下表仅为工程侧清点。

| API | 出现位置 | 状态 | 处置建议 |
|---|---|---|---|
| `retrieval.py::RetrievalEngine.rrf_fusion` | 方案文档 §4.6（论文未提） | 实现但未接入生产路径 | 无需改论文；方案文档可标注为"已实现未用于主实验" |
| `models.py::merge_evidence` / `resolve_conflict` | 方案文档（演化治理） | 实现但未接入 | 同上 |
| `storage.py::Neo4jStore` | 方案文档 §4.6（论文未提） | 实现但未接入（实验用内存图） | 同上 |
| `observability.py::ObservabilityMeter.gate` | §7 负面结果（Ω 门控） | 实现；Ω 方向已被证伪 | 保留作为负面结论的可复现证据 |
| `provenance.py::frame_provenance` | 溯源分级标签 | 实现但未接入 | 与 `frame_reliability` 配套的审计接口 |
| `hgnn.py::MetaphorHGNN.propagation_matrix` | §6.3 谱分析 | 实现；仅测试与谱分析用 | 保留（`exp/dynamics` 的谱性质结论依赖它） |
| `training.py::MetaphorScorer.save` | — | 实现但未接入生产路径 | 排序器持久化接口。**有配对的 `load`**（`training.py:559`），二者由 `test_metaphor_graph.py:940-941` 成对测试（存→读→分数一致）。审计器只把 `save` 报为孤立，是因为 `load` 被测试调用而 `save` 只在测试内被调用 —— 属**分析器粒度问题，不是半个接口** |

## 2. 测试专用自检工具（3 项）

| API | 用途 | 为什么"仅测试可达"是合理的 |
|---|---|---|
| `training.py::trivial_separators` | 泄漏自检：返回 AUC 过高的特征名 | 它**本就该**只在评测前被调用；生产路径不该跑自检 |
| `extractor.py::literal_false_positive_rate` | P1 自检 | 同上 |
| `health.py::GraphHealth.healthy` | 健康判定谓词 | 报告文本直接读字段，谓词供外部调用 |

> 这三项揭示了一个值得记录的现象：**自检工具若不被接线，就不是自检**。
> `trivial_separators` 在 `training.py` 的 docstring 里写着"上报任何指标前先跑"，
> 但没有任何生产脚本强制调用它。**建议**：在评测脚本入口加一次断言。

## 3. 异常类型与接口契约（4 项）

| API | 用途 |
|---|---|
| `embeddings.py::EmbedderFatalError` / `EmbedderError` | 错误分层（致命 vs 可重试）—— `llm_backend.py:56` 的注释明确说明"刻意不被 except 吞掉" |
| `embeddings.py::OpenAICompatibleEmbedder.embed` / `embed_batch` | 向量器接口；`embedder_from_env()` 返回实例后由 `set_embedder` 注入 |
| `context_budget.py::AdaptiveThreshold` | 自适应阈值类；A8 消融直接用它，但审计器把 `evaluate_*` 脚本视为非包内入口 |
| `query_signal.py::StratifiedNormalizer.transform` | 分层归一化；`fit` 被调用而 `transform` 未接 |

> 这四项多属**分析器能力边界**造成的假"孤立"（见下节）。

---

## 4. 分析器的已知假阴性（摘自 `reachability.md` §10）

审计器**不执行代码**，故以下情形会漏报可达性：

1. 运行期动态派发（`getattr(obj, name)`、注册表字典、插件式回调、装饰器改写）
2. 接收者不可解析的方法调用，且方法名在 `_BUILTIN_METHOD_NAMES` 白名单内
3. 跨仓库调用（本项目之外的调用方）
4. **不区分"可达"与"在关键路径上生效"** —— 例如 hgnn 的跨层传播只要被任何
   非测试调用方调用过就算可达，**即使检索打分路径并不走它**。要判后者需运行期插桩。

第 4 条正是本项目最著名的案例：`flat ≡ HGNN` 的根因是**评分路径从不调用 hgnn**，
而这一点审计器**无法**证明（它只能证明 hgnn 是可达的）。
该结论来自代码审计 + 指标证据，并已固化为 `test_hgnn_scoring_path_separation_is_visible`。

---

## 5. 建议的后续动作（按价值排序）

1. **在评测脚本入口调用 `trivial_separators`** —— 让自检真正生效（1 行断言）。
2. ~~论文 §3.4/§4.6 标注 RRF 与 Neo4j 的接入状态~~ —— **此建议已撤回**：
   逐词核对确认**论文从未提及这两者**（只在方案文档里），不存在"声称已实现"的误读。
   若要标注，改方案文档即可，与投稿稿无关。
3. ~~考虑删除 `MetaphorScorer.save`~~ —— **此建议已撤回**。核对后确认
   `load` 存在（`training.py:559`）且与 `save` 成对测试通过，
   `save` 是完整接口的一半配对，不该删。（本条原写"无对应 load"是我的核对错误。）
4. 其余 14 项保持现状（有理由的 API 表面）。
