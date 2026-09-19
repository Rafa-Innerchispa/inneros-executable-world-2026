# Execution Witness (EdgeOne)

Minimal external witness for InnerOS Executable World. Accepts **sanitized** execution receipts only.

## Purpose

```
InnerOS local → evidence receipt → EdgeOne witness → external confirmation
```

This does **not** host VoiceOps or replace `executable.creatorcore.ai`.

## Local smoke test

```bash
python agents/execution-witness/handler.py
curl -s http://127.0.0.1:8780/
curl -s -X POST http://127.0.0.1:8780/ -H 'Content-Type: application/json' \
  -d '{"event_type":"voiceops.test","receipt":{"session_id":"demo","evidence_sha256":"abc"}}'
```

## Runtime env (InnerOS on .4)

```bash
EXECUTABLE_ENABLE_EDGEONE=true
EDGEONE_PAGES_PROJECT=inneros-executable-world-2026
EDGEONE_WITNESS_URL=https://<your-edgeone-witness-host>/
```

Without `EDGEONE_WITNESS_URL`, status remains **CONFIGURED** (repo linked in EdgeOne console).
