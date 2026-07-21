#!/usr/bin/env python3
"""Render cropped figure images from critique PDFs for the research report.

For each spec entry we locate `search_text` (the start of the region, usually a
heading) and `capture_text` (a phrase that ends the region), then crop the page
from just above the search text to just below the capture text and render it to
a PNG.  Handles regions that span two pages by stacking the crops vertically.
"""
import json
import os
import re
import sys

import fitz  # PyMuPDF
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE, "pdfs")
OUT_DIR = os.path.join(BASE, "figures")
SPEC = os.path.join(BASE, "figures_spec.jsonl")

ZOOM = 2.5            # render scale (150 -> ~375 dpi feel); crisp for reports
MARGIN_TOP = 14       # pts of context above the heading
MARGIN_BOTTOM = 12    # pts of context below the capture line
SIDE_PAD = 4          # trim page side margins lightly


def resolve_pdf(spec_path):
    """Map the JSON /mnt/data/...(1).pdf reference to the local pdfs/ file."""
    name = os.path.basename(spec_path)
    name = name.replace("(1)", "")
    local = os.path.join(PDF_DIR, name)
    if os.path.exists(local):
        return local
    # fallback: strip a trailing (n) before extension, then fuzzy match by stem
    stem = os.path.splitext(name)[0]
    for f in os.listdir(PDF_DIR):
        if f.startswith(stem):
            return os.path.join(PDF_DIR, f)
    return None


_TOK = re.compile(r"[a-z0-9%]+")


def _tokens(text):
    """Split text into lowercase alphanumeric(+%) tokens."""
    return _TOK.findall(text.lower())


def find_text(page, needle):
    """Locate a phrase by alphanumeric tokens, tolerant of quotes, punctuation,
    em-dashes and line wrapping. Returns the union bounding rect of the run.

    A single word like ``accuracy—both`` yields two tokens that both map back to
    the same word rect, so a phrase may start or end mid-word."""
    toks, rects = [], []
    for w in page.get_text("words"):  # (x0,y0,x1,y1, text, block,line,word)
        r = fitz.Rect(w[:4])
        for tk in _tokens(w[4]):
            toks.append(tk)
            rects.append(r)
    target = _tokens(needle)
    if not target:
        return None
    n = len(target)
    for i in range(len(toks) - n + 1):
        if toks[i:i + n] == target:
            r = fitz.Rect(rects[i])
            for m in range(i + 1, i + n):
                r = r | rects[m]
            return r
    return None


def find_text_any_page(doc, needle, start_page=0):
    for pno in range(start_page, len(doc)):
        r = find_text(doc[pno], needle)
        if r:
            return pno, r
    return None, None


def render_clip(page, clip):
    mat = fitz.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def stack_vertical(images, bg=(255, 255, 255)):
    w = max(im.width for im in images)
    h = sum(im.height for im in images)
    out = Image.new("RGB", (w, h), bg)
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height
    return out


def process(spec):
    pdf = resolve_pdf(spec["pdf_path"])
    if not pdf:
        return False, f"PDF not found for {spec['pdf_path']}"
    doc = fitz.open(pdf)

    s_page, s_rect = find_text_any_page(doc, spec["search_text"])
    if s_rect is None:
        doc.close()
        return False, f"search_text not found: {spec['search_text']!r}"

    c_page, c_rect = find_text_any_page(doc, spec["capture_text"])
    if c_rect is None:
        doc.close()
        return False, f"capture_text not found: {spec['capture_text']!r}"

    # Order the two anchors by reading order (page, then vertical position) so
    # the region spans whichever comes first to whichever comes last.
    top_page, top_rect, bot_page, bot_rect = s_page, s_rect, c_page, c_rect
    if (c_page, c_rect.y0) < (s_page, s_rect.y0):
        top_page, top_rect, bot_page, bot_rect = c_page, c_rect, s_page, s_rect

    images = []
    if top_page == bot_page:
        page = doc[top_page]
        pw = page.rect.width
        clip = fitz.Rect(
            SIDE_PAD,
            max(0, top_rect.y0 - MARGIN_TOP),
            pw - SIDE_PAD,
            min(page.rect.height, bot_rect.y1 + MARGIN_BOTTOM),
        )
        images.append(render_clip(page, clip))
    else:
        # first page: from top anchor to its bottom
        first = doc[top_page]
        images.append(render_clip(first, fitz.Rect(
            SIDE_PAD, max(0, top_rect.y0 - MARGIN_TOP),
            first.rect.width - SIDE_PAD, first.rect.height)))
        # any full middle pages
        for pno in range(top_page + 1, bot_page):
            mid = doc[pno]
            images.append(render_clip(mid, fitz.Rect(
                SIDE_PAD, 0, mid.rect.width - SIDE_PAD, mid.rect.height)))
        # last page: top down to bottom anchor
        last = doc[bot_page]
        images.append(render_clip(last, fitz.Rect(
            SIDE_PAD, 0,
            last.rect.width - SIDE_PAD, min(last.rect.height, bot_rect.y1 + MARGIN_BOTTOM))))

    out_img = images[0] if len(images) == 1 else stack_vertical(images)
    out_path = os.path.join(OUT_DIR, spec["output_filename"])
    out_img.save(out_path, "PNG")
    doc.close()
    span = f"p{top_page+1}" if top_page == bot_page else f"p{top_page+1}-{bot_page+1}"
    return True, f"{spec['output_filename']}  ({out_img.width}x{out_img.height}, {span})"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    specs = [json.loads(l) for l in open(SPEC) if l.strip()]
    ok = 0
    for spec in specs:
        good, msg = process(spec)
        flag = "OK " if good else "ERR"
        print(f"[{flag}] id={spec['id']:>2}  {msg}")
        ok += good
    print(f"\n{ok}/{len(specs)} figures rendered -> {OUT_DIR}")
    return 0 if ok == len(specs) else 1


if __name__ == "__main__":
    sys.exit(main())
