"""Dreaming job tests (MEM-3)."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from social_core import SocialDB
from social_core.stm import StmStore

from presence_ui.deps import reset_stores
from presence_ui.main import create_app
from presence_ui.services.dream_digest import load_dream_digest
from presence_ui.services.dreaming import run_dreaming_job

_thread_local = threading.local()


class _DreamStores:
    def __init__(self, db: SocialDB) -> None:
        self.db = db
        self.policy_timezone = "Asia/Tokyo"
        self.self_narrative = MagicMock()
        self.self_narrative.append_daybook.return_value = MagicMock(day="2026-06-16")


def _thread_get_stores(db_path):
    stores = getattr(_thread_local, "stores", None)
    if stores is None:
        stores = _DreamStores(SocialDB(db_path))
        _thread_local.stores = stores
    return stores


@pytest.fixture
def dream_env(tmp_path, monkeypatch):
    db_path = tmp_path / "social.db"
    reset_stores()
    _thread_local.stores = None
    monkeypatch.setenv("SOCIAL_DB_PATH", str(db_path))
    monkeypatch.setenv("PRESENCE_DREAM_DIGEST_PATH", str(tmp_path / "dream.json"))

    def getter():
        return _thread_get_stores(db_path)

    monkeypatch.setattr("presence_ui.deps.get_stores", getter)
    monkeypatch.setattr("presence_ui.services.dreaming.get_stores", getter)
    db = SocialDB(db_path)
    return db_path, db, getter


def test_run_dreaming_job_skips_private_reflection(dream_env):
    _db_path, db, getter = dream_env
    stm = StmStore(db)
    stm.append(
        summary="まーと散歩の約束をした",
        kind="episode_close",
        source="episode_summary",
        person_id="ma",
        session_id="sess_promote",
        ts="2026-06-16T20:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    stm.append(
        summary="（自律の思考メモ） 深夜の独り言",
        kind="agent_private_reflection",
        source="experience_mirror",
        person_id="ma",
        ts="2026-06-16T21:00:00+09:00",
        timezone="Asia/Tokyo",
        metadata={"emotion_tag": "neutral", "importance": 3},
    )

    with (
        patch(
            "presence_ui.services.dreaming.http_remember",
            return_value={"ok": True, "memory_id": "m1"},
        ) as remember_mock,
        patch(
            "presence_ui.services.dreaming.http_consolidate",
            return_value={"ok": True, "stats": {}},
        ),
    ):
        result = run_dreaming_job(person_id="ma", local_day="2026-06-16", force=True)

    assert result.remembered_count == 1
    assert remember_mock.call_count == 1


def test_run_dreaming_job_promotes_and_marks(dream_env):
    _db_path, db, getter = dream_env
    stm = StmStore(db)
    entry = stm.append(
        summary="まーと散歩の約束をした",
        kind="episode_close",
        source="episode_summary",
        person_id="ma",
        session_id="sess_dream_api",
        ts="2026-06-16T20:00:00+09:00",
        timezone="Asia/Tokyo",
    )

    with (
        patch(
            "presence_ui.services.dreaming.http_remember",
            return_value={"ok": True, "memory_id": "m1"},
        ),
        patch(
            "presence_ui.services.dreaming.http_consolidate",
            return_value={"ok": True, "stats": {"replayed": 2}},
        ),
    ):
        result = run_dreaming_job(person_id="ma", local_day=entry.local_day, force=True)

    assert result.ok is True
    assert result.skipped is False
    assert result.remembered_count == 1
    assert result.stm_marked == 1
    assert result.consolidate_ok is True
    assert "[dream_digest]" in result.digest_summary
    assert stm.count_undreamed(person_id="ma", local_day=entry.local_day) == 0
    getter().self_narrative.append_daybook.assert_called_once_with(day=entry.local_day)
    digest = load_dream_digest()
    assert digest is not None
    assert digest.remembered_count == 1


def test_stm_dream_api(dream_env, monkeypatch):
    db_path, db, getter = dream_env
    stm = StmStore(db)
    entry = stm.append(
        summary="体調の話をした",
        kind="episode_close",
        source="episode_summary",
        person_id="ma",
        session_id="sess_api",
        ts="2026-06-16T21:00:00+09:00",
        timezone="Asia/Tokyo",
    )

    app = create_app()
    monkeypatch.setattr("presence_ui.deps.get_stores", getter)
    monkeypatch.setattr("presence_ui.services.dreaming.get_stores", getter)
    with TestClient(app) as client:
        with (
            patch("presence_ui.services.dreaming.http_remember", return_value={"ok": True}),
            patch(
                "presence_ui.services.dreaming.http_consolidate",
                return_value={"ok": True, "stats": {}},
            ),
        ):
            response = client.post(
                "/api/v1/stm/dream",
                json={"person_id": "ma", "local_day": entry.local_day, "force": True},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["stm_marked"] == 1

        digest = client.get("/api/v1/stm/dream-digest")
        assert digest.status_code == 200
        assert digest.json()["digest"] is not None
