from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    has_key = bool(os.getenv("BOSON_API_KEY", "").strip())
    enabled = env_truthy("VOICEOPS_ENABLE_BOSON", False)
    endpoint = os.getenv("BOSON_API_ENDPOINT", "https://api.boson.ai/v1")
    if has_key and enabled:
        return AdapterStatus(
            adapter_id="boson",
            provider="Boson Higgs Realtime",
            truth="REAL",
            status="CONNECTED",
            mode="higgs_relay",
            ready=True,
            remote_confirmed=True,
            evidence_note="Optional S2S voice adapter — core continues if Boson unavailable",
            extra={"endpoint": endpoint},
        )
    return AdapterStatus(
        adapter_id="boson",
        provider="Boson Higgs Realtime",
        truth="NOT_CONNECTED",
        status="NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Optional adapter. Set BOSON_API_KEY + VOICEOPS_ENABLE_BOSON=true to attach",
        extra={"endpoint": endpoint},
    )
