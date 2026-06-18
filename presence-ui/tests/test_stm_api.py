"""Gateway STM API tests (MEM-1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from social_core import SocialDB

from presence_ui.deps import reset_stores
from presence_ui.main import create_app


class _StmStores:
    def __init__(self, db: SocialDB) -> None:
        self.db = db
        self.policy_timezone = "Asia/Tokyo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "social.db"
    db = SocialDB(db_path)
    stores = _StmStores(db)
    reset_stores()
    monkeypatch.setenv("SOCIAL_DB_PATH", str(db_path))
    monkeypatch.setattr("presence_ui.deps.get_stores", lambda: stores)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_stores()


def test_stm_flush_wm_and_recent(client):
    payload = {
        "person_id": "ma",
        "session_id": "sess_api",
        "trigger": "session_end",
        "turns": [
            {"sender": "ma", "message": "テスト", "timestamp": "2026-06-16T12:00:00+09:00"},
            {"sender": "koyori", "message": "うん", "timestamp": "2026-06-16T12:00:01+09:00"},
        ],
        "timezone": "Asia/Tokyo",
    }
    flush = client.post("/api/v1/stm/flush-wm", json=payload)
    assert flush.status_code == 200
    body = flush.json()
    assert body["ok"] is True
    assert body["flushed"] == 2
    assert len(body["entry_ids"]) == 2

    recent = client.get("/api/v1/stm/recent", params={"person_id": "ma", "limit": 5})
    assert recent.status_code == 200
    recent_body = recent.json()
    assert recent_body["count"] == 2
    assert recent_body["local_day"] == "2026-06-16"
    assert "[stm_recent]" in recent_body["prompt_block"]
