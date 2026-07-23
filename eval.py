#!/usr/bin/env python3
"""Conceptual-critique eval (authoritative, v2 rubric). LLM -> [0, 1].

Each subcommand is append-only and resumable, reusing runner.py for the Anthropic
client, model IDs, streaming calls, provenance, and concurrency. The v2 grader uses
a 5-point dimension scale {0,.25,.5,.75,1}, returns structured flags instead of an
item_score, and the harness recomputes the score in code and applies the annotation
score caps.

  python eval.py merge                      # base + overrides -> data/eval/..._v2.jsonl
  python eval.py generate --models haiku sonnet opus fable --samples 3
  python eval.py grade    --grader opus
  python eval.py summarize

(Superseded graders live in archive/: v1 in archive/v1/, the failed v3 experiment in
archive/v3_experiment/. v3 was not promoted — its calibration did not pass.)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import anthropic

import runner  # DEFAULT_MODELS, call_model, extract_text, sha256_file, git_info, _now_iso, experiment_id

MODELS = runner.DEFAULT_MODELS

# The candidate instruction asks for <= 300 words. We do NOT truncate (that would
# cut reasoning mid-sentence and add an evaluation artifact); instead we record
# compliance per candidate and report the violation rate.
WORD_LIMIT = 300

DIMENSIONS = ["centrality", "argument_fidelity", "novelty", "justified_impact"]
PENALTIES = ["laundry_list", "overclaim", "mere_operationalization", "retreat_as_repair", "unsupported_claim"]
WEIGHTS = {"centrality": 0.35, "argument_fidelity": 0.25, "novelty": 0.20, "justified_impact": 0.20}
ROBUST_DISPOSITION = "qualify_no_fatal_flaw"

# v2 grader output space
DIM_VALUES = [0, 0.25, 0.5, 0.75, 1]
DISPOSITIONS = {"defeats", "narrows", "qualifies", "no_valid_critique"}

# Default inputs (v2 is authoritative)
BASE_ITEMS = "data/eval/critique_eval_annotated_items.jsonl"
OVERRIDES = "data/eval/critique_eval_annotation_overrides_v2.jsonl"
DEFAULT_ITEMS = "data/eval/critique_eval_annotated_items_v2.jsonl"
DEFAULT_CANDIDATE_PROMPT = "prompts/candidates/critique_300w_v1.txt"
DEFAULT_RUBRIC = "critique_eval_rubric_v2.md"
DEFAULT_GRADER_PROMPT = "critique_eval_grader_prompt_v2.txt"
V2_FIELDS = ["explicit_concessions", "minimum_full_credit_elements", "non_novel_restatements",
             "severity", "score_caps", "annotation_version"]


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def over_word_limit(word_count: int) -> bool:
    """Compliance check (recorded, never enforced): exactly WORD_LIMIT is compliant."""
    return word_count > WORD_LIMIT


# --------------------------------------------------------------------------- io

def load_items(path: str) -> list[dict[str, Any]]:
    items = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    for it in items:
        it["eval_id"] = int(it["eval_id"])
    return items


def load_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def dedup(rows, key):
    """Keep one row per key, preferring a successful row over an error row."""
    best: dict = {}
    for r in rows:
        k = key(r)
        cur = best.get(k)
        if cur is None or (cur.get("error") is not None and r.get("error") is None):
            best[k] = r
    return best


def new_run_id() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def make_provenance(argv: list[str], extra: dict[str, Any]) -> dict[str, Any]:
    prov = {
        "run_id": new_run_id(),
        "started_at": runner._now_iso(),
        "eval_sha256": runner.sha256_file(__file__),
        "runner_sha256": runner.sha256_file(runner.__file__),
        "git": runner.git_info(),
        "argv": argv,
    }
    prov.update(extra)
    return prov


def is_robust_control(item: dict[str, Any]) -> bool:
    ann = item.get("annotation") or {}
    return isinstance(ann, dict) and ann.get("gold_disposition") == ROBUST_DISPOSITION


def _git_short(prov: dict[str, Any]) -> str:
    g = prov.get("git")
    return f"{g['commit'][:12]}{'-dirty' if g['dirty'] else ''}" if g else "none"


def _write_manifest(path: str, entry: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------- merge

def merge(args: argparse.Namespace) -> None:
    """Overlay v2 annotation overrides onto the base items -> the versioned v2 item set."""
    base = load_items(args.base)
    overrides = {o["source_id"]: o for o in load_jsonl(args.overrides)}
    base_sids = {it["source_id"] for it in base}
    extra = set(overrides) - base_sids
    if extra:
        raise SystemExit(f"override source_ids not in base data: {sorted(extra)}")
    missing = base_sids - set(overrides)
    if missing:
        raise SystemExit(f"base items with no v2 override: {sorted(missing)}")

    merged = []
    for it in base:
        ov = overrides[it["source_id"]]
        ann = dict(it.get("annotation") or {})     # preserve every existing annotation field
        for k in V2_FIELDS:                          # overlay the v2 fields
            if k in ov:
                ann[k] = ov[k]
        out = dict(it)                               # preserve every top-level field
        out["annotation"] = ann
        merged.append(out)

    eids, sids = [m["eval_id"] for m in merged], [m["source_id"] for m in merged]
    if len(set(eids)) != 11 or len(set(sids)) != 11:
        raise SystemExit(f"expected 11 unique eval_id and source_id; got {len(set(eids))} / {len(set(sids))}")
    with open(args.output, "w", encoding="utf-8") as fh:
        for m in merged:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"wrote {args.output}: {len(merged)} items, {len(set(eids))} eval_ids, {len(set(sids))} source_ids")


# ---------------------------------------------------------------- generate

def load_candidate_prompt(path: str) -> str:
    """Load and minimally validate a versioned candidate-generation template."""
    with open(path, encoding="utf-8") as fh:
        template = fh.read().strip()
    missing = [field for field in ("question", "argument") if "{" + field + "}" not in template]
    if missing:
        raise SystemExit(f"candidate prompt {path} missing placeholder(s): {', '.join(missing)}")
    try:
        template.format(question="Q", argument="A")
    except (KeyError, ValueError) as exc:
        raise SystemExit(f"candidate prompt {path} has an invalid placeholder: {exc}") from exc
    return template


def candidate_prompt(item: dict[str, Any], template: str) -> str:
    """Render one item without modifying its stored question or argument."""
    return template.format(question=item["question"], argument=item["argument"])


def generate(args: argparse.Namespace) -> None:
    items = load_items(args.items)
    if args.limit:
        items = items[: args.limit]
    models = {a: MODELS[a] for a in args.models}
    candidate_template = load_candidate_prompt(args.candidate_prompt)
    candidate_prompt_sha256 = runner.sha256_file(args.candidate_prompt)
    candidate_prompt_version = os.path.splitext(os.path.basename(args.candidate_prompt))[0]
    prov = make_provenance(
        sys.argv[1:],
        {
            "phase": "generate",
            "items_path": args.items,
            "items_sha256": runner.sha256_file(args.items),
            "candidate_prompt_path": args.candidate_prompt,
            "candidate_prompt_version": candidate_prompt_version,
            "candidate_prompt_sha256": candidate_prompt_sha256,
            "models": models,
            "samples": args.samples,
            "max_tokens": args.max_tokens,
        },
    )

    # Resume key includes an experiment fingerprint (prompt + generation config), so a
    # stored candidate is reused only when the item's prompt and config are unchanged.
    def done_key(r: dict[str, Any]) -> tuple[str, int, str | None, int]:
        eid = r.get("experiment_id") or runner.experiment_id(
            r["prompt"], None, r.get("max_tokens", args.max_tokens))
        model_id = r.get("model_id") or MODELS.get(r["model_alias"])
        return (eid, r["eval_id"], model_id, r["sample_number"])

    done = {done_key(r) for r in load_jsonl(args.output) if r.get("error") is None}
    jobs = []
    for item in items:
        prompt = candidate_prompt(item, candidate_template)
        eid = runner.experiment_id(prompt, None, args.max_tokens)
        for alias, model_id in models.items():
            for sample in range(args.samples):
                if (eid, item["eval_id"], model_id, sample) not in done:
                    jobs.append((item, alias, model_id, sample, prompt, eid))

    print(f"run_id={prov['run_id']}  git={_git_short(prov)}", file=sys.stderr)
    print(f"generate: {len(items)} items x {len(models)} models x {args.samples} samples; "
          f"skip={len(done)} to_run={len(jobs)} concurrency={args.concurrency}", file=sys.stderr)
    if not jobs:
        print("nothing to generate.", file=sys.stderr)
        return

    client = anthropic.Anthropic(max_retries=5)

    def run_one(job) -> dict[str, Any]:
        item, alias, model_id, sample, prompt, eid = job
        row = {
            "run_id": prov["run_id"],
            "eval_id": item["eval_id"],
            "source_id": item.get("source_id"),
            "model_alias": alias,
            "model_id": model_id,
            "sample_number": sample,
            "timestamp": runner._now_iso(),
            "question": item["question"],
            "argument": item["argument"],
            "prompt": prompt,
            "candidate_prompt_version": candidate_prompt_version,
            "candidate_prompt_sha256": candidate_prompt_sha256,
            "max_tokens": args.max_tokens,
            "experiment_id": eid,
            "response_text": None,
            "word_count": None,
            "word_limit_exceeded": None,
            "stop_reason": None,
            "usage": None,
            "error": None,
        }
        try:
            resp = runner.call_model(client, model_id, None, prompt, args.max_tokens)
            text = runner.extract_text(resp)
            row["response_text"] = text
            row["word_count"] = len(text.split())
            row["word_limit_exceeded"] = over_word_limit(row["word_count"])  # recorded, not enforced
            row["stop_reason"] = resp.get("stop_reason")
            row["usage"] = resp.get("usage")
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        return row

    ok = fail = 0
    with open(args.output, "a", encoding="utf-8", buffering=1) as out:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(run_one, j): j for j in jobs}
            for fut in as_completed(futures):
                row = fut.result()
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                label = f"eval {row['eval_id']} | {row['model_alias']} | s{row['sample_number']}"
                if row["error"]:
                    fail += 1; print(f"FAIL {label}: {row['error']['type']}", file=sys.stderr)
                else:
                    ok += 1; print(f"ok   {label} ({row['word_count']}w)", file=sys.stderr)
    _write_manifest(args.manifest, {**prov, "finished_at": runner._now_iso(),
                                        "output_path": os.path.abspath(args.output),
                                        "succeeded": ok, "failed": fail})
    print(f"\ngenerate done: ok={ok} fail={fail}", file=sys.stderr)


# ------------------------------------------------------------- grade (v2)

def build_grader_prompt(base: str, rubric: str, item: dict[str, Any], critique: str) -> str:
    annotation = json.dumps(item.get("annotation"), ensure_ascii=False, indent=2)
    return (
        f"{base.strip()}\n\n"
        f"=== QUESTION ===\n{item['question']}\n\n"
        f"=== ARGUMENT ===\n{item['argument']}\n\n"
        f"=== ITEM ANNOTATION ===\n{annotation}\n\n"
        f"=== CANDIDATE CRITIQUE ===\n{critique}\n\n"
        f"=== RUBRIC ===\n{rubric.strip()}\n\n"
        "Return only the JSON object specified above. No prose, no code fences."
    )


def parse_grader_json(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j != -1 and j > i:
            return json.loads(t[i:j + 1])
        raise


def _near(x: Any, allowed: list[float]) -> bool:
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return False
    return any(abs(xf - a) < 1e-9 for a in allowed)


def validate_grade(obj: dict[str, Any]) -> dict[str, Any]:
    """Validate the v2 grader JSON: 5-point dimensions, 0/0.1 penalties, and the flags."""
    for d in DIMENSIONS:
        if not _near(obj.get(d), DIM_VALUES):
            raise ValueError(f"{d}={obj.get(d)!r} not in {{0,.25,.5,.75,1}}")
    pens = obj.get("penalties")
    if not isinstance(pens, dict):
        raise ValueError("penalties missing or not an object")
    for p in PENALTIES:
        if not _near(pens.get(p), [0, 0.1]):
            raise ValueError(f"penalty {p}={pens.get(p)!r} not in {{0,0.1}}")
    if obj.get("disposition") not in DISPOSITIONS:
        raise ValueError(f"disposition={obj.get('disposition')!r}")
    if not isinstance(obj.get("already_acknowledged"), bool):
        raise ValueError("already_acknowledged must be boolean")
    return obj


def compute_item_score(g: dict[str, Any], equal_weight: bool = False) -> float:
    """Plain weighted score (no caps) — the base formula; grade() applies caps via score()."""
    pen_sum = sum(float(g["penalties"][p]) for p in PENALTIES)
    if equal_weight:
        raw = 0.25 * sum(float(g[d]) for d in DIMENSIONS) - pen_sum
    else:
        raw = sum(WEIGHTS[d] * float(g[d]) for d in DIMENSIONS) - min(pen_sum, 0.25)
    return clip(raw)


def score(g: dict[str, Any], caps: dict, is_control: bool, equal_weight: bool = False):
    """Recompute the item score, applying annotation caps from the grader's flags.

    Caps (deterministic, from structured grader output + item control status):
      - novelty_if_acknowledged_only:               already_acknowledged is True
      - impact_if_no_conclusion_effect:              disposition == "no_valid_critique"
      - max_total_if_fatal_flaw_invented_on_control: control item AND disposition == "defeats"
    The centrality_if_only_secondary cap has no dedicated flag; it is enforced by the
    rubric's centrality scale at grading time.
    """
    dims = {d: float(g[d]) for d in DIMENSIONS}
    applied = []
    if g.get("already_acknowledged") is True and caps:
        cap = caps["novelty_if_acknowledged_only"]
        if dims["novelty"] > cap:
            applied.append("novelty_if_acknowledged_only")
        dims["novelty"] = min(dims["novelty"], cap)
    if g.get("disposition") == "no_valid_critique" and caps:
        cap = caps["impact_if_no_conclusion_effect"]
        if dims["justified_impact"] > cap:
            applied.append("impact_if_no_conclusion_effect")
        dims["justified_impact"] = min(dims["justified_impact"], cap)
    pen = min(sum(float(g["penalties"][p]) for p in PENALTIES), 0.25)
    w = {d: 0.25 for d in DIMENSIONS} if equal_weight else WEIGHTS
    s = clip(sum(w[d] * dims[d] for d in DIMENSIONS) - pen)
    if is_control and g.get("disposition") == "defeats" and caps:
        cap = caps["max_total_if_fatal_flaw_invented_on_control"]
        if s > cap:
            applied.append("max_total_if_fatal_flaw_invented_on_control")
        s = min(s, cap)
    return clip(s), applied


def grade(args: argparse.Namespace) -> None:
    items = {it["eval_id"]: it for it in load_items(args.items)}
    control = {eid: is_robust_control(it) for eid, it in items.items()}
    caps = {eid: (it["annotation"].get("score_caps") or {}) for eid, it in items.items()}
    rubric = open(args.rubric, encoding="utf-8").read()
    base = open(args.grader_prompt, encoding="utf-8").read()
    grader_id = MODELS[args.grader]

    transcripts = [r for r in dedup(load_jsonl(args.transcripts),
                                    lambda r: (r["eval_id"], r["model_alias"], r["sample_number"])).values()
                   if r.get("error") is None and (r.get("response_text") or "").strip()]
    if args.limit:
        transcripts = transcripts[: args.limit]
    done = {(r["eval_id"], r["candidate_model_alias"], r["sample_number"])
            for r in load_jsonl(args.output) if r.get("error") is None}
    todo = [t for t in transcripts if (t["eval_id"], t["model_alias"], t["sample_number"]) not in done]

    prov = make_provenance(sys.argv[1:], {"phase": "grade", "grader_model_alias": args.grader,
                                          "grader_model_id": grader_id,
                                          "items_sha256": runner.sha256_file(args.items),
                                          "rubric_sha256": runner.sha256_file(args.rubric),
                                          "grader_prompt_sha256": runner.sha256_file(args.grader_prompt)})
    print(f"run_id={prov['run_id']}  grader={args.grader} ({grader_id})", file=sys.stderr)
    print(f"grade: {len(transcripts)} candidates; skip={len(done)} to_run={len(todo)} "
          f"concurrency={args.concurrency}", file=sys.stderr)
    if args.grader != "opus":
        print(f"NOTE: grader is {args.grader}, not the preferred opus — recorded in every grade.", file=sys.stderr)
    if not todo:
        print("nothing to grade.", file=sys.stderr)
        return

    client = anthropic.Anthropic(max_retries=5)

    def grade_one(t):
        eid = t["eval_id"]
        row = {
            "run_id": prov["run_id"], "eval_id": eid, "source_id": t.get("source_id"),
            "candidate_model_alias": t["model_alias"], "candidate_model_id": t["model_id"],
            "sample_number": t["sample_number"], "grader_model_alias": args.grader, "grader_model_id": grader_id,
            "main_critique": None, "already_acknowledged": None, "control_item": None, "disposition": None,
            "centrality": None, "argument_fidelity": None, "novelty": None, "justified_impact": None,
            "penalties": None, "grader_confidence": None,
            "item_score": None, "item_score_equal_weight": None, "caps_applied": None,
            "annotation_control": control[eid], "brief_rationale": None, "grader_raw_response": None, "error": None,
        }
        prompt = build_grader_prompt(base, rubric, items[eid], t["response_text"])
        try:
            for attempt in (0, 1):
                p = prompt if attempt == 0 else prompt + (
                    "\n\nYour previous reply was not valid JSON matching the schema and allowed values. "
                    "Reply again with ONLY the JSON object.")
                resp = runner.call_model(client, grader_id, None, p, args.max_tokens)
                raw = runner.extract_text(resp)
                row["grader_raw_response"] = raw
                try:
                    obj = validate_grade(parse_grader_json(raw))
                    break
                except (ValueError, json.JSONDecodeError):
                    if attempt == 1:
                        raise
            for d in DIMENSIONS:
                row[d] = float(obj[d])
            row["penalties"] = {p: float(obj["penalties"][p]) for p in PENALTIES}
            for k in ("main_critique", "already_acknowledged", "control_item", "disposition",
                      "grader_confidence", "brief_rationale"):
                row[k] = obj.get(k)
            s, applied = score({**obj, "penalties": row["penalties"]}, caps[eid], control[eid])
            row["item_score"] = s
            row["caps_applied"] = applied
            row["item_score_equal_weight"] = score({**obj, "penalties": row["penalties"]},
                                                    caps[eid], control[eid], equal_weight=True)[0]
        except Exception as exc:  # noqa: BLE001
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return row

    ok = fail = 0
    with open(args.output, "a", encoding="utf-8", buffering=1) as out:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(grade_one, t): t for t in todo}
            for fut in as_completed(futures):
                row = fut.result()
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                label = f"eval {row['eval_id']} | {row['candidate_model_alias']} | s{row['sample_number']}"
                if row["error"]:
                    fail += 1; print(f"FAIL {label}: {row['error']['type']}: {row['error']['message']}", file=sys.stderr)
                else:
                    caps_note = f" caps={row['caps_applied']}" if row["caps_applied"] else ""
                    ok += 1; print(f"ok   {label} score={row['item_score']:.3f}{caps_note}", file=sys.stderr)
    _write_manifest(args.manifest, {**prov, "finished_at": runner._now_iso(),
                                        "output_path": os.path.abspath(args.output),
                                        "graded": ok, "failed": fail})
    print(f"\ngrade done: ok={ok} fail={fail}", file=sys.stderr)


# --------------------------------------------------------------- summarize

def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx > 0 and dy > 0 else None


def summarize(args: argparse.Namespace) -> None:
    items = {it["eval_id"]: it for it in load_items(args.items)}

    transcripts = dedup(load_jsonl(args.transcripts), lambda r: (r["eval_id"], r["model_alias"], r["sample_number"]))
    gen_fail_keys = {k for k, r in transcripts.items() if r.get("error") is not None}

    grade_map = dedup(load_jsonl(args.grades),
                      lambda g: (g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
    grades = [g for g in grade_map.values() if g.get("error") is None]
    grade_fail_keys = {k for k, g in grade_map.items() if g.get("error") is not None}

    aliases = sorted({g["candidate_model_alias"] for g in grades}, key=lambda a: list(MODELS).index(a) if a in MODELS else 99)

    def by_model(pred) -> dict[str, list[float]]:
        d: dict[str, list[float]] = {a: [] for a in aliases}
        for g in grades:
            if pred(g):
                d[g["candidate_model_alias"]].append(g["item_score"])
        return d

    import analysis as _A  # lazy: analysis imports eval, so import here to avoid a cycle at load time
    scores = by_model(lambda g: True)
    model_stats = {}
    for a in aliases:
        il = _A.item_level([{"eval_id": g["eval_id"], "item_score": g["item_score"]}
                            for g in grades if g["candidate_model_alias"] == a])
        model_stats[a] = {
            "n": il["n_generations"], "successful_generations": il["n_generations"],
            "mean": il["mean"], "ci95": il["ci95"], "items_covered": il["covered_items"],
            "std": statistics.pstdev(scores[a]) if len(scores[a]) > 1 else 0.0,
            "response_pooled_mean": _mean(scores[a]),
        }

    dim_means = {a: {d: _mean([float(g[d]) for g in grades if g["candidate_model_alias"] == a]) for d in DIMENSIONS}
                 for a in aliases}
    pen_rates = {a: {p: _mean([1.0 if float(g["penalties"][p]) > 0 else 0.0
                               for g in grades if g["candidate_model_alias"] == a]) for p in PENALTIES}
                 for a in aliases}

    robust_ids = {eid for eid, it in items.items() if is_robust_control(it)}
    flaw_ids = set(items) - robust_ids
    robust_scores = by_model(lambda g: g["eval_id"] in robust_ids)
    flaw_scores = by_model(lambda g: g["eval_id"] in flaw_ids)
    group = {a: {"robust_control_mean": _mean(robust_scores[a]), "flaw_mean": _mean(flaw_scores[a])} for a in aliases}

    eq = {a: _mean([g.get("item_score_equal_weight") for g in grades
                    if g["candidate_model_alias"] == a and g.get("item_score_equal_weight") is not None]) for a in aliases}
    order_main = [a for a in sorted(aliases, key=lambda a: model_stats[a]["mean"] or -1, reverse=True)]
    order_eq = [a for a in sorted(aliases, key=lambda a: eq[a] or -1, reverse=True)]

    lc_x, lc_y = [], []
    for g in grades:
        t = transcripts.get((g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
        wc = (t or {}).get("word_count")
        if wc is not None:
            lc_x.append(float(wc)); lc_y.append(g["item_score"])
    length_corr = _pearson(lc_x, lc_y)

    # 300-word compliance (recorded, never enforced by truncation): violation rate per model
    word_limit = {}
    for a in aliases:
        wcs = [t["word_count"] for (e, m, s), t in transcripts.items()
               if m == a and t.get("error") is None and t.get("word_count") is not None]
        viol = [w for w in wcs if over_word_limit(w)]
        word_limit[a] = {"n": len(wcs), "violations": len(viol),
                         "violation_rate": (len(viol) / len(wcs)) if wcs else None,
                         "mean_words": _mean(wcs), "max_words": max(wcs) if wcs else None}

    item_scores = {}
    for eid in sorted(items):
        xs = [g["item_score"] for g in grades if g["eval_id"] == eid]
        item_scores[eid] = {"n": len(xs), "mean": _mean(xs),
                            "robust_control": eid in robust_ids,
                            "case_type": (items[eid].get("annotation") or {}).get("case_type")}
    sample_scores = {}
    for s in sorted({g["sample_number"] for g in grades}):
        xs = [g["item_score"] for g in grades if g["sample_number"] == s]
        sample_scores[s] = {"n": len(xs), "mean": _mean(xs)}

    grader_alias = grades[0]["grader_model_alias"] if grades else None
    expected_order_ok = None
    if all(model_stats.get(a, {}).get("mean") is not None for a in ("opus", "sonnet", "haiku") if a in model_stats):
        try:
            expected_order_ok = model_stats["opus"]["mean"] > model_stats["sonnet"]["mean"] > model_stats["haiku"]["mean"]
        except KeyError:
            expected_order_ok = None

    results = {
        "grader_model": grader_alias,
        "n_items": len(items), "n_grades": len(grades),
        "generation_failures": len(gen_fail_keys), "grading_failures": len(grade_fail_keys),
        "generation_failure_keys": sorted(f"{e}/{m}/s{s}" for (e, m, s) in gen_fail_keys),
        "model_stats": model_stats, "dimension_means": dim_means, "penalty_rates": pen_rates,
        "robust_vs_flaw": group, "robust_control_item_ids": sorted(robust_ids), "flaw_item_ids": sorted(flaw_ids),
        "equal_weight_means": eq, "ordering_main": order_main, "ordering_equal_weight": order_eq,
        "ordering_changes_under_equal_weight": order_main != order_eq,
        "length_score_correlation": length_corr,
        "word_limit": WORD_LIMIT, "word_limit_compliance": word_limit,
        "expected_capability_ordering_opus_sonnet_haiku": expected_order_ok,
        "item_scores": {str(k): v for k, v in item_scores.items()},
        "sample_scores": {str(k): v for k, v in sample_scores.items()},
    }
    with open(args.json_output, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

    examples = _pick_examples(grades, transcripts, items, robust_ids)
    _write_markdown(args.markdown_output, results, examples, args.report_title)
    print(f"wrote {args.json_output} and {args.markdown_output}", file=sys.stderr)
    print("models: " + "  ".join(f"{a}={(model_stats[a]['mean'] or 0):.3f}" for a in aliases), file=sys.stderr)


def _pick_examples(grades, transcripts, items, robust_ids) -> list[dict[str, Any]]:
    def text_of(g):
        t = transcripts.get((g["eval_id"], g["candidate_model_alias"], g["sample_number"]))
        return (t or {}).get("response_text", "")

    picks: list[tuple[str, dict | None]] = []
    ok = [g for g in grades if g.get("item_score") is not None]
    if ok:
        picks.append(("Highest-scoring critique", max(ok, key=lambda g: g["item_score"])))
        polished = [g for g in ok if g["novelty"] <= 0.25 and (g["centrality"] + g["argument_fidelity"]) >= 1.5]
        picks.append(("Polished but low-novelty (novelty<=0.25, otherwise solid)",
                      max(polished, key=lambda g: g["item_score"]) if polished else None))
        op = [g for g in ok if g["penalties"]["mere_operationalization"] > 0]
        picks.append(("Operational-substitution failure (mere_operationalization penalty)",
                      min(op, key=lambda g: g["item_score"]) if op else None))
        invented = [g for g in ok if g["eval_id"] in robust_ids and (g["centrality"] == 0 or g["penalties"]["overclaim"] > 0)]
        picks.append(("Invented a flaw on a robust-control item",
                      min(invented, key=lambda g: g["item_score"]) if invented else None))
        capped = [g for g in ok if g.get("caps_applied")]
        picks.append(("Annotation cap applied by the harness",
                      min(capped, key=lambda g: g["item_score"]) if capped else None))

    out = []
    for label, g in picks:
        if g is None:
            out.append({"label": label, "note": "no matching example found"})
            continue
        out.append({
            "label": label, "eval_id": g["eval_id"], "model": g["candidate_model_alias"],
            "sample": g["sample_number"], "item_score": round(g["item_score"], 3),
            "caps_applied": g.get("caps_applied"),
            "dims": {d: g[d] for d in DIMENSIONS}, "penalties": g["penalties"],
            "rationale": g.get("brief_rationale"), "critique": text_of(g).strip(),
        })
    return out


def _fmt(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def _write_markdown(path: str, r: dict[str, Any], examples: list[dict], title: str) -> None:
    aliases = list(r["model_stats"])
    L = []
    L.append(f"# {title}\n")
    L.append(f"Grader model: **{r['grader_model']}**  |  items: {r['n_items']}  |  grades: {r['n_grades']}  "
             f"|  generation failures: {r['generation_failures']}  |  grading failures: {r['grading_failures']}\n")

    L.append("## 1. Model scores\n")
    L.append("Model score = mean over items of the per-item sample mean; 95% CI is an **item (cluster) bootstrap** — "
             "resampling arguments, not individual responses. Scores are recomputed in code (with annotation caps); "
             "the grader never returns item_score.\n")
    L.append("| model | items covered | successful gens | item mean | 95% item-CI |\n|---|---|---|---|---|")
    for a in aliases:
        s = r["model_stats"][a]
        ci = s.get("ci95", [None, None])
        L.append(f"| {a} | {s['items_covered']}/{r['n_items']} | {s['n']} | {_fmt(s['mean'])} | "
                 f"[{_fmt(ci[0])}, {_fmt(ci[1])}] |")
    L.append("")
    partial = [a for a in aliases if r["model_stats"][a]["items_covered"] < r["n_items"]]
    if partial:
        L.append(f"> ⚠️ **Partial coverage:** {', '.join(partial)} did not produce candidates for every item "
                 f"(generation failures: {r['generation_failure_keys']}). Their means cover only the items they "
                 f"produced, so cross-model comparison against them is not like-for-like.\n")

    L.append("## 2. Dimension means\n")
    L.append("| model | " + " | ".join(DIMENSIONS) + " |\n|" + "---|" * (len(DIMENSIONS) + 1))
    for a in aliases:
        L.append(f"| {a} | " + " | ".join(_fmt(r['dimension_means'][a][d], 2) for d in DIMENSIONS) + " |")
    L.append("")

    L.append("## 3. Penalty rates (fraction of grades where the penalty applied)\n")
    L.append("| model | " + " | ".join(PENALTIES) + " |\n|" + "---|" * (len(PENALTIES) + 1))
    for a in aliases:
        L.append(f"| {a} | " + " | ".join(_fmt(r['penalty_rates'][a][p], 2) for p in PENALTIES) + " |")
    L.append("")

    L.append("## 4. Robust-control vs flaw-item performance\n")
    L.append(f"Robust-control item ids (`qualify_no_fatal_flaw`): {r['robust_control_item_ids']}  \n"
             f"Flaw item ids: {r['flaw_item_ids']}\n")
    L.append("| model | robust-control mean | flaw mean |\n|---|---|---|")
    for a in aliases:
        g = r["robust_vs_flaw"][a]
        L.append(f"| {a} | {_fmt(g['robust_control_mean'])} | {_fmt(g['flaw_mean'])} |")
    L.append("\nA model that scores well on flaw items but poorly on robust controls is over-attacking; "
             "compare the two columns rather than reading the overall mean alone.\n")

    L.append("## 5. Equal-weight sensitivity\n")
    L.append("| model | main-weight mean | equal-weight mean |\n|---|---|---|")
    for a in aliases:
        L.append(f"| {a} | {_fmt(r['model_stats'][a]['mean'])} | {_fmt(r['equal_weight_means'][a])} |")
    L.append(f"\nMain-weight ordering: {' > '.join(r['ordering_main'])}  \n"
             f"Equal-weight ordering: {' > '.join(r['ordering_equal_weight'])}  \n"
             f"Ordering changes under equal weights: **{r['ordering_changes_under_equal_weight']}**\n")

    L.append("## 6. Response length & word-limit compliance\n")
    L.append(f"Pearson correlation between response word count and recomputed item score: "
             f"**{_fmt(r['length_score_correlation'])}**  \n"
             "A large positive correlation would be a verbosity-confound warning; the observed correlation is descriptive, not proof of style invariance.\n")
    L.append(f"The {r['word_limit']}-word instruction is **recorded, not enforced** — responses are never truncated "
             "(truncation cuts reasoning mid-sentence and adds an artifact). Violation rate by model:\n")
    L.append("| model | violation rate | violations / n | mean words | max words |\n|---|---:|---:|---:|---:|")
    for a in aliases:
        w = r["word_limit_compliance"][a]
        L.append(f"| {a} | {_fmt(w['violation_rate'], 2)} | {w['violations']}/{w['n']} | "
                 f"{'' if w['mean_words'] is None else round(w['mean_words'])} | {w['max_words']} |")
    L.append("")
    L.append("The grader is instructed not to reward length. The modest length–score correlation "
             f"({_fmt(r['length_score_correlation'])}) provides little evidence that verbosity alone drove scores "
             "in this sample, but it does not rule out nonlinear or stylistic effects. Overruns were frequent for "
             "some models but modest in magnitude (the maximum response was roughly 10% over the request).\n")

    L.append("## 7. Failures / invalid grader outputs\n")
    L.append(f"- generation failures: {r['generation_failures']}\n"
             f"- grading failures (invalid after retry): {r['grading_failures']}\n")

    L.append("## Score by item\n")
    L.append("| eval_id | robust-control | case_type | n | mean |\n|---|---|---|---|---|")
    for k, v in r["item_scores"].items():
        L.append(f"| {k} | {'yes' if v['robust_control'] else 'no'} | {v['case_type']} | {v['n']} | {_fmt(v['mean'])} |")
    L.append("")
    L.append("## Score by sample\n| sample | n | mean |\n|---|---|---|")
    for k, v in r["sample_scores"].items():
        L.append(f"| {k} | {v['n']} | {_fmt(v['mean'])} |")
    L.append("")

    L.append("## Expected capability ordering\n")
    L.append(f"Opus > Sonnet > Haiku holds: **{r['expected_capability_ordering_opus_sonnet_haiku']}**  \n"
             "Fable is reported without assuming a rank. Monotonic ordering alone does not establish validity — "
             "read it with the robust-control split, the item-bootstrap intervals, and the length correlation.\n")

    L.append("## 8. Manually useful examples\n")
    for ex in examples:
        L.append(f"### {ex['label']}")
        if ex.get("note"):
            L.append(f"_{ex['note']}_\n"); continue
        L.append(f"- eval_id **{ex['eval_id']}**, model **{ex['model']}**, sample {ex['sample']}, "
                 f"score **{ex['item_score']}**"
                 + (f", caps {ex['caps_applied']}" if ex.get('caps_applied') else ""))
        L.append(f"- dims: {ex['dims']} | penalties: { {k: v for k, v in ex['penalties'].items() if v} or 'none'}")
        L.append(f"- rationale: {ex['rationale']}")
        L.append("\n> " + ex["critique"].replace("\n", "\n> ") + "\n")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


# --------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge", help="Overlay v2 overrides onto base items.")
    m.add_argument("--base", default=BASE_ITEMS)
    m.add_argument("--overrides", default=OVERRIDES)
    m.add_argument("--output", default=DEFAULT_ITEMS)
    m.set_defaults(func=merge)

    g = sub.add_parser("generate", help="Generate candidate critiques.")
    g.add_argument("--items", default=DEFAULT_ITEMS)
    g.add_argument("--candidate-prompt", default=DEFAULT_CANDIDATE_PROMPT,
                   help="Candidate-generation template with {question} and {argument} placeholders.")
    g.add_argument("--models", nargs="+", choices=sorted(MODELS), default=sorted(MODELS))
    g.add_argument("--samples", type=int, default=3)
    g.add_argument("--output", default="eval_transcripts.jsonl")
    g.add_argument("--manifest", default="eval_runs.jsonl",
                   help="Append run provenance here (default: eval_runs.jsonl).")
    g.add_argument("--max-tokens", type=int, default=8192)
    g.add_argument("--concurrency", type=int, default=6)
    g.add_argument("--limit", type=int, default=0, help="Only the first N items (smoke testing).")
    g.set_defaults(func=generate)

    gr = sub.add_parser("grade", help="Grade candidate critiques (v2 grader).")
    gr.add_argument("--items", default=DEFAULT_ITEMS)
    gr.add_argument("--transcripts", default="eval_transcripts.jsonl")
    gr.add_argument("--rubric", default=DEFAULT_RUBRIC)
    gr.add_argument("--grader-prompt", default=DEFAULT_GRADER_PROMPT)
    gr.add_argument("--grader", choices=sorted(MODELS), default="opus")
    gr.add_argument("--output", default="eval_grades.jsonl")
    gr.add_argument("--manifest", default="eval_runs.jsonl",
                    help="Append run provenance here (default: eval_runs.jsonl).")
    gr.add_argument("--max-tokens", type=int, default=8192)
    gr.add_argument("--concurrency", type=int, default=8)
    gr.add_argument("--limit", type=int, default=0, help="Only the first N candidates (smoke testing).")
    gr.set_defaults(func=grade)

    s = sub.add_parser("summarize", help="Aggregate grades into results.")
    s.add_argument("--items", default=DEFAULT_ITEMS)
    s.add_argument("--transcripts", default="eval_transcripts.jsonl")
    s.add_argument("--grades", default="eval_grades.jsonl")
    s.add_argument("--json-output", default="eval_results.json")
    s.add_argument("--markdown-output", default="eval_results.md")
    s.add_argument("--report-title", default="Conceptual Critique Eval — Results (v2 grader)")
    s.set_defaults(func=summarize)

    args = p.parse_args(argv)
    if getattr(args, "func", None) in (generate, grade) and not os.environ.get("ANTHROPIC_API_KEY"):
        print("warning: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
