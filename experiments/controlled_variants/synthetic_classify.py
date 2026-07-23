#!/usr/bin/env python3
"""Run two model-blinded classifiers and retain exact consensus codes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402
import eval as critique_eval  # noqa: E402
import runner  # noqa: E402

BASE = Path("experiments/controlled_variants")
ITEMS = BASE / "input/items.jsonl"
TRANSCRIPTS = BASE / "transcripts.jsonl"
PROMPT = Path("prompts/synthetic/response_classifier_v1.txt")
RAW = BASE / "synthetic_classifications.jsonl"
CONSENSUS = BASE / "synthetic_consensus_codes.csv"
DISAGREEMENTS = BASE / "synthetic_classification_disagreements.jsonl"
LABELS = {
    "actual_reasoning_vs_reconstructed_justification", "evidence_underdetermines_reasoning",
    "purpose_relative_standard", "missing_threshold", "missing_process_or_documentation",
    "later_reviewer_bias", "coherence_not_truth", "generic_incompleteness",
    "no_major_conceptual_flaw", "other",
}
SEVERITIES = {"defeats", "narrows", "qualifies", "no_major_flaw"}
BOOL_FIELDS = ("targets_explicit_concession", "operational_substitution", "repeats_repaired_flaw")
CODE_FIELDS = ("primary_label", "severity", *BOOL_FIELDS)


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def validate(obj: dict) -> dict:
    required = {*CODE_FIELDS, "brief_rationale", "confidence"}
    if required - set(obj):
        raise ValueError(f"missing fields: {sorted(required - set(obj))}")
    if obj["primary_label"] not in LABELS or obj["severity"] not in SEVERITIES:
        raise ValueError("invalid label or severity")
    if any(not isinstance(obj[field], bool) for field in BOOL_FIELDS):
        raise ValueError("classification flags must be boolean")
    if obj["confidence"] not in {"low", "medium", "high"}:
        raise ValueError("invalid confidence")
    return obj


def render(template: str, **values: str) -> str:
    """Replace named markers without interpreting JSON braces in the template."""
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def parse(raw: str) -> dict:
    return validate(critique_eval.parse_grader_json(raw))


def call(client, model_id: str, prompt: str, max_tokens: int) -> tuple[str, dict]:
    raw = ""
    for attempt in (0, 1):
        current = prompt if attempt == 0 else prompt + "\n\nReturn corrected JSON only."
        response = runner.call_model(client, model_id, None, current, max_tokens)
        raw = runner.extract_text(response)
        try:
            return raw, parse(raw)
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                raise
    raise AssertionError("unreachable")


def successful_transcripts() -> list[dict]:
    best: dict[tuple, dict] = {}
    for row in jsonl(TRANSCRIPTS):
        key = (row["eval_id"], row["model_alias"], row["sample_number"])
        if row.get("error") is None and (row.get("response_text") or "").strip():
            best[key] = row
    return list(best.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifiers", nargs=2, choices=runner.DEFAULT_MODELS, default=["fable", "sonnet"])
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()
    if len(set(args.classifiers)) != 2:
        raise SystemExit("--classifiers must name two distinct models")
    if not TRANSCRIPTS.exists():
        raise SystemExit(f"missing {TRANSCRIPTS}; generate candidates first")

    items = {row["eval_id"]: row for row in jsonl(ITEMS)}
    template = PROMPT.read_text(encoding="utf-8").strip()
    existing = {}
    for row in jsonl(RAW):
        if row.get("error") is None:
            key = (row["eval_id"], row["candidate_model_alias"], row["sample_number"],
                   row["classifier_alias"], row["prompt_sha256"])
            existing[key] = row

    jobs = []
    for transcript in successful_transcripts():
        item = items[transcript["eval_id"]]
        prompt = render(
            template,
            question=item["question"], argument=item["argument"], critique=transcript["response_text"]
        )
        sha = hashlib.sha256(prompt.encode()).hexdigest()
        for alias in args.classifiers:
            key = (transcript["eval_id"], transcript["model_alias"], transcript["sample_number"], alias, sha)
            if key not in existing:
                jobs.append((transcript, alias, prompt, sha))
    print(f"synthetic response classification: {len(jobs)} calls pending")
    if jobs:
        client = anthropic.Anthropic(max_retries=5)

        def one(job):
            transcript, alias, prompt, sha = job
            row = {
                "eval_id": transcript["eval_id"], "source_id": transcript.get("source_id"),
                "candidate_model_alias": transcript["model_alias"],
                "sample_number": transcript["sample_number"],
                "classifier_alias": alias, "classifier_model_id": runner.DEFAULT_MODELS[alias],
                "prompt_sha256": sha, "prompt": prompt, "raw_response": None,
                "classification": None, "timestamp": runner._now_iso(), "error": None,
            }
            try:
                raw, obj = call(client, row["classifier_model_id"], prompt, args.max_tokens)
                row["raw_response"], row["classification"] = raw, obj
            except Exception as exc:  # noqa: BLE001
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            return row

        with RAW.open("a", encoding="utf-8", buffering=1) as fh:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                for future in as_completed([pool.submit(one, job) for job in jobs]):
                    row = future.result()
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    print(f"  {'ok' if row['error'] is None else 'FAIL'} "
                          f"item={row['eval_id']} candidate={row['candidate_model_alias']} "
                          f"sample={row['sample_number']} coder={row['classifier_alias']}")

    latest = {}
    for row in jsonl(RAW):
        if row.get("error") is None:
            latest[(row["eval_id"], row["candidate_model_alias"], row["sample_number"],
                    row["classifier_alias"], row["prompt_sha256"])] = row
    consensus_rows, disagreements = [], []
    for transcript in successful_transcripts():
        key3 = (transcript["eval_id"], transcript["model_alias"], transcript["sample_number"])
        item = items[transcript["eval_id"]]
        current_prompt = render(
            template,
            question=item["question"], argument=item["argument"], critique=transcript["response_text"],
        )
        sha = hashlib.sha256(current_prompt.encode()).hexdigest()
        pair = [latest.get((*key3, alias, sha)) for alias in args.classifiers]
        if any(row is None for row in pair):
            disagreements.append({"key": key3, "reason": "missing_classifier"})
            continue
        a, b = (row["classification"] for row in pair)
        if a["confidence"] == "low" or b["confidence"] == "low":
            disagreements.append({"key": key3, "reason": "low_confidence", "classifications": [a, b]})
        elif any(a[field] != b[field] for field in CODE_FIELDS):
            disagreements.append({"key": key3, "reason": "code_disagreement", "classifications": [a, b]})
        else:
            consensus_rows.append({
                "source_id": transcript.get("source_id"), "model_alias": transcript["model_alias"],
                "sample_number": transcript["sample_number"],
                **{field: a[field] for field in CODE_FIELDS},
                "notes": f"synthetic consensus: {args.classifiers[0]}+{args.classifiers[1]}",
            })

    with CONSENSUS.open("w", newline="", encoding="utf-8") as fh:
        fields = ["source_id", "model_alias", "sample_number", *CODE_FIELDS, "notes"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(consensus_rows, key=lambda row: (int(row["source_id"]), row["model_alias"], int(row["sample_number"]))))
    with DISAGREEMENTS.open("w", encoding="utf-8") as fh:
        for row in disagreements:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"materialized {len(consensus_rows)} consensus codes; {len(disagreements)} excluded/disagreed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
