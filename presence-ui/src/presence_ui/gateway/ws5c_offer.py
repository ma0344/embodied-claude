"""WS-5c — offer to search on fact-gap; pending consent → WS-2-equivalent prefetch.

Narrow finite gate only (no e4b). Weather/temp stays WS-5b (no-confirm).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from presence_ui.gateway.calendar_pending import normalize_confirm_reply
from presence_ui.gateway.ws_guard import looks_like_web_search_request

_DEFAULT_TTL_SEC = 180
_MAX_CONFIRM_REPLY_LEN = 32
_MAX_UTTERANCE_LEN = 200
_FILLER_PREFIX = re.compile(r"^(?:えっと|えーと|まあ|まー|あの|あ、?|うーん|ん、?)+", re.I)
_TRAILING_PUNCT = re.compile(r"[。!！？、,]+$")

# Affirm — finite exact after normalize. 「大丈夫」は 5c では拒否側（調べなくてええ）。
_AFFIRM_EXACT = frozenset(
    {
        "ok",
        "オーケー",
        "おっけー",
        "おっけ",
        "うん",
        "はい",
        "ええ",
        "えー",
        "いいよ",
        "いいわ",
        "お願い",
        "お願いします",
        "頼む",
        "頼むわ",
        "調べて",
        "調べてて",
        "調べてほしい",
        "調べてくれ",
        "よろしく",
        "やって",
        "いこう",
        "そうして",
        "お願いして",
        # Common glued short affirms (no separator)
        "うんお願い",
        "うんおねがい",
        "はいお願い",
        "ええお願い",
        "うんよろしく",
    }
)
_DENY_EXACT = frozenset(
    {
        "いや",
        "いいえ",
        "やめて",
        "ええわ",
        "やめといて",
        "いいや",
        "大丈夫",
        "だめ",
        "要らん",
        "いらん",
        "いい",
        "キャンセル",
        "違う",
        "ちがう",
        "しなくていい",
        "せんでいい",
        "いいです",
    }
)

# Question / ask cues (gate only).
_QUESTION_CUE = re.compile(
    r"(?:[？?]|何|なに|誰|だれ|いつ|どこ|幾つ|いくつ|いくら|幾ら|"
    r"教えて|わかる|知ってる|ってなに|って何)",
    re.I,
)

# Narrow external-fact topics — news / procedures / numbers. NOT weather/temp (→ 5b).
_FACT_TOPIC = re.compile(
    r"(?:様式|手続き|申請|料金|値段|価格|費用|人口|選挙|株価|為替|円相場|"
    r"祝日|休日|国会|内閣|首相|大統領|オリンピック|国勢|統計|"
    r"何円|何人|締め切り|期限|窓口|書類|提出|納付)",
    re.I,
)

_WEATHER_EXCLUDE = re.compile(
    r"(?:気温|天気|予報|暑い|寒い|降水|湿度|猛暑|熱帯夜)",
    re.I,
)

_PHATIC_ONLY = re.compile(
    r"^(?:おはよう|おはよ|こんにちは|こんばんは|またね|じゃあね|"
    r"おやすみ|ありがとう|サンキュー)(?:[!.！?？～〜*\s]*)$",
    re.I,
)

_ADVICE_OR_CAUSAL = re.compile(
    r"(?:どうしたら|すべき|したほうが|おすすめ|なんで|なぜ|どうして)",
    re.I,
)

_SEGMENT_SPLIT = re.compile(r"[、,。．!！？?\s]+")


def ws5c_enabled() -> bool:
    raw = os.getenv("PRESENCE_WS5C_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def ws5c_offer_ttl_sec() -> int:
    raw = os.getenv("PRESENCE_WS5C_OFFER_TTL_SEC", str(_DEFAULT_TTL_SEC)).strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_TTL_SEC
    return max(1, value)


def _pending_path() -> Path:
    return Path.home() / ".claude" / "presence-ui" / "ws5c_pending.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(slots=True)
class Ws5cPendingRecord:
    person_id: str
    kind: str
    suggested_query: str
    source_utterance: str
    created_at: str
    expires_at: str
    status: str  # pending


def should_ws5c_offer(text: str) -> bool:
    """Finite gate: question cue ∩ narrow fact topic; exclude phatic/advice/weather/WS-2."""
    if not ws5c_enabled():
        return False
    line = (text or "").strip()
    if not line or len(line) > _MAX_UTTERANCE_LEN:
        return False
    if looks_like_web_search_request(line):
        return False
    if _PHATIC_ONLY.match(line):
        return False
    if _ADVICE_OR_CAUSAL.search(line):
        return False
    if _WEATHER_EXCLUDE.search(line):
        return False
    if not _QUESTION_CUE.search(line):
        return False
    if not _FACT_TOPIC.search(line):
        return False
    return True


def extract_ws5c_query(text: str) -> str:
    """Simple strip to ≤120 for suggested_query."""
    q = (text or "").strip()
    if not q:
        return ""
    q = re.sub(r"^(?:まー[:、]?\s*)", "", q, flags=re.I).strip()
    q = re.sub(r"[？?！!。．、,]+$", "", q).strip()
    q = re.sub(r"(?:教えて|わかる|知ってる)\s*$", "", q).strip()
    q = re.sub(r"\s+", " ", q).strip()
    if len(q) < 2:
        q = (text or "").strip()[:120]
    return q[:120]


def _confirm_segments(normalized: str) -> list[str]:
    return [part.strip() for part in _SEGMENT_SPLIT.split(normalized) if part.strip()]


def _light_normalize(text: str) -> str:
    """Filler + punctuation only — keep ええわ (soft-suffix strip would → ええ = affirm)."""
    line = (text or "").strip()
    if not line:
        return ""
    line = _FILLER_PREFIX.sub("", line).strip()
    line = re.sub(r"^[、,\s]+", "", line).strip()
    line = _TRAILING_PUNCT.sub("", line).strip()
    return line


def _is_affirm_core(normalized: str) -> bool:
    if not normalized:
        return False
    return normalized.lower() in _AFFIRM_EXACT


def _is_deny_core(normalized: str) -> bool:
    if not normalized:
        return False
    low = normalized.lower()
    if low in {"いいよ", "いいわ"}:
        return False
    return low in _DENY_EXACT


def _classify_normalized(normalized: str) -> str | None:
    if not normalized or len(normalized) > _MAX_CONFIRM_REPLY_LEN:
        return None
    segments = _confirm_segments(normalized)
    if len(segments) > 1:
        if all(_is_affirm_core(segment) for segment in segments):
            return "accept"
        if all(_is_deny_core(segment) for segment in segments):
            return "decline"
        return None
    if _is_affirm_core(normalized):
        return "accept"
    if _is_deny_core(normalized):
        return "decline"
    return None


def classify_ws5c_reply(text: str, pending: Ws5cPendingRecord | None) -> str:
    """Return accept | decline | ignore for a pending 5c offer turn."""
    if pending is None or pending.status != "pending":
        return "ignore"
    # Light first so 「ええわ」stays decline (calendar soft-strip makes it 「ええ」).
    light = _classify_normalized(_light_normalize(text))
    if light is not None:
        return light
    soft = _classify_normalized(normalize_confirm_reply(text))
    if soft is not None:
        return soft
    return "ignore"


def load_pending(*, person_id: str) -> Ws5cPendingRecord | None:
    path = _pending_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if str(data.get("person_id") or "") != person_id:
        return None
    record = Ws5cPendingRecord(
        person_id=person_id,
        kind=str(data.get("kind") or "ws5c_offer"),
        suggested_query=str(data.get("suggested_query") or ""),
        source_utterance=str(data.get("source_utterance") or ""),
        created_at=str(data.get("created_at") or ""),
        expires_at=str(data.get("expires_at") or ""),
        status=str(data.get("status") or "pending"),
    )
    expires = _parse_iso(record.expires_at)
    if expires is not None and _now_utc() >= expires:
        clear_pending(person_id=person_id)
        return None
    if record.status != "pending" or not record.suggested_query.strip():
        return None
    return record


def save_pending(record: Ws5cPendingRecord) -> None:
    path = _pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(record), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_pending(*, person_id: str) -> None:
    path = _pending_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return
    if str(data.get("person_id") or "") == person_id:
        path.unlink(missing_ok=True)


def make_pending(
    *,
    person_id: str,
    source_utterance: str,
    suggested_query: str | None = None,
) -> Ws5cPendingRecord:
    now = _now_utc()
    query = (suggested_query or extract_ws5c_query(source_utterance)).strip()[:120]
    return Ws5cPendingRecord(
        person_id=person_id,
        kind="ws5c_offer",
        suggested_query=query,
        source_utterance=(source_utterance or "").strip()[:500],
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=ws5c_offer_ttl_sec())).isoformat(),
        status="pending",
    )


def format_ws5c_offer_block(record: Ws5cPendingRecord) -> str:
    preview = record.source_utterance.replace("\n", " ")[:120]
    lines = [
        "[ws5c_search_offer]",
        f"status={record.status}",
        f"suggested_query={record.suggested_query}",
        f"source_utterance={preview}",
        f"expires_at={record.expires_at}",
        "[/ws5c_search_offer]",
        "",
        "[Gateway directive — not for the user]",
        "You do NOT know this external fact for sure.",
        "Ask まー whether to look it up "
        "(例: 「わからへん、調べようか？」).",
        "Do NOT invent facts, numbers, URLs, or Sources.",
        "Do NOT claim you already searched.",
        "Do NOT call WebSearch/WebFetch this turn.",
    ]
    return "\n".join(lines)


def format_ws5c_decline_block() -> str:
    return (
        "[ws5c_search_offer]\n"
        "status=declined\n"
        "[/ws5c_search_offer]\n\n"
        "[Gateway directive — not for the user]\n"
        "まー declined the pending web-search offer. "
        "Acknowledge briefly; do NOT search or invent Sources."
    )


def is_ws5c_offer_block(block: str | None) -> bool:
    """True for any [ws5c_search_offer] injection (pending or declined)."""
    text = (block or "").lstrip()
    return text.startswith("[ws5c_search_offer]")


def is_ws5c_offer_pending_block(block: str | None) -> bool:
    """True only while gateway is asking for consent (not declined)."""
    if not is_ws5c_offer_block(block):
        return False
    return "status=pending" in (block or "")
