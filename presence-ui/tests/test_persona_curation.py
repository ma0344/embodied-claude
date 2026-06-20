"""Persona training curation (reject manifest + curated JSONL)."""

from __future__ import annotations

import json

import pytest

from presence_ui.training.persona_curation import (
    apply_persona_curation,
    pair_fingerprint,
    reject_training_pairs,
)
from presence_ui.training.persona_export import load_persona_jsonl


def test_pair_fingerprint_stable() -> None:
    left = pair_fingerprint("今日どう？", "まあまあやな。")
    right = pair_fingerprint("今日どう？", "まあまあやな。")
    assert left == right
    assert len(left) == 16


def test_apply_persona_curation_excludes_rejected(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates = tmp_path / "candidates.jsonl"
    curated = tmp_path / "curated.jsonl"
    rejected = tmp_path / "rejected.json"
    monkeypatch.setenv("PERSONA_TRAINING_CANDIDATES_JSONL", str(candidates))
    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(curated))
    monkeypatch.setenv("PERSONA_TRAINING_REJECTED_JSON", str(rejected))

    lines = []
    for i, (user, assistant) in enumerate(
        (
            ("u1", "a1"),
            ("u2", "a2"),
        )
    ):
        lines.append(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": assistant},
                    ]
                },
                ensure_ascii=False,
            )
        )
    candidates.write_text("\n".join(lines) + "\n", encoding="utf-8")

    added, stats = reject_training_pairs([("u1", "a1")])
    assert added == 1
    assert stats.candidates == 2
    assert stats.curated == 1
    assert stats.rejected == 1

    apply_persona_curation(candidates_path=candidates, curated_path=curated)
    kept = load_persona_jsonl(curated)
    assert len(kept) == 1
    assert kept[0].user == "u2"


def test_reject_is_idempotent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidates = tmp_path / "candidates.jsonl"
    curated = tmp_path / "curated.jsonl"
    rejected = tmp_path / "rejected.json"
    monkeypatch.setenv("PERSONA_TRAINING_CANDIDATES_JSONL", str(candidates))
    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(curated))
    monkeypatch.setenv("PERSONA_TRAINING_REJECTED_JSON", str(rejected))

    candidates.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "u1"},
                    {"role": "assistant", "content": "a1"},
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    first, _ = reject_training_pairs([("u1", "a1")])
    second, stats = reject_training_pairs([("u1", "a1")])
    assert first == 1
    assert second == 0
    assert stats.rejected == 1

    apply_persona_curation(candidates_path=candidates, curated_path=curated)
    assert load_persona_jsonl(curated) == []
