"""EdgeOne optional witness — sanitized execution receipts only."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import env_truthy

_LAST_WITNESS_OK: bool = False
_PROBE_CACHE: dict[str, Any] = {"ts": 0.0, "result": None}
_PROBE_TTL_SEC = 30.0


def witness_url() -> str:
    return os.getenv("EDGEONE_WITNESS_URL", "").strip().rstrip("/")


def pages_project() -> str:
    return os.getenv("EDGEONE_PAGES_PROJECT", "").strip()


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Never forward secrets — keep receipt fields only."""
    data = record.get("data") if isinstance(record.get("data"), dict) else {}
    safe_data = {
        k: v
        for k, v in data.items()
        if k.lower() not in {"token", "secret", "password", "api_key", "signature"}
    }
    return {
        "timestamp": record.get("timestamp"),
        "event_type": record.get("event_type"),
        "session_id": record.get("session_id"),
        "permit_id": safe_data.get("permit_id"),
        "proposal_id": safe_data.get("proposal_id"),
        "action_type": safe_data.get("action_type"),
        "result_status": safe_data.get("result_status"),
        "evidence_sha256": safe_data.get("evidence_sha256") or safe_data.get("evidence_hash"),
    }


def probe_witness(*, timeout: float = 2.0) -> dict[str, Any]:
    import time

    now = time.monotonic()
    cached = _PROBE_CACHE.get("result")
    if cached and (now - float(_PROBE_CACHE.get("ts") or 0)) < _PROBE_TTL_SEC:
        return cached

    if not env_truthy("EXECUTABLE_ENABLE_EDGEONE", False):
        result = {"ok": False, "reason": "disabled"}
        _PROBE_CACHE.update(ts=now, result=result)
        return result

    url = witness_url()
    project = pages_project()
    if not url:
        if project:
            result = {"ok": True, "mode": "configured_metadata_only", "project": project}
        else:
            result = {"ok": False, "reason": "witness_url_and_project_unset"}
        _PROBE_CACHE.update(ts=now, result=result)
        return result

    for method in ("GET", "HEAD"):
        request = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                if resp.status in {200, 204}:
                    result = {"ok": True, "mode": "witness_reachable", "url": url, "method": method}
                    _PROBE_CACHE.update(ts=now, result=result)
                    return result
        except Exception:
            continue

    result = {"ok": False, "reason": "witness_unreachable", "url": url}
    _PROBE_CACHE.update(ts=now, result=result)
    return result


def witness_event(event_type: str, record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_EDGEONE", False):
        return {"stored": False, "reason": "disabled"}

    url = witness_url()
    payload = {
        "witness": "inneros-executable-world",
        "event_type": event_type,
        "receipt": _sanitize_record(record),
        "pages_project": pages_project() or None,
    }
    if not url:
        return {
            "stored": False,
            "reason": "witness_url_unset",
            "metadata_only": True,
            "pages_project": pages_project() or None,
        }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.5) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            stored = resp.status in {200, 201, 202}
            if stored:
                global _LAST_WITNESS_OK
                _LAST_WITNESS_OK = True
            return {"stored": stored, "status": resp.status, "body": body[:200], "url": url}
    except Exception as exc:
        return {"stored": False, "reason": str(exc), "url": url}


def verify_witness_post(*, timeout: float = 2.5) -> dict[str, Any]:
    """POST a sanitized probe receipt — REAL requires successful response."""
    import time

    now = time.monotonic()
    cache_key = "verify"
    cached = _PROBE_CACHE.get(cache_key)
    if cached and (now - float(_PROBE_CACHE.get(f"{cache_key}_ts") or 0)) < _PROBE_TTL_SEC:
        return cached

    if not env_truthy("EXECUTABLE_ENABLE_EDGEONE", False):
        return {"ok": False, "reason": "disabled"}
    url = witness_url()
    if not url:
        project = pages_project()
        if project:
            return {"ok": False, "reason": "configured_only", "project": project}
        return {"ok": False, "reason": "witness_url_unset"}

    result = witness_event(
        "voiceops.edgeone_probe",
        {
            "timestamp": "probe",
            "session_id": "edgeone-probe",
            "event_type": "voiceops.edgeone_probe",
            "data": {"result_status": "probe_ok"},
        },
    )
    payload = {"ok": bool(result.get("stored")), "witness": result, "url": url}
    _PROBE_CACHE[cache_key] = payload
    _PROBE_CACHE[f"{cache_key}_ts"] = now
    return payload
