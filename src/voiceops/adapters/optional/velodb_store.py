"""VeloDB optional execution/evidence store — MySQL-compatible (Doris/VeloDB)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .base import env_truthy

logger = logging.getLogger(__name__)

_TABLE = "execution_events"
_LAST_INSERT_VERIFIED: bool = False
_PROBE_CACHE: dict[str, Any] = {"ts": 0.0, "result": None}
_PROBE_TTL_SEC = 30.0


def _config() -> dict[str, Any]:
    return {
        "host": os.getenv("VELODB_HOST", "").strip(),
        "port": int(os.getenv("VELODB_PORT", "9030") or "9030"),
        "user": os.getenv("VELODB_USER", "admin").strip(),
        "password": os.getenv("VELODB_PASSWORD", ""),
        "database": os.getenv("VELODB_DATABASE", "inneros_executable_world").strip(),
    }


def _connect(*, database: str | None = None):
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL not installed — pip install PyMySQL") from exc

    cfg = _config()
    if not cfg["host"]:
        raise RuntimeError("VELODB_HOST unset")

    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=database or cfg["database"],
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
        autocommit=True,
    )


def _ensure_schema(conn) -> None:
    cfg = _config()
    db = cfg["database"]
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
        cur.execute(f"USE `{db}`")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{_TABLE}` (
                event_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(128) NOT NULL,
                `timestamp` DATETIME NOT NULL,
                event_type VARCHAR(128) NOT NULL,
                intent VARCHAR(512) NULL,
                tool VARCHAR(128) NULL,
                approval_status VARCHAR(64) NULL,
                permit_id VARCHAR(128) NULL,
                action VARCHAR(256) NULL,
                execution_result VARCHAR(512) NULL,
                verification VARCHAR(64) NULL,
                truth VARCHAR(64) NULL,
                latency_ms INT NULL,
                evidence_hash VARCHAR(128) NULL,
                metadata_json TEXT NULL
            )
            DUPLICATE KEY(event_id)
            """
        )


def _record_to_row(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data") if isinstance(record.get("data"), dict) else {}
    metadata = {
        k: v
        for k, v in record.items()
        if k not in {"event_id", "session_id", "timestamp", "event_type", "data"}
    }
    if data:
        metadata["data"] = data

    evidence_hash = None
    if isinstance(data, dict):
        evidence_hash = data.get("evidence_sha256") or data.get("evidence_hash")
    if not evidence_hash:
        evidence_hash = hashlib.sha256(
            json.dumps(record, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    ts_raw = record.get("timestamp")
    if isinstance(ts_raw, str):
        ts_value = ts_raw.replace("Z", "+00:00")
        try:
            ts_dt = datetime.fromisoformat(ts_value)
        except ValueError:
            ts_dt = datetime.now(timezone.utc)
    else:
        ts_dt = datetime.now(timezone.utc)

    return {
        "event_id": record.get("event_id") or uuid.uuid4().hex,
        "session_id": str(record.get("session_id") or "executable-world-session"),
        "timestamp": ts_dt.astimezone(timezone.utc).replace(tzinfo=None),
        "event_type": str(record.get("event_type") or "voiceops.event"),
        "intent": data.get("intent") if isinstance(data, dict) else None,
        "tool": data.get("tool") if isinstance(data, dict) else None,
        "approval_status": data.get("approval_status") if isinstance(data, dict) else None,
        "permit_id": data.get("permit_id") if isinstance(data, dict) else None,
        "action": data.get("action_type") or data.get("action") if isinstance(data, dict) else None,
        "execution_result": data.get("result_status") if isinstance(data, dict) else None,
        "verification": data.get("verification") if isinstance(data, dict) else None,
        "truth": data.get("truth") if isinstance(data, dict) else None,
        "latency_ms": data.get("latency_ms") if isinstance(data, dict) else None,
        "evidence_hash": evidence_hash,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, default=str),
    }


def _insert_row(conn, row: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO `{_TABLE}` (
                event_id, session_id, `timestamp`, event_type, intent, tool,
                approval_status, permit_id, action, execution_result,
                verification, truth, latency_ms, evidence_hash, metadata_json
            ) VALUES (
                %(event_id)s, %(session_id)s, %(timestamp)s, %(event_type)s,
                %(intent)s, %(tool)s, %(approval_status)s, %(permit_id)s,
                %(action)s, %(execution_result)s, %(verification)s, %(truth)s,
                %(latency_ms)s, %(evidence_hash)s, %(metadata_json)s
            )
            """,
            row,
        )


def _select_row(conn, event_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT event_id, session_id, event_type, evidence_hash
            FROM `{_TABLE}`
            WHERE event_id = %s
            LIMIT 1
            """,
            (event_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "event_id": row[0],
            "session_id": row[1],
            "event_type": row[2],
            "evidence_hash": row[3],
        }


def verify_insert_select(*, probe: bool = False) -> dict[str, Any]:
    """CONNECT → CREATE TABLE → INSERT → SELECT readback."""
    if not env_truthy("EXECUTABLE_ENABLE_VELODB", False):
        return {"ok": False, "reason": "disabled"}

    cfg = _config()
    if not cfg["host"]:
        return {"ok": False, "reason": "VELODB_HOST unset"}
    if not cfg["password"]:
        return {"ok": False, "reason": "VELODB_PASSWORD unset"}

    started = time.monotonic()
    event_id = f"probe-{uuid.uuid4().hex[:16]}" if probe else uuid.uuid4().hex
    row = {
        "event_id": event_id,
        "session_id": "velodb-probe" if probe else "executable-world-session",
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
        "event_type": "voiceops.velodb_probe" if probe else "voiceops.verify",
        "intent": None,
        "tool": None,
        "approval_status": None,
        "permit_id": None,
        "action": None,
        "execution_result": "probe_ok" if probe else "verify_ok",
        "verification": "insert_select",
        "truth": "REAL",
        "latency_ms": None,
        "evidence_hash": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "metadata_json": json.dumps({"probe": probe}, ensure_ascii=False),
    }

    try:
        conn = _connect(database=None)
        try:
            _ensure_schema(conn)
            _insert_row(conn, row)
            readback = _select_row(conn, event_id)
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("VeloDB verify failed: %s", exc)
        return {"ok": False, "reason": str(exc), "host": cfg["host"], "port": cfg["port"]}

    if not readback or readback.get("event_id") != event_id:
        return {"ok": False, "reason": "readback_mismatch", "event_id": event_id}

    global _LAST_INSERT_VERIFIED
    _LAST_INSERT_VERIFIED = True
    return {
        "ok": True,
        "event_id": event_id,
        "session_id": readback.get("session_id"),
        "evidence_hash": readback.get("evidence_hash"),
        "latency_ms": int((time.monotonic() - started) * 1000),
        "database": cfg["database"],
    }


def probe_velodb(*, timeout: float = 2.0) -> dict[str, Any]:
    """Cached INSERT+SELECT verification — REAL requires proven readback."""
    del timeout  # connect timeouts configured on pymysql
    now = time.monotonic()
    cached = _PROBE_CACHE.get("result")
    if cached and (now - float(_PROBE_CACHE.get("ts") or 0)) < _PROBE_TTL_SEC:
        return cached

    result = verify_insert_select(probe=True)
    _PROBE_CACHE["ts"] = now
    _PROBE_CACHE["result"] = result
    return result


def append_event(record: dict[str, Any]) -> dict[str, Any]:
    if not env_truthy("EXECUTABLE_ENABLE_VELODB", False):
        return {"stored": False, "reason": "disabled"}

    cfg = _config()
    if not cfg["host"]:
        return {"stored": False, "reason": "VELODB_HOST unset"}
    if not cfg["password"]:
        return {"stored": False, "reason": "VELODB_PASSWORD unset"}

    row = _record_to_row(record)
    started = time.monotonic()
    try:
        conn = _connect()
        try:
            _ensure_schema(conn)
            _insert_row(conn, row)
            readback = _select_row(conn, row["event_id"])
        finally:
            conn.close()
    except Exception as exc:
        return {"stored": False, "reason": str(exc)}

    if not readback:
        return {"stored": False, "reason": "readback_missing", "event_id": row["event_id"]}

    global _LAST_INSERT_VERIFIED
    _LAST_INSERT_VERIFIED = True
    return {
        "stored": True,
        "event_id": row["event_id"],
        "session_id": readback.get("session_id"),
        "evidence_hash": readback.get("evidence_hash"),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
