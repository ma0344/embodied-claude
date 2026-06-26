"""Fetch one passage from Aozora Bunko for autonomous literary wandering (LW-1)."""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path

import httpx

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


def _load_state(path: Path) -> dict[str, int | dict[str, int]]:
    if not path.is_file():
        return {"work_index": 0, "passage_indices": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"work_index": 0, "passage_indices": {}}
    if not isinstance(data, dict):
        return {"work_index": 0, "passage_indices": {}}
    passage_indices = data.get("passage_indices")
    if not isinstance(passage_indices, dict):
        passage_indices = {}
    work_index = data.get("work_index", 0)
    try:
        work_index = int(work_index)
    except (TypeError, ValueError):
        work_index = 0
    return {"work_index": work_index, "passage_indices": passage_indices}


def _save_state(path: Path, state: dict[str, int | dict[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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
    """Pick the next passage using round-robin work + per-work passage indices."""
    catalog = works or load_works()
    if not catalog:
        return None

    path = state_path or aozora_state_path()
    state = _load_state(path)
    work_index = int(state.get("work_index", 0)) % len(catalog)
    passage_indices: dict[str, int] = dict(state.get("passage_indices") or {})  # type: ignore[arg-type]

    # Try each work starting from work_index (handles fetch failures).
    for offset in range(len(catalog)):
        work = catalog[(work_index + offset) % len(catalog)]
        passages, source_url = fetch_work_passages(work, timeout_sec=timeout_sec)
        if not passages:
            continue

        key = f"{work.author_id}:{work.work_id}"
        passage_index = int(passage_indices.get(key, 0)) % len(passages)
        text, next_passage_index = join_passages_from(
            passages,
            passage_index,
        )

        next_state = {
            "work_index": (work_index + offset + 1) % len(catalog),
            "passage_indices": {
                **passage_indices,
                key: next_passage_index % len(passages),
            },
        }
        _save_state(path, next_state)

        return AozoraPassage(
            work=work,
            text=text,
            passage_index=passage_index,
            total_passages=len(passages),
            source_url=source_url,
        )

    return None


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
