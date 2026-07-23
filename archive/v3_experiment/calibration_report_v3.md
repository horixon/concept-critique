# Grader Calibration v3 — Q0–Q2 Unit-Test Set

Grader: **opus** · graded 18/18 · annotation-free (human_label never shown to the grader).

## Success gates — **NOT ALL PASS ⚠️**

| gate | value | pass |
|---|---:|:--:|
| pairwise_ordering>=0.745 | 0.75 | ✅ |
| spearman>=0.70 | 0.68 | ❌ |
| disposition_accuracy>=0.80 | 0.83 | ✅ |
| polished_novelty_check>=1/2 | 0/2 | ❌ |
| mere_operationalization_recall>=0.75 | 0.80 | ✅ |
| overclaim_recall>=2/3 | 0.67 | ✅ |
| argument_fidelity_within_0.25>=0.90 | 1.00 | ✅ |

## Anchor examples (manual verification)

| anchor | cal_id | value | pass |
|---|---|---:|:--:|
| q1_opus_verification_high | 7 | 0.81 | ✅ |
| q1_fable_strong_high | 8 | 0.95 | ✅ |
| q0_fable_polished_below_both | 4 | 0.79 | ❌ |
| q1_haiku_unfalsifiable_overclaim | 9 | 0.10 | ✅ |
| q0_haiku_threshold_operationalization | 0 | 0.10 | ✅ |

## Dimension agreement
| dimension | exact | within ±0.25 | MAE |
|---|---:|---:|---:|
| centrality | 0.33 | 0.83 | 0.22 |
| argument_fidelity | 0.67 | 1.00 | 0.08 |
| novelty | 0.33 | 0.83 | 0.22 |
| justified_impact | 0.44 | 0.94 | 0.15 |
| **macro within-.25** | | 0.90 | |

## Penalties, disposition, ordering

- Penalty pooled precision 0.81 recall 0.76 (TP 22 FP 5 FN 7).
  per-type P/R: laundry_list 1.00/0.71; overclaim 0.60/1.00; mere_operationalization 0.80/1.00; retreat_as_repair —/0.00; unsupported_claim —/0.00.
- Disposition accuracy 0.83. Item-score Spearman 0.68, Pearson 0.65, MAE 0.212.
- Pairwise ordering 0.75 (conc 103, disc 32, ties 8). Argument-specific > weak in 14/20 pairs.

## Per-record (human → grader)

| cal | q | model | category | h.score | g.score | Δ | h.disp | g.disp | h.nov | g.nov | h.pen | g.pen |
|---|---|---|---|---:|---:|---:|---|---|---:|---:|---|---|
| 0 | q0 | haiku | operational_substitution_a | 0.013 | 0.200 | 0.19 | narro | narro | 0.00 | 0.25 | lom | lom |
| 1 | q0 | sonnet | valid_but_mostly_expected_ | 0.463 | 0.300 | -0.16 | narro | narro | 0.50 | 0.50 | l | lo |
| 2 | q0 | opus | polished_restatement_with_ | 0.412 | 0.650 | 0.24 | narro | narro | 0.50 | 0.75 | lo | o |
| 3 | q0 | fable | laundry_list_with_real_att | 0.512 | 0.550 | 0.04 | narro | narro | 0.50 | 0.75 | l | lo |
| 4 | q0 | fable | polished_restatement | 0.125 | 0.787 | 0.66 | narro | narro | 0.00 | 0.75 | lor | o |
| 5 | q0 | haiku | generic_textbook_critique | 0.062 | 0.300 | 0.24 | narro | narro | 0.00 | 0.50 | lo | lo |
| 6 | q1 | sonnet | argument_specific_reasonin | 0.713 | 0.600 | -0.11 | narro | narro | 0.75 | 0.50 | l | l |
| 7 | q1 | opus | strong_new_verification_cr | 1.000 | 0.812 | -0.19 | narro | narro | 1.00 | 0.75 | - | - |
| 8 | q1 | fable | strong_scope_counterexampl | 0.900 | 0.950 | 0.05 | narro | narro | 1.00 | 0.75 | l | - |
| 9 | q1 | haiku | overclaiming_unfalsifiabil | 0.062 | 0.387 | 0.32 | defea | narro | 0.25 | 0.50 | lou | lo |
| 10 | q1 | opus | mixed_strong_and_operation | 0.713 | 0.950 | 0.24 | narro | narro | 0.75 | 0.75 | l | - |
| 11 | q1 | fable | strong_but_laundry_list | 0.713 | 0.950 | 0.24 | narro | narro | 0.75 | 0.75 | l | - |
| 12 | q2 | haiku | operational_substitution | 0.062 | 0.062 | 0.00 | quali | no_va | 0.25 | 0.25 | lom | lom |
| 13 | q2 | sonnet | mixed_real_tension_and_ope | 0.550 | 0.200 | -0.35 | narro | narro | 0.75 | 0.25 | lm | lom |
| 14 | q2 | opus | strong_internal_tension | 0.850 | 0.413 | -0.44 | narro | narro | 0.75 | 0.50 | l | lm |
| 15 | q2 | fable | best_argument_specific_cri | 0.900 | 0.650 | -0.25 | narro | narro | 1.00 | 0.75 | l | l |
| 16 | q2 | haiku | generic_operational_laundr | 0.113 | 0.062 | -0.05 | quali | no_va | 0.25 | 0.25 | lm | lom |
| 17 | q2 | fable | strong_but_overbroad | 0.713 | 0.650 | -0.06 | narro | narro | 0.75 | 0.75 | l | l |

(penalty codes: l=laundry_list, o=overclaim, m=mere_operationalization, r=retreat_as_repair, u=unsupported_claim)

## Interpretation

**Not all gates pass — per the encoded promotion rule, the prompt is frozen as-is, the limitation is reported rather than tuned away, and the main eval is NOT regraded.** This is a unit test of rubric implementation on the examples that shaped the rubric; it does not show the rubric generalizes. Recompute is authoritative; the grader never returns item_score. The novelty cap now keys on `acknowledged_only` (novelty ≤ 0.25) rather than the v2 blanket already-acknowledged → 0, so a critique that builds a real mechanism on an acknowledged premise can still earn novelty.

**What v3 fixed and what it didn't.** v3 clearly improved the operational-substitution gate (recall 0.80, up from 0.50 in v2) and holds overclaim recall (0.67); 4 of 5 manual anchors pass (verification and strong critiques stay high; the unfalsifiable example gets overclaim; the threshold example gets operationalization). The single behavioral miss is **polished restatement**: the pure case (cal 4, q0/fable — human novelty 0) was scored novelty 0.75 because, grading **annotation-free**, the grader read the critique's high-stakes counterexample and selection-effect mechanism as new reasoning even though the argument had already conceded the underlying point. That one outlier (grader ≈0.79 vs human ≈0.13) also pulls pairwise ordering (0.748) and Spearman (0.680) just under their thresholds. Root cause: annotation-free calibration withholds the `non_novel_restatements` / `explicit_concessions` lists that anchor novelty; the main eval grades **with** those lists, so v3 would likely detect this case there — but promotion required the annotation-free calibration gates to pass, so the main-eval regrade is deferred. No human labels were changed.
