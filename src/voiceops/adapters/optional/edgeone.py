from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy
from .edgeone_witness import pages_project, probe_witness, verify_witness_post, witness_url


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_EDGEONE", False)
    project = pages_project()
    zone = os.getenv("EDGEONE_ZONE_ID", "").strip()
    url = witness_url()

    if not enabled:
        return AdapterStatus(
            adapter_id="edgeone",
            provider="Tencent EdgeOne",
            truth="NOT_CONNECTED",
            status="NOT_CONFIGURED",
            mode="disabled",
            evidence_note="Optional witness/CDN layer — InnerOS is NOT migrated to EdgeOne",
        )

    if url:
        verify = verify_witness_post()
        if verify.get("ok"):
            return AdapterStatus(
                adapter_id="edgeone",
                provider="Tencent EdgeOne",
                truth="REAL",
                status="CONNECTED",
                mode="witness",
                ready=True,
                remote_confirmed=True,
                evidence_note="Witness endpoint accepted sanitized execution receipt",
                extra={
                    "pages_project": project or None,
                    "witness_url": url,
                    "zone_id": zone[:8] + "…" if len(zone) > 8 else zone or None,
                },
            )
        probe = probe_witness()
        return AdapterStatus(
            adapter_id="edgeone",
            provider="Tencent EdgeOne",
            truth="NOT_CONNECTED",
            status="WITNESS_OFFLINE",
            mode="witness",
            evidence_note="Witness URL configured but POST probe failed",
            extra={"pages_project": project or None, "witness_url": url, "probe": probe, "verify": verify},
        )

    if project:
        return AdapterStatus(
            adapter_id="edgeone",
            provider="Tencent EdgeOne",
            truth="CONFIGURED",
            status="CONFIGURED",
            mode="witness_metadata",
            ready=False,
            remote_confirmed=False,
            evidence_note="EdgeOne Pages project linked — deploy agents/execution-witness for REAL",
            extra={
                "pages_project": project,
                "zone_id": zone[:8] + "…" if len(zone) > 8 else zone or None,
            },
        )

    return AdapterStatus(
        adapter_id="edgeone",
        provider="Tencent EdgeOne",
        truth="NOT_CONNECTED",
        status="MISSING_PROJECT",
        mode="witness",
        evidence_note="Set EDGEONE_PAGES_PROJECT (repo already authorized in EdgeOne console)",
    )
