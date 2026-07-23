#!/usr/bin/env python3
"""Run blind synthetic item annotation and constrained reconciliation.

The intended pair-role manifest is deliberately never loaded by this program.
Raw model outputs are append-only; derived exclusions and annotated items are
deterministically rebuilt from successful rows.
"""

from __future__ import annotations

import argparse
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

BASE = Path("experiments/questions_1_8")
DEFAULT_ITEMS = BASE / "input/items.paired.unannotated.jsonl"
ANNOTATION_PROMPT = Path("prompts/synthetic/item_annotation_v1.txt")
RECONCILE_PROMPT = Path("prompts/synthetic/item_reconciliation_v1.txt")
RAW_ANNOTATIONS = BASE / "synthetic_annotations.jsonl"
RAW_RECONCILIATIONS = BASE / "synthetic_reconciliations.jsonl"
EXCLUSIONS = BASE / "annotation_exclusions.jsonl"
ANNOTATED_ITEMS = BASE / "input/items.annotated.jsonl"
CAPS = {
    "centrality_if_only_secondary": 0.5,
    "novelty_if_acknowledged_only": 0.0,
    "impact_if_no_conclusion_effect": 0.5,
    "max_total_if_fatal_flaw_invented_on_control": 0.35,
}
DISPOSITIONS = {"reject_or_rewrite", "narrow", "qualify_no_fatal_flaw"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def render(template: str, **values: str) -> str:
    """Replace named markers without interpreting JSON braces in the template."""
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def parse(raw: str) -> dict:
    return critique_eval.parse_grader_json(raw)


def validate_annotation(obj: dict) -> dict:
    required = {
        "has_major_flaw", "gold_disposition", "central_issue", "why_it_matters",
        "explicit_concessions", "acceptable_secondary", "tempting_but_weak",
        "non_novel_restatements", "minimum_full_credit_elements", "severity", "confidence",
    }
    missing = required - set(obj)
    if missing:
        raise ValueError(f"missing annotation fields: {sorted(missing)}")
    if not isinstance(obj["has_major_flaw"], bool):
        raise ValueError("has_major_flaw must be boolean")
    if obj["gold_disposition"] not in DISPOSITIONS:
        raise ValueError("invalid gold_disposition")
    expected_flaw = obj["gold_disposition"] != "qualify_no_fatal_flaw"
    if obj["has_major_flaw"] != expected_flaw:
        raise ValueError("has_major_flaw conflicts with gold_disposition")
    if obj["confidence"] not in {"low", "medium", "high"}:
        raise ValueError("invalid confidence")
    for field in (
        "explicit_concessions", "acceptable_secondary", "tempting_but_weak",
        "non_novel_restatements", "minimum_full_credit_elements",
    ):
        if not isinstance(obj[field], list) or not all(isinstance(x, str) for x in obj[field]):
            raise ValueError(f"{field} must be a string list")
    if expected_flaw and not isinstance(obj["central_issue"], str):
        raise ValueError("flawed item requires central_issue")
    if not expected_flaw and obj["central_issue"] is not None:
        raise ValueError("control central_issue must be null")
    return obj


def validate_reconciliation(obj: dict, agreed: str) -> dict:
    required = {
        "case_type", "gold_disposition", "central_issue", "why_it_matters",
        "acceptable_secondary", "tempting_but_weak", "explicit_concessions",
        "minimum_full_credit_elements", "non_novel_restatements", "severity",
    }
    missing = required - set(obj)
    if missing:
        raise ValueError(f"missing reconciliation fields: {sorted(missing)}")
    if obj["gold_disposition"] != agreed:
        raise ValueError("reconciler changed agreed disposition")
    is_control = agreed == "qualify_no_fatal_flaw"
    if is_control and obj["central_issue"] is not None:
        raise ValueError("control central_issue must be null")
    if not is_control and not isinstance(obj["central_issue"], str):
        raise ValueError("flawed item requires central_issue")
    for field in (
        "acceptable_secondary", "tempting_but_weak", "explicit_concessions",
        "minimum_full_credit_elements", "non_novel_restatements",
    ):
        if not isinstance(obj[field], list) or not all(isinstance(x, str) for x in obj[field]):
            raise ValueError(f"{field} must be a string list")
    return obj


def latest_success(rows: list[dict], key_fields: tuple[str, ...]) -> dict[tuple, dict]:
    best: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if row.get("error") is None:
            best[key] = row
    return best


def call_structured(client, model_id: str, prompt: str, max_tokens: int, validator) -> tuple[str, dict]:
    last_raw = ""
    for attempt in (0, 1):
        current = prompt if attempt == 0 else prompt + "\n\nReturn corrected JSON only; the previous response failed schema validation."
        response = runner.call_model(client, model_id, None, current, max_tokens)
        last_raw = runner.extract_text(response)
        try:
            return last_raw, validator(parse(last_raw))
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                raise
    raise AssertionError("unreachable")


def run_annotations(args, items: list[dict]) -> None:
    template = read_prompt(ANNOTATION_PROMPT)
    existing = latest_success(read_jsonl(RAW_ANNOTATIONS), ("eval_id", "annotator_alias", "prompt_sha256"))
    jobs = []
    for item in items:
        prompt = render(template, question=item["question"], argument=item["argument"])
        sha = prompt_hash(prompt)
        for alias in args.annotators:
            if (item["eval_id"], alias, sha) not in existing:
                jobs.append((item, alias, prompt, sha))
    print(f"synthetic annotation: {len(jobs)} calls pending")
    if not jobs:
        return
    client = anthropic.Anthropic(max_retries=5)

    def one(job):
        item, alias, prompt, sha = job
        row = {
            "eval_id": item["eval_id"], "source_id": item.get("source_id"),
            "annotator_alias": alias, "annotator_model_id": runner.DEFAULT_MODELS[alias],
            "prompt_sha256": sha, "prompt": prompt, "raw_response": None,
            "annotation": None, "timestamp": runner._now_iso(), "error": None,
        }
        try:
            raw, obj = call_structured(client, row["annotator_model_id"], prompt, args.max_tokens, validate_annotation)
            row["raw_response"], row["annotation"] = raw, obj
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return row

    with RAW_ANNOTATIONS.open("a", encoding="utf-8", buffering=1) as fh:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for future in as_completed([pool.submit(one, job) for job in jobs]):
                row = future.result()
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"  {'ok' if row['error'] is None else 'FAIL'} item={row['eval_id']} {row['annotator_alias']}")


def agreement(items: list[dict], annotators: list[str]) -> tuple[list[tuple[dict, dict, dict]], list[dict]]:
    rows = latest_success(read_jsonl(RAW_ANNOTATIONS), ("eval_id", "annotator_alias", "prompt_sha256"))
    template = read_prompt(ANNOTATION_PROMPT)
    agreed, excluded = [], []
    for item in items:
        current_prompt = render(template, question=item["question"], argument=item["argument"])
        sha = prompt_hash(current_prompt)
        pair = [rows.get((item["eval_id"], alias, sha)) for alias in annotators]
        if any(row is None for row in pair):
            excluded.append({"eval_id": item["eval_id"], "reason": "missing_annotation_pass"})
            continue
        a, b = (row["annotation"] for row in pair)
        if a["confidence"] == "low" or b["confidence"] == "low":
            excluded.append({"eval_id": item["eval_id"], "reason": "low_confidence", "annotations": [a, b]})
        elif (a["has_major_flaw"], a["gold_disposition"]) != (b["has_major_flaw"], b["gold_disposition"]):
            excluded.append({"eval_id": item["eval_id"], "reason": "label_disagreement", "annotations": [a, b]})
        else:
            agreed.append((item, a, b))
    return agreed, excluded


def run_reconciliation(args, agreed: list[tuple[dict, dict, dict]]) -> None:
    template = read_prompt(RECONCILE_PROMPT)
    existing = latest_success(read_jsonl(RAW_RECONCILIATIONS), ("eval_id", "prompt_sha256"))
    jobs = []
    for item, a, b in agreed:
        prompt = render(
            template,
            gold_disposition=a["gold_disposition"], question=item["question"], argument=item["argument"],
            annotation_a=json.dumps(a, ensure_ascii=False, indent=2),
            annotation_b=json.dumps(b, ensure_ascii=False, indent=2),
        )
        sha = prompt_hash(prompt)
        if (item["eval_id"], sha) not in existing:
            jobs.append((item, a["gold_disposition"], prompt, sha))
    print(f"synthetic reconciliation: {len(jobs)} calls pending")
    if not jobs:
        return
    client = anthropic.Anthropic(max_retries=5)
    model_id = runner.DEFAULT_MODELS[args.reconciler]

    def one(job):
        item, disposition, prompt, sha = job
        row = {
            "eval_id": item["eval_id"], "source_id": item.get("source_id"),
            "reconciler_alias": args.reconciler, "reconciler_model_id": model_id,
            "prompt_sha256": sha, "prompt": prompt, "raw_response": None,
            "annotation": None, "timestamp": runner._now_iso(), "error": None,
        }
        try:
            raw, obj = call_structured(
                client, model_id, prompt, args.max_tokens,
                lambda value: validate_reconciliation(value, disposition),
            )
            row["raw_response"], row["annotation"] = raw, obj
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return row

    with RAW_RECONCILIATIONS.open("a", encoding="utf-8", buffering=1) as fh:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for future in as_completed([pool.submit(one, job) for job in jobs]):
                row = future.result()
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"  {'ok' if row['error'] is None else 'FAIL'} item={row['eval_id']} reconcile")


def materialize(items: list[dict], annotators: list[str]) -> None:
    agreed, excluded = agreement(items, annotators)
    reconciliation_template = read_prompt(RECONCILE_PROMPT)
    reconciled_rows = latest_success(read_jsonl(RAW_RECONCILIATIONS), ("eval_id", "prompt_sha256"))
    reconciled: dict[int, dict] = {}
    for item, a, b in agreed:
        current_prompt = render(
            reconciliation_template,
            gold_disposition=a["gold_disposition"], question=item["question"], argument=item["argument"],
            annotation_a=json.dumps(a, ensure_ascii=False, indent=2),
            annotation_b=json.dumps(b, ensure_ascii=False, indent=2),
        )
        row = reconciled_rows.get((item["eval_id"], prompt_hash(current_prompt)))
        if row is not None:
            reconciled[item["eval_id"]] = row
    agreed_ids = {item["eval_id"] for item, _, _ in agreed}
    for eval_id in sorted(agreed_ids - set(reconciled)):
        excluded.append({"eval_id": eval_id, "reason": "missing_reconciliation"})

    initially_eligible = agreed_ids & set(reconciled)
    ids_by_source: dict[int, set[int]] = {}
    for item in items:
        ids_by_source.setdefault(item["source_id"], set()).add(item["eval_id"])
    eligible_ids: set[int] = set()
    for source_id, pair_ids in ids_by_source.items():
        if pair_ids <= initially_eligible:
            eligible_ids.update(pair_ids)
        else:
            for eval_id in sorted(pair_ids & initially_eligible):
                excluded.append({"eval_id": eval_id, "source_id": source_id, "reason": "pair_mate_excluded"})

    with EXCLUSIONS.open("w", encoding="utf-8") as fh:
        for row in sorted(excluded, key=lambda value: value["eval_id"]):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with ANNOTATED_ITEMS.open("w", encoding="utf-8") as fh:
        for item in items:
            row = reconciled.get(item["eval_id"])
            if item["eval_id"] not in eligible_ids or row is None:
                continue
            annotation = dict(row["annotation"])
            annotation.update({
                "score_caps": CAPS,
                "annotation_version": "synthetic_v1",
                "annotation_source": {
                    "annotators": annotators,
                    "reconciler": row["reconciler_alias"],
                    "human_reviewed": False,
                },
            })
            fh.write(json.dumps({**item, "annotation": annotation}, ensure_ascii=False) + "\n")
    print(f"materialized {len(read_jsonl(ANNOTATED_ITEMS))} annotated items; {len(excluded)} excluded")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--annotators", nargs=2, choices=runner.DEFAULT_MODELS, default=["fable", "sonnet"])
    parser.add_argument("--reconciler", choices=runner.DEFAULT_MODELS, default="haiku")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()
    if len(set(args.annotators)) != 2:
        raise SystemExit("--annotators must name two distinct models")
    if args.reconciler in args.annotators:
        raise SystemExit("--reconciler must differ from both annotators")
    items = read_jsonl(args.items)
    if len({item["eval_id"] for item in items}) != len(items):
        raise SystemExit("duplicate eval_id")
    run_annotations(args, items)
    agreed, _ = agreement(items, args.annotators)
    run_reconciliation(args, agreed)
    materialize(items, args.annotators)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
