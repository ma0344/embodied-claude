"""OL7 gateway routing and pending_check integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from presence_ui.gateway.ol7_flow import (
    Ol7IngestResult,
    apply_ol7_after_ingest,
    route_ol7_classification,
)
from presence_ui.gateway.ol7_return_signal import Ol7Classification


def test_route_return_signal_to_pending() -> None:
    assert route_ol7_classification(
        signal="return_signal",
        close_loop_ids=("loop_walk",),
        confidence=0.9,
    ) == "pending_confirm"


def test_route_explicit_high_conf_to_immediate() -> None:
    assert route_ol7_classification(
        signal="explicit_completion",
        close_loop_ids=("loop_nap",),
        confidence=0.95,
    ) == "immediate_close"


def test_route_explicit_low_conf_to_pending() -> None:
    assert route_ol7_classification(
        signal="explicit_completion",
        close_loop_ids=("loop_nap",),
        confidence=0.5,
    ) == "pending_confirm"


def test_apply_ol7_sets_pending_on_return_signal(monkeypatch) -> None:
    stores = MagicMock()
    loop = MagicMock()
    loop.id = "loop_walk"
    loop.topic = "散歩に行く"
    loop.detail = {"utterance": "散歩に行く"}
    stores.relationship.list_open_loops.return_value = [loop]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        return Ol7Classification(
            utterance="ただいま",
            signal="return_signal",
            close_loop_ids=("loop_walk",),
            completion_summary="散歩から帰宅",
            confidence=0.9,
            reason="test",
        )

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="ただいま",
        ts="2026-06-29T12:00:00+09:00",
        source_event_id="evt-1",
    )
    assert result == Ol7IngestResult(route="pending_confirm", pending_loop_id="loop_walk")
    stores.relationship.set_ol7_pending_candidate.assert_called_once()
    stores.relationship.close_open_loops_by_ids.assert_not_called()


def test_apply_ol7_skips_when_pending_awaiting_confirm(monkeypatch) -> None:
    stores = MagicMock()
    loop = MagicMock()
    loop.id = "loop_walk"
    loop.topic = "散歩に行く"
    loop.detail = {"pending_check": {"asked_at": "2026-06-29T12:01:00+09:00"}}
    stores.relationship.list_open_loops.return_value = [loop]

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="うん、気持ちよかった",
        ts="2026-06-29T12:02:00+09:00",
        source_event_id="evt-2",
    )
    assert result.route == "no_op"
