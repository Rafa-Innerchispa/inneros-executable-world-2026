"""AgentX self-hosted local tracing via OTLP/HTTP (no paid hosted API)."""

from __future__ import annotations

import json
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Any

from .base import env_truthy

_LAST_TRACE_OK: bool = False
_PROBE_CACHE: dict[str, Any] = {"ts": 0.0, "result": None}
_PROBE_TTL_SEC = 20.0


def self_hosted_base() -> str:
    """Root URL of agentx-trace-eval (default port 4700)."""
    return (
        os.getenv("AGENTX_SELF_HOSTED_URL")
        or os.getenv("AGENTX_ENDPOINT")
        or "http://127.0.0.1:4700"
    ).rstrip("/")


def _api_key() -> str:
    return os.getenv("AGENTX_API_KEY", "").strip()


def _headers(*, json_body: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if json_body:
        headers["Content-Type"] = "application/json"
    api_key = _api_key()
    if api_key:
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def probe_self_hosted(*, timeout: float = 1.5) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_AGENTX", False):
        return {"ok": False, "reason": "disabled"}

    base = self_hosted_base()
    for path in ("/health", "/healthz"):
        url = f"{base}{path}"
        try:
            request = urllib.request.Request(url, headers=_headers(), method="GET")
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                if resp.status == 200:
                    return {"ok": True, "url": url, "base": base}
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return {"ok": False, "reason": "health_probe_failed", "base": base}


def _otlp_endpoint() -> str:
    explicit = os.getenv("AGENTX_OTLP_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    return f"{self_hosted_base()}/api/v1/otel/v1/traces"


def _otlp_span(name: str, attributes: dict[str, Any], *, session_id: str) -> dict[str, Any]:
    now_ns = int(time.time() * 1_000_000_000)
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    attr_list = [
        {"key": key, "value": {"stringValue": str(value)}}
        for key, value in attributes.items()
        if value is not None
    ]
    attr_list.append({"key": "agentx.session_id", "value": {"stringValue": session_id}})
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "inneros-executable-world"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "voiceops.sponsor_evidence"},
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": name,
                                "kind": 1,
                                "startTimeUnixNano": str(now_ns),
                                "endTimeUnixNano": str(now_ns + 1_000_000),
                                "attributes": attr_list,
                                "status": {"code": 1},
                            }
                        ],
                    }
                ],
            }
        ]
    }


def emit_trace(event_type: str, record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_AGENTX", False):
        return {"stored": False, "reason": "disabled"}

    health = probe_self_hosted()
    if not health.get("ok"):
        return {"stored": False, "reason": "health_failed", "probe": health}

    session_id = str(record.get("session_id") or "executable-world-session")
    payload = _otlp_span(
        event_type,
        {
            "voiceops.event_type": event_type,
            "voiceops.record_json": json.dumps(record, ensure_ascii=False, default=str)[:4000],
        },
        session_id=session_id,
    )
    url = _otlp_endpoint()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(json_body=True),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3.0) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            stored = resp.status in {200, 201, 202, 204}
            if stored:
                global _LAST_TRACE_OK
                _LAST_TRACE_OK = True
            return {
                "stored": stored,
                "status": resp.status,
                "url": url,
                "body": body[:200],
            }
    except Exception as exc:
        return {"stored": False, "reason": str(exc), "url": url}


def verify_trace_roundtrip(*, timeout: float = 3.0) -> dict[str, Any]:
    """Health + one OTLP span — required before REAL."""
    del timeout
    if not env_truthy("EXECUTABLE_ENABLE_AGENTX", False):
        return {"ok": False, "reason": "disabled"}

    health = probe_self_hosted()
    if not health.get("ok"):
        return {"ok": False, "reason": "health_failed", "probe": health}

    result = emit_trace(
        "voiceops.agentx_probe",
        {"session_id": "agentx-probe", "probe": True, "timestamp": time.time()},
    )
    ok = bool(result.get("stored"))
    return {
        "ok": ok,
        "health": health,
        "trace": result,
        "last_trace_ok": _LAST_TRACE_OK,
    }


def probe_with_trace(*, timeout: float = 2.0) -> dict[str, Any]:
    now = time.monotonic()
    cached = _PROBE_CACHE.get("result")
    if cached and (now - float(_PROBE_CACHE.get("ts") or 0)) < _PROBE_TTL_SEC:
        return cached

    result = verify_trace_roundtrip(timeout=timeout)
    _PROBE_CACHE["ts"] = now
    _PROBE_CACHE["result"] = result
    return result
