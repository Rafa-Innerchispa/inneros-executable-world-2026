from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class VoiceExecutionPermit:
    permit_id: str
    session_id: str
    source_event_id: str
    action_type: str
    transcript_hash: str
    proposal_hash: str
    state_hash: str
    issued_at: float
    expires_at: float
    signature: str
    used_at: float | None = None

    def safe_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["signature"] = "[sealed]"
        return data


class VoiceExecutionPermitManager:
    """Issues short-lived, single-use permits bound to exact observed state."""

    def __init__(self, *, ttl_seconds: float = 45.0, signing_key: bytes | None = None) -> None:
        self.ttl_seconds = max(5.0, min(float(ttl_seconds), 300.0))
        self._signing_key = signing_key or secrets.token_bytes(32)
        self._permits: dict[str, VoiceExecutionPermit] = {}

    @staticmethod
    def stable_hash(value: Any) -> str:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def issue(
        self,
        *,
        session_id: str,
        source_event_id: str,
        action_type: str,
        approval_transcript: str,
        proposal: Any,
        state_snapshot: Any,
        now: float | None = None,
    ) -> VoiceExecutionPermit:
        issued = time.time() if now is None else float(now)
        permit_id = f"vxp_{secrets.token_hex(8)}"
        transcript_hash = self.stable_hash(approval_transcript.strip())
        proposal_hash = self.stable_hash(proposal)
        state_hash = self.stable_hash(state_snapshot)
        expires_at = issued + self.ttl_seconds
        body = self._signature_body(
            permit_id=permit_id,
            session_id=session_id,
            source_event_id=source_event_id,
            action_type=action_type,
            transcript_hash=transcript_hash,
            proposal_hash=proposal_hash,
            state_hash=state_hash,
            issued_at=issued,
            expires_at=expires_at,
        )
        signature = hmac.new(self._signing_key, body, hashlib.sha256).hexdigest()
        permit = VoiceExecutionPermit(
            permit_id=permit_id,
            session_id=session_id,
            source_event_id=source_event_id,
            action_type=action_type,
            transcript_hash=transcript_hash,
            proposal_hash=proposal_hash,
            state_hash=state_hash,
            issued_at=issued,
            expires_at=expires_at,
            signature=signature,
        )
        self._permits[permit_id] = permit
        return permit

    def consume(
        self,
        permit_id: str,
        *,
        session_id: str,
        source_event_id: str,
        action_type: str,
        approval_transcript: str,
        proposal: Any,
        state_snapshot: Any,
        now: float | None = None,
    ) -> tuple[bool, str, VoiceExecutionPermit | None]:
        permit = self._permits.get(permit_id)
        if permit is None:
            return False, "permit_not_found", None
        current = time.time() if now is None else float(now)
        if permit.used_at is not None:
            return False, "permit_already_used", permit
        if current > permit.expires_at:
            return False, "permit_expired", permit
        expected = {
            "session_id": session_id,
            "source_event_id": source_event_id,
            "action_type": action_type,
            "transcript_hash": self.stable_hash(approval_transcript.strip()),
            "proposal_hash": self.stable_hash(proposal),
            "state_hash": self.stable_hash(state_snapshot),
        }
        for key, value in expected.items():
            if getattr(permit, key) != value:
                return False, f"permit_binding_mismatch:{key}", permit
        body = self._signature_body(
            permit_id=permit.permit_id,
            session_id=permit.session_id,
            source_event_id=permit.source_event_id,
            action_type=permit.action_type,
            transcript_hash=permit.transcript_hash,
            proposal_hash=permit.proposal_hash,
            state_hash=permit.state_hash,
            issued_at=permit.issued_at,
            expires_at=permit.expires_at,
        )
        expected_signature = hmac.new(self._signing_key, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, permit.signature):
            return False, "permit_signature_invalid", permit
        permit.used_at = current
        return True, "permit_consumed", permit

    @staticmethod
    def _signature_body(**fields: Any) -> bytes:
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
