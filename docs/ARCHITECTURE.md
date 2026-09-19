# Architecture — InnerOS Executable World 2026

**Canonical repo:** `Rafa-Innerchispa/inneros-executable-world-2026`  
**Ops task:** `ops_734e12ead662`

## CORE LOCAL (always on)

| Component | Role |
|-----------|------|
| VoiceOps web UI | Judge/demo panel at `executable.creatorcore.ai` |
| Qwen / AMD reasoner | Local OpenAI-compatible endpoint on `.5` |
| Governed tools | inspect → propose → explicit approval → execute |
| Execution permits | Single-use SHA-256 bound permits |
| Local evidence | `evidence/voiceops_events.jsonl` (always) |
| Home Assistant | Live telemetry + allowlisted actions |
| Grandstream PBX | SIP agent 1003 · user ext 1004 · RTP voice bridge |
| Audit / HTR | Human time returned metrics |

**Rule:** Core must run when all optional sponsors are `NOT_CONNECTED`.

## OPTIONAL PROVIDERS (attach/detach)

| Adapter | Purpose | Default |
|---------|---------|---------|
| AssemblyAI | Cloud STT/TTS voice channel | env-gated |
| Boson Higgs | Cloud S2S voice channel | env-gated |
| AgentX | **Self-hosted** tracing/evals | OFF |
| VeloDB | Evidence event store mirror | OFF |
| EdgeOne | Witness/CDN metadata only | OFF |

**Not in scope:** InsForge, InstaCloud, Memories.ai, AWS migration.

## Golden path

```text
Voice (browser mic OR PBX RTP)
  → InnerOS VoiceOps session
  → Qwen local reasoning + tool calls
  → live HA / AMI data (truth badges)
  → AgentX self-hosted trace (optional)
  → ExplicitApprovalGate
  → VoiceExecutionPermit (single-use)
  → Real PBX call OR governed HA action
  → Local evidence JSONL
  → VeloDB append (optional)
  → EdgeOne witness ping (optional)
```

## Telephony (frozen — do not redesign)

Confirmed working owner path:

- Server originates via SIP agent **1003**
- User answers on Zoiper **1004**
- Bidirectional audio + chat transcripts
- Multi-provider voice on server (AssemblyAI / Boson / server-local)
- Async `agent-call` + cancel + session polling

Changes to telephony require explicit owner approval.

## Data truth contract

Telemetry subsystems expose `truth`: `LIVE` | `UNVERIFIED` | `NOT_CONNECTED`.  
No synthetic values labeled LIVE. AMI/HA failures degrade gracefully.

## IDs per turn

- `session_id`
- `correlation_id` / `proposal_id`
- `permit_id`
- `action_id`
- evidence SHA-256

## Deployment

- **Production demo:** `.4` → `inneros-executable-world.service` → `:8769`
- **Public URL:** Cloudflare → `executable.creatorcore.ai`
- **Secrets:** `~/.config/inneros/executable.env` (never committed)

See also: `docs/SPONSOR_INTEGRATIONS.md`, `docs/DEMO_RUNBOOK.md`
