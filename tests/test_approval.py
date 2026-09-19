from voiceops.approval import ExplicitApprovalGate


def test_explicit_spanish_approval_passes() -> None:
    decision = ExplicitApprovalGate().decide("Sí, autorizo.")
    assert decision.approved is True


def test_ambiguous_phrase_fails_closed() -> None:
    decision = ExplicitApprovalGate().decide("si crees que corresponde")
    assert decision.approved is False
    assert decision.reason == "ambiguous_phrase_fail_closed"


def test_negated_authorization_fails_closed() -> None:
    decision = ExplicitApprovalGate().decide("No autorizo")
    assert decision.approved is False
    assert decision.reason == "explicit_denial_or_negation"
