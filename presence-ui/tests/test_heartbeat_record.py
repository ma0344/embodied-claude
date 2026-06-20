"""Tests for chat turn finalization / experience summaries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from presence_ui.heartbeat.record import (
    _agent_response_experience_summary,
    finalize_chat_turn,
)


def test_agent_response_experience_summary_uses_user_utterance() -> None:
    summary = _agent_response_experience_summary(
        user_text="こんにちは",
        reply="えっ、雨？急に来たん？",
    )
    assert summary == "Replied to まー (こんにちは)"


def test_finalize_chat_turn_stores_audit_summary_not_verbatim_reply() -> None:
    stores = MagicMock()
    with (
        patch("presence_ui.heartbeat.record.get_stores", return_value=stores),
        patch("presence_ui.heartbeat.record.ingest_agent_turn"),
        patch("presence_ui.heartbeat.record.apply_pulse_schedule"),
        patch(
            "presence_ui.heartbeat.interpretation_shift.record_interpretation_shifts",
            return_value=[],
        ),
    ):
        finalize_chat_turn(
            person_id="ma",
            session_id="sess-1",
            user_text="雨降ってきた？",
            reply_text="えっ、雨？急に来たん？さっきまで晴れてたのに。",
            plan=None,
            ctx=None,
        )
    payload = stores.orchestrator.record_agent_experience.call_args[0][0]
    assert payload.summary == "Replied to まー (雨降ってきた？)"
    assert "急に来た" not in payload.summary
