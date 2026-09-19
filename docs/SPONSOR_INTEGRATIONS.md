# Sponsor Integrations — Executable World 2026

**Task:** `ops_734e12ead662`  
**Repo:** `Rafa-Innerchispa/inneros-executable-world-2026`

## Out of scope (do not implement here)

- InsForge
- InstaCloud
- Memories.ai
- AWS migration
- Redesign of working PBX telephony (ext 1003/1004 bidirectional flow)

## Design rule

If AgentX, EdgeOne, or VeloDB fail → **core local keeps running**.

Local evidence is **always** written to `evidence/voiceops_events.jsonl`.

---

## AgentX — self-hosted local tracing

| | |
|---|---|
| **Purpose** | Traces/evals for governed voice → action flows |
| **Tier** | OPTIONAL |
| **Mode** | Self-hosted only — **no paid hosted API** |
| **Env** | `EXECUTABLE_ENABLE_AGENTX=true`, `AGENTX_SELF_HOSTED_URL=http://127.0.0.1:8090` |
| **Probe** | `GET /health` or `/healthz` or `/v1/health` |
| **Emit** | `POST /v1/traces` (best-effort JSON span) |
| **Status** | `REAL` when probe OK; else `NOT_CONNECTED` |

---

## VeloDB — execution / evidence event store

| | |
|---|---|
| **Purpose** | Remote mirror of approvals, permits, results, evidence |
| **Tier** | OPTIONAL |
| **Env** | `EXECUTABLE_ENABLE_VELODB=true`, `VELODB_URL=…`, `VELODB_API_KEY=…` |
| **Events** | proposals, approvals, governed actions, inspect mirrors |
| **Status** | `REAL` when `/health` OK; local JSONL always active |

---

## Tencent EdgeOne — auxiliary witness

| | |
|---|---|
| **Purpose** | Optional deployment witness / CDN metadata — **not** InnerOS migration |
| **Tier** | OPTIONAL |
| **Env** | `EXECUTABLE_ENABLE_EDGEONE=true`, `EDGEONE_PAGES_PROJECT=…`, optional `EDGEONE_WITNESS_URL` |
| **Status** | `REAL` when witness URL reachable; `CONFIGURED` when project metadata only |

Account + GitHub + repo selection in EdgeOne console is sufficient for `CONFIGURED` demo evidence.

---

## Golden path wiring

```text
Voice (web or PBX)
  → InnerOS VoiceOps
  → Qwen local (AMD .5)
  → live HA / AMI tools
  → AgentX trace (optional)
  → explicit approval gate
  → single-use permit
  → PBX real call OR governed HA action
  → local evidence JSONL
  → VeloDB mirror (optional)
  → EdgeOne witness (optional)
```

Telephony path is **frozen** — do not refactor SIP/RTP bridge for sponsor demos.
