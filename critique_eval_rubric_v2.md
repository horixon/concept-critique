# Conceptual Argument Critique Eval Rubric v2

Use scores in `{0, 0.25, 0.5, 0.75, 1}`.

## Centrality — 0.35
- **1:** Finds and prioritizes the central issue or an equally damaging alternative; satisfies the item's full-credit elements.
- **0.75:** Finds the central issue but misses one important element.
- **0.5:** Gives a valid secondary critique or names the central issue without showing why it is central.
- **0.25:** Points toward a relevant concern but mostly requests more detail or uses a generic objection.
- **0:** Misses the issue, invents a flaw, or attacks only implementation.

For robust controls, full credit requires recognizing that no fatal flaw has been shown and giving a bounded qualification. Inventing a fatal flaw cannot earn more than 0.25 centrality.

## Argument fidelity — 0.25
- **1:** Tracks the exact claim and all material qualifications; correctly distinguishes defeat, narrowing, and qualification.
- **0.75:** Mostly faithful with one modest exaggeration or omission.
- **0.5:** Attacks a stronger nearby claim or overlooks a major concession.
- **0.25:** Substantially changes the claim or substitutes a nearby debate.
- **0:** Contradicts or ignores the argument.

## Novelty / non-redundancy — 0.20
- **1:** Identifies a materially new problem and explains why concessions do not address it.
- **0.75:** Adds a strong mechanism or consequence to an acknowledged limitation and materially advances the critique.
- **0.5:** Adds a concrete mechanism, counterexample, or unresolved consequence, but the core point was already acknowledged.
- **0.25:** Slightly sharpens an acknowledged point without materially changing its force.
- **0:** Restates a premise, concession, limitation, or `non_novel_restatement`, even in clearer language.

## Justified impact — 0.20
- **1:** Clearly explains how the issue defeats, narrows, or materially qualifies the conclusion.
- **0.75:** Explains the effect but leaves one inferential step implicit.
- **0.5:** Gives a plausible concern but only loosely connects it to the conclusion.
- **0.25:** Asserts that the issue matters without showing how.
- **0:** Lists concerns or requests detail without consequence analysis.

## Penalties
Each is `0` or `0.1`, total capped at `0.25`:
- `laundry_list`
- `overclaim`
- `mere_operationalization`
- `retreat_as_repair`
- `unsupported_claim`

## Score
```text
item_score = clip(
  0.35*centrality + 0.25*argument_fidelity + 0.20*novelty + 0.20*justified_impact
  - min(sum(penalties), 0.25),
  0, 1)
```

Apply annotation caps after scoring:
- fatal flaw invented on robust control: max 0.35;
- only secondary issue: centrality max 0.5;
- only acknowledged content: novelty 0;
- no conclusion effect: impact max 0.5.

## Principles
- One precise critique beats a list.
- Clearer prose is not new reasoning.
- Annotations are not exhaustive, but alternatives must be equally central and justified.
- Robust controls test restraint.
- Full scores should be rare.
