from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy
from .velodb_store import probe_velodb


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_VELODB", False)
    url = os.getenv("VELODB_URL", "").strip().rstrip("/")
    if not enabled:
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB",
            truth="NOT_CONNECTED",
            status="NOT_CONFIGURED",
            mode="disabled",
            evidence_note="Optional evidence event store. Local JSONL always active.",
        )

    if not url:
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB",
            truth="NOT_CONNECTED",
            status="MISSING_URL",
            mode="evidence_store",
            evidence_note="Set VELODB_URL + EXECUTABLE_ENABLE_VELODB=true",
        )

    probe = probe_velodb()
    if probe.get("ok"):
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB",
            truth="REAL",
            status="CONNECTED",
            mode="evidence_store",
            ready=True,
            remote_confirmed=True,
            evidence_note="Execution/evidence events mirrored remotely; local trail preserved",
            extra={"url": url},
        )

    return AdapterStatus(
        adapter_id="velodb",
        provider="VeloDB",
        truth="NOT_CONNECTED",
        status="CONFIGURED_OFFLINE",
        mode="evidence_store",
        ready=False,
        evidence_note="VeloDB enabled but unreachable — local evidence still stored",
        extra={"url": url, "probe": probe},
    )
