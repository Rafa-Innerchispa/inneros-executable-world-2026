from __future__ import annotations

from typing import Any

from ..core.capability_matrix import CAPABILITY_MATRIX, collect_core_status
from .optional.registry import collect_optional_adapters


def collect_integration_status() -> dict[str, Any]:
    """Provider-agnostic status: CORE LOCAL always operational; optional adapters degrade gracefully."""
    core = collect_core_status()
    optional = collect_optional_adapters()
    adapters = optional.get("adapters", {})
    assemblyai = adapters.get("assemblyai", {})
    primary = optional.get("primary_voice_adapter", "local_qwen")

    if primary == "assemblyai":
        audio_source = "ASSEMBLYAI"
    elif primary == "boson":
        audio_source = "BOSON"
    else:
        audio_source = "LOCAL_QWEN"

    return {
        "product": "inneros-executable-world",
        "hostname": "executable.creatorcore.ai",
        "architecture": "provider_agnostic",
        "audio_source": audio_source,
        "core_truth": core.get("truth", "OPERATIONAL"),
        "capability_matrix": CAPABILITY_MATRIX,
        "core_local": core,
        "optional_adapters": optional,
        # Back-compat keys for existing UI panels
        "partner_integrations": adapters,
        "assemblyai": assemblyai,
        "home_assistant": core.get("capabilities", {}).get("home_assistant", {}),
        "grandstream_ami": core.get("capabilities", {}).get("grandstream", {}),
        "qwen": core.get("capabilities", {}).get("qwen", {}),
    }
