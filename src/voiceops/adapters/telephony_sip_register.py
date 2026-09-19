"""Keep the VoiceOps server SIP agent extension registered on the UCM6104."""

from __future__ import annotations

import logging
import os
import threading
import time

from voiceops.adapters.sip_transport import GrandstreamSipClient, SipAuth, SipError

_log = logging.getLogger(__name__)
_thread: threading.Thread | None = None
_stop = threading.Event()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _agent_auth() -> SipAuth | None:
    ext = _env("VOICEOPS_TELEPHONY_SIP_AGENT_EXT", "1003")
    secret = _env("VOICEOPS_TELEPHONY_SIP_AGENT_SECRET")
    if not secret:
        return None
    return SipAuth(ext, secret)


def _register_once() -> bool:
    auth = _agent_auth()
    if auth is None:
        return False
    host = _env("VOICEOPS_TELEPHONY_AMI_HOST", "192.168.1.6")
    sip_port = int(_env("VOICEOPS_TELEPHONY_SIP_PORT", "4321") or "4321")
    local_ip = _env("VOICEOPS_TELEPHONY_LOCAL_IP", "192.168.1.4")
    client = GrandstreamSipClient(host=host, auth=auth, local_ip=local_ip, sip_port=sip_port)
    try:
        client.register(expires=120)
        _log.info("SIP agent ext %s registered from %s", auth.extension, local_ip)
        return True
    finally:
        client.close()


def _loop(interval_seconds: float) -> None:
    while not _stop.is_set():
        try:
            _register_once()
        except (SipError, OSError, ValueError) as exc:
            _log.warning("SIP registration failed: %s", exc)
        _stop.wait(interval_seconds)


def start_persistent_sip_registration() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    if _agent_auth() is None:
        _log.info("SIP keepalive disabled (VOICEOPS_TELEPHONY_SIP_AGENT_SECRET unset)")
        return
    interval = float(_env("VOICEOPS_TELEPHONY_SIP_REGISTER_INTERVAL", "90") or "90")
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(interval,), name="voiceops-sip-register", daemon=True)
    _thread.start()
    _log.info("SIP keepalive started (interval %ss)", interval)


def stop_persistent_sip_registration() -> None:
    _stop.set()
