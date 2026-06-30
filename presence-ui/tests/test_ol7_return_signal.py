"""OL7 — return-signal classifier parse + threshold."""

from __future__ import annotations

from presence_ui.gateway.ol7_return_signal import (
    OpenLoopCandidate,
    build_ol7_task,
    classify_return_signal,
    parse_ol7_response,
    resolve_ol7_loop_ids,
    should_run_ol7_classifier,
    Ol7Classification,
)

_LOOPS = [
    OpenLoopCandidate("loop_nap", "お昼寝する", "お昼寝する"),
    OpenLoopCandidate("loop_docs", "書類を作る", "書類を作る"),
    OpenLoopCandidate("loop_mikan", "みかんを食べる", "みかんを食べる"),
]


def test_build_ol7_task_numbered_choices() -> None:
    task = build_ol7_task(utterance="昼寝終わった", open_loops=_LOOPS)
    assert "1. loop_id=loop_nap" in task
    assert "3. loop_id=loop_mikan" in task
    assert "utterance: 昼寝終わった" in task


def test_parse_explicit_completion_by_choice_index() -> None:
    raw = """{
      "utterance": "昼寝終わった",
      "signal": "explicit_completion",
      "choice_index": 1,
      "close_loop_ids": [],
      "completion_summary": "お昼寝を終えた",
      "confidence": 0.92,
      "reason": "昼寝+終わったが自然"
    }"""
    parsed = parse_ol7_response(raw, utterance="昼寝終わった", open_loops=_LOOPS)
    assert parsed is not None
    assert parsed.close_loop_ids == ("loop_nap",)
    assert parsed.signal == "explicit_completion"


def test_parse_none_clears_ids() -> None:
    raw = """{
      "utterance": "ごちそうさま",
      "signal": "none",
      "choice_index": null,
      "close_loop_ids": ["loop_mikan"],
      "completion_summary": "食事した",
      "confidence": 0.4,
      "reason": "曖昧"
    }"""
    parsed = parse_ol7_response(raw, utterance="ごちそうさま", open_loops=_LOOPS)
    assert parsed is not None
    assert parsed.close_loop_ids == ()
    assert parsed.completion_summary is None


def test_parse_rejects_unknown_loop_id() -> None:
    raw = """{
      "signal": "explicit_completion",
      "close_loop_ids": ["loop_food"],
      "confidence": 0.9,
      "reason": "捏造"
    }"""
    parsed = parse_ol7_response(raw, utterance="ごちそうさま", open_loops=_LOOPS)
    assert parsed is not None
    assert parsed.close_loop_ids == ()


def test_resolve_return_signal_single_candidate_fills_ids() -> None:
    loops = [
        OpenLoopCandidate(
            "loop_78d8f051e8",
            "これから 散歩 行ってくる",
            "これから 散歩 行ってくる",
            activity_label="散歩",
        )
    ]
    classification = Ol7Classification(
        utterance="ただいまー",
        signal="return_signal",
        close_loop_ids=(),
        completion_summary=None,
        confidence=0.5,
        reason="model omitted ids",
    )
    resolved = resolve_ol7_loop_ids(
        classification,
        utterance="ただいまー",
        open_loops=loops,
    )
    assert resolved.close_loop_ids == ("loop_78d8f051e8",)
    assert resolved.choice_index == 1


def test_resolve_known_return_phrase_departure_loop() -> None:
    loops = [
        OpenLoopCandidate(
            "loop_walk",
            "これから 散歩 行ってくる",
            "散歩",
            activity_label="散歩",
        )
    ]
    classification = Ol7Classification(
        utterance="ただいま",
        signal="none",
        close_loop_ids=(),
        completion_summary=None,
        confidence=0.5,
        reason="model rejected collocation",
    )
    resolved = resolve_ol7_loop_ids(
        classification,
        utterance="ただいま",
        open_loops=loops,
    )
    assert resolved.signal == "return_signal"
    assert resolved.close_loop_ids == ("loop_walk",)


def test_resolve_unscoped_past_completion_single_departure() -> None:
    from social_core.activity_frame import build_activity_frame_for_open

    nap_frame = build_activity_frame_for_open(label="昼寝", action_phrase="してくる")
    docs_frame = build_activity_frame_for_open(label="書類", action_phrase="作る")
    assert nap_frame is not None and docs_frame is not None
    loops = [
        OpenLoopCandidate(
            "loop_nap",
            "もう一度 昼寝 してくる",
            "昼寝",
            activity_label="昼寝",
            activity_frame=nap_frame,
        ),
        OpenLoopCandidate(
            "loop_docs",
            "書類 作る",
            "書類",
            activity_label="書類",
            activity_frame=docs_frame,
        ),
    ]
    classification = Ol7Classification(
        utterance="終わったよ",
        signal="none",
        close_loop_ids=(),
        completion_summary=None,
        confidence=0.4,
        reason="model missed unscoped completion",
    )
    resolved = resolve_ol7_loop_ids(
        classification,
        utterance="終わったよ",
        open_loops=loops,
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="終わった",
    )
    assert resolved.signal == "explicit_completion"
    assert resolved.close_loop_ids == ("loop_nap",)


def test_resolve_unscoped_multi_departure_no_fallback() -> None:
    from social_core.activity_frame import build_activity_frame_for_open

    nap_frame = build_activity_frame_for_open(label="昼寝", action_phrase="してくる")
    walk_frame = build_activity_frame_for_open(label="散歩", action_phrase="行ってくる")
    assert nap_frame is not None and walk_frame is not None
    loops = [
        OpenLoopCandidate(
            "loop_nap",
            "もう一度 昼寝 してくる",
            "昼寝",
            activity_label="昼寝",
            activity_frame=nap_frame,
        ),
        OpenLoopCandidate(
            "loop_walk",
            "散歩 行ってくる",
            "散歩",
            activity_label="散歩",
            activity_frame=walk_frame,
        ),
    ]
    classification = Ol7Classification(
        utterance="してきたよ",
        signal="none",
        close_loop_ids=(),
        completion_summary=None,
        confidence=0.4,
        reason="ambiguous",
    )
    resolved = resolve_ol7_loop_ids(
        classification,
        utterance="してきたよ",
        open_loops=loops,
        utterance_kind="past_completion",
        object_phrase=None,
        action_phrase="してきた",
    )
    assert resolved.close_loop_ids == ()


def test_should_run_ol7_classifier_allowlist() -> None:
    assert should_run_ol7_classifier(
        utterance_kind="past_completion",
        gw_s2_active=True,
    )
    assert should_run_ol7_classifier(utterance_kind="greeting", gw_s2_active=True)
    assert not should_run_ol7_classifier(
        utterance_kind="future_commitment",
        gw_s2_active=True,
    )
    assert not should_run_ol7_classifier(utterance_kind=None, gw_s2_active=True)
    assert should_run_ol7_classifier(utterance_kind=None, gw_s2_active=False)


def test_build_ol7_task_includes_utterance_kind() -> None:
    task = build_ol7_task(
        utterance="昼寝終わった",
        open_loops=_LOOPS[:1],
        utterance_kind="past_completion",
    )
    assert "utterance_kind: past_completion" in task


def test_build_ol7_task_includes_slots_and_gloss() -> None:
    from social_core.activity_frame import build_activity_frame_for_open, activity_gloss

    frame = build_activity_frame_for_open(label="お皿洗い", action_phrase="してくる")
    assert frame is not None
    task = build_ol7_task(
        utterance="お皿洗ったよ",
        utterance_kind="past_completion",
        object_phrase="お皿",
        action_phrase="洗った",
        open_loops=[
            OpenLoopCandidate(
                "loop_dish",
                "2026年6月30日 お皿洗い してくる",
                "お皿洗い",
                activity_label="お皿洗い",
                activity_frame=frame,
                frame_gloss=activity_gloss(frame),
            )
        ],
    )
    assert "slots: object=お皿 | action=洗った" in task
    assert "gloss=" in task
    assert "label=お皿洗い" in task


def test_build_ol7_task_includes_activity() -> None:
    task = build_ol7_task(
        utterance="ただいま",
        open_loops=[
            OpenLoopCandidate(
                "loop_x",
                "これから 散歩 行ってくる",
                "これから 散歩 行ってくる",
                activity_label="散歩",
            )
        ],
    )
    assert "activity=散歩" in task or "label=散歩" in task


def test_classify_below_threshold_becomes_no_close(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_OL7_MIN_CONFIDENCE", "0.8")

    def fake_turn(**_kwargs: object) -> str:
        return """{
          "signal": "return_signal",
          "close_loop_ids": ["loop_mikan"],
          "confidence": 0.55,
          "reason": "弱いペア"
        }"""

    monkeypatch.setattr(
        "presence_ui.gateway.ol7_return_signal.run_classifier_turn",
        fake_turn,
    )
    parsed = classify_return_signal(utterance="ごちそうさま", open_loops=_LOOPS)
    assert parsed is not None
    assert parsed.signal == "none"
    assert parsed.close_loop_ids == ()
