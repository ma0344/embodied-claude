"""SOUL prefetch for kiosk/native chat."""

from __future__ import annotations

from presence_ui.gateway.soul_prefetch import detect_soul_read_request, soul_read_prefetch_block


def test_detect_soul_read_request():
    assert detect_soul_read_request("./SOUL.mdを読んでみて")
    assert detect_soul_read_request("/soul")
    assert not detect_soul_read_request("おはよう")


def test_soul_prefetch_contains_voice_rules(tmp_path, monkeypatch):
    soul = tmp_path / "SOUL.md"
    soul.write_text(
        "うちは「こより」。関西弁のタメ口。一人称は「うち」。",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_SOUL_PATH", str(soul))
    block = soul_read_prefetch_block()
    assert "関西弁" in block
    assert "[soul_prefetch" in block
    assert "タメ口" in block
