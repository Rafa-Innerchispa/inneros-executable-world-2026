from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from voiceops.gateway import VoiceGateway


AgentReplyFn = Callable[[dict[str, object]], str | None]


@dataclass(slots=True)
class StreamingState:
    connected: bool = False
    provider_session_id: str | None = None
    final_turns: int = 0
    partial_turns: int = 0
    held_turns: int = 0
    context_updates: int = 0
    agent_replies: int = 0
    last_end_of_turn_confidence: float | None = None
    errors: list[str] = field(default_factory=list)
    last_gateway_result: dict[str, object] | None = None
    last_agent_reply: str | None = None


class AssemblyAIStreamingAdapter:
    """AssemblyAI v3 streaming adapter around the governed VoiceGateway.

    This is the custom-pipeline lane used when InnerOS owns LLM reasoning and TTS.
    The managed Voice Agent API is integrated separately by the judge browser UI.
    """

    AUDIO_ENCODING = "pcm_s16le"
    AUDIO_CHANNELS = 1

    def __init__(
        self,
        gateway: VoiceGateway,
        *,
        api_key: str | None = None,
        speech_model: str = "universal-3-5-pro",
        sample_rate: int = 16000,
        min_end_of_turn_confidence: float = 0.5,
        agent_reply_fn: AgentReplyFn | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if not 0.0 <= min_end_of_turn_confidence <= 1.0:
            raise ValueError("min_end_of_turn_confidence must be between 0 and 1")
        self.gateway = gateway
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        self.speech_model = speech_model
        self.sample_rate = sample_rate
        self.min_end_of_turn_confidence = min_end_of_turn_confidence
        self.agent_reply_fn = agent_reply_fn
        self.state = StreamingState()
        self._client: Any = None

    @property
    def audio_contract(self) -> dict[str, object]:
        return {
            "encoding": self.AUDIO_ENCODING,
            "channels": self.AUDIO_CHANNELS,
            "sample_rate": self.sample_rate,
            "recommended_chunk_ms_min": 50,
            "recommended_chunk_ms_max": 1000,
        }

    def _handle_agent_reply(self, result: dict[str, object]) -> None:
        if self.agent_reply_fn is None:
            return
        reply = self.agent_reply_fn(result)
        if reply is None or not reply.strip():
            return
        normalized = reply.strip()
        self.state.agent_replies += 1
        self.state.last_agent_reply = normalized
        self.gateway.evidence.add_event(
            "voiceops_agent_reply_prepared",
            character_count=len(normalized),
            content_recorded=False,
        )
        if self._client is not None:
            self.update_agent_context(normalized)

    def handle_turn(
        self,
        transcript: str,
        *,
        end_of_turn: bool,
        end_of_turn_confidence: float | None = None,
    ) -> dict[str, object] | None:
        if not transcript.strip():
            return None
        if end_of_turn_confidence is not None:
            confidence = float(end_of_turn_confidence)
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("end_of_turn_confidence must be between 0 and 1")
            self.state.last_end_of_turn_confidence = confidence
        if not end_of_turn:
            self.state.partial_turns += 1
            return None
        if (
            end_of_turn_confidence is not None
            and end_of_turn_confidence < self.min_end_of_turn_confidence
        ):
            self.state.held_turns += 1
            self.gateway.evidence.add_event(
                "assemblyai_turn_held",
                end_of_turn_confidence=float(end_of_turn_confidence),
                minimum_confidence=self.min_end_of_turn_confidence,
                transcript_recorded=False,
            )
            return None

        self.state.final_turns += 1
        self.gateway.evidence.add_event(
            "assemblyai_turn_accepted",
            end_of_turn_confidence=end_of_turn_confidence,
            minimum_confidence=self.min_end_of_turn_confidence,
        )
        result = self.gateway.process_final_transcript(transcript)
        self.state.last_gateway_result = result
        self._handle_agent_reply(result)
        return result

    def connect(self, *, agent_context: str | None = None) -> None:
        if not self.api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is required for live streaming")

        try:
            from assemblyai.streaming.v3 import (
                StreamingClient,
                StreamingClientOptions,
                StreamingEvents,
                StreamingParameters,
            )
        except ImportError as exc:  # pragma: no cover - optional live dependency
            raise RuntimeError(
                "Install the optional dependency with: pip install -e '.[assemblyai]'"
            ) from exc

        self._client = StreamingClient(StreamingClientOptions(api_key=self.api_key))

        def on_begin(_client: Any, event: Any) -> None:
            self.state.connected = True
            self.state.provider_session_id = getattr(event, "id", None)
            self.gateway.evidence.add_event(
                "assemblyai_session_started",
                provider_session_id=self.state.provider_session_id,
                speech_model=self.speech_model,
                audio_contract=self.audio_contract,
                min_end_of_turn_confidence=self.min_end_of_turn_confidence,
            )

        def on_turn(_client: Any, event: Any) -> None:
            self.handle_turn(
                getattr(event, "transcript", ""),
                end_of_turn=bool(getattr(event, "end_of_turn", False)),
                end_of_turn_confidence=getattr(event, "end_of_turn_confidence", None),
            )

        def on_termination(_client: Any, event: Any) -> None:
            self.state.connected = False
            self.gateway.evidence.add_event(
                "assemblyai_session_terminated",
                audio_duration_seconds=getattr(event, "audio_duration_seconds", None),
            )

        def on_error(_client: Any, error: Any) -> None:
            message = str(error)
            self.state.errors.append(message)
            self.gateway.evidence.add_event("assemblyai_error", message=message)

        self._client.on(StreamingEvents.Begin, on_begin)
        self._client.on(StreamingEvents.Turn, on_turn)
        self._client.on(StreamingEvents.Termination, on_termination)
        self._client.on(StreamingEvents.Error, on_error)

        params: dict[str, Any] = {
            "speech_model": self.speech_model,
            "sample_rate": self.sample_rate,
        }
        if agent_context:
            params["agent_context"] = agent_context
        self._client.connect(StreamingParameters(**params))

    def update_agent_context(self, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ValueError("agent_context must not be empty")
        if self._client is None:
            raise RuntimeError("connect() must be called before update_agent_context()")
        updater = getattr(self._client, "update_configuration", None)
        if not callable(updater):
            raise RuntimeError("AssemblyAI client does not support update_configuration()")
        updater(agent_context=normalized)
        self.state.context_updates += 1
        self.gateway.evidence.add_event(
            "assemblyai_agent_context_updated",
            character_count=len(normalized),
            content_recorded=False,
        )

    def stream(self, audio_source: Any) -> None:
        if self._client is None:
            raise RuntimeError("connect() must be called before stream()")
        self._client.stream(audio_source)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect(terminate=True)
            finally:
                self.state.connected = False
                self._client = None
