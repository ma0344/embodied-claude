"""Osaka grammar preset — stable append + dialect lint."""

from __future__ import annotations

from pathlib import Path

import pytest

from presence_ui.gateway.osaka_grammar import (
    apply_dialect_rewrite_hints,
    apply_negation_heh_hin_rules,
    dialect_leak_hits,
    dialect_lint_enabled,
    dialect_rewrite_enabled,
    load_osaka_grammar_distill,
    log_dialect_leak_if_any,
    osaka_grammar_in_append,
    osaka_grammar_stable_append,
    surface_reply_postprocess,
)


def test_osaka_grammar_append_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_OSAKA_GRAMMAR_IN_APPEND", raising=False)
    assert osaka_grammar_in_append() is False
    assert osaka_grammar_stable_append() == ""


def test_osaka_grammar_append_loads_distill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "koyori-osaka-grammar.distill.md").write_text(
        "## 大阪弁\n- へん",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", str(presets))
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_IN_APPEND", "1")
    load_osaka_grammar_distill.cache_clear()  # type: ignore[attr-defined]

    block = osaka_grammar_stable_append()
    assert "[Osaka grammar" in block
    assert "へん" in block


def test_dialect_leak_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "koyori-dialect-lint.json").write_text(
        '{"avoid_substrings":["です","ます"],"avoid_patterns":["なんださかい"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", str(presets))
    from presence_ui.gateway import osaka_grammar as og

    og._load_lint_config.cache_clear()  # type: ignore[attr-defined]

    assert "です" in dialect_leak_hits("そうですね")
    assert not dialect_leak_hits("ほんまやな")


def test_surface_reply_postprocess_rewrite_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "koyori-dialect-lint.json").write_text(
        '{"rewrite_hints":{"わかりません":"わからへん"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", str(presets))
    monkeypatch.setenv("PRESENCE_DIALECT_LINT_REWRITE", "0")
    from presence_ui.gateway import osaka_grammar as og

    og._load_lint_config.cache_clear()  # type: ignore[attr-defined]

    assert surface_reply_postprocess("わかりません") == "わかりません"


def test_surface_reply_postprocess_rewrite_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "koyori-dialect-lint.json").write_text(
        '{"rewrite_hints":{"わかりません":"わからへん"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", str(presets))
    monkeypatch.setenv("PRESENCE_DIALECT_LINT_REWRITE", "1")
    from presence_ui.gateway import osaka_grammar as og

    og._load_lint_config.cache_clear()  # type: ignore[attr-defined]

    assert surface_reply_postprocess("わかりません") == "わからへん"
    assert dialect_rewrite_enabled() is True


def test_rewrite_before_lint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "koyori-dialect-lint.json").write_text(
        '{"avoid_substrings":["です"],"rewrite_hints":{"そうですね":"そうやな"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENCE_OSAKA_GRAMMAR_PRESET_DIR", str(presets))
    monkeypatch.setenv("PRESENCE_DIALECT_LINT_REWRITE", "1")
    monkeypatch.setenv("PRESENCE_DIALECT_LINT", "1")
    from presence_ui.gateway import osaka_grammar as og

    og._load_lint_config.cache_clear()  # type: ignore[attr-defined]

    out = surface_reply_postprocess("そうですね")
    assert out == "そうやな"
    assert not dialect_leak_hits(out)


def test_dialect_lint_can_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_DIALECT_LINT", "0")
    assert dialect_lint_enabled() is False
    log_dialect_leak_if_any("ですます")  # no raise


def test_negation_idan_hin() -> None:
    assert apply_negation_heh_hin_rules("まだ知りへん") == "まだ知りひん"
    assert apply_negation_heh_hin_rules("食べへん") == "食べへん"
    assert apply_negation_heh_hin_rules("できへんねん") == "でけへんねん"


def test_negation_dekihen_lint_hit() -> None:
    assert "pattern:できへん" in dialect_leak_hits("それはできへんわ")
