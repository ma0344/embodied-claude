"""Unit tests for BIO HTTP handler helpers on MemoryServer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_mcp.server import MemoryMCPServer


@pytest.mark.asyncio
async def test_http_recall_divergent_requires_context() -> None:
    server = MemoryMCPServer()
    server._memory_store = MagicMock()
    result = await server._http_recall_divergent({})
    assert result["ok"] is False
    assert "context" in result["error"]


@pytest.mark.asyncio
async def test_http_recall_divergent_maps_items() -> None:
    server = MemoryMCPServer()
    memory = MagicMock()
    memory.id = "m1"
    memory.content = "hello world"
    memory.emotion = "curious"
    memory.category = "daily"
    hit = MagicMock(memory=memory, distance=0.2)
    server._memory_store = MagicMock()
    server._memory_store.recall_divergent = AsyncMock(return_value=([hit], {"branches": 1}))
    result = await server._http_recall_divergent({"context": "test"})
    assert result["ok"] is True
    assert result["items"][0]["content"] == "hello world"


@pytest.mark.asyncio
async def test_http_consolidate_returns_stats() -> None:
    server = MemoryMCPServer()
    server._memory_store = MagicMock()
    server._memory_store.consolidate_memories = AsyncMock(return_value={"replayed": 3})
    result = await server._http_consolidate({})
    assert result["ok"] is True
    assert result["stats"]["replayed"] == 3
