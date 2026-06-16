"""Phase B LLM reminder spec tests."""

from __future__ import annotations

import pytest

from presence_ui.gateway.reminder_spec import parse_llm_reminder_payload


def test_parse_llm_reminder_payload_ok() -> None:
    spec = parse_llm_reminder_payload(
        {
            "due_at_iso": "2026-06-16T20:00:00+09:00",
            "speak_line": "まー、打合せやで",
            "delivery": "say",
            "title": "打合せリマインド",
        },
        source_text="来週の打合せの前にリマインドして",
        ts="2026-06-16T19:00:00+09:00",
    )
    assert spec is not None
    assert spec.speak_line == "まー、打合せやで"
    assert spec.delivery == "say"


def test_parse_llm_reminder_payload_rejects_past() -> None:
    spec = parse_llm_reminder_payload(
        {
            "due_at_iso": "2026-06-16T18:00:00+09:00",
            "speak_line": "遅い",
            "delivery": "say",
        },
        source_text="リマインド",
        ts="2026-06-16T19:00:00+09:00",
    )
    assert spec is None


@pytest.mark.asyncio
async def test_try_create_llm_reminder_skips_when_rule_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock, MagicMock

    from presence_ui.gateway import reminder_spec

    monkeypatch.setattr(reminder_spec, "llm_reminder_spec_enabled", lambda: True)
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    result = await reminder_spec.try_create_llm_reminder_commitment(
        stores,
        person_id="ma",
        text="3分後に「まー」と say で教えて",
        ts="2026-06-16T19:00:00+09:00",
    )
    assert result is None
    stores.relationship.create_reminder_from_spec.assert_not_called()

    monkeypatch.setattr(
        reminder_spec,
        "generate_reminder_spec_llm",
        AsyncMock(
            return_value=parse_llm_reminder_payload(
                {
                    "due_at_iso": "2026-06-16T20:00:00+09:00",
                    "speak_line": "まー、打合せやで",
                    "delivery": "say",
                },
                source_text="来週の金曜15時にリマインドして",
                ts="2026-06-16T19:00:00+09:00",
            )
        ),
    )
    stores.relationship.create_reminder_from_spec.return_value = {"commitment_id": "c1"}
    result = await reminder_spec.try_create_llm_reminder_commitment(
        stores,
        person_id="ma",
        text="来週の打合せの15分前にリマインドして",
        ts="2026-06-16T19:00:00+09:00",
    )
    assert result == {"commitment_id": "c1"}
