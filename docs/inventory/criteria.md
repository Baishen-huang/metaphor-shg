# 准则全量清单（阈值 / 门槛 / 判定规则 / 不变量）

> 深化对象：`docs/inventory/_extracted.json` 的 `criterion` 类目（机械提取 17 项）。
> 本文件由人工 + AST/正则深挖产出，**共 139 项**，其中 **124 项为机械提取遗漏**
> （原 17 项被本文件的 15 行覆盖 —— `ontology.py` 的三个 `TYPE_RELIABILITY_*`
> 常量在 E5 合并为一条三档准则）。
> 生成日期：2026-09-27。代码为只读，未做任何修改。
>
> 口径说明：本文件区分 **硬门槛（Go/No-Go）** 与 **软参数（tunable）**。
> 论文 §4「指标」段明确把 P1 定为硬门槛，附录 B 把 P0–P5 定为里程碑验收；
> 其余全部为软参数。**软参数不达标不等于项目失败，但必须报告取值来源。**

---

## 0. 计数摘要

| 家族 | 项数 | 其中硬门槛 | 机械提取已捕获 | 本文件新增 |
|---|---|---|---|---|
| A 抽取门槛 | 26 | 1（P1） | 0 | 26 |
| B 构建门槛 | 16 | 2（P0/P2） | 3（B13/B14/B15） | 13 |
| C 检索门槛 | 18 | 0 | 2（C6/C7） | 16 |
| D 链接判据（L1.5） | 6 | 1（P3） | 1（D1） | 5 |
| E 可靠性 / 可观测性 | 17 | 0 | 8（E1–E8，其中 E5 合并 3 个常量） | 9 |
| F HGNN / 谱条件 | 9 | 0 | 1（F9，DIM=512） | 8 |
| G 训练 / 评测 | 26 | 0 | 0 | 26 |
| H 不变量（invariants） | 15 | — | 0 | 15 |
| I 外部参考实现（rmtop.rs） | 6 | 0 | 0 | 6 |
| **合计** | **139** | **4** | **17 项 / 覆盖 15 行** | **124** |

> 覆盖说明：机械提取的 17 个常量落在本文件的 15 行上 ——
> `ontology.py` 的 `TYPE_RELIABILITY_REGISTERED/FALLBACK/INVALID` 三个常量
> 在 E5 合并为一条三档准则。故 139 − 15 = **124 行为新增**。
> 逐行归属：B13/B14/B15、C6/C7、D1、E1/E2/E3/E4、E5、E6/E7/E8、F9 = 15 行。

---

## 1. 汇总表

### A 抽取门槛

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| A1 | **P1 字面误判率硬门槛** | `论文初稿.md:184`、`evaluate_real.py:115`、`test_metaphor_graph.py:334` | **< 0.15** | 方案 §6.5 拍定（Go/No-Go） | ✅ 实测 9.2%，单测 3 处护栏 |
| A2 | `conf_threshold` | `extractor.py:43` | 0.35 | 拍定（论文 §6.6 称「基础阈值 0.35」） | ⚠️ 无敏感性实验 |
| A3 | `llm_conf_threshold` | `extractor.py:46` | 0.5 | 拍定（构造器默认，比 A2 严） | ❌ 无实证；生产全用 0.85 |
| A4 | **LLM 置信达标拐点** | `evaluate_real.py:150`、`evaluate_llmgold.py:390`、`llm_ontology.py:76` | **0.85** | **实测标定**（P1 14.5% → 9.2%） | ✅ 论文 §5.1 双防线表 |
| A5 | 触发词置信公式 | `extractor.py:185` | `min(1.0, 0.4 + 0.2·n_trig)` | 拍定（线性启发式） | ❌ 无验证 |
| A6 | novelty 判据 | `extractor.py:221` | `n_triggers == 1` | 拍定（单触发词=新） | ❌ 无验证 |
| A7 | **MIPVU 三条排除项** | `llm_backend.py:132-141` | 3 类：词汇化成语 / 描写性美称 / 字面身份判断 | **继承文献**（MIPVU）+ 实测 | ✅ 去掉 P1 飙至 28.9% |
| A8 | MIPVU 标记窗口 | `mipvu.py:38` | `_TOKEN_WIN = 2` | 拍定（「X是一个Y」隔量词） | ⚠️ 有语言学论证，无消融 |
| A9 | 域内字面护栏 | `mipvu.py:105`、`llm_backend.py:524` | 同域词 `>= 2` 且 `== 主导域` | 实测标定（P1 17.1%→14.5%） | ✅ README §6.6 |
| A10 | 语义失谐稀有判据 | `mipvu.py:114` | `field_count > 1` → 跳过 | 拍定（Wmatrix keyness 类比） | ❌ 无验证 |
| A11 | 失谐强度阈值 | `mipvu.py:114` | `inc < 0.6` → 跳过 | 拍定（与 A12 同源） | ❌ 无验证 |
| A12 | 失谐分数取值 | `semfield.py:117,120` | 无主导域 0.3 / 跨域 0.6 / 同域 0 | 拍定 | ❌ 无验证 |
| A13 | MIPVU 候选置信档 | `mipvu.py:110,116` | 标记 0.5 / 高失谐 0.45 / 低 0.4 | 拍定（需 > A2=0.35 才存活） | ❌ 无验证 |
| A14 | 字面干扰词表 | `extractor.py:34` | 4 词（苹果/水/火/路） | 拍定（演示用） | ❌ 硬编码 4 词 |
| A15 | 悬空候选判据 | `extractor.py:266-270` | 触发词须能在原文定位 | 拍定（防 LLM 幻觉） | ✅ 有单测 |
| A16 | 自举 `min_df` | `bootstrap_triggers.py:180` | 3 | 拍定 | ⚠️ README §6.9 扫过 2/10/20 |
| A17 | 自举 `min_lift` | `bootstrap_triggers.py:181` | 3.0 | 拍定（沿用 lift 纪律） | ⚠️ 未扫 |
| A18 | 动词 lift 门槛 | `bootstrap_triggers.py:236` | `lift < 20` 剔除 | 拍定（比名词严 6.7×） | ❌ 无验证 |
| A19 | 泛用触发词剔除 | `llm_ontology.py:138-139` | `len < 2` 或 `跨框架数 > 3` | **实测标定**（不过滤 P1→81.6%） | ✅ README §6.9 |
| A20 | 本体候选置信 | `llm_ontology.py:76` | 0.85 | 继承 A4 | ✅ 同 A4 |
| A21 | 本体规模参数 | `llm_ontology.py:161-162` | `min_count=1`、`max_triggers=8` | 拍定 | ❌ 无验证 |
| A22 | 本体触发词 lift 收口 | `llm_ontology.py:243-244` | `min_lift=3.0`、`min_df=2` | **实测标定**（不过滤 P1→60.5%） | ✅ README §6.9 |
| A23 | LLM 输出默认置信 | `llm_backend.py:89,97` | 0.6 | 拍定（模型漏字段时兜底） | ❌ 无验证 |
| A24 | 域归并失败自检 | `llm_ontology.py:124` | 归并后种数 `>= 95%` 原种数 → 报错 | **实测标定**（账户欠费 402 静默降级踩坑） | ✅ 有 log 护栏 |
| A25 | 专有名词护栏 | `llm_backend.py:543` | `n >= 2` 词长 + 词性 `nr/ns/nt/nz` | 拍定（「苏利曼是苏丹」） | ✅ README §6.6 |
| A26 | LLM 调用超参 | `llm_backend.py:208` | `temperature=0.0`、`timeout=20.0` | 拍定（确定性优先） | ❌ 无验证 |

### B 构建门槛

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| B1 | **P0 框架数验收** | `llm_ontology.py:466`、`ontology_clean.py:373` | **≥ 300** | 方案 §8 拍定 | ✅ 实测 2,177（超额 7×） |
| B2 | **P2 层级覆盖率验收** | `health.py:114`、`evaluate_real.py:245` | **> 0.85** | 方案 §7 拍定 | ⚠️ 报出口径 100% / **诚实口径 82.4% 未达标** |
| B3 | 支持度分层 | `ontology_clean.py:107` | `core_min_support = 2` | 拍定（单例不删） | ✅ core-only 消融：longtail 贡献 +1.2pp 召回 |
| B4 | R1 自环删除 | `ontology_clean.py:124` | `source == target` | 拍定（建模错误） | ✅ 缓存重放三变体持平 |
| B5 | R2 明喻标记清理 | `ontology_clean.py:70` | 10 个标记词 | 继承 MIPVU（明喻也是隐喻） | ✅ 同上 |
| B6 | 平均元数下限 | `health.py:112` | `arity_floor = 2.2` | 拍定（2 = 退化为普通边） | ❌ 无敏感性 |
| B7 | 孤立端点率上限 | `health.py:113` | `orphan_ceiling = 0.8` | 拍定 | ❌ 无敏感性 |
| B8 | 未匹配池告警 | `health.py:244` | `> max(50, n_edges·0.3)` | 拍定（双阈值） | ❌ 无验证 |
| B9 | 脏摘要告警 | `health.py:248` | `> max(20, n_frames·0.5)` | 拍定 | ❌ 无验证 |
| B10 | 证据链为零告警 | `health.py:234` | `evidence_coverage == 0` | 拍定（0 是绝对缺陷） | ✅ 逻辑必然 |
| B11 | 孤儿框架打包规则 | `builder.py:33,186` | `"target"`（默认） | 拍定（保持历史口径） | ✅ 但 gen2 实测为**结构性缺陷**（99.2% 单目标域） |
| B12 | 扩展边溯源取最弱 | `extended.py:104` | `min(链上各边)` | 拍定（防「洗白」） | ✅ 有设计论证 |
| B13 | 文档分块大小 | `evaluate_document_corpus.py:43` | 500 字 | 方案 §4.6 拍定（400–600 区间） | ⚠️ 区间来自方案，取值未扫 |
| B14 | 分块重叠 | `evaluate_document_corpus.py:44` | 50 字（10%） | 拍定 | ❌ 无验证 |
| B15 | 单文档 chunk 上限 | `evaluate_document_corpus.py:45` | 40 | 拍定（成本控制） | ❌ 无验证 |
| B16 | 段落切分下限 | `evaluate_document_corpus.py:71` | `> 200` 字 | 拍定（鲁迅语料） | ❌ 无验证 |

### C 检索门槛

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| C1 | **自适应阈值 τ₀** | `context_budget.py:61` | 0.5 | **继承 HyperRAG**（WWW 2026） | ⚠️ A8 消融**测不出差异**（见下） |
| C2 | 阈值衰减步长 | `context_budget.py:61` | `decay = 0.1` | 继承 HyperRAG | 同上 |
| C3 | 最大衰减次数 | `context_budget.py:62` | `max_decays = 5` | 继承 HyperRAG | 同上 |
| C4 | 每跳最少保留 | `context_budget.py:62` | `min_keep = 50` | 继承 HyperRAG | 同上 |
| C5 | 高密度返回上限 | `context_budget.py:106` | `min_keep·3 = 150` | **拍定**（非 HyperRAG 原值） | ❌ 无验证 |
| C6 | 密度分档下界 | `context_budget.py:27` | `DENSITY_LOW = 2.35` | 继承 HyperRAG | ⚠️ 实测语料 Δ=1.07~2.17 **全部落在 low 档** |
| C7 | 密度分档上界 | `context_budget.py:28` | `DENSITY_HIGH = 5.0` | 继承 HyperRAG | ⚠️ 同上，high 档从未触发 |
| C8 | RRF 平滑常数 | `retrieval.py:32` | `k = 60` | **继承文献**（Cormack et al. 2009） | ❌ 无消融 |
| C9 | `top_k` 族 | `retrieval.py:138,317`、`metagraph.py:103,112` | 10 / 20 / 60 / 5 | 拍定（四处各不相同） | ⚠️ A6 实测 top_k=5 低估 17pp |
| C10 | 多线索汇聚阈值 | `retrieval.py:218,224` | `threshold=0.3`，判定 `s >= 2·threshold = 0.6` | 拍定（「≥2 触发词」的等价式） | ❌ 无验证 |
| C11 | clue 特征截断 | `retrieval.py:312`、`training.py:125,167` | `min(1.0, 0.5·hits)` | 拍定 | ❌ 无验证 |
| C12 | 中心性公式 | `retrieval.py:78`、`training.py:123,164` | `0.5·len(ground) + 0.5·[有级联]` | 拍定 | ⚠️ 是 `struct` 特征来源；人工权重过权 37–49× |
| C13 | 跨域检索打分 | `retrieval.py:170,191` | `confidence + 0.3·len(ground)` | 拍定 | ❌ 无验证 |
| C14 | 上下文预算 50/30/20 | `context_budget.py:146` | `(0.5, 0.3, 0.2)` | **继承 HyperRAG** | ✅ 有 `sum==1.0` 断言；`evaluate_packing_ablation` 做过 judge 消融 |
| C15 | token 预算 / 换算 | `context_budget.py:145,147` | `max_tokens=3000`、`chars_per_token=1.6` | 拍定 | ❌ 无验证 |
| C16 | 语义回退级联数 | `retrieval.py:185` | `sims[:2]` | 拍定 | ❌ 无验证 |
| C17 | 缓存容量 | `retrieval.py:239`、`observability.py:284` | 256 / 4096 | 拍定 | ❌ 无验证 |
| C18 | 元图打分权重 | `metagraph.py:145-151` | 0.5 / 0.3 / 0.4 | 拍定（启发式） | ❌ 无验证 |

> C1–C5 合起来构成一个**结构性事实**（本文件首次量化，见 §3.C）：
> `tau0 − decay·max_decays = 0.5 − 0.5 = 0.0`，即**衰减只能把阈值降到 0**。
> 而 `min_keep=50` 使得**候选数 ≤ 50 时衰减必然跑满 5 次**，`select()` 等价于
> 「全量返回、不设阈值」。实测 doc_project（17 条边）与全量语料（Δ=1.071）
> 均落在此区间 → **A8 消融测不出差异是结构必然而非经验发现**。

### D 链接判据（L1.5 扩展隐喻）

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| D1 | **P3 跨 chunk 消歧门槛** | `eval_corpus.py:93` | **> 0.70** | 方案 §7 拍定 | ✅ 诊疗集 F1=1.000；⚠️ 精选集，不可外推 |
| D2 | 分组判据 | `extended.py:53` | 同 `(frame_id, source_domain)` | 语言学论证（方案 §4.2） | ✅ |
| D3 | 间距约束 | `extended.py:38,71` | `max_gap = 3`，判定 `gap < 3` | 拍定 | ✅ 金标含负样本校验（跨距误并 = 0） |
| D4 | 喻底交集判据 | `extended.py:71` | `overlap >= 1` | 拍定 | ⚠️ 严格口径精度仅 **16.7%**（README §7.3） |
| D5 | 延续性判据（新增） | `extended.py:75` | 共享触发词 **或** 喻底交集 ≥ 2 | **实测标定**（针对 16.7% 失败模式） | ⚠️ 文本级无效（密度 52→49）；语义级有效（精度 16.7%→63.6%） |
| D6 | 跨距误并检出口径 | `evaluate_retrieval.py:90` | `ids[-1] - ids[0] >= 3` | 与 D3 同源（负样本检查） | ✅ |

### E 可靠性 / 可观测性

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| E1 | 本体登记框架可靠性 | `provenance.py:39` | 1.0 | 拍定（上限） | ✅ |
| E2 | 回退框架封顶 | `provenance.py:41` | 0.5 | 继承 VCP/RiverMemo 模式 | ✅ 保住 +55.8pp 召回 |
| E3 | 折扣下界 | `provenance.py:43` | 0.5 | 拍定 | ✅ floor 全档位扫描（1.0/0.9/0.75/0.5）**无一档优于基线** |
| E4 | 通道关闭开关 | `provenance.py:44` | 1.0 | 定义（恒等） | ✅ 逐位复原历史口径 |
| E5 | 类型可靠性三档 | `ontology.py:130-132` | 1.0 / 0.5 / 0.0 | 拍定（可核验通过 / 无法核验 / 可核验否决） | ✅ 有单测 + 修掉真实特征漂移 |
| E6 | 几何平均 ε 下界 | `observability.py:51` | `1e-3` | 拍定（防与门） | ✅ gen3 实测：ε 下界**完全按设计工作**（20/20 恒等式） |
| E7 | 单流量熵约定值 | `observability.py:52` | 0.5 | 继承 RiverMemo（「单条正流量取有限值」） | ❌ 约定值，无标定 |
| E8 | sparse/dense 分界 | `observability.py:53` | `SPARSE_MAX = 0.5` | 拍定 | ⚠️ **报告自己承认「阈值 0.5 是任意的」**，已扫 0.5/0.3/0.2/0.1 |
| E9 | Ω 门控阈值 | `observability.py:294` | `theta = 0.0` | 退化用法（等价 `if not agg`） | ✅ 门控等价性实验 |
| E10 | 保守取值不变式 | `provenance.py:85` | `min(stored, derived)` | 拍定（防伪升级） | ✅ 有单测 |
| E11 | 无证据权威度回落 | `models.py:124` | 0.5 | 拍定 | ❌ 无验证 |
| E12 | 冲突消解半衰期 | `models.py:230` | `half_life_days = 365.0` | 拍定（一年） | ❌ 无验证 |
| E13 | 冷启动无证据时 | `models.py:252,255` | 0.5 | 拍定 | ❌ 无验证 |
| E14 | 可靠性缓存容量 | `observability.py:284` | 4096 | 拍定 | ❌ 无验证 |
| E15 | Ω 完全无激活特判 | `observability.py:252` | 严格 0（不走 ε） | 拍定（语义区分） | ✅ 有单测 |
| E16 | 完备度定义 | `observability.py:215` | 覆盖字符 / 总字符，clip [0,1] | 拍定 | ⚠️ gen3 实测完备度是**共线但非主因** |
| E17 | 激活权重定义 | `observability.py:248` | 框架被多少触发词命中 | 拍定 | ✅ |

### F HGNN / 谱条件

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| F1 | 传播层数 | `hgnn.py:26` | `layers = 2` | 拍定（HyperC2Net 两步） | ✅ 逐层实测：layers=2 时同分量余弦仅 0.388（未坍缩） |
| F2 | 源项系数 | `hgnn.py:28` | `alpha = 1.0` | 定义（= 历史无源项行为） | ✅ α=1/ε=0 与历史**逐位相同**（maxdiff = 0） |
| F3 | 阻尼系数 | `hgnn.py:28` | `leak = 0.0` | 定义（= 历史行为） | ✅ 同上 |
| F4 | **谱半径收敛条件** | `hgnn.py:60` | `alpha·(1−leak/2) < 1` 严格成立，否则 `ValueError` | **数学必然**（Neumann 级数） | ✅ 单测 5 组参数校验 |
| F5 | leak 定义域 | `hgnn.py:56` | `0 ≤ leak < 1` | 数学必然（行和 = 1−ε/2 > 0） | ✅ 单测 |
| F6 | alpha 定义域 | `hgnn.py:58` | `alpha >= 0` | 拍定 | ✅ 单测 |
| F7 | 零范数保护 | `hgnn.py:230` | `na < 1e-9` → 返回 0.0 | 拍定（防除零） | ✅ |
| F8 | 检索 k 默认 | `hgnn.py:234,251` | `k = 10` | 拍定 | ❌ 无验证 |
| F9 | 嵌入维度 | `embeddings.py:25` | `DIM = 512` | 拍定（须与 HGNN 矩阵一致） | ⚠️ 玩具级哈希编码器，非真实句向量 |

### G 训练 / 评测

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| G1 | **泄漏判定阈值** | `training.py:216` | 单特征 AUC `>= 0.98` → 拒绝上报 | **实测标定**（抓「接近可分」的软泄漏） | ✅ 对 chain/cascade 模式正确触发 |
| G2 | 完美可分判定 | `training.py:225` | `threshold = 1e-9` | 数学必然 | ✅ 单测 |
| G3 | 负正样本配比 | `training.py:246,345,575`、`evaluate_llmgold.py:413` | `negatives_per_positive = 3` | 拍定 | ⚠️ 未扫；`--npp` 可调 |
| G4 | 随机种子 | `training.py:248,347,464,576` | 42 | 拍定（惯例） | ❌ |
| G5 | 训练超参 | `training.py:485-487` | `epochs=50`、`batch_size=32`、`lr=0.1`、`patience=10`、`l2=1e-4` | 拍定（docstring 称「与 HyperRAG 对齐」） | ❌ 无扫描 |
| G6 | 标准化零方差保护 | `training.py:477` | `sd < 1e-8` → 1.0 | 拍定 | ✅ |
| G7 | **人工权重（历史）** | `training.py:62` | `{sem 0.35, struct 0.25, clue 0.20, type 0.20}` | **手拍** | ❌ **实测 struct 过权 37–49×、type 12–19×** |
| G8 | **人工权重（现行）** | `training.py:65,76` | 按 110 个伪文档学到权重的均值归一化 | **实测标定** | ✅ 权重校正后 MRR 0.4809 → 0.5496（反超训练） |
| G9 | 特征顺序硬契约 | `training.py:41-49`、`evaluate_retrieval.py:41` | `FEATURE_NAMES` 7 维定序；`ROLE_IDX = [4,5,6]` | **契约**（重排会静默改变已上报数字） | ✅ 单测钉死 |
| G10 | 手写累加顺序 | `training.py:79-95` | 逐项顺序累加（禁 numpy 点积） | **实测标定**（浮点结合序差异 → 632 条查询中 1 条排序不同） | ✅ 单测 |
| G11 | A7/A9 结论阈值 | `evaluate_fullcorpus.py:297-306` | `|ΔMRR| <= 0.02` 视为无差异 | 拍定 | ✅ 用于 H5/H7 证伪 |
| G12 | H3 结论阈值 | `evaluate_retrieval.py:409` | `ΔRecall > 0.2` | 拍定 | ✅ |
| G13 | A5 结论阈值 | `evaluate_retrieval.py:411` | `ΔF1 > 0.2` | 拍定 | ✅ |
| G14 | A8 结论阈值 | `evaluate_retrieval.py:413` | `ΔRecall > 0.05` | 拍定 | ✅ |
| G15 | HGNN 判别力判据 | `evaluate_hgnn.py:395` | `acc > 0.5` | 拍定（随机水平） | ⚠️ 报告承认 n=20 功效不足，已改用全量 AUC |
| G16 | judge 失败率中止 | `evaluate_llmgold.py:269` | `> 0.2` → 告警 | 拍定（防半残金标） | ✅ |
| G17 | 金标键完整性 | `evaluate_llmgold.py:254` | 缺失 `> 50%` → 跳过该问题 | 拍定 | ✅ |
| G18 | 调参/报告集切分 | `evaluate_llmgold.py:446-448` | 偶数= tune / 奇数= report | 拍定（防测试集调参） | ✅ |
| G19 | A6 预算对等 | `evaluate_a6.py:136` | `--meta-top-k = 20` | **实测标定**（原硬编码 5 低估 17pp） | ✅ 20 已与无上限等价（1.0000） |
| G20 | κ 参考档 | `evaluate_gold_audit.py:206` | ≥0.8 几乎完美 / 0.6–0.8 高度一致 | **继承文献**（Landis & Koch） | ✅ 实测 κ=0.965 |
| G21 | 抽样规模 | `evaluate_gold_audit.py:64`、`evaluate_chain_quality.py:95`、`ontology_bilingual.py:348` | 50 / 30 / 84 | 拍定（成本约束） | ❌ |
| G22 | 一致性抽检温度 | `ontology_bilingual.py:348` | `temp = 0.7` | 拍定 | ❌ |
| G23 | coherence 过滤阈值 | `evaluate_chain_quality.py:104`、`论文初稿.md:468` | CLI 默认 0.0（关闭）；实测用 0.5 | 拍定 | ❌ **完全无效**：保留链 52→52 |
| G24 | 429 退避重试 | `evaluate_packing_ablation.py:72` | `attempt == 4`（共 5 次，间隔 5·(n+1) 秒） | 拍定 | ❌ |
| G25 | 断点检查点间隔 | `llm_backend.py:858` | `checkpoint_every = 10` 批 | 拍定（长任务防丢） | ❌ |
| G26 | LLM 批量大小族 | `llm_backend.py:647,695,757,820` | refine/discover 20、verify 8 | 拍定（摊薄样板开销） | ⚠️ README §6.8 称 20 句/批省 86% 样板 token |

### H 不变量（invariants）

| # | 名称 | 位置 | 陈述 | 护栏 |
|---|---|---|---|---|
| H1 | **传输算子行和 < 1** | `hgnn.py:150`、`test:1579` | `M = 0.5(I + (1−ε)S)` 行和 `= 1−ε/2 < 1` 严格成立；`ρ(M) ≤ 1−ε/2` | 单测遍历 ε ∈ {0.01, 0.05, 0.1, 0.5} |
| H2 | S 行随机 | `test:1563` | `S` 行和**恰为 1**（无源项必然坍缩的根源）；`ρ(S) = 1` | 单测（atol=1e-12） |
| H3 | **Ω 只读查询** | `observability.py:15-18`、`test:1313` | 签名无候选池形参；632 查询 × 4 种池扰动 → **0/632** 变化 | 单测 + 签名检查（禁用 8 个形参名） |
| H4 | **候选永不丢弃** | `provenance.py:16-18` | 折扣是「有下界的乘性因子 ∈ [floor, 1]」，`factor ≥ floor > 0` | 单测 `test_reliability_factor_is_capped_and_never_zero` |
| H5 | **特征口径一致（单一真源）** | `ontology.py:445`、`retrieval.py:303` | 两条打分路径必须走同一 `type_reliability_of` 与 `hand_weighted_score` | 单测 `test_two_scoring_paths_share_feature_schema` |
| H6 | **判据用 `get_frame()` 而非前缀** | `provenance.py:26-31`、`health.py:170-173` | 生产本体 98.6% 框架以 `F_LLM_` 开头，按前缀判定会全盘误判 | 单测 `test_judgement_is_registration_not_prefix`（两处） |
| H7 | 边 id 确定性 | `extractor.py:203-209` | 必须 md5，禁用 uuid4 / 内置 hash（`PYTHONHASHSEED` 随机化） | 单测 `TestDeterministicIds` |
| H8 | 预算比例和为 1 | `context_budget.py:148` | `|Σratios − 1| > 1e-6` → `ValueError` | 构造期断言 |
| H9 | 类型约束不丢弃候选 | `ontology.py:122-129` | 回退框架拿 0.5 而非 0.0，仍参与排序 | 单测三档 |
| H10 | 诚实覆盖率 ≤ 报出口径 | `test:1807` | `registered_hierarchy_coverage <= hierarchy_coverage` | 单测 |
| H11 | 不传 ontology 时历史口径逐位不变 | `health.py:122` | `registered_*` 保持 `None`，报告不含该行 | 单测 `test_honest_coverage_backward_compatible` |
| H12 | 扩展边溯源取链上最弱 | `extended.py:104` | `min(各边 provenance_reliability)`，防退化边借合并洗白 | 设计论证 |
| H13 | 可靠性只采信更保守值 | `provenance.py:85` | `min(stored, derived)` | 单测 |
| H14 | 本体 id 稳定 | `llm_ontology.py:67`、`builder.py:230` | md5 前 8 位，跨进程可复现 | 单测 |
| H15 | 评测入口可导入 | `test:2884` 附近 | 10 个评测模块全部可导入 + CLI 参数完整（合并回归护栏） | 2 项单测 |

### I 外部参考实现（`metaphor_graph/rmtop.rs`，RiverMemo 拓扑 V3）

> 该文件是**外部系统的 Rust 源码副本**（1 分 39 秒读入，99681 字节），
> 本项目通过 `experiments/对照分析_RiverMemo.md` 借用其机制设计。
> **它不是本项目的运行时依赖**，其参数值不进入本项目任何指标。
> 但任务清单里的「工况阈值 0.12/0.45」正出自这里，故单列并明确标注归属。

| # | 名称 | 位置 | 取值 | 依据 | 验证状态 |
|---|---|---|---|---|---|
| I1 | collapsed 阈值 | `rmtop.rs:269` | 0.12 | 上游系统拍定 | ❌ 本项目未验证 |
| I2 | sparse 阈值 | `rmtop.rs:270` | 0.45 | 上游系统拍定 | ❌ 同上 |
| I3 | 结构角色最小 Ω | `rmtop.rs:290` | 0.12 | 上游系统拍定 | ❌ |
| I4 | 条件直接带宽 | `rmtop.rs:284` | 0.12 | 上游系统拍定 | ❌ |
| I5 | 回退可靠性封顶 | `rmtop.rs:276` | 0.5 | 上游系统拍定 | ✅ **本项目借用了这个值**（E2） |
| I6 | Ω epsilon | `rmtop.rs:268` | 0.02 | 上游系统拍定 | ⚠️ 本项目用了 1e-3（E6），**未沿用** |

> **重要澄清**：任务描述把 0.12/0.45 归为「工况阈值」，暗示它在本项目内生效。
> 实测：本项目 `observability.py` 的 regime 是 **collapsed / sparse(<0.5) / dense**，
> **不含 0.12 与 0.45**。0.12/0.45 仅存在于 `rmtop.rs` 这份上游源码里。
> 本项目自己的分档值只有 E8 的 `SPARSE_MAX = 0.5`。

---

## 2. 详细块（按家族）

### 2.A 抽取门槛

#### A1 · P1 字面误判率硬门槛 —— 本项目唯一的抽取侧 Go/No-Go

- **位置**：`论文初稿.md:184`（「P1（硬门槛 <15%）」）、`metaphor_graph/README.md:645`、
  `metaphor_graph/evaluate_real.py:115`（`"✅ <0.15 达标" if ... < 0.15`）、
  `test_metaphor_graph.py:334/418/700`（三处单测护栏）
- **取值**：0.15，单位 = FP/(FP+TN) 的比率
- **判定什么**：决定 L1 抽取器能否进入下一阶段。方案 §6.5 明写「P1 未达门槛则暂停回炉」
- **依据**：**方案拍定**（`知识隐喻分析任务方案.md` §6.5），非实测标定
- **验证**：✅ 已跑。`evaluate_real.py` 在 CCL2018 全量（n=1100，含 76 中性句）
  实测 **0.092**。论文 §5.1 给出完整帕累托前沿：
  - 规则侧天花板：召回 9.7% / P1 7.9%
  - + LLM 0.85 + refine：召回 **69.6%** / P1 **9.2%** / F1 0.818 ✅
  - + LLM 0.5 不设防：召回 89.6% / P1 **32.9%** ❌ 撞穿门槛
- **若改变会怎样**：**实测过的**。阈值放宽到 0.5 → P1 32.9%（超门槛 2.2×），
  召回 +20pp。放宽到 0.15 以外无意义（已是硬门槛）。README §6.4 记录：
  「纯触发词自举的召回被 P1 门槛钉死在 ~6–8%」——**这是本项目最重要的结构性约束**：
  P1 门槛是整个抽取侧召回天花板的成因。

#### A4 · LLM 置信达标拐点 0.85

- **位置**：`evaluate_real.py:150`、`evaluate_llmgold.py:390`、`evaluate_fullcorpus.py:139`、
  `evaluate_repaired.py:353`、`evaluate_document_corpus.py:273`、
  `evaluate_a6.py:156`（硬编码）、`ablation.py`（7 处硬编码）、`llm_ontology.py:76`、`demo_rag.py:114`
- **取值**：0.85
- **判定什么**：LLM 开放发现候选的准入门槛（`cand.confidence < self.llm_conf_threshold` → 丢弃）
- **依据**：**实测标定**。README §6.7：「0.85 是实测的达标拐点（单独用阈值时 P1 14.5%）」
- **验证**：✅ 论文 §5.1「双防线」表：仅阈值 0.85 → P1 14.5%；加 refine → 9.2%
  （代价：召回 69.1% → 66.3%）。README §6.7 记录扫描过程：
  「真隐喻置信普遍 0.9+，误判多在 0.6–0.85，抬高阈值能精准切掉误判」
- **若改变会怎样**：**实测过的**。降到 0.5 → P1 32.9%（超门槛）。这是全项目
  标定最扎实的一个阈值。

#### A3 · `llm_conf_threshold` 构造器默认 0.5

- **位置**：`extractor.py:46`
- **取值**：0.5
- **判定什么**：`MetaphorExtractor` 未显式传参时的 LLM 候选门槛
- **依据**：**拍定**。docstring 只写「默认比基础阈值更严，压住 P1」
- **验证**：❌ **无实证**。README §6.7 明说 0.5 是「不设防」档，P1 32.9%。
  **生产代码没有一处使用这个默认值** —— 全部 20+ 处调用点都显式传 0.85。
  实测 `grep -rn "llm_conf_threshold=0.85"` 命中 12 个模块。
- **若改变会怎样**：若有人依赖默认值构建抽取器（如新写的脚本），
  会**直接拿到 P1=32.9% 的配置**。这是一个**危险默认**：
  README §6.7 的「不设防」实验证明该值撞穿硬门槛 2.2 倍。
- **⚠️ 判定**：**取值无实证依据，且与硬门槛冲突**。建议改默认为 0.85。

#### A7 · MIPVU 三条排除项（refine 判据）

- **位置**：`llm_backend.py:132-141`（`_MIPVU_RULE` 常量）
- **取值**：3 条排除项 —— ① 已词汇化的成语/惯用语（七上八下/守株待兔）；
  ② 纯描写性修饰语/美称（琼玉世界/金色大厅）；③ 字面用法与身份判断句（苏利曼是苏丹）
- **判定什么**：写进 discover / refine 的系统提示词，决定 LLM 判「是否隐喻」
- **依据**：**继承文献**（MIPVU，Steen et al. 2010）+ 实测补强
- **验证**：✅ README §6.6：「不加时模型会把固化成语（"七上八下"）、描写性美称
  （"琼玉世界"）、拟人（"钟塔告诫学子"）都判成隐喻，CCL2018 全量上 **P1 直接飙到 28.9%**
  （门槛 15%）」。论文 §3.2 复述同一数字。
- **若改变会怎样**：**实测过的**。去掉 → P1 28.9%（超门槛 1.9×）。
- **附带设计**：`_FIELDS_SPEC` 强制输出 `basic_meaning` 字段，「逼模型先把 MIPVU
  判据走一遍再下结论」—— 这是一个**提示工程层的判据强制**，无独立消融。

#### A19 / A22 · 触发词泛用剔除与 lift 收口

- **位置**：`llm_ontology.py:138-139`（`min_len=2`、`max_pairs=3`）、
  `llm_ontology.py:243-244`（`min_lift=3.0`、`min_df=2`）
- **判定什么**：决定 LLM 自举产出的触发词能否写进本体
- **依据**：**实测标定**，两处都有极端的失败数字支撑
- **验证**：✅ README §6.9 两张表：
  | 配置 | 规则侧召回 | 规则侧 P1 |
  |---|---|---|
  | 不用自举触发词 | 7.6% | 7.9% ✅ |
  | 自举本体但清空触发词 | 7.6% | 7.9% ✅ |
  | 自举触发词 min_df=2 | 34.4% | **32.9%** ❌ |
  | 自举触发词 min_df=10 | 11.9% | 14.5% ⚠️ |
  | 自举触发词 min_df=20 | 10.2% | 7.9% ✅ |
- **若改变会怎样**：**实测过的**。这是全项目**唯一被完整扫描过的一族参数**。
  结论：自举触发词的 train→test 泛化极差（召回涨 4.5×、误判也涨 4×），
  「收紧到 P1 达标时召回只剩 10~12%，性价比很低」。
  `_filter_triggers` 的 docstring 直接写：不过滤时 **P1 飙到 81.6%**。

### 2.B 构建门槛

#### B2 · P2 层级覆盖率 > 85% —— 状态最复杂的一个门槛

- **位置**：`health.py:114`（`coverage_floor=0.85`）、`evaluate_real.py:245`
- **取值**：0.85，单位 = `min(frame_coverage, cascade_coverage)`
- **判定什么**：L2/L3 归属是否建立完成
- **依据**：方案 §7 拍定
- **验证**：⚠️ **双口径**，这是本项目最重要的诚实性修正之一：
  | 口径 | 实测 | 状态 |
  |---|---|---|
  | 报出口径（`graph_health(shg)`） | **1.000** | ✅ |
  | **诚实口径**（`graph_health(shg, ontology=...)`） | **0.824** | ❌ **未达标** |
- **若改变会怎样**：已量化。`health.py:170-173` 的注释记录：
  「实测在 1100 句评测集上：超边 883 条，报出覆盖率 1.000，但本体正式登记的只有
  685/883 = 0.776」。两个独立实验分支（`exp/degrade` 与 `exp/cascade`）
  各自确认了 22.4pp 的注水。论文附录 B 已把 P2 状态从 ✅ 改为 **⚠️ 条件性达标**。
- **注水机制**：抽取器为未知喻体临时建 `F_LLM_*` 回退框架，
  由 `builder._ensure_cascades` 按**目标域**事后补 `C_ADHOC_*` 级联才够到 100%。
  `builder.py:161-166` 自己承认这是「已知结构缺陷」。

#### B3 · 支持度分层 core/longtail 的 count 阈值

- **位置**：`ontology_clean.py:107`（`core_min_support: int = 2`）、`ontology_clean.py:132`
- **取值**：`support >= 2` → core，否则 longtail
- **判定什么**：只打标签，**不删框架**（docstring 明确：「单例不删」）
- **依据**：拍定
- **验证**：✅ core-only 消融实测：V2 清洗 core-only（299 框架）召回 **68.5%**，
  比 V1 全量（2177 框架）的 69.6% **低 1.2pp**。结论：「longtail 单例框架是
  P2 模糊匹配的锚点，删了会掉召回」。生产默认两级全载。
- **若改变会怎样**：**实测过的**。若改成只留 core，召回 −1.2pp。
  这是一个**取值本身未被验证、但后果已被量化**的典型。

#### B1 · P0 框架数 ≥ 300

- **位置**：`llm_ontology.py:466`、`ontology_clean.py:373`
- **取值**：300
- **判定什么**：本体冷启动是否完成
- **依据**：方案 §8/§9.1 拍定（原文提到「目标 ≥1000 框架」）
- **验证**：✅ 实测 **2,177**（清洗后），超额 7 倍；README §6.9 记录自举前只有 31 个
  （差 10 倍），自举后 2222。
- **若改变会怎样**：未做敏感性。但 README §6.3 提到「目标 ≥1000 框架」，
  即项目内部存在**两个不同目标值**（300 是验收线，1000 是设计目标）。

#### B6–B9 · 图健康度四阈值

| 指标 | 取值 | 含义 | 依据 | 验证 |
|---|---|---|---|---|
| `arity_floor` | 2.2 | 超边平均元数下限 | 拍定（2.0 = 退化为普通边，留 0.2 余量） | ❌ |
| `orphan_ceiling` | 0.8 | 度 ≤1 端点占比上限 | 拍定 | ❌ |
| 未匹配池 | `max(50, n_edges·0.3)` | 本体跟不上语料 | 拍定（绝对+相对双阈值） | ❌ |
| 脏摘要 | `max(20, n_frames·0.5)` | 元图上层索引滞后 | 拍定 | ❌ |

- **判定什么**：只产出 `warnings` 列表，`healthy()` 返回 `not warnings`
- **验证**：❌ **四项均无消融、无敏感性分析、无实测标定**。
  `health.py` 的 docstring 说明了每个指标的**语义**，但没有一处说明**取值来源**。
  这是本文件发现的最大一片「无依据阈值」集中区。

### 2.C 检索门槛

#### C1–C7 · 自适应阈值与密度分档 —— 一个结构性失效

- **位置**：`context_budget.py:27-28,61-62,106`
- **取值**：τ₀=0.5、decay=0.1、max_decays=5、min_keep=50、
  DENSITY_LOW=2.35、DENSITY_HIGH=5.0、high 档上限 = min_keep·3 = 150
- **依据**：**继承 HyperRAG（WWW 2026）**。`context_budget.py:1-19` 的模块
  docstring 逐条列出上游取值，属**文献继承**而非本项目标定。
- **验证**：⚠️ A8 消融**测不出任何差异**。README §7.3：
  「在本 2 文档 8 查询的稀疏小语料上，关掉自适应阈值后跨域 Recall **完全不变（0.500）**」；
  全量语料（密度 Δ=1.071）复验：「A8 仍无差异，Recall@10 完全一致（0.250）」。
- **本文件的补充分析（机械提取无法发现的）**：
  1. **衰减幅度恰好用尽**：`tau0 − decay·max_decays = 0.5 − 0.5 = 0.0`。
     阈值最多降到 **0.0**，即**不可能滤掉任何非负分数**。
  2. **`min_keep=50` 使衰减必然跑满**：只要候选数 ≤ 50，
     `len(selected) < min(min_keep, len(items))` 恒真 → 循环跑满 5 次。
     实测验证（n=5/17/49/50/51/200，分数全 0.12）→ **全部返回 100% 候选**。
  3. **实际语料规模远小于 50**：doc_project 仅 17 条边；全量语料 856 条边 / 110 文档
     ≈ 7.8 条/文档。→ **`select()` 在本项目全部已上报实验中都是恒等函数**。
  4. **密度档位从未切换**：实测 doc_project Δ=2.1667（≤2.35 → low）；
     全量语料 Δ=1.071（low）。→ **high 档的 `max_keep=150` 分支从未执行**。
- **结论**：A8 的「中性结论」**不是经验发现，而是结构必然**。
  上游 HyperRAG 的取值是为**大规模稠密超图**设计的（每跳 ≥50 条边），
  本项目的隐喻超图规模小两个数量级，**机制未进入工作区间**。
  论文与 README 目前把 A8 表述为「需放到更大/更稠密的检索集上才能验证」，
  这个表述方向正确，但**未指出参数本身在该规模下是恒等的**。

#### C8 · RRF 融合 k=60

- **位置**：`retrieval.py:32`（`def _rrf(rank_list, k: int = 60)`）
- **取值**：60
- **判定什么**：`score += 1/(k + rank + 1)`，融合字面通路与隐喻通路
- **依据**：**继承文献**（Cormack, Clarke & Buettcher, SIGIR 2009 的标准取值）
- **验证**：❌ 无消融。且 `_rrf` 是**模块级私有函数**，无 CLI 参数暴露。
- **若改变会怎样**：未测。理论上 k 只改变长尾衰减速度；本项目候选数 ≤ 数十，
  `rank+1 << k`，故 `1/(60+r+1) ≈ 1/60` 近似常数 → **k 在本项目规模下近乎无影响**。

#### C9 · `top_k` 族 —— 四个不同默认值

| 位置 | 取值 | 用途 |
|---|---|---|
| `retrieval.py:138` | 10 | `cross_domain_retrieve` |
| `retrieval.py:317` | 20 | `rank_mappings` |
| `metagraph.py:112` | 60 | `MetaphorURetrieval.retrieve` |
| `metagraph.py:103` | 5 | `_literal_retrieve` |

- **依据**：四处**各自拍定**
- **验证**：⚠️ **A6 消融实测过其中一个**：`rank_mappings(top_k=5)`（硬编码）
  与常识通路的「无上限」不对等，**低估隐喻通路 Recall@10 约 17pp**
  （0.8287 → 1.0000）。已修为 `--meta-top-k=20`（20 已与无上限等价）。
- **若改变会怎样**：**实测过的**。这是本项目**第三个被发现的同类缺陷**
  （`audit_fairness.py` 的 docstring 列举三处：§6.1 候选池 ≤10 平凡饱和、
  §6.2 权重错配 37 倍、§6.4 A6 预算不对等）。
  该脚本是为此新增的**静态审计工具**，检查各评测脚本的预算参数是否两臂对等。

#### C14 · 上下文预算 50/30/20

- **位置**：`context_budget.py:146`
- **取值**：`(0.5, 0.3, 0.2)` = 超边 / 实体 / 源文本块
- **判定什么**：生成阶段三类组件的 token 分配；未用完的额度顺延给下一类
- **依据**：**继承 HyperRAG**（docstring：「与 HyperRAG 一致：超边信息密度最高，
  给最多；源文本块是「肉」，给最少」）
- **验证**：⚠️ 有 `evaluate_packing_ablation.py`（4 个变体 `ctrl_vec/curr/light/chunk_only`
  × 4 个 judge 维度）。**但该消融测的是「打包方式」而非「50/30/20 比例本身」**。
  且它需要 LLM_API_KEY，`experiments/` 下**没有对应的结果报告文件**。
- **不变量**：`|Σratios − 1| > 1e-6` → `ValueError`（H8）

#### C15 · token 预算与字符换算

- **位置**：`context_budget.py:145,147`
- **取值**：`max_tokens = 3000`、`chars_per_token = 1.6`
- **依据**：**拍定**。1.6 是中文的经验换算率，但**无引用、无实测**
- **验证**：❌ 无。`_cost(text) = max(1.0, len(text)/1.6)`
- **若改变会怎样**：未测。该值直接决定「多少超边能塞进上下文」，
  与 C14 的比例耦合。

### 2.D 链接判据（L1.5）

#### D1 · P3 跨 chunk 消歧门槛 > 70%

- **位置**：`eval_corpus.py:93`（`THRESHOLD_P3_ACC = 0.70`）、`baselines.py:137`
- **依据**：方案 §7 拍定
- **验证**：✅ 诊疗集 F1 = **1.000**（两篇文档各 4/3 条链全中，跨距误并 = 0）。
  ⚠️ **但 README 自己加了限制**：「这是**精选诊疗集**（语料即按可检测隐喻设计），
  证明机制在干净案例上正确重构；不是大规模基准，数字应读作「机制可用」而非「泛化上界」」。
  全量语料（CCL2018 独立短句）上扩展链天然稀疏（仅 5 条/110 文档）。
- **若改变会怎样**：`evaluate_retrieval.py` 用 `macro_f1` 与 `THRESHOLD_P3_ACC` 比较出
  `status` 字符串，仅影响打印。

#### D3/D4/D5 · 三判据合并

- **位置**：`extended.py:38,53,71,75`
- **取值**：
  ```
  同框架 + 同源域 (分组)
    AND gap < max_gap(=3)
    AND 喻底交集 ≥ 1
    AND [若 continuity=="vehicle_repeat"] (共享触发词 OR 喻底交集 ≥ 2)
  ```
- **依据**：
  - 间距 `max_gap=3`：拍定。**有金标负样本校验**（doc_project c10 与 c3/c4 同框架、
    间距 ≥3，机制未误合并 → 跨距误并 = 0）
  - 喻底交集 ≥1：拍定，**有语言学论证**（「若两 chunk 都用「战争」源域，
    但喻底分别是 [对抗,胜负] 与 [伤亡,代价]，可能属于同级联下不同框架，不该合并」）
  - `vehicle_repeat`：**实测标定**，为修复失败模式而新增
- **验证**：
  - ⚠️ **严格口径精度仅 16.7%**（README §7.3：52 条候选链经跨模型 judge 盲评）
  - `vehicle_repeat` **文本级无效**（密度 52→49，存活链不变）
  - **语义级有效**：`verify_chains_batch` 52 条通过 11 条（21.1%），
    保留集精度 **63.6%**（跨模型配对子集 71.4%）—— 相对未过滤 16.7% 约 **4 倍**
- **若改变会怎样**：**实测过的**。论文 §3.4 把这条写成「双段管线」
  （宽松生成保密度 + 语义校验保精度），并明确「结构信号的召回与精度
  不可由单一阈值同时优化」。

### 2.E 可靠性 / 可观测性

#### E2/E3 · 回退框架封顶 0.5 与折扣下界 0.5

- **位置**：`provenance.py:41,43`
- **取值**：`RELIABILITY_FALLBACK_CAP = 0.5`、`RELIABILITY_FLOOR = 0.5`
- **判定什么**：`reliability_factor(r, floor) = floor + (1−floor)·r ∈ [0.5, 1]`，
  乘到打分上改变次序但**永不归零**
- **依据**：
  - 0.5 封顶：**继承 VCP / RiverMemo 的「封顶可靠性通道」模式**
    （`provenance.py:10-12` 明确记录借鉴来源）
  - floor=0.5：**拍定**
- **验证**：✅ **`floor` 被完整扫描过**：`experiments/probe_floor.py` 扫
  `floors = [1.0, 0.9, 0.75, 0.5]`，结论：**「floor 全档位扫描无一档优于基线。
  净增益为零。」** 报告还给出机制解释：
  「句级判别 AUC = 0.3913（即反相关：字面句 100% 可靠度 1.0，
  而 21.7% 的真隐喻句可靠度 0.5）」——即**该通道的判别方向是反的**。
- **若改变会怎样**：**实测过的，且是负面的**。
  `RELIABILITY_FLOOR = 0.5` 这个默认值**在当前基底上不带来增益**，
  但保留它是因为：① 它不丢候选（召回结构不变）；② `floor=1.0` 可逐位复原历史口径。
  `experiments/REPORT_exp-degrade.md:368` 明确：「只是不能承担「影响 P1」的职责。
  默认 `reliability_floor=1.0` 语义等价于关闭」。
  **注意这里有一处口径混淆**：报告说「默认 reliability_floor=1.0」，
  但代码里 `provenance.RELIABILITY_FLOOR = 0.5`，`RetrievalEngine` 的默认
  `reliability_floor=provenance.RELIABILITY_FLOOR`（=0.5），
  `score_conditions(reliability=False)` 时根本不启用该通道。
  → **「默认」在三个层次上是三个不同的值**（常量 0.5 / 引擎 0.5 / 打分路径关闭）。

#### E8 · Ω 的 SPARSE_MAX = 0.5

- **位置**：`observability.py:53`
- **取值**：0.5
- **判定什么**：`regime_of(omega, n_frames, sparse_max)` → collapsed / sparse / dense
- **依据**：**拍定**
- **验证**：⚠️ **项目自己承认「阈值 0.5 是任意的」**（`REPORT_exp-cascade.md:415`），
  并已做敏感性扫描：
  | sparse_max | N3a collapsed | N3a sparse | N3a dense |
  |---|---|---|---|
  | 0.5 | 0.0% | 100.0% | 0.0% |
  | 0.3 | 0.0% | 100.0% | 0.0% |
  | 0.2 | 0.0% | 99.9% | 0.1% |
  | 0.1 | 0.0% | 97.3% | 2.7% |
  结论：「**结论方向不变**（自然查询族基本无 dense），但具体百分比是阈值产物」。
  另：重叠型全量查询池的 dense 率仅 4.3%，改写型仅 1 条（无统计意义）。
- **若改变会怎样**：**实测过的**。降阈值只会把极少数查询从 sparse 挪到 dense，
  不改变「Ω 与触发词命中数 ρ=0.9949」这一根本结论。

#### E6 · Ω 的 EPS = 1e-3

- **位置**：`observability.py:51`
- **取值**：`1e-3`
- **判定什么**：`geometric_mean` 的分量下界，防止一个 0 把 Ω 钉死为 0
- **依据**：拍定。**但上游 RiverMemo 用的是 0.02**（`rmtop.rs:268 omega_epsilon`），
  本项目用了 1e-3 —— **未沿用上游值，也未说明为何不同**。
- **验证**：✅ gen3 实测「**ε 下界完全按设计工作**（恒等式在 `source` 上 20/20 = 1.0000
  成立）——它只把 0/1 台阶变成 ε^(1/3) 台阶，信息量同为 1 bit」。
  单测 `test_geometric_mean_epsilon_floor` 断言 `(1·1e-3·1)^(1/3) = 0.1`。
- **若改变会怎样**：**实测过**：改变 ε 只改变台阶高度，不改变信息量。
  gen3 的 2⁴=16 种合成开关组合中 ε 下界不是主因（AUC 极差仅 0.126）。

#### E7 · SINGLE_FLOW_ENTROPY = 0.5

- **位置**：`observability.py:52`
- **取值**：0.5（只有一条正流量时的有限熵值）
- **依据**：**继承 RiverMemo 的退化约定**（docstring：「参考设计「单条正流量取有限值」」）
- **验证**：❌ **纯约定值，无任何标定或敏感性分析**。
  `normalized_entropy` 的三个分支（0 / 0.5 / H/log₂n）中，这个 0.5 是唯一
  带主观选择的。选 0 会让 Ω 归零（退化成与门），选 1 会掩盖坍缩。
- **若改变会怎样**：未测。它影响所有「单触发词查询」的 Ω_F，
  而 `REPORT_exp-cascade.md` 实测**单触发词层（n_seed=1）有 102 条**，
  是最大的一层。→ 影响面不小。

### 2.F HGNN / 谱条件

#### F1–F5 · 传播算子与收敛条件

- **位置**：`hgnn.py:26,28,56-63,150`
- **取值**：`layers=2`、`alpha=1.0`、`leak=0.0`；
  合法性约束 `leak ∈ [0,1)`、`alpha >= 0`、`alpha·(1−leak/2) < 1`
- **判定什么**：`forward()` 做 `X ← (1−α)X0 + α·M·X` 迭代 `layers` 次；
  非法参数在构造期抛 `ValueError`
- **依据**：
  - `layers=2`：**继承 HyperC2Net 两步传播**（docstring）
  - `alpha=1.0` / `leak=0.0`：**定义**，取这两个值即精确复原历史实现
  - 收敛条件：**数学必然**（Neumann 级数 `(I−αM)^{-1}` 要求 `α·ρ(M) < 1`，
    而 `ρ(M) ≤ 1−ε/2`）
- **验证**：✅ 极其扎实：
  - `test_S_rowsum_is_exactly_one`：S 行和恰为 1（atol=1e-12）
  - `test_spectral_radius_S_is_one`：`ρ(S) = 1.0`（places=9）
  - `test_leak_makes_rowsum_strictly_substochastic`：遍历 ε ∈ {0.01,0.05,0.1,0.5}，
    验证行和 `= 1−ε/2` 且 `ρ(M) ≤ 1−ε/2`
  - `test_alpha_one_equals_matrix_power`：α=1 时 `H = M^layers·X0`（atol=1e-10）
  - `test_alpha_one_has_no_fixed_point`：`cond(I−M) > 1e10`（奇异）
  - `test_default_is_undriven_and_unchanged`：α=1/ε=0 与历史**逐位相同**
  - `test_invalid_params_raise`：5 组非法参数全部拒绝
- **若改变会怎样**：**实测过的**（`exp/dynamics`）：
  - 逐层实测（无源项）：layers=2 时同分量余弦仅 **0.388**（距 1.0 很远），
    源信息保留 0.840 → **「退化」不能解释 layers=2 的 H4 数字**
  - 18 个 (α, ε) 配置下 `|acc_flat − acc_hgnn| ≤ 0.05`
  - 高功效口径（ROC-AUC）下 `|ΔAUC| ≤ 0.005`，95% CI 跨 0，**方向甚至轻微偏向 flat**
  - **源项的真实价值**：让深层迭代（layers ≥ 50）不再坍缩，**而非改善 layers=2**
- **⚠️ 关键背景**：`experiments/组件处置决策.md` 记录「**代码审计**——
  评分路径从不调用 HGNN，这解释了 flat ≡ HGNN」。即 **F1–F5 这组精心设计的
  谱条件参数，不在任何已上报指标的路径上**。

### 2.G 训练 / 评测

#### G1 · 泄漏判定阈值 AUC ≥ 0.98

- **位置**：`training.py:216`
- **取值**：`auc_threshold = 0.98`
- **判定什么**：`leakage_report(ds)` 返回单特征 AUC ≥ 0.98 的特征名；
  **非空 = 该样本集不适合上报指标**
- **依据**：**实测标定**。docstring：「trivial_separators 只抓**完美**可分（AUC=1.0），
  抓不住 AUC=0.99 这种实质上已被单特征决定的样本集。报告指标前必须看这个。」
- **验证**：✅ 有单测：
  - `test_leakage_report_empty_for_chunk_mode`（chunk 模式应无泄漏）
  - `test_leakage_report_fires_for_structural_mode`（chain/cascade 模式应触发）
  - `test_structural_modes_leak`（`trivial_separators` 对 structural 模式返回非空）
- **若改变会怎样**：未扫。但**语义清楚**：0.98 是「接近完美」的经验线。
  项目实测 clue 单特征在**训练集口径 AUC = 0.9985**（远超 0.98，正确触发），
  在**评测口径 AUC = 0.5087**（正常）。→ 该阈值成功区分了两个口径。

#### G7 · 人工权重（历史）—— 本项目最严重的标定事故

- **位置**：`training.py:62`（`HAND_WEIGHTS_LEGACY = {"sem":0.35, "struct":0.25, "clue":0.20, "type":0.20}`）
- **取值**：4 维手拍权重
- **判定什么**：`metaphor_retriever_score` 的**默认排序函数**（未训练时）
- **依据**：❌ **纯手拍，无任何依据**
- **验证**：❌ **实测证明是错的**。`experiments/实验结论汇总.md` 的 7 维特征审计表：

  | 特征 | 配对 AUC | 学到权重 | 人工权重 | 裁决 |
  |---|---|---|---|---|
  | `sem` | **0.6277** | +0.6911 | 0.35 | **唯一有真实判别力** |
  | `struct` | 0.5197 | +0.0195 | **0.25** | 弱；**人工过权 49 倍** |
  | `clue` | 0.5087 | +1.2543 | 0.20 | 弱 |
  | `type` | 0.5249 | +0.0487 | 0.20 | 弱正向；**过权 19 倍** |
  | `same_frame` | 0.5053 | +0.1953 | 0.00 | 接近随机 |
  | `same_cascade` | 0.5070 | +0.1958 | 0.00 | 接近随机 |
  | `ground_jaccard` | 0.5300 | +0.4965 | 0.00 | 弱 |

- **若改变会怎样**：**实测过的，且后果巨大**：
  - 仅把人工权重改成与学到权重同比例（**不训练任何模型**）：
    MRR **0.4809 → 0.5496**（+6.87pp，p=0.0000）
  - **反超**训练后的 7 维排序器（0.5447）
  - 结论：「已上报的『训练增益』**主要是人工权重配错的产物**」
  - **1 维 `sem` 单信号 = 0.5474**，与 7 维训练后无差异（Δ=+0.0025，CI 覆盖 0）；
    真实句向量下纯 `sem` **显著优于**训练后 7 维（+1.76pp，p=0.003）
- **注**：`实验结论汇总.md` 里出现过两个版本的数字 —— 一处写「struct 过权 49 倍、
  type 19 倍」（gen3 实测），另一处写「struct 过权 37 倍、type 12 倍」
  （`exp/repair` 的缺陷表）。**同一事实的两套数字并存于同一份文档**，
  差异源于 4 维 vs 7 维归一化口径。

#### G8 · 人工权重（现行）

- **位置**：`training.py:65`（`_LEARNED_SHARE`）、`training.py:76`（`HAND_WEIGHTS = _normalized(_LEARNED_SHARE)`）
- **取值**：`{sem 0.2382, struct 0.0067, clue 0.4323, type 0.0168,
  same_frame 0.0673, same_cascade 0.0675, ground_jaccard 0.1711}`（实测打印值）
- **依据**：**实测标定** —— 110 个伪文档各训一个排序器后取均值，标准化空间
- **验证**：✅ 单测 `test_hand_weights_single_source` 断言
  「struct 的过权倍数应 > 10（实测确认的错配，不可悄悄改回）」——
  **这是一条把「不要退回手拍值」钉成回归护栏的测试**。
- **若改变会怎样**：**实测过的**。这是本项目「单一真源」重构的核心成果：
  原实现把权重**硬编码在两个地方**（`retrieval.py` 与 `evaluate_retrieval.py`），
  已统一到 `training.hand_weighted_score`。

#### G9/G10 · 特征顺序契约与浮点累加顺序

- **位置**：`training.py:41-49`、`evaluate_retrieval.py:41`、`training.py:79-95`
- **取值**：
  - `FEATURE_NAMES = [sem, struct, clue, type, same_frame, same_cascade, ground_jaccard]`
  - `ROLE_IDX = [4, 5, 6]`
  - 累加必须**逐项顺序**（禁 numpy 点积）
- **依据**：**实测标定**。`test_manual_weights_come_from_single_source` 的 docstring：
  「人工加权公式必须逐项顺序累加，不能改成 numpy 点积 —— 浮点结合序不同会让
  632 条查询里有 **1 条**完整排序不同（人工加权 MRR 0.480947 → 0.481211）。
  这是实测踩到的坑。」
- **验证**：✅ 单测 `test_feature_index_contract` 逐位断言 7 个名字与 `ROLE_IDX`
- **若改变会怎样**：**实测过的**。任何重排都会**静默改变已上报数字**。

#### G11–G14 · 结论判定阈值族

| 位置 | 阈值 | 判定的假设 | 实测结果 |
|---|---|---|---|
| `evaluate_fullcorpus.py:297` | `d7 > 0.02` | H5（训练有增益） | 翻转 3 次：+0.3pp → +9.5pp → +0.29pp |
| `evaluate_fullcorpus.py:301` | `d9 > 0.02` | H7（角色特征有用） | 不成立 |
| `evaluate_fullcorpus.py:305` | `d8 > 0.02` | H6（阈值有用） | 中性 |
| `evaluate_retrieval.py:409` | `m_rec − l_rec > 0.2` | H3（隐喻通路有用） | 成立 |
| `evaluate_retrieval.py:411` | `on_f1 − off_f1 > 0.2` | A5（扩展边有用） | 成立 |
| `evaluate_retrieval.py:413` | `a8_on − a8_off > 0.05` | A8（阈值有用） | 无差异 |
| `evaluate_retrieval.py:415,417` | `d_mrr > 0` | H5 / H7 | 不成立 |

- **依据**：全部**拍定**（0.02 / 0.2 / 0.05 三个不同的「显著」线，无一处说明来源）
- **验证**：⚠️ 这些阈值**只影响打印的 ✅/❌ 字符串**，不参与任何计算。
  但它们**决定了论文的结论表述**。
- **若改变会怎样**：**这是本文件发现的一个真实风险**：
  同一个「训练增益」在不同阈值下得到相反结论 ——
  `0.02` 线下 +0.29pp 判「不成立」，但若线设成 `0.002` 则判「成立」。
  项目已通过**置信区间**（而非单一阈值）做了修正（gen3 报告全部改用 CI），
  但 `evaluate_fullcorpus.py` / `evaluate_retrieval.py` 的代码**未同步更新**。

### 2.H 不变量

（见汇总表；以下补充关键论证）

#### H1/H2 · 传输算子的谱性质

- **陈述**：`S` 行随机（行和 = 1）→ 无源项迭代 `M^k X0` 收敛到连通分量平稳分布
  → 同分量节点向量趋同 → `metaphor_coherence` 退化为「是否同分量」的近似二值指示。
  加 `(1−α)X0` 源项后不动点 `u* = (1−α)(I−αM)^{-1}X0` 保留源身份。
- **护栏**：7 项单测（见 F1–F5）
- **代价（已量化）**：`REPORT_exp-cascade.md` / `实验结论汇总.md`：
  「完美同分量指示器的准确率上限 = (20+602)/772 = **0.8057**，**低于** H4 实测的 0.950」
  → 这一条**单独就足以排除退化解释**。

#### H3 · Ω 只读查询

- **陈述**：`measure(query, ontology, *, eps, sparse_max)` 的签名里**没有候选池**。
  「Ω 对候选池不变」是**结构性**成立的，不是实验发现。
- **护栏**：`test_omega_invariant_to_candidate_pool`（632 查询 × 4 种池扰动 → 0/632 变化）
  + `test_measure_signature_has_no_candidate_argument`（禁用 8 个形参名：
  `shg/edges/candidates/retriever/chunks/ranked/result/scorer`）
- **实测代价（已量化）**：`exp/emergent` 发现
  「唯一在控制集合大小后仍保持判别力的是**读图**的判据（条件 AUC = **1.0000**），
  而读图就放弃了『只读查询』不变式。
  | 设计 | 控制集合大小后的判别力 |
  |---|---|
  | 只读查询（不变式成立） | **0.65** |
  | 读图（放弃不变式） | **1.0000** |
  **这是『只读查询』约束的真实代价**」

#### H4 · 候选永不丢弃

- **陈述**：折扣是「有下界的乘性因子」，不是过滤器。加性 bonus 不改变次序（无效），
  硬过滤会丢候选（召回归零）。**只有「有下界的乘性折扣」能在不丢任何候选的前提下改变排序。**
- **护栏**：`test_reliability_factor_is_capped_and_never_zero`、
  `test_reliability_scales_score_but_keeps_edge`
- **背景**：这是对 A1/H1 证伪的**直接回应**。README §7.1：
  「连贯性检查拒绝的是**绑定到某个框架**，候选并没有被丢弃 —— 它退化为临时框架
  `F_LLM_*` 后照样产出超边。要让它影响 P1，就必须**丢弃候选本身**，
  而那等于关掉开放发现（贡献 +55.8pp 召回）。」

#### H5 · 特征口径一致

- **陈述**：训练期与推理期对同一候选必须给出同一组 7 维特征
- **历史违约（真实 bug）**：
  - `training.extract_features`：`1.0 if cand.frame_id else 0.0`
  - `retrieval.metaphor_retriever_score`：查本体 `mapping_type` 后 `type_valid`，
    查不到就用 `frame_id` 原串去校验 → **恒 False**
  - 后果：同一个回退框架边在两条路径上得 **1.0 与 0.0**
- **修复**：统一走 `ontology.type_reliability_of`（三档 1.0/0.5/0.0）
- **护栏**：`test_two_scoring_paths_share_feature_schema`、`TestManualWeightedTypeConsistency`

#### H6 · 判据用 `get_frame()` 而非前缀

- **陈述**：「框架是否退化」的判据是**该 frame_id 在本体中是否有条目**，
  不是 `F_LLM_` 前缀
- **理由（实测陷阱）**：`llm_ontology.py` 把自举沉淀的**正式框架**也命名为 `F_LLM_*`，
  生产本体 **98.6%** 的框架全部是这个前缀。按前缀判定会把**整个生产本体误判为退化**。
- **护栏**：`test_coverage_judgement_is_registration_not_prefix`（`health.py`）、
  `test_judgement_is_registration_not_prefix`（`provenance.py`）
- **⚠️ 残留不一致**：`ontology.py:133` 仍定义了 `FALLBACK_FRAME_PREFIX = "F_LLM_"`，
  且 `llm_backend.py:481` 用它构造回退框架 id。**该常量已无判定用途但仍在，
  是一处误导性命名**（`builder.py:253` 用 `F_NOVEL_` 前缀，第三个前缀）。

#### H15 · 合并回归护栏

- **陈述**：10 个评测模块全部可导入 + CLI 参数完整
- **依据**：**实测踩坑**。`实验结论汇总.md` 记录合并 7 个实验分支时引入 **3 处回归**：
  | 回归 | 症状 | 护栏 |
  |---|---|---|
  | `score_conditions` 无条件加 legacy 臂 | `evaluate_fullcorpus` KeyError 崩溃 | 改为 opt-in + 1 测试 |
  | 冲突解决遗漏 argparse 定义 | `evaluate_hgnn` AttributeError | 补回 + `test_eval_cli_args_present` |
  | 多处 auto-merge 冲突标记未清 | 语法错误 | `test_all_eval_modules_importable` |
- **教训（原文）**：「222 项单测全绿**不足以**保证合并正确 ——
  单测不覆盖 CLI 入口与 `evaluate_fullcorpus` 等脚本。」

---

## 3. 「取值无实证依据」清单

> 判定标准：① 无实测标定记录；② 无消融/敏感性实验；③ 无文献继承出处。
> 满足全部三条 = **纯手拍**。以下按风险排序。

### 3.1 高风险：手拍值，且已知会造成错误结论

| # | 名称 | 取值 | 已知后果 |
|---|---|---|---|
| **G7** | 人工权重（历史） | 0.35/0.25/0.20/0.20 | **实测 struct 过权 37–49×、type 12–19×**；使「训练增益」成为配错权重的产物（+6.87pp 假增益）。已修，但 `HAND_WEIGHTS_LEGACY` 仍保留在代码里。 |
| **A3** | `llm_conf_threshold` 默认 | 0.5 | **与硬门槛直接冲突**：该值实测 P1 = 32.9%（超门槛 2.2×）。生产代码全部显式覆盖为 0.85，但**默认值仍危险**。 |
| **C1–C7** | 自适应阈值整组 | τ₀=0.5, decay=0.1, max_decays=5, min_keep=50, 密度档 2.35/5.0 | 继承自 HyperRAG（大规模稠密超图）。本项目规模小两个数量级 → **`select()` 在全部已上报实验中是恒等函数**（衰减幅度用尽 + min_keep 必然跑满 + 密度档从未切换）。A8 的「中性结论」是结构必然而非经验发现。 |
| **C9** | `top_k` 族（四处） | 10/20/60/5 | 已实测其中一处（A6 的硬编码 5）**低估 17pp**。这是**同类缺陷的第三例**，前两例是候选池 ≤10 与权重错配。 |

### 3.2 中风险：手拍值，未验证但影响面明确

| # | 名称 | 取值 | 影响面 |
|---|---|---|---|
| B6 | `arity_floor` | 2.2 | 图健康度告警（`< 2.2` 即判「超图表示失去意义」）。2.0 是数学边界，0.2 余量无依据。 |
| B7 | `orphan_ceiling` | 0.8 | 同上。80% 端点无复用才告警 —— 极宽松。 |
| B8/B9 | 未匹配池 / 脏摘要 | `max(50, n·0.3)` / `max(20, n·0.5)` | 双阈值各自拍定，无交叉验证。 |
| C5 | 高密度返回上限 | `min_keep·3 = 150` | **非 HyperRAG 原值**（上游用 `max_keep` 显式参数）。本项目自己算的 `·3`。 |
| C15 | token 预算 / 换算 | 3000 / 1.6 | 决定「多少超边能进上下文」，与 C14 比例耦合，无验证。 |
| E7 | `SINGLE_FLOW_ENTROPY` | 0.5 | 影响最大一层（n_seed=1，102 条查询）的 Ω_F。选 0 会让 Ω 归零，选 1 会掩盖坍缩 —— 0.5 是折中，无标定。 |
| A5 | 触发词置信公式 | `0.4 + 0.2·n` | 线性启发式，系数 0.4/0.2 无依据。决定 `conf_threshold=0.35` 下需几个触发词才通过（**1 个即可**：0.6 > 0.35）。 |
| A18 | 动词 lift 门槛 | 20 | 比名词的 3.0 严 6.7 倍，无说明。 |
| A21 | 本体规模参数 | `min_count=1`、`max_triggers=8` | `min_count=1` 意味着不过滤单例。 |
| G3 | `negatives_per_positive` | 3 | 未扫；`--npp` 暴露但无实验。 |
| G5 | 训练超参 | epochs=50, bs=32, lr=0.1, patience=10, l2=1e-4 | docstring 称「与 HyperRAG 对齐」，但**无扫描、无对齐证据**。 |
| G21/G22 | 抽样规模与温度 | 50/30/84、temp=0.7 | 成本约束下拍定。 |
| A10–A13 | MIPVU 语义通道参数 | 稀有判据 `>1`、失谐 `0.6`、置信 0.5/0.45/0.4 | 整条通道的判定全由这四个手拍值决定。README §6.5 只说「轻量接入」，未标定。 |
| A14 | 字面干扰词表 | 4 词 | 硬编码演示用词表，未泛化。 |
| A26 | LLM 超参 | temp=0.0, timeout=20.0 | temp=0 有明确理由（确定性），timeout=20s 无依据（`evaluate_chain_quality.py:136` 又改成 120.0）。 |
| C10–C13, C16–C18 | 检索启发式权重 | 0.3 / 0.5 / 2 / 0.5·3+0.4 | 全部手拍。C12（中心性公式）是 `struct` 特征的来源，而该特征**正是被过权 49 倍的那个**。 |

### 3.3 低风险：拍定但后果有限

| # | 名称 | 取值 | 说明 |
|---|---|---|---|
| C8 | RRF k=60 | 60 | 有文献出处（Cormack 2009）。且本项目候选数 ≤ 数十，`rank+1 << k` → 近似常数，近乎无影响。 |
| C17 | 缓存容量 | 256 / 4096 | 纯工程值，超限即清空。 |
| E11/E12/E13 | 冲突消解参数 | 0.5 / 365.0 / 0.5 | `resolve_conflict` 有 4 种策略，但**该函数不在任何评测路径上**（`models.py` 的演化机制未被评测脚本调用）。 |
| F8 | HGNN retrieve k | 10 | 同上，HGNN 不在评分路径上。 |
| G25 | 检查点间隔 | 10 批 | 工程值。 |
| I1–I6 | rmtop.rs 全部参数 | 0.12 / 0.45 等 | **外部系统源码，不进入本项目指标**。仅 I5（0.5）被借用为 E2。 |

### 3.4 特别标注：取值正确但「默认」在多个层次上不一致

| 概念 | 层次 1（常量） | 层次 2（构造器默认） | 层次 3（调用方） |
|---|---|---|---|
| 可靠性 floor | `provenance.RELIABILITY_FLOOR = 0.5` | `RetrievalEngine(reliability_floor=0.5)` | `score_conditions(reliability=False)` → **通道关闭** |
| LLM 置信门槛 | — | `extractor.llm_conf_threshold = 0.5` | 全部调用点显式传 **0.85** |
| 自适应阈值 | `DENSITY_LOW/HIGH` | `AdaptiveThreshold()` | `cross_domain_retrieve(adaptive=True)` |

- **报告与代码的口径分歧**：`experiments/REPORT_exp-degrade.md:368` 写
  「默认 `reliability_floor=1.0` 语义等价于关闭」，但代码默认是 **0.5**。
  正确表述应为「打分路径默认不启用该通道」。
- **影响**：读者按报告理解会以为默认关闭，按代码理解会以为默认 0.5 折扣生效。

---

## 4. 「机械提取遗漏的准则」

### 4.1 数字对比

| | 数量 |
|---|---|
| 机械提取（`inventory.py` 的 `CRITERION_PAT`） | **17** |
| 本文件 | **139** |
| **遗漏** | **124**（遗漏率 89.2%） |
| 机械提取项被覆盖的行数 | 15（`ontology.py` 三个常量合并为 E5 一行） |

### 4.2 遗漏的四个成因（按遗漏量排序）

#### 成因 1：函数参数默认值（**遗漏最多**，约 55 项）

`CRITERION_PAT` 只匹配 `^([A-Z][A-Z0-9_]{2,})\s*=\s*<数值>` —— 即
**模块级全大写常量**。函数签名里的默认参数完全不在其视野内。

本文件用 AST 提取了 **94 个数值型函数默认参数**（见 §5 命令 2），
其中约 55 个是准则。典型：
- `AdaptiveThreshold.__init__(tau0=0.5, decay=0.1, max_decays=5, min_keep=50)` —— **4 个准则全漏**
- `MetaphorHGNN.__init__(layers=2, alpha=1.0, leak=0.0)` —— **3 个准则全漏**
- `link_extended_metaphors(max_gap=3)` —— D3 漏
- `MetaphorScorer.fit(epochs=50, batch_size=32, lr=0.1, patience=10, l2=1e-4)` —— **5 个全漏**
- `_rrf(rank_list, k=60)` —— C8 漏
- `graph_health(arity_floor=2.2, orphan_ceiling=0.8, coverage_floor=0.85)` —— **3 个全漏**
- `build_training_set(negatives_per_positive=3, seed=42, max_gap=3)` —— 漏
- `MetaphorExtractor.__init__(conf_threshold=0.35, llm_conf_threshold=0.5)` —— **2 个漏**
- `group_by_ground(jaccard=0.34)` —— 漏
- `resolve_conflict(half_life_days=365.0)` —— 漏

#### 成因 2：argparse 默认值（约 15 项）

`--llm-conf 0.85`（5 个脚本）、`--meta-top-k 20`、`--npp 3`、
`--sample 30/50`、`--coherence-threshold 0.0`、`--doc-size 10`、
`--conf 0.35`、`--llm-conf 0.5`（`evaluate_real.py` 的**两个不同默认值**）、
`--batch 20`、`--min-lift 3.0`、`--min-df 2`、`--core-min-support 2`。

**特别值得注意**：`evaluate_real.py` 里 `--conf` 默认 **0.35** 而
`--llm-conf` 默认 **0.5** —— 与 `extractor.py` 的构造器默认值一致，
但**都不是生产实际使用的值**（0.85）。这是 A3 风险的第二个实例。

#### 成因 3：内联数值比较（约 20 项）

`CRITERION_PAT` 要求行**以常量名开头**。任何写在 `if` / `return` 里的判据全漏。
本文件用 AST 提取了 **139 个含数值常量的比较表达式**（§5 命令 3），其中约 20 个是准则：

- `if base < self.conf_threshold`（`extractor.py:200`）
- `if cand.confidence < self.llm_conf_threshold`（`extractor.py:262`）
- `if gap < max_gap and overlap`（`extended.py:71`）
- `if not (shared_trig or len(overlap) >= 2)`（`extended.py:75`）
- `if inc < 0.6 or field_counts.get(f, 0) > 1`（`mipvu.py:114`）
- `if field_counts.get(f, 0) >= 2 and f == dom`（`mipvu.py:105`）
- `if alpha > 1.0 and alpha * (1.0 - leak / 2.0) >= 1.0`（`hgnn.py:60`）
- `if v == v and v >= auc_threshold`（`training.py:222`）
- `if len(missing) > len(cids) / 2`（`evaluate_llmgold.py:254`）
- `if rate > 0.2`（`evaluate_llmgold.py:269`）
- `if (m_rec - l_rec) > 0.2`（`evaluate_retrieval.py:409`）
- `if d7 > 0.02`（`evaluate_fullcorpus.py:297`）
- `if ids[-1] - ids[0] >= 3`（`evaluate_retrieval.py:90`）
- `if merged >= len(values) * 0.95`（`llm_ontology.py:124`）
- `if h.unmatched_pool > max(50, h.n_edges * 0.3)`（`health.py:244`）
- `if abs(sum(ratios) - 1.0) > 1e-6`（`context_budget.py:148`）
- `if b['acc'] > 0.5`（`evaluate_hgnn.py:395`）
- `if r['literal_error_rate'] < 0.15`（`evaluate_real.py:115`）
- `if h.hierarchy_coverage >= 0.85`（`evaluate_real.py:245`）

#### 成因 4：文档中的硬门槛（prose gates，约 10 项）

`论文初稿.md` / `metaphor_graph/README.md` 里的 Go/No-Go 表述，
代码里**只有引用没有定义**（或定义在别处）：

| 出处 | 门槛 | 代码对应 |
|---|---|---|
| `论文初稿.md:184` | P1 < 15%（硬门槛） | `evaluate_real.py:115` 内联 |
| `论文初稿.md:附录B` | P0 ≥ 300 框架 | `llm_ontology.py:466` 内联 |
| `论文初稿.md:附录B` | P2 > 85% | `health.py:114` 参数默认 |
| `论文初稿.md:附录B` | P3 > 70% | `eval_corpus.py:93` 常量 ✅ |
| `论文初稿.md:附录B` | P4 抽取 F1 +5pp | **口径不匹配，已改测** |
| `论文初稿.md:128` | MIPVU 三条排除项 | `llm_backend.py:132` 提示词 ✅ |
| `README.md:645` | P1 < 15% Go/No-Go | 同 P1 |
| `README §6.7` | 0.85 是实测达标拐点 | 无常量，20+ 处字面量 |
| `README §7.1` | A1 预期 P1 回升 > 30% | `baselines.py:106` 字符串 |
| `baselines.py:106-113` | A1/A4 预期（>30% / >3pp） | 字符串常量，非数值 |

**另有一类纯文字门槛**（无对应代码）：
- `论文初稿.md:128`：「去除它 P1 飙至 28.9%」（MIPVU 判据的证伪阈值）
- `README §6.4`：「纯触发词自举的召回天花板约 6–8%」
- `README §7.1`：「H1 预期 P1 回升 >30%」
- `后续待办.md A4`：「κ ≥ 0.7」为人工抽查验收线（而 `evaluate_gold_audit.py:206`
  的参考档是 ≥0.8 —— **两个不同的验收线**）

### 4.3 遗漏的**非数值**准则（机械提取完全无法捕获）

以下准则**不含数字**，但确属「判定规则 / 不变量」：

1. **候选永不丢弃**（`provenance.py:16-18`）—— 乘性折扣而非过滤
2. **Ω 只读查询**（`observability.py:15-18`）—— API 形状保证
3. **判据用 `get_frame()` 而非 `F_LLM_` 前缀**（`provenance.py:26-31`）
4. **特征口径一致**（`ontology.py:416`）—— 两条路径同一实现
5. **边 id 确定性**（`extractor.py:203-209`）—— 禁 uuid4 / 内置 hash
6. **诚实覆盖率 ≤ 报出口径**（`test:1807`）
7. **扩展边溯源取最弱**（`extended.py:104`）
8. **可靠性只采信更保守值**（`provenance.py:85`）
9. **本体 id 稳定**（`llm_ontology.py:67`）
10. **类型约束不丢弃候选**（`ontology.py:122-129`）
11. **手写累加顺序**（`training.py:79-95`）
12. **H15 合并回归护栏**（CLI 参数完整性 + 全模块可导入）
13. **A7/A9 必须用同一候选池**（`audit_fairness.py` 检查的契约）
14. **refine 键必须是原跑缓存的子集**（`ontology_clean.py:199-202`）
15. **不传 ontology 时历史口径逐位不变**（`health.py:122`）

---

## 5. 复现命令

### 5.1 机械提取基线（原 17 项）

```bash
cd "E:/02_AI项目/元图隐喻分析"
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"
"$PY" -m metaphor_graph.inventory --json docs/inventory/_extracted.json
```

### 5.2 函数参数默认值（AST，命中 94 个数值默认参数）

```bash
"$PY" - <<'PY'
import ast, os
ROOT='metaphor_graph'; SKIP={'test_metaphor_graph.py','audit_fairness.py','inventory.py'}
res=[]
for f in sorted(os.listdir(ROOT)):
    if not f.endswith('.py') or f in SKIP: continue
    tree=ast.parse(open(os.path.join(ROOT,f),encoding='utf-8').read())
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            names=node.args.args[len(node.args.args)-len(node.args.defaults):]
            for n,val in zip(names,node.args.defaults):
                if isinstance(val,ast.Constant) and isinstance(val.value,(int,float)) \
                   and not isinstance(val.value,bool):
                    res.append((f,node.lineno,node.name,n.arg,val.value))
            for n,val in zip(node.args.kwonlyargs,node.args.kw_defaults):
                if isinstance(val,ast.Constant) and isinstance(val.value,(int,float)) \
                   and not isinstance(val.value,bool):
                    res.append((f,node.lineno,node.name,n.arg,val.value))
print(f"共 {len(res)} 项")
for r in res: print(f"{r[0]}:{r[1]} {r[2]}({r[3]}={r[4]})")
PY
```

### 5.3 内联数值比较（AST，命中 139 个表达式）

```bash
"$PY" - <<'PY'
import ast, os
ROOT='metaphor_graph'; SKIP={'test_metaphor_graph.py','inventory.py'}
out=[]; seen=set()
for f in sorted(os.listdir(ROOT)):
    if not f.endswith('.py') or f in SKIP: continue
    tree=ast.parse(open(os.path.join(ROOT,f),encoding='utf-8').read())
    for node in ast.walk(tree):
        if isinstance(node,ast.Compare):
            if any(isinstance(c,ast.Constant) and isinstance(c.value,(int,float))
                   and not isinstance(c.value,bool)
                   for c in [node.left]+list(node.comparators)):
                s=ast.unparse(node)[:100]
                if s not in seen: seen.add(s); out.append((f,node.lineno,s))
print(f"共 {len(out)} 项")
for r in out: print(f"{r[0]}:{r[1]}  {r[2]}")
PY
```

### 5.4 全部模块级大写常量（命中 109 个）

```bash
"$PY" - <<'PY'
import ast, os
ROOT='metaphor_graph'; SKIP={'test_metaphor_graph.py','audit_fairness.py','inventory.py'}
n=0
for f in sorted(os.listdir(ROOT)):
    if not f.endswith('.py') or f in SKIP: continue
    tree=ast.parse(open(os.path.join(ROOT,f),encoding='utf-8').read())
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for t in node.targets:
                if isinstance(t,ast.Name) and t.id.isupper() and len(t.id)>=3:
                    v=ast.unparse(node.value)
                    if len(v)<60:
                        n+=1; print(f"{f}:{node.lineno} {t.id} = {v}")
print("total:", n)
PY
```

### 5.5 argparse 默认值

```bash
grep -rn --include=*.py -E "add_argument\(" -A2 metaphor_graph/ | grep -E "default="
```

### 5.6 文档门槛（prose gates）

```bash
grep -n -E "(硬门槛|门槛|Go/No-Go|验收|达标|阈值|判据)" 论文初稿.md
grep -n -E "(硬门槛|门槛|验收|达标|阈值|判据|≥|>)" metaphor_graph/README.md
grep -n -E "(37 倍|49 倍|19 倍|过权|错配|拍定|标定|敏感性)" experiments/实验结论汇总.md
```

### 5.7 外部参考实现（rmtop.rs，0.12/0.45 的真实出处）

```bash
grep -n "collapsed_threshold\|sparse_threshold\|struct_role_min_omega\|conditional_direct_bandwidth" \
     metaphor_graph/rmtop.rs
# → rmtop.rs:269 collapsed_threshold: 0.12
# → rmtop.rs:270 sparse_threshold: 0.45
# → rmtop.rs:284 conditional_direct_bandwidth: 0.12
# → rmtop.rs:290 struct_role_min_omega: 0.12
```

### 5.8 不变量护栏定位

```bash
grep -n "class Test" metaphor_graph/test_metaphor_graph.py
# 重点类：TestHGNDriven(1519) / TestQueryObservability(1299) /
#         TestProvenanceReliability(2528) / TestTypeReliability(1966) /
#         TestFeatureSetAudit(2077) / TestDeterministicIds(1707) / TestRepairs(1736)
```

### 5.9 自适应阈值恒等性验证（本文件新增的分析）

```bash
"$PY" - <<'PY'
import sys; sys.path.insert(0,'.')
from metaphor_graph.context_budget import AdaptiveThreshold
t = AdaptiveThreshold()
print("最大可降幅 =", t.tau0 - t.decay*t.max_decays)   # → 0.0
for n in (5,17,49,50,51,200):
    sel,dec = t.select([(f"c{i}",0.12) for i in range(n)], density=1.071)
    print(f"n={n:4d} → τ {t.tau0}→{dec.threshold} 降{dec.n_decays}次 "
          f"选{dec.n_selected}/{dec.n_candidates} regime={dec.regime}")
# 结论：n ≤ 50 时衰减必然跑满 5 次，select() 等价于「全量返回」
PY
```

```bash
"$PY" - <<'PY'
import sys; sys.path.insert(0,'.')
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.retrieval import shg_density
from metaphor_graph.context_budget import AdaptiveThreshold
from metaphor_graph.eval_corpus import DOCS
shg = MetaphorSHGBuilder().build(DOCS["doc_project"], doc_id="dp")
d = shg_density(shg)
print("doc_project Δ =", round(d,4), "→ regime =", AdaptiveThreshold().regime(d))
# → Δ=2.1667, regime=low   （≤2.35，high 档从未触发）
# 全量语料：Δ=1.071（README §7.3），同样落 low 档
PY
```

---

## 6. 给下游的三条提醒

1. **A3（`llm_conf_threshold=0.5` 默认）是唯一一个「默认值即撞穿硬门槛」的参数**。
   全部生产调用点都显式传 0.85，说明这个默认值从未被有意使用过 ——
   但它对任何新写的脚本都是陷阱。建议改为 0.85。

2. **C1–C7（自适应阈值）在本项目规模下是恒等函数**，不是「未验证」而是
   「已验证为无作用」。论文/README 目前把 A8 表述为「需更大检索集才能验证」，
   方向正确但**未指出参数已用尽衰减空间**。若要真正测试该机制，
   必须先按本项目图规模重标定 `min_keep`（应远小于 50）与 `tau0`（应落在
   实际分数区间内 —— 实测 `hand_weighted_score` 的输出范围是 0.11–0.78）。

3. **G7 的遗留物 `HAND_WEIGHTS_LEGACY` 仍在代码里**，且 `evaluate_retrieval.py`
   的 `--legacy-arm` 可显式启用。单测 `test_hand_weights_single_source` 已把
   「过权倍数 > 10」钉成护栏，防止悄悄改回 —— 这是本项目处理
   「已证伪的手拍值」的标准做法，值得在其他参数上复用。
