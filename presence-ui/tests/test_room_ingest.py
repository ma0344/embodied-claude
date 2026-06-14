"""room_ingest — human open loops + agent transcript persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from relationship_mcp.schemas import DismissOutcome

from presence_ui.gateway import room_ingest


@pytest.fixture
def mock_stores(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stores = MagicMock()
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-42"}
    monkeypatch.setattr(room_ingest, "get_stores", lambda: stores)
    return stores


def test_ingest_human_turn_updates_open_loops(mock_stores: MagicMock) -> None:
    mock_stores.relationship.note_human_utterance_for_loops.return_value = DismissOutcome()
    event_id, outcome = room_ingest.ingest_human_turn(
        person_id="ma",
        session_id="sess-1",
        text="PR review 明日やるの覚えといて",
        ts="2026-06-14T03:00:00+00:00",
    )
    assert event_id == "evt-42"
    assert outcome.closed_loops == []
    mock_stores.relationship.note_human_utterance_for_loops.assert_called_once()


def test_ingest_human_turn_returns_dismiss_outcome(mock_stores: MagicMock) -> None:
    mock_stores.relationship.note_human_utterance_for_loops.return_value = DismissOutcome(
        closed_loops=["pr review"],
        cancelled_commitments=["PR review reminder"],
    )
    _event_id, outcome = room_ingest.ingest_human_turn(
        person_id="ma",
        session_id="sess-1",
        text="PRのレビューは中止。その予定は忘れて。",
    )
    assert outcome.closed_loops == ["pr review"]
    assert outcome.cancelled_commitments == ["PR review reminder"]


def test_ingest_agent_turn_skips_open_loops(mock_stores: MagicMock) -> None:
    room_ingest.ingest_agent_turn(
        person_id="ma",
        session_id="sess-1",
        text="了解やで",
        ts="2026-06-14T03:00:01+00:00",
    )
    mock_stores.relationship.note_human_utterance_for_loops.assert_not_called()
