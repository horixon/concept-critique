# Incomplete run artifacts

These files preserve an interrupted Questions 1–8 paired stress-test run. They are
not final results and must not be pooled with the primary 11-item evaluation or
cited as a completed follow-on experiment.

## Preserved state

- `transcripts.incomplete.jsonl`: 168 successful candidate critiques, covering
  14 retained items × 4 models × 3 samples. Candidate generation is complete for
  the retained set.
- `grades.incomplete.jsonl`: 168 attempted grade records; 115 succeeded and 53
  contain errors. Grading is incomplete.
- `runs.incomplete.jsonl`: generation and grading manifests for the interrupted
  run, including prompt, input, code, model, and experiment fingerprints.

No summary, model comparison, or paired analysis was produced from these partial
grades. Resume or retry the 53 failed grades, verify 168 successful grades, and
only then generate `results.json`, `automatic_results.md`, `paired_analysis.md`,
and a final report.

The `.incomplete` suffix is deliberate: it prevents the standard analysis commands
from silently treating these artifacts as a finished experiment.
