"""Kiosk routing for MCP say tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tts_mcp.kiosk_routing import (
    delegate_say_to_kiosk,
    fetch_kiosk_primary_active,
    should_route_local_say_to_kiosk,
)


def test_fetch_kiosk_primary_active_true() -> None:
    payload = json.dumps({"kiosk_primary_enabled": True, "kiosk_primary_active": True}).encode()

    class FakeResponse:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("tts_mcp.kiosk_routing.urllib.request.urlopen", return_value=FakeResponse()):
        assert fetch_kiosk_primary_active() is True


def test_should_route_when_kiosk_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_SAY_KIOSK_ROUTING", "1")
    with patch("tts_mcp.kiosk_routing.fetch_kiosk_primary_active", return_value=True):
        assert should_route_local_say_to_kiosk(play_audio=True, use_local=True) is True
    with patch("tts_mcp.kiosk_routing.fetch_kiosk_primary_active", return_value=False):
        assert should_route_local_say_to_kiosk(play_audio=True, use_local=True) is False


def test_delegate_say_to_kiosk_posts_text() -> None:
    captured: dict[str, bytes] = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = request.data
        return MagicMock(
            __enter__=lambda s: s,
            __exit__=lambda *a: False,
            read=lambda: b'{"ok": true}',
        )

    with patch("tts_mcp.kiosk_routing.urllib.request.urlopen", fake_urlopen):
        ok, detail, listeners = delegate_say_to_kiosk("こんにちは")
    assert ok is True
    assert listeners == 0
    assert "/api/v1/tts/room-say" in captured["url"]
    assert b"\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf" in captured["body"]
