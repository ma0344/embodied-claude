"""Phase B — LLM reminder spec when rule parser cannot resolve due_at."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from relationship_mcp.date_resolution import DEFAULT_TIMEZONE
from relationship_mcp.reminder_intent import (
    ReminderSpec,
    detect_delivery_mode,
    extract_quoted_speak_line,
    extract_reminder_request,
    needs_llm_reminder_parse,
)
from social_core import parse_timestamp

from presence_ui.deps import PresenceStores
from presence_ui.services.llm import _lm_studio_settings, _parse_openai_chat_content

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def llm_reminder_spec_enabled() -> bool:
    return os.getenv("PRESENCE_LLM_REMINDER_SPEC", "1").lower() not in {"0", "false", "no"}


def _extract_json_blob(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
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


def _validate_due_at(due_raw: str, *, base: datetime) -> str | None:
    try:
        due = parse_timestamp(due_raw).astimezone(base.tzinfo)
    except (TypeError, ValueError):
        return None
    if due <= base:
        return None
    if due > base + timedelta(days=30):
        return None
    return due.isoformat()


def parse_llm_reminder_payload(
    payload: dict[str, Any],
    *,
    source_text: str,
    ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> ReminderSpec | None:
    tz = ZoneInfo(tz_name)
    base = parse_timestamp(ts).astimezone(tz)

    due_raw = payload.get("due_at_iso") or payload.get("due_at")
    if not due_raw:
        return None
    due_at = _validate_due_at(str(due_raw), base=base)
    if not due_at:
        return None

    speak_line = payload.get("speak_line")
    if isinstance(speak_line, str):
        speak_line = speak_line.strip()[:240] or None
    else:
        speak_line = extract_quoted_speak_line(source_text)

    delivery_raw = str(payload.get("delivery") or detect_delivery_mode(source_text)).strip()
    delivery = "nudge_only" if delivery_raw == "nudge_only" else "say"

    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        title_text = title.strip()[:120]
    elif speak_line:
        title_text = speak_line[:120]
    else:
        title_text = "リマインド"

    if delivery == "say" and not speak_line:
        speak_line = title_text[:240]

    return ReminderSpec(
        title=title_text,
        due_at=due_at,
        speak_line=speak_line,
        delivery=delivery,  # type: ignore[arg-type]
    )


def build_reminder_spec_prompt(*, text: str, ts: str, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    base = parse_timestamp(ts).astimezone(tz)
    return f"""You extract a single reminder specification from まー's Japanese request to Koyori.
Return ONLY one JSON object (no prose) with keys:
- due_at_iso: ISO8601 datetime with timezone offset (Asia/Tokyo context)
- speak_line: exact phrase Koyori should say aloud at remind time (Kansai tone OK)
- delivery: "say" or "nudge_only"
- title: short label for the commitment (<=120 chars)

Rules:
- due_at_iso must be strictly after now and within 30 days.
- If まー quoted words to say, put them in speak_line verbatim.
- Default delivery is "say" unless まー asked for text-only / no voice.

Now (reference): {base.isoformat()}
Utterance:
{text}
"""


async def generate_reminder_spec_llm(
    text: str,
    *,
    ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> ReminderSpec | None:
    base, model, token = _lm_studio_settings()
    prompt = build_reminder_spec_prompt(text=text, ts=ts, tz_name=tz_name)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 280,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    url = f"{base.rstrip('/')}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        raw = _parse_openai_chat_content(response.json())
    if not raw:
        return None
    blob = _extract_json_blob(raw)
    if not blob:
        logger.warning("LLM reminder spec: invalid JSON: %s", raw[:200])
        return None
    spec = parse_llm_reminder_payload(blob, source_text=text, ts=ts, tz_name=tz_name)
    if spec is None:
        logger.warning("LLM reminder spec: validation failed for %r", blob)
    return spec


async def try_create_llm_reminder_commitment(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    tz_name: str | None = None,
) -> dict[str, str] | None:
    """Create commitment via LLM when rule parser missed a reminder-like utterance."""
    if not llm_reminder_spec_enabled():
        return None
    tz = tz_name or stores.policy_timezone or DEFAULT_TIMEZONE
    if extract_reminder_request(text, ts=ts, tz_name=tz) is not None:
        return None
    if not needs_llm_reminder_parse(text):
        return None
    try:
        spec = await generate_reminder_spec_llm(text, ts=ts, tz_name=tz)
    except Exception as exc:
        logger.warning("LLM reminder spec failed: %s", exc)
        return None
    if spec is None:
        return None
    created = stores.relationship.create_reminder_from_spec(
        person_id=person_id,
        spec=spec,
        source_utterance=text,
        source="reminder_llm",
    )
    if created:
        logger.info(
            "LLM reminder created commitment_id=%s due_at=%s",
            created.get("commitment_id"),
            spec.due_at,
        )
    return created
