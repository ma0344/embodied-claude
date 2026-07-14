"""DOC-READ C — e4b confirm after deterministic doc open candidates."""

from __future__ import annotations

import os
from dataclasses import dataclass

from presence_ui.gateway.doc_prefetch_stage_prompts import (
    HON_AS_BOOK_SYSTEM,
    build_doc_intent_system,
    build_doc_intent_task,
    build_hon_as_book_task,
)
from presence_ui.gateway.gateway_turn_cache import (
    doc_hon_cache_key,
    doc_intent_cache_key,
    get_or_set_cached,
)
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.services import doc_read


@dataclass(frozen=True, slots=True)
class DocIntentParsed:
    open_registered_book: bool
    reason: str = ""


def doc_intent_e4b_enabled() -> bool:
    raw = os.getenv("PRESENCE_DOC_INTENT_E4B", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def utterance_contains_hon_kanji(text: str) -> bool:
    return "本" in (text or "")


def parse_hon_as_book_response(text: str) -> bool | None:
    body = (text or "").strip()
    if not body:
        return None
    if "本ではありません" in body:
        return False
    if "本です" in body:
        return True
    return None


def run_hon_as_book_check(*, utterance: str) -> bool | None:
    if not doc_intent_e4b_enabled():
        return None

    def _extract() -> bool | None:
        raw = run_classifier_turn(
            system=HON_AS_BOOK_SYSTEM,
            user=build_hon_as_book_task(utterance=utterance),
            max_tokens=int(os.getenv("PRESENCE_DOC_HON_MAX_TOKENS", "32")),
            log_label="DOC-READ hon-as-book gate",
        )
        if not raw:
            return None
        return parse_hon_as_book_response(raw)

    return get_or_set_cached(doc_hon_cache_key(utterance), _extract)


def confirm_hon_as_book(*, utterance: str) -> bool:
    """True when 本 kanji is absent or e4b says it is book-noun usage."""
    if not utterance_contains_hon_kanji(utterance):
        return True
    if not doc_intent_e4b_enabled():
        return True
    result = run_hon_as_book_check(utterance=utterance)
    if result is None:
        return False
    return result


def _book_prompt_labels(doc_id: str) -> tuple[str, tuple[str, ...]]:
    title = ""
    aliases: tuple[str, ...] = ()
    for entry in doc_read.list_registry():
        if entry.doc_id == doc_id:
            title = entry.title
            aliases = tuple(entry.aliases)
            break
    if not title:
        meta = doc_read.load_meta(doc_id)
        title = meta.title if meta else doc_id
    return title, aliases


def parse_doc_intent_response(text: str) -> DocIntentParsed | None:
    data = _extract_json_object(text)
    if not data:
        return None
    raw = data.get("open_registered_book")
    if not isinstance(raw, bool):
        return None
    reason = str(data.get("reason") or "").strip()
    return DocIntentParsed(open_registered_book=raw, reason=reason)


def run_doc_intent_confirm(
    *,
    utterance: str,
    doc_id: str,
    gate_reason: str,
) -> DocIntentParsed | None:
    if not doc_intent_e4b_enabled():
        return None
    title, aliases = _book_prompt_labels(doc_id)

    def _extract() -> DocIntentParsed | None:
        raw = run_classifier_turn(
            system=build_doc_intent_system(book_title=title, book_aliases=aliases),
            user=build_doc_intent_task(utterance=utterance, gate_reason=gate_reason),
            max_tokens=int(os.getenv("PRESENCE_DOC_INTENT_MAX_TOKENS", "128")),
            log_label="DOC-READ doc intent confirm",
        )
        if not raw:
            return None
        return parse_doc_intent_response(raw)

    return get_or_set_cached(doc_intent_cache_key(utterance, doc_id, gate_reason), _extract)


def confirm_registered_book_open(
    *,
    utterance: str,
    doc_id: str,
    gate_reason: str,
) -> bool:
    """Return True when e4b confirms opening the registered book."""
    if gate_reason not in {"title", "cue"}:
        return True
    if not doc_intent_e4b_enabled():
        return gate_reason == "title"
    if not confirm_hon_as_book(utterance=utterance):
        return False
    parsed = run_doc_intent_confirm(
        utterance=utterance,
        doc_id=doc_id,
        gate_reason=gate_reason,
    )
    if parsed is None:
        return False
    return parsed.open_registered_book
