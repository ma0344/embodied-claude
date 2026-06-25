"""Tests for MEM-8b recall query shaping."""

from __future__ import annotations

import io
import json
import urllib.parse

from interaction_orchestrator_mcp.memory_adapter import HttpMemoryAdapter
from interaction_orchestrator_mcp.recall_query import (
    build_recall_queries,
    compose_hit_rank,
    extract_schedule_facts,
    is_episodic_blob,
    should_skip_compose_recall,
)


GISTS = [
    "まーのグループホーム名は「ここっち」（embodied-claude/口語の「こっち」と別）",
    (
        "まーの仕事・所属: 事務とかシステムの仕事をしているのは「ねっとわん」"
        "っていう会社だよ。水曜午前に行ってる。"
    ),
]


class TestRecallQuery:
    def test_skip_chitchat(self):
        assert should_skip_compose_recall("おはよう")
        assert not should_skip_compose_recall("ねっとわん いつ")

    def test_temporal_query_uses_gist_schedule(self):
        queries = build_recall_queries(
            purpose="compose",
            user_text="ねっとわん いつ",
            profile_gists=GISTS,
        )
        assert queries
        joined = " ".join(queries)
        assert "ねっとわん" in joined
        assert "水曜" in joined or "午前" in joined

    def test_deixis_query_adds_anchors(self):
        queries = build_recall_queries(
            purpose="compose",
            user_text="ここっちのお仕事の話",
            profile_gists=GISTS,
        )
        joined = " ".join(queries)
        assert "ここっち" in joined or "グループホーム" in joined

    def test_episodic_blob_detection(self):
        assert is_episodic_blob("【会話の区切り】\nまー: おはよう")
        assert is_episodic_blob("【会話の一区切り】\nまー: おはよう")
        assert not is_episodic_blob("まーのネットワン勤務は水曜午前")


class TestComposeHitRank:
    def test_demotes_episode_for_temporal(self):
        episode = "【会話の区切り】\n" + ("長い会話ログ\n" * 20)
        fact = "まーのねっとわん勤務は水曜午前"
        assert compose_hit_rank(episode, base_relevance=0.9, temporal=True) < compose_hit_rank(
            fact, base_relevance=0.7, temporal=True
        )


class TestExtractScheduleFacts:
    def test_extracts_from_ltm_fact(self):
        facts = extract_schedule_facts(
            "ねっとわん いつ",
            [
                "有限会社ねっとわんの事務・システム関連のお仕事は水曜午前が定例（週により日程がずれることあり）",
            ],
        )
        assert facts
        assert "水曜" in facts[0]
        assert "午前" in facts[0]

    def test_skips_episode_blob(self):
        facts = extract_schedule_facts(
            "ねっとわん いつ",
            ["【会話の一区切り】\nまー: 覚えといた\n" * 10],
        )
        assert facts == []


class TestCompactBlockLite:
    def test_lite_cap_preserves_pinned_schedule(self):
        from interaction_orchestrator_mcp.compose import _compact_block
        from interaction_orchestrator_mcp.schemas import RelevantMemoryRef, ResponseContract

        mem = RelevantMemoryRef(
            memory_id="m1",
            content="有限会社ねっとわんの事務・システム関連のお仕事は水曜午前が定例（週により日程がずれることあり）",
            relevance=1.0,
            use_policy="mentionable",
        )
        block = _compact_block(
            prompt_summary="Calendar today: 2026-06-25. Relevant memories: 1.",
            response_contract=ResponseContract(),
            relevant_memories=[mem],
            user_text="ねっとわん いつ",
            session_context_block="[session_history]\n" + ("turn\n" * 400),
            profile_gists=["長いgist " * 40],
            max_chars=1200,
        )
        assert "[schedule_facts" in block
        assert "水曜午前" in block
        assert block.index("[schedule_facts") < 600


class TestTemporalScheduleContract:
    def test_contract_off_skips_pinned_schedule(self, monkeypatch):
        from interaction_orchestrator_mcp.compose import _compact_block
        from interaction_orchestrator_mcp.schemas import RelevantMemoryRef, ResponseContract

        monkeypatch.setenv("PRESENCE_TEMPORAL_SCHEDULE_CONTRACT", "0")
        mem = RelevantMemoryRef(
            memory_id="m1",
            content="有限会社ねっとわんの事務・システム関連のお仕事は水曜午前が定例",
            relevance=1.0,
            use_policy="mentionable",
        )
        block = _compact_block(
            prompt_summary="Calendar today: 2026-06-25.",
            response_contract=ResponseContract(),
            relevant_memories=[mem],
            user_text="ねっとわん いつ",
            max_chars=8000,
        )
        assert "[schedule_facts" not in block
        assert "水曜午前" in block  # still in relevant_memories


class TestHttpAdapterComposeQueries:
    def test_temporal_uses_shaped_query_not_raw_user_text(self, monkeypatch):
        seen_urls: list[str] = []

        def fake_urlopen(url, timeout=3):
            seen_urls.append(url)
            decoded = urllib.parse.unquote(url)
            if "水曜" in decoded or "午前" in decoded:
                payload = json.dumps(
                    [
                        {
                            "content": "まーのねっとわん勤務は水曜午前",
                            "score": 0.75,
                        }
                    ],
                    ensure_ascii=False,
                ).encode("utf-8")
            else:
                payload = json.dumps(
                    [
                        {
                            "content": "【会話の区切り】\nまー: ねっとわんの話\n" * 5,
                            "score": 0.95,
                        }
                    ],
                    ensure_ascii=False,
                ).encode("utf-8")
            return io.BytesIO(payload)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        adapter = HttpMemoryAdapter(base_url="http://127.0.0.1:18999")
        hits = adapter.recall_for_response(
            user_text="ねっとわん いつ",
            profile_gists=GISTS,
            purpose="compose",
        )
        assert hits
        assert "水曜" in hits[0].content
        decoded_urls = [urllib.parse.unquote(url) for url in seen_urls]
        assert any("水曜" in url or "午前" in url for url in decoded_urls)
        assert not any("いつ" in url for url in decoded_urls)
