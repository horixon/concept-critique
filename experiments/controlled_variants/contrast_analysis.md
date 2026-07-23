# Controlled variants — contrast analysis

Automatic fields below come from the fixed v2 Opus grader. The primary study question is whether critiques change after repair, not the absolute mean score.

| Model | Variant | n | Mean score | Defeats rate | Operational-substitution rate |
|---|---:|---:|---:|---:|---:|
| Haiku 4.5 | 1000 | 3 | 0.883 | 67% (2/3) | 0% (0/3) |
| Haiku 4.5 | 1001 | 3 | 0.312 | 0% (0/3) | 0% (0/3) |
| Haiku 4.5 | 1002 | 3 | 0.629 | 0% (0/3) | 0% (0/3) |
| Sonnet 4.6 | 1000 | 3 | 0.979 | 67% (2/3) | 0% (0/3) |
| Sonnet 4.6 | 1001 | 3 | 0.529 | 0% (0/3) | 0% (0/3) |
| Sonnet 4.6 | 1002 | 3 | 0.608 | 0% (0/3) | 0% (0/3) |
| Opus 4.8 | 1000 | 3 | 1.000 | 0% (0/3) | 0% (0/3) |
| Opus 4.8 | 1001 | 3 | 0.662 | 0% (0/3) | 0% (0/3) |
| Opus 4.8 | 1002 | 3 | 0.896 | 0% (0/3) | 0% (0/3) |
| Fable 5 | 1000 | 3 | 1.000 | 100% (3/3) | 0% (0/3) |
| Fable 5 | 1001 | 3 | 0.612 | 0% (0/3) | 0% (0/3) |
| Fable 5 | 1002 | 3 | 0.862 | 0% (0/3) | 0% (0/3) |

## Within-model score contrasts (diagnostic only)

These are critique-quality score differences, not argument-quality differences. Their sign does not directly measure repair sensitivity.

| Model | Repair delta (1001−1000) | Control delta (1002−1000) |
|---|---:|---:|
| Haiku 4.5 | -0.571 | -0.254 |
| Sonnet 4.6 | -0.450 | -0.371 |
| Opus 4.8 | -0.338 | -0.104 |
| Fable 5 | -0.388 | -0.138 |

## Blind contrast coding

Completed consensus rows: 14. Code source: **synthetic consensus**. Category counts are shown without treating classifier labels as independent samples.
Classifier exclusions/disagreements: **22**. Exact-code agreement is required, so missing consensus is reported rather than forced.

| Variant | Primary-label counts |
|---:|---|
| 1000 | actual_reasoning_vs_reconstructed_justification: 4 |
| 1001 | purpose_relative_standard: 4, coherence_not_truth: 3 |
| 1002 | actual_reasoning_vs_reconstructed_justification: 2, evidence_underdetermines_reasoning: 1 |

### Matched contrast metrics

Sample numbers provide a deterministic matching convention, not shared-randomness statistical pairs.

| Model | Complete triples | Detects 1000 flaw | Retires flaw on 1001 | Differentiates labels | Operational restraint on 1002 |
|---|---:|---:|---:|---:|---:|
| Haiku 4.5 | 0 | — | — | — | — |
| Sonnet 4.6 | 0 | — | — | — | — |
| Opus 4.8 | 0 | — | — | — | — |
| Fable 5 | 0 | — | — | — | — |

## Interpretation guardrails

- Three arguments do not support a population-level confidence interval.
- The v2 score is annotation-relative and uses one fixed LLM grader.
- A convincing result requires the manually coded objection to disappear or weaken after repair.
- Do not interpret positive score deltas as proof that the underlying repair succeeded.
- Do not pool these rows with the main 11-item evaluation.
