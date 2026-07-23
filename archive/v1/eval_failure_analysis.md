# Eval Results and Failure Inspection

## Run integrity

Expected 132 candidate critiques (11 items × 3 samples × 4 models); 132 succeeded across 132 unique keys, with 0 final candidate failures and 0 grading failures. Every successful candidate has exactly one grade (132 grades). Duplicate keys: 16 candidate / 0 grade (retry rows deduped, successes preferred). Unexpected model IDs: none. Earlier Haiku 529 attempts remain visible in the raw operational history, but all missing candidates were later backfilled and every model covers 11/11 items.

## Model results

Model score = **mean over items of the per-item sample mean**; 95% CI is a bootstrap over **items** (clusters), not individual responses — three samples of one argument are one cluster, so this weights every argument equally and reflects generalization across arguments.

| Model | Overall | 95% item-CI | Items | Gens | Centrality | Fidelity | Novelty | Impact | Control score | False attack rate | Mean words |
|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0.603 | [0.47, 0.75] | 11 | 33 | 0.59 | 0.73 | 0.68 | 0.70 | 0.540 | 61% | 303 |
| Sonnet 4.6 | 0.852 | [0.74, 0.95] | 11 | 33 | 0.82 | 0.94 | 0.89 | 0.91 | 0.864 | 28% | 293 |
| Opus 4.8 | 0.902 | [0.81, 0.98] | 11 | 33 | 0.86 | 0.95 | 0.92 | 0.92 | 0.951 | 6% | 305 |
| Fable 5 | 0.984 | [0.95, 1.00] | 11 | 33 | 0.95 | 1.00 | 1.00 | 1.00 | 1.000 | 0% | 304 |

Item-level mean rises Haiku 0.603 < Sonnet 0.852 < Opus 0.902 < Fable 0.984. The sanity check **Opus > Sonnet > Haiku holds (True)**; Fable ranks highest (reported, not assumed). 95% item-bootstrap intervals (see `eval_model_scores.png`): Haiku 4.5 [0.47, 0.75] (11 items, 33 gens), Sonnet 4.6 [0.74, 0.95] (11 items, 33 gens), Opus 4.8 [0.81, 0.98] (11 items, 33 gens), Fable 5 [0.95, 1.00] (11 items, 33 gens).

## What drove the score

Separation is broad-based, not one dimension. Centrality (Haiku 0.59 → Fable 0.95) and novelty (Haiku 0.68 → Fable 1.00) move most; fidelity and impact are high across the board. Penalties are minor at the top (mean total Fable 0.000, Opus 0.009) and larger for Haiku (0.064), so the gap is mostly earned dimension credit, not penalty avoidance.

## Robust controls

Robust controls are the six `qualify_no_fatal_flaw` items (ids 1,2,3,5,8,9); a false attack is operationalized as the grader's `overclaim` penalty on a control (an unearned fatal-flaw claim). Control-item means: Haiku 0.540, Sonnet 0.864, Opus 0.951, Fable 1.000; false-attack rates 61%/28%/6%/0%. Stronger models mostly qualify rather than invent contradictions; every model has complete coverage of all six controls.

## Reward-hacking checks

Length–score correlation is weak: Pearson 0.13, Spearman 0.09 overall, with within-model Pearson Haiku 4.5 0.39, Sonnet 4.6 -0.10, Opus 4.8 -0.11, Fable 5 -0.02. The 300-word instruction constrains the observed length range (mean words Haiku 4.5 303, Sonnet 4.6 293, Opus 4.8 305, Fable 5 304), providing little evidence that verbosity alone buys score without ruling out other style effects. Laundry-list penalties are rare, and the novelty dimension is doing its intended job — though only 2 responses scored novelty 0 in the whole run (both Haiku, over-attacking the eval-1 control), so the pure polished-restatement trap barely fired here.

## Manual failure inspection

- **best_high_scoring** — eval 0 / sonnet / s1 (score 1.0, grader-reported 1.0; `eval_grades.jsonl` key `0/sonnet/s1`). Highest-scoring critique on a genuine-flaw item with full centrality; identifies the annotated central issue and shows its effect on the conclusion rather than only restating the argument.
- **operational_substitution** — eval 2 / haiku / s1 (score 0.0, grader-reported 0.125; `eval_grades.jsonl` key `2/haiku/s1`). Grader applied the mere_operationalization penalty: demands thresholds/procedures/detail without showing the omission defeats the conceptual claim.
- **robust_control_false_positive** — eval 1 / haiku / s2 (score 0.125, grader-reported 0.28; `eval_grades.jsonl` key `1/haiku/s2`). Robust-control item (qualify_no_fatal_flaw); the grader flagged an unearned fatal-flaw claim (overclaim) matching the item's tempting-but-weak list. The candidate over-attacked a broadly coherent argument instead of offering a bounded qualification.
- **polished_restatement** — eval 1 / haiku / s1 (score 0.125, grader-reported 0.23; `eval_grades.jsonl` key `1/haiku/s1`). Novelty scored 0 (no new reasoning beyond the argument's concessions). Caveat: only 3 of 132 graded responses scored novelty 0, and all of them also drew an overclaim penalty on the eval-1 control — a clean 'polished restatement' that tracks the argument without over-attacking did not clearly occur in this run, so this example doubles as a control over-attack.
- **questionable_grader** — eval 1 / sonnet / s0 (score 0.225, grader-reported 0.42; `eval_grades.jsonl` key `1/sonnet/s0`). The grader's dimension calls look defensible against the annotation, but its self-reported item_score (0.42) does not match the rubric applied to those same dimensions (0.225; gap 0.195) — a grader arithmetic error. The recomputed value is used. Largest such gap in the run; grader arithmetic disagreed with the formula in ~20% of grades.

Full excerpts, dimensions, and rationales are in `eval_failure_examples.json`.

## Interpretation

The eval measures how well a model's short critique matches an AI-assisted reference judgment under a rubric, as judged by one fixed Opus grader — not conceptual reasoning in general. The monotonic Opus>Sonnet>Haiku result and Fable's lead are consistent with capability but do **not** prove the eval valid; nor would a non-monotonic result prove the models misordered. Treat results as suggestive only.

**Limitations.**
1. The grader sees the reference annotation and may reward overlap with it.
2. Stronger models may raise valid critiques outside the annotated central issue that the grader under-credits.
3. Robust controls depend on the AI-assisted reference judgment that no fatal flaw exists being correct.
4. A single fixed grader may favor its own critique style (Opus/Fable share lineage).
5. With 11 items, item-level variance is large — the per-item table shows several 0/1 swings, and the bootstrap CIs for the top three overlap.
6. Three samples per item provide only a limited view of generation variance.
