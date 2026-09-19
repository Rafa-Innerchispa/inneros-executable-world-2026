from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .models import ActionProposal
from .workflows import SyntheticServiceWorkflow


@dataclass(slots=True)
class ReasoningResult:
    proposal: ActionProposal
    route: dict[str, Any]


class Reasoner(Protocol):
    def propose(self, facts: dict[str, Any]) -> ReasoningResult: ...


class DeterministicDemoReasoner:
    """Offline-safe reasoner used by tests and the public synthetic demo."""

    def __init__(self, workflow: SyntheticServiceWorkflow) -> None:
        self.workflow = workflow

    def propose(self, facts: dict[str, Any]) -> ReasoningResult:
        return ReasoningResult(
            proposal=self.workflow.propose(facts),
            route={
                "policy": "local_first",
                "provider": "deterministic_demo",
                "model": None,
                "external_fallback": False,
                "truth": "SYNTHETIC",
            },
        )


class CallableInnerOSReasoner:
    """Adapter boundary for Resource Fabric / MCP local reasoning.

    The injected callable is expected to be the existing InnerOS routing layer,
    not a second orchestration stack living in this hackathon repository.
    """

    def __init__(self, reason_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.reason_fn = reason_fn

    def propose(self, facts: dict[str, Any]) -> ReasoningResult:
        raw = self.reason_fn(facts)
        proposal_raw = raw.get("proposal") or {}
        route = raw.get("route") or {}
        required = {"action_type", "summary", "requires_approval", "payload"}
        missing = required.difference(proposal_raw)
        if missing:
            raise ValueError(f"InnerOS reasoning response missing fields: {sorted(missing)}")
        if route.get("policy") != "local_first":
            raise ValueError("InnerOS reasoning response must expose local_first routing policy")
        return ReasoningResult(
            proposal=ActionProposal(
                action_type=str(proposal_raw["action_type"]),
                summary=str(proposal_raw["summary"]),
                requires_approval=bool(proposal_raw["requires_approval"]),
                payload=dict(proposal_raw["payload"]),
            ),
            route=dict(route),
        )
