"""Browser review API for persona LoRA training JSONL."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import presence_ui.main as main_mod


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PRESENCE_NATIVE_CHAT", "0")
    return TestClient(main_mod.create_app())


def _write_candidates(path, pairs: list[tuple[str, str]]) -> None:
    lines = []
    for user, assistant in pairs:
        lines.append(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "うちはこより。"},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": assistant},
                    ]
                },
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_training_persona_api_paginates(
    tmp_path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    jsonl = tmp_path / "candidates.jsonl"
    _write_candidates(jsonl, [("user-0", "reply-0"), ("user-1", "reply-1"), ("user-2", "reply-2")])

    monkeypatch.setenv("PERSONA_TRAINING_CANDIDATES_JSONL", str(jsonl))
    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(tmp_path / "curated.jsonl"))
    monkeypatch.setenv("PERSONA_TRAINING_REJECTED_JSON", str(tmp_path / "rejected.json"))

    resp = client.get("/api/v1/training/persona?offset=1&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["candidates_total"] == 3
    assert data["curated_total"] == 3
    assert data["offset"] == 1
    assert len(data["pairs"]) == 1
    assert data["pairs"][0]["user"] == "user-1"
    assert data["pairs"][0]["rejected"] is False


def test_training_persona_reject_updates_curated(
    tmp_path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    candidates = tmp_path / "candidates.jsonl"
    curated = tmp_path / "curated.jsonl"
    rejected = tmp_path / "rejected.json"
    _write_candidates(
        candidates,
        [("keep-me", "ok"), ("drop-me", "bad")],
    )

    monkeypatch.setenv("PERSONA_TRAINING_CANDIDATES_JSONL", str(candidates))
    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(curated))
    monkeypatch.setenv("PERSONA_TRAINING_REJECTED_JSON", str(rejected))

    resp = client.post(
        "/api/v1/training/persona/reject",
        json={"pairs": [{"user": "drop-me", "assistant": "bad"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == 1
    assert data["curated_total"] == 1

    review = client.get("/api/v1/training/persona?offset=0&limit=10").json()
    assert review["curated_total"] == 1
    assert review["rejected_total"] == 1
    dropped = next(p for p in review["pairs"] if p["user"] == "drop-me")
    assert dropped["rejected"] is True

    assert curated.is_file()
    curated_pairs = [json.loads(line) for line in curated.read_text(encoding="utf-8").splitlines()]
    assert len(curated_pairs) == 1
    assert curated_pairs[0]["messages"][1]["content"] == "keep-me"


def test_training_persona_page(client: TestClient) -> None:
    resp = client.get("/training/persona")
    assert resp.status_code == 200
    assert "Persona LoRA" in resp.text
    assert "会話から再 export" in resp.text
    assert "選択を学習から除外" in resp.text
    assert 'class="pager-prev"' in resp.text


def test_training_persona_export(
    tmp_path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    candidates = tmp_path / "candidates.jsonl"
    curated = tmp_path / "curated.jsonl"
    rejected = tmp_path / "rejected.json"
    monkeypatch.setenv("PERSONA_TRAINING_CANDIDATES_JSONL", str(candidates))
    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(curated))
    monkeypatch.setenv("PERSONA_TRAINING_REJECTED_JSON", str(rejected))

    from presence_ui.training.persona_export import PersonaExportStats

    monkeypatch.setattr(
        "presence_ui.training.persona_review.export_persona_jsonl",
        lambda **kwargs: PersonaExportStats(
            sessions_scanned=3,
            pairs_written=12,
            pairs_skipped=4,
        ),
    )

    resp = client.post("/api/v1/training/persona/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sessions_scanned"] == 3
    assert data["pairs_written"] == 12
    assert data["pairs_skipped"] == 4
    assert data["curated_total"] == 0
