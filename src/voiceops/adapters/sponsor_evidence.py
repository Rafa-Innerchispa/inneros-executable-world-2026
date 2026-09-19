"""Optional hackathon evidence fan-out: local-first, VeloDB / AgentX / EdgeOne best-effort."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LOCAL_PATH = Path(
    os.getenv("VOICEOPS_EVIDENCE_DIR", "evidence")
) / "voiceops_events.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_append(record: dict[str, Any]) -> dict[str, Any]:
    path = _DEFAULT_LOCAL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"stored": True, "path": str(path)}


def record_evidence_event(
    event_type: str,
    data: dict[str, Any],
    *,
    session_id: str = "executable-world-session",
) -> dict[str, Any]:
    """Always persist locally; optionally mirror to VeloDB / AgentX / EdgeOne witness."""
    record: dict[str, Any] = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "session_id": session_id,
        "data": data,
    }

    outcomes: dict[str, Any] = {"local": _local_append(record)}

    try:
        from .optional import agentx_trace

        outcomes["agentx"] = agentx_trace.emit_trace(event_type, record)
    except Exception as exc:
        logger.debug("AgentX trace skipped: %s", exc)
        outcomes["agentx"] = {"stored": False, "error": str(exc)}

    try:
        from .optional import velodb_store

        outcomes["velodb"] = velodb_store.append_event(record)
    except Exception as exc:
        logger.debug("VeloDB store skipped: %s", exc)
        outcomes["velodb"] = {"stored": False, "error": str(exc)}

    try:
        from .optional import edgeone_witness

        outcomes["edgeone"] = edgeone_witness.witness_event(event_type, record)
    except Exception as exc:
        logger.debug("EdgeOne witness skipped: %s", exc)
        outcomes["edgeone"] = {"stored": False, "error": str(exc)}

    return {"ok": True, "event_type": event_type, "outcomes": outcomes}


def record_governed_action(
    proposal_id: str,
    permit_id: str,
    action_type: str,
    result_status: str,
    *,
    session_id: str = "executable-world-session",
) -> dict[str, Any]:
    return record_evidence_event(
        "voiceops.governed_action",
        {
            "proposal_id": proposal_id,
            "permit_id": permit_id,
            "action_type": action_type,
            "result_status": result_status,
        },
        session_id=session_id,
    )
