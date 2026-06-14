"""Deterministic memory saves for Claude Code hooks and presence-ui Gateway.

Stdlib-only: runs from ``auto_context.py`` without uv/venv.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_VALID_CATEGORIES = frozenset(
    {
        "core",
        "daily",
        "philosophical",
        "technical",
        "memory",
        "observation",
        "feeling",
        "conversation",
    }
)

_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(.+?)(?:を|って)?(?:覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて)[。．!！]?$",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:覚えておいて|覚えといて|記憶して|記憶しといて)[：:\s]+(.+)$",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:remember(?:\s+this|\s+forever)?|store\s+this(?:\s+permanently)?)"
        r"[：:\s]+(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"^(.+?)\s+(?:please\s+)?remember(?:\s+this|\s+forever)?[.!]?$",
        re.IGNORECASE | re.DOTALL,
    ),
)

_IMPERATIVE_ONLY = re.compile(
    r"^(?:これ|それ|あれ)?(?:を)?(?:覚えておいて|覚えといて|記憶して|記憶しといて)[。．!！]?$",
)

_TRIGGER_HINT = re.compile(
    r"(覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて|"
    r"remember\s+forever|remember\s+this|store\s+this)",
    re.IGNORECASE,
)

_QUOTED_JA = re.compile(r"[「『]([^」』]+)[」』]")
_LEADING_FILLER = re.compile(
    r"^(?:今度は|今回は|次は|次から|もう一度|あらためて|改めて|ちなみに)[、,\s]*",
)

_PERSONAL_FACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(?:僕|俺|私|わたし|自分)の出身(?:地)?(?:は|が).+",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:僕|俺|私|わたし|自分)(?:は|の).+(?:生まれた|育った|育て|"
        r"住んで(?:いた|た)|過ごした|暮らして(?:いた|た))",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:僕|俺|私|わたし|自分)(?:は|の)?(?:小学校|中学|高校|大学|幼少|子供|"
        r"子ども|小さい)頃.+",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:僕|俺|私|わたし|自分)(?:が|は).*(?:最初|初めて|一番).+"
        r"(?:PC|パソコン|コンピュータ|ゲーム機|MSX|ファミコン|スーファミ)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"^(?:僕|俺|私|わたし|自分)(?:が|は).*(?:買ってもらった|もらった|買った).+"
        r"(?:PC|パソコン|コンピュータ|ゲーム機)",
        re.IGNORECASE | re.DOTALL,
    ),
)

_RECALL_QUESTION = re.compile(
    r"(?:覚えて(?:い)?る|知って(?:い)?る|覚えて(?:い)?ます|知って(?:い)?ます)"
    r"(?:か|？|\?)?$",
    re.IGNORECASE,
)

_LIST_HINT = re.compile(
    r"(記憶|メモリ|memory).*(?:リスト|一覧|完全|出して|見せ|教え)|"
    r"(?:リスト|一覧).*(?:記憶|メモリ)|"
    r"(?:list|show).*(?:memor|memories)|"
    r"(?:直近|最近).*(?:記憶|メモリ)|"
    r"\d+\s*(?:個|件).*(?:記憶|メモリ)|"
    r"(?:記憶|メモリ).*\d+\s*(?:個|件)",
    re.IGNORECASE,
)

_MEMORIES_COMMAND = re.compile(
    r"^/?(?:memories|memory)(?:\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE,
)

_TRAILING_FILLER = re.compile(
    r"(?:よ|ね|な|わ|さ|かな|かも|んだ|の|だ|です|でした|だった|てた|ていた)[。．!！]?$"
)


@dataclass(slots=True, frozen=True)
class RememberIntent:
    content: str
    category: str = "conversation"


@dataclass(slots=True, frozen=True)
class RememberOutcome:
    ok: bool
    content: str
    memory_id: str | None = None
    duplicate: bool = False
    error: str | None = None
    via: str = "http"  # "http" | "sqlite"


def _normalize_remember_content(raw: str) -> str:
    content = raw.strip()
    quoted = _QUOTED_JA.findall(content)
    if quoted:
        return quoted[-1].strip()
    content = _LEADING_FILLER.sub("", content).strip()
    content = re.sub(r"^[「『\"']+|[」』\"']+$", "", content).strip()
    return content


def _normalize_personal_fact_content(raw: str) -> str:
    content = raw.strip()
    content = re.sub(r"[。．!！?？]+$", "", content).strip()
    for _ in range(3):
        stripped = _TRAILING_FILLER.sub("", content).strip()
        if stripped == content:
            break
        content = stripped
    return content


def _guess_category(content: str) -> str:
    lowered = content.lower()
    if any(k in content for k in ("作戦", "Cursor", "実装", "調査", "プロンプト", "技術")):
        return "technical"
    if any(k in lowered for k in ("feel", "感情", "嬉し", "悲し")):
        return "feeling"
    return "conversation"


def _looks_like_memory_list_request(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _MEMORIES_COMMAND.match(stripped):
        return True
    return len(stripped) >= 4 and bool(_LIST_HINT.search(stripped))


def detect_remember_intent(user_text: str) -> RememberIntent | None:
    text = (user_text or "").strip()
    if len(text) < 4 or not _TRIGGER_HINT.search(text):
        return None
    if _IMPERATIVE_ONLY.match(text):
        return None

    for pattern in _CONTENT_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        content = _normalize_remember_content(match.group(1).strip())
        if len(content) >= 2:
            return RememberIntent(content=content, category=_guess_category(content))
    return None


def detect_personal_fact_intent(user_text: str) -> RememberIntent | None:
    text = (user_text or "").strip()
    if len(text) < 8:
        return None
    if _TRIGGER_HINT.search(text):
        return None
    if text.endswith(("?", "？")) or _RECALL_QUESTION.search(text):
        return None
    if _looks_like_memory_list_request(text):
        return None

    for pattern in _PERSONAL_FACT_PATTERNS:
        if pattern.search(text):
            content = _normalize_personal_fact_content(text)
            if len(content) >= 6:
                return RememberIntent(content=content, category="memory")
    return None


def memory_db_path() -> Path:
    return Path(
        os.environ.get(
            "MEMORY_DB_PATH",
            str(Path.home() / ".claude" / "memories" / "memory.db"),
        )
    ).expanduser()


def _memory_http_base() -> str:
    override = os.getenv("MEMORY_HTTP_RECALL_BASE", "").strip()
    if override:
        return override.rstrip("/")
    port = os.getenv("MEMORY_HTTP_PORT", "18900")
    return f"http://127.0.0.1:{port}"


def _http_timeout() -> float:
    raw = os.getenv("MEMORY_HTTP_REMEMBER_TIMEOUT", "20")
    try:
        return max(2.0, float(raw))
    except ValueError:
        return 20.0


def _http_memory_available() -> bool:
    url = f"{_memory_http_base()}/health"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _sqlite_remember_fallback(intent: RememberIntent) -> RememberOutcome:
    db_path = memory_db_path()
    category = intent.category if intent.category in _VALID_CATEGORIES else "conversation"
    content = intent.content.strip()
    if not content:
        return RememberOutcome(ok=False, content=intent.content, error="empty content")

    if not db_path.is_file():
        return RememberOutcome(
            ok=False,
            content=content,
            error=f"memory.db not found at {db_path}",
        )

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT id FROM memories WHERE content = ? ORDER BY timestamp DESC LIMIT 1",
                (content,),
            ).fetchone()
            if row:
                return RememberOutcome(
                    ok=True,
                    content=content,
                    memory_id=str(row[0]),
                    duplicate=True,
                    via="sqlite",
                )

            memory_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO memories (
                    id, content, normalized_content, timestamp,
                    emotion, importance, category, access_count, last_accessed,
                    linked_ids, sensory_data, tags, links,
                    novelty_score, prediction_error, activation_count, last_activated
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    memory_id,
                    content,
                    content,
                    timestamp,
                    "neutral",
                    4,
                    category,
                    0,
                    "",
                    "",
                    "",
                    "",
                    "",
                    0.0,
                    0.0,
                    0,
                    "",
                ),
            )
            conn.commit()
    except sqlite3.Error as exc:
        return RememberOutcome(ok=False, content=content, error=str(exc))

    return RememberOutcome(
        ok=True,
        content=content,
        memory_id=memory_id,
        duplicate=False,
        via="sqlite",
    )


def _persist_via_http(intent: RememberIntent) -> RememberOutcome:
    category = intent.category if intent.category in _VALID_CATEGORIES else "conversation"
    payload = json.dumps(
        {
            "content": intent.content,
            "category": category,
            "emotion": "neutral",
            "importance": 4,
            "auto_link": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    url = f"{_memory_http_base()}/remember"
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_http_timeout()) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return RememberOutcome(ok=False, content=intent.content, error=str(exc))

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return RememberOutcome(
            ok=False,
            content=intent.content,
            error="invalid JSON from memory HTTP",
        )

    if not data.get("ok"):
        return RememberOutcome(
            ok=False,
            content=intent.content,
            error=str(data.get("error") or "remember failed"),
        )
    return RememberOutcome(
        ok=True,
        content=intent.content,
        memory_id=str(data.get("id") or "") or None,
        duplicate=bool(data.get("duplicate")),
        via="http",
    )


def persist_remember_intent(intent: RememberIntent) -> RememberOutcome:
    if _http_memory_available():
        http_outcome = _persist_via_http(intent)
        if http_outcome.ok:
            return http_outcome
    else:
        http_outcome = None

    sqlite_outcome = _sqlite_remember_fallback(intent)
    if sqlite_outcome.ok:
        return sqlite_outcome

    if http_outcome is not None:
        return http_outcome
    return sqlite_outcome


def memory_saved_prompt_note(outcome: RememberOutcome) -> str:
    if not outcome.ok:
        return (
            "[memory_save_failed]\n"
            "FACT: Server-side remember FAILED. You must NOT say you remembered, saved, or "
            "刻み込んだ anything.\n"
            "Reply: tell the user the save failed and suggest retry (or check memory daemon).\n"
            f"Content that failed: {outcome.content[:200]}\n"
            f"Error: {outcome.error or 'unknown'}"
        )
    dup = " (already stored)" if outcome.duplicate else ""
    mid = outcome.memory_id or "unknown"
    via = "sqlite" if outcome.via == "sqlite" else "memory-mcp HTTP"
    return (
        "[memory_saved_server]\n"
        f"FACT: Hook/Gateway already saved this via {via}{dup} (id={mid}).\n"
        f"Content: {outcome.content}\n"
        "You may briefly confirm — do NOT call mcp__memory__remember again.\n"
        "Do NOT claim you saved unless this block is present."
    )


def try_auto_remember(user_text: str) -> str | None:
    """Detect remember intent, persist, return prompt note for injection (or None)."""
    intent = detect_remember_intent(user_text) or detect_personal_fact_intent(user_text)
    if not intent:
        return None
    outcome = persist_remember_intent(intent)
    return memory_saved_prompt_note(outcome)
