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

Truth labels: `REAL`, `CONFIGURED`, `UNVERIFIED`, `NOT_CONNECTED` — never from env alone.

---

## AgentX — self-hosted local tracing

| | |
|---|---|
| **Purpose** | Traces/evals for governed voice → action flows |
| **Tier** | OPTIONAL |
| **Mode** | Self-hosted only — **no paid hosted API** |
| **Run** | `pip install agentx-python && agentx-trace-eval --dev` |
| **Env** | `EXECUTABLE_ENABLE_AGENTX=true`, `AGENTX_SELF_HOSTED_URL=http://127.0.0.1:4700`, optional `AGENTX_API_KEY` |
| **Probe** | `GET /health` on self-host root |
| **Emit** | OTLP/HTTP JSON → `{AGENTX_SELF_HOSTED_URL}/api/v1/otel/v1/traces` |
| **Status REAL** | Health OK **and** at least one OTLP span accepted |

---

## VeloDB — MySQL-compatible execution memory

| | |
|---|---|
| **Purpose** | Remote mirror of approvals, permits, results, evidence |
| **Tier** | OPTIONAL |
| **Protocol** | MySQL-compatible (Doris/VeloDB) via PyMySQL — **not REST** |
| **Env** | `EXECUTABLE_ENABLE_VELODB=true`, `VELODB_HOST`, `VELODB_PORT=9030`, `VELODB_USER`, `VELODB_PASSWORD`, `VELODB_DATABASE=inneros_executable_world` |
| **Table** | `execution_events` (auto-created) |
| **Status REAL** | CONNECT + CREATE TABLE + INSERT + SELECT readback verified |
| **Local fallback** | `evidence/voiceops_events.jsonl` always active |

---

## Tencent EdgeOne — auxiliary witness

| | |
|---|---|
| **Purpose** | Optional deployment witness — **not** InnerOS migration |
| **Tier** | OPTIONAL |
| **Component** | `agents/execution-witness/` + `edgeone.json` |
| **Env** | `EXECUTABLE_ENABLE_EDGEONE=true`, `EDGEONE_PAGES_PROJECT=…`, optional `EDGEONE_WITNESS_URL` |
| **Status CONFIGURED** | Repo/project linked in EdgeOne console, no witness URL |
| **Status REAL** | Witness URL reachable and POST receipt accepted |

Account + GitHub + repo selection already done by owner.

---

## Golden path wiring

```text
Voice (web or PBX)
  → InnerOS VoiceOps
  → Qwen local (AMD .5)
  → live HA / AMI tools
  → AgentX trace (optional OTLP)
  → explicit approval gate
  → single-use permit
  → PBX real call OR governed HA action
  → local evidence JSONL
  → VeloDB INSERT (optional)
  → EdgeOne witness POST (optional)
```

Telephony path is **frozen** — do not refactor SIP/RTP bridge for sponsor demos.
