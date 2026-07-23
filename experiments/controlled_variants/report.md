# Controlled variants — final report

> Separate follow-on experiment. **Not** part of the primary 11-item evaluation or
> its reported model scores, and never pooled with them. One three-argument family:
> findings are a case study, not a population estimate.

## Design and completed cells

One conceptual question is held fixed while only the argument changes:

- **1000 — flawed** (`reject_or_rewrite`): asserts historical fidelity, then counts a
  coherent post-hoc justification as preservation. Target flaw:
  `actual_reasoning_vs_reconstructed_justification`.
- **1001 — repaired** (`qualify_no_fatal_flaw`): the contradiction removed; a bounded,
  purpose-relative standard.
- **1002 — operational-decoy control** (`qualify_no_fatal_flaw`): deliberately omits
  procedure/thresholds to tempt an implementation-demand attack.

Candidate prompt: `prompts/candidates/critique_300w_v1.txt`. Grader: fixed v2 Opus.
Classifiers: Fable + Sonnet, model-blinded, consensus-only.

| Stage | Attempted | Succeeded | Failed |
|---|---:|---:|---:|
| Candidate generation (3 variants × 4 models × 3 samples) | 36 | **36** | 0 |
| v2 Opus grading | 36 | **36** | 0 |
| Synthetic classification (36 × 2 classifiers) | 72 | **72** | 0 |

**Synthetic classifier agreement: 14/36 responses reached exact five-field consensus
(39%); 22 excluded, all `code_disagreement`; 0 low-confidence, 0 missing.** Exact
agreement on `primary_label`, `severity`, and all three boolean flags is required, so
missing consensus is reported, never forced. All labels below are **synthetic
references**, not human ground truth.

## Primary findings (contrastive behavior)

**1. Flaw identification on 1000.** When the two classifiers agreed on a 1000 critique,
they agreed it targeted the intended contradiction: **4/4 consensus codes on 1000 are
`actual_reasoning_vs_reconstructed_justification`** (fable s2, haiku s2, opus s0, opus s2).
No competing label reached consensus on 1000.

**2. Retirement of the objection after repair.** On the repaired argument 1001, **0/7
consensus codes are the target flaw**; they shift entirely to bounded objections —
`purpose_relative_standard` ×4 (opus s0; sonnet s0/s1/s2) and `coherence_not_truth` ×3
(fable s0/s1/s2). Among responses with consensus on **both** members of the 1000→1001
pair (same model+sample), **2/2 retired** the contradiction and did not repeat it:
opus s0 (`actual_reasoning…` → `purpose_relative_standard`) and fable s2
(`actual_reasoning…` → `coherence_not_truth`). n=2 is tiny; see the caveat below.

**3. Severity adjustment (grader disposition, all 36 grades, no exclusions).** `defeats`
appears on 1000 (haiku 2/3, sonnet 2/3, opus 0/3, fable 3/3 → **7/12**) and drops to
**0/12 on 1001 and 0/12 on 1002** — every non-1000 critique is `narrows` or softer.
Consensus severities agree: every 1001/1002 consensus row is `narrows`, never `defeats`.

**4. Operational restraint on 1002.** **0/12 grader `mere_operationalization` penalties**
and **0/14 classifier `operational_substitution` flags** — no model attacked the control
by demanding templates/thresholds/workflows. The decoy did not fire here.

**5. Critique differentiation.** The consensus label set differs across variants
(1000: contradiction; 1001: purpose-relative / coherence-not-truth; 1002:
evidence-underdetermines + a residual contradiction read), i.e. models did not paste one
objection onto all three arguments.

**Empty matched-triple table.** `analyze.py`'s matched table requires consensus on all
**three** variants at the same model+sample; **0 such triples exist** (strict consensus is
sparse), so that table is blank by design. The pair-level retirement in finding 2 is the
strongest matched signal available; the rest of the primary evidence is the
aggregate consensus-label shift and the grader dispositions, reported without pretending
the triple analysis succeeded.

## Secondary automatic v2 scores (diagnostic only)

Critique-quality scores, **not** argument-quality; a negative repair delta does **not**
mean the repaired argument is worse — critiquing a robust argument well earns fewer of
the flaw-identification points available on 1000. Verified against `grades.jsonl`.

| Model | 1000 | 1001 | 1002 | Repair Δ (1001−1000) | Control Δ (1002−1000) |
|---|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0.883 | 0.312 | 0.629 | −0.571 | −0.254 |
| Sonnet 4.6 | 0.979 | 0.529 | 0.608 | −0.450 | −0.371 |
| Opus 4.8 | 1.000 | 0.662 | 0.896 | −0.338 | −0.104 |
| Fable 5 | 1.000 | 0.612 | 0.862 | −0.388 | −0.138 |

All four deltas are negative for every model; direction is not interpreted as repair
success (per `DESIGN.md`). Model ranking is intentionally not the headline.

## Sharp examples (model identity revealed only after classification)

**Success — matched retirement (Opus 4.8, sample 0).** On 1000 the critique names the
target contradiction directly: *"the argument's two criteria contradict each other, and
the conclusion silently abandons the stronger one … a justificatory standard … [vs] a
fidelity [standard]."* On 1001 it does **not** repeat that objection; it raises a bounded
point — *"conflates preserving reasoning with enabling a defensible reconstruction"* —
which both classifiers coded `purpose_relative_standard` / `narrows`. Objection retired
after repair, severity softened.

**Disagreement — classifier split (candidate Haiku 4.5 on 1000, sample 0).** Fable coded
it `actual_reasoning_vs_reconstructed_justification` / `defeats` / high-confidence; Sonnet
coded it `coherence_not_truth` / `narrows` / medium-confidence. Same critique, different
blind reads → excluded from consensus rather than forced. This is one of the 22 excluded
responses and illustrates why classifier agreement is only 39%.

## Limitations

- **One argument family; three variants.** No population-level confidence interval. The
  36 responses reduce within-family generation noise; they do not sample conceptual
  domains broadly.
- **Synthetic response codes**, produced by Fable + Sonnet — not human judgments.
  Fable/Sonnet also generate candidates, so a classifier may recognize its own family's
  style; consensus reduces but does not remove this.
- **Strict consensus is sparse** (14/36); primary behavioral counts rest on small n
  (e.g., 2 matched retirement pairs) and are reported with raw denominators throughout.
- **One fixed Opus grader** that sees the human/annotation framing and may reward overlap.
- **Sample numbers are a deterministic matching convention only** — sample 0 in one call
  is not statistically paired with sample 0 in another.
- Do not pool any of these rows or scores with the primary 11-item evaluation.
