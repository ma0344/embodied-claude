"""Outbound push — ntfy / Pushover on enqueue (A4g)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from social_core import SocialDB
from social_core.events import EventStore

from presence_ui.deps import PresenceStores
from presence_ui.services.outbound import enqueue_outbound_nudge
from presence_ui.services.outbound_push import send_outbound_push


def _minimal_stores(db: SocialDB) -> PresenceStores:
    return PresenceStores(
        db=db,
        events=EventStore(db=db),
        social_state=MagicMock(),
        relationship=MagicMock(),
        joint_attention=MagicMock(),
        boundary=MagicMock(),
        self_narrative=MagicMock(),
        orchestrator=MagicMock(),
        policy_timezone="Asia/Tokyo",
    )


def test_send_outbound_push_skips_without_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_OUTBOUND_NTFY_URL", raising=False)
    monkeypatch.delenv("PRESENCE_OUTBOUND_PUSHOVER_TOKEN", raising=False)
    monkeypatch.delenv("PRESENCE_OUTBOUND_PUSHOVER_USER", raising=False)
    ok, detail = send_outbound_push(text="まー、おる？")
    assert ok is False
    assert detail == "no push targets configured"


def test_send_outbound_push_ntfy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "https://ntfy.sh/test-topic")
    calls: list[tuple[str, str, str]] = []

    def fake_ntfy(url: str, *, title: str, message: str, timeout: float = 8.0) -> None:
        calls.append((url, title, message))

    monkeypatch.setattr("presence_ui.services.outbound_push._post_ntfy", fake_ntfy)
    ok, detail = send_outbound_push(text="まー、おる？")
    assert ok is True
    assert "ntfy:ok" in detail
    assert calls == [("https://ntfy.sh/test-topic", "Koyori", "まー、おる？")]


def test_enqueue_triggers_push(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "https://ntfy.sh/test-topic")
    pushed: list[str] = []

    def fake_push(*, text: str, title: str = "こより") -> tuple[bool, str]:
        pushed.append(text)
        return True, "ntfy:ok"

    monkeypatch.setattr("presence_ui.services.outbound_push.send_outbound_push", fake_push)
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    result = enqueue_outbound_nudge(stores, person_id="ma", text="Push テスト")
    assert result.ok is True
    assert pushed == ["Push テスト"]
