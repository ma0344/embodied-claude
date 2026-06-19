"""LM Studio temporal span extraction for benchmarks (OL2-temporal prototype)."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)
DEFAULT_TZ = "Asia/Tokyo"
DEFAULT_UTILITY_MODEL = "qwen2.5-3b-instruct"


def utility_model() -> str:
    return (
        os.environ.get("PRESENCE_LLM_UTILITY_MODEL")
        or os.environ.get("PRESENCE_LLM_TEMPORAL_MODEL")
        or DEFAULT_UTILITY_MODEL
    )


def _lm_settings() -> tuple[str, str]:
    base = (
        os.environ.get("LM_STUDIO_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:1234"
    ).rstrip("/")
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not token:
        token_file = os.environ.get(
            "LM_STUDIO_TOKEN_FILE",
            str(Path.home() / ".config" / "embodied-claude" / "lmstudio.token"),
        )
        if Path(token_file).is_file():
            token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        token = "lmstudio"
    return base, token


def lm_studio_available() -> bool:
    base, token = _lm_settings()
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{base}/v1/models",
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def _extract_json_blob(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    # Strip // line comments (some models add them and break json.loads)
    text = re.sub(r"//[^\n]*", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


_WEEKDAY_JA = ("月", "火", "水", "木", "金", "土", "日")


def _sunday_start_week_bounds(anchor_day: date) -> tuple[date, date, date, date, date, date]:
    """今週/来週/再来週 as Sun–Sat blocks containing anchor."""
    days_since_sunday = (anchor_day.weekday() + 1) % 7
    this_sun = anchor_day - timedelta(days=days_since_sunday)
    this_sat = this_sun + timedelta(days=6)
    next_sun = this_sun + timedelta(days=7)
    next_sat = next_sun + timedelta(days=6)
    week2_sun = this_sun + timedelta(days=14)
    week2_sat = week2_sun + timedelta(days=6)
    return this_sun, this_sat, next_sun, next_sat, week2_sun, week2_sat


def _calendar_hint(anchor: datetime) -> str:
    """Week boundaries (Sun-start) + day-by-day map for the next two weeks."""
    base = anchor.date()
    this_sun, this_sat, next_sun, next_sat, week2_sun, week2_sat = _sunday_start_week_bounds(
        base
    )
    lines = [
        f"anchor_day: {base.isoformat()} ({_WEEKDAY_JA[base.weekday()]})",
        f"今週 (Sun–Sat): {this_sun.isoformat()} .. {this_sat.isoformat()}",
        f"来週 (Sun–Sat): {next_sun.isoformat()} .. {next_sat.isoformat()}",
        f"再来週 (Sun–Sat): {week2_sun.isoformat()} .. {week2_sat.isoformat()}",
        "day_map:",
    ]
    for offset in range(0, 15):
        day = base + timedelta(days=offset)
        lines.append(f"  +{offset}d: {day.isoformat()} ({_WEEKDAY_JA[day.weekday()]})")
    return "\n".join(lines)


_WEEK_DEFINITIONS = """\
Definitions (Asia/Tokyo). Weeks are Sun–Sat (日曜始まり):
- 今週: the Sun–Sat week that contains anchor_day
- 来週: the next Sun–Sat week immediately after 今週 (7 days)
- 再来週: the Sun–Sat week immediately after 来週
- 来週のX曜日 / 再来週のX曜日: that weekday inside 来週 / 再来週 (single day)
- 来週中: a day Mon–Fri inside 来週 (pick the most likely single weekday if vague)
- 今週末 / 週末: Sat–Sun inside 今週 that are on or after anchor_day (prefer nearer day)
- 平日: Mon–Fri
- 今日 / 明日 / 明後日: anchor +0 / +1 / +2 calendar days
- 一週間後: anchor_day + 7 calendar days
- 来月 / 再来月: calendar month after anchor / two months after anchor
- 来月の頭 / 再来月の頭: 1st day of 来月 / 再来月
- Explicit dates (6月20日): that calendar day (ignore time-of-day)
resolved_date must be YYYY-MM-DD only (no weekday suffix).\
"""


def build_temporal_prompt(*, text: str, anchor_ts: str, tz_name: str = DEFAULT_TZ) -> str:
    tz = ZoneInfo(tz_name)
    raw = anchor_ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    anchor = datetime.fromisoformat(raw).astimezone(tz)
    hint = _calendar_hint(anchor)
    return f"""You resolve Japanese relative calendar expressions in an utterance.
Return ONLY valid JSON (no markdown, no // comments) with keys:
- spans: [{{"original":"phrase","resolved_date":"YYYY-MM-DD","confidence":0.0-1.0}}]
- anchored_text: utterance with relative phrases replaced by dates like 2026年6月19日

{_WEEK_DEFINITIONS}

Use the calendar hint; do not guess dates outside it or in the past.

{hint}

Now: {anchor.isoformat()}
Utterance:
{text}
"""


def _parse_span_dates(payload: dict[str, Any]) -> tuple[list[str], float | None, str | None]:
    spans = payload.get("spans") or []
    dates: list[str] = []
    confidences: list[float] = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        for key in ("resolved_date", "resolved_end"):
            raw = span.get(key)
            if not raw:
                continue
            try:
                dates.append(date.fromisoformat(str(raw)[:10]).isoformat())
            except ValueError:
                continue
        conf = span.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))
    anchored = payload.get("anchored_text")
    anchored_text = str(anchored).strip() if anchored else None
    min_conf = min(confidences) if confidences else None
    return dates, min_conf, anchored_text


def _validate_dates(dates: list[str], *, anchor_ts: str, tz_name: str) -> list[str]:
    tz = ZoneInfo(tz_name)
    raw = anchor_ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    anchor_day = datetime.fromisoformat(raw).astimezone(tz).date()
    lo = anchor_day - timedelta(days=3)
    hi = anchor_day + timedelta(days=400)
    out: list[str] = []
    for item in dates:
        try:
            day = date.fromisoformat(item)
        except ValueError:
            continue
        if lo <= day <= hi:
            out.append(day.isoformat())
    return out


def classify_temporal_with_llm(
    text: str,
    *,
    anchor_ts: str,
    tz_name: str = DEFAULT_TZ,
    model: str | None = None,
) -> tuple[list[str], float | None, str | None, str | None]:
    """Return (dates, min_confidence, anchored_text, raw_or_error)."""
    base, token = _lm_settings()
    chosen = model or utility_model()
    prompt = build_temporal_prompt(text=text, anchor_ts=anchor_ts, tz_name=tz_name)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }
    body = {
        "model": chosen,
        "max_tokens": 400,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
            response = client.post(
                f"{base}/v1/chat/completions",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        return [], None, None, f"HTTP error: {exc}"

    choices = data.get("choices") or []
    if not choices:
        return [], None, None, "empty choices"
    message = choices[0].get("message") or {}
    content = message.get("content")
    raw = content.strip() if isinstance(content, str) else ""
    if not raw:
        return [], None, None, "empty content"

    blob = _extract_json_blob(raw)
    if not blob:
        return [], None, None, raw[:500]
    dates, min_conf, anchored = _parse_span_dates(blob)
    dates = _validate_dates(dates, anchor_ts=anchor_ts, tz_name=tz_name)
    return dates, min_conf, anchored, raw
