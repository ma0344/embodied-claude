"""Shared store singletons for Presence UI (direct DB / file reads, no MCP spawn)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from boundary_mcp.policy import load_policy
from boundary_mcp.store import BoundaryStore
from interaction_orchestrator_mcp.store import InteractionOrchestratorStore
from joint_attention_mcp.store import JointAttentionStore
from relationship_mcp.store import RelationshipStore
from self_narrative_mcp.store import SelfNarrativeStore
from social_core import SocialDB
from social_core.events import EventStore
from social_state_mcp.store import SocialStateStore


@dataclass(slots=True)
class PresenceStores:
    db: SocialDB
    events: EventStore
    social_state: SocialStateStore
    relationship: RelationshipStore
    joint_attention: JointAttentionStore
    boundary: BoundaryStore
    self_narrative: SelfNarrativeStore
    orchestrator: InteractionOrchestratorStore
    policy_timezone: str


_local = threading.local()


def get_stores() -> PresenceStores:
    """Per-thread store bundle (FastAPI runs sync routes in a worker thread pool)."""
    stores = getattr(_local, "stores", None)
    if stores is not None:
        return stores

    db = SocialDB()
    policy = load_policy()
    stores = PresenceStores(
        db=db,
        events=EventStore(db=db),
        social_state=SocialStateStore(
            db=db,
            quiet_hours_windows=list(policy.global_policy.quiet_hours),
            policy_timezone=policy.global_policy.timezone,
        ),
        relationship=RelationshipStore(db=db),
        joint_attention=JointAttentionStore(db=db),
        boundary=BoundaryStore(db=db),
        self_narrative=SelfNarrativeStore(db=db),
        orchestrator=InteractionOrchestratorStore(db=db),
        policy_timezone=policy.global_policy.timezone,
    )
    _local.stores = stores
    return stores
