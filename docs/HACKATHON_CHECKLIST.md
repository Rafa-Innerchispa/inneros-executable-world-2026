# Hackathon Checklist

Last verified: 2026-09-13 GYT

Legend:
- `[x]` verified, implemented, or backed by captured runtime evidence.
- `[ ]` still manual or still required before final organizer submission.
- Public Cloud Run and private live-stack claims are kept separate on purpose.

## Registration
- [x] Participation/application approved for the AssemblyAI Voice Agent Hackathon.
- [ ] Team created/joined on lablab.ai and project attached to that team.
- [ ] Team/project name aligned with **InnerOS VoiceOps** on the event page.
- [x] Organizer email/announcements checked during the active build window.

## Technology
- [x] AssemblyAI is visibly and materially used through the Voice Agent / Streaming v3 adapters.
- [x] Realtime lifecycle, partial/final turn handling, shutdown, agent-context refresh and tool boundaries are implemented and covered by tests.
- [x] Speech context / `agent_context` integration is implemented where useful.
- [x] Local-first routing is preserved and AMD .5 live local inference has captured evidence.
- [x] Failure behavior and secret handling are documented.
- [x] Real AssemblyAI provider WebSocket/TTS smoke was captured in the private live stack.
- [x] Audio -> AssemblyAI STT -> InnerOS -> AMD .5 -> approval -> synthetic action -> Evidence/Replay -> spoken completion was captured PASS.
- [x] Three consecutive full AMD .5 live E2E runs passed after idempotency hardening.
- [ ] Capture a fresh browser-microphone recording for the final demo video. This is media evidence, not missing core implementation.
- [ ] Public Cloud Run live AssemblyAI remains intentionally disabled until its Owner Vault credential is bound through a proper Secret Manager mapping.

## Product
- [x] Complete voice-to-action workflow exists.
- [x] Approval gate is explicit and fails closed on ambiguous/negated approval.
- [x] Business outcome is visible as a synthetic/demo work order.
- [x] Voice Execution Permit binds session/event/transcript/proposal/state/action and is single-use.
- [x] HTR is visible with MEASURED vs ESTIMATED truth boundaries.
- [x] Evidence/audit output is visible.
- [x] Captured-evidence replay path is visible.
- [x] Judge-facing one-screen UI exists.
- [x] Physical Guardian integration consumes sanitized `NormalizedEvent`; camera/detector logic remains outside VoiceOps.
- [x] WhatsApp Voice Fabric is reusable platform code with AssemblyAI route + local Whisper fallback evidence.

## Safety
- [x] Synthetic demo data only in public artifacts.
- [x] No customer PII in repository evidence.
- [x] No committed AssemblyAI master key or other production secrets.
- [x] Demo action target is synthetic; no production work-order writes.
- [x] Public-facing workflow cannot directly expose production building controls.
- [x] Approval/policy boundaries remain in the execution path.
- [x] Public Cloud Run advertises `production_writes=false`.
- [x] Public Cloud Run is truth-labeled synthetic; it does not claim to run AMD .5.

## Repository
- [x] Public repository created.
- [x] README present.
- [x] Apache-2.0 license present.
- [x] Canonical project doc present.
- [x] Roadmap present.
- [x] Architecture doc present.
- [x] Demo script present.
- [x] Live runbook present.
- [x] Automated local test suite passes: **60/60** on final technical verification.
- [x] `python3 -m compileall -q src tests` passes.
- [x] `git diff --check` passes.
- [x] Canonical runtime workspace was rehydrated and verified at exact GitHub SHA `50fea125b3b19ede3f228a3263d5af3eef3aa132` before final release packaging.
- [x] GitHub CI workflow added for Python 3.11/3.12.
- [x] Release-packaging PR #9 CI completed successfully.
- [x] Final release merge recorded: `05887f268c90e3c5d649d5d045a9835cdaf6d372`.
- [x] Current canonical `main` advanced safely through telephony integration and is `461711617d4eb37fa848eefba9039bda1fde641f` as of 2026-09-13.

## Public deployment
- [x] Canonical public URL exists: `https://voiceops.creatorcore.ai/`.
- [x] Stale image `6bdcedc` was replaced with image built from exact canonical SHA `50fea125...`.
- [x] Cloud Run revision `voiceops-00002-r68` serves 100% traffic.
- [x] Public `/` returns HTTP 200.
- [x] Public `/api/state` returns HTTP 200.
- [ ] `/healthz` unexpectedly returns 404 despite the route existing in source. Do not claim it healthy until isolated; `/api/state` is the verified operational check for this release.

## Presentation
- [ ] Cover image.
- [ ] Architecture image suitable for submission/media.
- [ ] Judge UI screenshots from a clearly labeled public/synthetic run.
- [ ] Pitch deck uploaded.
- [ ] Demo video recorded/uploaded.
- [x] Spoken 75-second pitch/demo script finalized in `docs/SUBMISSION_PACKAGE.md`.
- [x] Concise judge testing instructions exist.

## Submission
- [x] Final title prepared.
- [x] Short description prepared.
- [x] Long description prepared.
- [x] Technologies list prepared.
- [x] Public repo URL exists.
- [x] Public demo URL exists.
- [ ] Video URL.
- [ ] Pitch deck/media links.
- [ ] Team information verified on organizer platform.
- [x] Existing-vs-new work disclosure is documented.
- [ ] Final submission confirmed on lablab.ai.

## Final verification
- [x] Current public service responds through Cloudflare and Cloud Run.
- [x] Canonical tests re-run on the reconciled source: 60/60 PASS.
- [x] AssemblyAI global provider preflight PASS with Owner Vault auth.
- [x] Public claims/truth boundaries documented in `evidence/FINAL_RELEASE_20260912.md`.
- [x] CI checks green on the final release-packaging PR.
- [ ] Secret scan over the exact final release tree.
- [ ] Fresh judge screenshots + browser-microphone recording for media.
- [ ] Verify organizer's exact closing hour immediately before submission.
- [ ] Submit before the internal freeze: **2026-09-29 22:00 America/Guayaquil**.

## Current P0

The technical product core is **submission-ready**. Release packaging and CI are closed. Remaining P0 work is final release hygiene, media, and organizer submission:

1. Run the exact-final-tree secret scan and preserve sanitized evidence.
2. Re-run CI/tests against the current canonical `main` after telephony integration.
3. Capture judge screenshots and a fresh browser-microphone demo recording.
4. Upload video/deck/media and insert their URLs into the submission package.
5. Verify team/project metadata and the organizer's exact closing hour.
6. Submit on lablab.ai before the internal September 29 freeze.

Do not fork, rebuild, or revive historical VoiceOps branches to accomplish these steps.
