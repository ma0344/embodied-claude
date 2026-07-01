"""Tests for GAPI-2r Stage1 calendar_read / calendar_write kinds."""

from __future__ import annotations

import pytest

from presence_ui.gateway.ol_gate import OlGateParsed, parse_ol_gate_response
from presence_ui.gateway.stage1_calendar import (
    normalize_calendar_stage1,
    resolve_calendar_stage1_kind,
)
from presence_ui.gateway.stage1_kinds import STAGE1_KINDS, STAGE1_ROUTES
from presence_ui.gateway.temp_c_staged import apply_staged_decisions, run_staged_classify


def _parsed(kind: str, utterance: str) -> OlGateParsed:
    return OlGateParsed(
        utterance=utterance,
        utterance_kind=kind,
        temporal_phrase=None,
        inferred_temporal_phrase=None,
        temporal_source=None,
        object_phrase=None,
        action_phrase=None,
        action_terms=(),
        completion_verbs=(),
        ineligibility_reason=None,
    )


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("来週の予定は？", "calendar_read"),
        ("明日空いてる？", "calendar_read"),
        ("来週火曜15時に歯医者、カレンダー入れといて", "calendar_write"),
        ("15時の予定を17時にずらして", "calendar_write"),
    ],
)
def test_resolve_calendar_stage1_kind_from_utterance(
    utterance: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    assert (
        resolve_calendar_stage1_kind(kind="calendar_operation", utterance=utterance)
        == expected
    )


def test_parse_accepts_calendar_read_write() -> None:
    read = parse_ol_gate_response(
        '{"utterance":"来週の予定は？","utterance_kind":"calendar_read",'
        '"close_shape":null,"action_terms":[],"completion_verbs":[]}'
    )
    assert read is not None
    assert read.utterance_kind == "calendar_read"
    write = parse_ol_gate_response(
        '{"utterance":"入れといて","utterance_kind":"calendar_write",'
        '"close_shape":null,"action_terms":[],"completion_verbs":[]}'
    )
    assert write is not None
    assert write.utterance_kind == "calendar_write"


def test_legacy_calendar_operation_normalized_to_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    stage1 = normalize_calendar_stage1(
        _parsed("calendar_operation", "来月の予定は？"),
        utterance="来月の予定は？",
    )
    assert stage1.utterance_kind == "calendar_read"


def test_stage1_kinds_include_calendar_split() -> None:
    assert "calendar_read" in STAGE1_KINDS
    assert "calendar_write" in STAGE1_KINDS
    assert STAGE1_ROUTES["calendar_read"] == "calendar_read_gapi"
    assert STAGE1_ROUTES["calendar_write"] == "calendar_gapi"


def test_run_staged_classify_calendar_read_skips_stage2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")

    def fake_turn(**kwargs: object) -> str:
        if "temp_c_stage1" in str(kwargs.get("user", "")):
            return (
                '{"utterance":"来週の予定は？","utterance_kind":"calendar_read",'
                '"close_shape":null,"action_terms":[],"completion_verbs":[]}'
            )
        raise AssertionError("Stage2 should not run for calendar_read")

    monkeypatch.setattr(
        "presence_ui.gateway.temp_c_staged.run_classifier_turn",
        fake_turn,
    )
    result = run_staged_classify(utterance="来週の予定は？")
    assert result is not None
    assert result.stage1.utterance_kind == "calendar_read"
    assert result.events == ()


def test_apply_staged_decisions_routes_calendar_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    calls: list[str] = []

    def fake_pipeline(utterance: str, *, anchor_iso: str | None = None) -> tuple[str, str]:
        calls.append(utterance)
        return ("[calendar_prefetch]\nstatus=ok\n[/calendar_prefetch]", "ok")

    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.run_calendar_read_pipeline",
        fake_pipeline,
    )
    from presence_ui.gateway.temp_c_staged import StagedClassifyResult

    result = StagedClassifyResult(
        utterance="来週の予定は？",
        stage1=_parsed("calendar_read", "来週の予定は？"),
        commitment_strength=None,
        events=(),
    )
    stores = type("S", (), {"policy_timezone": "Asia/Tokyo"})()
    apply_staged_decisions(
        stores,
        person_id="ma",
        text="来週の予定は？",
        ts="2026-07-01T18:00:00+09:00",
        source_event_id="evt-1",
        result=result,
        timezone="Asia/Tokyo",
    )
    assert calls == ["来週の予定は？"]
