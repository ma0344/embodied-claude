"""MEM-2b pre-dream episode closure tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from social_core import SocialDB

from presence_ui.schemas import (
    ChatMessage,
    NativeSessionListResponse,
    NativeSessionMessagesResponse,
    NativeSessionSummary,
)
from presence_ui.services import stm_episode


@pytest.mark.asyncio
async def test_close_open_native_episodes_before_dream_closes_today(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    db = SocialDB(tmp_path / "social.db")
    stores = MagicMock()
    stores.db = db
    stores.policy_timezone = "Asia/Tokyo"
    monkeypatch.setattr(stm_episode, "get_stores", lambda: stores)

    session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    today = "2026-06-18T20:00:00+09:00"
    list_response = NativeSessionListResponse(
        sessions=[
            NativeSessionSummary(
                session_id=session_id,
                title="test",
                preview="hi",
                updated_at=today,
                message_count=2,
            )
        ]
    )
    messages = NativeSessionMessagesResponse(
        session_id=session_id,
        messages=[
            ChatMessage(sender="koyori", message="まー、聞いてる？", timestamp=today),
            ChatMessage(sender="ma", message="うん", timestamp=today),
        ],
    )

    monkeypatch.setattr(
        "presence_ui.services.native_history.list_native_sessions",
        lambda **kwargs: list_response,
    )
    monkeypatch.setattr(
        "presence_ui.services.native_history.fetch_native_session_messages",
        lambda sid: messages if sid == session_id else None,
    )

    async def fake_summarize(turns, *, use_llm=None):
        return "まーと短くやり取りした。"

    monkeypatch.setattr(stm_episode, "summarize_episode_for_stm", fake_summarize)

    results = await stm_episode.close_open_native_episodes_before_dream(person_id="ma")
    assert len(results) == 1
    assert results[0]["session_id"] == session_id
    assert results[0]["closed"] is True
