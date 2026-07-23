#!/usr/bin/env python3
"""Build paired robust/flawed analysis from existing synthetic-v1 grades."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BASE = Path("experiments/questions_1_8")
MANIFEST = BASE / "input/pair_manifest.jsonl"
ITEMS = BASE / "input/items.annotated.jsonl"
GRADES = BASE / "grades.jsonl"
EXCLUSIONS = BASE / "annotation_exclusions.jsonl"
OUT = BASE / "paired_analysis.md"
MODELS = ["haiku", "sonnet", "opus", "fable"]
LABEL = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 4.6", "opus": "Opus 4.8", "fable": "Fable 5"}


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def pct(n: int, total: int) -> str:
    return "—" if not total else f"{100 * n / total:.0f}% ({n}/{total})"


def main() -> int:
    if not GRADES.exists() or not ITEMS.exists():
        raise SystemExit("missing annotated items or grades; follow README.md in order")
    manifest = {row["eval_id"]: row for row in jsonl(MANIFEST)}
    retained = {row["eval_id"] for row in jsonl(ITEMS)}
    grades_by_key = {}
    for row in jsonl(GRADES):
        if row.get("error") is None and row["eval_id"] in retained:
            grades_by_key[(row["eval_id"], row["candidate_model_alias"], row["sample_number"])] = row
    grades = list(grades_by_key.values())
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in grades:
        grouped[(row["candidate_model_alias"], manifest[row["eval_id"]]["pair_role"])].append(row)

    pair_sources = {manifest[eid]["source_id"] for eid in retained}
    lines = [
        "# Questions 1–8 paired stress test — analysis",
        "",
        "This is a **separate synthetic-annotation follow-on experiment**, not part of the primary 11-item "
        "score. Robust originals are paired with minimally changed flawed counterparts. Item references were "
        "generated before candidate critiques by two blind annotators and a constrained reconciler; they are "
        "synthetic references, not human ground truth.",
        "",
        f"Retained annotated items: **{len(retained)}/16** across **{len(pair_sources)}/8 complete pairs**. "
        f"Successful grades: **{len(grades)}**. Annotation exclusion records: **{len(jsonl(EXCLUSIONS))}**.",
        "",
        "## Primary behavior by role",
        "",
        "Flaw-detection is a strict proxy: centrality ≥ 0.75 and disposition `defeats` or `narrows`. "
        "False severe attack on a robust item means `defeats` or a nonzero overclaim penalty.",
        "",
        "| Model | Role | n | Mean v2 score | Flaw-detection rate | False-severe-attack rate | Operational-substitution rate |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        for role in ("robust", "flawed"):
            rows = grouped[(model, role)]
            detected = sum(float(row["centrality"]) >= 0.75 and row["disposition"] in {"defeats", "narrows"} for row in rows)
            false_attack = sum(
                row["disposition"] == "defeats" or float((row.get("penalties") or {}).get("overclaim", 0)) > 0
                for row in rows
            ) if role == "robust" else 0
            operational = sum(
                float((row.get("penalties") or {}).get("mere_operationalization", 0)) > 0 for row in rows
            )
            lines.append(
                f"| {LABEL[model]} | {role} | {len(rows)} | "
                f"{fmt(mean([float(row['item_score']) for row in rows]))} | "
                f"{pct(detected, len(rows)) if role == 'flawed' else '—'} | "
                f"{pct(false_attack, len(rows)) if role == 'robust' else '—'} | "
                f"{pct(operational, len(rows))} |"
            )

    lines += [
        "",
        "## Interpretation",
        "",
        "The desired joint pattern is high detection on flawed counterparts and low severe-attack rates on "
        "robust originals. Either rate alone is insufficient: always attacking can detect flaws but lacks "
        "restraint, while always qualifying can look restrained but miss real failures.",
        "",
        "V2 score differences between roles are secondary diagnostics. The score measures critique quality "
        "relative to each synthetic annotation, not whether one underlying argument is better than another.",
        "",
        "## Limitations",
        "",
        "- Synthetic references may reproduce model-family preferences and are not human ground truth.",
        "- Every flawed counterpart adds a conspicuous concluding overreach; this tests repair sensitivity more "
        "than subtle flaw discovery and may make flaws easier than the robust controls.",
        "- Three generations reduce sampling noise but are clustered within only eight conceptual families.",
        "- One fixed Opus grader sees the synthetic annotation and may reward its framing.",
        "- Report annotation disagreements and excluded pairs; never silently treat them as model failures.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
