#!/usr/bin/env python3
"""Build a descriptive report from an art & design exploration run.

Reads the transcripts produced by `runner.py` on this experiment's item file
and emits a Markdown report: run provenance, per-model descriptive stats
(word counts, output tokens, stop reasons, refusals/errors), and a per-question
excerpt from every model so critiques can be compared side by side.

This is an *exploration* run: there is no grader and no gold labels, so the
report makes no scored claims. Any per-question note about what a strong
critique would catch is the author's `expect` annotation from the input file,
labelled as such — not a measurement. Recompute-only: no API calls.

Usage:
  python3 experiments/art_design/exploration/report.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from typing import Any

MODEL_ORDER = ["haiku", "sonnet", "opus", "fable"]
MODEL_LABEL = {
    "haiku": "Haiku 4.5",
    "sonnet": "Sonnet 4.6",
    "opus": "Opus 4.8",
    "fable": "Fable 5",
}


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dedup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per (experiment_id, question, model, sample), preferring ok
    over error so a later successful retry supersedes an earlier failure."""
    best: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        key = (
            r.get("experiment_id"),
            str(r.get("question_id")),
            r.get("model_alias"),
            r.get("sample_number"),
        )
        cur = best.get(key)
        if cur is None or (cur.get("error") is not None and r.get("error") is None):
            best[key] = r
    return list(best.values())


def text_of(row: dict[str, Any]) -> str:
    resp = row.get("response") or {}
    return "".join(
        b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text"
    )


def word_count(s: str) -> int:
    return len(s.split())


def excerpt(s: str, limit: int = 320) -> str:
    """First chunk of a critique for side-by-side reading, cut on a sentence
    boundary when possible and collapsed to a single line."""
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    dot = cut.rfind(". ")
    if dot >= limit * 0.5:
        return cut[: dot + 1] + " …"
    return cut.rstrip() + " …"


def out_tokens(row: dict[str, Any]) -> int | None:
    usage = (row.get("response") or {}).get("usage") or {}
    return usage.get("output_tokens")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcripts", default="experiments/art_design/exploration/transcripts.jsonl")
    ap.add_argument("--questions", default="experiments/art_design/exploration/items.jsonl")
    ap.add_argument("--out", default="experiments/art_design/exploration/report.md")
    args = ap.parse_args()

    questions = load_jsonl(args.questions)
    qmeta = {str(q["id"]): q for q in questions}
    raw = load_jsonl(args.transcripts)
    rows = dedup(raw)

    ok = [r for r in rows if r.get("error") is None]
    err = [r for r in rows if r.get("error") is not None]

    run_ids = sorted({r.get("run_id") for r in rows if r.get("run_id")})
    exp_ids = sorted({r.get("experiment_id") for r in ok if r.get("experiment_id")})

    # Per-model descriptive stats.
    per_model: dict[str, dict[str, Any]] = {}
    for alias in MODEL_ORDER:
        mok = [r for r in ok if r.get("model_alias") == alias]
        merr = [r for r in err if r.get("model_alias") == alias]
        if not mok and not merr:
            continue
        words = [word_count(text_of(r)) for r in mok]
        toks = [t for t in (out_tokens(r) for r in mok) if t is not None]
        stops = Counter((r.get("response") or {}).get("stop_reason") for r in mok)
        per_model[alias] = {
            "n_ok": len(mok),
            "n_err": len(merr),
            "mean_words": round(sum(words) / len(words), 1) if words else 0,
            "min_words": min(words) if words else 0,
            "max_words": max(words) if words else 0,
            "mean_tokens": round(sum(toks) / len(toks), 1) if toks else 0,
            "stops": stops,
        }

    # Per-question: model -> list of critique texts (by sample).
    by_q: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in ok:
        by_q[str(r["question_id"])][r["model_alias"]].append(text_of(r))

    lines: list[str] = []
    A = lines.append

    A("# Art & Design — conceptual-critique exploration run")
    A("")
    A(
        "A separate, exploratory set of six conceptual questions on art and design, "
        "each paired with a one-sided argument for the models to critique. It reuses "
        "the `runner.py` harness with item-specific templates stored in "
        "`experiments/art_design/exploration/items.jsonl`; unlike the graded eval, it "
        "does not use `prompts/candidates/critique_300w_v1.txt`. It is **not** part "
        "of the primary evaluation and has **no grader or gold labels** — this report is "
        "descriptive, not scored."
    )
    A("")
    A("## Setup")
    A("")
    A(f"- Questions: `{args.questions}` ({len(questions)} items, incl. Duchamp's *Fountain* and AI-generated art)")
    A(f"- Transcripts: `{args.transcripts}` — {len(ok)} successful, {len(err)} errored (of {len(rows)} deduped)")
    A(f"- Models: {', '.join(MODEL_LABEL[a] for a in MODEL_ORDER if a in per_model)}")
    A(f"- Run id(s): {', '.join(f'`{r}`' for r in run_ids) or '—'}")
    A(f"- Distinct experiment fingerprints: {len(exp_ids)} (prompt+system+config)")
    A("")

    A("## Per-model descriptive stats")
    A("")
    A("| Model | Critiques | Mean words | Min–max words | Mean output tokens | Stop reasons | Errors |")
    A("|---|---:|---:|---:|---:|:--|---:|")
    for alias in MODEL_ORDER:
        m = per_model.get(alias)
        if not m:
            continue
        stops = ", ".join(f"{k}×{v}" for k, v in m["stops"].items()) or "—"
        A(
            f"| {MODEL_LABEL[alias]} | {m['n_ok']} | {m['mean_words']} | "
            f"{m['min_words']}–{m['max_words']} | {m['mean_tokens']} | {stops} | {m['n_err']} |"
        )
    A("")
    A(
        "_No word limit is imposed in this run (unlike the main eval's 300-word instruction), "
        "so word counts describe natural critique length, not compliance._"
    )
    A("")

    A("## Questions and critiques")
    A("")
    for q in questions:
        qid = str(q["id"])
        meta = qmeta.get(qid, {})
        md = meta.get("metadata", {})
        A(f"### {qid}")
        A("")
        A(f"**Question.** {q['question']}")
        A("")
        arg = (q.get("args") or {}).get("argument", "")
        A(f"**Argument under critique** ({word_count(arg)} words). {excerpt(arg, 500)}")
        A("")
        if md.get("control"):
            A(
                "> **Control item.** The argument is deliberately careful and qualified; "
                "a strong critique should *decline to invent a fatal flaw*. Inventing one "
                "is an overreach."
            )
            A("")
        if md.get("expect"):
            A(f"> **Author's note (not a graded label):** a strong critique would catch — {md['expect']}")
            A("")
        for alias in MODEL_ORDER:
            texts = by_q.get(qid, {}).get(alias, [])
            if not texts:
                continue
            # Show the first sample's opening; note how many samples were collected.
            more = f" _(sample 1 of {len(texts)})_" if len(texts) > 1 else ""
            A(f"- **{MODEL_LABEL[alias]}**{more}: {excerpt(texts[0])}")
        A("")

    A("## How to reproduce")
    A("")
    A("```bash")
    A("export ANTHROPIC_API_KEY=sk-ant-...")
    A("python3 runner.py -i experiments/art_design/exploration/items.jsonl \\")
    A("  -o experiments/art_design/exploration/transcripts.jsonl -n 2 \\")
    A("  -m haiku sonnet opus fable -c 6 --max-tokens 4096 \\")
    A("  --manifest experiments/art_design/exploration/runs.jsonl")
    A("python3 experiments/art_design/exploration/report.py")
    A("```")
    A("")

    report = "\n".join(lines) + "\n"
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {args.out} ({len(report)} bytes); ok={len(ok)} err={len(err)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
