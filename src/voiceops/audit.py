from __future__ import annotations

import json
from pathlib import Path

from .models import EvidenceBundle, HTRMetric


def build_htr(
    *,
    manual_seconds: float,
    human_active_seconds: float,
    classification: str,
    evidence_basis: str,
) -> HTRMetric:
    if classification not in {"MEASURED", "ESTIMATED"}:
        raise ValueError("classification must be MEASURED or ESTIMATED")
    if manual_seconds < 0 or human_active_seconds < 0:
        raise ValueError("HTR timings cannot be negative")
    saved = max(0.0, manual_seconds - human_active_seconds)
    return HTRMetric(
        manual_seconds=round(manual_seconds, 3),
        human_active_seconds=round(human_active_seconds, 3),
        saved_seconds=round(saved, 3),
        classification=classification,  # type: ignore[arg-type]
        evidence_basis=evidence_basis,
    )


def write_evidence_bundle(bundle: EvidenceBundle, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def replay_summary(bundle: EvidenceBundle) -> dict[str, object]:
    """Replay captured evidence only; never refetch current state."""
    return {
        "correlation_id": bundle.correlation_id,
        "session_id": bundle.session_id,
        "captured_turns": [turn.transcript for turn in bundle.turns],
        "proposal": bundle.proposal.summary if bundle.proposal else None,
        "approval": bundle.approval.approved if bundle.approval else False,
        "action_id": bundle.action_result.action_id if bundle.action_result else None,
        "htr": bundle.htr.saved_seconds if bundle.htr else None,
        "replay_source": "captured_evidence_only",
    }
