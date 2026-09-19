"""EdgeOne optional witness — deployment metadata only, no InnerOS migration."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import env_truthy


def witness_url() -> str:
    return os.getenv("EDGEONE_WITNESS_URL", "").strip().rstrip("/")


def probe_witness(*, timeout: float = 2.0) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_EDGEONE", False):
        return {"ok": False, "reason": "disabled"}
    url = witness_url()
    if not url:
        project = os.getenv("EDGEONE_PAGES_PROJECT", "").strip()
        if project:
            return {"ok": True, "mode": "configured_metadata_only", "project": project}
        return {"ok": False, "reason": "EDGEONE_WITNESS_URL unset"}
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return {"ok": resp.status == 200, "url": url}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "url": url}


def witness_event(event_type: str, record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_EDGEONE", False):
        return {"stored": False, "reason": "disabled"}

    url = witness_url()
    payload = {
        "witness": "inneros-executable-world",
        "event_type": event_type,
        "record": record,
        "pages_project": os.getenv("EDGEONE_PAGES_PROJECT", "").strip() or None,
    }
    if not url:
        return {"stored": False, "reason": "witness_url_unset", "metadata_only": True}

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as resp:
            return {"stored": resp.status in {200, 201, 202}, "status": resp.status}
    except Exception as exc:
        return {"stored": False, "reason": str(exc)}
