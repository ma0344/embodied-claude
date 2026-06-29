"""GAPI-7b — pending calendar drafts + confirm/affirm detection."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from presence_ui.gateway.calendar_resolve import format_confirm_summary_ja
from presence_ui.gateway.calendar_stage import CalendarResolvedDraft, CalendarStageExtract

_FILLER_PREFIX = re.compile(r"^(?:えっと|えーと|まあ|まー|あの|あ、?|うーん|ん、?)+", re.I)
_TRAILING_PUNCT = re.compile(r"[。!！？、,]+$")
_SOFT_SUFFIXES = (
    "だよ",
    "です",
    "でね",
    "だね",
    "だな",
    "だわ",
    "っす",
    "かな",
    "ね",
    "な",
    "わ",
    "よ",
    "で",
)
_AFFIRM_EXACT = frozenset(
    {
        "ok",
        "オーケー",
        "おっけー",
        "おっけ",
        "うん",
        "はい",
        "ええ",
        "えー",
        "いいよ",
        "いいわ",
        "それで",
        "大丈夫",
        "よろしく",
        "進めて",
        "入れて",
        "お願い",
        "いこう",
        "やって",
        "お願いします",
    }
)
_DENY_EXACT = frozenset(
    {
        "やめ",
        "やめて",
        "キャンセル",
        "違う",
        "ちがう",
        "だめ",
        "しない",
        "いい",
    }
)
_MAX_CONFIRM_REPLY_LEN = 32

CALENDAR_CONFIRM_HONESTY_DIRECTIVE = (
    "Do NOT say you already added, moved, or registered the event "
    "(入れた/入れといた/入れとく/変更した/ずらした/登録した) unless this turn includes "
    "[calendar_write_result] with status=ok."
)


def calendar_confirm_enabled() -> bool:
    import os

    from presence_ui.gateway.calendar_write import calendar_write_enabled

    if not calendar_write_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_CONFIRM", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def normalize_confirm_reply(text: str) -> str:
    """Strip fillers, punctuation, and soft sentence endings for yes/no detection."""
    line = (text or "").strip()
    if not line:
        return ""
    line = _FILLER_PREFIX.sub("", line).strip()
    line = re.sub(r"^[、,\s]+", "", line).strip()
    line = _TRAILING_PUNCT.sub("", line).strip()
    changed = True
    while changed and line:
        changed = False
        for suffix in _SOFT_SUFFIXES:
            if line.endswith(suffix) and len(line) > len(suffix):
                line = line[: -len(suffix)].strip()
                changed = True
                break
    return line


def _confirm_segments(normalized: str) -> list[str]:
    parts = re.split(r"[、,]+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _is_affirm_core(normalized: str) -> bool:
    if not normalized:
        return False
    low = normalized.lower()
    return low in _AFFIRM_EXACT


def _is_deny_core(normalized: str) -> bool:
    if not normalized:
        return False
    low = normalized.lower()
    if low in {"いいよ", "いいわ"}:
        return False
    return low in _DENY_EXACT


def is_calendar_affirmation(text: str) -> bool:
    normalized = normalize_confirm_reply(text)
    if not normalized or len(normalized) > _MAX_CONFIRM_REPLY_LEN:
        return False
    segments = _confirm_segments(normalized)
    if len(segments) > 1:
        return all(_is_affirm_core(segment) for segment in segments)
    return _is_affirm_core(normalized)


def is_calendar_denial(text: str) -> bool:
    normalized = normalize_confirm_reply(text)
    if not normalized or len(normalized) > _MAX_CONFIRM_REPLY_LEN:
        return False
    segments = _confirm_segments(normalized)
    if len(segments) > 1:
        return all(_is_deny_core(segment) for segment in segments)
    return _is_deny_core(normalized)


def _pending_path() -> Path:
    return Path.home() / ".claude" / "presence-ui" / "calendar_pending.json"


@dataclass(slots=True)
class CalendarPendingRecord:
    person_id: str
    status: str  # awaiting_confirm | needs_clarification
    action: str
    calendar_id: str
    topic: str | None
    start_iso: str | None
    end_iso: str | None
    match_label: str
    event_id: str | None
    event_calendar_id: str | None
    event_summary: str | None
    old_start: str | None
    old_end: str | None
    missing_fields: list[str]
    source_utterance: str
    confirm_summary_ja: str
    created_at: str


def load_pending(*, person_id: str) -> CalendarPendingRecord | None:
    path = _pending_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if str(data.get("person_id") or "") != person_id:
        return None
    return CalendarPendingRecord(
        person_id=person_id,
        status=str(data.get("status") or ""),
        action=str(data.get("action") or ""),
        calendar_id=str(data.get("calendar_id") or "primary"),
        topic=data.get("topic"),
        start_iso=data.get("start_iso"),
        end_iso=data.get("end_iso"),
        match_label=str(data.get("match_label") or ""),
        event_id=data.get("event_id"),
        event_calendar_id=data.get("event_calendar_id"),
        event_summary=data.get("event_summary"),
        old_start=data.get("old_start"),
        old_end=data.get("old_end"),
        missing_fields=list(data.get("missing_fields") or []),
        source_utterance=str(data.get("source_utterance") or ""),
        confirm_summary_ja=str(data.get("confirm_summary_ja") or ""),
        created_at=str(data.get("created_at") or ""),
    )


def save_pending(record: CalendarPendingRecord) -> None:
    path = _pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(record), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_pending(*, person_id: str) -> None:
    path = _pending_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return
    if str(data.get("person_id") or "") == person_id:
        path.unlink(missing_ok=True)


def pending_from_resolved(
    *,
    person_id: str,
    source_utterance: str,
    draft: CalendarResolvedDraft,
    created_at: str,
) -> CalendarPendingRecord:
    summary = format_confirm_summary_ja(
        action=draft.action,
        topic=draft.topic,
        start=draft.range.start,
        end=draft.range.end,
        match_label=draft.match_label,
    )
    return CalendarPendingRecord(
        person_id=person_id,
        status="awaiting_confirm",
        action=draft.action,
        calendar_id=draft.calendar_id,
        topic=draft.topic,
        start_iso=draft.range.start.isoformat(),
        end_iso=draft.range.end.isoformat(),
        match_label=draft.match_label,
        event_id=draft.event_id,
        event_calendar_id=draft.event_calendar_id,
        event_summary=draft.event_summary,
        old_start=draft.old_start,
        old_end=draft.old_end,
        missing_fields=[],
        source_utterance=source_utterance,
        confirm_summary_ja=summary,
        created_at=created_at,
    )


def pending_from_clarification(
    *,
    person_id: str,
    source_utterance: str,
    extract: CalendarStageExtract,
    missing_fields: list[str],
    created_at: str,
) -> CalendarPendingRecord:
    return CalendarPendingRecord(
        person_id=person_id,
        status="needs_clarification",
        action=extract.action,
        calendar_id=extract.calendar_id,
        topic=extract.topic,
        start_iso=None,
        end_iso=None,
        match_label="",
        event_id=None,
        event_calendar_id=None,
        event_summary=None,
        old_start=None,
        old_end=None,
        missing_fields=missing_fields,
        source_utterance=source_utterance,
        confirm_summary_ja="",
        created_at=created_at,
    )


def format_calendar_confirm_block(record: CalendarPendingRecord) -> str:
    lines = [
        "[calendar_confirm_pending]",
        f"status={record.status}",
        f"action={record.action}",
        f"calendar_id={record.calendar_id}",
    ]
    if record.status == "needs_clarification":
        lines.append(f"missing={','.join(record.missing_fields)}")
        if record.topic:
            lines.append(f"topic={record.topic}")
    else:
        lines.append(f"summary={record.confirm_summary_ja}")
        if record.topic:
            lines.append(f"topic={record.topic}")
        if record.start_iso:
            lines.append(f"start={record.start_iso}")
        if record.end_iso:
            lines.append(f"end={record.end_iso}")
        if record.match_label:
            lines.append(f"match_label={record.match_label}")
    lines.append("[/calendar_confirm_pending]")
    lines.append("")
    lines.append("[Gateway directive — not for the user]")
    if record.status == "needs_clarification":
        missing = "、".join(record.missing_fields) or "日時またはタイトル"
        directive = (
            f"Calendar write needs more info from まー: {missing}.\n"
            "Ask a short clarifying question in こより voice. "
            "Do NOT write to Google Calendar yet.\n"
            f"{CALENDAR_CONFIRM_HONESTY_DIRECTIVE}"
        )
    elif record.action == "update":
        directive = (
            f"Gateway parsed a calendar UPDATE: {record.confirm_summary_ja}.\n"
            "Ask まー to confirm this is the right event and new time "
            "(例: 「この予定でいい？」). "
            "Gateway writes only after まー affirms on a later turn.\n"
            f"{CALENDAR_CONFIRM_HONESTY_DIRECTIVE}"
        )
    else:
        directive = (
            f"Gateway parsed a calendar CREATE: {record.confirm_summary_ja}.\n"
            "Ask まー to confirm before writing "
            "(例: 「この内容でカレンダーに入れていい？」). "
            "Gateway writes only after まー affirms on a later turn.\n"
            f"{CALENDAR_CONFIRM_HONESTY_DIRECTIVE}"
        )
    lines.append(directive)
    return "\n".join(lines)


def format_calendar_cancel_block() -> str:
    return (
        "[calendar_confirm_pending]\n"
        "status=cancelled\n"
        "[/calendar_confirm_pending]\n\n"
        "[Gateway directive — not for the user]\n"
        "まー cancelled the pending calendar operation. Acknowledge briefly; do not write."
    )


def format_calendar_ingest_failed_block(*, utterance: str) -> str:
    preview = (utterance or "").strip().replace("\n", " ")[:120]
    return (
        "[calendar_confirm_pending]\n"
        "status=ingest_failed\n"
        f"source_utterance={preview}\n"
        "[/calendar_confirm_pending]\n\n"
        "[Gateway directive — not for the user]\n"
        "Gateway could NOT parse this calendar request into a pending draft "
        "(Stage2 extract or date resolution failed).\n"
        "Tell まー honestly that the calendar draft is not ready; ask to repeat "
        "date/time/title clearly (例: 9月8日10時〜17時).\n"
        f"{CALENDAR_CONFIRM_HONESTY_DIRECTIVE}\n"
        "Do NOT reuse an older pending draft from a previous request."
    )


def pending_matches_utterance(
    pending: CalendarPendingRecord,
    utterance: str,
) -> bool:
    return pending.source_utterance.strip() == (utterance or "").strip()
