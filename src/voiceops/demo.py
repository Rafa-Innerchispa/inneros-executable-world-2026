from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import replay_summary, write_evidence_bundle
from .gateway import VoiceGateway


DEFAULT_INTENT = "Ralphi, tenemos una alarma en el acceso norte. Revisa qué ocurre y abre una orden para el técnico si corresponde."
DEFAULT_APPROVAL = "Sí, autorizo."


def run_synthetic_demo(
    intent: str = DEFAULT_INTENT,
    approval: str = DEFAULT_APPROVAL,
    *,
    evidence_path: str | Path | None = None,
) -> dict[str, object]:
    gateway = VoiceGateway()
    first = gateway.process_final_transcript(intent)
    second = gateway.process_final_transcript(approval)

    if evidence_path is not None:
        write_evidence_bundle(gateway.evidence, evidence_path)

    return {
        "session_id": gateway.session_id,
        "correlation_id": gateway.correlation_id,
        "intent_result": first,
        "approval_result": second,
        "replay": replay_summary(gateway.evidence),
        "evidence": gateway.evidence.to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the InnerOS VoiceOps synthetic governed E2E demo.")
    parser.add_argument("--intent", default=DEFAULT_INTENT)
    parser.add_argument("--approval", default=DEFAULT_APPROVAL)
    parser.add_argument("--evidence", default="evidence/latest_synthetic_e2e.json")
    args = parser.parse_args()

    result = run_synthetic_demo(args.intent, args.approval, evidence_path=args.evidence)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
