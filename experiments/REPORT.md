<<<<<<< HEAD
# 实验报告索引

本目录下各方向的完整报告按分支分文件保存（原为同名 `REPORT.md`，合并时冲突）：

- [`REPORT_exp-source.md`](REPORT_exp-source.md) — type 特征双路径不一致的确认与修复
- [`REPORT_exp-cascade.md`](REPORT_exp-cascade.md) — 级联构造缺陷复现与构造规则对比
- [`REPORT_exp-dynamics.md`](REPORT_exp-dynamics.md) — 驱动/源项版 HGNN 与 H4 稳健性

跨方向的结论汇总见 [`实验结论汇总.md`](实验结论汇总.md)。
=======
# 退化溯源可靠性通道（degraded-provenance reliability channel）

**分支** `exp/degrade` ｜ **worktree** `.wt/degrade` ｜ 全部实验**离线、$0**（缓存重放，0 次 API 调用）

---

## 0. 结论先行（TL;DR）

**假设不成立 —— 而且不是「差一点」，是结构性不可能。**

| 问题 | 答案 |
|---|---|
| 封顶可靠性通道能否让类型/结构约束终于影响 P1？ | **不能，效应恒等于 0**。P1 是句级布尔指标（`pred = bool(edges)`），软通道只作用于打分/排序，不改变任何句子的产出与否。**数学上界就是 0**，不是调参问题。 |
| 能否在不丢召回的前提下做到？ | **能**（召回 0.696 → 0.696，逐位不变）。通道实现正确、召回完全保住。 |
| 那它影响排序了吗？ | **影响了，但是负的**：人工加权 MRR@10 **0.9948 → 0.8922（−0.1025）**。原因见 §5：by-construction 金标与通道前提直接冲突。 |
| 有无任何净增益？ | **无**。训练路径 +0.0000，人工加权路径 −0.1025，人工金标检索集 ±0.0000，floor 全档位扫描无一档优于基线。 |
| 那真正的收益是什么？ | **一个诚实的负面结论 + 一个被戳破的指标**：报出的 **P2 覆盖率 100% 里只有 77.6% 是本体正式归属**，其余 22.4% 由临时回退框架 + `builder._ensure_cascades` 事后补的 `C_ADHOC_*` 级联撑起（408 个级联里 184 个是事后补的）。 |

**张力没有被解决。** 参考系统（VCP/RiverMemo）的封顶可靠性模式在这里**不适用**，
原因是本项目的 P1 不是排序指标而是**存在性布尔指标** —— 这是与参考系统场景的关键结构差异，
也是本实验最有价值的发现。

---

## 1. 基线复现（精确数字）

### 1.1 口径陷阱：必须用缓存重放，不能直接跑 `evaluate_real.py`

直接跑 `python -m metaphor_graph.evaluate_real --use-llm ...` 在**无 API key** 的环境下会回落到
`LocalHeuristicBackend`（离线近似后端），而它**不实现 `discover_batch`/`batch_refine`**，
于是 `--llm-cache` 的缓存表根本没被消费 —— 实测：

```
本体: MetaNet迁移 + 自举触发词 + 语义域失谐 + LLM自举本体(2217框架) + LLM开放发现(LocalHeuristicBackend)
  Precision=0.923  Recall=0.388  F1=0.546
  字面误判率(P1) = 0.434   ⚠️ ≥0.15 未达标        ← 假性数字
```

**P1 = 0.434 是假的**（README §7.1 记录的同一类陷阱：`llm_backend is None` 被解释为
「未接后端 → 不做否定判断」，会顺带关掉 refine 校验，两个变量一起变）。

正确做法：用 `llm_backend.PrecomputedBackend` 把真实 DeepSeek 预取缓存喂给
`evaluate_real.eval_split`（指标口径逐位一致，零 API）。

### 1.2 真实基线（`experiments/baseline_eval_real.py`）

```
数据集 CCL2018(中文)  样本数=1100  （中性 76 句）
本体 LLM自举本体(2217框架)
LLM 后端 PrecomputedBackend(缓存重放 data/llm_cache_deepseek.json，
         discover 1100 句 / refine 3189 条，0 次请求)

[evaluate_real.eval_split 缓存重放]  n=1100
  TP=713  FP=7  TN=69  FN=311
  Precision=0.990  Recall=0.696  F1=0.818
  字面误判率(P1) = 0.092   ✅ <0.15 达标
  _type_rejects = 24
```

| 指标 | 基线实测 | README 记录 | 一致 |
|---|---|---|---|
| P1 字面误判率 | **0.092** | 9.2% | ✅ |
| 召回 | **0.696** | 69.6% | ✅ |
| 精确率 / F1 | 0.990 / 0.818 | 99.0% / 0.818 | ✅ |
| `_type_rejects` | **24** | 24 | ✅ |
| 开放发现召回边际贡献 | **+55.9pp** | +55.8pp | ✅ |

**A1 消融基线**（`python -m metaphor_graph.ablation`，与 README §7.1 逐字一致）：

```
A1 完整系统（类型检查开）   召回 0.696  P1 0.092  精确 0.990  F1 0.818  | 本体非法框架 0
A1 去掉全部类型检查        召回 0.696  P1 0.092  精确 0.990  F1 0.818  | 枚举拦 0 + 连贯性拦 24
                                                                         → P1 0.092 → 0.092
```

---

## 2. 实现（文件:行号）

### 2.1 新模块 `metaphor_graph/provenance.py`

| 位置 | 内容 |
|---|---|
| `provenance.py:39-48` | 常量：`RELIABILITY_ONTOLOGY=1.0`、`RELIABILITY_FALLBACK_CAP=0.5`、`RELIABILITY_FLOOR=0.5`、`RELIABILITY_FLOOR_OFF=1.0`（关闭开关）、分级标签 `PROV_ONTOLOGY`/`PROV_FALLBACK` |
| `provenance.py:51` | `frame_reliability(ontology, frame_id)` —— 派生可靠性 |
| `provenance.py:66` | `frame_provenance(...)` —— 分级标签 |
| `provenance.py:73` | `edge_reliability(edge, ontology)` —— 取存储值与派生值的**较小者**（防伪升级） |
| `provenance.py:88` | `reliability_factor(reliability, floor)` —— 映射到有下界的乘性因子 `floor + (1-floor)·r ∈ [floor, 1]` |

### 2.2 ⚠️ 判据必须是「本体有无条目」，**不是** `F_LLM_` 前缀

这是实现过程中最重要的一个坑，值得单独记录：

`llm_ontology.py:201` 用 `_stable_id("F_LLM", s, t)` 给**自举沉淀的正式框架**命名，
于是生产本体 `ontology_default.json` 的 **2177 个框架全部**以 `F_LLM_` 开头。
**按前缀判定会把整个生产本体误判为「退化」**，通道会退化成「惩罚一切」。

正确判据只有一条：`ontology.get_frame(frame_id) is not None`。
测试 `test_judgement_is_registration_not_prefix` 把这个坑钉死。

### 2.3 数据模型（向后兼容）

| 位置 | 改动 |
|---|---|
| `models.py:89` | `MetaphorHyperedge.provenance_reliability: float = 1.0` —— **默认 1.0**，手工建边/旧序列化数据不受影响 |
| `extractor.py:228` | `emit()` 写入 `provenance.frame_reliability(self.ont, frame.id)` |
| `extended.py:104-105` | L1.5 扩展边取链上 `min(...)` —— **退化边不得借合并洗白** |

**候选永不丢弃**：抽取器的 `emit()` 只多写一个字段，任何 return-None 分支都没动。

### 2.4 可靠性如何抵达打分/排序层

| 位置 | 接入点 |
|---|---|
| `retrieval.py:55,68-69` | `RetrievalEngine(..., reliability_floor=...)`；`floor=1.0` 即通道关闭 |
| `retrieval.py:82-101` | `_reliability()`（带缓存）+ `reliability_factor()` |
| `retrieval.py:274` | `metaphor_retriever_score()` —— **两条路径都乘折扣**（训练式 scorer 与人工加权） |
| `retrieval.py:171` | `cross_domain_retrieve()` 主通路 |
| `retrieval.py:192` | `cross_domain_retrieve()` 语义回退通路 |
| `evaluate_retrieval.py:176-217` | `score_conditions(..., reliability=True)` 新增 `*_reliab` 配置，**原三组逐位不变** |
| `health.py:159-176` | 诚实覆盖率（传 `ontology` 才算；不传字段为 `None`，历史口径逐位不变） |

**为什么是「有下界的乘性折扣」而不是加性 bonus 或过滤器**（设计论证）：
- 加性 bonus 对两项加同一常数 → **不改变相对次序** → 对排序无效；
- 硬过滤 → 丢候选 → 召回直接崩（§3 已实测：只留 curated 召回 0.696 → 0.077）；
- 有下界乘性折扣 → 改变次序，且 `factor ≥ floor > 0` → **永不归零，候选一个不丢**。

这是与「过滤方案」的分界线，也正是本次要检验的设计要点。

---

## 3. Before / After 表

### 3.1 P1 / 召回 / 精确率 / F1（`experiments/eval_degraded.py`）

| 配置 | 召回 | P1 | 精确率 | F1 | `_type_rejects` |
|---|---|---|---|---|---|
| 通道关闭（基线口径，floor=1.0） | 0.696 | 0.092 | 0.990 | 0.818 | 24 |
| **通道开启（封顶 0.5，floor=0.5）** | **0.696** | **0.092** | **0.990** | **0.818** | 24 |
| **差值** | **+0.0000** | **+0.0000** | **+0.0000** | **+0.0000** | 0 |

**召回完全保住（逐位不变）** —— 设计目标达成。**P1 位移精确为 0** —— 假设不成立。

### 3.2 排序指标（全量 CCL2018，伪文档 K=10，n=862 查询）

| 配置 | MRR@10 | Hits@3 | Hits@10 |
|---|---|---|---|
| trained | 0.9977 | 1.0000 | 1.0000 |
| trained + 可靠性折扣 | 0.9977 | 1.0000 | 1.0000 |
| trained_no_role (A9) | 0.9977 | 1.0000 | 1.0000 |
| hand_weighted | 0.9948 | 1.0000 | 1.0000 |
| **hand_weighted + 可靠性折扣** | **0.8922** | **0.8921** | 1.0000 |
| 差值（trained 路径） | **+0.0000** | 0 | 0 |
| 差值（hand 路径） | **−0.1025** | −0.1079 | 0 |

### 3.3 L2/L3 覆盖率：现报口径 vs 诚实口径

| 口径 | 值 |
|---|---|
| 现报 `hierarchy_coverage` | **1.000**（frame 1.000 / cascade 1.000） |
| **诚实口径：本体登记框架** | **0.776** |
| 诚实口径：本体登记级联 | 0.776 |
| 退化边占比 | 22.4% |
| 平均溯源可靠性 | 0.888 |
| 级联总数 / 其中 `C_ADHOC_` 事后补的 | 408 / **184（45.1%）** |

**现报的 100% 覆盖率有 22.4pp 是「注水」的**：这些边挂在抽取器临时新建的回退框架上，
靠 `builder._ensure_cascades`（`builder.py:142`）按目标域事后补 `C_ADHOC_*` 级联才够到 100%。
把这些排除后，**本体正式归属只有 77.6%，低于 P2 的 85% 门槛**。

`graph_health(..., ontology=...)` 现在会就此告警。不传 `ontology` 时字段为 `None`、
报告文本不含该行 —— **历史口径逐位不变**。

### 3.4 A1 再检查（可靠性通道已启用）

| 配置 | 召回 | P1 | 精确率 | F1 |
|---|---|---|---|---|
| A1 类型检查开 | 0.696 | 0.092 | 0.990 | 0.818 |
| A1 类型检查关 | 0.696 | 0.092 | 0.990 | 0.818 |
| 差值 | +0.0000 | **+0.0000** | +0.0000 | +0.0000 |

连贯性检查仍拦下 **24** 个候选，**P1 依然纹丝不动**。
`python -m metaphor_graph.ablation` 的输出与基线**逐字节相同**（`diff` 验证通过）——
向后兼容性完全成立。

---

## 4. 判别力审计（关键证据）

### 4.1 P1 无位移是结构性的，不是调参问题

`evaluate_real.eval_split` 的判据是 `pred = bool(edges)`（`evaluate_real.py:78`）。
P1 只统计「**这句话有没有产出任何边**」。可靠性通道**一个候选都不丢**，
所以任何句子的 `bool(edges)` 都不可能改变 → **P1 的效应上界恒等于 0**。

实测确认分子为 0：

| 类别 | 数量 |
|---|---|
| FP 句（应无隐喻却判出） | 7 |
| 其中「全部边都是临时回退框架」 | **0** |
| TP 句（真隐喻） | 713 |
| 其中「全部边都是临时回退框架」 | **155** |

**7 条 FP 句的边 100% 来自本体登记的正式框架**，逐条解剖（`experiments/probe_fp.log`）：

| # | 句子（截断） | 绑定的框架 | 类型 |
|---|---|---|---|
| 1 | 十里长安街亮如白昼…灿若星河 | 花→思想 | NATURE（本体登记） |
| 2 | …犹如千百万台摄影机在对我聚焦 | 摄影→记忆 | GENERIC_VEHICLE（本体登记） |
| 3 | 淅淅沥沥的一场春雨…也淋湿了老张的心 | 雨→书 | NATURAL_PHENOMENON（本体登记） |
| 4 | 黄义接过入住安居工程的纪念钥匙 | 钥匙→认识 | GENERIC_VEHICLE（本体登记） |
| 5 | 他目光痴情地掠过一株株的葡萄藤… | 马→人生 | ORGANISM（本体登记） |
| 6 | 敌人的防线被英勇的解放军战士冲破了 | 障碍→谈判 | GENERIC_VEHICLE（本体登记） |
| 7 | …广大公安民警才得以前仆后继，勇往直前 | 战争→工作 | WAR（本体登记） |

**「惩罚退化溯源」在 P1 上连分子都碰不到** —— 这不是效应小，是恒等于 0。

### 4.2 判别力 AUC = 0.39（反向）

把 `provenance_reliability` 当作句级「真隐喻 vs 字面」打分算 AUC：

```
有边的隐喻句 n=713，有边的字面句 n=7
句级 AUC = 0.3913                       ← 反向相关，不是 0.5 附近
隐喻句可靠性分布：min=0.50 p50=1.00 max=1.00 ｜ =1.0 占比 78.3%
字面句可靠性分布：min=1.00 p50=1.00 max=1.00 ｜ =1.0 占比 100.0%
```

字面句的可靠性**全部是 1.0**，而隐喻句有 21.7% 是 0.5。
**该通道与「这句是不是隐喻」负相关** —— 惩罚退化溯源会优先打到真隐喻上。

### 4.3 折扣强度全档位扫描：不存在「调参能救」的档位

| floor（越小=折扣越狠） | trained MRR@10 | hand MRR@10 | hand Hits@3 |
|---|---|---|---|
| **1.00（通道关闭，基线）** | **0.9977** | **0.9948** | **1.0000** |
| 0.90 | 0.9977 | 0.9868 | 0.9988 |
| 0.75 | 0.9977 | 0.9428 | 0.9548 |
| 0.50 | 0.9977 | 0.8922 | 0.8921 |

**所有档位 ≤ 基线**，单调劣化。没有任何一档能带来净增益。

### 4.4 为什么人工加权路径会掉，训练路径不掉？

**金标前提冲突**。`evaluate_fullcorpus.build_queries` 把 **Q_self 的金标定义为「产出该超边的那个 chunk」**。
实测 **26.6%（229/862）的查询，其金标 chunk 含退化边**。也就是说：

> **任何对退化边的降权，都在直接惩罚金标自身。**

这是**评测口径与通道设计前提的结构性冲突**，不是实现 bug。

**训练路径为何不掉分**（110 个伪文档上的实测，非单文档外推）：

| 项 | 值 |
|---|---|
| 训练后排序器平均权重 `clue` | **1.2583**（最高，次高 `sem` 0.6891） |
| 单特征 AUC `clue` | **0.999** |
| 单特征 AUC `struct` | **0.504** ← 可靠性最该调制的那一维，本身零判别力 |
| 单特征 AUC `sem` | 0.933 |

**注意：折扣确实改变了排序，只是改变不了「金标在第几名」**（n=857 查询）：

| 路径 | 排序序列被改变 | **金标名次被改变** | top-1 正确性翻转 | 金标本来就不是 top-1 |
|---|---|---|---|---|
| trained | 323（37.7%） | **0** | **0** | **仅 4 条** |
| hand_weighted | 284（33.1%） | **120** | 115 | 9 条 |

训练路径：**37.7% 的排序序列被改动，但金标名次一条都没变。**
原因是 `clue` 单特征 AUC = 0.999，金标 chunk 靠触发词命中已稳居第一且**分差极大**，
乘一个 ≥0.5 的因子在数值上改变了尾部次序，却**动不了头部**；
而且**金标本来就已经是 top-1 的占 853/857（99.5%）—— 该指标已饱和，没有可改善的空间**
（README §7.3 早已记录 A7/A9 在此指标上「测不出差异」）。
换句话说：**不是通道有效，是这个指标天花板效应 + 排序器不看这一维。**

人工加权路径的权重固定（0.35/0.25/0.20/0.20），`struct` 占 0.25 而可靠性直接乘总分，
折扣真的咬到了头部 —— 于是 120 条查询金标名次后移、115 条丢掉 top-1，MRR 掉 10 个点。
**同一个通道，在两条路径上一个「无效应」一个「强负效应」，差别只在于头部次序是否被咬到。**

### 4.5 与通道前提不冲突的尺子：人工金标检索集

用 `eval_corpus`（2 文档 8 查询，人工撰写、非构造金标）：

| 文档 | n | Recall@10 开 | Recall@10 关 | 差 |
|---|---|---|---|---|
| doc_project | 5 | 0.800 | 0.800 | **+0.000** |
| doc_relationship | 3 | 0.000 | 0.000 | **+0.000** |

**±0.0000。** 在唯一一把与通道前提不冲突的尺子上，效应是**精确的零**。

### 4.6 独立证据链：真正压 P1 的是 refine，不是可靠性

7 条 FP 句的边**全部来自 discover 通道**，走 `emit(..., skip_refine=True)`
（`extractor.py:273`）—— **从不经过 refine**。查真实 LLM 缓存：

```
FP 句 7 条；其边在 refine 缓存中命中 0 条（discover 通道 skip_refine，从未请求过）
```

这**强化了 README §7.1 的既有结论**：真正压住 P1 的是 **refine 校验（43.4% → 0.0%）与置信阈值**。
可靠性通道与这条证据链**正交**，不能替代它。若要压这 7 条 FP，
正确做法是**让 discover 通道的候选也过一遍 refine**（成本：7 条 × 1 次调用），
而不是给它们打可靠性折扣。

---

## 5. 诚实裁决

### 5.1 假设：**不成立**（not at all）

| 子问题 | 裁决 | 证据 |
|---|---|---|
| 能否让类型/结构约束影响 P1？ | **完全不能** | §4.1：分子恒为 0，上界 = 0 |
| 能否保住召回？ | **能**（但这不构成价值） | §3.1：召回 +0.0000 |
| 能否改善排序？ | **不能，且显著劣化** | §3.2：−0.1025（人工加权）；±0.0000（人工金标集） |
| 效应是否在噪声内？ | **P1 是精确的 0**（非噪声）；**排序是显著负效应**（−0.10，远超噪声） | §3.2 / §4.3 |
| 是否存在更优参数档位？ | **不存在**，全档位单调劣化 | §4.3 |

### 5.2 这是「relabeling」还是「真改进」？

**既不是真改进，也不只是 relabeling —— 它是一次有效的证伪。**

- **不是真改进**：P1 ±0.0000、人工金标检索 ±0.0000、by-construction 排序 −0.1025。
- **不是无害的 relabeling**：它有**实质性的负面副作用** —— 在 by-construction 排序上掉 10 个 MRR 点，
  且判别力 AUC = 0.39 说明它会**优先惩罚真隐喻**。
- **真正的产出**：证明「参考系统的封顶可靠性模式」在本项目**不适用**，
  并给出了不可反驳的机理：**P1 是存在性布尔指标，不是排序指标**。
  参考系统（VCP/RiverMemo）处理的是「同一候选有多可信」的排序问题；
  本项目的张力是「这个候选该不该存在」的存在性问题。**软通道对存在性问题无效。**

### 5.3 张力：**未解决**

README §7.1 的诊断**依然成立且被本次实验加强**：

> 要让约束影响 P1，就必须丢弃候选本身，而那等于关掉开放发现（+55.8pp 召回）。

本次实验排除了「不丢弃候选、改为软降权」这条中间路线：
**软通道在数学上够不到 P1**。二难依然闭合 ——
要么丢弃候选（丢 +55.9pp 召回），要么不丢弃（P1 不受影响）。**没有第三条路。**

### 5.4 但有一个**真实且重要的**附带发现：P2 覆盖率 100% 是注水的

这是本次实验唯一可以上报为正面的结果：

| | 值 |
|---|---|
| 报出的 P2 L2/L3 覆盖率 | 100% ✅（README §7.0 看板） |
| **诚实口径（本体登记框架）** | **77.6%** ❌（**低于 85% 门槛**） |
| 注水来源 | 22.4% 的边挂临时回退框架 + 184/408 个 `C_ADHOC_*` 事后补级联 |

README §7.0 的「**P2 覆盖率 100% ✅**」在诚实口径下**不达标**。
这不是通道带来的改进，而是通道**暴露出来的既有度量问题** —— 建议论文与看板据此改口径：
要么把 `_ensure_cascades` 的补级联排除在正式覆盖率之外单列，
要么明确标注该指标含「事后补归属」。

### 5.5 建议

1. **不要**把可靠性通道当作「修复 H1」的方案上报 —— 它不工作，且有害。
2. **应该**把本次结果写进论文：这是「改了、实现了、测了、确实无效」的完整负面证据，
   比只报「约束拦下 24 个候选」有说服力得多。机理陈述建议用：
   > 「类型/结构约束与可靠性折扣作用于**排序层**，而 P1 是**存在性布尔指标**；
   > 二者正交。在开放发现流水线上，任何不丢弃候选的机制都无法影响 P1。」
3. **应该**修正 P2 覆盖率口径（§5.4）。
4. **若要真正压这 7 条 FP**：让 discover 候选也过 refine（§4.6），成本 7 次调用。
   这直接攻击 FP 的成因（绕过校验），而不是绕路降权。
5. 通道本身**保留**（代码已入库、默认关闭、测试齐备）：它作为**可观测性**有价值
   （诚实覆盖率、退化边占比、`avg_provenance_reliability`），
   只是不能承担「影响 P1」的职责。默认 `reliability_floor=1.0` 语义等价于关闭。

---

## 6. 回归验证

| 检查 | 结果 |
|---|---|
| `python -m unittest metaphor_graph.test_metaphor_graph` | **129 passed**（原 116 + 新增 13） |
| `python -m metaphor_graph.ablation` 输出 | 与基线 **逐字节相同**（`diff` 通过） |
| `python -m metaphor_graph.evaluate_retrieval` | 与 README §7.3 一致（P3 F1 1.000，A7/A9 结论不变） |
| `graph_health(shg)` 不传 ontology | 字段 `None`、报告文本不变 —— **历史口径逐位不变** |
| `RetrievalEngine(reliability_floor=1.0)` | 打分与改动前逐位一致（`test_reliability_floor_one_reproduces_history`） |
| `MetaphorHyperedge.provenance_reliability` 默认 | `1.0`（`test_model_field_default_is_backward_compatible`） |

---

## 7. 复现命令

全部离线、$0（LLM 阶段全部走 `data/` 缓存重放）。

```bash
# 解释器
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"
cd "E:/02_AI项目/元图隐喻分析/.wt/degrade"

# 0) 测试套件（129 passed）
$PY -m unittest metaphor_graph.test_metaphor_graph

# 1) 基线复现（缓存重放；**不要**直接跑 evaluate_real.py，见 §1.1）
$PY experiments/baseline_eval_real.py              # P1 0.092 / 召回 0.696 / _type_rejects 24
$PY -m metaphor_graph.ablation \
     --cache data/llm_cache_deepseek.json \
     --ontology metaphor_graph/llm_ontology_train.json

# 2) 主实验：before/after + A1 再检查 + 覆盖率（快，约 2 分钟）
$PY experiments/eval_degraded.py --quick

# 3) 主实验全量：含排序指标（约 15 分钟）
$PY experiments/eval_degraded.py

# 4) 判别力与折扣敏感性探查
$PY experiments/probe_fp.py          # 7 条 FP 逐条解剖（分子为 0 的证明）
$PY experiments/probe_auc.py         # AUC 0.39 + 人工金标检索集 ±0.000
$PY experiments/probe_floor.py       # 折扣强度全档位扫描
$PY experiments/probe_whatchanged.py # 排序序列 vs 金标名次（解释 §4.4）
$PY experiments/probe_graded.py      # 分级前沿 + 过滤口径上界
$PY experiments/probe_frontier.py    # refine 缓存交叉验证
$PY experiments/probe_provenance2.py # 退化子类 + 诚实覆盖率
# ⚠️ probe_provenance.py 的判据是错的（按前缀判定），已被 probe_provenance2.py
#    取代，保留作反面教材 —— 它正是 §2.2 那个坑的来源，日志勿引用。

# 5) 回归对照
$PY -m metaphor_graph.evaluate_retrieval
```

**日志**：`experiments/*.log`（基线 `baseline_*.log`、主实验 `eval_degraded*.log`、探查 `probe_*.log`）

---

## 8. 变更文件清单

| 文件 | 改动 |
|---|---|
| `metaphor_graph/provenance.py` | **新增**（95 行）：可靠性派生 + 有下界乘性因子 |
| `metaphor_graph/models.py:89` | `MetaphorHyperedge.provenance_reliability: float = 1.0` |
| `metaphor_graph/extractor.py:28,228` | 导入 + `emit()` 写入可靠性（候选不丢弃） |
| `metaphor_graph/extended.py:104-105` | L1.5 扩展边取链上最弱一环 |
| `metaphor_graph/retrieval.py:15,55,68-101,171,192,274` | 引擎接入：`reliability_floor` + 两处通路 + 打分两条路径 |
| `metaphor_graph/evaluate_retrieval.py:176-217` | `score_conditions(..., reliability=True)` 新增 `*_reliab` 配置 |
| `metaphor_graph/health.py:50-53,82-88,159-176,193-201` | 诚实覆盖率 + 退化边占比 + 告警 |
| `metaphor_graph/__init__.py:46-52,68-72` | 导出 `provenance` 与 7 个符号 |
| `metaphor_graph/test_metaphor_graph.py` | **+13 测试**（`TestProvenanceReliability`） |
| `experiments/*.py`, `experiments/*.log` | **新增**：9 个探查/评测脚本 + 全部日志 |
| `experiments/REPORT.md` | **新增**：本报告 |
>>>>>>> exp/degrade
