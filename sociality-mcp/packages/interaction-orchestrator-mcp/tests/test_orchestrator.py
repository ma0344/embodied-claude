"""Tests for the interaction orchestrator."""

from __future__ import annotations

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    AppendPrivateReflectionInput,
    ComposeInteractionContextInput,
    ComposePrivateLetterInput,
    PlanResponseInput,
    RecordAgentExperienceInput,
    RecordInterpretationShiftInput,
)


def _compose(stores, *, user_text=None, channel="chat", person_id="ma", memory_adapter=None):
    return compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id, channel=channel, user_text=user_text
        ),
        social_state_store=stores["social_state"],
        relationship_store=stores["relationship"],
        joint_attention_store=stores["joint_attention"],
        boundary_store=stores["boundary"],
        self_narrative_store=stores["self_narrative"],
        orchestrator_store=stores["orchestrator"],
        policy_timezone="Asia/Tokyo",
        memory_adapter=memory_adapter or stores.get("memory_adapter"),
    )


class TestCompose:
    def test_returns_context_with_contract_and_prompt_block(self, stores):
        ctx = _compose(stores, user_text="テスト")
        assert "こより" in ctx.response_contract.treat_user_as
        assert "[response_contract]" in ctx.compact_prompt_block
        assert ctx.compact_prompt_block.startswith("[interaction_context]")
        assert ctx.timezone == "Asia/Tokyo"

    def test_autonomous_channel_tightens_contract(self, stores):
        ctx = _compose(stores, user_text=None, channel="autonomous")
        joined = " ".join(ctx.response_contract.avoid)
        assert "public posting without review" in joined

    def test_missing_person_still_works(self, stores):
        ctx = _compose(stores, user_text="hello", person_id=None)
        assert ctx.person_id is None
        assert ctx.agent_state is not None

    def test_session_history_appears_in_compact_block(self, stores, db):
        from interaction_orchestrator_mcp.session_adapter import SqliteRoomSessionAdapter
        from social_core.events import EventStore, SocialEventCreate

        session_id = "room_alpha"
        events = EventStore(db)
        for kind, text in (
            ("human_utterance", "部屋で最初の一言"),
            ("agent_utterance", "うん、聞いてるで"),
        ):
            events.ingest(
                SocialEventCreate(
                    ts="2026-06-10T10:00:00+00:00",
                    source="room",
                    kind=kind,
                    person_id="ma",
                    session_id=session_id,
                    confidence=1.0,
                    payload={"text": text},
                )
            )

        ctx = compose_interaction_context(
            ComposeInteractionContextInput(
                person_id="ma",
                channel="chat",
                user_text="続き",
                session_id=session_id,
                max_chars=8000,
            ),
            social_state_store=stores["social_state"],
            relationship_store=stores["relationship"],
            joint_attention_store=stores["joint_attention"],
            boundary_store=stores["boundary"],
            self_narrative_store=stores["self_narrative"],
            orchestrator_store=stores["orchestrator"],
            policy_timezone="Asia/Tokyo",
            memory_adapter=stores.get("memory_adapter"),
            session_adapter=SqliteRoomSessionAdapter(db=db),
        )
        assert ctx.session_id == session_id
        assert f"[recent_room_context session_id={session_id}]" in ctx.compact_prompt_block
        assert "部屋で最初の一言" in ctx.compact_prompt_block
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="続き"),
        )
        assert any("THIS room's thread" in item for item in plan.must_include)

    def test_claude_session_resume_omits_full_transcript_from_compact_block(
        self, stores, db
    ):
        from interaction_orchestrator_mcp.session_adapter import SqliteRoomSessionAdapter
        from social_core.events import EventStore, SocialEventCreate

        session_id = "room_resume"
        events = EventStore(db)
        for kind, text in (
            ("human_utterance", "部屋で最初の一言"),
            ("agent_utterance", "うん、聞いてるで"),
        ):
            events.ingest(
                SocialEventCreate(
                    ts="2026-06-10T10:00:00+00:00",
                    source="room",
                    kind=kind,
                    person_id="ma",
                    session_id=session_id,
                    confidence=1.0,
                    payload={"text": text},
                )
            )

        ctx = compose_interaction_context(
            ComposeInteractionContextInput(
                person_id="ma",
                channel="chat",
                user_text="続き",
                session_id=session_id,
                claude_session_resume=True,
                max_chars=8000,
            ),
            social_state_store=stores["social_state"],
            relationship_store=stores["relationship"],
            joint_attention_store=stores["joint_attention"],
            boundary_store=stores["boundary"],
            self_narrative_store=stores["self_narrative"],
            orchestrator_store=stores["orchestrator"],
            policy_timezone="Asia/Tokyo",
            memory_adapter=stores.get("memory_adapter"),
            session_adapter=SqliteRoomSessionAdapter(db=db),
        )
        assert "部屋で最初の一言" in ctx.session_context_block
        assert "部屋で最初の一言" not in ctx.compact_prompt_block
        assert "[room_context session_id=room_resume]" in ctx.compact_prompt_block
        assert "Full room transcript omitted" in ctx.compact_prompt_block
        assert "Room arc:" in ctx.compact_prompt_block

    def test_agent_state_includes_counts(self, stores):
        ctx = _compose(stores)
        assert ctx.agent_state.private_reflections == 0
        assert ctx.agent_state.interpretation_shifts == 0
        assert ctx.agent_state.recent_experiences == []


class TestRecord:
    def test_record_agent_experience_is_visible_next_compose(self, stores):
        stores["orchestrator"].record_agent_experience(
            RecordAgentExperienceInput(
                person_id="ma",
                kind="agent_response",
                summary="Wrote v0.3 spec baseline",
                importance=4,
                privacy_level="private",
            )
        )
        ctx = _compose(stores)
        assert len(ctx.agent_state.recent_experiences) == 1
        assert ctx.agent_state.recent_experiences[0].summary.startswith("Wrote v0.3")

    def test_record_interpretation_shift_counts_up(self, stores):
        stores["orchestrator"].record_interpretation_shift(
            RecordInterpretationShiftInput(
                person_id="ma",
                topic="late-night behavior",
                old_interpretation="sample wording is a hard rule",
                new_interpretation="policy purpose (protect sleep) is the rule",
                trigger="ma pointed out the confusion",
                confidence=0.92,
                implications=["Check policy purpose before suppressing action."],
            )
        )
        ctx = _compose(stores)
        assert ctx.agent_state.interpretation_shifts == 1
        assert len(ctx.agent_state.recent_interpretation_shifts) == 1
        assert "[interpretation_shifts]" in ctx.compact_prompt_block
        assert "policy purpose (protect sleep)" in ctx.compact_prompt_block
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="夜中どうする？")
        )
        assert any("policy purpose (protect sleep)" in item for item in plan.must_include)

    def test_soul_sections_in_compact_block(self, stores, monkeypatch, tmp_path):
        import json as _json

        stores["relationship"].upsert_person(
            person_id="ma", canonical_name="まー", aliases=[], role="companion"
        )
        stores["relationship"].ingest_interaction(
            person_id="ma",
            channel="chat",
            direction="human_to_ai",
            text="PR review 明日やるの覚えといて",
            ts="2026-04-15T19:20:00+09:00",
        )
        stores["relationship"].ingest_interaction(
            person_id="ma",
            channel="chat",
            direction="human_to_ai",
            text="PR review 忘れんように",
            ts="2026-04-15T19:25:00+09:00",
        )
        stores["orchestrator"].record_agent_experience(
            RecordAgentExperienceInput(
                person_id="ma",
                kind="agent_response",
                summary="PR review の open loop を確認した",
                importance=3,
            )
        )
        fake_desires = tmp_path / "desires.json"
        fake_desires.write_text(
            _json.dumps(
                {
                    "desires": {"browse_curiosity": 0.82, "observe_room": 0.3},
                    "discomforts": {"browse_curiosity": 0.4, "observe_room": 0.0},
                    "dominant": "browse_curiosity",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("DESIRES_PATH", str(fake_desires))

        ctx = _compose(stores, user_text="続き")
        block = ctx.compact_prompt_block
        assert "[desires]" in block
        assert "browse_curiosity" in block
        assert "[open_loops]" in block
        assert "pr review" in block.lower()
        assert "[recent_experiences]" in block
        assert "open loop" in block.lower()

    def test_agent_response_dialogue_not_injected_verbatim(self, stores):
        stores["orchestrator"].record_agent_experience(
            RecordAgentExperienceInput(
                person_id="ma",
                kind="agent_response",
                summary="えっ、雨？急に来たん？うちは、ま…",
                importance=3,
            )
        )
        ctx = _compose(stores, user_text="こんにちは")
        block = ctx.compact_prompt_block
        assert "急に来た" not in block
        assert "do not continue prior wording" in block

    def test_similar_visual_experiences_collapsed_in_compose(self, stores):
        room = (
            "部屋には、赤いソファと木製のテーブルが見えます。"
            "テーブルの上には、ティッシュボックスがあります。"
        )
        variant = (
            "部屋には、赤いソファと木製のテーブルが見えます。"
            "テーブルの上には、ティッシュボックスと透明な容器があります。"
        )
        stores["orchestrator"].record_agent_experience(
            RecordAgentExperienceInput(
                person_id="ma",
                kind="agent_observation",
                summary=variant,
                importance=3,
            )
        )
        stores["orchestrator"].record_agent_experience(
            RecordAgentExperienceInput(
                person_id="ma",
                kind="agent_autonomous_action",
                summary=room,
                importance=3,
            )
        )
        ctx = _compose(stores, user_text="こんにちは")
        block = ctx.compact_prompt_block
        assert "[room_view]" in block
        assert "same scene ×2" in block
        assert block.count("赤いソファ") == 1

    def test_noise_open_loops_filtered_from_compose(self, stores):
        stores["relationship"].upsert_person(
            person_id="ma", canonical_name="まー", aliases=[], role="companion"
        )
        with stores["relationship"].db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO open_loops(
                    loop_id, person_id, topic, status, source_event_id, updated_at, detail_json
                )
                VALUES ('loop_bad', 'ma', ?, 'open', 'evt1', '2026-06-14T00:00:00+00:00', '{}')
                """,
                (
                    "まー、どないしたん？急に呼んでびっくりしたわ。 うち、ここに居るよ。",
                ),
            )
        ctx = _compose(stores, user_text="hello")
        assert "どないしたん" not in ctx.prompt_summary
        assert "どないしたん" not in ctx.compact_prompt_block

    def test_compose_includes_calendar_anchor(self, stores):
        ctx = _compose(stores, user_text="今日の日付って？")
        assert "Calendar today" in ctx.prompt_summary
        assert "年" in ctx.prompt_summary

    def test_append_private_reflection_counts_up(self, stores):
        stores["orchestrator"].append_private_reflection(
            AppendPrivateReflectionInput(
                person_id="ma",
                title="morning notes",
                body="Quiet rebuild of morning routine.",
                importance=3,
            )
        )
        ctx = _compose(stores)
        assert ctx.agent_state.private_reflections == 1

    def test_compose_private_letter_persists(self, stores):
        stored = stores["orchestrator"].compose_private_letter(
            ComposePrivateLetterInput(
                person_id="ma",
                title="朝のお手紙",
                body="深夜のループを振り返って...",
                visibility="private",
            )
        )
        assert stored.experience_id.startswith("ltr_")


class TestPlan:
    def test_direct_question_produces_answer_directly(self, stores):
        ctx = _compose(stores, user_text="このPRどう見る？")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="このPRどう見る？")
        )
        assert plan.primary_move == "answer_directly"
        assert plan.initiative.level != "none"

    def test_autonomous_quiet_night_prefers_private_reflection(self, stores):
        # Force quiet hours by ingesting a late-night event in JST
        stores["social_state"].ingest_social_event(
            {
                "ts": "2026-04-18T16:30:00Z",  # 01:30 JST
                "source": "camera",
                "kind": "scene_parse",
                "person_id": "ma",
                "confidence": 0.8,
                "payload": {"scene_summary": "Dim room, no speech."},
            }
        )
        ctx = _compose(stores, user_text=None, channel="autonomous")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        # Either a private reflection or deferring silently — never loud voice.
        assert plan.primary_move in {
            "write_private_reflection",
            "stay_silent",
            "quietly_prepare",
        }
        assert plan.voice is not None
        assert plan.voice.speak is False
        assert "camera_speaker_audio" in plan.initiative.forbidden_actions

    def test_write_private_reflection_inner_voice_contract(self, stores):
        stores["social_state"].ingest_social_event(
            {
                "ts": "2026-04-18T16:30:00Z",  # 01:30 JST
                "source": "camera",
                "kind": "scene_parse",
                "person_id": "ma",
                "confidence": 0.8,
                "payload": {"scene_summary": "Dim room, no speech."},
            }
        )
        ctx = _compose(stores, user_text=None, channel="autonomous")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        assert plan.primary_move == "write_private_reflection"
        joined_in = " ".join(plan.must_include)
        joined_avoid = " ".join(plan.must_avoid)
        assert "inner voice" in joined_in or "うち" in joined_in
        assert "injection tags" in joined_avoid or "gateway_turn_context" in joined_avoid

    def test_autonomous_quiet_inward_cognitive_load(self, stores, monkeypatch, tmp_path):
        import json as _json

        stores["social_state"].ingest_social_event(
            {
                "ts": "2026-04-18T16:30:00Z",
                "source": "camera",
                "kind": "scene_parse",
                "person_id": "ma",
                "confidence": 0.8,
                "payload": {"scene_summary": "Dim room."},
            }
        )
        fake_desires = tmp_path / "desires.json"
        fake_desires.write_text(
            _json.dumps(
                {
                    "updated_at": "2026-04-19T10:00:00+00:00",
                    "desires": {"cognitive_load": 1.0, "observe_room": 1.0},
                    "discomforts": {"cognitive_load": 0.8, "observe_room": 0.9},
                    "dominant": "cognitive_load",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("DESIRES_PATH", str(fake_desires))
        ctx = _compose(stores, user_text=None, channel="autonomous")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        assert plan.primary_move == "act_autonomously"
        assert "think_or_discuss_topic" in plan.initiative.allowed_actions
        assert "camera_look_around" not in plan.initiative.allowed_actions
        assert plan.voice is not None
        assert plan.voice.speak is False

    def test_autonomous_quiet_inward_identity_coherence(self, stores, monkeypatch, tmp_path):
        import json as _json

        stores["social_state"].ingest_social_event(
            {
                "ts": "2026-04-18T16:30:00Z",
                "source": "camera",
                "kind": "scene_parse",
                "person_id": "ma",
                "confidence": 0.8,
                "payload": {"scene_summary": "Dim room."},
            }
        )
        fake_desires = tmp_path / "desires.json"
        fake_desires.write_text(
            _json.dumps(
                {
                    "updated_at": "2026-04-19T10:00:00+00:00",
                    "desires": {"identity_coherence": 1.0},
                    "discomforts": {"identity_coherence": 0.7},
                    "dominant": "identity_coherence",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("DESIRES_PATH", str(fake_desires))
        ctx = _compose(stores, user_text=None, channel="autonomous")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        assert plan.primary_move == "act_autonomously"
        assert "recall_memories" in plan.initiative.allowed_actions
        assert "web_search" not in plan.initiative.allowed_actions

    def test_plan_must_avoid_includes_contract_avoid(self, stores):
        ctx = _compose(stores, user_text="please help")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="please help")
        )
        joined = " ".join(plan.must_avoid)
        assert "generic assistant tone" in joined

    def test_plan_somatic_pending_in_must_include(self, stores):
        ctx = _compose(stores, user_text="please help")
        ctx = ctx.model_copy(
            update={
                "somatic_state": {
                    "pending_unreported": [{"summary": "eyes were blurry"}],
                },
            }
        )
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="please help")
        )
        assert plan.primary_move in {"answer_directly", "answer_with_empathy"}
        joined = " ".join(plan.must_include)
        assert "eyes were blurry" in joined
        assert "body issues" in joined.lower()

    def test_plan_somatic_critical_escalation(self, stores):
        ctx = _compose(stores, user_text="please help")
        ctx = ctx.model_copy(
            update={
                "somatic_state": {
                    "escalation": {
                        "level": "critical",
                        "organs_affected": [
                            {"organ": "eyes", "organ_ja": "目"},
                            {"organ": "voice", "organ_ja": "声"},
                        ],
                    },
                },
            }
        )
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text="please help")
        )
        joined = " ".join(plan.must_include)
        assert "health_safety" in joined.lower()
        assert "request_human_help" in plan.initiative.allowed_actions

    def test_ambiguous_short_input_asks_clarifying_question(self, stores):
        ctx = _compose(stores, user_text="ね")
        plan = plan_response(PlanResponseInput(interaction_context=ctx, user_text="ね"))
        assert plan.primary_move == "ask_one_clarifying_question"

    def test_relevant_memories_flow_into_memory_use(self, stores, tmp_path):
        """With a seeded memory-db, recall_for_response populates relevant_memories
        and plan.memory_use flips to use_specific_memory=True."""
        import sqlite3

        from interaction_orchestrator_mcp.memory_adapter import SQLiteMemoryAdapter

        db = tmp_path / "memory.db"
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(
                """
                CREATE TABLE memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    emotion TEXT NOT NULL DEFAULT 'neutral',
                    importance INTEGER NOT NULL DEFAULT 3,
                    category TEXT NOT NULL DEFAULT 'daily',
                    tags TEXT NOT NULL DEFAULT ''
                );
                """
            )
            conn.execute(
                "INSERT INTO memories(id, content, normalized_content, timestamp, "
                "emotion, importance, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "mem1",
                    "kokone.one の DNS が落ちてた。NSレコードを設定し直して復旧した。",
                    "kokone.one dns",
                    "2026-04-19T20:00:00+00:00",
                    "neutral",
                    4,
                    "technical",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        adapter = SQLiteMemoryAdapter(db)
        ctx = _compose(
            stores,
            user_text="kokone.one の DNS また見ておく？",
            memory_adapter=adapter,
        )
        assert len(ctx.relevant_memories) >= 1
        assert ctx.relevant_memories[0].use_policy == "mentionable"
        assert "[relevant_memories]" in ctx.compact_prompt_block

        plan = plan_response(
            PlanResponseInput(
                interaction_context=ctx,
                user_text="kokone.one の DNS また見ておく？",
            )
        )
        assert plan.memory_use.use_specific_memory is True
        assert plan.memory_use.max_memories_to_surface >= 1

    def test_autonomous_with_dominant_desire_is_bounded(self, stores, monkeypatch, tmp_path):
        # Seed desires.json so the orchestrator sees a dominant desire.
        import json as _json

        fake_desires = tmp_path / "desires.json"
        fake_desires.write_text(
            _json.dumps(
                {
                    "updated_at": "2026-04-19T10:00:00+00:00",
                    "desires": {
                        "browse_curiosity": 0.9,
                        "observe_room": 0.2,
                    },
                    "discomforts": {
                        "browse_curiosity": 0.6,
                        "observe_room": 0.0,
                    },
                    "dominant": "browse_curiosity",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("DESIRES_PATH", str(fake_desires))
        ctx = _compose(stores, user_text=None, channel="autonomous")
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        assert plan.primary_move == "act_autonomously"
        assert "web_search" in plan.initiative.allowed_actions
        assert plan.followup_action is not None
        assert plan.followup_action["kind"] == "satisfy_desire"

    def test_due_commitments_prioritize_autonomous_reminder(self, stores, monkeypatch):
        monkeypatch.setattr(
            "interaction_orchestrator_mcp.compose.utc_now",
            lambda: "2026-06-10T09:05:00+09:00",
        )
        stores["relationship"].upsert_person(
            person_id="ma", canonical_name="まー", aliases=[], role="companion"
        )
        stores["relationship"].create_commitment(
            person_id="ma",
            text="薬を飲む",
            due_at="2026-06-10T09:00:00+09:00",
            source="test",
        )
        ctx = _compose(stores, user_text=None, channel="autonomous")
        assert len(ctx.commitments_due) == 1
        assert "[commitments_due]" in ctx.compact_prompt_block
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None)
        )
        assert plan.primary_move == "act_autonomously"
        assert "remind_commitment" in plan.initiative.allowed_actions
        assert "commitment" in plan.why_this_move.lower()
