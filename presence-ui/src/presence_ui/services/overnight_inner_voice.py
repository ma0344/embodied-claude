"""MEM-5f-c — overnight inner voice synthesis for morning compose."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from social_core.stm import StmEntry

from presence_ui.deps import get_stores
from presence_ui.services.llm import _lm_studio_settings, _parse_openai_chat_content
from presence_ui.training.reflection_text import strip_reflection_noise

logger = logging.getLogger(__name__)

DEFAULT_INNER_VOICE_MAX_CHARS = 1800


def format_overnight_inner_voice_block(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    return f"[overnight_inner_voice]\n{body}\n[/overnight_inner_voice]"


def _day_bounds_iso(local_day: str, timezone: str) -> tuple[str, str]:
    day = date.fromisoformat(local_day)
    tz = ZoneInfo(timezone)
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day, time.max, tzinfo=tz)
    return start.isoformat(), end.isoformat()


def _collect_private_reflection_bodies(
    *,
    person_id: str,
    local_day: str,
    timezone: str,
) -> list[str]:
    since, until = _day_bounds_iso(local_day, timezone)
    stores = get_stores()
    rows = stores.db.fetchall(
        """
        SELECT title, body FROM private_reflections
        WHERE person_id = ? AND ts >= ? AND ts <= ?
        ORDER BY ts ASC
        LIMIT 24
        """,
        (person_id, since, until),
    )
    bodies: list[str] = []
    for row in rows:
        title = str(row["title"] or "").strip()
        body = strip_reflection_noise(str(row["body"] or ""))
        chunk = body or title
        if chunk:
            bodies.append(chunk[:600])
    return bodies


def collect_overnight_reflection_sources(
    entries: list[StmEntry],
    *,
    person_id: str,
    local_day: str,
    timezone: str,
) -> tuple[list[str], list[str]]:
    """Return (reflection texts, interpretation shift texts) for one dreaming day."""
    reflections: list[str] = []
    for entry in entries:
        if entry.kind == "agent_private_reflection":
            cleaned = strip_reflection_noise(entry.summary)
            if cleaned:
                reflections.append(cleaned[:600])

    db_reflections = _collect_private_reflection_bodies(
        person_id=person_id,
        local_day=local_day,
        timezone=timezone,
    )
    merged = db_reflections + reflections
    shifts = [
        entry.summary.strip()[:400]
        for entry in entries
        if entry.kind == "interpretation_shift"
    ]
    return merged, shifts


def _inner_voice_llm_enabled() -> bool:
    return os.environ.get("PRESENCE_OVERNIGHT_INNER_VOICE_LLM", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _build_inner_voice_prompt(
    reflections: list[str],
    *,
    interpretation_shifts: list[str],
    local_day: str,
) -> str:
    lines = [
        "あなたはこより。次の overnight private reflections を、朝の自分向けメモとして",
        "2〜3段落・一人称・関西弁混じりで thematic にまとめて。",
        "2〜4テーマに整理。ツール名・MCP・注入タグ・[brackets] は禁止。",
        "出力は本文のみ（見出し記号不要）。",
        f"対象日: {local_day}（これは「昨夜まで」の一日。翌朝の自分が読むので、",
        "「今日」は使わず「昨日」または日付で書く。翌日の予定は書かない）。",
        "",
        "[reflections]",
    ]
    for idx, text in enumerate(reflections[:16], start=1):
        lines.append(f"{idx}. {text[:500]}")
    if interpretation_shifts:
        lines.extend(["", "[interpretation_shifts]"])
        for shift in interpretation_shifts[:4]:
            lines.append(f"- {shift[:300]}")
    return "\n".join(lines)


def _fallback_inner_voice(
    reflections: list[str],
    *,
    interpretation_shifts: list[str],
) -> str:
    themes: list[str] = []
    for text in reflections[:6]:
        first = text.split("\n", 1)[0].strip()
        if first and first not in themes:
            themes.append(first[:160])
    paragraphs: list[str] = []
    if themes:
        joined = "\n".join(f"・{theme}" for theme in themes[:4])
        paragraphs.append(f"昨夜、ぼーっと考えてたのはこんな感じやった。\n{joined}")
    if interpretation_shifts:
        paragraphs.append(f"解釈が少し動いた点: {interpretation_shifts[0][:180]}")
    if not paragraphs:
        return ""
    return "\n\n".join(paragraphs)[:DEFAULT_INNER_VOICE_MAX_CHARS]


def synthesize_overnight_inner_voice(
    entries: list[StmEntry],
    *,
    person_id: str = "ma",
    local_day: str,
    timezone: str | None = None,
    use_llm: bool | None = None,
) -> str:
    """Build `[overnight_inner_voice]` block from overnight reflections (MEM-5f-c)."""
    stores = get_stores()
    tz = timezone or stores.policy_timezone
    reflections, shifts = collect_overnight_reflection_sources(
        entries,
        person_id=person_id,
        local_day=local_day,
        timezone=tz,
    )
    if not reflections and not shifts:
        return ""

    if use_llm is None:
        use_llm = _inner_voice_llm_enabled()

    body = ""
    if use_llm:
        base_url, model, token = _lm_studio_settings()
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 420,
            "temperature": 0.45,
            "messages": [
                {
                    "role": "user",
                    "content": _build_inner_voice_prompt(
                        reflections,
                        interpretation_shifts=shifts,
                        local_day=local_day,
                    ),
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
                response = client.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                text = _parse_openai_chat_content(response.json())
            if text and text.strip():
                body = text.strip()[:DEFAULT_INNER_VOICE_MAX_CHARS]
        except Exception as exc:
            logger.warning("Overnight inner voice LLM failed: %s", exc)

    if not body:
        body = _fallback_inner_voice(reflections, interpretation_shifts=shifts)
    return format_overnight_inner_voice_block(body)
