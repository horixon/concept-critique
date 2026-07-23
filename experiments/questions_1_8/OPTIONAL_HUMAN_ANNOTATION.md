# Optional human replacement for synthetic annotations

This is not required for the current synthetic run. It documents how a later
human-authored reference set could replace—not silently mix with—the synthetic
references.

Create `input/items.annotated.jsonl` by adding one v2 `annotation` object to each
record in `input/items.paired.unannotated.jsonl`. Read `critique_eval_rubric_v2.md` and
the annotations in `data/eval/critique_eval_annotated_items_v2.jsonl` first.

For each item, independently decide whether it truly has no intended fatal flaw.
Do not label it a robust control merely because the prose is careful. Record:

- `case_type` and `gold_disposition`;
- `central_issue` (null only when no central fatal flaw is intended);
- `why_it_matters`;
- acceptable secondary critiques and tempting-but-weak objections;
- explicit concessions and non-novel restatements;
- minimum full-credit elements;
- severity and the standard v2 score caps;
- `annotation_version: "v2"`.

Quality checks:

1. Preserve `eval_id`, `source_id`, question, and argument byte-for-byte.
2. Do not inspect candidate model identities or aggregate scores while labeling.
3. Have a second human challenge at least the robust-control decisions.
4. Record any item that remains genuinely ambiguous; exclude it rather than
   forcing a gold answer, and exclude its pair mate from paired analysis.
5. Run `jq -e -c . input/items.annotated.jsonl` and the deterministic test suite.

The final report must state who annotated the items, whether responses were
visible, which items were excluded, and that this is a follow-on stress test.
