"""Tests for OL1 date resolution and OL2 reminder commitments."""

from __future__ import annotations

import json

from relationship_mcp.date_resolution import is_stale, resolve_relative_date
from relationship_mcp.reminder_intent import (
    detect_delivery_mode,
    extract_quoted_speak_line,
    extract_reminder_request,
)


def test_resolve_relative_date_tomorrow():
    resolved = resolve_relative_date(
        topic="明日の PR review",
        updated_at="2026-04-15T19:12:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert resolved is not None
    assert resolved.isoformat() == "2026-04-16"


def test_is_stale_after_resolved_day():
    stale = is_stale(
        topic="明日の会議",
        updated_at="2026-04-15T10:00:00+09:00",
        tz_name="Asia/Tokyo",
        as_of=__import__("datetime").date(2026, 4, 17),
    )
    assert stale is not None
    assert stale.isoformat() == "2026-04-16"


def test_extract_reminder_request_tomorrow_at_ten():
    parsed = extract_reminder_request(
        "明日の10時に会議をリマインドして",
        ts="2026-04-15T19:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "会議" in parsed.title
    assert "2026-04-16T10:00:00" in parsed.due_at


def test_extract_reminder_request_today_rolls_forward():
    parsed = extract_reminder_request(
        "3時に薬を教えて",
        ts="2026-04-15T19:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "2026-04-16T03:00:00" in parsed.due_at


def test_extract_reminder_request_ten_minutes_later_with_quote():
    parsed = extract_reminder_request(
        "１０分後に、「まー、時間やで！！」って say でしゃべって教えて",
        ts="2026-06-16T18:04:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert parsed.speak_line == "まー、時間やで！！"
    assert parsed.delivery == "say"
    assert "2026-06-16T18:14:00" in parsed.due_at


def test_extract_quoted_speak_line():
    assert extract_quoted_speak_line("「お茶飲んで」って言って") == "お茶飲んで"


def test_needs_llm_reminder_parse_when_rule_misses():
    from relationship_mcp.reminder_intent import needs_llm_reminder_parse

    assert needs_llm_reminder_parse("来週の打合せの15分前にリマインドして") is True
    assert needs_llm_reminder_parse("3分後に「まー」と say で教えて") is False
    assert needs_llm_reminder_parse("おはよう") is False


def test_extract_reminder_event_minus_offset():
    parsed = extract_reminder_request(
        "15分後の打合せの10分前にリマインドして",
        ts="2026-06-16T20:53:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "2026-06-16T20:58:00" in parsed.due_at
    assert parsed.speak_line is None
    assert "打合せ" in parsed.title


def test_extract_reminder_long_form_event_minus_offset():
    parsed = extract_reminder_request(
        "15分後に打合せが始まるから、打ち合わせ開始の10分前にリマインドして",
        ts="2026-06-16T20:59:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "2026-06-16T21:04:00" in parsed.due_at
    assert "打合せ" in parsed.title


def test_extract_speak_line_followup():
    from relationship_mcp.reminder_intent import extract_speak_line_followup

    assert extract_speak_line_followup("「打合せの準備してな」でいいよ") == "打合せの準備してな"
    assert extract_speak_line_followup("5分後に「まー」と say で教えて") is None


def test_patch_reminder_speak_line_on_followup(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="15分後の打合せの10分前にリマインドして",
        ts="2026-06-16T20:53:00+09:00",
        source_event_id="evt_remind_1",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1
    assert commitments[0].metadata.get("speak_line") is None
    assert "2026-06-16T20:58:00" in commitments[0].due_at

    store.note_human_utterance_for_loops(
        person_id="ma",
        text="「打合せの準備してな」でいいよ",
        ts="2026-06-16T20:55:00+09:00",
        source_event_id="evt_remind_2",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert commitments[0].metadata.get("speak_line") == "打合せの準備してな"
    assert commitments[0].text == "打合せの準備してな"


def test_detect_delivery_mode_nudge_only():
    assert detect_delivery_mode("10時にテキストだけでリマインドして") == "nudge_only"


def test_note_human_creates_reminder_commitment(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="明日の9時に歯医者をリマインドして",
        ts="2026-04-15T18:00:00+09:00",
        source_event_id="evt_remind_1",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1
    assert commitments[0].due_at is not None
    assert "2026-04-16T09:00:00" in commitments[0].due_at


def test_note_human_creates_reminder_with_speak_line_metadata(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「まー、時間やで」と say で教えて",
        ts="2026-06-16T18:04:00+09:00",
        source_event_id="evt_remind_quote",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1
    assert commitments[0].metadata.get("speak_line") == "まー、時間やで"
    assert commitments[0].metadata.get("delivery") == "say"
    assert "2026-06-16T18:14:00" in commitments[0].due_at


def test_reminder_commitment_dedupes_same_due_at(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「A」と教えて",
        ts="2026-06-16T18:04:00+09:00",
        source_event_id="evt_remind_a",
    )
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「B」と教えて",
        ts="2026-06-16T18:04:30+09:00",
        source_event_id="evt_remind_b",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1


def test_close_stale_open_loops_on_ingest(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="明日の会議の準備したい",
        ts="2026-04-15T10:00:00+09:00",
    )
    assert len(store.list_open_loops(person_id="ma")) == 1

    closed = store.close_stale_open_loops(
        person_id="ma",
        as_of="2026-04-17T12:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert len(closed) == 1
    assert store.list_open_loops(person_id="ma") == []


def test_list_due_commitments_within_catch_up_window(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.create_commitment(
        person_id="ma",
        text="standup",
        due_at="2026-04-16T09:00:00+09:00",
        source="test",
        metadata={"speak_line": "まー、standup の時間やで"},
    )
    due = store.list_due_commitments(
        person_id="ma",
        as_of="2026-04-16T09:05:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert len(due) == 1
    assert due[0].text == "standup"
    assert due[0].metadata.get("speak_line") == "まー、standup の時間やで"

    future = store.list_due_commitments(
        person_id="ma",
        as_of="2026-04-15T09:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert future == []


def test_open_loop_detail_has_resolved_date(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="明日は会議がある",
        ts="2026-04-15T10:00:00+09:00",
    )
    row = store.db.fetchone(
        "SELECT topic, detail_json FROM open_loops WHERE person_id = ? AND status = 'open'",
        ("ma",),
    )
    assert row is not None
    detail = json.loads(row["detail_json"])
    assert detail.get("resolved_date") == "2026-04-16"
    assert row["topic"].startswith("2026年4月16日")
    assert detail.get("original_topic") == "明日は会議がある"


def test_open_loop_ambiguous_span_flags_confirmation(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="来週中に会議の準備をしたい",
        ts="2026-06-19T10:00:00+09:00",
    )
    row = store.db.fetchone(
        "SELECT topic, detail_json FROM open_loops WHERE person_id = ? AND status = 'open'",
        ("ma",),
    )
    assert row is not None
    assert row["topic"] == "来週中に会議の準備をしたい"
    detail = json.loads(row["detail_json"])
    assert detail.get("needs_date_confirmation") is True
    assert "来週中" in detail.get("ambiguous_phrases", [])
    loops = store.list_open_loops(person_id="ma")
    assert loops[0].needs_date_confirmation is True


def test_close_stale_anchored_loop_uses_resolved_date(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="明日は会議がある",
        ts="2026-04-15T10:00:00+09:00",
    )
    closed = store.close_stale_open_loops(
        person_id="ma",
        as_of="2026-04-17T10:00:00+09:00",
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_list_open_loops_reanchors_legacy_topic(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.db.execute(
        """
        INSERT INTO open_loops(
            loop_id, person_id, topic, status, source_event_id, updated_at, detail_json
        )
        VALUES (?, ?, ?, 'open', ?, ?, ?)
        """,
        (
            "loop_legacy",
            "ma",
            "明日の天気ってどう",
            "evt1",
            "2026-06-18T20:00:00+09:00",
            '{"kind":"future_task_or_question","resolved_date":"2026-06-19"}',
        ),
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    assert loops[0].topic.startswith("2026年6月19日")
    row = store.db.fetchone(
        "SELECT topic, detail_json FROM open_loops WHERE loop_id = ?",
        ("loop_legacy",),
    )
    assert row["topic"].startswith("2026年6月19日")
    detail = json.loads(row["detail_json"])
    assert detail.get("original_topic") == "明日の天気ってどう"


def test_list_open_loops_includes_ol_gate_detail(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-detail",
        source_text="明日、肉じゃがを作る",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月26日、肉じゃがを作る",
        action_terms=["肉じゃが"],
        completion_verbs=[],
        detail={
            "kind": "ol_gate",
            "utterance_kind": "future_commitment",
            "temporal_phrase": "明日",
            "object_phrase": "肉じゃがを",
            "action_phrase": "作る",
            "resolved_date": "2026-06-26",
        },
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    assert loops[0].detail.get("object_phrase") == "肉じゃがを"
    assert loops[0].detail.get("action_phrase") == "作る"
    assert loops[0].detail.get("temporal_phrase") == "明日"
    assert loops[0].detail.get("action_terms") == ["肉じゃが"]


def test_apply_ol_gate_anchors_unanchored_topic_from_temporal_detail(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-anchor",
        source_text="明日、県に提出する書類を作るよ",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="県に提出する書類 作る",
        action_terms=["県に提出する書類"],
        completion_verbs=["作った"],
        detail={
            "kind": "ol_gate",
            "utterance_kind": "future_commitment",
            "temporal_phrase": "明日",
            "event": {
                "what": "県に提出する書類",
                "effective_when_phrase": "明日",
                "action_phrase": "作る",
            },
        },
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    assert loops[0].topic.startswith("2026年6月26日")
    assert loops[0].detail.get("resolved_date") == "2026-06-26"


def test_apply_ol_gate_creates_future_loop(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-ol",
        source_text="明日、角煮を作る",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月26日、角煮を作る",
        action_terms=["角煮"],
        completion_verbs=[],
        detail={
            "kind": "ol_gate",
            "utterance_kind": "future_commitment",
            "resolved_date": "2026-06-26",
        },
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    assert "角煮" in loops[0].topic


def test_apply_ol_gate_ol5_closes_matching_loop(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-create",
        source_text="明日、角煮を作る",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月26日、角煮を作る",
        action_terms=["角煮"],
        completion_verbs=[],
        detail={"kind": "ol_gate", "resolved_date": "2026-06-26", "action_terms": ["角煮"]},
    )
    closed = store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-26T18:00:00+09:00",
        source_event_id="evt-done",
        source_text="角煮、作った",
        create_open_loop=False,
        try_ol5_close=True,
        loop_topic="",
        action_terms=["角煮"],
        completion_verbs=["作った"],
        detail={"kind": "ol_gate", "utterance_kind": "past_completion"},
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_apply_ol_gate_ol5_unions_stored_and_ingest_verbs(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-create",
        source_text="明日、角煮を作る",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月26日、角煮を作る",
        action_terms=["角煮"],
        completion_verbs=["作った", "できた"],
        detail={"kind": "ol_gate", "resolved_date": "2026-06-26"},
    )
    closed = store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-26T18:00:00+09:00",
        source_event_id="evt-done",
        source_text="角煮、完成した",
        create_open_loop=False,
        try_ol5_close=True,
        loop_topic="",
        action_terms=["角煮"],
        completion_verbs=["完成した"],
        detail={"kind": "ol_gate", "utterance_kind": "past_completion"},
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_apply_ol_gate_ol5_closes_only_matching_loop_when_multiple_open(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    for source_event_id, source_text, loop_topic, action_terms in (
        (
            "evt-niku",
            "明日、肉じゃがを作る",
            "2026年6月28日、肉じゃがを作る",
            ["肉じゃが"],
        ),
        (
            "evt-live",
            "明日、ライブに行く",
            "2026年6月27日、18:00にライブに行く",
            ["ライブ"],
        ),
    ):
        store.apply_ol_gate_decision(
            person_id="ma",
            ts="2026-06-25T10:00:00+09:00",
            source_event_id=source_event_id,
            source_text=source_text,
            create_open_loop=True,
            try_ol5_close=False,
            loop_topic=loop_topic,
            action_terms=action_terms,
            completion_verbs=[],
            detail={"kind": "ol_gate", "action_terms": action_terms},
        )
    closed = store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-27T05:04:14+00:00",
        source_event_id="evt-done-live",
        source_text="ちょっと早かったけど、ライブ、行ってきた",
        create_open_loop=False,
        try_ol5_close=True,
        loop_topic="",
        action_terms=["ライブ"],
        completion_verbs=["行ってきた", "行った"],
        detail={"kind": "ol_gate", "utterance_kind": "past_completion"},
    )
    assert closed == ["2026年6月27日、18:00にライブに行く"]
    open_topics = [loop.topic for loop in store.list_open_loops(person_id="ma")]
    assert open_topics == ["2026年6月28日、肉じゃがを作る"]


def test_apply_ol_gate_ol5_closes_sanpo_with_short_object_in_utterance(store):
    """散歩に行く loop must close on 「散歩、行ってきた」— not only full phrase match."""
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-28T12:13:47+09:00",
        source_event_id="evt-sanpo",
        source_text="明日 散歩に行く 終わったら すぐ 行く",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月29日 散歩に行く 終わったら すぐ 行く",
        action_terms=["散歩に行く"],
        completion_verbs=["行ってきた", "行った", "出かけてきた"],
        detail={
            "kind": "ol_gate",
            "object_phrase": "散歩に行く",
            "action_terms": ["散歩に行く"],
            "completion_verbs": ["行ってきた", "行った", "出かけてきた"],
        },
    )
    closed = store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T12:00:00+09:00",
        source_event_id="evt-sanpo-done",
        source_text="散歩、行ってきた",
        create_open_loop=False,
        try_ol5_close=True,
        loop_topic="",
        action_terms=["散歩"],
        completion_verbs=["行ってきた"],
        detail={"kind": "ol_gate", "utterance_kind": "past_completion"},
    )
    assert closed == ["2026年6月29日 散歩に行く 終わったら すぐ 行く"]
    assert store.list_open_loops(person_id="ma") == []


def test_apply_ol_gate_ol5_closes_dish_wash_with_shorter_object(store):
    """お皿洗い loop closes on 「お皿洗ったよ」— ingest object お皿 matches loop label."""
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-30T12:15:00+09:00",
        source_event_id="evt-dishes-open",
        source_text="お皿洗いもしてくる",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月30日 お皿洗い してくる",
        action_terms=["お皿洗い"],
        completion_verbs=["洗った", "終わった"],
        detail={
            "kind": "ol_gate",
            "action_terms": ["お皿洗い"],
            "event": {"what": "お皿洗い", "action_phrase": "してくる"},
            "activity_frame": {
                "label": "お皿洗い",
                "object_phrase": None,
                "action_stem": "し",
                "mode": "departure",
                "gloss": "お皿洗い",
            },
        },
    )
    closed = store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-30T12:18:45+09:00",
        source_event_id="evt-dishes-done",
        source_text="お皿洗ったよ",
        create_open_loop=False,
        try_ol5_close=True,
        loop_topic="",
        action_terms=["お皿"],
        completion_verbs=["洗った"],
        detail={"kind": "ol_gate", "utterance_kind": "past_completion"},
    )
    assert closed == ["2026年6月30日 お皿洗い してくる"]
    assert store.list_open_loops(person_id="ma") == []


def test_note_human_utterance_skips_rule_loops_when_disabled(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="また明日！",
        ts="2026-06-25T10:00:00+09:00",
        source_event_id="evt-phatic",
        rule_open_loops=False,
    )
    assert store.list_open_loops(person_id="ma") == []


def test_ol6_mark_check_and_close_on_short_confirm(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T08:00:00+09:00",
        source_event_id="evt-clean",
        source_text="今日10時ごろまで部屋の掃除",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月29日 部屋の掃除 10時ごろまで",
        action_terms=["掃除"],
        completion_verbs=["終わった", "片付けた"],
        detail={
            "resolved_date": "2026-06-29",
            "until_phrase": "10時ごろまで",
        },
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    loop_id = loops[0].id
    store.mark_loop_check_asked(
        loop_id=loop_id,
        person_id="ma",
        ts="2026-06-29T10:05:00+09:00",
        topic=loops[0].topic,
        ask_snippet="掃除、終わった？",
    )
    closed = store.try_ol6_pending_close(
        person_id="ma",
        text="終わったよ",
        ts="2026-06-29T10:06:00+09:00",
        source_event_id="evt-confirm",
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_ol6_pending_clear_on_denial(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T08:00:00+09:00",
        source_event_id="evt-doc",
        source_text="書類15時まで",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月29日 書類 15時まで",
        action_terms=["書類"],
        completion_verbs=["提出した"],
        detail={"resolved_date": "2026-06-29", "until_phrase": "15時まで"},
    )
    loop_id = store.list_open_loops(person_id="ma")[0].id
    store.mark_loop_check_asked(
        loop_id=loop_id,
        person_id="ma",
        ts="2026-06-29T15:05:00+09:00",
        topic="書類",
    )
    assert store.try_ol6_pending_close(
        person_id="ma",
        text="まだ",
        ts="2026-06-29T15:06:00+09:00",
        source_event_id="evt-deny",
    ) == []
    detail = store.list_open_loops(person_id="ma")[0].detail
    assert "pending_check" not in detail
    assert detail.get("check_asked_at")


def test_ol7_pending_candidate_then_confirm_close(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T08:00:00+09:00",
        source_event_id="evt-walk",
        source_text="散歩に行く",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="散歩に行く",
        action_terms=["散歩"],
        completion_verbs=["行ってきた"],
        detail={"utterance": "散歩に行く"},
    )
    loop_id = store.list_open_loops(person_id="ma")[0].id
    store.set_ol7_pending_candidate(
        loop_id=loop_id,
        person_id="ma",
        ts="2026-06-29T09:00:00+09:00",
        source_utterance="ただいま",
        completion_summary="散歩から帰宅",
    )
    detail = store.list_open_loops(person_id="ma")[0].detail
    pending = detail.get("pending_check")
    assert pending["trigger"] == "ol7_return_signal"
    assert not pending.get("asked_at")
    store.mark_loop_check_asked(
        loop_id=loop_id,
        person_id="ma",
        ts="2026-06-29T09:00:05+09:00",
        topic="散歩に行く",
        ask_snippet="散歩行ってきたん？",
        trigger="ol7_return_signal",
    )
    closed = store.try_ol6_pending_close(
        person_id="ma",
        text="うん、気持ちよかった～",
        ts="2026-06-29T09:01:00+09:00",
        source_event_id="evt-affirm",
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_ol7_pending_candidate_without_asked_at_confirm_close(store):
    """Organic Koyori confirm without mark_loop_check_asked still closes."""
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T08:00:00+09:00",
        source_event_id="evt-walk",
        source_text="散歩に行く",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="これから 散歩 行ってくる",
        action_terms=["散歩"],
        completion_verbs=["行ってきた"],
        detail={"utterance": "これから 散歩 行ってくる"},
    )
    loop_id = store.list_open_loops(person_id="ma")[0].id
    store.set_ol7_pending_candidate(
        loop_id=loop_id,
        person_id="ma",
        ts="2026-06-29T09:00:00+09:00",
        source_utterance="ただいま",
        completion_summary="散歩から帰宅",
    )
    closed = store.try_ol6_pending_close(
        person_id="ma",
        text="できたよ！",
        ts="2026-06-29T09:05:00+09:00",
        source_event_id="evt-affirm",
    )
    assert closed
    assert store.list_open_loops(person_id="ma") == []


def test_ol7_immediate_close_by_ids(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T08:00:00+09:00",
        source_event_id="evt-nap",
        source_text="お昼寝する",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="お昼寝する",
        action_terms=["お昼寝"],
        completion_verbs=["終わった"],
        detail={},
    )
    loop_id = store.list_open_loops(person_id="ma")[0].id
    closed = store.close_open_loops_by_ids(
        person_id="ma",
        loop_ids=[loop_id],
        ts="2026-06-29T09:30:00+09:00",
        source_event_id="evt-done",
        source_text="昼寝終わった",
        close_kind="ol7_completion",
    )
    assert closed == ["お昼寝する"]
    assert store.list_open_loops(person_id="ma") == []


def test_close_stale_skips_until_completed_policy(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.db.execute(
        """
        INSERT INTO open_loops(
            loop_id, person_id, topic, status, source_event_id, updated_at, detail_json
        )
        VALUES (?, ?, ?, 'open', ?, ?, ?)
        """,
        (
            "loop_doc",
            "ma",
            "県に提出する書類を作る",
            "evt1",
            "2026-06-28T10:00:00+09:00",
            json.dumps(
                {
                    "kind": "future_task_or_question",
                    "resolved_date": "2026-06-28",
                    "stale_policy": "until_completed",
                }
            ),
        ),
    )
    closed = store.close_stale_open_loops(
        person_id="ma",
        as_of="2026-06-30T10:00:00+09:00",
    )
    assert closed == []
    assert store.list_open_loops(person_id="ma")[0].status == "open"


def test_apply_ol_gate_sets_until_completed_without_resolved_date(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-29T10:00:00+09:00",
        source_event_id="evt-doc",
        source_text="県に提出する書類を作る",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="県に提出する書類を作る",
        action_terms=["書類"],
        completion_verbs=["提出した"],
        detail={"utterance": "県に提出する書類を作る"},
    )
    loop = store.list_open_loops(person_id="ma")[0]
    assert loop.detail.get("stale_policy") == "until_completed"
