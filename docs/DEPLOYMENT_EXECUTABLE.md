# Deploy — executable.creatorcore.ai

## GitHub (public)

Repository: https://github.com/Rafa-Innerchispa/inneros-executable-world-2026

CI runs on every push to `main` (pytest 3.11 + 3.12).

## Runtime (.4)

```bash
git clone https://github.com/Rafa-Innerchispa/inneros-executable-world-2026.git
cd inneros-executable-world-2026
cp .env.example ~/.config/inneros/executable.env   # fill secrets locally
ASSEMBLYAI_API_KEY=... python3 scripts/setup_executable_env.py
bash scripts/deploy_executable_14.sh
```

Service: `inneros-executable-world.service` → port **8769**

## Cloudflare tunnel ingress

In `~/.cloudflared/opportunityops.yml`:

```yaml
  - hostname: executable.creatorcore.ai
    service: http://192.168.1.4:8769
```

Restart: `systemctl --user restart opportunityops-cloudflared.service`

## DNS (creatorcore.ai zone) — InnerOS AG-44 integration

Cloudflare is integrated on **`.4`** via InnerOS platform (`inneros_core_runtime/agents/ag44_cloud_deployer.py`).
Credentials live in **owner_vault** (`cloudflare_pcdoctor_ai` category), not in repo env files.

On `.4`:

```bash
/home/rlopez/inneros/inneros_core/platform/venv/bin/python scripts/fix_executable_dns.py
```

This creates a proxied CNAME → `6fb8ceab-a17e-41b3-872d-e26ef2d1383f.cfargotunnel.com` (same pattern as `fieldops`, `voiceops`).

Tunnel ingress must include the hostname in `~/.cloudflared/opportunityops.yml` (see above).

**Note:** `.5` does not host Cloudflare tunnel/DNS — tunnel runs on `.4` (`opportunityops-cloudflared.service`).

## Verify

```bash
curl -sf http://192.168.1.4:8769/healthz
curl -sf https://executable.creatorcore.ai/healthz
```

Expect `live_voice_enabled: true` when `ASSEMBLYAI_API_KEY` is set in `executable.env`.
