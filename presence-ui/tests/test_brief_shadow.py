"""Brief shadow mode v0 — observe-only receive-time Brief."""

from __future__ import annotations

import json

from presence_ui.gateway.brief_shadow import (
    BriefShadowJob,
    BriefShadowResult,
    BriefShadowUaCandidate,
    append_brief_shadow,
    brief_shadow_enabled,
    build_brief_shadow_block,
    format_brief_shadow_block,
    parse_brief_shadow_response,
)
from presence_ui.services.llm import GATEWAY_STABLE_APPEND

NORTH_STAR = "冷蔵庫に鶏ももとキャベツと卵あるんだけど、いいアイデアある？"

NORTH_STAR_JSON = json.dumps(
    {
        "jobs": [
            {
                "id": "j1",
                "kind": "surface_reply",
                "parallel": True,
                "note": "材料を踏まえて献立アイデアを返す",
            },
            {
                "id": "j2",
                "kind": "web_search",
                "parallel": True,
                "note": "鶏もも・キャベツ・卵のレシピ検索",
            },
        ],
        "ua_candidates": [
            {
                "kind": "meal",
                "status": "skip",
                "object": "-",
                "write": "skip",
                "reason": "topic_only",
            }
        ],
    },
    ensure_ascii=False,
)


def test_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_BRIEF_SHADOW", raising=False)
    assert brief_shadow_enabled() is False
    assert build_brief_shadow_block(NORTH_STAR) is None


def test_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_SHADOW", "1")
    assert brief_shadow_enabled() is True


def test_format_and_parse_roundtrip() -> None:
    parsed = parse_brief_shadow_response(NORTH_STAR_JSON)
    assert parsed is not None
    block = format_brief_shadow_block(parsed)
    assert block.startswith("[brief_shadow]")
    assert "mode=shadow" in block
    assert "jobs=2" in block
    assert "kind=surface_reply" in block
    assert "kind=web_search" in block
    assert "parallel=true" in block
    assert "ua_candidates=1" in block
    assert "write=skip" in block
    assert "reason=topic_only" in block
    assert block.endswith("[/brief_shadow]")


def test_north_star_via_fixture_classify(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_SHADOW", "1")

    def _fixture(*, utterance: str) -> BriefShadowResult:
        assert "冷蔵庫" in utterance
        return parse_brief_shadow_response(NORTH_STAR_JSON)  # type: ignore[return-value]

    monkeypatch.setattr(
        "presence_ui.gateway.brief_shadow.run_brief_shadow_classify",
        _fixture,
    )
    block = build_brief_shadow_block(NORTH_STAR)
    assert block is not None
    assert "kind=surface_reply" in block
    assert "kind=web_search" in block
    assert "レシピ" in block or "献立" in block or "アイデア" in block
    assert "write=propose" not in block
    assert "write=skip" in block
    assert "topic_only" in block


def test_fail_soft_error_line(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_SHADOW", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.brief_shadow.run_brief_shadow_classify",
        lambda **_kwargs: None,
    )
    block = build_brief_shadow_block("こんにちは")
    assert block is not None
    assert "error=classify_failed" in block
    assert "mode=shadow" in block


def test_append_prepends_block(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_BRIEF_SHADOW", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.brief_shadow.run_brief_shadow_classify",
        lambda **_kwargs: BriefShadowResult(
            jobs=(
                BriefShadowJob(
                    id="j1", kind="surface_reply", parallel=True, note="hi"
                ),
            ),
            ua_candidates=(),
        ),
    )
    out = append_brief_shadow("[Must include] x", utterance="やあ")
    assert out.startswith("[brief_shadow]")
    assert "[Must include] x" in out


def test_append_noop_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_BRIEF_SHADOW", raising=False)
    assert append_brief_shadow("delta", utterance=NORTH_STAR) == "delta"


def test_stable_append_forbids_speaking_brief_shadow() -> None:
    assert "brief_shadow" in GATEWAY_STABLE_APPEND
    assert "ua_candidates" in GATEWAY_STABLE_APPEND


def test_ate_self_report_may_propose_but_is_shadow_only() -> None:
    raw = json.dumps(
        {
            "jobs": [
                {"id": "j1", "kind": "surface_reply", "parallel": False, "note": "ack"}
            ],
            "ua_candidates": [
                {
                    "kind": "meal",
                    "status": "confirmed",
                    "object": "カレー",
                    "write": "propose",
                    "reason": "self_report",
                }
            ],
        },
        ensure_ascii=False,
    )
    parsed = parse_brief_shadow_response(raw)
    assert parsed is not None
    block = format_brief_shadow_block(parsed)
    assert "status=confirmed" in block
    assert "write=propose" in block
    # Shadow module itself never writes UA — only formats candidates.
    assert BriefShadowUaCandidate(
        kind="meal",
        status="confirmed",
        object="カレー",
        write="propose",
        reason="self_report",
    ) in parsed.ua_candidates
