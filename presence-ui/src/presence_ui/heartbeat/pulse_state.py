"""Agent pulse persistence — when こより wakes next."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def pulse_state_path() -> Path:
    override = os.getenv("PRESENCE_AGENT_PULSE_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "presence-ui" / "agent_pulse.json"


@dataclass(slots=True)
class AgentPulseState:
    next_wake_at: str
    reason: str = ""
    last_wake_at: str | None = None
    last_action: str | None = None
    dominant_desire: str | None = None
    last_consolidate_at: str | None = None
    last_dream_at: str | None = None
    last_dream_summary: str | None = None
    channel: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AgentPulseState:
        return cls(
            next_wake_at=str(data.get("next_wake_at") or ""),
            reason=str(data.get("reason") or ""),
            last_wake_at=_opt_str(data.get("last_wake_at")),
            last_action=_opt_str(data.get("last_action")),
            dominant_desire=_opt_str(data.get("dominant_desire")),
            last_consolidate_at=_opt_str(data.get("last_consolidate_at")),
            last_dream_at=_opt_str(data.get("last_dream_at")),
            last_dream_summary=_opt_str(data.get("last_dream_summary")),
            channel=_opt_str(data.get("channel")),
        )


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_pulse_state() -> AgentPulseState | None:
    path = pulse_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not data.get("next_wake_at"):
        return None
    return AgentPulseState.from_dict(data)


def save_pulse_state(state: AgentPulseState) -> Path:
    path = pulse_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def parse_iso(ts: str, *, tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
