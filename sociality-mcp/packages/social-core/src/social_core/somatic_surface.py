"""BIO-8d escalation push templates — compose demote / Dreaming LTM skip.

Finite agent-fixed strings only (not open-ended NL health talk).
"""

from __future__ import annotations


def is_somatic_escalation_push_passage(content: str) -> bool:
    """True for BIO-8d escalation push templates (agent-fixed).

    Shape: starts with ``体の調子がおかしいで。`` and includes both a simultaneous-
    failure clause and ``見てもらえる？``.
    """
    text = (content or "").strip()
    if not text.startswith("体の調子がおかしいで。"):
        return False
    if "見てもらえる？" not in text:
        return False
    return (
        "が同時にダメかも" in text
        or "複数の感覚が同時にダメかも" in text
    )
