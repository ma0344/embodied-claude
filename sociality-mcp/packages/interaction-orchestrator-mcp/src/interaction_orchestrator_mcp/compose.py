"""compose_interaction_context — assemble a prompt-ready interaction frame."""

from __future__ import annotations

from typing import Any

from boundary_mcp.store import BoundaryStore
from joint_attention_mcp.store import JointAttentionStore
from relationship_mcp.store import RelationshipStore
from self_narrative_mcp.store import SelfNarrativeStore
from social_core import DEFAULT_POLICY_TIMEZONE, local_view, utc_now
from social_core.date_resolution import calendar_anchor_line
from social_state_mcp.store import SocialStateStore

from .desire_source import load_desire_snapshot
from .memory_adapter import (
    OrchestratorMemoryAdapter,
)
from .memory_adapter import (
    make_default_adapter as make_default_memory_adapter,
)
from .schemas import (
    AgentStateSummary,
    CommitmentSummary,
    ComposeInteractionContextInput,
    FollowupSuggestion,
    InteractionContext,
    InterpretationShiftSummary,
    OpenLoopSummary,
    RecentExperienceRef,
    RelevantMemoryRef,
    ResponseContract,
    SessionTurn,
)
from .session_adapter import (
    OrchestratorSessionAdapter,
    make_default_session_adapter,
)
from .store import InteractionOrchestratorStore


def compose_interaction_context(
    payload: ComposeInteractionContextInput,
    *,
    social_state_store: SocialStateStore,
    relationship_store: RelationshipStore,
    joint_attention_store: JointAttentionStore,
    boundary_store: BoundaryStore,
    self_narrative_store: SelfNarrativeStore,
    orchestrator_store: InteractionOrchestratorStore,
    policy_timezone: str = DEFAULT_POLICY_TIMEZONE,
    memory_adapter: OrchestratorMemoryAdapter | None = None,
    session_adapter: OrchestratorSessionAdapter | None = None,
) -> InteractionContext:
    """Gather everything the next move needs into a single snapshot."""

    ts = utc_now()
    local = local_view(ts, policy_timezone)
    local_time_text = local.isoformat(timespec="seconds")

    social_state = _call(
        social_state_store.get_social_state,
        window_seconds=900,
        person_id=payload.person_id,
        include_evidence=payload.include_private,
    )
    turn_taking_data = _infer_turn_taking(social_state_store, payload.person_id)

    person_model = None
    person_name = None
    open_loops: list[OpenLoopSummary] = []
    commitments: list[CommitmentSummary] = []
    followups: list[FollowupSuggestion] = []
    if payload.person_id:
        person_model = _optional_dict(
            relationship_store, "get_person_model", person_id=payload.person_id
        )
        if person_model:
            person_name = person_model.get("canonical_name") or person_model.get("person_id")
        open_loops = [
            OpenLoopSummary(
                loop_id=item.get("loop_id") or item.get("id", ""),
                topic=item.get("topic", ""),
                status=item.get("status", ""),
                updated_at=item.get("updated_at"),
                needs_date_confirmation=bool(item.get("needs_date_confirmation")),
                ambiguous_phrases=list(item.get("ambiguous_phrases") or []),
            )
            for item in _optional_list(
                relationship_store, "list_open_loops", person_id=payload.person_id
            )
            if not _is_noise_open_loop(str(item.get("topic") or ""))
        ]
        commitments = [
            CommitmentSummary(
                commitment_id=item.get("commitment_id") or item.get("id", ""),
                text=item.get("text", ""),
                due_at=item.get("due_at"),
                status=item.get("status", "active"),
                speak_line=_commitment_speak_line(item),
                delivery=_commitment_delivery(item),
            )
            for item in _optional_list(
                relationship_store,
                "list_due_commitments",
                person_id=payload.person_id,
                as_of=ts,
                timezone=policy_timezone,
            )
        ]
        followups = _collect_followups(relationship_store, payload.person_id, payload.user_text)

    self_summary_dict = _optional_dict(self_narrative_store, "get_self_summary")
    active_arcs = _optional_list(self_narrative_store, "list_active_arcs")
    latest_daybook = (self_summary_dict or {}).get("latest_daybook") if self_summary_dict else None

    desire_data = load_desire_snapshot() or {}
    dominant_desire = desire_data.get("dominant") if desire_data else None
    desires = desire_data.get("desires") or {}
    discomforts = desire_data.get("discomforts") or {}

    recent_experiences = orchestrator_store.recent_agent_experiences(
        person_id=payload.person_id, limit=5, include_private=payload.include_private
    )
    recent_shifts = orchestrator_store.recent_interpretation_shifts(
        person_id=payload.person_id, limit=3
    )

    memory = memory_adapter or make_default_memory_adapter()
    relevant_memories = [
        RelevantMemoryRef(
            memory_id=hit.memory_id,
            content=hit.content,
            relevance=hit.relevance,
            use_policy=hit.use_policy,
            reason=hit.reason,
        )
        for hit in memory.recall_for_response(
            user_text=payload.user_text,
            person_id=payload.person_id,
            max_results=6,
            include_private=payload.include_private,
        )
    ]

    joint_focus = _optional_dict(
        joint_attention_store,
        "get_current_joint_focus",
        person_id=payload.person_id,
    )

    boundary_hints = _derive_boundary_hints(boundary_store, social_state, ts)

    quiet_mode = _call(
        boundary_store.get_quiet_mode_state, ts=ts
    )
    quiet_active = bool(getattr(quiet_mode, "active", False)) if quiet_mode else False

    response_contract = _pick_contract(
        person_id=payload.person_id,
        channel=payload.channel,
        quiet_active=quiet_active,
    )

    agent_state = AgentStateSummary(
        ts=ts,
        desires={str(k): float(v) for k, v in desires.items()},
        discomforts={str(k): float(v) for k, v in discomforts.items()},
        dominant_desire=dominant_desire,
        recent_experiences=recent_experiences,
        active_arcs=list(active_arcs),
        private_reflections=orchestrator_store.count_private_reflections(
            person_id=payload.person_id
        ),
        interpretation_shifts=orchestrator_store.count_interpretation_shifts(),
        recent_interpretation_shifts=recent_shifts,
    )

    prompt_summary = _build_prompt_summary(
        local_time=local_time_text,
        calendar_anchor=calendar_anchor_line(ts=ts, tz_name=policy_timezone),
        person_id=payload.person_id,
        person_name=person_name,
        social_state=_to_plain(social_state),
        agent_state=agent_state,
        quiet_active=quiet_active,
        dominant_desire=dominant_desire,
        desires=desires,
        open_loops=open_loops,
        relevant_memories=relevant_memories,
    )

    session_history = _resolve_session_history(
        payload=payload,
        session_adapter=session_adapter or make_default_session_adapter(),
    )

    session_context_block = _format_session_context_block(
        session_id=payload.session_id,
        session_history=session_history,
    )
    prompt_session_block = _session_context_for_prompt(
        session_id=payload.session_id,
        session_history=session_history,
        claude_session_resume=payload.claude_session_resume,
    )

    compact_prompt_block = _compact_block(
        prompt_summary=prompt_summary,
        response_contract=response_contract,
        relevant_memories=relevant_memories,
        session_context_block=prompt_session_block,
        dominant_desire=dominant_desire,
        desires=desires,
        discomforts=discomforts,
        open_loops=open_loops,
        commitments_due=commitments,
        recent_shifts=recent_shifts,
        recent_experiences=recent_experiences,
        max_chars=payload.max_chars,
    )

    return InteractionContext(
        ts=ts,
        local_time=local_time_text,
        timezone=policy_timezone,
        person_id=payload.person_id,
        person_name=person_name,
        session_id=payload.session_id,
        session_history=session_history,
        session_context_block=session_context_block,
        social_state=_to_plain(social_state) or {},
        turn_taking=turn_taking_data,
        boundary_hints=boundary_hints,
        person_model=person_model,
        open_loops=open_loops,
        commitments_due=commitments,
        suggested_followups=followups,
        self_summary=self_summary_dict,
        active_arcs=list(active_arcs),
        latest_daybook=latest_daybook,
        desire_state=desire_data or None,
        agent_state=agent_state,
        relevant_memories=relevant_memories,
        recent_experiences=recent_experiences,
        joint_focus=joint_focus,
        current_scene_summary=(
            (joint_focus or {}).get("current_scene_summary") if joint_focus else None
        ),
        response_contract=response_contract,
        prompt_summary=prompt_summary,
        compact_prompt_block=compact_prompt_block,
    )


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _resolve_session_history(
    *,
    payload: ComposeInteractionContextInput,
    session_adapter: OrchestratorSessionAdapter,
) -> list[SessionTurn]:
    """Load transcript by session_id from social.db (shared room pointer)."""
    if payload.session_history:
        return list(payload.session_history)
    if not payload.session_id or not payload.person_id:
        return []
    return session_adapter.load_transcript(
        person_id=payload.person_id,
        session_id=payload.session_id,
    )


def _call(fn, **kwargs):
    try:
        return fn(**kwargs) if kwargs else fn()
    except Exception:
        return None


def _optional_dict(store: Any, method: str, **kwargs) -> dict[str, Any] | None:
    fn = getattr(store, method, None)
    if fn is None:
        return None
    try:
        result = fn(**kwargs) if kwargs else fn()
    except Exception:
        return None
    return _to_plain(result)


def _optional_list(store: Any, method: str, **kwargs) -> list[dict[str, Any]]:
    fn = getattr(store, method, None)
    if fn is None:
        return []
    try:
        result = fn(**kwargs) if kwargs else fn()
    except Exception:
        return []
    if result is None:
        return []
    plain = _to_plain(result)
    if isinstance(plain, list):
        return [item if isinstance(item, dict) else {"value": item} for item in plain]
    if isinstance(plain, dict):
        # Some stores return {"items": [...]} shapes.
        items = plain.get("items") or plain.get("open_loops") or plain.get("results")
        if isinstance(items, list):
            return [item if isinstance(item, dict) else {"value": item} for item in items]
    return []


def _to_plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


def _infer_turn_taking(
    social_state_store: SocialStateStore, person_id: str | None
) -> dict[str, Any]:
    """Call get_turn_taking_state if the store exposes it, else return idle."""

    fn = getattr(social_state_store, "get_turn_taking_state", None)
    if fn is not None:
        try:
            result = fn(person_id=person_id) if person_id else fn()
        except TypeError:
            try:
                result = fn()
            except Exception:
                return {"state": "hold", "confidence": 0.5}
        except Exception:
            return {"state": "hold", "confidence": 0.5}
        return _to_plain(result) or {"state": "hold", "confidence": 0.5}
    return {"state": "hold", "confidence": 0.5}


def _collect_followups(
    relationship_store: RelationshipStore, person_id: str, user_text: str | None
) -> list[FollowupSuggestion]:
    fn = getattr(relationship_store, "suggest_followup", None)
    if fn is None:
        return []
    try:
        raw = fn(person_id=person_id, context=user_text)
    except TypeError:
        try:
            raw = fn(person_id=person_id)
        except Exception:
            return []
    except Exception:
        return []
    plain = _to_plain(raw)
    items: list[dict[str, Any]] = []
    if isinstance(plain, list):
        items = [item for item in plain if isinstance(item, dict)]
    elif isinstance(plain, dict):
        seq = plain.get("suggestions") or plain.get("items") or []
        if isinstance(seq, list):
            items = [item for item in seq if isinstance(item, dict)]
    return [
        FollowupSuggestion(
            text=str(item.get("text") or item.get("suggestion") or ""),
            reason=item.get("reason"),
        )
        for item in items
        if item.get("text") or item.get("suggestion")
    ]


def _derive_boundary_hints(
    boundary_store: BoundaryStore, social_state: Any, ts: str
) -> list[str]:
    hints: list[str] = []
    plain = _to_plain(social_state) or {}
    availability = plain.get("availability")
    if availability == "do_not_interrupt":
        hints.append("current context signals do_not_interrupt")
    if availability == "maybe_interruptible":
        hints.append("availability is ambivalent; prefer bounded replies")
    if plain.get("interaction_phase") == "quiet_focus":
        hints.append("recent quiet request — avoid nudges")
    quiet_mode = _call(boundary_store.get_quiet_mode_state, ts=ts)
    if quiet_mode and getattr(quiet_mode, "active", False):
        hints.append("policy quiet hours are active — prefer private/non-voice actions")
    return hints


def _pick_contract(
    *, person_id: str | None, channel: str, quiet_active: bool
) -> ResponseContract:
    base = ResponseContract()
    if person_id == "ma":
        base = ResponseContract(
            treat_user_as="childhood friend まー; agent is こより (SOUL.md voice)",
            avoid=[
                "generic assistant tone or keigo",
                "breaking character into neutral chatbot",
                "pretending to remember unsupported facts",
                "meta comments about TTS or using tools",
            ],
            prefer=[
                "soft Kansai casual (うち / タメ口) per SOUL.md",
                "relationship-aware specificity with まー",
                "direct answers without over-explaining",
                "explicit uncertainty when memory or evidence is weak",
            ],
            initiative_policy="bounded",
            max_clarifying_questions=1,
        )
    if channel == "autonomous":
        base = base.model_copy(
            update={
                "initiative_policy": "bounded",
                "avoid": list(base.avoid)
                + ["public posting without review", "loud voice during quiet hours"],
                "max_clarifying_questions": 0,
            }
        )
    if quiet_active:
        base = base.model_copy(
            update={
                "prefer": list(base.prefer)
                + [
                    "private written reflection over spoken output",
                    "actions the human can read later, not interrupt on",
                ],
            }
        )
    return base


def _build_prompt_summary(
    *,
    local_time: str,
    calendar_anchor: str,
    person_id: str | None,
    person_name: str | None,
    social_state: dict[str, Any] | None,
    agent_state: AgentStateSummary,
    quiet_active: bool,
    dominant_desire: str | None,
    desires: dict[str, Any],
    open_loops: list[OpenLoopSummary],
    relevant_memories: list[RelevantMemoryRef],
) -> str:
    social = social_state or {}
    availability = social.get("availability", "unknown")
    activity = social.get("activity", "unknown")
    phase = social.get("interaction_phase", "idle")
    who = person_name or person_id or "the current person"
    desire_text = ""
    if dominant_desire:
        lvl = desires.get(dominant_desire)
        if isinstance(lvl, (int, float)):
            desire_text = f"Dominant pull: {dominant_desire} ({lvl:.2f})."
        else:
            desire_text = f"Dominant pull: {dominant_desire}."
    open_loop_text = (
        f"Open loops: {', '.join(loop.topic for loop in open_loops[:3])}."
        if open_loops
        else "No tracked open loops."
    )
    quiet_text = (
        "Policy quiet hours are ACTIVE — prefer private, non-voice, non-interruptive moves."
        if quiet_active
        else "Policy quiet hours are NOT active."
    )
    memory_text = (
        f"Relevant memories: {len(relevant_memories)} (mentionable: "
        f"{sum(1 for m in relevant_memories if m.use_policy == 'mentionable')})."
        if relevant_memories
        else "Relevant memories: none surfaced."
    )
    return (
        f"{calendar_anchor} Now {local_time} • {who} seems {availability}, {activity}, phase={phase}. "
        f"{desire_text} {open_loop_text} {quiet_text} {memory_text} "
        f"Recent agent experiences: {len(agent_state.recent_experiences)}; "
        f"interpretation_shifts so far: {agent_state.interpretation_shifts}."
    ).strip()


def _session_context_for_prompt(
    *,
    session_id: str | None,
    session_history: list[SessionTurn],
    claude_session_resume: bool,
) -> str:
    """Room text for prompt injection — full transcript or arc summary only.

    When Claude Code resumes a JSONL session (``claude_session_resume=True``),
    dialogue is already in the model context; inject only a one-line arc summary
    to avoid duplicating up to thousands of characters every turn.
    """

    if not session_id or not session_history:
        return ""
    if claude_session_resume:
        arc = _session_arc_summary(session_history)
        return (
            f"[room_context session_id={session_id}]\n"
            f"{arc}\n"
            "Full room transcript omitted — Claude Code session resume carries dialogue."
        )
    return _format_session_context_block(
        session_id=session_id,
        session_history=session_history,
    )


def _format_session_context_block(
    *,
    session_id: str | None,
    session_history: list[SessionTurn],
) -> str:
    if not session_id or not session_history:
        return ""

    arc = _session_arc_summary(session_history)
    lines = [
        f"[recent_room_context session_id={session_id}]",
        arc,
        "Conversation in THIS room only (chronological):",
    ]
    for turn in session_history:
        who = "まー" if turn.sender == "ma" else "こより"
        lines.append(f"{who}: {turn.text}")
    return "\n".join(lines)


def _session_arc_summary(session_history: list[SessionTurn]) -> str:
    total = len(session_history)
    human = sum(1 for turn in session_history if turn.sender == "ma")
    koyori = total - human
    last = session_history[-1]
    last_who = "まー" if last.sender == "ma" else "こより"
    return (
        f"Room arc: {total} turns ({human} from まー, {koyori} from こより). "
        f"Last speaker: {last_who}."
    )


def _trim_session_context_block(block: str, *, max_chars: int) -> str:
    if len(block) <= max_chars:
        return block
    lines = block.splitlines()
    if len(lines) <= 4:
        return block[: max_chars - 1].rstrip() + "…"

    header = lines[:3]
    body = lines[3:]
    budget = max_chars - sum(len(line) + 1 for line in header) - 40
    if budget < 200:
        return block[: max_chars - 1].rstrip() + "…"

    head_turns = body[:2]
    tail_budget = budget - sum(len(line) + 1 for line in head_turns)
    tail_turns: list[str] = []
    for line in reversed(body[2:]):
        if sum(len(item) + 1 for item in tail_turns) + len(line) + 1 > tail_budget:
            break
        tail_turns.insert(0, line)

    omitted = len(body) - len(head_turns) - len(tail_turns)
    middle = [f"… ({omitted} earlier turns omitted) …"] if omitted > 0 else []
    trimmed = "\n".join([*header, *head_turns, *middle, *tail_turns])
    if len(trimmed) > max_chars:
        return trimmed[: max_chars - 1].rstrip() + "…"
    return trimmed


def _is_noise_open_loop(topic: str) -> bool:
    """Skip legacy garbage loops (full agent lines mistaken as topics)."""

    compact = topic.strip()
    if not compact:
        return True
    if len(compact) > 40:
        return True
    if "うち、" in compact or "こより" in compact:
        return True
    if compact.count("、") >= 2:
        return True
    if "覚えてる" in compact or "覚えてます" in compact or "覚えとる" in compact:
        return True
    # Agent gratitude / reply lines mistaken as loop topics (legacy ingest noise).
    if "ありがと" in compact or "調べてくれた" in compact or "教えてくれた" in compact:
        return True
    if compact.endswith("ね") and "、調べ" in compact:
        return True
    return False


def _format_desire_section(
    *,
    dominant_desire: str | None,
    desires: dict[str, Any],
    discomforts: dict[str, Any],
    max_lines: int = 4,
) -> list[str]:
    if not desires and not dominant_desire:
        return []
    lines = ["[desires]"]
    if dominant_desire:
        lvl = desires.get(dominant_desire)
        dcom = discomforts.get(dominant_desire, 0.0)
        if isinstance(lvl, (int, float)):
            lines.append(
                f"dominant: {dominant_desire} level={float(lvl):.2f} "
                f"discomfort={float(dcom):.2f}"
            )
        else:
            lines.append(f"dominant: {dominant_desire}")
    ranked = sorted(
        ((name, value) for name, value in desires.items() if isinstance(value, (int, float))),
        key=lambda item: item[1],
        reverse=True,
    )
    shown = 0
    for name, lvl in ranked:
        if name == dominant_desire:
            continue
        dcom = discomforts.get(name, 0.0)
        lines.append(f"- {name}: {float(lvl):.2f} (discomfort {float(dcom):.2f})")
        shown += 1
        if shown >= max_lines:
            break
    return lines if len(lines) > 1 else []


def _commitment_speak_line(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata") or {}
    speak_line = metadata.get("speak_line") or item.get("speak_line")
    if not speak_line:
        return None
    return str(speak_line).strip() or None


def _commitment_delivery(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    delivery = metadata.get("delivery") or item.get("delivery") or "say"
    return "nudge_only" if delivery == "nudge_only" else "say"


def _format_open_loops_section(
    open_loops: list[OpenLoopSummary], *, max_items: int = 3
) -> list[str]:
    if not open_loops:
        return []
    lines = ["[open_loops]"]
    for loop in open_loops[:max_items]:
        status = loop.status or "open"
        if loop.needs_date_confirmation:
            phrases = ", ".join(loop.ambiguous_phrases) or "?"
            lines.append(
                f"- {loop.topic} ({status}; needs_date_confirmation: {phrases})"
            )
        else:
            lines.append(f"- {loop.topic} ({status})")
    return lines


def _format_date_confirmation_section(
    open_loops: list[OpenLoopSummary], *, max_items: int = 3
) -> list[str]:
    pending = [loop for loop in open_loops if loop.needs_date_confirmation][:max_items]
    if not pending:
        return []
    lines = ["[date_confirmation_needed]"]
    for loop in pending:
        phrases = ", ".join(loop.ambiguous_phrases) or loop.topic
        lines.append(
            f"- loop: {loop.topic[:120]} — ask まー for concrete date "
            f"(ambiguous: {phrases}); do not guess"
        )
    return lines


def _format_commitments_due_section(
    commitments: list[CommitmentSummary], *, max_items: int = 3
) -> list[str]:
    if not commitments:
        return []
    lines = ["[commitments_due]"]
    for item in commitments[:max_items]:
        due = item.due_at or "?"
        lines.append(f"- {item.text} (due {due})")
    return lines


def _format_shifts_section(
    shifts: list[InterpretationShiftSummary], *, max_items: int = 2
) -> list[str]:
    if not shifts:
        return []
    lines = ["[interpretation_shifts]"]
    for shift in shifts[:max_items]:
        old = shift.old_interpretation[:80] + (
            "…" if len(shift.old_interpretation) > 80 else ""
        )
        new = shift.new_interpretation[:80] + (
            "…" if len(shift.new_interpretation) > 80 else ""
        )
        lines.append(f"- {shift.topic}: OLD「{old}」→ NEW「{new}」")
    return lines


def _looks_like_dialogue_prose(text: str) -> bool:
    """Heuristic: stored agent_response that reads like spoken reply, not audit metadata."""
    if text.startswith("Replied to まー"):
        return False
    markers = ("うちは", "うち、", "まー", "……", "。", "？", "！", "\n")
    return sum(1 for m in markers if m in text) >= 2


def _format_experiences_section(
    experiences: list[RecentExperienceRef], *, max_items: int = 3
) -> list[str]:
    if not experiences:
        return []
    lines = ["[recent_experiences]"]
    for exp in experiences[:max_items]:
        if exp.kind == "agent_response" and _looks_like_dialogue_prose(exp.summary):
            lines.append(
                f"- [{exp.kind}] prior reply logged "
                "(answer THIS turn fresh; do not continue prior wording)"
            )
            continue
        summary = exp.summary[:100] + ("…" if len(exp.summary) > 100 else "")
        lines.append(f"- [{exp.kind}] {summary}")
    return lines


def _compact_block(
    *,
    prompt_summary: str,
    response_contract: ResponseContract,
    relevant_memories: list[RelevantMemoryRef],
    session_context_block: str = "",
    dominant_desire: str | None = None,
    desires: dict[str, Any] | None = None,
    discomforts: dict[str, Any] | None = None,
    open_loops: list[OpenLoopSummary] | None = None,
    commitments_due: list[CommitmentSummary] | None = None,
    recent_shifts: list[InterpretationShiftSummary] | None = None,
    recent_experiences: list[RecentExperienceRef] | None = None,
    max_chars: int,
) -> str:
    contract_lines = [f"treat_user_as: {response_contract.treat_user_as}"]
    if response_contract.avoid:
        contract_lines.append("avoid: " + "; ".join(response_contract.avoid[:4]))
    if response_contract.prefer:
        contract_lines.append("prefer: " + "; ".join(response_contract.prefer[:4]))
    contract_lines.append(
        f"initiative: {response_contract.initiative_policy}, "
        f"max_clarifying={response_contract.max_clarifying_questions}"
    )
    memory_lines: list[str] = []
    mentionable = [m for m in relevant_memories if m.use_policy == "mentionable"]
    background = [m for m in relevant_memories if m.use_policy == "background_only"]
    for m in mentionable[:3]:
        snippet = m.content[:120] + ("…" if len(m.content) > 120 else "")
        memory_lines.append(f"[mentionable r={m.relevance:.2f}] {snippet}")
    for m in background[:2]:
        snippet = m.content[:80] + ("…" if len(m.content) > 80 else "")
        memory_lines.append(f"[background r={m.relevance:.2f}] {snippet}")

    session_budget = min(7000, max(max_chars // 2, 1200))
    trimmed_session = ""
    if session_context_block:
        trimmed_session = _trim_session_context_block(
            session_context_block,
            max_chars=session_budget,
        )

    sections = [
        "[interaction_context]",
        prompt_summary,
    ]
    soul_sections = [
        *_format_desire_section(
            dominant_desire=dominant_desire,
            desires=desires or {},
            discomforts=discomforts or {},
        ),
        *_format_open_loops_section(open_loops or []),
        *_format_date_confirmation_section(open_loops or []),
        *_format_commitments_due_section(commitments_due or []),
        *_format_shifts_section(recent_shifts or []),
        *_format_experiences_section(recent_experiences or []),
    ]
    if soul_sections:
        sections.extend(["", *soul_sections])
    if trimmed_session:
        sections.extend(["", trimmed_session])
    sections.extend(
        [
            "[response_contract]",
            *contract_lines,
        ]
    )
    if memory_lines:
        sections.append("[relevant_memories]")
        sections.extend(memory_lines)
    block = "\n".join(sections)
    if len(block) > max_chars:
        block = block[: max_chars - 1].rstrip() + "…"
    return block
