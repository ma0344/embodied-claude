"""Tests for vision prefetch note formatting."""

from unittest.mock import patch

from presence_ui.gateway.see_intent import SeeIntent
from presence_ui.services.vision_capture import (
    VisionCaptureResult,
    remember_vision_capture,
    vision_prefetch_note,
)


def test_vision_prefetch_note_success() -> None:
    result = VisionCaptureResult(
        ok=True,
        mode="current",
        label="--- Current View ---",
        mcp_text="--- Current View ---\n=== VISION_CAPTION ===\nDesk and window.\n=== END ===",
        caption="Desk and window.",
        file_path="/tmp/cap.jpg",
        remember_ok=True,
    )
    note = vision_prefetch_note(
        result,
        intent=SeeIntent(mode="current", reason="user asked what is visible"),
        user_text="何が見える？",
    )
    assert "[vision_prefetch]" in note
    assert "VISION_CAPTION" in note
    assert "Do NOT call mcp__wifi-cam__see" in note
    assert "remember=ok" in note


def test_vision_prefetch_note_failure() -> None:
    result = VisionCaptureResult(
        ok=False,
        mode="window",
        label="window",
        mcp_text="",
        caption=None,
        file_path=None,
        error="TimeoutError",
    )
    note = vision_prefetch_note(
        result,
        intent=SeeIntent(mode="window", reason="outside"),
        user_text="外見て",
    )
    assert "error=TimeoutError" in note
    assert "guess the scene" in note.lower()


def test_remember_vision_capture_skipped_by_default(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_VISION_LTM_REMEMBER", raising=False)
    result = VisionCaptureResult(
        ok=True,
        mode="current",
        label="--- Current View ---",
        mcp_text="=== VISION_CAPTION ===\ndesk\n=== END ===",
        caption="desk",
        file_path="/tmp/cap.jpg",
    )
    with patch(
        "presence_ui.services.vision_capture.persist_remember_intent"
    ) as persist:
        assert remember_vision_capture(result) is False
        persist.assert_not_called()
    assert result.remember_ok is False


def test_remember_vision_capture_writes_when_env_on(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_VISION_LTM_REMEMBER", "1")
    result = VisionCaptureResult(
        ok=True,
        mode="current",
        label="--- Current View ---",
        mcp_text="=== VISION_CAPTION ===\ndesk\n=== END ===",
        caption="desk",
        file_path="/tmp/cap.jpg",
    )

    class _Ok:
        ok = True

    with patch(
        "presence_ui.services.vision_capture.persist_remember_intent",
        return_value=_Ok(),
    ) as persist:
        assert remember_vision_capture(result) is True
        persist.assert_called_once()
    assert result.remember_ok is True
