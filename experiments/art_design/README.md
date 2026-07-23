# Art/design experiments

This folder preserves two distinct studies. Neither changes or extends the
11-item score reported by the root evaluation.

## Ungraded exploration

`exploration/` uses six item-specific prompts and therefore measures qualitative
prompt/model behavior, not the fixed v2 eval. Rebuild its descriptive report:

```bash
python3 experiments/art_design/exploration/report.py
```

## Graded extension

`eval/` uses six annotated art/design arguments with the same candidate prompt,
v2 grader, rubric, and scoring code as the main eval. Reproduce or resume it:

```bash
python3 eval.py generate \
  --items experiments/art_design/eval/items.jsonl \
  --output experiments/art_design/eval/transcripts.jsonl --samples 3 \
  --manifest experiments/art_design/eval/runs.jsonl
python3 eval.py grade \
  --items experiments/art_design/eval/items.jsonl \
  --transcripts experiments/art_design/eval/transcripts.jsonl \
  --output experiments/art_design/eval/grades.jsonl \
  --manifest experiments/art_design/eval/runs.jsonl
python3 eval.py summarize \
  --items experiments/art_design/eval/items.jsonl \
  --transcripts experiments/art_design/eval/transcripts.jsonl \
  --grades experiments/art_design/eval/grades.jsonl \
  --json-output experiments/art_design/eval/results.json \
  --markdown-output experiments/art_design/eval/results.md \
  --report-title "Art & Design Conceptual Critique Eval — Results (v2 grader)"
python3 experiments/art_design/eval/report.py
```

The set is small (six items and one robust control), so its intervals and
false-attack estimate are directional. Its structured labels are AI-assisted
references, not independent human ground truth. Do not pool it with the main evaluation.
