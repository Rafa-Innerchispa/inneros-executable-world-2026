# Integration Boundaries — VoiceOps, Physical Guardian, and Hackathon Overlays

Last reviewed: 2026-09-08

## Why this boundary exists

InnerOS VoiceOps and InnerOS Physical Guardian are being developed in parallel and both can appear in the same physical-world demo. They must not become competing implementations of the same domain logic.

## Canonical ownership

### `Rafa-Innerchispa/inneros-physical-guardian`

Canonical reusable Physical Guardian product.

Owns:
- camera/source ingestion and RTSP/ONVIF/vendor abstraction;
- normalized physical events and evidence references;
- detection, tracking and perception backends;
- temporal/multi-camera anomaly interpretation;
- physical-world risk/event assessment;
- Physical Guardian action contracts and policy integration;
- physical actuator/device adapter boundaries;
- reusable Windows/edge deployment technology;
- reusable forensic evidence emitted by the physical layer.

VoiceOps must consume these capabilities through an adapter/MCP boundary. It must not reimplement them.

### `Rafa-Innerchispa/inneros-physical-guardian-ai-infra-2026`

Hackathon-specific overlay for the AI Infra Summit 2026.

Owns only:
- sponsor-specific integration and benchmarks;
- hackathon demo glue and fixtures;
- judging evidence and reproducibility artifacts;
- pitch/submission material;
- explicit disclosure of reused vs hackathon-period work.

Permanent Guardian technology belongs upstream in `inneros-physical-guardian`.

### `Rafa-Innerchispa/inneros-voiceops-assemblyai`

AssemblyAI Voice Agent Hackathon overlay and reusable VoiceOps integration layer.

Owns:
- AssemblyAI streaming integration;
- voice sessions, turns and transcript handling;
- spoken intent/context orchestration;
- voice approval UX and fail-closed authorization semantics;
- Resource Fabric / MCP routing from voice intent to canonical capabilities;
- voice-specific evidence correlation and HTR presentation;
- TTS response and judge-facing voice UX.

VoiceOps does **not** own:
- camera ingestion;
- object/person detection or tracking;
- anomaly detection;
- physical incident classification;
- physical actuator drivers;
- canonical work-order lifecycle;
- canonical Audit Fabric / Forensic Replay primitives.

## Integration direction

```text
Physical sources
      |
      v
InnerOS Physical Guardian
  NormalizedEvent / evidence / bounded action candidate
      |
      v
InnerOS capability / MCP boundary
      |
      +----------------------+
      |                      |
      v                      v
VoiceOps                 Other InnerOS clients
AssemblyAI STT
voice session
approval UX
      |
      v
InnerOps Service Operations / approved action capability
      |
      v
Audit Fabric / Forensic Replay / HTR
```

Dependency direction is one-way: VoiceOps may depend on Guardian contracts/capabilities; Physical Guardian must not depend on AssemblyAI or VoiceOps.

## Synthetic demo rule

VoiceOps may include synthetic fixtures that mimic the **output** of Physical Guardian for isolated tests and public demos. Such fixtures must start from a normalized incident/action candidate. They must not inspect raw camera state and reproduce Guardian anomaly logic.

The current synthetic fixture therefore emits a Guardian-style `NormalizedEvent` projection with an already-formed bounded action candidate. VoiceOps only performs orchestration, approval and synthetic Service Operations execution.

## Work-order boundary

A real work order belongs to InnerOps Service Operations. VoiceOps can request it through a capability adapter after approval, but it must not become the system of record for work-order lifecycle, assignment, billing or completion.

The local demo keeps an in-memory synthetic work order solely to prove the governed voice path.

## Audit boundary

Each layer may emit evidence, but canonical evidence contracts remain owned by Audit Fabric / Forensic Replay. VoiceOps should attach its session/turn/correlation IDs to upstream/downstream evidence instead of inventing a competing audit schema.

## Merge/reuse rule

If a feature is useful without AssemblyAI or without the AI Infra hackathon, it probably belongs in a canonical InnerOS/product repository rather than either hackathon overlay.

No code should be copied between the two hackathon repos merely to make demos self-contained. Prefer adapters, package references, MCP capabilities or captured synthetic fixtures.
