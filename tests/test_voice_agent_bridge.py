from __future__ import annotations

import json

from voiceops.webapp import DemoSessionStore, mint_voice_agent_token


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_voice_agent_token_is_minted_server_side_with_bounded_ttl() -> None:
    observed: dict[str, object] = {}

    def fake_open(request: object, timeout: int) -> FakeResponse:
        observed["request"] = request
        observed["timeout"] = timeout
        return FakeResponse({"token": "single-use-test-token"})

    result = mint_voice_agent_token("server-side-test-key", expires_in_seconds=120, opener=fake_open)
    assert result == {"token": "single-use-test-token", "expires_in_seconds": 120}
    request = observed["request"]
    assert "expires_in_seconds=120" in request.full_url  # type: ignore[attr-defined]
    assert request.get_header("Authorization") == "Bearer server-side-test-key"  # type: ignore[attr-defined]


def test_voice_agent_token_rejects_invalid_ttl() -> None:
    try:
        mint_voice_agent_token("test", expires_in_seconds=601)
    except ValueError as exc:
        assert "between 1 and 600" in str(exc)
    else:
        raise AssertionError("TTL above provider maximum must be rejected")


def test_tool_inspect_never_executes_consequential_action() -> None:
    store = DemoSessionStore()
    result = store.tool_inspect("Revisa la incidencia del acceso norte")
    assert result["status"] == "approval_required"
    assert result["requires_approval"] is True
    assert result["production_writes"] is False
    assert result["proposal"]["action_type"] == "create_work_order"  # type: ignore[index]
    assert store.snapshot()["action"] is None


def test_tool_approval_uses_inneros_fail_closed_gate() -> None:
    store = DemoSessionStore()
    store.tool_inspect("Revisa la incidencia")
    blocked = store.tool_approve("Si crees que hace falta")
    assert blocked["status"] == "blocked"
    assert blocked["approval"]["approved"] is False  # type: ignore[index]
    assert blocked["action"] is None

    completed = store.tool_approve("Si, autorizo")
    assert completed["status"] == "completed"
    assert completed["approval"]["approved"] is True  # type: ignore[index]
    assert completed["action"]["status"] == "created"  # type: ignore[index]


def test_approval_tool_rejects_when_nothing_is_pending() -> None:
    store = DemoSessionStore()
    try:
        store.tool_approve("Si, autorizo")
    except ValueError as exc:
        assert "no action is awaiting approval" in str(exc)
    else:
        raise AssertionError("approval without pending proposal must fail closed")
