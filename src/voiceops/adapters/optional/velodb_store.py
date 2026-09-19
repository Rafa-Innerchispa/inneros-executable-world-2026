"""VeloDB optional execution/evidence event store."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import env_truthy


def _base_url() -> str:
    return os.getenv("VELODB_URL", "").strip().rstrip("/")


def probe_velodb(*, timeout: float = 2.0) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_VELODB", False):
        return {"ok": False, "reason": "disabled"}
    base = _base_url()
    if not base:
        return {"ok": False, "reason": "VELODB_URL unset"}
    url = f"{base}/health"
    headers: dict[str, str] = {}
    api_key = os.getenv("VELODB_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return {"ok": resp.status == 200, "url": url}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "url": url}


def append_event(record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_VELODB", False):
        return {"stored": False, "reason": "disabled"}

    base = _base_url()
    if not base:
        return {"stored": False, "reason": "VELODB_URL unset"}

    url = f"{base}/v1/events"
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("VELODB_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url,
        data=json.dumps(record, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3.0) as resp:
            return {"stored": resp.status in {200, 201, 202}, "status": resp.status}
    except Exception as exc:
        return {"stored": False, "reason": str(exc), "url": url}
