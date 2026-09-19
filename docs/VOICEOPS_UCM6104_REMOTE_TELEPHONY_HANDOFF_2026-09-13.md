# VoiceOps / Grandstream UCM6104 Remote Telephony — Canonical Handoff

Date: 2026-09-13 (America/Guayaquil)
Owner project: `Rafa-Innerchispa/inneros-voiceops-assemblyai`
Canonical `main` observed when this handoff was finalized: `1b6664abf3752832623e231170de5d95b650ab6f`

## 1. Goal

Turn the existing Grandstream UCM6104 in Guayaquil into a private telephony endpoint for InnerOS/VoiceOps so the owner can:

- place calls through the Ecuador/Guayaquil landline while traveling in the United States;
- receive calls on a private SIP softphone extension;
- allow Ralphi/VoiceOps to originate bounded Ecuador calls only after live route verification and permit/audit controls;
- keep SIP/RTP private, avoid exposing the PBX directly to the public Internet, and preserve call quality.

The user confirmed the line plan has unlimited local Guayaquil and Ecuador cellular calls. International calling should remain disabled by default.

## 2. Live PBX truth — verified

Device:

- Model: Grandstream UCM6104 / UCM6104V1.6A
- LAN IP: `192.168.1.6`
- MAC: `00:0B:82:86:33:AB`
- Web admin: HTTPS `8089`
- Web stack: legacy lighttpd; web UI assets circa 2018
- Current firmware identified by SIP response: `1.0.18.12`
- Official target firmware for this EOL series: `1.0.18.18` only, after full backup. Do not use unofficial firmware.

SIP General Settings, confirmed directly by owner from the live UI:

- Bind UDP Port: `4321`
- Bind IPv4 address: `0.0.0.0`

Live network proof from InnerOS `.4`:

- a single unauthenticated SIP REGISTER to `192.168.1.6:4321/UDP` returned `SIP/2.0 401 Unauthorized` with Digest challenge;
- therefore the active SIP listener is confirmed on UDP 4321;
- old references to SIP port `25000` are historical/obsolete for the current LAN listener.

AMI:

- TCP port: `7777`
- banner: `Asterisk Call Manager/2.7.0`
- `Action: Challenge`, `AuthType: MD5` works;
- unauthenticated `Ping` is denied as expected;
- AMI remains the preferred long-term control/status plane.

Web CGI auth behavior already verified historically:

1. POST `action=challenge&user=<user>`
2. receive challenge
3. derive `MD5(challenge + password)`
4. POST `action=login&user=<user>&token=<derived>`
5. receive session cookie
6. authenticated read actions use the in-memory session only

Do not store or paste the PBX admin password in chat, Git, logs, docs, or source code.

## 3. Exact UCM firmware/API discoveries already integrated

The live SIP settings UI uses `getSIPGenSettings`, with `response.sip_general_settings` and these exact fields:

- `realm`
- `bindport`
- `bindaddr`
- `bindaddr6`
- `allowguest`
- `allowtransfer`
- `mwi_from`
- `enable_diversion`

Other SIP/config read actions discovered from the live firmware include:

- `getSIPMiscSettings`
- `getSIPSSTimerSettings`
- `getSIPTCPSettings`
- `getSIPNATSettings`
- `getTOSSettings`
- `getUsedPortInfo`
- `listSipNetAddrSettings`
- `getExtenPrefSettings`

PR #14 subsequently aligned the production CGI adapter to the exact live inventory/read action names used by this firmware:

- `listAccount`
- `listVoIPTrunk`
- `listTrunkGroup`
- `listAnalogTrunk`
- `listOutboundRoute`
- `listInboundRoute`
- `getRTPSettings`
- `getPayloadSettings`
- `getBackupSettings`
- `getUpgradeValue`

The adapter now also has a bounded pre-change telephony snapshot covering SIP, RTP, payloads, extensions, trunks, routes, backup settings and upgrade settings.

Firmware routes expose maintenance pages for `backup` and `upgrade`, plus feature pages for `ami`, `rtpSettings`, trunks, routes, etc.

## 4. VoiceOps adapters already merged

### Read-only AMI adapter

`src/voiceops/adapters/grandstream_ami.py`

- MD5 challenge login;
- no plaintext AMI secret sent;
- fail-closed read-only action allowlist;
- supports probe, ping, core status, SIP peer inventory/status;
- blocks `Originate`, `Command`, `Hangup`, `Redirect`, transfer/config writes.

### Read-only UCM CGI adapter

`src/voiceops/adapters/grandstream_ucm6104.py`

- private literal IP target enforcement;
- challenge/login in memory;
- no password stored on adapter instance;
- short-lived session cookie only;
- strict read-only action allowlist;
- normalized SIP General Settings;
- exact live extension/trunk/route/RTP/backup/upgrade read actions;
- bounded pre-change snapshot helper.

Related merged PRs before this handoff:

- PR #10: read-only AMI adapter
- PR #11: read-only UCM6104 CGI adapter
- PR #12: document live SIP 4321/0.0.0.0 truth
- PR #13: Ecuador outbound telephony policy and remote access runbook
- PR #14: exact live UCM6104 read actions plus bounded pre-change snapshot

Canonical `main` after PR #14 and before this handoff PR:

`1b6664abf3752832623e231170de5d95b650ab6f`

Full VoiceOps suite at that point: `88 PASS`.

## 5. Outbound calling policy already implemented

`src/voiceops/telephony_policy.py`

Policy classes:

- Guayaquil fixed lines
- Ecuador mobile
- other Ecuador geography
- international
- internal extensions
- invalid input

Rules:

- explicit owner-requested Guayaquil fixed and Ecuador mobile calls are policy-allowed;
- autonomous domestic calls require allowlist/permit policy;
- international is disabled by default;
- other Ecuador geography remains disabled until the live UCM outbound route/carrier entitlement is verified;
- canonical E.164 normalization is intentionally separate from the PBX dial string;
- VoiceOps must never guess whether the PBX route needs `0`, `9`, `00`, stripping `+593`, or another route prefix;
- `policy allowed` does not mean `execution ready` until the live outbound route has been read and translated.

`AMI Originate` is still intentionally disabled.

## 6. Home network / UniFi live truth

Gateway:

- `192.168.1.1`
- UniFi Cloud Gateway Ultra (`UDRULT` / UCG Ultra)
- firmware observed: `5.1.33.34087`
- remote access is enabled;
- PBX is wired, so local PBX audio does not depend on Wi-Fi.

Important WAN topology:

- UCG Ultra WAN IP: `192.168.100.4`
- upstream gateway: `192.168.100.1`
- public IP observed externally from `.4`: `190.131.139.30`

This means the UCG Ultra is behind an upstream NAT. The upstream management surface was not reachable on the common tested HTTP/HTTPS admin ports, so relying on a new upstream port-forward is undesirable.

## 7. Chosen remote-access architecture

### PRIMARY: UniFi Teleport

Chosen because the UCG Ultra is behind another NAT and Teleport is designed to provide remote access without publicly exposing SIP/RTP or requiring a manual SIP port-forward.

Target path:

`Phone in USA -> UniFi Teleport private tunnel -> UCG Ultra -> LAN -> UCM6104 192.168.1.6:4321/UDP -> Ecuador PSTN`

Why this is preferred now:

- no public SIP 4321 exposure;
- no public RTP exposure;
- avoids Cloudflare/Spectrum in the media path;
- avoids touching the upstream router solely to forward WireGuard;
- shorter/simpler private media path than relaying through application/cloud infrastructure.

### SECONDARY: native WireGuard on UCG Ultra

Use only if the upstream NAT can be deliberately configured to forward the WireGuard UDP port to the UCG. Do not open SIP/RTP ports to the public Internet.

### FALLBACK: Tailscale subnet routing via InnerOS `.4`

Tailscale is already running on `.4` and `.5`. It is a useful fallback, but not the first choice because indirect/DERP relay paths can add latency and jitter.

### NOT SELECTED: Cloudflare in the RTP/media path

Cloudflare is intentionally excluded from the audio path. Do not proxy SIP/RTP through Cloudflare just because it is available.

## 8. Client strategy

Grandstream Wave Lite is legacy/EOL. Do not make it the new primary client.

Preferred deployment:

- a maintained SIP softphone on the owner's phone;
- connect to the private Teleport/VPN first;
- then register the SIP account to `192.168.1.6:4321` as though local.

Create separate identities:

- one dedicated remote owner SIP extension;
- one dedicated Ralphi/VoiceOps SIP/service identity;
- do not permanently reuse web admin identity or extension 1000 for the agent.

Historical extension information exists for extension `1000`, but it is not yet authoritative current inventory. Re-read the live extension list before creating anything.

## 9. Firmware strategy

Current UCM firmware: `1.0.18.12`.

Recommended target: official Grandstream `1.0.18.18` only.

Mandatory order:

1. authenticated full UCM backup;
2. capture extension/trunk/route/RTP settings before change;
3. upgrade only to official `1.0.18.18`;
4. verify PBX boots and SIP 4321 responds;
5. verify trunks/routes/current inbound/outbound service;
6. review/change admin credentials afterward;
7. only then create new dedicated extensions.

Do not install unofficial firmware.

## 10. Exact current blockers

The technical design and safe local adapters are done. The remaining blocker is authenticated administrative access to execute the PBX/UniFi changes.

Temporary loopback-only browser proxies/sessions were prepared during the previous chat so the owner could authenticate without pasting passwords into ChatGPT. At handoff time they were still on login screens. Do not depend on old browser-session URLs or tokens in a new chat; create fresh temporary sessions if needed.

No PBX configuration, UniFi VPN configuration, firmware upgrade, new extension, or real call had been executed yet at the moment of this handoff.

## 11. Immediate execution sequence for the next chat

Do not re-research from zero. Continue exactly here:

1. Read this file and `docs/TELEPHONY_UCM6104.md` plus `docs/REMOTE_TELEPHONY_US_EC.md`.
2. Confirm canonical `main` and repo cleanliness; bootstrap/re-align the `.4` runtime to current `main` if needed.
3. Create fresh loopback-only human browser sessions for:
   - UCM admin (`192.168.1.6:8089` via local reverse proxy);
   - UniFi OS (`192.168.1.1` via local reverse proxy).
4. Have owner enter credentials into those browser sessions, never into chat.
5. On UCM, first create/download a full backup and preserve it outside Git.
6. Use the bounded pre-change snapshot/read helpers to record current authoritative:
   - extensions/SIP accounts;
   - trunks and trunk groups;
   - inbound routes;
   - outbound routes and dial patterns/prefixes;
   - RTP and payload settings;
   - SIP TCP/TLS state if relevant;
   - backup/upgrade settings;
   - AMI settings/available service identity options.
7. Configure UniFi Teleport with the minimum access needed for the remote phone to reach the PBX LAN address. Do not expose SIP/RTP publicly.
8. Verify tunnel reachability to `192.168.1.6` and UDP 4321 from a remote client when available.
9. Upgrade UCM to official `1.0.18.18` only after backup and pre-upgrade inventory.
10. Re-verify SIP listener/trunks/routes after upgrade.
11. Create a dedicated owner remote SIP extension and separate Ralphi service extension with strong generated secrets; keep secrets server-side/private.
12. Register maintained SIP softphone over Teleport; test extension-to-extension audio.
13. Derive the real PBX dial string for Guayaquil/mobile from live outbound routes. Do not guess prefixes.
14. Make one bounded real test call to an owner-approved Guayaquil/mobile destination and measure audio/latency/jitter/loss.
15. Only after the route is verified, implement a guarded AMI Originate path in VoiceOps using destination policy + permit/audit controls.
16. International remains disabled by default.

## 12. Safety constraints that must survive the handoff

- No raw admin/SIP/AMI secrets in chat, Git, logs, docs, screenshots, or coordination messages.
- No public SIP/RTP exposure.
- No unofficial PBX firmware.
- No blind port-forwarding.
- No `AMI Originate` until route translation is verified and VoiceOps permit/audit enforcement exists.
- No permanent reuse of admin identity or extension 1000 for Ralphi.
- Keep domestic call scope bounded to the verified Ecuador plan; international fail-closed.
- Preserve backups before firmware or route changes.
- Prefer reversible changes and before/after evidence.

## 13. Infrastructure note

Primary VoiceOps runtime on `.4` was aligned to the earlier PR #13 canonical `main`. Before executing PBX mutations in the next chat, bootstrap/re-align the primary runtime to the current canonical `main` and verify a clean worktree.

The VoiceOps runtime registry path on AMD `.5` previously reported `not_git_repository`; this is infrastructure debt, not a PBX/VoiceOps feature failure. Do not silently destroy/replace that path without deliberate Runtime Registry reconciliation.

## 14. Completion definition

This telephony lane is considered complete only when all of these are true:

- UCM full backup safely preserved;
- official firmware `1.0.18.18` installed and verified, unless a concrete risk discovered during backup/inventory justifies deferring it;
- Teleport remote path working from outside the home LAN;
- dedicated owner SIP extension registered over private tunnel;
- dedicated Ralphi service identity created;
- internal call test passes;
- one bounded Guayaquil/mobile PSTN call passes with acceptable audio;
- outbound route translation is documented from live PBX config;
- VoiceOps guarded Originate path is implemented with policy, permit, audit and tests;
- public SIP/RTP remains closed;
- international remains disabled by default.
