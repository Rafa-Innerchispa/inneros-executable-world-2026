from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AdapterStatus:
    adapter_id: str
    provider: str
    tier: str = "OPTIONAL"
    truth: str = "NOT_CONNECTED"
    status: str = "NOT_CONNECTED"
    mode: str = "disabled"
    ready: bool = False
    remote_confirmed: bool = False
    evidence_note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "adapter_id": self.adapter_id,
            "provider": self.provider,
            "tier": self.tier,
            "truth": self.truth,
            "status": self.status,
            "mode": self.mode,
            "ready": self.ready,
            "remote_confirmed": self.remote_confirmed,
            "evidence_note": self.evidence_note,
        }
        payload.update(self.extra)
        return payload
