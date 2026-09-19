from __future__ import annotations

import hashlib
import struct

import pytest

from voiceops.adapters.g711_rtp import (
    G711AssemblyAudioBridge,
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
    RtpPacket,
    alaw_to_pcm16,
    pcm16_to_alaw,
    pcm16_to_ulaw,
    ulaw_to_pcm16,
)
from voiceops.adapters.sip_transport import (
    DigestChallenge,
    GrandstreamSipClient,
    SipAuth,
    SipPolicyError,
    build_digest_authorization,
    parse_digest_challenge,
    parse_sdp_audio,
    parse_sip_message,
)


def _samples(blob: bytes) -> tuple[int, ...]:
    return struct.unpack("<" + "h" * (len(blob) // 2), blob)


def test_ulaw_known_silence_and_roundtrip() -> None:
    assert pcm16_to_ulaw(struct.pack("<h", 0)) == b"\xff"
    assert _samples(ulaw_to_pcm16(b"\xff")) == (0,)
    source = (-30000, -12000, -1000, 0, 1000, 12000, 30000)
    encoded = pcm16_to_ulaw(struct.pack("<" + "h" * len(source), *source))
    decoded = _samples(ulaw_to_pcm16(encoded))
    assert len(decoded) == len(source)
    assert max(abs(a - b) for a, b in zip(source, decoded)) < 1500


def test_alaw_known_silence_and_roundtrip() -> None:
    assert pcm16_to_alaw(struct.pack("<h", 0)) == b"\xd5"
    assert abs(_samples(alaw_to_pcm16(b"\xd5"))[0]) <= 8
    source = (-30000, -12000, -1000, 0, 1000, 12000, 30000)
    encoded = pcm16_to_alaw(struct.pack("<" + "h" * len(source), *source))
    decoded = _samples(alaw_to_pcm16(encoded))
    assert len(decoded) == len(source)
    assert max(abs(a - b) for a, b in zip(source, decoded)) < 2200


def test_rtp_packet_roundtrip_and_assemblyai_bridge() -> None:
    pcm8 = struct.pack("<" + "h" * 160, *([2000, -2000] * 80))
    ulaw = pcm16_to_ulaw(pcm8)
    packet = RtpPacket(PCMU_PAYLOAD_TYPE, 65535, 123456, 99, ulaw, True)
    wire = packet.to_bytes()
    parsed = RtpPacket.from_bytes(wire)
    assert parsed == packet

    bridge = G711AssemblyAudioBridge(outbound_payload_type=PCMU_PAYLOAD_TYPE, ssrc=7)
    pcm16k = bridge.decode_rtp_for_assemblyai(wire)
    assert pcm16k is not None
    assert len(pcm16k) == 640
    assert bridge.assemblyai_audio_contract == {
        "encoding": "pcm_s16le",
        "channels": 1,
        "sample_rate": 16000,
    }
    outgoing = RtpPacket.from_bytes(bridge.encode_assemblyai_pcm_for_rtp(pcm16k))
    assert outgoing.payload_type == PCMU_PAYLOAD_TYPE
    assert outgoing.ssrc == 7
    assert len(outgoing.payload) == 160


def test_bridge_supports_pcma_and_ignores_dtmf() -> None:
    bridge = G711AssemblyAudioBridge(outbound_payload_type=PCMA_PAYLOAD_TYPE, ssrc=8)
    pcm8 = struct.pack("<" + "h" * 160, *([500] * 160))
    packet = RtpPacket(PCMA_PAYLOAD_TYPE, 1, 10, 8, pcm16_to_alaw(pcm8)).to_bytes()
    assert len(bridge.decode_rtp_for_assemblyai(packet) or b"") == 640
    dtmf = RtpPacket(101, 2, 170, 8, b"\x01\x0a\x00\xa0").to_bytes()
    assert bridge.decode_rtp_for_assemblyai(dtmf) is None
    assert bridge.ignored_packets == 1


def test_parse_sip_digest_and_authorization() -> None:
    response = (
        "SIP/2.0 401 Unauthorized\r\n"
        "WWW-Authenticate: Digest realm=\"grandstream\", nonce=\"abcdef\", algorithm=MD5, qop=\"auth\"\r\n"
        "Content-Length: 0\r\n\r\n"
    )
    message = parse_sip_message(response)
    challenge = parse_digest_challenge(message)
    assert challenge == DigestChallenge("www-authenticate", "grandstream", "abcdef", "auth", "MD5", None)
    auth = SipAuth("1003", "unit-test-value")
    header = build_digest_authorization(
        challenge,
        method="REGISTER",
        uri="sip:192.168.1.6:4321",
        auth=auth,
        cnonce="0123456789abcdef",
    )
    ha1 = hashlib.md5(b"1003:grandstream:unit-test-value").hexdigest()
    ha2 = hashlib.md5(b"REGISTER:sip:192.168.1.6:4321").hexdigest()
    expected = hashlib.md5(f"{ha1}:abcdef:00000001:0123456789abcdef:auth:{ha2}".encode()).hexdigest()
    assert f'response="{expected}"' in header
    assert "unit-test-value" not in header
    assert "credential=" not in repr(auth)


def test_parse_sdp_audio_prefers_pcmu() -> None:
    sdp = (
        "v=0\r\n"
        "c=IN IP4 192.168.1.6\r\n"
        "m=audio 15000 RTP/AVP 0 8 101\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
    )
    endpoint = parse_sdp_audio(sdp)
    assert endpoint.host == "192.168.1.6"
    assert endpoint.port == 15000
    assert endpoint.preferred_g711_payload() == 0
    assert endpoint.codec_by_payload[101] == "TELEPHONE-EVENT"


class _FakeSocket:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = list(responses)
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.bound: tuple[str, int] | None = None
        self.closed = False

    def settimeout(self, _value: float) -> None:
        return None

    def bind(self, address: tuple[str, int]) -> None:
        self.bound = (address[0], 34000 if address[1] == 0 else address[1])

    def getsockname(self) -> tuple[str, int]:
        assert self.bound is not None
        return self.bound

    def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
        self.sent.append((payload, address))

    def recvfrom(self, _size: int) -> tuple[bytes, tuple[str, int]]:
        return self.responses.pop(0), ("192.168.1.6", 4321)

    def close(self) -> None:
        self.closed = True


def test_register_digest_401_to_200() -> None:
    unauthorized = (
        b"SIP/2.0 401 Unauthorized\r\n"
        b"CSeq: 1 REGISTER\r\n"
        b"WWW-Authenticate: Digest realm=\"grandstream\", nonce=\"n1\", algorithm=MD5, qop=\"auth\"\r\n"
        b"Content-Length: 0\r\n\r\n"
    )
    ok = b"SIP/2.0 200 OK\r\nCSeq: 2 REGISTER\r\nContent-Length: 0\r\n\r\n"
    fake = _FakeSocket([unauthorized, ok])
    client = GrandstreamSipClient(
        host="192.168.1.6",
        auth=SipAuth("1003", "unit-test-value"),
        local_ip="192.168.1.4",
        socket_factory=lambda *_args: fake,
    )
    result = client.register()
    assert result.status_code == 200
    assert len(fake.sent) == 2
    assert b"Authorization: Digest" in fake.sent[1][0]
    assert b"unit-test-value" not in fake.sent[1][0]
    client.close()
    assert fake.closed


def test_invite_is_policy_gated_and_uses_verified_dial_string() -> None:
    fake = _FakeSocket([])
    client = GrandstreamSipClient(
        host="192.168.1.6",
        auth=SipAuth("1003", "unit-test-value"),
        local_ip="192.168.1.4",
        socket_factory=lambda *_args: fake,
    )
    with pytest.raises(SipPolicyError):
        client.create_invite_dialog(
            "0991234567",
            explicit_user_request=True,
            route_verified=False,
            pbx_dial_string="0991234567",
            rtp_port=18000,
        )
    decision, dialog, payload = client.create_invite_dialog(
        "1001",
        explicit_user_request=True,
        route_verified=True,
        pbx_dial_string="1001",
        rtp_port=18000,
    )
    assert decision.execution_ready
    assert dialog.remote_uri == "sip:1001@192.168.1.6:4321"
    assert payload.startswith(b"INVITE sip:1001@192.168.1.6:4321 SIP/2.0")
    assert b"m=audio 18000 RTP/AVP 0 8 101" in payload
