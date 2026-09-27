> # ⚠️ 本文结论已被推翻（2026-09-27）
>
> 标题与结论「Lean 无法在本机安装」**是错的**。主控后续发现
> **`ghproxy.net` 代理可用**（~330 KB/s）与**系统代理 `127.0.0.1:7890` 可用**，
> 据此**成功安装了 Lean 4.15.0 并编译通过了 `lean/MetaphorSHG/Core.lean`**
> （9 条定理，0 错误 0 `sorry`）。
>
> 本文保留作为**排查过程记录**与**失败路径清单**（哪些镜像不可用、为什么），
> 但**不要引用本文的结论**。权威状态见 `lean_formalization.md`。
>
> 唯一仍成立的限制：**Mathlib 预编译缓存**因 ProofWidgets 的 GitHub release
> 不可达而获取失败，故依赖 Mathlib 的两个文件仍未编译。

---

# （已过时）环境约束记录：Lean 无法在本机安装

> 记录日期：2026-09-27
> 用途：为 `lean/` 目录下的形式化草稿提供**无法编译验证**的证据，避免后人误以为
> 这些文件已被 Lean 检查过。

---

## 1. 结论

**Lean 4 工具链无法在本机安装**，因此 `lean/` 下的文件是**形式化草稿**
（`sorry` 未填、未编译），不是已验证的证明。

## 2. 逐条验证记录

| 路径 | 命令/URL | 结果 |
|---|---|---|
| 已有安装 | `which lean lake elan` | 均未找到 |
| 全盘搜索 | `find /c/Users/huang /d/self /e/soft "/c/Program Files" -maxdepth 4 -iname "lean.exe" -o -iname "lake.exe"` | 空 |
| 官方安装脚本 | `https://leanprover-community.github.io/install/elan-init.sh` | 返回 HTML（非脚本），不可用 |
| GitHub Releases（elan） | `https://github.com/leanprover/elan/releases/...zip` | `curl (28) Failed to connect to github.com port 443` |
| GitHub 主页 | `https://github.com` | `curl (56) Recv failure: Connection was reset` |
| 清华镜像 | `https://mirrors.tuna.tsinghua.edu.cn/github-release/leanprover/elan/` | **404** |
| 交大镜像 | `https://mirror.sjtu.edu.cn/github-release/leanprover/elan/` | **301 → 重定向回 github.com**（仍被阻断） |
| Docker | `docker version` | daemon 未运行（`npipe:////./pipe/dockerDesktopLinuxEngine` 不存在） |
| conda | `conda search -c conda-forge lean4` | 无 `lean4` 包（只有无关的 `tclean`） |
| PyPI | `pip download lean4` | **可下载**，但解包后仅含 `.py` 包装（`lean4-1.0.0/lean/Init/Data/Int/Basic.py` 等），**无编译器二进制**（`grep -ci "bin/\|\.exe\|toolchain"` = 0） |

## 3. 关键判断

Lean 的**编译器二进制**只从 GitHub Releases 分发（elan 与 toolchain 皆然）。
本机 GitHub 被网络阻断，而所有可用镜像要么 404、要么重定向回 GitHub。
PyPI 上的 `lean4` 是无关的 Python 包，不含编译器。

**因此：任何声称"已用 Lean 验证"的说法在本机都不成立。**

## 4. 补救路径（供有网络的环境执行）

```bash
# 1) 安装 elan（需 GitHub 可达）
curl -sSfL https://github.com/leanprover/elan/releases/latest/download/elan-x86_64-unknown-linux-gnu.tar.gz | tar xz
./elan-init -y --default-toolchain none
source ~/.profile

# 2) 在 lean/ 目录下获取 toolchain 与 Mathlib
cd lean
lake exe cache get      # 拉取 Mathlib 预编译缓存（关键：否则编译要数小时）
lake build

# 3) 检查 sorry 残留
grep -rn "sorry" MetaphorSHG/*.lean
```

## 5. 本机可做的替代验证

既然 Lean 不可用，`lean/PROOFS.md` 提供**完整的中文非形式化证明**，
可由人直接阅读核验。此外 `math/spectral` 分支用 **sympy 符号计算 + 数值验证**
交叉检验了同一批命题（见 `docs/math/spectral.md`）。

**三者的证据强度排序**：Lean 编译通过 > 完整非形式化证明（可人工核验）>
数值验证（只覆盖有限实例）。

当前本机只能做到后两者。
