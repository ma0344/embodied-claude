"""Tests for HTTP sidecar helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from memory_mcp.http_sidecar import (
    find_listening_pid,
    is_address_in_use,
    probe_health,
    reclaim_stale_listener,
)


def test_is_address_in_use_windows_errno() -> None:
    assert is_address_in_use(OSError(10048, "Only one usage of each socket address"))


def test_is_address_in_use_linux_errno() -> None:
    assert is_address_in_use(OSError(98, "Address already in use"))


def test_find_listening_pid_parses_netstat() -> None:
    sample = """
  TCP    127.0.0.1:18900        0.0.0.0:0              LISTENING       4242
"""
    with patch("memory_mcp.http_sidecar.subprocess.check_output", return_value=sample):
        with patch("memory_mcp.http_sidecar.sys.platform", "win32"):
            assert find_listening_pid(18900) == 4242


def test_probe_health_accepts_ok_payload() -> None:
    body = json.dumps({"ok": True, "ready": False}).encode("utf-8")
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    with patch("memory_mcp.http_sidecar.urllib.request.urlopen", return_value=resp):
        assert probe_health(18900, timeout_sec=1.0) is True


def test_probe_health_rejects_timeout() -> None:
    with patch(
        "memory_mcp.http_sidecar.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    ):
        assert probe_health(18900, timeout_sec=0.1) is False


def test_reclaim_stale_listener_kills_unhealthy_peer() -> None:
    with patch("memory_mcp.http_sidecar.find_listening_pid", return_value=999):
        with patch("memory_mcp.http_sidecar.probe_health", return_value=False):
            with patch("memory_mcp.http_sidecar.kill_process_tree", return_value=True) as kill:
                assert reclaim_stale_listener(18900) is True
                kill.assert_called_once_with(999)


def test_reclaim_stale_listener_keeps_healthy_peer() -> None:
    with patch("memory_mcp.http_sidecar.find_listening_pid", return_value=999):
        with patch("memory_mcp.http_sidecar.probe_health", return_value=True):
            with patch("memory_mcp.http_sidecar.kill_process_tree") as kill:
                assert reclaim_stale_listener(18900) is False
                kill.assert_not_called()
