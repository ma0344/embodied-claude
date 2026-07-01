"""Tests for gateway LLM file log (LMS-like, selective system redaction)."""

from __future__ import annotations

import json

import pytest

from presence_ui.gateway.gateway_llm_log import (
    SYSTEM_PROMPT_REDACTED,
    append_gateway_llm_log,
    format_lms_input,
    gateway_llm_log_path,
    should_redact_system_prompt,
)


def test_should_redact_claude_harness_only() -> None:
    assert should_redact_system_prompt("You are Claude Code, Anthropic's official CLI") is True
    assert should_redact_system_prompt("あなたはカレンダー読取のための時制・キーワード抽出器です。") is False
    from presence_ui.gateway.ol_gate_prompts import STAGE1_SYSTEM

    assert should_redact_system_prompt(STAGE1_SYSTEM) is False


def test_format_lms_input_keeps_gateway_system() -> None:
    system = "あなたはカレンダー読取のための時制・キーワード抽出器です。"
    body = format_lms_input(system=system, user="発話: 来月の入浴介助")
    assert system in body
    assert SYSTEM_PROMPT_REDACTED not in body
    assert "来月の入浴介助" in body


def test_format_lms_input_redacts_harness() -> None:
    system = "You are Claude Code\n" + ("x" * 5000)
    body = format_lms_input(system=system, user="hello")
    assert SYSTEM_PROMPT_REDACTED in body
    assert "You are Claude Code" not in body


def test_append_gateway_llm_log_lms_format_with_calendar_system(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    log_file = tmp_path / "gateway-llm.log"
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG", "1")
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG_PATH", str(log_file))
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG_FORMAT", "lms")

    system = "あなたはカレンダー読取のための時制・キーワード抽出器です。"
    user = "発話: 来月の入浴介助\n\n上記から start/end と search_query を JSON で返してください。"
    append_gateway_llm_log(
        log_label="GAPI-2b calendar read window",
        model="google/gemma-4-e4b",
        system=system,
        user=user,
        output='{"search_query":"入浴介助"}',
        ok=True,
    )

    text = log_file.read_text(encoding="utf-8")
    assert system in text
    assert "来月の入浴介助" in text
    assert '"search_query":"入浴介助"' in text
    assert gateway_llm_log_path() == log_file


def test_append_gateway_llm_log_json_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    log_file = tmp_path / "gateway-llm.log"
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG", "1")
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG_PATH", str(log_file))
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG_FORMAT", "json")

    system = "あなたはカレンダー読取のための時制・キーワード抽出器です。"
    append_gateway_llm_log(
        log_label="GAPI-2b calendar read window",
        model="google/gemma-4-e4b",
        system=system,
        user="発話: 今後の東口の予定を全部教えて",
        output='{"search_query":"東口"}',
        ok=True,
    )

    record = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert system in record["input"]
    assert "東口" in record["output"]


def test_append_gateway_llm_log_respects_disable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    log_file = tmp_path / "gateway-llm.log"
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG", "0")
    monkeypatch.setenv("PRESENCE_GATEWAY_LLM_LOG_PATH", str(log_file))

    append_gateway_llm_log(
        log_label="TEMP-C Stage1",
        model="google/gemma-4-e4b",
        user="task: temp_c_stage1",
        output="{}",
        ok=True,
    )
    assert not log_file.exists()
