from __future__ import annotations

import json
import os
from pathlib import Path

from voiceops.adapters.sponsor_evidence import record_evidence_event


def test_local_evidence_always_stored(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICEOPS_EVIDENCE_DIR", str(tmp_path))
    monkeypatch.delenv("EXECUTABLE_ENABLE_AGENTX", raising=False)
    monkeypatch.delenv("EXECUTABLE_ENABLE_VELODB", raising=False)
    monkeypatch.delenv("EXECUTABLE_ENABLE_EDGEONE", raising=False)

    result = record_evidence_event("voiceops.test", {"foo": "bar"}, session_id="test-session")
    assert result["ok"] is True
    assert result["outcomes"]["local"]["stored"] is True

    path = Path(result["outcomes"]["local"]["path"])
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "expected at least one evidence row"
    row = json.loads(lines[-1])
    assert row["event_type"] == "voiceops.test"
    assert row["data"]["foo"] == "bar"


def test_optional_adapters_fail_closed_without_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICEOPS_EVIDENCE_DIR", str(tmp_path))
    monkeypatch.setenv("EXECUTABLE_ENABLE_AGENTX", "false")
    monkeypatch.setenv("EXECUTABLE_ENABLE_VELODB", "false")
    monkeypatch.setenv("EXECUTABLE_ENABLE_EDGEONE", "false")

    from voiceops.adapters.optional import agentx, edgeone, velodb

    assert agentx.status().truth == "NOT_CONNECTED"
    assert velodb.status().truth == "NOT_CONNECTED"
    assert edgeone.status().truth == "NOT_CONNECTED"
