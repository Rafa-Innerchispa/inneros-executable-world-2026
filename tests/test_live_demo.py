from voiceops.live_demo import live_preflight, render_agent_reply


def test_preflight_reports_missing_key_without_exposing_secret(monkeypatch) -> None:
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    report = live_preflight()

    assert report["assemblyai_api_key_present"] is False
    assert report["ready_for_live_stream"] is False
    assert "api_key" not in report


def test_render_agent_reply_uses_gateway_message(capsys) -> None:
    reply = render_agent_reply({"message": "Explicit authorization required."})
    captured = capsys.readouterr()

    assert reply == "Explicit authorization required."
    assert "InnerOS:" in captured.out
