"""STM episode closure — MEM-2 gateway orchestration."""

from __future__ import annotations

import os

import httpx
from social_core.stm import StmStore
from social_core.stm_episode import summarize_episode_turns


def _episode_ts_from_turns(turns: list[dict[str, str | None]]) -> str | None:
    for turn in reversed(turns):
        raw = turn.get("timestamp") or turn.get("ts")
        if raw:
            text = str(raw).strip()
            if text:
                return text
    return None

from presence_ui.deps import get_stores
from presence_ui.services.llm import _lm_studio_settings, _parse_openai_chat_content


def _episode_salience_metadata(
    *,
    person_id: str,
    summary: str,
) -> dict[str, object]:
    """MEM-5b: enrich episode_close with desires + open-loop overlap."""
    from interaction_orchestrator_mcp.desire_source import load_desire_snapshot
    from social_core.stm_salience import build_stm_salience_metadata, match_open_loop_ids

    stores = get_stores()
    loops = [
        (loop.id, loop.topic)
        for loop in stores.relationship.list_open_loops(person_id=person_id, limit=20)
    ]
    matched = match_open_loop_ids(summary, loops)
    dominant: str | None = None
    level: float | None = None
    snap = load_desire_snapshot() or {}
    dominant = snap.get("dominant")
    if dominant:
        try:
            level = float((snap.get("desires") or {}).get(dominant) or 0.0)
        except (TypeError, ValueError):
            level = None
    return build_stm_salience_metadata(
        summary=summary,
        kind="episode_close",
        source="episode_summary",
        importance=3,
        dominant_desire=str(dominant) if dominant else None,
        desire_level=level,
        open_loop_ids=matched or None,
    )


def _episode_llm_enabled() -> bool:
    return os.environ.get("PRESENCE_STM_EPISODE_LLM", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _build_episode_llm_prompt(turns: list[dict[str, str | None]]) -> str:
    lines = [
        "次の会話ログを、こよりの短期記憶（STM）用に3〜5行で要約して。",
        "事実・決定・約束・感情の変化を優先。挨拶だけなら「特になし」と1行。",
        "出力は要約本文のみ（ラベルや箇条書き記号は不要）。",
        "",
        "[会話]",
    ]
    for turn in turns[:24]:
        sender = turn.get("sender") or ""
        message = str(turn.get("message") or "").strip()
        if not message:
            continue
        label = "まー" if sender == "ma" else "こより"
        lines.append(f"{label}: {message[:400]}")
    return "\n".join(lines)


async def summarize_episode_for_stm(
    turns: list[dict[str, str | None]],
    *,
    use_llm: bool | None = None,
) -> str | None:
    """Rule-based summary; optional LM Studio polish when enabled."""
    base = summarize_episode_turns(turns)
    if not base:
        return None
    if use_llm is None:
        use_llm = _episode_llm_enabled()
    if not use_llm:
        return base

    base_url, model, token = _lm_studio_settings()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 220,
        "temperature": 0.35,
        "messages": [{"role": "user", "content": _build_episode_llm_prompt(turns)}],
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            text = _parse_openai_chat_content(response.json())
        if text and text.strip():
            return text.strip()[:2000]
    except Exception:
        pass
    return base


async def close_episode_for_session(
    *,
    person_id: str,
    session_id: str,
    turns: list[dict[str, str | None]],
    trigger: str = "new_session",
    timezone: str | None = None,
    use_llm: bool | None = None,
) -> dict[str, object]:
    stores = get_stores()
    tz = timezone or stores.policy_timezone
    stm = StmStore(stores.db)

    existing_id = stm.episode_closure_entry_id(session_id)
    if existing_id:
        entry = stm.close_episode(
            summary="",
            person_id=person_id,
            session_id=session_id,
            trigger=trigger,
            turn_count=len(turns),
            timezone=tz,
        )
        return {
            "ok": True,
            "closed": True,
            "skipped": True,
            "reason": "already_closed",
            "entry_id": existing_id,
            "summary": entry.summary if entry else None,
        }

    summary = await summarize_episode_for_stm(turns, use_llm=use_llm)
    if not summary:
        return {
            "ok": True,
            "closed": False,
            "skipped": True,
            "reason": "too_short",
            "entry_id": None,
            "summary": None,
        }

    entry = stm.close_episode(
        summary=summary,
        person_id=person_id,
        session_id=session_id,
        trigger=trigger,
        turn_count=len(turns),
        ts=_episode_ts_from_turns(turns),
        timezone=tz,
        salience=_episode_salience_metadata(person_id=person_id, summary=summary),
    )
    return {
        "ok": True,
        "closed": entry is not None,
        "skipped": False,
        "reason": None,
        "entry_id": entry.entry_id if entry else None,
        "summary": entry.summary if entry else summary,
        "local_day": entry.local_day if entry else None,
    }


def _turns_from_chat_messages(messages: list) -> list[dict[str, str | None]]:
    turns: list[dict[str, str | None]] = []
    for msg in messages:
        if isinstance(msg, dict):
            sender = msg.get("sender")
            text = str(msg.get("message") or "").strip()
            ts = msg.get("timestamp")
        else:
            sender = getattr(msg, "sender", None)
            text = str(getattr(msg, "message", "") or "").strip()
            ts = getattr(msg, "timestamp", None)
        if sender not in {"ma", "koyori"} or not text:
            continue
        turns.append({"sender": str(sender), "message": text, "timestamp": ts})
    return turns


def _session_updated_local_day(updated_at: str, *, timezone: str) -> str | None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from presence_ui.services.display_time import normalize_iso_timestamp

    normalized = normalize_iso_timestamp(updated_at)
    if not normalized:
        return None
    try:
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo(timezone)).date().isoformat()
    except ValueError:
        return None


async def close_open_native_episodes_before_dream(
    *,
    person_id: str,
    timezone: str | None = None,
) -> list[dict[str, object]]:
    """MEM-2b: close today's native sessions that were never episode-closed (pre-dream)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from presence_ui.services.native_history import (
        fetch_native_session_messages,
        list_native_sessions,
    )

    stores = get_stores()
    tz = timezone or stores.policy_timezone
    today = datetime.now(ZoneInfo(tz)).date().isoformat()
    stm = StmStore(stores.db)
    results: list[dict[str, object]] = []

    for summary in list_native_sessions(limit=60).sessions:
        session_id = summary.session_id
        if stm.episode_closure_entry_id(session_id):
            continue
        if _session_updated_local_day(summary.updated_at, timezone=tz) != today:
            continue
        fetched = fetch_native_session_messages(session_id)
        if fetched is None:
            continue
        turns = _turns_from_chat_messages(fetched.messages)
        if len(turns) < 2:
            continue
        outcome = await close_episode_for_session(
            person_id=person_id,
            session_id=session_id,
            turns=turns,
            trigger="quiet_hours",
            timezone=tz,
        )
        if outcome.get("closed") or outcome.get("reason") == "already_closed":
            results.append({"session_id": session_id, **outcome})
    return results
