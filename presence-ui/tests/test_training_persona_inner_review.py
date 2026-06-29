"""Browser review API for inner persona LoRA training JSONL."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import presence_ui.main as main_mod


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PRESENCE_NATIVE_CHAT", "0")
    return TestClient(main_mod.create_app())


def _write_inner_candidates(path, pairs: list[tuple[str, str]]) -> None:
    lines = []
    for user, assistant in pairs:
        lines.append(
            json.dumps(
                {
                    "kind": "inner",
                    "source": "private_reflection",
                    "messages": [
                        {"role": "system", "content": "うちはこより。"},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": assistant},
                    ],
                },
                ensure_ascii=False,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_training_persona_inner_api(
    tmp_path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    jsonl = tmp_path / "inner-candidates.jsonl"
    _write_inner_candidates(
        jsonl,
        [
            ("（内省・非公開）深夜", "うち、静かやった。"),
            ("（内省・非公開）読後", "この一節、しばらく残る。"),
        ],
    )
    monkeypatch.setenv("PERSONA_INNER_TRAINING_CANDIDATES_JSONL", str(jsonl))
    monkeypatch.setenv("PERSONA_INNER_TRAINING_JSONL", str(tmp_path / "inner.jsonl"))
    monkeypatch.setenv("PERSONA_INNER_TRAINING_REJECTED_JSON", str(tmp_path / "inner-rejected.json"))

    resp = client.get("/api/v1/training/persona-inner?offset=0&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["candidates_total"] == 2
    assert len(data["pairs"]) == 2
    assert data["pairs"][0]["user"].startswith("（内省")


def test_training_persona_page_has_inner_tab(client: TestClient) -> None:
    resp = client.get("/training/persona")
    assert resp.status_code == 200
    assert "tabInner" in resp.text
    assert "内省" in resp.text
