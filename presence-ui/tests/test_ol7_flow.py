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


def test_apply_ol7_resolves_empty_ids_on_return_signal(monkeypatch) -> None:
    """Reproduce LM log: return_signal + empty close_loop_ids → pending_confirm."""
    stores = MagicMock()
    loop = MagicMock()
    loop.id = "loop_78d8f051e8"
    loop.topic = "これから 散歩 行ってくる"
    loop.detail = {"utterance": "これから 散歩 行ってくる", "action_terms": ["散歩"]}
    stores.relationship.list_open_loops.return_value = [loop]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        return Ol7Classification(
            utterance="ただいまー",
            signal="return_signal",
            close_loop_ids=(),
            completion_summary=None,
            confidence=0.5,
            reason="出発とは直接的なコロケーションがない",
        )

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="ただいまー",
        ts="2026-06-30T11:00:38+09:00",
        source_event_id="evt-return",
    )
    assert result == Ol7IngestResult(
        route="pending_confirm",
        pending_loop_id="loop_78d8f051e8",
    )
    stores.relationship.set_ol7_pending_candidate.assert_called_once()


def test_apply_ol7_skips_future_commitment_without_classify(monkeypatch) -> None:
    stores = MagicMock()
    loop = MagicMock()
    loop.id = "loop_docs"
    loop.topic = "書類 作る"
    loop.detail = {"utterance": "書類 作る"}
    stores.relationship.list_open_loops.return_value = [loop]

    classify_called = False

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        nonlocal classify_called
        classify_called = True
        raise AssertionError("classifier should not run")

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="書類も作る",
        ts="2026-06-30T11:25:52+09:00",
        source_event_id="evt-future",
        utterance_kind="future_commitment",
    )
    assert result.route == "no_op"
    assert classify_called is False
    stores.relationship.close_open_loops_by_ids.assert_not_called()


def test_apply_ol7_frame_match_immediate_close_without_llm(monkeypatch) -> None:
    stores = MagicMock()
    loop_dishes = MagicMock()
    loop_dishes.id = "loop_dishes"
    loop_dishes.topic = "2026年6月30日 お皿洗い してくる"
    loop_dishes.detail = {
        "event": {"what": "お皿洗い", "action_phrase": "してくる"},
        "activity_frame": {
            "label": "お皿洗い",
            "action_stem": "し",
            "mode": "departure",
            "gloss": "お皿洗い",
        },
    }
    loop_laundry = MagicMock()
    loop_laundry.id = "loop_laundry"
    loop_laundry.topic = "洗濯 してくる"
    loop_laundry.detail = {
        "event": {"what": "洗濯", "action_phrase": "してくる"},
        "activity_frame": {"label": "洗濯", "action_stem": "し", "mode": "departure", "gloss": "洗濯"},
    }
    stores.relationship.list_open_loops.return_value = [loop_dishes, loop_laundry]
    stores.relationship.close_open_loops_by_ids.return_value = [
        "2026年6月30日 お皿洗い してくる"
    ]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        raise AssertionError("classifier should not run when frame matches uniquely")

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="お皿洗ったよ",
        ts="2026-06-30T12:18:45+09:00",
        source_event_id="evt-dishes",
        utterance_kind="past_completion",
        object_phrase="お皿",
        action_phrase="洗った",
    )
    assert result.route == "immediate_close"
    stores.relationship.close_open_loops_by_ids.assert_called_once()


def test_apply_ol7_runs_past_completion_despite_pending_on_other_loop(monkeypatch) -> None:
    """Explicit completion must not be blocked by unrelated loop's pending_check."""
    stores = MagicMock()
    loop_laundry = MagicMock()
    loop_laundry.id = "loop_laundry"
    loop_laundry.topic = "洗濯 してくる"
    loop_laundry.detail = {"pending_check": {"asked_at": "2026-06-30T03:15:20+00:00"}}
    loop_dishes = MagicMock()
    loop_dishes.id = "loop_dishes"
    loop_dishes.topic = "お皿洗い してくる"
    loop_dishes.detail = {
        "action_terms": ["お皿洗い"],
        "event": {"what": "お皿洗い", "action_phrase": "してくる"},
        "activity_frame": {"label": "お皿洗い", "action_stem": "し", "mode": "departure", "gloss": "お皿洗い"},
    }
    stores.relationship.list_open_loops.return_value = [loop_laundry, loop_dishes]
    stores.relationship.close_open_loops_by_ids.return_value = ["お皿洗い してくる"]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        raise AssertionError("frame match should close before classifier")

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="お皿洗ったよ",
        ts="2026-06-30T12:18:45+09:00",
        source_event_id="evt-dishes",
        utterance_kind="past_completion",
        object_phrase="お皿",
        action_phrase="洗った",
    )
    assert result.route == "immediate_close"
    stores.relationship.close_open_loops_by_ids.assert_called_once()


def test_apply_ol7_unscoped_past_completion_closes_single_departure(monkeypatch) -> None:
    """昼寝してくる open + 終わったよ (Stage1 object=null) closes without LLM."""
    stores = MagicMock()
    loop_nap = MagicMock()
    loop_nap.id = "loop_nap"
    loop_nap.topic = "もう一度 昼寝 してくる"
    loop_nap.detail = {
        "event": {"what": "昼寝", "action_phrase": "してくる"},
        "activity_frame": {
            "label": "昼寝",
            "action_stem": "し",
            "mode": "departure",
            "gloss": "昼寝",
        },
    }
    loop_docs = MagicMock()
    loop_docs.id = "loop_docs"
    loop_docs.topic = "書類 作る"
    loop_docs.detail = {
        "event": {"what": "書類", "action_phrase": "作る"},
        "activity_frame": {
            "label": "書類",
            "action_stem": "作",
            "mode": None,
            "gloss": "書類を作る行為",
        },
    }
    stores.relationship.list_open_loops.return_value = [loop_nap, loop_docs]
    stores.relationship.close_open_loops_by_ids.return_value = ["もう一度 昼寝 してくる"]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        raise AssertionError("unscoped past_completion should close before classifier")

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="終わったよ",
        ts="2026-06-30T13:01:00+09:00",
        source_event_id="evt-nap-done",
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="終わった",
    )
    assert result.route == "immediate_close"
    stores.relationship.close_open_loops_by_ids.assert_called_once_with(
        person_id="ma",
        loop_ids=["loop_nap"],
        ts="2026-06-30T13:01:00+09:00",
        source_event_id="evt-nap-done",
        source_text="終わったよ",
        close_kind="ol7_completion",
    )


def test_apply_ol7_contextual_wake_greeting_closes_single_departure(monkeypatch) -> None:
    """おはよう + single nap departure (Stage1 Q3a) → unscoped immediate close."""
    stores = MagicMock()
    loop_nap = MagicMock()
    loop_nap.id = "loop_nap"
    loop_nap.topic = "ちょっと 昼寝 してくる"
    loop_nap.detail = {
        "event": {"what": "昼寝", "action_phrase": "してくる"},
        "activity_frame": {
            "label": "昼寝",
            "action_stem": "し",
            "mode": "departure",
            "gloss": "昼寝",
        },
    }
    stores.relationship.list_open_loops.return_value = [loop_nap]
    stores.relationship.close_open_loops_by_ids.return_value = ["ちょっと 昼寝 してくる"]

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        raise AssertionError("contextual wake should close before classifier")

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="おはよう",
        ts="2026-06-30T14:02:00+09:00",
        source_event_id="evt-wake",
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="おはよう",
        close_shape="action_only",
    )
    assert result.route == "immediate_close"
    stores.relationship.close_open_loops_by_ids.assert_called_once()


def test_apply_ol7_unscoped_multi_departure_defers_to_classifier(monkeypatch) -> None:
    """してきたよ + 散歩/昼寝 both open → OL7 disambiguates (no marker/heuristic close)."""
    stores = MagicMock()
    loop_nap = MagicMock()
    loop_nap.id = "loop_nap"
    loop_nap.topic = "もう一度 昼寝 してくる"
    loop_nap.detail = {
        "event": {"what": "昼寝", "action_phrase": "してくる"},
        "activity_frame": {
            "label": "昼寝",
            "action_stem": "し",
            "mode": "departure",
            "gloss": "昼寝",
        },
    }
    loop_walk = MagicMock()
    loop_walk.id = "loop_walk"
    loop_walk.topic = "散歩 行ってくる"
    loop_walk.detail = {
        "event": {"what": "散歩", "action_phrase": "行ってくる"},
        "activity_frame": {
            "label": "散歩",
            "action_stem": "行",
            "mode": "departure",
            "gloss": "散歩",
        },
    }
    stores.relationship.list_open_loops.return_value = [loop_nap, loop_walk]

    classify_called = False

    def fake_classify(**_kwargs: object) -> Ol7Classification:
        nonlocal classify_called
        classify_called = True
        return Ol7Classification(
            utterance="してきたよ",
            signal="explicit_completion",
            close_loop_ids=("loop_nap",),
            completion_summary="昼寝から戻った",
            confidence=0.92,
            reason="test",
        )

    monkeypatch.setattr("presence_ui.gateway.ol7_flow.ol7_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.gw_s2_enabled", lambda: True)
    monkeypatch.setattr("presence_ui.gateway.ol7_flow.classify_return_signal", fake_classify)

    result = apply_ol7_after_ingest(
        stores,
        person_id="ma",
        text="してきたよ",
        ts="2026-06-30T13:14:00+09:00",
        source_event_id="evt-back",
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="してきた",
    )
    assert classify_called is True
    assert result.route == "immediate_close"
    stores.relationship.close_open_loops_by_ids.assert_called_once()
