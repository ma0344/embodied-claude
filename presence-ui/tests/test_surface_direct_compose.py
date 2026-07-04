"""Surface Direct compose flags."""

from __future__ import annotations

from presence_ui.gateway.surface_direct import compose_omit_session_transcript_in_compact


def test_surface_direct_includes_transcript_in_compact() -> None:
    assert compose_omit_session_transcript_in_compact("sess-1") is False


def test_legacy_cc_omits_transcript_when_session(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_SURFACE_USE_CLAUDE", "1")
    assert compose_omit_session_transcript_in_compact("sess-1") is True


def test_no_session_never_omits_via_resume_flag() -> None:
    assert compose_omit_session_transcript_in_compact(None) is False
    assert compose_omit_session_transcript_in_compact("") is False
