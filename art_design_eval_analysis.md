# Art & Design Eval — Results and Analysis (v2 grader)

Same graded pipeline as the main submission (`eval.py` generate → grade → summarize) run on a **separate 6-item art/design set**, graded by a fixed **Opus** grader; 72 grades. Scores are recomputed in code with the annotation caps — the grader returns structured flags, never an item_score. This set is **not** part of the main submission.

## Model results

Model score = **mean over items of the per-item sample mean**; 95% CI is a bootstrap over **items** (clusters), not individual responses — three samples of one argument are one cluster. Robust-control score is the mean on the single `qualify_no_fatal_flaw` item; false-attack rate is the fraction of control grades that drew an `overclaim` penalty (an unearned fatal-flaw claim).

| Model | Mean | 95% item-CI | Centrality | Fidelity | Novelty | Impact | Robust-control score | False-attack rate | Items | Gens |
|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0.771 | [0.66, 0.88] | 0.72 | 0.86 | 0.75 | 0.82 | 0.521 | 67% | 6/6 | 18 |
| Sonnet 4.6 | 0.918 | [0.82, 0.99] | 0.92 | 0.94 | 0.89 | 0.94 | 0.667 | 33% | 6/6 | 18 |
| Opus 4.8 | 0.926 | [0.86, 0.98] | 0.92 | 0.93 | 0.90 | 0.96 | 0.783 | 0% | 6/6 | 18 |
| Fable 5 | 0.931 | [0.84, 0.99] | 0.93 | 0.94 | 0.89 | 0.96 | 0.721 | 0% | 6/6 | 18 |

Item-level mean rises Haiku 4.5 0.771 < Sonnet 4.6 0.918 < Opus 4.8 0.926 < Fable 5 0.931. Expected-capability check **Opus > Sonnet > Haiku: True**; Fable is reported without assuming a rank.

## What drove the score

Centrality and novelty separate the models most; fidelity and impact stay high across the board (Centrality Haiku 0.72 → Fable 0.93; Novelty Haiku 0.75 → Fable 0.89). This mirrors the main eval: the gap is mostly earned dimension credit, not penalty avoidance.

## Robust control (over-attack check)

There is a single robust-control item (eval_id [4], `aura-reproduction`): a deliberately qualified, property-relative argument where inventing a fatal flaw is the failure mode. Control-item means and false-attack rates: Haiku 4.5 0.521/67%, Sonnet 4.6 0.667/33%, Opus 4.8 0.783/0%, Fable 5 0.721/0%. **Caveat:** with only one control item (× 3 samples per model), these two columns are low-n and should be read as directional, not as a stable false-attack rate — unlike the main eval's six controls.

## Score by item

| eval_id | control | case_type | mean |
|---|---|---|---:|
| 0 | no | modal_overreach_from_single_case | 0.983 |
| 1 | no | false_analogy_overreach | 0.916 |
| 2 | no | circular_definition_unfalsifiable | 0.908 |
| 3 | no | question_begging_smuggled_value | 0.961 |
| 4 | yes | property_relative_qualified_control | 0.673 |
| 5 | no | equivocation_and_scope_overreach | 0.877 |

## Interpretation & limitations

- Measures how well a short critique matches a human-annotated central flaw under the v2 rubric, as judged by one fixed Opus grader — not conceptual reasoning in general. Treat as suggestive.
- **Only 6 items (1 control).** Item-level variance is large and the bootstrap CIs are wide and likely overlapping; do not over-read small mean gaps. The main submission (11 items, 6 controls) is the better-powered version.
- The grader sees the human annotation and may reward overlap with it; stronger models may raise valid critiques outside the annotated issue that the grader under-credits.
- Robust-control validity depends on the human judgment that the `aura` argument has no fatal flaw.
- A single fixed grader may favor its own critique style (Opus/Fable share lineage).

