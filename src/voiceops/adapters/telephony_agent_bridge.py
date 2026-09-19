"""SIP/RTP bridge: ring an extension and run the selected voice provider on the call."""

from __future__ import annotations

import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from voiceops.adapters.g711_rtp import G711AssemblyAudioBridge
from voiceops.adapters.grandstream_ami import AMIError, GrandstreamAMIAdapter
from voiceops.adapters.sip_transport import GrandstreamSipClient, SipAuth, SipDialog, SipError, SdpAudioEndpoint
from voiceops.adapters.telephony_call_state import (
    append_agent_line,
    call_is_active,
    finish_call,
    reset_call_state,
    set_call_phase,
    snapshot,
    update_call_debug,
)
from voiceops.adapters.telephony_voice_providers import (
    TelephonyVoiceSession,
    _text_to_pcm16_tone,
    create_telephony_voice_session,
    provider_fallback_order,
    provider_status,
    start_best_voice_session,
)

VOICE_AGENT_PCM_RATE = 24000
BRIDGE_PCM_RATE = 16000
RTP_FRAME_PCM16_BYTES = 640  # 20 ms @ 16 kHz mono
PCM16_BYTES_PER_MS_16K = BRIDGE_PCM_RATE * 2 // 1000  # 32 bytes/ms @ 16 kHz mono


def _telephony_int_env(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _max_playout_bytes() -> int:
    return _telephony_int_env("VOICEOPS_TELEPHONY_MAX_PLAYOUT_MS", 100) * PCM16_BYTES_PER_MS_16K


def _input_chunk_bytes_16k() -> int:
    chunk_ms = max(20, min(100, _telephony_int_env("VOICEOPS_TELEPHONY_INPUT_CHUNK_MS", 20)))
    return chunk_ms * PCM16_BYTES_PER_MS_16K


def _trim_playout_buffer(buf: bytearray, max_bytes: int) -> int:
    if len(buf) <= max_bytes:
        return 0
    dropped = len(buf) - max_bytes
    del buf[:dropped]
    return dropped

_call_lock = threading.Lock()
_call_thread: threading.Thread | None = None
_cancel_event = threading.Event()
_active_hangup: threading.Lock = threading.Lock()
_active_client: GrandstreamSipClient | None = None
_active_dialog: SipDialog | None = None


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _truthy(name: str) -> bool:
    return _env(name).lower() in {"1", "true", "yes", "on"}


def _local_ip() -> str:
    return _env("VOICEOPS_TELEPHONY_LOCAL_IP", "192.168.1.4")


def _default_target() -> str:
    return _env("VOICEOPS_TELEPHONY_DEFAULT_EXTENSION", "1004")


def _agent_auth() -> SipAuth | None:
    ext = _env("VOICEOPS_TELEPHONY_SIP_AGENT_EXT", "1003")
    secret = _env("VOICEOPS_TELEPHONY_SIP_AGENT_SECRET")
    if not secret:
        return None
    return SipAuth(ext, secret)


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


def _send_pcm16_to_rtp_paced(
    rtp_sock: socket.socket,
    bridge: G711AssemblyAudioBridge,
    remote_addr: tuple[str, int],
    pcm16_16k: bytes,
) -> int:
    sent = 0
    for offset in range(0, len(pcm16_16k), RTP_FRAME_PCM16_BYTES):
        frame = pcm16_16k[offset : offset + RTP_FRAME_PCM16_BYTES]
        if len(frame) < RTP_FRAME_PCM16_BYTES:
            frame = frame + b"\x00" * (RTP_FRAME_PCM16_BYTES - len(frame))
        rtp_sock.sendto(bridge.encode_assemblyai_pcm_for_rtp(frame), remote_addr)
        sent += 1
        time.sleep(0.02)
    return sent


@dataclass
class AgentCallResult:
    ok: bool
    target: str
    ring_method: str
    voice_provider: str
    phase: str
    message: str
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "target": self.target,
            "ring_method": self.ring_method,
            "voice_provider": self.voice_provider,
            "phase": self.phase,
            "message": self.message,
            "error": self.error,
            "transcript": snapshot(),
            **self.details,
        }


def _ring_via_ami(target: str) -> dict[str, str]:
    if not _truthy("VOICEOPS_TELEPHONY_ORIGINATE_ENABLED"):
        raise AMIError("VOICEOPS_TELEPHONY_ORIGINATE_ENABLED is not true")
    ami = GrandstreamAMIAdapter()
    return ami.originate_internal_extension(target)


def _should_cancel_call() -> bool:
    return _cancel_event.is_set()


def _clear_active_handles() -> None:
    global _active_client, _active_dialog
    with _active_hangup:
        _active_client = None
        _active_dialog = None


def _set_active_handles(client: GrandstreamSipClient | None, dialog: SipDialog | None) -> None:
    global _active_client, _active_dialog
    with _active_hangup:
        _active_client = client
        _active_dialog = dialog


def _run_rtp_voice_session(
    *,
    rtp_sock: socket.socket,
    remote: SdpAudioEndpoint,
    bridge: G711AssemblyAudioBridge,
    voice_provider: str,
    duration_seconds: float,
    voice: TelephonyVoiceSession | None = None,
) -> dict[str, Any]:
    remote_addr = (remote.host, remote.port)
    learned_addr: tuple[str, int] | None = None
    stop_at = time.monotonic() + duration_seconds
    greeting = "InnerOS online. How can I help?"
    stats: dict[str, Any] = {
        "rtp_in": 0,
        "rtp_out": 0,
        "voice_mode": "tone",
        "sdp_remote": f"{remote.host}:{remote.port}",
        "requested_provider": voice_provider,
    }
    silence_pcm16 = b"\x00" * RTP_FRAME_PCM16_BYTES
    update_call_debug(sdp_remote=stats["sdp_remote"], requested_provider=voice_provider)

    active_provider = voice_provider
    if voice is None:
        voice, active_provider, attempts = start_best_voice_session(voice_provider, greeting=greeting)
        stats["provider_attempts"] = attempts
    else:
        active_provider = voice.provider_id
        if not voice.ready.is_set() and not voice.ready.wait(timeout=12):
            voice.close()
            voice = None
            voice, active_provider, attempts = start_best_voice_session(voice_provider, greeting=greeting)
            stats["provider_attempts"] = attempts

    pending_tone_pcm: bytes | None = None
    if voice is not None:
        stats["voice_mode"] = active_provider
        set_call_phase("speaking")
        update_call_debug(voice_mode=active_provider, active_provider=active_provider)
    else:
        stats["voice_mode"] = "fallback_tone"
        update_call_debug(voice_mode="fallback_tone")
        spoken = greeting
        append_agent_line(spoken)
        pending_tone_pcm = _text_to_pcm16_tone(spoken)

    pcm_accum = bytearray()
    max_playout_bytes = _max_playout_bytes()
    next_rtp_send = time.monotonic()
    tone_deadline = time.monotonic() + 2.5
    aai_audio_bytes = 0
    dropped_playout_bytes = 0
    last_debug_at = 0.0
    rtp_sock.settimeout(0.001)

    def _send_target() -> tuple[str, int]:
        return learned_addr or remote_addr

    def _process_inbound_rtp(data: bytes, addr: tuple[str, int]) -> None:
        nonlocal learned_addr, pending_tone_pcm
        if learned_addr is None:
            learned_addr = (addr[0], addr[1])
            stats["learned_remote"] = f"{learned_addr[0]}:{learned_addr[1]}"
            update_call_debug(learned_remote=stats["learned_remote"])
            if pending_tone_pcm:
                stats["rtp_out"] += _send_pcm16_to_rtp_paced(
                    rtp_sock, bridge, learned_addr, pending_tone_pcm
                )
                pending_tone_pcm = None
        stats["rtp_in"] += 1
        if voice is not None:
            pcm16 = bridge.decode_rtp_for_assemblyai(data)
            if pcm16:
                voice.send_pcm16_16k(pcm16)

    while time.monotonic() < stop_at:
        if _should_cancel_call():
            stats["cancelled"] = True
            break
        now = time.monotonic()

        if voice is not None:
            for pcm16 in voice.drain_outbound_pcm16():
                aai_audio_bytes += len(pcm16)
                pcm_accum.extend(pcm16)
            dropped_playout_bytes += _trim_playout_buffer(pcm_accum, max_playout_bytes)

        while len(pcm_accum) >= RTP_FRAME_PCM16_BYTES and now >= next_rtp_send:
            frame = bytes(pcm_accum[:RTP_FRAME_PCM16_BYTES])
            del pcm_accum[:RTP_FRAME_PCM16_BYTES]
            marker = stats["rtp_out"] == 0 or len(pcm_accum) == 0
            rtp_sock.sendto(
                bridge.encode_assemblyai_pcm_for_rtp(frame, marker=marker),
                _send_target(),
            )
            stats["rtp_out"] += 1
            next_rtp_send += 0.02
            now = time.monotonic()

        if now >= next_rtp_send and not pcm_accum:
            rtp_sock.sendto(bridge.encode_assemblyai_pcm_for_rtp(silence_pcm16), _send_target())
            stats["rtp_out"] += 1
            next_rtp_send += 0.02

        if pending_tone_pcm and learned_addr is None and now >= tone_deadline:
            stats["rtp_out"] += _send_pcm16_to_rtp_paced(
                rtp_sock, bridge, remote_addr, pending_tone_pcm
            )
            pending_tone_pcm = None

        while True:
            try:
                data, addr = rtp_sock.recvfrom(2048)
            except socket.timeout:
                break
            _process_inbound_rtp(data, addr)

        if now - last_debug_at >= 1.0:
            last_debug_at = now
            update_call_debug(
                rtp_in=stats["rtp_in"],
                rtp_out=stats["rtp_out"],
                aai_audio_bytes=aai_audio_bytes,
                playout_buffer_ms=len(pcm_accum) // PCM16_BYTES_PER_MS_16K,
                dropped_playout_ms=dropped_playout_bytes // PCM16_BYTES_PER_MS_16K,
                voice_mode=stats.get("voice_mode"),
            )

    stats["aai_audio_bytes"] = aai_audio_bytes
    stats["dropped_playout_bytes"] = dropped_playout_bytes
    update_call_debug(
        rtp_in=stats["rtp_in"],
        rtp_out=stats["rtp_out"],
        aai_audio_bytes=aai_audio_bytes,
        playout_buffer_ms=len(pcm_accum) // PCM16_BYTES_PER_MS_16K,
        dropped_playout_ms=dropped_playout_bytes // PCM16_BYTES_PER_MS_16K,
        voice_mode=stats.get("voice_mode"),
    )
    stats["active_provider"] = active_provider
    if voice is not None:
        voice.close()
    return stats


def _place_sip_agent_call(target: str, voice_provider: str) -> AgentCallResult:
    auth = _agent_auth()
    if auth is None:
        raise SipError("VOICEOPS_TELEPHONY_SIP_AGENT_SECRET is not configured on the server")

    reset_call_state(target=target, voice_provider=voice_provider)
    set_call_phase("dialing")

    host = _env("VOICEOPS_TELEPHONY_AMI_HOST", "192.168.1.6")
    sip_port = int(_env("VOICEOPS_TELEPHONY_SIP_PORT", "4321") or "4321")
    local_ip = _local_ip()
    rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp_sock.bind((local_ip, 0))
    rtp_sock.settimeout(0.02)
    rtp_port = int(rtp_sock.getsockname()[1])
    client = GrandstreamSipClient(host=host, auth=auth, local_ip=local_ip, sip_port=sip_port)
    dialog: SipDialog | None = None
    greeting = "InnerOS online. How can I help?"
    voice_prewarm: TelephonyVoiceSession | None = None
    set_call_phase("connecting_agent")
    for pid in provider_fallback_order(voice_provider):
        session = create_telephony_voice_session(pid, greeting=greeting)
        if session is None:
            continue
        try:
            session.start()
            voice_prewarm = session
            update_call_debug(voice_prewarm=f"{pid}:started", prewarm_provider=pid)
            break
        except Exception as exc:
            update_call_debug(**{f"{pid}_prewarm_error": str(exc)})
    try:
        _set_active_handles(client, None)
        set_call_phase("ringing")
        dialog, remote = client.invite_extension(
            target,
            rtp_port,
            timeout_seconds=55.0,
            should_cancel=_should_cancel_call,
        )
        _set_active_handles(client, dialog)
        bridge = G711AssemblyAudioBridge(outbound_payload_type=remote.preferred_g711_payload())
        set_call_phase("answered")
        stats = _run_rtp_voice_session(
            rtp_sock=rtp_sock,
            remote=remote,
            bridge=bridge,
            voice_provider=voice_provider,
            duration_seconds=float(_env("VOICEOPS_TELEPHONY_CALL_SECONDS", "90") or "90"),
            voice=voice_prewarm,
        )
        cancelled = bool(stats.get("cancelled"))
        finish_call(ok=not cancelled, phase="cancelled" if cancelled else None, error="cancelled by user" if cancelled else None)
        return AgentCallResult(
            ok=not cancelled,
            target=target,
            ring_method="sip_invite",
            voice_provider=voice_provider,
            phase="cancelled" if cancelled else "completed",
            message=(
                f"Phone call to {target} cancelled."
                if cancelled
                else f"Phone call to {target} finished. Audio stays on the handset; transcript is in the panel."
            ),
            error="cancelled by user" if cancelled else None,
            details={"agent_extension": auth.extension, "rtp_stats": stats, "transcript": snapshot()},
        )
    except Exception as exc:
        if _should_cancel_call() or "cancelled" in str(exc).lower():
            finish_call(ok=False, phase="cancelled", error="cancelled by user")
        else:
            finish_call(ok=False, error=str(exc))
        raise
    finally:
        if dialog is not None:
            try:
                client.send_bye(dialog)
            except Exception:
                pass
        client.close()
        rtp_sock.close()
        _clear_active_handles()


def place_agent_call(target: str, *, voice_provider: str = "assemblyai") -> dict[str, Any]:
    normalized = str(target or _default_target()).strip()
    if not normalized.isdigit():
        finish_call(ok=False, error="invalid extension")
        return AgentCallResult(
            ok=False,
            target=normalized,
            ring_method="none",
            voice_provider=voice_provider,
            phase="failed",
            message="Invalid extension.",
            error="extension must be numeric",
        ).to_dict()

    auth = _agent_auth()
    if auth is not None:
        try:
            return _place_sip_agent_call(normalized, voice_provider).to_dict()
        except Exception as exc:
            ami_fallback = _truthy("VOICEOPS_TELEPHONY_ORIGINATE_ENABLED")
            if not ami_fallback:
                return AgentCallResult(
                    ok=False,
                    target=normalized,
                    ring_method="sip_invite",
                    voice_provider=voice_provider,
                    phase="failed",
                    message="SIP agent call failed.",
                    error=str(exc),
                    details={"transcript": snapshot()},
                ).to_dict()

    try:
        reset_call_state(target=normalized, voice_provider=voice_provider)
        set_call_phase("ringing")
        originate = _ring_via_ami(normalized)
        finish_call(ok=True, phase="originated")
        return AgentCallResult(
            ok=True,
            target=normalized,
            ring_method="ami_originate",
            voice_provider=voice_provider,
            phase="originated",
            message=f"Ringing {normalized} via AMI (no RTP agent — configure SIP agent for voice).",
            details={"originate": originate, "transcript": snapshot()},
        ).to_dict()
    except Exception as exc:
        finish_call(ok=False, error=str(exc))
        return AgentCallResult(
            ok=False,
            target=normalized,
            ring_method="ami_originate",
            voice_provider=voice_provider,
            phase="failed",
            message="Could not ring the extension.",
            error=str(exc),
            details={"transcript": snapshot()},
        ).to_dict()


def get_call_session_snapshot() -> dict[str, Any]:
    return snapshot()


def get_telephony_provider_status() -> dict[str, Any]:
    return {
        "providers": provider_status(),
        "fallback_enabled": _env("VOICEOPS_TELEPHONY_PROVIDER_FALLBACK", "true").lower()
        not in {"0", "false", "no", "off"},
        "fallback_order": provider_fallback_order("assemblyai"),
    }


def cancel_active_call() -> dict[str, Any]:
    _cancel_event.set()
    with _active_hangup:
        client = _active_client
        dialog = _active_dialog
    if client is not None and dialog is not None:
        try:
            if dialog.established:
                client.send_bye(dialog)
            else:
                client.send_cancel_invite(dialog, dialog.cseq)
        except Exception:
            pass
    if call_is_active():
        finish_call(ok=False, phase="cancelled", error="cancelled by user")
    return {"ok": True, "cancelled": True, "session": snapshot()}


def _run_call_job(target: str, voice_provider: str) -> None:
    global _call_thread
    try:
        place_agent_call(target, voice_provider=voice_provider)
    finally:
        with _call_lock:
            _call_thread = None
        _cancel_event.clear()


def start_agent_call_async(target: str, *, voice_provider: str = "assemblyai") -> dict[str, Any]:
    global _call_thread
    normalized = str(target or _default_target()).strip()
    if not normalized.isdigit():
        return AgentCallResult(
            ok=False,
            target=normalized,
            ring_method="none",
            voice_provider=voice_provider,
            phase="failed",
            message="Invalid extension.",
            error="extension must be numeric",
        ).to_dict()

    with _call_lock:
        if call_is_active() or (_call_thread is not None and _call_thread.is_alive()):
            return {
                "ok": False,
                "started": False,
                "error": "A phone call is already in progress.",
                "session": snapshot(),
            }
        _cancel_event.clear()
        reset_call_state(target=normalized, voice_provider=voice_provider)
        set_call_phase("starting")
        _call_thread = threading.Thread(
            target=_run_call_job,
            args=(normalized, voice_provider),
            name="voiceops-telephony-call",
            daemon=True,
        )
        _call_thread.start()

    return {
        "ok": True,
        "started": True,
        "target": normalized,
        "voice_provider": voice_provider,
        "message": f"Calling extension {normalized}. Answer Zoiper on your phone.",
        "session": snapshot(),
    }
