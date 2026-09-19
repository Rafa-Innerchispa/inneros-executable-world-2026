from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from .models import ActionProposal, ActionResult, ApprovalDecision


class GuardianIncidentLike(Protocol):
    event_id: str

    def as_voiceops_context(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class SyntheticGuardianIncident:
    """Synthetic projection of a Physical Guardian normalized event."""

    event_id: str = field(default_factory=lambda: f"evt-demo-{uuid4().hex[:10]}")
    source_id: str = "camera-north-01"
    event_type: str = "camera_offline"
    severity: str = "high"
    zone_id: str = "north-access"
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_refs: tuple[str, ...] = ("synthetic://guardian/camera-north-01/offline",)

    def as_voiceops_context(self) -> dict[str, Any]:
        return {
            "contract_owner": "Rafa-Innerchispa/inneros-physical-guardian",
            "contract_projection": "NormalizedEvent",
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "zone_id": self.zone_id,
            "occurred_at": self.occurred_at,
            "evidence_refs": list(self.evidence_refs),
            "source": "synthetic_guardian_adapter",
            "production_event": False,
            "action_candidate": {
                "action_type": "create_work_order",
                "summary": (
                    f"Physical Guardian reported {self.event_type} for {self.source_id} "
                    f"in {self.zone_id}. Create a priority technical work order for inspection."
                ),
                "requires_approval": True,
                "payload": {
                    "source_event_id": self.event_id,
                    "source_id": self.source_id,
                    "zone_id": self.zone_id,
                    "priority": "high",
                    "reason_code": "GUARDIAN_CAMERA_OFFLINE",
                    "evidence_refs": list(self.evidence_refs),
                },
            },
        }


@dataclass(slots=True)
class NormalizedGuardianIncident:
    """Sanitized downstream projection of a real Guardian NormalizedEvent.

    VoiceOps never receives camera credentials, RTSP URLs or raw frames. It only
    receives the event contract and a bounded action candidate.
    """

    event_id: str
    source_id: str
    event_type: str
    severity: str
    occurred_at: str
    tenant_id: str = ""
    site_id: str = ""
    zone_id: str = ""
    confidence: float | None = None
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "NormalizedGuardianIncident":
        required = ("event_id", "source_id", "event_type", "severity", "occurred_at")
        missing = [key for key in required if not str(payload.get(key) or "").strip()]
        if missing:
            raise ValueError(f"Guardian NormalizedEvent missing fields: {missing}")
        rendered = repr(payload).lower()
        forbidden = ("rtsp://", "password", "credential", "authorization", "base64")
        if any(term in rendered for term in forbidden):
            raise ValueError("Guardian event contains forbidden private transport material")
        confidence_raw = payload.get("confidence")
        confidence = float(confidence_raw) if confidence_raw is not None else None
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError("Guardian confidence must be between 0 and 1")
        attrs = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {}
        evidence_refs = payload.get("evidence_refs") or []
        if not isinstance(evidence_refs, (list, tuple)):
            raise ValueError("Guardian evidence_refs must be a list")
        return cls(
            event_id=str(payload["event_id"]),
            source_id=str(payload["source_id"]),
            event_type=str(payload["event_type"]),
            severity=str(payload["severity"]).lower(),
            occurred_at=str(payload["occurred_at"]),
            tenant_id=str(payload.get("tenant_id") or ""),
            site_id=str(payload.get("site_id") or ""),
            zone_id=str(payload.get("zone_id") or attrs.get("zone_id") or attrs.get("zone_name") or ""),
            confidence=confidence,
            evidence_refs=tuple(str(item)[:240] for item in evidence_refs[:20]),
        )

    def as_voiceops_context(self) -> dict[str, Any]:
        priority = "high" if self.severity in {"high", "critical"} else "normal"
        zone = self.zone_id or "configured area"
        return {
            "contract_owner": "Rafa-Innerchispa/inneros-physical-guardian",
            "contract_projection": "NormalizedEvent",
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "zone_id": self.zone_id,
            "occurred_at": self.occurred_at,
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "source": "physical_guardian_normalized_event",
            "production_event": True,
            "action_candidate": {
                "action_type": "create_work_order",
                "summary": (
                    f"Physical Guardian reported {self.event_type} from {self.source_id} in {zone}. "
                    "Create a bounded technical work order for human follow-up."
                ),
                "requires_approval": True,
                "payload": {
                    "source_event_id": self.event_id,
                    "source_id": self.source_id,
                    "zone_id": self.zone_id,
                    "tenant_id": self.tenant_id,
                    "site_id": self.site_id,
                    "priority": priority,
                    "reason_code": "GUARDIAN_EVENT_REQUIRES_FOLLOWUP",
                    "evidence_refs": list(self.evidence_refs),
                },
            },
        }


class SyntheticServiceWorkflow:
    """Governed demo execution over Guardian input and synthetic Service Ops.

    Guardian may be synthetic or a real normalized event, but execution remains
    intentionally synthetic/no-production-write until a separate production
    policy explicitly enables a real Service Operations adapter.
    """

    def __init__(self, incident: GuardianIncidentLike | None = None) -> None:
        self.incident: GuardianIncidentLike = incident or SyntheticGuardianIncident()
        self.created_orders: list[dict[str, Any]] = []

    def bind_normalized_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.created_orders:
            raise ValueError("cannot replace Guardian event after an action was created")
        self.incident = NormalizedGuardianIncident.from_payload(payload)
        return self.incident.as_voiceops_context()

    def inspect(self) -> dict[str, Any]:
        return self.incident.as_voiceops_context()

    def propose(self, facts: dict[str, Any]) -> ActionProposal:
        candidate = facts.get("action_candidate")
        if not isinstance(candidate, dict):
            return ActionProposal(
                action_type="no_action",
                summary="Physical Guardian supplied no consequential action candidate.",
                requires_approval=False,
                payload={
                    "source_event_id": facts.get("event_id"),
                    "reason_code": "NO_GUARDIAN_ACTION_CANDIDATE",
                },
            )

        required = {"action_type", "summary", "requires_approval", "payload"}
        missing = required.difference(candidate)
        if missing:
            raise ValueError(f"Guardian action candidate missing fields: {sorted(missing)}")

        return ActionProposal(
            action_type=str(candidate["action_type"]),
            summary=str(candidate["summary"]),
            requires_approval=bool(candidate["requires_approval"]),
            payload=dict(candidate["payload"]),
        )

    def execute(self, proposal: ActionProposal, approval: ApprovalDecision | None) -> ActionResult:
        if proposal.requires_approval and (approval is None or not approval.approved):
            raise PermissionError("consequential action blocked: explicit approval required")

        if proposal.action_type == "no_action":
            return ActionResult(
                action_id=f"noop-{uuid4().hex[:10]}",
                action_type="no_action",
                status="created",
                details={"executed": False, "source": "synthetic_service_ops_adapter"},
            )

        order_id = f"WO-DEMO-{uuid4().hex[:8].upper()}"
        order = {
            "work_order_id": order_id,
            **proposal.payload,
            "environment": "synthetic_demo",
            "contract_owner": "InnerOps Service Operations",
        }
        self.created_orders.append(order)
        return ActionResult(
            action_id=order_id,
            action_type=proposal.action_type,
            status="created",
            details=order,
        )
