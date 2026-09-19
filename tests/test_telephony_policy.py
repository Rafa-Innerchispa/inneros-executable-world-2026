from voiceops.telephony_policy import DestinationClass, authorize_call, normalize_destination


def test_guayaquil_fixed_normalizes_to_e164_without_guessing_pbx_route():
    result = normalize_destination("04 234-5678")
    assert result.destination_class is DestinationClass.GUAYAQUIL_FIXED
    assert result.canonical_number == "+59342345678"


def test_ecuador_mobile_normalizes_to_e164():
    result = normalize_destination("09 1234 5678")
    assert result.destination_class is DestinationClass.ECUADOR_MOBILE
    assert result.canonical_number == "+593912345678"


def test_e164_domestic_numbers_are_accepted():
    assert normalize_destination("+59342345678").destination_class is DestinationClass.GUAYAQUIL_FIXED
    assert normalize_destination("+593912345678").destination_class is DestinationClass.ECUADOR_MOBILE


def test_00_country_prefix_is_canonicalized_then_international_denied():
    decision = authorize_call("0014155550123", explicit_user_request=True)
    assert decision.destination_class is DestinationClass.INTERNATIONAL
    assert decision.allowed is False
    assert decision.reason == "international_calls_disabled_by_default"


def test_other_ecuador_geography_is_classified_but_disabled():
    decision = authorize_call("+59322345678", explicit_user_request=True)
    assert decision.destination_class is DestinationClass.ECUADOR_OTHER
    assert decision.allowed is False
    assert decision.execution_ready is False


def test_domestic_explicit_request_is_policy_allowed_but_not_executable_before_route_read():
    decision = authorize_call("0912345678", explicit_user_request=True)
    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.execution_ready is False
    assert decision.pbx_dial_string is None
    assert decision.reason == "domestic_destination_allowed_route_translation_pending"


def test_domestic_autonomous_call_requires_allowlist():
    denied = authorize_call("0912345678", explicit_user_request=False)
    allowed = authorize_call("0912345678", explicit_user_request=False, allowlisted_autonomous_target=True)
    assert denied.allowed is False
    assert denied.requires_approval is True
    assert allowed.allowed is True
    assert allowed.requires_approval is True


def test_route_verified_requires_explicit_pbx_dial_string():
    no_dial_string = authorize_call("0912345678", explicit_user_request=True, route_verified=True)
    ready = authorize_call(
        "0912345678",
        explicit_user_request=True,
        route_verified=True,
        pbx_dial_string="0912345678",
    )
    assert no_dial_string.execution_ready is False
    assert ready.execution_ready is True
    assert ready.pbx_dial_string == "0912345678"


def test_internal_extension_is_bounded_and_policy_controlled():
    denied = authorize_call("1000", explicit_user_request=False)
    allowed = authorize_call("1000", explicit_user_request=True)
    assert denied.destination_class is DestinationClass.INTERNAL_EXTENSION
    assert denied.allowed is False
    assert allowed.allowed is True


def test_sip_feature_codes_and_injection_like_targets_are_invalid():
    for target in ("*98", "1000#", "1000\r\nAction: Originate", "abc", "+5934;rm"):
        result = normalize_destination(target)
        assert result.destination_class is DestinationClass.INVALID
        assert result.canonical_number is None
