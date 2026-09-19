# Demo Runbook — 60–90 seconds

**URL:** https://executable.creatorcore.ai  
**Host:** GYE-Node-01 (`.4`) · service `inneros-executable-world.service` · port `8769`

## Pre-flight (30s)

1. `curl -s https://executable.creatorcore.ai/healthz` → `"ok": true`, `"production_writes": false`
2. Panel shows **NO PROD WRITES** in status strip
3. `/api/integrations/status` → `core_truth: OPERATIONAL`; optional adapters may be `NOT_CONNECTED` (OK)

## Demo flow A — Web voice + live telemetry (45s)

1. Open panel · **Ctrl+Shift+R** if stale JS
2. Voice channel: **Boson Higgs** or **AssemblyAI** (not telephony)
3. **Start Live Voice** → ask: *“What is the solar output right now?”*
4. Agent uses live HA telemetry · badge shows LIVE/UNVERIFIED honestly
5. Show **Route:** chip and governed tool trace in UI

## Demo flow B — PBX call (45s) — PRESERVE AS-IS

1. Voice channel: **IP Phone (PBX call)**
2. Extension **1004** (Zoiper on phone, not browser mic)
3. **Call extension** → bidirectional audio + chat transcripts
4. Do **not** expect browser TTS during active PBX call
5. **Cancel call** releases button if needed

## Demo flow C — Governed action + evidence (30s)

1. Manual or voice: propose HA-safe action (e.g. inspect subsystem)
2. Explicit approval phrase: *“Sí, autorizo”*
3. Show permit ID + evidence hash in UI
4. Optional: check `evidence/voiceops_events.jsonl` on server for local trail

## Sponsor status lines (reporting)

| Integration | Expected without extra setup |
|-------------|------------------------------|
| AgentX | NOT_CONNECTED (enable self-hosted on `.5`) |
| VeloDB | NOT_CONNECTED |
| EdgeOne | NOT_CONNECTED or CONFIGURED (if `EDGEONE_PAGES_PROJECT` set) |
| Core local | OPERATIONAL |

## Failure modes (fail-closed)

- AgentX down → voice + PBX + approvals still work; traces skipped
- VeloDB down → local JSONL evidence remains
- EdgeOne down → no impact on demo path
- AMI slow → telephony badge UNVERIFIED; **do not** break working call bridge

## Post-demo SHA

Record exact git SHA from server deploy for judges:

```bash
cd ~/inneros/inneros_core/workspaces/inneros-executable-world-2026
git rev-parse HEAD
pytest -q
```
