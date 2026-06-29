"""Strip cheerleader sign-off sentences from persona LoRA training text."""

from __future__ import annotations

import re

_CHEERLEADER_RE = re.compile(
    r"(?:"
    r"応援し(?:て|と)|楽しみ(?:にして|や)|頑張って|いつでも言うて|"
    r"(?:なにか|何か)(?:でも|手伝|あったら)|"
    r"お疲れさ|無理せんと|適度に休|根詰めしすぎ|ペースで進め|ずっと応援|"
    r"遠慮なく言うて|準備できたら教えて|また教えて|教えてな"
    r")"
)
_TRAILING_CHEER_CLAUSE = re.compile(
    r"(?:"
    r"(?:、|けど|けども|から|し|ように|の)[^。！\n]*"
    r"(?:応援し(?:て|と)|楽しみ(?:にして|や)|頑張って)[^。！\n]*[。！]?|"
    r"[。！](?:終わったら[^。！\n]*教えて[^。！\n]*|また教えて[^。！\n]*)[。！]?"
    r")$"
)
_ENCOURAGEMENT_SENTENCE = re.compile(
    r"頑張って(?:終わらせ|頑張)|根詰め|ご褒美|無理せんと|自分のペースで進め|"
    r"応援し(?:て|と)る|いつでも休憩"
)
_OFFER_SENTENCE = re.compile(
    r"(?:なにか|何か).*(?:言うて|手伝)|集中できんこと"
)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\n])", text or "")
    return [part.strip() for part in parts if part and part.strip()]


def _cheerleader_match(sentence: str) -> re.Match[str] | None:
    return _CHEERLEADER_RE.search(sentence)


def is_cheerleader_sentence(sentence: str) -> bool:
    """True when the whole sentence is a cheerleader sign-off (not mixed factual + 応援)."""
    if _OFFER_SENTENCE.search(sentence):
        return True
    if _ENCOURAGEMENT_SENTENCE.search(sentence):
        return True
    match = _cheerleader_match(sentence)
    if not match:
        return False
    trimmed = _TRAILING_CHEER_CLAUSE.sub("", sentence).strip()
    if trimmed and trimmed != sentence:
        return False
    prefix = sentence[: match.start()].strip()
    return len(prefix) <= 8


def _trim_cheerleader_tail(sentence: str) -> str:
    trimmed = _TRAILING_CHEER_CLAUSE.sub("", sentence).strip()
    if trimmed and trimmed != sentence and not trimmed.endswith(("。", "！", "?", "？")):
        trimmed += "。"
    return trimmed


def _clean_sentences(sentences: list[str]) -> tuple[list[str], bool]:
    changed = False
    while sentences:
        tail = sentences[-1]
        trimmed = _trim_cheerleader_tail(tail)
        if trimmed != tail:
            if trimmed:
                sentences[-1] = trimmed
            else:
                sentences.pop()
            changed = True
            continue
        if is_cheerleader_sentence(tail):
            sentences.pop()
            changed = True
            continue
        break

    for idx in range(len(sentences) - 1, -1, -1):
        trimmed = _trim_cheerleader_tail(sentences[idx])
        if trimmed != sentences[idx]:
            if trimmed:
                sentences[idx] = trimmed
            else:
                sentences.pop(idx)
            changed = True
        elif is_cheerleader_sentence(sentences[idx]):
            sentences.pop(idx)
            changed = True

    return sentences, changed


def strip_trailing_cheerleader_closings(text: str) -> str:
    """Remove trailing cheerleader paragraphs/sentences; keep factual reply body."""
    body = (text or "").strip()
    if not body:
        return body

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if not paragraphs:
        return body

    changed = True
    while paragraphs and changed:
        changed = False
        sentences, paragraph_changed = _clean_sentences(_split_sentences(paragraphs[-1]))
        changed |= paragraph_changed
        if not sentences:
            paragraphs.pop()
            changed = True
        elif paragraph_changed:
            paragraphs[-1] = "".join(sentences).strip()

    return "\n\n".join(paragraphs).strip()
