# Lean 形式化草稿：隐喻超图的谱性质

本目录是**隐喻超图（MetaphorSHG）谱性质**的 Lean 4 形式化草稿。

> ## ✅ 状态更新（2026-09-27，主控补完）
>
> **本目录的 Lean 代码现在已被 Lean 编译器检查过。**
> Mathlib 源码编译已完成（5843 文件，约 1.5 小时），
> **整个项目 `lake build` 成功（exit 0）**：
>
> | 文件 | 编译 | `sorry` |
> |---|---|---|
> | `MetaphorSHG/Core.lean` | ✅ | **0**（9 定理全部验证） |
> | `MetaphorSHG/Basic.lean` | ✅ | **0**（纯定义，无定理待证） |
> | `MetaphorSHG/Spectral.lean` | ✅ | **19**（陈述已定类型，未证明） |
>
> **请注意区分**：「编译通过」= 陈述类型正确 + 已写证明被内核接受；
> **19 个 `sorry` 是未证明的陈述**，不可声称已验证。
>
> 补完过程中修复了 4 类真实错误（原文件从未编译过，故此前不可见）：
> ① `Mathlib.LinearAlgebra.Matrix.Notation` 模块不存在（正确为 `Data.Matrix.Notation`）；
> ② `λ` 不能作 Lean 4 绑定变量名（6 处改 `mu`）；
> ③ `G.IsEigenvalue` 应为 `Hypergraph.IsEigenvalue`（8 处，它们是普通函数）；
> ④ `List.sum` 不存在，改用 `List.foldl`。
>
> 以下原文保留作为历史记录。

> ## ⚠️ 最重要的一句话（历史记录，已过时）
>
> **本目录下的 Lean 代码从未被 Lean 编译器检查过。**
> 它包含 19 个 `sorry`，且作者**未能完成 Mathlib 依赖的获取**。
> 因此：**任何「这些命题已被形式化验证」的说法都是错的。**
>
> 「这些命题成立」这一判断的**可核验载体是 [`PROOFS.md`](./PROOFS.md)**
> —— 那里有**完整的中文非形式化证明**，可人工逐行核验。

---

## 1. 环境记录（与预期不同，值得记录）

任务的前提是「Lean 无法在本机安装」。**这个前提部分被推翻**：

### 1.1 已做到的事

| 步骤 | 结果 |
|---|---|
| `which lean lake elan` | 起初全部为空（符合预期） |
| `curl github.com`（HEAD） | **HTTP 200** —— 与「完全阻断」的预期不同 |
| `curl github.com/.../releases/...zip` | **Connection reset**（大文件被阻断，符合预期） |
| 清华 / 中科大 / 交大镜像 | 404 或 403，**不可用**（符合预期） |
| `pip download lean` | 下载到 QuantConnect 的**量化交易引擎**，与定理证明器无关 |
| conda `lean` / `lean4` | 无相关包 |
| **GitHub 代理 `ghproxy.net`** | ✅ **可用**，稳定 ~330 KB/s |
| elan 安装包（2.2 MB） | ✅ 经代理下载，`elan-init.exe` 安装成功 |
| **Lean 4.15.0 工具链（367 MB）** | ✅ 经代理完整下载（4233 个文件），手动装入 `.elan/toolchains/` |
| `lean --version` | ✅ `Lean (version 4.15.0, x86_64-w64-windows-gnu, commit 11651562caae, Release)` |
| `lake --version` | ✅ `Lake version 5.0.0-1165156 (Lean version 4.15.0)` |
| Mathlib 缓存服务器 | ✅ `cache.mathlib.org` 与 `lakecache.blob.core.windows.net` 均可达（返回 404，说明网络通） |
| **Mathlib 仓库本体** | ❌ **反复失败**：经代理 `git clone` 在 6–60 MB 处 `early EOF` / `Recv failure: Connection was reset`，重试 4 轮未成功 |

### 1.2 结论

- **Lean 编译器本身可以安装并运行**（与任务前提相反）。
- **Mathlib 无法获取**（大体积、多次连接，代理在传输中被重置）。
- 没有 Mathlib 就没有 `Finset`、`Matrix`、`ℝ`、`BigOperators`
  —— 作者已实测确认核心 `Init`/`Std` 中**不存在**这些：
  ```
  #check @Finset.sum   ->  error: unknown identifier 'Finset.sum'
  #check @Matrix       ->  error: unknown identifier 'Matrix'
  #check @Rat          ->  error: unknown identifier 'Rat'
  ```
  因此**无法编译本目录的任何文件**，更无法验证任何证明。

### 1.3 所以：草稿，不是验证

`MetaphorSHG/*.lean` 的每一行都是**按 Mathlib 语法写的**，但没有一行被检查过。
可能的错误类型包括（不止）：

- 类型错误（`Matrix` 的参数顺序、`mulVec` 的签名）；
- 命名错误（引用了不存在的 Mathlib 引理）；
- 定义错误（如 `Spectral.lean` 的 `convLoop`/`matLoop`，见其 `sorry` 注释）；
- 缺少实例（`Fintype`/`DecidableEq` 的传递）。

**作者已在所有不确定的 Mathlib 名字旁标注 `-- CHECK NAME:`**，
以避免后人误以为该名字已核实。

---

## 2. 如何在有网络的环境验证

```bash
# 0) 准备：Lean 4.15.0（本机已装；干净机器上）
#    经代理下载 elan 与 toolchain，或直接用可用的网络。

# 1) 进入本目录
cd lean

# 2) 拉取 Mathlib（本项目 pin 在 v4.15.0，与 lean-toolchain 一致）
lake update

# 3) 关键：拉取 Mathlib 预编译缓存
#    没有这一步，编译 Mathlib 本体需要数小时。
lake exe cache get

# 4) 编译
lake build

# 5) 查看剩余 sorry
grep -rn "sorry" MetaphorSHG/*.lean
```

`lakefile.toml` 与 `lean-toolchain` 已按上述流程写好：

```toml
name = "metaphor_shg"
defaultTargets = ["MetaphorSHG"]
[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "v4.15.0"
[[lean_lib]]
name = "MetaphorSHG"
```

```
leanprover/lean4:v4.15.0
```

**验证顺序建议**（从易到难，先建立信心）：

1. `reliabilityFactor_floor_one`（`ring` 一行）
2. `reliabilityFactor_mem` / `_mono`（初等代数）
3. `row_sum_S_isolated`（`Finset.sum_eq_zero`）
4. `row_sum_S`（本项目**最核心**的命题，需 `Finset.sum_comm` 等）
5. `S_conj_eq_N`、`N_symmetric`、`N_posSemidef`
6. `fixed_point_eq`（线性代数，不需要谱论）
7. `eigenvalue_M_le` / `_ge`（需要谱论素材）
8. `invertible_one_sub_smul_of_eigenvalue_bound`（需要特征多项式）
9. `undriven_iteration_converges`（**当前是近乎空真的占位，应重写**）
10. `conv_ne_matrix_of_duplicate_member`（**定义本身需先修正**，见其注释）

---

## 3. 文件说明

| 文件 | 内容 |
|---|---|
| `PROOFS.md` | **主要交付物**：Tier-1 命题的完整中文非形式化证明 |
| `MetaphorSHG/Basic.lean` | 超图结构、$H$、$B$、$S$、$M$ 的定义 |
| `MetaphorSHG/Spectral.lean` | 全部定理陈述（19 个定理，19 个 `sorry`） |
| `lakefile.toml` / `lean-toolchain` | 供将来验证用 |

---

## 4. 定理状态表

「陈述正确?」一列是作者**按数学内容**的判断（有 `PROOFS.md` 的证明支撑），
**不是** Lean 的检查结果。「证明完整?」指 Lean 里的证明。

### Tier 1

| # | Lean 声明 | 陈述正确? | 证明完整? | sorry | 备注 |
|---|---|---|---|---|---|
| T1 | `row_sum_S` | ✅ 是 | ❌ 否 | 1 | §1 已给出完整非形式化证明 |
| T1' | `row_sum_S_isolated` | ✅ 是 | ❌ 否 | 1 | §1 |
| — | `row_sum_M` | ✅ 是 | ❌ 否 | 1 | 项目实测 $1-\varepsilon/2$ |
| — | `row_sum_M_isolated` | ✅ 是 | ❌ 否 | 1 | 孤立节点行和恒 $\frac12$ |
| T2a | `N_symmetric` | ✅ 是 | ❌ 否 | 1 | §2.1 |
| T2b | `N_posSemidef` | ✅ 是 | ❌ 否 | 1 | §2.2（平方和分解） |
| T2c | `S_conj_eq_N` | ✅ 是 | ❌ 否 | 1 | §2.3 |
| — | `isEigenvalue_of_conj` | ✅ 是 | ❌ 否 | 1 | 相似不变性，辅助引理 |
| T2 | `eigenvalue_M_le` | ✅ 是 | ❌ 否 | 1 | 上界，**精确**（取等） |
| T2 | `eigenvalue_M_ge` | ✅ 是 | ❌ 否 | 1 | 下界，**强于**项目文档 |
| T2 | `eigenvalue_M_mem_unit` | ✅ 是 | ❌ 否 | 1 | 项目原文口径 |
| T3 | `fixed_point_eq` | ✅ 是 | ❌ 否 | 1 | §3.1 |
| T3' | `invertible_one_sub_smul_of_eigenvalue_bound` | ✅ 是 | ❌ 否 | 1 | §3.2 |
| — | `alpha_one_not_invertible` | ✅ 是（**已补 `Nonempty G.LiveIdx`**） | ❌ 否 | 1 | §3.3；缺该假设时为假，已修 |

### Tier 2

| # | Lean 声明 | 陈述正确? | 证明完整? | sorry | 备注 |
|---|---|---|---|---|---|
| T4 | `undriven_iteration_converges` | ⚠️ **近乎空真** | ❌ 否 | 1 | **占位，不应被引用为结果**；真正的目标陈述见 `PROOFS.md` §4 |
| T5a | `reliabilityFactor_mem` | ✅ 是 | ❌ 否 | 1 | §5 |
| T5b | `reliabilityFactor_mono` | ✅ 是 | ❌ 否 | 1 | §5 |
| T5c | `reliabilityFactor_floor_one` | ✅ 是 | ❌ 否 | 1 | §5 |
| T6 | `conv_ne_matrix_of_duplicate_member` | ✅ 是（**存在性形式**） | ❌ 否 | 1 | §6；**「重复 ⇒ 不等价」是假命题，已改** |

**统计**：**19 个定理，19 个 `sorry`**，**0 个已完成的 Lean 证明**，
**18 个陈述经非形式化论证为真**，
**1 个陈述（`undriven_iteration_converges`）近乎空真、需重写**。

---

## 5. 已知问题（诚实清单）

1. **全部 19 个 `sorry` 未填。** 本目录不含任何已验证的证明。
2. ~~`convLoop` / `matLoop` 定义有误~~ —— **已修正**。两个算子现分别定义为
   `convOp`（按**出现次数**加权 + 按出现次数计数）与 `matOp`
   （按**去重成员** + 按去重超边数计数），差异在分子与分母两处都体现。
   相应地，T6 的陈述已从「重复 ⇒ 不等价」改为**存在性**形式
   （前者是**假命题**：穷举发现 126 个含重复但仍一致的配置）。
3. **`undriven_iteration_converges` 近乎空真**（第一个合取项是 `True`）。
   这是**有意的占位**，因为真正的收敛命题需要 Perron–Frobenius，
   而作者无法确认 Mathlib 中该开发的现状。**不要把它当结果引用。**
4. **`alpha_one_not_invertible` 缺少 `Nonempty G.LiveIdx` 假设。**
   空图时 $M=\frac12 I$ 可逆，命题为假。已在该 `sorry` 注释中标出。
5. **所有 `-- CHECK NAME:` 标注的 Mathlib 引理名未核实。** 包括
   `Matrix.IsHermitian`、`Matrix.PosSemidef`、`spectralRadius`、
   `Matrix.det_eq_prod_eigenvalues` 等。填证明前应先确认。
6. **`Spectral.lean` 自定义了 `SymmetricMat` / `IsPSD` / `IsEigenvalue`**，
   而非直接用 Mathlib 的对应概念。这是**有意的**（避免引用未核实的概念名），
   但代价是填证明时可能需要在自定义概念与 Mathlib 概念之间搭桥。

---

## 6. 发现的项目问题（与本目录相关）

详见 `PROOFS.md` §3.3 与 §6。摘要：

| 问题 | 严重度 | 位置 |
|---|---|---|
| 「$\alpha=1$ 无不动点」**字面为假**（应为「不动点不唯一」） | 表述错误，不影响结论 | `experiments/convergence_check.py:190` 等 |
| `_conv` 与 `propagation_matrix` 在**成员重复**时不等价；重复成员在 `ontology_default.json`（295/2177）等**已发布数据中存在** | **真实缺陷**（当前 SHG 未受影响，但无测试覆盖） | `metaphor_graph/hgnn.py` docstring 与实现 |
| 「特征值在 $[0,1]$」可收紧为 $[\frac12, 1-\frac\varepsilon2]$ | 可改进 | `docs/inventory/mathematics.md` M18 |
| 「$\rho(M_\varepsilon)\le1-\varepsilon/2$」实际**取等** | 可改进 | `metaphor_graph/hgnn.py:47` |

---

## 7. 诚实评估：Lean 验证能加什么

**能加的**（相对 `PROOFS.md` 的非形式化证明）：

- 排除**笔误与隐藏假设**：非形式化证明里「显然」「同理」的跳跃，
  Lean 会逐个强制展开。本项目的核心命题（T1 的求和换序、T2c 的
  $\sqrt{d}\cdot\frac1d=\frac{1}{\sqrt d}$）正是容易写错的地方。
- 排除**定义与代码不一致**：形式化迫使把 Python 的
  `np.where(dv>0, 1/dv, 0)` 这类守卫显式写出来（本目录已如此做）。
  本项目已发现 13 处「文档 ≠ 代码」，形式化是系统性发现这类问题的工具。
- 使**前提条件无法被忽略**：T1 的「活节点」、T6 的「成员不重复」
  在非形式化写作中极易被省略，在 Lean 里省略会导致编译失败。

**不能加的**：

- **不能验证浮点实现**。全部实测数字（$2\times10^{-16}$、`0.063850`）
  都是浮点结果；Lean 证明的是实数命题，二者之间的差距（浮点误差、
  求和次序、`np.where` 的守卫）**必须单独论证**。
- **不能验证「代码实现了这些公式」**。本目录形式化的是**数学对象**，
  不是 Python 程序。代码与数学对象的一致性只能靠人工审读
  （`docs/inventory/mathematics.md` 做的正是这件事）。
- **不能替代对 T4 的理解**。T4 的形式化需要 Perron–Frobenius，
  这是本目录**最大的缺口**；即便填上，它也只说明数学命题成立，
  不说明「$layers=2$ 的工作点已坍缩」——项目已正确指出后者**不成立**。

**一句话**：`PROOFS.md` 是当前可核验的数学内容；Lean 目录是**为将来**
准备的形式化骨架，它的价值在**被填完之后**才兑现。

---

*撰写：2026-09-27。代码为只读，未做任何修改。*
