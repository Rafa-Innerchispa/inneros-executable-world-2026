from __future__ import annotations

from typing import Any

DEFAULT_SESSION_ID = "executable-world-session"


def mirror_voiceops_event(
    event_type: str,
    data: dict[str, Any],
    *,
    session_id: str = DEFAULT_SESSION_ID,
) -> dict[str, Any]:
    """Legacy name — routes to sponsor evidence (local-first, optional VeloDB/AgentX)."""
    from .sponsor_evidence import record_evidence_event

    return record_evidence_event(event_type, data, session_id=session_id)


def mirror_governed_action(
    proposal_id: str,
    permit_id: str,
    action_type: str,
    result: str,
) -> dict[str, Any]:
    from .sponsor_evidence import record_governed_action

    return record_governed_action(proposal_id, permit_id, action_type, result)
