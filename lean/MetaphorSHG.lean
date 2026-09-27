/-
  MetaphorSHG.lean — 库入口。

  库 `MetaphorSHG` 包含三个模块：
    - `MetaphorSHG.Core`     仅依赖 Lean core，**已验证**（9 定理，0 sorry）
    - `MetaphorSHG.Basic`    依赖 Mathlib，超图与传播算子的形式化
    - `MetaphorSHG.Spectral` 依赖 Mathlib，谱性质与不动点

  注意：`lake build` 默认构建本文件（即全部三个模块）。
  若只想验证 Core，可 `lean MetaphorSHG/Core.lean`（无需 Mathlib）。
-/

import MetaphorSHG.Core
import MetaphorSHG.Basic
import MetaphorSHG.Spectral
