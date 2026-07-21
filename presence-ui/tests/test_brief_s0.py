"""Brief S0 dry-run — observe-only spans inject."""

from __future__ import annotations

import json

from presence_ui.gateway.brief_s0 import (
    BriefS0Result,
    BriefS0Span,
    append_brief_s0,
    brief_s0_enabled,
    build_brief_s0_block,
    format_brief_s0_block,
    parse_brief_s0_response,
)
from presence_ui.services.llm import GATEWAY_STABLE_APPEND

SAMPLE_JSON = json.dumps(
    {
        "spans": [
            {
                "text": "設問文を修正してテストしたら、ちゃんとRequestになったから",
                "ask": "report",
                "hint": "none",
            },
            {
                "text": "書き換えの方向で追記をお願い。",
                "ask": "request",
                "hint": "none",
            },
        ]
    },
    ensure_ascii=False,
)


def test_brief_s0_default_on(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_BRIEF_S0", raising=False)
    assert brief_s0_enabled() is True


def test_brief_s0_off(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_S0", "0")
    assert brief_s0_enabled() is False
    assert build_brief_s0_block("やあ") is None


def test_parse_and_format() -> None:
    parsed = parse_brief_s0_response(SAMPLE_JSON, reasoning=True)
    assert parsed is not None
    assert len(parsed.spans) == 2
    assert parsed.spans[0].ask == "report"
    assert parsed.spans[1].ask == "request"
    block = format_brief_s0_block(parsed)
    assert block.startswith("[brief_s0]")
    assert "mode=dry-run" in block
    assert "reasoning=on" in block
    assert "ask=report" in block
    assert "ask=request" in block
    assert block.endswith("[/brief_s0]")


def test_build_block_uses_classify(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_S0", "1")
    monkeypatch.setenv("PRESENCE_BRIEF_S0_REASONING", "1")

    def fake_classify(*, utterance: str) -> BriefS0Result:
        return parse_brief_s0_response(SAMPLE_JSON, reasoning=True)  # type: ignore[return-value]

    monkeypatch.setattr(
        "presence_ui.gateway.brief_s0.run_brief_s0_classify",
        fake_classify,
    )
    block = build_brief_s0_block("テスト")
    assert block is not None
    assert "ask=request" in block


def test_build_block_fail_soft(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_S0", "1")

    def boom(*, utterance: str) -> BriefS0Result | None:
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "presence_ui.gateway.brief_s0.run_brief_s0_classify",
        boom,
    )
    block = build_brief_s0_block("やあ")
    assert block is not None
    assert "error=classify_exception" in block


def test_append_brief_s0_prepends(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_S0", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.brief_s0.run_brief_s0_classify",
        lambda *, utterance: parse_brief_s0_response(SAMPLE_JSON, reasoning=False),
    )
    out = append_brief_s0("[Must include] x", utterance="やあ")
    assert out.startswith("[brief_s0]")
    assert "[Must include] x" in out


def test_append_off_passthrough(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_S0", "0")
    assert append_brief_s0("delta", utterance="hi") == "delta"


def test_stable_append_forbids_speaking_brief_s0() -> None:
    assert "brief_s0" in GATEWAY_STABLE_APPEND
    assert "dry-run" in GATEWAY_STABLE_APPEND


def test_unknown_ask_becomes_other() -> None:
    raw = json.dumps(
        {"spans": [{"text": "x", "ask": "mystery", "hint": "life"}]},
        ensure_ascii=False,
    )
    parsed = parse_brief_s0_response(raw, reasoning=False)
    assert parsed is not None
    assert parsed.spans[0].ask == "other"
    assert parsed.spans[0].hint == "life"
