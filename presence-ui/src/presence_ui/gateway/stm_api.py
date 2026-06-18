"""STM API — MEM-1 WM flush and recent buffer (gateway)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from social_core import utc_now
from social_core.stm import StmStore, build_stm_prompt_block, local_day_for_ts

from presence_ui.deps import get_stores


class WmTurn(BaseModel):
    sender: Literal["ma", "koyori"]
    message: str
    timestamp: str | None = None


class StmFlushWmRequest(BaseModel):
    person_id: str = "ma"
    session_id: str | None = None
    trigger: str = "manual"
    turns: list[WmTurn] = Field(default_factory=list)
    timezone: str | None = None


class StmFlushWmResponse(BaseModel):
    ok: bool = True
    flushed: int = 0
    entry_ids: list[str] = Field(default_factory=list)


class StmRecentResponse(BaseModel):
    ok: bool = True
    local_day: str
    count: int
    entries: list[dict[str, Any]]
    prompt_block: str = ""


class StmCloseEpisodeRequest(BaseModel):
    person_id: str = "ma"
    session_id: str
    trigger: str = "new_session"
    turns: list[WmTurn] = Field(default_factory=list)
    timezone: str | None = None
    use_llm: bool | None = None


class StmCloseEpisodeResponse(BaseModel):
    ok: bool = True
    closed: bool = False
    skipped: bool = False
    reason: str | None = None
    entry_id: str | None = None
    summary: str | None = None


def stm_flush_wm(body: StmFlushWmRequest) -> StmFlushWmResponse:
    stores = get_stores()
    tz = body.timezone or stores.policy_timezone
    stm = StmStore(stores.db)
    turns = [turn.model_dump() for turn in body.turns]
    entries = stm.flush_wm_turns(
        turns=turns,
        person_id=body.person_id,
        session_id=body.session_id,
        trigger=body.trigger,
        timezone=tz,
    )
    return StmFlushWmResponse(
        ok=True,
        flushed=len(entries),
        entry_ids=[entry.entry_id for entry in entries],
    )


def stm_recent(
    *,
    person_id: str = "ma",
    limit: int = 20,
    local_day: str | None = None,
    include_prompt_block: bool = True,
) -> StmRecentResponse:
    stores = get_stores()
    tz = stores.policy_timezone
    stm = StmStore(stores.db)
    entries = stm.recent(person_id=person_id, limit=limit, local_day=local_day)
    day = local_day or (entries[0].local_day if entries else local_day_for_ts(utc_now(), tz))
    block = build_stm_prompt_block(entries) if include_prompt_block else ""
    return StmRecentResponse(
        ok=True,
        local_day=day,
        count=len(entries),
        entries=[entry.to_dict() for entry in entries],
        prompt_block=block,
    )


async def stm_close_episode(body: StmCloseEpisodeRequest) -> StmCloseEpisodeResponse:
    from presence_ui.services.stm_episode import close_episode_for_session

    turns = [turn.model_dump() for turn in body.turns]
    result = await close_episode_for_session(
        person_id=body.person_id,
        session_id=body.session_id,
        turns=turns,
        trigger=body.trigger,
        timezone=body.timezone,
        use_llm=body.use_llm,
    )
    return StmCloseEpisodeResponse.model_validate(result)
