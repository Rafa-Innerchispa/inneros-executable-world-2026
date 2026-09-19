from __future__ import annotations

from unittest.mock import patch

from voiceops.adapters.optional import edgeone


def test_edgeone_disabled(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_EDGEONE", "false")
    assert edgeone.status().truth == "NOT_CONNECTED"


def test_edgeone_configured_metadata_only(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_EDGEONE", "true")
    monkeypatch.setenv("EDGEONE_PAGES_PROJECT", "inneros-executable-world-2026")
    monkeypatch.delenv("EDGEONE_WITNESS_URL", raising=False)
    assert edgeone.status().truth == "CONFIGURED"


@patch("voiceops.adapters.optional.edgeone.verify_witness_post")
def test_edgeone_real_when_witness_post_ok(mock_verify, monkeypatch) -> None:
    monkeypatch.setenv("EXECUTABLE_ENABLE_EDGEONE", "true")
    monkeypatch.setenv("EDGEONE_WITNESS_URL", "https://witness.example/")
    mock_verify.return_value = {"ok": True}
    assert edgeone.status().truth == "REAL"
