"""DOC-READ — long-document ingest (A) + map/summary (B).

A (ingest): PDF → per-page text → chapter-aware chunks → index (meta.json + chunks.jsonl).
B (map): each chunk → こよりの言葉の要約 → 「本の地図」(map.md).

Ingest is deterministic sensory pre-processing (no persona). Only B calls the LLM.
Chapter detection uses a *bounded, structural* Japanese heading vocabulary (known-format,
not free-text parsing) and skips the 目次 (TOC) page to avoid false boundaries.

See docs/tracks/doc-read-discuss.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_JST = ZoneInfo("Asia/Tokyo")

# Bounded structural markers for Japanese books (known format — not meaning parsing).
_CHAPTER_RE = re.compile(
    r"^\s*("
    r"はじめに|まえがき|序章|プロローグ|"
    r"第[0-9０-９一二三四五六七八九十百]+[章部]|"
    r"終章|エピローグ|あとがき|おわりに"
    r")"
)


def _heading_max_len() -> int:
    raw = os.getenv("PRESENCE_DOC_HEADING_MAX_LEN", "40").strip()
    try:
        return max(6, min(int(raw), 120))
    except ValueError:
        return 40


def _jst_now() -> str:
    return datetime.now(tz=_JST).isoformat(timespec="seconds")


def doc_store_dir() -> Path:
    raw = os.getenv("PRESENCE_DOC_STORE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(
        os.environ.get("PRESENCE_UI_HOME", str(Path.home() / ".claude" / "presence-ui")),
    ).expanduser() / "docs"


def doc_dir(doc_id: str) -> Path:
    return doc_store_dir() / doc_id


def meta_path(doc_id: str) -> Path:
    return doc_dir(doc_id) / "meta.json"


def chunks_path(doc_id: str) -> Path:
    return doc_dir(doc_id) / "chunks.jsonl"


def map_path(doc_id: str) -> Path:
    return doc_dir(doc_id) / "map.md"


def registry_path() -> Path:
    return doc_store_dir() / "registry.json"


def _chunk_chars() -> int:
    raw = os.getenv("PRESENCE_DOC_CHUNK_CHARS", "8000").strip()
    try:
        return max(1000, min(int(raw), 40000))
    except ValueError:
        return 8000


def _chunk_overlap() -> int:
    raw = os.getenv("PRESENCE_DOC_CHUNK_OVERLAP", "400").strip()
    try:
        return max(0, min(int(raw), 2000))
    except ValueError:
        return 400


@dataclass(slots=True)
class DocChunk:
    doc_id: str
    chunk_id: int
    heading: str
    part: int  # 0 when a chapter fits in one chunk; 1,2,… when split
    page_start: int
    page_end: int
    char_count: int
    text: str


@dataclass(slots=True)
class DocMeta:
    doc_id: str
    source_path: str
    title: str
    page_count: int
    total_chars: int
    chunk_count: int
    created_at: str


def doc_id_for_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


def extract_pages(path: str | Path) -> tuple[list[str], str]:
    """Return (per-page text, title). Reads the file directly (ingest is まー-invoked)."""
    import fitz

    target = Path(path).expanduser()
    with fitz.open(str(target)) as doc:
        pages: list[str] = []
        for i in range(doc.page_count):
            raw = doc.load_page(i).get_text("text")
            pages.append(raw if isinstance(raw, str) else "")
        title = (doc.metadata or {}).get("title") or target.stem
    return pages, title


def _short_markers(text: str, max_len: int) -> list[str]:
    """Short heading-like lines on a page (real chapter titles, not in-body references)."""
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) <= max_len and _CHAPTER_RE.match(stripped):
            out.append(stripped)
    return out


def detect_chapters(pages: list[str]) -> list[tuple[str, int]]:
    """Return ordered (heading, page_index) chapter boundaries.

    Two deterministic signals (validated on まー's book, docs/tracks/doc-read-discuss.md §10):
    - **short line**: a real heading is short; in-body references ("第１章でも述べた…") are
      long and rejected by the length guard.
    - **TOC pages cluster markers**: a 目次 page (or its continuation) has ≥2 short heading
      lines packed together; real chapter pages carry exactly one. Skip clustered/目次 pages.
    First occurrence of each distinct heading key wins.
    """
    max_len = _heading_max_len()
    boundaries: list[tuple[str, int]] = []
    seen: set[str] = set()
    for page_index, text in enumerate(pages):
        markers = _short_markers(text, max_len)
        if "目次" in text or len(markers) >= 2:
            continue  # TOC page / index continuation
        for line in markers:
            match = _CHAPTER_RE.match(line)
            if match is None:
                continue
            key = match.group(1)
            if key in seen:
                continue
            seen.add(key)
            boundaries.append((line[:40], page_index))
    return boundaries


def _split_long(text: str, *, max_chars: int, overlap: int) -> list[str]:
    body = text.strip()
    if len(body) <= max_chars:
        return [body]
    parts: list[str] = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(body):
        parts.append(body[start: start + max_chars])
        start += step
    return parts


def build_chunks(pages: list[str], doc_id: str) -> list[DocChunk]:
    max_chars = _chunk_chars()
    overlap = _chunk_overlap()
    boundaries = detect_chapters(pages)

    segments: list[tuple[str, int, int]] = []  # heading, page_start, page_end
    if not boundaries or boundaries[0][1] > 0:
        end = boundaries[0][1] - 1 if boundaries else len(pages) - 1
        segments.append(("（前付け）", 0, max(0, end)))
    for idx, (heading, page_start) in enumerate(boundaries):
        page_end = (boundaries[idx + 1][1] - 1) if idx + 1 < len(boundaries) else len(pages) - 1
        segments.append((heading, page_start, page_end))

    chunks: list[DocChunk] = []
    chunk_id = 0
    for heading, page_start, page_end in segments:
        text = "\n".join(pages[page_start: page_end + 1]).strip()
        if not text:
            continue
        parts = _split_long(text, max_chars=max_chars, overlap=overlap)
        for part_index, part_text in enumerate(parts):
            chunks.append(
                DocChunk(
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    heading=heading,
                    part=0 if len(parts) == 1 else part_index + 1,
                    page_start=page_start,
                    page_end=page_end,
                    char_count=len(part_text),
                    text=part_text,
                )
            )
            chunk_id += 1
    return chunks


def ingest_pdf(path: str | Path) -> tuple[DocMeta, list[DocChunk]]:
    target = Path(path).expanduser()
    data = target.read_bytes()
    doc_id = doc_id_for_bytes(data)
    pages, title = extract_pages(target)
    chunks = build_chunks(pages, doc_id)
    meta = DocMeta(
        doc_id=doc_id,
        source_path=str(target),
        title=title,
        page_count=len(pages),
        total_chars=sum(len(p) for p in pages),
        chunk_count=len(chunks),
        created_at=_jst_now(),
    )
    _save(meta, chunks)
    register_doc(doc_id, title=title)
    return meta, chunks


def _save(meta: DocMeta, chunks: list[DocChunk]) -> None:
    directory = doc_dir(meta.doc_id)
    directory.mkdir(parents=True, exist_ok=True)
    meta_path(meta.doc_id).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with chunks_path(meta.doc_id).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def load_meta(doc_id: str) -> DocMeta | None:
    path = meta_path(doc_id)
    if not path.is_file():
        return None
    return DocMeta(**json.loads(path.read_text(encoding="utf-8")))


def load_chunks(doc_id: str) -> list[DocChunk]:
    path = chunks_path(doc_id)
    if not path.is_file():
        return []
    out: list[DocChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(DocChunk(**json.loads(line)))
    return out


# ── B: map / summary ────────────────────────────────────────────────

Summarizer = Callable[[str, str], Awaitable[str]]

_CHUNK_SUMMARY_MAX = 1024
_OVERALL_SUMMARY_MAX = 800


async def _llm_summarize(heading: str, text: str) -> str:
    from presence_ui.services import lm_client

    prompt = (
        "次は、まーが書いた本の一部（章）です。こよりとして、この章の要点を"
        "日本語で3〜5行にまとめて。事実だけ・誇張なし・本文に無いことは足さない。\n\n"
        f"# 章見出し: {heading}\n\n{text[:12000]}"
    )
    return (await lm_client.complete_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=_CHUNK_SUMMARY_MAX,
    )).strip()


async def _llm_overall(title: str, joined_gists: str) -> str:
    from presence_ui.services import lm_client

    prompt = (
        f"次は本『{title}』の章ごとの要約です。全体像を日本語で1段落（4〜6行）に"
        "まとめて。事実だけ・本文に無い推測は足さない。\n\n" + joined_gists[:12000]
    )
    return (await lm_client.complete_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=_OVERALL_SUMMARY_MAX,
    )).strip()


async def build_map(
    doc_id: str,
    *,
    summarize: Summarizer | None = None,
    overall: Callable[[str, str], Awaitable[str]] | None = None,
) -> str:
    """Summarize each chunk into a 「本の地図」 markdown and persist map.md."""
    meta = load_meta(doc_id)
    chunks = load_chunks(doc_id)
    if meta is None or not chunks:
        raise FileNotFoundError(f"doc not ingested: {doc_id}")

    summarize = summarize or _llm_summarize
    overall = overall or _llm_overall

    gists: list[tuple[str, str]] = []
    for chunk in chunks:
        label = chunk.heading if chunk.part == 0 else f"{chunk.heading}（{chunk.part}）"
        gist = await summarize(label, chunk.text)
        gists.append((label, gist))

    joined = "\n".join(f"## {label}\n{gist}" for label, gist in gists)
    # Prefer human-registered title (PDF metadata is often garbage like "!L").
    display_title = next(
        (e.title for e in list_registry() if e.doc_id == doc_id and (e.title or "").strip()),
        meta.title,
    )
    overall_text = await overall(display_title, joined)

    lines = [
        f"# 本の地図 — {display_title}",
        "",
        f"- doc_id: `{meta.doc_id}`",
        f"- {meta.page_count} ページ / {meta.total_chars} 字 / {meta.chunk_count} chunk",
        f"- source: `{meta.source_path}`",
        f"- created: {meta.created_at}",
        "",
        "## 全体",
        overall_text,
        "",
        "## 章ごと",
    ]
    for label, gist in gists:
        lines.append(f"### {label}")
        lines.append(gist)
        lines.append("")
    body = "\n".join(lines).strip() + "\n"
    map_path(doc_id).write_text(body, encoding="utf-8")
    from presence_ui.services import doc_memory

    doc_memory.remember_book_map(doc_id)
    return body


def rewrite_map_display_title(doc_id: str, title: str | None = None) -> str | None:
    """Rewrite the H1 title in an existing map.md (no LLM). Returns new body or None."""
    current = load_map(doc_id)
    if not current.strip():
        return None
    if title is None:
        title = next(
            (e.title for e in list_registry() if e.doc_id == doc_id and (e.title or "").strip()),
            None,
        )
    if not title:
        meta = load_meta(doc_id)
        title = meta.title if meta else None
    if not title:
        return None
    lines = current.splitlines()
    if lines and lines[0].startswith("# 本の地図"):
        lines[0] = f"# 本の地図 — {title}"
    else:
        lines.insert(0, f"# 本の地図 — {title}")
        lines.insert(1, "")
    body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    map_path(doc_id).write_text(body, encoding="utf-8")
    return body


def load_map(doc_id: str) -> str:
    path = map_path(doc_id)
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ── registry: active pointer + human title/alias (PDF metadata is unreliable) ──


@dataclass(slots=True)
class DocRegistryEntry:
    doc_id: str
    title: str
    aliases: list[str]


def _load_registry() -> dict:
    path = registry_path()
    if not path.is_file():
        return {"active": None, "docs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"active": None, "docs": {}}
    data.setdefault("active", None)
    data.setdefault("docs", {})
    return data


def _save_registry(data: dict) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_doc(doc_id: str, *, title: str, aliases: list[str] | None = None) -> None:
    data = _load_registry()
    entry = data["docs"].get(doc_id, {})
    entry["title"] = title
    if aliases is not None:
        entry["aliases"] = aliases
    entry.setdefault("aliases", [])
    data["docs"][doc_id] = entry
    if data.get("active") is None:
        data["active"] = doc_id
    _save_registry(data)


def get_doc_registry_entry(doc_id: str) -> dict:
    data = _load_registry()
    entry = data.get("docs", {}).get(doc_id) or {}
    return dict(entry)


def patch_doc_registry_entry(doc_id: str, **fields: object) -> None:
    data = _load_registry()
    entry = dict(data.get("docs", {}).get(doc_id) or {})
    entry.update(fields)
    data["docs"][doc_id] = entry
    _save_registry(data)


def set_doc_title(doc_id: str, title: str, *, aliases: list[str] | None = None) -> None:
    register_doc(doc_id, title=title, aliases=aliases)
    rewrite_map_display_title(doc_id, title)


def set_active_doc(doc_id: str | None) -> None:
    data = _load_registry()
    data["active"] = doc_id
    _save_registry(data)


def active_doc_id() -> str | None:
    return _load_registry().get("active")


def list_registry() -> list[DocRegistryEntry]:
    data = _load_registry()
    out: list[DocRegistryEntry] = []
    for doc_id, entry in data.get("docs", {}).items():
        out.append(
            DocRegistryEntry(
                doc_id=doc_id,
                title=str(entry.get("title") or ""),
                aliases=list(entry.get("aliases") or []),
            )
        )
    return out


def resolve_doc_by_text(text: str) -> str | None:
    """Match a book by its registered title/alias tokens appearing in the utterance.

    Enables 「この間の〇〇の本の続き」 across sessions (registry is persistent).
    Longest match wins so a specific title beats a short alias.
    """
    body = (text or "").strip()
    if not body:
        return None
    best: tuple[int, str] | None = None
    for entry in list_registry():
        needles = [entry.title, *entry.aliases]
        for needle in needles:
            needle = (needle or "").strip()
            if len(needle) >= 2 and needle in body:
                if best is None or len(needle) > best[0]:
                    best = (len(needle), entry.doc_id)
    return best[1] if best else None


# ── retrieve: chunk selection by keyword score (v1, embedding-free) ──

_JP_TERM_RE = re.compile(r"[\u3040-\u9fff\u30a0-\u30ff\uff66-\uff9f]{2,}")
_EN_TERM_RE = re.compile(r"[A-Za-z]{3,}")


def query_terms(text: str) -> list[str]:
    q = (text or "").strip()
    if not q:
        return []
    terms: list[str] = []
    for match in _JP_TERM_RE.finditer(q):
        term = match.group()
        if term not in terms:
            terms.append(term)
    for match in _EN_TERM_RE.finditer(q):
        term = match.group().lower()
        if term not in terms:
            terms.append(term)
    return terms[:16]


def match_terms(text: str, *, max_bigrams: int = 24) -> list[tuple[str, int]]:
    """(term, weight) for scoring. Content runs get length weight; JP bigrams weight 1.

    Bigrams make retrieval robust to particle-glued runs ("寄り添いについて" → 寄り添い hits
    via bigrams) without a tokenizer. Low weight keeps them from dominating content words.
    """
    weighted: list[tuple[str, int]] = []
    seen: set[str] = set()
    for term in query_terms(text):
        if term not in seen:
            seen.add(term)
            weighted.append((term, max(2, len(term))))
    bigrams: list[tuple[str, int]] = []
    for match in _JP_TERM_RE.finditer(text or ""):
        run = match.group()
        if len(run) < 3:
            continue
        for i in range(len(run) - 1):
            bg = run[i: i + 2]
            if bg not in seen:
                seen.add(bg)
                bigrams.append((bg, 1))
    return weighted + bigrams[:max_bigrams]


def score_chunk(chunk: DocChunk, terms: list[tuple[str, int]]) -> int:
    if not terms:
        return 0
    text = chunk.text
    lower = text.lower()
    heading = chunk.heading
    score = 0
    for term, weight in terms:
        hits = text.count(term) if term in text else lower.count(term.lower())
        if hits:
            score += min(hits, 5) * weight
        if term in heading:
            score += 4 if weight > 1 else 1
    return score


def select_chunks(doc_id: str, query: str, *, max_chunks: int = 2) -> list[DocChunk]:
    chunks = load_chunks(doc_id)
    if not chunks:
        return []
    terms = match_terms(query)
    if not terms:
        return []
    scored = [(score_chunk(c, terms), c) for c in chunks]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
    return [c for _s, c in scored[:max_chunks]]
