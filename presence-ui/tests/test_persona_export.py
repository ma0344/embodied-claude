"""RP Phase 2 persona export helpers."""

from __future__ import annotations

from presence_ui.training.persona_export import (
    _assistant_usable,
    _user_usable,
    pairs_from_session_jsonl,
)


def test_user_usable_rejects_gateway_injection() -> None:
    assert not _user_usable(
        "[gateway_turn_context — not for the user]\n[Social context]\nこんにちは"
    )
    assert _user_usable("今日の修正、何やったっけ？")


def test_assistant_usable_rejects_tools_and_keigo() -> None:
    assert not _assistant_usable("mcp__memory__recall を呼びます")
    assert not _assistant_usable("お役に立てて嬉しいです。何かお手伝いしましょうか。")
    assert _assistant_usable("うち、隣におるから。何でも話してな。")


def test_pairs_from_session_jsonl(tmp_path) -> None:
    path = tmp_path / "sess.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"type":"user","timestamp":"t1","message":{"content":[{"type":"text","text":"こんにちは"}]}}',
                '{"type":"assistant","timestamp":"t2","message":{"content":[{"type":"text","text":"まー、こんにちは。"}]}}',
            ]
        ),
        encoding="utf-8",
    )
    pairs = pairs_from_session_jsonl(path)
    assert pairs == [("こんにちは", "まー、こんにちは。")]
