"""Irodori TTS emoji enrich — e4b Stage-2 transform (plain reply → tts_input)."""

from __future__ import annotations

import logging
import os

from presence_ui.gateway.gateway_turn_cache import get_or_set_cached
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.irodori_emoji_allowlist import (
    IRODORI_EMOJI_ALLOWLIST,
    IRODORI_EMOJI_REFERENCE,
)
from presence_ui.gateway.llm_intent import _extract_json_object

logger = logging.getLogger(__name__)

_MAX_EMOJI_PER_LINE = 4
_MODULE_CACHE: dict[str, str] = {}
_MODULE_CACHE_MAX = 64

IRODORI_EMOJI_SYSTEM = """あなたは Irodori TTS 用の台詞整形器です。
入力の日本語台詞に、allowlist の emoji だけを 0〜4 個埋め込んだ tts_input を JSON 1 件で返してください。

**ルール**
1. 台詞の意味・語順は変えない（語句の削除・言い換え禁止）
2. emoji は allowlist 以外禁止 · 同じ emoji の繰り返しで強調可
3. 効果が自然でない箇所には無理に付けない（0 個でも可）
4. 既に allowlist emoji がある場合は活かすか微調整
5. JSON のみ · markdown フェンス不可

**出力**
{"tts_input": "..."}"""


def irodori_emoji_enrich_enabled() -> bool:
    raw = os.getenv("PRESENCE_IRODORI_EMOJI_ENRICH", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _max_tokens() -> int:
    return int(os.getenv("PRESENCE_IRODORI_EMOJI_MAX_TOKENS", "256"))


def _irodori_is_default_engine() -> bool:
    try:
        from presence_ui.repo_env import load_repo_env

        load_repo_env(force=True)
        from tts_mcp.config import TTSConfig

        config = TTSConfig.from_env()
        return config.resolve_engine(None) == "irodori" and config.irodori is not None
    except Exception:
        return False


def _emoji_reference_lines() -> str:
    return "\n".join(f"- {emoji}: {label}" for emoji, label in IRODORI_EMOJI_REFERENCE)


def build_irodori_emoji_task(*, reply_plain: str) -> str:
    text = reply_plain.strip().replace("\n", " ")
    return (
        "[gateway_internal — not for まー]\n"
        "task: irodori_emoji_enrich\n"
        f"reply_plain: {text}\n\n"
        "allowlist examples:\n"
        f"{_emoji_reference_lines()}\n"
    )


def _is_emoji_char(ch: str) -> bool:
    if not ch or len(ch) != 1:
        return False
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FAFF
        or 0x2600 <= cp <= 0x27BF
        or 0x2300 <= cp <= 0x23FF
        or cp in {0xFE0F, 0x200D}
    )


def sanitize_irodori_emojis(text: str) -> str:
    """Keep only allowlisted emoji sequences; drop unknown emoji codepoints."""
    allowed_sorted = sorted(IRODORI_EMOJI_ALLOWLIST, key=len, reverse=True)
    out: list[str] = []
    i = 0
    while i < len(text):
        matched = False
        for emoji in allowed_sorted:
            if text.startswith(emoji, i):
                out.append(emoji)
                i += len(emoji)
                matched = True
                break
        if matched:
            continue
        ch = text[i]
        if _is_emoji_char(ch):
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_irodori_emoji_response(text: str, *, fallback: str) -> str:
    data = _extract_json_object(text)
    if not data:
        return fallback
    tts = str(data.get("tts_input") or "").strip()
    if not tts:
        return fallback
    cleaned = sanitize_irodori_emojis(tts)
    return cleaned or fallback


def enrich_irodori_emoji(reply_plain: str) -> str:
    """Stateless e4b enrich; returns fallback plain on failure."""
    line = (reply_plain or "").strip()
    if not line:
        return line

    raw = run_classifier_turn(
        system=IRODORI_EMOJI_SYSTEM,
        user=build_irodori_emoji_task(reply_plain=line),
        max_tokens=_max_tokens(),
        temperature=0.2,
        log_label="Irodori emoji enrich",
    )
    if not raw:
        return sanitize_irodori_emojis(line)
    parsed = parse_irodori_emoji_response(raw, fallback=line)
    if parsed == line:
        return parsed
    logger.debug("Irodori emoji enrich: %r -> %r", line[:80], parsed[:80])
    return parsed


def _cache_get(key: str) -> str | None:
    return _MODULE_CACHE.get(key)


def _cache_set(key: str, value: str) -> None:
    if key not in _MODULE_CACHE and len(_MODULE_CACHE) >= _MODULE_CACHE_MAX:
        oldest = next(iter(_MODULE_CACHE))
        _MODULE_CACHE.pop(oldest, None)
    _MODULE_CACHE[key] = value


def prepare_irodori_tts_line(reply_plain: str) -> str:
    """Plain UI/chat line → TTS input (emoji-enriched when Irodori + enabled)."""
    line = (reply_plain or "").strip()
    if not line:
        return line
    if not irodori_emoji_enrich_enabled() or not _irodori_is_default_engine():
        return sanitize_irodori_emojis(line)

    cached = _cache_get(line)
    if cached is not None:
        return cached

    def _factory() -> str:
        return enrich_irodori_emoji(line)

    enriched = get_or_set_cached(("irodori_emoji", line), _factory)
    _cache_set(line, enriched)
    return enriched


def clear_irodori_emoji_cache_for_tests() -> None:
    _MODULE_CACHE.clear()
