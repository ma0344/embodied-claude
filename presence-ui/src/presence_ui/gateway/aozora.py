"""Fetch passages from Aozora Bunko — LW-1 fetch, LW-READ state machine."""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Literal

import httpx

ReadingPhase = Literal["read", "pause", "close"]

_MAIN_TEXT_RE = re.compile(
    r'<div class="main_text">(.*?)</div>\s*<div class="bibliographical',
    re.DOTALL,
)
_BR_SPLIT_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_CARD_FILE_RE = re.compile(r"\./files/(\d+_\d+\.html)")


@dataclass(frozen=True)
class AozoraWork:
    author_id: str
    work_id: str
    title: str
    author: str
    content_file: str | None = None

    @property
    def card_url(self) -> str:
        return f"https://www.aozora.gr.jp/cards/{self.author_id}/card{self.work_id}.html"

    def content_url(self) -> str:
        if self.content_file:
            return (
                f"https://www.aozora.gr.jp/cards/{self.author_id}/files/{self.content_file}"
            )
        return ""


@dataclass(frozen=True)
class AozoraPassage:
    work: AozoraWork
    text: str
    passage_index: int
    total_passages: int
    source_url: str


DEFAULT_WORKS: tuple[AozoraWork, ...] = (
    AozoraWork(
        author_id="000879",
        work_id="127",
        title="羅生門",
        author="芥川龍之介",
        content_file="127_15260.html",
    ),
    AozoraWork(
        author_id="000879",
        work_id="103",
        title="妙な話",
        author="芥川龍之介",
        content_file="103_15250.html",
    ),
    AozoraWork(
        author_id="000879",
        work_id="16",
        title="侏儒の言葉",
        author="芥川龍之介",
        content_file="16_14570.html",
    ),
)


def aozora_state_path() -> Path:
    raw = os.getenv("PRESENCE_AOZORA_STATE_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".claude" / "aozora_read_state.json"


def load_works() -> list[AozoraWork]:
    """Return curated works; override with PRESENCE_AOZORA_WORKS JSON if set."""
    raw = os.getenv("PRESENCE_AOZORA_WORKS", "").strip()
    if not raw:
        return list(DEFAULT_WORKS)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return list(DEFAULT_WORKS)
    if not isinstance(payload, list):
        return list(DEFAULT_WORKS)

    works: list[AozoraWork] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        author_id = str(item.get("author_id") or "").strip()
        work_id = str(item.get("work_id") or "").strip()
        title = str(item.get("title") or work_id).strip()
        author = str(item.get("author") or "").strip()
        content_file = str(item.get("content_file") or "").strip() or None
        if author_id and work_id:
            works.append(
                AozoraWork(
                    author_id=author_id,
                    work_id=work_id,
                    title=title,
                    author=author,
                    content_file=content_file,
                )
            )
    return works or list(DEFAULT_WORKS)


def work_key(work: AozoraWork) -> str:
    return f"{work.author_id}:{work.work_id}"


def work_from_dict(data: dict[str, Any]) -> AozoraWork | None:
    author_id = str(data.get("author_id") or "").strip()
    work_id = str(data.get("work_id") or "").strip()
    if not author_id or not work_id:
        return None
    content_file = str(data.get("content_file") or "").strip() or None
    return AozoraWork(
        author_id=author_id,
        work_id=work_id,
        title=str(data.get("title") or work_id).strip(),
        author=str(data.get("author") or "").strip(),
        content_file=content_file,
    )


def work_to_dict(work: AozoraWork) -> dict[str, str]:
    payload: dict[str, str] = {
        "author_id": work.author_id,
        "work_id": work.work_id,
        "title": work.title,
        "author": work.author,
    }
    if work.content_file:
        payload["content_file"] = work.content_file
    return payload


@dataclass
class ReadingState:
    """LW-READ external reading state (~/.claude/aozora_read_state.json)."""

    phase: ReadingPhase = "read"
    active_work: dict[str, str] | None = None
    passage_index: int = 0
    catalog_index: int = 0
    last_passage: dict[str, Any] | None = None
    sections_this_session: int = 0
    pending_followup_query: str = ""
    last_hook: str = ""
    # Legacy fields kept for migration reads only
    work_index: int = 0
    passage_indices: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "active_work": self.active_work,
            "passage_index": self.passage_index,
            "catalog_index": self.catalog_index,
            "last_passage": self.last_passage,
            "sections_this_session": self.sections_this_session,
            "pending_followup_query": self.pending_followup_query,
            "last_hook": self.last_hook,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReadingState:
        phase = str(data.get("phase") or "read")
        if phase not in {"read", "pause", "close"}:
            phase = "read"
        passage_indices = data.get("passage_indices")
        if not isinstance(passage_indices, dict):
            passage_indices = {}
        active = data.get("active_work")
        if active is not None and not isinstance(active, dict):
            active = None
        last_passage = data.get("last_passage")
        if last_passage is not None and not isinstance(last_passage, dict):
            last_passage = None
        return cls(
            phase=phase,  # type: ignore[arg-type]
            active_work=active,  # type: ignore[arg-type]
            passage_index=int(data.get("passage_index") or 0),
            catalog_index=int(data.get("catalog_index") or data.get("work_index") or 0),
            last_passage=last_passage,
            sections_this_session=int(data.get("sections_this_session") or 0),
            pending_followup_query=str(data.get("pending_followup_query") or ""),
            last_hook=str(data.get("last_hook") or ""),
            work_index=int(data.get("work_index") or 0),
            passage_indices={str(k): int(v) for k, v in passage_indices.items()},
        )


def sections_per_session_limit() -> int | None:
    """Optional cap before CLOSE; unset = no cap."""
    raw = os.getenv("PRESENCE_AOZORA_SECTIONS_PER_SESSION", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(1, value)


def load_reading_state(path: Path | None = None) -> ReadingState:
    file_path = path or aozora_state_path()
    if not file_path.is_file():
        return ReadingState()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ReadingState()
    if not isinstance(data, dict):
        return ReadingState()
    state = ReadingState.from_json(data)
    if state.active_work is None and "phase" not in data:
        _migrate_legacy_state(state, data)
    return state


def save_reading_state(state: ReadingState, path: Path | None = None) -> None:
    file_path = path or aozora_state_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(state.to_json(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reading_phase(path: Path | None = None) -> ReadingPhase:
    return load_reading_state(path).phase


def _migrate_legacy_state(state: ReadingState, data: dict[str, Any]) -> None:
    """Round-robin LW-1 state → single active_work at highest passage index."""
    catalog = load_works()
    if not catalog:
        return
    work_index = int(data.get("work_index") or 0) % len(catalog)
    passage_indices = state.passage_indices
    best_key = ""
    best_idx = 0
    for work in catalog:
        key = work_key(work)
        idx = int(passage_indices.get(key) or 0)
        if idx > best_idx or not best_key:
            best_key = key
            best_idx = idx
            state.active_work = work_to_dict(work)
            state.catalog_index = catalog.index(work)
    if state.active_work is None:
        work = catalog[work_index % len(catalog)]
        state.active_work = work_to_dict(work)
        state.catalog_index = work_index
        key = work_key(work)
        state.passage_index = int(passage_indices.get(key) or 0)
    else:
        state.passage_index = best_idx
    state.phase = "read"


def resolve_active_work(catalog: list[AozoraWork], state: ReadingState) -> AozoraWork:
    if state.active_work:
        work = work_from_dict(state.active_work)
        if work:
            for item in catalog:
                if work_key(item) == work_key(work):
                    return item
            return work
    if not catalog:
        raise ValueError("empty catalog")
    work = catalog[state.catalog_index % len(catalog)]
    state.active_work = work_to_dict(work)
    return work


def start_next_book(catalog: list[AozoraWork], state: ReadingState) -> AozoraWork:
    if not catalog:
        raise ValueError("empty catalog")
    state.catalog_index = (state.catalog_index + 1) % len(catalog)
    work = catalog[state.catalog_index]
    state.active_work = work_to_dict(work)
    state.passage_index = 0
    state.sections_this_session = 0
    state.last_passage = None
    state.pending_followup_query = ""
    state.phase = "read"
    return work


def _book_reached_end(started_index: int, next_index: int, total: int) -> bool:
    if total <= 0:
        return False
    if next_index == 0 and started_index > 0:
        return True
    return next_index >= total


def complete_reading_pause(
    *,
    next_move: str = "advance",
    hook: str = "",
    followup_query: str = "",
    state_path: Path | None = None,
) -> ReadingState:
    """Apply PAUSE outcome: advance index, reread, or close book."""
    path = state_path or aozora_state_path()
    state = load_reading_state(path)
    last = state.last_passage or {}
    started_index = int(last.get("passage_index") or state.passage_index)
    next_index = int(last.get("next_passage_index") or state.passage_index)
    total = int(last.get("total_passages") or 1)

    if hook.strip():
        state.last_hook = hook.strip()[:400]
    if followup_query.strip():
        state.pending_followup_query = followup_query.strip()[:240]

    move = next_move if next_move in {"advance", "reread_same", "close_book"} else "advance"
    limit = sections_per_session_limit()
    force_close = limit is not None and state.sections_this_session >= limit

    if move == "close_book" or force_close:
        state.phase = "close"
    elif move == "reread_same":
        state.phase = "read"
    else:
        if _book_reached_end(started_index, next_index, total):
            state.phase = "close"
        else:
            state.passage_index = next_index
            state.phase = "read"

    save_reading_state(state, path)
    return state


def finish_close_book(state_path: Path | None = None) -> ReadingState:
    """After CLOSE reflection, rotate to next catalog work."""
    path = state_path or aozora_state_path()
    state = load_reading_state(path)
    catalog = load_works()
    if catalog:
        start_next_book(catalog, state)
    else:
        state.phase = "read"
        state.sections_this_session = 0
        state.last_passage = None
    save_reading_state(state, path)
    return state

def strip_html_text(fragment: str) -> str:
    cleaned = re.sub(r"<rp>.*?</rp>", "", fragment, flags=re.DOTALL)
    cleaned = re.sub(r"<rt>.*?</rt>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"</?ruby>", "", cleaned)
    cleaned = re.sub(r"</?rb>", "", cleaned)
    text = _TAG_RE.sub("", cleaned)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def aozora_passage_max_chars() -> int:
    raw = os.getenv("PRESENCE_AOZORA_PASSAGE_MAX_CHARS", "1600").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 1600
    return max(400, min(value, 4000))


def join_passages_from(
    passages: list[str],
    start_index: int,
    *,
    max_chars: int | None = None,
) -> tuple[str, int]:
    """Join consecutive br-split passages until roughly max_chars (LW-1)."""
    if not passages:
        return "", start_index
    limit = max_chars if max_chars is not None else aozora_passage_max_chars()
    parts: list[str] = []
    idx = start_index % len(passages)
    used = 0
    for _ in range(len(passages)):
        chunk = passages[idx]
        extra = len(chunk) + (1 if parts else 0)
        if parts and used + extra > limit:
            break
        parts.append(chunk)
        used += extra
        idx = (idx + 1) % len(passages)
        if used >= limit:
            break
    text = "\n".join(parts)[:limit]
    next_index = (start_index + len(parts)) % len(passages)
    return text, next_index


def split_main_text_passages(html: str, *, min_chars: int = 24) -> list[str]:
    """Extract readable passages from an Aozora main_text block."""
    match = _MAIN_TEXT_RE.search(html)
    if not match:
        return []
    block = match.group(1)
    raw_parts = _BR_SPLIT_RE.split(block)
    passages: list[str] = []
    for part in raw_parts:
        text = strip_html_text(part)
        if len(text) >= min_chars:
            passages.append(text)
    return passages


def resolve_content_file(
    work: AozoraWork,
    *,
    timeout_sec: float = 15.0,
) -> str | None:
    if work.content_file:
        return work.content_file
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            response = client.get(work.card_url)
            response.raise_for_status()
            html = response.content.decode("shift_jis", errors="replace")
    except (httpx.HTTPError, UnicodeError):
        return None
    match = _CARD_FILE_RE.search(html)
    return match.group(1) if match else None


def fetch_work_passages(
    work: AozoraWork,
    *,
    timeout_sec: float = 20.0,
) -> tuple[list[str], str]:
    content_file = resolve_content_file(work, timeout_sec=timeout_sec)
    if not content_file:
        return [], work.card_url
    source_url = (
        f"https://www.aozora.gr.jp/cards/{work.author_id}/files/{content_file}"
    )
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            response = client.get(source_url)
            response.raise_for_status()
            html = response.content.decode("shift_jis", errors="replace")
    except (httpx.HTTPError, UnicodeError):
        return [], source_url
    return split_main_text_passages(html), source_url


def pick_passage(
    works: list[AozoraWork] | None = None,
    *,
    state_path: Path | None = None,
    timeout_sec: float = 20.0,
) -> AozoraPassage | None:
    """READ phase: fetch next chunk from active_work only; then phase=pause (LW-READ)."""
    catalog = works or load_works()
    if not catalog:
        return None

    path = state_path or aozora_state_path()
    state = load_reading_state(path)

    if state.phase == "close":
        finish_close_book(path)
        state = load_reading_state(path)

    if state.phase == "pause":
        return None

    work = resolve_active_work(catalog, state)
    passages, source_url = fetch_work_passages(work, timeout_sec=timeout_sec)
    if not passages:
        # Try next book in catalog once
        start_next_book(catalog, state)
        save_reading_state(state, path)
        work = resolve_active_work(catalog, state)
        passages, source_url = fetch_work_passages(work, timeout_sec=timeout_sec)
        if not passages:
            return None

    key = work_key(work)
    passage_index = state.passage_index % len(passages)
    text, next_passage_index = join_passages_from(passages, passage_index)

    state.sections_this_session += 1
    state.last_passage = {
        "work_key": key,
        "title": work.title,
        "author": work.author,
        "text": text,
        "passage_index": passage_index,
        "next_passage_index": next_passage_index % len(passages),
        "total_passages": len(passages),
        "source_url": source_url,
    }
    state.phase = "pause"
    save_reading_state(state, path)

    return AozoraPassage(
        work=work,
        text=text,
        passage_index=passage_index,
        total_passages=len(passages),
        source_url=source_url,
    )


def pick_random_passage(
    works: list[AozoraWork] | None = None,
    *,
    timeout_sec: float = 20.0,
) -> AozoraPassage | None:
    """Non-deterministic pick for tests or manual override."""
    catalog = works or load_works()
    if not catalog:
        return None
    shuffled = list(catalog)
    random.shuffle(shuffled)
    for work in shuffled:
        passages, source_url = fetch_work_passages(work, timeout_sec=timeout_sec)
        if passages:
            idx = random.randrange(len(passages))
            return AozoraPassage(
                work=work,
                text=passages[idx],
                passage_index=idx,
                total_passages=len(passages),
                source_url=source_url,
            )
    return None
