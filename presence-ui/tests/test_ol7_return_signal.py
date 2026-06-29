"""OL7 — return-signal classifier parse + threshold."""

from __future__ import annotations

from presence_ui.gateway.ol7_return_signal import (
    OpenLoopCandidate,
    build_ol7_task,
    classify_return_signal,
    parse_ol7_response,
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
