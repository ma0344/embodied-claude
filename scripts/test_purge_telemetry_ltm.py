"""Unit tests for scripts/purge-telemetry-ltm.py (finite markers only)."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parent / "purge-telemetry-ltm.py"
    spec = importlib.util.spec_from_file_location("purge_telemetry_ltm", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


purge = _load()


def _bootstrap(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                normalized_content TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                emotion TEXT NOT NULL DEFAULT 'neutral',
                importance INTEGER NOT NULL DEFAULT 3,
                category TEXT NOT NULL DEFAULT 'daily',
                tags TEXT NOT NULL DEFAULT ''
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _insert(path: Path, mid: str, content: str) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT INTO memories(id, content, timestamp) VALUES (?, ?, ?)",
            (mid, content, "2026-07-19T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()


def test_classify_keeps_meal_and_episode() -> None:
    assert purge.classify_bucket("7月18日に蕎麦を食べた記録がある") is None
    assert purge.classify_bucket("【会話の区切り】今日は天気の話をした") is None


def test_classify_vision_desire_bio8d_gateway() -> None:
    assert (
        purge.classify_bucket("=== VISION_CAPTION ===\n部屋\n=== END ===")
        == "vision"
    )
    assert purge.classify_bucket("[desire:observe_room] look_around") == "desire"
    assert (
        purge.classify_bucket(
            "体の調子がおかしいで。目と声が同時にダメかも。"
            "まー、見てもらえる？"
        )
        == "bio8d"
    )
    assert (
        purge.classify_bucket(
            "[gateway_turn_context — not for the user]\n[desires]"
        )
        == "gateway_turn_context"
    )


def test_list_matches_skips_legitimate_rows(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    _bootstrap(db)
    _insert(db, "keep-meal", "7月18日に蕎麦を食べた記録がある")
    _insert(db, "keep-ep", "【会話の区切り】今日は天気の話をした")
    _insert(
        db,
        "kill-v",
        "Captured image at 2026-07-19 (640x360). === VISION_CAPTION",
    )
    _insert(db, "kill-d", "[desire:look_outside] 外を見た")
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        matches = purge.list_matches(conn)
    finally:
        conn.close()
    ids = {str(r["id"]) for _, r in matches}
    assert ids == {"kill-v", "kill-d"}


def test_apply_deletes_only_matches(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    _bootstrap(db)
    _insert(db, "keep", "普通の会話メモリ")
    _insert(db, "kill", "[desire:browse_curiosity] WebSearch")
    rc = purge.main(["--db", str(db), "--apply", "--no-backup"])
    assert rc == 0
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT id FROM memories").fetchall()
    finally:
        conn.close()
    assert [r[0] for r in rows] == ["keep"]
