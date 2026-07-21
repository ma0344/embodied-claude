"""Brief S0 dry-run — observe-only meaning spans in gateway_turn_context.

No jobs execution, no S1 replacement. Dump ``[brief_s0]`` for inspection.
Canon: docs/tracks/brief-s0-spans.md · system: docs/tracks/brief-s0-system-prompt.md
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from presence_ui.gateway.brief_s0_reasoning import brief_s0_reasoning_enabled
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.repo_env import repo_root

logger = logging.getLogger(__name__)

_ASKS = frozenset(
    {"greeting", "report", "consult", "request", "correction", "other"}
)
_HINTS = frozenset({"calendar", "life", "household", "none"})

_FALLBACK_SYSTEM = """\
You are Brief S0: meaning decomposition for one chat utterance.
Output ONE JSON object only (no markdown fences). No tools. No side effects.
Schema: {"spans":[{"text":"...","ask":"greeting|report|consult|request|correction|other","hint":"calendar|life|household|none"}]}
One span = one ask. Split only when ask differs. Prefer fewer spans.
"""


@dataclass(frozen=True, slots=True)
class BriefS0Span:
    text: str
    ask: str
    hint: str


@dataclass(frozen=True, slots=True)
class BriefS0Result:
    spans: tuple[BriefS0Span, ...]
    reasoning: bool
    error: str | None = None


def brief_s0_enabled() -> bool:
    """Dry-run inject flag. Code default ON (observation); set 0 to disable."""
    raw = os.getenv("PRESENCE_BRIEF_S0", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def load_brief_s0_system() -> str:
    """Load evaluation system prompt from docs (canon). Fallback if missing."""
    path = repo_root() / "docs" / "tracks" / "brief-s0-system-prompt.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("brief_s0: cannot read %s — using fallback system", path)
        return _FALLBACK_SYSTEM
    start = text.find("```\n")
    end = text.find("\n```\n\nUser message")
    if start < 0 or end < 0:
        logger.warning("brief_s0: fence not found in %s — fallback", path)
        return _FALLBACK_SYSTEM
    return text[start + 4 : end].strip() or _FALLBACK_SYSTEM


def _sanitize_line(value: object, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return re.sub(r"[\r\n\t]+", " ", text).replace("=", "_")[:limit] or "-"


def _normalize_ask(raw: object) -> str:
    ask = str(raw or "").strip().lower()
    return ask if ask in _ASKS else "other"


def _normalize_hint(raw: object) -> str:
    hint = str(raw or "none").strip().lower() or "none"
    return hint if hint in _HINTS else "none"


def parse_brief_s0_response(text: str, *, reasoning: bool) -> BriefS0Result | None:
    data = _extract_json_object(text)
    if not data:
        return None
    raw_spans = data.get("spans")
    if not isinstance(raw_spans, list) or not raw_spans:
        return None
    spans: list[BriefS0Span] = []
    for item in raw_spans:
        if not isinstance(item, dict):
            continue
        span_text = str(item.get("text") or "").strip()
        if not span_text:
            continue
        spans.append(
            BriefS0Span(
                text=span_text,
                ask=_normalize_ask(item.get("ask")),
                hint=_normalize_hint(item.get("hint")),
            )
        )
    if not spans:
        return None
    return BriefS0Result(spans=tuple(spans), reasoning=reasoning)


def format_brief_s0_block(result: BriefS0Result) -> str:
    lines = [
        "[brief_s0]",
        "mode=dry-run",
        f"reasoning={'on' if result.reasoning else 'off'}",
    ]
    if result.error:
        lines.append(f"error={_sanitize_line(result.error, limit=80)}")
        lines.append("[/brief_s0]")
        return "\n".join(lines)

    lines.append(f"spans={len(result.spans)}")
    for span in result.spans:
        lines.append(
            f"- ask={span.ask} hint={span.hint} text={_sanitize_line(span.text)}"
        )
    lines.append("[/brief_s0]")
    return "\n".join(lines)


def run_brief_s0_classify(*, utterance: str) -> BriefS0Result | None:
    """e4b S0 turn with optional reasoning. Observe-only."""
    reasoning = brief_s0_reasoning_enabled()
    # Reasoning shares the completion budget (Gemma: reasoning_tokens ⊂ completion).
    # 512 hit finish_reason=length with ~450 reasoning tokens in dry-run.
    max_tokens = int(
        os.getenv(
            "PRESENCE_BRIEF_S0_MAX_TOKENS",
            "1536" if reasoning else "512",
        )
    )
    timeout = float(
        os.getenv(
            "PRESENCE_BRIEF_S0_TIMEOUT",
            "90" if reasoning else "45",
        )
    )
    raw = run_classifier_turn(
        system=load_brief_s0_system(),
        user=f"Utterance:\n{(utterance or '').strip()}",
        max_tokens=max_tokens,
        temperature=0.2,
        timeout=timeout,
        log_label="Brief S0 dry-run",
        reasoning=reasoning,
    )
    if not raw:
        return None
    return parse_brief_s0_response(raw, reasoning=reasoning)


def build_brief_s0_block(utterance: str) -> str | None:
    if not brief_s0_enabled():
        return None
    text = (utterance or "").strip()
    if not text:
        return None
    reasoning = brief_s0_reasoning_enabled()
    try:
        result = run_brief_s0_classify(utterance=text)
    except Exception:
        logger.exception("brief_s0 classify crashed")
        return format_brief_s0_block(
            BriefS0Result(spans=(), reasoning=reasoning, error="classify_exception")
        )
    if result is None:
        return format_brief_s0_block(
            BriefS0Result(spans=(), reasoning=reasoning, error="classify_failed")
        )
    return format_brief_s0_block(result)


def append_brief_s0(turn_delta: str, *, utterance: str) -> str:
    """Prepend ``[brief_s0]`` dry-run block (fail-soft)."""
    block = build_brief_s0_block(utterance)
    if not block:
        return turn_delta
    delta = (turn_delta or "").strip()
    if not delta:
        return block
    return f"{block}\n\n{delta}"
