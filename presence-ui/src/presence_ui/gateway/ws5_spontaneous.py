"""WS-5 v0 — spontaneous web search when facts are worth verifying (permissive gate).

Not «is this the best reply?» — «would skipping a lookup be *wrong*?» (POC 許可型).
WS-2 handles explicit 「調べて」; this module handles hearsay / news / weather reports.

v1: replace heuristics with a small e4b classifier (needs_fact_check + suggested_query).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from presence_ui.gateway.ws_guard import looks_like_web_search_request

# Finite hearsay / third-party report markers (gate only — not open-ended verb lists).
_HEARSAY_CUE = re.compile(
    r"(?:らしい|みたい|だったらしい|あったみたい|そうらしい|"
    r"そうなんだ|本当かな|ほんとかな|マジ\?|まじ\?)",
    re.I,
)

# Verifiable external-fact topics (disaster · weather · news-shaped).
_VERIFIABLE_TOPIC = re.compile(
    r"(?:地震|震度|余震|津波|台風|大雨|洪水|停電|事故|火事|噴火|竜巻|大雪|猛暑|"
    r"気温|降水|天気|梅雨|警戒|避難|被災|死者|負傷|感染者|"
    r"株価|為替|選挙|政変|サミット|会談|発表|速報)",
    re.I,
)

_REGION_CUE = re.compile(
    r"(?:関東|関西|東北|九州|北海道|沖縄|日本|全球|世界|"
    r"東京|大阪|名古屋|福岡|松本|長野|関東地方|首都圏)",
    re.I,
)

_TODAY_CUE = re.compile(r"(?:今日|きょう|本日)", re.I)

_PHATIC_ONLY = re.compile(
    r"^(?:おはよう|おはよ|こんにちは|こんばんは|またね|じゃあね|"
    r"おやすみ|ありがとう|サンキュー)(?:[!.！?？～〜*\s]*)$",
    re.I,
)

# Casual opinion without external-fact claim — do not search.
_CASUAL_OPINION = re.compile(
    r"(?:おもしろかった|つまらなかった|よかった|楽しかった|疲れた|眠い)$",
    re.I,
)


def ws5_enabled() -> bool:
    raw = os.getenv("PRESENCE_WS5_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def should_spontaneous_fact_check(text: str) -> bool:
    """True when gateway should prefetch without explicit 「調べて」 (WS-5 v0)."""
    if not ws5_enabled():
        return False
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if looks_like_web_search_request(line):
        return False
    if _PHATIC_ONLY.match(line):
        return False
    if _CASUAL_OPINION.search(line) and not _VERIFIABLE_TOPIC.search(line):
        return False
    has_hearsay = bool(_HEARSAY_CUE.search(line))
    has_topic = bool(_VERIFIABLE_TOPIC.search(line))
    has_region = bool(_REGION_CUE.search(line))
    has_today = bool(_TODAY_CUE.search(line))
    # Permissive: third-party report + something verifiable (topic or place or 今日).
    if has_hearsay and (has_topic or has_region or has_today):
        return True
    # Strong topic + uncertainty shape without explicit hearsay word (e.g. 地震 あった？).
    if has_topic and re.search(r"(?:あった|起きた|来てる|降ってる)[？?]?$", line):
        return True
    return False


def extract_spontaneous_search_query(
    text: str,
    *,
    timezone: str = "Asia/Tokyo",
) -> str:
    """Build a short search query from utterance + local date context."""
    line = (text or "").strip()
    if not line:
        return ""
    parts: list[str] = []
    for match in _VERIFIABLE_TOPIC.finditer(line):
        token = match.group(0)
        if token not in parts:
            parts.append(token)
    region = _REGION_CUE.search(line)
    if region:
        parts.append(region.group(0))
    if _TODAY_CUE.search(line):
        try:
            today = datetime.now(ZoneInfo(timezone)).strftime("%Y年%m月%d日")
        except Exception:
            today = datetime.now().astimezone().strftime("%Y年%m月%d日")
        parts.append(today)
    if parts:
        return " ".join(parts)[:120]
    # Fallback: strip hearsay fluff, keep substantive phrase.
    q = _HEARSAY_CUE.sub("", line)
    q = re.sub(r"(?:って|との)(?:こと)?", "", q)
    q = re.sub(r"[？?！!。．、,]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q[:120]


def resolve_ws5_prefetch(text: str, *, timezone: str = "Asia/Tokyo") -> tuple[str, str] | None:
    """Return (source, query) with source ``ws5`` when spontaneous prefetch applies."""
    if not should_spontaneous_fact_check(text):
        return None
    query = extract_spontaneous_search_query(text, timezone=timezone)
    if len(query) < 2:
        return None
    return ("ws5", query)
