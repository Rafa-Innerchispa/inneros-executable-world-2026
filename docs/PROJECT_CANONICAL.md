# Project Canonical — InnerOS VoiceOps

Last canonical reset: 2026-09-11

## One-sentence product

InnerOS VoiceOps turns spoken operational intent into governed, auditable real-world execution using AssemblyAI realtime speech plus InnerOS local-first orchestration.

## Hackathon objective

Build and submit a working voice-agent experience for the AssemblyAI Voice Agent Hackathon without creating a disposable parallel architecture. Every useful component should remain usable by InnerOS after the event.

## Canonical name

- Product: **InnerOS VoiceOps**
- Submission descriptor: **The Governed Voice Control Plane for the Physical World**
- Repository: `Rafa-Innerchispa/inneros-voiceops-assemblyai`
- Canonical branch: `main`
- Canonical merge SHA after branch consolidation: `7c9228aab8568345683a070300c8d011967b5bef`

## Canonical truth rule

`main` is the only operational truth. Feature branches are temporary implementation lanes only. After a branch is tested and merged, future chats and agents must resume from `main`, not from an older worktree or branch name.

Do not create a second repository for the same hackathon unless this document is explicitly amended.

## Consolidation checkpoint — 2026-09-11

The long-running branch `local-agent/assemblyai-voiceops-e2e` was validated at head `916d17eeb410484dd7b480ff38044d2704a487c0` and merged to `main` via PR #1. The resulting canonical merge SHA is `7c9228aab8568345683a070300c8d011967b5bef`.

Validation before merge:

- 59/59 pytest PASS
- `python3 -m compileall -q src` PASS
- prior live AssemblyAI + AMD .5 validation PASS
- three consecutive full AMD .5 live E2E runs previously recorded PASS
- no production writes
- no committed AssemblyAI secret

Merged functional surface includes:

- AssemblyAI Voice Agent API browser lane
- AssemblyAI Streaming v3 lane
- dynamic speech context / keyterms support
- neural turn handling and end-of-turn gating
- native reply audio
- barge-in/interruption handling
- governed tool calling
- local-first AMD .5 reasoning adapter
- explicit approval gate
- event-bound, short-lived, single-use Voice Execution Permits
- authenticated Guardian `NormalizedEvent` bridge
- synthetic Service Operations action flow
- Audit / Replay / HTR evidence
- judge-facing web UI
- CreatorCore deployment surface

## Current product thesis

The important interface shift is not “AI that can talk.” It is reducing the distance between human intention and safe execution. VoiceOps should let a person state an operational objective naturally, while InnerOS handles context, routing, approvals, tools, evidence, and follow-up.

## Canonical technical choices

1. AssemblyAI is the realtime speech layer.
2. InnerOS remains the orchestration/control plane.
3. Local AMD inference is preferred when capability and policy allow it.
4. MCP is the capability/tool execution boundary.
5. Existing domain systems are integrated through adapters; their business logic is not copied here.
6. Audit Fabric / Forensic Replay provide evidence contracts.
7. HTR measures returned human time with MEASURED and ESTIMATED clearly separated.
8. TTS is pluggable; prefer local where practical, but do not block the hackathon on a perfect local TTS stack.
9. Public demo data remains synthetic unless a specific sanitized real event is explicitly used.
10. Consequential actions require explicit policy/approval gates.

## Existing capabilities to integrate, not duplicate

- InnerOS control plane
- Resource Fabric / routing
- MCP tools and authorization
- AMD .5 local inference
- InnerOps Service Operations
- Physical Guardian `NormalizedEvent` contract
- Workforce integration where useful
- Audit Fabric
- Forensic Replay
- Human Time Returned

## Boundary with Physical Guardian / AI Infra Summit

Physical Guardian is a separate product/project. In this hackathon repo it may be consumed only through its sanitized `NormalizedEvent`/incident contract. Do not develop camera ingestion, pet/person detection, high-resolution capture, Door Guard, anomaly detection, or facial recognition in this repository. Those belong to the Physical Guardian / AI Infra Summit workstream.

## Demo invariant

The primary demo must complete one coherent workflow. Avoid a menu of half-working features.

Canonical flow:

1. Guardian or synthetic operational event is available.
2. User interacts by browser voice or WhatsApp voice note.
3. AssemblyAI transcribes / manages the live conversation.
4. InnerOS inspects the exact event/state.
5. AMD .5/local reasoning explains and proposes a bounded action.
6. User gives explicit verbal approval.
7. A short-lived execution permit is issued and consumed once.
8. Synthetic/demo-safe action executes.
9. Audit / Replay / HTR evidence is recorded.
10. VoiceOps reports completion.

## Winning narrative

**Intent → Governed Execution → Evidence → Human Time Returned**

## Current release blockers / next work

1. Publish a judge-safe HTTPS endpoint, target `voiceops.creatorcore.ai` or another approved equivalent.
2. Capture final same-run public-browser microphone proof on the canonical `main` build.
3. Finish WhatsApp Voice Fabric integration with AssemblyAI provider selection and local Whisper fallback without creating a second app/channel.
4. Capture final screenshots, architecture media, demo video, write-up and lablab.ai submission.
5. Re-run full tests after any remaining release changes before merge to `main`.

## Truth policy

Never overclaim:

- pre-existing InnerOS work is reused/integrated, not invented during the hackathon;
- only captured timing is MEASURED;
- estimates remain ESTIMATED;
- experimental integrations are labeled experimental;
- public demo does not imply production deployment;
- deterministic replay means replaying captured evidence deterministically where possible, not promising identical stochastic LLM prose.

## Development policy

Local-first execution. Use local dev/runtime and local models first. External agents/models are fallback for unsupported capability or verified blockers. Keep changes isolated and auditable. No unnecessary cloud spend.

### Branch discipline

- Start every new task from current `main`.
- Use one short-lived branch per bounded change.
- Run relevant tests before merge.
- Merge successful work immediately to `main`.
- After merge, treat the feature branch as historical only.
- Do not resume future work from merged feature branches.
- If two chats touch the same repo, both must read this file and coordination state before coding.

## Scope freeze rule

After the core E2E workflow passes, new features enter only if they materially improve judging criteria and do not threaten the demo. Stability beats feature accumulation.

## Resume protocol

On any future session, read in this order:

1. `docs/PROJECT_CANONICAL.md`
2. current `main` HEAD
3. `README.md`
4. `docs/HACKATHON_CHECKLIST.md`
5. `docs/ASSEMBLYAI_TECH_MATRIX.md`
6. `docs/LIVE_RUNBOOK.md`
7. latest evidence and coordination ops/messages

Then continue from the first incomplete P0 item. Do not redesign the project from memory and do not treat an old branch as canonical merely because its name sounds newer.
