# Judge UI MVP evidence — 2026-09-10

Repository: `Rafa-Innerchispa/inneros-voiceops-assemblyai`
Branch: `local-agent/assemblyai-voiceops-e2e`
Task: `ops_e6fefdbe0e3d`
Correlation: `assemblyai-voiceops-hackathon-20260908`

## Implemented

- standard-library HTTP demo server;
- one-screen judge UI;
- VoiceGateway-backed state machine;
- normalized Physical Guardian projection visible in the UI;
- reasoning route card with truth-sensitive labels;
- explicit approval and ambiguous-approval controls;
- synthetic work-order execution only after approval;
- evidence bundle and captured-evidence replay endpoints;
- HTR presentation;
- local AMD .5 bounded reasoner adapter;
- `voiceops-web` CLI entrypoint;
- static package assets included through setuptools package-data.

## Truth boundary

The offline UI defaults to the deterministic reasoner and is visibly labeled `SYNTHETIC`.

`AMD .5 LIVE` is only rendered when route evidence contains:

- provider: `local-amd-5`;
- truth: `LIVE_MODEL_RESPONSE`.

The AMD adapter preserves the Physical Guardian action candidate's action type, approval requirement and payload. The model is limited to producing a concise human-facing summary.

The bundled action target remains `SyntheticServiceWorkflow`; therefore there are no production writes.

## Verification

- Full pytest: **35 passed**.
- `python3 -m compileall -q src tests`: **PASS**.
- HTTP smoke test covers static page, state endpoint, proposal, fail-closed ambiguous approval, explicit approval, synthetic action and replay.
- Direct ad-hoc `python3 -c` live adapter probe was denied by the Local Execution Plane command allowlist. This is a tooling-policy restriction, not recorded as a product PASS.
- Separate prior runtime evidence confirms real AMD .5 / Qwen inference; this checkpoint does not falsely claim that the new web adapter itself was live-probed through the restricted command lane.

## Security

- no AssemblyAI API key committed;
- no customer PII;
- no camera credentials or private topology;
- no production work-order writes;
- bounded request size and transcript length;
- default HTTP request logging disabled to avoid accidental transcript leakage.
