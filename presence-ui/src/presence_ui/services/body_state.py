"""Persistent somatic body state (BIO-8b) — organs, probes, pending reports."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from social_core import utc_now

OrganName = Literal["eyes", "ears", "voice", "mind"]
OrganStatus = Literal["ok", "degraded", "failed", "unknown"]

_ORGAN_JA = {
    "eyes": "目",
    "ears": "耳",
    "voice": "声",
    "mind": "考え",
}


def body_state_path() -> Path:
    override = os.getenv("PRESENCE_BODY_STATE_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "presence-ui" / "body_state.json"


@dataclass(slots=True)
class OrganState:
    status: OrganStatus = "unknown"
    since: str | None = None
    last_probe_at: str | None = None
    last_ok_at: str | None = None
    summary: str | None = None
    remedies_tried: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> OrganState:
        if not data:
            return cls()
        remedies = data.get("remedies_tried")
        return cls(
            status=_status(data.get("status")),
            since=_opt_str(data.get("since")),
            last_probe_at=_opt_str(data.get("last_probe_at")),
            last_ok_at=_opt_str(data.get("last_ok_at")),
            summary=_opt_str(data.get("summary")),
            remedies_tried=[str(x) for x in remedies] if isinstance(remedies, list) else [],
        )


@dataclass(slots=True)
class PendingSomaticReport:
    report_id: str
    ts: str
    organ: OrganName
    summary: str
    action: str = ""
    remedy: str | None = None
    resolved: bool = False
    reported_to_ma: bool = False
    reflected_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingSomaticReport:
        return cls(
            report_id=str(data.get("report_id") or uuid.uuid4().hex[:12]),
            ts=str(data.get("ts") or utc_now()),
            organ=_organ(data.get("organ")),
            summary=str(data.get("summary") or ""),
            action=str(data.get("action") or ""),
            remedy=_opt_str(data.get("remedy")),
            resolved=bool(data.get("resolved")),
            reported_to_ma=bool(data.get("reported_to_ma")),
            reflected_at=_opt_str(data.get("reflected_at")),
        )


@dataclass(slots=True)
class BodyState:
    updated_at: str
    organs: dict[str, OrganState] = field(default_factory=dict)
    pending_reports: list[PendingSomaticReport] = field(default_factory=list)
    last_morning_digest_at: str | None = None
    last_escalation_level: str | None = None
    last_escalation_push_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "updated_at": self.updated_at,
            "organs": {k: v.to_dict() for k, v in self.organs.items()},
            "pending_reports": [r.to_dict() for r in self.pending_reports],
            "last_morning_digest_at": self.last_morning_digest_at,
            "last_escalation_level": self.last_escalation_level,
            "last_escalation_push_at": self.last_escalation_push_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BodyState:
        organs_raw = data.get("organs") if isinstance(data.get("organs"), dict) else {}
        organs = {str(k): OrganState.from_dict(v) for k, v in organs_raw.items()}
        pending_raw = data.get("pending_reports")
        pending = (
            [PendingSomaticReport.from_dict(item) for item in pending_raw if isinstance(item, dict)]
            if isinstance(pending_raw, list)
            else []
        )
        return cls(
            updated_at=str(data.get("updated_at") or utc_now()),
            organs=organs,
            pending_reports=pending,
            last_morning_digest_at=_opt_str(data.get("last_morning_digest_at")),
            last_escalation_level=_opt_str(data.get("last_escalation_level")),
            last_escalation_push_at=_opt_str(data.get("last_escalation_push_at")),
        )


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _status(value: object) -> OrganStatus:
    raw = str(value or "unknown").strip().lower()
    if raw in ("ok", "degraded", "failed", "unknown"):
        return raw  # type: ignore[return-value]
    return "unknown"


def _organ(value: object) -> OrganName:
    raw = str(value or "eyes").strip().lower()
    if raw in ("eyes", "ears", "voice", "mind"):
        return raw  # type: ignore[return-value]
    return "eyes"


def default_organs() -> dict[str, OrganState]:
    return {name: OrganState() for name in ("eyes", "ears", "voice", "mind")}


def load_body_state() -> BodyState:
    path = body_state_path()
    if not path.is_file():
        return BodyState(updated_at=utc_now(), organs=default_organs())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return BodyState(updated_at=utc_now(), organs=default_organs())
    if not isinstance(data, dict):
        return BodyState(updated_at=utc_now(), organs=default_organs())
    state = BodyState.from_dict(data)
    for name, organ in default_organs().items():
        state.organs.setdefault(name, organ)
    return state


def save_body_state(state: BodyState) -> Path:
    state.updated_at = utc_now()
    path = body_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _get_organ(state: BodyState, organ: OrganName) -> OrganState:
    return state.organs.setdefault(organ, OrganState())


def note_organ_probe(
    state: BodyState,
    *,
    organ: OrganName,
    status: OrganStatus,
    summary: str | None = None,
) -> None:
    now = utc_now()
    entry = _get_organ(state, organ)
    entry.last_probe_at = now
    if status == "ok":
        entry.status = "ok"
        entry.last_ok_at = now
        if summary:
            entry.summary = summary[:240]
        elif entry.status != "ok":
            entry.summary = None
        entry.since = now
        return
    if entry.status != status:
        entry.since = now
    entry.status = status
    if summary:
        entry.summary = summary[:240]


def note_organ_affliction(
    state: BodyState,
    *,
    organ: OrganName,
    summary: str,
    action: str,
    remedy: str | None = None,
    status: OrganStatus = "failed",
) -> PendingSomaticReport:
    now = utc_now()
    entry = _get_organ(state, organ)
    entry.status = status
    entry.since = entry.since or now
    entry.summary = summary[:240]
    if remedy and remedy not in entry.remedies_tried:
        entry.remedies_tried.append(remedy)
    report = PendingSomaticReport(
        report_id=uuid.uuid4().hex[:12],
        ts=now,
        organ=organ,
        summary=summary[:240],
        action=action,
        remedy=remedy,
    )
    if not _duplicate_pending(state, report):
        state.pending_reports.insert(0, report)
    state.pending_reports = state.pending_reports[:40]
    return report


def _duplicate_pending(state: BodyState, report: PendingSomaticReport) -> bool:
    for existing in state.pending_reports[:8]:
        if (
            existing.organ == report.organ
            and existing.summary == report.summary
            and not existing.resolved
            and not existing.reported_to_ma
        ):
            return True
    return False


def note_organ_ok(
    state: BodyState,
    *,
    organ: OrganName,
    note: str | None = None,
) -> None:
    now = utc_now()
    entry = _get_organ(state, organ)
    entry.status = "ok"
    entry.since = now
    entry.last_ok_at = now
    entry.last_probe_at = now
    if note:
        entry.summary = note[:240]
    for report in state.pending_reports:
        if report.organ == organ and not report.resolved:
            report.resolved = True


def unreported_pending(state: BodyState) -> list[PendingSomaticReport]:
    return [r for r in state.pending_reports if not r.reported_to_ma and not r.resolved]


def unreflected_pending(state: BodyState) -> list[PendingSomaticReport]:
    return [r for r in state.pending_reports if not r.reflected_at and not r.resolved]


EscalationLevel = Literal["none", "watch", "elevated", "critical"]


def compute_escalation(state: BodyState) -> dict[str, Any]:
    """Cross-organ severity for BIO-8d."""
    degraded = [
        (organ, entry)
        for organ, entry in state.organs.items()
        if entry.status in ("degraded", "failed")
    ]
    failed = [(organ, entry) for organ, entry in degraded if entry.status == "failed"]
    degraded_count = len(degraded)
    failed_count = len(failed)
    unresolved = [r for r in state.pending_reports if not r.resolved]
    unresolved_count = len(unresolved)
    organ_unresolved: dict[str, int] = {}
    for report in unresolved:
        organ_unresolved[report.organ] = organ_unresolved.get(report.organ, 0) + 1
    max_organ_unresolved = max(organ_unresolved.values()) if organ_unresolved else 0

    level: EscalationLevel = "none"
    reasons: list[str] = []
    if failed_count >= 2 or (failed_count >= 1 and degraded_count >= 2):
        level = "critical"
        reasons.append(f"{failed_count} failed and {degraded_count} degraded organs")
    elif degraded_count >= 2:
        level = "elevated"
        reasons.append(f"{degraded_count} organs degraded")
    elif max_organ_unresolved >= 3:
        level = "elevated"
        reasons.append(f"same organ unresolved {max_organ_unresolved} times")
    elif failed_count >= 1 and max_organ_unresolved >= 2:
        level = "elevated"
        reasons.append("persistent organ failure")
    elif degraded_count >= 1 or unresolved_count >= 2:
        level = "watch"
        if degraded_count:
            reasons.append("one organ degraded")
        if unresolved_count >= 2:
            reasons.append(f"{unresolved_count} pending body reports")

    organs_affected = [
        {
            "organ": organ,
            "organ_ja": _ORGAN_JA.get(organ, organ),
            "status": entry.status,
            "summary": entry.summary,
        }
        for organ, entry in degraded
    ]
    return {
        "level": level,
        "degraded_count": degraded_count,
        "failed_count": failed_count,
        "unresolved_pending_count": unresolved_count,
        "reasons": reasons,
        "organs_affected": organs_affected,
    }


def mark_escalation_push(state: BodyState, *, level: str) -> None:
    state.last_escalation_level = level
    state.last_escalation_push_at = utc_now()


def mark_reports_reported(state: BodyState, report_ids: list[str] | None = None) -> None:
    ids = set(report_ids or [])
    for report in state.pending_reports:
        if not ids or report.report_id in ids:
            if not report.resolved:
                report.reported_to_ma = True


def mark_reports_reflected(state: BodyState, report_ids: list[str] | None = None) -> None:
    now = utc_now()
    ids = set(report_ids or [])
    for report in state.pending_reports:
        if not ids or report.report_id in ids:
            report.reflected_at = now


def somatic_state_dict(state: BodyState) -> dict[str, Any]:
    degraded = [
        {
            "organ": organ,
            "organ_ja": _ORGAN_JA.get(organ, organ),
            "status": entry.status,
            "summary": entry.summary,
            "since": entry.since,
        }
        for organ, entry in state.organs.items()
        if entry.status in ("degraded", "failed")
    ]
    return {
        "updated_at": state.updated_at,
        "organs": {k: v.to_dict() for k, v in state.organs.items()},
        "degraded_organs": degraded,
        "pending_unreported": [r.to_dict() for r in unreported_pending(state)],
        "pending_unreflected": [r.to_dict() for r in unreflected_pending(state)],
        "last_morning_digest_at": state.last_morning_digest_at,
        "escalation": compute_escalation(state),
    }
