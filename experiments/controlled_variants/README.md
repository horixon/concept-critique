# Controlled variants: argument-sensitive critique

Status: **ready to run as a separate graded experiment**.

This study holds the conceptual question and candidate prompt fixed while
changing only the argument: flawed (`source_id=1000`), repaired (`1001`), and an
operational-decoy control (`1002`). The primary outcome is sensitivity to the
contrast, not which model has the highest overall mean.

## Inputs

- `input/source.jsonl`: the author's original runner-schema dataset, preserved
  unchanged for provenance.
- `input/items.jsonl`: evaluation-ready records. These are the already frozen
  v2 annotations for source items 1000–1002, selected from the main item set;
  they were not inferred from new candidate responses.
- `PROTOCOL_SOURCE.md`: the supplied experiment design, preserved verbatim.
- `DESIGN.md`: the corrected executable design. It resolves an important mismatch
  between critique-quality scores and argument-flaw severity.
- `synthetic_classify.py`: two model-blinded response classifiers; only exact
  consensus codes are analyzed.

The evaluation ids are `0,1,2`; use `source_id` for variant labels 1000–1002.

## Exact run

Run from the repository root:

```bash
export ANTHROPIC_API_KEY=...
python3 eval.py generate \
  --items experiments/controlled_variants/input/items.jsonl \
  --candidate-prompt prompts/candidates/critique_300w_v1.txt \
  --models haiku sonnet opus fable --samples 3 --concurrency 6 \
  --output experiments/controlled_variants/transcripts.jsonl \
  --manifest experiments/controlled_variants/runs.jsonl
python3 eval.py grade \
  --items experiments/controlled_variants/input/items.jsonl \
  --transcripts experiments/controlled_variants/transcripts.jsonl \
  --grader opus --concurrency 6 \
  --output experiments/controlled_variants/grades.jsonl \
  --manifest experiments/controlled_variants/runs.jsonl
python3 eval.py summarize \
  --items experiments/controlled_variants/input/items.jsonl \
  --transcripts experiments/controlled_variants/transcripts.jsonl \
  --grades experiments/controlled_variants/grades.jsonl \
  --json-output experiments/controlled_variants/results.json \
  --markdown-output experiments/controlled_variants/automatic_results.md \
  --report-title "Controlled Variant Experiment — Automatic v2 Results"
python3 experiments/controlled_variants/synthetic_classify.py \
  --classifiers fable sonnet --concurrency 6
python3 experiments/controlled_variants/analyze.py
```

Candidate generation, grading, and raw synthetic classification are append-only
and resumable. Consensus CSVs and reports are deterministically rebuilt.

## Analysis contract

Report, by model and variant: mean v2 score, major-attack rate (`defeats`), and
operational-substitution rate. The score contrasts below are diagnostics only:

```text
repair_delta  = mean_score(1001) - mean_score(1000)
control_delta = mean_score(1002) - mean_score(1000)
```

Do **not** interpret a positive score delta as evidence that the repaired argument
is better. The score measures critique quality, not argument soundness; a strong
critique can score highly on every variant for different reasons. Blindly classify
the main critique using `DESIGN.md`. The primary finding is whether a model retires
the historical-fidelity objection after repair, lowers severity, and avoids
implementation complaints on 1002. Synthetic classifier agreement and excluded
rows must be reported. Do not claim the three variants provide a population-level
confidence interval.
