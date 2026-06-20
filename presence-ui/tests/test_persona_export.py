"""RP Phase 2 persona export helpers."""

from __future__ import annotations

import json

from presence_ui.training.persona_export import (
    _assistant_usable,
    _user_usable,
    filter_drop_all_near_duplicate_pairs,
    format_persona_markdown,
    load_persona_jsonl,
    pair_usable_for_training,
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
    assert not _assistant_usable("No response requested.")
    assert _assistant_usable("うち、隣におるから。何でも話してな。")


def test_pair_usable_rejects_meta_and_voice_test() -> None:
    assert not pair_usable_for_training(
        "「まー！！時間やで！！」って言ってみて",
        "（今、もう一回言ったで！）",
    )
    assert not pair_usable_for_training(
        "もう一回や",
        "まー！！時間やで！！",
    )
    assert not pair_usable_for_training(
        "今日どう？",
        "（今、もう一回言ったで！）",
    )
    assert pair_usable_for_training(
        "今日どう？",
        "まあまあやな。まー、隣におるからな。",
    )


def test_filter_drop_all_near_duplicate_pairs() -> None:
    pairs = [
        ("今日雨やな", "雨、ずっと降ってるな。まー、窓見てた。"),
        ("雨降ってる", "雨、ずっと降ってるな。まー、窓見てたで。"),
        ("別の話題", "全然ちゃう返事や。"),
    ]
    kept = filter_drop_all_near_duplicate_pairs(pairs)
    assert kept == [("別の話題", "全然ちゃう返事や。")]


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


def test_format_persona_markdown(tmp_path) -> None:
    jsonl = tmp_path / "train.jsonl"
    jsonl.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "うちはこより。"},
                    {"role": "user", "content": "今日どう？"},
                    {"role": "assistant", "content": "まあまあやな。"},
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    examples = load_persona_jsonl(jsonl)
    md = format_persona_markdown(examples, source_path=jsonl)
    assert "## Pair 1" in md
    assert "### まー" in md
    assert "今日どう？" in md
    assert "まあまあやな。" in md
