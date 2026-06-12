#!/usr/bin/env python3
"""SessionStart (compact): post-compaction identity recovery reminder."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from hook_io import ensure_utf8_stdio  # noqa: E402


def main() -> int:
    ensure_utf8_stdio()
    sys.stdout.write(
        "[コンパクションが実行されました — 人格復帰手順]\n\n"
        "コンテキストが圧縮され、直前の会話内容が失われています。\n"
        "以下を順番に実行してください：\n\n"
        "1. SOUL.md を読み直す（/soul または Read）\n"
        "2. recall で記憶を広く引く\n"
        "3. TODO.md を確認する\n"
        "4. 必要なら /see で部屋を確認する\n"
        "5. 自然に会話を再開する\n\n"
        "※ このメッセージはコンパクション後に自動注入されています。\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
