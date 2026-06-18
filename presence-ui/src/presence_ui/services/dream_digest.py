"""Persist last Dreaming digest for MEM-4 morning compose."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def dream_digest_path() -> Path:
    override = os.getenv("PRESENCE_DREAM_DIGEST_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "presence-ui" / "last_dream_digest.json"


@dataclass(slots=True)
class DreamDigestRecord:
    dreamed_at: str
    local_day: str
    summary: str
    stm_entry_ids: list[str]
    remembered_count: int = 0
    consolidate_ok: bool = False
    consolidate_stats: dict[str, Any] | None = None
    daybook_day: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("consolidate_stats") is None:
            data.pop("consolidate_stats", None)
        if data.get("daybook_day") is None:
            data.pop("daybook_day", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DreamDigestRecord:
        return cls(
            dreamed_at=str(data.get("dreamed_at") or ""),
            local_day=str(data.get("local_day") or ""),
            summary=str(data.get("summary") or ""),
            stm_entry_ids=[str(item) for item in (data.get("stm_entry_ids") or [])],
            remembered_count=int(data.get("remembered_count") or 0),
            consolidate_ok=bool(data.get("consolidate_ok")),
            consolidate_stats=data.get("consolidate_stats")
            if isinstance(data.get("consolidate_stats"), dict)
            else None,
            daybook_day=_opt_str(data.get("daybook_day")),
        )


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_dream_digest() -> DreamDigestRecord | None:
    path = dream_digest_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or not data.get("dreamed_at"):
        return None
    return DreamDigestRecord.from_dict(data)


def save_dream_digest(record: DreamDigestRecord) -> Path:
    path = dream_digest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
