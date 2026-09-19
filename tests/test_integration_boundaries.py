from voiceops.workflows import SyntheticGuardianIncident, SyntheticServiceWorkflow


def test_voiceops_consumes_normalized_guardian_incident_not_raw_camera_state() -> None:
    workflow = SyntheticServiceWorkflow(SyntheticGuardianIncident())
    facts = workflow.inspect()

    assert facts["contract_owner"] == "Rafa-Innerchispa/inneros-physical-guardian"
    assert facts["contract_projection"] == "NormalizedEvent"
    assert facts["event_type"] == "camera_offline"
    assert "status" not in facts
    assert "camera_online" not in facts
    assert facts["action_candidate"]["action_type"] == "create_work_order"


def test_voiceops_does_not_infer_physical_action_when_guardian_candidate_missing() -> None:
    workflow = SyntheticServiceWorkflow()
    facts = workflow.inspect()
    facts.pop("action_candidate")

    proposal = workflow.propose(facts)

    assert proposal.action_type == "no_action"
    assert proposal.requires_approval is False
    assert proposal.payload["reason_code"] == "NO_GUARDIAN_ACTION_CANDIDATE"
