from voiceops.adapters.local_amd import LocalAMDReasoner
from voiceops.workflows import SyntheticServiceWorkflow


def test_local_amd_reasoner_preserves_guardian_action_boundary() -> None:
    workflow = SyntheticServiceWorkflow()
    facts = workflow.inspect()
    candidate = facts["action_candidate"]

    def fake_post(endpoint: str, payload: dict, timeout: float) -> dict:
        assert endpoint.endswith("/v1/chat/completions")
        assert payload["model"] == "test-model"
        assert timeout == 5.0
        return {
            "choices": [
                {"message": {"content": '{"summary":"AMD reviewed the Guardian event and recommends the bounded work order."}'}}
            ]
        }

    reasoner = LocalAMDReasoner(
        endpoint="http://127.0.0.1:18000/v1/chat/completions",
        model="test-model",
        timeout_seconds=5.0,
        post_json=fake_post,
    )
    result = reasoner.propose(facts)

    assert result.route["provider"] == "local-amd-5"
    assert result.route["truth"] == "LIVE_MODEL_RESPONSE"
    assert result.route["external_fallback"] is False
    assert result.proposal.action_type == candidate["action_type"]
    assert result.proposal.requires_approval == candidate["requires_approval"]
    assert result.proposal.payload == candidate["payload"]
    assert "AMD reviewed" in result.proposal.summary


def test_local_amd_reasoner_does_not_call_model_without_guardian_candidate() -> None:
    called = False

    def fail_post(endpoint: str, payload: dict, timeout: float) -> dict:
        nonlocal called
        called = True
        raise AssertionError("model must not run without a Guardian action candidate")

    reasoner = LocalAMDReasoner(post_json=fail_post)
    result = reasoner.propose({"event_id": "evt-1"})
    assert called is False
    assert result.proposal.action_type == "no_action"
    assert result.proposal.requires_approval is False
    assert result.route["truth"] == "LIVE_NO_MODEL_CALL"


def test_local_amd_reasoner_falls_back_to_guardian_summary_on_non_json_text() -> None:
    workflow = SyntheticServiceWorkflow()
    facts = workflow.inspect()
    candidate = facts["action_candidate"]

    reasoner = LocalAMDReasoner(
        post_json=lambda endpoint, payload, timeout: {
            "choices": [{"message": {"content": "not-json"}}]
        }
    )
    result = reasoner.propose(facts)
    assert result.proposal.summary == candidate["summary"]
    assert result.proposal.payload == candidate["payload"]
