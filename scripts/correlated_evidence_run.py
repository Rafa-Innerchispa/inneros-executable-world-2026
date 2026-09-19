#!/usr/bin/env python3
"""Demo-safe governed action + cross-sponsor evidence correlation."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from voiceops.adapters.sponsor_evidence import record_evidence_event
from voiceops.governed_tools import propose_governed_action, submit_user_approval


def _last_jsonl_row(path: Path) -> dict | None:
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else None


def main() -> int:
    session_id = f"correlated-demo-{uuid.uuid4().hex[:12]}"
    proposed = propose_governed_action("create_work_order", "demo", {"note": "correlated evidence run"})
    proposal_id = proposed["proposal_id"]
    executed = submit_user_approval(proposal_id, "Si, autorizo.", session_id=session_id)

    permit_id = executed.get("permit_id")
    evidence_hash = executed.get("evidence_sha256")

    mirror = record_evidence_event(
        "voiceops.correlated_demo",
        {
            "proposal_id": proposal_id,
            "permit_id": permit_id,
            "action_type": proposed.get("action_type"),
            "result_status": executed.get("status"),
            "evidence_sha256": evidence_hash,
        },
        session_id=session_id,
    )

    evidence_path = Path(
        __import__("os").environ.get("VOICEOPS_EVIDENCE_DIR", "evidence")
    ) / "voiceops_events.jsonl"
    jsonl_row = _last_jsonl_row(evidence_path)

    velodb_row = None
    velodb_event_id = (mirror.get("outcomes") or {}).get("velodb", {}).get("event_id")
    if velodb_event_id:
        try:
            from voiceops.adapters.optional import velodb_store

            cfg = velodb_store._config()
            conn = velodb_store._connect()
            try:
                velodb_store._ensure_schema(conn)
                velodb_row = velodb_store._select_row(conn, velodb_event_id)
            finally:
                conn.close()
        except Exception as exc:
            velodb_row = {"error": str(exc)}

    report = {
        "session_id": session_id,
        "proposal_id": proposal_id,
        "permit_id": permit_id,
        "evidence_hash": evidence_hash,
        "execution_status": executed.get("status"),
        "local_jsonl": {
            "matched": bool(
                jsonl_row
                and jsonl_row.get("session_id") == session_id
                and jsonl_row.get("event_type") == "voiceops.correlated_demo"
            ),
            "event_type": (jsonl_row or {}).get("event_type"),
        },
        "agentx": (mirror.get("outcomes") or {}).get("agentx"),
        "velodb": {
            "mirror": (mirror.get("outcomes") or {}).get("velodb"),
            "readback": velodb_row,
        },
        "edgeone": (mirror.get("outcomes") or {}).get("edgeone"),
    }

    out_path = Path("evidence/CORRELATED_RUN_20260919.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["local_jsonl"]["matched"] else 1


if __name__ == "__main__":
    sys.exit(main())
