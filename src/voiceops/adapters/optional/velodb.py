from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy
from .velodb_store import probe_velodb


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_VELODB", False)
    host = os.getenv("VELODB_HOST", "").strip()
    database = os.getenv("VELODB_DATABASE", "inneros_executable_world").strip()

    if not enabled:
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB (MySQL-compatible)",
            truth="NOT_CONNECTED",
            status="NOT_CONFIGURED",
            mode="disabled",
            evidence_note="Optional execution memory. Local JSONL always active.",
        )

    if not host:
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB (MySQL-compatible)",
            truth="NOT_CONNECTED",
            status="MISSING_HOST",
            mode="mysql_evidence_store",
            evidence_note="Set VELODB_HOST + VELODB_PASSWORD + EXECUTABLE_ENABLE_VELODB=true",
        )

    if not os.getenv("VELODB_PASSWORD", "").strip():
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB (MySQL-compatible)",
            truth="NOT_CONNECTED",
            status="MISSING_PASSWORD",
            mode="mysql_evidence_store",
            evidence_note="VELODB_PASSWORD must be set locally — never commit secrets",
            extra={"host": host, "database": database},
        )

    probe = probe_velodb()
    if probe.get("ok"):
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB (MySQL-compatible)",
            truth="REAL",
            status="CONNECTED",
            mode="mysql_evidence_store",
            ready=True,
            remote_confirmed=True,
            evidence_note="INSERT + SELECT readback verified against execution_events",
            extra={
                "host": host,
                "database": database,
                "last_probe_event_id": probe.get("event_id"),
            },
        )

    return AdapterStatus(
        adapter_id="velodb",
        provider="VeloDB (MySQL-compatible)",
        truth="NOT_CONNECTED",
        status="CONFIGURED_OFFLINE",
        mode="mysql_evidence_store",
        ready=False,
        evidence_note="VeloDB enabled but INSERT/SELECT probe failed — local evidence still stored",
        extra={"host": host, "database": database, "probe": probe},
    )
