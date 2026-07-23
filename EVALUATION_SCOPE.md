# Evaluation scope and result sets

## Primary reported evaluation

Only the **11-item root v2 evaluation** and its documented development evidence:

- `data/eval/critique_eval_annotated_items_v2.jsonl`
- `eval_transcripts.jsonl`, `eval_grades.jsonl`, `eval_results.json`, `eval_results.md`
- `eval_failure_analysis.md`
- grader calibration evidence and archived v1/v3 development history

The primary reported score is the root evaluation's 11-item, 132-critique result.

## Separate follow-on results

Everything under `experiments/`:

- `experiments/art_design/`: completed follow-on exploration/extension.
- `experiments/controlled_variants/`: separate three-variant study.
- `experiments/questions_1_8/`: separate paired synthetic-reference stress test.

These studies may be discussed as subsequent work, but their items, generations,
grades, and scores must never be pooled with or presented as validation of the
primary 11-item result.
