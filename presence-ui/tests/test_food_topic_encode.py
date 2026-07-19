"""Food topic fact encode — dated meal-record hints."""

from __future__ import annotations

from presence_ui.gateway.food_topic_encode import (
    food_topic_encode_enabled,
    food_topic_facts_from_turns,
    foods_mentioned_in_text,
    format_cook_topic_fact,
    format_food_topic_fact,
    format_jp_month_day,
)


def test_legacy_food_ltm_encode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_FOOD_TOPIC_FACTS", raising=False)
    assert food_topic_encode_enabled() is False
    monkeypatch.setenv("PRESENCE_FOOD_TOPIC_FACTS", "1")
    assert food_topic_encode_enabled() is True


def test_foods_mentioned_prefers_specific_tokens() -> None:
    assert foods_mentioned_in_text("冷たいラーメンにするわ") == ["冷たいラーメン"]
    assert "蕎麦" in foods_mentioned_in_text("そろそろ蕎麦の準備")
    assert foods_mentioned_in_text("窓の外がきれい") == []


def test_format_meal_record_hint() -> None:
    assert format_jp_month_day("2026-07-01") == "2026年7月1日"
    line = format_food_topic_fact("蕎麦", on_date="2026-07-01")
    assert line == "まーは直近で2026年7月1日に麺類（蕎麦）を食べた記録がある"
    assert "麺類" in line
    curry = format_food_topic_fact("カレー", on_date="2026-06-15")
    assert curry == "まーは直近で2026年6月15日にカレーを食べた記録がある"
    cook = format_cook_topic_fact("カレー", on_date="2026-06-15")
    assert cook == "まーは直近で2026年6月15日にカレーを作った記録がある"
    assert "食べた" not in cook


def test_food_facts_from_ma_turns_carry_date() -> None:
    turns = [
        {
            "sender": "ma",
            "message": "この間は蕎麦やったな",
            "timestamp": "2026-07-01T12:30:00+09:00",
        },
        {"sender": "koyori", "message": "蕎麦おいしいよね"},
    ]
    facts = food_topic_facts_from_turns(turns, tz_name="Asia/Tokyo")
    assert any("麺類（蕎麦）" in f and "7月1日" in f for f in facts)
    assert all("【会話" not in f for f in facts)
