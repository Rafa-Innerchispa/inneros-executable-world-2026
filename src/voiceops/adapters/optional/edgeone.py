from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_EDGEONE", False)
    zone = os.getenv("EDGEONE_ZONE_ID", "").strip()
    if enabled and zone:
        return AdapterStatus(
            adapter_id="edgeone",
            provider="EdgeOne",
            truth="CONFIGURED",
            status="CONNECTED",
            mode="edge_cdn",
            ready=True,
            evidence_note="EdgeOne CDN/WAF optional layer",
            extra={"zone_id": zone[:8] + "…" if len(zone) > 8 else zone},
        )
    return AdapterStatus(
        adapter_id="edgeone",
        provider="EdgeOne",
        truth="NOT_CONNECTED",
        status="NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Optional edge adapter — not required for local core",
    )
