from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    has_url = bool(os.getenv("VELODB_URL", "").strip())
    has_key = bool(os.getenv("VELODB_API_KEY", "").strip())
    enabled = env_truthy("EXECUTABLE_ENABLE_VELODB", False)
    if has_url and has_key and enabled:
        return AdapterStatus(
            adapter_id="velodb",
            provider="VeloDB",
            truth="REAL",
            status="CONNECTED",
            mode="vector_store",
            ready=True,
            remote_confirmed=False,
            evidence_note="VeloDB attached for semantic memory — core evidence trail remains local",
            extra={"url": os.getenv("VELODB_URL", "").rstrip("/")},
        )
    return AdapterStatus(
        adapter_id="velodb",
        provider="VeloDB",
        truth="NOT_CONNECTED",
        status="NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Hackathon-only adapter. Set VELODB_URL + VELODB_API_KEY + EXECUTABLE_ENABLE_VELODB=true",
    )
