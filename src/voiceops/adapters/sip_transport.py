from __future__ import annotations

import hashlib
import secrets
import socket
import time
from dataclasses import dataclass, field
from typing import Callable

from voiceops.telephony_policy import DialDecision, authorize_call

DEFAULT_SIP_PORT = 4321


class SipError(RuntimeError):
    pass


class SipAuthenticationError(SipError):
    pass


class SipProtocolError(SipError):
    pass


class SipPolicyError(SipError):
    pass


@dataclass(frozen=True, slots=True)
class SipAuth:
    extension: str
    credential: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.extension or not self.extension.isdigit():
            raise ValueError("extension must contain digits only")
        if not self.credential:
            raise ValueError("credential must not be empty")


@dataclass(frozen=True, slots=True)
class DigestChallenge:
    header_name: str
    realm: str
    nonce: str
    qop: str | None = None
    algorithm: str = "MD5"
    opaque: str | None = None


@dataclass(frozen=True, slots=True)
class SipMessage:
    start_line: str
    headers: dict[str, str]
    body: bytes

    @property
    def status_code(self) -> int | None:
        if not self.start_line.startswith("SIP/2.0 "):
            return None
        try:
            return int(self.start_line.split(" ", 2)[1])
        except (IndexError, ValueError):
            return None

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)


@dataclass(frozen=True, slots=True)
class SdpAudioEndpoint:
    host: str
    port: int
    payload_types: tuple[int, ...]
    codec_by_payload: dict[int, str]

    def preferred_g711_payload(self) -> int:
        if 0 in self.payload_types:
            return 0
        if 8 in self.payload_types:
            return 8
        raise SipProtocolError("remote SDP does not offer PCMU or PCMA")


@dataclass(slots=True)
class SipDialog:
    call_id: str
    from_tag: str
    local_uri: str
    remote_uri: str
    remote_target: str
    cseq: int
    to_header: str = ""
    established: bool = False


def parse_sip_message(data: bytes | str) -> SipMessage:
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    head, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        raise SipProtocolError("SIP message is missing header terminator")
    lines = head.decode("utf-8", "replace").split("\r\n")
    if not lines or not lines[0].strip():
        raise SipProtocolError("SIP message has no start line")
    headers: dict[str, str] = {}
    current_name: str | None = None
    for line in lines[1:]:
        if line[:1] in {" ", "\t"} and current_name:
            headers[current_name] += " " + line.strip()
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        current_name = name.strip().lower()
        value = value.strip()
        headers[current_name] = headers.get(current_name, "") + ((", " if current_name in headers else "") + value)
    if headers.get("content-length"):
        try:
            body = body[: int(headers["content-length"])]
        except ValueError as exc:
            raise SipProtocolError("invalid SIP Content-Length") from exc
    return SipMessage(lines[0].strip(), headers, body)


def parse_digest_challenge(message: SipMessage) -> DigestChallenge:
    header_name, value = "", ""
    for candidate in ("proxy-authenticate", "www-authenticate"):
        value = message.header(candidate)
        if value:
            header_name = candidate
            break
    if not value or not value.lower().startswith("digest "):
        raise SipAuthenticationError("SIP response does not contain a Digest challenge")
    fields: list[str] = []
    token, quoted = "", False
    for char in value[7:]:
        if char == '"':
            quoted = not quoted
        if char == "," and not quoted:
            fields.append(token)
            token = ""
        else:
            token += char
    if token:
        fields.append(token)
    parts: dict[str, str] = {}
    for item in fields:
        if "=" in item:
            key, raw_value = item.split("=", 1)
            parts[key.strip().lower()] = raw_value.strip().strip('"')
    realm, nonce = parts.get("realm", ""), parts.get("nonce", "")
    if not realm or not nonce:
        raise SipAuthenticationError("Digest challenge is missing realm or nonce")
    algorithm = parts.get("algorithm", "MD5")
    if algorithm.upper() != "MD5":
        raise SipAuthenticationError(f"unsupported SIP digest algorithm {algorithm!r}")
    qop = parts.get("qop")
    if qop:
        offered = [item.strip() for item in qop.split(",")]
        qop = "auth" if "auth" in offered else offered[0]
    return DigestChallenge(header_name, realm, nonce, qop, algorithm, parts.get("opaque"))


def build_digest_authorization(
    challenge: DigestChallenge,
    *,
    method: str,
    uri: str,
    auth: SipAuth,
    nonce_count: int = 1,
    cnonce: str | None = None,
) -> str:
    method = method.upper().strip()
    if not method or not uri:
        raise ValueError("method and uri are required")
    cnonce = cnonce or secrets.token_hex(8)
    ha1 = _md5_hex(f"{auth.extension}:{challenge.realm}:{auth.credential}")
    ha2 = _md5_hex(f"{method}:{uri}")
    params = [f'username="{auth.extension}"', f'realm="{challenge.realm}"', f'nonce="{challenge.nonce}"', f'uri="{uri}"']
    if challenge.qop:
        nc = f"{nonce_count:08x}"
        response = _md5_hex(f"{ha1}:{challenge.nonce}:{nc}:{cnonce}:{challenge.qop}:{ha2}")
        params += [f'response="{response}"', "algorithm=MD5", f"qop={challenge.qop}", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        response = _md5_hex(f"{ha1}:{challenge.nonce}:{ha2}")
        params += [f'response="{response}"', "algorithm=MD5"]
    if challenge.opaque:
        params.append(f'opaque="{challenge.opaque}"')
    name = "Proxy-Authorization" if challenge.header_name == "proxy-authenticate" else "Authorization"
    return f"{name}: Digest " + ", ".join(params)


def parse_sdp_audio(body: bytes | str) -> SdpAudioEndpoint:
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    host = ""
    audio_port: int | None = None
    payloads: tuple[int, ...] = ()
    codecs: dict[int, str] = {0: "PCMU", 8: "PCMA"}
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if line.startswith("c=IN IP4 "):
            host = line[len("c=IN IP4 ") :].strip()
        elif line.startswith("m=audio "):
            parts = line.split()
            if len(parts) < 4:
                raise SipProtocolError("malformed SDP audio media line")
            try:
                audio_port = int(parts[1])
                payloads = tuple(int(value) for value in parts[3:])
            except ValueError as exc:
                raise SipProtocolError("non-numeric SDP audio port or payload type") from exc
        elif line.lower().startswith("a=rtpmap:"):
            mapping = line[len("a=rtpmap:") :].split(None, 1)
            if len(mapping) == 2:
                try:
                    codecs[int(mapping[0])] = mapping[1].split("/", 1)[0].upper()
                except ValueError:
                    pass
    if not host or audio_port is None:
        raise SipProtocolError("SDP is missing IPv4 connection or audio media endpoint")
    return SdpAudioEndpoint(host, audio_port, payloads, codecs)


class GrandstreamSipClient:
    """Bounded SIP UA that relies on the existing VoiceOps call policy."""

    def __init__(self, *, host: str, auth: SipAuth, local_ip: str, sip_port: int = DEFAULT_SIP_PORT, timeout_seconds: float = 4.0, socket_factory: Callable[..., socket.socket] = socket.socket) -> None:
        self.host = host
        self.sip_port = int(sip_port)
        self.auth = auth
        self.local_ip = local_ip
        self.timeout_seconds = timeout_seconds
        self._socket_factory = socket_factory
        self._sip_socket: socket.socket | None = None
        self._local_port: int | None = None
        self._registration_call_id = f"voiceops-{secrets.token_hex(10)}@{local_ip}"
        self._registration_tag = secrets.token_hex(6)
        self._registration_cseq = 0

    @property
    def local_port(self) -> int:
        if self._local_port is None:
            raise SipError("client is not bound")
        return self._local_port

    def bind(self) -> None:
        if self._sip_socket is not None:
            return
        sock = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_seconds)
        sock.bind((self.local_ip, 0))
        self._sip_socket = sock
        self._local_port = int(sock.getsockname()[1])

    def close(self) -> None:
        if self._sip_socket is not None:
            self._sip_socket.close()
            self._sip_socket = None
            self._local_port = None

    def register(self, *, expires: int = 120) -> SipMessage:
        if not 30 <= expires <= 3600:
            raise ValueError("registration expiry must be between 30 and 3600 seconds")
        self.bind()
        uri = f"sip:{self.host}:{self.sip_port}"
        self._registration_cseq += 1
        first_cseq = self._registration_cseq
        first = self._send_and_receive(
            self._build_register(uri, first_cseq, expires),
            expected_cseq=first_cseq,
            expected_method="REGISTER",
        )
        if first.status_code == 200:
            return first
        if first.status_code not in {401, 407}:
            raise SipAuthenticationError(
                f"REGISTER challenge failed with status {first.status_code} ({first.start_line})"
            )
        challenge = parse_digest_challenge(first)
        self._registration_cseq += 1
        auth_cseq = self._registration_cseq
        authorization = build_digest_authorization(challenge, method="REGISTER", uri=uri, auth=self.auth)
        second = self._send_and_receive(
            self._build_register(uri, auth_cseq, expires, authorization),
            expected_cseq=auth_cseq,
            expected_method="REGISTER",
        )
        if second.status_code != 200:
            raise SipAuthenticationError(
                f"REGISTER authentication failed with status {second.status_code} ({second.start_line})"
            )
        return second

    def dial_decision(self, target: str, *, explicit_user_request: bool, route_verified: bool, pbx_dial_string: str | None, allowlisted_autonomous_target: bool = False) -> DialDecision:
        decision = authorize_call(target, explicit_user_request=explicit_user_request, allowlisted_autonomous_target=allowlisted_autonomous_target, route_verified=route_verified, pbx_dial_string=pbx_dial_string)
        if not decision.allowed or not decision.execution_ready or not decision.pbx_dial_string:
            raise SipPolicyError(decision.reason)
        return decision

    def create_invite_dialog(self, target: str, *, explicit_user_request: bool, route_verified: bool, pbx_dial_string: str, rtp_port: int, allowlisted_autonomous_target: bool = False) -> tuple[DialDecision, SipDialog, bytes]:
        self.bind()
        if not 1 <= rtp_port <= 65535:
            raise ValueError("rtp_port must be 1..65535")
        decision = self.dial_decision(target, explicit_user_request=explicit_user_request, allowlisted_autonomous_target=allowlisted_autonomous_target, route_verified=route_verified, pbx_dial_string=pbx_dial_string)
        remote_uri = f"sip:{decision.pbx_dial_string}@{self.host}:{self.sip_port}"
        dialog = SipDialog(f"voiceops-{secrets.token_hex(10)}@{self.local_ip}", secrets.token_hex(6), f"sip:{self.auth.extension}@{self.host}", remote_uri, remote_uri, 1)
        return decision, dialog, self._build_invite(dialog, rtp_port)

    def _build_register(self, uri: str, cseq: int, expires: int, authorization: str = "") -> bytes:
        lines = [f"REGISTER {uri} SIP/2.0", f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};branch=z9hG4bK{secrets.token_hex(8)};rport", "Max-Forwards: 70", f"From: <sip:{self.auth.extension}@{self.host}>;tag={self._registration_tag}", f"To: <sip:{self.auth.extension}@{self.host}>", f"Call-ID: {self._registration_call_id}", f"CSeq: {cseq} REGISTER", f"Contact: <sip:{self.auth.extension}@{self.local_ip}:{self.local_port}>", f"Expires: {expires}", "User-Agent: InnerOS-VoiceOps/1.0"]
        if authorization:
            lines.append(authorization)
        return "\r\n".join(lines + ["Content-Length: 0", "", ""]).encode()

    def _build_invite(self, dialog: SipDialog, rtp_port: int, authorization: str = "") -> bytes:
        sdp = "\r\n".join(["v=0", f"o=- 1 1 IN IP4 {self.local_ip}", "s=InnerOS VoiceOps", f"c=IN IP4 {self.local_ip}", "t=0 0", f"m=audio {rtp_port} RTP/AVP 0 8 101", "a=rtpmap:0 PCMU/8000", "a=rtpmap:8 PCMA/8000", "a=rtpmap:101 telephone-event/8000", "a=fmtp:101 0-16", "a=sendrecv", ""]).encode()
        lines = [f"INVITE {dialog.remote_uri} SIP/2.0", f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};branch=z9hG4bK{secrets.token_hex(8)};rport", "Max-Forwards: 70", f"From: \"Ralphi VoiceOps\" <{dialog.local_uri}>;tag={dialog.from_tag}", f"To: <{dialog.remote_uri}>", f"Call-ID: {dialog.call_id}", f"CSeq: {dialog.cseq} INVITE", f"Contact: <sip:{self.auth.extension}@{self.local_ip}:{self.local_port}>", "Allow: INVITE, ACK, CANCEL, BYE, OPTIONS", "Content-Type: application/sdp"]
        if authorization:
            lines.append(authorization)
        return "\r\n".join(lines + [f"Content-Length: {len(sdp)}", "", ""]).encode() + sdp

    def invite_extension(
        self,
        target: str,
        rtp_port: int,
        *,
        timeout_seconds: float = 45.0,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[SipDialog, SdpAudioEndpoint]:
        """Place an authenticated INVITE to an internal extension and wait for 200 OK."""
        self.register()
        _decision, dialog, payload = self.create_invite_dialog(
            target,
            explicit_user_request=True,
            route_verified=True,
            pbx_dial_string=target,
            rtp_port=rtp_port,
        )
        invite_cseq = dialog.cseq
        deadline = time.monotonic() + timeout_seconds
        auth_sent = False
        if self._sip_socket is None:
            raise SipError("client is not bound")
        self._sip_socket.sendto(payload, (self.host, self.sip_port))
        while time.monotonic() < deadline:
            if should_cancel and should_cancel():
                self.send_cancel_invite(dialog, invite_cseq)
                raise SipError("call cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._sip_socket.settimeout(min(1.0, remaining))
            try:
                data, _ = self._sip_socket.recvfrom(65535)
            except socket.timeout:
                continue
            message = parse_sip_message(data)
            code = message.status_code
            if code in {100, 180, 183}:
                continue
            if code in {401, 407} and not auth_sent:
                challenge = parse_digest_challenge(message)
                dialog.cseq += 1
                invite_cseq = dialog.cseq
                authorization = build_digest_authorization(
                    challenge,
                    method="INVITE",
                    uri=dialog.remote_uri,
                    auth=self.auth,
                )
                payload = self._build_invite(dialog, rtp_port, authorization)
                self._sip_socket.sendto(payload, (self.host, self.sip_port))
                auth_sent = True
                continue
            if code == 200:
                remote = parse_sdp_audio(message.body)
                dialog.to_header = message.header("to") or f"<{dialog.remote_uri}>"
                dialog.established = True
                self._send_ack(dialog)
                return dialog, remote
            if code is not None and code >= 400:
                raise SipError(message.header("reason") or message.start_line)
        self.send_cancel_invite(dialog, invite_cseq)
        raise SipError(f"INVITE to {target} timed out")

    def _send_ack(self, dialog: SipDialog) -> None:
        if self._sip_socket is None:
            raise SipError("client is not bound")
        to_header = dialog.to_header or f"<{dialog.remote_uri}>"
        lines = [
            f"ACK {dialog.remote_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};branch=z9hG4bK{secrets.token_hex(8)};rport",
            "Max-Forwards: 70",
            f"From: \"InnerOS VoiceOps\" <{dialog.local_uri}>;tag={dialog.from_tag}",
            f"To: {to_header}",
            f"Call-ID: {dialog.call_id}",
            f"CSeq: {dialog.cseq} ACK",
            f"Contact: <sip:{self.auth.extension}@{self.local_ip}:{self.local_port}>",
            "Content-Length: 0",
            "",
            "",
        ]
        self._sip_socket.sendto("\r\n".join(lines).encode("utf-8"), (self.host, self.sip_port))

    def send_cancel_invite(self, dialog: SipDialog, invite_cseq: int) -> None:
        if self._sip_socket is None:
            return
        to_header = dialog.to_header or f"<{dialog.remote_uri}>"
        lines = [
            f"CANCEL {dialog.remote_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};branch=z9hG4bK{secrets.token_hex(8)};rport",
            "Max-Forwards: 70",
            f"From: \"InnerOS VoiceOps\" <{dialog.local_uri}>;tag={dialog.from_tag}",
            f"To: {to_header}",
            f"Call-ID: {dialog.call_id}",
            f"CSeq: {invite_cseq} CANCEL",
            f"Contact: <sip:{self.auth.extension}@{self.local_ip}:{self.local_port}>",
            "Content-Length: 0",
            "",
            "",
        ]
        self._sip_socket.sendto("\r\n".join(lines).encode("utf-8"), (self.host, self.sip_port))

    def send_bye(self, dialog: SipDialog) -> None:
        if self._sip_socket is None or not dialog.established:
            return
        dialog.cseq += 1
        to_header = dialog.to_header or f"<{dialog.remote_uri}>"
        lines = [
            f"BYE {dialog.remote_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};branch=z9hG4bK{secrets.token_hex(8)};rport",
            "Max-Forwards: 70",
            f"From: \"InnerOS VoiceOps\" <{dialog.local_uri}>;tag={dialog.from_tag}",
            f"To: {to_header}",
            f"Call-ID: {dialog.call_id}",
            f"CSeq: {dialog.cseq} BYE",
            "Content-Length: 0",
            "",
            "",
        ]
        self._sip_socket.sendto("\r\n".join(lines).encode("utf-8"), (self.host, self.sip_port))

    def _send_and_receive(
        self,
        payload: bytes,
        *,
        expected_cseq: int | None = None,
        expected_method: str | None = None,
        timeout_seconds: float | None = None,
    ) -> SipMessage:
        if self._sip_socket is None:
            raise SipError("client is not bound")
        self._sip_socket.sendto(payload, (self.host, self.sip_port))
        deadline = time.monotonic() + (timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            self._sip_socket.settimeout(max(0.05, min(1.0, remaining)))
            try:
                data, _ = self._sip_socket.recvfrom(65535)
            except socket.timeout:
                continue
            message = parse_sip_message(data)
            if expected_cseq is None or expected_method is None:
                return message
            cseq_header = message.header("cseq")
            if not cseq_header:
                continue
            parts = cseq_header.split()
            if len(parts) < 2:
                continue
            try:
                cseq_num = int(parts[0])
            except ValueError:
                continue
            if cseq_num == expected_cseq and parts[1].upper() == expected_method.upper():
                return message
        raise SipError(f"SIP {expected_method or 'request'} timed out waiting for response")


def _md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8"), usedforsecurity=False).hexdigest()
