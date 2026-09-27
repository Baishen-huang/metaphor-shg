# 谱性质的完整非形式化证明

> **本文件是 `lean/` 目录的主要交付物。**
>
> Lean 草稿（`MetaphorSHG/*.lean`）在本机**未能通过编译器检查**（原因见
> `README.md` 的环境记录），因此「这些命题成立」这一判断的**可核验载体是
> 本文件**，不是 Lean 代码。下面每条定理都给出**完整证明**，不含未说明的跳跃。
> 凡有缺口的地方，用 **⚠️ 缺口** 显式标出。
>
> 对应代码：`metaphor_graph/hgnn.py`（`main` 分支，2026-09-27）。
> 记号一律以代码为准，文档公式与代码不一致处会专门指出。
>
> 撰写日期：2026-09-27。

---

## 0. 记号与约定

设超图 $G=(V,E,\mathrm{inc})$，其中 $V$ 是有限节点集，$E$ 是有限超边集，
$\mathrm{inc}\colon V\times E\to\{0,1\}$ 是**布尔**关联关系（$1$ 表示属于）。

> **关于重数的约定（重要）**：代码里的 `he_members` 是 `List[List[int]]`，
> 一条超边**可以**重复列出同一个节点。本文件的矩阵论断（§1–§4）一律按
> `propagation_matrix` 的口径，即把关联看作**布尔关系**（重复只算一次）。
> 循环实现 `_conv` 在重复时与矩阵不一致 —— 这是一个**真实的缺陷**，
> 见 §6。

定义：

| 记号 | 定义 | 代码对应 |
|---|---|---|
| $H_{ve}$ | $\mathrm{inc}(v,e)$ | `H = np.zeros((V,E)); H[i,j]=1.0` |
| $D_v(v)$ | $\sum_{e}H_{ve}$ | `dv = H.sum(axis=1)` |
| $D_e(e)$ | $\sum_{v}H_{ve}$ | `de = H.sum(axis=0)` |
| $w_v(v)$ | $\begin{cases}1/D_v(v),&D_v(v)>0\\0,&D_v(v)=0\end{cases}$ | `np.where(dv>0, 1/dv, 0)` |
| $w_e(e)$ | $\begin{cases}1/D_e(e),&D_e(e)>0\\0,&D_e(e)=0\end{cases}$ | `np.where(de>0, 1/de, 0)` |
| $B$ | $B_{vw}=\sum_e H_{ve}\,w_e(e)\,H_{we}$ | （代码未显式构造） |
| $S$ | $S_{vw}=w_v(v)\,B_{vw}$ | `S = (dv_inv[:,None]*H) @ (de_inv[:,None]*H.T)` |
| $M_\varepsilon$ | $(M_\varepsilon)_{vw}=\tfrac12\left(\delta_{vw}+(1-\varepsilon)S_{vw}\right)$ | `0.5*(I + (1-leak)*S)` |

**「活节点」定义**：$D_v(v)>0$（代码 `live = dv > 0`）。
**孤立节点**：$D_v(v)=0$，此时 $w_v(v)=0$。

> **为什么必须区分活/孤立**：$S$ 的行随机性**只在活节点上成立**。
> 孤立节点整行为 $0$，$M$ 的对应行和为 $1/2$（与 $\varepsilon$ 无关）。
> 项目文档已正确记录这一点（M17/M18），本文件 §1、§2 把它作为定理的必要条件。

---

## 1. 定理 T1：$S$ 在活节点上行随机

> **定理 T1.** 对任意 $v\in V$ 且 $D_v(v)>0$，
> $$\sum_{w\in V}S_{vw}=1 .$$
>
> **推论 T1'.** 若 $D_v(v)=0$，则 $\sum_w S_{vw}=0$。

### 证明

固定 $v$，设 $d:=D_v(v)>0$。

**第一步：展开。**

$$\sum_{w}S_{vw}=\sum_{w}w_v(v)\sum_{e}H_{ve}\,w_e(e)\,H_{we}
=w_v(v)\sum_{w}\sum_{e}H_{ve}\,w_e(e)\,H_{we}.$$

**第二步：交换求和次序。** $V,E$ 均有限，$\sum_w\sum_e=\sum_e\sum_w$（有限和可交换，Fubini 的平凡情形）：

$$=w_v(v)\sum_{e}H_{ve}\,w_e(e)\sum_{w}H_{we}.$$

**第三步：内层和。** 由 $D_e(e)=\sum_w H_{we}$ 的定义，内层和**恰为** $D_e(e)$：

$$\sum_{w}H_{we}=D_e(e).$$

**第四步：分情况。**

- 若 $D_e(e)=0$（空超边）：此时 $w_e(e)=0$，且对一切 $v$ 有 $H_{ve}=0$。
  该 $e$ 对求和的贡献为 $0\cdot 0\cdot 0=0$，与「$w_e(e)\cdot D_e(e)$ 应为 $1$」
  无关，因为**整个项已经为 0**。
- 若 $D_e(e)>0$：$w_e(e)\cdot D_e(e)=\dfrac{1}{D_e(e)}\cdot D_e(e)=1$。

**关键观察**：若 $H_{ve}=1$，则 $v$ 是 $e$ 的成员，故 $D_e(e)\ge 1>0$，
自动落入第二种情形。所以**只有 $H_{ve}=1$ 的那些 $e$ 会真正贡献**，且每个贡献恰好 $1$：

$$\sum_{e}H_{ve}\,w_e(e)\cdot D_e(e)=\sum_{e}H_{ve}\cdot 1=\sum_e H_{ve}=D_v(v)=d .$$

**第五步：合并。**

$$\sum_w S_{vw}=w_v(v)\cdot d=\frac{1}{d}\cdot d=1 .$$

（$w_v(v)=1/d$ 用到了 $d>0$，这正是假设。$\blacksquare$）

**推论 T1' 的证明**：$D_v(v)=0$ 时 $w_v(v)=0$，故每个 $S_{vw}=0\cdot B_{vw}=0$，
求和为 $0$。$\blacksquare$

### 与实测的一致性

项目实测（`REPORT_exp-dynamics.md` §2）：`S_rowsum_exact_one_live = True`，
`min = 0.9999999999999998`、`max = 1.0`。上式的精确值为 $1$，浮点误差
$\sim10^{-16}$ 来自 $1/D_e(e)$ 与 $D_e(e)$ 的乘法不是精确的浮点运算。

作者独立复现（2026-09-27，含孤立节点与空超边的构造用例）：
`max|rowsum-1| = 1.11e-16`；孤立节点行和为 `0.0`。与定理一致。

### ⚠️ 一个容易写错的细节

$S_{vw}$ 的定义里，$w_v(v)$ 在**求和号外**、$w_e(e)$ 在**求和号内**。
如果误把 $w_v$ 也放进内层（写成 $\sum_e w_v(v) H_{ve}w_e(e)H_{we}$ 再对 $w$ 求和），
结论不变；但如果把 $w_e(e)$ 提到外层，第四步的「$w_e(e)\cdot D_e(e)=1$」
就不再与 $H_{ve}$ 联动，空超边的情形会出问题。形式化时要注意求和结构的层次。

---

## 2. 定理 T2：$M=\frac12(I+(1-\varepsilon)S)$ 的特征值落在 $[0,1]$

这条定理的**难点不在结论，而在 $S$ 不对称**。项目已实测 `S_sym = False`，
因此不能直接对 $S$ 用对称矩阵谱定理。正确路线是**相似变换**。

### 2.1 引理 T2a：$B$ 对称，$N$ 对称

> **引理 T2a.** $B_{vw}=B_{wv}$；且在活节点集上，矩阵
> $N_{vw}:=\dfrac{1}{\sqrt{D_v(v)}}B_{vw}\dfrac{1}{\sqrt{D_v(w)}}$
> 对称。

**证明.** $B_{vw}=\sum_e H_{ve}w_e(e)H_{we}$，把 $v,w$ 互换得到
$\sum_e H_{we}w_e(e)H_{ve}$。实数乘法可交换，且有限和与次序无关，
逐项相等，故 $B_{vw}=B_{wv}$。

$N$ 的对称性：$N_{vw}=\frac{1}{\sqrt{D_v(v)}}B_{vw}\frac{1}{\sqrt{D_v(w)}}$，
互换 $v,w$ 后 $B$ 对称、两个标量因子互换位置，仍相等。$\blacksquare$

### 2.2 引理 T2b：$N$ 半正定（关键一步）

> **引理 T2b.** 对任意实向量 $x$，
> $$x^{\mathsf T}Nx=\sum_{e\in E}\frac{1}{D_e(e)}\Bigl(\sum_{v}H_{ve}\frac{x_v}{\sqrt{D_v(v)}}\Bigr)^{2}\ \ge\ 0 .$$
> （约定：$D_e(e)=0$ 的项取 $0$；此时该超边无成员，内层和为 $0$，
> 故约定与公式自洽。）

**证明.** 令 $y_v:=\dfrac{x_v}{\sqrt{D_v(v)}}$（$v$ 为活节点）。则

$$x^{\mathsf T}Nx=\sum_v\sum_w x_v\frac{B_{vw}}{\sqrt{D_v(v)}\sqrt{D_v(w)}}x_w
=\sum_v\sum_w y_v B_{vw}y_w .$$

代入 $B$ 的定义：

$$=\sum_v\sum_w y_v\Bigl(\sum_e H_{ve}w_e(e)H_{we}\Bigr)y_w
=\sum_e w_e(e)\sum_v\sum_w y_v H_{ve}H_{we}y_w .$$

内层双重和可写成完全平方：

$$\sum_v\sum_w y_vH_{ve}H_{we}y_w=\Bigl(\sum_v H_{ve}y_v\Bigr)\Bigl(\sum_w H_{we}y_w\Bigr)
=\Bigl(\sum_v H_{ve}y_v\Bigr)^{2}.$$

故 $x^{\mathsf T}Nx=\sum_e w_e(e)\left(\sum_v H_{ve}y_v\right)^2$。
每个 $w_e(e)\in\{0\}\cup(0,\infty)$ 非负，平方非负，有限和保号，
所以 $x^{\mathsf T}Nx\ge 0$。$\blacksquare$

**这个平方和形式是 T2 全部内容的来源。** 它同时给出「$N$ 的特征值 $\ge0$」
与「$N$ 可对角化（实特征值）」。

### 2.3 引理 T2c：相似变换

> **引理 T2c.** 在活节点集上，令 $D:=\mathrm{diag}(D_v(v))$。则
> $$D^{1/2}\,S\,D^{-1/2}=N .$$

**证明.** 对活节点 $v$：

$$S_{vw}=w_v(v)B_{vw}=\frac{1}{D_v(v)}B_{vw}.$$

于是

$$\left(D^{1/2}SD^{-1/2}\right)_{vw}
=\sqrt{D_v(v)}\cdot\frac{1}{D_v(v)}B_{vw}\cdot\frac{1}{\sqrt{D_v(w)}}.$$

关键恒等式：$\sqrt{D_v(v)}\cdot\dfrac{1}{D_v(v)}=\dfrac{1}{\sqrt{D_v(v)}}$
（因 $D_v(v)=\sqrt{D_v(v)}\cdot\sqrt{D_v(v)}$ 且 $\sqrt{D_v(v)}>0$）。
代回：

$$=\frac{1}{\sqrt{D_v(v)}}B_{vw}\frac{1}{\sqrt{D_v(w)}}=N_{vw}.\qquad\blacksquare$$

**注意**：$D^{1/2}SD^{-1/2}=N$ 意味着 $S$ 与 $N$ **相似**（$D^{1/2}$ 可逆，
因为所有对角元 $D_v(v)>0$）。相似矩阵有相同的特征值（含重数）。
这是「$S$ 虽不对称，但特征值全为实数且 $\ge0$」的**唯一依据**。

### 2.4 定理 T2：特征值界

> **定理 T2.** 设 $\lambda$ 是 $M_\varepsilon$ 的特征值，$\varepsilon\in[0,1]$。则
> $$\frac12\ \le\ \lambda\ \le\ 1-\frac{\varepsilon}{2}.$$
> 特别地 $\lambda\in[0,1]$（项目文档的表述），且两个端点都**取得到**。

**证明.**

**（a）孤立节点块。** 若 $D_v(v)=0$，则 $S$ 的第 $v$ 行为 $0$，
故 $M_\varepsilon$ 的第 $v$ 行是 $\frac12 e_v^{\mathsf T}$（只有对角元 $\frac12$）。
这一块的特征值是 $\frac12$，满足 $\frac12\le\lambda\le1-\frac\varepsilon2$
（后者因 $\varepsilon\le1$）。

**（b）活节点块。** 记 $M^{\mathrm{live}}:=\frac12(I+(1-\varepsilon)S^{\mathrm{live}})$，
其中 $S^{\mathrm{live}}$ 是 $S$ 在活节点上的限制。

由 T2c，$S^{\mathrm{live}}$ 与 $N$ 相似，故二者特征值集合相同（含重数）。
由 T2b，$N$ 半正定且对称，故 $N$ 的**全部特征值为实数且 $\ge0$**
（对称矩阵有正交特征基，$N=Q\Lambda Q^{\mathsf T}$，
$x^{\mathsf T}Nx=\sum_i\lambda_i(Q^{\mathsf T}x)_i^2\ge0$
对全部 $x$ 成立 $\Rightarrow$ 全部 $\lambda_i\ge0$）。

所以 $S^{\mathrm{live}}$ 的每个特征值 $\mu$ 满足 $\mu\ge0$。

$M^{\mathrm{live}}=\frac12 I+\frac{1-\varepsilon}{2}S^{\mathrm{live}}$，
且 $I$ 与 $S^{\mathrm{live}}$ 可交换（$I$ 是单位阵），
故二者**同时上三角化**（Schur 三角化），$M^{\mathrm{live}}$ 的特征值恰为
$$\lambda=\frac12+\frac{1-\varepsilon}{2}\mu,\qquad \mu\in\mathrm{spec}(S^{\mathrm{live}}).$$

- 下界：$\mu\ge0$ 且 $\varepsilon\le1\Rightarrow1-\varepsilon\ge0$，故
  $\lambda\ge\frac12+\frac{1-\varepsilon}{2}\cdot0=\frac12$。
- 上界：由 T1，$S^{\mathrm{live}}\mathbf 1=\mathbf 1$（每行和为 $1$）。
  对**非负**矩阵 $S^{\mathrm{live}}$（$H\ge0,w_e\ge0,w_v\ge0\Rightarrow S\ge0$），
  Gershgorin 圆盘定理给出：每个特征值 $\mu$ 落在某个圆盘
  $\{\mu:|\mu-S_{vv}|\le\sum_{w\ne v}S_{vw}\}$ 内。
  由于 $S\ge0$ 且行和为 $1$，圆盘半径为 $\sum_{w\ne v}S_{vw}=1-S_{vv}$，
  故 $|\mu-S_{vv}|\le1-S_{vv}$，即 $\mu\le S_{vv}+(1-S_{vv})=1$。
  （也可用 Perron–Frobenius：$\rho(S^{\mathrm{live}})=1$，且非负矩阵的谱半径
  本身是特征值。）
  所以 $\mu\le1$，从而 $\lambda\le\frac12+\frac{1-\varepsilon}{2}\cdot1=1-\frac\varepsilon2$。

**（c）端点可取到。** $\mu=1$ 确实是特征值（$S^{\mathrm{live}}\mathbf1=\mathbf1$，
$\mathbf1\ne0$），代入得 $\lambda=1-\frac\varepsilon2$。故上界**精确**，
与项目实测 `ρ(M) = 1 − ε/2`（`ε=0.1 → 0.9500000000` 等）完全一致。

下界 $\frac12$ 也可取到：孤立节点给出 $\lambda=\frac12$；
`doc_project` 实测 `min = 0.500000`。$\blacksquare$

### 2.5 与项目文档的差异（两个改进）

1. **项目文档说「特征值在 $[0,1]$」，实际更强：特征值在 $[\frac12, 1-\frac\varepsilon2]$。**
   $[0,\frac12)$ 是空的。实测 `min = 0.500000`（对所有试过的 $\varepsilon$）。
   这不是错误，而是**可以收紧但项目未收紧**的界。
2. **项目文档 M18 写「谱半径 $\rho(M_\varepsilon)\le1-\varepsilon/2$」（不等式），
   实测取等。** 由 (c) 可知**取等是定理**，不是巧合。建议文档把 $\le$ 改成 $=$。

### ⚠️ 关于 Gershgorin 的说明

上面的上界证明用了 Gershgorin 圆盘定理。这是一条完全标准的定理，但它的
陈述依赖「$S^{\mathrm{live}}$ 非负 + 行和为 1」这个组合。若形式化时想绕开
Gershgorin，另一条路是：

- 由 T1'，$S^{\mathrm{live}}\mathbf1=\mathbf1$；
- 对任意特征对 $(\mu,x)$，取 $|x_i|=\max_j|x_j|$（$x\ne0$ 保证 $|x_i|>0$）；
- $|\mu|\,|x_i|=|\sum_j S_{ij}x_j|\le\sum_j S_{ij}|x_j|\le|x_i|\sum_j S_{ij}=|x_i|$；
- 约去 $|x_i|>0$ 得 $|\mu|\le1$。

这给出 $|\mu|\le1$（含 $\mu\ge-1$），**比 Gershgorin 更直接**，且只需行随机 +
非负。下界 $\mu\ge0$ 仍须由 T2b 的半正定性提供（这一步无法绕开）。
**建议形式化时采用这条路线**，因为它需要的 Mathlib 素材更少。

---

## 3. 定理 T3：驱动迭代的不动点

代码（`hgnn.py::forward`）：

```python
X0 = self.X.copy(); X = X0.copy()
for _ in range(self.layers):
    X = (1.0 - self.alpha) * X0 + self.alpha * self._conv(X)
```

不动点方程（去掉层数截断，令迭代趋于稳定）：

$$u=(1-\alpha)X_0+\alpha Mu
\quad\Longleftrightarrow\quad
(I-\alpha M)u=(1-\alpha)X_0 .$$

### 3.1 定理 T3（唯一性与显式解）

> **定理 T3.** 设 $A:=I-\alpha M$ 可逆，逆为 $A^{-1}$。若 $u$ 满足
> $u=(1-\alpha)X_0+\alpha Mu$，则
> $$u=(1-\alpha)A^{-1}X_0 .$$

**证明.** 把不动点方程移项：

$$u-\alpha Mu=(1-\alpha)X_0\ \Longrightarrow\ (I-\alpha M)u=(1-\alpha)X_0
\ \Longrightarrow\ Au=(1-\alpha)X_0 .$$

两边左乘 $A^{-1}$：

$$u=A^{-1}\bigl((1-\alpha)X_0\bigr)=(1-\alpha)A^{-1}X_0 ,$$

最后一步用线性性（标量可提出）。$\blacksquare$

**注**：证明**只用了 $A^{-1}A=I$**（左逆）。若 $A$ 是方阵且可逆，
左逆即逆；形式化时给两个方向更省事（避免在陈述里纠结「可逆」的编码方式）。

### 3.2 定理 T3'（可逆性条件）

> **定理 T3'.** 若 $\alpha\rho(M)<1$（$\rho$ 为谱半径），则 $I-\alpha M$ 可逆。

**证明.** 有限维情形：$\det(I-\alpha M)=\prod_i(1-\alpha\lambda_i)$，
其中 $\lambda_i$ 遍历 $M$ 的特征值（含代数重数）。
由 $\alpha\rho(M)<1$ 得 $|\alpha\lambda_i|\le\alpha\rho(M)<1$，
故每个因子 $1-\alpha\lambda_i\ne0$，乘积非零，矩阵可逆。$\blacksquare$

**代码对应**：`hgnn.py::__init__` 在 `alpha > 1` 时要求
`α·(1−ε/2) < 1` 否则抛 `ValueError`，注释写「Neumann 级数发散」。
由 §2.4(c)，$\rho(M)=1-\varepsilon/2$ 精确成立，故
$\alpha\rho(M)<1\iff\alpha(1-\varepsilon/2)<1$ —— **代码的检查条件与定理一致**。

**Neumann 级数形式**（项目 docstring 的说法）：

$$(I-\alpha M)^{-1}=\sum_{k\ge0}(\alpha M)^k ,$$

在 $\alpha\rho(M)<1$ 时收敛（有限维时由 $\rho(\alpha M)<1$ 保证；
一般 Banach 代数中需 $\alpha\|M\|<1$）。代入 T3：

$$u=(1-\alpha)\sum_{k\ge0}(\alpha M)^kX_0 ,$$

即「$X_0$ 的每一轮传播按 $\alpha^k$ 加权」，这解释了为什么 $\alpha$ 小则源身份保留好
（实测同分量余弦 $\alpha=0.3\to0.0683$，$\alpha=0.9\to0.5652$，$\alpha=1\to1.0$）。

### 3.3 ⚠️ **发现一处错误陈述**：$\alpha=1$ 「无不动点」

项目在多处写「$\alpha=1$ 无不动点」（`convergence_check.py:190`、
`test_metaphor_graph.py::test_alpha_one_has_no_fixed_point` 的 docstring：
「$\alpha=1$ 时 $I-\alpha M$ 奇异（$\rho(M)=1$）→ 无唯一不动点」）。

**字面上这是错的。** 正确说法是**不动点不唯一**，而非不存在：

- $M u=u$ 等价于 $(I-M)u=0$，即 $u\in\ker(I-M)$；
- 作者实测：`doc_project` 的 $\dim\ker(I-M)=5$（= 连通分量数），
  即**存在 5 维的解空间**，远非「无解」；
- 且 $\alpha=1$ 的迭代**确实收敛到其中一个解**：作者实测
  $k=2000$ 时 $\lVert MX-X\rVert_{\max}=0$（机器精度内），
  $k=500$ 时 $2.1\times10^{-7}$。若真无不动点，迭代不可能收敛到满足
  $MX=X$ 的点。

**哪个说法是对的**：`test_alpha_one_has_no_fixed_point` 的**正文**（docstring 第二句）
其实已经写对了 —— 「无**唯一**不动点」。是简写「无不动点」丢了「唯一」二字。

**建议修改**：把 `convergence_check.py:190` 的
「$\alpha=1$ 无不动点：$\rho(M)=1$ 使 $I-\alpha M$ 奇异」
改为「$\alpha=1$ **不动点不唯一**：$I-\alpha M$ 奇异，$\ker$ 维数 = 连通分量数」。
这是**表述错误，不影响任何实测结论**（所有下游结论用的都是「不唯一/坍缩」的意思）。

Lean 里对应的真命题见 `Spectral.lean::alpha_one_not_invertible`，
它陈述的是**不可逆**（正确），而不是「无不动点」（错误）。

---

## 4. 定理 T4：无源迭代 $M^kX_0$ 的收敛（Tier 2，仅框架）

> **定理 T4（目标陈述）.** 设 $\varepsilon=0$，$\alpha=1$。则 $M^kX_0$ 收敛，
> 且极限 $u$ 在 $G$ 的每个连通分量上取常向量（「同分量坍缩」）。

**证明框架**（不完整，缺口见下）：

1. 由 T1，$S$ 在活节点上行随机，且 $S\ge0$。
2. 按连通分量分块，$S$ 是分块对角的（不同分量之间无超边相连）。
   每个块 $S_c$ 是非负、行随机矩阵。若分量连通，$S_c$ 不可约。
3. **Perron–Frobenius（不可约、行随机）**：$\rho(S_c)=1$，
   $1$ 是单重特征值，对应右特征向量 $\mathbf 1$；
   其余特征值满足 $|\mu|<1$。
4. 于是 $S_c^k\to \mathbf 1\,\pi_c^{\mathsf T}$，其中 $\pi_c$ 是平稳分布
   （$S_c$ 的左 Perron 向量，$\pi_c^{\mathsf T}S_c=\pi_c^{\mathsf T}$，
   归一化 $\sum_v(\pi_c)_v=1$）。收敛速率由第二大特征值模决定。
5. 因此 $M^kX_0\to u$，且 $u$ 在每个分量 $c$ 上等于
   $\mathbf 1\cdot(\pi_c^{\mathsf T}X_0^{(c)})$ —— **常向量**，源身份被抹平。

### ⚠️ 缺口（显式标出）

- 步骤 3 的「连通 ⇒ 不可约」需要先证明 $S_c$ 的不可约性与超图连通性等价。
  这一步**直观成立但不平凡**：超图连通 $\Rightarrow$ 关联二分图连通
  $\Rightarrow$ $S_c$ 的支撑图连通。需要小心处理「度 0 节点」与「空超边」
  （它们使 $S_c$ 出现零行，破坏不可约性）。**正确的陈述应把分量限制在活节点上。**
- 若分量内存在**孤立子结构**（例如某节点只属于一条只含它自己的超边），
  $S_c$ 仍可能可约，此时 $1$ 的重数 > 1，极限不唯一（但仍是某个平稳向量）。
- 项目实测的「同分量余弦」在 $layers=500$ 时 = $1.000000$，
  这是**渐近**陈述；$layers=2$ 时仅 $0.383$。**工作点未坍缩**，
  这一点项目已正确记录（`REPORT_exp-dynamics.md` §0 结论 1）。

**结论**：T4 的**数学内容正确**（非负行随机矩阵的经典收敛理论），
但形式化它需要 Mathlib 的 Perron–Frobenius 开发，作者**未能在本机确认
Mathlib 中该开发的现状**。这是一个**已知的、有意的**形式化缺口。

---

## 5. 定理 T5：可靠性因子的单调性（Tier 2 热身）

代码（`provenance.py::reliability_factor`）：

```python
floor = min(1.0, max(0.0, float(floor)))
r     = min(1.0, max(0.0, float(reliability)))
return floor + (1.0 - floor) * r
```

> **定理 T5.** 设 $f,r\in[0,1]$，$\varphi(r):=f+(1-f)r$。则
> 1. $\varphi(r)\in[f,1]$；
> 2. $\varphi$ 关于 $r$ 单调不减；
> 3. $f=1\Rightarrow\varphi\equiv1$。

**证明.**

(1) 下界：$1-f\ge0$，$r\ge0$，故 $(1-f)r\ge0$，$\varphi(r)=f+(1-f)r\ge f$。
上界：$r\le1$ 且 $1-f\ge0$，故 $(1-f)r\le1-f$，于是
$\varphi(r)\le f+(1-f)=1$。

(2) 对 $r_1\le r_2$：$\varphi(r_2)-\varphi(r_1)=(1-f)(r_2-r_1)\ge0$
（$1-f\ge0$，$r_2-r_1\ge0$）。故 $\varphi(r_1)\le\varphi(r_2)$。

(3) $f=1$ 时 $1-f=0$，$\varphi(r)=1+0\cdot r=1$。$\blacksquare$

**注**：Python 的 `min 1 ∘ max 0` 钳制使得**输入超界时**结论仍成立，
但 Lean 里把钳制作为假设更干净（本文件按假设表述）。若要对**任意**实数输入
证明，需先在 Lean 里定义 `clamp01` 并证 `clamp01 r ∈ [0,1]`。
项目表 M15 记录的「$\text{floor}=1.0$ → 恒 $1.0$（通道关闭）」对应 (3)。

---

## 6. 一处**真实的实现缺陷**：`_conv` 与 `propagation_matrix` 在成员重复时不等价

### 6.1 声明

`hgnn.py::propagation_matrix` 的 docstring 写：

> 与 `_conv` 的循环实现**逐元素等价**，供谱分析 / 单元测试使用。

**这个声明在成员重复时是假的。** 项目已知另一个反例（空 `he_members`，
见 `mathematics.md` D.6）；本节给出**第二个、独立的反例**，且它的
**前提条件在已发布数据中真实存在**。

### 6.2 机制

两个实现对「同一节点在一条超边中出现两次」的处理不同：

- **`_conv`**（循环）遍历 `he_members[j]`（一个 **list**）：
  ```python
  for i in members:          # 成员 1 出现两次 -> 循环体执行两次
      newX[i] += he_feat[j]; counts[i] += 1
  ```
  节点 $i$ 从超边 $j$ 收到 **2 份**贡献，同时 `counts[i]` 也**加了 2**。
  但**其他**超边 $j'$ 对 $i$ 的贡献也被除以这个被抬高的 `counts[i]`。
- **`propagation_matrix`**（矩阵）用 `H[i,j] = 1.0` **赋值**：
  ```python
  for i in members: H[i, j] = 1.0     # 赋两次，结果仍是 1.0
  ```
  重复被**静默折叠**为一次。$D_v(i)$ 因此偏小，$w_v(i)$ 偏大。

两者对 $i$ 的归一化分母不同 ⇒ 作用在 $X$ 上不同。

### 6.3 精确反例（符号计算，非浮点）

取 `he_members = [[1,1,2],[0,3]]`（4 个节点，节点 1 在超边 0 中重复），
$X=(a,b,c,d)$。用**精确有理数/符号算术**（sympy）算出两个算子的系数矩阵
（即 `newX = A @ X` 中的 $A$）：

| 节点 | `_conv` | `M@X` | 差 |
|---|---|---|---|
| 0 | $\frac34a+\frac14d$ | $\frac34a+\frac14d$ | $0$ |
| 1 | $\frac56b+\frac16c$ | $\frac34b+\frac14c$ | $\frac{1}{12}(b-c)$ |
| 2 | $\frac13b+\frac23c$ | $\frac14b+\frac34c$ | $\frac{1}{12}(b-c)$ |
| 3 | $\frac14a+\frac34d$ | $\frac14a+\frac34d$ | $0$ |

即两算子在节点 1、2 上**恰好相差 $\frac{b-c}{12}$**。
取 $X=(0,1,0,0)$ 即得具体反例：`_conv` 给节点 1 是 $\frac56$，
矩阵给 $\frac34$，差 $\frac{1}{12}\ne0$。

同一构造用浮点（`np.random` 的 $X$）复现：`max|_conv(X) - M@X| = 0.063850`。

**$S$ 的行随机性仍然成立**（实测 `row sums = [1,1,1,1]`）——
缺陷在算子的**作用**上，不在行和上。所以「行随机」测试**抓不到**它。

### 6.4 ⚠️ **一个必须承认的修正：重复本身不是充分条件**

作者在写 Lean 陈述时先写下「若某超边重复了成员，则两算子必然不同」，
**然后发现这个更强的陈述是假的**。穷举搜索（节点数 $\le3$、超边数 $\le2$、
所有含重复的成员列表组合）：

> **126 个含重复成员但两算子仍然一致的配置。**

最简单的：`he_members = [[0,0]]`（单节点、单超边、重复一次）。
此时 `_conv` 与矩阵形式**都**返回 $X_0$，完全一致。

原因：重复要造成分歧，必须**同时**满足两个条件 ——
(1) 该节点还属于**其他**超边（否则分母的膨胀被抵消），
且 (2) 存在**同超边内的另一节点**与它取值不同（否则分子无差异）。

**所以正确的陈述只能是存在性的**：

> **T6.** **存在**含重复成员的配置，使两算子不一致。

这正是 Lean 里 `conv_ne_matrix_of_duplicate_member` 的写法（$\exists$，不是 $\forall$）。
**这条经验本身值得记录**：如果按「重复 ⇒ 不等价」去写 Lean 陈述，
会得到一个**假命题**，而 `sorry` 会把它掩盖过去 —— 这正是
「陈述正确性」比「证明完整性」更重要的例证。

### 6.5 前提条件在已发布数据中存在（这条最要紧）

作者扫描了仓库内全部 JSON（7232 条含 `source_domain/target_domain/ground` 的记录）：

| 文件 | 重复成员记录数 / 总数 |
|---|---|
| `metaphor_graph/ontology_default.json` | **295 / 2177** |
| `metaphor_graph/llm_ontology_train.json` | **303 / 2185** |
| `release/metaphor_resources/ontology_default.json` | **295 / 2177** |
| `metaphor_graph/llm_ontology.json` | **106 / 656** |

典型例子（`llm_ontology.json`）：

```
('旅程','人生', ['旅程','终点'])   -> members = ['旅程','人生','旅程','终点']   # '旅程' 出现两次
('融化','状态', ['融化'])         -> members = ['融化','状态','融化']
('泥潭','困难', ['深陷','泥潭'])   -> members = ['泥潭','困难','深陷','泥潭']
```

成因是 `member_entities = [source_domain, target_domain] + ground`：
当 LLM 把源域（或目标域）同时写进 `ground` 时，该节点在成员列表中重复。
全仓库有 **988/7232（13.7%）** 的记录存在 `ground` 与 `source/target` 的重叠。

**当前的暴露面（已核实）**：`MetaphorSHGBuilder` 构造出的
`doc_project`（17 条边）与 `doc_relationship`（10 条边）中
**重复成员数为 0**，因此**本仓库当前跑出的谱数字未受此缺陷影响**。
但：

- 该缺陷**不是假设性的** —— 输入数据里就有；
- 任何把本体记录**直接**转成超边的路径（不经 builder 的去重）都会命中；
- 目前**没有测试**覆盖「重复成员」这一情形（现有测试只覆盖空 `he_members`）。

**注入实验（证明影响可达）**：在真实 SHG 上把 `source_domain` 追加进
`doc_project` 首条边的 `ground`：

```
edge0 members before: ['旅程','项目进展','起点','方向','障碍','里程碑','停滞']
edge0 members after : ['旅程','项目进展','起点','方向','障碍','里程碑','停滞','旅程']
max|_conv(X) - M@X| = 0.021478804657352135    # ≠ 0
```

即：一旦重复进入 SHG，偏差立刻出现。

### 6.6 建议

1. **修 docstring**：把「逐元素等价」限定为「在每条超边的成员互不重复时」。
2. **修实现（二选一）**：
   - 在 `_build_hyperedges` 里对 `members` 去重（`list(dict.fromkeys(...))`），
     使两个实现真正等价；或
   - 在 `_conv` 里也按集合语义处理（但会改变现有数字，需评估）。
3. **加测试**：构造一条含重复成员的 `he_members`，断言 `_conv(X) == M@X`。
   当前这个测试**不存在**，所以缺陷不会被 CI 抓到。
4. 注意 `health.py:141` 已经在**别处**做了去重（`dict.fromkeys`），
   说明项目**知道**要去重，只是 `hgnn.py` 的这条路径漏了。

---

## 7. 汇总：本文件证明了什么、没证明什么

| 编号 | 命题 | 非形式化证明 | 状态 |
|---|---|---|---|
| T1 | $S$ 行随机（活节点） | §1 完整 | ✅ 正确且完整 |
| T1' | 孤立节点行和为 0 | §1 完整 | ✅ 正确且完整 |
| T2a | $B$、$N$ 对称 | §2.1 完整 | ✅ 正确且完整 |
| T2b | $N$ 半正定（平方和形式） | §2.2 完整 | ✅ 正确且完整 |
| T2c | $D^{1/2}SD^{-1/2}=N$ | §2.3 完整 | ✅ 正确且完整 |
| T2 | 特征值 $\in[\frac12,1-\frac\varepsilon2]$ | §2.4 完整 | ✅ 正确且完整（**强于**项目文档的 $[0,1]$） |
| T3 | 不动点 $=(1-\alpha)(I-\alpha M)^{-1}X_0$ | §3.1 完整 | ✅ 正确且完整 |
| T3' | $\alpha\rho(M)<1\Rightarrow$ 可逆 | §3.2 完整 | ✅ 正确且完整 |
| T4 | $M^kX_0\to$ 分量常向量 | §4 **框架** | ⚠️ 缺口已标出（依赖 Perron–Frobenius） |
| T5 | 可靠性因子 $\in[f,1]$、单调、$f{=}1$ 关闭 | §5 完整 | ✅ 正确且完整 |
| T6 | **存在**含重复成员的配置使 `_conv` ≠ `propagation_matrix` | §6 机制+精确反例 | ✅ 正确且完整（**注意是存在性，不是「重复 ⇒ 不等价」**） |

### 本文件**没有**证明的

- **任何浮点/数值论断**。所有定理都是关于实数的精确命题；实测数字
  （$2\times10^{-16}$、`0.063850` 等）只作为**一致性检查**引用。
- **T4 的完整证明**（见 §4 缺口）。
- **`_conv` 在浮点下的逐位等价性**（即便去重后，浮点求和次序不同也可能
  产生 $10^{-16}$ 级差异；项目实测 `max|diff| = 5.6e-17`，这是浮点误差，
  不是数学不等）。

### 一条**修正过的**项目陈述

| 项目原文 | 位置 | 问题 | 正确表述 |
|---|---|---|---|
| 「$\alpha=1$ 无不动点」 | `convergence_check.py:190`、`hgnn.py` 附近注释 | **字面为假**（解空间 5 维，迭代确实收敛到其中一点） | 「$\alpha=1$ **不动点不唯一**（$I-\alpha M$ 奇异）」 |
| 「谱半径 $\rho(M_\varepsilon)\le1-\varepsilon/2$」 | `hgnn.py:47` | 不是错，但**可收紧为等式** | 「$\rho(M_\varepsilon)=1-\varepsilon/2$ **精确成立**」（§2.4c 已证） |
| 「特征值在 $[0,1]$」 | `mathematics.md` M18 | 不是错，但**未收紧** | 「特征值在 $[\frac12,1-\frac\varepsilon2]$」（§2.4 已证） |
| 「与 `_conv` 逐元素等价」 | `hgnn.py::propagation_matrix` docstring | **有第二个反例**（重复成员），且前提在数据中存在 | 「**在每条超边成员互不重复时**逐元素等价」 |

---

## 附：与 Lean 草稿的对应关系

| 本文件 | Lean 声明 | Lean 文件 |
|---|---|---|
| T1 | `Hypergraph.row_sum_S` | `MetaphorSHG/Spectral.lean` |
| T1' | `Hypergraph.row_sum_S_isolated` | 同上 |
| — | `Hypergraph.row_sum_M` / `row_sum_M_isolated` | 同上 |
| T2a | `Hypergraph.N_symmetric` | 同上 |
| T2b | `Hypergraph.N_posSemidef` | 同上 |
| T2c | `Hypergraph.S_conj_eq_N` | 同上 |
| T2 | `Hypergraph.eigenvalue_M_le` / `eigenvalue_M_ge` / `eigenvalue_M_mem_unit` | 同上 |
| T3 | `Hypergraph.fixed_point_eq` | 同上 |
| T3' | `Hypergraph.invertible_one_sub_smul_of_eigenvalue_bound` | 同上 |
| T4 | `Hypergraph.undriven_iteration_converges`（**占位，近乎空真**） | 同上 |
| T5 | `Hypergraph.reliabilityFactor_mem` / `_mono` / `_floor_one` | 同上 |
| T6 | `Hypergraph.conv_ne_matrix_of_duplicate_member` | 同上 |
| §3.3 修正 | `Hypergraph.alpha_one_not_invertible` | 同上 |

**Lean 侧的 `sorry` 数量与填写指引见 `README.md` 的状态表。**
