from voiceops.adapters.assemblyai_quality import (
    AssemblyAIQualityEvaluator,
    build_post_session_transcript_payload,
    minimize_evidence_for_qa,
)
from voiceops.gateway import VoiceGateway


def _completed_evidence() -> dict[str, object]:
    gateway = VoiceGateway()
    gateway.process_final_transcript("Revisa la incidencia")
    gateway.process_final_transcript("Si, autorizo")
    return gateway.evidence.to_dict()


def test_post_session_payload_enables_privacy_guardrails_for_spanish() -> None:
    payload = build_post_session_transcript_payload("https://example.invalid/demo.wav", language_code="es")
    assert payload["redact_pii"] is True
    assert payload["redact_pii_sub"] == "entity_name"
    assert payload["entity_detection"] is True
    assert payload["content_safety"] is True
    assert "sentiment_analysis" not in payload


def test_quality_evidence_minimization_excludes_transcript_and_payload() -> None:
    minimized = minimize_evidence_for_qa(_completed_evidence())
    assert minimized["raw_transcript_included"] is False
    assert minimized["arbitrary_action_payload_included"] is False
    text = str(minimized)
    assert "Revisa la incidencia" not in text
    assert "Si, autorizo" not in text
    assert "evidence_refs" not in text


def test_llm_gateway_evaluator_is_read_only_structured_critic() -> None:
    observed: dict[str, object] = {}

    def fake_post(endpoint: str, headers: dict[str, str], payload: dict[str, object], timeout: float) -> dict[str, object]:
        observed.update(endpoint=endpoint, headers=headers, payload=payload, timeout=timeout)
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"task_success":5,"approval_adherence":5,"evidence_completeness":5,"note":"Governed flow completed."}'
                    }
                }
            ]
        }

    evaluator = AssemblyAIQualityEvaluator(api_key="test-key", post_json=fake_post)
    result = evaluator.evaluate(_completed_evidence())
    assert result["task_success"] == 5
    assert result["approval_adherence"] == 5
    assert result["evidence_completeness"] == 5
    assert result["authority"] == "read_only_critic"
    payload = observed["payload"]
    assert payload["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert payload["post_processing_steps"] == [{"type": "json-repair"}]  # type: ignore[index]


def test_llm_gateway_requires_server_side_credential() -> None:
    evaluator = AssemblyAIQualityEvaluator(api_key=None)
    evaluator.api_key = None
    try:
        evaluator.evaluate(_completed_evidence())
    except RuntimeError as exc:
        assert "ASSEMBLYAI_API_KEY" in str(exc)
    else:
        raise AssertionError("LLM Gateway must fail without a server-side credential")
