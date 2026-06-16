"""Outbound push — ntfy / Pushover on enqueue (A4g)."""

from __future__ import annotations

from pathlib import Path
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
    monkeypatch.setenv("PRESENCE_OUTBOUND_WIN_TOAST", "0")
    ok, detail = send_outbound_push(text="まー、おる？")
    assert ok is False
    assert detail == "no push targets configured"


def test_send_outbound_push_ntfy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "https://ntfy.sh/test-topic")
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_CLICK_URL", "http://127.0.0.1:8090/")
    monkeypatch.setenv("PRESENCE_OUTBOUND_WIN_TOAST", "0")
    calls: list[tuple[str, str, str, str | None]] = []

    def fake_ntfy(
        url: str,
        *,
        title: str,
        message: str,
        click_url: str | None = None,
        timeout: float = 8.0,
    ) -> None:
        calls.append((url, title, message, click_url))

    monkeypatch.setattr("presence_ui.services.outbound_push._post_ntfy", fake_ntfy)
    ok, detail = send_outbound_push(text="まー、おる？")
    assert ok is True
    assert "ntfy:ok" in detail
    assert calls == [
        ("https://ntfy.sh/test-topic", "Koyori", "まー、おる？", "http://127.0.0.1:8090/")
    ]


def test_send_outbound_push_win_toast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_OUTBOUND_NTFY_URL", raising=False)
    monkeypatch.setenv("PRESENCE_OUTBOUND_WIN_TOAST", "1")
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_CLICK_URL", "http://127.0.0.1:8090/")
    calls: list[tuple[str, str, str]] = []

    def fake_win(*, title: str, message: str, click_url: str) -> None:
        calls.append((title, message, click_url))

    monkeypatch.setattr("presence_ui.services.outbound_push._win_toast_script", lambda: Path("x.ps1"))
    monkeypatch.setattr("presence_ui.services.outbound_push.sys.platform", "win32")
    monkeypatch.setattr("presence_ui.services.outbound_push._show_win_toast", fake_win)
    ok, detail = send_outbound_push(text="まー、おる？")
    assert ok is True
    assert "win-toast:ok" in detail
    assert calls == [("Koyori", "まー、おる？", "http://127.0.0.1:8090/")]


def test_enqueue_triggers_push(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "https://ntfy.sh/test-topic")
    pushed: list[str] = []

    def fake_push(*, text: str, title: str = "こより", **kwargs) -> tuple[bool, str]:
        pushed.append(text)
        return True, "ntfy:ok"

    monkeypatch.setattr("presence_ui.services.outbound_push.send_outbound_push", fake_push)
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    result = enqueue_outbound_nudge(stores, person_id="ma", text="Push テスト")
    assert result.ok is True
    assert pushed == ["Push テスト"]
