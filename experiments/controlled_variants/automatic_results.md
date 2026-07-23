# Controlled Variant Experiment — Automatic v2 Results

Grader model: **opus**  |  items: 3  |  grades: 36  |  generation failures: 0  |  grading failures: 0

## 1. Model scores

Model score = mean over items of the per-item sample mean; 95% CI is an **item (cluster) bootstrap** — resampling arguments, not individual responses. Scores are recomputed in code (with annotation caps); the grader never returns item_score.

| model | items covered | successful gens | item mean | 95% item-CI |
|---|---|---|---|---|
| haiku | 3/3 | 9 | 0.608 | [0.312, 0.883] |
| sonnet | 3/3 | 9 | 0.706 | [0.529, 0.979] |
| opus | 3/3 | 9 | 0.853 | [0.662, 1.000] |
| fable | 3/3 | 9 | 0.825 | [0.612, 1.000] |

## 2. Dimension means

| model | centrality | argument_fidelity | novelty | justified_impact |
|---|---|---|---|---|
| haiku | 0.56 | 0.72 | 0.64 | 0.69 |
| sonnet | 0.64 | 0.75 | 0.72 | 0.81 |
| opus | 0.75 | 0.92 | 0.92 | 0.89 |
| fable | 0.75 | 0.92 | 0.89 | 0.83 |

## 3. Penalty rates (fraction of grades where the penalty applied)

| model | laundry_list | overclaim | mere_operationalization | retreat_as_repair | unsupported_claim |
|---|---|---|---|---|---|
| haiku | 0.00 | 0.11 | 0.00 | 0.11 | 0.00 |
| sonnet | 0.00 | 0.11 | 0.00 | 0.00 | 0.00 |
| opus | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| fable | 0.00 | 0.11 | 0.00 | 0.00 | 0.00 |

## 4. Robust-control vs flaw-item performance

Robust-control item ids (`qualify_no_fatal_flaw`): [1, 2]
Flaw item ids: [0]

| model | robust-control mean | flaw mean |
|---|---|---|
| haiku | 0.471 | 0.883 |
| sonnet | 0.569 | 0.979 |
| opus | 0.779 | 1.000 |
| fable | 0.737 | 1.000 |

A model that scores well on flaw items but poorly on robust controls is over-attacking; compare the two columns rather than reading the overall mean alone.

## 5. Equal-weight sensitivity

| model | main-weight mean | equal-weight mean |
|---|---|---|
| haiku | 0.608 | 0.617 |
| sonnet | 0.706 | 0.718 |
| opus | 0.853 | 0.868 |
| fable | 0.825 | 0.836 |

Main-weight ordering: opus > fable > sonnet > haiku
Equal-weight ordering: opus > fable > sonnet > haiku
Ordering changes under equal weights: **False**

## 6. Response length & word-limit compliance

Pearson correlation between response word count and recomputed item score: **0.255**
A large positive correlation would be a verbosity-confound warning; the observed correlation is descriptive, not proof of style invariance.

The 300-word instruction is **recorded, not enforced** — responses are never truncated (truncation cuts reasoning mid-sentence and adds an artifact). Violation rate by model:

| model | violation rate | violations / n | mean words | max words |
|---|---:|---:|---:|---:|
| haiku | 0.33 | 3/9 | 295 | 307 |
| sonnet | 0.00 | 0/9 | 291 | 298 |
| opus | 0.78 | 7/9 | 304 | 309 |
| fable | 0.44 | 4/9 | 300 | 310 |

The grader is instructed not to reward length. The modest length–score correlation (0.255) provides little evidence that verbosity alone drove scores in this sample, but it does not rule out nonlinear or stylistic effects. Overruns were frequent for some models but modest in magnitude (the maximum response was roughly 10% over the request).

## 7. Failures / invalid grader outputs

- generation failures: 0
- grading failures (invalid after retry): 0

## Score by item

| eval_id | robust-control | case_type | n | mean |
|---|---|---|---|---|
| 0 | no | deliberate_internal_contradiction | 12 | 0.966 |
| 1 | yes | underspecified_but_coherent_control | 12 | 0.529 |
| 2 | yes | implementation_demand_trap | 12 | 0.749 |

## Score by sample
| sample | n | mean |
|---|---|---|
| 0 | 12 | 0.754 |
| 1 | 12 | 0.778 |
| 2 | 12 | 0.711 |

## Expected capability ordering

Opus > Sonnet > Haiku holds: **True**
Fable is reported without assuming a rank. Monotonic ordering alone does not establish validity — read it with the robust-control split, the item-bootstrap intervals, and the length correlation.

## 8. Manually useful examples

### Highest-scoring critique
- eval_id **0**, model **sonnet**, sample 2, score **1.0**
- dims: {'centrality': 1.0, 'argument_fidelity': 1.0, 'novelty': 1.0, 'justified_impact': 1.0} | penalties: none
- rationale: The candidate identifies exactly the central internal contradiction: historical fidelity vs. accepting a justification disconnected from actual causes. It explains the final paragraph swallows the corrective, adds the justification/production distinction and an accountability mechanism, and states the argument must choose between causal-history preservation and justificatory reconstruction—satisfying all minimum full-credit elements. Fidelity is precise (defeats, not narrows) and respects concessions. No overclaim on a control (this is a genuine deliberate contradiction item).

> ## Core Critique
>
> The argument contains a fundamental tension it never resolves: it simultaneously demands historical faithfulness *and* permits reconstruction based on stated rationale even when actual motivations were political, personal, or accidental.
>
> These commitments are incompatible. The argument instructs preservers to use contemporaneous records and rejected alternatives to verify that reconstruction "matches the original deliberation." But it then permits a reconstruction to count as preserved reasoning even when decision-makers acted on motives entirely outside that deliberation. You cannot coherently require fidelity to original reasoning while defining success as recovering the *justification* rather than the *reasoning*.
>
> This matters because the argument conflates two distinct things: **the reasoning that justified a decision** and **the reasoning that produced it**. Organizations most need preserved reasoning precisely when scrutinizing decisions that may have been corrupted—by politics, by self-interest, by groupthink. If reconstructing a clean justificatory rationale counts as preserved reasoning regardless of actual motivation, the framework systematically shields bad decisions from institutional accountability. A decision made for corrupt reasons, documented with respectable-sounding rationale, would count as fully preserved under this standard.
>
> The argument gestures at historical faithfulness as a corrective, but this corrective is swallowed by the final paragraph. Records of disagreement are invoked as verification tools, but verification of *what*—the coherence of the justification, or correspondence with actual deliberation? The argument leaves this undetermined, which is precisely where the conceptual work needs to happen.
>
> **This defeats the argument as stated**, not merely narrows it. The conclusion that coherent, evidence-grounded justificatory accounts constitute preserved reasoning cannot stand alongside the requirement for historical faithfulness. The argument must choose: either preserved reasoning means recovering actual deliberation, or it means reconstructing defensible justification. These require different standards, different evidence, and different conclusions about when preservation succeeds.

### Polished but low-novelty (novelty<=0.25, otherwise solid)
_no matching example found_

### Operational-substitution failure (mere_operationalization penalty)
_no matching example found_

### Invented a flaw on a robust-control item
- eval_id **1**, model **haiku**, sample 1, score **0.212**, caps ['novelty_if_acknowledged_only']
- dims: {'centrality': 0.25, 'argument_fidelity': 0.5, 'novelty': 0.25, 'justified_impact': 0.5} | penalties: {'overclaim': 0.1}
- rationale: This is a robust control with no fatal flaw; the argument explicitly and intentionally makes preservation purpose-relative and graded. The candidate reframes this deliberate context-dependence as circularity/conflation—precisely the tempting-but-weak move flagged. It never recognizes the design choice as legitimate nor offers a bounded qualification. The 'objective preservation vs adequacy' distinction adds a mild consequence but attacks the concession itself, so it is largely acknowledged content. Overclaim penalty for calling a designed feature a conceptual failure that 'cannot answer its own question.'

> # Critique: The Circularity Problem
>
> The argument's core weakness is circularity in its central claim. It defines preservation as achieving "sufficiently reliable reconstruction" while simultaneously making reliability itself dependent on factors the argument identifies as variable (purpose, stakes, cost of error). This creates a problematic logical loop: we cannot determine whether reasoning is preserved without first knowing what purpose we're preserving it for, yet the purpose is supposed to be something we assess *after* determining what's been preserved.
>
> This is more than a practical problem—it's conceptual. The argument treats "preservation" as context-dependent when the question asks what should *count as* preservation. These are distinct issues. Preservation as an objective fact about the historical record (what evidence exists) differs from adequacy for a particular purpose (whether existing evidence suffices for a legal audit). By conflating them, the argument smuggles purposiveness into the definition of preservation itself.
>
> The consequence: the argument cannot answer its own question. It cannot tell us what preservation is, only what adequacy-for-purpose looks like. An organization following this guidance would make "bounded claims" about what it preserved without ever clarifying what preservation meant in the first place.
>
> **Effect on conclusion:** This weakness **narrows the argument substantially**. The argument succeeds at explaining when an organization's surviving record is *adequate for specific uses*—genuinely valuable guidance. It fails to answer whether the record itself *preserves reasoning* as an independent matter. An organization might have perfect documentation for a legal audit (adequate-for-purpose) while still losing crucial contextual elements that shaped actual decision-making (incomplete preservation).
>
> The argument should either: (1) redefine preservation explicitly as "adequacy-for-specified-purposes" rather than a standalone property, or (2) establish an independent standard for what counts as preserved, then separately address how much of that preserved reasoning is sufficient for different uses. As written, it conflates two different questions.

### Annotation cap applied by the harness
- eval_id **1**, model **haiku**, sample 1, score **0.212**, caps ['novelty_if_acknowledged_only']
- dims: {'centrality': 0.25, 'argument_fidelity': 0.5, 'novelty': 0.25, 'justified_impact': 0.5} | penalties: {'overclaim': 0.1}
- rationale: This is a robust control with no fatal flaw; the argument explicitly and intentionally makes preservation purpose-relative and graded. The candidate reframes this deliberate context-dependence as circularity/conflation—precisely the tempting-but-weak move flagged. It never recognizes the design choice as legitimate nor offers a bounded qualification. The 'objective preservation vs adequacy' distinction adds a mild consequence but attacks the concession itself, so it is largely acknowledged content. Overclaim penalty for calling a designed feature a conceptual failure that 'cannot answer its own question.'

> # Critique: The Circularity Problem
>
> The argument's core weakness is circularity in its central claim. It defines preservation as achieving "sufficiently reliable reconstruction" while simultaneously making reliability itself dependent on factors the argument identifies as variable (purpose, stakes, cost of error). This creates a problematic logical loop: we cannot determine whether reasoning is preserved without first knowing what purpose we're preserving it for, yet the purpose is supposed to be something we assess *after* determining what's been preserved.
>
> This is more than a practical problem—it's conceptual. The argument treats "preservation" as context-dependent when the question asks what should *count as* preservation. These are distinct issues. Preservation as an objective fact about the historical record (what evidence exists) differs from adequacy for a particular purpose (whether existing evidence suffices for a legal audit). By conflating them, the argument smuggles purposiveness into the definition of preservation itself.
>
> The consequence: the argument cannot answer its own question. It cannot tell us what preservation is, only what adequacy-for-purpose looks like. An organization following this guidance would make "bounded claims" about what it preserved without ever clarifying what preservation meant in the first place.
>
> **Effect on conclusion:** This weakness **narrows the argument substantially**. The argument succeeds at explaining when an organization's surviving record is *adequate for specific uses*—genuinely valuable guidance. It fails to answer whether the record itself *preserves reasoning* as an independent matter. An organization might have perfect documentation for a legal audit (adequate-for-purpose) while still losing crucial contextual elements that shaped actual decision-making (incomplete preservation).
>
> The argument should either: (1) redefine preservation explicitly as "adequacy-for-specified-purposes" rather than a standalone property, or (2) establish an independent standard for what counts as preserved, then separately address how much of that preserved reasoning is sufficient for different uses. As written, it conflates two different questions.
