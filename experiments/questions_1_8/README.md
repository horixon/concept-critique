# Questions 1–8: paired robust/flawed stress test

Status: **incomplete run preserved; grading must be resumed before analysis**.

The partial run artifacts are intentionally named `*.incomplete.jsonl` and are
documented in [`INCOMPLETE_RESULTS.md`](INCOMPLETE_RESULTS.md). They are retained
for provenance and resumability, not presented as results.

This is a separate follow-on experiment, not part of the primary 11-item eval.
Each of the eight supplied careful arguments is paired with a minimally changed
counterpart containing one concluding conceptual failure. The study tests both
restraint on robust arguments and flaw detection on nearby flawed arguments.

## Design and inputs

- `input/source.jsonl`: original supplied runner-schema file, unchanged.
- `input/items.unannotated.jsonl`: original eight normalized for fixed-prompt
  generation, retained as provenance but superseded by the paired design.
- `build_pairs.py`: deterministic robust/flawed pair construction.
- `input/items.paired.unannotated.jsonl`: 16 frozen items shown to synthetic
  annotators; it contains no intended role labels.
- `input/pair_manifest.jsonl`: intended robust/flawed roles, used only in final
  analysis and never loaded by `synthetic_annotate.py`.
- `input/items.annotated.jsonl`: created only after two annotation passes agree
  and a separate constrained reconciliation succeeds.

The flawed variants append a conspicuous concluding overreach. This is a sharp
repair-sensitivity test, not a naturalistic estimate of all conceptual flaws.

## Exact run order

Run from the repository root. Do not generate candidate critiques until Step 1
has frozen the synthetic references.

### 1. Build and annotate items before candidate generation

```bash
export ANTHROPIC_API_KEY=...
python3 experiments/questions_1_8/build_pairs.py
python3 experiments/questions_1_8/synthetic_annotate.py \
  --annotators fable sonnet --reconciler haiku --concurrency 6
```

The annotators see only question and argument—not item role, candidate responses,
model identities, or expected rankings. Items are excluded when the annotators
disagree about flaw existence/disposition or either reports low confidence. If
one member of a pair is excluded, its pair mate is also excluded. Raw passes,
reconciliations, and exclusions remain auditable.

### 2. Generate fixed-prompt candidates on retained items

```bash
python3 eval.py generate \
  --items experiments/questions_1_8/input/items.annotated.jsonl \
  --candidate-prompt prompts/candidates/critique_300w_v1.txt \
  --models haiku sonnet opus fable --samples 3 --concurrency 6 \
  --output experiments/questions_1_8/transcripts.jsonl \
  --manifest experiments/questions_1_8/runs.jsonl
```

The maximum is 192 responses (16 items × 4 models × 3 samples); exclusions reduce
that number. Report the actual denominator.

For the preserved run, annotation retained 14 items and generation completed all
168 expected candidates. Rename or copy the incomplete artifacts to the canonical
paths in the commands below before resuming; do not regenerate completed candidates.

### 3. Grade, summarize, and build paired analysis

```bash
python3 eval.py grade \
  --items experiments/questions_1_8/input/items.annotated.jsonl \
  --transcripts experiments/questions_1_8/transcripts.jsonl \
  --grader opus --concurrency 6 \
  --output experiments/questions_1_8/grades.jsonl \
  --manifest experiments/questions_1_8/runs.jsonl
python3 eval.py summarize \
  --items experiments/questions_1_8/input/items.annotated.jsonl \
  --transcripts experiments/questions_1_8/transcripts.jsonl \
  --grades experiments/questions_1_8/grades.jsonl \
  --json-output experiments/questions_1_8/results.json \
  --markdown-output experiments/questions_1_8/automatic_results.md \
  --report-title "Questions 1–8 Paired Stress Test — Synthetic References"
python3 experiments/questions_1_8/analyze.py
```

Use `paired_analysis.md` as the basis for the final `report.md`. Lead with the
joint detection/restraint pattern, annotation agreement and excluded pairs—not
the overall model score.

## Validity boundary

These are model-generated references, not human ground truth. Fable and Sonnet
annotate independently, Haiku reconciles only agreed labels, and Opus grades.
Role separation reduces direct self-grading but does not remove shared model-family
bias. Results must remain separate from the primary evaluation, controlled variants, and
art/design experiments.
