# InnerOS Executable World 2026

[![CI](https://github.com/Rafa-Innerchispa/inneros-executable-world-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/Rafa-Innerchispa/inneros-executable-world-2026/actions/workflows/ci.yml)

**Public repo:** https://github.com/Rafa-Innerchispa/inneros-executable-world-2026  
**Live demo:** https://executable.creatorcore.ai

Provider-agnostic sovereign runtime for hackathon demos.

> InnerOS is not another cloud agent. The intelligence and execution core runs locally.
> Cloud AI services are replaceable capabilities that can be attached or removed without
> taking the operational system down.

## Three clean surfaces

| URL | Repo | Role |
|-----|------|------|
| `voiceops.creatorcore.ai` | `inneros-voiceops-assemblyai` | Permanent VoiceOps product (**do not modify from here**) |
| `voiceopsboson.pcdoctor.ai` | `inneros-voiceops-one-day-2026` | Boson hackathon experiment |
| `executable.creatorcore.ai` | **this repo** | Executable World — AgentX, VeloDB, optional adapters |

## Capability matrix

**CORE LOCAL ✓** — Qwen, execution engine, approval gate, permits, evidence, Grandstream, MCP/tools

**OPTIONAL ○** — AssemblyAI, Boson, AgentX, VeloDB, EdgeOne, Memories.ai, WorkBuddy

See `PROVENANCE.md` for baseline lineage from `inneros-voiceops-assemblyai`.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env       # configure secrets locally — never commit
executable-web --host 127.0.0.1 --port 8769
```

## Deploy (.4)

```bash
bash scripts/deploy_executable_14.sh
```

Configure `~/.config/inneros/executable.env` on the host (AssemblyAI key, HA token, etc.).
