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

## DNS (creatorcore.ai zone)

Mirror other InnerOS hostnames (`fieldops`, `voiceops`): proxied **A** records to Cloudflare anycast, or CNAME to the `opportunityops` tunnel.

Example (Cloudflare dashboard → DNS → creatorcore.ai):

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | executable | 172.67.212.1 | Proxied |
| A | executable | 104.21.53.103 | Proxied |

Or CNAME: `executable` → `6fb8ceab-a17e-41b3-872d-e26ef2d1383f.cfargotunnel.com` (proxied).

Tunnel ingress must include the hostname (see above).

## Verify

```bash
curl -sf http://192.168.1.4:8769/healthz
curl -sf https://executable.creatorcore.ai/healthz
```

Expect `live_voice_enabled: true` when `ASSEMBLYAI_API_KEY` is set in `executable.env`.
