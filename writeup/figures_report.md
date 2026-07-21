# Conceptual Critique Eval — Figure Placement

Screenshots of model critiques, grouped by report section. Each figure is preceded by the sentence it should follow in the draft and annotated with its caption. Regenerate images with `python3 make_figures.py`.

## Q0 baseline and critique leakage

> Insert after: “Haiku often focused on clearer thresholds, broader coverage, and how much accuracy should count as enough.”

![Haiku shifts toward threshold-setting and operational detail rather than identifying a deeper conceptual flaw.](figures/q0_haiku_s1_thresholds.png)

***Figure 1.*** Haiku shifts toward threshold-setting and operational detail rather than identifying a deeper conceptual flaw. *(Haiku, Q0, sample 1.)*

> Insert after: “All four model families found some version of those points.”

![Sonnet identifies the expected sampling and rare-omission critique that Q0 strongly cued.](figures/q0_sonnet_s1_sampling.png)

***Figure 2.*** Sonnet identifies the expected sampling and rare-omission critique that Q0 strongly cued. *(Sonnet, Q0, sample 1.)*

## Q0 polished restatement

> Insert after: “Opus and Fable produced broader critiques, but some initially seemed better than they were because they restated premises already present in the argument using more polished language.”

![Opus gives a polished formulation of the question-distribution concern.](figures/q0_opus_s2_question_selection.png)

***Figure 3.*** Opus gives a polished formulation of the question-distribution concern. *(Opus, Q0, sample 2.)*

## Laundry-list critique

> Insert after: “Longer responses accumulated many plausible objections but often did not decide which one was central.”

![Fable lists several overlapping critique categories without clearly ranking the load-bearing flaw.](figures/q0_fable_s0_laundry_list.png)

***Figure 4.*** Fable lists several overlapping critique categories without clearly ranking the load-bearing flaw. *(Fable, Q0, sample 0.)*

## Q1 argument-specific critiques

> Insert after: “Sonnet questioned whether reaching the same output means the reasoning process was preserved.”

![Sonnet challenges whether matching outputs implies equivalent reasoning.](figures/q1_sonnet_s2_same_place.png)

***Figure 5.*** Sonnet challenges whether matching outputs implies equivalent reasoning. *(Sonnet, Q1, sample 2.)*

> Insert after: “Opus pointed out that verifying whether the summary is faithful is itself a task that still requires the original.”

![Opus identifies verification as a function the original still performs.](figures/q1_opus_s0_verification_regress.png)

***Figure 6.*** Opus identifies verification as a function the original still performs. *(Opus, Q1, sample 0.)*

> Insert after: “Fable identified the clearest new counterexample: some documents matter because they are the original.”

![Fable notes that authoritative or evidential status may not transfer to a summary.](figures/q1_fable_s1_authoritative_original.png)

***Figure 7.*** Fable notes that authoritative or evidential status may not transfer to a summary. *(Fable, Q1, sample 1.)*

## Weak novelty detection and overclaiming

> Insert after: “It also sometimes overstated objections with labels such as “circular,” “unfalsifiable,” or “straw man,” even when the underlying issue was weaker or repairable.”

![Opus overstates the full-source paragraph as a straw man.](figures/q0_opus_s2_straw_man.png)

***Figure 8.*** Opus overstates the full-source paragraph as a straw man. *(Opus, Q0, sample 2.)*

> Insert after: “It also sometimes overstated objections with labels such as “circular,” “unfalsifiable,” or “straw man,” even when the underlying issue was weaker or repairable.”

![Haiku calls the criterion unfalsifiable even though it remains testable over a specified task set.](figures/q1_haiku_s2_unfalsifiable.png)

***Figure 9.*** Haiku calls the criterion unfalsifiable even though it remains testable over a specified task set. *(Haiku, Q1, sample 2.)*

## Q0/Q1 polished restatement

> Insert after: “The argument already acknowledged that relevance is task-relative, finite evaluation cannot guarantee complete preservation, and downstream performance is evidence rather than proof.”

![Fable sharpens the observed-versus-possible-tasks distinction, but much of the premise was already acknowledged.](figures/q1_fable_s1_dispositional.png)

***Figure 10.*** Fable sharpens the observed-versus-possible-tasks distinction, but much of the premise was already acknowledged. *(Fable, Q1, sample 1.)*
