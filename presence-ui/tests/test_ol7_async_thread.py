"""OL7 async entry must use per-thread get_stores()."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway.ol7_flow import Ol7IngestResult, try_ol7_after_ingest
from presence_ui.gateway.ol7_return_signal import Ol7Classification


@pytest.mark.asyncio
async def test_try_ol7_uses_get_stores_in_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    main_stores = MagicMock()
    worker_stores = MagicMock()
    loop = MagicMock()
    loop.id = "loop_soccer"
    loop.topic = "サッカー"
    loop.detail = {}
    worker_stores.relationship.list_open_loops.return_value = [loop]

    captured: dict[str, object] = {}

    def fake_apply(stores, **kwargs: object) -> Ol7IngestResult:
        captured["stores"] = stores
        return Ol7IngestResult(route="no_op")

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.apply_ol7_after_ingest", fake_apply)
    monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)

    with patch("presence_ui.deps.get_stores", return_value=worker_stores):
        await try_ol7_after_ingest(
            person_id="ma",
            text="試合、見終わった",
            ts="2026-06-30T09:31:00+09:00",
            source_event_id="evt-1",
        )

    assert captured["stores"] is worker_stores
    assert captured["stores"] is not main_stores
