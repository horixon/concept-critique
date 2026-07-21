#!/usr/bin/env python3
"""Render one transcript row as a human-readable PDF for evaluation.

Look up a row by its response message id (the `msg_...` id the API assigns) and
lay out the request, response, and provenance so a person can read and grade it.

    from report import render_pdf
    render_pdf("msg_01AbC...", out="critique.pdf")

or from the shell:

    python report.py msg_01AbC... -o critique.pdf
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def load_rows(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def find_row(rows: list[dict[str, Any]], message_id: str) -> dict[str, Any] | None:
    """Find the row whose response message id matches (case-sensitive, exact)."""
    for row in rows:
        if (row.get("response") or {}).get("id") == message_id:
            return row
    return None


def load_run(runs_path: str, run_id: str | None) -> dict[str, Any]:
    """Return the manifest entry for a run_id (full provenance), or {} if unavailable."""
    if not run_id or not os.path.exists(runs_path):
        return {}
    for line in open(runs_path, "r", encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("run_id") == run_id:
            return entry
    return {}


def split_content(response: dict[str, Any]) -> tuple[str, str]:
    """Return (thinking_text, answer_text) concatenated from the response content blocks."""
    thinking, answer = [], []
    for block in response.get("content", []):
        if block.get("type") == "thinking":
            thinking.append(block.get("thinking", ""))
        elif block.get("type") == "text":
            answer.append(block.get("text", ""))
    return "".join(thinking), "".join(answer)


def _esc(text: str) -> str:
    """Escape for reportlab paragraph markup and preserve line breaks."""
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br/>")


def render_pdf(
    message_id: str,
    transcripts: str = "transcripts.jsonl",
    runs: str = "runs.jsonl",
    out: str | None = None,
) -> str:
    """Render the transcript row with the given response message id to a PDF.

    Returns the output path. Raises KeyError if no row matches message_id.
    """
    rows = load_rows(transcripts)
    row = find_row(rows, message_id)
    if row is None:
        available = [
            f"  {(r.get('response') or {}).get('id')}  ({r['model_alias']} q{r['question_id']} s{r['sample_number']})"
            for r in rows
            if (r.get("response") or {}).get("id")
        ]
        raise KeyError(
            f"no row with response id {message_id!r} in {transcripts}.\n"
            + ("Available:\n" + "\n".join(available) if available else "(no completed responses)")
        )

    out = out or (
        f"{row.get('run_id')}_q{row['question_id']}_{row['model_alias']}"
        f"_s{row['sample_number']}_{message_id}.pdf"
    )
    response = row.get("response") or {}
    run = load_run(runs, row.get("run_id"))
    usage = response.get("usage") or {}
    thinking, answer = split_content(response)

    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], spaceBefore=14, spaceAfter=4, textColor=colors.HexColor("#1a3c5e"))
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=16, spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, alignment=TA_LEFT, spaceAfter=6)
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=9.5, leading=13)
    kv = ParagraphStyle("kv", parent=styles["BodyText"], fontSize=9, leading=12, wordWrap="CJK")

    story: list[Any] = []
    story.append(Paragraph(f"{row['model_alias']} &middot; question {row['question_id']} &middot; sample {row['sample_number']}", title))
    story.append(Paragraph(f"{message_id}", ParagraphStyle("sub", parent=body, textColor=colors.grey, fontSize=9)))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c5e"), spaceBefore=4, spaceAfter=8))

    git = run.get("git") or {}
    git_str = (
        f"{git['commit'][:12]}{'-dirty' if git.get('dirty') else ''} ({git.get('branch')})"
        if git else "none"
    )
    meta_rows = [
        ("model_id", row.get("model_id")),
        ("run_id", row.get("run_id")),
        ("timestamp", row.get("timestamp")),
        ("stop_reason", response.get("stop_reason")),
        ("tokens", f"in={usage.get('input_tokens')}  out={usage.get('output_tokens')}  "
                   f"cache_read={usage.get('cache_read_input_tokens')}  cache_write={usage.get('cache_creation_input_tokens')}"),
        ("input_sha256", run.get("input_sha256")),
        ("runner_sha256", run.get("runner_sha256")),
        ("git", git_str),
    ]
    table = Table(
        [[Paragraph(f"<b>{k}</b>", kv), Paragraph(_esc(str(v)), kv)] for k, v in meta_rows],
        colWidths=[1.3 * inch, 5.4 * inch],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)

    if row.get("system"):
        story.append(Paragraph("System", h))
        story.append(Paragraph(_esc(row["system"]), body))

    story.append(Paragraph("Prompt", h))
    story.append(Paragraph(_esc(row.get("prompt", "")), mono))

    if thinking.strip():
        story.append(Paragraph("Thinking (summary)", h))
        story.append(Paragraph(_esc(thinking), body))

    if "error" in row:
        err = row["error"]
        story.append(Paragraph("Error", ParagraphStyle("err", parent=h, textColor=colors.HexColor("#a11"))))
        story.append(Paragraph(_esc(f"{err.get('type')}: {err.get('message')}"), body))
        if err.get("traceback"):
            story.append(Paragraph(_esc(err["traceback"]), mono))
    else:
        story.append(Paragraph("Response", h))
        story.append(Paragraph(_esc(answer) if answer.strip() else "<i>(empty response)</i>", body))

    doc = SimpleDocTemplate(
        out, pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title=f"{row['model_alias']} q{row['question_id']} s{row['sample_number']}",
    )
    doc.build(story)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("message_id", help="Response message id (msg_...) of the row to render.")
    p.add_argument("-t", "--transcripts", default="transcripts.jsonl", help="Transcripts JSONL. Default transcripts.jsonl.")
    p.add_argument("-r", "--runs", default="runs.jsonl", help="Run manifest JSONL. Default runs.jsonl.")
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output PDF path. Default <run_id>_q<qid>_<model>_s<n>_<message_id>.pdf.",
    )
    args = p.parse_args(argv)
    try:
        out = render_pdf(args.message_id, args.transcripts, args.runs, args.output)
    except KeyError as exc:
        raise SystemExit(exc.args[0]) from exc
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
