"""Osaka dialect grammar presets — stable append + post-reply lint (optional)."""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DISTILL_NAME = "koyori-osaka-grammar.distill.md"
_LINT_NAME = "koyori-dialect-lint.json"
_DISTILL_MAX_CHARS = 1600

# い段（直前音節の母音がい）で終わる語幹 + へん は誤り → ひん
_IDAN_KANA = "いきぎしじちぢにひびぴみり"
_IDAN_HEHN = re.compile(rf"([{_IDAN_KANA}])へん")

# できる → でけへん（できへんは誤）。できひんも正しい別形。
_LEXICAL_NEGATION_FIXES: tuple[tuple[str, str], ...] = (("できへん", "でけへん"),)


def osaka_grammar_in_append() -> bool:
    """Append distill.md to gateway stable prompt (off if already in LM Studio system)."""
    raw = os.environ.get("PRESENCE_OSAKA_GRAMMAR_IN_APPEND", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def dialect_rewrite_enabled() -> bool:
    raw = os.environ.get("PRESENCE_DIALECT_LINT_REWRITE", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def dialect_lint_enabled() -> bool:
    raw = os.environ.get("PRESENCE_DIALECT_LINT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _preset_path(name: str) -> Path:
    override = os.environ.get("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", "").strip()
    base = Path(override).expanduser() if override else _repo_root() / "presets"
    return base / name


@lru_cache(maxsize=1)
def load_osaka_grammar_distill(*, max_chars: int = _DISTILL_MAX_CHARS) -> str:
    path = _preset_path(_DISTILL_NAME)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()[:max_chars]


def osaka_grammar_stable_append() -> str:
    if not osaka_grammar_in_append():
        return ""
    body = load_osaka_grammar_distill()
    if not body:
        return ""
    return f"[Osaka grammar — mandatory voice reference]\n{body}"


@lru_cache(maxsize=1)
def _load_lint_config() -> dict[str, Any]:
    path = _preset_path(_LINT_NAME)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("failed to read dialect lint preset: %s", path)
        return {}
    return data if isinstance(data, dict) else {}


def dialect_leak_hits(text: str) -> list[str]:
    """Return avoid tokens/patterns found in surface reply (deterministic)."""
    line = (text or "").strip()
    if not line:
        return []
    cfg = _load_lint_config()
    hits: list[str] = []
    for sub in cfg.get("avoid_substrings", []):
        token = str(sub).strip()
        if token and token in line:
            hits.append(token)
    for pat in cfg.get("avoid_patterns", []):
        token = str(pat).strip()
        if token and token in line:
            hits.append(f"pattern:{token}")
    if "できへん" in line:
        hits.append("pattern:できへん")
    return hits


def apply_negation_heh_hin_rules(text: str) -> str:
    """い段語幹はひん、それ以外はへん。できるはでけへん（できへん不可）。"""
    out = text
    for src, dst in _LEXICAL_NEGATION_FIXES:
        out = out.replace(src, dst)
    return _IDAN_HEHN.sub(r"\1ひん", out)


def log_dialect_leak_if_any(reply: str) -> None:
    if not dialect_lint_enabled():
        return
    hits = dialect_leak_hits(reply)
    if not hits:
        return
    logger.info("dialect lint: standard-Japanese leakage in surface reply: %s", hits)


def apply_dialect_rewrite_hints(reply: str) -> str:
    """Optional soft rewrite for obvious ですます slips + へん/ひん境界."""
    if not dialect_rewrite_enabled():
        return reply
    cfg = _load_lint_config()
    hints = cfg.get("rewrite_hints", {})
    out = reply
    applied: list[str] = []
    if isinstance(hints, dict) and hints:
        for src, dst in sorted(hints.items(), key=lambda kv: -len(str(kv[0]))):
            src_s, dst_s = str(src), str(dst)
            if src_s and src_s in out:
                out = out.replace(src_s, dst_s)
                applied.append(src_s)
    if applied:
        logger.info("dialect rewrite: %s", applied)
    neg_fixed = apply_negation_heh_hin_rules(out)
    if neg_fixed != out:
        logger.info("dialect rewrite: negation heh/hin rules applied")
    return neg_fixed


def surface_reply_postprocess(reply: str) -> str:
    rewritten = apply_dialect_rewrite_hints(reply)
    log_dialect_leak_if_any(rewritten)
    return rewritten
