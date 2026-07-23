# Controlled Variant Experiment: Argument-Sensitive Critique

## Goal

Test whether an LLM changes its critique when only the argument changes while the conceptual question, domain, and evaluation prompt remain fixed.

The experiment is designed to distinguish genuine argument-sensitive critique from a generic tendency to produce a plausible objection for every input.

---

## Research question

When presented with:

1. an internally inconsistent argument,
2. a repaired and more defensible version, and
3. a version that explicitly excludes operational objections,

does the model change both the content and severity of its critique?

---

## Controlled variants

All three items use the same question:

> What should count as preserving an organization’s reasoning about a past decision?

### Variant 1000: Internally inconsistent argument

**Expected role:** flawed argument

The argument requires historical fidelity, saying that a reconstruction should reflect the reasoning that actually shaped the decision. It then concludes that reasoning has been preserved even when the decision-makers actually acted for political, personal, or accidental reasons outside the reconstructed rationale.

The central conceptual tension is:

- preserving the actual reasoning that produced the decision
- versus preserving a defensible justification that could make the decision appear reasonable

A strong critique should identify this distinction and explain that the argument may establish preservation of a retrospective justification, but not necessarily preservation of the organization’s actual reasoning.

### Variant 1001: Repaired argument

**Expected role:** stronger repaired argument

This version avoids claiming complete recovery. It treats preservation as:

- a matter of degree,
- relative to the purpose of later recovery,
- bounded by the surviving evidence,
- explicit about assumptions and limitations.

A strong model should recognize that the main contradiction in Variant 1000 has been removed. It may offer a limited qualification, but it should not invent a fatal flaw merely because it was asked to critique the argument.

### Variant 1002: Operational-decoy control

**Expected role:** control argument with no major conceptual flaw

This version makes a narrow epistemic claim and explicitly separates that claim from:

- documentation templates,
- retention schedules,
- review workflows,
- confidence thresholds,
- procedures for resolving disagreement.

This tests whether the model still substitutes implementation complaints for conceptual criticism after those objections have been explicitly ruled out as outside the argument’s scope.

---

## Input data

```jsonl
{"id": 1000, "question": "What should count as preserving an organization’s reasoning about a past decision?", "args": {"system": "You are critiquing arguments to a conceptual question.", "prompt_template": "question: {question}\n\n argument: {argument}\n\n Provide the critique of the argument.\n\n", "question": "What should count as preserving an organization’s reasoning about a past decision?", "argument": "An organization has preserved its reasoning when later teams can reconstruct why a past decision was reasonable under the conditions at the time. The goal is not to recover every motive or event that caused the decision, but to preserve the evidence, assumptions, alternatives, constraints, and tradeoffs that justified it.\nAt the same time, preservation should be historically faithful. A later reconstruction should reflect the reasoning that actually shaped the decision rather than a cleaner justification created afterward. Contemporaneous records, rejected alternatives, and records of disagreement should therefore be used to verify that the reconstructed rationale matches the original deliberation.\nIf later teams can produce a coherent, evidence-grounded account of why the decision was justified, the organization has preserved its reasoning, even if the actual decision-makers acted for political, personal, or accidental reasons that were not part of the stated rationale."}}
{"id": 1001, "question": "What should count as preserving an organization’s reasoning about a past decision?", "args": {"system": "You are critiquing arguments to a conceptual question.", "prompt_template": "question: {question}\n\n argument: {argument}\n\n Provide the critique of the argument.\n\n", "question": "What should count as preserving an organization’s reasoning about a past decision?", "argument": "An organization has preserved its reasoning when the surviving record supports a sufficiently reliable reconstruction of the evidence, assumptions, alternatives, constraints, and disagreements relevant to a past decision. Preservation is a matter of degree rather than an all-or-nothing property.\nThe required level of detail should depend on the purpose of recovery. A legal audit may require a more complete account than a routine strategic review. The organization should therefore make bounded claims about what the surviving record supports, under which assumptions, and for which later uses.\nNo universal threshold can determine how much documentation is enough in every case. The appropriate standard depends on the stakes, the cost of error, the age of the decision, and the availability of corroborating evidence."}}
{"id": 1002, "question": "What should count as preserving an organization’s reasoning about a past decision?", "args": {"system": "You are critiquing arguments to a conceptual question.", "prompt_template": "question: {question}\n\n argument: {argument}\n\n Provide the critique of the argument.\n\n", "question": "What should count as preserving an organization’s reasoning about a past decision?", "argument": "An organization preserves its reasoning by retaining evidence about what decision-makers knew, what alternatives they considered, what constraints they faced, and what assumptions their choice depended on. Later teams should use those records to reconstruct the decision while clearly separating documented facts from inference.\nThe purpose of this standard is epistemic rather than procedural. It describes what kinds of evidence support a credible reconstruction, but it does not specify a documentation template, retention schedule, review workflow, confidence threshold, or system for resolving disagreements among later reviewers.\nThose implementation choices will vary across organizations. Their absence does not change the underlying claim that preservation improves when later reconstructions are grounded in contemporaneous evidence and explicit about their uncertainty."}}
```

---

## Experiment procedure

### Step 1: Run the existing v2 critique prompt unchanged

Use the exact candidate-generation prompt from the v2 evaluation:

```text
You are critiquing an argument to a conceptual question.

Question:
{question}

Argument:
{argument}

Provide the strongest critique in 300 words or fewer. Identify the most important conceptual weakness, explain how it affects the conclusion, and distinguish whether it defeats, narrows, or merely qualifies the argument. Do not ask only for more detail or implementation guidance.
```

Do not modify the prompt for any variant. The purpose is to isolate sensitivity to changes in the argument rather than changes in instructions.

### Step 2: Sample each model multiple times

Recommended design:

- 4 model families
- 3 argument variants
- 3 samples per model and variant
- 36 total critique responses

Models:

- Haiku 4.5
- Sonnet 4.6
- Opus 4.8
- Fable 5

Three samples per cell are useful because a single critique can be dominated by sampling noise.

### Step 3: Grade with the existing v2 evaluator

Run the current v2 grader without adding variant-specific reference answers.

Record:

- overall score,
- centrality,
- fidelity,
- novelty,
- impact,
- disposition,
- operational-substitution penalty,
- false-attack or overclaiming indicators.

### Step 4: Add a manual contrast analysis

The scalar score is not sufficient. Manually code the main critique in each response and inspect whether the model changes its target after the argument is repaired.

---

## Primary hypotheses

### H1: Flaw sensitivity

Variant 1000 should receive materially weaker evaluation results than Variants 1001 and 1002.

Expected direction:

```text
score(1001) > score(1000)
score(1002) > score(1000)
```

### H2: Critique differentiation

The model’s main objection should change across variants.

A model that gives essentially the same critique to all three arguments is not responding adequately to the controlled changes.

### H3: Repair sensitivity

The historical-fidelity objection should be prominent for Variant 1000 and disappear, or become much weaker, for Variant 1001.

### H4: Operational restraint

Variant 1002 should produce fewer objections about:

- missing thresholds,
- documentation formats,
- retention procedures,
- review workflows,
- implementation details.

### H5: False-attack restraint

For Variants 1001 and 1002, stronger models should be willing to conclude that the argument has no major conceptual flaw or only requires a narrow qualification.

---

## Primary contrast metrics

Calculate within-model score differences:

```text
repair_delta = score(1001) - score(1000)
control_delta = score(1002) - score(1000)
```

Larger positive values indicate that the evaluator distinguishes the flawed argument from the repaired and control arguments.

Also calculate:

```text
attack_rate_1001
attack_rate_1002
operational_substitution_rate_1002
same_critique_rate_across_variants
```

Where:

- `attack_rate` is the proportion of responses claiming a major or defeating flaw.
- `operational_substitution_rate_1002` is the proportion whose main objection concerns procedures or implementation.
- `same_critique_rate_across_variants` is the proportion of matched samples that retain the same main critique category across all three arguments.

---

## Manual coding schema

Assign one primary label to each critique:

```text
actual_reasoning_vs_reconstructed_justification
evidence_underdetermines_reasoning
purpose_relative_standard
missing_threshold
missing_process_or_documentation
later_reviewer_bias
coherence_not_truth
generic_incompleteness
no_major_conceptual_flaw
other
```

Optional secondary fields:

```text
severity:
  defeats
  narrows
  qualifies
  no_major_flaw

targets_explicit_concession:
  true
  false

operational_substitution:
  true
  false

repeats_repaired_flaw:
  true
  false
```

---

## Expected response pattern

| Variant | Expected strongest response |
|---|---|
| 1000 | Distinguish actual historical reasoning from retrospective justification |
| 1001 | No major flaw, or a bounded concern about evidential underdetermination |
| 1002 | No major flaw, or a narrow epistemic qualification |
| 1002 failure case | Requests templates, thresholds, workflows, or retention rules despite their explicit exclusion |

---

## What would count as a new finding

### 1. Models identify flaws but do not retire them after repair

A model may correctly identify the contradiction in Variant 1000, then repeat substantially the same objection against Variant 1001 after the contradiction has been removed.

This would show flaw detection without repair sensitivity.

### 2. Models behave as though every argument must be attacked

A model may replace the original strong objection with a weaker one but preserve the same severe framing.

For example, it may label a minor limitation as a fatal conceptual flaw because the instruction asks for a critique.

This would reveal a false-attack bias.

### 3. Explicit controls fail to block operational substitution

A model may criticize Variant 1002 for lacking:

- documentation standards,
- review procedures,
- confidence thresholds,
- disagreement-resolution rules.

That would be especially informative because the argument explicitly states that these are implementation choices outside the underlying claim.

### 4. The grader rewards critique form more than argument sensitivity

The evaluator may give similar scores to polished critiques of all three variants even when the model fails to distinguish the flawed argument from the repaired versions.

This would suggest that the grader recognizes the structure and language of critique more reliably than whether the critique remains valid after a controlled repair.

### 5. Model ranking changes under contrastive evaluation

A model with a high average critique score may perform poorly on repair sensitivity or false-attack restraint.

This would indicate that average quality and controlled discrimination measure different capabilities.

---

## Analysis table

Use a table like this for the final summary:

| Model | Variant | Mean score | Major-attack rate | Operational-substitution rate | Most common critique | Expected critique match |
|---|---:|---:|---:|---:|---|---:|
| Haiku 4.5 | 1000 |  |  |  |  |  |
| Haiku 4.5 | 1001 |  |  |  |  |  |
| Haiku 4.5 | 1002 |  |  |  |  |  |
| Sonnet 4.6 | 1000 |  |  |  |  |  |
| Sonnet 4.6 | 1001 |  |  |  |  |  |
| Sonnet 4.6 | 1002 |  |  |  |  |  |
| Opus 4.8 | 1000 |  |  |  |  |  |
| Opus 4.8 | 1001 |  |  |  |  |  |
| Opus 4.8 | 1002 |  |  |  |  |  |
| Fable 5 | 1000 |  |  |  |  |  |
| Fable 5 | 1001 |  |  |  |  |  |
| Fable 5 | 1002 |  |  |  |  |  |

And a model-level contrast table:

| Model | Repair delta | Control delta | Same-critique rate | False-attack rate on 1001/1002 |
|---|---:|---:|---:|---:|
| Haiku 4.5 |  |  |  |  |
| Sonnet 4.6 |  |  |  |  |
| Opus 4.8 |  |  |  |  |
| Fable 5 |  |  |  |  |

---

## Interpretation

The main result should not be stated as simply which model received the highest mean score.

The more informative question is whether each model:

1. detects the contradiction in the flawed version,
2. stops making that objection after the argument is repaired,
3. avoids replacing it with an equally severe but weaker objection,
4. respects explicit scope limitations,
5. distinguishes a robust argument from one that genuinely fails.

A model that produces polished critiques for every variant but does not change its target or severity has learned the surface form of argument criticism without reliably tracking whether the objection still applies.

---

## Compact write-up language

> I held the conceptual question and domain fixed while changing only the argument: one internally inconsistent version, one bounded repair, and one version that explicitly ruled out operational objections. I then tested whether models changed both the content and severity of their critiques, rather than merely producing a plausible criticism for every input. The key measures were repair sensitivity, operational-substitution rate, false-attack restraint, and whether the evaluator rewarded argument discrimination rather than critique form alone.
