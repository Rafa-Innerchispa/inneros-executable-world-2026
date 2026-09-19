from __future__ import annotations

from typing import Any

from . import agentx, assemblyai, boson, edgeone, memories_ai, velodb, workbuddy

_OPTIONAL_MODULES = (
    assemblyai,
    boson,
    agentx,
    velodb,
    edgeone,
    memories_ai,
    workbuddy,
)


def collect_optional_adapters() -> dict[str, Any]:
    adapters: dict[str, dict[str, Any]] = {}
    connected = 0
    for module in _OPTIONAL_MODULES:
        payload = module.status().to_dict()
        adapter_id = payload["adapter_id"]
        adapters[adapter_id] = payload
        if payload.get("truth") in {"REAL", "CONFIGURED"}:
            connected += 1

    primary_voice = None
    if adapters.get("assemblyai", {}).get("truth") == "REAL":
        primary_voice = "assemblyai"
    elif adapters.get("boson", {}).get("truth") == "REAL":
        primary_voice = "boson"
    else:
        primary_voice = "local_qwen"

    return {
        "tier": "OPTIONAL_ADAPTERS",
        "connected_count": connected,
        "total_count": len(adapters),
        "primary_voice_adapter": primary_voice,
        "degradation_note": (
            "Core local runtime remains operational when optional adapters are NOT_CONNECTED."
        ),
        "adapters": adapters,
    }
