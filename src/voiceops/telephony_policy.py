from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class DestinationClass(str, Enum):
    GUAYAQUIL_FIXED = "guayaquil_fixed"
    ECUADOR_MOBILE = "ecuador_mobile"
    ECUADOR_OTHER = "ecuador_other"
    INTERNATIONAL = "international"
    INTERNAL_EXTENSION = "internal_extension"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class NormalizedDestination:
    raw: str
    canonical_number: str | None
    destination_class: DestinationClass
    reason: str


@dataclass(frozen=True, slots=True)
class DialDecision:
    allowed: bool
    canonical_number: str | None
    destination_class: DestinationClass
    requires_approval: bool
    execution_ready: bool
    pbx_dial_string: str | None
    reason: str


_ALLOWED_SEPARATORS = re.compile(r"[\s().-]+")
_GUAYAQUIL_NATIONAL = re.compile(r"^04\d{7}$")
_MOBILE_NATIONAL = re.compile(r"^09\d{8}$")
_GUAYAQUIL_E164 = re.compile(r"^\+5934\d{7}$")
_MOBILE_E164 = re.compile(r"^\+5939\d{8}$")
_ECUADOR_E164 = re.compile(r"^\+593\d{8,9}$")
_INTERNAL_EXTENSION = re.compile(r"^\d{3,6}$")


def _clean_target(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    value = _ALLOWED_SEPARATORS.sub("", value)
    if value.startswith("00"):
        value = "+" + value[2:]
    elif value.startswith("593"):
        value = "+" + value
    return value


def normalize_destination(raw: str, *, allow_internal_extension: bool = True) -> NormalizedDestination:
    """Normalize a bounded Ecuador destination without guessing PBX route prefixes.

    Policy scope intentionally covers Guayaquil fixed lines and Ecuador mobile numbers.
    Other Ecuador geographic destinations remain classified but disabled until the live
    UCM outbound-route inventory is known.
    """

    value = _clean_target(raw)
    if not value:
        return NormalizedDestination(raw=str(raw or ""), canonical_number=None, destination_class=DestinationClass.INVALID, reason="empty_destination")

    if any(ch not in "+0123456789" for ch in value) or value.count("+") > 1 or ("+" in value and not value.startswith("+")):
        return NormalizedDestination(raw=str(raw), canonical_number=None, destination_class=DestinationClass.INVALID, reason="invalid_characters")

    if allow_internal_extension and _INTERNAL_EXTENSION.fullmatch(value):
        return NormalizedDestination(raw=str(raw), canonical_number=value, destination_class=DestinationClass.INTERNAL_EXTENSION, reason="internal_extension")

    if _GUAYAQUIL_NATIONAL.fullmatch(value):
        return NormalizedDestination(raw=str(raw), canonical_number="+593" + value[1:], destination_class=DestinationClass.GUAYAQUIL_FIXED, reason="guayaquil_fixed_national")

    if _MOBILE_NATIONAL.fullmatch(value):
        return NormalizedDestination(raw=str(raw), canonical_number="+593" + value[1:], destination_class=DestinationClass.ECUADOR_MOBILE, reason="ecuador_mobile_national")

    if _GUAYAQUIL_E164.fullmatch(value):
        return NormalizedDestination(raw=str(raw), canonical_number=value, destination_class=DestinationClass.GUAYAQUIL_FIXED, reason="guayaquil_fixed_e164")

    if _MOBILE_E164.fullmatch(value):
        return NormalizedDestination(raw=str(raw), canonical_number=value, destination_class=DestinationClass.ECUADOR_MOBILE, reason="ecuador_mobile_e164")

    if value.startswith("+593"):
        if _ECUADOR_E164.fullmatch(value):
            return NormalizedDestination(raw=str(raw), canonical_number=value, destination_class=DestinationClass.ECUADOR_OTHER, reason="ecuador_destination_outside_initial_policy")
        return NormalizedDestination(raw=str(raw), canonical_number=None, destination_class=DestinationClass.INVALID, reason="invalid_ecuador_number")

    if value.startswith("+"):
        return NormalizedDestination(raw=str(raw), canonical_number=value, destination_class=DestinationClass.INTERNATIONAL, reason="international_destination")

    return NormalizedDestination(raw=str(raw), canonical_number=None, destination_class=DestinationClass.INVALID, reason="unrecognized_destination")


def authorize_call(
    target: str,
    *,
    explicit_user_request: bool,
    allowlisted_autonomous_target: bool = False,
    route_verified: bool = False,
    pbx_dial_string: str | None = None,
) -> DialDecision:
    """Apply VoiceOps outbound-call policy before any AMI Originate capability exists.

    A policy-allowed number is not automatically executable. `execution_ready` remains
    false until the UCM outbound route has been verified and a concrete PBX dial string
    has been derived from that live route rather than guessed.
    """

    normalized = normalize_destination(target)
    cls = normalized.destination_class

    if cls is DestinationClass.INVALID:
        return DialDecision(False, None, cls, False, False, None, normalized.reason)

    if cls is DestinationClass.INTERNATIONAL:
        return DialDecision(False, normalized.canonical_number, cls, True, False, None, "international_calls_disabled_by_default")

    if cls is DestinationClass.ECUADOR_OTHER:
        return DialDecision(False, normalized.canonical_number, cls, True, False, None, "ecuador_geographic_destination_not_yet_enabled")

    if cls is DestinationClass.INTERNAL_EXTENSION:
        allowed = explicit_user_request or allowlisted_autonomous_target
        return DialDecision(
            allowed,
            normalized.canonical_number,
            cls,
            not explicit_user_request,
            allowed and route_verified and bool(pbx_dial_string),
            pbx_dial_string if allowed and route_verified else None,
            "internal_extension_allowed" if allowed else "internal_extension_requires_user_request_or_allowlist",
        )

    if cls in {DestinationClass.GUAYAQUIL_FIXED, DestinationClass.ECUADOR_MOBILE}:
        allowed = explicit_user_request or allowlisted_autonomous_target
        if not allowed:
            return DialDecision(False, normalized.canonical_number, cls, True, False, None, "domestic_destination_requires_user_request_or_allowlist")
        execution_ready = route_verified and bool(pbx_dial_string)
        return DialDecision(
            True,
            normalized.canonical_number,
            cls,
            not explicit_user_request,
            execution_ready,
            pbx_dial_string if execution_ready else None,
            "domestic_destination_allowed_route_verified" if execution_ready else "domestic_destination_allowed_route_translation_pending",
        )

    return DialDecision(False, normalized.canonical_number, cls, True, False, None, "destination_class_not_enabled")
