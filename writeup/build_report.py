#!/usr/bin/env python3
"""Assemble figures into a report document, placing each under its
`document_section` with the `insert_after_text` lead-in and a `caption`."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(BASE, "figures_spec.jsonl")
OUT = os.path.join(BASE, "figures_report.md")

specs = [json.loads(l) for l in open(SPEC) if l.strip()]

# preserve first-appearance order of sections, and spec order within each
sections = {}
for s in specs:
    sections.setdefault(s["document_section"], []).append(s)

lines = [
    "# Conceptual Critique Eval — Figure Placement",
    "",
    "Screenshots of model critiques, grouped by report section. Each figure is "
    "preceded by the sentence it should follow in the draft and annotated with "
    "its caption. Regenerate images with `python3 make_figures.py`.",
    "",
]

fig_no = 0
for section, items in sections.items():
    lines += [f"## {section}", ""]
    for s in items:
        fig_no += 1
        rel = os.path.join("figures", s["output_filename"])
        lines += [
            f"> Insert after: “{s['insert_after_text']}”",
            "",
            f"![{s['caption']}]({rel})",
            "",
            f"***Figure {fig_no}.*** {s['caption']} "
            f"*({s['model'].capitalize()}, {s['experiment'].upper()}, sample {s['sample']}.)*",
            "",
        ]

open(OUT, "w").write("\n".join(lines))
print(f"Wrote {OUT}  ({fig_no} figures across {len(sections)} sections)")
for section, items in sections.items():
    print(f"  {section}: {len(items)}")
