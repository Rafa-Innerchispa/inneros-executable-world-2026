from voiceops.adapters.assemblyai_streaming import AssemblyAIStreamingAdapter
from voiceops.gateway import VoiceGateway


def test_low_end_of_turn_confidence_is_held_before_reasoning() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(
        gateway,
        api_key="test-key-not-used",
        min_end_of_turn_confidence=0.5,
    )

    result = adapter.handle_turn(
        "Revisa la alarma",
        end_of_turn=True,
        end_of_turn_confidence=0.31,
    )

    assert result is None
    assert adapter.state.held_turns == 1
    assert adapter.state.final_turns == 0
    assert gateway.evidence.proposal is None
    event = gateway.evidence.events[-1]
    assert event.kind == "assemblyai_turn_held"
    assert event.data["transcript_recorded"] is False


def test_high_end_of_turn_confidence_enters_governed_gateway() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(gateway, api_key="test-key-not-used")

    result = adapter.handle_turn(
        "Revisa la alarma",
        end_of_turn=True,
        end_of_turn_confidence=0.92,
    )

    assert result is not None
    assert result["status"] == "approval_required"
    assert adapter.state.final_turns == 1
    assert adapter.state.last_end_of_turn_confidence == 0.92
    assert any(event.kind == "assemblyai_turn_accepted" for event in gateway.evidence.events)


def test_end_of_turn_threshold_is_bounded() -> None:
    try:
        AssemblyAIStreamingAdapter(
            VoiceGateway(),
            api_key="test-key-not-used",
            min_end_of_turn_confidence=1.2,
        )
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("invalid confidence threshold must be rejected")
