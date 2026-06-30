"""GW-S2 ol_gate must not pass thread-bound stores into asyncio.to_thread."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway.ol_gate import try_ol_gate_after_ingest


@pytest.mark.asyncio
async def test_try_ol_gate_fetches_departures_on_ingest_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_stores = MagicMock()
    fetch_threads: list[int] = []
    classify_threads: list[int] = []

    def fake_fetch(stores, *, person_id: str):
        fetch_threads.append(threading.get_ident())
        assert stores is main_stores
        return ()

    def fake_classify(**kwargs: object):
        classify_threads.append(threading.get_ident())
        return None

    async def passthrough_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("presence_ui.gateway.ol_gate.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol_gate.should_run_ol_gate", lambda _t: True)
    monkeypatch.setattr(
        "presence_ui.gateway.temp_c_staged.gw_s2_staged_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.stage1_context.fetch_stage1_departure_hints",
        fake_fetch,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.temp_c_staged.run_staged_classify",
        fake_classify,
    )
    monkeypatch.setattr(asyncio, "to_thread", passthrough_to_thread)

    ingest_tid = threading.get_ident()
    await try_ol_gate_after_ingest(
        main_stores,
        person_id="ma",
        text="ちょっと昼寝してくる",
        ts="2026-06-30T14:46:00+09:00",
        source_event_id="evt-1",
    )

    assert fetch_threads == [ingest_tid]
    assert classify_threads == [ingest_tid]
