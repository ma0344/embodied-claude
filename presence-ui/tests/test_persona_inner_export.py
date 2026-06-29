"""Tests for inner persona LoRA export (RP-2c)."""

from __future__ import annotations

import json

import pytest

from presence_ui.training.persona_inner_export import (
    _cue_for_private_reflection,
    _is_private_note_timestamp_stub,
    append_inner_voice_archive,
    export_persona_inner_jsonl,
    inner_body_usable,
)


def test_inner_body_usable_rejects_autonomous_memory_trace() -> None:
    text = (
        "（自律の記憶なぞり）\n"
        "- 【会話の一区切り】まー: ありがと〜。こより: 了解。\n"
        "- 【会話の一区切り】まー: おはようさん。こより: おはようさん！"
    )
    assert not inner_body_usable(text)


def test_inner_body_usable_rejects_episode_close_dump() -> None:
    text = "【会話の一区切り】まー: おるよ〜。こより: お疲れ様、まー。"
    assert not inner_body_usable(text)


def test_inner_body_usable_rejects_gw_s1_v0_placeholder() -> None:
    text = (
        "（青空を読んだあと — 咀嚼）\n"
        "【引っかかったところ】\n"
        "（次の tick で GW-S1 がここを埋める。v0 は一節を眺め直すだけ。）"
    )
    assert not inner_body_usable(text)


def test_inner_body_usable_rejects_private_note_timestamp_stub() -> None:
    title = "Private note 2026-06-26 19:20 UTC"
    assert not inner_body_usable(title)


def test_private_note_timestamp_stub_pair() -> None:
    title = "Private note 2026-06-26 19:20 UTC"
    assert _is_private_note_timestamp_stub(title, title)
    assert _is_private_note_timestamp_stub(title, "")


def test_inner_body_usable_rejects_keigo_without_uchi() -> None:
    assert not inner_body_usable("本日はお役に立てて嬉しいです。よろしくお願いいたします。")


def test_inner_body_usable_accepts_kansai_reflection() -> None:
    text = "うち、今日は部屋が静かやったな。まーの様子、少し疲れて見えた気がする。"
    assert inner_body_usable(text)


def test_cue_for_private_reflection() -> None:
    assert _cue_for_private_reflection("深夜メモ").startswith("（内省・非公開）")


def test_append_inner_voice_archive(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "inner-voice-archive.jsonl"
    monkeypatch.setenv("PERSONA_INNER_VOICE_ARCHIVE_JSONL", str(archive))
    append_inner_voice_archive(
        local_day="2026-06-28",
        dreamed_at="2026-06-29T05:00:00+09:00",
        body="[overnight_inner_voice]\n昨夜は穏やかやった。うち、少し考え込んでた。まーのこと、頭から離れへんかった。\n[/overnight_inner_voice]",
    )
    assert archive.is_file()
    record = json.loads(archive.read_text(encoding="utf-8").strip())
    assert record["source"] == "overnight_inner_voice"
    assert "穏やか" in record["body"]
    assert "overnight_inner_voice" not in record["body"]


def test_export_persona_inner_jsonl_from_db(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from social_core import SocialDB

    db_path = tmp_path / "social.db"
    db = SocialDB(db_path)
    db.connect()
    db.execute(
        """
        INSERT INTO private_reflections(
            reflection_id, ts, person_id, title, body, tags,
            importance, may_surface_later, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ref_test1",
            "2026-06-28T23:00:00+09:00",
            "ma",
            "深夜メモ",
            "うち、今日は部屋が静かやったな。まーの様子、少し疲れて見えた気がする。",
            "",
            3,
            0,
            "2026-06-28T23:00:00+09:00",
        ),
    )

    social_db = db

    class FakeStores:
        db = social_db

    monkeypatch.setattr(
        "presence_ui.deps.get_stores",
        lambda: FakeStores(),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "presets").mkdir()
    (repo / "presets" / "koyori-SOUL.core.md").write_text(
        "うちはこより。", encoding="utf-8"
    )
    out = tmp_path / "inner-candidates.jsonl"
    stats = export_persona_inner_jsonl(repo_root=repo, output_path=out)
    assert stats.pairs_written == 1
    record = json.loads(out.read_text(encoding="utf-8").strip())
    assert record["kind"] == "inner"
    assert record["source"] == "private_reflection"
    assert record["messages"][1]["content"].startswith("（内省・非公開）")
    assert "静かやった" in record["messages"][2]["content"]
    db.close()


def test_export_skips_gw_s1_placeholder_and_private_note_stubs(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from social_core import SocialDB

    db_path = tmp_path / "social.db"
    db = SocialDB(db_path)
    db.connect()
    gw_body = (
        "（青空を読んだあと — 咀嚼）\n"
        "『テスト』\n\n"
        "【引っかかったところ】\n"
        "（次の tick で GW-S1 がここを埋める。v0 は一節を眺め直すだけ。）"
    )
    private_title = "Private note 2026-06-26 19:20 UTC"
    memory_body = (
        "（自律の記憶なぞり）\n"
        "- 【会話の一区切り】まー: ありがと〜。こより: 了解。"
    )
    for reflection_id, title, body in (
        ("ref_gw", "青空メモ", gw_body),
        ("ref_stub", private_title, private_title),
        ("ref_memory", private_title, memory_body),
        ("ref_good", "深夜メモ", "うち、今日は部屋が静かやったな。まーの様子、少し疲れて見えた気がする。"),
    ):
        db.execute(
            """
            INSERT INTO private_reflections(
                reflection_id, ts, person_id, title, body, tags,
                importance, may_surface_later, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reflection_id,
                "2026-06-28T23:00:00+09:00",
                "ma",
                title,
                body,
                "",
                3,
                0,
                "2026-06-28T23:00:00+09:00",
            ),
        )

    social_db = db

    class FakeStores:
        db = social_db

    monkeypatch.setattr("presence_ui.deps.get_stores", lambda: FakeStores())
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "presets").mkdir()
    (repo / "presets" / "koyori-SOUL.core.md").write_text("うちはこより。", encoding="utf-8")
    out = tmp_path / "inner-candidates.jsonl"
    stats = export_persona_inner_jsonl(repo_root=repo, output_path=out)
    assert stats.pairs_written == 1
    record = json.loads(out.read_text(encoding="utf-8").strip())
    assert "静かやった" in record["messages"][2]["content"]
    db.close()
