"""Tests for stdio → HTTP daemon delegation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from memory_mcp.http_delegate import (
    daemon_healthy,
    format_recall_items,
    format_remember_result,
    http_recall,
    http_remember,
    stdio_delegate_enabled,
)


def test_stdio_delegate_enabled_defaults_on() -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert stdio_delegate_enabled() is True


def test_stdio_delegate_enabled_can_disable() -> None:
    with patch.dict("os.environ", {"MEMORY_STDIO_DELEGATE_HTTP": "0"}):
        assert stdio_delegate_enabled() is False


def test_daemon_healthy_delegates_to_probe() -> None:
    with patch("memory_mcp.http_delegate.probe_health", return_value=True) as probe:
        assert daemon_healthy(port=18900) is True
        probe.assert_called_once()


def test_http_recall_parses_list_payload() -> None:
    payload = [{"content": "hello", "emotion": "happy", "score": 0.9}]
    body = json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    with patch("memory_mcp.http_delegate.urllib.request.urlopen", return_value=resp):
        items = http_recall(query="test", n=2)
    assert items == payload


def test_http_remember_parses_ok_payload() -> None:
    body = json.dumps({"ok": True, "id": "mem-1"}).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    with patch("memory_mcp.http_delegate.urllib.request.urlopen", return_value=resp):
        data = http_remember(content="saved fact")
    assert data["ok"] is True
    assert data["id"] == "mem-1"


def test_format_recall_items_empty() -> None:
    assert "No relevant memories" in format_recall_items([])


def test_format_remember_result_error() -> None:
    text = format_remember_result({"ok": False, "error": "boom"}, content="x")
    assert "Error: boom" in text


def test_format_remember_result_ok() -> None:
    text = format_remember_result({"ok": True, "id": "abc"}, content="fact")
    assert "Memory saved via HTTP daemon" in text
    assert "abc" in text
