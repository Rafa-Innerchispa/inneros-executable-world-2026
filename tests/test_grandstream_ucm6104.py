from __future__ import annotations

import hashlib

import pytest

from voiceops.adapters.grandstream_ucm6104 import (
    GrandstreamUCM6104ReadOnlyCGI,
    SIPGeneralSettings,
    UCM6104AuthenticationError,
    UCM6104ProtocolError,
    UCM6104ReadOnlyViolation,
)


class FakeCGI:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.responses: dict[str, dict] = {
            "challenge": {"status": 0, "response": {"challenge": "abc123"}},
            "login": {"status": 0, "response": {"cookie": "session-cookie-secret"}},
            "logout": {"status": 0, "response": {}},
            "getSIPGenSettings": {
                "status": 0,
                "response": {
                    "sip_general_settings": {
                        "realm": "ucm6104",
                        "bindport": "4321",
                        "bindaddr": "0.0.0.0",
                        "bindaddr6": "::",
                        "allowguest": "no",
                        "allowtransfer": "yes",
                        "mwi_from": "",
                        "enable_diversion": "yes",
                    }
                },
            },
            "getSIPMiscSettings": {"status": 0, "response": {"sip_misc_settings": {"videosupport": "no"}}},
            "getSIPSSTimerSettings": {
                "status": 0,
                "response": {"sip_sessiontimer_settings": {"session_expires": "1800"}},
            },
            "getSIPTCPSettings": {"status": 0, "response": {"sip_tcp_settings": {"tcpenable": "no"}}},
            "getSIPNATSettings": {"status": 0, "response": {"sip_nat_settings": {"externudpport": "4321"}}},
            "getTOSSettings": {"status": 0, "response": {"tos_settings": {"tos_sip": "cs3"}}},
            "getRTPSettings": {
                "status": 0,
                "response": {"rtp_settings": {"rtpstart": "10000", "rtpend": "20000"}},
            },
            "getPayloadSettings": {
                "status": 0,
                "response": {"payload_settings": {"fixture": "read-only"}},
            },
            "getBackupSettings": {
                "status": 0,
                "response": {"type": {"config": "yes", "cdr": "yes"}},
            },
            "getUpgradeValue": {
                "status": 0,
                "response": {"upgrade-via": "http", "firmware-server-path": ""},
            },
            "listAccount": {
                "status": 0,
                "response": {"account": [{"extension": "1000"}], "total_item": 1},
            },
            "listVoIPTrunk": {
                "status": 0,
                "response": {"voiptrunk": [{"trunk_name": "provider"}], "total_item": 1},
            },
            "listTrunkGroup": {
                "status": 0,
                "response": {"trunkgroup": [{"name": "group-1"}], "total_item": 1},
            },
            "listAnalogTrunk": {
                "status": 0,
                "response": {"analogtrunk": [{"trunk_name": "fxo-1"}], "total_item": 1},
            },
            "listOutboundRoute": {
                "status": 0,
                "response": {"outbound_routes": [{"name": "out"}], "total_item": 1},
            },
            "listInboundRoute": {
                "status": 0,
                "response": {"inbound_routes": [{"name": "in"}], "total_item": 1},
            },
        }

    def __call__(self, host: str, port: int, form: dict[str, str], timeout: float, verify_tls: bool) -> dict:
        assert host == "192.168.1.6"
        assert port == 8089
        assert timeout > 0
        assert verify_tls is False
        self.calls.append(dict(form))
        return self.responses[form["action"]]


def authenticated_client(fake: FakeCGI) -> GrandstreamUCM6104ReadOnlyCGI:
    client = GrandstreamUCM6104ReadOnlyCGI(post_form=fake)
    info = client.authenticate("reader", "correct horse")
    assert info.authenticated is True
    return client


def test_requires_private_literal_host() -> None:
    with pytest.raises(ValueError):
        GrandstreamUCM6104ReadOnlyCGI(host="example.com")
    with pytest.raises(ValueError):
        GrandstreamUCM6104ReadOnlyCGI(host="8.8.8.8")


def test_challenge_login_uses_expected_legacy_md5_without_retaining_password() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)

    assert fake.calls[0] == {"action": "challenge", "user": "reader"}
    expected = hashlib.md5(b"abc123correct horse").hexdigest()  # noqa: S324 - protocol fixture
    assert fake.calls[1] == {"action": "login", "user": "reader", "token": expected}
    assert "correct horse" not in repr(client)
    assert "session-cookie-secret" not in repr(client)
    assert client.authenticated is True


def test_read_requires_authenticated_session() -> None:
    fake = FakeCGI()
    client = GrandstreamUCM6104ReadOnlyCGI(post_form=fake)
    with pytest.raises(UCM6104AuthenticationError):
        client.read_action("getSIPGenSettings")
    assert fake.calls == []


def test_non_readonly_actions_fail_before_transport() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    before = len(fake.calls)
    for action in (
        "updateSIPGenSettings",
        "addSipNetAddrSettings",
        "deleteSipNetAddrSettings",
        "backupUCMConfig",
        "restoreUCMConfig",
        "setUpgradeValue",
        "updateUser",
        "deleteOutboundRoute",
        "Originate",
        "Command",
    ):
        with pytest.raises(UCM6104ReadOnlyViolation):
            client.read_action(action)
    assert len(fake.calls) == before


def test_reserved_session_fields_cannot_be_overridden() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    before = len(fake.calls)
    with pytest.raises(UCM6104ReadOnlyViolation):
        client.read_action("getSIPGenSettings", cookie="attacker")
    assert len(fake.calls) == before


def test_general_settings_are_normalized_from_exact_firmware_fields() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    settings = client.get_sip_general_settings()
    assert settings == SIPGeneralSettings(
        realm="ucm6104",
        bind_udp_port=4321,
        bind_ipv4_address="0.0.0.0",
        bind_ipv6_address="::",
        allow_guest_calls=False,
        allow_transfer=True,
        mwi_from_header="",
        enable_diversion_header=True,
    )
    read_form = fake.calls[-1]
    assert read_form["action"] == "getSIPGenSettings"
    assert read_form["user"] == "reader"
    assert read_form["cookie"] == "session-cookie-secret"


def test_sip_snapshot_uses_only_firmware_read_actions() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    snapshot = client.get_sip_snapshot()
    assert snapshot["general"]["bindport"] == "4321"
    assert snapshot["misc"]["videosupport"] == "no"
    assert snapshot["session_timer"]["session_expires"] == "1800"
    assert snapshot["tcp_tls"]["tcpenable"] == "no"
    assert snapshot["nat"]["externudpport"] == "4321"
    assert snapshot["tos"]["tos_sip"] == "cs3"


def test_inventory_helpers_use_exact_live_firmware_read_actions() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)

    extensions = client.get_extension_inventory()
    assert extensions["account"][0]["extension"] == "1000"

    trunks = client.get_trunk_inventory()
    assert trunks["voip"]["voiptrunk"][0]["trunk_name"] == "provider"
    assert trunks["groups"]["trunkgroup"][0]["name"] == "group-1"
    assert trunks["analog"]["analogtrunk"][0]["trunk_name"] == "fxo-1"

    routes = client.get_route_inventory()
    assert routes["outbound"]["outbound_routes"][0]["name"] == "out"
    assert routes["inbound"]["inbound_routes"][0]["name"] == "in"

    called = [call["action"] for call in fake.calls]
    assert "listAccount" in called
    assert "listVoIPTrunk" in called
    assert "listTrunkGroup" in called
    assert "listAnalogTrunk" in called
    assert "listOutboundRoute" in called
    assert "listInboundRoute" in called


def test_prechange_snapshot_collects_only_read_actions() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    snapshot = client.get_telephony_snapshot()

    assert snapshot["rtp"]["rtp_settings"]["rtpstart"] == "10000"
    assert snapshot["payload"]["payload_settings"]["fixture"] == "read-only"
    assert snapshot["backup"]["type"]["config"] == "yes"
    assert snapshot["upgrade"]["upgrade-via"] == "http"

    mutating = {
        "backupUCMConfig",
        "restoreUCMConfig",
        "setUpgradeValue",
        "updateUser",
        "deleteOutboundRoute",
        "deleteInboundRoute",
    }
    assert not mutating.intersection(call["action"] for call in fake.calls)
    backup_call = next(call for call in fake.calls if call["action"] == "getBackupSettings")
    assert backup_call["type"] == "realtime"


def test_nonzero_read_status_is_error_without_exposing_session_material() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)
    fake.responses["getSIPGenSettings"] = {"status": -6, "response": {}}
    with pytest.raises(UCM6104ProtocolError) as excinfo:
        client.get_sip_general_settings()
    message = str(excinfo.value)
    assert "status=-6" in message
    assert "session-cookie-secret" not in message


def test_logout_clears_local_session_even_if_device_logout_fails() -> None:
    fake = FakeCGI()
    client = authenticated_client(fake)

    def failing_transport(host: str, port: int, form: dict[str, str], timeout: float, verify_tls: bool) -> dict:
        if form["action"] == "logout":
            raise TimeoutError("legacy box ignored logout")
        return fake(host, port, form, timeout, verify_tls)

    client._post_form = failing_transport
    client.logout()
    assert client.authenticated is False
