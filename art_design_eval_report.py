#!/usr/bin/env python3
"""Report + result analysis for the art & design graded eval.

Parallels analysis.py, but parameterized and free of the main eval's hardcoded
narrative (item counts, control ids, and the Haiku-529 story are all specific to
the submission). Reads the art/design items + transcripts + grades, recomputes
every score from the validated grader dimensions/penalties via eval.score's
formula (already stored on each grade row as item_score), and writes:

  art_design_eval_model_scores.csv   one row per model
  art_design_eval_analysis.md        the per-model table + a result analysis

Same aggregation as the main eval: model score = mean over items of the per-item
sample mean; 95% CI is a cluster (item) bootstrap. Recompute-only, no API calls.
"""

from __future__ import annotations

import csv
import json

import analysis as A   # item_level (cluster bootstrap), spearman
import eval as E        # load_items, load_jsonl, dedup, is_robust_control, DIMENSIONS, PENALTIES, MODELS

ORDER = ["haiku", "sonnet", "opus", "fable"]
DISPLAY = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 4.6", "opus": "Opus 4.8", "fable": "Fable 5"}

ITEMS_PATH = "critique_eval_annotated_items_art_design.jsonl"
TX_PATH = "art_design_eval_transcripts.jsonl"
GR_PATH = "art_design_eval_grades.jsonl"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def build():
    items = {it["eval_id"]: it for it in E.load_items(ITEMS_PATH)}
    control_ids = {eid for eid, it in items.items() if E.is_robust_control(it)}
    flaw_ids = set(items) - control_ids

    tx = E.dedup(E.load_jsonl(TX_PATH), lambda r: (r["eval_id"], r["model_alias"], r["sample_number"]))
    gr = E.dedup(E.load_jsonl(GR_PATH),
                 lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    grades = [g for g in gr.values() if g.get("error") is None]

    recs = []
    for g in grades:
        eid = g["eval_id"]
        t = tx.get((eid, g["candidate_model_alias"], g["sample_number"]), {})
        recs.append({
            "eval_id": eid, "model": g["candidate_model_alias"], "sample": g["sample_number"],
            "score": g["item_score"],
            "centrality": float(g["centrality"]), "argument_fidelity": float(g["argument_fidelity"]),
            "novelty": float(g["novelty"]), "justified_impact": float(g["justified_impact"]),
            "penalties": {p: float(g["penalties"][p]) for p in E.PENALTIES},
            "word_count": (t or {}).get("word_count"),
            "is_control": eid in control_ids,
        })

    per_model = {}
    for m in ORDER:
        rs = [r for r in recs if r["model"] == m]
        ctrl = [r for r in rs if r["is_control"]]
        flaw = [r for r in rs if not r["is_control"]]
        il = A.item_level([{"eval_id": r["eval_id"], "item_score": r["score"]} for r in rs])
        per_model[m] = {
            "n": il["n_generations"], "items_covered": il["covered_items"],
            "mean": il["mean"], "ci95": il["ci95"],
            "centrality": mean([r["centrality"] for r in rs]),
            "argument_fidelity": mean([r["argument_fidelity"] for r in rs]),
            "novelty": mean([r["novelty"] for r in rs]),
            "justified_impact": mean([r["justified_impact"] for r in rs]),
            "control_mean": mean([r["score"] for r in ctrl]),
            "flaw_mean": mean([r["score"] for r in flaw]),
            "control_false_attack_rate": mean([1.0 if r["penalties"]["overclaim"] > 0 else 0.0 for r in ctrl]),
            "mean_words": mean([r["word_count"] for r in rs if r["word_count"] is not None]),
            "word_limit_violation_rate": mean([1.0 if (r["word_count"] or 0) > E.WORD_LIMIT else 0.0
                                               for r in rs if r["word_count"] is not None]),
        }

    by_item = {e: mean([r["score"] for r in recs if r["eval_id"] == e]) for e in sorted(items)}
    covered = [m for m in ORDER if per_model[m]["mean"] is not None]
    order_by_mean = sorted(covered, key=lambda m: per_model[m]["mean"], reverse=True)
    try:
        expected_ok = per_model["opus"]["mean"] > per_model["sonnet"]["mean"] > per_model["haiku"]["mean"]
    except TypeError:
        expected_ok = None
    return items, control_ids, flaw_ids, per_model, by_item, order_by_mean, expected_ok, len(grades)


def f(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def write_csv(per_model):
    with open("art_design_eval_model_scores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Model", "Mean", "ci95_lo", "ci95_hi", "Items", "Gens",
                    "Centrality", "Fidelity", "Novelty", "Impact",
                    "Robust-control score", "False-attack rate"])
        for m in ORDER:
            s = per_model[m]
            def g(x): return "" if x is None else round(x, 3)
            w.writerow([DISPLAY[m], g(s["mean"]), g(s["ci95"][0]), g(s["ci95"][1]),
                        s["items_covered"], s["n"], g(s["centrality"]), g(s["argument_fidelity"]),
                        g(s["novelty"]), g(s["justified_impact"]), g(s["control_mean"]),
                        pct(s["control_false_attack_rate"])])


def write_md(items, control_ids, flaw_ids, per_model, by_item, order_by_mean, expected_ok, n_grades):
    L = []
    L.append("# Art & Design Eval — Results and Analysis (v2 grader)\n")
    L.append(
        "Same graded pipeline as the main submission (`eval.py` generate → grade → summarize) run on a "
        f"**separate 6-item art/design set**, graded by a fixed **Opus** grader; {n_grades} grades. "
        "Scores are recomputed in code with the annotation caps — the grader returns structured flags, "
        "never an item_score. This set is **not** part of the main submission.\n")

    L.append("## Model results\n")
    L.append("Model score = **mean over items of the per-item sample mean**; 95% CI is a bootstrap over **items** "
             "(clusters), not individual responses — three samples of one argument are one cluster. "
             "Robust-control score is the mean on the single `qualify_no_fatal_flaw` item; false-attack rate is the "
             "fraction of control grades that drew an `overclaim` penalty (an unearned fatal-flaw claim).\n")
    L.append("| Model | Mean | 95% item-CI | Centrality | Fidelity | Novelty | Impact | Robust-control score | False-attack rate | Items | Gens |")
    L.append("|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in ORDER:
        s = per_model[m]
        L.append(f"| {DISPLAY[m]} | {f(s['mean'])} | [{f(s['ci95'][0], 2)}, {f(s['ci95'][1], 2)}] | "
                 f"{f(s['centrality'], 2)} | {f(s['argument_fidelity'], 2)} | {f(s['novelty'], 2)} | "
                 f"{f(s['justified_impact'], 2)} | {f(s['control_mean'])} | {pct(s['control_false_attack_rate'])} | "
                 f"{s['items_covered']}/{len(items)} | {s['n']} |")
    L.append("")
    ranked = " < ".join(f"{DISPLAY[m]} {f(per_model[m]['mean'])}" for m in
                        sorted(order_by_mean, key=lambda m: per_model[m]["mean"]))
    L.append(f"Item-level mean rises {ranked}. Expected-capability check **Opus > Sonnet > Haiku: "
             f"{expected_ok}**; Fable is reported without assuming a rank.\n")

    L.append("## What drove the score\n")
    L.append("Centrality and novelty separate the models most; fidelity and impact stay high across the board "
             f"(Centrality Haiku {f(per_model['haiku']['centrality'], 2)} → Fable {f(per_model['fable']['centrality'], 2)}; "
             f"Novelty Haiku {f(per_model['haiku']['novelty'], 2)} → Fable {f(per_model['fable']['novelty'], 2)}). "
             "This mirrors the main eval: the gap is mostly earned dimension credit, not penalty avoidance.\n")

    L.append("## Robust control (over-attack check)\n")
    L.append(f"There is a single robust-control item (eval_id {sorted(control_ids)}, `aura-reproduction`): a "
             "deliberately qualified, property-relative argument where inventing a fatal flaw is the failure mode. "
             "Control-item means and false-attack rates: "
             + ", ".join(f"{DISPLAY[m]} {f(per_model[m]['control_mean'])}/{pct(per_model[m]['control_false_attack_rate'])}"
                         for m in ORDER) + ". "
             "**Caveat:** with only one control item (× 3 samples per model), these two columns are low-n and should "
             "be read as directional, not as a stable false-attack rate — unlike the main eval's six controls.\n")

    L.append("## Score by item\n")
    L.append("| eval_id | control | case_type | mean |\n|---|---|---|---:|")
    for e in sorted(items):
        ann = items[e].get("annotation") or {}
        L.append(f"| {e} | {'yes' if e in control_ids else 'no'} | {ann.get('case_type')} | {f(by_item[e])} |")
    L.append("")

    L.append("## Interpretation & limitations\n")
    L.append("- Measures how well a short critique matches a human-annotated central flaw under the v2 rubric, as "
             "judged by one fixed Opus grader — not conceptual reasoning in general. Treat as suggestive.\n"
             "- **Only 6 items (1 control).** Item-level variance is large and the bootstrap CIs are wide and likely "
             "overlapping; do not over-read small mean gaps. The main submission (11 items, 6 controls) is the "
             "better-powered version.\n"
             "- The grader sees the human annotation and may reward overlap with it; stronger models may raise valid "
             "critiques outside the annotated issue that the grader under-credits.\n"
             "- Robust-control validity depends on the human judgment that the `aura` argument has no fatal flaw.\n"
             "- A single fixed grader may favor its own critique style (Opus/Fable share lineage).\n")
    open("art_design_eval_analysis.md", "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    items, control_ids, flaw_ids, per_model, by_item, order_by_mean, expected_ok, n_grades = build()
    write_csv(per_model)
    write_md(items, control_ids, flaw_ids, per_model, by_item, order_by_mean, expected_ok, n_grades)
    print("wrote art_design_eval_model_scores.csv, art_design_eval_analysis.md")
    print("means:", {m: round(per_model[m]["mean"], 3) if per_model[m]["mean"] is not None else None for m in ORDER})


if __name__ == "__main__":
    main()
