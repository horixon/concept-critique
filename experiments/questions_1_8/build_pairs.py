#!/usr/bin/env python3
"""Deterministically build frozen robust/flawed pairs from the supplied items."""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path("experiments/questions_1_8")
SOURCE = BASE / "input/source.jsonl"
ITEMS = BASE / "input/items.paired.unannotated.jsonl"
MANIFEST = BASE / "input/pair_manifest.jsonl"

# Each flawed counterpart changes one conclusion while leaving the domain,
# question, and preceding qualifications untouched. The intended flaw is stored
# separately so synthetic annotators never see it.
FLAW_INSERTIONS = {
    100: (
        "It follows that persistent disagreement among capable and informed people should always reduce "
        "confidence by the same amount, even when their evidence is correlated or one side can explain the "
        "other's error.",
        "The conclusion discards the argument's own dependence, asymmetry, and explainable-error conditions "
        "and turns conditional conciliation into an unconditional fixed update.",
    ),
    200: (
        "Therefore an explanation is adequate whenever it is understandable and useful to its intended user, "
        "even if it does not faithfully track the model's actual decision process.",
        "The conclusion abandons the fidelity requirement and makes usefulness sufficient even when the "
        "explanation is false about what drove the decision.",
    ),
    300: (
        "Therefore, once a rule has been applied consistently across enough cases, that consistency is "
        "sufficient evidence that the rule itself is rational and good.",
        "The conclusion turns implementation consistency into sufficient evidence of substantive quality "
        "after the argument explicitly distinguished those properties.",
    ),
    400: (
        "If a simplified model fits the cases observed so far, any omitted factor can be treated as irrelevant "
        "by definition, because a relevant factor would already have changed those observed results.",
        "The conclusion defines omitted factors as irrelevant from in-sample fit, defeating the earlier demand "
        "for stress tests under reintroduction, interactions, and boundary changes.",
    ),
    500: (
        "Accordingly, sufficiently high predictive accuracy is by itself enough to justify an irreversible, "
        "high-stakes intervention even when the intervention moves the system outside the conditions in which "
        "the prediction was validated.",
        "The conclusion makes prediction alone sufficient precisely where the argument required causal and "
        "invariance evidence because intervention and distribution shift can break the relationship.",
    ),
    600: (
        "Therefore consensus reached after extensive discussion is direct evidence that the final decision is "
        "true or correct, regardless of whether dissent was safe or participants shared the same framing.",
        "The conclusion treats consensus as truth evidence while discarding the process conditions the argument "
        "said determine whether consensus is informative.",
    ),
    700: (
        "Thus continued improvement in the proxy is sufficient evidence that the underlying goal is improving, "
        "even after participants have adapted their behavior around what is measured.",
        "The conclusion assumes the proxy-target link remains valid in the exact adaptive setting where the "
        "argument warned that optimization can break or redefine it.",
    ),
    800: (
        "Consequently, any decision that can formally be reversed should always require less evidence than an "
        "irreversible one, even when reversal leaves reputational, coordination, or path-dependent harms behind.",
        "The conclusion uses nominal reversibility as sufficient after the argument required total state "
        "restoration and explicitly recognized hidden irreversibility.",
    ),
}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    source = load_jsonl(SOURCE)
    if {int(row["id"]) for row in source} != set(FLAW_INSERTIONS):
        raise SystemExit("source ids do not match the frozen flaw-insertion map")

    items: list[dict] = []
    manifest: list[dict] = []
    for row in source:
        source_id = int(row["id"])
        question = row["question"]
        argument = row["args"]["argument"]
        insertion, intended_flaw = FLAW_INSERTIONS[source_id]
        robust_id = source_id
        flawed_id = source_id + 1
        items.extend([
            {"eval_id": robust_id, "source_id": source_id, "question": question, "argument": argument},
            {
                "eval_id": flawed_id,
                "source_id": source_id,
                "question": question,
                "argument": argument.rstrip() + "\n\n" + insertion,
            },
        ])
        manifest.extend([
            {"eval_id": robust_id, "source_id": source_id, "pair_role": "robust", "intended_flaw": None},
            {
                "eval_id": flawed_id,
                "source_id": source_id,
                "pair_role": "flawed",
                "intended_flaw": intended_flaw,
            },
        ])

    with ITEMS.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    with MANIFEST.open("w", encoding="utf-8") as fh:
        for row in manifest:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {ITEMS} and {MANIFEST}: {len(items)} items / {len(items) // 2} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
