"""Tests for DOC-READ doc intent e4b confirm."""

from __future__ import annotations

from presence_ui.gateway.doc_prefetch_stage import (
    parse_doc_intent_response,
    parse_hon_as_book_response,
    utterance_contains_hon_kanji,
)


def test_parse_doc_intent_response_accepts_bool():
    parsed = parse_doc_intent_response(
        '{"open_registered_book": true, "reason": "registered title mentioned"}'
    )
    assert parsed is not None
    assert parsed.open_registered_book is True

    parsed_false = parse_doc_intent_response(
        '{"open_registered_book": false, "reason": "literary discussion"}'
    )
    assert parsed_false is not None
    assert parsed_false.open_registered_book is False


def test_parse_doc_intent_response_rejects_invalid():
    assert parse_doc_intent_response('{"open_registered_book": "yes"}') is None
    assert parse_doc_intent_response("not json") is None


def test_parse_hon_as_book_response_two_choice():
    assert parse_hon_as_book_response("本ではありません") is False
    assert parse_hon_as_book_response("本です") is True
    assert parse_hon_as_book_response("資本の話なので、本ではありません") is False


def test_utterance_contains_hon_kanji():
    assert utterance_contains_hon_kanji("本能") is True
    assert utterance_contains_hon_kanji("さっきの続き") is False
