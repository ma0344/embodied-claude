"""GW Claude --resume and post-chat internal turn."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract

from presence_ui.gateway.gw_resume import run_post_chat_internal_turn
from presence_ui.gateway.gw_silent import run_silent_internal_turn_async


def _ctx(*, session_id: str | None = "sess-abc") -> InteractionContext:
    return InteractionContext(
        ts="2026-06-29T01:00:00+00:00",
        local_time="2026-06-29T10:00:00+09:00",
        timezone="Asia/Tokyo",
        session_id=session_id,
        agent_state={
            "ts": "2026-06-29T01:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": None,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="chat",
        compact_prompt_block="",
    )


@pytest.mark.asyncio
async def test_run_silent_internal_turn_async_uses_claude_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GW_S1_CLAUDE", "1")

    async def fake_chat(**kwargs):
        assert kwargs["session_id"] == "sess-abc"
        assert kwargs["is_new"] is False
        assert "[Gateway internal" in kwargs["config"].append_system_prompt
        yield {"event": "text", "data": {"content": '{"hook":"x","felt":"y","next_move":"advance"}'}}

    mock_agent = MagicMock()
    mock_agent.chat = fake_chat
    mock_agent.cancel = AsyncMock()

    with patch(
        "claude_code_server.agent.ClaudeAgent",
        return_value=mock_agent,
    ):
        text = await run_silent_internal_turn_async(
            task="[gateway_internal] pause reflect",
            session_id="sess-abc",
        )

    assert text is not None
    assert "hook" in text
    mock_agent.cancel.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_silent_internal_turn_async_no_session_uses_lm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GW_S1_CLAUDE", "1")

    with (
        patch(
            "presence_ui.gateway.gw_silent.lm_studio_available",
            return_value=True,
        ),
        patch(
            "presence_ui.gateway.gw_silent.run_classifier_turn",
            return_value='{"hook":"lm","felt":"flat","next_move":"advance"}',
        ) as classifier,
    ):
        text = await run_silent_internal_turn_async(
            task="task",
            session_id=None,
        )

    classifier.assert_called_once()
    assert text is not None
    assert "lm" in text


@pytest.mark.asyncio
async def test_post_chat_internal_skips_without_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PRESENCE_GW_AFTER_CHAT", raising=False)
    monkeypatch.delenv("PRESENCE_GW_S1_CLAUDE", raising=False)

    with patch(
        "presence_ui.gateway.direct_actions.reflect_on_aozora_passage_direct",
    ) as reflect:
        await run_post_chat_internal_turn(
            session_id="sess-1",
            person_id="ma",
            ctx=_ctx(),
            plan=MagicMock(),
            reply_text="おはよう",
        )

    reflect.assert_not_called()


@pytest.mark.asyncio
async def test_post_chat_internal_runs_reflect_on_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GW_AFTER_CHAT", "1")
    monkeypatch.setenv("PRESENCE_GW_S1_CLAUDE", "1")

    from presence_ui.gateway.aozora import ReadingState
    from presence_ui.gateway import direct_actions

    state = ReadingState(
        phase="pause",
        last_passage={
            "title": "羅生門",
            "author": "芥川",
            "text": "下人は。",
            "passage_index": 1,
            "total_passages": 40,
        },
        sections_this_session=1,
        last_reflected_passage_index=-1,
    )

    with (
        patch(
            "presence_ui.gateway.gw_resume.load_reading_state",
            return_value=state,
        ),
        patch(
            "presence_ui.gateway.gw_resume.get_stores",
            return_value=MagicMock(),
        ),
        patch(
            "presence_ui.gateway.direct_actions.reflect_on_aozora_passage_direct",
            return_value=direct_actions.DirectActionOutcome(
                ok=True,
                action="reflect_on_aozora_passage",
                summary="saved",
            ),
        ) as reflect,
    ):
        await run_post_chat_internal_turn(
            session_id="sess-resume",
            person_id="ma",
            ctx=_ctx(session_id="old-wrong"),
            plan=MagicMock(),
            reply_text="うん",
        )

    reflect.assert_called_once()
    call_ctx = reflect.call_args.kwargs["ctx"]
    assert call_ctx.session_id == "sess-resume"
