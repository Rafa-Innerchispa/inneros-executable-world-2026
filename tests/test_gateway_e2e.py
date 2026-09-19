from voiceops.gateway import VoiceGateway
from voiceops.workflows import SyntheticServiceWorkflow


def test_governed_synthetic_e2e_creates_work_order_after_approval() -> None:
    workflow = SyntheticServiceWorkflow()
    gateway = VoiceGateway(workflow=workflow, manual_baseline_seconds=720)

    first = gateway.process_final_transcript(
        "Ralphi, tenemos una alarma en el acceso norte. Revisa qué ocurre y abre una orden si corresponde."
    )
    assert first["status"] == "approval_required"
    assert gateway.pending_approval is True
    assert workflow.created_orders == []

    second = gateway.process_final_transcript("Sí, autorizo.")
    assert second["status"] == "completed"
    assert str(second["action_id"]).startswith("WO-DEMO-")
    assert len(workflow.created_orders) == 1
    assert gateway.evidence.action_result is not None
    assert gateway.evidence.htr is not None
    assert gateway.evidence.htr.classification == "ESTIMATED"


def test_consequential_action_never_executes_on_ambiguous_reply() -> None:
    workflow = SyntheticServiceWorkflow()
    gateway = VoiceGateway(workflow=workflow)
    gateway.process_final_transcript("Revisa la alarma y abre una orden si corresponde")

    result = gateway.process_final_transcript("si crees que hace falta")
    assert result["status"] == "blocked"
    assert workflow.created_orders == []
    assert gateway.pending_approval is True


def test_evidence_captures_guardian_snapshot_not_live_refetch() -> None:
    gateway = VoiceGateway()
    gateway.process_final_transcript("Revisa la alarma")
    snapshots = [event for event in gateway.evidence.events if event.kind == "state_snapshot"]
    assert len(snapshots) == 1
    snapshot = snapshots[0].data["snapshot"]
    assert snapshot["source"] == "synthetic_guardian_adapter"
    assert snapshot["contract_projection"] == "NormalizedEvent"
    assert snapshot["contract_owner"] == "Rafa-Innerchispa/inneros-physical-guardian"
