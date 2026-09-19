# Project Continuity — InnerOS VoiceOps / AssemblyAI Hackathon

Last updated: 2026-09-13 GYT

## Canonical source of truth

- Repository: `Rafa-Innerchispa/inneros-voiceops-assemblyai`
- Canonical branch: `main`
- Current canonical main at continuity update: `7138fea77a4fa7fdd8b6dce9e9c02deedd2b67a4`
- Rule: do not resume development from historical feature branches. Any useful work must be reconciled into `main` first.

## Current product state

The technical VoiceOps core is submission-ready. Current `main` includes the governed AssemblyAI voice flow, local-first AMD reasoning, Guardian-bound execution permits, judge-facing web UI, public deployment work, release packaging/CI, and UCM6104 telephony integration.

Canonical public judge URL recorded in the project checklist:
- `https://voiceops.creatorcore.ai/`

## Verified evidence carried forward

Historical validated E2E milestone before final release packaging:
- AssemblyAI provider WebSocket/TTS smoke PASS.
- AssemblyAI tool-call probe PASS.
- Full audio -> AssemblyAI STT -> InnerOS -> AMD .5 -> explicit approval -> synthetic action -> evidence/replay -> spoken completion PASS.
- Three consecutive live AMD .5 E2E runs PASS after idempotency hardening.
- No production writes.

Release state recorded on current main:
- release-packaging PR #9 CI completed successfully;
- release merge recorded as `05887f268c90e3c5d649d5d045a9835cdaf6d372`;
- telephony integration subsequently advanced canonical main;
- reconciled source tests previously recorded as 60/60 PASS;
- current checklist requires a fresh exact-final-tree verification after telephony integration.

## Branch policy

1. `main` is the only canonical working truth.
2. Feature branches are temporary implementation surfaces only.
3. After a feature is merged and verified, do not continue work from that feature branch.
4. Before starting a new chat or agent session, fetch `main` and read this continuity file plus the canonical project docs.
5. If a branch contains unique work not in `main`, document the diff and either merge it with tests or explicitly archive/discard it. Do not silently fork the product state.
6. Do not create parallel implementations of existing VoiceOps capabilities.

## Known historical branches

The following branches are historical and must not be treated as canonical unless a verified diff proves unique useful work:
- `local-agent/assemblyai-voiceops-e2e`
- `chatgpt/voiceops-live-validation`
- `chatgpt/winning-golden-path-v2`
- `chatgpt/voiceops-assemblyai-managed-reconcile`
- `chatgpt/voiceops-cloudrun-ready-v2`
- `chatgpt/voiceops-workforce-visual-v2`

The former E2E branch contains the older merge chain including Guardian event-bound voice execution permits and the loopback Guardian bridge. That work has already been carried forward through the project release history; do not overwrite newer `main` with that branch.

## Current remaining P0

Follow `docs/HACKATHON_CHECKLIST.md` on `main`. Current remaining work is release hygiene and submission, not architecture reconstruction:

1. Run an exact-final-tree secret scan and preserve sanitized evidence.
2. Re-run tests/CI against current canonical `main` after telephony integration.
3. Capture fresh judge screenshots and a browser-microphone demo recording.
4. Upload final video/deck/media and place their URLs in the submission package.
5. Verify team/project metadata and organizer closing time.
6. Submit before the internal freeze recorded in the checklist.

## Resume protocol for any new ChatGPT / agent session

Read in this order:
1. `docs/PROJECT_CONTINUITY.md`
2. `docs/PROJECT_CANONICAL.md`
3. `docs/HACKATHON_CHECKLIST.md`
4. `README.md`
5. latest commits on `main`
6. current coordination / ops task for VoiceOps

Then continue only from the first incomplete P0 item. Never redesign from memory and never assume a historical branch is newer than `main`.

## Cross-project boundary

Physical Guardian remains an upstream event source only for this hackathon. Camera/perception/high-resolution pet/person development belongs to the Physical Guardian / AI Infra workstream and must not be developed inside the VoiceOps hackathon chat unless explicitly required as an integration boundary.
