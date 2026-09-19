from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from voiceops.provider_smoke import (  # noqa: E402
    _connect_websocket,
    _load_runtime_api_key,
    _mint_token,
    _recv_frame,
    _send_frame,
)

PCM_BYTES_PER_SECOND = 24_000 * 2
DEFAULT_INTENT = "Ralphi, revisa la incidencia del acceso norte y abre una orden técnica si corresponde."
DEFAULT_APPROVAL = "Sí, apruebo. Sí, autorizo."


def _http_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    with urlopen(request, timeout=10) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"unexpected JSON response from {path}")
    return parsed


def _recv_json(sock: Any) -> dict[str, Any] | None:
    while True:
        opcode, payload = _recv_frame(sock)
        if opcode == 0x9:
            _send_frame(sock, payload, opcode=0xA)
            continue
        if opcode == 0x8:
            return None
        if opcode != 0x1:
            continue
        message = json.loads(payload.decode("utf-8"))
        if isinstance(message, dict):
            return message


def _synthesize_fixture(api_key: str, text: str) -> tuple[bytes, dict[str, Any]]:
    sock = _connect_websocket(_mint_token(api_key))
    audio = bytearray()
    events: list[str] = []
    ready = False
    done = False
    ended = False
    try:
        config = {
            "type": "session.update",
            "session": {
                "system_prompt": "Speak the configured greeting exactly as a short audio fixture.",
                "greeting": text,
                "output": {"voice": "anna", "format": {"encoding": "audio/pcm"}},
                "input": {"format": {"encoding": "audio/pcm"}},
                "tools": [],
            },
        }
        _send_frame(sock, json.dumps(config, separators=(",", ":")).encode("utf-8"))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            message = _recv_json(sock)
            if message is None:
                break
            event_type = str(message.get("type") or "unknown")
            events.append(event_type)
            if event_type == "session.ready":
                ready = True
            elif event_type == "reply.audio":
                encoded = message.get("data")
                if isinstance(encoded, str):
                    audio.extend(base64.b64decode(encoded))
            elif event_type == "reply.done":
                done = True
                _send_frame(sock, b'{"type":"session.end"}')
            elif event_type == "session.ended":
                ended = True
                break
            elif event_type == "session.error":
                raise RuntimeError(
                    f"fixture session error: {message.get('code')}: {message.get('message')}"
                )
        if not (ready and done and audio):
            raise RuntimeError("AssemblyAI TTS fixture did not produce complete PCM audio")
        return bytes(audio), {
            "session_ready": ready,
            "reply_done": done,
            "session_ended": ended,
            "audio_bytes": len(audio),
            "event_types": events[:30],
        }
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _send_pcm_realtime(sock: Any, pcm: bytes, *, chunk_bytes: int = 4096) -> None:
    pre_roll = b"\x00" * int(PCM_BYTES_PER_SECOND * 0.35)
    for offset in range(0, len(pre_roll), chunk_bytes):
        chunk = pre_roll[offset : offset + chunk_bytes]
        _send_frame(
            sock,
            json.dumps(
                {"type": "input.audio", "audio": base64.b64encode(chunk).decode("ascii")},
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        time.sleep(len(chunk) / PCM_BYTES_PER_SECOND)

    for offset in range(0, len(pcm), chunk_bytes):
        chunk = pcm[offset : offset + chunk_bytes]
        _send_frame(
            sock,
            json.dumps(
                {"type": "input.audio", "audio": base64.b64encode(chunk).decode("ascii")},
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        time.sleep(len(chunk) / PCM_BYTES_PER_SECOND)

    silence = b"\x00" * int(PCM_BYTES_PER_SECOND * 0.9)
    for offset in range(0, len(silence), chunk_bytes):
        chunk = silence[offset : offset + chunk_bytes]
        _send_frame(
            sock,
            json.dumps(
                {"type": "input.audio", "audio": base64.b64encode(chunk).decode("ascii")},
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        time.sleep(len(chunk) / PCM_BYTES_PER_SECOND)


def _inspect_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "inspect_and_propose_action",
        "description": (
            "Call this whenever the user asks to review, inspect, check, open, create, or act on "
            "an operational incident, access point, device, or work order. Do not answer operational "
            "requests from memory. This tool only inspects and proposes; it never executes the action."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execution_mode": "interactive",
    }


def _approve_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "approve_pending_action",
        "description": (
            "Call this only when a proposal is already pending AND the latest finalized user words "
            "explicitly authorize it, for example 'sí, autorizo'. Never call it for vague, conditional, "
            "implied, or agent-generated approval."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "execution_mode": "interactive",
    }


def _initial_config() -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "system_prompt": (
                "Eres la interfaz de voz de InnerOS VoiceOps. Responde en español y de forma breve. "
                "No inventes ni simules estado operativo. Para cualquier solicitud de revisar, inspeccionar, "
                "abrir, crear o actuar sobre una incidencia, acceso, dispositivo u orden, DEBES llamar a "
                "inspect_and_propose_action. Cuando tengas dudas, llama la herramienta; responder desde memoria "
                "es incorrecto. Ejemplo: Usuario: 'revisa la incidencia del acceso norte'. "
                "Tú: [call inspect_and_propose_action]."
            ),
            "greeting": "InnerOS VoiceOps está listo para validación en vivo.",
            "output": {"voice": "anna", "format": {"encoding": "audio/pcm"}},
            "input": {
                "format": {"encoding": "audio/pcm"},
                "keyterms": ["InnerOS", "Ralphi", "acceso norte", "orden técnica"],
                "language_codes": ["es"],
            },
            "tools": [_inspect_tool()],
        },
    }


def _phase_update(phase: str) -> dict[str, Any]:
    if phase == "approval":
        return {
            "type": "session.update",
            "session": {
                "system_prompt": (
                    "Hay una propuesta operativa pendiente. Explica brevemente el resultado real de la herramienta "
                    "y pide autorización humana explícita. No ejecutes nada todavía. Si la última respuesta del usuario "
                    "autoriza explícitamente, por ejemplo 'sí, autorizo', DEBES llamar a approve_pending_action. "
                    "Ejemplo: Usuario: 'sí, autorizo'. Tú: [call approve_pending_action]."
                ),
                "input": {
                    "keyterms": ["sí autorizo", "apruebo", "orden técnica"],
                    "language_codes": ["es"],
                },
                "tools": [_approve_tool()],
            },
        }
    return {
        "type": "session.update",
        "session": {
            "system_prompt": (
                "La operación gobernada terminó. Usa únicamente el resultado de la herramienta para confirmar el estado, "
                "el identificador de la orden si existe y que se registró Decision Evidence. No llames más herramientas."
            ),
            "tools": [],
        },
    }


def _send_tool_result(sock: Any, call_id: str, result: dict[str, Any]) -> None:
    _send_frame(
        sock,
        json.dumps(
            {
                "type": "tool.result",
                "call_id": call_id,
                "result": json.dumps(result, separators=(",", ":")),
            },
            separators=(",", ":"),
        ).encode("utf-8"),
    )


def run_live_e2e(*, config_path: Path, base_url: str) -> dict[str, Any]:
    started = time.time()
    api_key = _load_runtime_api_key(config_path)
    result: dict[str, Any] = {
        "provider": "assemblyai",
        "surface": "voice_agent_api",
        "audio_source": "assemblyai_tts_fixture",
        "production_writes": False,
        "intent_fixture": {},
        "approval_fixture": {},
        "main_session": {
            "session_ready": False,
            "intent_final_transcript": False,
            "inspect_tool_called": False,
            "approval_final_transcript": False,
            "approve_tool_called": False,
            "reply_audio_seen": False,
            "session_ended": False,
        },
    }

    intent_audio, intent_fixture = _synthesize_fixture(api_key, DEFAULT_INTENT)
    approval_audio, approval_fixture = _synthesize_fixture(api_key, DEFAULT_APPROVAL)
    result["intent_fixture"] = intent_fixture
    result["approval_fixture"] = approval_fixture

    _http_json(base_url, "/api/reset", method="POST", payload={})
    sock = _connect_websocket(_mint_token(api_key))
    events: list[str] = []
    agent_transcripts: list[str] = []
    pending_calls: list[dict[str, Any]] = []
    phase = "greeting"
    intent_transcript = ""
    approval_transcript = ""
    inspect_result: dict[str, Any] | None = None
    approval_result: dict[str, Any] | None = None
    final_reply_complete = False
    session_id_suffix = ""

    try:
        _send_frame(sock, json.dumps(_initial_config(), separators=(",", ":")).encode("utf-8"))
        deadline = time.monotonic() + 90

        while time.monotonic() < deadline:
            message = _recv_json(sock)
            if message is None:
                break
            event_type = str(message.get("type") or "unknown")
            events.append(event_type)

            if event_type == "session.ready":
                result["main_session"]["session_ready"] = True
                session_id = message.get("session_id")
                if isinstance(session_id, str):
                    session_id_suffix = session_id[-8:]

            elif event_type == "transcript.user":
                user_text = str(message.get("text") or "").strip()
                if phase in {"intent_input", "intent_reply"}:
                    intent_transcript = user_text
                    result["main_session"]["intent_transcript_text"] = user_text
                    result["main_session"]["intent_final_transcript"] = bool(user_text)
                    phase = "intent_reply"
                elif phase in {"approval_input", "approval_reply"}:
                    approval_transcript = user_text
                    result["main_session"]["approval_transcript_text"] = user_text
                    result["main_session"]["approval_final_transcript"] = bool(user_text)
                    phase = "approval_reply"

            elif event_type == "transcript.agent":
                agent_text = str(message.get("text") or "").strip()
                if agent_text:
                    agent_transcripts.append(agent_text)

            elif event_type == "tool.call":
                pending_calls.append(
                    {
                        "call_id": message.get("call_id"),
                        "name": message.get("name"),
                    }
                )

            elif event_type == "reply.audio":
                result["main_session"]["reply_audio_seen"] = True

            elif event_type == "reply.done":
                result["main_session"]["last_reply_status"] = message.get("status")

                if pending_calls:
                    calls = pending_calls[:]
                    pending_calls.clear()
                    for call in calls:
                        call_name = str(call.get("name") or "")
                        call_id = call.get("call_id")
                        if not isinstance(call_id, str) or not call_id:
                            raise RuntimeError("tool.call missing call_id")

                        if call_name == "inspect_and_propose_action":
                            if not intent_transcript:
                                raise RuntimeError("inspect tool requested before finalized intent transcript")
                            inspect_result = _http_json(
                                base_url,
                                "/api/tool/inspect-and-propose",
                                method="POST",
                                payload={"intent": intent_transcript},
                            )
                            result["main_session"]["inspect_tool_called"] = True
                            phase = "after_inspect_tool"
                            _send_frame(
                                sock,
                                json.dumps(_phase_update("approval"), separators=(",", ":")).encode("utf-8"),
                            )
                            _send_tool_result(sock, call_id, inspect_result)

                        elif call_name == "approve_pending_action":
                            if not approval_transcript:
                                raise RuntimeError("approval tool requested before finalized approval transcript")
                            approval_result = _http_json(
                                base_url,
                                "/api/tool/approve-pending",
                                method="POST",
                                payload={"authorization_phrase": approval_transcript},
                            )
                            result["main_session"]["approve_tool_called"] = True
                            phase = "after_approve_tool"
                            _send_frame(
                                sock,
                                json.dumps(_phase_update("complete"), separators=(",", ":")).encode("utf-8"),
                            )
                            _send_tool_result(sock, call_id, approval_result)
                        else:
                            raise RuntimeError(f"unexpected tool call: {call_name}")

                elif phase == "greeting" and result["main_session"]["session_ready"]:
                    phase = "intent_input"
                    _send_pcm_realtime(sock, intent_audio)

                elif phase == "after_inspect_tool":
                    phase = "approval_input"
                    _send_pcm_realtime(sock, approval_audio)

                elif phase == "after_approve_tool":
                    final_reply_complete = True
                    _send_frame(sock, b'{"type":"session.end"}')
                    phase = "ending"

                elif phase == "intent_reply":
                    raise RuntimeError("agent completed intent reply without calling inspect_and_propose_action")

                elif phase == "approval_reply":
                    raise RuntimeError("agent completed approval reply without calling approve_pending_action")

            elif event_type == "session.ended":
                result["main_session"]["session_ended"] = True
                break

            elif event_type == "session.error":
                raise RuntimeError(
                    f"main session error: {message.get('code')}: {message.get('message')}"
                )

        state = _http_json(base_url, "/api/state")
        evidence = _http_json(base_url, "/api/evidence")
        replay = _http_json(base_url, "/api/replay")
        action = state.get("action") if isinstance(state.get("action"), dict) else {}
        approval = state.get("approval") if isinstance(state.get("approval"), dict) else {}

        result["agent_transcripts"] = agent_transcripts
        result["main_session"]["session_id_suffix"] = session_id_suffix
        result["main_session"]["event_types"] = events[:120]
        result["main_session"]["intent_transcript"] = intent_transcript
        result["main_session"]["approval_transcript"] = approval_transcript
        result["governed_state"] = {
            "pending_approval": state.get("pending_approval"),
            "approval_approved": approval.get("approved"),
            "action_status": action.get("status"),
            "action_type": action.get("action_type"),
            "reasoning_mode": state.get("reasoning_mode"),
            "production_writes": state.get("production_writes"),
            "htr_present": bool(state.get("htr")),
            "evidence_events": len(evidence.get("events", []))
            if isinstance(evidence.get("events"), list)
            else 0,
            "replay_source": replay.get("replay_source"),
        }
        result["inspect_requires_approval"] = bool(
            inspect_result and inspect_result.get("requires_approval")
        )
        result["approval_action_created"] = bool(
            approval_result
            and isinstance(approval_result.get("action"), dict)
            and approval_result["action"].get("status") == "created"
        )
        result["final_reply_complete"] = final_reply_complete
        result["pass"] = bool(
            result["main_session"]["session_ready"]
            and result["main_session"]["intent_final_transcript"]
            and result["main_session"]["inspect_tool_called"]
            and result["main_session"]["approval_final_transcript"]
            and result["main_session"]["approve_tool_called"]
            and result["main_session"]["reply_audio_seen"]
            and final_reply_complete
            and state.get("pending_approval") is False
            and approval.get("approved") is True
            and action.get("status") == "created"
            and state.get("production_writes") is False
            and replay.get("replay_source") == "captured_evidence_only"
        )

    except Exception as exc:
        result["pass"] = False
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:600]
        result["agent_transcripts"] = agent_transcripts
        result["main_session"]["event_types"] = events[:120]
        try:
            _send_frame(sock, b'{"type":"session.end"}')
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
        result["elapsed_seconds"] = round(time.time() - started, 3)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AssemblyAI audio-to-governed-action live E2E smoke"
    )
    parser.add_argument(
        "--runtime-config",
        type=Path,
        default=Path("runtime/assemblyai.conf"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8791")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/live_e2e_result.json"),
    )
    args = parser.parse_args()
    result = run_live_e2e(config_path=args.runtime_config, base_url=args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result.get("pass") else 1)


if __name__ == "__main__":
    main()
