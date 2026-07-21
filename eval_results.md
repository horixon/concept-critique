# Conceptual Critique Eval — Results (v2 grader)

Grader model: **opus**  |  items: 11  |  grades: 132  |  generation failures: 0  |  grading failures: 0

## 1. Model scores

Model score = mean over items of the per-item sample mean; 95% CI is an **item (cluster) bootstrap** — resampling arguments, not individual responses. Scores are recomputed in code (with annotation caps); the grader never returns item_score.

| model | items covered | successful gens | item mean | 95% item-CI |
|---|---|---|---|---|
| haiku | 11/11 | 33 | 0.583 | [0.478, 0.697] |
| sonnet | 11/11 | 33 | 0.716 | [0.614, 0.816] |
| opus | 11/11 | 33 | 0.816 | [0.738, 0.897] |
| fable | 11/11 | 33 | 0.829 | [0.750, 0.908] |

## 2. Dimension means

| model | centrality | argument_fidelity | novelty | justified_impact |
|---|---|---|---|---|
| haiku | 0.55 | 0.69 | 0.65 | 0.67 |
| sonnet | 0.67 | 0.83 | 0.76 | 0.77 |
| opus | 0.77 | 0.87 | 0.86 | 0.83 |
| fable | 0.78 | 0.90 | 0.86 | 0.84 |

## 3. Penalty rates (fraction of grades where the penalty applied)

| model | laundry_list | overclaim | mere_operationalization | retreat_as_repair | unsupported_claim |
|---|---|---|---|---|---|
| haiku | 0.12 | 0.12 | 0.03 | 0.03 | 0.00 |
| sonnet | 0.09 | 0.06 | 0.03 | 0.00 | 0.00 |
| opus | 0.03 | 0.03 | 0.00 | 0.00 | 0.00 |
| fable | 0.00 | 0.09 | 0.00 | 0.00 | 0.00 |

## 4. Robust-control vs flaw-item performance

Robust-control item ids (`qualify_no_fatal_flaw`): [1, 2, 3, 5, 8, 9]  
Flaw item ids: [0, 4, 6, 7, 10]

| model | robust-control mean | flaw mean |
|---|---|---|
| haiku | 0.520 | 0.658 |
| sonnet | 0.656 | 0.787 |
| opus | 0.797 | 0.838 |
| fable | 0.811 | 0.850 |

A model that scores well on flaw items but poorly on robust controls is over-attacking; compare the two columns rather than reading the overall mean alone.

## 5. Equal-weight sensitivity

| model | main-weight mean | equal-weight mean |
|---|---|---|
| haiku | 0.583 | 0.589 |
| sonnet | 0.716 | 0.720 |
| opus | 0.816 | 0.822 |
| fable | 0.829 | 0.836 |

Main-weight ordering: fable > opus > sonnet > haiku  
Equal-weight ordering: fable > opus > sonnet > haiku  
Ordering changes under equal weights: **False**

## 6. Response length & word-limit compliance

Pearson correlation between response word count and recomputed item score: **0.102**  
A large positive correlation would be a verbosity-confound warning; the 300-word cap keeps this small.

The 300-word cap is **recorded, not enforced** — responses are never truncated (truncation cuts reasoning mid-sentence and adds an artifact). Violation rate by model:

| model | violation rate | violations / n | mean words | max words |
|---|---:|---:|---:|---:|
| haiku | 0.48 | 16/33 | 303 | 329 |
| sonnet | 0.12 | 4/33 | 293 | 312 |
| opus | 0.85 | 28/33 | 305 | 320 |
| fable | 0.76 | 25/33 | 304 | 325 |

The grader is instructed not to reward length, and the near-zero length–score correlation (0.102) supports that: the models that overshoot the cap most do not gain score from it, so the (small, ~10% max) cap violations are not confounding the results.

## 7. Failures / invalid grader outputs

- generation failures: 0
- grading failures (invalid after retry): 0

## Score by item

| eval_id | robust-control | case_type | n | mean |
|---|---|---|---|---|
| 0 | no | deliberate_internal_contradiction | 12 | 0.986 |
| 1 | yes | underspecified_but_coherent_control | 12 | 0.562 |
| 2 | yes | implementation_demand_trap | 12 | 0.734 |
| 3 | yes | strong_qualified_argument | 12 | 0.676 |
| 4 | no | subtle_construct_equivocation | 12 | 0.586 |
| 5 | yes | strong_qualified_argument | 12 | 0.707 |
| 6 | no | strong_argument_with_epistemic_limit | 12 | 0.928 |
| 7 | no | subtle_decision_theory_gap | 12 | 0.626 |
| 8 | yes | strong_qualified_argument | 12 | 0.710 |
| 9 | yes | strong_qualified_argument | 12 | 0.785 |
| 10 | no | internal_accounting_tension | 12 | 0.789 |

## Score by sample
| sample | n | mean |
|---|---|---|
| 0 | 44 | 0.725 |
| 1 | 44 | 0.735 |
| 2 | 44 | 0.747 |

## Expected capability ordering

Opus > Sonnet > Haiku holds: **True**  
Fable is reported without assuming a rank. Monotonic ordering alone does not establish validity — read it with the robust-control split, the item-bootstrap intervals, and the length correlation.

## 8. Manually useful examples

### Highest-scoring critique
- eval_id **0**, model **haiku**, sample 0, score **1.0**
- dims: {'centrality': 1.0, 'argument_fidelity': 1.0, 'novelty': 1.0, 'justified_impact': 1.0} | penalties: none
- rationale: The candidate identifies the exact central contradiction: the final paragraph abandons the historical-fidelity criterion by accepting coherent justifications disconnected from actual reasoning. It explains why the contemporaneous-records concession is insufficient (artifacts underdetermine the actual reasoning process), addressing the concession directly. It distinguishes 'could be justified' from 'actually preserved,' states the argument must choose, and shows the impact defeats the core claim. All minimum full-credit elements met without inventing flaws or overclaiming.

> # Critique: The Coherence Standard Undermines Historical Fidelity
> 
> The argument contains a fundamental tension between its two key commitments that ultimately collapses into incoherence.
> 
> The argument requires that reconstructions be "historically faithful"—reflecting reasoning that *actually* shaped the decision. It rightly warns against "cleaner justification created afterward." Yet it then permits a reconstructed rationale that is "evidence-grounded" and "coherent" even when the actual decision-makers operated on unstated political, personal, or accidental grounds.
> 
> This creates a problem: **coherence and historical accuracy can diverge sharply**. A later team might construct a rationally defensible account from scattered evidence—one that is internally consistent and references genuine constraints—while fundamentally misrepresenting *how* the original deliberators actually reasoned. The coherence standard cannot detect this divergence because it only checks whether a story *could have* justified the decision, not whether it *did*.
> 
> Consider an example: a decision made primarily through office politics might leave traces (budget documents, meeting notes about constraints) that support a coherence-based reconstruction emphasizing rational resource allocation. This reconstruction could be evidence-grounded and coherent while being historically false about the actual reasoning.
> 
> The argument tries to guard against this by requiring use of "contemporaneous records, rejected alternatives, and disagreement records." But this is insufficient. These artifacts can be consistent with multiple, mutually incompatible reasoning processes. The coherence standard still does the justificatory work—and it permits fabrication.
> 
> **The weakness is conceptual, not merely practical.** The argument conflates two different things: (1) whether a decision *could be justified* given available evidence, and (2) whether an organization *has actually preserved* the thinking that produced it. These are not the same. An organization that loses all records of its deliberation has lost its reasoning, even if a historian could later invent a coherent justification.
> 
> This **defeats the core claim**. The argument should acknowledge that preservation requires some reliable link to actual deliberation—not merely the possibility of retrospective reconstruction.

### Polished but low-novelty (novelty<=0.25, otherwise solid)
_no matching example found_

### Operational-substitution failure (mere_operationalization penalty)
- eval_id **2**, model **haiku**, sample 1, score **0.212**
- dims: {'centrality': 0.25, 'argument_fidelity': 0.5, 'novelty': 0.5, 'justified_impact': 0.5} | penalties: {'overclaim': 0.1, 'mere_operationalization': 0.1}
- rationale: This is a robust control where the argument explicitly disclaims procedural specification. The candidate frames non-specification as a fatal circularity/vacuity flaw, essentially demanding the very implementation thresholds ('what counts as contemporaneous,' 'how explicit') the argument concedes are out of scope. It fails the full-credit requirement of recognizing no fatal flaw. The best available angle—epistemic sufficiency of contemporaneous evidence (performativity, contested fact/inference separation)—is gestured at but not developed. Inventing vacuity on a control caps centrality at 0.25. Overclaim and operationalization-demand penalties apply.

> # Critique: The Circularity Problem
> 
> The argument's core weakness is circularity in defining "preservation." It claims organizations preserve reasoning by retaining evidence that enables later reconstruction, then measures preservation success by whether reconstructions are credible. But this makes preservation parasitic on reconstruction quality—a quality the argument explicitly declines to specify.
> 
> This matters because the argument faces a fundamental dilemma:
> 
> **If reconstruction quality is measurable**, the argument should define it. Instead, it defers all substantive standards to "implementation choices," which means organizations could satisfy the proposed standard while producing radically different reconstruction outcomes. One organization's "grounded in contemporaneous evidence" might mean careful cross-referencing; another's might mean a single memo with minimal interpretation. Both would satisfy the epistemic standard as stated.
> 
> **If reconstruction quality is unmeasurable or context-dependent**, then the standard becomes vacuous. "Preserve evidence and be explicit about uncertainty" applies equally to rigorous archives and to haphazard record-keeping with disclaimers attached. The standard cannot distinguish genuinely preserved reasoning from its appearance.
> 
> The argument tries to escape this by claiming implementation details don't matter—only grounding in contemporaneous evidence and explicit uncertainty do. But this distinction collapses under scrutiny. What counts as "contemporaneous"? How explicit must uncertainty be? These aren't mere implementation details; they're what determine whether a reconstruction actually preserves reasoning or merely simulates it.
> 
> **Effect on the conclusion**: This weakness doesn't entirely defeat the argument's intuition—that better documentation probably helps reconstruct decisions. But it narrows it significantly. The argument cannot actually tell us what counts as preserving reasoning without either specifying reconstruction standards (contradicting its claims) or accepting that "preservation" is organization-relative and potentially not meaningful as a general concept.
> 
> The argument is strongest as a procedural recommendation, not as a conceptual analysis of preservation itself.

### Invented a flaw on a robust-control item
- eval_id **2**, model **haiku**, sample 1, score **0.212**
- dims: {'centrality': 0.25, 'argument_fidelity': 0.5, 'novelty': 0.5, 'justified_impact': 0.5} | penalties: {'overclaim': 0.1, 'mere_operationalization': 0.1}
- rationale: This is a robust control where the argument explicitly disclaims procedural specification. The candidate frames non-specification as a fatal circularity/vacuity flaw, essentially demanding the very implementation thresholds ('what counts as contemporaneous,' 'how explicit') the argument concedes are out of scope. It fails the full-credit requirement of recognizing no fatal flaw. The best available angle—epistemic sufficiency of contemporaneous evidence (performativity, contested fact/inference separation)—is gestured at but not developed. Inventing vacuity on a control caps centrality at 0.25. Overclaim and operationalization-demand penalties apply.

> # Critique: The Circularity Problem
> 
> The argument's core weakness is circularity in defining "preservation." It claims organizations preserve reasoning by retaining evidence that enables later reconstruction, then measures preservation success by whether reconstructions are credible. But this makes preservation parasitic on reconstruction quality—a quality the argument explicitly declines to specify.
> 
> This matters because the argument faces a fundamental dilemma:
> 
> **If reconstruction quality is measurable**, the argument should define it. Instead, it defers all substantive standards to "implementation choices," which means organizations could satisfy the proposed standard while producing radically different reconstruction outcomes. One organization's "grounded in contemporaneous evidence" might mean careful cross-referencing; another's might mean a single memo with minimal interpretation. Both would satisfy the epistemic standard as stated.
> 
> **If reconstruction quality is unmeasurable or context-dependent**, then the standard becomes vacuous. "Preserve evidence and be explicit about uncertainty" applies equally to rigorous archives and to haphazard record-keeping with disclaimers attached. The standard cannot distinguish genuinely preserved reasoning from its appearance.
> 
> The argument tries to escape this by claiming implementation details don't matter—only grounding in contemporaneous evidence and explicit uncertainty do. But this distinction collapses under scrutiny. What counts as "contemporaneous"? How explicit must uncertainty be? These aren't mere implementation details; they're what determine whether a reconstruction actually preserves reasoning or merely simulates it.
> 
> **Effect on the conclusion**: This weakness doesn't entirely defeat the argument's intuition—that better documentation probably helps reconstruct decisions. But it narrows it significantly. The argument cannot actually tell us what counts as preserving reasoning without either specifying reconstruction standards (contradicting its claims) or accepting that "preservation" is organization-relative and potentially not meaningful as a general concept.
> 
> The argument is strongest as a procedural recommendation, not as a conceptual analysis of preservation itself.

### Annotation cap applied by the harness
- eval_id **1**, model **haiku**, sample 2, score **0.263**, caps ['novelty_if_acknowledged_only']
- dims: {'centrality': 0.25, 'argument_fidelity': 0.5, 'novelty': 0.5, 'justified_impact': 0.75} | penalties: {'overclaim': 0.1}
- rationale: This is a robust control with no fatal flaw; the candidate leads with circularity/vacuity, a tempting-but-weak move the annotation flags. The purpose-relativity it attacks is an explicit concession, not a hidden defect, so it fails to recognize no fatal flaw exists (centrality capped low). It does add a mechanism—the property-vs-relation conflation and same-record/different-purpose consequence—earning partial novelty and decent impact. Overclaim penalty for framing intentional context-dependence as a definitional vacuum that 'mislocates what preservation is.'

> # Critique: The Circularity Problem
> 
> The argument's central weakness is circularity: it defines preservation in terms of "sufficiently reliable reconstruction," but "sufficiently" is left entirely to contextual factors that the argument itself identifies as variable and context-dependent. This creates a definitional vacuum rather than a genuine criterion.
> 
> The argument acknowledges this by pivoting to pragmatism: preservation becomes whatever serves the stated purpose. But this conflates two distinct questions:
> 1. What constitutes preserving reasoning? (conceptual)
> 2. What level of reconstruction suffices for a given use? (practical)
> 
> By absorbing the second into the first, the argument loses analytical grip on preservation itself. Under this logic, an organization could preserve "its reasoning" differently for different audiences with identical documentary records—the same surviving evidence would simultaneously constitute preservation for legal audits but not for routine reviews. This makes "preservation" a predicate on the *user's needs* rather than on the *record's properties*, which fundamentally mislocates what preservation is.
> 
> **Effect on the conclusion:** This narrows the argument substantially. The conclusion stops being a conceptual account of preservation and becomes instead a practical guide for calibrating recovery efforts. That's useful advice, but it doesn't answer the original question about what preservation *is*.
> 
> **What's missing:** A prior account of what makes reasoning genuinely *preserved* (as opposed to merely *recoverable-to-degree-X-for-purpose-Y*). The argument needs to specify whether preservation requires: capturing the *actual* deliberation, meeting a *minimum* evidentiary standard regardless of use, or achieving some *threshold of fidelity* to the decision-making process itself.
> 
> The argument's flexibility is marketed as realism but actually obscures the conceptual distinction between preservation (a property of records) and sufficiency (a relationship between records and purposes). Collapsing these leaves us unable to ask whether an organization has truly preserved reasoning or merely left behind recoverable traces.

