/-
  MetaphorSHG/Basic.lean

  Incidence structure of the metaphor hypergraph, and the propagation
  operators `S` and `M` that the project's spectral analysis is built on.

  SOURCE OF TRUTH (Python, `main` branch, 2026-09-27):
    - `metaphor_graph/hgnn.py::_build_hyperedges`  — how `he_members` is built
    - `metaphor_graph/hgnn.py::_conv`              — the loop form
    - `metaphor_graph/hgnn.py::propagation_matrix` — the dense form
    - `experiments/_common.py::{incidence,S_matrix,M_matrix}`

  STATUS: UNVERIFIED DRAFT — see `README.md`. Every `sorry` is marked with a
  `-- SORRY:` comment naming what would close it. Do not cite as verified.
-/

import Mathlib.Data.Matrix.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Data.Real.Sqrt
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.LinearAlgebra.Matrix.Notation
import Mathlib.Tactic

open Classical BigOperators Matrix

namespace MetaphorSHG

/-! ## 1. The hypergraph

We model the *mathematical* object: a Boolean incidence relation, so a node is
either in a hyperedge or not. Multiplicity is deliberately NOT modelled.

This matters. The Python `he_members` is a `List[List[int]]`, and the shipped
ontology files do repeat a member inside one hyperedge
(`ontology_default.json`: 295 of 2177 records; `llm_ontology_train.json`:
303 of 2185). In that situation the loop implementation `_conv` (which counts
the repeat twice) and the dense implementation `propagation_matrix` (which
cannot) disagree. See `Spectral.lean::conv_ne_matrix_of_duplicate_member`.
-/

structure Hypergraph where
  V : Type*
  [fintypeV : Fintype V]
  [decEqV : DecidableEq V]
  E : Type*
  [fintypeE : Fintype E]
  [decEqE : DecidableEq E]
  /-- `inc v e` is `true` iff node `v` is a member of hyperedge `e`. -/
  inc : V → E → Bool

attribute [instance] Hypergraph.fintypeV Hypergraph.decEqV
attribute [instance] Hypergraph.fintypeE Hypergraph.decEqE

namespace Hypergraph

variable (G : Hypergraph)

/-- Node degree `D_v(v) = Σ_e inc v e`. Isolated nodes have degree `0`. -/
noncomputable def degV (v : G.V) : ℕ :=
  ∑ e : G.E, if G.inc v e then 1 else 0

/-- Hyperedge cardinality `D_e(e) = Σ_v inc v e`. Empty hyperedges have size `0`. -/
noncomputable def degE (e : G.E) : ℕ :=
  ∑ v : G.V, if G.inc v e then 1 else 0

/-- A node is *live* when it belongs to at least one hyperedge.

This is the project's `dv > 0` mask. The measured "row-stochastic" property
holds exactly on live nodes; isolated nodes get an all-zero row. -/
def Live (v : G.V) : Prop := G.degV v ≠ 0

/-- The incidence matrix `H`, entries `1` / `0` in `ℝ`. -/
noncomputable def H : Matrix G.V G.E ℝ :=
  fun v e => if G.inc v e then 1 else 0

/-- The guarded reciprocal of the hyperedge cardinality: `1/|e|`, or `0` for an
empty hyperedge. Mirrors `np.where(de > 0, 1/de, 0)`. -/
noncomputable def wE (e : G.E) : ℝ :=
  if G.degE e ≠ 0 then ((G.degE e : ℝ))⁻¹ else 0

/-- The guarded reciprocal of the node degree: `1/D_v`, or `0` for an isolated
node. Mirrors `np.where(dv > 0, 1/dv, 0)`. -/
noncomputable def wV (v : G.V) : ℝ :=
  if G.Live v then ((G.degV v : ℝ))⁻¹ else 0

/-! ## 2. The propagation operators

Python (`propagation_matrix`):

    S = (dv_inv[:, None] * H) @ (de_inv[:, None] * H.T)
    M = 0.5 * (np.eye(n) + (1 - leak) * S)

Entrywise that is `S = D_v⁻¹ · B` and `M = ½(I + (1-ε)S)`, where
`B = H D_e⁻¹ Hᵀ` is the *symmetric* weighted co-occurrence matrix. Splitting
`B` out is what makes the eigenvalue argument work: `B` is a Gram matrix, hence
positive semidefinite. -/

/-- `B = H D_e⁻¹ Hᵀ`, the symmetric weighted incidence Gram matrix.

`B v w = Σ_e [v ∈ e] · (1/|e|) · [w ∈ e]`.

This is the symmetric core of `S`. Python never materialises it, but
`D_v^{1/2} S D_v^{-1/2} = D_v^{-1/2} B D_v^{-1/2}`, so `S` is *similar* to a
symmetric matrix. -/
noncomputable def B : Matrix G.V G.V ℝ :=
  fun v w => ∑ e : G.E, G.H v e * G.wE e * G.H w e

/-- `S = D_v⁻¹ H D_e⁻¹ Hᵀ = D_v⁻¹ B`. The project's propagation operator.

Note `S` is **not symmetric** in general (the project records this:
`S_sym = False`), and its row sums are `1` exactly on live nodes
(`Spectral.lean::row_sum_S`). -/
noncomputable def S : Matrix G.V G.V ℝ :=
  fun v w => G.wV v * G.B v w

/-- `M_ε = ½ (I + (1-ε) S)`. The project's `_conv` / `propagation_matrix`
operator with `leak = ε`.

`eps = 0` is the shipped default; `eps > 0` is the "strictly substochastic
damping" channel. -/
noncomputable def M (eps : ℝ) : Matrix G.V G.V ℝ :=
  fun v w => (1 / 2) * ((if v = w then 1 else 0) + (1 - eps) * G.S v w)

/-- The live-node index type. Restricting to live nodes removes the singular
`D_v` block; this is the index set on which `S` is row-stochastic and on which
the symmetric similarity transform is invertible. -/
def LiveIdx : Type _ := {v : G.V // G.Live v}

noncomputable instance : Fintype G.LiveIdx := by
  unfold LiveIdx; infer_instance

instance : DecidableEq G.LiveIdx := by
  unfold LiveIdx; infer_instance

/-- `S` restricted to live nodes. -/
noncomputable def S_live : Matrix G.LiveIdx G.LiveIdx ℝ :=
  fun v w => G.S v.1 w.1

/-- `M` restricted to live nodes. -/
noncomputable def M_live (eps : ℝ) : Matrix G.LiveIdx G.LiveIdx ℝ :=
  fun v w => G.M eps v.1 w.1

/-- The symmetric matrix `N = D_v^{-1/2} B D_v^{-1/2}` (live nodes only).

`N` is symmetric, and `S_live = D_v^{1/2} N D_v^{-1/2}` is similar to it, so
`S_live` and `N` have the same eigenvalues. This is the bridge from the
non-symmetric `S` to the spectral theorem for symmetric matrices. -/
noncomputable def N : Matrix G.LiveIdx G.LiveIdx ℝ :=
  fun v w => (Real.sqrt (G.degV v.1 : ℝ))⁻¹ * G.B v.1 w.1 * (Real.sqrt (G.degV w.1 : ℝ))⁻¹

end Hypergraph

/-! ## 3. Reliability factor (Tier-2 warm-up)

`metaphor_graph/provenance.py::reliability_factor`:

    floor = min 1 (max 0 floor);  r = min 1 (max 0 r)
    return floor + (1 - floor) * r

We state the clean affine fact; the clamps are hypotheses. -/

/-- `reliability_factor floor r = floor + (1-floor)*r`.

With `floor ∈ [0,1]` and `r ∈ [0,1]` this is the affine interpolation the
project uses to map a reliability score into `[floor, 1]`. -/
noncomputable def reliabilityFactor (floor r : ℝ) : ℝ :=
  floor + (1 - floor) * r

end MetaphorSHG
