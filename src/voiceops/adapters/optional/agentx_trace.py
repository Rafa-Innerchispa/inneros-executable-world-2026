"""AgentX self-hosted local tracing (no paid hosted API required)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import env_truthy


def self_hosted_url() -> str:
    return (
        os.getenv("AGENTX_SELF_HOSTED_URL")
        or os.getenv("AGENTX_ENDPOINT")
        or "http://127.0.0.1:8090"
    ).rstrip("/")


def probe_self_hosted(*, timeout: float = 1.5) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_AGENTX", False):
        return {"ok": False, "reason": "disabled"}
    base = self_hosted_url()
    for path in ("/health", "/healthz", "/v1/health"):
        url = f"{base}{path}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return {"ok": True, "url": url}
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return {"ok": False, "reason": "probe_failed", "base": base}


def emit_trace(event_type: str, record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_AGENTX", False):
        return {"stored": False, "reason": "disabled"}

    payload = {
        "name": event_type,
        "kind": "span",
        "attributes": record,
    }
    url = f"{self_hosted_url()}/v1/traces"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.0) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return {"stored": resp.status in {200, 201, 202, 204}, "status": resp.status, "body": body[:200]}
    except Exception as exc:
        return {"stored": False, "reason": str(exc), "url": url}
