"""Telephony voice providers — all run on the VoiceOps server (never in the browser)."""

from __future__ import annotations

import base64
import json
import os
import struct
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

from voiceops.adapters.telephony_call_state import (
    append_agent_line,
    append_user_line,
    set_agent_partial,
    set_call_phase,
    set_user_partial,
    update_call_debug,
)

VOICE_AGENT_PCM_RATE = 24000
BRIDGE_PCM_RATE = 16000


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _input_chunk_bytes_16k() -> int:
    raw = _env("VOICEOPS_TELEPHONY_INPUT_CHUNK_MS", "20")
    try:
        chunk_ms = max(20, min(100, int(raw)))
    except ValueError:
        chunk_ms = 20
    return chunk_ms * (BRIDGE_PCM_RATE * 2 // 1000)


def _resample_pcm16(pcm16: bytes, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate or not pcm16:
        return pcm16
    samples = struct.unpack("<" + "h" * (len(pcm16) // 2), pcm16)
    if not samples:
        return b""
    out_len = max(1, int(len(samples) * to_rate / from_rate))
    out: list[int] = []
    for i in range(out_len):
        pos = i * from_rate / to_rate
        idx = int(pos)
        frac = pos - idx
        s0 = samples[min(idx, len(samples) - 1)]
        s1 = samples[min(idx + 1, len(samples) - 1)]
        out.append(int(s0 + (s1 - s0) * frac))
    return struct.pack("<" + "h" * len(out), *out)


class TelephonyVoiceSession(ABC):
    provider_id: str = "unknown"
    output_pcm_rate: int = BRIDGE_PCM_RATE

    def __init__(self, *, greeting: str) -> None:
        self.greeting = greeting
        self.ready = threading.Event()
        self.done = threading.Event()

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def send_pcm16_16k(self, pcm16: bytes) -> None: ...

    @abstractmethod
    def drain_outbound_pcm16(self) -> list[bytes]:
        """Return PCM16 mono chunks at output_pcm_rate (16 kHz for RTP)."""


class AssemblyAITelephonySession(TelephonyVoiceSession):
    provider_id = "assemblyai"
    output_pcm_rate = BRIDGE_PCM_RATE

    def __init__(self, *, api_key: str, greeting: str) -> None:
        super().__init__(greeting=greeting)
        import websocket

        self._websocket_mod = websocket
        self.api_key = api_key
        self.ws: Any = None
        self.outbound_pcm24: list[bytes] = []
        self._lock = threading.Lock()
        self._last_agent_partial = ""
        self._input_buf = bytearray()
        self._min_input_pcm16_16k = _input_chunk_bytes_16k()

    def start(self) -> None:
        from voiceops.webapp import mint_voice_agent_token

        token = mint_voice_agent_token(self.api_key)["token"]
        self.ws = self._websocket_mod.create_connection(
            f"wss://agents.assemblyai.com/v1/ws?token={token}",
            timeout=10,
        )
        self.ws.settimeout(0.05)
        threading.Thread(target=self._reader, daemon=True, name="telephony-aai-reader").start()
        self.ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "system_prompt": (
                            "You are InnerOS VoiceOps. Reply in one short spoken sentence. "
                            "Be direct and conversational."
                        ),
                        "greeting": self.greeting,
                        "output": {
                            "voice": "lola",
                            "format": {"encoding": "audio/pcm", "sample_rate": VOICE_AGENT_PCM_RATE},
                            "volume": 100,
                        },
                        "input": {
                            "format": {"encoding": "audio/pcm", "sample_rate": VOICE_AGENT_PCM_RATE},
                            "language_codes": ["en", "es"],
                        },
                    },
                }
            )
        )

    def _reader(self) -> None:
        assert self.ws is not None
        while not self.done.is_set():
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            if not raw:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "session.ready":
                self.ready.set()
                set_call_phase("connected")
                set_agent_partial(self.greeting)
                update_call_debug(aai_ready=True, active_provider=self.provider_id)
            elif mtype == "transcript.user":
                text = str(msg.get("text") or "").strip()
                if not text:
                    continue
                set_user_partial(text)
                if msg.get("end_of_turn") is not False:
                    append_user_line(text)
                    set_user_partial("")
            elif mtype == "transcript.agent":
                text = str(msg.get("text") or "").strip()
                self._last_agent_partial = text
                if text:
                    set_agent_partial(text)
            elif mtype == "reply.audio" and msg.get("data"):
                pcm = base64.b64decode(msg["data"])
                with self._lock:
                    self.outbound_pcm24.append(pcm)
            elif mtype == "reply.done":
                if self._last_agent_partial:
                    append_agent_line(self._last_agent_partial)
                    self._last_agent_partial = ""
                    set_agent_partial("")
            elif mtype == "session.error":
                err = str(msg.get("message") or msg.get("code") or "session.error")
                update_call_debug(aai_error=err, active_provider=self.provider_id)
                self.done.set()
            elif mtype == "session.ended":
                self.done.set()

    def send_pcm16_16k(self, pcm16: bytes) -> None:
        if not self.ready.is_set() or self.ws is None or not pcm16:
            return
        self._input_buf.extend(pcm16)
        while len(self._input_buf) >= self._min_input_pcm16_16k:
            chunk16 = bytes(self._input_buf[: self._min_input_pcm16_16k])
            del self._input_buf[: self._min_input_pcm16_16k]
            pcm24 = _resample_pcm16(chunk16, BRIDGE_PCM_RATE, VOICE_AGENT_PCM_RATE)
            payload = base64.b64encode(pcm24).decode("ascii")
            try:
                self.ws.send(json.dumps({"type": "input.audio", "audio": payload}))
            except Exception:
                self.done.set()
                return

    def drain_outbound_pcm16(self) -> list[bytes]:
        chunks: list[bytes] = []
        with self._lock:
            pending = list(self.outbound_pcm24)
            self.outbound_pcm24.clear()
        for pcm24 in pending:
            chunks.append(_resample_pcm16(pcm24, VOICE_AGENT_PCM_RATE, BRIDGE_PCM_RATE))
        return chunks

    def close(self) -> None:
        self.done.set()
        if self.ws is not None:
            try:
                self.ws.send(json.dumps({"type": "session.end"}))
            except Exception:
                pass
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


class BosonTelephonySession(TelephonyVoiceSession):
    provider_id = "boson"
    output_pcm_rate = VOICE_AGENT_PCM_RATE

    def __init__(self, *, greeting: str) -> None:
        super().__init__(greeting=greeting)
        from voiceops.adapters.boson_realtime import _connect_upstream, build_session_update

        self._connect_upstream = _connect_upstream
        self._build_session_update = build_session_update
        self.ws: Any = None
        self.outbound_pcm24: list[bytes] = []
        self._lock = threading.Lock()
        self._last_agent_partial = ""
        self._input_buf = bytearray()
        self._min_input_pcm16_16k = _input_chunk_bytes_16k()

    def start(self) -> None:
        from voiceops.adapters.boson_realtime import boson_api_key

        key = boson_api_key()
        if not key:
            raise RuntimeError("BOSON_API_KEY not configured")
        self.ws = self._connect_upstream(api_key=key)
        self.ws.settimeout(0.05)
        threading.Thread(target=self._reader, daemon=True, name="telephony-boson-reader").start()
        self.ws.send(json.dumps(self._build_session_update(), ensure_ascii=False))
        self.ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {
                        "modalities": ["audio"],
                        "instructions": self.greeting,
                    },
                },
                ensure_ascii=False,
            )
        )

    def _reader(self) -> None:
        from voiceops.adapters.boson_realtime import _maybe_handle_tool_call

        assert self.ws is not None
        while not self.done.is_set():
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue
            if _maybe_handle_tool_call(msg, self.ws, None):
                continue
            mtype = msg.get("type", "")
            if mtype in {"session.created", "session.updated"}:
                self.ready.set()
                set_call_phase("connected")
                set_agent_partial(self.greeting)
                update_call_debug(boson_ready=True, active_provider=self.provider_id)
            elif mtype in {
                "response.output_audio_transcript.delta",
                "response.audio_transcript.delta",
                "response.output_text.delta",
            }:
                delta = str(msg.get("delta") or "")
                if delta:
                    self._last_agent_partial += delta
                    set_agent_partial(self._last_agent_partial)
            elif mtype in {
                "response.output_audio_transcript.done",
                "response.audio_transcript.done",
            }:
                final = str(msg.get("transcript") or self._last_agent_partial or "").strip()
                if final:
                    append_agent_line(final)
                    self._last_agent_partial = ""
                    set_agent_partial("")
            elif mtype in {"response.output_audio.delta", "response.audio.delta"}:
                delta = msg.get("delta") or ""
                if delta:
                    pcm = base64.b64decode(delta)
                    with self._lock:
                        self.outbound_pcm24.append(pcm)
            elif mtype in {"conversation.item.input_audio_transcription.completed", "input_audio_transcription.completed"}:
                user_text = str(
                    (msg.get("transcript") or msg.get("text") or (msg.get("item") or {}).get("transcript") or "")
                ).strip()
                if user_text:
                    append_user_line(user_text)
                    set_user_partial("")
            elif mtype == "error":
                err = str((msg.get("error") or msg))
                update_call_debug(boson_error=err, active_provider=self.provider_id)
                self.done.set()
            elif mtype in {"response.done", "response.output_audio.done", "response.audio.done"}:
                if self._last_agent_partial:
                    append_agent_line(self._last_agent_partial.strip())
                    self._last_agent_partial = ""
                    set_agent_partial("")

    def send_pcm16_16k(self, pcm16: bytes) -> None:
        if not self.ready.is_set() or self.ws is None or not pcm16:
            return
        self._input_buf.extend(pcm16)
        while len(self._input_buf) >= self._min_input_pcm16_16k:
            chunk16 = bytes(self._input_buf[: self._min_input_pcm16_16k])
            del self._input_buf[: self._min_input_pcm16_16k]
            pcm24 = _resample_pcm16(chunk16, BRIDGE_PCM_RATE, VOICE_AGENT_PCM_RATE)
            payload = base64.b64encode(pcm24).decode("ascii")
            try:
                self.ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": payload}))
            except Exception:
                self.done.set()
                return

    def drain_outbound_pcm16(self) -> list[bytes]:
        with self._lock:
            pending = list(self.outbound_pcm24)
            self.outbound_pcm24.clear()
        return [_resample_pcm16(pcm, VOICE_AGENT_PCM_RATE, BRIDGE_PCM_RATE) for pcm in pending]

    def close(self) -> None:
        self.done.set()
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


class ServerLocalTelephonySession(TelephonyVoiceSession):
    """InnerOS server-local turns: VAD + Higgs text brain + audible tone (no cloud voice API)."""

    provider_id = "browser_local"
    output_pcm_rate = BRIDGE_PCM_RATE

    def __init__(self, *, greeting: str) -> None:
        super().__init__(greeting=greeting)
        self.outbound_pcm16: list[bytes] = []
        self._lock = threading.Lock()
        self._speech_buf = bytearray()
        self._in_speech = False
        self._last_voice_at = 0.0
        self._turns = 0
        self._speech_threshold = 350
        self._silence_seconds = 0.75

    def start(self) -> None:
        self.ready.set()
        set_call_phase("connected")
        set_agent_partial(self.greeting)
        update_call_debug(active_provider=self.provider_id, server_local=True)
        reply = self._inneros_reply("Phone call connected")
        append_agent_line(reply)
        set_agent_partial("")
        with self._lock:
            self.outbound_pcm16.append(_text_to_pcm16_tone(reply))

    def _inneros_reply(self, user_text: str) -> str:
        from voiceops.adapters.higgs_realtime import HiggsRealtimeSession

        session = HiggsRealtimeSession()
        data = session.converse(user_text, active_proposal_id=None)
        return str(data.get("reply") or "InnerOS online. How can I help?")

    def _avg_abs(self, pcm16: bytes) -> int:
        if len(pcm16) < 2:
            return 0
        samples = struct.unpack("<" + "h" * (len(pcm16) // 2), pcm16)
        if not samples:
            return 0
        return int(sum(abs(s) for s in samples) / len(samples))

    def _finalize_turn(self) -> None:
        if not self._speech_buf:
            return
        self._turns += 1
        user_text = f"[Phone speech turn {self._turns}]"
        append_user_line(user_text)
        set_user_partial("")
        reply = self._inneros_reply(
            "The operator spoke on the Guayaquil phone line. Give a short operational reply."
        )
        append_agent_line(reply)
        set_agent_partial("")
        with self._lock:
            self.outbound_pcm16.append(_text_to_pcm16_tone(reply))
        self._speech_buf.clear()
        self._in_speech = False

    def send_pcm16_16k(self, pcm16: bytes) -> None:
        if not pcm16:
            return
        now = time.monotonic()
        energy = self._avg_abs(pcm16)
        if energy >= self._speech_threshold:
            self._in_speech = True
            self._last_voice_at = now
            self._speech_buf.extend(pcm16)
            return
        if self._in_speech and (now - self._last_voice_at) >= self._silence_seconds:
            self._finalize_turn()

    def drain_outbound_pcm16(self) -> list[bytes]:
        with self._lock:
            if not self.outbound_pcm16:
                return []
            chunks = list(self.outbound_pcm16)
            self.outbound_pcm16.clear()
            return chunks

    def close(self) -> None:
        self.done.set()
        if self._in_speech:
            self._finalize_turn()


def _text_to_pcm16_tone(text: str, sample_rate: int = 16000) -> bytes:
    words = [w for w in text.split() if w][:24] or ["InnerOS"]
    samples: list[int] = []
    for word in words:
        seed = sum(ord(c) for c in word) % 500
        for i in range(sample_rate // 12):
            sample = int(1800 * (0.45 + 0.55 * ((seed + i) % 11) / 11))
            if i % 40 < 20:
                sample = int(sample * 0.4)
            samples.append(max(-32767, min(32767, sample)))
        samples.extend([0] * (sample_rate // 30))
    return struct.pack("<" + "h" * len(samples), *samples)


def provider_status() -> dict[str, Any]:
    aai = bool(_env("ASSEMBLYAI_API_KEY"))
    boson = bool(_env("BOSON_API_KEY") or _env("HIGGS_API_KEY"))
    return {
        "assemblyai": {"configured": aai, "label": "AssemblyAI · Lola"},
        "boson": {"configured": boson, "label": "Boson / InnerOS"},
        "browser_local": {"configured": True, "label": "InnerOS · server local"},
    }


def provider_fallback_order(requested: str) -> list[str]:
    requested = (requested or "assemblyai").strip()
    if _env("VOICEOPS_TELEPHONY_PROVIDER_FALLBACK", "true").lower() in {"0", "false", "no", "off"}:
        return [requested]
    chain = [requested]
    for candidate in ("assemblyai", "boson", "browser_local"):
        if candidate not in chain:
            chain.append(candidate)
    return chain


def create_telephony_voice_session(provider_id: str, *, greeting: str) -> TelephonyVoiceSession | None:
    if provider_id == "assemblyai":
        key = _env("ASSEMBLYAI_API_KEY")
        if not key:
            return None
        return AssemblyAITelephonySession(api_key=key, greeting=greeting)
    if provider_id == "boson":
        if not (_env("BOSON_API_KEY") or _env("HIGGS_API_KEY")):
            return None
        return BosonTelephonySession(greeting=greeting)
    if provider_id == "browser_local":
        return ServerLocalTelephonySession(greeting=greeting)
    return None


def start_best_voice_session(
    requested_provider: str,
    *,
    greeting: str,
    ready_timeout: float = 12.0,
) -> tuple[TelephonyVoiceSession | None, str, list[str]]:
    attempts: list[str] = []
    for provider_id in provider_fallback_order(requested_provider):
        session = create_telephony_voice_session(provider_id, greeting=greeting)
        if session is None:
            attempts.append(f"{provider_id}:not_configured")
            continue
        try:
            session.start()
        except Exception as exc:
            attempts.append(f"{provider_id}:start_error:{exc}")
            update_call_debug(**{f"{provider_id}_error": str(exc)})
            continue
        if session.ready.wait(timeout=ready_timeout):
            update_call_debug(active_provider=provider_id, provider_attempts=",".join(attempts))
            return session, provider_id, attempts
        attempts.append(f"{provider_id}:ready_timeout")
        session.close()
    update_call_debug(provider_attempts=",".join(attempts))
    return None, requested_provider, attempts
