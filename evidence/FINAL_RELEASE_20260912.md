# Final Release Evidence — 2026-09-12 GYT

## Canonical release

- Repository: `Rafa-Innerchispa/inneros-voiceops-assemblyai`
- Canonical source SHA before this release-doc/CI PR: `50fea125b3b19ede3f228a3263d5af3eef3aa132`
- Cross-chat reconciliation PR: #8
- Release truth: `main` is the only source of product truth. Historical `local-agent/*` and feature branches are not continuation points.

## Code verification

Re-run against the canonical reconciled source on 2026-09-12/13 GYT:

- `python3 -m pytest -q` -> **60/60 PASS**
- `python3 -m compileall -q src tests` -> **PASS**
- `git diff --check` -> **PASS**
- Runtime workspace was rehydrated from GitHub and verified at exact SHA `50fea125b3b19ede3f228a3263d5af3eef3aa132`.

The current test surface covers governed approval, execution permits, Guardian event binding, AssemblyAI streaming behavior, server-side temporary Voice Agent tokens, evidence/replay, HTTP judge flow, local AMD reasoning adapter, and integration boundaries.

## AssemblyAI provider

Global reusable provider preflight: **PASS**.

Provider contract is registered in InnerOS Resource Fabric with Owner Vault authentication and capabilities including realtime STT, Voice Agent sessions, TTS, semantic turn detection, barge-in, tool calling, session resume, keyterms, agent context, PII redaction, entity detection, content moderation, and LLM Gateway.

The master AssemblyAI credential is not stored in this repository and is not exposed to browser code.

Prior captured live evidence in the canonical internal continuity includes:

- real AssemblyAI provider WebSocket/TTS smoke: **PASS**
- AssemblyAI tool-call probe: **PASS**
- audio -> AssemblyAI STT -> InnerOS -> AMD .5 -> explicit approval -> synthetic action -> Evidence/Replay -> spoken completion: **PASS**
- three consecutive full AMD .5 live E2E runs after idempotency hardening: **PASS**

These are historical captured runtime proofs, not claims that the public Cloud Run revision currently reaches the private AMD node.

## WhatsApp Voice Fabric

Reusable platform implementation is outside this repo and was merged through `innerops-agentic-platform` PR #33.

Evidence from that merge:

- focused AssemblyAI + WhatsApp tests: **18/18 PASS**
- explicit AssemblyAI route: **PASS**
- local Whisper fallback: **PASS**
- media/file sanitization: **PASS**
- compileall / diff-check: **PASS**

VoiceOps consumes that capability instead of owning another WhatsApp/STT implementation.

## Public deployment

The previous public service was found to be serving stale image tag `6bdcedc`. It was replaced with a container built from the exact canonical SHA above.

Cloud Build:

- build id: `1c9d2fc5-5eba-41b7-8279-c4fed479dc9c`
- image: `us-central1-docker.pkg.dev/innerops-agentic-platform/inneros/voiceops:50fea125`

Cloud Run:

- service: `voiceops`
- region: `us-central1`
- revision: `voiceops-00002-r68`
- traffic: **100%**
- `VOICEOPS_REASONER=synthetic`
- `VOICEOPS_ENABLE_LIVE_ASSEMBLYAI=false`
- `VOICEOPS_PRODUCTION_WRITES=false`

Public judge URL:

`https://voiceops.creatorcore.ai/`

Verified after deployment:

- `/` -> **HTTP 200**
- `/api/state` -> **HTTP 200**
- public state truthfully reports `mode=synthetic_demo` and `production_writes=false`

### Known deployment discrepancy

`/healthz` currently returns **404** from the deployed service even though the canonical `webapp.py` contains the route. `/api/state` is therefore the verified operational health surface for this release. Do not claim `/healthz` PASS until this discrepancy is isolated.

## Public/live truth boundary

The public Cloud Run demo is intentionally safe and synthetic. Live AssemblyAI is not enabled in that revision because the global Owner Vault credential has not been bound to Cloud Run through a Secret Manager mapping. We deliberately did not copy the raw API key into plain environment variables merely to make a demo badge turn green.

The private/local stack has captured live AssemblyAI + AMD .5 evidence. The public judge surface demonstrates the same governance state machine, explicit approval, single-use permit, action evidence and replay without production writes.

## Safety

- no production business writes
- no camera credentials or RTSP URLs
- no customer footage or customer PII in public evidence
- no raw AssemblyAI key in repo/browser
- tool invocation is not authorization
- ambiguous authorization fails closed
- consequential demo execution requires explicit approval and a valid single-use permit
- public reasoner is labeled synthetic; AMD live is claimed only from captured live evidence

## Release verdict

**TECHNICAL BUILD: PASS / SUBMISSION-READY CORE**

Remaining non-code work is presentation/submission packaging and the final organizer submission action. Public live AssemblyAI enablement is an optional secure deployment enhancement, not a reason to fork or rebuild the product.
