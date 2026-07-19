"""MEM-8b — purpose-specific recall query shaping (compose first)."""

from __future__ import annotations

import os
import re
from typing import Literal

RecallPurpose = Literal["compose", "followup", "autonomous"]

_EPISODE_MARKERS = ("【会話の区切り】", "【会話の一区切り】", "episode_close")
_LITERARY_USER_CUE = re.compile(
    r"青空|文庫|読んだ|読んでる|読んでた|本|小説|一冊|しおり|芥川|羅生門"
)
_TEMPORAL_Q = re.compile(r"いつ|何曜|曜日|何時|スケジュール|予定|何日")
_DEIXIS = re.compile(r"ここっち|こっち|それ|あれ|この|その")
_CHITCHAT = re.compile(
    r"^(おはよう|こんばんは|こんにちは|おやすみ|うん|はい|ねえ|ん+|ok|hi|hello)[。!?？\s]*$",
    re.IGNORECASE,
)
# Soft status / reassurance replies — not memory queries (e.g. 大丈夫。ぼーっと…).
_SOFT_STATUS_REPLY = re.compile(
    r"^(大丈夫|平気|問題ない|なんともない|気にせんといて)"
    r"[。．.!！？?\s　]*(.*)$",
    re.IGNORECASE,
)
_SOFT_STATUS_BLOCK = re.compile(
    r"[?？]|いつ|何|誰|どこ|どう|なぜ|予定|覚え|覚えて|読ん|青空|本"
)
_WEEKDAY_TIME = re.compile(r"[月火水木金土]曜|午前|午後|\d{1,2}[:：]\d{2}")
_JP_RUN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff々]+")
_ENTITY_GROUPS: tuple[tuple[str, ...], ...] = (
    ("ねっとわん", "ネットワン", "netone"),
    ("ここっち", "グループホーム"),
)


def is_episodic_blob(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return True
    if any(marker in text for marker in _EPISODE_MARKERS):
        return True
    return len(text) > 360 and text.count("\n") >= 2


def is_literary_agent_passage(content: str) -> bool:
    """True for LW-READ encode lines (青空 passage dumps), not user book talk."""
    from social_core.literary_surface import is_literary_agent_surface

    return is_literary_agent_surface(content)


_VISION_BRIDGE_MARKERS = (
    "=== VISION_CAPTION",
    "=== VISION_DESCRIBE_FAILED",
    "VISION_DESCRIBE_FAILED",
    "Captured image at ",
    "Center View",
)


def is_vision_bridge_noise(content: str) -> bool:
    """True for camera caption / describe-failure dumps — not cross-session talk gists."""
    text = (content or "").strip()
    if not text:
        return True
    return any(marker in text for marker in _VISION_BRIDGE_MARKERS)


def is_desire_satisfaction_telemetry(content: str) -> bool:
    """True for agent desire-satisfaction dumps (``[desire:…]`` encode lines)."""
    return (content or "").strip().startswith("[desire:")


def is_legacy_food_talk_fact(content: str) -> bool:
    """Old meal encode: 「〜の話をした（食事の話題）」— prefer dated 食べた記録 instead."""
    text = (content or "").strip()
    if not text:
        return False
    if "を食べた記録がある" in text:
        return False
    return "の話をした" in text and "食事の話題" in text


def is_meal_record_fact(content: str) -> bool:
    """Dated meal-record card for bridge / compose hints."""
    return "を食べた記録がある" in (content or "")


def is_action_record_fact(content: str) -> bool:
    """Meal/cook dated cards — do not forward-anchor bare M月D日 on inject."""
    text = content or ""
    return "を食べた記録がある" in text or "を作った記録がある" in text


def is_somatic_escalation_push_passage(content: str) -> bool:
    """True for BIO-8d escalation push templates (agent-fixed), not free NL health talk."""
    from social_core.somatic_surface import (
        is_somatic_escalation_push_passage as _is_push,
    )

    return _is_push(content)


def literary_user_cue(user_text: str) -> bool:
    """まー is asking about / continuing a reading thread."""
    return bool(_LITERARY_USER_CUE.search((user_text or "").strip()))


def should_skip_compose_recall(user_text: str) -> bool:
    text = (user_text or "").strip()
    if len(text) < 2:
        return True
    if _CHITCHAT.match(text):
        return True
    if len(text) <= 3 and "?" not in text and "？" not in text:
        return True
    soft = _SOFT_STATUS_REPLY.match(text)
    if soft is not None:
        rest = (soft.group(2) or "").strip()
        if not rest or not _SOFT_STATUS_BLOCK.search(rest):
            return True
    return False


def _normalize_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        cleaned = " ".join(q.split()).strip()
        if len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _entities_in_text(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for group in _ENTITY_GROUPS:
        for alias in group:
            if alias in text or alias.lower() in lower:
                found.append(group[0])
                break
    return list(dict.fromkeys(found))


def _schedule_hints_from_gists(gists: list[str], entities: list[str]) -> list[str]:
    hints: list[str] = []
    for gist in gists:
        gist_lower = gist.lower()
        if entities and not any(
            entity in gist or entity.lower() in gist_lower for entity in entities
        ):
            continue
        for match in _WEEKDAY_TIME.finditer(gist):
            token = match.group().strip()
            if token and token not in hints:
                hints.append(token)
    return hints[:4]


def _anchors_from_gists(gists: list[str]) -> list[str]:
    anchors: list[str] = []
    for gist in gists:
        if "ここっち" in gist and "グループホーム" in gist:
            anchors.extend(["ここっち", "グループホーム"])
        if "embodied-claude" in gist or "こっち" in gist:
            anchors.append("embodied-claude")
    return list(dict.fromkeys(anchors))[:4]


def _keyword_query(text: str, *, max_keywords: int = 6) -> str:
    from interaction_orchestrator_mcp.memory_adapter import _extract_keywords

    keywords = _extract_keywords(text, max_keywords=max_keywords)
    if keywords:
        return " ".join(keywords)
    return text[:120].strip()


def _compose_queries(user_text: str, profile_gists: list[str]) -> list[str]:
    text = user_text.strip()
    queries: list[str] = []
    temporal = bool(_TEMPORAL_Q.search(text))
    entities = _entities_in_text(text)
    schedule_hints = _schedule_hints_from_gists(profile_gists, entities)

    if temporal:
        entity_part = " ".join(entities) if entities else _keyword_query(text, max_keywords=4)
        if schedule_hints:
            queries.append(" ".join([entity_part, *schedule_hints, "まー"]).strip())
        queries.append(
            " ".join(
                [
                    entity_part,
                    "水曜",
                    "午前",
                    "スケジュール",
                    "仕事",
                ]
            ).strip()
        )

    if _DEIXIS.search(text):
        anchors = _anchors_from_gists(profile_gists)
        if anchors:
            queries.append(
                " ".join([*anchors, *_keyword_query(text, max_keywords=3).split()]).strip()
            )

    if entities and not temporal:
        queries.append(" ".join([*entities, *_keyword_query(text, max_keywords=4).split()]))

    if not queries:
        queries.append(_keyword_query(text))

    return _normalize_queries(queries)[:2]


def build_recall_queries(
    *,
    purpose: RecallPurpose = "compose",
    user_text: str | None,
    profile_gists: list[str] | None = None,
) -> list[str]:
    """Return 0–2 HTTP /recall queries for the given purpose."""
    text = (user_text or "").strip()
    if len(text) < 2:
        return []

    gists = [g.strip() for g in (profile_gists or []) if g and g.strip()]

    if purpose == "compose":
        if should_skip_compose_recall(text):
            return []
        return _compose_queries(text, gists)

    return [_keyword_query(text)]


def is_temporal_question(user_text: str) -> bool:
    return bool(_TEMPORAL_Q.search((user_text or "").strip()))


def temporal_schedule_contract_enabled() -> bool:
    """MEM-8b 退縮実験: 0/false で schedule_facts + temporal must_include を無効化."""
    raw = os.getenv("PRESENCE_TEMPORAL_SCHEDULE_CONTRACT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def extract_schedule_facts(user_text: str, sources: list[str]) -> list[str]:
    """Pull one-line schedule answers from LTM/gist text for temporal questions."""
    if not is_temporal_question(user_text):
        return []
    entities = _entities_in_text(user_text)
    facts: list[str] = []
    for source in sources:
        text = (source or "").strip()
        if not text or is_episodic_blob(text):
            continue
        if not _WEEKDAY_TIME.search(text):
            continue
        if entities and not any(
            entity in text or entity.lower() in text.lower() for entity in entities
        ):
            continue
        for clause in re.split(r"[。\n]", text):
            cand = clause.strip()
            if len(cand) < 8 or not _WEEKDAY_TIME.search(cand):
                continue
            facts.append(cand[:140])
            break
        else:
            facts.append(text[:140])
    return list(dict.fromkeys(facts))[:2]


def compose_hit_rank(content: str, *, base_relevance: float, temporal: bool) -> float:
    score = base_relevance
    if is_episodic_blob(content):
        score -= 0.55 if temporal else 0.15
        if temporal:
            score = min(score, 0.35)
    if temporal:
        if _WEEKDAY_TIME.search(content):
            score += 0.3
        if any(token in content for token in ("水曜", "午前", "午後", "スケジュール")):
            score += 0.15
        if len(content) < 280 and not is_episodic_blob(content):
            score += 0.1
    return max(0.0, min(1.0, score))


def is_fact_like_row(content: str) -> bool:
    """MEM-8a-lite — compact fact row heuristic (until multi-view encode lands)."""
    text = (content or "").strip()
    if not text or is_episodic_blob(text):
        return False
    if any(marker in text for marker in _EPISODE_MARKERS):
        return False
    if len(text) > 280 or text.count("\n") >= 2:
        return False
    return True


_FACT_CATEGORIES = frozenset({"observation", "memory", "technical", "feeling", "daily"})


def bridge_hit_rank(
    content: str,
    *,
    base_relevance: float,
    category: str | None = None,
    importance: int | None = None,
) -> float:
    """Rank bridge recall hits — prefer 8a-like fact rows over narrative snippets."""
    score = compose_hit_rank(content, base_relevance=base_relevance, temporal=False)
    if is_fact_like_row(content):
        score += 0.25
    cat = (category or "").strip().lower()
    if cat in _FACT_CATEGORIES and cat != "daily":
        score += 0.08
    if importance is not None and importance >= 4:
        score += 0.05
    if not is_fact_like_row(content) and len(content) > 180:
        score -= 0.15
    return max(0.0, min(1.0, score))
