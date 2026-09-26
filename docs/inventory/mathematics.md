# 数学对象登记册（mathematics.md）

> **本文件要回答的问题**：项目里到底定义了哪些**数学对象**，每个对象的**文档公式**与
> **代码实现**是否一致，它在什么条件下**退化**，以及它的**实证状态**。
>
> **口径**：以代码为唯一真源（`metaphor_graph/`，main 分支，2026-09-27）。
> 文档公式逐字引自论文 / docstring / 实验报告。**本文件的核心价值是核对，不是转录。**
>
> **已发现 12 处「文档 ≠ 代码」的实质分歧**（§D），全部给出可复现的验证命令：
> **5 处 ★**（影响结论或指标：D.1–D.5）＋ **7 处 ☆/⚠️**（表述/口径/数字问题：D.6–D.12）。
>
> **实证状态四档**：`validated`（实测支持）｜`refuted`（实测证伪）｜
> `diagnostic-only`（可算但无下游用途）｜`untested`（无实测）。
>
> 生成日期：2026-09-27 ｜ 代码为只读，未做任何修改。

---

## 0. 汇总表

| # | 名称 | 代码位置 | 文档公式 | 代码一致? | 退化条件 | 实证状态 |
|---|---|---|---|---|---|---|
| M1 | Ω_E 边激活 | `observability.py::measure:244` | `min(1, |框架|/|种子|)` | ✅ 一致 | `n_seed=1` 层恒为 1（死分量） | validated（值域正确，层内零变异） |
| M2 | Ω_N 涌现 | `observability.py::measure:246` | `min(1, |涌现域|/|种子|)` | ✅ 一致（**但文档未警示截断**） | **`n_emergent ≥ n_seed` 时饱和为 1**；生产本体 99.2% 级联结构上恒空 | **refuted**（死分量） |
| M3 | Ω_F 流量熵 | `observability.py::normalized_entropy:164` | `H/log2(n)`，单条→0.5，无→0 | ✅ 一致 | `n=1` 取约定值 0.5（非 0 非 1）；全同权重→1 | validated |
| M4 | 几何平均 + ε 下界 | `observability.py::geometric_mean:185` | `(∏ max(v,ε))^{1/3}` | ✅ 一致 | `ε` 下界把 `v<ε` 的区间**压成一点**（破坏严格单调） | validated（按设计工作，非坍缩源） |
| M5 | 观测完备度 comp | `observability.py::completeness:201` | `覆盖字符/查询长度`，clip[0,1] | ⚠️ 文档未提**重叠重复计数** | 长查询系统性惩罚（与 `n_seed` ρ=0.9954） | validated（是共线因子） |
| M6 | Ω 合成 | `observability.py::measure:257` | `(Ω_E·Ω_N·Ω_F)^{1/3} × comp` | ✅ 一致（+无激活特判） | **Ω>0 ⟺ n_seed≥1**（1 bit） | **refuted**（下游不可用） |
| M7 | regime 分档 | `observability.py::regime_of:218` | collapsed/sparse/dense | ✅ 一致 | `n_frames≤0 or Ω≤0` → collapsed 双条件 | validated |
| M8 | S_query | `query_signal.py::_s_query:249` | Ω 去掉 Ω_N 的 `min(1,·)` | ✅ 一致 | 去掉截断后 `Ω_N>1` 无上界（实测 max 496） | diagnostic-only |
| M9 | compose() 四开关 | `query_signal.py::compose:140` | 4 开关正交 2⁴ 组合 | ❌ **`outer_zero` 是死开关** | 实际只有 2³=8 种组合 | validated（16→8 已实测） |
| M10 | S_log | `query_signal.py::_s_log:218` | `log1p(f)+log1p(c)+log1p(new)` | ⚠️ docstring 称「等价几何平均」**不准确** | 无上界；退化计数贡献 0（中性） | diagnostic-only |
| M11 | S_struct | `query_signal.py::_s_struct:230` | 结构化合成（退化分量不参与） | ✅ 一致 | `n_frames≤0`→0；`n_new=0` 时退化为单分量 | diagnostic-only |
| M12 | StratifiedNormalizer | `query_signal.py:321` | `z=(x−μ_stratum)/σ_stratum` | ✅ 一致（+sd=0 回退） | 层内 sd=0 → 用全局 sd；未见层 → 用 μ 均值 | **refuted**（不优于原始计数） |
| M13 | gate_by | `query_signal.py:381` | `signal[name] ≥ theta` | ✅ 一致 | 未知信号抛 KeyError | untested（无调用方） |
| M14 | frame_reliability | `provenance.py:51` | 登记→1.0 / 未登记→0.5 | ✅ 一致 | `ontology=None` 或 `frame_id` 空 → 返回 **1.0**（不做降级） | validated |
| M15 | reliability_factor | `provenance.py:88` | `floor+(1−floor)·r ∈ [floor,1]` | ✅ 一致 | `floor=1.0` → 恒 1.0（通道关闭） | validated（P1 效应恒 0） |
| M16 | edge_reliability | `provenance.py:73` | `min(stored, derived)` | ✅ 一致 | 只能降不能升（防伪升级） | validated |
| M17 | 传播算子 S | `hgnn.py::propagation_matrix:167` | `D_v^{-1} H D_e^{-1} H^T` | ✅ 一致 | 孤立节点行全 0；行随机仅在活节点上 | validated |
| M18 | 传播算子 M | `hgnn.py::_conv:150` | `M = ½(I+(1−ε)S)` | ❌ **空 `he_members` 时 `_conv` ≠ M·X** | `ρ(M)=1−ε/2`；`ε=0` 时 ρ=1 | validated（谱性质实测） |
| M19 | 驱动迭代 forward | `hgnn.py::forward:179` | `X ← (1−α)X0 + α·M·X` | ✅ 一致 | `α=1` 无不动点（`I−M` 奇异，零空间维=分量数） | validated |
| M20 | 不动点 u* | `convergence_check.py:47` | `u*=(1−α)(I−αM)^{-1}X0` | ✅ 一致（实测 1.7e-16） | `α<1` 且 ρ(M)≤1 才可逆 | validated |
| M21 | metaphor_coherence | `hgnn.py:221` | `cos(H_a, H_b)` | ✅ 一致 | `k→∞` 无源项 → 同分量余弦→1（身份被抹） | validated（渐近退化，layers=2 未退化） |
| M22 | 图密度 Δ | `context_budget.py::graph_density:32` | `总关联数/端点数` | ✅ 一致（+去重口径需注意） | `n_nodes≤0`→0.0 | validated（A8 中性） |
| M23 | 自适应阈值衰减 | `context_budget.py::select:80` | `τ₀−c·k`，最多 `max_decays` 次 | ✅ 一致（**τ 无下限钳制**） | τ 可为负 → 全量放行 | validated（A8 无差异） |
| M24 | 上下文预算 50/30/20 | `context_budget.py::pack:157` | 三类配额 + 顺延 | ⚠️ 文档称「按分数降序」**代码不排序** | `carry` 逐类顺延；大项放不下**跳过**而非 break | validated（盲评 judge 敏感） |
| M25 | RRF 融合 | `retrieval.py::_rrf:32` | `Σ 1/(k+rank+1)`，k=60 | ✅ 一致（rank 0-based） | 字面路 rank = **文档枚举顺序**（非相关性） | untested（无独立评测） |
| M26 | 7 维特征 | `training.py:41/106/148` | sem/struct/clue/type/same_frame/same_cascade/ground_jaccard | ❌ `ground_jaccard` **两条路径定义不同** | 无本体时 3 维恒 0；`struct` 85.1% 饱和到 1.0 | validated（1 维 sem 即达标） |
| M27 | HAND_WEIGHTS | `training.py:76` | `_normalized(_LEARNED_SHARE)` | ✅ 一致 | LEGACY 未覆盖 3 个新维 → 权重 0 | validated（重标定 +5.7pp） |
| M28 | 全量 AUC | `evaluate_hgnn.py::_auc_full:316` | `P(pos>neg)+0.5·P(pos=neg)` | ✅ 一致（三实现逐位相同） | 全并列 → 恒 0.5（配对准确率则 → 0） | validated |
| M29 | 诚实覆盖率 | `health.py:184` | `min(reg_frame_cov, reg_cascade_cov)` | ❌ **两次赋值冲突，hc 与字段可矛盾** | 无 `frame_id` 的边被第二段误判为「已登记」 | validated（82.4% < 85% 门槛） |
| M30 | 报出覆盖率 | `health.py:162` | `min(frame_cov, cascade_cov)` | ✅ 一致 | 由 `C_ADHOC_*` 事后补建撑到 100% | refuted（注水） |
| M31 | multi_clue_retrieval | `retrieval.py:217` | 「≥2 个触发词支持的映射」 | ❌ **判据是分数和，不是触发词个数** | 重复触发词被重复计数 | untested |
| M32 | cross_domain 候选分 | `retrieval.py:170` | — | 文档未给出 | 无上界；同 chunk 累加 | validated |

**计数**：32 个数学对象。

| 汇总表状态 | 个数 | 对象 |
|---|---|---|
| ✅ 公式一致 | **23** | M1–M4、M6–M8、M11–M17、M19–M23、M25、M27、M28、M30 |
| ⚠️ 文档未警示 / 表述不准确 | **3** | M5（重叠计数未说明）、M10（「等价几何平均」不准确）、M24（「按分数降序」未实现） |
| ❌ 实质不一致 | **5** | M9（死开关）、M18（等价性声明失效）、M26（两路径定义不同）、M29（两次赋值冲突）、M31（判据语义错） |
| 文档未给出公式 | **1** | M32 |
| 合计 | **32** | ✓ |

**§D 的 12 处分歧**与上表**不是一一对应**：

| §D 编号 | 对应对象 | 是否改变上表状态 |
|---|---|---|
| D.1 | M9 | 是（→ ❌） |
| D.2 | M29 | 是（→ ❌） |
| D.3 | M8 | 否（公式一致，**数字**错） |
| D.4 | M26 | 是（→ ❌） |
| D.5 | M31 | 是（→ ❌） |
| D.6 | M18 | 是（→ ❌） |
| D.7 | M24 | 是（→ ⚠️） |
| D.8 | M5 | 是（→ ⚠️） |
| D.9 | M12 | 否（主公式一致，**回退分支描述**不准） |
| D.10 | M23 | 否（默认参数下不越界，仅自定义参数时） |
| D.11 | M2 | 否（模块 docstring 已写，**论文/README 未披露**） |
| D.12 | M10 | 是（→ ⚠️） |

---

## 1. Ω 查询侧可观测泛函（M1–M7）

### M1 Ω_E 边激活

- **位置**：`metaphor_graph/observability.py::measure:244`
- **文档公式**（`observability.py` 模块 docstring:21）：
  > `Ω_E  edge activation  查询触发词实际点亮的框架数 / 种子触发词数，clip [0,1]`

  实验报告 `experiments/REPORT_exp-cascade.md:32` 逐字：
  > `Ω_E  edge activation = min(1, |点亮的框架| / |种子触发词|)          clip [0,1]`
- **代码**：
  ```python
  omega_e = min(1.0, n_frames / n_seed) if n_seed else 0.0
  ```
  其中 `n_frames = len(st["frames"])`，`frames = sorted(hits)`（**去重后的框架 id**）。
- **是否一致**：`一致`
- **数学性质**：
  - 值域 `[0,1]`；`n_seed ≥ 1` 时对 `n_frames` 单调不减，对 `n_seed` 单调不增。
  - 分子去重、分母不去重 → **触发词同义冗余会压低 Ω_E**（"泥潭，沼泽" → 0.5 而非 1.0）。
  - 不可微（离散计数 + `min` 折点）。
- **退化条件**：
  - **`n_seed=1` 层恒为 1.0**（`n_frames ≥ 1` 恒成立，因为 `matched_triggers` 只遍历
    `_trigger_index` 的键，每个键至少映射 1 个 `frame_id`）→ **该层 Ω_E 零变异，对 Ω 的
    层内序贡献为零**（gen3 §2.4 实测：102 条全部 `Ω_E=1.0`，`ρ(Ω,Ω_E)=nan`）。
  - 分母错误：docstring 自己承认「触发词可以同义冗余」（exp6 §S2）。
- **实证状态**：`validated`（值域/语义正确）但**层内为死分量**。

### M2 Ω_N 涌现 —— ★ 本项目最关键的退化点

- **位置**：`metaphor_graph/observability.py::measure:246`
- **文档公式**（模块 docstring:22-23）：
  > `Ω_N  emergence  经级联扩展抵达、且不在直接命中目标域集里的目标概念数 / 种子触发词数，clip [0,1]`

  实验报告 `REPORT_exp-cascade.md:33`：
  > `Ω_N  emergence = min(1, |级联涌现目标域| / |种子触发词|)      clip [0,1]`
- **代码**：
  ```python
  omega_n = min(1.0, len(st["emergent"]) / n_seed) if n_seed else 0.0
  ```
  其中 `emergent = expanded - direct`（`activated_structure:161`），
  `expanded` = 所有被点亮级联的成员框架的 `target_domain` 集合。

- **是否一致**：`一致`（代码与 docstring 逐字吻合）。
  **但**：`Ω_N` 的 `min(1,·)` 截断虽然在**模块 docstring 与实验报告里都写了**，
  却在**论文正文与 README 中完全缺席**——论文里 Ω 只出现在 §7 的负面结果一行，
  没有任何分量定义。因此对只读论文的读者，`min(1,·)` 是**未披露的实现细节**。

- **数学性质**：
  - 值域 `[0,1]`；`n_seed ≥ 1` 时对 `n_emergent` 单调不减。
  - **截断是饱和非线性**：`n_emergent ≥ n_seed` ⟹ `Ω_N ≡ 1.0`（算术恒等式）。
  - 可微性：除 `min` 折点与 `n_seed=0` 间断外连续。

- **退化条件**（三重，全部实测）：

  1. **饱和截断（元凶）**：`n_emergent ≥ n_seed` 时 `Ω_N` 恒为 1.0。
     实测（`experiments/gen3/dataset_source.json` 复算，n=114 子集）：
     ```
     n_seed=1 层: n=102,  n_emergent 取值数 = 23,  Ω_N 取值数 = 2,  顶到 1.0 = 82 条
     n_seed=2 层: n= 11,  n_emergent 取值数 =  9,  Ω_N 取值数 = 1,  顶到 1.0 = 11 条
     ```
     **23 档取值 → 2 档**，102 条中 82 条被压到同一个饱和值。
     去掉这一处截断（= `S_query`）后 AUC **0.6539 → 0.8243**。
     四规则下的截断触发率（`n_seed≥1` 子集 n=114）：
     | 规则 | raw Ω_N>1 条数 | raw Ω_N ≥1 条数 | max raw Ω_N |
     |---|---|---|---|
     | `json`（生产） | 3 | 9 | 2.0 |
     | `source` | **92** | 94 | 74.0 |
     | `metanet` | 81 | 86 | 74.0 |
     | `source_type` | **114**（全部） | 114 | **496.0** |

  2. **结构性恒空（基底错配）**：生产本体的级联按 `target_domain` 分组构造
     （`ontology_clean` 的 `LLM_TARGET::{t}`），成员**必然共享目标域** → 级联闭包
     不带来新目标域 → `emergent = ∅` → `Ω_N ≡ 0`。
     实测（`build_replay_ontology()`，2209 框架 / 758 级联）：
     ```
     级联闭包不带来新目标域 = 752/758 = 99.2%
     成员数=1 的级联 = 412/758 = 54.4%
     单框架出发闭包不带来新目标域 = 2196/2209 = 99.4%
     对照·内置种子级联（13 个，人工构造）：跨目标域的有 6 个
     ```
     实测 Ω：改写型 `Ω_N>0` 占比 9/632 = 1.4%，重叠型 33/632 = 5.2%。
  3. **两者叠加的后果**：`Ω_N` 要么恒 0（把 Ω 压低约 3–5 倍），要么饱和到 1（把
     23 档压成 2 档）——**在任何一种情形下都不提供查询间区分度**。

- **实证状态**：**`refuted`**。gen1 判「Ω_N 是死分量」，gen3 定位到根因是
  `min(1,·)` 截断（`REPORT_exp-cascade.md` TL;DR 表 + `gen3/REPORT.md §2.2`）。
  exp6 §S1 的修法建议：把 `Ω_N` 从几何平均移除，或改为「点亮的级联数 / 种子数」。

### M3 Ω_F 流量熵

- **位置**：`metaphor_graph/observability.py::normalized_entropy:164`
- **文档公式**（模块 docstring:24-25）：
  > `Ω_F  flow entropy     激活权重分布的归一化熵（防止全部坍缩到一个触发词/框架）；单条正流量取有限值 0.5，无流量取 0`

  `REPORT_exp-cascade.md:35-37`：
  > `Ω_F  flow entropy = H(激活权重分布) / log2(n)  （权重 = 框架被几个触发词命中）`
  > `无正流量 → 0；单条正流量 → 0.5（有限值）；n>1 → 归一化熵`
- **代码**：
  ```python
  pos = [w for w in weights if w > 0]
  n = len(pos)
  if n == 0: return 0.0
  if n == 1: return SINGLE_FLOW_ENTROPY     # = 0.5
  total = sum(pos)
  if total <= 0: return 0.0
  h = -sum((w / total) * math.log2(w / total) for w in pos)
  return h / math.log2(n)
  ```
  权重 `flow = tuple(float(st["hits"][fid]) for fid in st["frames"])`，
  `hits[fid]` = 该框架被多少个触发词命中。
- **是否一致**：`一致`（含两个退化约定）
- **数学性质**：
  - 值域 `[0,1]`（归一化熵上界 1，n>1 时）。
  - **`n=1` 时取 0.5 是人为约定**（真熵为 0，最大熵为 0），制造了
    `H(单条)=0.5 > H(无流量)=0` 的序，使「流量存在但坍缩」与「完全没流量」可区分。
  - 对权重分布的置换不变；对权重尺度不变（归一化）。
  - 实测：`(3.0,)→0.5`；`(1.0,1.0)→1.0`；`(1.0,3.0)→0.8113`；`()→0.0`。
- **退化条件**：
  - `n_frames=0` → `flow=()` → 返回 0。
  - 所有框架被**同样多**的触发词命中 → 返回 1.0（**熵高 ≠ 结构丰富**：1 个触发词
    点亮 1 个框架与 4 个触发词点亮 4 个框架（各 1 次）都给 1.0… 后者给 1.0 而
    前者给 0.5）。
  - 权重全为整数计数 → 取值是离散的，取值数受 `n_seed` 限制。
- **实证状态**：`validated`（分量语义与退化约定均按设计工作）。

### M4 几何平均 + ε 下界

- **位置**：`metaphor_graph/observability.py::geometric_mean:185`
- **文档公式**（模块 docstring:26）：
  > `Ω_geo = (Ω_E · Ω_N · Ω_F)^(1/3)，各分量带 ε 下界（避免几何平均退化成「与门」）`
- **代码**：
  ```python
  if not values: return 0.0
  acc = 1.0
  for v in values:
      acc *= max(float(v), eps)
  return acc ** (1.0 / len(values))
  ```
- **是否一致**：`一致`
- **数学性质**：
  - 值域 `[ε, 1]`（**下界是 `ε` 而非 `ε^{1/3}`**：三分量全触底时
    `∏ max(v,ε) = ε³` → `Ω_geo = ε = 1e-3`；实测 `geometric_mean((0,0,0)) = 0.001`）。
  - 只有**一个**分量触底、其余为 1 时 `Ω_geo = ε^{1/3} = 0.1`
    （实测 `geometric_mean((1,0,1)) = 0.1`）。这是实践中最常见的台阶高度。
  - 对每个分量单调不减；**不是处处严格单调**：`v ≤ ε` 的所有取值被压成同一点
    （实测 `geometric_mean((1,0,1)) == geometric_mean((1,1e-4,1)) == 0.1`）。
  - 齐次度 1（对分量同比例缩放线性响应）。
  - 可微（分量 > ε 区域）；在 `v=ε` 处一阶不可导。
- **退化条件**：
  - **ε 下界把「0/1 台阶」变成「ε^{1/3} 台阶」——信息量同为 1 bit**
    （gen3 §2.4 实测：ε 下界恒等式在 `source` 上 20/20 成立，**完全按设计工作**，
    **不是**坍缩来源。核心假设的这条归因应撤回）。
  - 完全无激活时**不走这个函数**：`measure` 有外层特判（见 M6）。
- **实证状态**：`validated`（按设计工作；曾被误判为元凶，gen3 已澄清）。

### M5 观测完备度 comp

- **位置**：`metaphor_graph/observability.py::completeness:201`
- **文档公式**（模块 docstring:27）：
  > `Ω = Ω_geo × 观测完备度（查询中被触发词覆盖的字符占比）`
- **代码**：
  ```python
  covered = 0
  for t in trigs:
      if t: covered += len(t) * query.count(t)
  covered = min(covered, len(query))
  return covered / len(query), covered
  ```
- **是否一致**：`一致`（但**文档未说明重叠重复计数**）
- **数学性质**：
  - 值域 `[0,1]`；对查询长度**反比**（同命中下）。
  - **重叠触发词重复计数**：`completeness('aaaa', ['a','aa'])` = 1.0
    （覆盖 4+8=12，被 `min` 截到 4）。子串重叠时覆盖率虚高。
  - 对**触发词集合**单调不减（`covered` 是非负求和），但**可能不增加**
    （`min(covered, len(query))` 截断）：实测
    `completeness('泥潭',['泥潭']) == completeness('泥潭',['泥潭','潭']) == 1.0`。
  - 对**查询长度**单调不增（同命中下 `covered/L` 递减）。
- **退化条件**：
  - **长度偏置**：实测族均值（exp4 §[3]）
    ```
    N2 文档 chunk 全文   mean 长度 416.3  mean comp 0.0114  mean Ω_geo 0.1844
    N3a 文档句·含触发词   mean 长度  26.6  mean comp 0.1002  mean Ω_geo 0.1446
    ```
    Ω_geo 反而更高（0.184 > 0.145）但 comp 低 9 倍 → Ω 被压到 0.0031 vs 0.0145。
  - **与 n_seed 高度共线**：`ρ(comp, n_seed) = 0.9954`（gen3 §2.4），
    即它把 Ω 进一步推向 1-bit 指示器。去掉完备度后 AUC 反而**更差**
    （0.6539 → 0.6148）——它携带一点弱信号（Ω>0 子集内 AUC 0.552）。
- **实证状态**：`validated`（共线因子，非坍缩主因）。

### M6 Ω 合成

- **位置**：`metaphor_graph/observability.py::measure:252-258`
- **文档公式**（模块 docstring:26-28）：
  > `Ω = Ω_geo × 观测完备度`
  > `无任何激活时 Ω 恒为 0（ε 下界不适用于「完全没观测到」这一情形）`
- **代码**：
  ```python
  if n_seed == 0 or n_frames == 0:
      omega_geo = omega = 0.0
      omega_e = omega_n = omega_f = comp = 0.0
  else:
      omega_geo = geometric_mean((omega_e, omega_n, omega_f), eps=eps)
      omega = omega_geo * comp
  ```
- **是否一致**：`一致`
- **数学性质**：
  - 值域 `[0,1]`；实测恒等式 `Ω = Ω_geo × comp` 全部满足。
  - 无激活时**强制 `Ω_geo = 0`**（而不是 `(ε·ε·ε)^{1/3}=0.1`）——这是
    「完全没观测到」与「观测到了但分量很低」的显式区分。
  - `n_frames == 0` 与 `n_seed == 0` 是**同一个条件**（前者蕴含后者，反之亦然），
    因此这个 `or` 的第二项是冗余的（防御性写法）。
- **退化条件**：
  - **`Ω>0 ⟺ n_seed≥1` 逐条一致率 632/632 = 1.0000**（exp6 §S3）。
    `Ω` 在「级联通路是否非空」上的信息 = 触发词有无 = **1 bit**。
  - `ρ(Ω, n_seed) = 0.9949`（exp2 §D，p≈0）。
  - 门控与现有 `if not agg` 判据的一致率 0.8956，且**Ω 门控严格更弱**：
    它漏掉 66 条「有触发词但通路仍空」的查询（exp3 §B）。
- **实证状态**：**`refuted`**。论文 §7 表格逐字：
  > 查询侧可观测标量 Ω ｜ 预测级联通路失效 ｜ ρ(Ω, 触发词命中数)=**0.9949**；
  > 控制集合大小后全部标量 AUC 覆盖 0.5；穷举 64 种合成组合 AUC 均落在 0.50–0.93
  > ｜ **方向不可行**：只读查询的标量退化为 1-bit 触发词指示器；"触发词命中数"即天花板

### M7 regime 分档

- **位置**：`metaphor_graph/observability.py::regime_of:218`
- **文档公式**（模块 docstring:30）：
  > `regime：collapsed（无框架被点亮）/ sparse（Ω < 0.5）/ dense（Ω ≥ 0.5）。`
- **代码**：
  ```python
  if n_frames <= 0 or omega <= 0.0:
      return REGIME_COLLAPSED
  return REGIME_SPARSE if omega < sparse_max else REGIME_DENSE
  ```
- **是否一致**：`一致`（文档说「无框架被点亮」→ collapsed，代码是**双条件** `or`）
- **数学性质**：阈值 0.5 为 `SPARSE_MAX`，可配置。
  实测边界：`Ω=0.4999999→sparse`；`Ω=0.5→dense`；`Ω=1e-12, n_frames=3→sparse`。
- **退化条件**：
  - **dense 档几乎不可达**：exp1 实测改写型 dense=1/632（0.2%）、重叠型 30/632（4.7%）、
    CCL2018 原句 dense=0/1100、文档 chunk dense=0/1050。
    `Ω ≥ 0.5` 要求 `Ω_geo ≥ 0.5/comp`，而 comp 通常 ≪ 1 → dense 档实质上是空档。
  - 分档边界在 `Ω=0.5` 处**不连续**（dense 起点即 sparse 终点），
    但两档的工程动作无差异（`gate` 只用 θ）。
- **实证状态**：`validated`（分档可算；dense 档实测近空）。

---

## 2. S_query 与 query_signal（M8–M13）

### M8 S_query

- **位置**：`metaphor_graph/query_signal.py::_s_query:249`（常量 `SIG_S_QUERY:53`）
- **文档公式**（`query_signal.py:253-257` docstring 逐字）：
  ```
  Ω   = (Ω_E · min(1, n_em / n_seed) · Ω_F)^(1/3) × comp
  S_query = (Ω_E ·     (n_em / n_seed)  · Ω_F)^(1/3) × comp
  ```
  但 docstring 的正文又说「**与 Ω 逐字相同**」——两处表述自相矛盾（见 §D.1）。
  `gen3/REPORT.md:903-905` 的写法带 `max(·,ε)`：
  ```
  Ω       = (Ω_E · min(1, n_emergent/n_seed) · Ω_F)^(1/3) × 完备度
  S_query = (Ω_E ·     (n_emergent/n_seed)  · Ω_F)^(1/3) × 完备度
  ```
- **代码**：
  ```python
  omega_e = min(1.0, n_frames / n_seed)
  omega_n = n_emergent / n_seed            # ← 与 Ω 的唯一差别：无 min(1,·)
  vals = (max(omega_e, eps), max(omega_n, eps), max(omega_f, eps))
  geo = math.exp(sum(math.log(v) for v in vals) / len(vals))
  return geo * comp
  ```
- **是否一致**：`一致`（代码同时保留 `Ω_E` 的 `min(1,·)` 与三个分量的 ε 下界，
  与 gen3 REPORT 的公式吻合；**只**去掉 `Ω_N` 的截断）。
  实测交叉核对：`'泥潭'` → `Ω=0.7937 / S_query=1.0000`；手算复现一致。
- **数学性质**：
  - **值域无上界**：`Ω_E ∈ [0,1]`、`Ω_F ∈ [0,1]`，但 `n_emergent/n_seed` 可 ≫ 1。
    实测 max raw `Ω_N`：`json` 2.0 / `source` 74.0 / `source_type` **496.0**。
    实测 `S_query` 取值（`n_seed≥1` 子集 n=114）：
    | 规则 | max | `>1` 条数 | `>0.5` 条数 |
    |---|---|---|---|
    | `json` | 0.5000 | 0 | 0 |
    | `source` | 1.5166 | 2 | 18 |
    | `metanet` | 1.5166 | 2 | 17 |
    | `source_type` | **2.6075** | **28** | 86 |
    → **`S_query` 可 > 1**（与 Ω 的值域 `[0,1]` 不同），且其分布形态强依赖级联规则。
  - 对 `n_emergent` 单调不减（无饱和）；对 `n_seed` 单调不增。
  - 可微（除 `n_seed=0` 间断）。
- **退化条件**：
  - `n_seed ≤ 0 or n_frames ≤ 0` → 返回 0.0（与 Ω 同一特判）。
  - 去掉截断后**取值数从 40 → 82**（`source` 规则），但**这是诊断价值不是功能价值**：
    gen3 §4.4 证明它预测的目标 `cascade_nonempty` 是**定理**：
    ```
    cascade_nonempty = 1  ⟺  reachable_domains ∩ live_domains(doc) ≠ ∅
    json 635/635 · source 635/635 · metanet 635/635 · source_type 635/635 （一致率 1.0000）
    ```
    决定性对照：同一个「可达集合大小」标量预测**尺寸匹配的随机集合**得
    AUC **0.9739** vs 预测真实非空 **0.9640** —— **同级**，判别力来自「集合更大」。
  - 下游无预测力：per-query MRR 文档内 `ρ = +0.1116`（置换 p = **0.0665**，不显著）。
- **实证状态**：**`diagnostic-only`**。`gen3/REPORT.md:1172` 逐字：
  > **没有证明** `S_query` 在**工程上**有用。它在弱目标上 AUC 更高，但那个目标是定理；
  > 在下游目标上无预测力。`S_query` 的价值是**诊断性的**（暴露了 Ω 的实现缺陷），
  > 不是**功能性**的。

  ⚠️ 另：docstring 里 `0.593 → 0.609（json）` 的 AUC 提升数字**实测不成立**——
  复算得 `json`: `Ω 0.5933 → S_query 0.5926`（**下降** 0.0007）。
  `gen3/REPORT.md:873` 自己报的是 `0.5933 → 0.5926`。见 §D.3。

### M9 compose() 四开关合成器

- **位置**：`metaphor_graph/query_signal.py::compose:140`
- **文档公式**（docstring:146-157）：
  > 开关按**与 Ω 实现相同的顺序**应用，四个开关正交：
  > 1. `normalize`  True → 各分量除以 n_seed
  > 2. `floor`      True → 各分量 `max(v, eps)`；False → 分量为 0 时**直接不参与**
  > 3. 几何平均（固定）
  > 4. `use_completeness` True → 结果乘观测完备度
  > 5. `outer_zero` True → 无激活（n_seed=0）时严格为 0
- **代码**：
  ```python
  if n_seed <= 0:
      return 0.0                                    # ← 提前返回
  vals = [float(v) / n_seed if normalize else float(v) for v in components.values()]
  if floor:
      vals = [max(v, eps) for v in vals]
  else:
      vals = [v for v in vals if v > 0.0]
      if not vals: return 0.0
  geo = math.exp(sum(math.log(v) for v in vals) / len(vals))
  if use_completeness:
      geo *= completeness
  return geo if not outer_zero or n_seed > 0 else 0.0   # ← 三元恒取 geo 分支
  ```
- **是否一致**：**`不一致`**。docstring 声称四个开关**正交**（2⁴ = 16 组合），
  但第 159-160 行的提前 `return 0.0` 使末尾三元表达式 `geo if not outer_zero or n_seed > 0`
  在唯一 `outer_zero` 可能起作用的场景（`n_seed=0`）**永远不会被求值**。
- **数学性质**：
  - **`outer_zero` 是死开关**：`outer_zero=True` 与 `False` 的输出**逐位相同**。
  - **实际正交维度是 3，不是 4**：实测 16 种组合在 `n_seed=2` 上只产生 **8 种**
    不同结果（`n_seed=0` 上只产生 1 种）。
  - `floor=False` 时几何平均的**维数可变**（退化分量被剔除 → 分母 `len(vals)` 变化）
    → 对分量的单调性**不成立**（剔除一个 0 分量反而可能提高结果）。
- **退化条件**：
  - `n_seed ≤ 0` → 恒 0（无论其余开关）。
  - `floor=False` 且所有分量 ≤ 0 → 0.0。
  - **对机制归因实验的影响**：`exp_g3_1_baseline.py` 用 `compose` 做 2⁴ 全因子对照，
    实际只有 8 个有效格点 → 报告的「16 种合成组合」应读作「8 种 + 8 个重复」。
    （结论不受影响：极差 0.126 的估计在 8 个格点上仍成立。）
- **实证状态**：`validated`（作为归因工具；开关正交性假设被证伪）。

### M10 S_log

- **位置**：`metaphor_graph/query_signal.py::_s_log:218`
- **文档公式**（docstring:219-224）：
  > `S_log = log1p(框架数) + log1p(级联数) + log1p(新买到域数)。`
  > ...
  > `等价于 (1+n_f)(1+n_c)(1+n_new) 的几何平均 —— 即「保留几何平均、去掉 ε 下界与归一化」这一支。`
- **代码**：
  ```python
  return (math.log1p(max(0, n_frames)) + math.log1p(max(0, n_cascades))
          + math.log1p(max(0, n_new_domains)))
  ```
- **是否一致**：**`不一致（表述不准确）`**。`S_log = log(∏(1+nᵢ))`，而
  `∏(1+nᵢ)^{1/3}` 的**对数是 `S_log/3`**。实测：
  ```
  S_log(3,2,5) = 4.276666
  3·log(几何平均) = 4.276666   ← 相等
  log(几何平均)   = 1.425555   ← 不相等
  ```
  正确表述是「**乘积的对数**」或「几何平均的对数的 **3 倍**」。
- **数学性质**：
  - 值域 `[0, ∞)`，**无上界**（实测 `_s_log(1000,1000,1000)=20.73`）。
  - `(0,0,0) → 0.0`（退化分量在 log 空间贡献 0，中性）。
  - 对每个计数单调不减；**尺度不变性丢失**（与 Ω 不同，它随计数无界增长）。
- **退化条件**：全为 0 时恒 0；计数极大时主导合成（无归一化）。
- **实证状态**：`diagnostic-only`（gen3 §3.1：`source` 子集 AUC 0.8342，取值数 38，
  但同样受「集合大小」机械效应支配）。

### M11 S_struct

- **位置**：`metaphor_graph/query_signal.py::_s_struct:230`
- **文档公式**（docstring:231-240）：
  > 三个分量按「该分量的基底是否可能非退化」决定是否入选：
  > - 框架激活：n_seed ≥ 1 时基底成立 → min(1, n_frames / n_seed)
  > - 级联扩展：只有在「被激活级联带来了新域」时才入选
- **代码**：
  ```python
  if n_seed <= 0 or n_frames <= 0: return 0.0
  parts = [min(1.0, n_frames / n_seed)]
  if n_cascades > 0 and n_new_domains > 0:
      parts.append(min(1.0, n_new_domains / n_seed))
  return math.exp(sum(math.log(v) for v in parts) / len(parts))
  ```
- **是否一致**：`一致`
- **数学性质**：
  - **只有 2 个分量**（不是 3）——`Ω_F` 完全缺席。
  - 值域 `[0,1]`；`parts` 长度在 1 与 2 之间**跳变** → 在 `n_new_domains=0↔1`
    的边界上函数**不连续**（分母 `len(parts)` 从 2 变 1）。
  - 实测：`(1,1,0,0)→1.0`；`(1,1,1,1)→1.0`；`(2,2,1,1)→0.7071`；`(1,0,0,0)→0.0`。
- **退化条件**：
  - `n_cascades=0 or n_new_domains=0` → 退化为单分量 `min(1, n_frames/n_seed)`，
    取值只有 `{0} ∪ {1/n_seed, 2/n_seed, ..., 1}` 有限档。
  - 用 `n_new_domains`（**检索口径，含源域**）而不是 `n_emergent`（目标域口径）
    → 与 Ω_N 口径不同，两者不可直接比较。
- **实证状态**：`diagnostic-only`（gen3 §3 表格未把它列为强候选）。

### M12 StratifiedNormalizer

- **位置**：`metaphor_graph/query_signal.py::StratifiedNormalizer:321`
- **文档公式**（class docstring:322）：
  > 把任意查询侧计数按 **n_seed 分层** 标准化：`z = (x − μ_stratum) / σ_stratum`。
  > ...
  > `fit()` 只在**有触发词命中**的样本上统计（n_seed=0 的层没有可标准化的变异）。
  > 层内 sd=0 时回退为「x − μ」（即层内偏差），再整体除以全局 sd，避免整层被清零。
- **代码**：
  ```python
  # fit: 对每个 n_seed>=1 的层算 mu 与样本方差 sd（ddof=1，len==1 时 var=0）
  #      devs 收集所有 (v - mu)，再算全局 sd（ddof=1）
  # transform_one:
  if n_seed <= 0: return 0.0
  mu = self._mu.get(int(n_seed))
  if mu is None:                     # 未见过的层 → 全局 z
      mu = sum(self._mu.values()) / len(self._mu) if self._mu else 0.0
  sd = self._sd.get(int(n_seed), 0.0)
  dev = x - mu
  if sd > 1e-9: return dev / sd
  return dev / self._global_sd
  ```
- **是否一致**：`一致`（含两条回退规则）。注意 docstring 说「未见过的层 → 全局 z」，
  代码用的是 **`_mu` 的算术平均**（不是全局 μ）——这一点 docstring 未说明（见 §D.4）。
- **数学性质**：
  - 值域无界；对层内样本的仿射不变（线性）。
  - 层内 sd=0 时**不是标准 z**，而是 `(x−μ)/global_sd`（缩放到全局尺度）。
  - 未见层用「层均值的均值」作 μ，`sd=0` → 走 global_sd 分支。
  - 实测：`_mu={1:1.1667, 2:1.5}`，`_sd={1:1.169, 2:1.291}`，`_global_sd=1.1467`；
    `transform_one(1,3.0)=1.5682`；`transform_one(2,3.0)=1.1619`；`transform_one(0,5.0)=0.0`。
- **退化条件**：
  - `n_seed ≤ 0` → 恒 0.0（层间不可比）。
  - 层内 sd=0 → 用 global_sd，**层内序被保留但尺度被全局化**。
  - **作为标量它并不优于原始计数**：gen3 §3.3 实测条件 z 分数 AUC **0.826** <
    原始 `n_emergent` 的 **0.836**。报告结论：
    > gen2 的「0.654 → 0.836」跳变来自「**换检验方式**（分层内比较）」，不是「换标量」。
- **实证状态**：**`refuted`**（作为「更好的合成」而言）。

### M13 gate_by

- **位置**：`metaphor_graph/query_signal.py::gate_by:381`
- **文档公式**（docstring:382）：
  > 通用门控：信号 ≥ theta 时放行。不改变任何已上报数字。
- **代码**：
  ```python
  if name not in signal:
      raise KeyError(f"未知信号：{name}（可选：{sorted(signal)}）")
  return signal[name] >= theta
  ```
- **是否一致**：`一致`（`>=` 边界放行，实测 `gate_by(sig,'S_query',0.5)` 于 `S_query=0.5` 返回 True）
- **数学性质**：布尔值域；对 `theta` 单调不增；未知键抛异常（fail-fast）。
- **退化条件**：`theta=0.0` 时等价于「信号 > 0 或 == 0」，对非负信号退化为恒真。
  `ObservabilityMeter.gate:294` 的 docstring 明确说 `theta=0` 等价于现有
  `if not agg` 判据（**实测不成立**：一致率仅 0.8956，Ω 门控漏 66 条）。
- **实证状态**：`untested`（模块内无调用方；`ObservabilityMeter.gate` 的等价性声明被 exp3 §B 证伪）。

---

## 3. 溯源可靠性通道（M14–M16）

### M14 frame_reliability

- **位置**：`metaphor_graph/provenance.py::frame_reliability:51`
- **文档公式**（模块 docstring:16-17）：
  > 2. 本体登记的框架 → 1.0；抽取器临时新建的回退框架 → 封顶 0.5；
- **代码**：
  ```python
  if ontology is None or not frame_id:
      return RELIABILITY_ONTOLOGY            # 1.0
  try:
      registered = ontology.get_frame(frame_id) is not None
  except AttributeError:
      return RELIABILITY_ONTOLOGY
  return RELIABILITY_ONTOLOGY if registered else RELIABILITY_FALLBACK_CAP
  ```
- **是否一致**：`一致`（含「无本体/无 id → 不降级」的保守回退）
- **数学性质**：
  - 值域 `{0.5, 1.0}`（**只有两档**，不是连续量）。
  - 对 `frame_id` 不是单调函数（是集合成员判定）。
  - `ontology=None` 或 `frame_id` 为假值 → **恒 1.0**（信息不足时不降级）。
- **退化条件**：
  - **判据必须是「本体有无条目」而非 `F_LLM_` 前缀**：生产本体 **98.6%** 的框架
    以 `F_LLM_` 开头（自举沉淀的正式框架），按前缀判定会把整个本体误判为退化。
  - `frame_id` 为 `None`/`""` → 返回 1.0。**这是 M29 冲突的根源**：
    `health.graph_health` 的第二段口径用本函数统计覆盖率时，无 `frame_id` 的边
    被算作「已登记」。
  - 生产本体上，回退框架的存在使诚实覆盖率从 100% 掉到 82.4%（120 句子集实测）。
- **实证状态**：`validated`（判据正确，实测 82.4% < 85% 门槛暴露了报出 100% 的注水）。

### M15 reliability_factor

- **位置**：`metaphor_graph/provenance.py::reliability_factor:88`
- **文档公式**（docstring:89）：
  > 把可靠性映射成有下界的乘性因子 ∈ [floor, 1]。
  > floor=1.0 时恒为 1.0 —— 即关闭该通道（历史口径的精确复原开关）。
- **代码**：
  ```python
  floor = min(1.0, max(0.0, float(floor)))
  r = min(1.0, max(0.0, float(reliability)))
  return floor + (1.0 - floor) * r
  ```
- **是否一致**：`一致`（实测 `floor=0.5, r=0.5 → 0.75`）
- **数学性质**：
  - 值域 `[floor, 1]`；对 `r` **仿射单调不减**（斜率 `1−floor ≥ 0`）。
  - **`r=1` 是不动点**（`factor(1)=1`）；`r=0` 取到下界 `floor`。
  - **`floor=0` 时是恒等映射**（因子 = r）；`floor=1` 时是常值映射（因子 ≡ 1）。
  - **有下界 ⟹ 永不归零 ⟹ 候选一个不丢**（这是「不丢弃」设计约束的数学实现）。
  - 对 `r` 的双重 clamp（`[0,1]`）使输入越界不会破坏值域。
- **退化条件**：
  - `floor=1.0`（`RELIABILITY_FLOOR_OFF`）→ 通道关闭，历史口径逐位复原。
  - **乘性折扣改变排序但不改变「存在性」**：exp-degrade 实测
    ```
    hand_weighted          MRR 0.9948  Hits@3 1.0000  Hits@10 1.0000
    hand_weighted + 折扣    MRR 0.8922  Hits@3 0.8921  Hits@10 1.0000
    ```
    折扣确实咬到头部（120 条查询金标名次后移、115 条丢掉 top-1，MRR 掉 10 个点）。
  - **对 P1 效应恒为 0（数学上界）**：P1 是句级布尔存在性指标
    （`pred = bool(edges)`），软通道只作用于打分/排序，不改变任何句子的产出与否。
- **实证状态**：`validated`（机制成立；对 P1 的期望被证伪，且是**结构性不可能**而非调参问题）。
  论文 §7 逐字：
  > 降级来源封顶可靠度通道 ｜ 让类型约束影响 P1 ｜ P1 效应恒为 **0**；
  > 7/7 条字面误判句**全部**由本体正式框架支撑（0/7 来自降级边）
  > ｜ **结构性不可能**：P1 是句级布尔存在性指标，软通道只作用于排序

### M16 edge_reliability

- **位置**：`metaphor_graph/provenance.py::edge_reliability:73`
- **文档公式**（docstring:74-78）：
  > 以「边自己记录的 `provenance_reliability`」为准（抽取器写入、可序列化、可审计），
  > 但**优先用本体复核** ...
  > 只有当存储值**更保守**时才采信（防伪升级，允许显式降级）
- **代码**：
  ```python
  derived = frame_reliability(ontology, getattr(edge, "frame_id", None))
  stored = getattr(edge, "provenance_reliability", None)
  if stored is None: return derived
  return min(float(stored), derived)
  ```
- **是否一致**：`一致`
- **数学性质**：
  - `edge_reliability ≤ derived` 恒成立（**只能降不能升**）。
  - 交换律/结合律：对多个存储值反复取 min 仍是 min（幂等）。
  - 实测：`登记/存0.5 → 0.5`（显式降级生效）；
    `未登记/存1.0 → 0.5`（伪升级被阻止）。
- **退化条件**：
  - `stored is None` → 退化为 `derived`（**无本体时为 1.0**）。
  - `frame_id=None` → `derived=1.0` → `min(stored, 1.0) = stored`（存储值不被本体复核约束）。
- **实证状态**：`validated`（防伪升级逻辑实测有效）。

---

## 4. 隐喻连贯度与 HGNN（M17–M21）

### M17 传播算子 S

- **位置**：`metaphor_graph/hgnn.py::propagation_matrix:152`（矩阵形式）；
  `_conv:123`（循环形式）
- **文档公式**（`propagation_matrix` docstring:153）：
  > 稠密传播算子 `M = 0.5(I + (1-ε)·Dv^{-1} H De^{-1} H^T)`。
  > 与 `_conv` 的循环实现逐元素等价，供谱分析 / 单元测试使用。
  > 孤立节点（度 0）行全 0，与 `_conv` 的 `counts[counts==0]=1` 一致。
- **代码**（矩阵形式）：
  ```python
  S = (dv_inv[:, None] * H) @ (de_inv[:, None] * H.T)
  ```
  即 `S = D_v^{-1} H D_e^{-1} H^T`，其中
  `dv = H.sum(axis=1)`（节点度）、`de = H.sum(axis=0)`（超边基数），
  `dv_inv = 1/dv`（`dv=0` 时取 0）、`de_inv = 1/de`（`de=0` 时取 0）。
- **是否一致**：`一致`
- **数学性质**（全部实测，`doc_project`：V=61, E=30）：
  - **行随机**：`S` 行和（活节点）实测 `min = 0.9999999999999998`、
    `max = 1.0`（在 `atol=1e-12` 内精确；浮点误差量级 ~2e-16）。
    这是 `_conv` 两步均值归一化的必然结果（节点度归一 + 超边基数归一）。
  - **ρ(S) = 1.0000000000000013**、**ρ(M) = 1.0000000000000002**
    （`np.linalg.eigvals` 绝对值最大，因 S 非对称；浮点误差内 = 1）。
  - **S 非对称**（`D_v^{-1} H D_e^{-1} H^T` 一般不对称）→ **不能当对称矩阵做特征分解**。
  - **孤立节点（度 0）行全 0**（**不是**行随机）：实测 `S_rowsum = 0.0`。
    只有「活节点」满足行随机。
  - 非负矩阵；不可约性取决于图的连通性（每个连通分量一个单位特征值）。
- **退化条件**：
  - **行随机 ⟹ 质量守恒 ⟹ 无源项迭代必然收敛到分量平稳分布**
    （Perron–Frobenius：ρ=1，单位特征值的重数 = 连通分量数）。
  - `de=0` 的空超边 → 该列贡献 0（`de_inv=0`）。
  - `dv=0` 的孤立节点 → 该行 0，不参与传播。
- **实证状态**：`validated`（`REPORT_exp-dynamics.md §2` 事实 1：
  `S_rowsum_exact_one_live = True`，ρ(S)=ρ(M)=1.0000000000）。

### M18 传播算子 M —— ★ 有文档-代码分歧

- **位置**：`metaphor_graph/hgnn.py::_conv:150`（循环）/ `propagation_matrix:168`（矩阵）
- **文档公式**（`_conv` docstring:126）：
  > 返回 `M·X`，其中 `M = 0.5(I + (1-ε)S)`，`ε = self.leak`。
  > 源项在 `forward` 里加（`_conv` 保持「纯传播算子」语义）。
- **代码**（循环形式）：
  ```python
  # 节点→超边：每条超边取成员节点的均值
  he_feat = [X[members].mean(axis=0) for members in self.he_members]   # (E, D)
  # 超边→节点：每个节点聚合其所属超边的均值
  newX[i] += he_feat[j]; counts[i] += 1
  counts[counts == 0] = 1
  newX /= counts[:, None]
  return 0.5 * (X + (1.0 - self.leak) * newX)
  ```
- **是否一致**：**`不一致`**（在一种边界情形上）。实测 `max|_conv(X) − M@X| = 5.6e-17`
  （正常图，**等价**）；但在 **`he_members` 为空且 `num_nodes > 0`** 时：
  ```python
  if not self.he_members:
      return X                 # ← _conv 提前返回 X
  ```
  而 `propagation_matrix()` 返回 `0.5·I` → `M@X = 0.5·X`。
  实测（`cross_layer=False` + 无 L1 边的图，V=2）：`max|diff| = 0.288675` ≠ 0。
  触发条件：`cross_layer=False` 且 `shg.edges` 为空，但 `shg.frames`/`cascades` 非空。
- **数学性质**（实测）：
  - `M` 行和（活节点）= `1 − ε/2` 精确（实测 `ε=0.1 → 0.95`，`ε=0.2 → 0.9`，`ε=0.5 → 0.75`）。
  - **谱半径 `ρ(M) = 1 − ε/2` 精确取到**（不是不等式）：实测
    `ε=0.1 → ρ=0.9500000000`，`ε=0.2 → ρ=0.9000000000`，`ε=0.5 → ρ=0.7500000000`。
    docstring 写的是 `ρ(M_ε) ≤ 1 − ε/2`（不等式），实测**取等**。
  - `M` 非对称（因 S 非对称）。
  - **孤立节点（度 0）**：`S` 行 = 0 → `M` 行和 = `0.5·1 + 0.5(1−ε)·0 = 0.5`，
    **与 ε 无关**（实测 `ε=0` 与 `ε=0.2` 均为 `0.5`，对角 `M_ii = 0.5`）。
    即「行和 = 1−ε/2」**只在活节点上成立**（实测 `min_keep`… 见上）。
  - **谱半径条件**：`ε=0` 时 ρ(M)=1 → `(I − αM)` 在 `α=1` 时奇异（实测
    `cond = 4.2e16`，零空间维数 = 5 = 连通分量数）。
  - **参数合法性**（`__init__:56-63`）：`leak ∈ [0,1)`；`alpha ≥ 0`；
    `alpha > 1` 需 `α(1−ε/2) < 1` 严格成立，否则抛 `ValueError`（Neumann 级数发散）。
- **退化条件**：
  - `ε=0` 且 `α=1`：非收缩边界，无不动点（`I−M` 奇异）；截断迭代仍有界。
  - `ε>0` 且无源项：迭代**几何衰减到 0**（信息随层数流失）→ docstring 明确
    「ε 只在**配合源项**时才有意义」。
  - 空 `he_members`：`_conv` 与 `propagation_matrix` **不一致**（见上）。
- **实证状态**：`validated`（谱性质全部实测确认；分歧只在退化边界）。

### M19 驱动迭代 forward

- **位置**：`metaphor_graph/hgnn.py::forward:170`
- **文档公式**（docstring:171）：
  > 驱动迭代：`X ← (1-α)·X0 + α·M·X`，迭代 `layers` 次。
  > α = 1.0（默认）时与历史实现逐位一致（`X ← M·X`）
- **代码**：
  ```python
  X0 = self.X.copy()
  X = X0.copy()
  for _ in range(self.layers):
      X = (1.0 - self.alpha) * X0 + self.alpha * self._conv(X)
  ```
- **是否一致**：`一致`
- **数学性质**（实测）：
  - `α=1` 时 `H = M^layers · X0`：实测 `L=1/2/3/5` 的 `max diff` 全 ≤ 1.1e-16。
  - `α=0` 时 `H = X0` 精确（`max diff = 0.0`）。
  - 递推与循环等价（`α ∈ {1.0, 0.5, 0.3, 0.0}`，`max diff ≤ 1.1e-16`）。
  - 收敛速率：`α(1−ε/2) < 1` 时几何收敛，速率 = `α·ρ(M)`。
- **退化条件**：
  - `α=1, ε=0`：`ρ(αM)=1` → **不收敛到不动点**，收敛到分量平稳分布
    （见 M21 的坍缩）。
  - `α=1, ε>0`：`ρ = 1−ε/2 < 1` → 迭代**收敛到 0**（所有节点向量消失）→
    `metaphor_coherence` 的分母趋 0 → 返回 0.0（`na < 1e-9` 保护）。
  - `layers=0`：`H = X0`（未传播）。
- **实证状态**：`validated`（向后兼容性逐位一致；源项效果见 M20）。

### M20 不动点 u*

- **位置**：`experiments/convergence_check.py::fixed_point_solve:47`
- **文档公式**（`hgnn.py` docstring:41-42）：
  > 加上 `(1-α)X0` 源项后，不动点 `u* = (1-α)(I - αM)^{-1} X0` 保留了各自的源身份，不再坍缩。
- **代码**：
  ```python
  A = np.eye(n) - alpha * M
  return (1.0 - alpha) * np.linalg.solve(A, g.X)
  ```
- **是否一致**：`一致`（实测 2000 次迭代 vs 解析解 `max diff = 1.7e-16`）
- **数学性质**：
  - 存在唯一 ⟺ `(I − αM)` 可逆 ⟺ `α·ρ(M) < 1` ⟺ `α(1−ε/2) < 1`。
  - **`α=1` 时不存在**：`I − M` 奇异（实测 `cond=4.2e16`，零空间维数 = 5 = 分量数）
    → 此时 `forward` 收敛到分量平稳分布而非 `u*`。
  - 展开：`u* = (1−α)Σ_{k≥0} (αM)^k X0`（Neumann 级数，收敛条件同上）。
  - **同分量余弦**（源身份保留度量，实测 `doc_project`）：
    ```
    α=0.3 → 0.0683      α=0.5 → 0.1164      α=0.9 → 0.5652
    对照 α=1（layers=500）→ 1.000000
    ```
    即 `α` 越小，源身份保留越充分；`α=1` 完全坍缩。
- **退化条件**：
  - `α → 1`：`(I − αM)` 条件数 → ∞，`u*` 数值不稳定，退化为 M21 的坍缩。
  - `α = 0`：`u* = X0`（无传播）。
  - `ε > 0` 且 `α = 0`：`M` 不起作用，无意义。
- **实证状态**：`validated`（解析解与长迭代一致；`α=1` 无不动点已确认）。

### M21 metaphor_coherence

- **位置**：`metaphor_graph/hgnn.py::metaphor_coherence:221`
- **文档公式**（docstring:222）：
  > 检测器核心：两个实体在跨层图空间中的隐喻连贯度（余弦）。
- **代码**：
  ```python
  a, b = self.entity_vec(src), self.entity_vec(tgt)
  na, nb = np.linalg.norm(a), np.linalg.norm(b)
  if na < 1e-9 or nb < 1e-9: return 0.0
  return float(np.dot(a, b) / (na * nb))
  ```
- **是否一致**：`一致`
- **数学性质**：
  - 值域 `[−1,1]`（实测 `within_component_cosine` 只观测到正值）。
  - 对称；`coh(a,a)=1`（当范数非零）。
  - **`H` 未做归一化** → 范数随层数衰减（实测 `doc_project`：`L=1→0.653`，
    `L=500→0.336`），但不影响余弦。
- **退化条件**（★ 本项目最深刻的数学发现）：
  - **无源项扩散（`α=1`）的渐近坍缩**：`S` 行随机 + `ρ=1` ⟹ `M^k X0` 收敛到
    连通分量的平稳分布 ⟹ **同分量节点向量趋同** ⟹ `metaphor_coherence` 退化为
    「是否同分量」的**二值指示器**。实测 `doc_project`：
    ```
    layers=  1: 同分量余弦 0.187650    跨分量 0.046206
    layers=  2: 同分量余弦 0.383003    跨分量 0.072135   ← H4 的工作点
    layers=  5: 同分量余弦 0.648544
    layers= 50: 同分量余弦 0.963537
    layers=500: 同分量余弦 1.000000    跨分量 0.132778
    ```
  - **但这是渐近命题，不是工作点命题**：`layers=2` 时同分量余弦仅 0.383，
    远未坍缩。`REPORT_exp-dynamics.md §0` 结论 1：
    > 所以「H4 的 0.950 是算子退化造成的」这一说法 **REFUTED**。
    决定性反证：负样本中只有 2/13（doc_project）/ 2/7（doc_relationship）与 src 同分量，
    **完美同分量指示器在该配对样本上的准确率上限 = 16/20 = 0.8000 < H4 实测 0.950**。
  - **`α=1, ε>0`**：所有向量衰减到 0 → 余弦的分子分母同时趋 0 → 返回 0.0
    （`na < 1e-9` 保护）。
  - **`encode()` 未知词的静默回退**（`hgnn.py:183-199`）：未知词的表示
    被替换为「**最近实体节点的 H**」→ 其 coherence 实际是「最近实体 vs 目标」的
    余弦，不是该词自身的语义。这是一个**静默的语义替换**。
- **实证状态**：`validated`（渐近退化成立；工作点未退化；H4 主指标全量 AUC
  HGNN 0.915 vs flat 0.910 —— 层级贡献为零）。
  论文 §6.3 逐字：
  > **信号载体是 n 元性，不是层级性**：关掉框架/级联判别力不变（AUC 0.915 vs 0.910）

---

## 5. 图密度与自适应阈值（M22–M23）

### M22 图密度 Δ

- **位置**：`metaphor_graph/context_budget.py::graph_density:32`；
  `retrieval.py::shg_density:39`；`health.py:144`
- **文档公式**（`graph_density` docstring:33）：
  > 超图密度 Δ = 平均每个端点参与的超边数（总关联数 / 端点数）。
  > 与 HyperRAG 的 Δ(G) 同义：低密度图遍历容易断，高密度图遍历容易爆。
- **代码**：
  ```python
  if n_nodes <= 0: return 0.0
  return float(incidences) / float(n_nodes)
  ```
  调用方 `shg_density:39-47`：
  ```python
  for e in shg.edges:
      ents = set(e.member_entities)      # ← 去重
      nodes |= ents
      inc += len(ents)                   # ← 去重后的元数
  return graph_density(inc, len(nodes))
  ```
  `health.py:139-144` 同样先 `dict.fromkeys` 去重再计度。
- **是否一致**：`一致`。实测 `doc_project`：`inc=104, nodes=48, Δ=2.1667`（两个模块逐位相同）。
- **数学性质**：
  - 值域 `[0, ∞)`；`n_nodes=0 → 0.0`（而非 NaN/异常）。
  - **去重口径**：同一超边内重复出现的端点只计 1 次关联。
  - 与超图的标准「关联数 / (节点数 × 超边数)」**不同**（这是「平均度」而非「密度」，
    docstring 自己也说「平均每个端点参与的超边数」）。
- **退化条件**：
  - 单节点图（`n_nodes=1`）→ Δ = 该节点的度（可极大）。
  - 空图 → 0.0 → 落入 `regime='low'`（`density <= 2.35`）→ 低密度策略。
  - 实测参考值：`doc_project Δ=2.1667`（low 档）、`doc_relationship Δ=2.6250`（mid 档）、
    CCL2018 全量 `Δ=1.071`（low 档）。
- **实证状态**：`validated`（A8 实测中性：稀疏/稠密图均无差异）。

### M23 自适应阈值衰减

- **位置**：`metaphor_graph/context_budget.py::AdaptiveThreshold.select:80`
- **文档公式**（模块 docstring:13-17）：
  > 每跳至少保留 M 条超边，不够就按 c 降阈值（τ₀=0.5, c=0.1, 最多降 5 次）；
  > 同时按图密度 Δ 分三档（下界 2.35 / 上界 5）切换策略——
  > 低密度时把被丢弃的候选补回，高密度时给每跳返回量设上限。
- **代码**：
  ```python
  items = sorted(scored, key=lambda x: -x[1])
  tau = self.tau0; decays = 0
  selected = [it for it in items if it[1] >= tau]
  while len(selected) < min(self.min_keep, len(items)) and decays < self.max_decays:
      tau -= self.decay; decays += 1
      selected = [it for it in items if it[1] >= tau]
  ```
  密度分档 `regime:73`：`density <= low(2.35) → "low"`；`<= high(5.0) → "mid"`；否则 `"high"`。
  高密度截断：`cap = self.max_keep or max(self.min_keep * 3, 1)`。
- **是否一致**：`一致`（默认参数 `tau0=0.5, decay=0.1, max_decays=5, min_keep=50`）。
  实测：`tau0=0.5, decay=0.1, min_keep=50`，200 候选 → 降 1 次到 τ=0.4，选 51 条。
- **数学性质**：
  - `τ(k) = τ₀ − k·c`，`k ≤ max_decays`；**无下限钳制**。
  - `selected(τ)` 对 τ 单调不增 → 循环是「找最小的 k 使 `|selected| ≥ min_keep`」。
  - **`min(self.min_keep, len(items))`**：候选不足时不硬凑（`test_no_padding_with_noise` 护栏）。
  - **τ 可为负**：实测 `tau0=0.5, decay=0.3, max_decays=5` → τ 最终 **−0.1**，
    此时 `score >= τ` 恒真 → **全量放行**（无上限，除非高密度档）。
- **退化条件**：
  - **τ < 0** → 阈值失效，退化为「返回全部候选」（再由 `top_k` 截断）。
  - `min_keep` 大于候选数 → 循环空转（`min(...)` 保护）。
  - **A8 实测无差异**：`REPORT`/README §7.3
    ```
    开阈值 Recall@10 0.500   关阈值 Recall@10 0.500  （2 文档 8 查询）
    全量 CCL2018（Δ=1.071）: 开/关 Recall@10 完全一致（0.250, n=6 有效级联查询）
    ```
    论文 §7 逐字：`A8 关自适应阈值 | — | 稀疏/稠密图均无差异 | 中性`
- **实证状态**：`validated`（机制正确，A8 中性——评测集密度不足以触发该机制）。

---

## 6. 上下文预算（M24）

### M24 上下文预算 50/30/20

- **位置**：`metaphor_graph/context_budget.py::ContextBudget.pack:157`
- **文档公式**（模块 docstring:5-8）：
  > HyperRAG 把生成上下文拆成三类组件并硬性分配预算：
  > 超边 50% / 实体 30% / 源文本块 20%，按合理性分数降序填充，
  > 某一类没用完的额度顺延给下一类。
- **代码**：
  ```python
  budgets = [self.max_tokens * r for r in self.ratios]      # ratios=(0.5, 0.3, 0.2)
  carry = 0.0
  for i in range(3):
      room = budgets[i] + carry
      used = 0.0
      for item in pools[i]:
          c = self._cost(item)
          if used + c <= room:
              picked[i].append(item); used += c
      carry = room - used          # 没用完的额度顺延给下一类
  ```
  `_cost:154`：`max(1.0, len(text) / chars_per_token)`，`chars_per_token=1.6`。
- **是否一致**：**`部分不一致`**。
  - 预算比例 `(0.5, 0.3, 0.2)` 与顺延规则 **一致**。实测 `max_tokens=1000`、
    `chars_per_token=1.0`、三类各 `["短", "概念A", "x"*500]`：
    超边配额 500 只用 1 → 顺延 499；实体 `room = 300+499 = 799` 只用 3 → 顺延 796；
    chunk `room = 200+796 = 996`，500 字被接受。三类都命中。
  - **「按合理性分数降序填充」不成立**：`pack()` **不做任何排序**，按调用方传入的
    顺序尝试。实测：输入 `[50字(低分), 4字(高分)]` 与 `[4字(高分), 50字(低分)]`
    给出**不同的结果**（前者选 50 字，后者选 4 字）。排序责任在调用方
    （`pack_context:334` 传入的是 `rank_mappings` 的输出，已排序）。
  - **大项放不下是「跳过」不是「break」**：实测预算 50、池 `[60字, 10字]`
    → 选中 `[10字]`（跳过 60 继续尝试 10）。docstring 未说明这一点。
- **数学性质**：
  - 三类配额和为 `max_tokens`（`ratios` 和必须为 1，否则抛 `ValueError`）。
  - **顺延使总用量有上界 `max_tokens`**：`room_i = budget_i + carry_{i-1}`，
    `carry_i = room_i − used_i ≥ 0` → `Σ used = Σ budget − carry_final ≤ max_tokens`。
    实测 `max_tokens=1000`、三类 `[1, 3, 0]` 字 → 总用量 4 ≤ 1000。
    （注意：单类 `room` 可超过该类配额——实测 chunk 的 `room = 200 + 297 + 499 = 996`，
    但三类总和仍受 `max_tokens` 约束。）
  - `_cost` 有下界 1.0 → **空串也占 1 token**（防止零成本无限填充）。
  - 非单调：加入一个更大的候选可能挤掉后面的小候选（贪心）。
- **退化条件**：
  - `ratios` 和 ≠ 1 → 抛异常（`test_ratios_must_sum_to_one` 护栏）。
  - 单项 `_cost > room` → 该项被丢弃（`test_overflow_is_trimmed`：
    预算 100、单项 200 字 → `hyperedges=[]`）。
  - `chars_per_token=1.6` 是**拍定值**（中文按 1.6 字符/token 估算），
    无实测校准 → 实际 token 数可能偏差 ±30%。
- **实证状态**：`validated`（机制正确）。生成层效果**judge 敏感**：
  论文 §6.5 逐字
  > deepseek judge 判纯向量对照 6:1 胜，glm judge 判当前打包最优（26.50 vs 21.12）
  > ——**结论随 judge 模型反转**。

---

## 7. RRF 融合（M25）

### M25 RRF

- **位置**：`metaphor_graph/retrieval.py::_rrf:32`；调用方 `rrf_fusion:346`
- **文档公式**（`知识隐喻分析任务方案.md:434`）：`融合：RRF`
  （**方案只给了名字，没给公式**；`retrieval.py` 模块 docstring 也只说「RRF 融合」）
- **代码**：
  ```python
  def _rrf(rank_list: List[str], k: int = 60) -> Dict[str, float]:
      s: Dict[str, float] = defaultdict(float)
      for rank, cid in enumerate(rank_list):
          s[cid] += 1.0 / (k + rank + 1)
      return dict(s)
  ```
  融合（`rrf_fusion:349-351`）：
  ```python
  fused = defaultdict(float, _rrf(literal))
  for cid, s in _rrf(meta.chunk_ids).items():
      fused[cid] += s
  ```
- **是否一致**：`一致`（与标准 RRF `1/(k+rank)`、rank 从 1 起、k=60 等价；
  实测 `_rrf(['x']) = 1/61 = 0.01639344262295082`）。
- **数学性质**：
  - `RRF(第 i 名) = 1/(k+i)`，`i = 1,2,3,...`；值域 `(0, 1/(k+1)]`。
  - 对排名单调递减；对多路求和 → 融合分 = 各路的倒数排名之和。
  - **无权重**：字面路与隐喻路量级相同（两路各返回 k 条时，第 1 名合计 `2/61`）。
  - `k=60` 抑制头部优势：`1/61 = 0.0164` vs `1/62 = 0.0161`（相邻名次差 1.6%）。
- **退化条件**：
  - **字面通路的「排名」不含相关性信息**：`rrf_fusion:347`
    ```python
    literal = [f"{self.doc_id}_c{i}" for i, c in enumerate(self.chunks) if query in c]
    ```
    → rank 就是 **chunk 在文档中的枚举顺序**，不是匹配强度（无 TF/IDF/位置权重）。
    实测：`chunks=["泥潭在这里","无关句子","泥潭又在别处"]` → literal = `['d_c0','d_c2']`。
  - **无候选时**：`_rrf([]) = {}` → `fused` 只有另一路的贡献。
  - `k` 无自适应：文档长度、通路数变化时 `k=60` 固定。
  - **实测状态**：`untested`。全仓无 RRF 的独立评测
    （`test_rrf_fusion` 只断言「融合结果非空」）。
- **实证状态**：`untested`（公式正确，但「融合是否带来增益」无实测；
  且字面通路在改写型查询上 Recall = 0.0000，融合实际退化为单路）。

---

## 8. 7 维特征与人工权重（M26–M27）

### M26 7 维特征

- **位置**：`metaphor_graph/training.py::FEATURE_NAMES:41`；
  `extract_text_features:106`（文本锚点）；`extract_features:148`（边锚点）
- **文档公式**（`training.py:42-49`）：
  ```python
  FEATURE_NAMES = [
      "sem",        # 查询超边与候选超边描述的语义相似度
      "struct",     # 候选超边中心性（喻底规模 + 级联归属）
      "clue",       # 触发词重合度
      "type",       # 类型安全约束（结构化防污染，本项目独有）
      "same_frame", # 角色感知结构信号：同框架
      "same_cascade",  # 角色感知结构信号：同级联
      "ground_jaccard",  # 喻底集合 Jaccard（扩展隐喻合并判据的连续化）
  ]
  ```
  论文 §3.4 只列名字（`sem/struct/clue/type/same_frame/same_cascade/ground_jaccard`），
  **未给任何一维的公式**。
- **代码（逐维实测）**：

  | 维 | 边锚点 `extract_features` | 文本锚点 `extract_text_features` | 值域 |
  |---|---|---|---|
  | `sem` | `max(0.0, cosine(embed(qe.describe()), embed(cand.describe())))` | 同上，`qe` 换 `query_text` | `[0,1]`（**clamp 到 0**） |
  | `struct` | `min(1.0, centrality.get(cand.id, 0.0))`，`centrality = 0.5·|ground| + 0.5·[cascade_id 非空]` | 同左（`centrality` 为 None 时现算同一式） | `[0,1]`（被 `min` 截断） |
  | `clue` | `min(1.0, 0.5 · |qe.triggers ∩ cand.triggers|)` | `min(1.0, 0.5 · |{t ∈ cand.triggers : t in query_text}|)` | `[0,1]` |
  | `type` | `ont.type_reliability_of(cand.frame_id, cand.source_type)` | 同左 | `{0.0, 0.5, 1.0}` |
  | `same_frame` | `1.0 if (qe.frame_id and qe.frame_id == cand.frame_id) else 0.0` | `1.0 if cand.frame_id in frames else 0.0`，`frames` = 查询触发词命中的框架集 | `{0,1}` |
  | `same_cascade` | `1.0 if (qe.cascade_id and qe.cascade_id == cand.cascade_id) else 0.0` | `1.0 if cand.cascade_id in cascades else 0.0` | `{0,1}` |
  | `ground_jaccard` | `_jaccard(qe.ground, cand.ground) = |∩|/|∪|` | `|{w ∈ cand.ground : w in query_text}| / max(1, |cand.ground|)`（**包含率，不是 Jaccard**） | `[0,1]` |

  ⚠️ **死代码**：`retrieval.py:310` 的 `_clue_count` 全仓**无调用方**
  （`metaphor_retriever_score` 已改走 `_pair_features` → `training.extract_features`）。
  `experiments/probe_formula_divergence.py:7` 的注释「retrieval: `_clue_count` 同式」
  因此是**过时描述**。该函数与 `extract_features` 的 `clue` 表达式**确实同式**
  （`min(1.0, 0.5 * hits)`，实测一致），故无实质分歧。

- **是否一致**：**`不一致`（`ground_jaccard` 两路径定义不同）**。
  `experiments/REPORT_exp-source.md §5.1` 逐字：
  > | `extract_text_features:98`（文本锚点） | **包含率** `|g ∩ text| / |g|` |
  > | `extract_features:130`（边锚点） | **真 Jaccard** `|gq ∩ gc| / |gq ∪ gc|` |
  > 实测：包含率均值 0.125 vs Jaccard 均值 0.150；包含率 ≥ Jaccard 的比例 96.3%。
  > 这是**设计内的锚点差异**——文本没有喻底集合，无法算 Jaccard。
  > 但两者不是同一函数的两种写法（包含率分母只有 `|g|`，系统性偏高）
  分歧率实测 **4.76%（113/2375）**。
- **数学性质**：
  - `sem`：**clamp 到 0** → 负相似度被丢弃。
    ⚠️ 历史隐患**已消除**：`REPORT_exp-source.md §5.2` 曾标注「`retrieval.py:246-247`
    的人工加权路径无 clamp」——但当前代码 `metaphor_retriever_score:303` 已改为
    `self._pair_features(...)` → `training.extract_features`（含 clamp），
    故两条路径现在**都是 clamp 的**。全仓仅剩 `retrieval.py:181` 的语义兜底路径
    直接调 `embeddings.cosine`（那不是特征，无 clamp 需求）。
  - `struct`：**85.1% 的候选对取值恰为 1.0**（`REPORT_exp-source.md:186`）。
    精确饱和条件（实测）：`(|ground| ≥ 1 且 cascade_id 非空)` 或
    `(|ground| ≥ 2 且 无级联)`；`centrality=None` 与 `centrality` 字典两条路径
    在**有值**时一致，但 **`centrality={}`（空字典）会让 `struct` 恒为 0.0**
    （`dict.get` 默认值），而 `centrality=None` 会走现算式给出 1.0
    —— 这是**静默的口径陷阱**（`RetrievalEngine._compute_centrality` 覆盖全部边，
    故生产路径不受影响）。
  - `clue`：**AUC≈1.0**（自监督 chunk 模式）→ 训练退化为「复读抽取器」。
  - `type`：单特征 AUC ≈ **0.497**（近噪声）；`_LEARNED_SHARE` 里权重 0.0487（≈0）。
  - `same_frame`/`same_cascade`：**成对共线**（`_LEARNED_SHARE` 0.1953 / 0.1958，
    单特征 AUC 均为 0.5975）。
  - `_jaccard([], []) = 0.0`（**空集对返回 0 而非 1**，有意为之）。
  - `_jaccard` 值域 `[0,1]`；对称；对集合去重（`set(a)`）。
- **退化条件**：
  - **无 ontology 时**：`same_frame = same_cas = 0.0`（`if ontology is not None` 守卫）
    → 3 维恒 0。且 `type_ok` 回落 `DEFAULT_ONTOLOGY`（种子本体，20 框架）。
  - **`centrality={}`**（空字典而非 None）→ `centrality.get(cand.id, 0.0) = 0.0`
    → `struct` 恒 0（静默退化）。
  - **改写型查询下**：`same_frame`/`same_cascade`/`ground_jaccard` 全部失效
    （AUC 0.505–0.530），仅剩 `sem`（AUC 0.62）→
    论文 §6.1 逐字：**语义通路在改写型查询上退化为纯语义相似度检索**。
  - **1 维 `sem` 单信号 = 7 维训练后**：论文修正建议 §269
    > **1 维 `sem` 单信号 = 0.5474，与 7 维训练后 0.5449 无差异**（Δ=+0.0025，CI 覆盖 0）；
    > 在真实句向量下 **纯 `sem` 显著优于训练后 7 维（+1.76pp，p=0.003）**。
- **实证状态**：`validated`（特征正确；A9 去角色特征 MRR 完全不变 → **H7 证伪**）。

### M27 HAND_WEIGHTS / HAND_WEIGHTS_LEGACY

- **位置**：`metaphor_graph/training.py:62`（LEGACY）/ `:65`（`_LEARNED_SHARE`）/
  `:70`（`_normalized`）/ `:76`（HAND_WEIGHTS）/ `:79`（`hand_weighted_score`）
- **文档公式**（`training.py:60-61`）：
  > `HAND_WEIGHTS_LEGACY` —— 原 4 维（0.35/0.25/0.20/0.20），保留以复现历史数字
  > `HAND_WEIGHTS`        —— 按训练学到权重的比例重标定（默认，7 维）
- **代码**：
  ```python
  HAND_WEIGHTS_LEGACY = {"sem": 0.35, "struct": 0.25, "clue": 0.20, "type": 0.20}
  _LEARNED_SHARE = {"sem": 0.6911, "struct": 0.0195, "clue": 1.2543, "type": 0.0487,
                    "same_frame": 0.1953, "same_cascade": 0.1958,
                    "ground_jaccard": 0.4965}
  def _normalized(d): 
      tot = sum(d.values())
      return {k: v / tot for k, v in d.items()} if tot > 0 else dict(d)
  HAND_WEIGHTS = _normalized(_LEARNED_SHARE)
  ```
  打分（`hand_weighted_score:79-95`）：
  ```python
  for i, name in enumerate(FEATURE_NAMES):
      wi = w.get(name, 0.0)
      if wi == 0.0: continue
      v = features[i]
      if name in ("struct", "clue"): v = min(v, 1.0)
      total += wi * v
  ```
- **是否一致**：`一致`
- **归一化后的实际权重**（实测）：
  ```
  sem              0.238212
  struct           0.006721
  clue             0.432338
  type             0.016786
  same_frame       0.067317
  same_cascade     0.067489
  ground_jaccard   0.171136
  ─────────────────────────
  和               1.000000
  ```
- **数学性质**：
  - `HAND_WEIGHTS` 权重和 = 1.0；`LEGACY` 和 = 1.0（4 维）。
  - `hand_weighted_score` 是**线性组合 + 两个 `min(·,1)` 截断**。
  - **`min(v,1.0)` 对 `struct`/`clue` 是死代码**：两个生产者已经各自
    `min(1.0, ·)`（`extract_features:164/167`、`extract_text_features:123/125`）
    → 实测对 `ground=6/triggers=3` 的边，截断与不截断给出**相同分数**。
    只有裸传入 >1 的值才起作用（实测 `[1,5,9,...]` → 0.9144 vs 4.4）。
  - **LEGACY 未覆盖 3 个新维** → `w.get(name, 0.0)` 视为 0 → LEGACY 是「4 维
    线性组合」而 HAND_WEIGHTS 是「7 维」→ **两者不可直接比数值**。
- **过权倍数**（实测）：
  ```
  struct: LEGACY 0.25 vs HAND_WEIGHTS 0.006721  → 37.2× 过权
  type:   LEGACY 0.20 vs HAND_WEIGHTS 0.016786  → 11.9× 过权
  ```
  论文 §6.2 逐字：
  > **"训练反超人工加权 +4.5pp"主要是人工权重配错的产物**。原人工权重
  > （0.35/0.25/0.20/0.20）与学到权重严重错配：**struct 过权 37 倍、type 12 倍**
  > （归一化后；原始口径 49/19 倍）。仅把人工权重按学到比例重标定
  > （不训练任何模型），anchored MRR 即从 0.8390 升到 **0.8956（+5.7pp）**；
  > 而在 deanchor 下重标定效应仅 **+0.0023**。
- **退化条件**：
  - **`struct`/`clue` 在真实数据上高度饱和**（85.1% / AUC≈1.0）→ 加权和对候选的
    区分度主要来自 `sem` 与 `ground_jaccard`。
  - `weights={}` → `total = 0.0`（全维权重 0）。
  - 重标定只在**锚定口径**下有效（anchored Δ=+0.0565，deanchor Δ=+0.0023）。
- **实证状态**：`validated`（重标定效果实测；`REPORT_exp-source.md` 判定
  「训练增益主要是配错权重的产物」）。

---

## 9. H4 全量 AUC（M28）

### M28 全量 AUC

- **位置**：`metaphor_graph/evaluate_hgnn.py::_auc_full:316`；
  `metaphor_graph/training.py::feature_auc:210-212`；
  `experiments/_stats.py::auc:113`
- **文档公式**（`_auc_full` docstring:317）：
  > ROC-AUC = P(pos > neg) + 0.5·P(pos == neg)，用全量正负对。
  `experiments/_stats.py:114`：
  > P(X_a > X_b) + 0.5·P(=) —— 与 Mann-Whitney U 同一统计量（AUC 视角）。
- **代码**（三处实现）：
  ```python
  # evaluate_hgnn._auc_full
  auc = float((p > q).mean() + 0.5 * (p == q).mean())
  # training.feature_auc
  gt = (pos[:, None] > neg[None, :]).mean()
  eq = (pos[:, None] == neg[None, :]).mean()
  out[name] = float(gt + 0.5 * eq)
  # experiments/_stats.auc（Mann-Whitney U 形式）
  ranks = _rank(list(a) + list(b))
  return (ra - len(a) * (len(a) + 1) / 2.0) / (len(a) * len(b))
  ```
- **是否一致**：`一致`。三实现在含大量并列的样本上**逐位相同**
  （实测 `_auc_full = _stats.auc = 暴力 gt+0.5eq = 0.4866666667`）。
  另 `Cliff's δ = 2·AUC − 1` 与 `auc` 一致（实测 `−0.0266666667`）。
- **数学性质**：
  - 值域 `[0,1]`；0.5 = 无信息（**正确处理并列**）。
  - 与 Mann-Whitney U 的关系：`AUC = U/(n₁n₂)`（exp5 §V 自校验：
    `U/(n1·n2) = 0.349289 = AUC`）。
  - 对称性：`AUC(a,b) = 1 − AUC(b,a)`（无并列时）。
  - 与**配对准确率**的差别：`acc = P(pos > neg)`，**并列计为错误**。
    实测全并列时 `acc = 0.0` 而 `AUC = 0.5`。
- **退化条件**（★ 本项目一个重要的口径陷阱）：
  - **全并列 → AUC = 0.5（无信息），但配对准确率 → 0.0（看起来「反向判别」）**。
    论文 §6.3 逐字：
    > 原表 0.150 低于随机是**并列计错的口径产物**——默认哈希向量下抽象域标签
    > 几乎无共享 n-gram，实测全体并列率 94.6%。
    > 修正表述为：**没有 n 元共现聚合就没有可判别的结构信号**（AUC 0.550 ≈ 随机）。
  - **n=20 的配对准确率功效不足**：分辨率 0.05，18 个 `(α,ε)` 配置下
    `|Δacc| ≤ 0.05` 全部落在噪声内，且「结论字符串」会随 α 抖动翻转
    （α=0.5 时打印「依赖跨层传播 ✅」）。论文 §7 逐字：
    > HGNN 加源项 ｜ 打破 flat/HGNN 平局 ｜ 18 个 (α,ε) 配置下 \|ΔAUC\| ≤ 0.005，
    > 95% CI 跨 0 ｜ **平局非算子退化所致**；源项只在 layers ≥ 50 有意义
- **实证状态**：`validated`（作为主指标被采纳；实测
  `auc_h4.csv`：`auc_hgnn=0.9414 / auc_flat=0.9409 / auc_raw=0.5500 / auc_gru=0.9400`）。

---

## 10. 诚实覆盖率（M29–M30）

### M29 诚实覆盖率 —— ★ 有文档-代码分歧

- **位置**：`metaphor_graph/health.py::graph_health:174-219`
- **文档公式**（`health.py:52-55` 注释 + 论文 §5.2）：
  > 上面报出的 hierarchy_coverage 里，有多少是**本体登记框架 + 本体登记级联**
  > 撑起来的？...
  > 传 ontology 时才算；不传则为 None（历史口径逐位不变）。
  `health.py:184-185`：
  ```python
  h.registered_hierarchy_coverage = min(h.registered_frame_coverage,
                                        h.registered_cascade_coverage)
  ```
- **代码**（**两次赋值，第二次覆盖第一次但不算 hc**）：
  ```python
  # 第一段 (health.py:174-194)：算 hc 与 n_fallback_edges
  if ontology is not None:
      reg = [e for e in edges
             if e.frame_id and ontology.get_frame(e.frame_id) is not None]   # ← 要求 frame_id 非空
      h.registered_frame_coverage = len(reg) / len(edges)
      n_cas = 0
      for e in reg:
          cid = ontology.get_cascade(e.frame_id)                            # ← 只看本体级联
          if cid and cid in ontology.cascades: n_cas += 1
      h.registered_cascade_coverage = n_cas / len(edges)
      h.registered_hierarchy_coverage = min(...)                            # ← hc 在这里定型
      h.n_fallback_edges = len(edges) - len(reg)

  # ... 中间还有 deprecated/evidence/avg_confidence ...

  # 第二段 (health.py:205-219)：**覆写** registered_frame_coverage / cascade_coverage
  if ontology is not None:
      reg_frame = sum(1 for e in edges
                      if frame_reliability(ontology, e.frame_id) >= RELIABILITY_ONTOLOGY)
      h.registered_frame_coverage = reg_frame / len(edges)                  # ← 覆写
      def _in_reg_cascade(e):
          if frame_reliability(ontology, e.frame_id) < RELIABILITY_ONTOLOGY: return False
          cid = e.cascade_id or ontology.get_cascade(e.frame_id)            # ← 也看 e.cascade_id
          return bool(cid) and ontology.get_cascade_spec(cid) is not None
      h.registered_cascade_coverage = (sum(...) / len(edges))               # ← 覆写
      # ← 没有重算 h.registered_hierarchy_coverage
  ```
- **是否一致**：**`不一致`**。三个后果：
  1. **`registered_hierarchy_coverage` 与 `min(registered_frame_coverage,
     registered_cascade_coverage)` 可以矛盾**。
  2. **无 `frame_id` 的边在第二段被算作「已登记」**：`frame_reliability(ontology, None)`
     返回 **1.0**（`provenance.py:57` 的 `not frame_id` 分支）。
  3. **`registered_cascade_coverage` 的第二段口径更宽**：它接受 `e.cascade_id`
     （可能是 `C_ADHOC_*`），而第一段只看 `ontology.get_cascade(frame_id)`。
- **实测分歧**（构造最小反例，V=2 条边：一条挂登记框架，一条无 `frame_id`
  但 `cascade_id` 指向本体级联）：
  ```
  字段: fc=1.0000  cc=1.0000  hc=0.5000
  第一段口径: fc1=0.5  cc1=0.5  hc1=0.5
  第二段口径: fc2=1.0  cc2=1.0
  >>> min(报出的 fc, 报出的 cc) = 1.0000  !=  报出的 hc = 0.5000   **矛盾**
  n_fallback_edges = 1（与 fc=1.0 矛盾：它说 1 条是回退边）
  ```
  另一反例（`e.cascade_id = "C_ADHOC_xxx"`）：
  ```
  第一段 cc1 = 1.0（忽略 e.cascade_id）  第二段 cc2 = 0.0（采信 C_ADHOC_）
  >>> min(字段 fc, 字段 cc) = 0.0000  !=  hc = 1.0000
  ```
- **在真实语料上不触发**：实测 110 句伪文档（2 文档 × 2 次 build）
  **分歧文档 0/2，无 `frame_id` 的边总数 = 0**（builder 保证每条边都有框架归属）。
  → 这是**潜在 bug，当前不显现**；一旦有边无框架（例如 L3 消融的
  `orphan_cascade_rule="none"` 或手工构造的边）就会显现。
- **数学性质**：
  - 第一段：`reg` 要求 `frame_id` 非空 **且** 本体有条目 → 严格口径。
  - 第二段：`frame_reliability(...) >= 1.0` ⟺ `frame_id` 为空 **或** 本体有条目
    → 更宽（把「无框架」当「已登记」）。
  - `min(·,·)` 是「与」式合成：两项都要高才高（与 Ω 的几何平均同类）。
- **退化条件**：
  - 不传 `ontology` → 所有 `registered_*` 保持 `None`，报告不含该行（历史口径逐位不变）。
  - 无 `frame_id` 的边 → 第二段把它算进分子，`n_fallback_edges`（第一段算的）
    与之矛盾。
  - `adhoc_cascades` 只统计 `C_ADHOC_` 前缀的**图中**级联（不是本体级联）。
- **实证状态**：`validated`（作为指标：论文 §5.2 报 **82.4% < 85% 门槛**，
  暴露报出 100% 的注水）。分歧本身**未在真实语料触发**。

### M30 报出覆盖率

- **位置**：`metaphor_graph/health.py:162`
- **文档公式**（`health.py` 模块 docstring:12）：
  > hierarchy_cov    L1→L2→L3 归属覆盖率。方案 §7 的 P2 门槛是 >85%。
- **代码**：
  ```python
  h.frame_coverage = with_frame / len(edges)
  h.cascade_coverage = len(in_cascade & frame_ids) / max(1, len(frame_ids))
  h.hierarchy_coverage = min(h.frame_coverage, h.cascade_coverage)
  ```
- **是否一致**：`一致`
- **数学性质**：
  - 值域 `[0,1]`；`min` 合成（与式）。
  - `cascade_coverage` 的分母是**框架数**（不是边数）→ 两个分量的分母不同，
    `min` 的比较是跨尺度的。
- **退化条件**：
  - **可由 `C_ADHOC_*` 事后补建撑到 1.000**：`builder._ensure_cascades` 给
    「不属于任何级联」的孤儿框架按目标域打包补建级联（110 次 build 共补出 399 个
    `C_ADHOC_` 级联，size 中位数 1、max 1）。
  - `shg.frames` 为空 → `cascade_coverage = 0.0` → `hierarchy_coverage = 0`。
  - **已知结构缺陷**：按目标域打包与 `llm_ontology.build_specs` 的规则**完全相同**
    → 补出的级联与本体级联同构（成员共享单一目标域，跨域扩展能力为零），
    唯一量化收益是把 `cascade_coverage` 从 ~0.78 抬到 1.000。
- **实证状态**：**`refuted`**（作为「层级归属达标」的证据）。论文 §5.2 逐字：
  > 报出的 100% 由两种不同性质的归属混合而成。实测（120 句子集）：超边 108 条中
  > **只有 82.4% 挂在本体正式登记的框架上** ... **排除这些后覆盖率 82.4%，
  > 低于 P2 的 85% 门槛。**

---

## 11. 其余检索层数学对象（M31–M32）

### M31 multi_clue_retrieval —— ★ 有文档-代码分歧

- **位置**：`metaphor_graph/retrieval.py::multi_clue_retrieval:217`
- **文档公式**（docstring:219 + 方案 §4.4.2）：
  > 被 ≥2 个触发词支持的映射优先返回（§4.4.2）。
  方案 `知识隐喻分析任务方案.md:340` 的代码：
  ```python
  # 只保留被 ≥2 个触发词支持的映射
  return [(c, s) for c, s in candidate_scores.items() if s >= 2 * THRESHOLD]
  ```
- **代码**：
  ```python
  candidate_scores: Dict[str, float] = defaultdict(float)
  for trig in triggers:
      for m in self.get_mappings(trig):
          candidate_scores[m.target_domain] += m.confidence
  return [(c, s) for c, s in candidate_scores.items() if s >= 2 * threshold]
  ```
- **是否一致**：**`不一致`（文档表述误导）**。
  - 方案自己的代码也写 `s >= 2 * THRESHOLD`，注释却说「≥2 个触发词支持」
    → **注释与代码在方案里就已经不符**。
  - 实测：单触发词 `['泥潭']` 且 `confidence=0.9` → **被放行**
    （`0.9 ≥ 2×0.3 = 0.6`），即**只有 1 个触发词支持**。
  - 实测：`['泥潭','泥潭']`（重复）→ `0.9+0.9=1.8` → **重复触发词被计两次**。
  - 实测：`['发条']` 且 `confidence=0.4` → 被拦（`0.4 < 0.6`）。
  - 正确的语义是「**同一目标域的置信度之和 ≥ 2·threshold**」，
    它既不是触发词计数，也不是「≥2 条映射」。
- **数学性质**：
  - 按 `target_domain` 聚合（**不是按映射/超边**）。
  - 对触发词列表**非幂等**（重复元素改变结果）。
  - 值域 `[0, ∞)`；无上界（触发词多时可极大）。
  - 阈值 `threshold=0.3` 是拍定值（**无敏感性实验**）。
- **退化条件**：
  - 高置信度单触发词可单独通过（`confidence ≥ 2·threshold`）→
    「多线索汇聚」退化为「单线索高置信」。
  - 重复触发词 → 分数虚高。
  - `triggers=[]` → 返回 `[]`。
- **实证状态**：`untested`（`demo.py:110` 与 `test_metaphor_graph.py:187` 是仅有的
  调用方，均只断言非空；**不参与任何已上报指标**）。

### M32 cross_domain_retrieve 候选打分

- **位置**：`metaphor_graph/retrieval.py:170-172`
- **文档公式**：**文档未给出**。方案 §4.4.1 只描述了通路，未给打分式。
- **代码**：
  ```python
  score = (e.confidence + 0.3 * len(e.ground)) * self.reliability_factor(e)
  agg[s.chunk_id] += score
  ```
  语义兜底路径（`:190-192`）用同一式。
- **是否一致**：`文档未给出`（仅在 `retrieval.py` 模块 docstring 提及「跨域检索」）。
- **数学性质**：
  - 非负；**无上界**（`len(e.ground)` 无界；`confidence ∈ [0,1]` 典型）。
  - `0.3·|ground|` 是「n 元性奖励」：喻底越多分越高。
  - `reliability_factor ∈ [floor, 1]` → 缩放但**不改变符号**。
  - `agg[chunk_id]` 是**同一 chunk 上所有命中超边的分数之和** → 可 > 1。
  - **不归一化、不做长度惩罚** → 长喻底超边系统性占优。
- **退化条件**：
  - `reliability_floor=1.0` → 因子恒 1（历史口径）。
  - 无候选（`agg` 空）→ 走 `semantic_fallback`（若开启）或返回空结果。
  - `ground=[]` → 分数退化为 `confidence × factor`。
  - **与 7 维特征路径不一致**：本式用 `0.3·|ground|` 线性奖励，
    7 维路径用 `struct = min(1, 0.5|ground| + 0.5[cascade])`（**饱和**）
    → 两条路径对「长喻底」的偏好不同（前者无界，后者封顶）。
- **实证状态**：`validated`（A6 消融主通路；`evaluate_fullcorpus` 走的是
  `score_conditions` 的 7 维路径，**不经过**本式）。

---

## D. 「文档与代码不一致」清单（完整）

> 共 **12 处**。按严重程度排序：
> `★` = 影响结论或指标（D.1–D.5，5 处）；
> `☆` = 表述 / 口径 / 未披露（D.6–D.11，6 处）；
> `⚠️` = 数字错误（D.12，1 处）。

### D.1 ★ M9 `compose()` 的 `outer_zero` 是死开关（4 开关实为 3）

- **文档**：`query_signal.py:146-157` 声称「四个开关正交」→ 暗示 2⁴ = 16 种组合。
- **代码**：`:159-160` 的 `if n_seed <= 0: return 0.0` 提前返回，
  使末尾 `return geo if not outer_zero or n_seed > 0 else 0.0` 在
  `outer_zero` 唯一可能起作用的场景下**永不被求值**。
- **实测**：`n_seed=0` 时两个取值都返回 0.0；`n_seed=2` 时 16 种组合只产生 **8 种**
  不同结果。
- **影响**：`exp_g3_1_baseline.py` 的「2⁴ 全因子对照」实为 8 个有效格点 + 8 个重复。
  结论（极差 0.126）不受影响，但「16 种组合」的表述应改为「8 种」。
- **验证命令**：
  ```bash
  $PY -c "
  import itertools
  from metaphor_graph.query_signal import compose
  v=set()
  for f,n,u,o in itertools.product([True,False],repeat=4):
      v.add(round(compose({'a':1.,'b':0.,'c':1.},n_seed=2,completeness=.8,floor=f,normalize=n,use_completeness=u,outer_zero=o),12))
  print(len(v))   # 输出 8，不是 16
  "
  ```

### D.2 ★ M29 `health.graph_health` 的 `registered_*` 两次赋值冲突

- **文档**：`health.py:52-55` 说明「registered_hierarchy_coverage = min(frame_cov, cascade_cov)」。
- **代码**：`:184` 用**第一段**（`get_frame` 非空且 `frame_id` 非空）算 hc；
  `:210/:218` 用**第二段**（`frame_reliability`，把 `frame_id=None` 当已登记；
  `e.cascade_id or get_cascade`）**覆写** fc/cc，但**不重算 hc**。
- **实测**：构造 2 条边（1 条挂登记框架、1 条无 `frame_id`）→
  `fc=1.0, cc=1.0, hc=0.5`，`min(fc,cc) ≠ hc`；`n_fallback_edges=1` 与 `fc=1.0` 矛盾。
  另一反例（`e.cascade_id="C_ADHOC_x"`）→ `min(fc,cc)=0.0 ≠ hc=1.0`。
- **影响**：当前真实语料（builder 保证每条边都有 `frame_id`）**不触发**，
  但任何手工构造的边 / L3 消融都会触发。修复方向：删除第一段或让第二段复用第一段的
  严格判据并重算 hc。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.models import MetaphorSHG, MetaphorHyperedge, MetaphorFrame
  from metaphor_graph.health import graph_health
  from metaphor_graph.ontology import DEFAULT_ONTOLOGY as O
  fid=next(iter(O.frames)); cas=O.get_cascade(fid)
  edges=[MetaphorHyperedge(id='e1',source_domain='a',target_domain='b',ground=['g'],triggers=['t'],frame_id=fid,cascade_id=cas),
         MetaphorHyperedge(id='e2',source_domain='c',target_domain='d',ground=['g'],triggers=['t'],frame_id=None,cascade_id=cas)]
  h=graph_health(MetaphorSHG(edges=edges,frames=[MetaphorFrame(id=fid,name='x')]),ontology=O)
  print(h.registered_frame_coverage, h.registered_cascade_coverage, h.registered_hierarchy_coverage)
  "   # 输出 1.0 1.0 0.5  -> min(1,1) != 0.5
  ```

### D.3 ★ M8 `_s_query` docstring 的 json AUC 数字错误

- **文档**：`query_signal.py:262` 声称「去掉截断后 ... AUC 0.654 → 0.824（`source`）/
  **0.593 → 0.609（`json`）**」。
- **代码**：`_s_query` 本身与 docstring 一致（无 `min`）。
- **实测**（`experiments/gen3/dataset_json.json` 复算，`n_seed≥1` 子集 n=114）：
  ```
  json:  omega AUC = 0.5933   S_query AUC = 0.5926   ← 下降 0.0007，不是升到 0.609
  ```
  `gen3/REPORT.md:873` 自己报的是 `0.5933 → 0.5926`（与复算一致）。
  → docstring 的 `0.609` 是**错误的**（可能来自另一个口径或笔误）。
- **影响**：文档层面高估了 `S_query` 在生产规则（`json`）上的收益。实际是：
  去掉截断在 `json` 上**无增益**（因为 `json` 规则下 `n_emergent` 本来就只有 3 档，
  截断只影响 9/114 条）。这与「截断是元凶」的结论**并不矛盾**——它恰恰说明
  截断的伤害程度取决于基底（`source` 规则下才严重）。
- **验证命令**：
  ```bash
  $PY -c "
  import json, numpy as np
  rows=json.load(open('experiments/gen3/dataset_json.json',encoding='utf-8'))['rows']
  sub=[r for r in rows if r['n_seed']>=1]; y=[r['cascade_nonempty'] for r in sub]
  def auc(s,y):
      s=np.asarray(s,float); y=np.asarray(y,int); P=int(y.sum()); N=len(y)-P
      o=np.argsort(s,kind='mergesort'); r=np.empty(len(s),float); sx=s[o]; i=0
      while i<len(sx):
          j=i
          while j+1<len(sx) and sx[j+1]==sx[i]: j+=1
          r[o[i:j+1]]=(i+j)/2.+1.; i=j+1
      return (r[y==1].sum()-P*(P+1)/2.)/(P*N)
  sq=[np.exp(sum(np.log(max(v,1e-3)) for v in (min(1.,r['n_frames']/r['n_seed']), r['n_emergent']/r['n_seed'], r['omega_f']))/3)*r['comp'] for r in sub]
  print(auc([r['omega'] for r in sub],y), auc(sq,y))
  "   # 输出 0.5933... 0.5926...
  ```

### D.4 ★ M26 `ground_jaccard` 两条路径定义不同（真 Jaccard vs 包含率）

- **文档**：`FEATURE_NAMES:48` 注释「喻底集合 Jaccard（扩展隐喻合并判据的连续化）」，
  论文 §3.4 只列名字。
- **代码**：
  - `extract_features:177`：`_jaccard(query_edge.ground, cand.ground) = |∩|/|∪|`（**真 Jaccard**）
  - `extract_text_features:144`：
    ```python
    gj = (len({w for w in g if w in query_text}) / max(1, len(g))) if g else 0.0
    ```
    （**包含率**，分母只有 `|g|`）
- **实测**：分歧率 **4.76%（113/2375）**；包含率均值 0.125 vs Jaccard 均值 0.150；
  包含率 ≥ Jaccard 的比例 96.3%。
- **文档是否说明**：**`REPORT_exp-source.md §5.1` 说明并标注「本次未改」**，
  但 **docstring 与论文均未说明**。这是设计内的锚点差异（文本无喻底集合，
  无法算 Jaccard），但两者不是同一函数。
- **影响**：训练期（边锚点）与推理期（文本锚点）对同一候选给出不同特征 →
  **特征漂移**。实测 `ground_jaccard` 单特征 AUC 0.7437（`_LEARNED_SHARE` 0.4965）
  是第三重要的维，漂移不可忽略。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.training import extract_features, extract_text_features, _jaccard
  from metaphor_graph.models import MetaphorHyperedge
  e=MetaphorHyperedge(id='E',source_domain='s',target_domain='t',ground=['a','b','c'],triggers=['x'])
  print(extract_features(e,e,centrality={})[6], extract_text_features('a',e,centrality={})[6])
  "   # 边锚点 1.0（自比） vs 文本锚点 0.3333（只有 'a' 命中）
  ```

### D.5 ★ M31 `multi_clue_retrieval` 的「≥2 个触发词」表述

- **文档**：docstring 与方案 §4.4.2 注释均称「被 ≥2 个触发词支持的映射优先返回」。
- **代码**：`if s >= 2 * threshold`，`s` 是**同一 target_domain 上所有映射的
  confidence 之和**。
- **实测**：单触发词 `['泥潭']` + `confidence=0.9` → 被放行（**1 个触发词**）；
  `['泥潭','泥潭']` → 分数 1.8（重复计数）。
- **影响**：`multi_clue_retrieval` 不参与已上报指标（仅 demo/单测），
  但方案文档的机制描述与实现语义不符，应改为「同一目标域的置信度之和 ≥ 2·threshold」。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.retrieval import RetrievalEngine
  from metaphor_graph.models import MetaphorSHG, MetaphorHyperedge
  e=MetaphorHyperedge(id='m',source_domain='s',target_domain='T',ground=['g'],triggers=['泥潭'],confidence=0.9)
  print(RetrievalEngine(MetaphorSHG(edges=[e]),['c']).multi_clue_retrieval(['泥潭']))
  "   # 输出 [('T', 0.9)] —— 只有 1 个触发词却通过
  ```

### D.6 ☆ M18 `_conv` 与 `propagation_matrix` 在空 `he_members` 时不等价

- **文档**：`propagation_matrix` docstring:155「与 `_conv` 的循环实现**逐元素等价**」。
- **代码**：`_conv:130-131` 有 `if not self.he_members: return X` 的提前返回；
  `propagation_matrix` 无此特判 → 返回 `0.5·I`。
- **实测**：`cross_layer=False` + 无 L1 边的图（V=2）→ `max|_conv(X) − M@X| = 0.288675`。
- **影响**：正常图（有超边）上逐元素等价（实测 5.6e-17）；只在退化图上分歧。
  该退化图在 L3 消融（`orphan_cascade_rule="none"`）与空语料下可达。
- **验证命令**：
  ```bash
  $PY -c "
  import numpy as np
  from metaphor_graph.hgnn import MetaphorHGNN
  from metaphor_graph.models import MetaphorSHG, MetaphorFrame, MetaphorCascade
  shg=MetaphorSHG(edges=[],frames=[MetaphorFrame(id='F1',name='x')],cascades=[MetaphorCascade(id='C1',name='y',member_frame_ids=['F1'])])
  g=MetaphorHGNN(shg,layers=2,cross_layer=False)
  print(np.max(np.abs(g._conv(g.X)-g.propagation_matrix()@g.X)))
  "   # 输出 0.2886751...，不是 0
  ```

### D.7 ☆ M24 上下文预算的「按合理性分数降序填充」

- **文档**：模块 docstring:7「按合理性分数降序填充」。
- **代码**：`pack()` **不排序**，按传入顺序尝试；大项放不下时**跳过**（不是 break）。
- **实测**：`[50字, 4字]` vs `[4字, 50字]` 给出不同结果（预算 50）；
  `[60字, 10字]` 预算 50 → 选中 `[10字]`。
- **影响**：排序责任在调用方（`pack_context` 传入已排序的 `rank_mappings` 输出），
  当前调用路径正确。但 docstring 应说明「调用方负责排序」与「跳过而非截断」。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.context_budget import ContextBudget
  b=ContextBudget(max_tokens=100,chars_per_token=1.0)
  print([len(t) for t in b.pack(['x'*60,'y'*10],[],[]).hyperedges])   # [10] 跳过 60
  "
  ```

### D.8 ☆ M5 观测完备度未说明「重叠重复计数」

- **文档**：docstring:202「查询中被触发词覆盖的字符占比」。
- **代码**：`covered += len(t) * query.count(t)` → **重叠子串重复计数**，
  再由 `min(covered, len(query))` 截断。
- **实测**：`completeness('aaaa', ['a','aa']) = 1.0`（覆盖 4+8=12 → min 截到 4）。
- **影响**：短查询 + 多重叠触发词时覆盖率虚高；单触发词情形无影响。
  生产本体单触发词最长 5 字、无空串触发词 → 影响有限。
- **验证命令**：
  ```bash
  $PY -c "from metaphor_graph.observability import completeness; print(completeness('aaaa',['a','aa']))"
  ```

### D.9 ☆ M12 `StratifiedNormalizer` 未见层的 μ 取值未说明

- **文档**：docstring:365「未见过的层 → 全局 z」。
- **代码**：`mu = sum(self._mu.values()) / len(self._mu)`（**层均值的算术平均**），
  不是「全局 μ」（全局 μ 需在 `fit` 里另行统计，代码没有）。
- **实测**：`_mu={1:1.1667, 2:1.5}` → 未见层的 μ = 1.3333。
- **影响**：未见层的 z 分数尺度依赖「层数」而非「样本数」，是**未加权**的层平均。
  该分量最终被 gen3 判定为「不优于原始计数」，故影响有限。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.query_signal import StratifiedNormalizer
  sn=StratifiedNormalizer().fit([{'n_seed':1,'n_new_domains':v} for v in [0,1,2]]+[{'n_seed':2,'n_new_domains':v} for v in [0,1,2,3]])
  print(sn._mu, sn.transform_one(99,1.0))
  "
  ```

### D.10 ☆ M23 自适应阈值的 τ 无下限钳制

- **文档**：模块 docstring:15「不够就按 c 降阈值（τ₀=0.5, c=0.1, 最多降 5 次）」
  → 默认参数下 τ 最低 0.0，看起来有界。
- **代码**：无 `max(tau, 0.0)` 钳制 → **自定义 `decay` 时 τ 可为负**。
- **实测**：`tau0=0.5, decay=0.3, max_decays=5` → τ 最终 **−0.1**，全量放行。
- **影响**：默认参数（`decay=0.1`，`τ₀−5×0.1 = 0.0`）恰好触底于 0，不越界。
  但参数可配 → 是潜在退化点。建议加 `tau = max(tau, 0.0)`。
- **验证命令**：
  ```bash
  $PY -c "
  from metaphor_graph.context_budget import AdaptiveThreshold
  print(AdaptiveThreshold(tau0=0.5,decay=0.3,max_decays=5,min_keep=50).select([('a',0.),('b',0.)],density=1.0)[1].threshold)
  "   # 输出 -0.1
  ```

### D.11 ☆ M2 `min(1,·)` 截断在论文/README 中完全缺席

- **文档**：`observability.py` 模块 docstring、`REPORT_exp-cascade.md`、`gen3/REPORT.md`
  都写了 `Ω_N = min(1, n_emergent/n_seed)`。
  但**论文 `论文初稿.md` 与 `metaphor_graph/README.md` 中 Ω 只出现在 §7 的一行负面结果**，
  没有任何分量定义 → 对只读论文的读者，`min(1,·)` 是**未披露的实现细节**。
- **代码**：`:246`。
- **影响**：论文的「只读查询的标量退化为 1-bit 指示器」这一结论**缺少机制说明**。
  `experiments/论文修正建议.md:327-334` 已给出建议表述，但**尚未写入论文初稿**。
- **验证命令**：
  ```bash
  grep -n "Ω" 论文初稿.md   # 只有 1 行（§7 表格）
  grep -n "min(1" metaphor_graph/observability.py   # :246 有
  ```

### D.12 ⚠️ M10 `_s_log` docstring 称「等价于几何平均」不准确

- **文档**：`query_signal.py:223-224`
  > 等价于 (1+n_f)(1+n_c)(1+n_new) 的几何平均 —— 即「保留几何平均、
  > 去掉 ε 下界与归一化」这一支。
- **代码**：`return math.log1p(n_frames) + math.log1p(n_cascades) + math.log1p(n_new_domains)`
  = `log(∏(1+nᵢ))`。
- **实测**：
  ```
  S_log(3,2,5) = 4.276666
  3·log(几何平均) = 4.276666   ← 相等
  log(几何平均)   = 1.425555   ← 不相等
  ```
  正确表述是「**乘积的对数**」或「几何平均的对数的 **3 倍**」。
- **影响**：仅表述问题（该量本身是「无下界、无除法的计数和」，语义清晰）。
  但若有人按 docstring 理解为「几何平均」并在同一尺度上与 Ω 比较，会得出错误结论
  （`S_log` 的量级是 `log` 尺度，`Ω` 是 `[0,1]` 线性尺度）。
- **验证命令**：
  ```bash
  $PY -c "
  import math
  from metaphor_graph.query_signal import _s_log
  print(_s_log(3,2,5), 3*math.log(((1+3)*(1+2)*(1+5))**(1/3)))
  "   # 4.276666 4.276666
  ```

---

## E. 退化条件汇总

> 按「退化类型」分组。**这是本文件最有价值的部分**：项目的核心发现几乎全部是
> 「某个形式化在什么条件下塌掉」。

### E.1 分量饱和 / 截断型（信息被压成常数）

| 对象 | 退化式 | 触发条件 | 实测证据 |
|---|---|---|---|
| **Ω_N** | `min(1, n_em/n_seed) ≡ 1` | `n_emergent ≥ n_seed` | `source` n_seed=1 层：23 档 → 2 档，82/102 饱和；`source_type` 114/114 饱和 |
| Ω_E | `min(1, n_frames/n_seed) ≡ 1` | `n_seed = 1`（且 `n_frames ≥ 1`，恒真） | gen3 §2.4：该层 102 条全部 Ω_E=1.0，`ρ(Ω,Ω_E)=nan` |
| `struct` 维 | `min(1, 0.5|g|+0.5) ≡ 1` | `|ground| ≥ 1` 且 `cascade_id` 非空 | `REPORT_exp-source.md:186`：85.1% 候选对恰为 1.0 |
| `type` 维 | 恒为常数 | 无 ontology 或所有候选同状态 | §6.2 原表：`type` 取值 `{1.0: 7437}` 全为 1.0 |
| 几何平均 ε 下界 | `v ≤ ε` 压成一点 | 任一分量 ≤ 1e-3 | 实测 `g(0)=g(1e-4)=0.1`（保序性在这些点丢失） |
| `clue` 维 | `min(1, 0.5·hits) ≡ 1` | 触发词重合 ≥ 2 | 单特征 AUC≈1.0（自监督 chunk 模式） |

### E.2 结构性恒空型（基底不支持该量）

| 对象 | 退化 | 触发条件 | 实测证据 |
|---|---|---|---|
| **Ω_N** | `emergent ≡ ∅` | 级联成员共享单一目标域 | 生产本体 **752/758 = 99.2%** 级联如此；单框架出发 **2196/2209 = 99.4%** |
| `registered_*` | 无法区分 | 所有边都挂登记框架 | 真实语料 `fc=cc=1.0`（无区分度） |
| `evidence_coverage` | 恒 0 | 无人写入 Evidence | 实测 `evidence_coverage = 0.0` → 触发告警 |
| `deprecated_rate` | 恒 0 | 无人标记软删除 | 实测 `deprecated_rate = 0.0` |
| `avg_provenance_reliability` | 恒 1.0 | 所有框架都已登记 | 实测 `= 1.0`（`degraded_edge_rate = 0.0`） |
| `same_frame`/`same_cascade` | 恒 0 | `ontology=None` | 代码 `if ontology is not None` 守卫 |

### E.3 算子收敛型（迭代抹掉信息）

| 对象 | 退化 | 触发条件 | 实测证据 |
|---|---|---|---|
| **`metaphor_coherence`** | 同分量余弦 → 1（身份被抹） | `α=1` 且 `layers → ∞` | `doc_project`：L=2 → 0.383；L=50 → 0.964；L=500 → **1.000000** |
| `forward`（`ε>0`, `α=1`） | 所有向量 → 0 | `ρ(M)=1−ε/2 < 1` 且无源项 | docstring 明确「ε 只在配合源项时才有意义」 |
| `u*` 不存在 | `I − αM` 奇异 | `α·ρ(M) = 1`（如 `α=1, ε=0`） | 实测 `cond=4.2e16`，零空间维数 = 5 = 分量数 |
| **同分量指示器** | AUC ≡ 0.5 | 在「同分量负样本」子集上 | `auc_h4.py` 设计此对照；实测 16/20 = 0.8000 是该子集的准确率上限 |

### E.4 1-bit 塌缩型（连续量退化为指示器）

| 对象 | 退化 | 触发条件 | 实测证据 |
|---|---|---|---|
| **Ω** | `Ω>0 ⟺ n_seed≥1` | 无激活特判 + 分量全由计数驱动 | 逐条一致率 **632/632 = 1.0000**；`ρ(Ω,n_seed)=0.9949` |
| Ω 门控 | 弱于 `if not agg` | 有触发词但域不覆盖任何 live 超边 | 一致率 0.8956；Ω 漏 66 条（通道 2） |
| `Ω_N` | 2 档（0 与 1） | 见 E.1 | 见 E.1 |
| `regime` dense 档 | 近空档 | `Ω ≥ 0.5` 且 `comp ≪ 1` | 改写型 dense=1/632；CCL2018 dense=0/1100 |
| `n_seed` | 4 档（0/1/2/3） | 触发词命中数的自然取值数 | exp5 §C：`Counter({1:102, 2:11, 3:1})` |

### E.5 口径冲突型（同一对象两套定义）

| 对象 | 冲突 | 实测分歧 |
|---|---|---|
| `registered_frame_coverage` | `get_frame is not None`（严格）vs `frame_reliability >= 1`（宽，把 `None` 当已登记） | 构造反例：1.0 vs 0.5 |
| `registered_cascade_coverage` | `get_cascade(frame_id)` vs `e.cascade_id or get_cascade` | 构造反例：1.0 vs 0.0 |
| `ground_jaccard` | 真 Jaccard（边锚点）vs 包含率（文本锚点） | 4.76%（113/2375） |
| `sem` | `max(0, cos)`（训练）vs `cos`（人工加权，无 clamp） | 当前语料无负 cos，换真实向量后分歧 |
| `type` | 曾有两套（已修，现统一 `type_reliability_of`） | 修复前 22.0% |
| `n_emergent` vs `n_new_domains` | 目标域口径 vs 「目标域 ∪ 源域」口径 | 定义不同，数值不可比 |
| `Ω_N` vs `emergence_ratio` | `min(1, n_em/n_seed)` vs `n_em/(n_direct+n_em)` | 实测 `'泥潭'`：1.0 vs 0.6667 |

### E.6 空/边界型

| 对象 | 退化 | 实测 |
|---|---|---|
| `_conv` vs `propagation_matrix` | `he_members=[]` 时不等价 | `max diff = 0.288675` |
| `graph_density` | `n_nodes ≤ 0` → 0.0 | 空图 → Δ=0 → `regime='low'` |
| `AdaptiveThreshold` | `τ < 0` → 全量放行 | `decay=0.3` → τ=−0.1 |
| `compose` | `n_seed ≤ 0` → 恒 0 | 8 种有效组合 |
| `S_query` | `n_seed ≤ 0 or n_frames ≤ 0` → 0 | 与 Ω 同一特判 |
| `_jaccard` | 空集对 → 0.0（**不是 1.0**） | `_jaccard([],[]) = 0.0` |
| `reliability_factor` | `floor=1.0` → 常值 1 | 通道关闭 |
| `frame_reliability` | `ontology=None` 或 `frame_id` 假值 → 1.0 | 不降级 |
| `ContextBudget.pack` | 单项超预算 → 丢弃（跳过，不 break） | 预算 100、单项 200 → `[]` |
| `encode()` 未知词 | 静默回退到最近实体的 H | 语义替换 |
| `Multi_clue` | 单高置信触发词即可通过 | `conf=0.9 ≥ 2×0.3` |

---

## F. 验证命令

> 解释器：`C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe`
> 以下 `$PY` 均指该路径。全部命令在项目根目录执行。

### F.1 一键复核（本文件所有实测数字）

```bash
cd "E:/02_AI项目/元图隐喻分析"
$PY - <<'PY'
import sys, math, itertools, json
import numpy as np
sys.path.insert(0, '.')
from metaphor_graph import observability as O, query_signal as Q, provenance as P
from metaphor_graph import hgnn as H, training as T
from metaphor_graph.retrieval import _rrf, shg_density
from metaphor_graph.context_budget import graph_density, AdaptiveThreshold, ContextBudget
from metaphor_graph.evaluate_hgnn import _auc_full
from metaphor_graph.evaluate_fullcorpus import build_replay_ontology

print("--- M2 Ω_N 截断饱和 ---")
for n_em, n_seed in [(23,1),(5,1),(1,1),(0,1),(3,2)]:
    print(f"  n_em={n_em} n_seed={n_seed}: raw={n_em/n_seed:.2f} clipped={min(1.0,n_em/n_seed)}")

print("--- M2 Ω_N 结构性恒空（生产本体）---")
ont, _ = build_replay_ontology()
uni = sum(1 for c in ont.cascades.values()
          if len({ont.get_frame(f).target_domain for f in c.member_frames
                  if ont.get_frame(f)}) < 2)
print(f"  闭包不带来新目标域的级联 = {uni}/{len(ont.cascades)} = {uni/len(ont.cascades)*100:.1f}%")

print("--- M4 ε 下界破坏严格单调 ---")
print("  g(0)=", O.geometric_mean((1.,0.,1.)), " g(1e-4)=", O.geometric_mean((1.,1e-4,1.)))

print("--- M9 compose outer_zero 死开关 ---")
v = {round(Q.compose({'a':1.,'b':0.,'c':1.}, n_seed=2, completeness=.8, floor=f,
                     normalize=n, use_completeness=u, outer_zero=o), 12)
     for f,n,u,o in itertools.product([True,False],repeat=4)}
print(f"  16 组合产生 {len(v)} 种不同结果（应为 16）")

print("--- M17/M18 谱性质 ---")
from metaphor_graph.builder import MetaphorSHGBuilder
from metaphor_graph.eval_corpus import DOCS
shg = MetaphorSHGBuilder().build(DOCS[list(DOCS)[0]], doc_id='d')
g = H.MetaphorHGNN(shg, layers=1); M = g.propagation_matrix()
S = 2*M - np.eye(g.num_nodes)
print("  S 行和(live) min/max =", S.sum(axis=1).min(), S.sum(axis=1).max())
print("  ρ(S)=", np.max(np.abs(np.linalg.eigvals(S))), " ρ(M)=", np.max(np.abs(np.linalg.eigvals(M))))
for eps in (0.1, 0.5):
    Me = H.MetaphorHGNN(shg, layers=1, leak=eps).propagation_matrix()
    print(f"  ε={eps}: ρ(M)={np.max(np.abs(np.linalg.eigvals(Me))):.10f}  1−ε/2={1-eps/2:.10f}")
print("  _conv ≡ M·X ?", float(np.max(np.abs(g._conv(g.X) - M@g.X))) < 1e-12)

print("--- M20 α=1 无不动点 ---")
print("  cond(I−M) =", np.linalg.cond(np.eye(g.num_nodes) - M))

print("--- M25 RRF ---")
print("  _rrf(['x']) =", _rrf(['x']), " 1/61 =", 1/61)

print("--- M27 HAND_WEIGHTS ---")
print(" ", {k: round(v,6) for k,v in T.HAND_WEIGHTS.items()})

print("--- M28 AUC 三实现一致 ---")
pos = np.array([0.,1.,2.,3.,4.]); neg = np.array([0.,0.,1.,1.,2.])
print("  _auc_full =", _auc_full(pos, neg)[0])
print("  暴力 gt+0.5eq =", (pos[:,None]>neg[None,:]).mean() + 0.5*(pos[:,None]==neg[None,:]).mean())
PY
```

### F.2 逐对象验证（M 编号 → 命令）

| 对象 | 命令 |
|---|---|
| M1/M2/M6 | `$PY -c "from metaphor_graph.observability import measure; [print(q, measure(q).summary()) for q in ['泥潭','推进，停滞，迈步，抵达','今天天气不错']]"` |
| M2 截断 | `$PY -c "import json; r=json.load(open('experiments/gen3/dataset_source.json',encoding='utf-8'))['rows']; s=[x for x in r if x['n_seed']==1]; print(len({x['n_emergent'] for x in s}), len({x['omega_n'] for x in s}))"` → `23 2` |
| M3 | `$PY -c "from metaphor_graph.observability import normalized_entropy as e; print([e(w) for w in [(),(3.,),(1.,1.),(1.,3.)]])"` → `[0.0, 0.5, 1.0, 0.8113]` |
| M5 | `$PY -c "from metaphor_graph.observability import completeness; print(completeness('aaaa',['a','aa']))"` |
| M8 | `$PY -c "from metaphor_graph.query_signal import measure_signal; print(measure_signal('泥潭').get('S_query'))"` → `1.0` |
| M9 | 见 F.1 的 compose 段 |
| M12 | `$PY -c "from metaphor_graph.query_signal import StratifiedNormalizer as S; n=S().fit([{'n_seed':1,'n_new_domains':v} for v in [0,1,2]]); print(n._mu, n.transform_one(1,2.0))"` |
| M14–M16 | `$PY -c "from metaphor_graph.provenance import *; print([reliability_factor(r) for r in [0,.25,.5,.75,1]])"` |
| M17–M21 | 见 F.1 的谱性质段；`$PY experiments/convergence_check.py`（完整版） |
| M21 坍缩 | `$PY experiments/auc_h4.py`（写 `auc_h4.csv/json`） |
| M22/M23 | `$PY -c "from metaphor_graph.context_budget import graph_density, AdaptiveThreshold; print(graph_density(10,4)); print(AdaptiveThreshold().regime(2.35), AdaptiveThreshold().regime(5.0), AdaptiveThreshold().regime(9.0))"` |
| M24 | `$PY -c "from metaphor_graph.context_budget import ContextBudget; print([len(t) for t in ContextBudget(max_tokens=100,chars_per_token=1.0).pack(['x'*60,'y'*10],[],[]).hyperedges])"` → `[10]` |
| M25 | `$PY -c "from metaphor_graph.retrieval import _rrf; print(_rrf(['a','b','c']))"` |
| M26 | `$PY -c "from metaphor_graph.training import extract_features, extract_text_features, FEATURE_NAMES; print(FEATURE_NAMES)"` |
| M27 | `$PY -c "from metaphor_graph.training import HAND_WEIGHTS, HAND_WEIGHTS_LEGACY; print(HAND_WEIGHTS, HAND_WEIGHTS_LEGACY)"` |
| M28 | `$PY experiments/auc_h4.py` |
| M29/M30 | 见 D.2 的构造反例命令；`$PY -m metaphor_graph.health`（若可运行） |
| M31 | 见 D.5 的命令 |
| 全量单测 | `$PY -m unittest metaphor_graph.test_metaphor_graph`（137 tests） |

### F.3 论文/报告中的文档公式来源

| 文档 | 覆盖的数学对象 |
|---|---|
| `论文初稿.md §3.4/§3.5` | 7 维特征（**仅列名**）、HGNN 两步传播 + 残差（**无公式**） |
| `论文初稿.md §6.2/§6.3` | AUC 口径（P(pos>neg)+0.5P(pos=neg)）、权重过权倍数 |
| `论文初稿.md §7` | Ω（**仅一行负面结果，无定义**）、溯源可靠性（**仅一行**）、源项（**仅一行**） |
| `论文初稿.md §5.2` | 诚实覆盖率（**仅结论数字，无公式**） |
| `论文初稿.md §6.5` | 50/30/20 预算（**仅一句**） |
| `metaphor_graph/observability.py` docstring | Ω 三分量 + 几何平均 + ε 下界 + 完备度 + regime（**最完整的文档**） |
| `metaphor_graph/hgnn.py` docstring | M = ½(I+S)、源项、leak、谱半径条件（**完整**） |
| `metaphor_graph/context_budget.py` docstring | Δ、τ₀/c/max_decays、50/30/20（**完整**） |
| `experiments/REPORT_exp-cascade.md §1` | Ω 三分量 + 几何平均 + ε 下界（**逐字公式**） |
| `experiments/REPORT_exp-dynamics.md §2` | S 行随机、ρ=1、坍缩表（**逐字数字**） |
| `experiments/gen3/REPORT.md §2.2/§4.1` | Ω_N 截断的因子分解、S_query 定义（**逐字公式**） |
| `experiments/对照分析_RiverMemo.md §6` | M = ½(I+S) 的无源项退化（**逐字谱数字**） |

---

## G. 元观察：本项目数学形式化的三种失败模式

> 32 个对象的核对结果指向三条**可复用的教训**，它们比单个公式更值得记录。

### G.1 「与门」式合成会吃掉序信息（Ω、`min`、几何平均）

Ω 的三个分量各自 `clip [0,1]`、几何平均、再乘完备度——**四层「与」式结构**。
每一层都保证「值域 [0,1]」这个好看的性质，代价是**任何一层饱和都会让整个泛函
退化为指示器**。实测：`Ω>0 ⟺ n_seed≥1` 逐条一致率 632/632。

**一般形式**：若 `F = ∏ fᵢ(xᵢ)^{1/n}` 且存在 `i` 使 `fᵢ` 在子域上为常数，
则 `F` 在该子域上的**变异只来自其余分量**；若其余分量也被同一驱动量决定
（这里都是 `n_seed`），`F` 就退化为 `n_seed` 的函数。

**修法**（gen3 的结论）：不是换合成算子（16 种组合极差仅 0.126），
而是**让分量在基底上真的有变异**（去掉 `min(1,·)` 后 AUC 0.654 → 0.824）。
但即便如此，只要**预测目标本身是定理**（`cascade_nonempty ⟺ 集合相交`），
提升就是空洞的。**先问目标是不是同义反复，再问公式好不好。**

### G.2 无源项扩散必然收敛到分量共识（HGNN）

`S = D_v^{-1} H D_e^{-1} H^T` 行随机 + `ρ(S)=1` ⟹ `M^k X0` 收敛到分量平稳分布
⟹ 同分量节点向量趋同 ⟹ 余弦退化为「是否同分量」。
这是 **Perron–Frobenius 的直接推论**，不是实现 bug。

**修法**：加源项 `X ← (1−α)X0 + αMX`，不动点 `u* = (1−α)(I−αM)^{-1}X0`
保留源身份（实测 α=0.5 时同分量余弦 0.116 vs α=1 的 1.000）。

**但本项目的重要教训是**：这个理论退化**在实际工作点（layers=2）并未发生**
（同分量余弦仅 0.383）。「H4 的 0.950 是算子退化造成的」这一说法被
**REFUTED**（完美同分量指示器的准确率上限 0.800 < 0.950）。
**渐近命题不能直接用来解释有限步行为**——这是本次核对中最容易犯的推理错误。

### G.3 「不丢弃」约束下，唯一可用的手段是「有下界的乘性折扣」

`reliability_factor(r) = floor + (1−floor)·r ∈ [floor, 1]` 是这一约束下
**唯一**能同时满足三条要求的映射：
1. 改变排序（加性 bonus 不改变次序）；
2. 不丢候选（硬过滤会召回归零）；
3. 有下界（纯乘性 `r` 在 `r=0` 时归零）。

**代价**：因为它只作用于**排序层**，任何**存在性布尔指标**（如 P1）对它
**结构性无感**（实测 P1 效应恒 0，7/7 条误判句全部由正式框架支撑）。
「数学上界就是 0，不是调参问题」——这一条比任何数字都重要。

---

*文件结束。全部实测数字可由 §F 的命令复现；代码为只读，未做任何修改。*
