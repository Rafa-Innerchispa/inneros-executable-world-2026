from __future__ import annotations

from unittest.mock import MagicMock, patch

from voiceops.adapters.optional import agentx


def test_agentx_disabled(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_AGENTX", "false")
    assert agentx.status().truth == "NOT_CONNECTED"


@patch("voiceops.adapters.optional.agentx.probe_with_trace")
def test_agentx_real_when_trace_ok(mock_probe, monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_AGENTX", "true")
    mock_probe.return_value = {"ok": True, "health": {"url": "http://127.0.0.1:4700/health"}}
    assert agentx.status().truth == "REAL"


@patch("voiceops.adapters.optional.agentx.probe_with_trace")
def test_agentx_unverified_health_only(mock_probe, monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_AGENTX", "true")
    mock_probe.return_value = {"ok": False, "health": {"ok": True}}
    assert agentx.status().truth == "UNVERIFIED"
