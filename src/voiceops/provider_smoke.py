from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

HOST = "agents.assemblyai.com"
PORT = 443
TOKEN_URL = "https://agents.assemblyai.com/v1/token"


def _load_runtime_api_key(config_path: Path) -> str:
    env_key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    if env_key:
        return env_key
    if not config_path.exists():
        raise RuntimeError("AssemblyAI credential is not available in environment or runtime config")
    for line in config_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASSEMBLYAI_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise RuntimeError("AssemblyAI credential is missing from runtime config")


def _mint_token(api_key: str) -> str:
    url = TOKEN_URL + "?" + urlencode({"expires_in_seconds": 120})
    request = Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("AssemblyAI temporary token response did not contain a token")
    return token


def _recv_exact(sock: ssl.SSLSocket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("websocket closed unexpectedly")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _send_frame(sock: ssl.SSLSocket, payload: bytes, opcode: int = 0x1) -> None:
    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length <= 0xFFFF:
        header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked)


def _recv_frame(sock: ssl.SSLSocket) -> tuple[int, bytes]:
    head = _recv_exact(sock, 2)
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def _connect_websocket(token: str) -> ssl.SSLSocket:
    raw = socket.create_connection((HOST, PORT), timeout=10)
    context = ssl.create_default_context()
    sock = context.wrap_socket(raw, server_hostname=HOST)
    sock.settimeout(15)
    websocket_key = base64.b64encode(os.urandom(16)).decode("ascii")
    path = "/v1/ws?token=" + quote(token, safe="")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {websocket_key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "User-Agent: InnerOS-VoiceOps-Smoke/1.0\r\n\r\n"
    ).encode("ascii")
    sock.sendall(request)
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
        if len(response) > 65536:
            raise RuntimeError("oversized websocket handshake")
    header_blob, leftover = response.split(b"\r\n\r\n", 1)
    status_line = header_blob.split(b"\r\n", 1)[0].decode("latin1")
    if " 101 " not in status_line:
        raise RuntimeError(f"websocket upgrade failed: {status_line}")
    headers: dict[str, str] = {}
    for line in header_blob.split(b"\r\n")[1:]:
        if b":" in line:
            key, value = line.split(b":", 1)
            headers[key.decode("latin1").strip().lower()] = value.decode("latin1").strip()
    expected = base64.b64encode(
        hashlib.sha1(
            (websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        ).digest()
    ).decode("ascii")
    if headers.get("sec-websocket-accept") != expected:
        raise RuntimeError("invalid websocket accept header")
    if leftover:
        raise RuntimeError("unexpected buffered websocket frame after handshake")
    return sock


def run_voice_agent_smoke(config_path: Path) -> dict[str, object]:
    started = time.time()
    result: dict[str, object] = {
        "provider": "assemblyai",
        "surface": "voice_agent_api",
        "token_minted": False,
        "websocket_upgraded": False,
        "session_ready": False,
        "greeting_transcript": False,
        "reply_audio_seen": False,
        "reply_done": False,
        "session_ended": False,
        "event_types": [],
        "production_writes": False,
    }
    sock: ssl.SSLSocket | None = None
    try:
        token = _mint_token(_load_runtime_api_key(config_path))
        result["token_minted"] = True
        sock = _connect_websocket(token)
        result["websocket_upgraded"] = True
        configuration = {
            "type": "session.update",
            "session": {
                "system_prompt": "You are a protocol validation agent for InnerOS VoiceOps. Keep replies brief.",
                "greeting": "InnerOS VoiceOps protocol smoke is online.",
                "output": {"voice": "anna", "format": {"encoding": "audio/pcm"}},
                "input": {"format": {"encoding": "audio/pcm"}},
                "tools": [],
            },
        }
        _send_frame(sock, json.dumps(configuration, separators=(",", ":")).encode("utf-8"))
        events: list[str] = []
        deadline = time.monotonic() + 15
        requested_end = False
        while time.monotonic() < deadline:
            opcode, payload = _recv_frame(sock)
            if opcode == 0x9:
                _send_frame(sock, payload, opcode=0xA)
                continue
            if opcode == 0x8:
                break
            if opcode != 0x1:
                continue
            message = json.loads(payload.decode("utf-8"))
            event_type = str(message.get("type") or "unknown")
            events.append(event_type)
            if event_type == "session.ready":
                result["session_ready"] = True
                session_id = message.get("session_id")
                if isinstance(session_id, str):
                    result["session_id_suffix"] = session_id[-8:]
            elif event_type == "transcript.agent":
                result["greeting_transcript"] = True
            elif event_type == "reply.audio":
                result["reply_audio_seen"] = True
            elif event_type == "reply.done":
                result["reply_done"] = True
                if result["session_ready"] and not requested_end:
                    _send_frame(sock, b'{"type":"session.end"}')
                    requested_end = True
            elif event_type == "session.ended":
                result["session_ended"] = True
                break
            elif event_type == "session.error":
                result["provider_error_code"] = message.get("code")
                result["provider_error_message"] = message.get("message")
                break
        if result["session_ready"] and not requested_end:
            _send_frame(sock, b'{"type":"session.end"}')
        result["event_types"] = events[:40]
        result["pass"] = bool(
            result["token_minted"]
            and result["websocket_upgraded"]
            and result["session_ready"]
        )
    except Exception as exc:
        result["pass"] = False
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)[:500]
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        result["elapsed_seconds"] = round(time.time() - started, 3)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitized live AssemblyAI Voice Agent protocol smoke")
    parser.add_argument("--runtime-config", type=Path, default=Path("runtime/assemblyai.conf"))
    parser.add_argument("--output", type=Path, default=Path("runtime/ws_smoke_result.json"))
    args = parser.parse_args()
    result = run_voice_agent_smoke(args.runtime_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result.get("pass") else 1)


if __name__ == "__main__":
    main()
