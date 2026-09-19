# Architecture — InnerOS VoiceOps

## Principle

VoiceOps is an adapter/orchestration product over existing InnerOS capabilities. It must not become a fork of InnerOS.

## Data flow

```text
Browser / microphone
  -> Voice session
  -> AssemblyAI realtime streaming STT
  -> normalized utterance + timing metadata
  -> InnerOS Voice Gateway
  -> policy/context/tenant resolution
  -> Resource Fabric route decision
  -> local AMD model preferred
  -> MCP capability selection
  -> approval gate when required
  -> domain adapter / action
  -> result
  -> Audit Fabric hooks
  -> HTR / Evidence Bundle / Replay reference
  -> response text
  -> TTS
  -> user
```

## Boundaries

### AssemblyAI adapter
Responsible for audio streaming, connection lifecycle, transcript events, timing, errors, and speech-context features. It must not own business policy or tool authorization.

### Voice Gateway
Responsible for conversation/session state, correlation IDs, intent handoff, approval dialogue, interruption behavior, and translating speech events into InnerOS requests.

### InnerOS
Canonical control plane. Owns routing, capability access, policy, authorization, agent/tool orchestration, and local-first decisions.

### Domain adapters
Thin integration layer to Service Operations, VigilOS, Workforce, QuoteOps, etc. Business logic stays in its canonical system.

### Audit/evidence
Record start/route/approval/action/result/quality references. Preserve source evidence and truth boundaries. Heavy raw evidence stays outside transactional Mongo when appropriate.

### TTS
Pluggable. Prefer local where practical. Do not couple core workflow correctness to one speech-synthesis vendor.

## IDs

Every voice workflow should carry:

- `session_id`
- `correlation_id`
- `turn_id`
- `tenant_id` or synthetic-demo tenant
- trace/span context where available
- evidence bundle reference when generated

## Approval model

A transcript is not automatically authorization. The Voice Gateway must distinguish:

- informational request;
- proposed action;
- explicit approval/denial;
- ambiguous utterance;
- interruption/cancellation.

High-impact actions must fail closed when approval is absent or ambiguous.

## Demo-safe architecture

The public judge path must point to synthetic/demo capabilities. It must not expose direct production building/security controls.

## Performance evidence

Capture at least:

- speech-end to final transcript latency;
- transcript to route decision;
- route to first model token/result when observable;
- tool execution latency;
- end-to-end voice workflow duration;
- baseline human minutes;
- assisted active human minutes;
- rework/interventions;
- local/cloud seconds and cost where available.

Do not manufacture numbers to make charts prettier. Charts have survived without our emotional support for centuries.
