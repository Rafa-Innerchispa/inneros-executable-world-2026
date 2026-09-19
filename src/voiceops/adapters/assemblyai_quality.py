from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.request import Request, urlopen


LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
DEFAULT_QA_MODEL = "google/gemini-2.5-flash-lite"


def build_post_session_transcript_payload(audio_url: str, *, language_code: str = "es") -> dict[str, Any]:
    """Build a privacy-oriented AssemblyAI archival analysis request.

    This is intentionally post-session. Live Voice Agent / Streaming remains the
    realtime path. Raw PII is not required for public VoiceOps evidence.
    """
    if not audio_url.strip():
        raise ValueError("audio_url must not be empty")
    return {
        "audio_url": audio_url,
        "speech_models": ["universal-3-pro", "universal-2"],
        "language_code": language_code,
        "redact_pii": True,
        "redact_pii_policies": [
            "person_name",
            "email_address",
            "phone_number",
            "location",
            "account_number",
        ],
        "redact_pii_sub": "entity_name",
        "entity_detection": True,
        "content_safety": True,
        # Sentiment Analysis is deliberately not enabled for the Spanish demo.
    }


class AssemblyAIQualityEvaluator:
    """Optional LLM Gateway critic over minimized VoiceOps evidence.

    The evaluator is read-only and post-action. It cannot change approval,
    execute tools, or alter the captured evidence bundle.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_QA_MODEL,
        endpoint: str = LLM_GATEWAY_URL,
        timeout_seconds: float = 15.0,
        post_json: Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        self.model = model
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._post_json = post_json or _post_json

    def evaluate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is required for LLM Gateway QA")
        minimized = minimize_evidence_for_qa(evidence)
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a read-only QA critic for a governed voice agent. "
                        "Score only the evidence provided. Return strict JSON with keys "
                        "task_success, approval_adherence, evidence_completeness, and note. "
                        "The three scores must be integers 1-5. Do not invent missing evidence."
                    ),
                },
                {"role": "user", "content": json.dumps(minimized, ensure_ascii=False)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "voiceops_quality_score",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "task_success": {"type": "integer", "minimum": 1, "maximum": 5},
                            "approval_adherence": {"type": "integer", "minimum": 1, "maximum": 5},
                            "evidence_completeness": {"type": "integer", "minimum": 1, "maximum": 5},
                            "note": {"type": "string"},
                        },
                        "required": ["task_success", "approval_adherence", "evidence_completeness", "note"],
                        "additionalProperties": False,
                    },
                },
            },
            "post_processing_steps": [{"type": "json-repair"}],
        }
        headers = {"authorization": self.api_key, "content-type": "application/json"}
        raw = self._post_json(self.endpoint, headers, payload, self.timeout_seconds)
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM Gateway response missing choices[0].message.content") from exc
        if isinstance(content, dict):
            result = content
        elif isinstance(content, str):
            result = json.loads(content)
        else:
            raise ValueError("LLM Gateway QA content must be JSON")
        _validate_quality_score(result)
        return {
            **result,
            "provider": "assemblyai_llm_gateway",
            "model": self.model,
            "authority": "read_only_critic",
        }


def minimize_evidence_for_qa(evidence: dict[str, Any]) -> dict[str, Any]:
    """Remove transcript text and arbitrary payloads before optional cloud QA."""
    proposal = evidence.get("proposal") or {}
    approval = evidence.get("approval") or {}
    action = evidence.get("action_result") or {}
    htr = evidence.get("htr") or {}
    events = evidence.get("events") or []
    return {
        "correlation_id": evidence.get("correlation_id"),
        "turn_count": len(evidence.get("turns") or []),
        "proposal": {
            "action_type": proposal.get("action_type"),
            "requires_approval": proposal.get("requires_approval"),
        },
        "approval": {
            "approved": approval.get("approved"),
            "reason": approval.get("reason"),
        },
        "action": {
            "action_type": action.get("action_type"),
            "status": action.get("status"),
        },
        "htr": {
            "classification": htr.get("classification"),
            "saved_seconds": htr.get("saved_seconds"),
        },
        "event_kinds": [item.get("kind") for item in events if isinstance(item, dict)],
        "raw_transcript_included": False,
        "arbitrary_action_payload_included": False,
    }


def _validate_quality_score(result: Any) -> None:
    if not isinstance(result, dict):
        raise ValueError("quality score must be an object")
    for key in ("task_success", "approval_adherence", "evidence_completeness"):
        value = result.get(key)
        if not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"{key} must be an integer between 1 and 5")
    if not isinstance(result.get("note"), str):
        raise ValueError("note must be a string")


def _post_json(
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed AssemblyAI endpoint
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("LLM Gateway response must be an object")
    return body
