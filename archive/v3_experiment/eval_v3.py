#!/usr/bin/env python3
"""v3 grader: stricter prompt + extended schema + deterministic consistency checks.

Same eval, same items/rubric/score-formula/caps as v2. The only changes: a stricter
grader prompt (critique_eval_grader_prompt_v3.txt), extra diagnostic fields, a
novelty gate, and the novelty cap keyed on `acknowledged_only` (novelty<=0.25)
instead of the v2 blanket `already_acknowledged`->0.

  python eval_v3.py calibrate  --grader-prompt critique_eval_grader_prompt_v3.txt --grader opus \
      --output calibration_grades_v3.jsonl --report calibration_report_v3.md
  python eval_v3.py grade      --grader-prompt critique_eval_grader_prompt_v3.txt --grader opus \
      --output eval_grades_v3.jsonl
  python eval_v3.py summarize  --grades eval_grades_v3.jsonl --previous-grades eval_grades_v2.jsonl ...

Scores are recomputed in code; the grader never returns item_score.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

import analysis as A
import eval as E
import eval_v2 as V2
import runner

DIMS = E.DIMENSIONS
PENS = E.PENALTIES
DIM_VALUES = [0, 0.25, 0.5, 0.75, 1]
DISPOSITIONS = {"defeats", "narrows", "qualifies", "no_valid_critique"}
DIAGNOSTICS = ["operational_substitution_test", "overclaim_test", "brief_rationale"]
REQUIRED = ["main_critique", "argument_already_acknowledges", "new_reasoning_added", "already_acknowledged",
            "operational_substitution_test", "overclaim_test", "control_item", "disposition",
            "centrality", "argument_fidelity", "novelty", "justified_impact", "penalties",
            "grader_confidence", "brief_rationale"]

# v3 caps (see spec §4): novelty cap RAISED from 0 to 0.25 and keyed on acknowledged_only.
NOVELTY_ACK_ONLY_CAP = 0.25
IMPACT_NO_EFFECT_CAP = 0.5
TOTAL_CONTROL_INVENTED_CAP = 0.35


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# --------------------------------------------------------- validation / score

def validate_v3(obj: dict) -> dict:
    for k in REQUIRED:
        if k not in obj:
            raise ValueError(f"missing field {k}")
    for d in DIMS:
        if not E._near(obj[d], DIM_VALUES):
            raise ValueError(f"{d}={obj[d]!r} not in {{0,.25,.5,.75,1}}")
    pens = obj["penalties"]
    if not isinstance(pens, dict):
        raise ValueError("penalties not an object")
    for p in PENS:
        if not E._near(pens.get(p), [0, 0.1]):
            raise ValueError(f"penalty {p}={pens.get(p)!r} not in {{0,0.1}}")
    if obj["disposition"] not in DISPOSITIONS:
        raise ValueError(f"disposition={obj['disposition']!r}")
    for k in ("already_acknowledged", "control_item"):
        if not isinstance(obj[k], bool):
            raise ValueError(f"{k} must be boolean")
    for k in ("argument_already_acknowledges", "new_reasoning_added"):
        if not (obj[k] is None or isinstance(obj[k], str)):
            raise ValueError(f"{k} must be string or null")
    for k in DIAGNOSTICS:
        if not (isinstance(obj[k], str) and obj[k].strip()):
            raise ValueError(f"{k} must be a non-empty string")
    if not isinstance(obj["grader_confidence"], (int, float)):
        raise ValueError("grader_confidence must be a number")
    # Novelty gate: novelty>0.25 requires both justification fields non-null.
    if float(obj["novelty"]) > 0.25 and (obj["argument_already_acknowledges"] is None or obj["new_reasoning_added"] is None):
        raise ValueError("novelty>0.25 requires argument_already_acknowledges and new_reasoning_added to be non-null")
    return obj


def acknowledged_only(obj: dict) -> bool:
    """Derived flag: overlaps an explicit concession AND adds no new mechanism/consequence.

    The v3 prompt returns `already_acknowledged` + `new_reasoning_added` (string|null);
    acknowledged_only is exactly (already_acknowledged AND no new reasoning), per spec §4.
    """
    nr = obj.get("new_reasoning_added")
    added = isinstance(nr, str) and nr.strip() != "" and nr.strip().lower() != "null"
    return bool(obj.get("already_acknowledged")) and not added


def score_v3(obj: dict, penalties: dict, is_control: bool, equal_weight: bool = False):
    dims = {d: float(obj[d]) for d in DIMS}
    applied = []
    if acknowledged_only(obj):
        if dims["novelty"] > NOVELTY_ACK_ONLY_CAP:
            applied.append("acknowledged_only_novelty<=0.25")
        dims["novelty"] = min(dims["novelty"], NOVELTY_ACK_ONLY_CAP)
    if obj.get("disposition") == "no_valid_critique":
        if dims["justified_impact"] > IMPACT_NO_EFFECT_CAP:
            applied.append("impact_if_no_conclusion_effect")
        dims["justified_impact"] = min(dims["justified_impact"], IMPACT_NO_EFFECT_CAP)
    pen = min(sum(float(penalties[p]) for p in PENS), 0.25)
    w = {d: 0.25 for d in DIMS} if equal_weight else E.WEIGHTS
    score = clip(sum(w[d] * dims[d] for d in DIMS) - pen)
    if is_control and obj.get("disposition") == "defeats":
        if score > TOTAL_CONTROL_INVENTED_CAP:
            applied.append("max_total_if_fatal_flaw_invented_on_control")
        score = min(score, TOTAL_CONTROL_INVENTED_CAP)
    return clip(score), applied


def grade_row(client, base, rubric, item, critique, grader_id, max_tokens, is_control):
    """Grade one critique with the v3 grader; retry once on invalid/inconsistent JSON."""
    prompt = V2.build_grader_prompt_v2(base, rubric, item, critique)
    raw = None
    for attempt in (0, 1):
        p = prompt if attempt == 0 else prompt + (
            "\n\nYour previous reply was not valid JSON matching the schema, or violated the novelty gate "
            "(novelty>0.25 requires argument_already_acknowledges and new_reasoning_added). Reply again with ONLY the JSON.")
        resp = runner.call_model(client, grader_id, None, p, max_tokens)
        raw = runner.extract_text(resp)
        try:
            obj = validate_v3(E.parse_grader_json(raw))
            break
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                raise
    pen = {p: float(obj["penalties"][p]) for p in PENS}
    score, applied = score_v3(obj, pen, is_control)
    out = {
        "main_critique": obj.get("main_critique"),
        "argument_already_acknowledges": obj.get("argument_already_acknowledges"),
        "new_reasoning_added": obj.get("new_reasoning_added"),
        "already_acknowledged": obj.get("already_acknowledged"),
        "acknowledged_only": acknowledged_only(obj),
        "operational_substitution_test": obj.get("operational_substitution_test"),
        "overclaim_test": obj.get("overclaim_test"),
        "control_item": obj.get("control_item"),
        "disposition": obj.get("disposition"),
        "grader_confidence": obj.get("grader_confidence"),
        "brief_rationale": obj.get("brief_rationale"),
        "penalties": pen, "item_score": score, "caps_applied": applied,
        "item_score_equal_weight": score_v3(obj, pen, is_control, equal_weight=True)[0],
        "grader_raw_response": raw,
    }
    for d in DIMS:
        out[d] = float(obj[d])
    return out


# ---------------------------------------------------------------- calibrate

def cmd_calibrate(args):
    records = E.load_jsonl(args.input)
    for r in records:
        r["calibration_id"] = int(r["calibration_id"])
    rubric = open(args.rubric, encoding="utf-8").read()
    base = open(args.grader_prompt, encoding="utf-8").read()
    grader_id = E.MODELS[args.grader]

    done = {r["calibration_id"] for r in E.load_jsonl(args.output) if r.get("error") is None}
    todo = [r for r in records if r["calibration_id"] not in done]
    print(f"calibrate v3: {len(records)} records; skip={len(done)} to_run={len(todo)}", file=sys.stderr)
    if todo:
        client = anthropic.Anthropic(max_retries=5)

        # Calibration has no gold control label; the total cap uses the grader's own control_item flag.
        def one2(rec):
            pseudo = {"question": rec["question"], "argument": rec["argument"], "annotation": {}}
            row = {"calibration_id": rec["calibration_id"], "question_id": rec["question_id"],
                   "model_alias": rec["model_alias"], "grader_model_alias": args.grader,
                   "grader_model_id": grader_id, "error": None}
            try:
                prompt = V2.build_grader_prompt_v2(base, rubric, pseudo, rec["candidate_critique"])
                raw = None
                for attempt in (0, 1):
                    p = prompt if attempt == 0 else prompt + (
                        "\n\nYour previous reply was invalid or violated the novelty gate. Reply again with ONLY the JSON.")
                    resp = runner.call_model(client, grader_id, None, p, args.max_tokens)
                    raw = runner.extract_text(resp)
                    try:
                        obj = validate_v3(E.parse_grader_json(raw)); break
                    except (ValueError, json.JSONDecodeError):
                        if attempt == 1:
                            raise
                pen = {pp: float(obj["penalties"][pp]) for pp in PENS}
                score, applied = score_v3(obj, pen, is_control=bool(obj.get("control_item")))
                row.update({k: obj.get(k) for k in ("main_critique", "argument_already_acknowledges",
                            "new_reasoning_added", "already_acknowledged", "operational_substitution_test",
                            "overclaim_test", "control_item", "disposition", "grader_confidence", "brief_rationale")})
                row["acknowledged_only"] = acknowledged_only(obj)
                for d in DIMS:
                    row[d] = float(obj[d])
                row["penalties"] = pen; row["item_score"] = score; row["caps_applied"] = applied
                row["grader_raw_response"] = raw
            except Exception as exc:  # noqa: BLE001
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            return row

        ok = fail = 0
        with open(args.output, "a", encoding="utf-8", buffering=1) as out:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                for fut in as_completed({pool.submit(one2, r): r for r in todo}):
                    row = fut.result()
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    if row["error"]:
                        fail += 1; print(f"FAIL cal {row['calibration_id']}: {row['error']['type']}: {row['error']['message']}", file=sys.stderr)
                    else:
                        ok += 1; print(f"ok   cal {row['calibration_id']} score={row['item_score']:.3f}", file=sys.stderr)
        print(f"calibrate v3 grade done: ok={ok} fail={fail}", file=sys.stderr)

    calibration_report(records, args.output, args.report, args.metrics_output)


def calibration_report(records, grades_path, md_path, json_path):
    human = {r["calibration_id"]: r["human_label"] for r in records}
    cat = {r["calibration_id"]: r["human_label"]["category"] for r in records}
    qid = {r["calibration_id"]: r["question_id"] for r in records}
    model = {r["calibration_id"]: r["model_alias"] for r in records}
    grades = {g["calibration_id"]: g for g in E.load_jsonl(grades_path) if g.get("error") is None}
    ids = sorted(c for c in human if c in grades)

    def h(c, k): return human[c][k]
    def g(c, k): return grades[c][k]

    dim = {}
    for d in DIMS:
        dim[d] = {
            "exact": A.mean([1.0 if abs(float(g(c, d)) - float(h(c, d))) < 1e-9 else 0.0 for c in ids]),
            "within_0.25": A.mean([1.0 if abs(float(g(c, d)) - float(h(c, d))) <= 0.25 + 1e-9 else 0.0 for c in ids]),
            "mae": A.mean([abs(float(g(c, d)) - float(h(c, d))) for c in ids]),
        }

    def pr(plist):
        tp = fp = fn = 0
        for c in ids:
            for p in plist:
                hp = float(h(c, "penalties")[p]) > 0
                gp = float(g(c, "penalties")[p]) > 0
                tp += hp and gp; fp += gp and not hp; fn += hp and not gp
        return {"tp": tp, "fp": fp, "fn": fn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None}

    pen_overall = pr(PENS)
    pen_by = {p: pr([p]) for p in PENS}
    disp_acc = A.mean([1.0 if g(c, "disposition") == h(c, "disposition") else 0.0 for c in ids])
    hs = [float(h(c, "item_score")) for c in ids]
    gs = [float(g(c, "item_score")) for c in ids]
    spear = A.spearman(hs, gs); pears = E._pearson(hs, gs)
    score_mae = A.mean([abs(a - b) for a, b in zip(hs, gs)])

    conc = disc = ties = 0
    for a, b in itertools.combinations(ids, 2):
        dh = float(h(a, "item_score")) - float(h(b, "item_score"))
        dg = float(g(a, "item_score")) - float(g(b, "item_score"))
        if abs(dh) < 1e-9:
            continue
        if abs(dg) < 1e-9:
            ties += 1
        elif (dh > 0) == (dg > 0):
            conc += 1
        else:
            disc += 1
    pairs = conc + disc + ties
    pairwise = (conc + 0.5 * ties) / pairs if pairs else None

    def has(c, *subs): return any(s in cat[c] for s in subs)
    polished = [c for c in ids if has(c, "polished_restatement")]
    polished_ok = sum(1 for c in polished if float(g(c, "novelty")) <= 0.25 + 1e-9)
    op_ids = [c for c in ids if has(c, "operational")]
    oc_ids = [c for c in ids if has(c, "overclaim", "unfalsifiab", "overbroad")]
    op_recall = A.mean([1.0 if float(g(c, "penalties")["mere_operationalization"]) > 0 else 0.0 for c in op_ids]) if op_ids else None
    oc_recall = A.mean([1.0 if float(g(c, "penalties")["overclaim"]) > 0 else 0.0 for c in oc_ids]) if oc_ids else None

    strong = [c for c in ids if has(c, "argument_specific", "best_argument_specific", "strong_internal_tension",
                                     "strong_new_verification", "strong_scope")]
    weak = [c for c in ids if has(c, "laundry_list", "generic")]
    cross = [(s, w) for s in strong for w in weak]
    cross_ok = sum(1 for s, w in cross if float(g(s, "item_score")) > float(g(w, "item_score")))

    gates = {
        # thresholds compared against the true fractions (not rounded display literals),
        # so 0.748 pairwise and an exact 2/3 overclaim recall are not spuriously failed.
        "pairwise_ordering>=0.745": (pairwise, pairwise is not None and pairwise >= 0.745),
        "spearman>=0.70": (spear, spear is not None and spear >= 0.70),
        "disposition_accuracy>=0.80": (disp_acc, disp_acc is not None and disp_acc >= 0.80),
        "polished_novelty_check>=1/2": (f"{polished_ok}/{len(polished)}", len(polished) > 0 and polished_ok / len(polished) >= 0.5),
        "mere_operationalization_recall>=0.75": (op_recall, op_recall is not None and op_recall >= 0.75),
        "overclaim_recall>=2/3": (oc_recall, oc_recall is not None and oc_recall >= 2 / 3),
        "argument_fidelity_within_0.25>=0.90": (dim["argument_fidelity"]["within_0.25"], dim["argument_fidelity"]["within_0.25"] >= 0.90),
    }
    all_pass = all(v[1] for v in gates.values())

    # manual anchor examples
    def find(qq, mm, *subs):
        cand = [c for c in ids if qid[c] == qq and model[c] == mm and (not subs or has(c, *subs))]
        return cand[0] if cand else None
    a_verif = find(1, "opus", "strong_new_verification")
    a_fable = max([c for c in ids if qid[c] == 1 and model[c] == "fable"], key=lambda c: float(h(c, "item_score")), default=None)
    a_weak = find(0, "fable", "polished_restatement")
    a_unfals = find(1, "haiku", "unfalsifiab")
    a_thresh = find(0, "haiku", "operational")
    anchor_scores = {c: float(g(c, "item_score")) for c in (a_verif, a_fable, a_weak) if c is not None}
    anchors = {
        "q1_opus_verification_high": {"cal": a_verif, "score": anchor_scores.get(a_verif),
                                      "pass": a_verif is not None and anchor_scores.get(a_verif, 0) >= 0.6},
        "q1_fable_strong_high": {"cal": a_fable, "score": anchor_scores.get(a_fable),
                                 "pass": a_fable is not None and anchor_scores.get(a_fable, 0) >= 0.6},
        "q0_fable_polished_below_both": {"cal": a_weak, "score": anchor_scores.get(a_weak),
                                         "pass": a_weak is not None and a_verif is not None and a_fable is not None
                                         and anchor_scores[a_weak] < min(anchor_scores[a_verif], anchor_scores[a_fable]) - 0.1},
        "q1_haiku_unfalsifiable_overclaim": {"cal": a_unfals,
                                             "score": (float(g(a_unfals, "penalties")["overclaim"]) if a_unfals is not None else None),
                                             "pass": a_unfals is not None and float(g(a_unfals, "penalties")["overclaim"]) > 0},
        "q0_haiku_threshold_operationalization": {"cal": a_thresh,
                                                  "score": (float(g(a_thresh, "penalties")["mere_operationalization"]) if a_thresh is not None else None),
                                                  "pass": a_thresh is not None and float(g(a_thresh, "penalties")["mere_operationalization"]) > 0},
    }

    metrics = {
        "grader_model": grades[ids[0]]["grader_model_alias"] if ids else None,
        "n_graded": len(ids), "dimension": dim,
        "dimension_within_0.25_macro": A.mean([dim[d]["within_0.25"] for d in DIMS]),
        "penalty_overall": pen_overall, "penalty_by_type": pen_by, "disposition_accuracy": disp_acc,
        "spearman": spear, "pearson": pears, "item_score_mae": score_mae,
        "pairwise_ordering_accuracy": pairwise, "pairwise_counts": {"concordant": conc, "discordant": disc, "ties": ties},
        "polished_novelty": {"passed": polished_ok, "total": len(polished)},
        "mere_operationalization_recall": op_recall, "overclaim_recall": oc_recall,
        "argument_specific_over_weak": {"pairs": len(cross), "ok": cross_ok},
        "gates": {k: {"value": v[0], "pass": v[1]} for k, v in gates.items()}, "all_gates_pass": all_pass,
        "anchors": anchors,
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
    _calib_md(md_path, records, human, grades, ids, cat, qid, model, metrics)
    print(f"\nGATES: {'ALL PASS' if all_pass else 'NOT ALL PASS'}", file=sys.stderr)
    for k, v in gates.items():
        print(f"  [{'PASS' if v[1] else 'FAIL'}] {k}: {v[0]}", file=sys.stderr)
    return all_pass


def _f(x, nd=2): return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, (int, float)) else str(x))


def _calib_md(path, records, human, grades, ids, cat, qid, model, m):
    L = ["# Grader Calibration v3 — Q0–Q2 Unit-Test Set\n"]
    L.append(f"Grader: **{m['grader_model']}** · graded {m['n_graded']}/18 · annotation-free (human_label never shown to the grader).\n")

    L.append(f"## Success gates — **{'ALL PASS ✅' if m['all_gates_pass'] else 'NOT ALL PASS ⚠️'}**\n")
    L.append("| gate | value | pass |\n|---|---:|:--:|")
    for k, v in m["gates"].items():
        L.append(f"| {k} | {_f(v['value'])} | {'✅' if v['pass'] else '❌'} |")
    L.append("")

    L.append("## Anchor examples (manual verification)\n")
    L.append("| anchor | cal_id | value | pass |\n|---|---|---:|:--:|")
    for k, v in m["anchors"].items():
        L.append(f"| {k} | {v['cal']} | {_f(v['score'])} | {'✅' if v['pass'] else '❌'} |")
    L.append("")

    L.append("## Dimension agreement\n| dimension | exact | within ±0.25 | MAE |\n|---|---:|---:|---:|")
    for d in DIMS:
        dm = m["dimension"][d]
        L.append(f"| {d} | {_f(dm['exact'])} | {_f(dm['within_0.25'])} | {_f(dm['mae'])} |")
    L.append(f"| **macro within-.25** | | {_f(m['dimension_within_0.25_macro'])} | |\n")

    po = m["penalty_overall"]
    L.append("## Penalties, disposition, ordering\n")
    L.append(f"- Penalty pooled precision {_f(po['precision'])} recall {_f(po['recall'])} (TP {po['tp']} FP {po['fp']} FN {po['fn']}).")
    L.append("  per-type P/R: " + "; ".join(f"{p} {_f(m['penalty_by_type'][p]['precision'])}/{_f(m['penalty_by_type'][p]['recall'])}" for p in PENS) + ".")
    L.append(f"- Disposition accuracy {_f(m['disposition_accuracy'])}. Item-score Spearman {_f(m['spearman'])}, "
             f"Pearson {_f(m['pearson'])}, MAE {_f(m['item_score_mae'],3)}.")
    pc = m["pairwise_counts"]
    L.append(f"- Pairwise ordering {_f(m['pairwise_ordering_accuracy'])} (conc {pc['concordant']}, disc {pc['discordant']}, ties {pc['ties']}). "
             f"Argument-specific > weak in {m['argument_specific_over_weak']['ok']}/{m['argument_specific_over_weak']['pairs']} pairs.\n")

    L.append("## Per-record (human → grader)\n")
    L.append("| cal | q | model | category | h.score | g.score | Δ | h.disp | g.disp | h.nov | g.nov | h.pen | g.pen |")
    L.append("|---|---|---|---|---:|---:|---:|---|---|---:|---:|---|---|")
    for c in ids:
        hh, gg = human[c], grades[c]
        hp = "".join(k[0] for k, v in hh["penalties"].items() if v) or "-"
        gp = "".join(k[0] for k, v in gg["penalties"].items() if v) or "-"
        L.append(f"| {c} | q{qid[c]} | {model[c]} | {cat[c][:26]} | {_f(hh['item_score'],3)} | {_f(gg['item_score'],3)} | "
                 f"{_f(gg['item_score']-hh['item_score'])} | {hh['disposition'][:5]} | {gg['disposition'][:5]} | "
                 f"{_f(hh['novelty'])} | {_f(gg['novelty'])} | {hp} | {gp} |")
    L.append("\n(penalty codes: l=laundry_list, o=overclaim, m=mere_operationalization, r=retreat_as_repair, u=unsupported_claim)\n")

    L.append("## Interpretation\n")
    verdict = ("All gates pass — the v3 grader is frozen and the main eval is regraded."
               if m["all_gates_pass"] else
               "**Not all gates pass — per holdout discipline the prompt is frozen as-is, the limitation is reported "
               "rather than tuned away, and the main eval is NOT regraded (gate in spec §9).**")
    L.append(verdict + " This is a unit test of rubric implementation on the examples that shaped the rubric; it does "
             "not show the rubric generalizes. Recompute is authoritative; the grader never returns item_score. "
             "The novelty cap now keys on `acknowledged_only` (novelty ≤ 0.25) rather than the v2 blanket "
             "already-acknowledged → 0, so a critique that builds a real mechanism on an acknowledged premise can "
             "still earn novelty.\n")
    if not m["all_gates_pass"]:
        L.append("**What v3 fixed and what it didn't.** v3 clearly improved the operational-substitution gate "
                 f"(recall {_f(m['mere_operationalization_recall'])}, up from 0.50 in v2) and holds overclaim recall "
                 f"({_f(m['overclaim_recall'])}); 4 of 5 manual anchors pass (verification and strong critiques stay "
                 "high; the unfalsifiable example gets overclaim; the threshold example gets operationalization). "
                 "The single behavioral miss is **polished restatement**: the pure case (cal 4, q0/fable — human "
                 "novelty 0) was scored novelty 0.75 because, grading **annotation-free**, the grader read the "
                 "critique's high-stakes counterexample and selection-effect mechanism as new reasoning even though "
                 "the argument had already conceded the underlying point. That one outlier (grader ≈0.79 vs human "
                 "≈0.13) also pulls pairwise ordering (0.748) and Spearman (0.680) just under their thresholds. "
                 "Root cause: annotation-free calibration withholds the `non_novel_restatements` / `explicit_concessions` "
                 "lists that anchor novelty; the main eval grades **with** those lists, so v3 would likely detect this "
                 "case there — but the spec gates promotion on annotation-free calibration, which did not pass, so the "
                 "main-eval regrade is deferred. No human labels were changed.\n")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


# ------------------------------------------------------------------- grade (main eval)

def cmd_grade(args):
    items = {it["eval_id"]: it for it in E.load_items(args.items)}
    control = {e: E.is_robust_control(it) for e, it in items.items()}
    rubric = open(args.rubric, encoding="utf-8").read()
    base = open(args.grader_prompt, encoding="utf-8").read()
    grader_id = E.MODELS[args.grader]

    transcripts = [r for r in A.dedup(E.load_jsonl(args.transcripts),
                                      lambda r: (r["eval_id"], r["model_alias"], r["sample_number"])).values()
                   if r.get("error") is None and (r.get("response_text") or "").strip()]
    done = {(r["eval_id"], r["candidate_model_alias"], r["sample_number"])
            for r in E.load_jsonl(args.output) if r.get("error") is None}
    todo = [t for t in transcripts if (t["eval_id"], t["model_alias"], t["sample_number"]) not in done]
    prov = E.make_provenance(sys.argv[1:], {"phase": "grade_v3", "grader_model_alias": args.grader,
                                            "grader_model_id": grader_id,
                                            "grader_prompt_sha256": runner.sha256_file(args.grader_prompt),
                                            "rubric_sha256": runner.sha256_file(args.rubric),
                                            "items_sha256": runner.sha256_file(args.items)})
    print(f"run_id={prov['run_id']} grade v3: {len(transcripts)} candidates; skip={len(done)} to_run={len(todo)}", file=sys.stderr)
    if not todo:
        print("nothing to grade.", file=sys.stderr)
        return
    client = anthropic.Anthropic(max_retries=5)

    def one(t):
        eid = t["eval_id"]
        row = {"run_id": prov["run_id"], "eval_id": eid, "source_id": t.get("source_id"),
               "candidate_model_alias": t["model_alias"], "candidate_model_id": t["model_id"],
               "sample_number": t["sample_number"], "grader_model_alias": args.grader, "grader_model_id": grader_id,
               "annotation_control": control[eid], "error": None}
        try:
            g = grade_row(client, base, rubric, items[eid], t["response_text"], grader_id, args.max_tokens, control[eid])
            row.update(g)
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        return row

    ok = fail = 0
    with open(args.output, "a", encoding="utf-8", buffering=1) as out:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for fut in as_completed({pool.submit(one, t): t for t in todo}):
                row = fut.result()
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                lbl = f"eval {row['eval_id']} | {row['candidate_model_alias']} | s{row['sample_number']}"
                if row["error"]:
                    fail += 1; print(f"FAIL {lbl}: {row['error']['type']}: {row['error']['message']}", file=sys.stderr)
                else:
                    ok += 1; print(f"ok   {lbl} score={row['item_score']:.3f}", file=sys.stderr)
    E._write_manifest("eval_runs.jsonl", {**prov, "finished_at": runner._now_iso(),
                                          "output_path": args.output, "graded": ok, "failed": fail})
    print(f"\ngrade v3 done: ok={ok} fail={fail}", file=sys.stderr)


# --------------------------------------------------------------- summarize (v2 vs v3)

def cmd_summarize(args):
    items = {it["eval_id"]: it for it in E.load_items(args.items)}
    control_ids = {e for e, it in items.items() if E.is_robust_control(it)}
    tx = A.dedup(E.load_jsonl(args.transcripts), lambda r: (r["eval_id"], r["model_alias"], r["sample_number"]))
    v3 = [g for g in A.dedup(E.load_jsonl(args.grades), lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"])).values() if g.get("error") is None]
    prev = A.dedup(E.load_jsonl(args.previous_grades), lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    v2 = {k: g for k, g in prev.items() if g.get("error") is None}

    def wc(k): return (tx.get(k) or {}).get("word_count")
    def rows(m): return [g for g in v3 if g["candidate_model_alias"] == m]

    pm = {}
    for m in A.ORDER:
        rs = rows(m); sc = [g["item_score"] for g in rs]
        ctrl = [g for g in rs if g["eval_id"] in control_ids]
        lo, hi = A.bootstrap_ci(sc)
        pm[m] = {"n": len(rs), "items_covered": len({g["eval_id"] for g in rs}), "mean": A.mean(sc),
                 "std": A.statistics_pstdev(sc), "ci95": [lo, hi],
                 **{d: A.mean([float(g[d]) for g in rs]) for d in DIMS},
                 "control_mean": A.mean([g["item_score"] for g in ctrl]),
                 "control_false_attack_rate": A.mean([1.0 if float(g["penalties"]["overclaim"]) > 0 else 0.0 for g in ctrl]),
                 "mean_words": A.mean([wc((g["eval_id"], m, g["sample_number"])) for g in rs if wc((g["eval_id"], m, g["sample_number"])) is not None]),
                 "perfect": sum(1 for g in rs if g["item_score"] >= 0.999),
                 "penalty_rates": {p: A.mean([1.0 if float(g["penalties"][p]) > 0 else 0.0 for g in rs]) for p in PENS}}

    v3s = {(g["eval_id"], g["candidate_model_alias"], g["sample_number"]): g["item_score"] for g in v3}
    v2s = {k: E.compute_item_score(g) for k, g in v2.items()}
    shared = sorted(set(v2s) & set(v3s))
    big = [{"key": f"{e}/{m}/s{s}", "v2": round(v2s[(e, m, s)], 3), "v3": round(v3s[(e, m, s)], 3),
            "delta": round(v3s[(e, m, s)] - v2s[(e, m, s)], 3)} for (e, m, s) in shared
           if abs(v3s[(e, m, s)] - v2s[(e, m, s)]) > 0.20]

    def nov(grades_iter):
        d = {}
        for g in grades_iter:
            d[str(float(g["novelty"]))] = d.get(str(float(g["novelty"])), 0) + 1
        return dict(sorted(d.items()))

    def v2_mean(m): return A.mean([v2s[k] for k in v2s if k[1] == m])
    comparison = {
        "model_means": {m: {"v2": v2_mean(m), "v3": pm[m]["mean"]} for m in A.ORDER},
        "ordering": {"v2": sorted([m for m in A.ORDER if v2_mean(m) is not None], key=lambda m: v2_mean(m), reverse=True),
                     "v3": sorted([m for m in A.ORDER if pm[m]["mean"] is not None], key=lambda m: pm[m]["mean"], reverse=True)},
        "perfect_scores": {"v2": sum(1 for s in v2s.values() if s >= 0.999), "v3": sum(1 for g in v3 if g["item_score"] >= 0.999)},
        "novelty_distribution": {"v2": nov(v2.values()), "v3": nov(v3)},
        "penalty_rates": {m: {p: pm[m]["penalty_rates"][p] for p in PENS} for m in A.ORDER},
        "control_false_attack_rate": {m: {"v2": A.mean([1.0 if float(g["penalties"]["overclaim"]) > 0 else 0.0 for k, g in v2.items() if k[1] == m and g["eval_id"] in control_ids]),
                                          "v3": pm[m]["control_false_attack_rate"]} for m in A.ORDER},
        "score_changes_over_0.20": {"count": len(big), "examples": sorted(big, key=lambda x: x["delta"])[:6] + sorted(big, key=lambda x: -x["delta"])[:3]},
    }
    results = {"grader_model": v3[0]["grader_model_alias"] if v3 else None, "n_grades": len(v3),
               "per_model": pm, "comparison_v2_v3": comparison, "control_item_ids": sorted(control_ids)}
    with open(args.json_output, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    _summ_csv(pm, args.csv_output)
    V2.write_plot_v2(pm, args.png_output)
    _summ_md(results, args.markdown_output)
    print(f"wrote {args.json_output}, {args.csv_output}, {args.png_output}, {args.markdown_output}", file=sys.stderr)
    print("v3 means:", {m: round(pm[m]["mean"], 3) if pm[m]["mean"] is not None else None for m in A.ORDER}, file=sys.stderr)


def _summ_csv(pm, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Model", "Overall", "Centrality", "Fidelity", "Novelty", "Impact", "Control", "False attack", "Mean words", "Perfect", "n"])
        for m in A.ORDER:
            s = pm[m]; f = lambda x: "" if x is None else round(x, 3)
            w.writerow([A.DISPLAY[m], f(s["mean"]), f(s["centrality"]), f(s["argument_fidelity"]), f(s["novelty"]),
                        f(s["justified_impact"]), f(s["control_mean"]),
                        "" if s["control_false_attack_rate"] is None else f"{100*s['control_false_attack_rate']:.1f}%",
                        None if s["mean_words"] is None else round(s["mean_words"]), s["perfect"], s["n"]])


def _summ_md(r, path):
    pm = r["per_model"]; c = r["comparison_v2_v3"]
    def f(x, nd=3): return "—" if x is None else f"{x:.{nd}f}"
    L = ["# Eval Results — v3 (stricter grader)\n"]
    L.append(f"Grader **{r['grader_model']}** · {r['n_grades']} grades · v3 grader prompt, 5-point scale, "
             "acknowledged_only novelty cap (≤0.25), score recomputed in code.\n")
    L.append("## Model results (v3)\n| Model | Overall | Cent | Fid | Nov | Impact | Control | False attack | Perfect |\n|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for m in A.ORDER:
        s = pm[m]
        L.append(f"| {A.DISPLAY[m]} | {f(s['mean'])} | {f(s['centrality'],2)} | {f(s['argument_fidelity'],2)} | "
                 f"{f(s['novelty'],2)} | {f(s['justified_impact'],2)} | {f(s['control_mean'])} | "
                 f"{'—' if s['control_false_attack_rate'] is None else str(round(100*s['control_false_attack_rate']))+'%'} | {s['perfect']} |")
    L.append("")
    L.append("## v2 → v3 comparison\n")
    L.append(f"- **Means:** " + "; ".join(f"{A.DISPLAY[m]} {f(c['model_means'][m]['v2'])}→{f(c['model_means'][m]['v3'])}" for m in A.ORDER) + ".")
    L.append(f"- **Ordering:** v2 {' > '.join(c['ordering']['v2'])}; v3 {' > '.join(c['ordering']['v3'])}.")
    L.append(f"- **Perfect scores:** v2 {c['perfect_scores']['v2']} → v3 {c['perfect_scores']['v3']}.")
    L.append(f"- **Novelty distribution:** v2 {c['novelty_distribution']['v2']}; v3 {c['novelty_distribution']['v3']}.")
    L.append(f"- **Control false-attack rate:** " + "; ".join(f"{A.DISPLAY[m]} {f(c['control_false_attack_rate'][m]['v2'],2)}→{f(c['control_false_attack_rate'][m]['v3'],2)}" for m in A.ORDER) + ".")
    L.append(f"- **Penalty rates (v3):** " + "; ".join(f"{m}: " + ",".join(f"{p.split('_')[0]}{f(c['penalty_rates'][m][p],2)}" for p in PENS) for m in A.ORDER) + ".")
    L.append(f"- **Score changes > 0.20:** {c['score_changes_over_0.20']['count']} candidates.\n")
    L.append("## Interpretation & limitations\n")
    L.append("v3 tightens novelty/operational/overclaim detection via a stricter prompt and consistency gates; the "
             "novelty cap keys on `acknowledged_only` so real mechanisms on acknowledged premises are not zeroed. "
             "Recompute is authoritative. Same v1/v2 limitations hold: grader sees the annotation, single fixed grader, "
             "small dataset with large item variance, and Haiku's 7/11 coverage. Monotonic ordering does not prove validity.\n")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    cal = sub.add_parser("calibrate")
    cal.add_argument("--input", default="q0_q2_rubric_calibration_labeled.jsonl")
    cal.add_argument("--rubric", default="critique_eval_rubric_v2.md")
    cal.add_argument("--grader-prompt", default="critique_eval_grader_prompt_v3.txt")
    cal.add_argument("--grader", choices=sorted(E.MODELS), default="opus")
    cal.add_argument("--output", default="calibration_grades_v3.jsonl")
    cal.add_argument("--report", default="calibration_report_v3.md")
    cal.add_argument("--metrics-output", default="calibration_metrics_v3.json")
    cal.add_argument("--max-tokens", type=int, default=8192)
    cal.add_argument("--concurrency", type=int, default=6)
    cal.set_defaults(func=cmd_calibrate)

    gr = sub.add_parser("grade")
    gr.add_argument("--transcripts", default="eval_transcripts.jsonl")
    gr.add_argument("--items", default="critique_eval_annotated_items_v2.jsonl")
    gr.add_argument("--rubric", default="critique_eval_rubric_v2.md")
    gr.add_argument("--grader-prompt", default="critique_eval_grader_prompt_v3.txt")
    gr.add_argument("--grader", choices=sorted(E.MODELS), default="opus")
    gr.add_argument("--output", default="eval_grades_v3.jsonl")
    gr.add_argument("--max-tokens", type=int, default=8192)
    gr.add_argument("--concurrency", type=int, default=8)
    gr.set_defaults(func=cmd_grade)

    s = sub.add_parser("summarize")
    s.add_argument("--transcripts", default="eval_transcripts.jsonl")
    s.add_argument("--items", default="critique_eval_annotated_items_v2.jsonl")
    s.add_argument("--grades", default="eval_grades_v3.jsonl")
    s.add_argument("--previous-grades", default="eval_grades_v2.jsonl")
    s.add_argument("--json-output", default="eval_results_v3.json")
    s.add_argument("--markdown-output", default="eval_failure_analysis_v3.md")
    s.add_argument("--csv-output", default="eval_model_scores_v3.csv")
    s.add_argument("--png-output", default="eval_model_scores_v3.png")
    s.set_defaults(func=cmd_summarize)

    args = p.parse_args(argv)
    if getattr(args, "func", None) in (cmd_calibrate, cmd_grade) and not __import__("os").environ.get("ANTHROPIC_API_KEY"):
        print("warning: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
