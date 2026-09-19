"""In-memory telephony call transcript/state for the web panel (phone audio only)."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {
    "active": False,
    "phase": "idle",
    "target": "",
    "voice_provider": "",
    "user_lines": [],
    "agent_lines": [],
    "agent_partial": "",
    "user_partial": "",
    "events": [],
    "started_at": None,
    "ended_at": None,
    "error": None,
    "debug": {},
}


def reset_call_state(*, target: str, voice_provider: str) -> None:
    with _lock:
        _state.update(
            {
                "active": True,
                "phase": "ringing",
                "target": target,
                "voice_provider": voice_provider,
                "user_lines": [],
                "agent_lines": [],
                "agent_partial": "",
                "user_partial": "",
                "events": [],
                "started_at": time.time(),
                "ended_at": None,
                "error": None,
                "debug": {},
            }
        )


def update_call_debug(**fields: Any) -> None:
    with _lock:
        _state["debug"].update({k: v for k, v in fields.items() if v is not None})


def set_call_phase(phase: str) -> None:
    with _lock:
        _state["phase"] = phase
        _state["events"].append({"t": time.time(), "phase": phase})


def append_user_line(text: str) -> None:
    line = str(text or "").strip()
    if not line:
        return
    with _lock:
        if _state["user_lines"] and _state["user_lines"][-1] == line:
            return
        _state["user_lines"].append(line)


def append_agent_line(text: str) -> None:
    line = str(text or "").strip()
    if not line:
        return
    with _lock:
        if _state["agent_lines"] and _state["agent_lines"][-1] == line:
            return
        _state["agent_lines"].append(line)
        _state["agent_partial"] = ""


def set_agent_partial(text: str) -> None:
    with _lock:
        _state["agent_partial"] = str(text or "").strip()


def set_user_partial(text: str) -> None:
    with _lock:
        _state["user_partial"] = str(text or "").strip()


def finish_call(*, ok: bool, error: str | None = None, phase: str | None = None) -> None:
    with _lock:
        _state["active"] = False
        if phase:
            _state["phase"] = phase
        else:
            _state["phase"] = "completed" if ok else "failed"
        _state["ended_at"] = time.time()
        _state["error"] = error


def call_is_active() -> bool:
    with _lock:
        return bool(_state["active"])


def snapshot() -> dict[str, Any]:
    with _lock:
        return {
            "active": _state["active"],
            "phase": _state["phase"],
            "target": _state["target"],
            "voice_provider": _state["voice_provider"],
            "user_lines": list(_state["user_lines"]),
            "agent_lines": list(_state["agent_lines"]),
            "agent_partial": _state["agent_partial"],
            "user_partial": _state["user_partial"],
            "user_count": len(_state["user_lines"]),
            "agent_count": len(_state["agent_lines"]),
            "error": _state["error"],
            "debug": dict(_state["debug"]),
        }
