#!/usr/bin/env python3
"""UserPromptSubmit hook: memory recall + social ingest + desire hint (cross-platform).

Replaces auto-recall.sh + auto-social.sh on Windows and Linux.
Stdout is injected into the agent context.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path

SKIP_SUBSTRINGS = (
    "好きなことをいっぱいして",
    "深呼吸や瞑想",
    "Twitter/X",
    "外の景色を見る",
    "Awareness of Awareness",
    "青空文庫",
    "記憶を整理する",
)

AUTONOMOUS_MARKERS = SKIP_SUBSTRINGS  # same skip list for heartbeat prompts


def _read_user_prompt() -> str:
    raw = sys.stdin.read()
    if not raw.strip():
        return ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return str(data.get("prompt") or data.get("message") or "").strip()
    except json.JSONDecodeError:
        pass
    return raw.strip()


def _should_skip(text: str) -> bool:
    return any(marker in text for marker in AUTONOMOUS_MARKERS)


def _recall_lines(text: str) -> list[str]:
    if len(text) < 5:
        return []
    port = os.environ.get("MEMORY_HTTP_PORT", "18900")
    q = urllib.parse.quote(text)
    url = f"http://127.0.0.1:{port}/recall?q={q}&n=2"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return []
    if not body or body.strip() in ("", "[]"):
        return []
    return [f"[associative_recall] {body.strip()}"]


def _social_ingest(text: str) -> None:
    if len(text) < 3:
        return
    db_path = Path(os.environ.get("SOCIAL_DB_PATH", Path.home() / ".claude/sociality/social.db"))
    if not db_path.is_file():
        return
    person_id = os.environ.get("SOCIAL_PRIMARY_PERSON_ID", "kouta")
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    event_id = f"evt_{sha1(f'{ts}{text}'.encode()).hexdigest()[:16]}"
    payload = json.dumps({"text": text}, ensure_ascii=False)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO events
                (event_id, ts, source, kind, person_id, confidence, payload_json, created_at)
                VALUES (?, ?, 'hook', 'human_utterance', ?, 1.0, ?, ?)
                """,
                (event_id, ts, person_id, payload, ts),
            )
    except sqlite3.Error:
        return


def _desire_hint() -> list[str]:
    path = Path(
        os.environ.get("DESIRES_PATH", str(Path.home() / ".claude" / "desires.json"))
    ).expanduser()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    dominant = data.get("dominant")
    discomforts = data.get("discomforts") or {}
    if not dominant and not discomforts:
        return []
    parts = []
    if dominant:
        parts.append(f"dominant={dominant}")
    hot = sorted(discomforts.items(), key=lambda kv: kv[1], reverse=True)[:2]
    if hot:
        parts.append("discomfort=" + ", ".join(f"{k}:{v:.2f}" for k, v in hot))
    return [f"[desire_hint] {'; '.join(parts)}"]


def main() -> int:
    text = _read_user_prompt()
    if not text or _should_skip(text):
        return 0

    lines: list[str] = []
    lines.extend(_recall_lines(text))
    lines.extend(_desire_hint())
    _social_ingest(text)

    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
