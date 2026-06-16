"""Gateway chat stream wrapper."""

from __future__ import annotations

import json

import pytest

from presence_ui.gateway import chat_stream
from presence_ui.gateway.social_chat import ChatInterceptResult


@pytest.mark.asyncio
async def test_stream_gateway_chat_emits_progress_and_forwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enriched = {"message": "hi", "appendSystemPrompt": "[ctx]"}

    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        chat_stream,
        "intercept_chat_request_async",
        AsyncMock(
            return_value=ChatInterceptResult(forward=True, payload=enriched, user_text="hi")
        ),
    )

    async def fake_passthrough(**_kwargs):
        yield b'{"type":"done"}\n'

    monkeypatch.setattr(chat_stream, "stream_passthrough_chat", fake_passthrough)

    chunks: list[dict] = []
    async for raw in chat_stream.stream_gateway_chat(payload={"message": "hi"}):
        chunks.append(json.loads(raw.decode("utf-8")))

    assert chunks[0]["type"] == "room_progress"
    assert chunks[0]["phase"] == "composing"
    assert any(c.get("type") == "room_progress" and c.get("phase") == "replying" for c in chunks)
    assert chunks[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_gateway_chat_silent_skips_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        chat_stream,
        "intercept_chat_request_async",
        AsyncMock(
            return_value=ChatInterceptResult(forward=False, plan_move="stay_silent")
        ),
    )
    passthrough = AsyncMock()
    monkeypatch.setattr(chat_stream, "stream_passthrough_chat", passthrough)

    chunks: list[dict] = []
    async for raw in chat_stream.stream_gateway_chat(payload={"message": "shh"}):
        chunks.append(json.loads(raw.decode("utf-8")))

    passthrough.assert_not_called()
    assert any(c.get("type") == "social_silent" for c in chunks)
