# Input data

This directory contains versioned inputs only. Generated transcripts, grades,
run manifests, reports, and plots remain outside `data/`.

```text
data/
├── exploration/
│   ├── questions.example.jsonl          # minimal runner example
│   └── questions.jsonl                  # Part 0/1 conceptual questions
├── eval/
│   ├── critique_eval_annotated_items.jsonl
│   ├── critique_eval_annotation_overrides_v2.jsonl
│   └── critique_eval_annotated_items_v2.jsonl
└── calibration/
    └── q0_q2_rubric_calibration_labeled.jsonl
```

The `eval.py merge` command deterministically constructs the v2 items by copying
the base items and overlaying only the named annotation fields from the v2
overrides. Questions and arguments are preserved unchanged.

Files use JSON objects as records. The evaluation and calibration files are
strict one-object-per-line JSONL. The exploratory runner additionally accepts
pretty-printed, multi-line JSON objects for easier hand authoring.

Self-contained follow-on studies, including their inputs and outputs, live under
`experiments/`. This directory is reserved for the primary evaluation.
