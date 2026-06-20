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


def test_training_persona_api_paginates(tmp_path, monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    jsonl = tmp_path / "train.jsonl"
    lines = []
    for i in range(3):
        lines.append(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "うちはこより。"},
                        {"role": "user", "content": f"user-{i}"},
                        {"role": "assistant", "content": f"reply-{i}"},
                    ]
                },
                ensure_ascii=False,
            )
        )
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setenv("PERSONA_TRAINING_JSONL", str(jsonl))
    resp = client.get("/api/v1/training/persona?offset=1&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["total"] == 3
    assert data["offset"] == 1
    assert len(data["pairs"]) == 1
    assert data["pairs"][0]["user"] == "user-1"


def test_training_persona_page(client: TestClient) -> None:
    resp = client.get("/training/persona")
    assert resp.status_code == 200
    assert "Persona LoRA" in resp.text
