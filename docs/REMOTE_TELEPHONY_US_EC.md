# Remote telephony: United States -> Ecuador UCM6104

Status date: 2026-09-13

## Goal

Allow the owner to use the Ecuador Grandstream UCM6104 as the PSTN egress point while physically in the United States, while keeping SIP/RTP private and preserving call quality.

## Recommended network path

Preferred path:

`mobile/softphone -> WireGuard or UniFi Teleport -> UniFi gateway -> UCM6104 192.168.1.6:4321/UDP -> Ecuador PSTN`

The live gateway at `192.168.1.1` has been identified read-only as UniFi OS. The UCM6104 SIP listener is independently verified on `192.168.1.6:4321/UDP` and currently binds IPv4 `0.0.0.0`.

Do not expose SIP `4321` or the RTP range directly to the public Internet for this design. Do not put Cloudflare/Spectrum in the RTP media path when the objective is minimum latency and jitter. The VPN should make the remote phone behave like a LAN client instead.

## VPN preference order

1. Native UniFi WireGuard server when the gateway has a suitable public WAN address.
2. UniFi Teleport when zero-configuration NAT traversal is preferable or the gateway is behind NAT.
3. A Tailscale/WireGuard subnet router on an InnerOS host only as a fallback if the gateway cannot provide the VPN service.

Use split tunneling for the Ecuador LAN (`192.168.1.0/24`) rather than forcing all mobile Internet traffic through Ecuador. Voice signalling and RTP to the UCM should traverse the VPN; unrelated Internet traffic should continue to use the phone's local connection.

## SIP client strategy

The legacy Grandstream Wave Lite client explicitly supported the UCM6100 series, but Grandstream now lists Wave Lite as end-of-life and no longer available in Google Play or the Apple App Store. Do not build a new remote-access design around sideloading an abandoned client.

Use a maintained standard SIP softphone over the VPN. The client should register to:

- SIP server: `192.168.1.6`
- transport: UDP initially
- SIP port: `4321`
- account: a dedicated remote-owner extension, not the PBX administrator account and not the future Ralphi service extension

Do not create the extension or guess its credentials until the current extension/routing inventory has been read and a dedicated identity can be provisioned safely.

## Media quality policy

- Keep the media path direct: remote SIP client <-> VPN <-> UCM.
- Avoid SIP/RTP relays unless NAT conditions make them necessary.
- Prefer a short codec list to reduce negotiation ambiguity.
- Prefer G.711 u-law/a-law when the VPN path has adequate bandwidth and the PSTN/trunk path can use it without extra transcoding; otherwise select the best codec supported end-to-end by the live trunk.
- Read the live UCM RTP range before writing firewall rules; do not assume a default range.
- Do not enable UPnP merely for SIP traversal.
- Check/disable SIP ALG only where it actually exists on the WAN path and interferes with SIP; VPN traffic should normally make ALG unnecessary.
- Measure packet loss, RTT and jitter over the actual U.S. mobile/Wi-Fi path before tuning jitter-buffer values.

## Outbound call policy

Initial VoiceOps policy is deliberately narrower than the phone carrier plan:

- Guayaquil fixed lines: permitted for an explicit owner request; autonomous calls require an allowlisted target.
- Ecuador mobile numbers: permitted for an explicit owner request; autonomous calls require an allowlisted target.
- Other Ecuador geographic destinations: classified but disabled until the UCM route patterns and carrier entitlement are verified.
- International calls: disabled by default.
- Internal extensions: permitted only through explicit request or policy allowlist.

Canonical E.164 normalization is separate from the PBX dial string. VoiceOps must not assume the UCM outbound route accepts `+593...`, `0...`, or any particular prefix until the live outbound route is read. Policy approval therefore does not imply execution readiness.

## Firmware

The live UCM6104 identifies as firmware `1.0.18.12`. Grandstream's official UCM61xx firmware page lists `1.0.18.18` as the final supported UCM6100 firmware and states that it contains a security fix. The upgrade must be preceded by a full configuration/data backup and followed by credential review/change per Grandstream guidance.

Do not install unofficial firmware on this production PBX. The expected benefit is not worth the recovery and telephony-availability risk on an end-of-life appliance.

## Safe implementation order

1. Back up the UCM configuration using an authenticated maintenance session.
2. Read current extensions, trunks, inbound/outbound routes, RTP settings and NAT/SIP settings.
3. Upgrade only to official `1.0.18.18` in a maintenance window and re-verify boot, trunks and routes.
4. Rotate/review UCM web credentials after the security update.
5. Create a dedicated owner remote SIP extension and a separate Ralphi SIP extension.
6. Enable native UniFi WireGuard or Teleport and restrict remote access to only the networks/services required.
7. Register a maintained SIP client over the VPN and verify extension-to-extension audio first.
8. Verify one domestic outbound test call with the exact live UCM dial pattern.
9. Measure RTT, jitter and packet loss; then tune codecs/jitter buffer if evidence says it is needed.
10. Only after the route and permit controls are proven, add governed AMI call origination to VoiceOps.

## Explicitly not enabled yet

- public WAN SIP exposure
- public WAN RTP exposure
- Cloudflare/Spectrum media proxy
- AMI `Originate`
- international calling
- guessed outbound dial prefixes
- unofficial UCM firmware
