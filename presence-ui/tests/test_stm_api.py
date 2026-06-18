"""Gateway STM API tests (MEM-1+)."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from social_core import SocialDB

from presence_ui.deps import reset_stores
from presence_ui.main import create_app

_thread_local = threading.local()


class _StmStores:
    def __init__(self, db: SocialDB) -> None:
        self.db = db
        self.policy_timezone = "Asia/Tokyo"


def _thread_get_stores(db_path):
    stores = getattr(_thread_local, "stores", None)
    if stores is None:
        stores = _StmStores(SocialDB(db_path))
        _thread_local.stores = stores
    return stores


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "social.db"
    reset_stores()
    _thread_local.stores = None
    monkeypatch.setenv("SOCIAL_DB_PATH", str(db_path))

    def getter():
        return _thread_get_stores(db_path)

    monkeypatch.setattr("presence_ui.deps.get_stores", getter)
    monkeypatch.setattr("presence_ui.gateway.stm_api.get_stores", getter)
    monkeypatch.setattr("presence_ui.services.stm_episode.get_stores", getter)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_stores()
    _thread_local.stores = None


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


def test_stm_close_episode(client):
    payload = {
        "person_id": "ma",
        "session_id": "sess_close",
        "trigger": "new_session",
        "turns": [
            {
                "sender": "ma",
                "message": "明日の天気どう？",
                "timestamp": "2026-06-16T18:00:00+09:00",
            },
            {
                "sender": "koyori",
                "message": "雨みたいやから傘持って行った方がええかも",
                "timestamp": "2026-06-16T18:00:05+09:00",
            },
        ],
        "timezone": "Asia/Tokyo",
        "use_llm": False,
    }
    first = client.post("/api/v1/stm/close-episode", json=payload)
    assert first.status_code == 200
    body = first.json()
    assert body["ok"] is True
    assert body["closed"] is True
    assert body["skipped"] is False
    assert body["entry_id"]
    assert "天気" in (body["summary"] or "")

    second = client.post("/api/v1/stm/close-episode", json=payload)
    assert second.status_code == 200
    again = second.json()
    assert again["skipped"] is True
    assert again["reason"] == "already_closed"
    assert again["entry_id"] == body["entry_id"]
