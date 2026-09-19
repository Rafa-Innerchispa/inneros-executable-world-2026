# Cross-repository boundary review — 2026-09-08

Repositories reviewed:

- `Rafa-Innerchispa/inneros-physical-guardian`
- `Rafa-Innerchispa/inneros-physical-guardian-ai-infra-2026`
- `Rafa-Innerchispa/inneros-voiceops-assemblyai`

## Result

The two Physical Guardian repositories already have the correct product/hackathon separation. The material collision risk was in the VoiceOps synthetic demo, where raw-ish camera state (`status=offline`) was being interpreted inside VoiceOps to produce a work-order proposal.

That interpretation has been removed from VoiceOps.

VoiceOps now consumes a synthetic projection of the canonical Physical Guardian `NormalizedEvent` output plus an already-formed bounded action candidate. It does not infer physical anomalies from camera state. If no Guardian action candidate is present, VoiceOps defaults to `no_action` rather than inventing a physical-domain decision.

## Canonical ownership after review

- Physical Guardian product owns ingestion, perception, anomaly/event interpretation, normalized physical events, physical action contracts and reusable edge technology.
- Physical Guardian AI Infra hackathon repo owns sponsor/demo/benchmark/submission glue only.
- VoiceOps owns AssemblyAI, voice session/turn handling, voice approval UX, orchestration, evidence correlation and TTS/judge UX.
- InnerOps Service Operations remains owner of real work-order lifecycle.
- Audit Fabric / Forensic Replay remain owners of canonical audit/replay primitives.

## Verification

- Added `docs/INTEGRATION_BOUNDARIES.md`.
- Added tests asserting VoiceOps consumes normalized Guardian output and does not infer an action when the Guardian candidate is missing.
- Updated E2E evidence test to identify the synthetic Guardian adapter explicitly.
- `python3 -m pytest tests -q`: 16 PASS.
- `python3 -m compileall -q src tests`: PASS.

No production writes, customer data, camera credentials or private topology were introduced.
