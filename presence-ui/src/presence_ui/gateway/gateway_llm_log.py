"""Gateway e4b/classifier log — LMS-like text; huge harness system prompts redacted."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SYSTEM_PROMPT_REDACTED = "<System Prompt Deleted>"

_HARNESS_MARKERS = (
    "You are Claude Code",
    "Claude Agent SDK",
    "Anthropic's official CLI for Claude",
)

# Gateway e4b classifiers — always log full system (even when > length threshold).
_GATEWAY_CLASSIFIER_MARKERS = (
    "open loop 入口フィルタ",
    "カレンダー読取のための時制",
    "カレンダー読取のキーワード抽出器",
)


def gateway_llm_log_enabled() -> bool:
    raw = os.getenv("PRESENCE_GATEWAY_LLM_LOG", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def gateway_llm_log_path() -> Path:
    override = os.getenv("PRESENCE_GATEWAY_LLM_LOG_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "logs" / "gateway-llm.log"


def gateway_llm_log_format() -> str:
    raw = os.getenv("PRESENCE_GATEWAY_LLM_LOG_FORMAT", "lms").strip().lower()
    if raw in ("json", "jsonl"):
        return "json"
    return "lms"


def _redact_system_over_chars() -> int:
    raw = os.getenv("PRESENCE_GATEWAY_LLM_LOG_REDACT_SYSTEM_OVER", "3500").strip()
    try:
        return max(500, int(raw))
    except ValueError:
        return 3500


def should_redact_system_prompt(system: str | None) -> bool:
    """Redact Claude harness-sized system prompts only; keep gateway e4b prompts."""
    text = (system or "").strip()
    if not text:
        return False
    if any(marker in text for marker in _GATEWAY_CLASSIFIER_MARKERS):
        return False
    if any(marker in text for marker in _HARNESS_MARKERS):
        return True
    return len(text) > _redact_system_over_chars()


def _log_max_chars() -> int | None:
    raw = os.getenv("PRESENCE_GATEWAY_LLM_LOG_MAX_CHARS", "0").strip()
    if not raw or raw == "0":
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(0, value)


def _clip(text: str, *, max_chars: int | None) -> str:
    if max_chars is None or len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def format_lms_input(*, system: str | None, user: str) -> str:
    """LMS-style prompt body; redact only harness-scale system prompts."""
    user_body = (user or "").strip()
    if should_redact_system_prompt(system):
        system_body = SYSTEM_PROMPT_REDACTED
    else:
        system_body = (system or "").strip()
    return (
        "<bos><|turn>system\n"
        f"{system_body}<turn|>\n"
        "<|turn>user\n"
        f"{user_body}<turn|>\n"
        "<|turn>model\n"
    )


def _timestamp_line() -> str:
    tz_name = os.getenv("PRESENCE_POLICY_TIMEZONE", "Asia/Tokyo")
    try:
        ts = datetime.now(ZoneInfo(tz_name))
    except Exception:
        ts = datetime.now().astimezone()
    return f"{ts.year}/{ts.month}/{ts.day} {ts.hour:02d}:{ts.minute:02d}:{ts.second:02d}"


def _append_lms_record(
    *,
    path: Path,
    log_label: str,
    model: str,
    system: str | None,
    user: str,
    output: str | None,
    ok: bool,
) -> None:
    max_chars = _log_max_chars()
    user_text = _clip((user or "").strip(), max_chars=max_chars)
    output_text = _clip((output or "").strip(), max_chars=max_chars)
    blocks = [
        "",
        f"timestamp: {_timestamp_line()}",
        "type: llm.prediction.input",
        f"label: {log_label}",
        f"modelIdentifier: {model}",
        f"modelPath: {model}",
        "input:",
        format_lms_input(
            system=_clip((system or "").strip(), max_chars=max_chars),
            user=user_text,
        ),
        "",
        f"timestamp: {_timestamp_line()}",
        "type: llm.prediction.output",
        f"modelIdentifier: {model}",
        f"ok: {str(ok).lower()}",
        "output:",
        output_text,
        "",
    ]
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(blocks))
    except OSError:
        return


def _append_json_record(
    *,
    path: Path,
    log_label: str,
    model: str,
    system: str | None,
    user: str,
    output: str | None,
    ok: bool,
) -> None:
    max_chars = _log_max_chars()
    tz_name = os.getenv("PRESENCE_POLICY_TIMEZONE", "Asia/Tokyo")
    try:
        ts = datetime.now(ZoneInfo(tz_name)).isoformat(timespec="seconds")
    except Exception:
        ts = datetime.now().astimezone().isoformat(timespec="seconds")

    record = {
        "ts": ts,
        "label": log_label,
        "model": model,
        "ok": ok,
        "input": format_lms_input(
            system=_clip((system or "").strip(), max_chars=max_chars),
            user=_clip((user or "").strip(), max_chars=max_chars),
        ),
        "output": _clip((output or "").strip(), max_chars=max_chars),
    }
    line = json.dumps(record, ensure_ascii=False)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def append_gateway_llm_log(
    *,
    log_label: str,
    model: str,
    user: str,
    output: str | None,
    ok: bool,
    system: str | None = None,
) -> None:
    """Append one gateway classifier turn to gateway-llm.log."""
    if not gateway_llm_log_enabled():
        return
    path = gateway_llm_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    if gateway_llm_log_format() == "json":
        _append_json_record(
            path=path,
            log_label=log_label,
            model=model,
            system=system,
            user=user,
            output=output,
            ok=ok,
        )
    else:
        _append_lms_record(
            path=path,
            log_label=log_label,
            model=model,
            system=system,
            user=user,
            output=output,
            ok=ok,
        )
