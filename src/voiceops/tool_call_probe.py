from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from voiceops.live_e2e_smoke import _recv_json, _send_pcm_realtime, _synthesize_fixture  # noqa: E402
from voiceops.provider_smoke import _connect_websocket, _load_runtime_api_key, _mint_token, _send_frame  # noqa: E402


def run_probe(config_path: Path) -> dict[str, object]:
    started = time.time()
    result: dict[str, object] = {
        "provider": "assemblyai",
        "probe": "single_client_tool",
        "session_ready": False,
        "user_transcript": "",
        "tool_called": False,
        "tool_name": "",
        "reply_done": False,
        "session_ended": False,
        "production_writes": False,
    }
    api_key = _load_runtime_api_key(config_path)
    audio, fixture = _synthesize_fixture(api_key, "Usa la herramienta ping ahora.")
    result["fixture_audio_bytes"] = fixture.get("audio_bytes")
    sock = _connect_websocket(_mint_token(api_key))
    events: list[str] = []
    pending_call_id = ""
    try:
        config = {
            "type": "session.update",
            "session": {
                "system_prompt": (
                    "Eres un agente de prueba. Para CUALQUIER mensaje del usuario debes llamar a ping_tool. "
                    "No respondas al contenido por tu cuenta. Cuando en duda, llama la herramienta. "
                    "Ejemplo: Usuario: 'usa la herramienta'. Tú: [call ping_tool]."
                ),
                "greeting": "Prueba de herramienta lista.",
                "output": {"voice": "anna", "format": {"encoding": "audio/pcm"}},
                "input": {"format": {"encoding": "audio/pcm"}},
                "tools": [
                    {
                        "type": "function",
                        "name": "ping_tool",
                        "description": (
                            "Call this tool for every user turn, especially when the user asks to use, test, call, "
                            "invoke, or execute a tool. Do not answer such requests without calling it."
                        ),
                        "parameters": {"type": "object", "properties": {}, "required": []},
                        "execution_mode": "interactive",
                    }
                ],
            },
        }
        _send_frame(sock, json.dumps(config, separators=(",", ":")).encode("utf-8"))
        phase = "greeting"
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            message = _recv_json(sock)
            if message is None:
                break
            event_type = str(message.get("type") or "unknown")
            events.append(event_type)
            if event_type == "session.ready":
                result["session_ready"] = True
            elif event_type == "transcript.user":
                result["user_transcript"] = str(message.get("text") or "")
            elif event_type == "tool.call":
                result["tool_called"] = True
                result["tool_name"] = str(message.get("name") or "")
                call_id = message.get("call_id")
                if isinstance(call_id, str):
                    pending_call_id = call_id
            elif event_type == "reply.done":
                result["reply_done"] = True
                if phase == "greeting":
                    phase = "user"
                    _send_pcm_realtime(sock, audio)
                elif pending_call_id:
                    _send_frame(
                        sock,
                        json.dumps(
                            {"type": "tool.result", "call_id": pending_call_id, "result": '{"ok":true,"pong":true}'},
                            separators=(",", ":"),
                        ).encode("utf-8"),
                    )
                    pending_call_id = ""
                    phase = "tool_result"
                elif phase == "tool_result":
                    _send_frame(sock, b'{"type":"session.end"}')
                    phase = "ending"
            elif event_type == "session.ended":
                result["session_ended"] = True
                break
            elif event_type == "session.error":
                result["provider_error_code"] = message.get("code")
                result["provider_error_message"] = message.get("message")
                break
        result["event_types"] = events[:80]
        result["pass"] = bool(
            result["session_ready"]
            and result["user_transcript"]
            and result["tool_called"]
            and result["tool_name"] == "ping_tool"
        )
        if result["session_ready"] and not result["session_ended"]:
            try:
                _send_frame(sock, b'{"type":"session.end"}')
            except Exception:
                pass
    except Exception as exc:
        result["pass"] = False
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:500]
        result["event_types"] = events[:80]
    finally:
        try:
            sock.close()
        except Exception:
            pass
        result["elapsed_seconds"] = round(time.time() - started, 3)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal AssemblyAI client-side tool-call probe")
    parser.add_argument("--runtime-config", type=Path, default=Path("runtime/assemblyai.conf"))
    parser.add_argument("--output", type=Path, default=Path("runtime/tool_call_probe_result.json"))
    args = parser.parse_args()
    result = run_probe(args.runtime_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result.get("pass") else 1)


if __name__ == "__main__":
    main()
