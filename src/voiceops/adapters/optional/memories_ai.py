from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    has_key = bool(os.getenv("MEMORIES_AI_API_KEY", "").strip())
    enabled = env_truthy("EXECUTABLE_ENABLE_MEMORIES_AI", False)
    if has_key and enabled:
        return AdapterStatus(
            adapter_id="memories_ai",
            provider="Memories.ai",
            truth="CONFIGURED",
            status="CONNECTED",
            mode="long_term_memory",
            ready=True,
            evidence_note="Optional long-term memory — local audit trail remains authoritative",
        )
    return AdapterStatus(
        adapter_id="memories_ai",
        provider="Memories.ai",
        truth="NOT_CONNECTED",
        status="NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Optional memory adapter",
    )
