# Grader Calibration — Q0–Q2 Rubric Unit-Test Set

Grader: **opus** · graded 18/18 records. Annotation-free grading (as the human labeled them). This checks that the grader **implements** the v2 rubric; per the set's README it does **not** show the rubric generalizes.

## Dimension agreement (grader vs human)

| dimension | exact | within ±0.25 | MAE |
|---|---:|---:|---:|
| centrality | 0.22 | 0.78 | 0.26 |
| argument_fidelity | 0.50 | 1.00 | 0.12 |
| novelty | 0.33 | 0.78 | 0.24 |
| justified_impact | 0.33 | 0.94 | 0.18 |
| **macro** | 0.35 | 0.88 | — |

## Penalties, disposition, ordering

- **Penalty (pooled)** precision 0.95, recall 0.69 (TP 20, FP 1, FN 9).
  per-type recall/precision: laundry_list P0.94/R1.00; overclaim P1.00/R0.17; mere_operationalization P1.00/R0.50; retreat_as_repair P—/R0.00; unsupported_claim P—/R0.00.
- **Disposition accuracy:** 0.83.
- **Item-score:** Spearman 0.74, Pearson 0.70, MAE 0.219.
- **Pairwise ordering accuracy:** 0.79 (concordant 108, discordant 26, grader-ties 9).
- **Argument-specific > laundry/generic:** grader ranks the stronger higher in 12/20 cross-pairs (human 19/20).

## Primary calibration checks (grader vs human baseline)

Pass counts are out of the category members; the human baseline shows how many the hand labels themselves satisfy (category names carry nuance), so grader ≈ human is the real target.

- ⚠️ **Polished restatement -> novelty in {0, 0.25}** — grader 0/2, human 1/2; grader misses cal_id [2, 4].
- ⚠️ **Operational substitution -> mere_operationalization penalty** — grader 2/5, human 4/5; grader misses cal_id [0, 10, 13].
- ⚠️ **Overclaiming -> overclaim penalty** — grader 1/3, human 2/3; grader misses cal_id [0, 17].
- ✅ **Scope correction -> disposition 'narrows' (not 'defeats')** — grader 1/1, human 1/1.

## Per-record (human → grader)

| cal | q | model | category | h.score | g.score | Δ | h.disp | g.disp |
|---|---|---|---|---:|---:|---:|---|---|
| 0 | q0 | haiku | operational_substitution_and_overc | 0.013 | 0.300 | 0.29 | narrows | narrows |
| 1 | q0 | sonnet | valid_but_mostly_expected_sampling | 0.463 | 0.300 | -0.16 | narrows | narrows |
| 2 | q0 | opus | polished_restatement_with_specific | 0.412 | 0.787 | 0.38 | narrows | narrows |
| 3 | q0 | fable | laundry_list_with_real_attribution | 0.512 | 0.650 | 0.14 | narrows | narrows |
| 4 | q0 | fable | polished_restatement | 0.125 | 0.638 | 0.51 | narrows | narrows |
| 5 | q0 | haiku | generic_textbook_critique | 0.062 | 0.387 | 0.32 | narrows | narrows |
| 6 | q1 | sonnet | argument_specific_reasoning_proces | 0.713 | 0.650 | -0.06 | narrows | narrows |
| 7 | q1 | opus | strong_new_verification_critique | 1.000 | 0.838 | -0.16 | narrows | narrows |
| 8 | q1 | fable | strong_scope_counterexample | 0.900 | 0.900 | 0.00 | narrows | narrows |
| 9 | q1 | haiku | overclaiming_unfalsifiability | 0.062 | 0.437 | 0.37 | defeats | narrows |
| 10 | q1 | opus | mixed_strong_and_operational | 0.713 | 0.838 | 0.12 | narrows | narrows |
| 11 | q1 | fable | strong_but_laundry_list | 0.713 | 0.900 | 0.19 | narrows | narrows |
| 12 | q2 | haiku | operational_substitution | 0.062 | 0.362 | 0.30 | qualifies | qualifies |
| 13 | q2 | sonnet | mixed_real_tension_and_operational | 0.550 | 0.400 | -0.15 | narrows | qualifies |
| 14 | q2 | opus | strong_internal_tension | 0.850 | 0.650 | -0.20 | narrows | qualifies |
| 15 | q2 | fable | best_argument_specific_critique | 0.900 | 0.650 | -0.25 | narrows | narrows |
| 16 | q2 | haiku | generic_operational_laundry_list | 0.113 | 0.200 | 0.09 | qualifies | qualifies |
| 17 | q2 | fable | strong_but_overbroad | 0.713 | 0.463 | -0.25 | narrows | narrows |

## Interpretation

Agreement here shows the grader reproduces the rubric's intended behavior on the examples that motivated it — a unit test, not evidence the rubric generalizes to unseen arguments. Exact per-dimension agreement is expected to be modest (the 5-point scale invites ±0.25 disagreements); the more meaningful signals are within-±0.25 agreement, disposition accuracy, penalty recall on the targeted failure modes, and the pairwise ordering.

**Main gap: the grader is more lenient than the human**, especially on the weak critiques. Per-record deltas are positive on the polished-restatement / operational / generic categories, and penalty recall is low (overclaim and mere_operationalization are frequently missed). It still recovers the broad ordering (Spearman/pairwise) and disposition. A likely contributor is that this calibration grades **annotation-free**, so the grader lacks the `non_novel_restatements` and `explicit_concessions` lists that anchor novelty and the penalties in the full eval. Those annotations may improve strictness, but that direction was not tested with a paired annotated/annotation-free comparison. The grader prompt was not modified during this v2 calibration run; metrics are over all 18 records. Because these examples helped motivate the rubric, this remains a rubric-implementation unit test rather than holdout evidence.

