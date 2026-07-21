# writeup/ — report + figure tooling (not part of the eval)

Helpers used to build the write-up PDF and its figures. **Not required to run or
extend the evaluation** — the eval's own figure is `eval_model_scores.png` from
`analysis.py`.

- `make_figures.py` — crops regions from a rendered PDF into `figures/*.png` (needs `PyMuPDF` + `Pillow`, and the source PDF, which is not committed).
- `build_report.py` — assembles report text.
- `figures/` — the cropped critique figures.
- `figures_report.md` — figure captions / notes.
- `rephrase_prompt.md` — the working note for how question id 1 was rephrased from id 0.
