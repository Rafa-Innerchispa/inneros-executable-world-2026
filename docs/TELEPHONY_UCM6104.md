# InnerOS Telephony Adapter — Grandstream UCM6104

Status date: 2026-09-13

## Scope

This integration connects VoiceOps/Ralphi to the legacy Grandstream UCM6104 through bounded local interfaces. The initial production surface is intentionally read-only. Call origination and other consequential telephony actions remain disabled until a dedicated service identity, routing policy, approval policy, and Voice Execution Permit binding are in place.

## Live verified device state

- Device: Grandstream UCM6104
- LAN address: `192.168.1.6`
- MAC: `00:0B:82:86:33:AB`
- UniFi device state: connected/wired
- HTTP 80: open, redirects to `https://192.168.1.6:8089/`
- HTTPS 8089: open, TLS 1.2, `lighttpd/1.4.47`
- HTTP 8088: open, root returns 404 with `Asterisk/13.4.0` server header
- TCP 389: open
- TCP 7777: open and verified as Asterisk Manager Interface
- AMI banner: `Asterisk Call Manager/2.7.0`
- AMI `Challenge` with `AuthType: MD5`: supported
- Unauthenticated AMI `Ping`: denied, as expected
- SIP UDP bind from the live General SIP page: `4321`
- SIP IPv4 bind address from the live General SIP page: `0.0.0.0` (all IPv4 interfaces)
- A single unauthenticated SIP `REGISTER` probe to `192.168.1.6:4321` received `SIP/2.0 401 Unauthorized` from `192.168.1.6:4321` with a Digest challenge
- SIP response identified the server as `Grandstream UCM6104V1.6A 1.0.18.12`
- TCP 22/443/5038/5039/5060/5061/9090/25000/25001: closed from the LAN probes
- UDP OPTIONS/read-only probes to 4569/5060/5061/9090/25000/25001: no response from either InnerOS `.4` or AMD `.5`

No PBX configuration was changed while collecting this evidence.

## Historical configuration versus live truth

Historical notes confirm extension `1000`, Auth ID `PCD0ct0r1000`, and SIP port `25000` existed in the old documentation. The extension/Auth ID are not yet an authoritative current inventory read. The SIP port is now resolved: the current live UDP bind is `4321`, so `25000` is historical/obsolete for the current LAN SIP listener.

The historical house number and the currently supplied house number differ. VoiceOps must not infer the active DID/trunk from either value. The current trunk and inbound/outbound route inventory remain unverified until an authenticated read-only PBX session is available.

`25000` must therefore be treated as historical/obsolete for the current LAN SIP listener. It does not answer on the PBX LAN address over TCP or UDP from two independent LAN sources, while `4321/UDP` now answers with a valid SIP authentication challenge. `25000` may have been an old bind, an external/NAT-facing port, or a retired setting. UPnP/IGD discovery from the InnerOS host returned no gateway mapping inventory, so no NAT claim is made from that probe.

## Why AMI is now the preferred control path

The UCM6104 exposes AMI on TCP 7777 and supports the standard MD5 challenge flow. That gives InnerOS a narrower and more structured management surface than automating the legacy web UI.

The adapter in `src/voiceops/adapters/grandstream_ami.py` is fail-closed:

- no `Originate` yet;
- no `Command` action;
- no `Hangup`, `Redirect`, transfer, config writes, or route writes;
- only explicit read-only actions are accepted;
- authentication uses AMI MD5 challenge/key rather than sending the secret as an AMI `Secret` field;
- credentials are resolved only at call time;
- production should inject credentials from a server-side vault via `credential_loader`;
- arbitrary AMI headers and action injection are rejected.

Initial read-only capabilities:

- AMI reachability/challenge probe;
- authenticated ping;
- core status;
- extension status via `SIPshowpeer`;
- SIP peer inventory via `SIPpeers`;
- bounded channel/status inspection actions.

## Runtime configuration

Preferred production path: a server-side credential loader backed by Owner Vault/Secret Manager.

Environment fallback supported by the adapter:

- `VOICEOPS_TELEPHONY_AMI_HOST`
- `VOICEOPS_TELEPHONY_AMI_PORT` (verified UCM value: `7777`)
- `VOICEOPS_TELEPHONY_AMI_USERNAME`
- `VOICEOPS_TELEPHONY_AMI_SECRET`

Never commit an AMI or PBX secret to Git, evidence files, coordination logs, screenshots, or test fixtures.

## Required PBX service identity

Do not reuse the administrator login and do not make extension `1000` the permanent Ralphi identity.

Create a dedicated AMI account for VoiceOps with the smallest read permissions needed for the initial phase. Its source ACL should be restricted to the InnerOS LAN nodes that actually need access. Write permissions should remain absent until outbound calling is explicitly implemented and governed.

Separately, when the active SIP bind/transport is known, create a dedicated Ralphi SIP extension. That extension is the voice/media endpoint; the AMI service account is the management/control identity. Keeping them separate avoids turning one leaked credential into universal PBX access.

## Planned governed call flow

Future write-enabled flow, not yet active:

`event/user intent -> VoiceOps policy -> target allowlist -> explicit approval when required -> Voice Execution Permit -> AMI Originate/SIP media bridge -> AssemblyAI -> AMD .5 reasoning -> bounded action -> audit/evidence`

Policy target:

- internal extensions: eligible for automatic calling under policy;
- owner extensions: eligible for automatic calling under policy;
- external allowlist: bounded and audited;
- unknown external numbers: explicit approval;
- international calling: disabled by default;
- duration/spend caps: required before external calling;
- every call: destination, reason, timestamps, result and permit evidence recorded.

## Remaining live verification

1. Provision or safely retrieve a dedicated read-only AMI service credential.
2. Authenticate through AMI and read `CoreStatus` / SIP peer inventory.
3. Verify whether extension `1000` still exists and its live registration status.
4. Read current SIP peer inventory to identify the actual active SIP stack and endpoint names.
5. Read current trunks and inbound/outbound routes through an approved read-only PBX surface.
6. Confirm the current DID/house number from live configuration rather than historical notes.
7. Create a dedicated Ralphi SIP extension on the confirmed `4321/UDP` transport only after the peer/routing inventory is known.
8. Keep call origination disabled until the Voice Execution Permit path and telephony policy are connected end-to-end.

## SIP General Settings discovery from the live firmware UI

The live UCM6104 frontend bundle was inspected read-only on 2026-09-13. The `sipSettings` webpack chunk is `/sipSettings.569c47e4.chunk.js`. The firmware reads the General SIP page with:

- CGI action: `getSIPGenSettings`
- response object: `response.sip_general_settings`
- Realm for Digest Authentication: `realm`
- Bind UDP Port: `bindport`
- Bind IPv4 address: `bindaddr`
- Bind IPv6 address: `bindaddr6`
- Allow Guest Calls: `allowguest`
- Allow Transfer: `allowtransfer`
- MWI From Header: `mwi_from`
- Enable Diversion Header: `enable_diversion`

The same chunk confirms these additional read groups:

- `getSIPMiscSettings` -> `sip_misc_settings`
- `getSIPSSTimerSettings` -> `sip_sessiontimer_settings`
- `getSIPTCPSettings` -> `sip_tcp_settings`
- `getSIPNATSettings` -> `sip_nat_settings`
- `getTOSSettings` -> SIP ToS/media settings

An unauthenticated `getSIPGenSettings` request returns HTTP 200 with UCM status `-6`, so the configuration is session-protected. No attempt is made to bypass that gate.

The owner then read the live General SIP page and confirmed these current values:

- `bindport = 4321`
- `bindaddr = 0.0.0.0`

`0.0.0.0` means Asterisk is bound to all IPv4 interfaces on the appliance rather than a single IPv4 address. A subsequent unauthenticated `REGISTER` to `192.168.1.6:4321` received `401 Unauthorized` plus a Digest challenge from the same endpoint, which independently verifies that SIP is actively listening on UDP 4321. This response does **not** by itself prove that extension `1000` exists, because authentication policy can challenge unknown registrations as well.

`src/voiceops/adapters/grandstream_ucm6104.py` implements the bounded setup/discovery path. It uses the firmware's existing `challenge` -> MD5(`challenge + password`) -> `login` sequence, keeps only the short-lived session cookie in memory, never stores the password on the adapter, and permits only an explicit read-only CGI allowlist. Any `update*`, add/delete, `Originate`, `Command`, or other non-allowlisted action is rejected before a network request is made.

This creates a deliberate split:

`AMI :7777 = live telephony/status control plane`

`legacy CGI :8089 = temporary authenticated configuration discovery`

The CGI reader is intended to establish the authoritative current SIP bind, transports, trunks and routes. It is not the long-term automation surface.
