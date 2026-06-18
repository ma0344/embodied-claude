"""STM episode closure — MEM-2 gateway orchestration."""

from __future__ import annotations

import os

import httpx
from social_core.stm import StmStore
from social_core.stm_episode import summarize_episode_turns

from presence_ui.deps import get_stores
from presence_ui.services.llm import _lm_studio_settings, _parse_openai_chat_content


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
        timezone=tz,
    )
    return {
        "ok": True,
        "closed": entry is not None,
        "skipped": False,
        "reason": None,
        "entry_id": entry.entry_id if entry else None,
        "summary": entry.summary if entry else summary,
    }
