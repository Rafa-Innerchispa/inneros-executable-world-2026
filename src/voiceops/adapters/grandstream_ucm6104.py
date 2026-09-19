from __future__ import annotations

import hashlib
import ipaddress
import json
import ssl
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class UCM6104Error(RuntimeError):
    """Base error for the bounded legacy UCM6104 CGI adapter."""


class UCM6104AuthenticationError(UCM6104Error):
    """Raised when challenge/login/session state is invalid."""


class UCM6104ReadOnlyViolation(UCM6104Error):
    """Raised before transport when a non-read-only CGI action is requested."""


class UCM6104ProtocolError(UCM6104Error):
    """Raised when the legacy CGI returns an unexpected response."""


PostForm = Callable[[str, int, dict[str, str], float, bool], dict[str, Any]]


READ_ONLY_ACTIONS = frozenset(
    {
        "getInfo",
        "getSIPGenSettings",
        "getSIPMiscSettings",
        "getSIPSSTimerSettings",
        "getSIPTCPSettings",
        "getSIPNATSettings",
        "getTOSSettings",
        "getUsedPortInfo",
        "getRTPSettings",
        "getPayloadSettings",
        "getBackupSettings",
        "getUpgradeValue",
        "getInterfaceStatus",
        "getSIPAccountList",
        "getAccountList",
        "listAccount",
        "getExtenPrefSettings",
        "getTrunkList",
        "listVoIPTrunk",
        "listTrunkGroup",
        "listAnalogTrunk",
        "getOutboundRouteList",
        "listOutboundRoute",
        "getInboundRouteList",
        "listInboundRoute",
        "getAnalogTrunkList",
        "listSipNetAddrSettings",
    }
)

_RESERVED_FORM_KEYS = frozenset({"action", "user", "cookie", "token"})


@dataclass(frozen=True)
class SIPGeneralSettings:
    """Normalized subset of the UCM6104 SIP General Settings page."""

    realm: str
    bind_udp_port: int
    bind_ipv4_address: str
    bind_ipv6_address: str
    allow_guest_calls: bool
    allow_transfer: bool
    mwi_from_header: str
    enable_diversion_header: bool


@dataclass(frozen=True)
class UCM6104SessionInfo:
    authenticated: bool
    user: str
    host: str
    port: int


class GrandstreamUCM6104ReadOnlyCGI:
    """Fail-closed reader for the legacy Grandstream UCM6104 `/cgi` API.

    This adapter exists for configuration discovery only. AMI remains the
    preferred live telephony/status channel. The web credential is accepted
    only at runtime, the password is never stored on the instance, and the
    derived login token/cookie are never returned by public methods.
    """

    def __init__(
        self,
        *,
        host: str = "192.168.1.6",
        port: int = 8089,
        timeout_seconds: float = 5.0,
        verify_tls: bool = False,
        post_form: PostForm | None = None,
    ) -> None:
        _validate_private_literal_host(host)
        if not 1 <= int(port) <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.host = host
        self.port = int(port)
        self.timeout_seconds = float(timeout_seconds)
        self.verify_tls = bool(verify_tls)
        self._post_form = post_form or _post_form_https
        self._user: str | None = None
        self._cookie: str | None = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"authenticated={self.authenticated!r})"
        )

    @property
    def authenticated(self) -> bool:
        return bool(self._user and self._cookie)

    def authenticate(self, username: str, password: str) -> UCM6104SessionInfo:
        """Authenticate using the firmware's challenge + MD5(challenge+password) flow."""

        username = str(username).strip()
        if not username:
            raise ValueError("username must be non-empty")
        if not isinstance(password, str) or not password:
            raise ValueError("password must be non-empty")

        challenge_payload = self._post({"action": "challenge", "user": username})
        challenge = _nested_text(challenge_payload, "response", "challenge")
        if not challenge:
            raise UCM6104AuthenticationError(
                f"UCM6104 challenge failed with status={challenge_payload.get('status')!r}"
            )

        token = hashlib.md5((challenge + password).encode("utf-8")).hexdigest()  # noqa: S324 - device protocol
        login_payload = self._post({"action": "login", "user": username, "token": token})
        if login_payload.get("status") != 0:
            raise UCM6104AuthenticationError(
                f"UCM6104 login failed with status={login_payload.get('status')!r}"
            )
        cookie = _nested_text(login_payload, "response", "cookie")
        if not cookie:
            raise UCM6104AuthenticationError("UCM6104 login succeeded without a session cookie")

        self._user = username
        self._cookie = cookie
        return UCM6104SessionInfo(True, username, self.host, self.port)

    def logout(self) -> None:
        """Close the legacy web session; always clears local session state."""

        user, cookie = self._user, self._cookie
        self._user = None
        self._cookie = None
        if not user or not cookie:
            return
        try:
            self._post({"action": "logout", "user": user, "cookie": cookie})
        except Exception:
            return

    def read_action(self, action: str, **params: Any) -> dict[str, Any]:
        """Execute one explicitly allowlisted read action with the active session."""

        if action not in READ_ONLY_ACTIONS:
            raise UCM6104ReadOnlyViolation(f"CGI action is not read-only allowlisted: {action}")
        if not self.authenticated:
            raise UCM6104AuthenticationError("UCM6104 read requires an authenticated session")
        collisions = _RESERVED_FORM_KEYS.intersection(params)
        if collisions:
            raise UCM6104ReadOnlyViolation(
                f"reserved CGI form keys cannot be overridden: {sorted(collisions)}"
            )

        form = {
            "action": action,
            "user": str(self._user),
            "cookie": str(self._cookie),
        }
        form.update({key: _form_value(value) for key, value in params.items()})
        payload = self._post(form)
        if payload.get("status") != 0:
            raise UCM6104ProtocolError(
                f"UCM6104 read action {action} failed with status={payload.get('status')!r}"
            )
        response = payload.get("response")
        if not isinstance(response, dict):
            raise UCM6104ProtocolError(f"UCM6104 read action {action} returned no response object")
        return response

    def get_sip_general_settings(self) -> SIPGeneralSettings:
        response = self.read_action("getSIPGenSettings")
        settings = response.get("sip_general_settings")
        if not isinstance(settings, dict):
            raise UCM6104ProtocolError("getSIPGenSettings missing sip_general_settings")
        try:
            bind_port = int(str(settings.get("bindport", "")).strip())
        except ValueError as exc:
            raise UCM6104ProtocolError("SIP bindport is not an integer") from exc
        if not 1 <= bind_port <= 65535:
            raise UCM6104ProtocolError("SIP bindport is outside 1..65535")

        return SIPGeneralSettings(
            realm=str(settings.get("realm", "")),
            bind_udp_port=bind_port,
            bind_ipv4_address=str(settings.get("bindaddr", "")),
            bind_ipv6_address=str(settings.get("bindaddr6", "")),
            allow_guest_calls=_yes_no(settings.get("allowguest"), field="allowguest"),
            allow_transfer=_yes_no(settings.get("allowtransfer"), field="allowtransfer"),
            mwi_from_header=str(settings.get("mwi_from", "")),
            enable_diversion_header=_yes_no(
                settings.get("enable_diversion"), field="enable_diversion"
            ),
        )

    def get_sip_snapshot(self) -> dict[str, Any]:
        """Read all SIP configuration groups exposed by the legacy UI."""

        groups = {
            "general": ("getSIPGenSettings", "sip_general_settings"),
            "misc": ("getSIPMiscSettings", "sip_misc_settings"),
            "session_timer": ("getSIPSSTimerSettings", "sip_sessiontimer_settings"),
            "tcp_tls": ("getSIPTCPSettings", "sip_tcp_settings"),
            "nat": ("getSIPNATSettings", "sip_nat_settings"),
            "tos": ("getTOSSettings", "tos_settings"),
        }
        snapshot: dict[str, Any] = {}
        for name, (action, key) in groups.items():
            response = self.read_action(action)
            value = response.get(key)
            snapshot[name] = dict(value) if isinstance(value, dict) else value
        return snapshot

    def get_extension_inventory(self) -> dict[str, Any]:
        """Read the extension table using the exact action used by this firmware UI."""

        return self.read_action("listAccount", item_num=1000, page=1)

    def get_trunk_inventory(self) -> dict[str, dict[str, Any]]:
        """Read VoIP, trunk-group, and analog inventories without mutating the PBX."""

        return {
            "voip": self.read_action("listVoIPTrunk", item_num=1000, page=1),
            "groups": self.read_action("listTrunkGroup", item_num=1000, page=1),
            "analog": self.read_action("listAnalogTrunk", item_num=1000, page=1),
        }

    def get_route_inventory(self) -> dict[str, dict[str, Any]]:
        """Read inbound and outbound route tables using exact live firmware actions."""

        return {
            "outbound": self.read_action("listOutboundRoute", item_num=1000, page=1),
            "inbound": self.read_action("listInboundRoute", item_num=1000, page=1),
        }

    def get_rtp_settings(self) -> dict[str, Any]:
        """Read live RTP settings used to derive media/firewall requirements."""

        return self.read_action("getRTPSettings")

    def get_payload_settings(self) -> dict[str, Any]:
        """Read RTP payload mappings from the exact firmware page action."""

        return self.read_action("getPayloadSettings")

    def get_backup_settings(self) -> dict[str, Any]:
        """Read backup capabilities before any backup/upgrade mutation is attempted."""

        return self.read_action("getBackupSettings", type="realtime")

    def get_upgrade_settings(self) -> dict[str, Any]:
        """Read firmware-upgrade settings without uploading or changing firmware."""

        return self.read_action("getUpgradeValue")

    def get_telephony_snapshot(self) -> dict[str, Any]:
        """Collect the exact read-only state required before telephony changes."""

        return {
            "sip": self.get_sip_snapshot(),
            "rtp": self.get_rtp_settings(),
            "payload": self.get_payload_settings(),
            "extensions": self.get_extension_inventory(),
            "trunks": self.get_trunk_inventory(),
            "routes": self.get_route_inventory(),
            "backup": self.get_backup_settings(),
            "upgrade": self.get_upgrade_settings(),
        }

    def _post(self, form: dict[str, str]) -> dict[str, Any]:
        payload = self._post_form(
            self.host,
            self.port,
            dict(form),
            self.timeout_seconds,
            self.verify_tls,
        )
        if not isinstance(payload, dict):
            raise UCM6104ProtocolError("UCM6104 CGI response must be a JSON object")
        return payload


def _post_form_https(
    host: str,
    port: int,
    form: dict[str, str],
    timeout_seconds: float,
    verify_tls: bool,
) -> dict[str, Any]:
    context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    request = Request(
        f"https://{host}:{port}/cgi",
        data=urlencode(form).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "InnerOS-VoiceOps-UCM6104/1.0",
        },
        method="POST",
    )
    with urlopen(request, context=context, timeout=timeout_seconds) as response:  # noqa: S310 - validated private literal host
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise UCM6104ProtocolError("UCM6104 CGI response exceeded 1 MiB")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UCM6104ProtocolError("UCM6104 CGI response was not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise UCM6104ProtocolError("UCM6104 CGI response must be a JSON object")
    return payload


def _validate_private_literal_host(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("UCM6104 host must be a literal private/loopback IP address") from exc
    if not (address.is_private or address.is_loopback):
        raise ValueError("UCM6104 host must be private or loopback")


def _nested_text(payload: dict[str, Any], *keys: str) -> str:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return str(value).strip() if value is not None else ""


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _yes_no(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"yes", "1", "true", "on"}:
        return True
    if normalized in {"no", "0", "false", "off"}:
        return False
    raise UCM6104ProtocolError(f"{field} is not a recognized yes/no value")
