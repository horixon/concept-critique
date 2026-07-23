# Eval Results and Failure Inspection — v2

Grader: **opus** · v2 grades: 132 · grading failures: 0 · 5-point dimension scale, grader returns no item_score (harness recomputes), annotation score caps applied in code.

## Model results (v2)

Model score = mean over items of the per-item sample mean; 95% CI is a bootstrap over **items** (clusters), not responses.

| Model | Overall | 95% item-CI | Items | Gens | Centrality | Fidelity | Novelty | Impact | Control score | False attack rate | Mean words | Perfect |
|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0.583 | [0.48, 0.70] | 11 | 33 | 0.55 | 0.69 | 0.65 | 0.67 | 0.520 | 22% | 303 | 1 |
| Sonnet 4.6 | 0.716 | [0.61, 0.82] | 11 | 33 | 0.67 | 0.83 | 0.76 | 0.77 | 0.656 | 11% | 293 | 3 |
| Opus 4.8 | 0.816 | [0.74, 0.90] | 11 | 33 | 0.77 | 0.87 | 0.86 | 0.83 | 0.797 | 6% | 305 | 9 |
| Fable 5 | 0.829 | [0.75, 0.91] | 11 | 33 | 0.78 | 0.90 | 0.86 | 0.84 | 0.811 | 6% | 304 | 10 |

Expected Opus>Sonnet>Haiku holds: **True**; v2 ordering fable > opus > sonnet > haiku. All models cover 11/11 items.

## v1 → v2 comparison

- **Model ordering:** v1 fable > opus > sonnet > haiku; v2 fable > opus > sonnet > haiku; changed: **False**.
- **Mean compression:** overall mean 0.835 → 0.736 (down 0.099). Per model: Haiku 4.5 0.603→0.583; Sonnet 4.6 0.852→0.716; Opus 4.8 0.902→0.816; Fable 5 0.984→0.829.
- **Perfect scores (=1.0):** v1 80 → v2 23.
- **Novelty distribution:** v1 {'0.0': 3, '0.5': 27, '1.0': 102}; v2 {'0.0': 1, '0.5': 24, '0.75': 64, '1.0': 43}.
- **Robust-control false-attack rate:** Haiku 4.5 61%→22%; Sonnet 4.6 28%→11%; Opus 4.8 6%→6%; Fable 5 0%→6%.
- **Grader arithmetic failures:** v1 33 → v2 0 (v2 grader returns no item_score; nothing to miscompute).
- **Item-level changes > 0.20:** 40 of 132 graded candidates (historical comparison detail is preserved in git history; the active v2 aggregate is `../../eval_results.json`).
- **Caps fired (v2):** {'novelty_if_acknowledged_only': 12}.

## What v2 changed and why

v2 widens the dimension scale to 5 points, forces the grader to extract one main critique and check it against `explicit_concessions` / `non_novel_restatements` before scoring novelty, requires `minimum_full_credit_elements` for centrality 1, and moves score arithmetic entirely into the harness with annotation caps. The intended effect is to make full credit rare and to stop polished restatements and concession-repeats from scoring high. The comparison above shows whether ceiling saturation actually dropped (perfect-score count and mean compression).

## Length / reward-hacking check (v2)

Length–score Pearson (v2): 0.10. Full scores: Haiku 4.5 1, Sonnet 4.6 3, Opus 4.8 9, Fable 5 10.

## Interpretation & limitations

Recompute is authoritative; the v2 grader supplies dimensions and flags only. Caps are applied from structured flags (`already_acknowledged`→novelty, `disposition==no_valid_critique`→impact, control+`disposition==defeats`→total); the centrality secondary cap is enforced by the rubric scale at grading time (no dedicated flag). Monotonic ordering does not prove validity. Limitations carried from v1: the grader still sees the human annotation (overlap reward), valid off-annotation critiques may be under-credited, robust controls depend on the human no-fatal-flaw judgment, a single fixed grader may favor its own style, and 11 items give large item-level variance. Every model now covers all 11 items.
