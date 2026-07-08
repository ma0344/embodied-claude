"""WS-2d — extract text from PDFs (local path or fetched bytes).

Text-embedded PDFs only (papers, e-docs, forms). Scanned/image PDFs are detected
and reported as ``scanned`` for a future OCR/VLM fallback (Phase 2). No captioning
or remembering here — this is pure sensory pre-processing (deterministic, no persona).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_MAX_PAGES = 50
_DEFAULT_MAX_CHARS = 20000
_DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB


def pdf_extract_enabled() -> bool:
    raw = os.getenv("PRESENCE_PDF_EXTRACT", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _max_pages() -> int:
    raw = os.getenv("PRESENCE_PDF_MAX_PAGES", str(_DEFAULT_MAX_PAGES)).strip()
    try:
        return max(1, min(int(raw), 500))
    except ValueError:
        return _DEFAULT_MAX_PAGES


def _max_chars() -> int:
    raw = os.getenv("PRESENCE_PDF_MAX_CHARS", str(_DEFAULT_MAX_CHARS)).strip()
    try:
        return max(500, min(int(raw), 100_000))
    except ValueError:
        return _DEFAULT_MAX_CHARS


def max_pdf_bytes() -> int:
    raw = os.getenv("PRESENCE_PDF_MAX_BYTES", str(_DEFAULT_MAX_BYTES)).strip()
    try:
        return max(50_000, min(int(raw), 100 * 1024 * 1024))
    except ValueError:
        return _DEFAULT_MAX_BYTES


def allow_dirs() -> list[Path]:
    """Roots under which local PDF paths may be read. Defaults to the user home."""
    raw = os.getenv("PRESENCE_PDF_ALLOW_DIRS", "").strip()
    roots: list[Path] = []
    if raw:
        for chunk in raw.split(os.pathsep):
            chunk = chunk.strip().strip('"')
            if not chunk:
                continue
            try:
                roots.append(Path(chunk).expanduser().resolve())
            except (OSError, ValueError):
                continue
    if not roots:
        roots.append(Path.home().resolve())
    return roots


def is_path_allowed(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except (OSError, ValueError):
        return False
    for root in allow_dirs():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


@dataclass(slots=True)
class PdfExtractResult:
    text: str
    status: str  # ok | scanned | empty | not_found | not_allowed | too_large | failed | disabled
    pages_used: int = 0
    pages_total: int = 0
    truncated: bool = False


def _extract_from_document(doc, *, max_pages: int, max_chars: int) -> PdfExtractResult:
    pages_total = doc.page_count
    limit = min(pages_total, max_pages)
    parts: list[str] = []
    total = 0
    used = 0
    truncated = False
    for index in range(limit):
        page_text = doc.load_page(index).get_text("text") or ""
        page_text = page_text.strip()
        used = index + 1
        if not page_text:
            continue
        parts.append(page_text)
        total += len(page_text)
        if total >= max_chars:
            truncated = True
            break
    if limit < pages_total:
        truncated = True

    body = "\n\n".join(parts).strip()
    if len(body) > max_chars:
        body = body[:max_chars]
        truncated = True

    if not body:
        # Pages exist but carry no embedded text → almost certainly a scan/image PDF.
        status = "scanned" if pages_total else "empty"
        return PdfExtractResult("", status, used, pages_total, truncated)
    return PdfExtractResult(body, "ok", used, pages_total, truncated)


def extract_text_from_bytes(data: bytes) -> PdfExtractResult:
    if not pdf_extract_enabled():
        return PdfExtractResult("", "disabled")
    if not data:
        return PdfExtractResult("", "empty")
    if len(data) > max_pdf_bytes():
        return PdfExtractResult("", "too_large")
    try:
        import fitz  # PyMuPDF; imported lazily so a missing wheel degrades gracefully
    except ImportError:
        return PdfExtractResult("", "disabled")
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return _extract_from_document(doc, max_pages=_max_pages(), max_chars=_max_chars())
    except Exception:
        return PdfExtractResult("", "failed")


def extract_text_from_path(path: str | Path) -> PdfExtractResult:
    if not pdf_extract_enabled():
        return PdfExtractResult("", "disabled")
    target = Path(path).expanduser()
    if not is_path_allowed(target):
        return PdfExtractResult("", "not_allowed")
    if not target.is_file():
        return PdfExtractResult("", "not_found")
    try:
        if target.stat().st_size > max_pdf_bytes():
            return PdfExtractResult("", "too_large")
    except OSError:
        return PdfExtractResult("", "failed")
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return PdfExtractResult("", "disabled")
    try:
        with fitz.open(str(target)) as doc:
            return _extract_from_document(doc, max_pages=_max_pages(), max_chars=_max_chars())
    except Exception:
        return PdfExtractResult("", "failed")
