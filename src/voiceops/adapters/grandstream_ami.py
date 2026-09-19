from __future__ import annotations

import hashlib
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Callable


DEFAULT_AMI_PORT = 7777
READ_ONLY_ACTIONS = frozenset(
    {
        "Ping",
        "CoreStatus",
        "CoreSettings",
        "CoreShowChannels",
        "Status",
        "SIPshowpeer",
        "SIPpeers",
        "PJSIPShowEndpoint",
        "PJSIPShowEndpoints",
    }
)
LIST_TERMINATORS = {
    "CoreShowChannels": "CoreShowChannelsComplete",
    "Status": "StatusComplete",
    "SIPpeers": "PeerlistComplete",
    "PJSIPShowEndpoint": "EndpointDetailComplete",
    "PJSIPShowEndpoints": "EndpointListComplete",
}


class AMIError(RuntimeError):
    """Base error for the bounded Asterisk Manager Interface adapter."""


class AMIAuthenticationError(AMIError):
    """Raised when AMI authentication fails or credentials are unavailable."""


class AMIPermissionError(AMIError):
    """Raised when callers attempt an action outside the read-only allowlist."""


@dataclass(frozen=True)
class AMIProbeResult:
    host: str
    port: int
    reachable: bool
    banner: str | None
    challenge_supported: bool
    challenge: str | None = None
    error: str | None = None


CredentialLoader = Callable[[], tuple[str, str]]
SocketFactory = Callable[[tuple[str, int], float], socket.socket]


class GrandstreamAMIAdapter:
    """Fail-closed read-only AMI adapter for the legacy Grandstream UCM6104.

    The verified device exposes Asterisk Manager Interface on TCP 7777. This
    adapter deliberately excludes Originate, Command, Hangup, Redirect,
    configuration writes, transfers, and every other mutating AMI action.

    Credentials are resolved only when an authenticated method is called. A
    production deployment should provide ``credential_loader`` backed by a
    server-side vault. Environment variables remain a deployment fallback.
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        timeout_seconds: float = 3.0,
        credential_loader: CredentialLoader | None = None,
        socket_factory: SocketFactory | None = None,
    ) -> None:
        resolved_host = host or os.getenv("VOICEOPS_TELEPHONY_AMI_HOST", "").strip()
        if not resolved_host:
            raise ValueError("AMI host is required; set host or VOICEOPS_TELEPHONY_AMI_HOST")
        self.host = resolved_host
        self.port = int(port or os.getenv("VOICEOPS_TELEPHONY_AMI_PORT", DEFAULT_AMI_PORT))
        self.timeout_seconds = timeout_seconds
        self._credential_loader = credential_loader
        self._socket_factory = socket_factory or _default_socket_factory

    def probe(self) -> AMIProbeResult:
        """Verify reachability and MD5 challenge support without logging in."""

        try:
            with self._connect() as conn:
                buffer = bytearray()
                banner = self._read_banner(conn, buffer)
                action_id = self._action_id("challenge")
                self._send(
                    conn,
                    {
                        "Action": "Challenge",
                        "AuthType": "MD5",
                        "ActionID": action_id,
                    },
                )
                response = self._read_message(conn, buffer)
                challenge = response.get("Challenge")
                supported = response.get("Response") == "Success" and bool(challenge)
                return AMIProbeResult(
                    host=self.host,
                    port=self.port,
                    reachable=True,
                    banner=banner,
                    challenge_supported=supported,
                    challenge=challenge if supported else None,
                    error=None if supported else response.get("Message", "AMI challenge rejected"),
                )
        except (OSError, AMIError) as exc:
            return AMIProbeResult(
                host=self.host,
                port=self.port,
                reachable=False,
                banner=None,
                challenge_supported=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    def ping(self) -> dict[str, str]:
        messages = self.read_action("Ping")
        return messages[0] if messages else {}

    def core_status(self) -> dict[str, str]:
        messages = self.read_action("CoreStatus")
        return messages[0] if messages else {}

    def extension_status(self, extension: str) -> dict[str, str]:
        normalized = extension.strip()
        if not normalized or any(ch not in "0123456789*#" for ch in normalized):
            raise ValueError("extension must contain only dialable extension characters")
        messages = self.read_action("SIPshowpeer", {"Peer": normalized})
        return messages[0] if messages else {}

    def list_sip_peers(self) -> list[dict[str, str]]:
        return self.read_action("SIPpeers")

    def originate_internal_extension(
        self,
        extension: str,
        *,
        context: str | None = None,
        caller_id: str | None = None,
    ) -> dict[str, str]:
        """Ring an internal PBX extension via AMI Originate (opt-in only).

        Disabled unless ``VOICEOPS_TELEPHONY_ORIGINATE_ENABLED=true`` in the deployment env.
        """

        enabled = os.getenv("VOICEOPS_TELEPHONY_ORIGINATE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            raise AMIPermissionError("AMI Originate disabled; set VOICEOPS_TELEPHONY_ORIGINATE_ENABLED=true")

        normalized = extension.strip()
        if not normalized or any(ch not in "0123456789*#" for ch in normalized):
            raise ValueError("extension must contain only dialable extension characters")

        dial_context = (context or os.getenv("VOICEOPS_TELEPHONY_ORIGINATE_CONTEXT", "from-internal")).strip()
        agent_ext = os.getenv("VOICEOPS_TELEPHONY_AGENT_EXTENSION", "").strip()
        cid = caller_id or f'"InnerOS VoiceOps" <{agent_ext or "100"}>'

        channel_candidates: list[str] = []
        if agent_ext and agent_ext != normalized:
            channel_candidates.extend([f"SIP/{agent_ext}", f"PJSIP/{agent_ext}"])
        channel_candidates.extend(
            [
                f"Local/{normalized}@from-internal/n",
                f"PJSIP/{normalized}",
                f"SIP/{normalized}",
            ]
        )

        username, secret = self._credentials()
        with self._connect() as conn:
            buffer = bytearray()
            self._read_banner(conn, buffer)
            self._login_md5(conn, buffer, username, secret)
            errors: list[str] = []
            for channel in channel_candidates:
                action_id = self._action_id("originate")
                self._send(
                    conn,
                    {
                        "Action": "Originate",
                        "ActionID": action_id,
                        "Channel": channel,
                        "Context": dial_context,
                        "Exten": normalized,
                        "Priority": "1",
                        "CallerID": cid,
                        "Async": "true",
                    },
                )
                reply = self._read_message(conn, buffer)
                if reply.get("Response") == "Success":
                    reply["ChannelUsed"] = channel
                    return reply
                errors.append(f"{channel}: {reply.get('Message', 'failed')}")
            raise AMIError("; ".join(errors) or "AMI Originate failed")

    def read_action(
        self,
        action: str,
        fields: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Execute an explicitly allowlisted, read-only AMI action."""

        if action not in READ_ONLY_ACTIONS:
            raise AMIPermissionError(f"AMI action {action!r} is not in the read-only allowlist")
        clean_fields = {str(k): str(v) for k, v in (fields or {}).items()}
        forbidden_headers = {"Action", "ActionID", "Secret", "Key", "Username", "AuthType"}
        collision = forbidden_headers.intersection(clean_fields)
        if collision:
            raise AMIPermissionError(f"reserved AMI headers are not accepted: {sorted(collision)}")

        username, secret = self._credentials()
        with self._connect() as conn:
            buffer = bytearray()
            self._read_banner(conn, buffer)
            self._login_md5(conn, buffer, username, secret)
            action_id = self._action_id(action.lower())
            payload = {"Action": action, "ActionID": action_id, **clean_fields}
            self._send(conn, payload)
            messages = self._read_action_messages(
                conn,
                buffer,
                action_id=action_id,
                terminal_event=LIST_TERMINATORS.get(action),
            )
            if not messages:
                raise AMIError(f"AMI action {action} returned no response")
            first = messages[0]
            if first.get("Response") == "Error":
                raise AMIError(first.get("Message", f"AMI action {action} failed"))
            return messages

    def _credentials(self) -> tuple[str, str]:
        if self._credential_loader is not None:
            username, secret = self._credential_loader()
        else:
            username = os.getenv("VOICEOPS_TELEPHONY_AMI_USERNAME", "")
            secret = os.getenv("VOICEOPS_TELEPHONY_AMI_SECRET", "")
        if not username or not secret:
            raise AMIAuthenticationError(
                "AMI credentials are unavailable; provide a server-side credential loader or deployment secrets"
            )
        return username, secret

    def _connect(self) -> socket.socket:
        try:
            conn = self._socket_factory((self.host, self.port), self.timeout_seconds)
        except OSError as exc:
            raise AMIError(f"cannot connect to AMI at {self.host}:{self.port}") from exc
        conn.settimeout(self.timeout_seconds)
        return conn

    def _login_md5(
        self,
        conn: socket.socket,
        buffer: bytearray,
        username: str,
        secret: str,
    ) -> None:
        challenge_id = self._action_id("challenge")
        self._send(conn, {"Action": "Challenge", "AuthType": "MD5", "ActionID": challenge_id})
        challenge_reply = self._read_message(conn, buffer)
        challenge = challenge_reply.get("Challenge")
        if challenge_reply.get("Response") != "Success" or not challenge:
            raise AMIAuthenticationError(challenge_reply.get("Message", "AMI challenge failed"))

        key = hashlib.md5((challenge + secret).encode("utf-8"), usedforsecurity=False).hexdigest()
        login_id = self._action_id("login")
        self._send(
            conn,
            {
                "Action": "Login",
                "ActionID": login_id,
                "Username": username,
                "AuthType": "MD5",
                "Key": key,
                "Events": "off",
            },
        )
        reply = self._read_message(conn, buffer)
        if reply.get("Response") != "Success":
            raise AMIAuthenticationError(reply.get("Message", "AMI login failed"))

    def _read_action_messages(
        self,
        conn: socket.socket,
        buffer: bytearray,
        *,
        action_id: str,
        terminal_event: str | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        while True:
            message = self._read_message(conn, buffer)
            messages.append(message)
            if terminal_event:
                if message.get("Event") == terminal_event:
                    break
                continue
            if message.get("ActionID") == action_id or message.get("Response"):
                break
        return messages

    def _read_banner(self, conn: socket.socket, buffer: bytearray) -> str:
        data = self._recv_until(conn, buffer, b"\r\n")
        banner = data.decode("utf-8", "replace").strip()
        if not banner.startswith("Asterisk Call Manager/"):
            raise AMIError(f"unexpected AMI banner: {banner!r}")
        return banner

    def _read_message(self, conn: socket.socket, buffer: bytearray) -> dict[str, str]:
        raw = self._recv_until(conn, buffer, b"\r\n\r\n")
        text = raw.decode("utf-8", "replace")
        fields: dict[str, str] = {}
        for line in text.split("\r\n"):
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
        if not fields:
            raise AMIError("empty or malformed AMI response")
        return fields

    @staticmethod
    def _recv_until(
        conn: socket.socket,
        buffer: bytearray,
        delimiter: bytes,
        max_bytes: int = 1_048_576,
    ) -> bytes:
        while True:
            index = buffer.find(delimiter)
            if index >= 0:
                end = index + len(delimiter)
                data = bytes(buffer[:end])
                del buffer[:end]
                return data
            chunk = conn.recv(4096)
            if not chunk:
                raise AMIError("AMI connection closed before a complete message arrived")
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise AMIError("AMI response exceeded bounded read limit")

    @staticmethod
    def _send(conn: socket.socket, fields: dict[str, str]) -> None:
        payload = "\r\n".join(f"{key}: {value}" for key, value in fields.items()) + "\r\n\r\n"
        conn.sendall(payload.encode("utf-8"))

    @staticmethod
    def _action_id(prefix: str) -> str:
        return f"voiceops-{prefix}-{uuid.uuid4().hex[:12]}"


def _default_socket_factory(address: tuple[str, int], timeout: float) -> socket.socket:
    return socket.create_connection(address, timeout=timeout)
