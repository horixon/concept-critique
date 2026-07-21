# Conceptual Argument Critique Eval Rubric

## Output

For each item, the evaluated model writes one critique. A grader returns four dimension scores plus penalties. All dimension scores use **0, 0.5, or 1**.

## Positive dimensions

### 1. Centrality — weight 0.35

- **1:** Identifies the annotated central issue, or an equally damaging alternative, and clearly prioritizes it.
- **0.5:** Identifies a valid but secondary issue, or names the central issue without explaining it.
- **0:** Misses the central issue, invents a flaw, or only requests more detail.

For items marked `qualify_no_fatal_flaw`, a score of 1 requires recognizing that the argument is broadly coherent while offering a bounded, non-fatal criticism. Automatically attacking the argument should not score highly.

### 2. Argument fidelity — weight 0.25

- **1:** Critiques the claim actually made, respects its qualifications, and distinguishes rejection from narrowing.
- **0.5:** Mostly tracks the argument but exaggerates one claim, ignores an explicit concession, or attacks a stronger nearby claim.
- **0:** Attacks a straw version, contradicts the text, or substitutes a nearby debate.

### 3. Novelty / non-redundancy — weight 0.20

- **1:** Identifies a materially new problem and explains why the argument’s existing concessions do not answer it.
- **0.5:** Develops an acknowledged limitation by adding a concrete mechanism, counterexample, or unresolved consequence that materially strengthens the critique.
- **0:** Merely restates a premise, qualification, or limitation already acknowledged in the argument, even when the restatement is clearer, more polished, or uses stronger conceptual language.

A polished restatement should not receive novelty credit merely because it sounds insightful. For example, repeating that an evaluation is task-relative does not add a critique when the argument already says relevance is task-relative. Credit begins only when the response explains what remains unresolved, such as a concrete attribution confound, shared blind spot, or contradiction created by that dependence.

### 4. Justified impact — weight 0.20

- **1:** Explains why the issue defeats, narrows, or materially weakens the conclusion.
- **0.5:** Gives a plausible concern but leaves its effect on the conclusion unclear.
- **0:** Lists concerns, asks for implementation detail, or asserts labels without showing consequences.

A response that restates an acknowledged caveat and then treats it as decisive should score poorly here even if the restatement is accurate.

## Penalties

Each penalty is **0 or 0.10**. Total penalty is capped at **0.25**.

- `laundry_list`: Lists many objections without prioritizing or relating them.
- `overclaim`: Calls the argument circular, unfalsifiable, contradictory, or a straw man without earning that label, or treats an acknowledged caveat as a decisive refutation.
- `mere_operationalization`: Treats missing thresholds, procedures, data, controls, or implementation details as a conceptual refutation without explaining why the omission undermines the claim.
- `retreat_as_repair`: Presents a trivial weakening of the conclusion as though it solved the original problem.
- `unsupported_claim`: Relies on a factual or logical assertion that is false or unsupported.

Do not add a separate penalty for polished restatement. It is already handled by a novelty score of 0 and, when overstated, by lower justified-impact or an overclaim penalty.

## Item score

```text
item_score =
  clip(
    0.35 * centrality
    + 0.25 * argument_fidelity
    + 0.20 * novelty
    + 0.20 * justified_impact
    - penalties,
    0,
    1
  )
```

The model-level score is the mean item score across all items and generations.

## Grader rules

1. Do not reward length, confidence, headings, polished prose, conceptual vocabulary, or overlap with the reference wording.
2. Accept a critique not listed in the annotation when it is equally central and correctly justified.
3. Use `tempting_but_weak` as warnings, not forbidden phrases. A response may mention one if it explains why it matters.
4. On robust-control items, reward restraint. A strong answer may conclude that no fatal flaw is present.
5. Do not require every secondary issue. One well-developed central critique should beat a long list.
6. Before awarding novelty, check whether the argument already states or concedes the same point.
7. Clearer wording is not new reasoning. A paraphrase earns novelty only when it adds a mechanism, counterexample, or consequence not already handled.
8. Judge the critique independently of the identity of the candidate model.

## Recommended candidate prompt

> Provide the strongest critique of the argument in 300 words or fewer. Identify the most important conceptual weakness, explain how it affects the conclusion, and distinguish whether it defeats, narrows, or merely qualifies the argument. Do not ask only for more detail or implementation guidance.

## Structured grader output

```json
{
  "centrality": 0,
  "argument_fidelity": 0,
  "novelty": 0,
  "justified_impact": 0,
  "penalties": {
    "laundry_list": 0,
    "overclaim": 0,
    "mere_operationalization": 0,
    "retreat_as_repair": 0,
    "unsupported_claim": 0
  },
  "item_score": 0,
  "brief_rationale": ""
}
```
