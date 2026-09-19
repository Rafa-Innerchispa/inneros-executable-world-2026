from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy
from .edgeone_witness import probe_witness


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_EDGEONE", False)
    project = os.getenv("EDGEONE_PAGES_PROJECT", "").strip()
    zone = os.getenv("EDGEONE_ZONE_ID", "").strip()

    if not enabled:
        return AdapterStatus(
            adapter_id="edgeone",
            provider="Tencent EdgeOne",
            truth="NOT_CONNECTED",
            status="NOT_CONFIGURED",
            mode="disabled",
            evidence_note="Optional witness/CDN layer — InnerOS is NOT migrated to EdgeOne",
        )

    probe = probe_witness()
    if probe.get("ok"):
        truth = "REAL" if probe.get("url") else "CONFIGURED"
        return AdapterStatus(
            adapter_id="edgeone",
            provider="Tencent EdgeOne",
            truth=truth,
            status="CONNECTED" if truth == "REAL" else "CONFIGURED",
            mode="witness",
            ready=True,
            remote_confirmed=bool(probe.get("url")),
            evidence_note="Auxiliary witness only — core remains on creatorcore.ai / local .4",
            extra={
                "pages_project": project or None,
                "zone_id": zone[:8] + "…" if len(zone) > 8 else zone or None,
                "probe": probe,
            },
        )

    return AdapterStatus(
        adapter_id="edgeone",
        provider="Tencent EdgeOne",
        truth="NOT_CONNECTED",
        status="CONFIGURED_OFFLINE",
        mode="witness",
        evidence_note="EdgeOne enabled but witness endpoint not verified",
        extra={"pages_project": project or None, "probe": probe},
    )
