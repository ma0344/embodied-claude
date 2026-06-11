"""Chat send interaction tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.schemas import ChatMessage, ChatSendResponse
from presence_ui.services.interact import handle_chat_send


@pytest.mark.asyncio
async def test_handle_chat_send_generates_reply() -> None:
    fake_reply = "まー、おはよう。うちも元気やで。"
    fake_ctx = MagicMock(compact_prompt_block="test context")
    fake_plan = MagicMock(primary_move="answer_directly", why_this_move="test")

    with (
        patch("presence_ui.services.interact.get_session", return_value=object()),
        patch(
            "presence_ui.services.interact._compose_and_plan",
            return_value=(fake_ctx, fake_plan),
        ),
        patch(
            "presence_ui.services.interact.generate_koyori_reply",
            new_callable=AsyncMock,
            return_value=fake_reply,
        ),
        patch(
            "presence_ui.services.interact._ingest_human_message",
            return_value="evt_user_test",
        ),
        patch(
            "presence_ui.services.interact._ingest_koyori_message",
            return_value="evt_koyori_test",
        ),
        patch("presence_ui.services.interact._record_response"),
        patch("presence_ui.services.interact.touch_session"),
    ):
        result = await handle_chat_send(
            message="おはよう",
            session_id="room_test123",
            person_id="ma",
        )

    assert result.user_message.sender == "ma"
    assert result.user_message.message == "おはよう"
    assert result.koyori_message is not None
    assert result.koyori_message.sender == "koyori"
    assert result.koyori_message.message == fake_reply
    assert result.silent is False


@pytest.mark.asyncio
async def test_handle_chat_send_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        await handle_chat_send(message="   ", session_id="room_test123", person_id="ma")


def test_chat_send_endpoint_validation() -> None:
    client = TestClient(create_app())
    response = client.post("/api/chat", json={"message": "", "requestId": "req-empty"})
    assert response.status_code == 400


@pytest.mark.skip(reason="Gateway forwards /api/chat to Claude Code backend")
def test_chat_send_endpoint_mocked() -> None:
    client = TestClient(create_app())
    fake = ChatSendResponse(
        session_id="room_test123",
        user_message=ChatMessage(
            sender="ma",
            message="test",
            timestamp="2026-06-10T12:00:00+00:00",
            message_id="evt_user",
            session_id="room_test123",
        ),
        koyori_message=ChatMessage(
            sender="koyori",
            message="うん、聞いてるで",
            timestamp="2026-06-10T12:00:01+00:00",
            message_id="evt_koyori",
            session_id="room_test123",
        ),
        silent=False,
        plan_move="answer_directly",
    )

    with patch(
        "presence_ui.main.handle_chat_send",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        response = client.post(
            "/api/v1/chat/send",
            json={"message": "test", "session_id": "room_test123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_message"]["sender"] == "ma"
    assert data["koyori_message"]["sender"] == "koyori"
