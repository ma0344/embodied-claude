"""Tests for OL5-c completion verb expansion."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from presence_ui.gateway.ol5_completion_verbs import (
    enrich_decision_completion_verbs,
    merge_completion_verbs,
    parse_completion_verbs_response,
)
from presence_ui.gateway.ol_gate import OlGateGatewayDecision


def test_merge_completion_verbs_dedup_and_cap() -> None:
    merged = merge_completion_verbs(
        ("作った", "できた"),
        ["できた", "提出した", "送った", "出した", "a", "b", "c", "d", "e", "f", "g"],
    )
    assert merged[0] == "作った"
    assert "提出した" in merged
    assert len(merged) == 10


def test_parse_completion_verbs_response() -> None:
    verbs = parse_completion_verbs_response(
        '{"completion_verbs":["提出した","送った","作った"]}'
    )
    assert verbs == ("提出した", "送った", "作った")


def test_enrich_decision_merges_llm_verbs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL5_C_ENABLED", "1")
    decision = OlGateGatewayDecision(
        utterance="2026年6月29日 県に提出する書類 作る",
        utterance_kind="future_commitment",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月29日 県に提出する書類 作る",
        action_terms=("県に提出する書類",),
        completion_verbs=("作った", "できた", "完成した"),
        resolved_date="2026-06-29",
        needs_date_confirmation=False,
        ambiguous_phrases=(),
        original_topic=None,
        detail={
            "object_phrase": "県に提出する書類",
            "action_phrase": "作る",
            "completion_verbs": ["作った", "できた", "完成した"],
        },
    )
    llm_json = '{"completion_verbs":["提出した","送った","出した"]}'
    with patch(
        "presence_ui.gateway.ol5_completion_verbs.run_classifier_turn",
        return_value=llm_json,
    ):
        enriched = enrich_decision_completion_verbs(decision)
    assert "提出した" in enriched.completion_verbs
    assert "作った" in enriched.completion_verbs
    assert enriched.detail.get("ol5_c") is True


def test_enrich_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL5_C_ENABLED", "0")
    decision = OlGateGatewayDecision(
        utterance="x",
        utterance_kind="future_commitment",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="角煮 作る",
        action_terms=("角煮",),
        completion_verbs=("作った",),
        resolved_date=None,
        needs_date_confirmation=False,
        ambiguous_phrases=(),
        original_topic=None,
        detail={"action_phrase": "作る"},
    )
    with patch(
        "presence_ui.gateway.ol5_completion_verbs.run_classifier_turn",
    ) as mock_llm:
        enriched = enrich_decision_completion_verbs(decision)
    mock_llm.assert_not_called()
    assert enriched.completion_verbs == ("作った",)
