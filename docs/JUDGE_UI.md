# Judge UI MVP

InnerOS VoiceOps now includes a single-screen judge-facing web demo.

## What the screen proves

The UI presents one governed execution trace:

1. voice/transcript input;
2. normalized Physical Guardian incident;
3. reasoning route;
4. bounded action proposal;
5. explicit approval gate;
6. synthetic Service Operations action;
7. evidence timeline, HTR and captured-state replay.

The UI is intentionally not a dashboard. It is a live execution trace that lets a judge understand the causal chain without navigating between pages.

## Run modes

### Offline-safe synthetic mode

```bash
voiceops-web --host 127.0.0.1 --port 8765 --reasoner synthetic
```

This mode is deterministic and requires no model endpoint. The reasoning card is labeled `SYNTHETIC`.

### Local AMD .5 mode

```bash
voiceops-web --host 127.0.0.1 --port 8765 --reasoner amd5
```

Default local runtime endpoint:

`http://127.0.0.1:18000/v1/chat/completions`

Override only through environment configuration:

- `VOICEOPS_AMD5_URL`
- `VOICEOPS_AMD5_MODEL`

The UI labels the route `AMD .5 LIVE` only after a real model response returns through `LocalAMDReasoner`.

## Safety boundary

Physical Guardian owns the normalized incident and action candidate. `LocalAMDReasoner` can produce a concise human-facing summary, but VoiceOps preserves the Guardian-provided:

- action type;
- approval requirement;
- action payload.

A model response cannot silently upgrade or alter those fields.

The bundled web demo uses `SyntheticServiceWorkflow`, therefore `production_writes=false` at all times.

## Demo controls

- **Run demo intent**: injects the canonical operational request into the real `VoiceGateway` state machine.
- **Say Yes, authorize**: supplies explicit approval and allows the synthetic action.
- **Try ambiguous approval**: supplies a deliberately ambiguous phrase and demonstrates fail-closed behavior.
- **View evidence**: opens the complete in-memory evidence bundle.
- **Replay decision**: reconstructs the result only from captured evidence.
- **Reset**: creates a fresh session/correlation ID and clears demo state.

## HTTP endpoints

- `GET /api/state`
- `GET /api/evidence`
- `GET /api/replay`
- `POST /api/intent`
- `POST /api/approve`
- `POST /api/reset`

All demo state is in memory. Request transcript length is bounded and default HTTP access logging is suppressed to reduce accidental transcript leakage.

## Remaining live work

The current web product is demonstrable and test-covered. The remaining provider-level integrations are:

1. inject a valid AssemblyAI credential server-side;
2. feed live AssemblyAI final turns into the same `VoiceGateway` session used by this UI;
3. expose local TTS output through the existing InnerOS XTTS/Piper capability;
4. deploy the web server behind an approved public demo route.
