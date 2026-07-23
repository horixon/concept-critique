# archive/v3_experiment — stricter grader (NOT promoted)

The **v3 grader** was an experiment to tighten detection of polished restatement,
operational substitution, and unearned logical labels (circular / unfalsifiable /
contradictory). It added a stricter prompt, extra diagnostic output fields, a
novelty gate, and an `acknowledged_only` novelty cap (≤0.25 instead of v2's blanket
→0).

**It was not promoted: its calibration did not pass all success gates.** On the
annotation-free Q0–Q2 unit-test set it improved operational-substitution recall
(0.50 → 0.80) and passed 5/7 gates, but the pure polished-restatement case was
scored too high (its concrete counterexample read as new reasoning without the
annotation's `non_novel_restatements` list), which also pulled the ordering
correlations just under threshold. Per holdout discipline the prompt was frozen and
the main eval was **not** regraded with v3. See `calibration_report_v3.md` for the
full gate table and anchor checks.

## What's here

- `eval_v3.py` — the v3 grader code.
- `critique_eval_grader_prompt_v3.txt` — the v3 grader prompt.
- `calibration_grades_v3.jsonl`, `calibration_report_v3.md`, `calibration_metrics_v3.json` — calibration outputs.

## Reproducing

`eval_v3.py` was written against the pre-reorg module layout (it imported the old
`eval_v2.py`). To run it, check out the commit that introduced v3 (before the
"Reorganize" commit); the top-level v2 pipeline in `eval.py` is the maintained one.
In the current layout, shared evaluation items and calibration inputs live under
`../../data/eval/` and `../../data/calibration/`. V3 changed the grader only; it
did not create a separate candidate-generation prompt or main-eval transcript set.
