from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    has_key = bool(os.getenv("AGENTX_API_KEY", "").strip())
    enabled = env_truthy("EXECUTABLE_ENABLE_AGENTX", False)
    endpoint = os.getenv("AGENTX_ENDPOINT", "https://api.agentx.ai/v1")
    if has_key and enabled:
        return AdapterStatus(
            adapter_id="agentx",
            provider="AgentX",
            truth="REAL",
            status="CONNECTED",
            mode="agent_runtime",
            ready=True,
            remote_confirmed=False,
            evidence_note="AgentX attached as optional execution surface",
            extra={"endpoint": endpoint},
        )
    return AdapterStatus(
        adapter_id="agentx",
        provider="AgentX",
        truth="NOT_CONNECTED",
        status="NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Hackathon-only adapter. Set AGENTX_API_KEY + EXECUTABLE_ENABLE_AGENTX=true",
        extra={"endpoint": endpoint},
    )
