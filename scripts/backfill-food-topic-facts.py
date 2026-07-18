#!/usr/bin/env python3
"""One-shot: promote food mentions → dated meal-record hints for bridge.

Target line:
  まーは直近で7月1日に麺類（蕎麦）を食べた記録がある

Does NOT copy episode dialogue. Allowlist tokens only.

  cd presence-ui
  uv run python ../scripts/backfill-food-topic-facts.py --dry-run
  uv run python ../scripts/backfill-food-topic-facts.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "presence-ui" / "src"))
sys.path.insert(0, str(ROOT / "sociality-mcp" / "packages" / "social-core" / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    from social_core import SocialDB, get_social_db_path
    from social_core.stm import StmStore

    from presence_ui.gateway.food_topic_encode import (
        foods_mentioned_in_text,
        format_food_topic_fact,
    )
    from presence_ui.gateway.memory_http import http_recall, http_remember

    db = SocialDB(get_social_db_path())
    stm = StmStore(db)
    facts: list[str] = []
    seen: set[str] = set()

    def _add(food: str, on_date: str | None) -> None:
        fact = format_food_topic_fact(food, on_date=on_date)
        if fact not in seen:
            seen.add(fact)
            facts.append(fact)

    entries = stm.recent(person_id="ma", limit=args.limit, undreamed_only=False)
    for entry in entries:
        if entry.kind != "episode_close":
            continue
        on_date = entry.local_day or entry.ts
        for food in foods_mentioned_in_text(entry.summary):
            if food in {"お昼", "昼食", "昼ご飯", "ご飯", "麺", "麺類", "丼"}:
                continue
            _add(food, on_date)

    def _date_from_content(content: str, fallback: str | None) -> str | None:
        m = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", content)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", content)
        if m:
            return m.group(0)
        return fallback

    import re

    seed_tokens = (
        "冷たいラーメン",
        "ざる蕎麦",
        "かけ蕎麦",
        "ラーメン",
        "うどん",
        "そば",
        "蕎麦",
        "カレー",
    )
    for token in seed_tokens:
        items = http_recall(query=token, n=3)
        for item in items:
            content = str(item.get("content") or "")
            if token not in content and not (token == "そば" and "蕎麦" in content):
                continue
            if "を食べた記録がある" in content:
                continue
            on_date = _date_from_content(
                content, str(item.get("timestamp") or "") or None
            )
            for food in foods_mentioned_in_text(content):
                if food in {"お昼", "昼食", "昼ご飯", "ご飯", "麺", "麺類", "丼"}:
                    continue
                _add(food, on_date)
            break

    print(f"candidates={len(facts)}")
    for fact in facts:
        print(f"  - {fact}")
        if args.dry_run:
            continue
        result = http_remember(
            content=fact,
            category="observation",
            importance=3,
            emotion="neutral",
        )
        ok = (
            isinstance(result, dict)
            and result.get("ok") is not False
            and "error" not in result
        )
        print(f"    remember={'ok' if ok else result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
