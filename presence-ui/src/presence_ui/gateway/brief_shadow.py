"""Brief shadow mode v0 — observe-only receive-time structure (IBF principle D).

Side effects: none. Does not run web_search, UA write, TEMP-C, or prefetch.
Dump format is line-oriented (not a frozen JSON Schema).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object

logger = logging.getLogger(__name__)

JobKind = Literal["surface_reply", "web_search", "other"]
UaStatus = Literal["intended", "confirmed", "skip"]
UaWrite = Literal["propose", "skip"]

_JOB_KINDS = frozenset({"surface_reply", "web_search", "other"})
_UA_STATUSES = frozenset({"intended", "confirmed", "skip"})
_UA_WRITES = frozenset({"propose", "skip"})

_BRIEF_SHADOW_SYSTEM = """\
You structure a receive-time Brief for a home companion chat (shadow / observe only).
Output ONE JSON object only (no markdown fences). No side effects — classify only.

Schema (minimal):
{
  "jobs": [
    {"id": "j1", "kind": "surface_reply", "parallel": true, "note": "short"},
    {"id": "j2", "kind": "web_search", "parallel": true, "note": "recipe search for listed ingredients"}
  ],
  "ua_candidates": [
    {"kind": "meal", "status": "skip", "object": "-",
     "write": "skip", "reason": "topic_only"}
  ]
}

kind for jobs must be exactly one of: surface_reply, web_search, other.
object must be a concrete meal word (e.g. カレー) or "-" — never copy schema placeholders.

Rules:
- Always include at least one job; usually surface_reply.
- If the user lists ingredients / fridge contents and asks for ideas/recipes, you MUST include
  BOTH surface_reply and web_search (both parallel=true). web_search note mentions recipe/idea.
- Topic-only meal talk (ideas, ingredients, questions like いいアイデアある？) →
  ua write MUST be skip, status skip, reason=topic_only (or ua_candidates=[]).
  Never write=propose when reason=topic_only.
- Past meal self-report ("食べた") → kind=meal status=confirmed write=propose (shadow only).
- Dinner plan ("にする") → kind=meal status=intended write=propose (shadow only).
- Unknown / no UA signal → ua_candidates=[].
- Do not invent jobs for calendar/prefetch/TEMP-C; those stay outside this Brief.
"""

# Schema placeholders the classifier sometimes echoes into object=.
_UA_OBJECT_PLACEHOLDERS = frozenset(
    {
        "-",
        "allowlist_or_-",
        "allowlist",
        "object",
        "<meal allowlist word or ->",
        "meal",
    }
)


@dataclass(frozen=True, slots=True)
class BriefShadowJob:
    id: str
    kind: JobKind
    parallel: bool
    note: str = ""


@dataclass(frozen=True, slots=True)
class BriefShadowUaCandidate:
    kind: str
    status: UaStatus
    object: str
    write: UaWrite
    reason: str = ""


@dataclass(frozen=True, slots=True)
class BriefShadowResult:
    jobs: tuple[BriefShadowJob, ...]
    ua_candidates: tuple[BriefShadowUaCandidate, ...]
    error: str | None = None


def brief_shadow_enabled() -> bool:
    """Feature flag. Code default OFF; local.env.example recommends ON for visibility."""
    raw = os.getenv("PRESENCE_BRIEF_SHADOW", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _sanitize_token(value: object, *, fallback: str = "-") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    # Keep dump lines single-line / parseable (mechanical, not NL understanding).
    return re.sub(r"[\r\n\t]+", " ", text).replace("=", "_")[:120] or fallback


def _normalize_job_kind(raw: object) -> JobKind:
    kind = str(raw or "").strip().lower()
    if kind in _JOB_KINDS:
        return kind  # type: ignore[return-value]
    return "other"


def _normalize_ua_status(raw: object) -> UaStatus:
    status = str(raw or "").strip().lower()
    if status in _UA_STATUSES:
        return status  # type: ignore[return-value]
    return "skip"


def _normalize_ua_write(raw: object) -> UaWrite:
    write = str(raw or "").strip().lower()
    if write in _UA_WRITES:
        return write  # type: ignore[return-value]
    return "skip"


def parse_brief_shadow_response(text: str) -> BriefShadowResult | None:
    data = _extract_json_object(text)
    if not data:
        return None
    raw_jobs = data.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        return None
    jobs: list[BriefShadowJob] = []
    for i, item in enumerate(raw_jobs, start=1):
        if not isinstance(item, dict):
            continue
        jid = _sanitize_token(item.get("id"), fallback=f"j{i}")
        note = _sanitize_token(item.get("note"), fallback="")
        if note == "-":
            note = ""
        parallel_raw = item.get("parallel", True)
        if isinstance(parallel_raw, str):
            parallel = parallel_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            parallel = bool(parallel_raw)
        jobs.append(
            BriefShadowJob(
                id=jid,
                kind=_normalize_job_kind(item.get("kind")),
                parallel=parallel,
                note=note,
            )
        )
    if not jobs:
        return None

    ua_list: list[BriefShadowUaCandidate] = []
    raw_ua = data.get("ua_candidates")
    if isinstance(raw_ua, list):
        for item in raw_ua:
            if not isinstance(item, dict):
                continue
            kind = _sanitize_token(item.get("kind"), fallback="-")
            if kind not in {"meal", "-"}:
                kind = "-"
            ua_list.append(
                BriefShadowUaCandidate(
                    kind=kind,
                    status=_normalize_ua_status(item.get("status")),
                    object=_sanitize_token(item.get("object"), fallback="-"),
                    write=_normalize_ua_write(item.get("write")),
                    reason=_sanitize_token(item.get("reason"), fallback=""),
                )
            )

    return _coerce_brief_shadow(
        BriefShadowResult(jobs=tuple(jobs), ua_candidates=tuple(ua_list))
    )


def _coerce_brief_shadow(result: BriefShadowResult) -> BriefShadowResult:
    """Field coherence only — does NOT decide web_search (that is e4b's job)."""
    ua_list: list[BriefShadowUaCandidate] = []
    for ua in result.ua_candidates:
        write = ua.write
        status = ua.status
        obj = ua.object
        reason = ua.reason
        if reason == "topic_only" or reason.endswith("topic_only"):
            write = "skip"
            status = "skip"
        low_obj = obj.strip().lower()
        if low_obj in {p.lower() for p in _UA_OBJECT_PLACEHOLDERS} or "allowlist" in low_obj:
            obj = "-"
        ua_list.append(
            BriefShadowUaCandidate(
                kind=ua.kind,
                status=status,
                object=obj,
                write=write,
                reason=reason,
            )
        )
    return BriefShadowResult(
        jobs=result.jobs, ua_candidates=tuple(ua_list), error=result.error
    )


def format_brief_shadow_block(result: BriefShadowResult) -> str:
    lines = ["[brief_shadow]", "mode=shadow"]
    if result.error:
        lines.append(f"error={_sanitize_token(result.error)}")
        lines.append("[/brief_shadow]")
        return "\n".join(lines)

    lines.append(f"jobs={len(result.jobs)}")
    for job in result.jobs:
        note = job.note or "-"
        lines.append(
            f"- id={job.id} kind={job.kind} parallel="
            f"{'true' if job.parallel else 'false'} note={note}"
        )
    lines.append(f"ua_candidates={len(result.ua_candidates)}")
    for ua in result.ua_candidates:
        reason = ua.reason or "-"
        lines.append(
            f"- kind={ua.kind} status={ua.status} object={ua.object} "
            f"write={ua.write} reason={reason}"
        )
    lines.append("[/brief_shadow]")
    return "\n".join(lines)


def run_brief_shadow_classify(*, utterance: str) -> BriefShadowResult | None:
    """Single e4b/Stage classifier turn. Returns None on transport/parse failure."""
    max_tokens = int(os.getenv("PRESENCE_BRIEF_SHADOW_MAX_TOKENS", "384"))
    raw = run_classifier_turn(
        system=_BRIEF_SHADOW_SYSTEM,
        user=f"Utterance:\n{(utterance or '').strip()}",
        max_tokens=max_tokens,
        log_label="Brief shadow v0",
    )
    if not raw:
        return None
    return parse_brief_shadow_response(raw)


def build_brief_shadow_block(utterance: str) -> str | None:
    """Return ``[brief_shadow]…`` block, or None when flag off / fail-soft omit."""
    if not brief_shadow_enabled():
        return None
    text = (utterance or "").strip()
    if not text:
        return None
    try:
        result = run_brief_shadow_classify(utterance=text)
    except Exception:
        logger.exception("brief_shadow classify crashed")
        return format_brief_shadow_block(
            BriefShadowResult(jobs=(), ua_candidates=(), error="classify_exception")
        )
    if result is None:
        return format_brief_shadow_block(
            BriefShadowResult(jobs=(), ua_candidates=(), error="classify_failed")
        )
    return format_brief_shadow_block(result)


def append_brief_shadow(turn_delta: str, *, utterance: str) -> str:
    """Prepend shadow block into turn delta when enabled (fail-soft)."""
    block = build_brief_shadow_block(utterance)
    if not block:
        return turn_delta
    delta = (turn_delta or "").strip()
    if not delta:
        return block
    return f"{block}\n\n{delta}"
