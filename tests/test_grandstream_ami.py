from __future__ import annotations

import hashlib

import pytest

from voiceops.adapters.grandstream_ami import (
    AMIAuthenticationError,
    AMIPermissionError,
    GrandstreamAMIAdapter,
)


class FakeSocket:
    def __init__(self, payload: bytes) -> None:
        self._payload = bytearray(payload)
        self.sent: list[bytes] = []
        self.timeout: float | None = None
        self.closed = False

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def recv(self, size: int) -> bytes:
        if not self._payload:
            return b""
        data = bytes(self._payload[:size])
        del self._payload[:size]
        return data

    def sendall(self, payload: bytes) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.closed = True


def factory_for(fake: FakeSocket):
    def factory(address: tuple[str, int], timeout: float) -> FakeSocket:
        assert address == ("192.168.1.6", 7777)
        assert timeout == 2.0
        return fake

    return factory


def test_probe_detects_verified_ami_banner_and_md5_challenge() -> None:
    fake = FakeSocket(
        b"Asterisk Call Manager/2.7.0\r\n"
        b"Response: Success\r\nActionID: x\r\nChallenge: 142923223\r\n\r\n"
    )
    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        port=7777,
        timeout_seconds=2.0,
        socket_factory=factory_for(fake),
    )

    result = adapter.probe()

    assert result.reachable is True
    assert result.banner == "Asterisk Call Manager/2.7.0"
    assert result.challenge_supported is True
    assert result.challenge == "142923223"
    assert b"Action: Challenge" in b"".join(fake.sent)
    assert b"Username:" not in b"".join(fake.sent)


def test_ping_uses_md5_login_without_sending_raw_secret() -> None:
    challenge = "246813579"
    secret = "not-a-real-production-secret"
    expected_key = hashlib.md5((challenge + secret).encode("utf-8"), usedforsecurity=False).hexdigest()
    fake = FakeSocket(
        b"Asterisk Call Manager/2.7.0\r\n"
        + f"Response: Success\r\nChallenge: {challenge}\r\n\r\n".encode()
        + b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n"
        + b"Response: Success\r\nPing: Pong\r\n\r\n"
    )
    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        port=7777,
        timeout_seconds=2.0,
        credential_loader=lambda: ("voiceops_readonly", secret),
        socket_factory=factory_for(fake),
    )

    response = adapter.ping()

    sent = b"".join(fake.sent).decode("utf-8")
    assert response["Response"] == "Success"
    assert response["Ping"] == "Pong"
    assert "Action: Challenge" in sent
    assert "Action: Login" in sent
    assert "AuthType: MD5" in sent
    assert "Username: voiceops_readonly" in sent
    assert f"Key: {expected_key}" in sent
    assert secret not in sent
    assert "Action: Ping" in sent


def test_extension_status_is_bounded_to_sipshowpeer() -> None:
    fake = FakeSocket(
        b"Asterisk Call Manager/2.7.0\r\n"
        b"Response: Success\r\nChallenge: 99\r\n\r\n"
        b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n"
        b"Response: Success\r\nChanneltype: SIP\r\nObjectName: 1000\r\nStatus: OK (12 ms)\r\n\r\n"
    )
    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        port=7777,
        timeout_seconds=2.0,
        credential_loader=lambda: ("readonly", "test-secret"),
        socket_factory=factory_for(fake),
    )

    result = adapter.extension_status("1000")

    sent = b"".join(fake.sent).decode("utf-8")
    assert result["ObjectName"] == "1000"
    assert result["Status"] == "OK (12 ms)"
    assert "Action: SIPshowpeer" in sent
    assert "Peer: 1000" in sent


def test_list_sip_peers_preserves_coalesced_ami_messages() -> None:
    fake = FakeSocket(
        b"Asterisk Call Manager/2.7.0\r\n"
        b"Response: Success\r\nChallenge: 777\r\n\r\n"
        b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n"
        b"Response: Success\r\nEventList: start\r\n\r\n"
        b"Event: PeerEntry\r\nObjectName: 1000\r\nStatus: OK (8 ms)\r\n\r\n"
        b"Event: PeerlistComplete\r\nListItems: 1\r\n\r\n"
    )
    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        port=7777,
        timeout_seconds=2.0,
        credential_loader=lambda: ("readonly", "test-secret"),
        socket_factory=factory_for(fake),
    )

    messages = adapter.list_sip_peers()

    assert len(messages) == 3
    assert messages[1]["Event"] == "PeerEntry"
    assert messages[1]["ObjectName"] == "1000"
    assert messages[2]["Event"] == "PeerlistComplete"


def test_mutating_ami_actions_are_fail_closed_before_connecting() -> None:
    called = False

    def socket_factory(address: tuple[str, int], timeout: float):
        nonlocal called
        called = True
        raise AssertionError("socket must not be opened for denied actions")

    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        socket_factory=socket_factory,
        credential_loader=lambda: ("readonly", "test-secret"),
    )

    with pytest.raises(AMIPermissionError):
        adapter.read_action("Originate", {"Channel": "SIP/1000"})

    with pytest.raises(AMIPermissionError):
        adapter.read_action("Command", {"Command": "sip show peers"})

    assert called is False


def test_missing_credentials_fail_closed() -> None:
    adapter = GrandstreamAMIAdapter(host="192.168.1.6", socket_factory=lambda *_: None)  # type: ignore[arg-type]
    with pytest.raises(AMIAuthenticationError):
        adapter.ping()


def test_extension_rejects_injection_characters() -> None:
    adapter = GrandstreamAMIAdapter(
        host="192.168.1.6",
        credential_loader=lambda: ("readonly", "test-secret"),
        socket_factory=lambda *_: None,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError):
        adapter.extension_status("1000\r\nAction: Originate")
