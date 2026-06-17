"""Tests for memory HTTP BIO helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from presence_ui.gateway.memory_http import http_consolidate, http_recall_divergent


def test_http_recall_divergent_parses_items() -> None:
    body = json.dumps({"ok": True, "items": [{"content": "branch", "score": 0.8}]}).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    with patch("presence_ui.gateway.memory_http.urllib.request.urlopen", return_value=resp):
        items = http_recall_divergent(context="こより", n_results=3)
    assert len(items) == 1
    assert items[0]["content"] == "branch"


def test_http_consolidate_parses_ok() -> None:
    body = json.dumps({"ok": True, "stats": {"replayed": 2}}).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    with patch("presence_ui.gateway.memory_http.urllib.request.urlopen", return_value=resp):
        result = http_consolidate()
    assert result["ok"] is True
    assert result["stats"]["replayed"] == 2
