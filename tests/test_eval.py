"""Focused, deterministic tests for the correctness boundaries of the v2 eval.

No API calls. Uses inline fixtures and tests/fixtures/mini_grades.jsonl.
Run with:  python -m pytest tests/  (or)  python tests/test_eval.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis as A  # noqa: E402
import eval as E      # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Uniform annotation caps (as merged into every v2 item).
CAPS = {"centrality_if_only_secondary": 0.5, "novelty_if_acknowledged_only": 0.0,
        "impact_if_no_conclusion_effect": 0.5, "max_total_if_fatal_flaw_invented_on_control": 0.35}


def _grade(c, af, nov, ji, pens=None, **flags):
    g = {"centrality": c, "argument_fidelity": af, "novelty": nov, "justified_impact": ji,
         "penalties": {p: 0.0 for p in E.PENALTIES}}
    for p, v in (pens or {}).items():
        g["penalties"][p] = v
    g.update(flags)
    return g


# --- score calculation and clipping ---------------------------------------

def test_score_calculation_and_clipping():
    # 0.35*1 + 0.25*0.5 + 0.20*0 + 0.20*0.5 - 0.1  == 0.475 (the rubric's worked example)
    g = _grade(1, 0.5, 0, 0.5, {"laundry_list": 0.1})
    s, applied = E.score(g, {}, is_control=False)
    assert abs(s - 0.475) < 1e-9 and applied == []
    assert E.score(_grade(1, 1, 1, 1), {}, False)[0] == 1.0     # upper bound
    assert E.score(_grade(0, 0, 0, 0), {}, False)[0] == 0.0     # lower bound
    # clip floor: weighted 0.075 minus 0.25 penalty would be negative -> clipped to 0
    assert E.score(_grade(0, 0, 0, 0, {p: 0.1 for p in E.PENALTIES}), {}, False)[0] == 0.0


# --- penalty cap (sum capped at 0.25) -------------------------------------

def test_penalty_cap():
    assert E.score(_grade(1, 1, 1, 1, {p: 0.1 for p in E.PENALTIES}), {}, False)[0] == 0.75   # 0.5 -> capped 0.25
    assert abs(E.score(_grade(1, 1, 1, 1, {"laundry_list": 0.1, "overclaim": 0.1}), {}, False)[0] - 0.80) < 1e-9  # 0.2
    assert E.score(_grade(1, 1, 1, 1, {p: 0.1 for p in E.PENALTIES[:3]}), {}, False)[0] == 0.75  # 0.3 -> capped 0.25


# --- novelty / control / impact caps --------------------------------------

def test_novelty_cap_acknowledged_only():
    g = _grade(1, 1, 1, 1, already_acknowledged=True, disposition="narrows")
    s, applied = E.score(g, CAPS, is_control=False)
    assert "novelty_if_acknowledged_only" in applied
    assert abs(s - 0.80) < 1e-9  # novelty 1 -> 0: 0.35+0.25+0+0.20
    # not acknowledged -> novelty kept
    g2 = _grade(1, 1, 1, 1, already_acknowledged=False, disposition="narrows")
    assert E.score(g2, CAPS, is_control=False) == (1.0, [])


def test_control_total_cap():
    g = _grade(1, 1, 1, 1, already_acknowledged=False, disposition="defeats")
    s, applied = E.score(g, CAPS, is_control=True)
    assert "max_total_if_fatal_flaw_invented_on_control" in applied and abs(s - 0.35) < 1e-9
    # same disposition on a non-control item is not capped
    assert E.score(g, CAPS, is_control=False)[0] == 1.0


def test_impact_cap_no_valid_critique():
    g = _grade(1, 1, 1, 1, already_acknowledged=False, disposition="no_valid_critique")
    s, applied = E.score(g, CAPS, is_control=False)
    assert "impact_if_no_conclusion_effect" in applied
    assert abs(s - 0.90) < 1e-9  # impact 1 -> 0.5: 0.35+0.25+0.20+0.10


# --- invalid grader values ------------------------------------------------

def test_validate_grade_accepts_and_rejects():
    good = _grade(1, 0.75, 0.5, 0.25, already_acknowledged=True, disposition="narrows")
    assert E.validate_grade(good) is good
    bad = [
        _grade(0.7, 1, 1, 1, already_acknowledged=True, disposition="narrows"),   # dim off-scale
        dict(_grade(1, 1, 1, 1, already_acknowledged=True, disposition="narrows"),
             penalties={"laundry_list": 0.2, "overclaim": 0, "mere_operationalization": 0,
                        "retreat_as_repair": 0, "unsupported_claim": 0}),           # penalty off-scale
        _grade(1, 1, 1, 1, already_acknowledged=True, disposition="banana"),        # bad disposition
        _grade(1, 1, 1, 1, already_acknowledged="yes", disposition="narrows"),      # non-bool flag
    ]
    for b in bad:
        try:
            E.validate_grade(b)
            assert False, f"should have rejected {b}"
        except ValueError:
            pass


# --- malformed JSON repair behavior ---------------------------------------

def test_parse_grader_json_repair():
    obj = {"centrality": 1, "disposition": "narrows"}
    import json
    raw = json.dumps(obj)
    assert E.parse_grader_json(raw) == obj                              # plain
    assert E.parse_grader_json("```json\n" + raw + "\n```") == obj      # fenced
    assert E.parse_grader_json("Here is the grade:\n" + raw + "\nDone") == obj  # prose-wrapped -> {..} extracted
    try:
        E.parse_grader_json("no json here at all")
        assert False, "should raise on garbage"
    except Exception:
        pass


# --- duplicate-record selection (prefer ok over error) --------------------

def test_dedup_prefers_ok_over_error():
    rows = E.load_jsonl(os.path.join(FIX, "mini_grades.jsonl"))
    d = E.dedup(rows, lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    # key (1, haiku, 0) appears as error THEN ok -> the ok row wins
    assert d[(1, "haiku", 0)]["error"] is None and d[(1, "haiku", 0)]["item_score"] == 1.0


# --- per-item (cluster) aggregation ---------------------------------------

def test_item_level_aggregation_differs_from_pooled():
    rows = E.load_jsonl(os.path.join(FIX, "mini_grades.jsonl"))
    d = E.dedup(rows, lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    haiku = [g for g in d.values() if g["candidate_model_alias"] == "haiku" and g["error"] is None]
    il = A.item_level([{"eval_id": g["eval_id"], "item_score": g["item_score"]} for g in haiku])
    # item 0 = mean(1.0, 0.0) = 0.5 ; item 1 = 1.0 ; item-level mean = mean(0.5, 1.0) = 0.75
    assert abs(il["mean"] - 0.75) < 1e-9
    pooled = sum(g["item_score"] for g in haiku) / len(haiku)          # (1+0+1)/3 = 0.667
    assert abs(pooled - 2 / 3) < 1e-9 and il["mean"] != pooled
    assert il["covered_items"] == 2 and il["n_generations"] == 3


# --- partial coverage -----------------------------------------------------

def test_partial_coverage():
    rows = E.load_jsonl(os.path.join(FIX, "mini_grades.jsonl"))
    d = E.dedup(rows, lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    sonnet = [g for g in d.values() if g["candidate_model_alias"] == "sonnet" and g["error"] is None]
    il = A.item_level([{"eval_id": g["eval_id"], "item_score": g["item_score"]} for g in sonnet])
    assert il["covered_items"] == 1 and il["n_generations"] == 1        # sonnet only covered item 0


# --- robust-control identification ----------------------------------------

def test_robust_control_identification():
    assert E.is_robust_control({"annotation": {"gold_disposition": "qualify_no_fatal_flaw"}}) is True
    assert E.is_robust_control({"annotation": {"gold_disposition": "reject_or_rewrite"}}) is False
    assert E.is_robust_control({"annotation": {"gold_disposition": "narrow"}}) is False
    assert E.is_robust_control({}) is False                              # no annotation


# --- over-limit response recording (recorded, not enforced) ---------------

def test_over_word_limit_boundary():
    assert E.WORD_LIMIT == 300
    assert E.over_word_limit(299) is False
    assert E.over_word_limit(300) is False    # exactly the cap is compliant
    assert E.over_word_limit(301) is True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
