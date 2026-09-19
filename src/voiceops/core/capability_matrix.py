from __future__ import annotations

import os
from typing import Any

CAPABILITY_MATRIX: dict[str, dict[str, Any]] = {
    "core_local": {
        "label": "CORE LOCAL",
        "description": "Always-on sovereign runtime. System degrades gracefully if optional adapters detach.",
        "capabilities": {
            "qwen": {
                "label": "Qwen (local reasoning)",
                "env": ["VOICEOPS_AMD_ENDPOINT"],
            },
            "execution_engine": {
                "label": "Execution engine",
                "module": "voiceops.operational_state",
            },
            "approval_gate": {
                "label": "Approval gate",
                "module": "voiceops.approval",
            },
            "execution_permits": {
                "label": "Execution permits",
                "module": "voiceops.execution_permit",
            },
            "evidence": {
                "label": "Evidence / audit trail",
                "module": "voiceops.audit",
            },
            "grandstream": {
                "label": "Grandstream UCM6104",
                "env": ["VOICEOPS_AMI_HOST", "VOICEOPS_AMI_PORT"],
            },
            "mcp_tools": {
                "label": "MCP / governed tools",
                "module": "voiceops.governed_tools",
            },
        },
    },
    "optional_adapters": {
        "label": "OPTIONAL ADAPTERS",
        "description": "Replaceable cloud capabilities. NOT_CONNECTED does not stop the core.",
        "capabilities": {
            "assemblyai": {"label": "AssemblyAI Voice Agent", "adapter": "assemblyai"},
            "boson": {"label": "Boson Higgs Realtime", "adapter": "boson"},
            "agentx": {"label": "AgentX", "adapter": "agentx"},
            "velodb": {"label": "VeloDB", "adapter": "velodb"},
            "edgeone": {"label": "EdgeOne", "adapter": "edgeone"},
            "memories_ai": {"label": "Memories.ai", "adapter": "memories_ai"},
            "workbuddy": {"label": "WorkBuddy", "adapter": "workbuddy"},
        },
    },
}


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def collect_core_status() -> dict[str, Any]:
    """Report CORE LOCAL availability — always returns operational core even if optional adapters fail."""
    from ..adapters.live_ha_provider import fetch_ha_snapshot
    from ..adapters.live_telephony_provider import fetch_ami_telephony_snapshot

    qwen_endpoint = os.getenv("VOICEOPS_AMD_ENDPOINT", "http://127.0.0.1:18000/v1/chat/completions")
    qwen_configured = bool(os.getenv("VOICEOPS_AMD_ENDPOINT", "").strip()) or qwen_endpoint.startswith("http")

    ha = fetch_ha_snapshot()
    ami = fetch_ami_telephony_snapshot()

    return {
        "tier": "CORE_LOCAL",
        "truth": "OPERATIONAL",
        "narrative": (
            "InnerOS is not another cloud agent. Intelligence and execution run locally. "
            "Cloud AI services are replaceable capabilities."
        ),
        "capabilities": {
            "qwen": {
                "truth": "CONFIGURED" if qwen_configured else "LOCAL_DEFAULT",
                "endpoint": qwen_endpoint,
                "status": "ready",
            },
            "execution_engine": {"truth": "REAL", "status": "ready"},
            "approval_gate": {"truth": "REAL", "status": "fail_closed"},
            "execution_permits": {"truth": "REAL", "status": "ready"},
            "evidence": {"truth": "REAL", "status": "ready"},
            "grandstream": {
                "truth": ami.get("truth", "NOT_CONNECTED"),
                "status": ami.get("status", "unknown"),
            },
            "home_assistant": {
                "truth": ha.get("truth", "SNAPSHOT"),
                "status": ha.get("status", "unknown"),
            },
            "mcp_tools": {
                "truth": "REAL",
                "status": "ready",
                "enabled": _env_truthy("VOICEOPS_ENABLE_GOVERNED_TOOLS", True),
            },
        },
    }
