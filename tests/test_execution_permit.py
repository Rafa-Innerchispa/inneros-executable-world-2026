from __future__ import annotations

from dataclasses import asdict

from voiceops.execution_permit import VoiceExecutionPermitManager
from voiceops.gateway import VoiceGateway
from voiceops.workflows import NormalizedGuardianIncident, SyntheticServiceWorkflow


def guardian_event(event_id: str = "evt_guardian_123") -> dict[str, object]:
    return {
        "event_id": event_id,
        "source_id": "camera-2",
        "event_type": "zone.person.prolonged",
        "severity": "high",
        "occurred_at": "2026-09-11T12:00:00+00:00",
        "tenant_id": "tenant-demo",
        "site_id": "site-demo",
        "zone_id": "Puerta",
        "confidence": 0.94,
        "evidence_refs": ["evidence://guardian/evt_guardian_123"],
    }


def test_normalized_guardian_event_is_bound_without_private_transport_material() -> None:
    workflow = SyntheticServiceWorkflow()
    bound = workflow.bind_normalized_event(guardian_event())
    assert bound["source"] == "physical_guardian_normalized_event"
    assert bound["event_id"] == "evt_guardian_123"
    assert bound["action_candidate"]["payload"]["source_event_id"] == "evt_guardian_123"
    assert bound["production_event"] is True


def test_normalized_guardian_event_rejects_private_transport_material() -> None:
    payload = guardian_event()
    payload["rtsp_uri"] = "rtsp://private.example/camera"
    try:
        NormalizedGuardianIncident.from_payload(payload)
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("private transport material must be rejected")


def test_execution_permit_is_single_use_and_state_bound() -> None:
    manager = VoiceExecutionPermitManager(ttl_seconds=30, signing_key=b"x" * 32)
    proposal = {"action_type": "create_work_order", "payload": {"source_event_id": "evt_1"}}
    state = {"event_id": "evt_1", "severity": "high"}
    permit = manager.issue(
        session_id="sess_1",
        source_event_id="evt_1",
        action_type="create_work_order",
        approval_transcript="Sí, autorizo.",
        proposal=proposal,
        state_snapshot=state,
        now=100.0,
    )
    ok, reason, _ = manager.consume(
        permit.permit_id,
        session_id="sess_1",
        source_event_id="evt_1",
        action_type="create_work_order",
        approval_transcript="Sí, autorizo.",
        proposal=proposal,
        state_snapshot=state,
        now=101.0,
    )
    assert ok is True
    assert reason == "permit_consumed"
    second_ok, second_reason, _ = manager.consume(
        permit.permit_id,
        session_id="sess_1",
        source_event_id="evt_1",
        action_type="create_work_order",
        approval_transcript="Sí, autorizo.",
        proposal=proposal,
        state_snapshot=state,
        now=102.0,
    )
    assert second_ok is False
    assert second_reason == "permit_already_used"


def test_execution_permit_rejects_changed_state() -> None:
    manager = VoiceExecutionPermitManager(ttl_seconds=30, signing_key=b"y" * 32)
    proposal = {"action_type": "create_work_order", "payload": {"source_event_id": "evt_1"}}
    state = {"event_id": "evt_1", "severity": "high"}
    permit = manager.issue(
        session_id="sess_1",
        source_event_id="evt_1",
        action_type="create_work_order",
        approval_transcript="Sí, autorizo.",
        proposal=proposal,
        state_snapshot=state,
        now=100.0,
    )
    ok, reason, _ = manager.consume(
        permit.permit_id,
        session_id="sess_1",
        source_event_id="evt_1",
        action_type="create_work_order",
        approval_transcript="Sí, autorizo.",
        proposal=proposal,
        state_snapshot={"event_id": "evt_1", "severity": "critical"},
        now=101.0,
    )
    assert ok is False
    assert reason == "permit_binding_mismatch:state_hash"


def test_gateway_real_guardian_event_requires_explicit_approval_and_records_permit() -> None:
    gateway = VoiceGateway()
    gateway.bind_guardian_event(guardian_event())
    proposed = gateway.process_final_transcript("Revisa esta incidencia y abre una orden si corresponde.")
    assert proposed["status"] == "approval_required"
    assert proposed["source_event_id"] == "evt_guardian_123"
    blocked = gateway.process_final_transcript("Si crees que hace falta.")
    assert blocked["status"] == "blocked"
    completed = gateway.process_final_transcript("Sí, autorizo.")
    assert completed["status"] == "completed"
    assert completed["source_event_id"] == "evt_guardian_123"
    assert completed["permit_single_use"] is True
    assert completed["action_id"].startswith("WO-DEMO-")
    kinds = [event.kind for event in gateway.evidence.events]
    assert "guardian_event_bound" in kinds
    assert "voice_execution_permit_issued" in kinds
    assert "voice_execution_permit_consumed" in kinds
    assert "action_executed" in kinds
    permit_event = next(event for event in gateway.evidence.events if event.kind == "voice_execution_permit_issued")
    assert permit_event.data["signature_exposed"] is False
