# 资源 / 接口 / 契约 清单

> 对象：`E:\02_AI项目\元图隐喻分析`（MetaphorSHG：中文隐喻超超图检索）
> 生成方式：逐文件读取 + 解释器实测计数（`venv_jieba/Scripts/python.exe`，Python 3.13.12）。
> **本文所有计数均为实测值**，与文档叙述不一致处集中在
> [「文档与实际的计数差异」](#文档与实际的计数差异) 一节。
> 本文只读；未修改任何被清点的资源。

---

## 0. 汇总表

| 资源 | 路径 | 规模（实测） | 许可 | 用途 |
|---|---|---|---|---|
| 生产本体（中文） | `metaphor_graph/ontology_default.json` | 2,177 框架 / 733 级联 / 895 触发词槽（606 唯一） | CC BY-NC-SA 4.0 | L2/L3 查表归属 |
| 双语对齐本体 | `metaphor_graph/ontology_bilingual.json` | 2,177 条对齐（curated 2 / auto_gloss 2,175 / unmapped 0） | CC BY-NC-SA 4.0 | 英文锚点、跨语引用 |
| 自举触发词表 | `metaphor_graph/bootstrap_triggers.json` | 61 名词喻体 / 0 动词喻体 | CC BY-NC-SA 4.0 | 触发词回填种子 |
| 自举本体（原始） | `metaphor_graph/llm_ontology_train.json` | 2,185 框架 / 734 级联 | CC BY-NC-SA 4.0 | 清洗前原始产物（留档） |
| 自举本体（首轮） | `metaphor_graph/llm_ontology.json` | 656 框架 / 284 级联（全 GENERIC_VEHICLE） | CC BY-NC-SA 4.0 | 早期试验留档 |
| MetaNet 种子 | `metaphor_graph/ontology_metanet_seeds.json` | 25 框架 / 18 级联 / 5 类型约束扩展 | 代码 MIT（内置种子） | 冷启动种子 |
| 资源发布包 | `release/metaphor_resources/` | 5 文件 / 1,786,255 B | CC BY-NC-SA 4.0 | 本体对外交付 |
| 检索基准 | `release/MetaphorRAG-Bench/` | 4 文件 / 108,344 B；632 查询 / 18 chunk / 106 文档元数据 | CC BY-NC-SA 4.0 | 评测协议 |
| 发布 zip | `release/metaphor_shg_release.zip` | 272,697 B / 9 条目 | CC BY-NC-SA 4.0 | 单文件分发 |
| LLM 缓存族 | `data/llm_cache_*.json` | 13 个文件，见 §3 | 不入库（`data/` 已 gitignore） | 零成本重放 |
| 向量缓存 | `data/embed_cache.json` | 3,176 条 / 512 维 / 22,197,131 B | 不入库 | 真实句向量重放 |
| 语料缓存 | `data/corpus/*` | 1,050 chunk / 106 文档 / 见 §3.4 | 不入库（版权） | 连贯文档 L1.5 验证 |
| Neo4j schema | `metaphor_graph/neo4j_schema.cypher` | 85 行：6 索引 + 5 唯一约束 + 6 查询模板 | MIT | 图存储契约 |
| Cypher 导出样例 | `metaphor_graph/export_shg.cypher` | 250 行 / 250 语句（7 CREATE + 119 MATCH + 124 MERGE） | MIT | 幂等导入样例 |
| 存储接口 | `metaphor_graph/storage.py` | 291 行；`Neo4jStore` + `shg_to_cypher` | MIT | 图读写 |
| LLM 接口 | `metaphor_graph/llm_backend.py` | 914 行；4 后端 + 1 Protocol | MIT | 可插拔 LLM |
| 向量接口 | `metaphor_graph/embeddings.py` | 307 行；2 编码器 + 1 客户端 | MIT | 文本向量化 |
| 数据模型 | `metaphor_graph/models.py` | 268 行；7 dataclass + 2 函数 | MIT | 数据契约 |
| 数据集获取 | `metaphor_graph/download_datasets.py` | 51 行 | MIT | 语料自助获取 |

**不入库清单**（`git ls-files data/` → 0 条）：`data/` 整个目录、`.workbuddy/`、`.wt/`、
`experiments/gen3/*.pkl` 均被 `.gitignore` 排除。仓库共 295 个跟踪文件。

---

## 1. 本体资源

### 1.1 `metaphor_graph/ontology_default.json` — 生产默认本体（中文）

- **规模（实测）**：1,147,665 B / 51,475 行；`frames` **2,177**、`cascades` **733**、
  `canon` 3 键、`provenance` 5 键。
- **schema**：顶层 `{frames:[FrameSpec], cascades:[CascadeSpec], canon:{...}, provenance:{...}}`

  ```
  FrameSpec = {id, name, mapping_type, source_domain, target_domain,
               ground: List[str], triggers: List[str],
               source_type, source_frame, target_frame, support:int, tier:str}
  CascadeSpec = {id, name, member_frames: List[str],
                 discourse_domains: List[str], typical_triggers: List[str]}
  canon = {sources: 1,927 条, targets: 2,099 条, dropped_triggers: 291 条}
  ```

- **实测分布**：

  | 维度 | 计数 |
  |---|---|
  | `tier` | core **299** / longtail **1,878** |
  | `support` | =1: 1,878；=2: 204；=3: 46；=4: 19；≥5: 30（最大 13） |
  | `source_type` | 15 类；NATURAL_PHENOMENON 358、GENERIC_VEHICLE 793、PHYSICAL_OBJECT 190、BODY_SENSATION 179、ORGANISM 128、NATURE 121、MOTION 110、WAR 106 … |
  | `mapping_type` | 1,071 个不同值（GENERIC_VEHICLE_MAP 793 + `DISCOVERED::<TYPE>_TO_<目标域>` 1,384） |
  | 触发词 | 895 槽位 / **606 唯一**；1,387 个框架 0 触发词 |
  | 喻底 | 3,301 槽位 / 2,282 唯一；25 个框架 0 喻底 |
  | 域词 | 源域 535 唯一 / 目标域 733 唯一 / 并集 1,156 |
  | 级联成员 | 2,177 槽位（无空级联，恰好一一覆盖框架集） |
  | id 前缀 | 框架 **100%** `F_LLM_`（2,177/2,177）；级联 **100%** `C_LLM_`（733/733） |
  | 唯一性 | id / name 均无重复；自环（source==target）**0** |

- **保证**：
  - **只用训练集构建**（`provenance.source_json = llm_ontology_train.json`），
    测试集仅用于评估 → 无测试集泄漏。
  - **构建规则确定性**（`provenance.rules`）：
    R1 删自环（`source_domain == target_domain`）；
    R2 剔除喻底中的明喻标记 `['一般','仿佛','似','像','像…一样','好比','如','宛如','犹如','般','若']`；
    R3 `count>=2 → core，否则 longtail`。
  - **可复现**：`provenance.stats` 记录 `n_in 2185 → n_out 2177`（删 8 自环、清 50 处喻底）。
  - **不含句子原文**：DATA.md 声明"已扫描验证：0 条测试集原句"，本体只保留概念域/喻底/触发词。
  - **id 跨进程稳定**：`llm_ontology._stable_id()` 用 `md5("||".join(parts))[:8]`，
    不用内置 `hash`（受 `PYTHONHASHSEED` 随机化）。

- **边界**：
  - 1387/2177（**63.7%**）框架无触发词 → 只能靠模糊匹配/LLM 发现触达，查表通路对它们无效。
  - longtail 1,878 条（86.3%）从未二次验证；core-only 消融显示 longtail 贡献 +1.2pp 召回，
    故默认两级全载 —— 精度与覆盖的取舍未被进一步优化。
  - `mapping_type` 的 1,384 个 `DISCOVERED::*` 值是**每个 (source_type, target_domain) 一个**，
    并非受控词表；`TYPE_CONSTRAINTS` 需在构建时动态登记，否则 `type_valid` 全判非法。
  - `name` 形如 `LLM::食物_IS_爱情`（中文），无英文锚点 —— 需 `ontology_bilingual.json` 补齐。
  - 本体**不含** confidence / 证据链字段：支持度只有 `support:int` 一个标量。

- **许可**：**CC BY-NC-SA 4.0**（`LICENSE` §2）。理由：由 CCL2018 训练集经 LLM 自举构建，
  属评测数据派生作品；CCL2018 声明"仅限学术研究、禁止商业用途"，派生资源沿用非商业口径。

### 1.2 `metaphor_graph/ontology_bilingual.json` — 双语对齐

- **规模（实测）**：620,352 B / 23,958 行；`alignments` **2,177** 条（与本体框架一一对应）。
- **schema**：`{coverage:{n_frames, curated, auto_gloss, unmapped, note}, alignments:{frame_id: {...}}}`

  ```
  alignment = {zh_name, zh_source, zh_target, en_name, en_source, en_target,
               alignment: "curated"|"auto_gloss"|"unmapped", tier, support}
  ```

- **实测分布**：`curated` **2** / `auto_gloss` **2,175** / `unmapped` **0**；
  9 个字段全部 2,177 条齐备，`en_name` 无空值。
  curated 两条为：`F_LLM_8e5603e7 旅程→生活 = LIFE IS A JOURNEY`、
  `F_LLM_46eec99b 旅程→爱情 = LOVE IS A JOURNEY`。
- **保证**：
  - 三级策略**显式标注不混淆**（`alignment` 字段）：`curated` = 与
    `metanet_migrate.BUILTIN_CONCEPTUAL_METAPHORS`（11 条）中英完全一致；
    `auto_gloss` = 域级词典 `DOMAIN_ZH_EN` 双向命中，`en_name = "{EN_SOURCE} IS {EN_TARGET}"`；
    `unmapped` = 任一侧域不在词典中，**保留原样不猜**。
  - `coverage.note` 内嵌诚实声明：**auto_gloss 只主张概念域对应，不主张该英文隐喻在
    MetaNet 中真实存在**。
- **边界（重要，影响可复现性）**：
  - **`ontology_bilingual.json` 无法由仓库内代码单独重建**。实测：
    仅用静态词典 `DOMAIN_ZH_EN`（**485 条**）→ auto_gloss 1,055 / unmapped 1,122；
    合并 `data/bilingual_llm_ext.json`（**835 条**）→ auto_gloss 2,177 / unmapped 0，
    与发布产物一致。而 `bilingual_llm_ext.json` 位于被 gitignore 的 `data/` 下。
  - 词典扩展由 `ontology_bilingual.llm_complete()` 调 LLM 生成，需要 `LLM_API_KEY`；
    自一致性抽检 `data/bilingual_spotcheck.json`：n=84，self_consistency = **0.869**。
  - 2,175 条（99.9%）是机器词汇转写，**不是**独立的英文抽取本体；英文资源为对齐标注，
    不是可独立使用的英文隐喻知识库（DATA.md §5 边界 6）。
- **许可**：**CC BY-NC-SA 4.0**（同 1.1；`LICENSE` §2 明列）。

### 1.3 `metaphor_graph/bootstrap_triggers.json` — 自举触发词表

- **规模（实测）**：7,888 B / 442 行；11 个顶层键。
- **schema**：

  ```
  {source: "train.xml", n_met: 4075, n_neu: 319, min_df: 3,
   literal_constraint: "df_neu==0", n_noun: 61, n_verb: 0,
   noun_vehicles: [61 项], verb_vehicles: [0 项],
   noun_rows: [{word, df_met, df_neu, lift}, 61 项], verb_rows: []}
  ```

- **实测内容**：`noun_vehicles` 61 条（如 `是人生 / 是人 / 是人类 / 是祖国 / 是战争 /
  成了海洋 / 像人 / 像火 / 是灵魂 / 是旅程 / 是海洋`）；
  样例行 `{"word":"是人生","df_met":12,"df_neu":0,"lift":2944785.3}`。
- **保证**：
  - 挖掘来源与阈值**显式落盘**：源 `train.xml`，隐喻句 4,075 / 中性句 319，
    最小文档频次 3，**字面约束 `df_neu==0`**（只在隐喻句出现、从不在中性句出现）。
  - 复用 `metaphor_graph/bootstrap_triggers.py`（328 行，依赖 jieba）可重建。
- **边界**：
  - **动词喻体 0 条**：`n_verb=0`、`verb_rows=[]` —— 动词通道实际未产出。
  - 只有 61 条名词喻体，是**种子**而非完整触发词表（本体另有 895 个触发词槽位）。
  - 产物形式是「等比模式串」（含「是」「像」「成了」等标记词），不能直接当独立触发词使用。
  - 依赖 jieba；缺失时 `bootstrap_triggers.py` 以 `SystemExit` 提示而非静默降级，
    相关单测在无 jieba 环境下 skip。
- **许可**：**CC BY-NC-SA 4.0**（`LICENSE` §2 明列 `bootstrap_triggers.json`）。

### 1.4 `metaphor_graph/llm_ontology_train.json` — 自举原始产物（留档）

- **规模（实测）**：1,060,460 B / 47,315 行；`frames` **2,185**、`cascades` **734**、`canon` 3 键。
- **与生产本体的差**：框架 2,185 → 2,177（删 8 自环）；级联 734 → 733；
  触发词槽位 896 → 895（唯一触发词两者同为 **606**）；
  且**无** `support` / `tier` / `provenance` 字段。
- **保证**：作为清洗的可复算输入保留，`ontology_clean.py` 可从此文件重跑出生产本体。
- **边界**：含自环框架与喻底明喻标记污染（即被 R1/R2 删除的内容），
  **不应直接用作生产本体**。`GENERIC_VEHICLE` 占 799/2,185 = 36.6%。
- **许可**：**CC BY-NC-SA 4.0**（`LICENSE` §2 明列）。

### 1.5 `metaphor_graph/llm_ontology.json` — 首轮自举留档

- **规模（实测）**：321,897 B / 14,697 行；`frames` **656**、`cascades` **284**、`canon` 3 键。
- **实测特征**：**656/656（100%）`source_type = GENERIC_VEHICLE`**，无 `support`/`tier`。
- **保证**：无（历史留档，无 provenance 字段）。
- **边界**：**全部**为 `GENERIC_VEHICLE` → 该版本下 `TYPE_CONSTRAINTS` 对
  `GENERIC_VEHICLE_MAP` 无条件合法，**类型安全约束运行时从不拒绝任何候选**。
  这正是 README §7.1 A1 记录的"H1 不成立"的根因来源，不可用于生产。
- **许可**：`LICENSE` 未单独列出；按同族产物归入 CC BY-NC-SA 4.0 口径。

### 1.6 `metaphor_graph/ontology_metanet_seeds.json` — MetaNet 种子

- **规模（实测）**：18,816 B / 838 行；`frames` **25**、`cascades` **18**、
  `type_constraints_ext` **5**。
- **schema**：`frames` 为 dict（id → FrameSpec-like），`cascades` 为 dict。
- **保证**：`metanet_migrate.BUILTIN_CONCEPTUAL_METAPHORS` 内置 **11 条**中英概念隐喻，
  是 `ontology_bilingual` 的 curated 层唯一来源。
- **边界（实测发现）**：内置 11 条中只有 **2 条**（`旅程→生活`、`旅程→爱情`）
  在 2,177 框架里存在对应 (source, target) 对；
  另 9 条（`目的地→目标 / 洁净→道德 / 视觉→理解 / 植物→组织 / 上下→情绪效价 /
  物体传递→交流 / 体量→重要性 / 食物→想法 / 建筑→理论`）**无匹配框架** ——
  自举产物没有生成这些经典概念隐喻的组合。
- **许可**：`LICENSE` §1（代码 MIT）覆盖内置种子；§4 声明引用方法（MetaNet 等）
  版权归各自作者，本仓库仅含独立实现。

### 1.7 schema 定义源：`FrameSpec` / `CascadeSpec`

- **路径**：`metaphor_graph/ontology.py`（471 行）。
- **签名**（`@dataclass`）：

  ```python
  FrameSpec(id, name, mapping_type, source_domain, target_domain,
            ground: List[str], triggers: List[str], source_type,
            source_frame="", target_frame="",
            support: int = 0, tier: str = "")
  CascadeSpec(id, name, member_frames: List[str],
              discourse_domains=[], typical_triggers=[])
  ```

- **配套接口**：`CascadeOntology.match_by_triggers / match_frame / get_frame /
  get_cascade / get_cascade_spec / type_valid / type_reliability / type_reliability_of / stats`；
  `infer_source_type(domain)` 按 15 类关键词表推断 `source_type`。
- **`TYPE_CONSTRAINTS`（15 类 source_type → 允许 mapping_type）**，例如
  `PHYSICAL_OBJECT → [OBJECT_IS_CONTAINER, OBJECT_IS_INSTRUMENT]`、
  `GENERIC_VEHICLE → [GENERIC_VEHICLE_MAP]`（无条件合法，刻意保留）。
- **保证**：
  - `type_reliability` 是**两条打分路径唯一口径**（`training.extract_features` 与
    `retrieval.metaphor_retriever_score` 都必须调它），防止特征漂移。
    判定：无 frame_id → 0.0；已登记且 `type_valid` → 1.0；已登记但非法 → 0.0；
    **未登记（回退框架）→ 0.5 封顶**（不丢弃候选）。
  - 生产本体 `F_LLM_` 前缀占比 **100%**，故**唯一正确的"是否退化"判据是
    "该 frame_id 在本体中有无条目"**，绝不能按 `F_LLM_` 前缀判定
    （`provenance.py` 明确记录此为实测陷阱）。
- **边界**：`TYPE_CONSTRAINTS` 的键集合需在装载自举本体时**动态扩充**
  （`load_metaphor_resources.py` 与 `llm_ontology.build_llm_ontology` 各自补登），
  否则新 `DISCOVERED::*` 映射会被 `type_valid` 全判非法、整个自举本体失效。
- **许可**：MIT（`LICENSE` §1）。

---

## 2. 发布物

### 2.1 `release/metaphor_resources/` — 资源包

- **规模（实测）**：5 文件 / **1,786,255 B**。

  | 文件 | 字节 | 说明 |
  |---|---|---|
  | `ontology_default.json` | 1,147,665 | 与 `metaphor_graph/` 同名文件 **md5 一致**（`0afe957214…`） |
  | `ontology_bilingual.json` | 620,352 | md5 一致（`2ef2cb3d53…`） |
  | `bootstrap_triggers.json` | 7,888 | md5 一致（`8da552e800…`） |
  | `DATASET_CARD.md` | 783 | 数据卡 |
  | `load_metaphor_resources.py` | 1,567 | 一键加载脚本 |

- **`load_metaphor_resources.py` 签名**：`load_resources() -> (CascadeOntology, dict)`。
  内部重建 `_trigger_index`、`_frame_to_cascade`，并把每个框架的 `mapping_type`
  补登进 `TYPE_CONSTRAINTS`。自检输出：`本体: 2177 框架 / 733 级联; 双语对齐 2177 条`。
- **`DATASET_CARD.md` 内容**：来源（CCL2018 训练集 LLM 自举，`glm-5.3-flash`，置信≥0.85）
  → 清洗（删自环/清喻底/支持度分层）→ 生产沉淀；构建脚本 `ontology_clean.py`；
  schema 说明；双语三级说明；口径说明；许可说明。
- **保证**：发布副本与工作副本**逐字节一致**（md5 实测相等）→ 无版本漂移。
- **边界**：
  - `DATASET_CARD.md` **未记录许可全文**，只写"语料与本体仅供研究使用"；
    正式条款在仓库根 `LICENSE` §2，**不在发布包内**（zip 也不含 `LICENSE`/`DATA.md`）。
  - 不含 `llm_ontology_train.json`（原始产物），也不含任何缓存。
  - `load_metaphor_resources.py` 依赖 `metaphor_graph.ontology` 模块（`sys.path` 上溯一级），
    不是零依赖的独立脚本。
- **许可**：**CC BY-NC-SA 4.0**（`LICENSE` §2 明列 `release/metaphor_resources/**`）。

### 2.2 `release/MetaphorRAG-Bench/` — 检索基准

- **规模（实测）**：4 文件 / **108,344 B**。

  | 文件 | 字节 | 实测计数 |
  |---|---|---|
  | `bench_queries.json` | 81,382 | **632** 条查询 |
  | `bench_extended_chains.json` | 23,549 | **106** 篇文档元数据，其中 9 篇 `n_ext>0`，**11** 个 span |
  | `bench_docs.json` | 2,690 | 2 篇文档 / **18** chunk（11 + 7） |
  | `BENCHMARK.md` | 723 | 协议说明 |

- **schema**：

  ```python
  # bench_queries.json（list）
  {doc_id: "fc0", question: str, gold_chunks: ["fc0_c0", ...]}
  # 实测：646 gold 槽位 / 544 唯一 chunk；gold 大小 =1: 619, =2: 12, =3: 1
  #       覆盖 108 个 fc 文档（fc0..fc109，缺 fc10/fc11）；64 条 question 重复

  # bench_docs.json（dict）
  {doc_id: {chunks: [str], gold_extended: [[int]], gold_retrieval: [[str,[int]]]}}
  # doc_project: 11 chunk / 4 gold_extended / 5 gold_retrieval
  # doc_relationship: 7 chunk / 3 gold_extended / 3 gold_retrieval

  # bench_extended_chains.json（list）
  {doc_id, title, source, n_chunks, n_l1, n_ext, spans: [{n_chunks, span, frame, ground}]}
  # 实测：Σn_chunks=1050, Σn_l1=822, Σn_ext=11
  #       source 分布：人民网财经 40 / 鲁迅全集(公版) 60 / 维基文库 6
  ```

- **保证**：
  - `bench_queries` 的金标是 **LLM 非构造金标**：由 `evaluate_llmgold` 两阶段
    （gen 改写 → judge listwise 相关性）产出，再按**确定性边 id** 映射到 chunk 集合。
    改写阶段有程序化红线：禁止出现触发词/源域/目标域（实测剔除 26.7%）。
  - **可复算漏斗**（实测复现，逐级收敛）：
    自动查询 **861** → 红线过滤后 **635** → 有 LLM 金标 **635** →
    金标 chunk 非空 **632**（= `bench_queries.json` 规模）。差额 3 条因金标边无 chunk_spans。
  - `bench_docs` 含**字面干扰**与**跨距负样本**（如"苹果发布了新手机…"、
    "这家餐厅新出了春日限定套餐…"）。
- **边界**：
  - **632 条查询的 `doc_id` 覆盖 108 个 fc 文档**，但 `bench_docs.json` 只含 **2** 篇
    文档原文 —— 其余 106 篇的 chunk 文本**不在发布包内**（需 CCL2018 才能还原）。
    这意味着 `bench_queries.json` 单独**不可完整评测**。
  - `bench_extended_chains.json` 含 **106 条新闻标题**与 11 条 span 元数据；
    DATA.md 提示"标题属合理引用范畴，但如需完全规避风险可自行剔除"。
    **链上 chunk 原文并不在发布文件里**（只有 `n_chunks` 等统计量），
    与 `BENCHMARK.md` 所述"含链上 chunk 原文"不符（见 §7 差异表）。
  - 632 条中 64 条 question 字面重复（doc_id 不同），去重后唯一问题数 568。
  - gold_chunks 分布极度偏斜（97.9% 只有 1 个 gold chunk）→ Recall@10 区分度低。
  - `BENCHMARK.md` 引用的校验缓存路径
    `chain_verify/llm_cache_corups.verify.json` **在仓库中不存在**；
    实际文件是 `data/corpus/llm_cache_corpus.json.verify.json`（且 `data/` 不入库）。
- **许可**：**CC BY-NC-SA 4.0**（`LICENSE` §2 明列 `release/MetaphorRAG-Bench/**`）。

### 2.3 `release/metaphor_shg_release.zip`

- **规模（实测）**：272,697 B / **9** 个条目（= 2.1 的 5 文件 + 2.2 的 4 文件）。
- **保证**：由 `package_release.py` 在本地、无网络、无 LLM 条件下生成；
  内容与 `release/` 下两目录逐文件对应。
- **边界**：**不含 `LICENSE` 与 `DATA.md`** —— 单独分发 zip 时许可条款不随包。
- **许可**：CC BY-NC-SA 4.0（同 2.1 / 2.2）。

---

## 3. 缓存架构

### 3.1 缓存清单与键构造

| 文件 | 字节 | 条数 | 键 | 值 |
|---|---|---|---|---|
| `data/llm_cache_deepseek.json` | 254,540 | **1,100** | CCL2018 测试集原句 | `List[LLMCandidate]` |
| `data/llm_cache_deepseek.json.refine.json` | 467,266 | **3,189** | `[chunk, 源域, 目标域]` | `LLMRefine` 或 `null` |
| `data/llm_cache_train.json` | 943,824 | **4,074** | CCL2018 训练集隐喻句 | `List[LLMCandidate]` |
| `data/llm_cache_paraphrase.json` | 48,274 | **782** | `"{doc_id}|{查询}"` | 改写后问题（str） |
| `data/llm_cache_judge.json` | 116,121 | **571** | `"{doc_id}|{改写问题}"` | `{edge_id: 0/1}` |
| `data/llm_cache_judge.stale_ids.bak.json` | 116,121 | 571 | 同上（uuid4 时代的陈旧副本） | 同上 |
| `data/llm_cache_llmasjudge.json` | 5,653 | **24** | `gen\|meta\|… / gen\|vec\|… / judge\|…` | str / dict |
| `data/llm_cache_packing.json` | 12,533 | **40** | `gen\|{md5(ctx)[:8]}\|{query}`、`judge\|{query}` | str / dict |
| `data/llm_cache_rag.json` | 498 | **2** | `metaphor\|{query}`、`vector\|{query}` | str |
| `data/llm_cache_translate.json` | 32,475 | **14** | `md5(片段)[:12]` | 英文译文（str） |
| `data/llm_cache_bilingual.json` | 20,011 | **835** | 中文域词 | 英文域词（str） |
| `data/gold_audit_cache.json` | 3,069 | **13** | 问题文本 | dict |
| `data/gold_audit_cache_reorder.json` | 11,463 | **50** | 问题文本 | dict |
| `data/corpus/llm_cache_corpus.json` | 1,603,423 | **1,050** | 连贯语料 chunk 原文 | `List[LLMCandidate]` |
| `data/corpus/llm_cache_corpus.json.refine.json` | 3,392,515 | **2,469** | `[chunk, 源域, 目标域]` | `LLMRefine` 或 `null` |
| `data/corpus/llm_cache_corpus.json.verify.json` | 2,115 | **52** | `"{doc}\|{源域}\|{喻底}"` | bool（11 True / 41 False） |
| `data/corpus/chain_judge_cache.json` | 4,503 | **35** | `"{doc}\|{源域}\|{喻底}"` | `{verdict, reason}` |
| `data/corpus/cs_neighbors.json` | 176,083 | **987** | 概念词 | 12 个常识邻居 |
| `data/embed_cache.json` | 22,197,131 | **3,176** | 文本 | 512 维 float 列表 |

- **键的确定性构造（实测）**：
  - **边 id**：`extractor` 用 `"L1_" + md5(span_key)[:8]`、`"F_LLM_" + md5(f"{源域}|{目标域}")[:8]`；
    `extended` 用 `"EXT_" + md5(...)`；`training` 用 `"REF_" + md5(f"{cid}|{src}|{tgt}")`；
    `builder` 级联用 `"C_" + tag + "_" + md5(key)[:8]`；`llm_ontology` 用 `_stable_id`。
    **全部显式避开内置 `hash`**（README §7.5 工程注记：L1 边 id 原为 `uuid4`，
    跨进程对不上号导致 judge 缓存重放时金标全零；已改 md5 并有 `TestDeterministicIds` 护栏）。
  - **LLM 缓存键**：discover 直接以**原文**为键（可读、可审计）；
    refine 以 `(chunk, source_domain, target_domain)` 三元组为键（清洗只删框架/改喻底，
    保留框架的触发通道绑定不变 → 键是原跑的子集）；
    judge/paraphrase 以 `doc_id|文本` 拼接；translate/packing 用 md5 前 8–12 位。
- **保证**：
  - **零成本重放**：discover / refine / 查询改写 / 相关性判定 / 链校验 / 常识关联 / 生成
    全部落盘；命中缓存时**不发出任何请求**（`batch_discover` 实测打印"0 次请求"）。
  - **缓存完整性实测**：`llm_cache_deepseek.json` 的 1,100 个键 = CCL2018 测试集
    1,100 句（**100% 覆盖**）；`llm_cache_train.json` 的 4,074 个键 = 训练集
    4,074 个唯一隐喻句（训练集隐喻句 4,075，去重后 4,074，**0 条遗漏**）。
  - **清洗对照的缓存干净性实测**：三变体（V0 原始 2,185 / V1 清洗全量 2,177 /
    V2 core-only 299）重放，refine 缓存命中 2,128 / 2,125 / 846，**未命中均为 0**。
  - `save_table` / `load_table` 成对使用；`_batch_discover_uncached` 每 10 批写检查点，
    中断可续。
- **边界**：
  - **`data/` 整个目录被 gitignore** → 上述缓存**全部不入库**。零成本重放的保证
    只在本地工作副本成立；干净检出后需要 `LLM_API_KEY` 重跑或另行获取缓存。
  - **缓存键含第三方语料原文**：`llm_cache_deepseek.json`（1,100 条测试集原句）、
    `llm_cache_train.json`（4,074 条训练集原句）。虽不含密钥，但**包含 CCL2018 原文，
    因此一并排除，不得发布**（DATA.md §1 明确点名）。
  - `llm_cache_judge.json` 与 `llm_cache_judge.stale_ids.bak.json` 大小完全相同（116,121 B），
    后者是 uuid4 时代的陈旧副本，**不应用于重放**。
  - 覆盖率**不是全局 100%**：见 §4 的「缓存覆盖率」表。

### 3.2 `data/embed_cache.json` — 真实句向量缓存

- **规模（实测）**：22,197,131 B；`model = "embedding-3"`；`vectors` **3,176** 条；
  **全部 512 维**（无例外、无空值、无重复维度）。
- **schema**：`{"model": str, "vectors": {text: List[float](512)}}`
- **写入方**：`embeddings.OpenAICompatibleEmbedder._save()`；
  读入时校验 `payload["model"] == self.model`，**不匹配则整份缓存丢弃**（安全设计）。
- **保证**：
  - 向量是**确定性资产**：同文本同模型 → 同向量；缓存后重跑零请求。
  - **超边描述命中率 100%**：实测重跑 `experiments/check_embed_cache_coverage.py`，
    "评测**实际嵌入**的唯一文本 1,348 条（边描述 861 次调用）→ 缓存命中 1,348 = **100.00%**，
    未命中 0"。
  - `OpenAICompatibleEmbedder` 有**静默丢批防护**：返回条数 ≠ 请求条数即抛 `EmbedderError`。
- **边界（关键）**：
  - **查询文本命中率 81.9%（519/634）**：实测复现 `evaluate_repaired.build_query_sets`，
    `anchored` 634 条查询命中 519（**81.9%**）、`deanchor` 385 条命中 308（**80.0%**）。
    未命中的 115 条（anchored）/ 77 条（deanchor）**会被脚本跳过** ——
    因此真实向量下的修复版基准**不是全量复测**，只在"查询文本已缓存"的子集上测
    （`evaluate_repaired_real.py` docstring 显式声明）。
  - 缓存 3,176 条中，仅 **1,310 条**（41.2%）属于"边描述 ∪ anchored 查询 ∪ deanchor 查询"
    这 1,425 条评测必需文本；**其余 1,866 条**是其他阶段的文本（样例含 CCL2018 原句
    "山坡上，大路边，村子口…"、"她是我的太阳。"等），**不在上述三集合内**。
  - 全量复测需 `EMBED_API_KEY` 重取 115 条查询向量。

### 3.3 缓存覆盖率（离线重放边界）

| 阶段 | 缓存 | 覆盖 | 离线可否 | 缺口 |
|---|---|---|---|---|
| discover（测试集建图） | `llm_cache_deepseek.json` | **1,100/1,100 = 100%** | ✅ 零请求 | — |
| discover（训练集建本体） | `llm_cache_train.json` | **4,074/4,074 = 100%** | ✅ 零请求 | — |
| refine（测试集） | `llm_cache_deepseek.json.refine.json` | 3,189 条；清洗三变体实测**未命中 0** | ✅ 零请求 | 键为子集，新增框架需补取 |
| refine（连贯语料） | `llm_cache_corpus.json.refine.json` | 2,469 条 | ✅ 零请求 | 同上 |
| 查询改写 gen | `llm_cache_paraphrase.json` | **782** 条（覆盖 110 个 fc 文档） | ✅ 零请求 | 861 自动查询 → 782 有改写 |
| 相关性判定 judge | `llm_cache_judge.json` | **571** 条（覆盖 108 个 fc 文档） | ✅ 零请求 | 782 改写 → 571 有判定 |
| 链校验 verify | `llm_cache_corpus.json.verify.json` | **52/52 = 100%**（11 通过 / 41 剔除 = 21.1%） | ✅ 零请求 | 仅连贯语料的 52 条候选链 |
| 常识关联 | `cs_neighbors.json` | **987** 概念词 | ✅ 零请求 | A6 口径需 733 个概念词 |
| 向量（超边描述） | `embed_cache.json` | **1,348/1,348 = 100%**（边描述 861 次调用） | ✅ 零请求 | — |
| **向量（查询文本）** | `embed_cache.json` | **519/634 = 81.9%**（anchored）<br>**308/385 = 80.0%**（deanchor） | ⚠️ **仅子集** | **115 / 77 条查询被跳过** |
| 论文翻译 | `llm_cache_translate.json` | 14 个分片 | ✅ 零请求 | 仅论文正文 |
| 双语域词典补全 | `llm_cache_bilingual.json` | 835 个域词 | ✅ 零请求 | **该文件在 `data/` 下，不入库** |
| 人工评估预演 | `llm_cache_llmasjudge.json` | 24 条 | ✅ 零请求 | 2 文档小集 |
| 上下文打包消融 | `llm_cache_packing.json` | 40 条 | ✅ 零请求 | 2 文档小集 |
| 端到端 RAG demo | `llm_cache_rag.json` | 2 条 | ✅ 零请求 | 仅 demo |
| 金标交叉审核 | `gold_audit_cache*.json` | 13 + 50 条 | ✅ 零请求 | 抽样 |

**结论**：
- **完全可离线重放**（0 次 API 调用）：全部 LLM 阶段 + 超边描述向量。
- **需要 `EMBED_API_KEY`**：真实句向量下的**全量**查询复测（缺 115 条查询向量）。
- **需要 `LLM_API_KEY`**：从零重建本体、双语词典、连贯语料建图，
  或任何超出上述缓存键集合的新输入。

### 3.4 语料缓存（`data/corpus/`，不入库）

| 文件 | 字节 | 内容（实测） |
|---|---|---|
| `chunks.jsonl` | 1,482,443 | **1,050** 行；字段 `{doc_id, chunk_id, source, title, chunk_index, text}` |
| `luxun_quanji.txt` | 1,843,308 | 鲁迅全集，625,889 字符（UTF-8 BOM） |
| `gov_reports.json` | 3,370,582 | 55 篇政府工作报告池（实际使用 6 篇） |
| `caijing_news.json` | 742,673 | 150 篇人民网财经池（实际使用 40 篇） |
| `l15_results.json` | 25,987 | 106 篇文档建图结果（`n_chunks / n_l1 / n_ext / spans`） |
| `cs_neighbors.json` | 176,083 | 987 概念词的常识邻居 |
| `_gov_links.json` | 6,957 | 55 条政府工作报告 URL |

- **实测文档构成**：106 篇 = 人民网财经 **40** / 鲁迅全集(公版) **60** / 维基文库政府工作报告 **6**；
  chunk 分布 lx 632 / gov 240 / cj 178；Σn_chunks = **1,050**、Σn_l1 = **822**、Σn_ext = **11**。
- **保证**：语料取自公开渠道（新闻/维基文库/公版全集）；分块规格 500 字 + 10% 重叠。
- **边界**：
  - `data/` 不入库 → 语料与建图结果**均不可从仓库复现**，只能按 DATA.md §1 自行获取。
  - 人民网财经池 150 篇中只用了 40 篇，政府工作报告池 55 篇中只用了 6 篇 ——
    池与用量差**未在文档中说明选取规则**。
  - `_ec_probe.json`（15,176,197 B）**不是合法 JSON**（实测 `JSONDecodeError` at char 15066596），
    为损坏的中间产物。
- **许可**：**不入库、不发布**。CCL2018（大连理工 DUTIR）仅限学术研究、禁止商业用途；
  人民网新闻为新闻媒体版权；政府工作报告与鲁迅全集虽属公版，但"为一致性一并排除"（DATA.md §1）。

---

## 4. 外部依赖接口

### 4.1 `metaphor_graph/llm_backend.py`（914 行）

- **Protocol 契约**（`runtime_checkable`）：

  ```python
  class MetaphorLLMBackend(Protocol):
      def discover(self, chunk: str) -> List[LLMCandidate]: ...
      def refine(self, chunk: str, frame: FrameSpec) -> Optional[LLMRefine]: ...
      def cluster(self, edges) -> Optional[dict]: ...
  ```

- **数据类型**：

  ```python
  LLMCandidate = {source_domain, target_domain,
                  ground: List[str] = [], triggers: List[str] = [],
                  confidence: float = 0.6}       # 实测落盘字段恰为这 5 个
  LLMRefine    = {is_metaphor: bool, confidence: float = 0.6,
                  ground: List[str] = []}
  ```

  > 注：提示词 `_FIELDS_SPEC` 要求模型额外输出 `basic_meaning`（"该喻体词的基本义"），
  > 这是**刻意的**——逼模型先确认"基本义 ≠ 语境义"再下结论，等价于让它走一遍 MIPVU 判据，
  > 实测能明显压掉固化成语类误判。但该字段**不被 `LLMCandidate` 采集**（构造时丢弃），
  > 因此**不落盘、不可审计**。

- **四个实现**：

  | 后端 | 密钥 | 行为 | 边界 |
  |---|---|---|---|
  | `OpenAIBackend` | `LLM_API_KEY` | OpenAI 兼容 `/chat/completions`，标准库 `urllib`；`temperature=0.0`、`timeout=20.0`；累计 `usage`（含 `prompt_cache_hit_tokens`）；支持 `discover_batch` / `refine_batch` | 无密钥时 `_chat` 返回 `None`（记 warning 跳过，**不崩**）；401/402/403 → `LLMFatalError`（不重试不降级） |
  | `LocalHeuristicBackend` | 无 | 离线确定性近似（等比结构挖掘 + 本体/语义域绑定） | 需 jieba |
  | `PrecomputedBackend` | 无 | 消费 `precompute_all()` 的落盘结果 | `refine_table` 为 `None` 时回落 `LLMRefine(is_metaphor=True, confidence=0.6)` —— **默认判为隐喻** |
  | `MockBackend` | 无 | 单测用，返回预置结果 | — |

- **环境变量约定**（`OpenAIBackend`）：
  - `LLM_API_KEY`（必需，代码不硬编码任何密钥）
  - `LLM_BASE_URL`（可选，默认 `https://api.openai.com/v1`）
  - `LLM_MODEL`（可选，默认 `gpt-4o-mini`）
  - 优先级：**显式参数 > 环境变量 > 默认值**
  - 另有 `extra_body` 透传厂商私有参数（如 GLM-5.3 的 `{"reasoning_effort":"low"}`）

- **保证**：
  - **失败纪律**（`_FATAL_HTTP_CODES`）：401（Key 无效）/ 402（欠费）/ 403（无权限）
    → `LLMFatalError`，**刻意不被 `except Exception` 吞掉**。文档记录的踩坑：
    DeepSeek 402 曾被优雅降级吞成空结果，导致域归并返回 100% 恒等映射、本体碎片化，
    而流程"一路成功"。
  - **批量化降本**：实测 CCL2018 句子中位数仅 15 字，而单次调用样板提示 321 字，
    逐句调用 91% 输入 token 是样板；20 句/批可省 86%。
  - **MIPVU 排除规则内嵌**：去掉它时模型会把固化成语、描写性美称、拟人判成隐喻，
    CCL2018 全量 P1 飙到 28.9%（门槛 15%）。
  - **`verify_chains_batch` 的失败纪律**：整批解析失败重试一次，仍失败则该批
    **不写入缓存**并在返回值中缺失 —— 调用方必须把"缺失"当未校验，不得当通过。
  - `_parse_json_blob` 容错解析：整段 `json.loads` 失败则回退抽取首个 `[...]` 或 `{...}` 子串。
- **边界**：
  - `discover` 的 `ground` / `triggers` 是**模型自由文本**，与本体的规范标签几乎不会字符串
    相等 —— 需 `extractor._frame_for_candidate` 的模糊匹配（子串包含）兜底。
  - `cluster()` 在生产路径上**基本不用**（L2/L3 走本体查表）。
  - `PrecomputedBackend` 在 `refine_table is None` 时**默认判为隐喻**（`is_metaphor=True`），
    这是一个宽松默认值，误用会抬高召回并压低精度。
- **许可**：MIT（`LICENSE` §1）。

### 4.2 `metaphor_graph/embeddings.py`（307 行）

- **全局可插拔接口**：

  ```python
  set_embedder(fn: Optional[Callable[[str], List[float]]], propagate: bool = True) -> None
  get_embedder() -> Optional[Callable[[str], List[float]]]
  embed(text: str, dim: int = DIM) -> List[float]      # DIM = 512
  cosine(a, b) -> float
  embedder_from_env() -> Optional[OpenAICompatibleEmbedder]
  ```

- **两个编码器 + 一个客户端**：

  | 名称 | 依赖 | 行为 |
  |---|---|---|
  | 默认 `embed()` | 无 | char 1–2 gram 哈希桶 + L2 归一化（**已上报数字的口径**） |
  | `NgramEmbedder(dim=512, max_n=3, signed=True)` | 无 | 1–3 gram + **符号哈希**（按 hash 高位定 ±1，降低碰撞正偏置）；opt-in 变体，**未转正** |
  | `OpenAICompatibleEmbedder` | `EMBED_API_KEY` | OpenAI 兼容 `/embeddings`；`batch_size=32`、`timeout=60.0`；磁盘缓存；`dimensions` 支持降维 |

- **环境变量约定**（`embedder_from_env`）：
  - `EMBED_API_KEY`（必需；未设返回 `None`，**不报错**）
  - `EMBED_BASE_URL`（默认智谱 `https://open.bigmodel.cn/api/paas/v4`）
  - `EMBED_MODEL`（默认 `embedding-3`）
  - `EMBED_DIMENSIONS`（默认 `512`，**须与 `embeddings.DIM` 一致**，HGNN 矩阵依赖）
  - `EMBED_CACHE`（默认 `<项目>/data/embed_cache.json`）
  - 回落链：`EMBED_BASE_URL` → `LLM_BASE_URL` → `""`
- **保证**：
  - **`propagate` 语义明确**：`propagate=True`（默认）把 semfield 的独立 embedder 槽位一并设置；
    **检索层实验必须传 `propagate=False`** —— semfield 会改变抽取候选
    （`incongruity_score` 换语义相似度），冻结抽取管线才能把"句向量增益"隔离在检索/排序层。
  - **失败纪律**：401/402/403 → `EmbedderFatalError`（不降级不重试）；
    网络/解析错误 → `EmbedderError`，**是否回退哈希向量由调用方决定**，
    本模块不替调用方做"安静退回哈希向量"的决定。
  - 注入的 embedder 抛出的异常**原样上抛**（无静默回退）。
  - 缓存模型不匹配则整份丢弃（`payload.get("model") == self.model` 校验）。
- **边界**：
  - 默认哈希编码器**是玩具级**：无预训练语义，`README` 明确"生产环境请替换"。
  - `NgramEmbedder` 未转正：全部已上报数字（P4-B 0.950 / 全量基准 0.998 等）
    基于默认哈希编码器；换默认必须重测全部数字。
  - 真实向量结果基于**单一厂商单模型**（智谱 embedding-3），转正前需统一重测
    （DATA.md §5 边界 1）。
  - `set_embedder` 是**全局可变状态**：多实验并行会互相污染。
- **许可**：MIT（`LICENSE` §1）。

### 4.3 `metaphor_graph/download_datasets.py`（51 行）

- **签名**：`main()`；`_run(cmd)` 内部用 `subprocess.run(cmd, shell=True, check=False)`。
- **行为**：
  1. `git clone --depth 1 https://github.com/DUTIR-Emotion-Group/CCL2018-Chinese-Metaphor-Analysis.git`
     → `data/CCL2018-Chinese-Metaphor-Analysis`（已存在则跳过）；
     含 `dataset/subtask1-metaphor-recognition/{train.xml, test.xml, test_with_label.csv}`
     与 subtask2 全套。
  2. **打印**（不自动下载）英文 VUA 的三条获取路径：
     `EducationalTestingService/metaphor`、Zenodo `records/10721623`、`linahmoh/MelBERT`。
- **保证**：幂等（目录已存在则跳过克隆）；`check=False` → 克隆失败不中断流程。
- **边界**：
  - **英文基准不会被下载**，只打印说明；且文档明示"当前中文抽取器对英文召回≈0"，
    需补英文本体或接 LLM 后端。
  - `check=False` 意味着**克隆失败会被静默忽略**，需人工核对。
  - CCL2018 的 README 声明：子任务一训练集 **4,394** 句 / 测试集 **1,100** 句。
- **许可**：MIT（代码）。**下载的数据不受本仓库许可覆盖**，版权归原作者，
  仅限学术研究、禁止商业用途。

---

## 5. 存储接口

### 5.1 `metaphor_graph/neo4j_schema.cypher`（85 行）

- **内容**：6 个索引 + 5 个唯一约束 + 6 个查询模板。
- **节点标签**：`:Domain`（端点）/ `:MetaphorMapping`（L1 超边，layer 1 或 1.5）/
  `:MetaphorFrame`（L2）/ `:MetaphorCascade`（L3）/ `:Chunk`。
- **关系类型**：

  ```
  (Mapping)-[:HAS_SOURCE]->(Domain)
  (Mapping)-[:HAS_TARGET]->(Domain)
  (Mapping)-[:HAS_GROUND]->(Domain)     # 喻底集合 = 超边多端点语义的来源
  (Mapping)-[:IN_FRAME]->(Frame)
  (Frame)-[:IN_CASCADE]->(Cascade)
  (Mapping)-[:SPANS]->(Chunk)           # 可跨多 chunk（L1.5）
  (Mapping)-[:SUPPORTED_BY]->(Evidence) # storage.py 实现中存在
  ```

- **建模契约**：一条 L1 超边 = **一个 `:MetaphorMapping` 节点** + 多条关系，
  以此在属性图里表达「n 元 / 喻底集合」的超边语义。
- **6 个查询模板**：跨域检索 / 多线索汇聚 / 沿级联下钻 / 扩展隐喻跨 chunk 召回 /
  **喻底交集**（依赖 `HAS_GROUND`，是扩展隐喻合并判据第三条） / 证据链溯源与冲突消解。
- **保证**：唯一性约束是 MERGE 幂等写入的前提；无约束时增量摄入会退化成"每次都新建"。
- **边界**：
  - **模板 3 有缺陷**：`MATCH (c:MetaphorCascade {name:'PROGRESS_IS_JOURNEY'})` 按 `name`
    匹配，但生产本体的级联 name 形如 `LLM_TARGET::下属`（`C_LLM_*`），
    **不存在** `PROGRESS_IS_JOURNEY` 这样的名字 —— 该模板对生产本体无效。
  - 类型安全约束段（`:Domain)-[:OF_TYPE]->(:DomainType)`）**只有注释与示例，无实际语句**；
    等价逻辑在 `ontology.TYPE_CONSTRAINTS` 里，未落成图约束。
  - 模板 6 引用 `:Evidence`，而 `neo4j_schema.cypher` 的节点标签清单**未列** `:Evidence`
    （实际由 `storage.shg_to_cypher` 创建）。
  - 未声明 `:Chunk` 的 `doc_id` 索引。
- **许可**：MIT（`LICENSE` §1）。

### 5.2 `metaphor_graph/storage.py`（291 行）

- **导出接口**：

  ```python
  constraints_cypher() -> List[str]                       # 5 唯一约束 + 2 索引
  shg_to_cypher(shg: MetaphorSHG, with_constraints=True) -> List[str]
  shg_to_json(shg: MetaphorSHG, path: str)
  class Neo4jFatalError(RuntimeError)                     # 401/403
  class Neo4jError(RuntimeError)                          # Cypher/网络/格式
  class Neo4jStore(uri="http://127.0.0.1:7474", user="neo4j",
                   password="", database="neo4j",
                   batch_size=200, timeout=60.0)
      execute(statements: List[tuple]) -> List[list]
      run(cypher, params=None) -> list
      load_shg(shg, with_constraints=True) -> int          # 返回写入语句数
      clear()
      counts() -> dict                                     # {label: n}
  ```

- **保证**：
  - **幂等**：全部写入用 `MERGE` + 唯一性约束，可重复导入。文档记录旧实现全用 `CREATE`
    会产生重复节点，且 `:Domain` 端点节点从未被创建（`MATCH` 不到 → 关系全建不出来）；
    本版修复并补齐 `HAS_GROUND`。
  - **零额外依赖**：走 Neo4j **HTTP 事务端点** `POST /db/{db}/tx/commit`，标准库 `urllib` 直连，
    不需要官方 python driver。
  - **schema 与数据分事务**（硬约束）：Neo4j 禁止在同一显式事务里先做 schema 修改再写数据
    （`Neo.ClientError.Transaction.ForbiddenDueToTransactionType`）——
    "真库联测抓出，mock 测不到"。约束/索引逐条独立事务，数据按 `batch_size` 分批。
  - **失败纪律**：401/403 → `Neo4jFatalError`（不重试不降级）；
    事务 `errors` 数组非空 → `Neo4jError`（带 Neo4j 的 code 与 message）；
    **是否回退 JSON 导出由调用方决定，本类不做静默回退**。
  - **转义**：`_esc()` 处理反斜杠与单引号（防域/喻底含引号导致 Cypher 语法错误）。
  - `execute([])` 是 no-op（返回 `[]`），不浪费 HTTP 往返。
- **边界**：
  - `shg_to_cypher` 的 `ground` 写入为 **JSON 数组属性 `m.ground`**，
    **同时**为每个喻底建 `HAS_GROUND` 关系 —— 双写，存在不一致风险（关系是权威）。
  - `Neo4jStore` **无连接池、无重试**；单条 `run()` 每次一个新 HTTP 请求。
  - `counts()` 用 `MATCH (n) RETURN labels(n)[0]` —— 只取**第一个标签**，
    多标签节点会被归并到任一标签。
  - 无认证信息的环境变量约定：`uri`/`user`/`password` 全为显式参数，
    与 `llm_backend`/`embeddings` 的"环境变量 + 优雅降级"模式不同。
- **许可**：MIT（`LICENSE` §1）。

### 5.3 `metaphor_graph/export_shg.cypher` + `export_shg.json`

- **规模（实测）**：`export_shg.cypher` **250 条语句**（无末行换行，`wc -l` 报 249）；
  7 `CREATE` 约束/索引 + 119 `MATCH` + 124 `MERGE`；
  `export_shg.json` 16,514 B / 730 行。
- **内容（实测）**：12 条 L1 边（10 条 `layer=1` + 2 条 `layer=1.5`）、
  8 个框架、5 个级联；文档 `demo_doc`（`demo_doc_c0` / `demo_doc_c1`）。
  框架 id：`F_PROG_JOURNEY / F_OBST_TERRAIN / F_LIFE_MACHINE / F_COMP_WAR /
  F_ARG_WAR / F_ANGER_HEAT / F_EMO_CONT / F_MIND_CONT`；
  级联 id：`C_PROGRESS_JOURNEY / C_LIFE_MACHINE / C_ARG_WAR / C_ANGER_HEAT / C_MIND_CONTAINER`。
- **保证**：
  - 是 `storage.shg_to_cypher` 的**实际输出样例**（可对照验证导出格式）。
  - 使用**手工种子框架**（`F_ARG_WAR` 等来自 `ontology.py` 内置 20+ 框架），
    不是自举本体，故 id 无 `F_LLM_` 前缀。
  - `m.description` 字段由 `MetaphorHyperedge.describe()` 生成自然语言
    （借鉴 HyperGraphRAG：超边必须渲染成自然语言才能参与向量检索）。
- **边界**：
  - **仅为 12 边的样例**，不是全量导出（生产图有 856 条 L1 边）。
  - 含**重复语句**（如 `MERGE (ch:Chunk {id:'demo_doc_c1'})` 出现两次）——
    源于同一 chunk 上有两条超边，`MERGE` 使其幂等，但文件冗余。
  - 行尾带分号，**不能直接喂给 Neo4j HTTP 事务端点**（`Neo4jStore.load_shg` 会 `rstrip(";")`）。
- **许可**：MIT（`LICENSE` §1）。

---

## 6. 数据契约

### 6.1 `MetaphorHyperedge`（`metaphor_graph/models.py`，268 行）

- **字段与语义**：

  ```python
  @dataclass
  class MetaphorHyperedge:
      id: str
      source_domain: str          # 源域（如：金钱 / 泥潭 / 发条）
      target_domain: str          # 目标域（如：时间 / 项目困境 / 生活状态）
      ground: List[str]           # 喻底集合 ← 超边性的来源
      triggers: List[str]         # 触发词列表（L0）
      chunk_spans: List[ChunkSpan] = []
      cascade_id: Optional[str] = None       # → L3
      frame_id: Optional[str] = None         # → L2
      novelty: str = "conventional"          # conventional / novel
      sentiment: Dict[str, float] = {}       # 受 EmoBi 启发
      confidence: float = 0.0
      source_type: str = "UNKNOWN"
      provenance_reliability: float = 1.0    # ∈[0,1]，默认 1.0
      is_extended: bool = False              # 是否为 L1.5 合并的跨 chunk 超边
      layer: int = 1                         # 1 = L1；1.5 = 扩展
      evidence: List[Evidence] = []
      extractor_version: str = "1.0.0"
      deprecated: bool = False               # 软删除：保留溯源链，不参与检索
  ```

- **不变量（实测/代码级）**：
  1. **`ground` 是集合而非单值** —— 这是"超边性"的来源：一条超边同时连接多个端点，
     且端点之间不存在两两语义关系，与普通三元组有本质区别。
     `member_entities = [source_domain, target_domain] + list(ground)`。
     实测生产本体：3,301 个喻底槽位 / 2,282 唯一，25 个框架 0 喻底
     （空喻底在 `describe()` 里渲染为"（未抽取到喻底）"）。
  2. **`provenance_reliability` 默认 1.0**：历史构造点（手工建边、旧序列化数据）不受影响。
     `provenance.edge_reliability()` 采信 `min(存储值, 本体现算值)` ——
     **只允许更保守，防伪升级**。
  3. **`deprecated` 是软删除**：保留溯源链但不参与检索（`resolve_conflict` 先过滤 `deprecated`）。
  4. **跨 `extractor_version` 的 `confidence` 不可比** —— 因此 `resolve_conflict`
     **刻意不直接使用 `confidence` 作为决胜依据**，避免度量口径漂移污染消解结果。
  5. **`layer` 用 `int` 类型标注但取值为 1 / 1.5**（`extended.link_extended_metaphors`
     写入 `layer=1.5`）—— 类型标注与取值不一致，见 §7 差异表。
- **`describe()` 契约**（供向量化与生成上下文）：

  ```
  f"{source_domain}→{target_domain}：把{target_domain}比作{source_domain}，"
  f"强调{grounds}。触发词：{trig}。"
  ```

  其中 `grounds = "、".join(ground)`（空则"（未抽取到喻底）"），
  `trig = "、".join(triggers[:5])`（空则"（无）"）—— **触发词只取前 5 个**。
- **辅助接口**：`member_entities`、`describe()`、`authority()`（无证据回落 0.5）、
  `support()`（独立 chunk_id 数，**下限 1**：`len(...) or 1`）、`to_dict()`。
- **冲突消解**（`resolve_conflict(edges, strategy, now, half_life_days=365.0)`）：
  `authority` / `recent` / `vote` / `hybrid`（默认 = 权威度 × 时间衰减 × log1p(票数)）。
- **许可**：MIT（`LICENSE` §1）。

### 6.2 其余数据模型

```python
Evidence(chunk_id, doc_id="doc0", timestamp=time.time(),
         authority=0.5, extractor_version=EXTRACTOR_VERSION, snippet="")
    # 为什么不是单个 confidence 标量：标量只能回答"这次抽取有多确定"，
    # 回答不了"两条矛盾的映射信哪个"。证据链让超边可被审计/比较/消解。
ChunkSpan(chunk_id, start, end, text, doc_id="doc0")   # 字符偏移，便于高亮与溯源
MetaphorFrame(id, name, member_mapping_ids=[], source_frame="", target_frame="", layer=2)
MetaphorCascade(id, name, member_frame_ids=[], discourse_domains=[], typical_triggers=[], layer=3)
MetaphorSHG(edges=[], frames=[], cascades=[])  # .incidence 属性 → (H, nodes) 关联矩阵
RetrieverResult(chunk_ids, scores, trace="", path=[])
```

- **`EXTRACTOR_VERSION = "1.0.0"`**（模块级常量）：每条超边都记录产出它的版本，
  冲突消解与 A/B 对比**只在同一版本内进行**。
- **`MetaphorSHG.incidence`** 延迟导入 numpy（避免无 numpy 时崩溃）。
- **许可**：MIT。

### 6.3 `chunk_id` 命名约定

| 场景 | 格式 | 来源 |
|---|---|---|
| 建图（规范） | `f"{doc_id}_c{i}"`，i 从 0 起 | `builder.py:60`、`retrieval.py:60` |
| 抽取器缺省 | `f"{doc_id}_c{uuid.uuid4().hex[:4]}"` | `extractor.py:172` |
| CCL2018 伪文档 | `fc{di}_c{i}`，di 0–109，每组 10 句 | `evaluate_*.py` |
| 连贯语料 | `cj{n}_c{i}` / `gov{n}_c{i}` / `lx{n}_c{i}` | `chunks.jsonl` |
| 诊疗集基准 | `fc0_c0`…（`bench_docs` 用 `doc_project` / `doc_relationship`） | `eval_corpus.py` |
| Neo4j | `:Chunk {id: chunk_id}` + `doc_id` 属性 | `storage.py` |

- **保证**：`chunk_id` 是 `SPANS` 关系与 L1.5「跨 chunk」判断的唯一依据；
  `ChunkSpan.start/end` 是**字符偏移**（不是字节、不是 token）。
- **边界**：
  - `extractor.py` 的**默认值用 uuid4** → 若调用方不显式传 `chunk_id`，
    id 不可复现。生产路径都显式传，但这是**默认值级别的隐患**。
  - `fc10` / `fc11` 在 `bench_queries.json` 中**不存在**（其余 fc0–fc109 齐全）——
    这 2 个伪文档无任何查询。
  - `doc_id` 与 `chunk_id` 用 `_c` 分隔；**若 `doc_id` 本身含 `_c`，解析会歧义**
    （`evaluate_document_corpus.py:204` 用 `chunk_id.split("_c")[-1]` 取索引）。

### 6.4 层号约定

| 层 | 名称 | 载体 | `layer` 取值 | 实测规模 |
|---|---|---|---|---|
| **L0** | 触发词层 | 语言形式（"失血""泥潭""发条"） | — | 本体 895 触发词槽 / 606 唯一 |
| **L1** | 映射层 | 隐喻超边（源域, 目标域, 喻底集合, 触发词列表） | `1` | 全量图 **856** 条（CCL2018）；连贯语料 822 条 |
| **L1.5** | 扩展层 | 跨 chunk 合并的超边（`is_extended=True`） | `1.5` | CCL2018 **5** 条；连贯语料 **52** 条候选 → 校验后 **11** 条 |
| **L2** | 框架层 | 一般隐喻 = 超顶点（L1 超边的集合） | `2` | 本体 **2,177** 框架 |
| **L3** | 级联层 | 隐喻级联 = 超超顶点（L2 框架的集合） | `3` | 本体 **733** 级联 |

- **L1.5 合并判据**（`extended.link_extended_metaphors`）：同框架 + 同源域 + chunk 距离 < 3
  + 喻底交集 ≥1。`continuity` 参数：
  - `"ground1"`（原口径）：喻底交集 ≥1
  - `"vehicle_repeat"`：喻底交集 ≥1 **且**（同一触发词跨 chunk 词面复现 或 喻底交集 ≥2）
- **保证**：层级同构 `Cascade(L3) → Frame(L2) → Mapping(L1)` 严格对应。
- **边界（重要）**：
  - **L2/L3 覆盖率存在两个口径**：
    - **报出口径 100%**（每条边都有层级归属）
    - **诚实口径 82.4%**（归属是否来自本体）—— 实测 120 句子集：108 条超边中
      只有 82.4% 挂在本体正式登记的框架上；其余挂在抽取器为未知喻体临时建的
      回退框架上，靠 `builder._ensure_cascades` 按目标域**事后补建**的 `C_ADHOC_*`
      级联才够到 100%（19/108 条回退边，19/89 个级联为事后补建）。
      **82.4% < P2 的 85% 门槛**。
  - **`C_ADHOC_*` 级联与本体级联结构同构**（都按目标域打包）→ 跨域扩展能力为零。
    gen2 实测：110 次 build 共补出 **399** 个 distinct `C_ADHOC_` 级联，**size 中位数 1、max 1**；
    唯一量化收益是 `cascade_coverage` 从 **0.767** 抬到 **1.000**（关掉它即跌破 >0.85 门槛）。
    更关键的是：**这些补建的级联不回写 `edge.cascade_id`** ——
    实测 `edge.cascade_id` 以 `C_ADHOC_` 开头的边数 = **0**。
    → 论文/README 的"cascade 查表将覆盖率提升至 100%"**归因不准确**：
    本体级联查表单独贡献 **0.767**，`builder._ensure_cascades` 的目标域兜底打包贡献剩下 **0.233**。
    成本主张（~20 次/千边 vs ~187 次）不受影响（兜底也是查表式、零 LLM 调用）。
    替代规则见 `cascade_rules` 模块（`orphan_cascade_rule=` 参数）。
  - **L1.5 的 `layer=1.5` 与 `int` 类型标注冲突**（`models.py` 声明 `layer: int = 1`）。
  - **层级价值已证伪**：跨层传播在检索（P4-A）与检测（H4）两个口径下均无增益；
    应改述为"检索组织/可解释性"而非信号本身。
  - **L1.5 密度与质量**：连贯语料扩展链密度 **6.3 条/百 L1**、**30%（32/106）文档含链**；
    但严格 MIPVU 口径链精度仅 **16.7%**，双段管线（生成候选 → 语义校验过滤）后
    **63.6%（7/11）**。**`l15_results.json` 中的 11 条是校验后存活链，
    不是 52 条候选链** —— 见 §7 差异表。

### 6.5 `Evidence` / 溯源可靠性契约

- **`provenance.py`（95 行）常量**：

  ```python
  RELIABILITY_ONTOLOGY      = 1.0    # 本体登记框架（人工种子 或 自举回流沉淀）
  RELIABILITY_FALLBACK_CAP  = 0.5    # 抽取器临时框架，本体无条目 —— 显式封顶
  RELIABILITY_FLOOR         = 0.5    # 打分层的下界
  RELIABILITY_FLOOR_OFF     = 1.0    # 关闭该通道（历史口径的精确复原开关）
  ```

- **接口**：`frame_reliability(ontology, frame_id)` / `frame_provenance(...)` /
  `edge_reliability(edge, ontology)` / `reliability_factor(reliability, floor)`。
- **保证**：
  - **是"封顶折扣"，不是过滤器**：任何候选都不会因此消失，召回结构完全不变。
  - **用乘性因子而非加性 bonus**：加性 bonus 只改绝对值不改相对次序（两项加同一常数），
    对排序无效；乘性因子按可靠性缩放分数才能真正改变次序，同时因 `floor > 0` 永不归零。
  - 无 ontology 可查时返回 1.0（信息不足时不做无根据的降级）。
- **边界**：`reliability_factor` 的 `floor` 默认 0.5 → 该通道**最多只能把分数压到一半**；
  要完全关闭需显式传 `RELIABILITY_FLOOR_OFF`。
- **许可**：MIT。

---

## 7. 许可与合规

### 7.1 分项许可结构（`LICENSE`，3,390 B）

| 条款 | 适用范围 | 许可 |
|---|---|---|
| **§1 代码** | `metaphor_graph/` 下全部 `.py` + 仓库根构建/脚本文件 | **MIT** |
| **§2 本体资源与基准** | `ontology_default.json`、`ontology_bilingual.json`、`bootstrap_triggers.json`、`llm_ontology_train.json`、`release/metaphor_resources/**`、`release/MetaphorRAG-Bench/**` | **CC BY-NC-SA 4.0** |
| **§3 论文与文档** | `论文初稿.md`、`论文初稿_en.md`、`知识隐喻分析任务方案.md`、`效果对比.md`、`论文表述改写.md`、`README.md`、`DATA.md`、`后续待办.md` | **CC BY 4.0** |
| **§4 未包含的第三方内容** | CCL2018、人民网新闻等 | 不受本仓库许可覆盖，遵循原始条款 |

### 7.2 为什么这样分

- **为什么本体是 NC（非商业）**：`ontology_default.json` 由 **CCL2018 中文隐喻识别评测数据集
  （大连理工 DUTIR）的训练集**经 LLM 自举构建，**属评测数据的派生作品**。
  CCL2018 自身声明**仅限学术研究、禁止商业用途** → 其派生资源沿用非商业口径。
- **为什么本体是 SA（相同方式共享）**：如修改并再分发本体，须以相同条款共享。
- **为什么代码可以是 MIT 而本体不能**：代码是独立实现（`LICENSE` §4 声明
  MetaNet / HGNN / HyperRAG / MedGraphRAG / HL-index 等引用方法版权归各自作者，
  本仓库仅含独立实现），不派生自 CCL2018；本体是数据派生作品，受上游约束。
- **为什么论文可以是 CC BY（无 NC）**：论文是独立著作，不含语料原文
  （仅 1 条单句引用，见 7.4）。

### 7.3 语料许可与排除

| 语料 | 规模（实测） | 许可状态 | 能否随仓库分发 |
|---|---|---|---|
| CCL2018 子任务一 | 测试集 **1,100** 句 / 训练集 **4,394** 句（其中隐喻句 4,075） | 大连理工 DUTIR 评测共享任务，**仅限学术研究** | ❌ 否 |
| 人民网财经新闻 | 池 150 篇，实际用 **40** 篇 | 新闻媒体版权 | ❌ 否 |
| 政府工作报告 | 池 55 篇，实际用 **6** 篇（维基文库） | 公版 | ⚠️ 可，但为一致性一并排除 |
| 鲁迅全集散文 | **60** 篇（公版） | 公版 | ⚠️ 可，但为一致性一并排除 |

- **`.gitignore` 排除整个 `data/`**，理由是**许可，不是体积**。
- **关键点**：`data/llm_cache_deepseek.json` 的缓存**键就是 CCL2018 测试集原句**
  （实测 1,100 条），`data/llm_cache_train.json` 的键是训练集原句（实测 4,074 条）。
  这些文件虽不含密钥，但**包含第三方评测数据集的原文，因此一并排除，不得发布**。
- **已做的合规清理**：`test_metaphor_graph.py`、`demo_llm.py` 等文件中原有的
  示例句已替换为**人工构造的等价句**（功能完全一致）。
- **自行获取方式**：`python -m metaphor_graph.download_datasets`（见 §4.3）。

### 7.4 论文中的语料引用（实测核验）

- DATA.md 声明：`论文初稿.md` / `论文初稿_en.md` 各含 **1 条** CCL2018 测试集句子，
  作为说明"标注存疑"的**单句引用示例**。
- **实测核验**：精确整句匹配 0 条；按 ≥10 字符片段匹配，`论文初稿.md` 命中 **1 条**
  （`王华英（潘汉年饰演者）：扮演潘汉年，时时处处感到有千百万双眼睛犹如千百万台
  摄影机在对我聚焦…` 的片段 `千百万双眼睛犹如千百万台摄影机`）。
  → **声明与实测一致**（片段引用，非整句引用）。

### 7.5 发布物中的许可缺口

- `release/metaphor_shg_release.zip`（272,697 B / 9 条目）**不含 `LICENSE` 与 `DATA.md`**；
  单独分发 zip 时许可条款不随包。
- `release/metaphor_resources/DATASET_CARD.md` 只写"语料与本体仅供研究使用"，
  **未写 CC BY-NC-SA 4.0 全称**，也未指向仓库 `LICENSE`。
- `release/MetaphorRAG-Bench/BENCHMARK.md` **完全未提许可**。
- `LICENSE` §2 的清单**未包含** `metaphor_graph/llm_ontology.json`
  与 `metaphor_graph/ontology_metanet_seeds.json`（同族产物，按口径应同归）。
- `.licenses/` 下有 2 份第三方服务条款记录
  （`literature_search_arxiv_LICENSE.txt` 443 B、`literature_search_openalex_LICENSE.txt` 318 B），
  与本体/基准无关，记录的是文献检索工具的 API 使用条款。

---

## 8. 缓存覆盖率

### 8.1 离线重放边界

| 能力 | 是否可离线 | 依据 |
|---|---|---|
| CCL2018 全量建图（1,100 句 → 856 条 L1） | ✅ **可**（0 次 API 调用） | `llm_cache_deepseek.json` 1,100/1,100 |
| 本体清洗三变体对照验证 | ✅ **可** | refine 缓存未命中 0（2,128 / 2,125 / 846 命中） |
| 训练集建本体（4,074 句） | ✅ **可** | `llm_cache_train.json` 4,074/4,074 |
| 改写查询基准（632 条） | ✅ **可** | paraphrase 782 + judge 571 |
| 连贯语料建图 + L1.5 | ✅ **可** | `llm_cache_corpus.json` 1,050 + refine 2,469 |
| 链语义校验（52 条） | ✅ **可** | verify 52/52（11 True） |
| A6 常识消融 | ✅ **可** | `cs_neighbors.json` 987 |
| 真实句向量下的**超边描述**评分 | ✅ **可** | embed 命中 1,348/1,348 = **100%** |
| **真实句向量下的全量查询复测** | ⚠️ **仅子集** | anchored **519/634 = 81.9%**；deanchor **308/385 = 80.0%** |
| 从零重建本体 / 双语词典 / 新语料 | ❌ **需 `LLM_API_KEY`** | 缓存键集合外 |
| 全量真实向量查询 | ❌ **需 `EMBED_API_KEY`** | 缺 115（anchored）/ 77（deanchor）条查询向量 |

### 8.2 需要密钥的阶段

```bash
export LLM_API_KEY=...      # 必需
export LLM_BASE_URL=...     # 可选，默认 https://api.openai.com/v1
export LLM_MODEL=...        # 可选，默认 gpt-4o-mini

export EMBED_API_KEY=...    # 必需（真实句向量）
export EMBED_BASE_URL=...   # 可选，默认智谱
export EMBED_MODEL=...      # 可选，默认 embedding-3
export EMBED_DIMENSIONS=512 # 可选，须与 embeddings.DIM 一致
export EMBED_CACHE=...      # 可选，默认 data/embed_cache.json
```

- **代码不硬编码任何密钥**，全部经环境变量读取。
- 未配置时：`llm_backend._chat` 返回 `None` 并记 warning（**不崩溃**）；
  `embeddings.embedder_from_env` 返回 `None`（调用方决定）；
  部分脚本（`evaluate_llmasjudge` / `evaluate_chain_quality` / `evaluate_gold_audit` /
  `evaluate_packing_ablation`）**主动 `raise SystemExit("需要 LLM_API_KEY")`**。

### 8.3 缓存的"部分覆盖"是结构性限制

- `embed_cache.json` 的 **3,176** 条中，只有 **1,310 条（41.2%）** 落在
  "边描述 ∪ anchored 查询 ∪ deanchor 查询"（1,425 条）内；**1,866 条是其他阶段的文本**。
  这意味着缓存**不是为评测按需构建的**，而是多轮实验的累积 ——
  新增实验的文本若不在历史累积里，就必须回源。
- **两个覆盖率口径的范围不同，不可互相换算**：
  - `experiments/check_embed_cache_coverage.py` 在 **110 个逐文档子图**上统计 →
    唯一文本 **1,348** 条（其中边描述被调用 861 次），命中 **100%**。
  - 本文在**全局图**（1,100 chunk 单图）上统计 → 唯一边描述 **791** 条、
    anchored 查询 634 条、deanchor 查询 385 条，去重并集 **1,425** 条，
    命中 1,310 条。
  两者都说明"超边描述侧 100% 可离线"，但**查询侧命中率只在 anchored/deanchor 口径下
  有 81.9% / 80.0% 的实测值**。
- `llm_cache_paraphrase.json`（782）与 `llm_cache_judge.json`（571）**键集合不相交**
  （实测交集 **0**）—— 前者键为 `doc_id|原查询`，后者键为 `doc_id|改写问题`，
  命名空间不同但同属一条漏斗链。
- 漏斗实测：861 自动查询 → 782 有改写 → 571 有判定 → **632** 金标 chunk 非空。
  每一步都有损耗，且损耗原因不同（红线过滤 / 判定失败 / 金标边无 chunk_spans）。

---

## 9. 文档与实际的计数差异

> 下表只列**实测与文档叙述不一致**的项。所有"实际值"均由本清单生成时逐文件实测。

| # | 文档 | 文档所述 | 实测值 | 性质 |
|---|---|---|---|---|
| 1 | `release/MetaphorRAG-Bench/BENCHMARK.md`、`package_release.py` docstring | bench_queries「**652** 条改写查询」 | **632** 条 | ❌ **文档错误**（`package_release.log` 实测打印"查询 632 条"；652 是未做红线过滤的中间口径） |
| 2 | `BENCHMARK.md` | bench_extended_chains「106 篇…抽取的 **52** 条候选扩展链（**含链上 chunk 原文**）」 | 发布文件含 **106** 篇文档元数据、**11** 个 span、**0** 条 chunk 原文 | ❌ **文档错误**：既非 52（52 是候选数，发布的是校验后 11 条），也不含原文 |
| 3 | `BENCHMARK.md` | 校验判定见 `chain_verify/llm_cache_corups.verify.json` | 该路径**不存在**；实际为 `data/corpus/llm_cache_corpus.json.verify.json`（且 `data/` 不入库） | ❌ **路径错误** |
| 4 | `ontology_bilingual.py` docstring | curated「`BUILTIN_CONCEPTUAL_METAPHORS` 的 **11** 条」 | JSON 中 curated **2** 条 | ⚠️ 措辞歧义：11 是内置表规模，只有 2 条在本体中命中 |
| 5 | `ontology_bilingual.py` docstring | 例句「**食物→爱情** = FOOD IS LOVE」属 auto_gloss 示例 | 与 `BUILTIN_CONCEPTUAL_METAPHORS` 的 `食物→想法 = IDEAS ARE FOOD` 不同；实测 `食物→爱情` 确为 auto_gloss | ✅ 一致（此处列出以便读者区分两个「食物」条目） |
| 6 | `metaphor_graph/README.md` §7.3 | 连贯语料「扩展链密度 **6.3 条/百 L1**、**30%** 文档」 | 实测 6.33 条/百 L1（52/822）、30.2%（32/106） | ✅ 一致（基于**未校验**的 52 条候选） |
| 7 | `论文初稿.md` §5.2 / `metaphor_graph/README.md` | 生产本体「**98.6%** 的框架以 `F_LLM_` 开头」 | **100%**（2,177/2,177） | ⚠️ 数字来源是 `experiments/probe_graded.log`（curated=32 / llm-frame=2185，基于**未清洗**的 2,185 框架），清洗后 100%。结论方向不变（按前缀判定仍会误判整个本体），但数字已过时 |
| 8 | `DATA.md` §4 | 自检「应为 **224** 项通过」 | 实测 **228** tests, OK | ⚠️ 文档滞后（新增 4 项测试未同步） |
| 9 | `metaphor_graph/README.md` §3 | 「单元测试（**114** 项）」 | **228** 项 | ⚠️ 文档严重滞后 |
| 10 | `models.py` 类型标注 | `layer: int = 1` | 实际写入 `layer=1.5`（`extended.py:107`） | ⚠️ **类型契约与实现不一致** |
| 11 | `metaphor_graph/README.md` §3 目录树 | 列出 `../论文初稿.md` **两次**（v0.2 / v0.1 两行） | 同一文件 | ⚠️ 文档笔误 |
| 12 | `package_release.py` docstring | `bench_extended_chains.json`「连贯文档语料 **52** 条候选扩展链（含 chunk 原文与判定缓存键）」 | 11 条 span、无原文、无缓存键 | ❌ 同 #2 |
| 13 | `DATASET_CARD.md` | 「**curated=MetaNet 内置一致 / auto_gloss=词汇级转写**」 | 一致（curated 2 / auto_gloss 2,175 / unmapped 0） | ✅ 一致 |
| 14 | `ontology_clean.py` docstring | 「count≥2 的只有 **301** 个」 | 实测 core **299**（清洗后本体） | ⚠️ 301 是清洗前（2,185 框架）的统计；清洗后 299。`provenance.stats.n_core=299` 与实际一致 |
| 15 | `metaphor_graph/README.md` | 全量图「**856** 条 L1 边 / **861** 查询」 | 实测 856 L1 边 ✅、861 自动查询 ✅ | ✅ 一致 |
| 16 | `release/metaphor_resources/DATASET_CARD.md` | 「glm-5.3-flash，置信≥0.85」 | `llm_cache_train.json` 有 4,074 条；本体 2,177 框架 | ✅ 一致（构建参数无法从产物反查，但计数链自洽） |
| 17 | `metaphor_graph/README.md` §7.5 | 「违规剔除 **26.7%**」 | 实测 (861−635)/861 = **26.2%**；若以 861→632 计则 26.6% | ⚠️ 轻微偏差，量级一致 |
| 18 | `paper`/`README` | `evaluate_repaired_real.py` docstring「查询文本命中率 **81.9%**（519/634）」 | 实测 519/634 = **81.9%** ✅ | ✅ 一致 |
| 19 | `evaluate_repaired_real.py` docstring | 「超边描述命中率 **100%**（861/861）」 | 复跑 `check_embed_cache_coverage.py`：**1,348/1,348 = 100.00%**，未命中 0 | ✅ 一致（861 是调用次数，1,348 是唯一文本数） |
| 20 | `DATA.md` §1 | `llm_cache_train.json` 键「训练集原句（**4,074** 条）」 | **4,074** ✅（训练集隐喻句 4,075，去重后 4,074，0 遗漏） | ✅ 一致 |

### 9.1 需要修正的高优先级项

1. **#1（652 → 632）**：`BENCHMARK.md` 与 `package_release.py` docstring 应改为 632；
   或显式说明 652 是"红线过滤前"的口径。
2. **#2/#12（52 条 / 含原文）**：`BENCHMARK.md` 应说明发布的是**校验后 11 条 span**，
   且**不含** chunk 原文（原文需 CCL2018 或 `data/corpus/`）。
3. **#3（路径）**：`chain_verify/llm_cache_corups.verify.json` 应改为
   `data/corpus/llm_cache_corpus.json.verify.json`（并标注该文件不入库）。
4. **#8/#9（224/114 → 228）**：测试计数应统一为 228。
5. **#7（98.6% → 100%）**：论文与 README 应更新为清洗后口径。
6. **#10（`layer: int` vs 1.5）**：`models.py` 应改为 `layer: float = 1`（或 `Union[int,float]`）。
7. **§7.5 许可缺口**：zip 应包含 `LICENSE` 与 `DATA.md`。

---

## 10. 未入库的内容及原因

| 内容 | 规模（实测） | 是否入库 | 原因 |
|---|---|---|---|
| `data/` **整个目录** | 38.7 MB（含缓存 22.2 MB + 语料 12.4 MB） | ❌ 否（`git ls-files data/` = 0） | **许可**（非体积）：缓存键含 CCL2018 原文；语料为第三方版权 |
| ├ `data/CCL2018-Chinese-Metaphor-Analysis/` | 训练 4,394 句 / 测试 1,100 句 | ❌ | 大连理工 DUTIR，仅限学术研究、禁止商业用途 |
| ├ `data/llm_cache_deepseek.json` | 1,100 条 | ❌ | **键 = CCL2018 测试集原句** |
| ├ `data/llm_cache_train.json` | 4,074 条 | ❌ | **键 = CCL2018 训练集原句** |
| ├ `data/llm_cache_bilingual.json` | 835 个域词 | ❌ | 随 `data/` 排除（**但它是重建 `ontology_bilingual.json` 的必需输入** —— 见 1.2 边界） |
| ├ `data/embed_cache.json` | 3,176 条 × 512 维 | ❌ | 随 `data/` 排除；含 CCL2018 原句作为键 |
| ├ `data/corpus/luxun_quanji.txt` | 625,889 字符 | ❌ | 公版，但"为一致性一并排除" |
| ├ `data/corpus/gov_reports.json` | 55 篇 | ❌ | 公版（维基文库），同上 |
| ├ `data/corpus/caijing_news.json` | 150 篇 | ❌ | 新闻媒体版权 |
| ├ `data/corpus/chunks.jsonl` | 1,050 chunk | ❌ | 派生自上述语料 |
| └ `data/_ec_probe.json` | 15,176,197 B | ❌ | 随 `data/` 排除；**且文件损坏**（非法 JSON） |
| `.workbuddy/` | — | ❌ | 内部工作记录 |
| `.wt/` | 8 个并行实验 worktree | ❌ | 各自是独立检出，不嵌套入库 |
| `experiments/gen3/*.pkl` | — | ❌ | 二进制重放缓存，可复算（`cache_default ~5s` / `cache_real ~60s`） |
| `metaphor_graph/__pycache__/` | — | ❌ | Python 字节码 |
| **论文中的 CCL2018 单句引用** | `论文初稿.md` 1 处片段引用 | ⚠️ 入库 | 学术评论语境下的合理引用（实测为 ≥10 字符片段，非整句） |
| **`bench_extended_chains.json` 的 106 条新闻标题** | 106 条 + 11 条 span 元数据 | ⚠️ 入库 | 标题属合理引用范畴；DATA.md 提示"如需完全规避风险可自行剔除" |

### 10.1 排除导致的复现边界

- **干净检出后无法直接重放**：所有缓存都在 `data/` 下。要复现论文全部表格，
  必须（a）从其他渠道取得缓存副本，或（b）配置 `LLM_API_KEY` + `EMBED_API_KEY` 重跑。
  DATA.md 的"零 API 费用重放"保证**只在本地工作副本成立**。
- **`ontology_bilingual.json` 存在单向可复现性缺口**：其输入
  `data/bilingual_llm_ext.json`（835 条，与 `llm_cache_bilingual.json` **md5 相同**）
  不入库 → 仅凭仓库无法复算出 2,177 条 auto_gloss 对齐。
  **但发布产物本身已入库**（`metaphor_graph/` 与 `release/` 各一份），故不影响资源使用。
- **`bench_queries.json` 不可独立评测**：632 条查询覆盖 108 个 fc 文档，
  但发布包只含 2 篇文档原文 → 需 CCL2018 才能还原候选池。
- **`bench_extended_chains.json` 的链内容不可还原**：只有统计量（`n_chunks` / `n_l1` /
  `n_ext` / `span`），无 chunk 原文 → 需 `data/corpus/`。

---

## 附录 A：本文使用的核验命令

```bash
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"

# 本体计数
$PY -c "import json;d=json.load(open('metaphor_graph/ontology_default.json',encoding='utf-8'));\
print(len(d['frames']),len(d['cascades']))"          # → 2177 733

# 基准计数
$PY -c "import json;print(len(json.load(open('release/MetaphorRAG-Bench/bench_queries.json',encoding='utf-8'))))"  # → 632

# 向量缓存
$PY -c "import json;d=json.load(open('data/embed_cache.json',encoding='utf-8'));\
print(d['model'],len(d['vectors']))"                  # → embedding-3 3176

# 超边描述向量覆盖率（复跑实测 100%）
$PY experiments/check_embed_cache_coverage.py

# 查询文本向量命中率（复跑实测 81.9% / 80.0%）
$PY /tmp/chk_q.py                                     # 见 §8.1

# 单测
$PY -m unittest metaphor_graph.test_metaphor_graph     # → Ran 228 tests, OK

# 发布副本一致性
$PY -c "import hashlib;print(hashlib.md5(open('metaphor_graph/ontology_default.json','rb').read()).hexdigest())"
```
