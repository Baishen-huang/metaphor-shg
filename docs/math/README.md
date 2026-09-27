# 数学探索总索引

> 目标：对**元图 / 图 / 谱 / 贝叶斯 / 拓扑**相关内容做数学探索与优化，
> 并将**拓扑作为损失函数**试验；同时推进 **Lean 形式证明**。
> 方法：5 个并行方向（4 个数学 + 1 个形式化），全部离线、$0。

---

## 0. 总览

| 方向 | 报告 | 核心裁决 | 是否带来增益 |
|---|---|---|---|
| **谱理论** | [spectral.md](spectral.md) | 27 图验证 7 组命题；`layers=2` 余弦可**闭式预测**（偏差 5.6e-16） | ✅ **是**（把数值观察升级为定理） |
| **贝叶斯** | [bayes.md](bayes.md) | 3 个模型：2 个负面、1 个正面；**附带发现全局状态污染** | ⚠️ 部分（正面在"扣偏差"而非"排序变好"） |
| **拓扑** | [topology.md](topology.md) | 图拓扑非平凡（β₁=837）但拓扑对链质量**零判别力**（AUC 0.5000） | ❌ 否（干净的负面结果） |
| **拓扑损失** | [topological_loss.md](topological_loss.md) | 64 配置扫描：**有效但效应小**（deanchor +0.0097）；优于度匹配随机图 2.8× | ⚠️ **弱正面**（零梯度问题只存在于路 A） |
| **Lean 形式化** | [lean_formalization.md](lean_formalization.md) | **整个项目 `lake build` 成功**：Core 9 定理全验证；Basic 纯定义 0 sorry；Spectral 27 定理/定义含 19 sorry | ✅ 是（真实验证 + 明确标注未证部分） |

---

## 1. 最有价值的三个成果

### 1.1 `layers=2` 余弦的闭式预测（spectral）

项目此前只能**测**"layers=2 时同分量余弦 = 0.383"，现在可以**算**：

```
实测  0.38300320937497484
预测  0.383003209374975        偏差 5.6e-16
```

**意义**：这**独立裁决**了 H4 的争议——若"0.950 是算子退化造成的"，
则 layers=2 时应已接近退化（余弦 → 1）；但预测与实测都给 0.383。
且 `μ₂(M) = 0.9827` 衰减极慢（需 k≈500 才达 0.99999）。
→ **"退化"在 layers=2 处不成立。**

### 1.2 Lean 真实验证（lean_formalization）

**整个 Lean 项目 `lake build` 成功（exit 0）**，Mathlib 源码编译已完成
（5843 文件，约 1.5 小时）：

| 文件 | 编译 | `sorry` | 说明 |
|---|---|---|---|
| `Core.lean` | ✅ | **0** | **9 定理全部机器验证** |
| `Basic.lean` | ✅ | **0** | 纯定义（14 def），无定理待证 |
| `Spectral.lean` | ✅ | **19** | 27 定理/定义；19 条已定类型未证明 |

**「编译通过」≠「全部验证」**：前者指陈述类型正确、已写证明被内核接受；
19 个 `sorry` 是未证明的陈述。

**修复了 4 类真实错误**（原文件从未编译过，故此前不可见）：
① `Mathlib.LinearAlgebra.Matrix.Notation` 模块不存在（正确为 `Data.Matrix.Notation`）；
② `λ` 不能作 Lean 4 绑定变量名（6 处改 `mu`）；
③ `G.IsEigenvalue` 应为 `Hypergraph.IsEigenvalue`（8 处，它们是普通函数非方法）；
④ `List.sum` 不存在，改用 `List.foldl`。

**诚实限定**：`Core.lean` 验证的是**代数骨架**（交换律、分配律、零保护），
**不是谱定理本身** —— 谱定理在 `Spectral.lean`，含 19 个 `sorry`。

### 1.3 全局状态污染（bayes 附带发现）

`build_llm_ontology()` 就地扩充模块级 `TYPE_CONSTRAINTS`（实测 +1070 条），
使**同一份代码的结果依赖调用顺序**（同脚本 MRR@10 差 2.5pp）。

主控已复核并修复：加计数 + 快照 + reset 接口，`evaluate_repaired` 建图前取快照、
跑完恢复。**保证评测可重复。**

---

## 2. 四类数学结果

### 2.1 谱（7 组命题，27 图全部验证）

| 命题 | 验证结果 |
|---|---|
| T1 行和为 1（活节点） | 偏差 ≤ 2.2e-16；孤立节点恰为 0 |
| T2 特征值全实 | 相似变换偏差 ≤ 3.3e-16；最大虚部 ≤ 4.8e-16 |
| T3 ρ(S)=1 且 dim ker(S)=V−rank(H) | **27/27 逐图精确相等** |
| T4 ρ(M_ε)=1−ε/2 且 mult(λ=1)=分量数 | ε 三档全中，分量数逐图匹配 |
| T5 收敛速率 e_k=(αM)^k(X₀−u*) | 42 个组合 maxdiff 5.8e-16 |
| T6 layers=2 余弦闭式预测 | 预测 = 实测 |
| T7 重复成员致两实现分歧 | 真实图 173/2257 条边触发（7.7%） |

**附带**：`ker(S)` 维数很大（ccl1100 上 929/2825 ≈ 33%），这些方向在传播中
被完全湮灭 —— 这是"无源项塌缩"的代数根源。
`cond(I−M)` 在 ε=0 时达 3.9e17（数值不可逆），给出 ε-阻尼的工程理由。

### 2.2 贝叶斯（3 模型）

| # | 问题 | 裁决 | 关键数字 |
|---|---|---|---|
| A | 溯源可靠性手拍 0.5 封顶 | ❌ 贝叶斯化无增益，但**手拍值有害** | 后验均值 ΔMRR +0.002（CI 跨 0）；手拍封顶 **−0.0190**（CI 全负） |
| B | `clue` 泄漏 | ⚠️ 部分正面：去偏对**总体比例**有效（RMSE 降 6×），对**排序**无效 | RMSE 0.3008 → 0.0504；AUC(clue;R) = 0.5061 |
| C | LLM 金标误差率未知 | ✅ 正面：给出可信区间，暴露现报数字**系统性偏低** | MRR@10 0.5487 → **0.5581 [0.5481, 0.5717]** |

**最重要的结论**：本项目需要的不是"更复杂的先验"，而是**承认哪些量没有证据**
（A：封顶的 0.5 就是没有证据，正确动作是**取消它**而非精修）；
以及**把已知的偏差方向扣掉**（B/C：去偏与积分）。

### 2.3 拓扑

- **图非平凡**：B(H) 关联复形 β₁ = **837**；Dowker β₁ = 17、β₂ = 905
- **H₀ 解释力弱**：H0 指示器 AUC **0.796** vs n 元共现 **0.949**
  → 从拓扑侧独立确认"信号载体是 n 元性"
  → 0.796 与 dynamics 独立测得的"上限 0.800"**高度一致**
- **持续同调零判别力**：预测 LLM 校验器保留的 AUC = **0.5000**
- **Euler 特征**：有信息但不替代现有标量（与 β₀ 强相关）

### 2.4 拓扑损失（弱正面 + 一次自我更正）

> **⚠️ 此项初版结论写"结构性无效"，基于不完整数据（仅 2 条 sanity 记录）。
> 完整 64 配置扫描后更正为"有效但效应小"。**

| arm（最优 λ） | Δanchored | Δdeanchor |
|---|---|---|
| `pers_w1`（持续性 W1） | +0.0032 | **+0.0097** |
| `pers_tp` | +0.0032 | +0.0066 |
| `cut` / `spec_S` | +0.0032 | +0.0002 / −0.0025 |
| **`ctrl_randgraph`（度匹配随机图）** | +0.0000 | +0.0035 |
| **`ctrl_randgrad`（等范数随机梯度）** | **+0.0000** | **+0.0000** |
| `ctrl_lap`（普通 Laplacian） | +0.0000 | −0.0025 |

**三条对照全部通过**：
- 等范数随机梯度 **恰为 0** ⟹ 不是任意扰动
- 普通 Laplacian **有害**（−0.0025）⟹ 不是平滑性
- 度匹配随机图只有 **+0.0035**，拓扑损失是其 **2.8 倍** ⟹ 拓扑内容有贡献

**λ-响应形状不同**（最强证据）：`pers_w1` 随 λ **单调上升**（0.3263→0.3359），
而随机图对照在 λ=3 时**回落**（0.3298→0.3204）。

**零梯度问题确实存在，但只限于路 A**（拓扑建在固定图上）；
路 B（拓扑建在权重加权的特征空间）梯度非零（实测 5.89）且有效。

**限定**：+0.0097 效应量小、单 seed、未做配对显著性检验。
且项目已测出**权重重标定**带来 +0.1553（anchored），**远大于拓扑损失**——
故拓扑损失不应替代重标定。

---

## 3. 环境：Lean 可用性（我先前的判断是错的）

我最初记录"Lean 无法安装"，**该结论错误**：

| 路径 | 结果 |
|---|---|
| `ghproxy.net` 代理 | ✅ 可用（~330 KB/s） |
| 系统代理 `127.0.0.1:7890` | ✅ 可用 |
| 直连 github.com | ✅ 后来也可达 |

**已做到**：安装 Lean 4.15.0 → `lake update` 拉取 Mathlib（729 MB）→
`Core.lean` 编译通过。

**已做到（后续补完）**：Mathlib 预编译缓存因 ProofWidgets release 不可达而失败，
但**源码编译成功**（5843 文件，约 1.5 小时）。**整个项目 `lake build` 成功**。

---

## 3b. 相关工作的关键约束（subagent 附带完成）

拓扑方向顺带做了一次**文献侦察**，产出
`output/literature-search/graph-topology-rag-gnn-tda/`（含 idea-grounding）。
两条**约束本项目主张**的发现：

| 发现 | 对本项目的意义 |
|---|---|
| **HPT-TRACE**（OpenReview 在审）已占据「拓扑空间 + 分层划分树 + 证据路径求交」的 reranking 位置 | 本项目的拓扑工作**不应定位为"又一个图 RAG 变体"**；应定位在**诊断/可解释层**——这与本次实测结论一致（拓扑对链质量零判别力，但 β₁/χ 有描述价值） |
| **Michel et al. 2017**（NoDaLiDa）的负结果：PH 文档表示未在传统 NLP 任务上带来增益 | 与本次**独立实测一致**（持续同调预测链质量的 AUC = 0.5000）。文献里已有先例，说明这不是本项目的实现问题 |

**结论**：本次实测的拓扑负面结果**与文献一致**，故它是**领域性结论**而非本项目特例。
拓扑的价值应定位为**诊断层**（图健康、结构刻画），不是**检索层**。

## 4. 交付物

```
docs/math/
  README.md                    本索引
  spectral.md                  谱理论（27 图验证 + 闭式预测）
  bayes.md                     贝叶斯（3 模型 + 全局状态污染发现）
  topology.md                  同调/持续同调/Euler 特征
  topological_loss.md          拓扑损失（结构性否定）
  lean_formalization.md        Lean 形式化状态
  ENV_lean_unavailable.md      （已标注过时）环境排查过程记录

lean/
  MetaphorSHG/Core.lean        ✅ 已验证（9 定理）
  MetaphorSHG/Basic.lean       ⚠️ 草稿（1 sorry，需 Mathlib）
  MetaphorSHG/Spectral.lean    ⚠️ 草稿（21 sorry，需 Mathlib）
  PROOFS.md                    完整中文非形式化证明

experiments/math/              全部脚本与数据（离线、$0）

metaphor_graph/
  llm_ontology.py              + 全局状态可见性设施（计数/快照/reset）
  evaluate_repaired.py         + 建图前后快照/恢复守卫
```

---

## 5. 复现

```bash
PY="C:/Users/huang/.workbuddy/binaries/python/versions/3.13.12/venv_jieba/Scripts/python.exe"

# 谱（27 图 × 40 指标）
$PY experiments/math/t1_spectrum.py
$PY experiments/math/t2_convergence.py      # layers=2 余弦预测

# 贝叶斯
$PY experiments/math/bayes_a_reliability.py
$PY experiments/math/bayes_c_gold_error.py

# 拓扑
$PY experiments/math/topo_A_connectivity.py
$PY experiments/math/topo_B_chains.py

# Lean（需 ~/.elan/bin 在 PATH）
export PATH="$HOME/.elan/bin:$PATH"
cd lean && lean MetaphorSHG/Core.lean      # exit=0 即通过

# 单测
$PY -m unittest metaphor_graph.test_metaphor_graph    # 257 项
```
