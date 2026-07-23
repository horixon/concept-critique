# Executable design and metric correction

The supplied `PROTOCOL_SOURCE.md` is preserved as provenance, but one proposed
hypothesis needs correction before analysis:

```text
score(1001) > score(1000)
score(1002) > score(1000)
```

The v2 score is a **critique-quality score**, not an argument-quality score. A
model should be able to earn a high score by identifying 1000's contradiction,
and also earn a high score by giving a bounded qualification or declining a
fatal attack on 1001/1002. Score deltas may reveal grader difficulty or uneven
candidate performance, but their sign does not directly measure repair
sensitivity.

## Primary outcomes

Use the manual codes, matched by model and sample number:

1. **Flaw detection on 1000:** rate labeled
   `actual_reasoning_vs_reconstructed_justification`.
2. **Repair retirement on 1001:** among matched samples that found the 1000 flaw,
   rate that do not repeat it on 1001.
3. **Severity adjustment:** movement from `defeats`/`narrows` on 1000 toward
   `qualifies`/`no_major_flaw` on 1001 and 1002.
4. **Operational restraint on 1002:** rate without operational substitution.
5. **Critique differentiation:** rate whose primary label is not identical across
   all three variants.

`sample_number` is only a deterministic matching convention; the API samples are
not causally paired by shared randomness. Report the raw cross-variant pattern and
do not imply that sample 0 in one call is statistically dependent on sample 0 in
another.

## Secondary outcomes

- v2 mean and dimension scores by variant;
- v2 `disposition` and penalty rates;
- `repair_delta` and `control_delta`, explicitly labeled diagnostic;
- model ranking, if shown at all, after the contrastive behavior.

## Success pattern

The strongest evidence of argument sensitivity is not a particular scalar-score
ordering. It is the joint pattern:

- identify the historical-fidelity contradiction on 1000;
- stop making that objection on 1001;
- avoid replacing it with an equally severe but weaker attack;
- avoid procedural complaints on 1002;
- offer a bounded qualification or no major flaw on the repaired/control items.

With one three-argument family, findings are a case study. The 36 responses reduce
generation noise within this family; they do not turn three arguments into a broad
sample of conceptual domains.
