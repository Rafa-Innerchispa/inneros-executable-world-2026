from voiceops.adapters.assemblyai_streaming import AssemblyAIStreamingAdapter
from voiceops.gateway import VoiceGateway


class FakeStreamingClient:
    def __init__(self) -> None:
        self.contexts: list[str] = []
        self.disconnect_calls: list[bool] = []

    def update_configuration(self, *, agent_context: str) -> None:
        self.contexts.append(agent_context)

    def disconnect(self, *, terminate: bool) -> None:
        self.disconnect_calls.append(terminate)


def test_partial_turn_does_not_trigger_governed_action() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(gateway, api_key="test-key-not-used")

    result = adapter.handle_turn("Revisa la alarma", end_of_turn=False)
    assert result is None
    assert adapter.state.partial_turns == 1
    assert gateway.evidence.proposal is None


def test_final_turn_enters_gateway() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(gateway, api_key="test-key-not-used")

    result = adapter.handle_turn("Revisa la alarma", end_of_turn=True)
    assert result is not None
    assert result["status"] == "approval_required"
    assert adapter.state.final_turns == 1


def test_live_connect_requires_api_key() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(gateway, api_key=None)
    adapter.api_key = None

    try:
        adapter.connect()
    except RuntimeError as exc:
        assert "ASSEMBLYAI_API_KEY" in str(exc)
    else:
        raise AssertionError("connect() must fail without a live API key")


def test_audio_contract_is_pcm16_mono_16khz_by_default() -> None:
    adapter = AssemblyAIStreamingAdapter(VoiceGateway(), api_key="test-key-not-used")
    assert adapter.audio_contract == {
        "encoding": "pcm_s16le",
        "channels": 1,
        "sample_rate": 16000,
        "recommended_chunk_ms_min": 50,
        "recommended_chunk_ms_max": 1000,
    }


def test_agent_context_updates_live_client_without_recording_content() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(gateway, api_key="test-key-not-used")
    fake = FakeStreamingClient()
    adapter._client = fake

    adapter.update_agent_context("Detecté una incidencia. ¿Autorizas crear la orden?")

    assert fake.contexts == ["Detecté una incidencia. ¿Autorizas crear la orden?"]
    assert adapter.state.context_updates == 1
    event = gateway.evidence.events[-1]
    assert event.kind == "assemblyai_agent_context_updated"
    assert event.data["content_recorded"] is False
    assert "Detecté" not in str(event.data)


def test_agent_reply_callback_refreshes_context_after_final_turn() -> None:
    gateway = VoiceGateway()
    adapter = AssemblyAIStreamingAdapter(
        gateway,
        api_key="test-key-not-used",
        agent_reply_fn=lambda result: str(result["message"]),
    )
    fake = FakeStreamingClient()
    adapter._client = fake

    result = adapter.handle_turn("Revisa la alarma", end_of_turn=True)

    assert result is not None
    assert result["status"] == "approval_required"
    assert adapter.state.agent_replies == 1
    assert adapter.state.context_updates == 1
    assert fake.contexts == [adapter.state.last_agent_reply]
    prepared = [e for e in gateway.evidence.events if e.kind == "voiceops_agent_reply_prepared"]
    assert len(prepared) == 1
    assert prepared[0].data["content_recorded"] is False


def test_close_always_terminates_live_session() -> None:
    adapter = AssemblyAIStreamingAdapter(VoiceGateway(), api_key="test-key-not-used")
    fake = FakeStreamingClient()
    adapter._client = fake
    adapter.state.connected = True

    adapter.close()

    assert fake.disconnect_calls == [True]
    assert adapter.state.connected is False
    assert adapter._client is None
