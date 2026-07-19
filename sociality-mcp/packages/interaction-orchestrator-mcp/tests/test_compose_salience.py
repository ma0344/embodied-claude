"""MEM-8g — compose salience and topic retire tests."""

from __future__ import annotations

from interaction_orchestrator_mcp.compose_salience import (
    apply_compose_memory_salience,
    select_surface_memories,
)
from interaction_orchestrator_mcp.schemas import RelevantMemoryRef
from interaction_orchestrator_mcp.topic_retire import (
    TopicRetireStore,
    detect_user_completion_utterance,
    extract_retire_topics,
    maybe_record_topic_retire,
    memory_matches_retired_topics,
)
from social_core import SocialDB


def _mem(content: str, *, policy: str = "mentionable") -> RelevantMemoryRef:
    return RelevantMemoryRef(
        memory_id="m1",
        content=content,
        relevance=0.9,
        use_policy=policy,  # type: ignore[arg-type]
        reason="test",
    )


class TestComposeSalience:
    def test_episodic_never_mentionable_even_when_only_hits(self) -> None:
        episode = _mem("【会話の区切り】\nまー: 今日の昼は蕎麦やね\n" + ("ログ\n" * 30))
        adjusted = apply_compose_memory_salience(
            [episode],
            user_text="沖縄は梅雨が明けたみたい",
            person_id="ma",
            db=None,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert adjusted[0].use_policy == "background_only"
        assert adjusted[0].reason == "episodic_off_topic"

    def test_literary_passage_off_topic_not_mentionable(self) -> None:
        literary = _mem(
            "青空文庫で読んだ『羅生門』（芥川龍之介）— "
            "どうにもならない事を、どうにかするためには、手段を選んでいる遑はない。"
        )
        adjusted = apply_compose_memory_salience(
            [literary],
            user_text="大丈夫。ぼーっとしとるわけではないで（笑）",
            person_id="ma",
            db=None,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "literary_passage_off_topic"

    def test_literary_passage_stays_when_user_cues_reading(self) -> None:
        literary = _mem(
            "青空文庫で読んだ『羅生門』（芥川龍之介）— 下人は、老婆をつき放すと"
        )
        adjusted = apply_compose_memory_salience(
            [literary],
            user_text="羅生門どうやった？",
            person_id="ma",
            db=None,
        )
        mentionable, _ = select_surface_memories(adjusted)
        assert len(mentionable) == 1
        assert adjusted[0].use_policy == "mentionable"

    def test_fact_memory_stays_mentionable(self) -> None:
        fact = _mem("沖縄の梅雨明けは6月29日頃")
        adjusted = apply_compose_memory_salience(
            [fact],
            user_text="沖縄は梅雨が明けたみたい",
            person_id="ma",
            db=None,
        )
        mentionable, _ = select_surface_memories(adjusted)
        assert len(mentionable) == 1

    def test_prefetch_fact_check_omits_episodic_from_surface(self) -> None:
        episode = _mem("【会話の区切り】\n蕎麦\n" + ("x\n" * 25))
        adjusted = apply_compose_memory_salience(
            [episode],
            user_text="沖縄 梅雨",
            person_id="ma",
            db=None,
            prefetch_fact_check=True,
        )
        mentionable, background = select_surface_memories(
            adjusted,
            prefetch_fact_check=True,
        )
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"

    def test_legacy_food_talk_demoted_prefer_meal_record(self) -> None:
        legacy = _mem("まーが蕎麦の話をした（食事の話題）")
        meal = _mem("まーは直近で7月1日に麺類（蕎麦）を食べた記録がある")
        adjusted = apply_compose_memory_salience(
            [legacy, meal],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
        )
        mentionable, _ = select_surface_memories(adjusted)
        assert all("食べた記録" in m.content for m in mentionable)
        assert not any("話をした" in m.content for m in mentionable)
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "legacy_food_talk_not_meal_record"

    def test_somatic_escalation_push_demoted_when_gate_off(self) -> None:
        push = _mem(
            "体の調子がおかしいで。目と声が同時にダメかも。見てもらえる？"
        )
        adjusted = apply_compose_memory_salience(
            [push],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
            health_safety_active=False,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "somatic_escalation_push_off_topic"

    def test_somatic_escalation_push_stays_when_gate_on(self) -> None:
        push = _mem(
            "体の調子がおかしいで。複数の感覚が同時にダメかも。見てもらえる？"
        )
        adjusted = apply_compose_memory_salience(
            [push],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
            health_safety_active=True,
        )
        mentionable, _ = select_surface_memories(adjusted)
        assert len(mentionable) == 1
        assert adjusted[0].use_policy == "mentionable"
        assert adjusted[0].reason != "somatic_escalation_push_off_topic"

    def test_non_push_body_report_not_demoted_by_somatic_reason(self) -> None:
        body = _mem("目が曇ってたけど、reload で直したで")
        adjusted = apply_compose_memory_salience(
            [body],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
            health_safety_active=False,
        )
        assert adjusted[0].use_policy == "mentionable"
        assert adjusted[0].reason != "somatic_escalation_push_off_topic"

    def test_somatic_push_undemotes_when_gate_turns_on(self) -> None:
        demoted = RelevantMemoryRef(
            memory_id="m1",
            content="体の調子がおかしいで。目と声が同時にダメかも。見てもらえる？",
            relevance=0.9,
            use_policy="do_not_surface",
            reason="somatic_escalation_push_off_topic",
        )
        adjusted = apply_compose_memory_salience(
            [demoted],
            user_text="ねえ",
            person_id="ma",
            db=None,
            health_safety_active=True,
        )
        assert adjusted[0].use_policy == "mentionable"
        assert adjusted[0].reason == "somatic_escalation_push_in_scope"

    def test_vision_caption_dumps_demoted(self) -> None:
        samples = [
            "=== VISION_CAPTION === 部屋の奥には棚がある",
            "--- Center View (room scan) ---\n机の上にコップ",
            "Captured image at 2026-07-19T02:00:00+00:00",
        ]
        for content in samples:
            adjusted = apply_compose_memory_salience(
                [_mem(content)],
                user_text="今日の晩御飯は何にしよ？",
                person_id="ma",
                db=None,
            )
            mentionable, background = select_surface_memories(adjusted)
            assert not mentionable, content
            assert not background, content
            assert adjusted[0].use_policy == "do_not_surface"
            assert adjusted[0].reason == "vision_caption_off_topic"

    def test_literary_desire_prefix_demoted_without_reading_cue(self) -> None:
        literary = _mem(
            "[desire:literary_wander] 青空文庫で読んだ『羅生門』（芥川龍之介）— "
            "下人は、老婆をつき放すと"
        )
        adjusted = apply_compose_memory_salience(
            [literary],
            user_text="大丈夫。ぼーっとしとるわけではないで（笑）",
            person_id="ma",
            db=None,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "literary_passage_off_topic"

    def test_literary_kangaeta_prefix_demoted(self) -> None:
        literary = _mem("考えた。青空『羅生門』— 下人は、老婆をつき放すと")
        adjusted = apply_compose_memory_salience(
            [literary],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "literary_passage_off_topic"

    def test_desire_satisfaction_telemetry_demoted(self) -> None:
        desire = _mem("[desire:observe_room] 部屋を一通り見た。特に変化なし。")
        adjusted = apply_compose_memory_salience(
            [desire],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
        )
        mentionable, background = select_surface_memories(adjusted)
        assert not mentionable
        assert not background
        assert adjusted[0].use_policy == "do_not_surface"
        assert adjusted[0].reason == "desire_satisfaction_telemetry"

    def test_meal_record_not_demoted_by_new_filters(self) -> None:
        meal = _mem("まーは直近で7月1日に麺類（蕎麦）を食べた記録がある")
        adjusted = apply_compose_memory_salience(
            [meal],
            user_text="今日の晩御飯は何にしよ？",
            person_id="ma",
            db=None,
        )
        mentionable, _ = select_surface_memories(adjusted)
        assert len(mentionable) == 1
        assert adjusted[0].use_policy == "mentionable"
        assert adjusted[0].reason == "test"


class TestTopicRetire:
    def test_completion_detection_finite_markers(self) -> None:
        assert detect_user_completion_utterance("お昼ご飯はさっきもう作ったよ")
        assert not detect_user_completion_utterance("沖縄は梅雨が明けたみたい")

    def test_extract_topics_narrow_not_meal_category(self) -> None:
        topics = extract_retire_topics("お昼ご飯の蕎麦はもう作ったよ")
        assert "蕎麦" in topics
        assert "お昼ご飯の蕎麦" in topics
        assert "お昼ご飯" in topics
        assert "ご飯" not in topics
        assert "お昼" not in topics
        assert "もう" not in topics

    def test_lunch_prep_without_soba_matches_slot_retire(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(
            person_id="ma",
            topics=extract_retire_topics("お昼ご飯の蕎麦はもう作ったよ"),
        )
        prep = _mem("お昼ご飯の準備はだいたい終わった")
        adjusted = apply_compose_memory_salience(
            [prep],
            user_text="お疲れ",
            person_id="ma",
            db=db,
        )
        assert adjusted[0].reason == "topic_retired"

    def test_nihachi_soba_matches_soba_token(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(person_id="ma", topics=["蕎麦"])
        soba = _mem("やっぱり二八蕎麦がいいね")
        adjusted = apply_compose_memory_salience(
            [soba],
            user_text="ねえ",
            person_id="ma",
            db=db,
        )
        assert adjusted[0].reason == "topic_retired"

    def test_pivot_reopen_on_new_lunch_dish(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(
            person_id="ma",
            topics=extract_retire_topics("お昼ご飯の蕎麦はもう作ったよ"),
        )
        assert store.active_retired_topics(person_id="ma")
        store.clear_matching_topics(
            person_id="ma",
            user_text="明日のお昼はお好み焼きを作るんだっけ？",
        )
        assert not store.active_retired_topics(person_id="ma")

    def test_slot_only_when_no_named_dish(self) -> None:
        topics = extract_retire_topics("お昼ご飯はさっきもう作ったよ")
        assert topics == ["お昼ご飯"]

    def test_okonomiyaki_memory_not_retired_by_soba(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(person_id="ma", topics=extract_retire_topics("お昼ご飯の蕎麦はもう作ったよ"))
        okonomiyaki = _mem("晩御飯はお好み焼きにする予定")
        adjusted = apply_compose_memory_salience(
            [okonomiyaki],
            user_text="お疲れさん",
            person_id="ma",
            db=db,
        )
        assert adjusted[0].use_policy == "mentionable"
        assert adjusted[0].reason != "topic_retired"

    def test_memory_match_substring_only(self) -> None:
        assert memory_matches_retired_topics("今日の昼は蕎麦やね", ["蕎麦"])
        assert not memory_matches_retired_topics("沖縄の梅雨明け", ["蕎麦"])

    def test_retire_and_filter_in_compose(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(
            person_id="ma",
            topics=["蕎麦", "昼ご飯"],
            source_utterance="お昼ご飯はさっきもう作ったよ",
        )
        episode = _mem("【会話の区切り】\nまー: 蕎麦おいしかった\n" + ("y\n" * 25))
        adjusted = apply_compose_memory_salience(
            [episode],
            user_text="沖縄は梅雨が明けたみたい",
            person_id="ma",
            db=db,
        )
        assert adjusted[0].use_policy == "background_only"
        assert adjusted[0].reason == "topic_retired"

    def test_reopen_when_user_mentions_topic(self, tmp_path) -> None:
        db = SocialDB(tmp_path / "social.db")
        store = TopicRetireStore(db)
        store.retire_topics(person_id="ma", topics=["蕎麦", "昼ご飯"])
        assert "蕎麦" in store.active_retired_topics(person_id="ma")
        store.clear_matching_topics(person_id="ma", user_text="今日の蕎麦どうだった？")
        assert "蕎麦" not in store.active_retired_topics(person_id="ma")
