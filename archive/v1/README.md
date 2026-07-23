# archive/v1 — original grader (superseded)

The **v1 grader** was the first version of the critique eval. It used a 3-point
dimension scale `{0, 0.5, 1}`, a grader that returned its own `item_score` (which
the harness recomputed and often disagreed with), and no annotation score caps.
It was superseded by the **v2 grader**, which is now the authoritative pipeline in
the top-level `eval.py` (5-point scale, structured flags, code-applied caps).

## What's here (evidence, kept for the write-up)

- `critique_eval_rubric_updated.md`, `critique_eval_grader_prompt.txt` — v1 inputs.
- `eval_grades.jsonl` — v1 grades.
- `eval_results.json`, `eval_results.md` — v1 aggregates.
- `eval_failure_analysis.md`, `eval_failure_examples.json`,
  `eval_model_scores.csv`, `eval_model_scores.png` — v1 failure analysis + figures.
- `v1_to_v2_comparison.md` — the v1→v2 comparison (perfect-score count, mean
  compression, novelty distribution, control false-attack rates).

## Reproducing v1

The v1 grader code is preserved in git history (it was the pre-reorganization
`eval.py`). The candidate transcripts (`../../eval_transcripts.jsonl`) are shared
and unchanged, and the current items live at
`../../data/eval/critique_eval_annotated_items_v2.jsonl`. For exact historical
reproduction, check out the pre-reorganization commit rather than mixing its
`eval.py` with the current layout. The active pipeline uses the independently
versioned candidate prompt under `../../prompts/candidates/`.
