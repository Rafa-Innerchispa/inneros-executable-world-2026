from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from voiceops.adapters.optional import velodb
from voiceops.adapters.optional import velodb_store


def test_velodb_disabled_without_env(monkeypatch) -> None:
    monkeypatch.delenv("EXECUTABLE_ENABLE_VELODB", raising=False)
    assert velodb.status().truth == "NOT_CONNECTED"


def test_velodb_missing_password(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_VELODB", "true")
    monkeypatch.setenv("VELODB_HOST", "example.test")
    monkeypatch.delenv("VELODB_PASSWORD", raising=False)
    assert velodb.status().truth == "NOT_CONNECTED"
    assert velodb.status().status == "MISSING_PASSWORD"


@patch("voiceops.adapters.optional.velodb_store._connect")
def test_velodb_insert_select_readback(mock_connect, monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_VELODB", "true")
    monkeypatch.setenv("VELODB_HOST", "example.test")
    monkeypatch.setenv("VELODB_PASSWORD", "secret")
    monkeypatch.setenv("VELODB_DATABASE", "inneros_executable_world")

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    mock_connect.return_value = conn

    event_id = "evt-123"
    cursor.fetchone.return_value = (event_id, "sess-1", "voiceops.test", "hash-abc")

    result = velodb_store.append_event(
        {
            "event_type": "voiceops.test",
            "session_id": "sess-1",
            "timestamp": "2026-09-19T00:00:00+00:00",
            "data": {"permit_id": "permit-1", "evidence_sha256": "hash-abc"},
        }
    )

    assert result["stored"] is True
    assert result["event_id"]
    assert result["evidence_hash"] == "hash-abc"
    assert cursor.execute.call_count >= 2


@patch("voiceops.adapters.optional.velodb_store.verify_insert_select")
def test_velodb_real_after_probe(mock_verify, monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_VELODB", "true")
    monkeypatch.setenv("VELODB_HOST", "example.test")
    monkeypatch.setenv("VELODB_PASSWORD", "secret")
    mock_verify.return_value = {"ok": True, "event_id": "probe-1"}
    velodb_store._PROBE_CACHE["ts"] = 0.0
    assert velodb.status().truth == "REAL"
