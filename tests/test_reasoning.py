from voiceops.reasoning import CallableInnerOSReasoner


def test_inneros_reasoner_requires_local_first_route() -> None:
    reasoner = CallableInnerOSReasoner(
        lambda facts: {
            "proposal": {
                "action_type": "create_work_order",
                "summary": "Create synthetic work order",
                "requires_approval": True,
                "payload": {"device": facts["device"]},
            },
            "route": {
                "policy": "local_first",
                "provider": "local-amd-5",
                "model": "QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ",
            },
        }
    )
    result = reasoner.propose({"device": "camera-north-01"})
    assert result.route["provider"] == "local-amd-5"
    assert result.proposal.requires_approval is True


def test_inneros_reasoner_rejects_non_local_first_contract() -> None:
    reasoner = CallableInnerOSReasoner(
        lambda _facts: {
            "proposal": {
                "action_type": "noop",
                "summary": "noop",
                "requires_approval": False,
                "payload": {},
            },
            "route": {"policy": "external_first"},
        }
    )
    try:
        reasoner.propose({})
    except ValueError as exc:
        assert "local_first" in str(exc)
    else:
        raise AssertionError("non-local-first reasoning route must be rejected")
