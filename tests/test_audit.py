from voiceops.audit import build_htr, replay_summary
from voiceops.gateway import VoiceGateway


def test_htr_truth_boundary_is_explicit() -> None:
    metric = build_htr(
        manual_seconds=720,
        human_active_seconds=70,
        classification="ESTIMATED",
        evidence_basis="manual baseline estimate; active time measured",
    )
    assert metric.saved_seconds == 650
    assert metric.classification == "ESTIMATED"


def test_invalid_htr_classification_is_rejected() -> None:
    try:
        build_htr(
            manual_seconds=100,
            human_active_seconds=10,
            classification="CLAIMED",
            evidence_basis="none",
        )
    except ValueError as exc:
        assert "MEASURED or ESTIMATED" in str(exc)
    else:
        raise AssertionError("invalid HTR classification must fail")


def test_replay_uses_captured_evidence_only() -> None:
    gateway = VoiceGateway()
    gateway.process_final_transcript("Revisa la alarma")
    gateway.process_final_transcript("Sí, autorizo")
    replay = replay_summary(gateway.evidence)
    assert replay["replay_source"] == "captured_evidence_only"
    assert replay["approval"] is True
