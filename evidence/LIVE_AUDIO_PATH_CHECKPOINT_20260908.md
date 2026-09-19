# Live Audio Path Checkpoint — 2026-09-08

## Status
PARTIAL / implementation PASS, external AssemblyAI session pending credential/runtime validation.

## Implemented in this checkpoint
- `WavPCM16Source` validates PCM16 mono 16 kHz before streaming.
- WAV chunks are constrained to the AssemblyAI recommended 50–1000 ms range.
- Live CLI supports reproducible WAV input and optional microphone input.
- Live preflight reports only whether the SDK/key are present; it never prints a key.
- AssemblyAI adapter now accepts an InnerOS agent-reply callback.
- Final VoiceOps results automatically refresh AssemblyAI `agent_context` when a live client exists.
- Evidence records context-update metadata but not agent reply content.
- Session close remains fail-safe via `disconnect(terminate=True)`.
- `docs/LIVE_RUNBOOK.md` documents the live path and truth boundary.

## Verification
- `python3 -m pytest tests -q`: 25 PASS
- `python3 -m compileall -q src tests`: PASS
- No production writes.
- No customer PII, camera credentials, or private footage.
- No AssemblyAI secret committed.

## External truth boundary
Internal memory/coordination search did not find an existing AssemblyAI credential reference for this project. Therefore no live AssemblyAI session is claimed in this checkpoint.

A valid `ASSEMBLYAI_API_KEY` must be injected by the runtime/secret store before the first paid/live stream. The live harness is ready to fail closed when it is absent.

## Next proof
1. Inject credential server-side without committing it.
2. Run `voiceops-live --preflight`.
3. Stream one controlled PCM16 mono 16 kHz WAV fixture.
4. Confirm Begin -> partial/final Turn -> agent-context refresh -> Termination.
5. Persist sanitized evidence with provider session ID and audio duration.
6. Repeat with microphone input.
