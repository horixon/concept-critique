#!/usr/bin/env python3
"""Build the controlled-variant contrast report from existing grades.

No API calls. Automatic metrics come from the fixed v2 grader. Blind contrast
codes are summarized only when the two synthetic classifiers agree exactly.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("experiments/controlled_variants")
ITEMS = BASE / "input/items.jsonl"
GRADES = BASE / "grades.jsonl"
SYNTHETIC = BASE / "synthetic_consensus_codes.csv"
CLASSIFIER_DISAGREEMENTS = BASE / "synthetic_classification_disagreements.jsonl"
OUT = BASE / "contrast_analysis.md"
MODELS = ["haiku", "sonnet", "opus", "fable"]
LABEL = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 4.6", "opus": "Opus 4.8", "fable": "Fable 5"}


def jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def pct(n: int, total: int) -> str:
    return "—" if not total else f"{100 * n / total:.0f}% ({n}/{total})"


def dedup_grades(rows: list[dict]) -> list[dict]:
    """Prefer the latest successful row for each candidate key."""
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (row["eval_id"], row["candidate_model_alias"], row["sample_number"])
        current = best.get(key)
        if current is None or (current.get("error") is not None and row.get("error") is None):
            best[key] = row
    return [row for row in best.values() if row.get("error") is None]


def load_codes() -> tuple[list[dict], str]:
    """Load only exact consensus from the two synthetic classifiers."""
    if not SYNTHETIC.exists():
        return [], "none"
    with SYNTHETIC.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("primary_label")]
    return rows, "synthetic consensus"


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes", "y"}


def main() -> int:
    if not GRADES.exists():
        raise SystemExit(f"missing {GRADES}; run generate and grade first (see README.md)")

    source_by_eval = {row["eval_id"]: row["source_id"] for row in jsonl(ITEMS)}
    grades = dedup_grades(jsonl(GRADES))
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for grade in grades:
        grouped[(grade["candidate_model_alias"], source_by_eval[grade["eval_id"]])].append(grade)

    lines = [
        "# Controlled variants — contrast analysis",
        "",
        "Automatic fields below come from the fixed v2 Opus grader. The primary study question is whether "
        "critiques change after repair, not the absolute mean score.",
        "",
        "| Model | Variant | n | Mean score | Defeats rate | Operational-substitution rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        for source_id in (1000, 1001, 1002):
            rows = grouped[(model, source_id)]
            scores = [float(row["item_score"]) for row in rows]
            attacks = sum(row.get("disposition") == "defeats" for row in rows)
            operational = sum(float((row.get("penalties") or {}).get("mere_operationalization", 0)) > 0 for row in rows)
            lines.append(
                f"| {LABEL[model]} | {source_id} | {len(rows)} | {fmt(mean(scores))} | "
                f"{pct(attacks, len(rows))} | {pct(operational, len(rows))} |"
            )

    lines += [
        "",
        "## Within-model score contrasts (diagnostic only)",
        "",
        "These are critique-quality score differences, not argument-quality differences. Their sign does not "
        "directly measure repair sensitivity.",
        "",
        "| Model | Repair delta (1001−1000) | Control delta (1002−1000) |",
        "|---|---:|---:|",
    ]
    for model in MODELS:
        scores = {
            source_id: mean([float(row["item_score"]) for row in grouped[(model, source_id)]])
            for source_id in (1000, 1001, 1002)
        }
        repair = None if scores[1000] is None or scores[1001] is None else scores[1001] - scores[1000]
        control = None if scores[1000] is None or scores[1002] is None else scores[1002] - scores[1000]
        lines.append(f"| {LABEL[model]} | {fmt(repair)} | {fmt(control)} |")

    codes, code_source = load_codes()
    lines += ["", "## Blind contrast coding", ""]
    if not codes:
        lines.append(
            "Coding is not complete. Run `synthetic_classify.py`, then rerun this script."
        )
    else:
        lines += [
            f"Completed consensus rows: {len(codes)}. Code source: **{code_source}**. Category counts are shown "
            "without treating classifier labels as independent samples.",
            f"Classifier exclusions/disagreements: **{count_jsonl(CLASSIFIER_DISAGREEMENTS)}**. Exact-code "
            "agreement is required, so missing consensus is reported rather than forced.",
            "",
            "| Variant | Primary-label counts |",
            "|---:|---|",
        ]
        for source_id in (1000, 1001, 1002):
            counts = Counter(row["primary_label"] for row in codes if int(row["source_id"]) == source_id)
            rendered = ", ".join(f"{name}: {count}" for name, count in counts.most_common()) or "—"
            lines.append(f"| {source_id} | {rendered} |")

        coded = {
            (row["model_alias"], int(row["sample_number"]), int(row["source_id"])): row
            for row in codes
        }
        lines += [
            "",
            "### Matched contrast metrics",
            "",
            "Sample numbers provide a deterministic matching convention, not shared-randomness statistical pairs.",
            "",
            "| Model | Complete triples | Detects 1000 flaw | Retires flaw on 1001 | Differentiates labels | Operational restraint on 1002 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        target = "actual_reasoning_vs_reconstructed_justification"
        for model in MODELS:
            triples = []
            for sample in range(3):
                rows = [coded.get((model, sample, source_id)) for source_id in (1000, 1001, 1002)]
                if all(rows):
                    triples.append(rows)
            detected = [rows for rows in triples if rows[0]["primary_label"] == target]
            retired = sum(
                rows[1]["primary_label"] != target and not truthy(rows[1].get("repeats_repaired_flaw"))
                for rows in detected
            )
            different = sum(len({row["primary_label"] for row in rows}) > 1 for rows in triples)
            restrained = sum(not truthy(rows[2].get("operational_substitution")) for rows in triples)
            lines.append(
                f"| {LABEL[model]} | {len(triples)} | {pct(len(detected), len(triples))} | "
                f"{pct(retired, len(detected))} | {pct(different, len(triples))} | "
                f"{pct(restrained, len(triples))} |"
            )

    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- Three arguments do not support a population-level confidence interval.",
        "- The v2 score is annotation-relative and uses one fixed LLM grader.",
        "- A convincing result requires the manually coded objection to disappear or weaken after repair.",
        "- Do not interpret positive score deltas as proof that the underlying repair succeeded.",
        "- Do not pool these rows with the main 11-item evaluation.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} from {len(grades)} successful grades and {len(codes)} {code_source} codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
