# Lean 形式化：做了什么、没做什么、值不值得做

> 撰写日期：2026-09-27
> 对应目录：[`lean/`](../../lean/)
> 主要交付物：[`lean/PROOFS.md`](../../lean/PROOFS.md)（完整中文非形式化证明）

---

## 1. 一句话结论

> **⚠️ 本节已被主控更正（2026-09-27，见 §1b）**：原文写"Lean 代码一行都没编译过"、
> "`lean/` 下没有任何已验证的东西"——**这两句现在都不成立**。
> 主控后续经 `ghproxy.net` 装上了完整工具链，并**新增 `Core.lean` 并编译通过**。

**做完了**：Tier-1 三个命题的**完整非形式化证明**（中文，可人工核验），
一份 19 个定理、13 个 `sorry` 的 Lean 4 + Mathlib 形式化骨架，
以及 **`MetaphorSHG/Core.lean` —— 9 条定理，已在 Lean 4.15.0 上编译通过，
0 错误 0 `sorry`**。

**做完了（更正）**：**Mathlib 源码编译已完成**（5843 文件，约 1.5 小时），
**整个 Lean 项目现在 `lake build` 成功（exit 0）**：

| 文件 | 编译 | `sorry` | 性质 |
|---|---|---|---|
| `MetaphorSHG/Core.lean` | ✅ | **0** | 9 定理全部机器验证 |
| `MetaphorSHG/Basic.lean` | ✅ | **0** | **纯定义**（14 个 def，无定理待证） |
| `MetaphorSHG/Spectral.lean` | ✅ | **19** | 27 定理/定义；19 条陈述已定类型但未证明 |

**关键区分**：「编译通过」= 所有**陈述**类型正确 + 已写的证明被内核接受；
13 个 `sorry` 是**未证明的陈述**，不可声称已验证。

**修复过程中发现并解决 4 类真实错误**（原文件从未编译过，故这些错误此前不可见）：
1. `import Mathlib.LinearAlgebra.Matrix.Notation` —— 该模块**不存在**，
   正确路径是 `Mathlib.Data.Matrix.Notation`
2. `λ` 作为绑定变量名 —— Lean 4 中 `λ` 是保留符号，**不能作标识符**
   （6 处，已改为 `mu`）
3. `G.IsEigenvalue` —— 这些是**普通函数**（接受矩阵参数），
   不是 `Hypergraph` 的方法，须写 `Hypergraph.IsEigenvalue`（8 处）
4. `List.sum` —— 该版本 Mathlib 中不存在，改用 `List.foldl`

### §1b 环境更正（我先前的判断错了）

我最初记录"Lean 无法在本机安装"，依据是 GitHub 直连被阻断、镜像 404。
**该结论错误**：

| 路径 | 实测结果 |
|---|---|
| `ghproxy.net` 代理 | ✅ 可用，~330 KB/s，成功下载 `elan-init.exe` |
| 系统代理 `http://127.0.0.1:7890` | ✅ 可用 |
| 直连 github.com | ✅ 后来也可达 |

**已做到**：安装 **Lean 4.15.0**（`~/.elan/bin/lean`）→ `lake update` 拉取
**Mathlib 729 MB** → `Core.lean` **编译通过**（exit=0）。

### §1c `Core.lean` 的建模约束（诚实记录）

Lean 4.15.0 的 **core + Std 中没有 `Rat` 与 `Finset`**（实测 `import Std` 后
`#check Rat` 报 unknown identifier；二者均在 Mathlib）。故 `Core.lean` 只能
用 `Nat`/`Int` 陈述，因此：

- "行和 = 1"被**弱化**为"每条边贡献非零"（`contribution_nonzero`），
  而非直接陈述归一化 —— 完整有理数版本在 `Spectral.lean`（未验证）。
- 不动点被表述为**线性恒等式**（`scalar_fixed_point_identity`），
  而非除法形式（后者需域结构）。
- `denominators_diverge` / `no_duplicate_of_equal_denominator` 是**平凡重言式**，
  作用是**记录建模意图**（分母是重复成员分歧的根源），不提供数学内容。

**净结论**：`Core.lean` 验证的是**代数骨架**（交换律、分配律、零保护、
不可逆的充分条件），**不是谱定理本身**。谱性质（特征值界、ρ(S)=1、收敛速率）
仍需 Mathlib，仍在草稿状态。**不要声称"谱性质已形式化验证"。**

**顺带发现**：2 处项目陈述问题（1 处**字面为假**，1 处**真实缺陷**，
后者的触发条件**已存在于已发布数据中**）。见 §5。

---

## 2. 形式化了什么

形式化对象以 `metaphor_graph/hgnn.py`（`main` 分支）为准。

| 编号 | 命题 | Lean 声明 | 非形式化证明 |
|---|---|---|---|
| **T1** | $S=D_v^{-1}HD_e^{-1}H^{\mathsf T}$ 在**活节点**上行和为 1 | `row_sum_S` | ✅ 完整（§1） |
| **T2** | $M=\frac12(I+(1-\varepsilon)S)$ 特征值 $\in[\frac12,1-\frac\varepsilon2]$ | `eigenvalue_M_le/_ge/_mem_unit` | ✅ 完整（§2） |
| **T3** | 不动点 $u=(1-\alpha)(I-\alpha M)^{-1}X_0$，条件 $\alpha\rho(M)<1$ | `fixed_point_eq`、`invertible_...` | ✅ 完整（§3） |
| T4 | $M^kX_0\to$ 分量常向量 | `undriven_iteration_converges`（**占位**） | ⚠️ 仅框架（§4） |
| T5 | 可靠性因子 $\in[f,1]$、单调、$f{=}1$ 关闭 | `reliabilityFactor_*` | ✅ 完整（§5） |
| T6 | **存在**含重复成员的配置使 `_conv` ≠ `propagation_matrix` | `conv_ne_matrix_of_duplicate_member` | ✅ 机制+精确反例（§6） |

**辅助引理**（T2 的证明路线，全部给出完整证明）：

- T2a：$B$、$N$ 对称；
- T2b：$N$ 半正定，**平方和分解**
  $x^{\mathsf T}Nx=\sum_e\frac{1}{D_e(e)}\bigl(\sum_v H_{ve}x_v/\sqrt{D_v(v)}\bigr)^2\ge0$；
- T2c：相似变换 $D^{1/2}SD^{-1/2}=N$。

---

## 3. 环境：与预期不同（重要）

任务前提是「Lean 无法安装」。**这个前提部分不成立**，记录如下：

| 尝试 | 结果 |
|---|---|
| `which lean lake elan` | 起初为空 |
| `curl https://github.com`（HEAD） | **HTTP 200** —— 并非完全阻断 |
| `curl .../releases/...zip` | Connection reset（大文件被阻断） |
| 清华/中科大/交大镜像 | 404 / 403，不可用 |
| `pip download lean` | QuantConnect 量化引擎，**与定理证明器无关** |
| **`ghproxy.net` GitHub 代理** | ✅ **可用**，~330 KB/s |
| elan 安装包 | ✅ 下载并安装成功 |
| **Lean 4.15.0 工具链（367 MB）** | ✅ **完整下载**，`lean --version` 正常输出 |
| **Mathlib 仓库** | ❌ **6 次 `git clone` 全部失败**（`early EOF` / 连接重置），最大到 ~60 MB |

### 关键事实

- **Lean 编译器可装可跑**：`Lean (version 4.15.0, x86_64-w64-windows-gnu)`。
- **Mathlib 拿不到**：没有它就没有 `Finset`、`Matrix`、`ℝ`。
  实测核心库确认：
  ```
  #check @Finset.sum  ->  unknown identifier
  #check @Matrix      ->  unknown identifier
  #check @Rat         ->  unknown identifier
  ```
- 因此 **`lean/` 下没有任何文件能通过编译**，包括那些只用了初等代数的。

### 对后续的意义

在有网络的环境（或代理更稳定的时段），验证成本很低：

```bash
cd lean && lake update && lake exe cache get && lake build
```

`lake exe cache get` 是**关键**：没有预编译缓存，编译 Mathlib 本体要数小时。

---

## 4. 诚实评估：Lean 验证能加什么、不能加什么

### 能加

1. **排除笔误与隐藏假设。** 本项目 T1 的求和换序、T2c 的
   $\sqrt d\cdot\frac1d=\frac{1}{\sqrt d}$，正是非形式化写作最容易出错的地方。
2. **暴露「文档 ≠ 代码」。** 形式化迫使把 `np.where(dv>0, 1/dv, 0)`
   这类守卫显式写出。本项目已登记 **13 处**文档-代码分歧，
   形式化是系统性发现这类问题的工具。
3. **让前提条件无法被省略。** T1 的「活节点」、T6 的「成员不重复」，
   在散文里极易被省掉，在 Lean 里省掉就编译不过。

### 不能加

1. **不能验证浮点实现。** 所有实测数字（$2\times10^{-16}$、`0.063850`）
   都是浮点结果；Lean 证明的是实数命题。二者之间的差距
   （浮点误差、求和次序、`np.where` 守卫）**必须单独论证**。
2. **不能验证「代码实现了这些公式」。** 形式化的是**数学对象**，不是 Python 程序。
   代码与数学对象的一致性只能靠人工审读 —— 这正是
   `docs/inventory/mathematics.md` 在做的事。
3. **不能替代对 T4 的理解。** T4 需要 Perron–Frobenius，是本次**最大缺口**。
   即便填上，也只说明数学命题成立，**不说明**「$layers=2$ 工作点已坍缩」
   —— 项目已正确指出后者**不成立**（`REPORT_exp-dynamics.md` §0 结论 1，
   且给出了决定性反证：完美同分量指示器的准确率上限 0.8000 < 实测 0.950）。

### 结论

**`lean/PROOFS.md` 是当前可核验的数学内容；`lean/MetaphorSHG/*.lean` 是
为将来准备的骨架，价值在被填完之后才兑现。** 二者不可混淆。

---

## 5. 发现的项目问题

### 5.1 「$\alpha=1$ 无不动点」——**字面为假**（表述错误）

**位置**：`experiments/convergence_check.py:190`、`hgnn.py` 邻近注释、
`test_metaphor_graph.py::test_alpha_one_has_no_fixed_point` 的 docstring 首句。

**问题**：$\alpha=1$ 时 $M u=u$ **有解**，且解空间维数 = 连通分量数。
作者实测 `doc_project`：$\dim\ker(I-M)=5$，且 $\alpha=1$ 的迭代
**确实收敛到其中一个解**（$k=2000$ 时 $\lVert MX-X\rVert_{\max}=0$）。
若真无不动点，迭代不可能收敛到满足 $MX=X$ 的点。

**正确表述**：「$\alpha=1$ **不动点不唯一**」。
该测试的 docstring **第二句**其实已经写对了（「无**唯一**不动点」），
是简写时丢了「唯一」二字。

**影响**：**不影响任何实测结论** —— 所有下游论断用的都是「不唯一/坍缩」的意思。
属于表述问题，建议修字面。

### 5.2 `_conv` 与 `propagation_matrix` 在**成员重复**时不等价（**真实缺陷**）

**位置**：`metaphor_graph/hgnn.py`，`propagation_matrix` 的 docstring 声称
「与 `_conv` 的循环实现**逐元素等价**」。

**问题**：一条超边重复列出同一节点时，两个实现的分母不同：

- `_conv` 按 **list** 迭代，节点收到 2 份贡献、`counts[i]` 也加 2，
  但**其他**超边的贡献也被这个被抬高的 `counts[i]` 除；
- `propagation_matrix` 用 `H[i,j]=1.0` **赋值**，重复被静默折叠为一次。

**复现**（作者实测）：`he_members=[[1,1,2],[0,3]]` 时
`max|_conv(X) - M@X| = 0.063850 ≠ 0`。
在真实 SHG 上注入重复（`doc_project`，把 `source_domain` 追加进 `ground`）：
`max|diff| = 0.0214788 ≠ 0`。
注意 **$S$ 的行随机性不受影响**（仍为 1），所以「行随机」测试**抓不到**这个缺陷。

**触发条件在已发布数据中存在**（这是最要紧的一点）：

| 文件 | 含重复成员的记录 / 总数 |
|---|---|
| `metaphor_graph/ontology_default.json` | **295 / 2177** |
| `metaphor_graph/llm_ontology_train.json` | **303 / 2185** |
| `release/metaphor_resources/ontology_default.json` | **295 / 2177** |
| `metaphor_graph/llm_ontology.json` | **106 / 656** |

成因：`member_entities = [source_domain, target_domain] + ground`，
LLM 把源域/目标域同时写进 `ground` 时该节点重复。
全仓库 **988/7232（13.7%）** 的记录存在 `ground` 与 `source/target` 的重叠。

**当前暴露面**：`MetaphorSHGBuilder` 产出的 `doc_project`（17 边）、
`doc_relationship`（10 边）**重复成员数为 0**，
所以**当前跑出的谱数字未受影响**。但：

- 缺陷**不是假设性的** —— 输入数据里就有；
- 任何把本体记录**直接**转成超边的路径都会命中；
- **没有测试**覆盖这一情形（现有测试只覆盖空 `he_members`）；
- `health.py:141` 已在别处做去重（`dict.fromkeys`），说明项目**知道**要去重，
  只是 `hgnn.py` 这条路径漏了。

**建议**：(a) docstring 限定为「成员互不重复时等价」；
(b) 在 `_build_hyperedges` 对 `members` 去重；
(c) 加一条含重复成员的回归测试。

### 5.3 两处**可收紧**（不是错）

| 项目原文 | 位置 | 实际 |
|---|---|---|
| 特征值在 $[0,1]$ | `mathematics.md` M18 | 实际在 $[\frac12,1-\frac\varepsilon2]$，$[0,\frac12)$ 是空的（实测 `min=0.500000`） |
| $\rho(M_\varepsilon)\le1-\varepsilon/2$（不等式） | `hgnn.py:47` | 实测**取等**；`PROOFS.md` §2.4(c) 证明取等是定理 |

---

## 6. 交付清单

| 文件 | 内容 | 状态 |
|---|---|---|
| `lean/PROOFS.md` | **主要交付物**：T1–T6 完整中文非形式化证明 | ✅ 完整 |
| `lean/README.md` | 环境记录、验证流程、状态表、已知问题 | ✅ 完整 |
| `lean/MetaphorSHG/Basic.lean` | 超图、$H$、$B$、$S$、$M$ 定义 | ⚠️ 未编译 |
| `lean/MetaphorSHG/Spectral.lean` | 19 个定理陈述，13 个 `sorry` | ⚠️ 未编译 |
| `lean/lakefile.toml` / `lean-toolchain` | 供将来验证 | ✅ 与 Mathlib v4.15.0 对齐 |
| `docs/math/lean_formalization.md` | 本文件 | ✅ |

**统计**：19 个定理，13 个 `sorry`，0 个已完成的 Lean 证明，
20 个陈述经非形式化论证为真，1 个（`undriven_iteration_converges`）为
近乎空真的占位需重写，1 个（`alpha_one_not_invertible`）需补假设后才为真。

---

## 7. 若要继续

**优先级 1（低成本高价值）**：在一个有网络的环境跑
`cd lean && lake update && lake exe cache get && lake build`，
按 `README.md` §2 的顺序填 `sorry`（从 `reliabilityFactor_floor_one` 开始）。
这一步能把「20 个非形式化论证」变成「20 个机器检查的定理」。

**优先级 2**：修 §5.2 的缺陷（去重 + 回归测试）。这是**代码问题**，
与 Lean 无关，可以立刻做。

**优先级 3**：T4 的 Perron–Frobenius 形式化。这是最大的数学工程，
且**边际价值最低** —— 项目已经用实测正确否证了「工作点坍缩」的误读，
T4 的渐近结论本身不是论文的承重点。
