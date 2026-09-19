from __future__ import annotations

import os

from .agentx_trace import probe_with_trace, self_hosted_base
from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    enabled = env_truthy("EXECUTABLE_ENABLE_AGENTX", False)
    endpoint = self_hosted_base()
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

    probe = probe_with_trace()
    if probe.get("ok"):
        return AdapterStatus(
            adapter_id="agentx",
            provider="AgentX (self-hosted)",
            truth="REAL",
            status="CONNECTED",
            mode="self_hosted_otlp",
            ready=True,
            remote_confirmed=True,
            evidence_note="Health OK and OTLP trace accepted by self-hosted AgentX",
            extra={
                "endpoint": endpoint,
                "health_url": (probe.get("health") or {}).get("url"),
                "otlp_status": (probe.get("trace") or {}).get("status"),
            },
        )

    health_only = (probe.get("health") or {}).get("ok")
    if health_only:
        return AdapterStatus(
            adapter_id="agentx",
            provider="AgentX (self-hosted)",
            truth="UNVERIFIED",
            status="HEALTH_ONLY",
            mode="self_hosted_otlp",
            ready=False,
            evidence_note="AgentX health reachable but trace ingest not verified",
            extra={"endpoint": endpoint, "probe": probe},
        )

    return AdapterStatus(
        adapter_id="agentx",
        provider="AgentX (self-hosted)",
        truth="NOT_CONNECTED",
        status="CONFIGURED_OFFLINE",
        mode="self_hosted_otlp",
        ready=False,
        evidence_note="Enabled but self-hosted AgentX not reachable; core local continues",
        extra={"endpoint": endpoint, "probe": probe},
    )
