"""WS-5b — light direct weather/temp questions (no-confirm auto prefetch).

Separate from WS-5 v0 hearsay gate. Weather/temp only; advice/causal/chitchat out.
Unspecified region → 松本 default with premise line in the answer path.
"""

from __future__ import annotations

import os
import re

from presence_ui.gateway.ws_guard import looks_like_web_search_request

# Finite allowlist gates only — not NL semantic coverage.
_WEATHER_TOPIC = re.compile(
    r"(?:気温|天気|予報|寒い|暑い|何度|℃|度ぐらい|度くらい|"
    r"曇|晴れ|雨|雪|湿気|湿度)",
    re.I,
)

_INQUIRE = re.compile(
    r"(?:[？?]|何度|ぐらい|くらい|どう|教えて|今の|いまの|今は|いまは)",
    re.I,
)

# Hardcoded region aliases (松本 default when none match).
_REGION_CUE = re.compile(r"(?:松本市?|まつもと|長野市?)", re.I)

_ADVICE_OR_CAUSAL = re.compile(
    r"(?:なぜ|なんで|どうして|すべき|した方が|したほう|アドバイス|対策|避け|"
    r"どうすれば|どうやって防ぐ)",
    re.I,
)

_PHATIC_ONLY = re.compile(
    r"^(?:おはよう|おはよ|こんにちは|こんばんは|またね|じゃあね|"
    r"おやすみ|ありがとう|サンキュー)(?:[!.！?？～〜*\s]*)$",
    re.I,
)

DEFAULT_REGION = "松本"
DEFAULT_REGION_PREMISE = "松本（前提・地域未指定）"


def ws5b_enabled() -> bool:
    raw = os.getenv("PRESENCE_WS5B_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def extract_region_label(text: str) -> tuple[str, bool]:
    """Return (region_label, used_default)."""
    line = (text or "").strip()
    match = _REGION_CUE.search(line)
    if not match:
        return DEFAULT_REGION, True
    raw = match.group(0)
    if raw.startswith("まつもと") or raw.startswith("松本"):
        return "松本", False
    if raw.startswith("長野"):
        return "長野", False
    return raw, False


def should_ws5b_weather_prefetch(text: str) -> bool:
    """True for direct weather/temp asks (WS-5b). Does not widen WS-5 v0 hearsay."""
    if not ws5b_enabled():
        return False
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if looks_like_web_search_request(line):
        return False
    if _PHATIC_ONLY.match(line):
        return False
    if _ADVICE_OR_CAUSAL.search(line):
        return False
    if not _WEATHER_TOPIC.search(line):
        return False
    if not _INQUIRE.search(line):
        return False
    return True


def extract_ws5b_search_query(text: str) -> str:
    """Deterministic short query; default region 松本 when cue absent."""
    line = (text or "").strip()
    if not line:
        return ""
    region, used_default = extract_region_label(line)
    parts: list[str] = [region]
    for match in _WEATHER_TOPIC.finditer(line):
        token = match.group(0)
        if token not in parts:
            parts.append(token)
    if "気温" not in parts and "天気" not in parts:
        parts.append("気温")
    if used_default:
        # Query stays searchable; premise is applied in the answer path.
        pass
    return " ".join(parts)[:120]


def resolve_ws5b_prefetch(text: str) -> tuple[str, str] | None:
    """Return (source, query) with source ``ws5b`` when light weather ask applies."""
    if not should_ws5b_weather_prefetch(text):
        return None
    query = extract_ws5b_search_query(text)
    if len(query) < 2:
        return None
    return ("ws5b", query)
