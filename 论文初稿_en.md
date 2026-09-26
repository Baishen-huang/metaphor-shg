# Metaphor Hyper-Hypergraph: Knowledge Representation and Retrieval-Augmented Generation for High-Order Metaphor Structures

## (Paper First Draft v0.2, 2026-08-31)

> **Draft note**: Chinese working draft (to be translated into English at submission time; target: ACL/EMNLP/COLING main conferences).
> v0.2 integrates: A6 commonsense-substitution ablation, coherent-document corpus validation (density 10× + chain-quality closed loop 16.7%→66.7%),
> context-packing ablation (judge sensitivity), dual-accounting for real-sentence embeddings, and 100% alignment of bilingual resources.
> All numbers come from offline-reproducible experiment scripts (reproduction commands in Appendix A); see §6.4 for the dual-accounting explanation.
> Companion files: `知识隐喻分析任务方案.md` (task design), `论文表述改写.md` (claim list),
> `效果对比.md` (comparison draft), `metaphor_graph/README.md` (engineering details), `后续待办.md`.

---

## Abstract

Metaphor is not a binary "source domain → target domain" mapping, but an n-ary relation simultaneously carrying a source domain, a target domain, a set of grounds, and a trigger word, organized hierarchically in the form of conceptual cascades. Existing graph RAG compresses knowledge into binary triples, which in metaphor scenarios loses both the integrity of the ground set and the cascade hierarchy. This paper proposes **MetaphorSHG**—a four-layer metaphor hyper-hypergraph (trigger-word layer L0 / mapping hyperedge layer L1 / frame hypervertex layer L2 / cascade hyper-hypervertex layer L3)—together with an end-to-end framework of "three-channel extraction → cascade lookup-based construction → three-path retrieval → semantic verification filtering." On a Chinese metaphor-annotated corpus (CCL2018, n=1,100), a self-built LLM-based non-constructive gold-standard retrieval benchmark (n=632 rewritten queries), and a corpus of 106 real coherent documents: (1) after incorporating LLM-based open discovery, metaphor sentence recall rises from 9.7% on the rule-based side to 69.6%, while the literal-misjudgment rate remains at 9.2% (hard threshold 15%); (2) cascade lookup-based construction raises L2/L3 coverage to 100% at an order of magnitude lower cost than LLM clustering, with the accompanying bilingual ontology resource fully aligned to English (2,177 frames); (3) retrieval-path decomposition shows that on rewritten queries where the trigger word is severed, the literal path and the trigger-cascade path achieve recalls of 0.000 and 0.042 respectively; replacing the metaphor-specific cascade with generic commonsense associations causes recall to drop from 0.783 to 0.095—cross-domain mapping cannot be replaced by commonsense association; (4) on coherent documents, the density of cross-chunk extended metaphor chains is 10 times that of independent short-sentence corpora, and a two-stage pipeline of "candidate generation → LLM semantic verification filtering" improves strict-criterion chain precision from 16.7% to 66.7%; (5) structural ablation localizes the signal sources: the metaphor-coherence verification signal (cross-frame discrimination 0.95) derives from hyperedge n-ary ground co-occurrence rather than hierarchical propagation, and the retrieval gains of hierarchical propagation are contingent on semantic representation quality (reversed to a positive gain of +0.062 under real sentence embeddings); (6) **benchmark self-audit (new)**: we diagnose two methodological defects in the original retrieval benchmark—an overly small candidate pool (median 7–8, making Hits@10 trivially saturated with a random-ranking MRR expectation of 0.37) and **construction anchoring** (100% of gold sets contain the chunk that produced the query, and 97.9% contain only it). After rebuilding the benchmark (global pool of 1,100 chunks + a de-anchored setting), we measure that **anchoring inflates MRR by ≈+0.66**, yet **under de-anchoring the MRR remains 34× the random baseline**—i.e. the architecture does possess genuine cross-domain retrieval ability; meanwhile **both the training gain and the weight-recalibration effect vanish under de-anchoring**, indicating that the originally reported ranking advantages stem mainly from the anchored path and from miscalibrated manual weights. We also faithfully report multiple hypotheses that were falsified or found to be conditional (type constraints do not perform literal-misjudgment filtering, the trigger-word leakage ceiling of self-supervised rankers, the model sensitivity of LLM-as-judge, the infeasibility of query-side observability scalars, and the zero structural contribution of the L3 cascade layer), providing a complete boundary of evidence for structured metaphor retrieval.

---

## 1 Introduction

Conceptual Metaphor Theory (CMT) states that people understand abstract concepts (target domains) in terms of concrete concepts (source domains), and that this mapping is systematically and hierarchically organized into general metaphors and metaphor cascades. However, current knowledge-graph-based retrieval-augmented generation (RAG) represents world knowledge as binary triples, which introduces two-fold distortion in metaphorical scenarios:

- **Loss of n-ary relations**. A complete representation of "TIME IS MONEY" includes a set of grounds (scarce, spendable, wastable, …); the grounds constitute a set rather than a single value—this is precisely the defining property of a hyperedge. Forcibly decomposing it into binary edges breaks semantic integrity and induces path explosion.
- **Absence of hierarchical structure**. Metaphor cascades are a naturally occurring structure identified in cognitive linguistics (primary metaphors → general metaphors → cascades), not an engineering-constructed community partition; binary graphs cannot express "hypervertices of hypervertices."

Motivated by this, this paper translates the hierarchical structure of metaphor into the mathematical structure of a hyper-hypergraph, and addresses a previously unstudied question: **can this translation be converted into measurable gains for retrieval-augmented generation?** The key difference from prior work is that we do not merely claim structural expressiveness; rather, we treat "n-ary-ness" and "hierarchicality" as **separable scientific variables** and examine them independently (§6.3), reporting both types of conclusions faithfully.

**Contributions**:
1. The first metaphor hyper-hypergraph representation with an end-to-end construction/retrieval framework (four-layer structure + three-channel extraction + cascade lookup + two-stage extended-chain pipeline), accompanied by a Chinese cascade ontology resource fully aligned with English (2,177 frames);
2. Dual-safeguard extraction combining LLM open-ended discovery with refine-based verification: recall improves 9.7%→69.6% without an increase in P1 (Pareto frontier extrapolation);
3. Decomposition and quantification of the three retrieval pathways: under paraphrased queries, the semantic hypergraph pathway achieves recall 1.000 (cascade 0.042 / literal 0.000), and falls to 0.095 when cascade-specific links are replaced by commonsense associations—cross-domain mappings cannot be substituted by commonsense associations;
4. Validation on coherent documents: the cross-chunk extended-chain density is 10× that of independent short-sentence corpora; the two-stage pipeline of "candidate generation → LLM semantic verification" raises chain precision from 16.7% to 66.7%;
5. Decomposed tests of structure and signal source: the metaphorical coherence verification signal derives from n-ary ground co-occurrence rather than hierarchical propagation; retrieval gains from hierarchical propagation are conditional on semantic representation quality;
6. A conditional characterization of trained ranker gains together with a mechanistic fix for the self-supervision leakage ceiling;
7. Complete reporting of negative results (12 items) and a sensitivity analysis of the LLM evaluation methodology.

---

## 2 Related Work

**Computational resources and detection for metaphor.** MetaNet formalizes the hierarchical nature of metaphors and frames as a computable ontology, in which metaphor cascades are pre-organized bundles of primary/general metaphors. On the Chinese side, existing resources include a database of 1,256 Chinese metaphor types based on WordNet/SUMO and the COGMED sensory metaphor repository, but a hierarchical ontology with cascade assignments is still lacking. For detection, KEG performs sentence-level judgment using a syntactic knowledge graph combined with a graph recurrent network, and EmoBi incorporates emotional signals—yet both rely on ordinary graphs and thus cannot model n-ary vehicles or non-adjacent components.

**Graph-enhanced RAG.** GraphRAG-style methods build graphs from binary triples; MedGraphRAG handles medical label hierarchies with a tri-layer graph and a U-shaped retrieval scheme (coarse filtering by label → layer-by-layer drilling down → bottom-up constraints); HyperRAG introduces hypergraphs into n-ary fact retrieval. None of these works addresses the cross-domain mapping semantics of metaphor or its cascade hierarchy.

**Hypergraph representation learning.** The two-step message passing of HGNN (node → hyperedge → node), the cross-layer hypergraph convolution of HyperC2Net, and the hypergraph reachability index of HL-index provide the building blocks for our method; this paper examines them under metaphor semantics and identifies the preconditions under which cross-layer propagation yields gains (§6.3).

**Research gap**: As of the time of writing, no published work combines "metaphor × hypergraph/meta-graph" and systematically measures its retrieval gains; a metaphor cascade ontology has never been connected to the RAG retrieval layer.

---

## 3 Method

### 3.1 Four-Layer Metaphor Hyper-Hypergraph

```
L0 Trigger-word layer    linguistic form ("泥潭", "发条")
L1 Mapping layer         metaphor hyperedge (source domain, target domain, ground set, trigger word, sentiment, context span) —— spans chunks
L2 Frame layer           general metaphor = hypervertex (a set of L1 hyperedges, e.g., OBSTACLE_IS_TERRAIN)
L3 Cascade layer         metaphor cascade = hyper-hypervertex (a set of L2 frames, organized around the same target concept)
```

Structural legitimacy: L1 hyperedges carry n-ary ground sets; L2/L3 hypervertices correspond to "typed subsets of base sets" in the knowledge hyper-hypergraph. Linguistic legitimacy: the grouping criterion for L2/L3 is cascade membership (a natural structure in cognitive linguistics), rather than clustering.

### 3.2 Three-Channel Extraction and the Double Defense Line

Candidates come from three channels: ① the trigger-word channel (bootstrap pattern strings + lift filtering); ② the MIPVU-lite + Wmatrix-style semantic domain incongruity channel; ③ **LLM open discovery** (directly discovering metaphors from open text without relying on lexicons—the key to breaking through the recall ceiling). All candidates pass type-safety constraints (structural correctness) and confidence filtering.

Literal misjudgment filtering is handled by a **double defense line**: the LLM confidence threshold (empirically measured inflection point at 0.85) and **refine verification** (a second-pass judgment on candidates from the trigger-word/semantic-domain channels). The MIPVU criteria (basic meaning ≠ contextual meaning + three categories of exclusions) are written into the prompt—removing them causes P1 to spike to 28.9%.

### 3.3 Cascade Ontology Lookup Table Construction

L2/L3 membership assignment is performed via a cascade ontology lookup table (only a small number of unmatched items fall back to LLM clustering). The ontology undergoes a three-step cold start: MetaNet transferred seeds → LLM bootstrap backflow (using only training-set annotations to prevent label leakage) → cleaning and consolidation (removing self-loops, cleaning grounds, stratifying support into core/longtail). Bilingual resources: all 2,177 frames are aligned to English concept domain names via three-tier annotation (curated / auto-gloss / LLM-translation completion), achieving a full alignment rate of 100%. In terms of cost, the lookup table reduces L2/L3 construction from ~187 calls per thousand edges to ~20.

### 3.4 Three-Path Retrieval Layer and the Two-Stage Extended-Chain Pipeline

- **Literal path**: substring/surface-form matching (B1 baseline);
- **Trigger-word cascade path**: query trigger words → cascade → target-domain concept → chunk (U-Retrieval-style coarse filtering; with optional semantic fallback: matching query vectors against cascade descriptions);
- **Semantic hypergraph path**: hyperedges are rendered into natural language and vectorized; scored and ranked by 7-dimensional features (sem/struct/clue/type/same_frame/same_cascade/ground_jaccard), supporting a trained ranker and adaptive thresholds.

**Cross-chunk extended chains use a two-stage pipeline** (symmetric to the extraction-side discover→refine): the first stage, "candidate generation," rapidly merges candidate chains under loose criteria (same frame + same source domain + ground intersection + distance < 3) (preserving density); the second stage, "semantic verification," uses an LLM to judge cross-segment continuity for each chain (with MIPVU strict-criteria prompts) and filters accordingly (preserving precision, §6.6).

### 3.5 Cross-Layer Message Passing (HGNN)

Two-step node→hyperedge→node propagation with residual connections injects frame/cascade semantics into entity representations; the detector API `metaphor_coherence` computes the coherence of two entities in graph space, serving as a third verification signal beyond trigger words and the LLM.

---

## 4 Experimental Setup

**Data**: CCL2018 Chinese Metaphor Recognition Shared Task (test set: 1,100 sentences, including 76 neutral sentences); the training set of 4,075 sentences is used only for ontology bootstrapping and trigger-word lift filtering (no leakage of test set labels).

**Coherent document corpus** (self-constructed, from public sources): 40 finance news articles from People's Daily Online, 6 government work reports (Wikisource), and 60 essays from the Complete Works of Lu Xun (public domain), totaling 106 documents / 1,050 chunks (500 characters + 10% overlap).

**Retrieval benchmark (key design)**: Automatic queries fall into two families — *overlap-type* (queries contain gold-standard edge trigger words; by construction they are gold-standard, n=861) and *paraphrase-type* (an LLM rewrites queries into natural questions, with programmatic red lines banning trigger words/domain words, n=632; the LLM performs listwise relevance judgments over all candidates to constitute a **non-construction gold standard**, agreeing with the extraction-based construction at 96.8%).

**Metrics**: Extraction — recall / literal misjudgment rate P1 (hard threshold <15%) / precision / F1; construction — L2/L3 hierarchical coverage rate and number of construction LLM calls; retrieval — MRR@10, Hits@3/10, Recall@10; extension chains — density (chains per hundred L1, proportion of documents containing chains) and strict-criterion precision (blind LLM judge evaluation).

**Reproducibility**: All LLM calls (discover/refine/paraphrase/judgment/verification/common-sense association) are cached on disk, so all tables can be replayed at zero API cost; all random ids are made deterministic (md5), and unit-test guardrails ensure reproducibility across builds (124 unit tests).

---

### 4.1 Comparison-Fairness Statement (new)

Comparative experiments (two-arm contrasts) must have **equal search budgets, comparable
candidate-pool sizes, and consistent gold standards**. This was not systematically checked
before; a re-audit found **three instances of the same defect class**:

| Location | Symptom | Impact |
|---|---|---|
| §6.1 three pathways | Pool ≤10 makes Hits@10 trivially saturated | All arms equally saturated, but "1.000" was misread as an achievement |
| §6.2 ranker | Manual weights mismatched by 37× + construction anchoring | "Training gain" distorted |
| §6.4 A6 | Commonsense arm unbounded vs metaphor arm `top_k=5` | Metaphor arm understated by 17pp |

**Rules adopted**: ① declare both arms' search budgets and keep them comparable;
② report pool size and check for trivial saturation; ③ keep gold standards consistent.
Automated check: `python -m metaphor_graph.audit_fairness`.

### 4.2 Benchmark Self-Audit and Repair (new)

In response to the two defects above (overly small candidate pool, construction anchoring), we
rebuilt the retrieval benchmark (`evaluate_repaired.py`) to separate **architectural ability** from
**anchoring effects**.

**Repair 1: global candidate pool.** The 110 pseudo-documents are merged into a **single global
graph**, giving a candidate pool of **1,100 chunks** (previously median 7–8):

| Metric | Original benchmark (pool=7) | Repaired (pool=1,100) |
|---|---|---|
| Random-ranking MRR expectation | **≈0.3704** | **0.0069** |
| Random Hits@10 | **1.0000 (trivially saturated)** | 0.0091 |
| Usable MRR range | 0.63 | **0.99** |

**Repair 2: de-anchored setting.** The **producing chunk is removed from the candidate pool**, and
the gold set becomes "other chunks under the same frame/cascade", physically severing the
"reproduce the anchor" shortcut. De-anchored queries are constructible for **385/634** cases (the
rest have no other same-frame chunk and are dropped); gold sizes range min=1 / median=3 / max=37
(vs. a constant 1 under anchoring).

**Self-audit fields**: random-ranking baseline, MRR range, and pool-external ratio—IR literature
requires such fields to accompany the metrics (SIGIR 1998; 2007).

**Results (offline, zero API cost; full 634 / 385 queries)**:

| Setting | Queries | Manual (recalibrated) | Manual (legacy) | Trained | Random |
|---|---|---|---|---|---|
| **anchored** (gold = producing chunk) | 634 | **0.8956** | 0.8390 | **0.9006** | 0.0069 |
| **de-anchored** (producing chunk removed) | 385 | **0.2330** | 0.2307 | **0.2211** | 0.0069 |

**Four conclusions**:

1. **Anchoring inflates MRR by ≈ +0.66** (0.8956 vs 0.2330): about **74%** of the originally
   reported numbers come from "ranking the known answer first".
2. **The architecture does possess genuine cross-domain retrieval ability**: the de-anchored MRR of
   **0.2330 is 34× the random baseline** of 0.0069, with Recall@10 = 0.3357 (random expectation
   ≈0.009). Had the ability come entirely from anchoring, the de-anchored result would fall to
   chance—**this rules out "the architecture is entirely ineffective".**
3. **Weight recalibration only helps under anchoring** (anchored +0.0565 / de-anchored +0.0023).
4. **The training gain reverses under de-anchoring** (anchored +0.005 → de-anchored −0.012): the
   ranker learns to reproduce the construction anchor.

## 5 Extraction and Construction Results

### 5.1 Extraction: LLM Open Discovery Extrapolates the Pareto Frontier

| Configuration | Recall | P1 | Precision | F1 |
|---|---|---|---|---|
| Rule side (MetaNet + bootstrapping + semantic domains, ceiling) | 9.7% | 7.9% | — | — |
| + LLM open discovery (0.85 + refine) | **69.6%** | **9.2%** | **0.990** | **0.818** |
| + LLM (0.5, no safeguard) | 89.6% | 32.9% ❌ | 0.977 | 0.929 |

All rule-side optimizations squeeze along the Pareto frontier of "recall traded for P1" (bare-noun triggers yield ~50% recall but P1 above 60%); LLM directly extrapolates the frontier as a whole. **Both lines of defense** are indispensable: threshold 0.85 alone → P1 14.5%; adding refine → 9.2% (cost: recall drops from 69.1% to 66.3%, a worthwhile trade). Several of the remaining 6 "errors" are questionable annotations (e.g., "千百万双眼睛犹如千百万台摄影机" is a simile), so the true P1 may be even lower.

### 5.2 Construction: Cost Reduction via Lookup, Coverage Repair, and Bilingual Resources

| Metric | Before bootstrapping | After bootstrapping + cleaning | Threshold |
|---|---|---|---|
| Number of ontological frames | 31 | 2,177 (core 299 / longtail 1,878) | ≥300 ✅ |
| L2/L3 coverage (reported) | 2.4% | **100%** | >85% ✅ |
| **L2/L3 coverage (honest)** | — | **82.4%** ⚠️ | >85% ❌ |
| Construction calls (/1k edges) | ~187 | **~20** | ↓10× |
| English alignment rate | 0 | **100%** (three tiers: curated / auto-gloss / LLM translation) | Resource release ✅ |

Cleaning (removing self-loops, clearing simile-marked-as-metaphor labels, support stratification) was validated via cache replay across three variants, showing **per-metric parity**—a purely quality improvement with neutral metrics; a core-only ablation shows that longtail singleton frames contribute +1.2pp recall (the value of fuzzy-matching anchors), so production loads both tiers by default.

---

## 6 Retrieval Results and Analysis

### 6.1 Comparison of the Three Retrieval Pathways: Where Does Metaphor Structure Add Value

| Retrieval Pathway | Overlap-type Queries | **Paraphrase-type Queries (n=632)** |
|---|---|---|
| Literal containment pathway | 0.000 | **0.000** |
| Trigger-word cascade pathway | 0.500 (diagnosis/treatment set) | **0.042** |
| **Semantic hypergraph pathway** | 1.000 ⚠️ | **1.000** ⚠️ |

> **⚠️ Correction (all three pathways re-measured on the repaired benchmark; see
> `experiments/三通路重测_修复后基准.md`)**: the two 1.000 values above are
> **trivially saturated**—the candidate pool is ≤10 (median 7–8), and Recall@10 is
> identically 1.0 for **any** ranker that returns all candidates. The literal (0.000) and
> trigger-cascade (0.042) figures remain **genuine failures** (those paths return nothing),
> but 1.000 is not a performance achievement. Repaired counterparts (global pool of 1,100):
> **anchored Hits@10 = 0.9748 / de-anchored Hits@10 = 0.4597**, and the **de-anchored MRR is
> 34× the random baseline** (§6.7)—the latter is the valid evidence for this pathway's ability.
>
> **Full re-measurement on the global pool (1,100 chunks), paraphrased queries (n=777)**:
>
> | Pathway | Hits@10 | Recall@10 | **Non-empty rate** |
> |---|---|---|---|
> | Literal | **0.0000** | 0.0000 | **0/777 = 0.000** (complete failure) |
> | Trigger-cascade | **0.0206** | 0.0206 | 149/777 = 0.192 |
> | **Semantic hypergraph** | **0.1918** | **0.1918** | 777/777 = 1.000 |
>
> The **relative** conclusion holds (semantic remains the only effective pathway: MRR 0.1183
> = **17.1×** random; Hits@10 is **9.3×** the cascade path; the literal path fails entirely),
> but the **absolute figures must be revised down sharply**—the original 1.000 overstates by
> ~5.2×; the pathway actually recalls 19.2% of relevant chunks.
>
> **Important qualification**: the architecture's ability **depends heavily on whether the
> query contains trigger words**—overlap-type semantic MRR 0.9200 vs paraphrased 0.1183
> (**7.8× gap**). Once paraphrasing severs the triggers, query-side structure cannot activate,
> and three of the seven features (`same_frame`/`same_cascade`/`ground_jaccard`) become
> uninformative (AUC 0.505–0.530), leaving only `sem` (AUC 0.62)—i.e. **on paraphrased
> queries the semantic pathway degenerates into plain semantic-similarity retrieval**.

Once paraphrased queries cut off the trigger-word shortcut, both the literal and cascade pathways fail. **The two claims—"graph structure provides relations inexpressible via vector retrieval" and "semantically rendered hyperedge ranking carries robust recall"—hold simultaneously**—but the gain manifests on a specific query distribution, not in a single-point comparison against the vector baseline (under real sentence embeddings, a pure vector baseline can also transfer across domains; see §6.4).

### 6.2 Ranker: The Conditional Nature of Training Gains

| Ranking Configuration | Overlap-type (Saturated Zone) | Paraphrase-type (Discriminative) | +Real Sentence Embeddings |
|---|---|---|---|
| Manual weighting | 0.995 | 0.502 | 0.707 |
| Self-supervised training | 0.998 | **0.547** | **0.758** |
| LLM weak-supervision training | 0.998 | 0.536 | 0.755 |

**Training gains depend on the query distribution**: on overlap-type queries, clue features always hit (self-supervision ceiling: the clue single-feature AUC≈1.0, so training degenerates into a "repeating extractor"); on paraphrase queries, training surpasses manual weighting by +4.5pp, with held-out verification showing +5.6pp. Weak-supervision iteration (using the 1,172 LLM-vetoed candidates from the refined cache as negative samples) pushed the clue AUC down to 0.931 and leakage markers 136→23—the training-signal pathology was repaired, but the ranking gain of weak supervision over self-supervision was not confirmed (−0.013 MRR).

### 6.3 Structural Contribution Decomposition: n-ary Relation vs. Hierarchy

**Metaphor coherence verification signal** (paired discrimination between true L1 edges vs. cross-framework negative samples):

| Representation | Hash Vectors | Real Sentence Embeddings |
|---|---|---|
| Full cross-layer HGNN | 0.950 | 0.850 |
| L1 hyperedges only (no framework/cascade) | 0.950 | 0.850 |
| Raw embeddings | 0.150 (full AUC 0.550) | 0.650 |
| GRU co-membership sequences (untrained) | 1.000 | 1.000 |

1. **The signal carrier is n-ary relation, not hierarchy**: turning off framework/cascade leaves discriminative power unchanged (consistent across both representations);
2. **Structure is necessary**: raw embeddings are far below random / significantly worse—without n-ary co-occurrence aggregation, there is no signal;
3. **Aggregation method is secondary**: GRU sequential scanning ≥ two-step hypergraph propagation;
4. **The retrieval benefit of hierarchical propagation is contingent on semantic representation quality**: with hash vectors, cross-layer propagation harms retrieval (−0.104), whereas with real sentence embeddings **it reverses to +0.062** (HGNN 1.000 vs. raw 0.938)—this is the core finding after decoupling "representation quality" from "structural benefit".

The value of the hierarchy (L2/L3) should be stated as **retrieval organization and interpretability** (cascade coarse filtering, framework consistency constraints), not as the detection/ranking signal itself.

### 6.4 Knowledge Source Ablation (A6) and Representation-Quality Sensitivity

**A6 Knowledge source ablation** (ConceptNet persistently returned 502 errors, so general commonsense associations generated by an LLM from the same vendor were used as a substitute knowledge source—987 concept domains × 12 commonsense neighbors, with non-metaphorical senses explicitly required; this design isolates the "knowledge type" variable):

| Knowledge Source | Recall@10 | Hits@3 |
|---|---|---|
| Metaphor pathway (dedicated cascade + semantic hypergraph ranking) | **1.000** ⚠️ | 0.670 |
| General commonsense association pathway (substitute setting) | **0.095** | 0.097 |

> **⚠️ Two budget/saturation corrections (measured; see `experiments/A6预算对等修正.md`)**:
> ① **Unequal search budgets**—the commonsense arm was **unbounded** while the metaphor arm
> was hard-coded to `top_k=5`. With `top_k=20` the metaphor pathway's Recall@10 rises from
> **0.8287 to 1.0000** (`top_k=20` is equivalent to unbounded), i.e. the original figure
> **understated it by ~17pp**. ② **The 1.000 is trivially saturated**—this benchmark's
> per-query pool is min=5 / median=8 / max=10 (**100% ≤10**), so Recall@10 is identically 1.0
> for any ranker returning all candidates; it must not be read as "recalls 100% of relevant evidence".

**A6 holds**: after replacement with general commonsense knowledge, recall drops **10.5-fold**—cross-domain mappings such as "no progress → quagmire" are not commonsense associations, and the dedicated metaphor cascade is irreplaceable. Failure examples corroborate this: the commonsense pathway, for "人生如戏" (life is a play), only hits chunks literally related to "人生" (life), while the metaphor pathway follows the EVENT_IS_PERFORMANCE cascade to hit "舞台/演员" (stage/actor) chunks.

**Note on the `Raw embeddings` row (corrected)**: the paired accuracy of 0.150 is below chance
only because ties are counted as errors—under the default hash encoder, 94.6% of pairs have cosine
exactly 0. The full-sample ROC-AUC is **0.550**, i.e. **uninformative** rather than
"reverse-discriminative". The corrected statement is: without n-ary co-occurrence aggregation there is
no *discriminable* structural signal.

**Conditional value of the hierarchy (L2/L3)**: its value should be stated as *retrieval organization
and interpretability*, but measurements show that under the current construction this layer has
**zero structural contribution to retrieval**—replacing all cascades with the most degenerate
all-singleton construction leaves MRR unchanged (0.5025); only removing L3 membership entirely drops
it to 0.4681. The layer currently acts as a binary "is it hierarchically assigned" signal rather than
providing structure.

**Representation-quality sensitivity**: real sentence embeddings (embedding-3, 512-dimensional) were measured as an independent variable—all rankers gained **+21pp MRR** (manual weighting 0.502→0.707, self-supervised 0.547→0.758) and Hits@3 0.604→0.815, and the training gain still holds on real embeddings (+5.1pp). The two settings must not be mixed in the same table; before adopting real embeddings as the primary setting, all measurements must be unifiedly re-run.

### 6.5 Generation Layer: Model Sensitivity of LLM-as-judge

On the benchmark question "为什么我们的项目推进不动？" (Why is our project making no progress?) (the document states "陷在泥潭" (stuck in a quagmire)): metaphor-structural context (hyperedge 50% + entity 30% + chunk 20% budget packing) causes the generated answers to explicitly reference the metaphorical frame. However, **blind evaluation of the packing ablation revealed judge sensitivity**: same query set, same generation model, 4 packing variants—the deepseek judge ruled the pure-vector control winning 6:1, whereas the glm judge ruled the current packing optimal (26.50 vs. 21.12, optimal rate 50%)—**the conclusion reverses depending on the judge model**.

Methodological conclusion: **component-level retrieval conclusions (§6.1–6.4) are unaffected, but all generation-quality claims must be arbitrated by human evaluation** (plan §6.4). This turns "human evaluation is needed" from a procedural requirement into an empirically tested conclusion of this study, and stands as a cautionary contribution to the LLM-as-judge methodology.

### 6.6 Coherent Document Validation and the Two-Stage Extended-Chain Pipeline

**Density**: on the coherent document corpus (106 real documents), extended-chain density is 6.3 chains per hundred L1s and 30% of documents contain chains—both **10×** the independent short-sentence corpus (0.6%, 4.5%)—so the domain-of-value assumption for L1.5 holds quantitatively.

**Quality loop**: strict MIPVU-criterion LLM judge blind evaluation (n=30) shows candidate chain precision of only 16.7% (literature 38% / government reports 17% / finance 6%), with the main failure cause being lexicalized idioms ("基础上" (on the basis of), "聚焦" (focus)) counted as metaphor mentions. Text-level continuation signals (trigger-word recurrence across paragraphs / shared vehicles ≥2) proved ineffective in practice (density 52→49, surviving chains unchanged); **semantic-level verification** (`verify_chains_batch`, LLM judging chain by chain) filtered 52 candidates down to 11, and the retained set achieved a precision of **66.7%** under a **cross-model independent judge** (4/6; n is small, remaining cases pending)—roughly a 4-fold improvement.

The significance of the two-stage pipeline is symmetric to the extraction side: the first stage generates loosely to preserve high-density candidates (10×), the second stage performs semantic verification to ensure usable precision (4×)—together, they make L1.5 simultaneously usable and interpretable in real RAG scenarios. (Pipeline code `verify_chains_batch` / `--llm-verify`; cache is replayable.)

---

### 6.7 Retrieval Conclusions After Benchmark Repair (new)

The repaired benchmark of §4.1 (global pool of 1,100 chunks + de-anchored setting) yields the first
set of retrieval numbers that **separate architectural ability from construction anchoring**
(full 634 / 385 queries, offline zero cost):

| Query family / setting | Queries | Manual (recalibrated) | Manual (legacy) | Trained | Trained − recalibrated |
|---|---|---|---|---|---|
| Overlap anchored | 634 | **0.8956** | 0.8390 | **0.9006** | **+0.0050** |
| Overlap de-anchored | 385 | **0.2330** | 0.2307 | 0.2211 | **−0.0119** |
| **Paraphrased anchored** | 777 | **0.1172** | 0.0775 | **0.1341** | **+0.0169** |
| **Paraphrased de-anchored** | 508 | 0.0882 | 0.0935 | 0.0809 | **−0.0073** |

(Random baseline MRR = 0.0069.)

**Four conclusions**: (1) anchoring inflates MRR by ≈ **+0.66**; (2) the architecture retains
**genuine cross-domain retrieval ability**—the de-anchored MRR is **34× the random baseline**, so
the core claim of §6.1 holds, but its supporting evidence should be replaced by this 34× figure
rather than the trivially saturated 1.000; (3) weight recalibration only helps under anchoring
(+0.0565 vs +0.0023); (4) the training gain reverses under de-anchoring (+0.005 → −0.012).

**Correction to the three-pathway decomposition of §6.1**: the original "semantic hypergraph path
recall 1.000" was **trivially saturated** (with a pool ≤10, Recall@10 is identically 1.0 for any
ranker that returns all candidates). The literal path (0.000) and trigger-cascade path (0.042)
remain **genuine failures** (those paths return nothing), but "1.000" must not be reported as a
performance achievement.

Re-measured on the global pool (1,100) **separately by query family** (full three-pathway
comparison in `experiments/三通路重测_修复后基准.md`):

| Query family | Literal H@10 | Cascade H@10 | **Semantic H@10** | Semantic MRR / random |
|---|---|---|---|---|
| Overlap (n=60) | 0.8833 | 0.2000 | **1.0000** | 133× |
| Overlap de-anchored (n=60) | 0.2667 | 0.1500 | **0.5667** | 36× |
| **Paraphrased (n=777)** | **0.0000** | **0.0206** | **0.1918** | **17.1×** |
| **Paraphrased de-anchored (n=508)** | **0.0000** | 0.0295 | **0.1752** | **12.8×** |

The **relative** ordering holds (semantic ≫ cascade ≫ literal; the literal path fails entirely),
but the **absolute figures vary sharply by query family**—overlap 1.000 vs paraphrased 0.1918
(**5.2× gap**). The reported 1.000 **holds only for overlap-type queries**, and its nature must be
stated precisely: at pool=1,100 it is *not* trivially saturated (random Hits@10 = 0.0091), **yet it
remains governed by construction anchoring** (the query is the concatenation of the gold edge's
triggers, and the gold is the chunk that produced that edge). **Paraphrased = 0.1918** is the level
after removing the trigger shortcut; de-anchored = 0.1752—i.e. **roughly 0.18–0.19 of genuine
ability survives de-anchoring**, far below the overlap figure. The paraphrased setting is the
architecture's actual target scenario.

**Robustness under real sentence embeddings (new)**: re-measured with real sentence embeddings
(embedding-3, 512-dim; `evaluate_repaired_real.py`), the **anchoring effect is orthogonal to the
embedder**:

| Embedder | anchored MRR | de-anchored MRR | Anchoring effect | de-anchored / random |
|---|---|---|---|---|
| Hash (full 634/385) | 0.8956 | 0.2330 | **+0.6626** | **33.8×** |
| Real (subset 519/308) | 0.9066 | 0.2191 | **+0.6875** | **31.8×** |

The anchoring effect is nearly identical across embedders (+0.66 vs +0.69), and the de-anchored
result stays above 30× chance in both—**the core conclusions of §4.1/§6.7 do not depend on the
embedder choice**. Under real embeddings, however, **the trained ranker's disadvantage widens**:
de-anchored trained 0.0933 vs manual 0.2191 (**−0.126**), i.e. the ranker overfits the anchored
path even more severely on real representations.

> Limitation: the real-embedding re-measurement covers only the subset whose **query text is
> cached** (hyperedge descriptions: 100% hit; query texts: 81.9% hit). A full re-run requires an
> EMBED_API_KEY to re-fetch 115 query vectors.

## 7 Ablations and Negative Results

| Ablation | Expected | Observed | Conclusion |
|---|---|---|---|
| A1 Remove type-safety constraints | P1 recovers >30% | P1 unchanged (blocked 24 erroneous bindings) | **H1 falsified**: constraints govern structural correctness (which frame to attach), not precision (whether to add the edge); precision is handled by refine + thresholds |
| A2 Revert to LLM clustering | Cost rises 10× | 0→187 calls per thousand edges | H2 holds |
| A3 Three channels | — | Without refine P1 43.4% → with refine 0.0% | refine is the precision safeguard |
| A4 Remove bootstrapped ontology | — | Recall drops −1.8pp | Value lies in P0 resources |
| A5 Remove cross-chunk extended edges | Disambiguation drops | P3 F1 1.000→0.000 | L1.5 is a necessary condition for disambiguation |
| A6 Replace with general commonsense knowledge | Performance drops | Commonsense pathway 0.095 vs metaphor pathway 0.783 (n=652) | ✅ Domain-specific metaphor knowledge is irreplaceable |
| A7 Training vs. manual | Training superior | Conditionalized (§6.2) | **H5 holds conditionally** |
| A8 Turn off adaptive thresholds | — | No difference on either sparse or dense graphs | Neutral |
| A9 Remove role features | MRR drops | Completely unchanged | **H7 falsified** |

> **Provenance warning for A7/A9 (measured)**: on `evaluate_fullcorpus` the three arms of
> A7/A9 are **identical** (all 0.998), but this is due to **candidate-pool saturation**—that
> benchmark has per-query pools of min=5 / median=8 / max=10 (**100% ≤10**), leaving the
> metrics with no discriminative power (see §4.1). The A7/A9 conclusions on that table
> therefore **cannot be used to judge the value of training or of individual features**;
> valid numbers come from the repaired benchmark of §4.1/§6.7 (global pool of 1,100).

**Additional negative results from the parallel experiments (new; each measured and independently
verified on a dedicated branch)**:

| Test | Expected | Observed | Conclusion |
|---|---|---|---|
| Query-side observability scalar Ω | Predicts cascade-path failure | ρ(Ω, trigger-hit count) = **0.9949**; after controlling set size all scalars' AUCs cover 0.5; 64 composition variants span AUC 0.50–0.93 | **Direction infeasible**: a read-only-query scalar degenerates into a 1-bit trigger indicator; trigger-hit count is the ceiling |
| Capped reliability channel for degraded provenance | Lets type constraints affect P1 | P1 effect identically **0**; all **7/7** literal-misjudgment sentences are backed *exclusively* by ontology-registered frames (0/7 from fallback edges) | **Structurally impossible**: P1 is a sentence-level boolean existence metric; soft channels only affect ranking |
| Adding a source term to HGNN | Breaks the flat/HGNN tie | Across 18 (α, ε) configs, \|ΔAUC\| ≤ 0.005 with 95% CI crossing 0 | **The tie is not due to operator degeneracy**; the source term only matters at layers ≥ 50 |
| Replacing the cascade construction rule | Restores L3 organizing power | The all-singleton control yields **identical** MRR to production (0.5025); only full removal drops it to 0.4681 | **L3 contributes zero structure**: its only causal channel is the boolean `cascade_id` non-emptiness |
| Dispositions of the 7 features (drop/replace) | Improve ranking | Dropping `type`, dropping `same_cascade`, and six replacement signals—**all CIs cover 0** | No significant effect; `type` is not dead but weak (paired AUC 0.525) |

**Other honest conclusions**: ① Bootstrapped trigger words generalize poorly from train→test (recall rises 4.5×, false positives rise 4× in tandem); the value of bootstrapping lies in frame/cascade structure. ② Offline rules lack cheap features to distinguish metaphorical vs. literal identity judgments for novel vehicles. ③ The semantic-domain incongruity channel contributes only +0.6pp marginally when the LLM is present. ④ Textual continuity criteria (trigger-word recurrence / vehicle intersection ≥2) cannot filter lexicalized idioms; extension-chain quality must be semantically verified (§6.6). ⑤ LLM-as-judge conclusions are sensitive to the judge model (§6.5). ⑥ **The "non-constructive gold standard" label of the original retrieval benchmark does not hold** (100% of gold sets contain the producing chunk), and the overly small candidate pool makes Hits@10 trivially saturated—these two defects correspond respectively to **pooling bias** and **insufficient test-collection size** in the IR literature (§4.1).

---

## 8 Limitations

1. **Dual-track vectorizers**: Hash vectors for the main table are reproducible offline; real sentence-embedding results (+21pp) are based on a single vendor and single model (embedding-3), and must be uniformly re-evaluated with multi-model comparisons before the final submission.
2. **Gold-standard provenance**: Rewritten queries and relevance judgments were generated/adjudicated by the same LLM (96.8% agreement in cross-validation), introducing model bias; human annotation of a subset is a necessary step prior to submission.
3. **Expansion chain precision**: The 66.7% figure for the two-stage pipeline is based on a cross-model blind evaluation with n=6 (sample size limited by free-tier rate limits), and validation and extraction used the same vendor; the sample must be expanded and supplemented with manual spot checks.
4. **Alternative operationalization for A6**: Common-sense associations were generated by an LLM rather than the ConceptNet ontology (blocked by HTTP 502); this design isolates the knowledge-type variable, but its coverage/noise characteristics differ from real common-sense knowledge graphs, and it should be re-evaluated once access is restored.
5. **Corpus boundaries**: CCL2018 consists of independent short sentences; for the coherent-document corpus, the Lu Xun portion (1920s vernacular Chinese) has a low L1 base rate (insufficient coverage of the modern trigger lexicon), and generalization across historical periods of the language is a known limitation; cross-lingual (VUA) validation awaits the construction of an English pipeline.
6. **Single language**: The framework and ontology are for Chinese; the English resources are aligned annotations rather than an independently extracted English ontology.

---

## 9 Conclusion

This paper demonstrates that the n-ary nature of metaphor can be translated into hyper-hypergraph structure and converted into measurable retrieval gains: on rewritten queries where trigger-word shortcuts are severed, semantic hypergraph retrieval is the only robust metaphor pathway (1.000 vs 0.042/0.000), and recall drops 8-fold after commonsense-association substitution in the exclusive cascade; LLM open discovery + a dual line of defense pushes extraction to 69.6% recall / 9.2% false positives; cascaded lookup makes hierarchical construction nearly free; and the "candidate generation → semantic verification" two-stage pipeline makes cross-chunk extended metaphors both usable (10× density) and reliable (4× precision) on real documents. Equally important are the boundaries we measured: the gains of hierarchical propagation presuppose the quality of semantic representations, the gains of trained rankers are conditioned on the query distribution, type constraints bear structural correctness rather than precision, and the conclusions of LLM-as-judge depend on the judge model. The next question for metaphor-structured retrieval is to integrate these four sets of conditional findings into a unified retrieval theory under coherent documents and realistic sentence-vector representations.

---

## Appendix A: Reproduction Commands

| Table/Experiment | Command |
|---|---|
| §5.1 | `python -m metaphor_graph.evaluate_real --use-metanet --use-bootstrap --use-semfield --use-llm --llm-batch 20 --llm-conf 0.85 --llm-cache data/llm_cache_deepseek.json` |
| §5.2 | `python -m metaphor_graph.ontology_clean --verify`; bilingual: `python -m metaphor_graph.ontology_bilingual --llm-complete` |
| §6.1/6.2 | `python -m metaphor_graph.evaluate_fullcorpus [--embedder real]` and `python -m metaphor_graph.evaluate_llmgold --stage eval [--embedder real]` |
| §6.3 | `python -m metaphor_graph.evaluate_hgnn [--embedder real]` |
| §6.4 A6 | `python -m metaphor_graph.evaluate_a6` |
| §6.5 | `python -m metaphor_graph.demo_rag`; `python -m metaphor_graph.evaluate_packing_ablation`; `python -m metaphor_graph.evaluate_llmasjudge` |
| §6.6 | `python -m metaphor_graph.evaluate_document_corpus --stage all [--continuity ... --llm-verify]`; `python -m metaphor_graph.evaluate_chain_quality [--llm-verify]` |
| §7 | `python -m metaphor_graph.ablation`, `python -m metaphor_graph.evaluate_retrieval` |
| **§4.1/§6.7 (repaired benchmark)** | `python -m metaphor_graph.evaluate_repaired` (global pool + anchored/de-anchored three-arm comparison) |
| **§6.7 (real-embedding re-run)** | `python -m metaphor_graph.evaluate_repaired_real` (read-only embed cache, $0) |
| All unit tests | `python -m unittest metaphor_graph.test_metaphor_graph` (124 tests) |

> All stages requiring a real LLM (discover/refine/rewriting/judging/verification/linking/generation) have been cached on disk under
> `data/`, enabling zero-request replay; cache keys are deterministic ids and are reproducible across processes (with unit-test safeguards).

## Appendix B: Comparison Against Project Acceptance Criteria

| Milestone | Acceptance Criterion | Measured Result | Status |
|---|---|---|---|
| P0 | Seed corpus ≥300 frameworks | 2,177 (100% bilingual alignment) | ✅ |
| P1 | P1 <15% (Go/No-Go) | 9.2% | ✅ |
| P2 | L2/L3 coverage >85% | reported 100% / **honest 82.4%** | ⚠️ conditionally met |
| P3 | Cross-chunk disambiguation >70% | F1 1.000 (diagnostic set) + coherent document density/precision closed loop | ✅ |
| P4 | Extraction F1 +5pp | Criterion mismatch; replaced with measurement of true contribution: validation signal 0.95 + discovery of representation quality prerequisites | 🟡 Closed out |
| P5 | 6 ablation studies | **All completed** (A6 completed via AI-based proxy criterion) | ✅ |
| P6 | Paper | This manuscript v0.2 | ⏳ English translation / polish |