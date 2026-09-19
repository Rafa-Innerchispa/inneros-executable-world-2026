from __future__ import annotations

import os

from .agentx_trace import probe_self_hosted, self_hosted_url
from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_AGENTX", False)
    endpoint = self_hosted_url()
    if not enabled:
        return AdapterStatus(
            adapter_id="agentx",
            provider="AgentX (self-hosted)",
            truth="NOT_CONNECTED",
            status="NOT_CONFIGURED",
            mode="disabled",
            evidence_note="Self-hosted tracing only. Set EXECUTABLE_ENABLE_AGENTX=true + AGENTX_SELF_HOSTED_URL",
            extra={"endpoint": endpoint, "hosted_api": False},
        )

    probe = probe_self_hosted()
    if probe.get("ok"):
        return AdapterStatus(
            adapter_id="agentx",
            provider="AgentX (self-hosted)",
            truth="REAL",
            status="CONNECTED",
            mode="self_hosted_tracing",
            ready=True,
            remote_confirmed=True,
            evidence_note="Local AgentX trace endpoint reachable — no paid hosted API",
            extra={"endpoint": endpoint, "probe_url": probe.get("url")},
        )

    return AdapterStatus(
        adapter_id="agentx",
        provider="AgentX (self-hosted)",
        truth="NOT_CONNECTED",
        status="CONFIGURED_OFFLINE",
        mode="self_hosted_tracing",
        ready=False,
        evidence_note="Enabled but self-hosted endpoint not reachable; core local continues",
        extra={"endpoint": endpoint, "probe": probe},
    )
