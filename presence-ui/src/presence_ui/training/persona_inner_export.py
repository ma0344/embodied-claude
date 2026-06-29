"""RP-2c — export inner-voice prose for persona LoRA (private reflections + archive)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from presence_ui.training.reflection_text import strip_reflection_noise
from presence_ui.training.cheerleader_strip import strip_trailing_cheerleader_closings
from presence_ui.training.persona_curation import training_dir
from presence_ui.training.persona_export import (
    PersonaExportStats,
    _has_keigo,
    _has_tool_markers,
    _is_meta_parenthetical_only,
    _normalize_pair_text,
    load_soul_core_text,
)

_INNER_CUE_PREFIX = "（内省・非公開）"
_OVERNIGHT_INNER_FENCE = re.compile(
    r"^\[overnight_inner_voice\]\s*|\s*\[/overnight_inner_voice\]$",
    re.I,
)
_MIN_BODY_CHARS = 24
_MAX_BODY_CHARS = 1200
_GW_S1_V0_PLACEHOLDER = re.compile(
    r"GW-S1 がここを埋める|v0 は一節を眺め直すだけ|v0 は一節を眺め返すだけ"
)
_PRIVATE_NOTE_TITLE = re.compile(
    r"^Private note \d{4}-\d{2}-\d{2} \d{1,2}:\d{2} UTC$",
    re.I,
)
_AUTONOMOUS_MEMORY_TRACE = re.compile(r"^（自律の記憶なぞり）|^（記憶なぞり")
_EPISODE_SUMMARY_MARKERS = ("【会話の区切り】", "【会話の一区切り】", "episode_close")
_SOCIAL_CONTEXT_INJECT = re.compile(r"\[Social context\]", re.I)


@dataclass(frozen=True, slots=True)
class InnerTrainingRow:
    source: str
    user_cue: str
    body: str
    ts: str = ""


def inner_voice_archive_path() -> Path:
    raw = os.environ.get("PERSONA_INNER_VOICE_ARCHIVE_JSONL", "").strip()
    if raw:
        return Path(raw).expanduser()
    return training_dir() / "inner-voice-archive.jsonl"


def append_inner_voice_archive(
    *,
    local_day: str,
    dreamed_at: str,
    body: str,
) -> None:
    """Append one overnight inner-voice row when dreaming saves digest (RP-2c)."""
    cleaned = strip_reflection_noise(_strip_overnight_fence(body))
    if len(cleaned) < _MIN_BODY_CHARS:
        return
    path = inner_voice_archive_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "overnight_inner_voice",
        "local_day": local_day,
        "dreamed_at": dreamed_at,
        "body": cleaned,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _strip_overnight_fence(text: str) -> str:
    body = (text or "").strip()
    body = _OVERNIGHT_INNER_FENCE.sub("", body).strip()
    return body


def _cue_for_private_reflection(title: str) -> str:
    label = (title or "").strip()
    if label:
        return f"{_INNER_CUE_PREFIX}{label}"
    return f"{_INNER_CUE_PREFIX}一人で考える。"


def _cue_for_overnight(local_day: str) -> str:
    day = (local_day or "").strip()
    if day:
        return f"{_INNER_CUE_PREFIX}今朝、{day} の夜を振り返る。"
    return f"{_INNER_CUE_PREFIX}今朝、昨夜のことを振り返る。"


def _is_gw_s1_v0_pause_placeholder(text: str) -> bool:
    return bool(_GW_S1_V0_PLACEHOLDER.search(text or ""))


def _is_autonomous_memory_trace(text: str) -> bool:
    """Gateway recall_memories_direct — STM episode bullets, not inner voice."""
    stripped = (text or "").strip()
    if _AUTONOMOUS_MEMORY_TRACE.match(stripped):
        return True
    return "記憶なぞり" in stripped[:80]


def _is_conversation_episode_dump(text: str) -> bool:
    """STM episode_close summaries and injected social context."""
    body = text or ""
    if any(marker in body for marker in _EPISODE_SUMMARY_MARKERS):
        return True
    return bool(_SOCIAL_CONTEXT_INJECT.search(body))


def _is_private_note_timestamp_stub(title: str, body: str) -> bool:
    """Auto-generated gateway title with no real reflection body."""
    title = (title or "").strip()
    body = (body or "").strip()
    if not title.startswith("Private note "):
        return False
    if _PRIVATE_NOTE_TITLE.match(title) and (not body or body == title or _PRIVATE_NOTE_TITLE.match(body)):
        return True
    return body == title and bool(_PRIVATE_NOTE_TITLE.match(title))


def inner_body_usable(text: str) -> bool:
    body = strip_trailing_cheerleader_closings(strip_reflection_noise(text))
    if _is_gw_s1_v0_pause_placeholder(body):
        return False
    if _is_autonomous_memory_trace(body):
        return False
    if _is_conversation_episode_dump(body):
        return False
    if _PRIVATE_NOTE_TITLE.match(body):
        return False
    if len(body) < _MIN_BODY_CHARS or len(body) > _MAX_BODY_CHARS:
        return False
    if _has_tool_markers(body):
        return False
    if _has_keigo(body) and "うち" not in body[:60]:
        return False
    if _is_meta_parenthetical_only(body):
        return False
    if body.startswith("[dream_digest]") or "[/dream_digest]" in body:
        return False
    return True


def _prepare_body(text: str) -> str:
    return strip_trailing_cheerleader_closings(strip_reflection_noise(text)).strip()


def _load_private_reflection_rows(
    db: object,
    *,
    person_id: str | None,
    limit: int,
) -> list[InnerTrainingRow]:
    args: list[object] = []
    where = ""
    if person_id:
        where = "WHERE person_id = ? OR person_id IS NULL"
        args.append(person_id)
    args.append(max(1, min(limit, 500)))
    rows = db.fetchall(  # type: ignore[attr-defined]
        f"""
        SELECT ts, title, body FROM private_reflections
        {where}
        ORDER BY ts DESC
        LIMIT ?
        """,
        tuple(args),
    )
    out: list[InnerTrainingRow] = []
    for row in rows:
        title = str(row["title"] or "")
        body = _prepare_body(str(row["body"] or ""))
        ts = str(row["ts"] or "")
        if _is_private_note_timestamp_stub(title, body):
            continue
        if _is_autonomous_memory_trace(title):
            continue
        if _is_gw_s1_v0_pause_placeholder(body):
            continue
        if _is_autonomous_memory_trace(body):
            continue
        if _is_conversation_episode_dump(body):
            continue
        if not inner_body_usable(body):
            if _is_private_note_timestamp_stub(title, title):
                continue
            chunk = _prepare_body(title)
            if inner_body_usable(chunk) and not _is_private_note_timestamp_stub(title, chunk):
                body = chunk
            else:
                continue
        out.append(
            InnerTrainingRow(
                source="private_reflection",
                user_cue=_cue_for_private_reflection(title),
                body=body,
                ts=ts,
            )
        )
    return out


def _load_archive_rows(*, limit: int) -> list[InnerTrainingRow]:
    path = inner_voice_archive_path()
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[InnerTrainingRow] = []
    for raw in reversed(lines[-limit:]):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        body = _prepare_body(str(record.get("body") or ""))
        if not inner_body_usable(body):
            continue
        local_day = str(record.get("local_day") or "")
        out.append(
            InnerTrainingRow(
                source="overnight_inner_voice",
                user_cue=_cue_for_overnight(local_day),
                body=body,
                ts=str(record.get("dreamed_at") or ""),
            )
        )
    return out


def _dedupe_rows(rows: list[InnerTrainingRow]) -> tuple[list[InnerTrainingRow], int]:
    seen: set[str] = set()
    kept: list[InnerTrainingRow] = []
    skipped = 0
    for row in rows:
        key = _normalize_pair_text(row.body)
        if not key or key in seen:
            skipped += 1
            continue
        seen.add(key)
        kept.append(row)
    return kept, skipped


def collect_inner_training_rows(
    *,
    person_id: str | None = "ma",
    max_rows: int = 500,
) -> tuple[list[InnerTrainingRow], int]:
    from presence_ui.deps import get_stores

    stores = get_stores()
    rows = _load_private_reflection_rows(stores.db, person_id=person_id, limit=max_rows)
    rows.extend(_load_archive_rows(limit=max_rows))
    rows.sort(key=lambda item: item.ts, reverse=True)
    return _dedupe_rows(rows[: max_rows * 2])


def export_persona_inner_jsonl(
    *,
    repo_root: Path,
    output_path: Path,
    person_id: str | None = "ma",
    max_rows: int = 500,
    system_text: str | None = None,
) -> PersonaExportStats:
    system = system_text if system_text is not None else load_soul_core_text(repo_root=repo_root)
    rows, skipped = collect_inner_training_rows(person_id=person_id, max_rows=max_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows[:max_rows]:
            record = {
                "kind": "inner",
                "source": row.source,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": row.user_cue},
                    {"role": "assistant", "content": row.body},
                ],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return PersonaExportStats(
        sessions_scanned=0,
        pairs_written=written,
        pairs_skipped=skipped,
    )
