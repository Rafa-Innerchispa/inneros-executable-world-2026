from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TranscriptTurn:
    session_id: str
    turn_id: str
    transcript: str
    end_of_turn: bool
    received_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ActionProposal:
    action_type: str
    summary: str
    requires_approval: bool
    payload: dict[str, Any]


@dataclass(slots=True)
class ApprovalDecision:
    approved: bool
    phrase: str
    reason: str
    decided_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ActionResult:
    action_id: str
    action_type: str
    status: Literal["created", "blocked", "failed"]
    details: dict[str, Any]
    completed_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class HTRMetric:
    manual_seconds: float
    human_active_seconds: float
    saved_seconds: float
    classification: Literal["MEASURED", "ESTIMATED"]
    evidence_basis: str


@dataclass(slots=True)
class EvidenceEvent:
    kind: str
    data: dict[str, Any]
    at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class EvidenceBundle:
    correlation_id: str
    session_id: str
    turns: list[TranscriptTurn] = field(default_factory=list)
    proposal: ActionProposal | None = None
    approval: ApprovalDecision | None = None
    action_result: ActionResult | None = None
    htr: HTRMetric | None = None
    events: list[EvidenceEvent] = field(default_factory=list)

    def add_event(self, kind: str, **data: Any) -> None:
        self.events.append(EvidenceEvent(kind=kind, data=data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
