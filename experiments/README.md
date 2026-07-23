# Follow-on experiment layout

The repository has one authoritative evaluation at the root. Everything under
this directory is an independent study and must write to its own folder; results
from different item sets are never silently pooled.

Each experiment should contain:

```text
experiments/<name>/
├── README.md                 # purpose, validity boundary, exact commands
├── input/                    # immutable source and evaluation-ready items
├── transcripts.jsonl        # candidate generations (created by a run)
├── grades.jsonl              # v2 grades, only when annotations exist
├── results.json              # machine-readable summary
└── report.md                 # human-readable findings
```

The shared components remain at the repository root:

- `eval.py`: fixed v2 generation, grading, and summary pipeline.
- `runner.py`: flexible ungraded exploration runner.
- `prompts/candidates/critique_300w_v1.txt`: fixed candidate prompt.
- `critique_eval_grader_prompt_v2.txt` and `critique_eval_rubric_v2.md`: fixed grader.

Use `eval.py generate` when comparing studies under the same candidate prompt.
Use `runner.py` only when prompt variation is itself part of an explicitly
ungraded exploration. A JSONL file with only questions and arguments is enough
for generation, but `eval.py grade` additionally requires frozen reference
annotations. Human references are preferred. If a follow-on uses synthetic
references, they must be generated before candidate responses, role-separated,
versioned, and labeled synthetic in every report. Never infer references from the
candidate answers being graded.

Every experiment README should say whether it is (a) ungraded exploration,
(b) human-annotated, or (c) synthetic-annotated. Commit inputs and code before
paid API runs when provenance matters; the harness will still record hashes and
a dirty working-tree flag.
