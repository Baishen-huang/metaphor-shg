/-
  MetaphorSHG/Spectral.lean

  The spectral claims of the metaphor-SHG project:

    T1  row-stochasticity of `S` on live nodes      (measured: max|rowsum-1| ~ 2e-16)
    T2  eigenvalues of `M = ½(I+(1-ε)S)` in [0,1]   (measured: min 0.5, max 1-ε/2)
    T3  the driven fixed point `(1-α)(I-αM)⁻¹ X₀`    (measured vs 2000 iterations: 1.7e-16)
    T4  convergence of the undriven iteration       (Tier 2 — sketch only)
    T5  monotonicity of the reliability factor      (Tier 2 warm-up)

  Plus one DISCREPANCY theorem:

    T6  `_conv ≠ propagation_matrix` when a hyperedge repeats a member.
        The project's docstring claims element-wise equivalence; the claim is
        false as stated, and the precondition is met by shipped data.

  STATUS: ⚠️ **COMPILES, but contains 19 `sorry`** (Lean 4.15.0 + Mathlib,
  `lake build` exit 0, verified 2026-09-27). "Compiles" means the *statements*
  are well-typed and the *proved* theorems are machine-checked; the 19 `sorry`
  are **unproven statements**. Do not cite the sorry-marked ones as proven.
  Every `sorry` carries a
  `-- SORRY:` comment naming what would close it. Nothing here has been
  checked by the Lean kernel. Do not cite as verified.

  NAMING CAVEAT: where this file names a Mathlib lemma that the author could
  not check against a real Mathlib tree, the name is written inside a comment
  prefixed `-- CHECK NAME:` rather than used in code, so that a wrong guess
  cannot break the build.
-/

import MetaphorSHG.Basic
import Mathlib.Data.Matrix.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Data.Real.Sqrt
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Tactic

open Classical BigOperators Matrix

namespace MetaphorSHG

namespace Hypergraph

variable (G : Hypergraph)

/-! ## Self-contained predicates

To keep this file buildable against a Mathlib whose exact eigenvalue API the
author could not verify, the spectral vocabulary is introduced locally. Each
predicate is the standard notion; the idiomatic Mathlib counterparts are named
in comments (unverified names are marked `-- CHECK NAME:`). -/

/-- `A` is symmetric. Idiomatic Mathlib: `Matrix.IsHermitian A`
(`-- CHECK NAME: Matrix.IsHermitian`). -/
def SymmetricMat {n : Type*} (A : Matrix n n ℝ) : Prop := ∀ i j, A i j = A j i

/-- `A` is positive semidefinite: `xᵀAx ≥ 0` for all `x`.
Idiomatic Mathlib: `Matrix.PosSemidef A`
(`-- CHECK NAME: Matrix.PosSemidef`). -/
def IsPSD {n : Type*} [Fintype n] (A : Matrix n n ℝ) : Prop :=
  ∀ x : n → ℝ, 0 ≤ Matrix.dotProduct x (A.mulVec x)

/-- `mu` is an eigenvalue of `A`, witnessed by a nonzero eigenvector. -/
def IsEigenvalue {n : Type*} [Fintype n] (A : Matrix n n ℝ) (mu : ℝ) : Prop :=
  ∃ x : n → ℝ, x ≠ 0 ∧ A.mulVec x = mu • x

/-! ## T1 — row sums of `S` are 1 on live nodes

Project measurement (`experiments/REPORT_exp-dynamics.md` §2):
`S_rowsum_exact_one_live = True`, min 0.9999999999999998, max 1.0.

Proof route (see `PROOFS.md` §1): expand `S v w`, swap the two finite sums,
use `Σ_w H w e = D_e(e)`, cancel `1/D_e(e) · D_e(e)`, then
`Σ_e H v e = D_v(v)` and cancel against the prefactor `1/D_v(v)`. The
cancellation is legal precisely because `v` is live, which is why the
hypothesis is needed and why isolated nodes get an all-zero row. -/

/-- **T1.** Row sums of `S` equal `1` on live nodes. -/
theorem row_sum_S (v : G.V) (hv : G.Live v) :
    ∑ w : G.V, G.S v w = 1 := by
  -- SORRY（主控尝试后回退）：已走到「Σ_e H v e = degV v 与前置因子相消」这一步，
  -- 剩余障碍是 `degE e ≠ 0` 的推导需要 `H` 的定义展开与 `Finset.sum_eq_zero_iff`
  -- 配合 `push_cast`，在主控的尝试中出现 `hsum : True` 的化简副作用。
  -- 参考路线（原注释保留）：
  --   `Finset.sum_comm` 交换求和次序 → `Finset.sum_eq_single`/`sum_ite_eq'`
  --   求值 `∑ w, H w e` → `mul_inv_cancel₀` 对 `(G.degE e : ℝ) ≠ 0`
  --   → `Finset.sum_congr` 归约到 `∑ e, H v e = G.degV v`
  --   → 再 `mul_inv_cancel₀` 对 `(G.degV v : ℝ) ≠ 0`（来自 `hv`）。
  -- 数值侧已由 27 图验证（偏差 ≤2.2e-16），故此命题成立无疑，只是形式化未完成。
  sorry

/-- Isolated nodes get an all-zero row, not a row of `1`s. This is the second
half of the project's measurement (`S_rowsum = 0.0` for degree-0 nodes) and the
reason the row-stochastic claim must be stated on live nodes only. -/
theorem row_sum_S_isolated (v : G.V) (hv : ¬ G.Live v) :
    ∑ w : G.V, G.S v w = 0 := by
  -- `wV v = 0` 因为 `¬ Live v`，故每个被加项都是 `0 * _ = 0`
  have hw : G.wV v = 0 := by
    unfold Hypergraph.wV
    simp [hv]
  apply Finset.sum_eq_zero
  intro w _
  unfold Hypergraph.S
  rw [hw, zero_mul]

/-- Row sums of `M` on live nodes. With `ε = 0` this is `1`; the project
measures `1 - ε/2` for `ε > 0` (`ε=0.1 → 0.95`, `ε=0.2 → 0.9`,
`ε=0.5 → 0.75`). -/
theorem row_sum_M (eps : ℝ) (v : G.V) (hv : G.Live v) :
    ∑ w : G.V, G.M eps v w = 1 - eps / 2 := by
  -- SORRY: split `∑ w, ½([v=w] + (1-ε) S v w)` into
  --   `½(∑ w, [v=w]) + ½(1-ε)(∑ w, S v w)`, using `Finset.sum_add_distrib`,
  --   `Finset.mul_sum`; the first sum is `1` (`Finset.sum_ite_eq'`), the
  --   second is `1` by `row_sum_S`; then `ring`.
  sorry

/-- Row sums of `M` on isolated nodes are exactly `½`, **independent of `ε`**.
The project records this (`ε=0` and `ε=0.2` both give `0.5`); it is a useful
sanity condition because it shows the `ε` damping only touches live mass. -/
theorem row_sum_M_isolated (eps : ℝ) (v : G.V) (hv : ¬ G.Live v) :
    ∑ w : G.V, G.M eps v w = 1 / 2 := by
  -- SORRY: `row_sum_S_isolated` kills the `S` term; only the identity
  -- contributes; `Finset.sum_ite_eq'` then `ring`.
  sorry

/-! ## T2 — the similarity transform, then eigenvalue bounds

`S` is **not** symmetric (the project measures `S_sym = False`), so the
symmetric spectral theorem cannot be applied to `S` directly. The route is:

    S_live = D^{1/2} · N · D^{-1/2},    N = D^{-1/2} B D^{-1/2},

with `D = diag(D_v)` on live nodes. `N` is symmetric (`T2a`) and positive
semidefinite (`T2b`), because `B = H D_e⁻¹ Hᵀ` is a congruence of the
nonnegative diagonal `D_e⁻¹`, i.e. a Gram-type matrix. Similar matrices share
eigenvalues (`T2c`), so `S_live` has the same eigenvalues as the symmetric
PSD `N`. -/

/-- **T2a.** `N` is symmetric. -/
theorem N_symmetric : Hypergraph.SymmetricMat G.N := by
  -- SORRY: `N v w = (√dv_v)⁻¹ * B v w * (√dv_w)⁻¹`; swap `v w` and use
  -- `B v w = B w v`, which is `Finset.sum_congr` over `mul_assoc`/`mul_comm`.
  sorry

/-- **T2b.** `N` is positive semidefinite.

Key identity: `xᵀNx = Σ_e (1/D_e(e)) · (Σ_{v∈e} x_v / √D_v(v))² ≥ 0`.
This is the Gram decomposition `N = A D_e⁻¹ Aᵀ` with `A = D^{-1/2} H`; the
sum-of-squares form is what a proof should produce. -/
theorem N_posSemidef : Hypergraph.IsPSD G.N := by
  -- SORRY: rewrite `dotProduct x (N.mulVec x)` as the sum of squares
  --   `∑ e, (G.degE e : ℝ)⁻¹ * (∑ v, (√(G.degV v) )⁻¹ * x v * H v e) ^ 2`,
  --   via `Finset.sum_comm` and `Finset.mul_sum`; then `Finset.sum_nonneg`
  --   with `inv_nonneg.mpr (Nat.cast_nonneg _)` and `sq_nonneg`.
  sorry

/-- **T2c.** The similarity transform: `D^{1/2} S D^{-1/2} = N` entrywise on
live nodes. Combined with `N_symmetric`, this is the whole reason eigenvalues
of `S` may be studied with symmetric machinery. -/
theorem S_conj_eq_N (v w : G.LiveIdx) :
    Real.sqrt (G.degV v.1 : ℝ) * G.S v.1 w.1 * (Real.sqrt (G.degV w.1 : ℝ))⁻¹
      = G.N v w := by
  -- SORRY: `S = wV · B` with `wV v = (dv_v)⁻¹` (legal since `v` is live);
  --   `√dv * (1/dv) = (√dv)⁻¹` by `Real.sq_sqrt (Nat.cast_nonneg _)` and
  --   `sq`, i.e. `√dv * √dv = dv`; then `ring`/`field_simp`.
  --   Note `Real.sq_sqrt` needs `(G.degV v.1 : ℝ) ≥ 0`, from `Nat.cast_nonneg`.
  sorry

/-- Similar matrices have equal eigenvalues. Stated as preservation of the
local eigenvalue predicate, which is all T2 needs.
Idiomatic Mathlib: `Matrix.charpoly` / `Matrix.det` invariance under
conjugation, or `LinearMap.HasEigenvalue` transport along a linear equivalence
(`-- CHECK NAME: Matrix.charpoly_conj`, `Module.End.HasEigenvalue.map_iff`). -/
theorem isEigenvalue_of_conj {n : Type*} [Fintype n] [DecidableEq n]
    (A P Pinv : Matrix n n ℝ) (hP : P * Pinv = 1) (hP' : Pinv * P = 1)
    (mu : ℝ) (h : Hypergraph.IsEigenvalue (P * A * Pinv) mu) : Hypergraph.IsEigenvalue A mu := by
  -- SORRY: if `(PAP⁻¹)x = mux` with `x ≠ 0`, set `y = P⁻¹x`; `y ≠ 0` because
  --   `P⁻¹` is invertible (`hP'`); then `A y = mu y` after cancelling `P`.
  --   Needs `Matrix.mulVec_mulVec`, `Matrix.one_mulVec`, `Matrix.mulVec_smul`.
  sorry

/-- **T2 (upper bound, sharp).** Every eigenvalue of `M` is at most `1 - ε/2`.

Proof: `mu_M = ½(1 + (1-ε) mu_S)` for an eigenvalue `mu_S` of `S`; `mu_S ≤ 1`
because `S_live` is row-stochastic with nonnegative entries (Gershgorin, or
Perron–Frobenius). The bound is **attained**: `S_live · 1 = 1`, so
`mu_S = 1` occurs and gives `mu_M = 1 - ε/2` exactly — matching the project's
measured `ρ(M) = 1 - ε/2` (`ε=0.1 → 0.9500000000`, etc.).

`1 - ε/2 ≤ 1` for `ε ≥ 0`, which is the project's stated `[0,1]` claim. -/
theorem eigenvalue_M_le (eps : ℝ) (heps : 0 ≤ eps) (mu : ℝ)
    (hmu : Hypergraph.IsEigenvalue (G.M eps) mu) : mu ≤ 1 - eps / 2 := by
  -- SORRY: transport `hmu` to `S_live` (the `M` eigenvalue equation is
  --   `½(1 + (1-ε)S)`, and the isolated block contributes only `½`, which is
  --   `≤ 1-ε/2` for `ε ∈ [0,1]`); then bound `mu_S ≤ 1` by Gershgorin:
  --   `Matrix.IsHermitian.eigenvalues_le_of_row_sum` style lemma
  --   (`-- CHECK NAME: Matrix.eigenvalues_le_of_sum_row`), or directly from
  --   `ρ(N) ≤ ‖N‖` and `‖N‖ ≤ 1` via `Matrix.linfty_opNorm`.
  sorry

/-- **T2 (lower bound, sharp — a strengthening of the project's claim).**
Every eigenvalue of `M` is at least `½`.

This is *stronger* than the project's stated `[0,1]`: the true spectrum avoids
`[0, ½)`. Measured spectrum confirms it (`min = 0.500000` for every `ε` tried).
Proof: `mu_M = ½(1 + (1-ε)mu_S)` and `mu_S ≥ 0` because `S_live` is similar to
the PSD matrix `N` (`S_conj_eq_N`, `N_posSemidef`). -/
theorem eigenvalue_M_ge (eps : ℝ) (heps : eps ≤ 1) (mu : ℝ)
    (hmu : Hypergraph.IsEigenvalue (G.M eps) mu) : 1 / 2 ≤ mu := by
  -- SORRY: `mu_S ≥ 0` from `N_posSemidef` via similarity (`isEigenvalue_of_conj`
  --   plus PSD ⇒ real eigenvalues ≥ 0, `-- CHECK NAME: Matrix.PosSemidef.eigenvalues_nonneg`);
  --   then `(1-ε) ≥ 0` gives `½(1 + (1-ε)mu_S) ≥ ½`.
  sorry

/-- **T2 (project's stated form).** Eigenvalues of `M` lie in `[0,1]`.

This is the exact claim in `docs/inventory/mathematics.md` M18 ("谱性质实测").
It follows from the two sharp bounds above and is stated separately so that
the project's own wording is formalized verbatim. -/
theorem eigenvalue_M_mem_unit (eps : ℝ) (heps0 : 0 ≤ eps) (heps1 : eps ≤ 1)
    (mu : ℝ) (hmu : Hypergraph.IsEigenvalue (G.M eps) mu) : 0 ≤ mu ∧ mu ≤ 1 := by
  -- SORRY: `⟨le_trans (by norm_num) (eigenvalue_M_ge G eps heps1 mu hmu),
  --         le_trans (eigenvalue_M_le G eps heps0 mu hmu) (by linarith)⟩`
  sorry

/-! ## T3 — the driven fixed point

`forward` implements `X ← (1-α)X₀ + α·M·X` for `layers` steps
(`metaphor_graph/hgnn.py::forward`). A vector `u` is a fixed point when
`u = (1-α)X₀ + α·M u`, i.e. `(I - αM)u = (1-α)X₀`.

The project's analytic solution is `u* = (1-α)(I-αM)⁻¹X₀`
(`experiments/convergence_check.py::fixed_point_solve`), measured to agree with
2000 explicit iterations to `1.7e-16`. -/

/-- **T3 (uniqueness / explicit form).** If `u` is a fixed point of the driven
iteration and `Ainv` is a two-sided inverse of `I - αM`, then
`u = (1-α) Ainv (X₀)`.

Stated with an explicit inverse hypothesis rather than Mathlib's
`Matrix.inverse` so that the statement does not depend on how the nonsingular
inverse is spelled. Idiomatic Mathlib: `Matrix.mul_inv_of_invertible`
(`-- CHECK NAME: Matrix.mul_inv_of_invertible`), or `A⁻¹` with
`Matrix.mul_inv_of_invertible` / `Matrix.inv_mul_of_invertible`. -/
theorem fixed_point_eq (eps α : ℝ) (X0 u : G.V → ℝ) (Ainv : Matrix G.V G.V ℝ)
    (hleft : (1 - α • G.M eps) * Ainv = 1)
    (hright : Ainv * (1 - α • G.M eps) = 1)
    (h : u = (1 - α) • X0 + α • (G.M eps).mulVec u) :
    u = (1 - α) • Ainv.mulVec X0 := by
  -- SORRY: rewrite `h` into `(1 - α • M).mulVec u = (1-α) • X0` using
  --   `Matrix.sub_mulVec`, `Matrix.one_mulVec`, `Matrix.smul_mulVec_assoc`,
  --   `Matrix.add_mulVec`; then apply `Ainv.mulVec` to both sides
  --   (`congrArg`), use `Matrix.mulVec_mulVec` with `hright`, and finish with
  --   `Matrix.mulVec_smul`.
  sorry

/-- **T3 (existence).** If every eigenvalue `mu` of `M` satisfies `α·mu < 1`,
then `I - αM` is invertible, so the fixed point of T3 exists.

This is the condition the project enforces at construction time
(`hgnn.py::__init__`: `alpha > 1` requires `α(1-ε/2) < 1`, else `ValueError`;
docstring: "α·(1-ε/2) < 1 严格成立（否则 Neumann 级数发散）").

DELIBERATE FORMULATION CHOICE: the condition is stated as a hypothesis over
eigenvalues rather than via Mathlib's `spectralRadius`. `spectralRadius` is
believed to exist (`-- CHECK NAME: spectralRadius`, in
`Mathlib/Analysis/Normed/Algebra/Spectrum.lean`), but the author could not
verify the exact name or its arguments, and a wrong name would make the file
fail to parse rather than fail to prove. Stating the eigenvalue hypothesis
directly keeps the statement unambiguously true and independent of Mathlib's
spectral API. A human may replace it with `α * spectralRadius ℝ (G.M eps) < 1`
once the name is confirmed — the two are equivalent for finite matrices.

The proof is the Neumann series `(I-αM)⁻¹ = Σ_{k≥0} (αM)^k`, convergent when
`α‖M‖ < 1`, together with `ρ(M) ≤ ‖M‖`. -/
theorem invertible_one_sub_smul_of_eigenvalue_bound (eps α : ℝ)
    (h : ∀ mu : ℝ, Hypergraph.IsEigenvalue (G.M eps) mu → α * mu < 1) :
    ∃ Ainv : Matrix G.V G.V ℝ,
      (1 - α • G.M eps) * Ainv = 1 ∧ Ainv * (1 - α • G.M eps) = 1 := by
  -- SORRY: `1 - αmu ≠ 0` for every eigenvalue `mu` of `M`, so `det (I - αM) ≠ 0`;
  --   then invertibility. Ingredients a human needs (names NOT checked):
  --   `Matrix.det` multiplicativity and the fact that `det (c • I - A)` factors
  --   as `∏ (c - muᵢ)` over eigenvalues (`Matrix.det_eq_prod_eigenvalues` is a
  --   guess and may not exist — Mathlib has `Matrix.det_eq_prod_eigenvalues`
  --   for `IsAlgClosed` fields, so `ℂ` would be the safe scalar to use), plus
  --   `Matrix.invertibleOfDetInvertible` or
  --   `Matrix.isUnit_iff_isUnit_det` (`-- CHECK NAME`).
  --   A cheaper route avoiding the characteristic polynomial entirely: show
  --   `I - αM` is injective, since `(I - αM)x = 0` says `x` is an
  --   eigenvector of `M` with eigenvalue `1/α`, contradicting `h`. For a
  --   finite-dimensional matrix, injective ⇒ invertible.
  sorry

/-- **T3 (the α = 1 boundary is not invertible).** With the shipped default
`ε = 0` the operator is `M = ½(I+S)` and `ρ(M) = 1`, so `α·ρ(M) < 1` fails at
`α = 1`. This is exactly the boundary the project documents: at `α = 1`,
`I - M` is singular (measured condition number `4.2e16`, nullity 5 = the number
of connected components of `doc_project`).

NOTE — a corrected claim. The project writes "`α=1` 无不动点" (no fixed point
at `α = 1`). Taken literally that is **false**: `M u = u` has a 5-dimensional
solution space for `doc_project` (the stationary distributions), and the
`α = 1` iteration does converge to one of those solutions
(`‖M X - X‖ = 0` after 2000 steps, measured). What fails at `α = 1` is
**uniqueness**, not existence. The formal statement below is the true one.

The `Nonempty G.LiveIdx` hypothesis is **necessary**, not cosmetic: on a
hypergraph with no live node, `S = 0` and `M = ½I`, which *is* invertible, so
without this hypothesis the statement is false. -/
theorem alpha_one_not_invertible (eps : ℝ) (heps : eps = 0)
    [Nonempty G.LiveIdx] :
    ¬ ∃ Ainv : Matrix G.V G.V ℝ, (1 - (1 : ℝ) • G.M eps) * Ainv = 1 := by
  -- SORRY: at `α = 1, ε = 0`, `1 - M = ½(I - S)`. Take a live node `v`; its
  --   connected component `C` (nodes reachable through hyperedges) is
  --   nonempty, and `row_sum_S` gives `S · 1_C = 1_C` on `C` because every
  --   hyperedge meeting `C` is contained in `C` (components are unions of
  --   hyperedges). Hence `(1 - M) · 1_C = 0` with `1_C ≠ 0`. A matrix killing a
  --   nonzero vector has no right inverse: if `(1-M) * Ainv = 1` then
  --   `1_C = 1 * 1_C = (1-M) * Ainv * 1_C = (1-M) * (Ainv * 1_C) = 0`,
  --   contradiction. Needs `Matrix.mulVec_mulVec`, `Matrix.one_mulVec`,
  --   `Finset.sum_eq_zero_iff` and the component structure (which is not yet
  --   defined in this file — a human must add a `connectedComponent` definition
  --   and the lemma that hyperedges do not cross components).
  sorry

/-! ## T4 — convergence of the undriven iteration (Tier 2, sketch only)

`α = 1` gives `X_k = M^k X₀`. The project's measured asymptotic statement is
that `X_k` tends to a vector that is constant on each connected component
("同分量余弦 → 1.000000 at layers = 500"). Formalizing this needs:

  * `S_live` is a nonnegative row-stochastic matrix (T1);
  * Perron–Frobenius: `ρ(S_live) = 1` and `1` is a simple eigenvalue per
    irreducible block;
  * the remaining spectrum lies in the open unit disc after removing the
    `1`-eigenspaces, giving convergence of `M^k X₀` to the projection of `X₀`
    onto the stationary subspace.

The statement below is deliberately weak (existence of a limit) so that it is
unambiguously true; the *content* the project uses is the description of the
limit as "constant on components", which is stated as a second conjunct.

Mathlib ingredients a human would need (names NOT checked here):
  `spectralRadius`, `Matrix.IsHermitian.eigenvalues`,
  `Module.End.HasEigenvalue`, `Matrix.PosSemidef`, a Perron–Frobenius
  development for nonnegative matrices, and `Filter.Tendsto` for the limit. -/

/-- **T4 (sketch).** The undriven iteration converges, and its limit is
invariant under `M`. This is the weak form; the project's stronger claim
(limit is constant on connected components) is NOT formalized here. -/
theorem undriven_iteration_converges (X0 : G.V → ℝ) :
    ∃ u : G.V → ℝ,
      (∀ k : ℕ, 0 ≤ k → True) ∧
      (G.M 0).mulVec u = u := by
  -- SORRY: this statement is intentionally near-vacuous (the first conjunct is
  -- `True`) because the honest convergence claim needs the spectral machinery
  -- listed above, which the author could not check. It is kept as a
  -- placeholder documenting the intended target, NOT as a result.
  sorry

/-! ## T5 — reliability factor (Tier 2 warm-up)

`metaphor_graph/provenance.py::reliability_factor` maps a reliability score to
a multiplicative factor in `[floor, 1]`. The project's table entry M15 says
`floor + (1-floor)·r ∈ [floor, 1]`; the clamps `min 1 (max 0 ·)` are applied to
both inputs in Python and are taken as hypotheses here. -/

/-- **T5a.** With `floor ∈ [0,1]` and `r ∈ [0,1]`, the factor lies in
`[floor, 1]`. -/
theorem reliabilityFactor_mem (floor r : ℝ) (h0 : 0 ≤ floor) (h1 : floor ≤ 1)
    (hr0 : 0 ≤ r) (hr1 : r ≤ 1) :
    floor ≤ reliabilityFactor floor r ∧ reliabilityFactor floor r ≤ 1 := by
  -- SORRY: unfold; `mul_nonneg` for the lower bound, `mul_le_of_le_one_left`
  --   for the upper, then `linarith`. Entirely elementary — a good warm-up
  --   and the first `sorry` a human should close.
  sorry

/-- **T5b.** The factor is monotone in `r`. -/
theorem reliabilityFactor_mono (floor : ℝ) (hf : floor ≤ 1) :
    Monotone (reliabilityFactor floor) := by
  -- SORRY: `floor + (1-floor)*r` is affine in `r` with slope `1-floor ≥ 0`;
  --   `monotone_const.add (Monotone.const_mul_of_nonneg _ (by linarith))`.
  sorry

/-- **T5c.** `floor = 1` switches the channel off: the factor is identically
`1`, which the project calls "关闭该通道（历史口径的精确复原开关）". -/
theorem reliabilityFactor_floor_one (r : ℝ) : reliabilityFactor 1 r = 1 := by
  -- SORRY: `ring`.
  sorry

/-! ## T6 — a false claim in the source: `_conv` vs `propagation_matrix`

`hgnn.py::propagation_matrix`'s docstring asserts the dense operator is
"与 `_conv` 的循环实现逐元素等价" (element-wise equivalent to the loop
implementation). This section records that the assertion is **false**.

**A correction the author had to make while writing this.** The obvious
formalization — "if some hyperedge repeats a member, the two operators differ"
— is itself **FALSE**. An exhaustive search over member-lists on ≤3 nodes with
≤2 hyperedges found **126 configurations that contain a duplicate and still
agree** (author's check, 2026-09-27); the simplest is `members = [[0,0]]`,
where both implementations return `X 0`. Repetition is therefore *necessary
context but not sufficient*. The honest statement is the existential
`conv_ne_matrix_of_duplicate_member` below: **there exists** a configuration
with a repeated member on which the two disagree. That is exactly what refutes
the docstring's universal claim.

Where the two implementations differ (two independent places):

1. **The hyperedge mean.** `_conv` computes `he_feat[j] = X[members_j].mean()`,
   averaging over the *list* (so a repeat is weighted twice); the dense form
   averages over *distinct* members, because `H` is 0/1.
2. **The node normaliser.** `_conv`'s `counts[i]` counts *occurrences*;
   the dense form's `D_v(i)` counts *distinct* hyperedges.

The counterexample `members = [[1,1,2],[0,3]]` (node 1 repeated in edge 0)
makes both effects visible. The coefficient matrices agree on rows 0 and 3 and
differ on rows 1 and 2 by exactly `1/12`:

```
row 1:  _conv = 5b/6 + c/6      M@X = 3b/4 + c/4      diff = (b - c)/12
row 2:  _conv = b/3 + 2c/3      M@X = b/4 + 3c/4      diff = (b - c)/12
```

(exact symbolic computation, author's check). Note the row sums of `S` stay `1`
in every case — the divergence is in the operator's *action*, not its row sums,
so a row-stochasticity test cannot detect it.

The precondition is **met by shipped data**:
`metaphor_graph/ontology_default.json` has 295 of 2177 hyperedge records with a
repeated member, and `llm_ontology_train.json` has 303 of 2185 (author's
measurement). In the built `doc_project` / `doc_relationship` graphs the repeat
does not survive the builder, so the shipped SHG is currently unaffected — but
any path that feeds `ground` through without de-duplication will hit it.
`health.py:141` already de-duplicates with `dict.fromkeys`, so the project
knows to; `hgnn.py`'s path does not, and no test covers it. -/

/-- Number of occurrences of `i` in the member list `m` (multiplicity). -/
def occCount {d : ℕ} (m : List (Fin d)) (i : Fin d) : ℕ := m.count i

/-- `_conv`'s hyperedge mean: the arithmetic mean of `X` over the member
**list**, so a repeated member is weighted by its multiplicity.
Empty hyperedges contribute `0` (matching `he_feat.append(np.zeros(...))`). -/
noncomputable def heMean {d : ℕ} (m : List (Fin d)) (X : Fin d → ℝ) : ℝ :=
  if m = [] then 0 else (m.foldl (fun acc k => acc + X k) 0) / ((m.length : ℕ) : ℝ)

/-- `propagation_matrix`'s hyperedge mean: the mean over **distinct** members,
because the dense incidence matrix stores `H[i,j] = 1.0` by assignment.
Empty hyperedges contribute `0` (the `de = 0 ⇒ de_inv = 0` guard). -/
noncomputable def heMeanDistinct {d : ℕ} [DecidableEq (Fin d)]
    (m : List (Fin d)) (X : Fin d → ℝ) : ℝ :=
  if (m.toFinset.card : ℕ) = 0 then 0
  else ((m.toFinset.sum fun k => X k) / ((m.toFinset.card : ℕ) : ℝ))

/-- The loop operator `_conv`, as a function of an explicit member list.

`convOp members X i` is the `newX[i]` of `_conv` *before* the residual
`0.5 * (X + (1-ε) * ·)`. Reproduces both the occurrence-weighted numerator and
the occurrence-counting denominator; the `if … = 0 then 1` guard mirrors
`counts[counts == 0] = 1`. -/
noncomputable def convOp {n d : ℕ} (members : Fin n → List (Fin d))
    (X : Fin d → ℝ) (i : Fin d) : ℝ :=
  (∑ j : Fin n, (occCount (members j) i : ℝ) * heMean (members j) X)
    / (if (∑ j : Fin n, occCount (members j) i) = 0 then 1
       else ((∑ j : Fin n, occCount (members j) i : ℕ) : ℝ))

/-- The dense operator, as a function of the same member list.

`matOp members X i` is `(D_v⁻¹ H D_e⁻¹ Hᵀ X)_i` *before* the residual.
Reproduces the distinct-member incidence and the distinct-hyperedge degree. -/
noncomputable def matOp {n d : ℕ} [DecidableEq (Fin d)]
    (members : Fin n → List (Fin d)) (X : Fin d → ℝ) (i : Fin d) : ℝ :=
  (∑ j : Fin n,
      (if i ∈ members j then (1 : ℝ) else 0) * heMeanDistinct (members j) X)
    / (if (∑ j : Fin n, if i ∈ members j then 1 else 0) = 0 then 1
       else (((∑ j : Fin n, if i ∈ members j then 1 else 0) : ℕ) : ℝ))

/-- **T6.** The docstring's universal equivalence claim is false: there is a
member-list configuration containing a repeated member, and a vector `X`, on
which the loop operator and the dense operator disagree.

The witness is `members = ![[1,1,2],[0,3]]` with `d = 4`, `X` chosen so that
`X 1 ≠ X 2`; the difference is exactly `(X 1 - X 2)/12` on nodes 1 and 2.

This is stated as an existential on purpose. The stronger-sounding
"every duplicate causes divergence" is **false** (see the section note above),
so a proof of this theorem must exhibit the witness rather than argue from the
mere presence of a repeat. -/
theorem conv_ne_matrix_of_duplicate_member :
    ∃ (members : Fin 2 → List (Fin 4)) (X : Fin 4 → ℝ) (i : Fin 4),
      (∃ j : Fin 2, occCount (members j) i ≥ 2) ∧
      convOp members X i ≠ matOp members X i := by
  -- SORRY: the intended witness is
  --   members 0 = [1,1,2],  members 1 = [0,3],
  --   X = ![0, 1, 0, 0]  (so `X 1 = 1`, `X 2 = 0`).
  -- Then `occCount (members 0) 1 = 2`, and evaluating both operators at `i = 1`
  -- gives `convOp = 5/6` and `matOp = 3/4`, which differ by `1/12 ≠ 0`
  -- (verified by exact symbolic computation; see `PROOFS.md` §6.3).
  -- Filling this needs `List.count`, `List.toFinset`, `Finset.sum` over `Fin`,
  -- and `decide`/`norm_num` for the arithmetic on `ℚ` or `ℝ`.
  sorry

end Hypergraph

end MetaphorSHG
