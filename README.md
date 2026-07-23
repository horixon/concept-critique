# Concept-critique experiment harness

**Evaluation scope:** the primary reported result is the root 11-item v2 eval.
Everything under `experiments/` is separate follow-on work. See
[`EVALUATION_SCOPE.md`](EVALUATION_SCOPE.md).

A minimal, resumable harness for sampling Claude models on conceptual questions,
plus a graded **conceptual-critique evaluation** built on top of it. Each model
writes the strongest critique of a short argument; an Opus grader scores it against
a rubric; the harness recomputes the score in code and aggregates.

## Findings

Eval score = how well a model's critique matches a human-annotated central flaw
under the v2 rubric, graded by Opus. Model score is the mean over items of the
per-item sample mean; the interval is a 95% **item (cluster) bootstrap** — 11
arguments × 3 samples × 4 models = 132 critiques.

| model | score | 95% item-CI |
|---|---:|:--:|
| Haiku 4.5 | 0.583 | [0.48, 0.70] |
| Sonnet 4.6 | 0.716 | [0.61, 0.82] |
| Opus 4.8 | 0.816 | [0.74, 0.90] |
| Fable 5 | 0.829 | [0.75, 0.91] |

The sanity check **Opus > Sonnet > Haiku holds**, and Fable ranks highest (reported,
not assumed). Read this as suggestive, not validated: the top three CIs **overlap**,
it's only 11 items with one fixed grader, and the grader sees the human annotation.
The checks found little evidence that the ordering was explained by simple response
length (word-count↔score correlation ≈ 0.10; the limit is recorded, not enforced),
penalty avoidance, or unearned attacks on the six annotated controls. These checks
do not rule out nonlinear or stylistic grader effects. Ordering is unchanged under
equal weights.

**One sharp failure, honestly reported.** A stricter **v3** grader built to catch
polished restatement / operational substitution / unearned labels **failed two of
its encoded promotion gates** — the polished-restatement novelty check (0/2)
and Spearman correlation (0.68 < 0.70). Because it failed those gates, I **froze it
without using it to regrade the main evaluation; the results above are therefore the
v2 results.** Graded annotation-free, it had read a polished restatement's concrete
counterexample as new reasoning because it lacked the annotation's concession lists.
It's preserved with its evidence in `archive/v3_experiment/`. Full analysis:
`eval_failure_analysis.md` (main eval) and `calibration_report.md` /
`archive/v3_experiment/calibration_report_v3.md` (grader).

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Input format

A stream of JSON objects, normally one object per line. The exploratory runner also
accepts pretty-printed multi-line objects for hand-authored inputs. Fields:

| field      | required | notes |
|------------|----------|-------|
| `question` | yes      | the conceptual question / argument text |
| `id`       | no       | stable identifier (defaults to the line index) — used for resume keys |
| `args`     | no       | free-form dict. If it has `prompt_template`, the prompt is `template.format(question=..., **args)` |
| `system`   | no       | per-question system prompt (overrides `--system`) |
| `metadata` | no       | carried through to the transcript verbatim |

See `data/exploration/questions.example.jsonl`.

## Run

Copy `run.sh.example` → `run.sh` (gitignored), export `ANTHROPIC_API_KEY` in your
shell, and use the script as the canonical invocation. The script contains flags,
not credentials, and exits immediately if the environment variable is absent:

```bash
./run.sh            # full run
./run.sh --dry-run  # preview the planned matrix (extra args pass through)
```

`run.sh` calls `runner.py` under the hood; the direct form is:

```bash
python runner.py -i data/exploration/questions.example.jsonl -o transcripts.jsonl -n 3
```

Options:

- `-n/--samples` — samples per (question, model). Default 3.
- `-m/--models` — subset of `haiku sonnet opus fable`. Default: all four.
- `--max-tokens` — max output tokens per call. Default 8192.
- `--system` — global system prompt.
- `-c/--concurrency` — number of concurrent API calls. Default 1 (sequential).
- `--dry-run` — print the planned sample matrix and exit without calling the API.

### Preview what will run

```bash
python runner.py -i data/exploration/questions.example.jsonl -o transcripts.jsonl -n 2 --dry-run
```

`--dry-run` scans the output file for already-completed samples and prints only
what's still pending, e.g.:

```
DRY RUN — planned=12 already_done=1 to_run=11

  free-will: opus[1] haiku[0,1]
  ship-of-theseus: opus[0,1] haiku[0,1]
  trolley: opus[0,1] haiku[0,1]
```

### Run faster

```bash
python runner.py -i data/exploration/questions.example.jsonl -o transcripts.jsonl -n 5 -c 8
```

`-c/--concurrency` runs that many calls in parallel via a thread pool (the
`anthropic` client is shared and thread-safe). Transcripts are written from the
main thread as each call completes, so the output file stays valid and resumable
even mid-run. The SDK auto-retries 429/5xx with backoff, so modest concurrency
is usually safe; back off if you hit sustained rate limits.

Models (`runner.py:DEFAULT_MODELS`): `haiku`=claude-haiku-4-5,
`sonnet`=claude-sonnet-4-6, `opus`=claude-opus-4-8, `fable`=claude-fable-5.

## Output format

One transcript per line, kept lean — the raw `response` is the single source of
truth (content, `usage`, `stop_reason`, `stop_details` all live inside it), the
run is referenced by `run_id`, and empty fields are omitted rather than written
as null:

```jsonc
{
  "run_id": "20260720T211529Z-8d8429",  // -> full provenance in runs.jsonl
  "question_id": "0",
  "model_alias": "opus",
  "model_id": "claude-opus-4-8",
  "sample_number": 0,
  "timestamp": "2026-07-20T...Z",
  "system": "...",                       // omitted if none
  "prompt": "...",                        // exact user prompt sent
  "metadata": {...},                      // omitted if none
  "response": {...}                       // full serialized Messages response
                                          //   (.content, .usage, .stop_reason, ...)
  // on failure, "error": {type, message, traceback} replaces "response"
}
```

Helpers for pulling fields back out live in `report.py` (`split_content` →
thinking/answer text) and `runner.py` (`extract_text`).

## Reading a response for evaluation (PDF)

Render any single row to a human-readable PDF, keyed by the response message id
(`msg_...`, i.e. `response.id`):

```bash
python report.py msg_011CdE178ueavEXpHiHhyZL2 -o critique.pdf
```

or as a method:

```python
from report import render_pdf
render_pdf("msg_011CdE178ueavEXpHiHhyZL2", out="critique.pdf")
```

The PDF shows a provenance header (model, run_id, tokens, stop_reason, input/runner
hashes, git), then the system prompt, the prompt, any thinking summary, and the
response (or the error). Run `python report.py <bad-id>` to list every available
message id with its `model / question / sample`. Options: `-t` transcripts file,
`-r` runs manifest, `-o` output path (default `<message_id>.pdf`).

## Provenance & run history

As you iterate on `runner.py` and the questions file, every result stays
traceable to the exact versions that produced it — via the row's `run_id`, which
joins to a `runs.jsonl` entry (one per run) carrying the full provenance:

```jsonc
// one line per run in runs.jsonl (also the source of the PDF's header):
{
  "run_id": "20260720T191749Z-1ca086",   // unique per invocation
  "started_at": "2026-07-20T19:17:49Z",
  "runner_path": "/.../runner.py",
  "runner_sha256": "cb81ee98a067...",     // fingerprint of the runner code
  "git": {                                // null if not a git repo / git absent
    "commit": "4935835737...",            // commit runner.py lives in
    "branch": "main",
    "dirty": false                        // true => uncommitted changes present
  },
    "input_path": "data/exploration/questions.jsonl",
  "input_sha256": "2a8452232e53...",      // fingerprint of the questions file
  "argv": ["-i", "...", "-n", "3", ...],  // effective flags
  "models": {"opus": "claude-opus-4-8", ...},
  "samples": 3,
  "max_tokens": 8192,
  "finished_at": "2026-07-20T19:18:40Z",
  "output_path": "/.../transcripts.jsonl",
  "planned": 12, "skipped": 0, "succeeded": 12, "failed": 0
}
```

So `runner.py` changed → `runner_sha256` changes; questions edited → `input_sha256`
changes. Group or diff results by those hashes to compare across iterations.

`git` is captured best-effort: if the project is a git repo, results carry the
`commit` (so a `runner_sha256` maps to a viewable diff) and a `dirty` flag — a
`dirty: true` result came from code not fully captured by that commit, so commit
before a run you want to be able to reproduce exactly. Outside a git repo it's
`null` and the SHA-256 hashes remain the source of truth.

One such line is appended per invocation (`runs.jsonl` by default, `--manifest`
to change) — a chronological log of every run, including no-op resumes. Each
transcript row stores only the `run_id`; join on it to recover the full
provenance above (that's exactly what the PDF header does). The `run_id` and
short hashes are printed to stderr at the start and end of each run.

`runs.jsonl` is gitignored (via `*.jsonl`) as local history; drop the ignore rule
if you'd rather track run history in git.

## Resumability (experiment-safe)

Each sample is keyed by `(experiment_id, question_id, model_id, sample_number)`,
where `experiment_id = sha256(prompt + system + generation config)`. On startup the
harness scans the output file and skips any key that already succeeded (a row with
no `error`). Because the key carries the fingerprint, a stored response is reused
**only when the prompt, system instruction, model, and config are unchanged** —
editing a question, prompt, or `max_tokens` changes the fingerprint and forces
regeneration instead of silently reusing a stale answer. Failed attempts are retried;
the file is written line-buffered, so interrupting mid-run leaves a resumable file.
Legacy rows without a stored fingerprint have it recomputed from their prompt/system,
so pre-fingerprint runs still resume. (See `tests/test_resume.py`.)

To change how many samples exist, bump `-n` and re-run against the same output file —
only the missing samples are generated.

## Notes

- **No refusal fallbacks.** Fable 5 can return `stop_reason: "refusal"`; this
  harness records that verbatim rather than transparently re-serving the request
  on another model. Silent fallbacks would contaminate a per-model comparison, so
  they are deliberately omitted. Refusals show up as successful transcripts with
  `stop_reason: "refusal"` and (usually) empty `response_text`.
- **Uniform call shape.** No `temperature`/`top_p`/`thinking` are set, so the same
  request works across all four models (Fable 5 rejects those and thinks
  adaptively on its own). Add per-model config in `call_model` if you need it.
- **Fable 5 requires 30-day data retention** on your org (not available under
  zero-data-retention). If every Fable call 400s, check the org retention setting.
- Calls are sequential by default; `--concurrency N` enables a bounded thread
  pool while keeping all JSONL writes on the main thread.

---

# Conceptual critique eval (`eval.py`)

`eval.py` is the **authoritative evaluation** (v2 rubric). Each model critiques a
set of conceptual arguments; an Opus grader scores each critique on a 5-point
per-dimension scale and returns structured flags (no `item_score`); the harness
recomputes the score in code and applies the annotation score caps. Built on
`runner.py` (client, model IDs, streaming, provenance, concurrency, fingerprinted
resume).

Superseded work is under `archive/`: the original 3-point grader in `archive/v1/`,
and the stricter v3 grader — **not promoted, its calibration did not pass** — in
`archive/v3_experiment/`. Each archive dir has a README.

## Files

```
eval.py        # authoritative eval: merge / generate / grade / summarize
runner.py      # concept-critique harness + shared LLM/provenance/resume helpers
analysis.py    # failure inspection + report artifacts (recompute-only)
calibrate.py   # grader calibration on the Q0–Q2 unit-test set
report.py      # render one transcript row to a PDF
prompts/candidates/   # versioned prompts sent to candidate models
data/           # versioned exploration, eval, and calibration inputs
tests/         # deterministic eval, resume, and experiment tests (no API)
archive/v1/    # original grader (evidence + README)
archive/v3_experiment/   # stricter v3 grader, not promoted (+ README)
writeup/       # report + figure tooling (not part of the eval; own README)
```

## Inputs (versioned)

- `data/eval/critique_eval_annotated_items.jsonl` (base) + `data/eval/critique_eval_annotation_overrides_v2.jsonl` → merged into `data/eval/critique_eval_annotated_items_v2.jsonl`.
- `prompts/candidates/critique_300w_v1.txt` — fixed candidate-generation prompt for the final results.
- `critique_eval_rubric_v2.md`, `critique_eval_grader_prompt_v2.txt`.

The versions are independent: the item set supplies `question`, `argument`, and
grader-only `annotation`; the candidate prompt generates a critique; the grader
prompt + rubric judge the stored critique; Python owns the scoring policy. The
v1/v2/v3 labels in `archive/` describe **grader revisions**, not candidate-prompt
revisions. This separation permits regrading stored critiques without regenerating
them, or testing a new candidate prompt without silently mixing experiments.

## Reproduce

```bash
export ANTHROPIC_API_KEY=...

python eval.py merge                                   # -> data/eval/critique_eval_annotated_items_v2.jsonl
python eval.py generate --models haiku sonnet opus fable --samples 3 \
  --candidate-prompt prompts/candidates/critique_300w_v1.txt           # -> eval_transcripts.jsonl
python eval.py grade    --grader opus                  # -> eval_grades.jsonl
python eval.py summarize                               # -> eval_results.json, eval_results.md
python analysis.py                                     # -> eval_failure_analysis.md, eval_failure_examples.json,
                                                       #    eval_model_scores.csv/.png
python calibrate.py                                    # grader calibration -> calibration_report.md, calibration_metrics.json
```

Every phase is append-only and resumable. Generation resume is fingerprinted
(see **Resumability** above), so editing an item or candidate prompt regenerates
only candidates whose rendered prompt changed. Newly generated transcript rows
record the candidate-prompt version and SHA-256; legacy stored rows remain valid
because their exact rendered prompt already participates in the resume fingerprint.
Grades separately record the grader prompt and rubric in their run provenance.

## Scoring

`item_score = clip(0.35·centrality + 0.25·argument_fidelity + 0.20·novelty + 0.20·justified_impact − min(Σpenalties, 0.25), 0, 1)`,
**recomputed in code** from validated grader values — the grader returns no score.
Annotation caps are applied from the grader's structured flags: `already_acknowledged`
→ novelty cap, `disposition == "no_valid_critique"` → impact cap, control item +
`disposition == "defeats"` → total cap. Invalid grader JSON triggers one repair retry,
then the grade is recorded as an error rather than coerced.

## Aggregation & uncertainty

The model score is `mean_over_items(mean_over_samples)` — three samples of one
argument are a cluster, not three independent tests — and the 95% CI is a **bootstrap
over items** (weights every argument equally; uncertainty reflects generalization
across arguments). Reports show items covered and successful generations per model.

## Outputs

- `eval_transcripts.jsonl` — one candidate critique per row (with `experiment_id`, `max_tokens`).
- `eval_grades.jsonl` — one grade per row (5-point dims, flags, penalties, recomputed `item_score`, `caps_applied`, `grader_raw_response`).
- `eval_results.json` / `eval_results.md` — aggregates (item-level means + item-bootstrap CIs, dimensions, penalties, robust-control vs flaw, equal-weight sensitivity, length correlation).
- `eval_failure_analysis.md`, `eval_failure_examples.json`, `eval_model_scores.csv/.png` — failure inspection (from `analysis.py`).
- `eval_runs.jsonl` — per-phase provenance (run_id, git commit, input hashes, counts).

## Tests

Focused, deterministic, no API calls and no test-framework dependency:

```bash
python3 tests/test_eval.py
python3 tests/test_resume.py
python3 tests/test_experiments.py
```

- `tests/test_eval.py` — score calculation + clipping, penalty cap, novelty/control/impact caps, invalid grader values, malformed-JSON repair, duplicate-record selection, per-item (cluster) aggregation, partial coverage, robust-control identification, over-limit recording (fixtures in `tests/fixtures/`).
- `tests/test_resume.py` — experiment-fingerprint resume isolation (edited prompt/system/config regenerates; unchanged resumes; legacy rows resume).
- `tests/test_experiments.py` — paired-item construction, role blinding,
  synthetic prompt rendering, and annotation/classifier schema validation.

## Grader calibration

`calibrate.py` runs the grader on 18 hand-labeled Q0–Q2 critiques (annotation-free)
and compares to `human_label` — dimension agreement, penalty precision/recall,
disposition accuracy, Spearman, pairwise ordering. It's a unit test of rubric
*implementation*, not evidence the rubric generalizes.

## Follow-on experiments

The root evaluation remains the single authoritative primary eval. Independent
studies live under `experiments/<name>/`, with their own protocol, inputs, outputs,
and reproduction commands. See `experiments/README.md` for the shared contract.

- `experiments/art_design/` contains the existing ungraded exploration and the
  separate six-item graded extension.
- `experiments/controlled_variants/` tests whether critiques change when one
  argument is flawed, repaired, or explicitly excludes operational objections.
- `experiments/questions_1_8/` pairs eight robust arguments with eight minimally
  changed flawed counterparts and uses explicitly synthetic, pre-generation
  references. Its results are a separate stress test, not human-ground-truth scores.

Experiment scores must not be pooled with the 11-item main result.
