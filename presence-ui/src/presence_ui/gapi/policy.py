"""Load gapi-policy.toml — calendar/Drive scope for GAPI."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CalendarPolicy:
    id: str
    label: str = ""
    enabled: bool = True
    read_events: bool = True
    allow_create: bool = False
    allow_update: bool = False
    allow_delete: bool = False


@dataclass(slots=True)
class GooglePolicy:
    enabled: bool = False
    prefetch_day_range: list[str] = field(default_factory=lambda: ["today", "tomorrow"])
    max_prefetch_chars: int = 4000
    oauth_account_label: str = ""
    timezone: str = "Asia/Tokyo"
    calendars: list[CalendarPolicy] = field(default_factory=list)

    def readable_calendars(self) -> list[CalendarPolicy]:
        return [
            cal
            for cal in self.calendars
            if cal.enabled and cal.read_events and cal.id.strip()
        ]


def get_policy_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    env = os.environ.get("GAPI_POLICY_PATH")
    if env:
        return Path(env).expanduser()

    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        policy = candidate / "gapi-policy.toml"
        if policy.exists():
            return policy
        try:
            if candidate == Path.home():
                break
        except RuntimeError:
            pass
        if len(candidate.parts) <= max(1, len(cwd.parts) - 6):
            break
    return cwd / "gapi-policy.toml"


def _global_timezone() -> str:
    env = os.environ.get("GAPI_TIMEZONE", "").strip()
    if env:
        return env
    for candidate in (Path.cwd(), *Path.cwd().parents):
        social = candidate / "socialPolicy.toml"
        if not social.exists():
            continue
        try:
            data = tomllib.loads(social.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        tz = str((data.get("global") or {}).get("timezone") or "").strip()
        if tz:
            return tz
        break
    return "Asia/Tokyo"


def load_google_policy(path: str | Path | None = None) -> GooglePolicy:
    policy_path = get_policy_path(path)
    timezone = _global_timezone()
    if not policy_path.exists():
        return GooglePolicy(enabled=False, timezone=timezone)

    data = tomllib.loads(policy_path.read_text(encoding="utf-8"))
    root = data.get("google") or {}
    calendars: list[CalendarPolicy] = []
    for row in root.get("calendars") or []:
        if not isinstance(row, dict):
            continue
        cal_id = str(row.get("id") or "").strip()
        if not cal_id:
            continue
        calendars.append(
            CalendarPolicy(
                id=cal_id,
                label=str(row.get("label") or cal_id),
                enabled=bool(row.get("enabled", True)),
                read_events=bool(row.get("read_events", True)),
                allow_create=bool(row.get("allow_create", False)),
                allow_update=bool(row.get("allow_update", False)),
                allow_delete=bool(row.get("allow_delete", False)),
            )
        )

    day_range = root.get("prefetch_day_range") or ["today", "tomorrow"]
    if not isinstance(day_range, list):
        day_range = ["today", "tomorrow"]

    return GooglePolicy(
        enabled=bool(root.get("enabled", False)),
        prefetch_day_range=[str(d) for d in day_range],
        max_prefetch_chars=int(root.get("max_prefetch_chars") or 4000),
        oauth_account_label=str(root.get("oauth_account_label") or ""),
        timezone=timezone,
        calendars=calendars,
    )
