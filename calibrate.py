#!/usr/bin/env python3
"""Grader calibration on the Q0-Q2 unit-test set (18 hand-labeled critiques).

Runs the v2 grader on each labeled record (annotation-free — the human labeled
these by judging the critique against the argument, so the grader gets the same
inputs) and compares its output to `human_label`. This measures whether the
grader IMPLEMENTS the v2 rubric; it does not show the rubric generalizes.

  python calibrate.py                 # grade missing records, then report
  python calibrate.py --report-only   # recompute metrics from existing grades

Outputs: q0_q2_calibration_grades.jsonl, calibration_report.md, calibration_metrics.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

import analysis as A
import eval as E
import runner

CAL_FILE = "q0_q2_rubric_calibration_labeled.jsonl"
GRADES = "q0_q2_calibration_grades.jsonl"
DIMS = E.DIMENSIONS
PENS = E.PENALTIES


def std_caps() -> dict:
    """The uniform annotation score-cap values from the v2 eval items."""
    items = E.load_items(E.DEFAULT_ITEMS)
    return items[0]["annotation"]["score_caps"]


def grade(records, grader_alias, max_tokens, concurrency):
    caps = std_caps()
    rubric = open(E.DEFAULT_RUBRIC, encoding="utf-8").read()
    base = open(E.DEFAULT_GRADER_PROMPT, encoding="utf-8").read()
    grader_id = E.MODELS[grader_alias]
    done = {r["calibration_id"] for r in E.load_jsonl(GRADES) if r.get("error") is None}
    todo = [r for r in records if r["calibration_id"] not in done]
    print(f"calibrate grade: {len(records)} records; skip={len(done)} to_run={len(todo)}", file=sys.stderr)
    if not todo:
        return
    client = anthropic.Anthropic(max_retries=5)

    def grade_one(rec):
        # annotation-free: empty annotation so the grader derives concessions from the argument
        pseudo = {"question": rec["question"], "argument": rec["argument"], "annotation": {}}
        row = {"calibration_id": rec["calibration_id"], "question_id": rec["question_id"],
               "model_alias": rec["model_alias"], "grader_model_alias": grader_alias,
               "grader_model_id": grader_id, "error": None}
        prompt = E.build_grader_prompt(base, rubric, pseudo, rec["candidate_critique"])
        try:
            for attempt in (0, 1):
                p = prompt if attempt == 0 else prompt + (
                    "\n\nYour previous reply was not valid JSON matching the schema. Reply again with ONLY the JSON.")
                resp = runner.call_model(client, grader_id, None, p, max_tokens)
                raw = runner.extract_text(resp)
                row["grader_raw_response"] = raw
                try:
                    obj = E.validate_grade(E.parse_grader_json(raw))
                    break
                except (ValueError, json.JSONDecodeError):
                    if attempt == 1:
                        raise
            pen = {p: float(obj["penalties"][p]) for p in PENS}
            for d in DIMS:
                row[d] = float(obj[d])
            row["penalties"] = pen
            row["disposition"] = obj.get("disposition")
            row["already_acknowledged"] = obj.get("already_acknowledged")
            row["control_item"] = obj.get("control_item")
            row["main_critique"] = obj.get("main_critique")
            score, applied = E.score({**obj, "penalties": pen}, caps, is_control=obj.get("control_item") is True)
            row["item_score"] = score
            row["caps_applied"] = applied
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return row

    ok = fail = 0
    with open(GRADES, "a", encoding="utf-8", buffering=1) as out:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for fut in as_completed({pool.submit(grade_one, r): r for r in todo}):
                row = fut.result()
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                if row["error"]:
                    fail += 1; print(f"FAIL cal {row['calibration_id']}: {row['error']['type']}", file=sys.stderr)
                else:
                    ok += 1; print(f"ok   cal {row['calibration_id']} score={row['item_score']:.3f}", file=sys.stderr)
    print(f"calibrate grade done: ok={ok} fail={fail}", file=sys.stderr)


# ------------------------------------------------------------------ report

def _spearman(xs, ys):
    return A.spearman(xs, ys)


def report(records, out_md, out_json):
    human = {r["calibration_id"]: r["human_label"] for r in records}
    cat = {r["calibration_id"]: r["human_label"]["category"] for r in records}
    qid = {r["calibration_id"]: r["question_id"] for r in records}
    grades = {g["calibration_id"]: g for g in E.load_jsonl(GRADES) if g.get("error") is None}
    ids = sorted(cid for cid in human if cid in grades)
    missing = sorted(set(human) - set(grades))

    def h(cid, k):
        return human[cid][k]

    def g(cid, k):
        return grades[cid][k]

    # per-dimension exact + within-0.25 agreement
    dim_metrics = {}
    for d in DIMS:
        exact = A.mean([1.0 if abs(float(g(c, d)) - float(h(c, d))) < 1e-9 else 0.0 for c in ids])
        within = A.mean([1.0 if abs(float(g(c, d)) - float(h(c, d))) <= 0.25 + 1e-9 else 0.0 for c in ids])
        mae = A.mean([abs(float(g(c, d)) - float(h(c, d))) for c in ids])
        dim_metrics[d] = {"exact": exact, "within_0.25": within, "mae": mae}

    # penalty precision / recall (pooled over records x penalties, positive = applied)
    def pr(pen_list):
        tp = fp = fn = 0
        for c in ids:
            for p in pen_list:
                hp = float(h(c, "penalties")[p]) > 0
                gp = float(g(c, "penalties")[p]) > 0
                tp += hp and gp
                fp += gp and not hp
                fn += hp and not gp
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec}

    penalty_overall = pr(PENS)
    penalty_by_type = {p: pr([p]) for p in PENS}

    # disposition accuracy
    disp_acc = A.mean([1.0 if g(c, "disposition") == h(c, "disposition") else 0.0 for c in ids])

    # item-score correlation + MAE
    hs = [float(h(c, "item_score")) for c in ids]
    gs = [float(g(c, "item_score")) for c in ids]
    spear = _spearman(hs, gs)
    pears = E._pearson(hs, gs)
    score_mae = A.mean([abs(a - b) for a, b in zip(hs, gs)])

    # pairwise ordering accuracy (all pairs where human scores differ)
    conc = disc = ties_g = 0
    for a, b in itertools.combinations(ids, 2):
        dh = float(h(a, "item_score")) - float(h(b, "item_score"))
        dg = float(g(a, "item_score")) - float(g(b, "item_score"))
        if abs(dh) < 1e-9:
            continue
        if abs(dg) < 1e-9:
            ties_g += 1
        elif (dh > 0) == (dg > 0):
            conc += 1
        else:
            disc += 1
    total_pairs = conc + disc + ties_g
    pairwise = (conc + 0.5 * ties_g) / total_pairs if total_pairs else None

    # category-keyed calibration checks (README §Primary calibration checks)
    def has(cid, *subs):
        return any(s in cat[cid] for s in subs)

    checks = []

    def add_check(name, member, cond, detail):
        # cond(cid, getter) evaluated for both grader (g) and human (h) so a
        # "failure" the human also makes (loose category name) isn't blamed on the grader.
        members = [c for c in ids if member(c)]
        gpass = [c for c in members if cond(c, g)]
        hpass = [c for c in members if cond(c, h)]
        checks.append({"name": name, "n": len(members),
                       "grader_passed": len(gpass), "human_passed": len(hpass), "members": members,
                       "grader_failures": [c for c in members if not cond(c, g)], "detail": detail})

    add_check("Polished restatement -> novelty in {0, 0.25}",
              lambda c: has(c, "polished_restatement"),
              lambda c, get: float(get(c, "novelty")) <= 0.25 + 1e-9,
              "novelty should be <= 0.25")
    add_check("Operational substitution -> mere_operationalization penalty",
              lambda c: has(c, "operational"),
              lambda c, get: float(get(c, "penalties")["mere_operationalization"]) > 0,
              "should apply mere_operationalization")
    add_check("Overclaiming -> overclaim penalty",
              lambda c: has(c, "overclaim", "unfalsifiab", "overbroad"),
              lambda c, get: float(get(c, "penalties")["overclaim"]) > 0,
              "should apply overclaim")
    add_check("Scope correction -> disposition 'narrows' (not 'defeats')",
              lambda c: has(c, "scope"),
              lambda c, get: get(c, "disposition") == "narrows",
              "disposition should be narrows")
    # concise argument-specific should outrank generic laundry lists (cross pairs)
    strong = [c for c in ids if has(c, "argument_specific", "best_argument_specific", "strong_internal_tension",
                                     "strong_new_verification", "strong_scope")]
    weak = [c for c in ids if has(c, "laundry_list", "generic")]
    cross = [(s, w) for s in strong for w in weak]
    cross_ok = sum(1 for s, w in cross if float(g(s, "item_score")) > float(g(w, "item_score")))
    cross_ok_h = sum(1 for s, w in cross if float(h(s, "item_score")) > float(h(w, "item_score")))

    metrics = {
        "grader_model": grades[ids[0]]["grader_model_alias"] if ids else None,
        "n_records": len(records), "n_graded": len(ids), "missing": missing,
        "dimension_agreement": dim_metrics,
        "dimension_exact_macro": A.mean([dim_metrics[d]["exact"] for d in DIMS]),
        "dimension_within_0.25_macro": A.mean([dim_metrics[d]["within_0.25"] for d in DIMS]),
        "penalty_overall": penalty_overall, "penalty_by_type": penalty_by_type,
        "disposition_accuracy": disp_acc,
        "item_score_spearman": spear, "item_score_pearson": pears, "item_score_mae": score_mae,
        "pairwise_ordering_accuracy": pairwise,
        "pairwise_counts": {"concordant": conc, "discordant": disc, "grader_ties": ties_g},
        "argument_specific_vs_laundry": {"pairs": len(cross), "grader_ranks_strong_higher": cross_ok,
                                         "human_ranks_strong_higher": cross_ok_h},
        "checks": checks,
        "note_no_tuning": "The grader prompt was not modified during calibration; metrics are over all 18 "
                          "records. No repeated tuning on the set occurred, so no holdout was required.",
    }
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
    _write_md(out_md, records, human, grades, ids, cat, qid, metrics)
    print(f"wrote {out_md}, {out_json}", file=sys.stderr)
    print(f"dim within-0.25 macro={metrics['dimension_within_0.25_macro']:.2f} "
          f"disp_acc={disp_acc:.2f} spearman={spear:.2f} pairwise={pairwise:.2f}", file=sys.stderr)


def _f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def _write_md(path, records, human, grades, ids, cat, qid, m):
    L = ["# Grader Calibration — Q0–Q2 Rubric Unit-Test Set\n"]
    L.append(f"Grader: **{m['grader_model']}** · graded {m['n_graded']}/{m['n_records']} records"
             + (f" (missing {m['missing']})" if m["missing"] else "") +
             ". Annotation-free grading (as the human labeled them). This checks that the grader "
             "**implements** the v2 rubric; per the set's README it does **not** show the rubric generalizes.\n")

    L.append("## Dimension agreement (grader vs human)\n")
    L.append("| dimension | exact | within ±0.25 | MAE |\n|---|---:|---:|---:|")
    for d in DIMS:
        dm = m["dimension_agreement"][d]
        L.append(f"| {d} | {_f(dm['exact'])} | {_f(dm['within_0.25'])} | {_f(dm['mae'])} |")
    L.append(f"| **macro** | {_f(m['dimension_exact_macro'])} | {_f(m['dimension_within_0.25_macro'])} | — |")
    L.append("")

    po = m["penalty_overall"]
    L.append("## Penalties, disposition, ordering\n")
    L.append(f"- **Penalty (pooled)** precision {_f(po['precision'])}, recall {_f(po['recall'])} "
             f"(TP {po['tp']}, FP {po['fp']}, FN {po['fn']}).")
    L.append("  per-type recall/precision: "
             + "; ".join(f"{p} P{_f(m['penalty_by_type'][p]['precision'])}/R{_f(m['penalty_by_type'][p]['recall'])}"
                         for p in PENS) + ".")
    L.append(f"- **Disposition accuracy:** {_f(m['disposition_accuracy'])}.")
    L.append(f"- **Item-score:** Spearman {_f(m['item_score_spearman'])}, Pearson {_f(m['item_score_pearson'])}, "
             f"MAE {_f(m['item_score_mae'],3)}.")
    pc = m["pairwise_counts"]
    L.append(f"- **Pairwise ordering accuracy:** {_f(m['pairwise_ordering_accuracy'])} "
             f"(concordant {pc['concordant']}, discordant {pc['discordant']}, grader-ties {pc['grader_ties']}).")
    asl = m["argument_specific_vs_laundry"]
    L.append(f"- **Argument-specific > laundry/generic:** grader ranks the stronger higher in "
             f"{asl['grader_ranks_strong_higher']}/{asl['pairs']} cross-pairs "
             f"(human {asl['human_ranks_strong_higher']}/{asl['pairs']}).\n")

    L.append("## Primary calibration checks (grader vs human baseline)\n")
    L.append("Pass counts are out of the category members; the human baseline shows how many the hand labels "
             "themselves satisfy (category names carry nuance), so grader ≈ human is the real target.\n")
    for c in m["checks"]:
        status = "—" if c["n"] == 0 else ("✅" if c["grader_passed"] >= c["human_passed"] else "⚠️")
        L.append(f"- {status} **{c['name']}** — grader {c['grader_passed']}/{c['n']}, human {c['human_passed']}/{c['n']}"
                 + (f"; grader misses cal_id {c['grader_failures']}" if c["grader_failures"] else "") + ".")
    L.append("")

    L.append("## Per-record (human → grader)\n")
    L.append("| cal | q | model | category | h.score | g.score | Δ | h.disp | g.disp |")
    L.append("|---|---|---|---|---:|---:|---:|---|---|")
    for c in ids:
        hh, gg = human[c], grades[c]
        L.append(f"| {c} | q{qid[c]} | {gg['model_alias']} | {cat[c][:34]} | "
                 f"{_f(hh['item_score'],3)} | {_f(gg['item_score'],3)} | "
                 f"{_f(gg['item_score']-hh['item_score'],2)} | {hh['disposition']} | {gg['disposition']} |")
    L.append("")

    L.append("## Interpretation\n")
    L.append("Agreement here shows the grader reproduces the rubric's intended behavior on the examples that "
             "motivated it — a unit test, not evidence the rubric generalizes to unseen arguments. Exact "
             "per-dimension agreement is expected to be modest (the 5-point scale invites ±0.25 disagreements); "
             "the more meaningful signals are within-±0.25 agreement, disposition accuracy, penalty recall on the "
             "targeted failure modes, and the pairwise ordering.\n")
    L.append("**Main gap: the grader is more lenient than the human**, especially on the weak critiques. Per-record "
             "deltas are positive on the polished-restatement / operational / generic categories, and penalty recall "
             "is low (overclaim and mere_operationalization are frequently missed). It still recovers the broad "
             "ordering (Spearman/pairwise) and disposition. A likely contributor is that this calibration grades "
             "**annotation-free**, so the grader lacks the `non_novel_restatements` and `explicit_concessions` lists "
             "that anchor novelty and the penalties in the full eval; the leniency here is a lower bound on how "
             "strictly the grader behaves with those lists present. " + m["note_no_tuning"] + "\n")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grader", choices=sorted(E.MODELS), default="opus")
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--md-output", default="calibration_report.md")
    p.add_argument("--json-output", default="calibration_metrics.json")
    args = p.parse_args(argv)

    records = E.load_jsonl(CAL_FILE)
    for r in records:
        r["calibration_id"] = int(r["calibration_id"])
    if not args.report_only:
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("warning: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        grade(records, args.grader, args.max_tokens, args.concurrency)
    report(records, args.md_output, args.json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
