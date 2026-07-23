#!/usr/bin/env python3
"""Deterministic checks for follow-on experiment construction and schemas."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


QA = load_module("synthetic_annotate", ROOT / "experiments/questions_1_8/synthetic_annotate.py")
CC = load_module("synthetic_classify", ROOT / "experiments/controlled_variants/synthetic_classify.py")


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_paired_dataset_is_complete_and_role_blind():
    items = jsonl(ROOT / "experiments/questions_1_8/input/items.paired.unannotated.jsonl")
    manifest = jsonl(ROOT / "experiments/questions_1_8/input/pair_manifest.jsonl")
    assert len(items) == len(manifest) == 16
    assert len({row["eval_id"] for row in items}) == 16
    assert all("annotation" not in row and "pair_role" not in row for row in items)
    by_source = {}
    for row in manifest:
        by_source.setdefault(row["source_id"], set()).add(row["pair_role"])
    assert len(by_source) == 8
    assert all(roles == {"robust", "flawed"} for roles in by_source.values())


def test_flawed_counterpart_preserves_original_argument():
    items = {row["eval_id"]: row for row in jsonl(ROOT / "experiments/questions_1_8/input/items.paired.unannotated.jsonl")}
    manifest = jsonl(ROOT / "experiments/questions_1_8/input/pair_manifest.jsonl")
    for robust in (row for row in manifest if row["pair_role"] == "robust"):
        source_id = robust["source_id"]
        assert items[source_id + 1]["argument"].startswith(items[source_id]["argument"] + "\n\n")
        assert items[source_id + 1]["question"] == items[source_id]["question"]


def test_synthetic_prompt_render_keeps_json_and_removes_markers():
    template = (ROOT / "prompts/synthetic/item_annotation_v1.txt").read_text(encoding="utf-8")
    prompt = QA.render(template, question="Q", argument="A")
    assert "{question}" not in prompt and "{argument}" not in prompt
    assert '"has_major_flaw"' in prompt and "Question:\nQ" in prompt


def test_annotation_validation_accepts_control_and_rejects_conflict():
    obj = {
        "has_major_flaw": False, "gold_disposition": "qualify_no_fatal_flaw",
        "central_issue": None, "why_it_matters": "bounded",
        "explicit_concessions": [], "acceptable_secondary": [], "tempting_but_weak": [],
        "non_novel_restatements": [], "minimum_full_credit_elements": [],
        "severity": "robust_control", "confidence": "high",
    }
    assert QA.validate_annotation(dict(obj))["gold_disposition"] == "qualify_no_fatal_flaw"
    obj["has_major_flaw"] = True
    try:
        QA.validate_annotation(obj)
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting synthetic label was accepted")


def test_classifier_prompt_is_model_blind_and_schema_validates():
    template = (ROOT / "prompts/synthetic/response_classifier_v1.txt").read_text(encoding="utf-8")
    prompt = CC.render(template, question="Q", argument="A", critique="C")
    assert "candidate_model_alias" not in prompt
    obj = {
        "primary_label": "no_major_conceptual_flaw", "severity": "no_major_flaw",
        "targets_explicit_concession": False, "operational_substitution": False,
        "repeats_repaired_flaw": False, "brief_rationale": "bounded", "confidence": "high",
    }
    assert CC.validate(obj)["severity"] == "no_major_flaw"


def main() -> None:
    tests = sorted((name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn))
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    main()
