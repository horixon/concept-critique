# Evaluation scope and result sets

## Primary reported evaluation

Only the **11-item root v2 evaluation** and its documented development evidence:

- `data/eval/critique_eval_annotated_items_v2.jsonl`
- `eval_transcripts.jsonl`, `eval_grades.jsonl`, `eval_results.json`, `eval_results.md`
- `eval_failure_analysis.md`
- grader calibration evidence and archived v1/v3 development history

The primary reported score is the root evaluation's 11-item, 132-critique result.

### Annotation provenance

The primary item labels are **AI-assisted reference annotations**, not independent
human ground truth. Some judgments and initial drafts came from the author, but AI
tools substantially rewrote and expanded the structured fields (including central
issues, concessions, weak objections, and full-credit requirements). The author
selected and used the final references, but had not completed a blind, independent
human re-annotation before the reported run.

Accordingly, the evaluation measures agreement with these frozen reference
judgments under one fixed grader. Annotation anchoring and reasonable disagreement
about items 4, 6, 7, and 10 remain explicit validity limitations. The reported v2
scores remain frozen; any later human review should be reported as a post-hoc audit
or sensitivity analysis, not silently substituted into the primary result.

## Separate follow-on results

Everything under `experiments/`:

- `experiments/art_design/`: completed follow-on exploration/extension.
- `experiments/controlled_variants/`: separate three-variant study.
- `experiments/questions_1_8/`: separate paired synthetic-reference stress test.

These studies may be discussed as subsequent work, but their items, generations,
grades, and scores must never be pooled with or presented as validation of the
primary 11-item result.
