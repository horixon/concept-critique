# Prompt catalog

Prompt families are versioned independently so changing how critiques are
generated is not confused with changing how stored critiques are graded.

| Stage | Current input | Role |
|---|---|---|
| Candidate generation | `candidates/critique_300w_v1.txt` | Receives `question` and `argument`; produces a critique |
| Grading | `../critique_eval_grader_prompt_v2.txt` | Receives the item, annotation, stored critique, and rubric; produces structured judgments |
| Rubric | `../critique_eval_rubric_v2.md` | Defines dimensions, allowed values, penalties, and principles |
| Scoring policy | `../eval.py` | Validates judgments and deterministically computes caps and scores |

The historical v1/v2/v3 labels refer to **grader iterations**. The candidate
prompt used for the final and art/design graded runs remained the same.

To test another candidate elicitation without changing items or the grader:

```bash
python3 eval.py generate \
  --candidate-prompt prompts/candidates/my_candidate_prompt.txt \
  --output my_candidate_transcripts.jsonl
```

A candidate template must contain both `{question}` and `{argument}`. Its rendered
text participates in the resume fingerprint, so changing the template cannot
silently reuse responses produced by an earlier prompt.

`synthetic/` contains prompts for explicitly synthetic follow-on labeling. They
are not part of the primary v2 result:

- `item_annotation_v1.txt`: independent blind item-annotation passes.
- `item_reconciliation_v1.txt`: constrained synthesis after label agreement.
- `response_classifier_v1.txt`: blind coding of controlled-variant responses.
