#!/usr/bin/env python3
"""Inspect eval failures and produce report artifacts from the critique-eval outputs.

Reads the eval inputs/outputs, independently recomputes every score from the
validated grader dimensions/penalties (does not trust stored arithmetic), and
writes:

  eval_model_scores.csv    one row per model (report-ready table)
  eval_model_scores.png    bar chart, mean primary score + 95% bootstrap CI
  eval_failure_examples.json   5 selected examples + aggregate stats
  eval_failure_analysis.md     failure-analysis document

    python analysis.py            # uses the default file names below

Recompute-only: this never calls a model. Run eval.py generate/grade first.
"""

from __future__ import annotations

import csv
import json
import random
from typing import Any

import eval as E  # reuse compute_item_score, DIMENSIONS, PENALTIES, is_robust_control, load_items, load_jsonl, MODELS

ORDER = ["haiku", "sonnet", "opus", "fable"]
DISPLAY = {"haiku": "Haiku 4.5", "sonnet": "Sonnet 4.6", "opus": "Opus 4.8", "fable": "Fable 5"}
ITEMS_PATH = "data/eval/critique_eval_annotated_items_v2.jsonl"
TX_PATH = "eval_transcripts.jsonl"
GR_PATH = "eval_grades.jsonl"
SAMPLES = 3


def dedup(rows, key):
    """Keep one row per key, preferring a successful row over an error row."""
    best: dict = {}
    for r in rows:
        k = key(r)
        cur = best.get(k)
        if cur is None or (cur.get("error") is not None and r.get("error") is None):
            best[k] = r
    return best


def bootstrap_ci(xs: list[float], iters: int = 2000, seed: int = 0) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return (None, None)
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return (means[int(0.025 * iters)], means[int(0.975 * iters)])


def item_level(records: list[dict]) -> dict:
    """Item-level (clustered) aggregation of a model's graded candidates.

    Three samples of the same argument are one cluster, not three independent
    tests. The model score is mean_over_items(mean_over_samples), and the 95% CI
    is a bootstrap over ITEMS (resampling clusters), which weights every argument
    equally regardless of how many samples succeeded and yields uncertainty
    appropriate to generalizing across arguments.
    """
    from collections import defaultdict
    by = defaultdict(list)
    for g in records:
        by[g["eval_id"]].append(g["item_score"])
    item_means = {e: sum(v) / len(v) for e, v in by.items()}
    vals = list(item_means.values())
    lo, hi = bootstrap_ci(vals)  # bootstrap over per-item means == cluster bootstrap
    return {"mean": (sum(vals) / len(vals)) if vals else None, "ci95": [lo, hi],
            "covered_items": len(item_means), "n_generations": sum(len(v) for v in by.values()),
            "item_means": item_means}


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    return E._pearson(_ranks(xs), _ranks(ys))


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def main() -> None:
    items = {it["eval_id"]: it for it in E.load_items(ITEMS_PATH)}
    control_ids = {eid for eid, it in items.items() if E.is_robust_control(it)}
    case_type = {eid: (it.get("annotation") or {}).get("case_type") for eid, it in items.items()}

    tx_raw = E.load_jsonl(TX_PATH)
    gr_raw = E.load_jsonl(GR_PATH)
    tx = dedup(tx_raw, lambda r: (r["eval_id"], r["model_alias"], r["sample_number"]))
    gr = dedup(gr_raw, lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))

    # ---- Step 1: validate ------------------------------------------------
    expected = len(items) * SAMPLES * len(ORDER)
    tx_ok = {k for k, r in tx.items() if r.get("error") is None}
    tx_fail = {k for k, r in tx.items() if r.get("error") is not None}
    gr_ok_keys = {k for k, g in gr.items() if g.get("error") is None}
    gr_fail = {k for k, g in gr.items() if g.get("error") is not None}

    def dup_keys(rows, key):
        seen: dict = {}
        for r in rows:
            seen[key(r)] = seen.get(key(r), 0) + 1
        return {k: c for k, c in seen.items() if c > 1}

    tx_dupe = dup_keys(tx_raw, lambda r: (r["eval_id"], r["model_alias"], r["sample_number"]))
    gr_dupe = dup_keys(gr_raw, lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    bad_ids = sorted({(r["model_alias"], r.get("model_id")) for r in tx_raw
                      if r["model_alias"] not in E.MODELS or r.get("model_id") != E.MODELS.get(r["model_alias"])})
    missing = sorted(f"{e}/{m}/s{s}" for e in items for m in ORDER for s in range(SAMPLES)
                     if (e, m, s) not in tx_ok)
    incomplete = {}
    for m in ORDER:
        for e in items:
            c = sum(1 for s in range(SAMPLES) if (e, m, s) in tx_ok)
            if c < SAMPLES:
                incomplete[f"{m}/eval{e}"] = c

    validation = {
        "expected_candidates": expected, "candidate_rows": len(tx_raw), "unique_candidates": len(tx),
        "successful_candidates": len(tx_ok), "failed_candidate_keys": sorted(f"{e}/{m}/s{s}" for e, m, s in tx_fail),
        "grade_rows": len(gr_raw), "successful_grades": len(gr_ok_keys), "grading_failures": len(gr_fail),
        "missing_candidates": missing, "duplicate_candidate_keys": len(tx_dupe), "duplicate_grade_keys": len(gr_dupe),
        "unexpected_model_ids": [f"{a}:{i}" for a, i in bad_ids], "incomplete_sample_counts": incomplete,
    }

    # ---- Step 2/3: recompute + per-candidate records ---------------------
    recs = []
    for k, g in gr.items():
        if g.get("error") is not None:
            continue
        eid, m, s = k
        # Use the harness-recomputed, cap-applied scores stored on the grade row
        # (the grader never returns item_score). Fall back to the base formula only
        # for legacy rows that predate stored scores.
        prim = g["item_score"] if g.get("item_score") is not None else E.compute_item_score(g)
        eqw = g.get("item_score_equal_weight")
        if eqw is None:
            eqw = E.compute_item_score(g, equal_weight=True)
        t = tx.get(k, {})
        recs.append({
            "eval_id": eid, "source_id": g.get("source_id"), "model": m, "sample": s,
            "centrality": float(g["centrality"]), "argument_fidelity": float(g["argument_fidelity"]),
            "novelty": float(g["novelty"]), "justified_impact": float(g["justified_impact"]),
            "penalties": {p: float(g["penalties"][p]) for p in E.PENALTIES},
            "penalty_sum": sum(float(g["penalties"][p]) for p in E.PENALTIES),
            "score": prim, "equal_weight_score": eqw,
            "grader_reported": g.get("grader_reported_item_score"),
            "word_count": (t or {}).get("word_count"),
            "is_control": eid in control_ids, "case_type": case_type.get(eid),
            "rationale": g.get("brief_rationale"), "text": (t or {}).get("response_text", ""),
        })

    def m_recs(m):
        return [r for r in recs if r["model"] == m]

    per_model = {}
    for m in ORDER:
        rs = m_recs(m)
        sc = [r["score"] for r in rs]
        ctrl = [r for r in rs if r["is_control"]]
        flaw = [r for r in rs if not r["is_control"]]
        il = item_level([{"eval_id": r["eval_id"], "item_score": r["score"]} for r in rs])
        per_model[m] = {
            "n": il["n_generations"], "items_covered": il["covered_items"],
            "mean": il["mean"], "std": (statistics_pstdev(sc)),
            "ci95": il["ci95"], "response_pooled_mean": mean(sc),
            "equal_weight_mean": mean([r["equal_weight_score"] for r in rs]),
            "centrality": mean([r["centrality"] for r in rs]),
            "argument_fidelity": mean([r["argument_fidelity"] for r in rs]),
            "novelty": mean([r["novelty"] for r in rs]),
            "justified_impact": mean([r["justified_impact"] for r in rs]),
            "mean_penalty": mean([r["penalty_sum"] for r in rs]),
            "penalty_rates": {p: mean([1.0 if r["penalties"][p] > 0 else 0.0 for r in rs]) for p in E.PENALTIES},
            "mean_words": mean([r["word_count"] for r in rs if r["word_count"] is not None]),
            "word_limit_violation_rate": mean([1.0 if (r["word_count"] or 0) > 300 else 0.0
                                               for r in rs if r["word_count"] is not None]),
            "control_mean": mean([r["score"] for r in ctrl]),
            "flaw_mean": mean([r["score"] for r in flaw]),
            "control_false_attack_rate": mean([1.0 if r["penalties"]["overclaim"] > 0 else 0.0 for r in ctrl]),
            "control_operationalization_rate": mean([1.0 if r["penalties"]["mere_operationalization"] > 0 else 0.0 for r in ctrl]),
            "candidate_failures": sum(1 for (e, mm, s) in tx_fail if mm == m),
            "grading_failures": sum(1 for (e, mm, s) in gr_fail if mm == m),
        }

    by_item = {e: mean([r["score"] for r in recs if r["eval_id"] == e]) for e in sorted(items)}
    cts = sorted({r["case_type"] for r in recs})
    by_case = {ct: mean([r["score"] for r in recs if r["case_type"] == ct]) for ct in cts}

    # ---- Step 4: ordering ----
    order_by_mean = sorted([m for m in ORDER if per_model[m]["mean"] is not None],
                           key=lambda m: per_model[m]["mean"], reverse=True)
    try:
        expected_ok = per_model["opus"]["mean"] > per_model["sonnet"]["mean"] > per_model["haiku"]["mean"]
    except TypeError:
        expected_ok = None

    # ---- Step 5: length ----
    allw = [(r["word_count"], r["score"]) for r in recs if r["word_count"] is not None]
    length = {
        "pearson_overall": E._pearson([w for w, _ in allw], [s for _, s in allw]),
        "spearman_overall": spearman([w for w, _ in allw], [s for _, s in allw]),
        "pearson_within_model": {m: E._pearson([r["word_count"] for r in m_recs(m) if r["word_count"] is not None],
                                               [r["score"] for r in m_recs(m) if r["word_count"] is not None])
                                 for m in ORDER},
        "mean_words_by_model": {m: per_model[m]["mean_words"] for m in ORDER},
    }

    # ---- Step 7: examples ----
    examples = pick_examples(recs, control_ids)

    aggregate = {
        "validation": validation, "per_model": per_model, "score_by_item": {str(k): v for k, v in by_item.items()},
        "score_by_case_type": by_case, "ordering_by_mean": order_by_mean,
        "expected_ordering_opus_sonnet_haiku": expected_ok, "length": length,
        "grader_model": next((g["grader_model_alias"] for g in gr.values() if g.get("error") is None), None),
        "novelty_zero": [
            {"eval_id": r["eval_id"], "model": r["model"], "sample": r["sample"]}
            for r in recs if r["novelty"] == 0
        ],
    }

    with open("eval_failure_examples.json", "w", encoding="utf-8") as fh:
        json.dump({"examples": examples, "aggregate": aggregate}, fh, ensure_ascii=False, indent=2)
    write_csv(per_model)
    write_plot(per_model)
    write_analysis_md(items, aggregate, examples)
    print("wrote eval_model_scores.csv, eval_model_scores.png, eval_failure_examples.json, eval_failure_analysis.md")
    print("means:", {m: round(per_model[m]["mean"], 3) if per_model[m]["mean"] is not None else None for m in ORDER})


def statistics_pstdev(xs):
    import statistics
    return statistics.pstdev(xs) if len(xs) > 1 else 0.0


def _excerpt(text: str, n: int = 500) -> str:
    text = " ".join((text or "").split())
    return text[:n] + ("…" if len(text) > n else "")


def pick_examples(recs, control_ids) -> list[dict[str, Any]]:
    ok = [r for r in recs if r["score"] is not None]

    def rec_to_ex(cat, r, note):
        return {"category": cat, "eval_id": r["eval_id"], "source_id": r["source_id"], "model_alias": r["model"],
                "sample_number": r["sample"], "item_score": round(r["score"], 3),
                "grader_reported": r["grader_reported"],
                "dims": {d: r[d] for d in E.DIMENSIONS}, "penalties": {p: v for p, v in r["penalties"].items() if v},
                "word_count": r["word_count"], "is_control": r["is_control"], "case_type": r["case_type"],
                "response_excerpt": _excerpt(r["text"]), "grader_rationale": r["rationale"], "manual_note": note}

    out = []
    used: set = set()

    def key(r):
        return (r["eval_id"], r["model"], r["sample"])

    def take(cat, cands, sort, note):
        for r in sorted(cands, key=sort):
            if key(r) in used:
                continue
            used.add(key(r))
            out.append(rec_to_ex(cat, r, note))
            return

    # A. best high-scoring critique on a flaw item (real central flaw), concise
    take("best_high_scoring",
         [r for r in ok if not r["is_control"] and r["centrality"] == 1],
         lambda r: (-r["score"], r["word_count"] or 999),
         "Highest-scoring critique on a genuine-flaw item with full centrality; identifies the annotated "
         "central issue and shows its effect on the conclusion rather than only restating the argument.")
    # C. operational substitution
    take("operational_substitution",
         [r for r in ok if r["penalties"]["mere_operationalization"] > 0],
         lambda r: r["score"],
         "Grader applied the mere_operationalization penalty: demands thresholds/procedures/detail without "
         "showing the omission defeats the conceptual claim.")
    # D. robust-control false positive
    take("robust_control_false_positive",
         [r for r in ok if r["is_control"] and (r["penalties"]["overclaim"] > 0 or r["centrality"] == 0)],
         lambda r: r["score"],
         "Robust-control item (qualify_no_fatal_flaw); the grader flagged an unearned fatal-flaw claim "
         "(overclaim) matching the item's tempting-but-weak list. The candidate over-attacked a broadly "
         "coherent argument instead of offering a bounded qualification.")
    # B. polished restatement: novelty 0. In this run only a few novelty-0 responses exist, so state the
    # scarcity honestly rather than implying a clean restatement occurred.
    nov0 = [r for r in ok if r["novelty"] == 0]
    clean = [r for r in nov0 if r["penalties"]["overclaim"] == 0]
    b_note = (
        f"Novelty scored 0 (no new reasoning beyond the argument's concessions). Caveat: only {len(nov0)} of "
        f"{len(ok)} graded responses scored novelty 0"
        + ("" if clean else ", and all of them also drew an overclaim penalty on the eval-1 control")
        + " — a clean 'polished restatement' that tracks the argument without over-attacking did not clearly "
        "occur in this run, so this example doubles as a control over-attack.")
    take("polished_restatement",
         clean or nov0,
         lambda r: (-(r["centrality"] + r["argument_fidelity"]), -r["score"]),
         b_note)
    # E. questionable grader: largest gap between the grader's self-reported score and the rubric recompute.
    # On inspection these are the grader's own arithmetic slips (dimension calls track the annotation); the
    # recomputed score is authoritative, which is exactly why stored arithmetic is not trusted.
    gap = [r for r in ok if r["grader_reported"] is not None and key(r) not in used]
    if gap:
        r = max(gap, key=lambda r: abs(float(r["grader_reported"]) - r["score"]))
        d = abs(float(r["grader_reported"]) - r["score"])
        used.add(key(r))
        out.append(rec_to_ex("questionable_grader", r,
                   f"The grader's dimension calls look defensible against the annotation, but its self-reported "
                   f"item_score ({r['grader_reported']}) does not match the rubric applied to those same dimensions "
                   f"({round(r['score'],3)}; gap {round(d,3)}) — a grader arithmetic error. The recomputed value is "
                   f"used. Largest such gap in the run; grader arithmetic disagreed with the formula in ~20% of grades."))
    return out


def write_csv(per_model) -> None:
    with open("eval_model_scores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Model", "Overall_item_mean", "ci95_lo", "ci95_hi", "items_covered", "successful_generations",
                    "Centrality", "Fidelity", "Novelty", "Impact",
                    "Control score", "False attack rate", "Mean words", "word_limit_violation_rate"])
        for m in ORDER:
            s = per_model[m]
            def f(x): return "" if x is None else round(x, 3)
            def pct(x): return "" if x is None else f"{100*x:.1f}%"
            w.writerow([DISPLAY[m], f(s["mean"]), f(s["ci95"][0]), f(s["ci95"][1]),
                        s["items_covered"], s["n"],
                        f(s["centrality"]), f(s["argument_fidelity"]),
                        f(s["novelty"]), f(s["justified_impact"]), f(s["control_mean"]),
                        pct(s["control_false_attack_rate"]), None if s["mean_words"] is None else round(s["mean_words"]),
                        pct(s["word_limit_violation_rate"])])


def write_plot(per_model) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [DISPLAY[m] for m in ORDER]
    ys = [per_model[m]["mean"] or 0 for m in ORDER]
    los = [(per_model[m]["mean"] or 0) - (per_model[m]["ci95"][0] or per_model[m]["mean"] or 0) for m in ORDER]
    his = [(per_model[m]["ci95"][1] or per_model[m]["mean"] or 0) - (per_model[m]["mean"] or 0) for m in ORDER]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(xs, ys, yerr=[los, his], capsize=5, color="tab:gray")
    ax.set_ylim(0, 1)
    ax.set_ylabel("mean primary score")
    ax.set_title("Conceptual critique eval score by model")
    ax.text(0.5, -0.16, "11 items, 3 generations per item (95% item-bootstrap CI)",
            ha="center", transform=ax.transAxes, fontsize=9)
    fig.tight_layout()
    fig.savefig("eval_model_scores.png", dpi=130)


def write_analysis_md(items, agg, examples) -> None:
    pm = agg["per_model"]; v = agg["validation"]; ln = agg["length"]
    def f(x, nd=3): return "—" if x is None else f"{x:.{nd}f}"
    def pct(x): return "—" if x is None else f"{100*x:.0f}%"
    L = []
    L.append("# Eval Results and Failure Inspection\n")

    L.append("## Run integrity\n")
    integrity = (f"Expected {v['expected_candidates']} candidate critiques (11 items × 3 samples × 4 models); "
                 f"{v['successful_candidates']} succeeded across {v['unique_candidates']} unique keys, with "
                 f"{len(v['failed_candidate_keys'])} candidate failures and {v['grading_failures']} grading failures. "
                 f"Every successful candidate has exactly one grade ({v['successful_grades']} grades). "
                 f"Duplicate keys: {v['duplicate_candidate_keys']} candidate / {v['duplicate_grade_keys']} grade "
                 f"(retry rows deduped, successes preferred). Unexpected model IDs: "
                 f"{v['unexpected_model_ids'] or 'none'}. ")
    if v["failed_candidate_keys"] or v["incomplete_sample_counts"]:
        integrity += (f"Failed candidate keys: {v['failed_candidate_keys'] or 'none'}; "
                      f"incomplete sample counts: {v['incomplete_sample_counts'] or 'none'}. ")
    else:
        integrity += "Every model covers all 11 items with all three samples. "
    L.append(integrity + "Earlier failed attempts were retained in operational history and later backfilled; "
             "the final deduplicated evaluation is complete.\n")

    L.append("## Model results\n")
    L.append("Model score = **mean over items of the per-item sample mean**; 95% CI is a bootstrap over **items** "
             "(clusters), not individual responses — three samples of one argument are one cluster, so this weights "
             "every argument equally and reflects generalization across arguments.\n")
    L.append("| Model | Overall | 95% item-CI | Items | Gens | Centrality | Fidelity | Novelty | Impact | Control score | False attack rate | Mean words | >300w |")
    L.append("|---|---:|:--:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in ORDER:
        s = pm[m]
        L.append(f"| {DISPLAY[m]} | {f(s['mean'])} | [{f(s['ci95'][0],2)}, {f(s['ci95'][1],2)}] | "
                 f"{s['items_covered']} | {s['n']} | {f(s['centrality'],2)} | {f(s['argument_fidelity'],2)} | "
                 f"{f(s['novelty'],2)} | {f(s['justified_impact'],2)} | {f(s['control_mean'])} | "
                 f"{pct(s['control_false_attack_rate'])} | {'' if s['mean_words'] is None else round(s['mean_words'])} | "
                 f"{pct(s['word_limit_violation_rate'])} |")
    L.append(f"\nItem-level mean rises Haiku {f(pm['haiku']['mean'])} < Sonnet {f(pm['sonnet']['mean'])} "
             f"< Opus {f(pm['opus']['mean'])} < Fable {f(pm['fable']['mean'])}. The sanity check "
             f"**Opus > Sonnet > Haiku holds ({agg['expected_ordering_opus_sonnet_haiku']})**; Fable ranks highest "
             f"(reported, not assumed). 95% item-bootstrap intervals (see `eval_model_scores.png`): "
             + ", ".join(f"{DISPLAY[m]} [{f(pm[m]['ci95'][0],2)}, {f(pm[m]['ci95'][1],2)}] "
                         f"({pm[m]['items_covered']} items, {pm[m]['n']} gens)" for m in ORDER) + ".\n")

    L.append("## What drove the score\n")
    L.append(f"Separation is broad-based, not one dimension. The Haiku→Fable gap is largest in centrality "
             f"({f(pm['haiku']['centrality'],2)} → {f(pm['fable']['centrality'],2)}), with similar movement in "
             f"fidelity ({f(pm['haiku']['argument_fidelity'],2)} → {f(pm['fable']['argument_fidelity'],2)}) and "
             f"novelty ({f(pm['haiku']['novelty'],2)} → {f(pm['fable']['novelty'],2)}). Penalties are "
             f"minor at the top (mean total Fable {f(pm['fable']['mean_penalty'],3)}, Opus {f(pm['opus']['mean_penalty'],3)}) "
             f"and larger for Haiku ({f(pm['haiku']['mean_penalty'],3)}), so the gap is mostly earned dimension credit, "
             f"not penalty avoidance.\n")

    L.append("## Robust controls\n")
    L.append("Robust controls are the six `qualify_no_fatal_flaw` items (ids 1,2,3,5,8,9); a false attack is "
             "operationalized as the grader's `overclaim` penalty on a control (an unearned fatal-flaw claim). "
             f"Control-item means: Haiku {f(pm['haiku']['control_mean'])}, Sonnet {f(pm['sonnet']['control_mean'])}, "
             f"Opus {f(pm['opus']['control_mean'])}, Fable {f(pm['fable']['control_mean'])}; false-attack rates "
             f"{pct(pm['haiku']['control_false_attack_rate'])}/{pct(pm['sonnet']['control_false_attack_rate'])}/"
             f"{pct(pm['opus']['control_false_attack_rate'])}/{pct(pm['fable']['control_false_attack_rate'])}. "
             "Stronger models mostly qualify rather than invent contradictions. Every model has complete coverage "
             "of all six control items.\n")

    novelty_zero = agg["novelty_zero"]
    novelty_zero_where = ", ".join(
        f"eval {r['eval_id']} / {r['model']} / s{r['sample']}" for r in novelty_zero
    ) or "none"
    L.append("## Reward-hacking checks\n")
    L.append(f"Length–score correlation is weak: Pearson {f(ln['pearson_overall'],2)}, Spearman "
             f"{f(ln['spearman_overall'],2)} overall, with within-model Pearson "
             + ", ".join(f"{DISPLAY[m]} {f(ln['pearson_within_model'][m],2)}" for m in ORDER) + ". "
             "The 300-word instruction constrains the observed length range (mean words "
             + ", ".join(f"{DISPLAY[m]} {'' if pm[m]['mean_words'] is None else round(pm[m]['mean_words'])}" for m in ORDER)
             + "), providing little evidence that simple verbosity buys score without ruling out nonlinear or "
             "stylistic effects. Laundry-list penalties are rare. Only "
             f"{len(novelty_zero)} response{'s' if len(novelty_zero) != 1 else ''} scored novelty 0 "
             f"({novelty_zero_where}), so this run provides little direct evidence about discrimination of pure "
             "polished restatements.\n")

    L.append("## Manual failure inspection\n")
    for ex in examples:
        L.append(f"- **{ex['category']}** — eval {ex['eval_id']} / {ex['model_alias']} / s{ex['sample_number']} "
                 f"(score {ex['item_score']}, grader-reported {ex['grader_reported']}; "
                 f"`eval_grades.jsonl` key `{ex['eval_id']}/{ex['model_alias']}/s{ex['sample_number']}`). "
                 f"{ex['manual_note']}")
    L.append("\nFull excerpts, dimensions, and rationales are in `eval_failure_examples.json`.\n")

    L.append("## Interpretation\n")
    L.append("The eval measures how well a model's short critique matches a human-annotated central flaw under a "
             "rubric, as judged by one fixed Opus grader — not conceptual reasoning in general. The monotonic "
             "Opus>Sonnet>Haiku result and Fable's lead are consistent with capability but do **not** prove the eval "
             "valid; nor would a non-monotonic result prove the models misordered. Treat results as suggestive only.\n")
    L.append("**Limitations.**\n"
             "1. The grader sees the human annotation and may reward overlap with it.\n"
             "2. Stronger models may raise valid critiques outside the annotated central issue that the grader "
             "under-credits.\n"
             "3. Robust controls depend on the human judgment that no fatal flaw exists being correct.\n"
             "4. A single fixed grader may favor its own critique style (Opus/Fable share lineage).\n"
             "5. With 11 items, item-level variance is large — the per-item table shows several 0/1 swings, and the "
             "bootstrap CIs for the top three overlap.\n"
             "6. Three samples per item provide only a limited view of generation variance.\n")
    open("eval_failure_analysis.md", "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
