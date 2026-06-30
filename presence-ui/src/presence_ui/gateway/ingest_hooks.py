"""Ingest hook failures — log + recent buffer for ops visibility."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_RECENT_MAX = 20
_recent: deque[dict[str, str]] = deque(maxlen=_RECENT_MAX)


@dataclass(frozen=True, slots=True)
class IngestHookFailure:
    hook: str
    error_type: str
    message: str


def record_ingest_hook_failure(hook: str, exc: BaseException) -> IngestHookFailure:
    """Log with traceback and keep a short ring buffer for /ui-config."""
    failure = IngestHookFailure(
        hook=hook,
        error_type=type(exc).__name__,
        message=str(exc).strip()[:240] or type(exc).__name__,
    )
    logger.error(
        "ingest hook %s failed: %s: %s",
        hook,
        failure.error_type,
        failure.message,
        exc_info=exc,
    )
    _recent.append(
        {
            "ts": datetime.now(UTC).isoformat(),
            "hook": hook,
            "error_type": failure.error_type,
            "message": failure.message,
        }
    )
    return failure


def recent_ingest_hook_failures(*, limit: int = 10) -> list[dict[str, str]]:
    items = list(_recent)
    if limit < 1:
        return []
    return items[-limit:]


def clear_recent_ingest_hook_failures() -> None:
    _recent.clear()
