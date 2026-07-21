# Eval Results and Failure Inspection

## Run integrity

Expected 132 candidate critiques (11 items × 3 samples × 4 models); 132 succeeded across 132 unique keys, with 0 candidate failures and 0 grading failures. Every successful candidate has exactly one grade (132 grades). Duplicate keys: 0 candidate / 0 grade (retry rows deduped, successes preferred; nothing dropped). Unexpected model IDs: none. All failures are **Haiku 4.5 on items 2/3/6/8** (deterministic 529 overloaded_error), so Haiku covers only 11/11 items; the other three models are complete at 11/11.

## Model results

Model score = **mean over items of the per-item sample mean**; 95% CI is a bootstrap over **items** (clusters), not individual responses — three samples of one argument are one cluster, so this weights every argument equally and reflects generalization across arguments.

| Model | Overall | 95% item-CI | Items | Gens | Centrality | Fidelity | Novelty | Impact | Control score | False attack rate | Mean words | >300w |
|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0.583 | [0.48, 0.70] | 11 | 33 | 0.55 | 0.69 | 0.65 | 0.67 | 0.520 | 22% | 303 | 48% |
| Sonnet 4.6 | 0.716 | [0.61, 0.82] | 11 | 33 | 0.67 | 0.83 | 0.76 | 0.77 | 0.656 | 11% | 293 | 12% |
| Opus 4.8 | 0.816 | [0.74, 0.90] | 11 | 33 | 0.77 | 0.87 | 0.86 | 0.83 | 0.797 | 6% | 305 | 85% |
| Fable 5 | 0.829 | [0.75, 0.91] | 11 | 33 | 0.78 | 0.90 | 0.86 | 0.84 | 0.811 | 6% | 304 | 76% |

Item-level mean rises Haiku 0.583 < Sonnet 0.716 < Opus 0.816 < Fable 0.829. The sanity check **Opus > Sonnet > Haiku holds (True)**; Fable ranks highest (reported, not assumed). 95% item-bootstrap intervals (see `eval_model_scores.png`): Haiku 4.5 [0.48, 0.70] (11 items, 33 gens), Sonnet 4.6 [0.61, 0.82] (11 items, 33 gens), Opus 4.8 [0.74, 0.90] (11 items, 33 gens), Fable 5 [0.75, 0.91] (11 items, 33 gens).

## What drove the score

Separation is broad-based, not one dimension. Centrality (Haiku 0.55 → Fable 0.78) and novelty (Haiku 0.65 → Fable 0.86) move most; fidelity and impact are high across the board. Penalties are minor at the top (mean total Fable 0.009, Opus 0.006) and larger for Haiku (0.030), so the gap is mostly earned dimension credit, not penalty avoidance.

## Robust controls

Robust controls are the six `qualify_no_fatal_flaw` items (ids 1,2,3,5,8,9); a false attack is operationalized as the grader's `overclaim` penalty on a control (an unearned fatal-flaw claim). Control-item means: Haiku 0.520, Sonnet 0.656, Opus 0.797, Fable 0.811; false-attack rates 22%/11%/6%/6%. Stronger models mostly qualify rather than invent contradictions; Haiku's control score is depressed partly by missing 3 of the 6 control items, so read it cautiously.

## Reward-hacking checks

Length–score correlation is weak: Pearson 0.10, Spearman 0.07 overall, with within-model Pearson Haiku 4.5 0.39, Sonnet 4.6 -0.12, Opus 4.8 -0.04, Fable 5 -0.44. The 300-word cap compresses length (mean words Haiku 4.5 303, Sonnet 4.6 293, Opus 4.8 305, Fable 5 304), so there is no strong sign that verbosity buys score. Laundry-list penalties are rare, and the novelty dimension is doing its intended job — though only 2 responses scored novelty 0 in the whole run (both Haiku, over-attacking the eval-1 control), so the pure polished-restatement trap barely fired here.

## Manual failure inspection

- **best_high_scoring** — eval 0 / sonnet / s1 (score 1.0, grader-reported None; `eval_grades.jsonl` key `0/sonnet/s1`). Highest-scoring critique on a genuine-flaw item with full centrality; identifies the annotated central issue and shows its effect on the conclusion rather than only restating the argument.
- **operational_substitution** — eval 2 / haiku / s1 (score 0.212, grader-reported None; `eval_grades.jsonl` key `2/haiku/s1`). Grader applied the mere_operationalization penalty: demands thresholds/procedures/detail without showing the omission defeats the conceptual claim.
- **robust_control_false_positive** — eval 1 / haiku / s1 (score 0.212, grader-reported None; `eval_grades.jsonl` key `1/haiku/s1`). Robust-control item (qualify_no_fatal_flaw); the grader flagged an unearned fatal-flaw claim (overclaim) matching the item's tempting-but-weak list. The candidate over-attacked a broadly coherent argument instead of offering a bounded qualification.

Full excerpts, dimensions, and rationales are in `eval_failure_examples.json`.

## Interpretation

The eval measures how well a model's short critique matches a human-annotated central flaw under a rubric, as judged by one fixed Opus grader — not conceptual reasoning in general. The monotonic Opus>Sonnet>Haiku result and Fable's lead are consistent with capability but do **not** prove the eval valid; nor would a non-monotonic result prove the models misordered. Treat results as suggestive only.

**Limitations.**
1. The grader sees the human annotation and may reward overlap with it.
2. Stronger models may raise valid critiques outside the annotated central issue that the grader under-credits.
3. Robust controls depend on the human judgment that no fatal flaw exists being correct.
4. A single fixed grader may favor its own critique style (Opus/Fable share lineage).
5. With 11 items, item-level variance is large — the per-item table shows several 0/1 swings, and the bootstrap CIs for the top three overlap.
6. Haiku's incomplete coverage (7/11, all failures a provider-side 529) further limits its comparison.

