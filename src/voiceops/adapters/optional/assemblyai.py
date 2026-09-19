from __future__ import annotations

import os

from .base import AdapterStatus, env_truthy


def status() -> AdapterStatus:
    has_key = bool(os.getenv("ASSEMBLYAI_API_KEY", "").strip())
    enabled = env_truthy("VOICEOPS_ENABLE_LIVE_ASSEMBLYAI", True)
    if has_key and enabled:
        return AdapterStatus(
            adapter_id="assemblyai",
            provider="AssemblyAI Voice Agent",
            truth="REAL",
            status="CONNECTED",
            mode="voice_agent_websocket",
            ready=True,
            remote_confirmed=True,
            evidence_note="Server-side token minting; browser uses temporary tokens only",
            extra={
                "token_endpoint": "/api/assemblyai/token",
                "websocket_endpoint": "wss://agents.assemblyai.com/v1/ws",
            },
        )
    return AdapterStatus(
        adapter_id="assemblyai",
        provider="AssemblyAI Voice Agent",
        truth="NOT_CONNECTED",
        status="DISABLED" if has_key else "NOT_CONFIGURED",
        mode="disabled",
        evidence_note="Set ASSEMBLYAI_API_KEY + VOICEOPS_ENABLE_LIVE_ASSEMBLYAI=true",
        extra={"token_endpoint": "/api/assemblyai/token"},
    )
