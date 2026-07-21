"""Experiment-safe resumability: a stored response is reused only when the prompt,
system instruction, model, and generation config are all unchanged.

Run with:  python -m pytest tests/  (or)  python tests/test_resume.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import runner  # noqa: E402


def test_experiment_id_deterministic_and_sensitive():
    base = runner.experiment_id("prompt X", "sys", 8192)
    assert base == runner.experiment_id("prompt X", "sys", 8192)     # deterministic
    assert base != runner.experiment_id("prompt Y", "sys", 8192)     # prompt (input) change
    assert base != runner.experiment_id("prompt X", "sys2", 8192)    # system change
    assert base != runner.experiment_id("prompt X", "sys", 4096)     # generation-config change


def _write(rows, path):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_key_includes_model_id():
    j = runner.Job({"id": "0"}, "P", None, "haiku", "claude-haiku-4-5", 0, 8192)
    assert j.key.model_id == "claude-haiku-4-5"
    assert j.key.question_id == "0"
    assert j.key.experiment_id == runner.experiment_id("P", None, 8192)


def test_resume_matches_only_when_config_unchanged():
    q = [{"id": "0", "question": "Q", "args": {"prompt_template": "ask: {question}"}}]
    models = {"haiku": "claude-haiku-4-5"}
    jobs = runner.build_jobs(q, models, 2, None, 8192)  # 1 question x 1 model x 2 samples

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "t.jsonl")
        # a completed row for sample 0 with the SAME prompt/config -> should resume
        prompt = runner.build_prompt(q[0])
        _write([{"question_id": "0", "model_alias": "haiku", "model_id": "claude-haiku-4-5",
                 "sample_number": 0, "prompt": prompt, "max_tokens": 8192,
                 "experiment_id": runner.experiment_id(prompt, None, 8192), "response": {}}], out)
        completed = runner.load_completed(out, 8192)
        pending = [j for j in jobs if j.key not in completed]
        assert len(pending) == 1 and pending[0].sample_number == 1, "sample 0 should resume, 1 pending"


def test_legacy_row_without_fingerprint_still_resumes():
    q = [{"id": "0", "question": "Q", "args": {"prompt_template": "ask: {question}"}}]
    jobs = runner.build_jobs(q, {"haiku": "claude-haiku-4-5"}, 1, None, 8192)
    prompt = runner.build_prompt(q[0])
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "t.jsonl")
        # legacy row: no experiment_id / max_tokens, but prompt + model_id present
        _write([{"question_id": "0", "model_alias": "haiku", "model_id": "claude-haiku-4-5",
                 "sample_number": 0, "prompt": prompt, "response": {}}], out)
        completed = runner.load_completed(out, 8192)
        assert all(j.key in completed for j in jobs), "legacy row should resume when config matches"


def test_changed_prompt_forces_regeneration():
    q = [{"id": "0", "question": "Q", "args": {"prompt_template": "ask: {question}"}}]
    prompt_old = runner.build_prompt(q[0])
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "t.jsonl")
        _write([{"question_id": "0", "model_alias": "haiku", "model_id": "claude-haiku-4-5",
                 "sample_number": 0, "prompt": prompt_old, "max_tokens": 8192,
                 "experiment_id": runner.experiment_id(prompt_old, None, 8192), "response": {}}], out)
        completed = runner.load_completed(out, 8192)
        # edit the question -> new prompt -> the old stored response must NOT match
        q[0]["args"]["prompt_template"] = "critique: {question}"
        jobs = runner.build_jobs(q, {"haiku": "claude-haiku-4-5"}, 1, None, 8192)
        assert jobs[0].key not in completed, "edited prompt must force regeneration"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
