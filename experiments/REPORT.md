# `type` 特征双路径不一致：确认、修复与 §6.2 重测

分支 `exp/source` ｜ 全部实验离线（$0，无 LLM/API 调用，全部走 `data/` 缓存重放）
被测代码改动：`metaphor_graph/{ontology,training,retrieval,test_metaphor_graph}.py`

---

## 0. 摘要（先给结论）

1. **bug 确认**：`type` 特征确实有两条不一致的实现，且**确实分歧**（22.0% 的候选对）。
2. **但原假设的因果链是错的**：§6.2 的「人工加权」**根本不调用**
   `retrieval.metaphor_retriever_score`。它走 `evaluate_retrieval.score_conditions`，
   用的是 `training.extract_features` 的 7 维向量。所以 §6.2 表里的
   0.502/0.547/0.536 **没有**被 `retrieval.py:250` 那个表达式污染。
3. **然而 §6.2 的 `type` 是常数 1.0**（真实图上 7437/7437 个候选对全为 1.0），
   所以那一维在已上报的 §6.2 表里**不携带任何排序信息**——它是被 bias 吸收的
   常数项。原假设说「训练路径 type=1.0 而人工加权 type=0.0，增益是编码产物」，
   实测**不成立**：两条路径在 §6.2 里都是 1.0。
4. **修复后 §6.2 数字变化，但方向与假设相反**：人工加权从 0.502 **降到** 0.481，
   自监督从 0.547 降到 0.545。**训练增益从 +4.5pp 扩大到 +6.4pp**。
   即：修复**不是**抹掉增益，而是让增益更真实、更大。
5. **意外发现（更重要）**：`evaluate_fullcorpus` 的 A7/H5 结论
   （原为「H5 不成立❌，训练无增益」）**翻转**为「H5 成立✅，+9.5pp」。
   原因正是修复让 `type` 从常数变成可区分信号，而人工加权硬编码 0.20 权重、
   训练器只学到 +0.049 → 人工加权结构性吃亏。
6. **A1/H1 完全不变**（日志逐字节相同）：P1 0.092 → 0.092，枚举拦 0 + 连贯性拦 24。

**对原问题的诚实回答**：已上报的 +4.5pp **不是**编码伪影——因为两条路径在 §6.2
里本来就同值（都是 1.0）。修复后增益反而增大到 +6.4pp。真正的问题是
**§6.2 的 `type` 维此前是死维**（恒常数），以及 **`retrieval.py` 那条 buggy
表达式确实在别处（A6）造成过 1.8pp 的静默低估**。

---

## 1. bug 确认（file:line）

### 1.1 两条不一致的表达式

原始代码（`git show HEAD:<file>`）：

**训练路径** — `metaphor_graph/training.py:81`（`extract_text_features`）：
```python
# 类型护栏：有框架归属即视为通过（详细校验需 ontology.type_valid）
type_ok = 1.0 if cand.frame_id else 0.0
```

**训练路径（边锚点版）** — `metaphor_graph/training.py:112-113`（`extract_features`）：
```python
fspec_type = cand.frame_id or ""
type_ok = 1.0 if fspec_type else 0.0  # 有框架归属即视为通过类型护栏
```

**检索路径** — `metaphor_graph/retrieval.py:250-252`（`metaphor_retriever_score`
人工加权分支）：
```python
fspec = self.ont.get_frame(mapping.frame_id) if mapping.frame_id else None
mtype = fspec.mapping_type if fspec else mapping.frame_id or ""
type_score = 1.0 if self.ont.type_valid(mapping.source_type, mtype) else 0.0
```

**分歧机制**：回退框架 id 形如 `F_LLM_ab12cd34`。若它未注册进本体，
`get_frame()` 返回 `None` → `mtype` 退化成 `frame_id` 原串 →
`type_valid('GENERIC_VEHICLE', 'F_LLM_ab12cd34')` 为 `False` → **0.0**。
而它的真实 `mapping_type` 是 `GENERIC_VEHICLE_MAP`，
`type_valid('GENERIC_VEHICLE', 'GENERIC_VEHICLE_MAP')` 为 `True`。

### 1.2 量化：真实评测图上的分歧

`experiments/probe_type_divergence.py`（`evaluate_fullcorpus` 口径，K=10，
110 伪文档，本体 2177 框架，856 条 L1 边）：

```
L1 边总数             : 856
F_LLM_* 回退框架边数  : 775 = 90.5%
无 frame_id 的边      : 0 = 0.0%
本体已注册框架的边     : 81 = 9.5%

type 特征分歧（文本锚点 vs 检索路径）: 188/856 = 22.0%
  training.extract_text_features type 取值分布: {1.0: 856}   ← 恒 1.0
  retrieval 人工加权路径 type 取值分布: {1.0: 668, 0.0: 188}
```

### 1.3 关键细分：`F_LLM_*` 有两类，不能一概而论

**原任务描述说「`F_LLM_*` 框架 get_frame() 找不到」——这只对了一部分。**

```
F_LLM_* 且本体已注册（get_frame 命中）: 587
F_LLM_* 且本体未注册（get_frame=None）: 188
```

原因：`F_LLM_*` 这个前缀被**两套不同的 id 空间**共用：

| 生成处 | 公式 | 是否注册进本体 |
|---|---|---|
| `extractor.py:113`（开放发现临时框架） | `md5(f"{src}\|{tgt}")[:8]` | 否（`F_LLM_*` 但不在 `ontology_default.json`） |
| `llm_ontology.py:201`（自举本体构建） | `md5("src\|\|tgt")[:8]` | 是（写进 `ontology_default.json`） |

两套 hash 输入不同（`|` vs `||`），所以 id 空间不相交：

```
extractor 临时 id : F_LLM_d808b8bb   （舞台|生活）
ontology 注册 id  : F_LLM_362c22f3   （舞台||生活）
same? False
```

**只有 188 条未注册边会被 buggy 表达式判 0.0**；另 587 条虽带 `F_LLM_` 前缀
但已注册，`get_frame` 命中、`type_valid` 通过，两条路径都给 1.0。
这解释了为什么分歧率是 22.0% 而不是 90.5%。

### 1.4 为什么这个 bug 的**实际影响范围**比预期小

**§6.2 的表根本不走 `retrieval.py:250`。**

`experiments/probe_feature_paths.py` 打印了 `evaluate_retrieval.score_conditions`
源码并核对了全部 `metaphor_retriever_score` 引用：

```python
# metaphor_graph/evaluate_retrieval.py:176-200
def score_conditions(eng, scorer, query):
    feats = {m.id: eng._pair_features(query, m) for m in cands}
    for name, fn in (
        ("trained", ...),
        ("trained_no_role", ...),
        ("hand_weighted", lambda f: 0.35 * f[0] + 0.25 * min(f[1], 1.0)
         + 0.20 * f[2] + 0.20 * f[3]),     # ← f[3] 来自 _pair_features
    ):
```

`eng._pair_features` → `training.extract_features` / `extract_text_features`。
`hand_weighted` 只是对这 7 维做一个**固定线性组合**。

`metaphor_retriever_score` 的**全部**调用方（`git grep`）：

| 文件 | 用途 | 是否影响已上报指标 |
|---|---|---|
| `retrieval.py:267`（`rank_mappings`） | 生成上下文 | 间接 |
| `demo.py:117` | 演示 | 否 |
| `test_metaphor_graph.py:197/952/956` | 单测 | 否 |
| `evaluate_a6.py:202`（经 `rank_mappings`） | **A6 指标** | **是** |
| `evaluate_llmasjudge.py:131`、`evaluate_packing_ablation.py:159`（经 `rank_mappings`） | 生成质量盲评 | 排序影响 top-5 |

**§6.2 / A7 / A9 / fullcorpus 全部不经此路**。

### 1.5 §6.2 的 `type` 是死维（常数）

`experiments/probe_path_mix.py`：

```
查询总数                     : 861
查询侧无超边命中（→文本锚点） : 612 = 71.1%
候选对总数                   : 7437
  走文本锚点 extract_text_features : 5062 = 68.1%
  走边锚点 extract_features        : 2375 = 31.9%

type 取值（文本锚点口径）: {1.0: 7437}   ← 全部 1.0
type 取值（边锚点口径）  : {1.0: 2375}   ← 全部 1.0
```

数学上确证（`probe_feature_paths.py` Q2 输出）：

- 人工加权：`0.20 * 1.0` 是常数 → 排序不变（数值验证：`rank_order` 完全一致）。
- 训练路径：该列标准化后恒为 0 → 权重无意义（`max|X_scaled[:,3]| = 0.0`）。

**结论：在已上报的 §6.2 表里，`type` 维对两条路径都无贡献。**
「训练路径 type=1.0 / 人工加权 type=0.0」的对照在 §6.2 上**不存在**。

---

## 2. 修复

### 2.1 共享的可靠性函数

新增于 `metaphor_graph/ontology.py:110-130`（常量）与 `:412-461`（函数）：

```python
TYPE_RELIABILITY_REGISTERED = 1.0
TYPE_RELIABILITY_FALLBACK = 0.5
TYPE_RELIABILITY_INVALID = 0.0
FALLBACK_FRAME_PREFIX = "F_LLM_"

@staticmethod
def type_reliability(frame_id, source_type="", frames=None) -> float:
    """type 护栏的封顶可靠性——两条打分路径唯一的 type 口径。"""
    if not frame_id:
        return TYPE_RELIABILITY_INVALID          # 无任何类型归属信息
    spec = (frames or {}).get(frame_id)
    if spec is None:
        return TYPE_RELIABILITY_FALLBACK         # 未注册：无法核验 → 封顶 0.5
    st = source_type or spec.source_type
    if CascadeOntology.type_valid(st, spec.mapping_type):
        return TYPE_RELIABILITY_REGISTERED       # 1.0
    return TYPE_RELIABILITY_INVALID              # 0.0（可核验的否定）

def type_reliability_of(self, frame_id, source_type="") -> float:
    """实例方法：用本体自身的 frames 表；调 self.type_valid 以尊重实例级补丁。"""
```

设计要点（对齐 VCP/RiverMemo 的意图）：**不丢弃候选**。`F_LLM_*` 边正是开放发现
换来 +55.8pp 召回的载体，判 0.0 等于关掉开放发现；改判**封顶 0.5**——
仍参与排序（召回不受损），但与本体框架可区分。

`type_reliability_of` 刻意调 `self.type_valid` 而非类上的静态方法，这样
`ablation.py` 对 `ont.type_valid` 的实例级打补丁（A1 计数用）照常生效。

### 2.2 三处调用点统一

| 位置 | 改动 |
|---|---|
| `metaphor_graph/training.py:87-88` | `type_ok = ont.type_reliability_of(cand.frame_id, cand.source_type)`（原 `1.0 if cand.frame_id else 0.0`） |
| `metaphor_graph/training.py:126-128` | 同上；并给 `extract_features` **新增 `ontology=None` 形参** |
| `metaphor_graph/retrieval.py:250-252` → `:253-254` | 删掉 `get_frame`+`type_valid` 手写分支，改调 `self.ont.type_reliability_of(...)` |

配套：`training.py` 增加 `from .ontology import DEFAULT_ONTOLOGY`；
`retrieval._pair_features`（`retrieval.py:231`）补传 `self.ont`，否则训练期与推理期
会拿到不同的本体实例；`training.py:369`（`_add`）补传 `ontology`。

### 2.3 新增单测（`metaphor_graph/test_metaphor_graph.py`）

`TestTypeReliability`（8 例）+ `TestManualWeightedTypeConsistency`（1 例）：

- 三级取值（1.0 / 0.5 / 0.0）与「无归属」边界
- 在册但非法映射 → 0.0（可核验的否定）
- **两条路径对同一候选必须同值**（核心回归）
- `type` 在混合候选池上必须**非常数**
- `type_reliability_of` 尊重 `ont.type_valid` 实例级补丁
- **`FALLBACK > 0` 的设计意图护栏**（防止后人「顺手」改成 0.0 而毁掉召回）
- `retrieval` 人工加权的 type 分量 == `extract_features` 的 `f[3]`

**测试套件：116 → 125 passing，全绿。**

---

## 3. §6.2 重测

### 3.1 已上报数字的复现（先证基线可信）

`python -m metaphor_graph.evaluate_llmgold --stage eval` 在**未改动**代码上重跑，
与 README §6.2 / `data/it_r0_baseline.log` **逐位一致**：

| 配置 | 本次复现 | 已上报 |
|---|---|---|
| 人工加权 | 0.502 | 0.502 |
| 自监督训练 | 0.547 | 0.547 |
| LLM弱监督 | 0.536 | 0.536 |

### 3.2 修复前后对照（LLM 非构造金标，n=632 改写查询）

| 配置 | 修复前 MRR@10 | 修复后 MRR@10 | Δ | 修复前 Hits@3 | 修复后 Hits@3 |
|---|---|---|---|---|---|
| 人工加权 | **0.502** | **0.481** | **−2.1pp** | 0.604 | 0.593 |
| 自监督训练 | 0.547 | 0.545 | −0.2pp | 0.634 | 0.638 |
| LLM弱监督训练 | 0.536 | 0.526 | −1.0pp | 0.641 | 0.647 |
| 自监督-去角色 | 0.547 | 0.545 | −0.2pp | 0.633 | 0.636 |
| **训练增益（自监督 − 人工加权）** | **+4.5pp** | **+6.4pp** | **+1.9pp** | | |

构造金标（对照）：

| 配置 | 修复前 | 修复后 |
|---|---|---|
| 人工加权 | 0.496 | 0.474 |
| 自监督训练 | 0.540 | 0.538 |
| LLM弱监督 | 0.529 | 0.518 |

**三条检索通路不变**（触发词级联 0.042 / 字面 0.000 / 语义超图 1.000）。
构造金标一致性不变（612/632 = 96.8%）。

### 3.3 控制变量的反事实：三种编码只改 f[3]

`experiments/exp_type_encoding_counterfactual.py` —— 同一份图、同一套金标、
同一套查询、同一训练集，**唯一变量是 `f[3]` 的编码**：

| type 编码 | 配置 | MRR@10 | Hits@3 | n |
|---|---|---|---|---|
| OLD-CONST 恒 1.0（已上报） | hand_weighted | 0.5025 | 0.6044 | 632 |
| | trained | 0.5481 | 0.6266 | 632 |
| | trained_weak | 0.5362 | 0.6424 | 632 |
| | **训练增益** | **+4.56pp** | | |
| BUGGY-RETR（retrieval.py:250） | hand_weighted | 0.4810 | 0.5934 | 632 |
| | trained | 0.5399 | 0.6313 | 632 |
| | trained_weak | 0.5095 | 0.6345 | 632 |
| | **训练增益** | **+5.89pp** | | |
| FIXED-CAP 封顶 0.5（本次修复） | hand_weighted | 0.4809 | 0.5934 | 632 |
| | trained | 0.5449 | 0.6377 | 632 |
| | trained_weak | 0.5255 | 0.6472 | 632 |
| | **训练增益** | **+6.39pp** | | |

（与 3.2 的 `evaluate_llmgold` 端到端重跑在 3 位小数上一致，互为交叉验证。）

### 3.4 real-embedder 一行（已上报 0.707/0.758/0.755）

**可离线精确重放。** `experiments/check_embed_cache_coverage.py` 精确复刻
`stage_eval` 的嵌入调用路径（含「有查询侧超边时不嵌查询原文」这一细节）：

```
评测**实际嵌入**的唯一文本 1348 条（边描述 861 次调用）
缓存命中 1348 = 100.00%
未命中 0
```

`experiments/exp_real_embed_replay.py` 用只读缓存的 embedder 重跑
（`n_hit=25520, n_miss=0`），先证基线可信：

| type 编码 | 配置 | MRR@10 | Hits@3 | 训练增益 |
|---|---|---|---|---|
| OLD-CONST 恒 1.0 | hand_weighted | **0.7073** | 0.8149 | |
| | trained | **0.7591** | 0.8734 | |
| | trained_weak | **0.7557** | 0.8703 | **+5.19pp** |
| BUGGY-RETR | hand_weighted | 0.6731 | 0.7816 | |
| | trained | 0.7407 | 0.8592 | |
| | trained_weak | 0.7050 | 0.8307 | +6.77pp |
| FIXED-CAP 封顶 0.5 | hand_weighted | 0.6734 | 0.7832 | |
| | trained | 0.7512 | 0.8703 | |
| | trained_weak | 0.7340 | 0.8608 | **+7.78pp** |

复现对照：已上报 0.707 / 0.758 / 0.755 vs 本次 0.7073 / 0.7591 / 0.7557 ——
**误差 ≤ 0.001**，确认重放口径正确。

**修复后（真实句向量）**：人工加权 0.707 → 0.673（−3.4pp），
自监督 0.759 → 0.751（−0.8pp），训练增益 +5.2pp → **+7.8pp**。
方向与哈希编码一致：**修复让增益更大，不是更小**。

### 3.5 训练增益是否存活？

**存活，且变大。** 三个设置全部一致：

| 设置 | 修复前增益 | 修复后增益 | 变化 |
|---|---|---|---|
| §6.2 哈希（端到端） | +4.5pp | +6.4pp | ↑ |
| §6.2 哈希（反事实，控制变量） | +4.56pp | +6.39pp | ↑ |
| §6.2 真实句向量 | +5.19pp | +7.78pp | ↑ |
| fullcorpus A7 | +0.3pp（判为「无增益」） | **+9.5pp（判为「有增益」）** | **结论翻转** |

---

## 4. 机制：为什么修复让增益变大

`experiments/probe_type_signal_alignment.py`：

```
【§6.2 LLM 金标】
frame 类别           金标边占比     非金标边占比
registered            85.3%          79.1%
fallback_unreg        14.7%          20.9%

§6.2 每查询的 type 均值：金标候选 0.9154  vs  非金标候选 0.8905  差 +0.0249
  金标 type 均值更高的查询数 393，更低的 123（共 632）
```

`type` 与金标**弱正相关**（393 vs 123 查询）。既然正相关，为什么人工加权反而变差？

`experiments/probe_learned_type_weight.py`（110 伪文档均值）：

```
特征               权重均值    权重标准差   单特征AUC均值
sem               0.6911     0.1415      0.9329
struct            0.0195     0.0672      0.5036
clue              1.2543     0.2337      0.9985
type              0.0487     0.0831      0.4973   ← 训练器几乎忽略
same_frame        0.1953     0.1600      0.5975
same_cascade      0.1958     0.1560      0.5975
ground_jaccard    0.4965     0.2009      0.7437
```

**机制**：`type` 的单特征 AUC ≈ 0.497（几乎无信息），训练器学到 +0.049 ≈ 0。
但 `hand_weighted` **硬编码 0.20**。在 `sem`/`clue` 之外硬塞一个近噪声维、
还占 20% 权重，等于往分数里加噪声 → 人工加权被拖累。训练路径可以自由压权重，
所以不受害。修复把 `type` 从「恒常数」变成「近噪声但非零方差」，
于是**人工加权从「无害常数」变成「有害噪声」**，而训练路径几乎无变化。

这解释了 3.2–3.4 的全部数字：人工加权降幅（−2.1pp / −3.4pp）远大于训练降幅
（−0.2pp / −0.8pp）。

> 诚实标注：`type` 与金标弱正相关但 AUC 仅 0.497，说明**正相关来自 chunk 级
> 聚合掩盖的组内抵消**，不是可用的排序信号。结论应表述为
> 「`type` 在本基准上不是有效的排序特征」，而非「`type` 有害」。

---

## 5. 其他维度的分歧排查

`experiments/probe_formula_divergence.py`（2375 个可比对样本）：

| 特征 | 两路径分歧率 | 判定 |
|---|---|---|
| `type` | **已修**（修复前 22.0%） | 真 bug，已修 |
| `sem` | 31.9% | **设计内**（锚点不同：查询文本 vs 查询超边） |
| `clue` | 0.3% | 设计内（同上，触发词重合度） |
| `struct` | 0.0% | 一致 |
| `same_frame` | **0.0%** | **一致**（`_query_edges` 刻意把查询侧超边定义为「查询触发词命中框架下的超边」，故语义对齐） |
| `same_cascade` | **0.08%**（2/2375） | 基本一致；残差来自 `_pair_features` 的 `max` 聚合（多查询边取最强） |
| `ground_jaccard` | 4.76%（113/2375） | **定义不同，非同一函数的两种写法** |

### 5.1 `ground_jaccard` 的定义分歧（需注意，但非 bug）

| 路径 | 公式 |
|---|---|
| `extract_text_features:98`（文本锚点） | **包含率** `|g ∩ text| / |g|` |
| `extract_features:130`（边锚点） | **真 Jaccard** `|gq ∩ gc| / |gq ∪ gc|` |

实测：包含率均值 0.125 vs Jaccard 均值 0.150；包含率 ≥ Jaccard 的比例 96.3%。

这是**设计内的锚点差异**——文本没有喻底集合，无法算 Jaccard。但两者不是同一
函数的两种写法（包含率分母只有 `|g|`，系统性偏高），**已在报告标注，本次未改**
（改动会波及所有历史数字，且无明确更优选择）。

### 5.2 `sem` 的 clamp 分歧（潜在隐患，已标注未改）

| 路径 | 公式 |
|---|---|
| `training.py:72/104` | `max(0.0, cosine(...))` |
| `retrieval.py:246-247`（人工加权） | `cosine(...)`，**无 clamp** |

本次语料下 cos 恒非负（7437 样本中 0 个负值，最负 0.0000），所以**当前无影响**。
但换 `NgramEmbedder` / 真实句向量后 cos 可为负，届时人工加权会给出负 `sem`
（惩罚）而训练路径为 0。已标注为隐患。

---

## 6. A1 / H1 复查

`python -m metaphor_graph.ablation --cache data/llm_cache_deepseek.json --ontology metaphor_graph/llm_ontology_train.json`

修复前 vs 修复后**逐字节相同**（`diff` 仅差我追加的 `EXIT=0` 标记行）：

```
配置                                召回     P1误判    精确率     F1
A1 完整系统（类型检查开）              0.696    0.092    0.990    0.818
A1 去掉全部类型检查                   0.696    0.092    0.990    0.818
                                    枚举拦 0 + 连贯性拦 24 → P1 0.092 → 0.092
```

**H1 结论不变：仍为证伪。** 类型约束拦下 24 个错误绑定，但 P1 纹丝不动。
原因与本次修复无关（已在 README §7.1 挖清）：连贯性检查拒绝的是**绑定**，
候选并未被丢弃——它退化为 `F_LLM_*` 临时框架后照样产出超边。

> 本次修复**没有**改变这一点，而且**设计上也不该改变**：封顶 0.5 而非 0.0
> 正是为了保住开放发现的召回（+55.8pp）。若为压 P1 而判 0.0，就同时毁掉召回——
> 那正是 README §7.1 已论证过的死路。

A2/A3/A4 同样不变（三通道全开 0.696/0.092、去掉自举本体 0.678 等）。

---

## 7. 附带发现：A6 曾静默低估 1.8pp

A6 是**唯一真正调用 `retrieval.py:250` buggy 表达式的已上报指标**
（经 `rank_mappings`，`scorer=None`）。`experiments/probe_a6_sensitivity.py`：

```
A6 敏感性（n=652 改写查询；top_k=5）
top-5 集合发生变化的查询数      : 182 = 27.9%
chunk 并集顺序发生变化的查询数  : 177 = 27.1%

type 编码                 Recall@10   Hits@3
OLD-CONST 恒1.0             0.8011   0.6120
BUGGY-RETR (retrieval)     0.7835   0.6012   ← 与已上报 0.783/0.601 一致
FIXED-CAP 封顶0.5            0.7835   0.6012   ← 与 buggy 同值
```

- 已上报的 A6 隐喻通路 **0.783 / 0.601** 与 **BUGGY-RETR** 行精确吻合，
  证明 A6 走的就是 buggy 表达式。
- 修复后（FIXED-CAP）A6 **指标不变**（0.7835/0.6012），但**不是因为排序不变**：
  精确测量（`experiments/probe_a6_buggy_vs_fixed.py`）显示 BUGGY 与 FIXED 的
  top-5 有 **19/652 = 2.9%** 的查询不同（未注册回退边进入 top-5 的条数
  从 181 增至 194）。指标不变是因为 A6 的 Recall@10/Hits@3 只看
  **前 5 条边的 chunk 并集是否命中金标**，而这 19 个查询的并集命中情况恰好未变。
  → 结论：**本次修复不改变 A6 的已上报数字**（这是实测结论，非推理）。
- **真正的静默低估**：若 A6 用 OLD-CONST 口径，应是 **0.8011/0.6120**。
  即 buggy 表达式让 A6 少报了 **1.8pp Recall@10**（top-5 在 27.9% 的查询上不同）。
  **A6 结论（常识通路 0.095 vs 隐喻通路 0.783 的 8 倍差距）不受影响。**

`python -m metaphor_graph.evaluate_a6` 修复后重跑，输出与 `data/a6_eval.log` 一致
（0.095 / 0.783 / 0.601），无回归。

---

## 8. 诚实结论：+4.5pp 是训练效应还是伪影？

**不是伪影。** 理由：

1. **原假设的因果链不成立**。§6.2 的 `hand_weighted` 不调用
   `retrieval.metaphor_retriever_score`；两条路径在 §6.2 里**都**给 `type = 1.0`
   （7437/7437 候选对），是常数项，不贡献任何排序差异。
   「训练 1.0 / 人工 0.0」这个对照在 §6.2 上不存在。
2. **修复后增益变大**：+4.5pp → +6.4pp（哈希）、+5.2pp → +7.8pp（真实句向量）、
   fullcorpus 从「无增益」翻转为 +9.5pp。若 +4.5pp 是编码伪影，修复应当缩小它。
3. **机制可解释**：修复让 `type` 从「无害常数」变成「近噪声但非零方差」，
   人工加权因硬编码 0.20 权重而吃亏，训练器学到 +0.049 几乎忽略它。
   降幅差异（人工 −2.1pp vs 训练 −0.2pp）正是这个机制的签名。

**但确实存在两个真实问题，都已修复/量化：**

- **`type` 维此前是死维**（恒 1.0）。论文若主张「新增 type 维度防污染」，
  在该基准上**没有证据支持**——它与 A9/H7 的证伪结论同类。
  修复后它才携带信息（虽仍近似噪声）。
- **`retrieval.py:250` 的表达式确实错**，且确实在 A6 上造成 1.8pp 的静默低估
  （0.783 → 应为 0.801）。A6 的定性结论不变。

**对论文的建议**：

1. §6.2 表需按修复后重报：人工加权 0.481 / 自监督 0.545 / 弱监督 0.526；
   real-embedder 0.673 / 0.751 / 0.734。训练增益表述从 +4.5pp 改为 **+6.4pp**
   （真实句向量 **+7.8pp**）。
2. §7.3 的 A7/H5 结论**需要改写**：从「H5 不成立（训练无增益）」改为
   「H5 在更大基准上成立（+9.5pp），此前的不成立是 `type` 维为常数 +
   人工加权硬编码权重所致」。**这是一个需要人工复核的重大结论变更。**
3. `type` 维的贡献主张应下调：单特征 AUC 0.497，学到权重 +0.049，
   与 A9（角色特征）同属「试过但无证据」。
4. A6 的 0.783 应更新为 0.801（或注明口径），定性结论不变。

---

## 9. 复现命令

全部离线、$0。解释器：
`C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe`
工作目录：`E:\02_AI项目\元图隐喻分析\.wt\source`

```bash
# ---- 诊断（确认 bug 与量化）----
python experiments/probe_type_divergence.py        # 22.0% 分歧；90.5% 回退边
python experiments/probe_feature_paths.py          # §6.2 不走 retrieval 路径；type 恒 1.0
python experiments/probe_path_mix.py               # 68.1% 文本锚点 / 31.9% 边锚点
python experiments/probe_formula_divergence.py     # 其余 6 维分歧
python experiments/probe_type_signal_alignment.py  # type 与金标弱正相关
python experiments/probe_learned_type_weight.py    # 学到 type 权重 +0.049
python experiments/probe_a6_sensitivity.py         # A6 走 buggy 表达式；OLD 口径应 0.801
python experiments/probe_a6_buggy_vs_fixed.py      # A6: buggy vs fixed top-5 仅 2.9% 不同

# ---- §6.2 重测 ----
python -m metaphor_graph.evaluate_llmgold --stage eval      # 修复后：0.481/0.545/0.526
python experiments/exp_type_encoding_counterfactual.py      # 三种编码控制变量
python experiments/exp_real_embed_replay.py                 # real-embedder 0.673/0.751/0.734
python experiments/check_embed_cache_coverage.py            # 100% 缓存命中

# ---- A7/H5（结论翻转）----
python -m metaphor_graph.evaluate_fullcorpus                # A7: +0.3pp → +9.5pp
python experiments/exp_fullcorpus_counterfactual.py         # 翻转由 type 编码引起

# ---- A1/H1（不变）----
python -m metaphor_graph.ablation --cache data/llm_cache_deepseek.json \
       --ontology metaphor_graph/llm_ontology_train.json

# ---- A6（数字不变，但证明 buggy 表达式的影响）----
python -m metaphor_graph.evaluate_a6

# ---- 测试 ----
python -m unittest metaphor_graph.test_metaphor_graph       # 125 passing
```

**修复前基线**（`git stash` 或 `git checkout HEAD~1 -- metaphor_graph/`）：
`experiments/logs/baseline_*.log`
**修复后**：`experiments/logs/fixed_*.log`、`experiments/logs/*.log`

---

## 10. 变更文件清单

| 文件 | 改动 |
|---|---|
| `metaphor_graph/ontology.py` | +常量（`:110-130`）、+`type_reliability` / `type_reliability_of`（`:412-461`） |
| `metaphor_graph/training.py` | `extract_text_features` / `extract_features` 改用共享函数；`extract_features` 新增 `ontology` 形参；`_add` 补传；+`DEFAULT_ONTOLOGY` 导入 |
| `metaphor_graph/retrieval.py` | `metaphor_retriever_score` 改用共享函数；`_pair_features` 补传 `self.ont` |
| `metaphor_graph/test_metaphor_graph.py` | +9 单测（`TestTypeReliability`、`TestManualWeightedTypeConsistency`） |
| `experiments/`（新目录） | 8 个探针 + 4 个实验脚本 + 14 个日志 |

---

## 附：本报告的自我更正记录

初稿有两处推理错误，已在正文更正，此处留痕以示诚实：

1. **初稿称「§6.2 的 `type` 恒 1.0 → 训练路径 1.0 / 人工加权 0.0 的对照不存在」**——
   前半句对（实测 7437/7437 全为 1.0），但初稿据此断言「两条路径在 §6.2 里都同值」
   依赖的是「§6.2 不走 retrieval 路径」这一**代码路径**论证。该论证正确
   （`score_conditions` 源码已核对），故结论成立。
2. **初稿称「A6 的 buggy 与 fixed top-5 不变，因为两者对未注册边都是同一常量」**——
   **这是错的**。buggy 给未注册边 0.0、fixed 给 0.5，未注册边整体 +0.1 分会改变
   组间相对排序。实测（`probe_a6_buggy_vs_fixed.py`）：top-5 有 19/652 = 2.9% 不同。
   A6 的**指标**确实不变，但原因是指标只看 chunk 并集命中，不是排序不变。
   正文 §7 已按实测改写。

另一处方法学更正：`check_embed_cache_coverage.py` 前两版把「查询原文」全部计入
待嵌入集合，得出 14 条未命中的错误结论。修正为精确复刻 `_pair_features` 的调用
条件（**仅当查询侧无超边命中时才嵌入查询原文**）后，命中率为 **100.00%**
（1348/1348）。real-embedder 一行因此**可以**零请求离线精确重放。
