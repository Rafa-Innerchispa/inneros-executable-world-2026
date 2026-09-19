from __future__ import annotations

import time
from dataclasses import asdict
from uuid import uuid4

from .approval import ExplicitApprovalGate
from .audit import build_htr
from .execution_permit import VoiceExecutionPermitManager
from .models import EvidenceBundle, TranscriptTurn
from .reasoning import DeterministicDemoReasoner, Reasoner
from .workflows import SyntheticServiceWorkflow


class VoiceGateway:
    """Session state machine for governed voice execution."""

    def __init__(
        self,
        workflow: SyntheticServiceWorkflow | None = None,
        reasoner: Reasoner | None = None,
        *,
        manual_baseline_seconds: float = 720.0,
        baseline_classification: str = "ESTIMATED",
        permit_ttl_seconds: float = 45.0,
    ) -> None:
        self.workflow = workflow or SyntheticServiceWorkflow()
        self.reasoner = reasoner or DeterministicDemoReasoner(self.workflow)
        self.approval_gate = ExplicitApprovalGate()
        self.permits = VoiceExecutionPermitManager(ttl_seconds=permit_ttl_seconds)
        self.session_id = f"sess_{uuid4().hex[:12]}"
        self.correlation_id = f"corr_{uuid4().hex[:16]}"
        self._turn_number = 0
        self._started = time.monotonic()
        self._pending_proposal = None
        self._pending_state_snapshot: dict[str, object] | None = None
        self._manual_baseline_seconds = manual_baseline_seconds
        self._baseline_classification = baseline_classification
        self.evidence = EvidenceBundle(
            correlation_id=self.correlation_id,
            session_id=self.session_id,
        )
        self.evidence.add_event("session_started", mode="synthetic_demo", production_writes=False)

    @property
    def pending_approval(self) -> bool:
        return self._pending_proposal is not None

    def bind_guardian_event(self, payload: dict[str, object]) -> dict[str, object]:
        """Bind a sanitized Guardian NormalizedEvent before governed execution."""
        if self._pending_proposal is not None:
            raise ValueError("cannot replace Guardian event while approval is pending")
        if self.evidence.action_result is not None:
            raise ValueError("cannot replace Guardian event after action completion")
        bound = self.workflow.bind_normalized_event(dict(payload))
        self.evidence.add_event(
            "guardian_event_bound",
            event_id=bound.get("event_id"),
            event_type=bound.get("event_type"),
            source_id=bound.get("source_id"),
            contract_projection="NormalizedEvent",
            production_event=True,
            raw_media_included=False,
        )
        return bound

    def _new_turn(self, transcript: str) -> TranscriptTurn:
        self._turn_number += 1
        turn = TranscriptTurn(
            session_id=self.session_id,
            turn_id=f"turn_{self._turn_number:04d}",
            transcript=transcript,
            end_of_turn=True,
        )
        self.evidence.turns.append(turn)
        self.evidence.add_event(
            "transcript_final",
            turn_id=turn.turn_id,
            transcript=turn.transcript,
        )
        return turn

    def process_final_transcript(self, transcript: str) -> dict[str, object]:
        turn = self._new_turn(transcript)

        if self._pending_proposal is not None:
            approval = self.approval_gate.decide(transcript)
            self.evidence.approval = approval
            self.evidence.add_event(
                "approval_decision",
                turn_id=turn.turn_id,
                approved=approval.approved,
                reason=approval.reason,
            )
            if not approval.approved:
                return {
                    "status": "blocked",
                    "requires_approval": True,
                    "reason": approval.reason,
                    "message": "Action not executed. Explicit authorization is still required.",
                }

            proposal = self._pending_proposal
            state_snapshot = self._pending_state_snapshot or self.workflow.inspect()
            source_event_id = str(proposal.payload.get("source_event_id") or state_snapshot.get("event_id") or "")
            permit = self.permits.issue(
                session_id=self.session_id,
                source_event_id=source_event_id,
                action_type=proposal.action_type,
                approval_transcript=transcript,
                proposal=asdict(proposal),
                state_snapshot=state_snapshot,
            )
            self.evidence.add_event(
                "voice_execution_permit_issued",
                permit_id=permit.permit_id,
                source_event_id=permit.source_event_id,
                action_type=permit.action_type,
                proposal_hash=permit.proposal_hash,
                state_hash=permit.state_hash,
                transcript_hash=permit.transcript_hash,
                expires_at=permit.expires_at,
                signature_exposed=False,
            )
            allowed, permit_reason, consumed = self.permits.consume(
                permit.permit_id,
                session_id=self.session_id,
                source_event_id=source_event_id,
                action_type=proposal.action_type,
                approval_transcript=transcript,
                proposal=asdict(proposal),
                state_snapshot=state_snapshot,
            )
            self.evidence.add_event(
                "voice_execution_permit_consumed",
                permit_id=permit.permit_id,
                allowed=allowed,
                reason=permit_reason,
                single_use=True,
            )
            if not allowed:
                return {
                    "status": "blocked",
                    "requires_approval": True,
                    "reason": permit_reason,
                    "message": "Action not executed because the execution permit was invalid.",
                }

            result = self.workflow.execute(proposal, approval)
            self.evidence.action_result = result
            self.evidence.add_event(
                "action_executed",
                action_id=result.action_id,
                action_type=result.action_type,
                environment="synthetic_demo",
                permit_id=consumed.permit_id if consumed else permit.permit_id,
                source_event_id=source_event_id,
            )
            elapsed = time.monotonic() - self._started
            basis = (
                "VoiceOps active time measured in-process; manual baseline measured externally."
                if self._baseline_classification == "MEASURED"
                else "VoiceOps active time measured in-process; manual baseline is an explicit demo estimate."
            )
            self.evidence.htr = build_htr(
                manual_seconds=self._manual_baseline_seconds,
                human_active_seconds=elapsed,
                classification=self._baseline_classification,
                evidence_basis=basis,
            )
            self._pending_proposal = None
            self._pending_state_snapshot = None
            return {
                "status": "completed",
                "requires_approval": False,
                "action_id": result.action_id,
                "permit_id": permit.permit_id,
                "permit_single_use": True,
                "source_event_id": source_event_id,
                "message": f"Synthetic work order {result.action_id} created.",
                "htr_saved_seconds": self.evidence.htr.saved_seconds,
                "htr_classification": self.evidence.htr.classification,
            }

        facts = self.workflow.inspect()
        self.evidence.add_event("state_snapshot", snapshot=facts)
        reasoning = self.reasoner.propose(facts)
        proposal = reasoning.proposal
        self.evidence.proposal = proposal
        self.evidence.add_event("reasoning_route", route=reasoning.route)
        self.evidence.add_event(
            "action_proposed",
            action_type=proposal.action_type,
            requires_approval=proposal.requires_approval,
            payload=proposal.payload,
        )

        if proposal.requires_approval:
            self._pending_proposal = proposal
            self._pending_state_snapshot = facts
            return {
                "status": "approval_required",
                "requires_approval": True,
                "source_event_id": str(proposal.payload.get("source_event_id") or facts.get("event_id") or ""),
                "message": proposal.summary + " Say an explicit authorization to proceed.",
                "proposal": proposal.summary,
            }

        result = self.workflow.execute(proposal, None)
        self.evidence.action_result = result
        self.evidence.add_event("action_completed_without_consequence", action_id=result.action_id)
        return {
            "status": "completed",
            "requires_approval": False,
            "action_id": result.action_id,
            "message": proposal.summary,
        }
