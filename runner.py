#!/usr/bin/env python3
"""Minimal experiment harness for sampling Claude models on conceptual questions.

Reads conceptual questions + arguments from a JSONL file, calls each configured
Claude model multiple times via the Anthropic Messages API, and appends a
complete transcript per sample to a JSONL output file.

Runs are resumable: on startup the output file is scanned and any successful
(prompt/config fingerprint, question, exact model, sample) key is skipped.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import anthropic

# Alias -> exact model ID. Edit here to add/retire models.
# IDs are current as of the Anthropic model catalog; do not append date suffixes.
DEFAULT_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
    "fable": "claude-fable-5",
}


def experiment_id(prompt: str, system: str | None, max_tokens: int) -> str:
    """Fingerprint of everything that determines the response for a sample except
    the model and sample index: the exact prompt (which encodes question, args,
    template, and argument), the system instruction, and the generation config.

    Folding this into the completion key means a stored response is reused only
    when the question/prompt/system/config are unchanged — editing any of them
    changes the fingerprint and forces regeneration instead of silently reusing
    a stale answer.
    """
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8"))
    h.update(b"\x00")
    h.update((system or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(str(max_tokens).encode("utf-8"))
    return h.hexdigest()[:16]


@dataclass(frozen=True)
class SampleKey:
    """Identifies one transcript, fingerprinted so a config change can't be silently reused."""

    experiment_id: str      # fingerprint of prompt + system + generation config
    question_id: str
    model_id: str
    sample_number: int


@dataclass
class Job:
    """One unit of work: a single API call to make."""

    record: dict[str, Any]
    prompt: str
    system: str | None
    alias: str
    model_id: str
    sample_number: int
    max_tokens: int

    @property
    def key(self) -> SampleKey:
        return SampleKey(
            experiment_id(self.prompt, self.system, self.max_tokens),
            self.record["id"],
            self.model_id,
            self.sample_number,
        )

    @property
    def label(self) -> str:
        return f"{self.record['id']} | {self.alias} | sample {self.sample_number}"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def sha256_file(path: str) -> str:
    """Full SHA-256 of a file's bytes — the version fingerprint for code/input."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_info() -> dict[str, Any] | None:
    """Best-effort git state of the runner's repo, or None if not a repo / git absent.

    Ties a runner_sha256 to a viewable commit. `dirty` flags uncommitted changes,
    so a result marked dirty came from code that isn't fully captured by `commit`.
    """
    repo_dir = os.path.dirname(os.path.abspath(__file__))

    def _git(*cmd: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *cmd],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return None  # not a git repo, or git unavailable
    return {
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
    }


def build_provenance(args: argparse.Namespace, models: dict[str, str]) -> dict[str, Any]:
    """Fingerprint the run: which runner code + which input file + which flags.

    Stamped into every transcript so a result is always traceable to the exact
    runner.py and questions JSONL that produced it, even as both change.
    """
    started = _now_iso()
    return {
        "run_id": _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:6],
        "started_at": started,
        "runner_path": os.path.abspath(__file__),
        "runner_sha256": sha256_file(__file__),
        "git": git_info(),
        "input_path": args.input,
        "input_sha256": sha256_file(args.input),
        "argv": sys.argv[1:],
        "models": models,
        "samples": args.samples,
        "max_tokens": args.max_tokens,
    }


def load_questions(path: str) -> list[dict[str, Any]]:
    """Load conceptual questions from a JSONL file.

    Each line is a JSON object. Recognized fields:
      id         (str)  optional  - stable identifier; defaults to line index
      question   (str)  REQUIRED  - the conceptual question / argument text
      args       (dict) optional  - free-form arguments. If it contains
                                    "prompt_template", the prompt is built as
                                    template.format(question=..., **args).
      system     (str)  optional  - per-question system prompt override
      metadata   (dict) optional  - carried through to the transcript verbatim
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    # Parse a stream of JSON objects separated by whitespace/newlines. This
    # accepts both compact JSONL (one object per line) and pretty-printed /
    # multi-line objects, so hand-authored files just work.
    decoder = json.JSONDecoder()
    questions: list[dict[str, Any]] = []
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        try:
            record, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}: invalid JSON near offset {idx}: {exc}") from exc
        idx = end
        if not isinstance(record, dict):
            raise SystemExit(f"{path}: top-level values must be objects, got {type(record).__name__}")
        if "question" not in record:
            raise SystemExit(f"{path}: a record is missing the required 'question' field")
        record.setdefault("id", str(len(questions)))
        record["id"] = str(record["id"])
        questions.append(record)
    return questions


def build_prompt(record: dict[str, Any]) -> str:
    """Construct the user prompt from a question record.

    Defaults to the raw question. If args.prompt_template is provided, it is
    formatted with every arg as a named field, plus the top-level `question`
    (which overrides any `question` inside args, so both may be present).
    """
    args = record.get("args") or {}
    template = args.get("prompt_template")
    if not template:
        return record["question"]
    fields = {**args, "question": record["question"]}
    try:
        return template.format(**fields)
    except KeyError as exc:
        raise SystemExit(
            f"question {record['id']}: prompt_template references {{{exc.args[0]}}} "
            f"but it is not present in args (have: {sorted(args)})"
        ) from exc


def resolve_system(record: dict[str, Any], global_system: str | None) -> str | None:
    """Pick the system prompt: top-level `system`, then args.system, then --system."""
    if record.get("system") is not None:
        return record["system"]
    args = record.get("args") or {}
    if args.get("system") is not None:
        return args["system"]
    return global_system


def build_jobs(
    questions: list[dict[str, Any]],
    models: dict[str, str],
    samples: int,
    global_system: str | None,
    max_tokens: int,
) -> list[Job]:
    """Expand questions x models x samples into the full job list (nothing filtered)."""
    jobs: list[Job] = []
    for record in questions:
        prompt = build_prompt(record)
        system = resolve_system(record, global_system)
        for alias, model_id in models.items():
            for sample_number in range(samples):
                jobs.append(Job(record, prompt, system, alias, model_id, sample_number, max_tokens))
    return jobs


def load_completed(path: str, max_tokens: int) -> set[SampleKey]:
    """Scan an existing output file and return the set of successfully completed keys.

    A record counts as completed only if its "error" field is null, so failed
    attempts are retried on the next run. Each key carries the sample's experiment
    fingerprint; legacy rows without a stored `experiment_id` have it recomputed
    from their prompt/system/max_tokens, so a resume matches only when the current
    prompt/system/config are identical.
    """
    completed: set[SampleKey] = set()
    if not os.path.exists(path):
        return completed
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                # Tolerate a torn final line from a previous interrupted run.
                continue
            if rec.get("error") is not None:
                continue
            try:
                model_id = rec.get("model_id") or DEFAULT_MODELS[rec["model_alias"]]
                eid = rec.get("experiment_id") or experiment_id(
                    rec["prompt"], rec.get("system"), rec.get("max_tokens", max_tokens))
                key = SampleKey(eid, str(rec["question_id"]), str(model_id), int(rec["sample_number"]))
            except (KeyError, TypeError, ValueError):
                continue
            completed.add(key)
    return completed


def call_model(
    client: anthropic.Anthropic,
    model_id: str,
    system: str | None,
    prompt: str,
    max_tokens: int,
) -> dict[str, Any]:
    """Call the Messages API once and return the full serialized message.

    Streaming is used so large max_tokens values don't trip the SDK's
    request-timeout guard; get_final_message() reassembles the complete message.
    Sampling params (temperature/top_p) and thinking config are intentionally
    omitted so the same call shape works across all four models — notably
    Fable 5, which rejects those and runs adaptive thinking implicitly.
    """
    kwargs: dict[str, Any] = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    with client.messages.stream(**kwargs) as stream:
        message = stream.get_final_message()
    return message.to_dict()


def extract_text(response: dict[str, Any]) -> str:
    """Join the text of all text blocks in a response content array."""
    parts = [
        block.get("text", "")
        for block in response.get("content", [])
        if block.get("type") == "text"
    ]
    return "".join(parts)


def execute_job(
    client: anthropic.Anthropic,
    job: Job,
    max_tokens: int,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Run one job and return its transcript row.

    Rows are kept lean: the run is referenced by `run_id` (full provenance lives
    once per run in the manifest), the raw `response` is the single source of
    truth for content/usage/stop_reason, and empty fields are omitted rather
    than written as null. On failure `error` replaces `response`.
    """
    record: dict[str, Any] = {
        "run_id": provenance["run_id"],
        "question_id": job.record["id"],
        "model_alias": job.alias,
        "model_id": job.model_id,
        "sample_number": job.sample_number,
        "timestamp": _now_iso(),
    }
    if job.system:
        record["system"] = job.system
    record["prompt"] = job.prompt
    record["max_tokens"] = max_tokens
    record["experiment_id"] = experiment_id(job.prompt, job.system, max_tokens)
    metadata = job.record.get("metadata")
    if metadata:
        record["metadata"] = metadata

    try:
        record["response"] = call_model(client, job.model_id, job.system, job.prompt, max_tokens)
    except Exception as exc:  # noqa: BLE001 - record every failure, keep going
        record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    return record


def print_matrix(jobs: list[Job], completed: set[SampleKey]) -> None:
    """Print the planned sample matrix without calling the API."""
    # Group pending sample numbers per (question_id, alias), preserving order.
    order: list[str] = []
    pending: dict[str, dict[str, list[int]]] = {}
    n_pending = 0
    for job in jobs:
        if job.key in completed:
            continue
        n_pending += 1
        qid = job.record["id"]
        if qid not in pending:
            pending[qid] = {}
            order.append(qid)
        pending[qid].setdefault(job.alias, []).append(job.sample_number)

    print(f"DRY RUN — planned={len(jobs)} already_done={len(completed)} to_run={n_pending}\n")
    if not n_pending:
        print("(nothing to run — every planned sample is already complete)")
        return
    for qid in order:
        segments = " ".join(
            f"{alias}[{','.join(map(str, nums))}]" for alias, nums in pending[qid].items()
        )
        print(f"  {qid}: {segments}")


def format_git(prov: dict[str, Any]) -> str:
    """One-line git summary for stderr, or a 'no git' note."""
    g = prov.get("git")
    if not g:
        return "git=none"
    return f"git={g['commit'][:12]}{'-dirty' if g['dirty'] else ''} ({g['branch']})"


def write_manifest(manifest_path: str, entry: dict[str, Any]) -> None:
    """Append one line summarizing a run to the runs index (chronological log)."""
    with open(manifest_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(
    jobs: list[Job],
    out_path: str,
    max_tokens: int,
    concurrency: int,
    provenance: dict[str, Any],
    manifest_path: str,
) -> None:
    completed = load_completed(out_path, max_tokens)
    if completed:
        print(f"Resuming: {len(completed)} completed sample(s) already in {out_path}", file=sys.stderr)

    print(f"run_id={provenance['run_id']}  {format_git(provenance)}", file=sys.stderr)
    print(
        f"runner_sha256={provenance['runner_sha256'][:12]} "
        f"input_sha256={provenance['input_sha256'][:12]} ({provenance['input_path']})",
        file=sys.stderr,
    )

    pending = [job for job in jobs if job.key not in completed]
    print(
        f"planned={len(jobs)} skipped={len(jobs) - len(pending)} to_run={len(pending)} "
        f"concurrency={concurrency}",
        file=sys.stderr,
    )
    if not pending:
        print("Nothing to do.", file=sys.stderr)
        write_manifest(
            manifest_path,
            {
                **provenance,
                "finished_at": _now_iso(),
                "output_path": os.path.abspath(out_path),
                "planned": len(jobs),
                "skipped": len(jobs),
                "succeeded": 0,
                "failed": 0,
            },
        )
        return

    client = anthropic.Anthropic(max_retries=5)
    ok = 0
    failed = 0

    def report(transcript: dict[str, Any], label: str) -> None:
        nonlocal ok, failed
        if "error" in transcript:
            failed += 1
            err = transcript["error"]
            print(f"FAIL  {label}: {err['type']}: {err['message']}", file=sys.stderr)
        else:
            ok += 1
            stop = (transcript.get("response") or {}).get("stop_reason")
            note = f" [stop_reason={stop}]" if stop not in (None, "end_turn") else ""
            print(f"ok    {label}{note}", file=sys.stderr)

    # Line-buffered append so each transcript is durably on disk as soon as it
    # is written — an interrupt at any point leaves a resumable file. All writes
    # happen on this (main) thread as futures complete, so no lock is needed.
    with open(out_path, "a", encoding="utf-8", buffering=1) as out:
        if concurrency <= 1:
            for job in pending:
                transcript = execute_job(client, job, max_tokens, provenance)
                out.write(json.dumps(transcript, ensure_ascii=False) + "\n")
                report(transcript, job.label)
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(execute_job, client, job, max_tokens, provenance): job
                    for job in pending
                }
                for future in as_completed(futures):
                    job = futures[future]
                    transcript = future.result()
                    out.write(json.dumps(transcript, ensure_ascii=False) + "\n")
                    report(transcript, job.label)

    write_manifest(
        manifest_path,
        {
            **provenance,
            "finished_at": _now_iso(),
            "output_path": os.path.abspath(out_path),
            "planned": len(jobs),
            "skipped": len(jobs) - len(pending),
            "succeeded": ok,
            "failed": failed,
        },
    )
    print(f"\nDone. run_id={provenance['run_id']} succeeded={ok} failed={failed}", file=sys.stderr)
    print(f"Run recorded in {manifest_path}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--input", required=True, help="Input JSONL of questions.")
    p.add_argument("-o", "--output", required=True, help="Output JSONL of transcripts (appended to).")
    p.add_argument("-n", "--samples", type=int, default=3, help="Samples per (question, model). Default 3.")
    p.add_argument(
        "-m",
        "--models",
        nargs="+",
        choices=sorted(DEFAULT_MODELS),
        default=sorted(DEFAULT_MODELS),
        help="Which model aliases to run. Default: all.",
    )
    p.add_argument("--max-tokens", type=int, default=8192, help="Max output tokens per call. Default 8192.")
    p.add_argument("--system", default=None, help="Global system prompt (per-question 'system' overrides it).")
    p.add_argument(
        "--manifest",
        default="runs.jsonl",
        help="Per-run index file (one line per run). Default runs.jsonl.",
    )
    p.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=1,
        help="Concurrent API calls. Default 1 (sequential).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned sample matrix and exit without calling the API.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.samples < 1:
        raise SystemExit("--samples must be >= 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be >= 1")

    models = {alias: DEFAULT_MODELS[alias] for alias in args.models}
    questions = load_questions(args.input)
    if not questions:
        raise SystemExit(f"No questions found in {args.input}")
    jobs = build_jobs(questions, models, args.samples, args.system, args.max_tokens)
    provenance = build_provenance(args, models)

    if args.dry_run:
        completed = load_completed(args.output, args.max_tokens)
        print(
            f"{format_git(provenance)}\n"
            f"runner_sha256={provenance['runner_sha256'][:12]} "
            f"input_sha256={provenance['input_sha256'][:12]} ({provenance['input_path']})\n",
            file=sys.stderr,
        )
        print_matrix(jobs, completed)
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("warning: ANTHROPIC_API_KEY is not set in the environment.", file=sys.stderr)
    run(
        jobs=jobs,
        out_path=args.output,
        max_tokens=args.max_tokens,
        concurrency=args.concurrency,
        provenance=provenance,
        manifest_path=args.manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
