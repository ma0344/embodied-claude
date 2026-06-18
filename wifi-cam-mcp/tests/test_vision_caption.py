"""Vision caption corruption detection."""

from wifi_cam_mcp.vision import caption_looks_corrupt, normalize_vision_caption


def test_caption_looks_corrupt_all_question_marks() -> None:
    assert caption_looks_corrupt("????????????????")
    assert caption_looks_corrupt("? ? ? ? ? ? ? ?")


def test_caption_looks_corrupt_mostly_question_marks() -> None:
    assert caption_looks_corrupt("??????????あ")


def test_caption_looks_corrupt_valid_japanese() -> None:
    assert not caption_looks_corrupt("部屋にソファと窓が見える")
    assert not caption_looks_corrupt("short")


def test_normalize_vision_caption_rejects_corrupt() -> None:
    assert normalize_vision_caption("????????????????") is None
    assert normalize_vision_caption("  窓の外は曇り  ") == "窓の外は曇り"
