"""SPONT-B2 / S2 — silent calendar Expectation cards (know ≠ speak).

Autonomous tick may refresh a short lookahead of Google Calendar events into a
local JSON cache and inject them as *background* context. Speaking about those
events is forbidden unless まー asked about schedule, or a reminder / concern
path is already active.

See docs/tracks/spontaneity.md § B / S2.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract

from presence_ui.gapi.calendar_client import CalendarEvent, list_events_in_time_range
from presence_ui.gateway.calendar_prefetch import looks_like_calendar_query

logger = logging.getLogger(__name__)

_EXPECTATIONS_AVOID = (
    "mentioning [calendar_expectations] or Google Calendar event details "
    "unless まー asked about schedule/予定, or a due reminder / open-loop "
    "check path is already active"
)
_OUTBOUND_CALENDAR_AVOID = (
    "bringing up calendar or schedule items from [calendar_expectations] "
    "in a casual outbound ping"
)


def calendar_lookahead_enabled() -> bool:
    raw = os.getenv("PRESENCE_CALENDAR_LOOKAHEAD", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def calendar_lookahead_hours() -> int:
    raw = os.getenv("PRESENCE_CALENDAR_LOOKAHEAD_HOURS", "6").strip()
    try:
        return max(1, min(48, int(raw)))
    except ValueError:
        return 6


def calendar_lookahead_max_events() -> int:
    raw = os.getenv("PRESENCE_CALENDAR_LOOKAHEAD_MAX_EVENTS", "5").strip()
    try:
        return max(1, min(20, int(raw)))
    except ValueError:
        return 5


def calendar_lookahead_min_interval_minutes() -> int:
    raw = os.getenv("PRESENCE_CALENDAR_LOOKAHEAD_MIN_INTERVAL_MINUTES", "30").strip()
    try:
        return max(0, min(360, int(raw)))
    except ValueError:
        return 30


def expectations_path() -> Path:
    override = os.getenv("PRESENCE_CALENDAR_EXPECTATIONS_PATH", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".claude" / "presence-ui" / "calendar_expectations.json"


@dataclass(slots=True)
class ExpectationCard:
    event_id: str
    summary: str
    start: str
    end: str
    location: str = ""
    calendar_label: str = ""


def _parse_iso(ts: str) -> datetime | None:
    raw = (ts or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _should_skip_refresh(path: Path, *, now: datetime) -> bool:
    interval = calendar_lookahead_min_interval_minutes()
    if interval <= 0 or not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    updated = _parse_iso(str(payload.get("updated_at") or ""))
    if updated is None:
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=now.tzinfo)
    age = now - updated.astimezone(now.tzinfo)
    return age < timedelta(minutes=interval)


def format_expectation_block(
    cards: list[ExpectationCard],
    *,
    timezone: str,
    hours: int,
    status: str = "ok",
) -> str:
    """Background-only block — not the chat calendar_prefetch honesty directive."""
    lines = [
        "[calendar_expectations — background only]",
        f"timezone={timezone}",
        f"lookahead_hours={hours}",
        f"status={status}",
        "policy=know≠speak; do NOT mention unless asked or reminder/concern path",
        "--- events ---",
    ]
    if not cards:
        lines.append("(none in window)")
    else:
        for card in cards:
            loc = f" | {card.location}" if card.location else ""
            cal = f" | cal={card.calendar_label}" if card.calendar_label else ""
            lines.append(f"{card.start} | {card.summary}{loc}{cal}")
    lines.append("[/calendar_expectations]")
    return "\n".join(lines)


def cards_from_events(events: list[CalendarEvent], *, limit: int) -> list[ExpectationCard]:
    cards: list[ExpectationCard] = []
    for event in events[:limit]:
        cards.append(
            ExpectationCard(
                event_id=event.event_id,
                summary=event.summary,
                start=event.start,
                end=event.end,
                location=event.location,
                calendar_label=event.calendar_label,
            )
        )
    return cards


def save_expectations(
    *,
    cards: list[ExpectationCard],
    timezone: str,
    hours: int,
    status: str,
    path: Path | None = None,
) -> Path:
    target = path or expectations_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(ZoneInfo(timezone)).isoformat(),
        "timezone": timezone,
        "lookahead_hours": hours,
        "status": status,
        "events": [asdict(card) for card in cards],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_expectations(*, path: Path | None = None) -> dict | None:
    target = path or expectations_path()
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def build_block_from_payload(payload: dict) -> str:
    events = payload.get("events") or []
    cards: list[ExpectationCard] = []
    if isinstance(events, list):
        for row in events:
            if not isinstance(row, dict):
                continue
            cards.append(
                ExpectationCard(
                    event_id=str(row.get("event_id") or ""),
                    summary=str(row.get("summary") or "（無題）"),
                    start=str(row.get("start") or ""),
                    end=str(row.get("end") or ""),
                    location=str(row.get("location") or ""),
                    calendar_label=str(row.get("calendar_label") or ""),
                )
            )
    return format_expectation_block(
        cards,
        timezone=str(payload.get("timezone") or "Asia/Tokyo"),
        hours=int(payload.get("lookahead_hours") or calendar_lookahead_hours()),
        status=str(payload.get("status") or "ok"),
    )


def refresh_calendar_expectations(*, force: bool = False) -> dict | None:
    """Fetch Google Calendar lookahead and persist. No speech. Returns payload or None."""
    if not calendar_lookahead_enabled() and not force:
        return None

    from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service
    from presence_ui.gapi.policy import load_google_policy
    from presence_ui.gateway.calendar_prefetch import gapi_router_enabled

    if not gapi_router_enabled():
        logger.info("calendar lookahead skipped: PRESENCE_GAPI_ENABLED off")
        return None

    policy = load_google_policy()
    if policy is None or not policy.enabled:
        logger.info("calendar lookahead skipped: gapi-policy disabled/missing")
        return None
    if not policy.readable_calendars():
        logger.info("calendar lookahead skipped: no readable calendars")
        return None

    tz = ZoneInfo(policy.timezone)
    now = datetime.now(tz)
    path = expectations_path()
    if not force and _should_skip_refresh(path, now=now):
        return load_expectations(path=path)

    hours = calendar_lookahead_hours()
    time_min = now
    time_max = now + timedelta(hours=hours)
    status = "ok"
    cards: list[ExpectationCard] = []
    try:
        service = get_calendar_service()
        events = list_events_in_time_range(
            service,
            policy,
            time_min=time_min,
            time_max=time_max,
        )
        cards = cards_from_events(events, limit=calendar_lookahead_max_events())
    except GoogleAuthError as exc:
        status = "auth_error"
        logger.warning("calendar lookahead auth failed: %s", exc)
    except Exception as exc:
        status = "error"
        logger.warning("calendar lookahead failed: %s", exc)

    save_expectations(
        cards=cards,
        timezone=policy.timezone,
        hours=hours,
        status=status,
        path=path,
    )
    return load_expectations(path=path)


def _merge_avoid(contract: ResponseContract, *extras: str) -> ResponseContract:
    avoid = list(contract.avoid)
    for item in extras:
        if item not in avoid:
            avoid.append(item)
    return contract.model_copy(update={"avoid": avoid})


def inject_calendar_expectations(
    ctx: InteractionContext,
    *,
    user_text: str | None = None,
    channel: str | None = None,
) -> InteractionContext:
    """Append background expectations + must_avoid. Never forces speech."""
    payload = load_expectations()
    if not payload:
        return ctx

    block = build_block_from_payload(payload)
    if not block.strip():
        return ctx

    compact = ctx.compact_prompt_block.strip()
    compact = f"{compact}\n\n{block}" if compact else block

    # Asked about schedule → avoid softens (chat prefetch is authoritative).
    asked = looks_like_calendar_query(user_text or "")
    has_due_reminder = bool(ctx.commitments_due)
    has_loop_check = bool(ctx.loops_due_for_check)
    contract = ctx.response_contract
    if not asked and not has_due_reminder and not has_loop_check:
        contract = _merge_avoid(contract, _EXPECTATIONS_AVOID)
        # Autonomous / outbound: extra blunt avoid
        if (channel or "") in ("autonomous", "voice", ""):
            contract = _merge_avoid(contract, _OUTBOUND_CALENDAR_AVOID)

    from presence_ui.gateway.context_limits import enrich_max_chars
    from presence_ui.gateway.prompt_block_safe import truncate_prompt_text

    return ctx.model_copy(
        update={
            "compact_prompt_block": truncate_prompt_text(compact, enrich_max_chars()),
            "response_contract": contract,
        }
    )
