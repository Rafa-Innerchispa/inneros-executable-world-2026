# VoiceOps SIP/RTP Bridge

## Purpose

This bridge connects the AssemblyAI VoiceOps pipeline to the existing Grandstream UCM6104 without exposing SIP or RTP to the public Internet.

The media boundary is explicit:

- UCM side: SIP/UDP plus RTP with G.711 PCMU or PCMA at 8 kHz mono.
- AssemblyAI side: PCM signed 16-bit little-endian, 16 kHz mono.
- `G711AssemblyAudioBridge` performs the bounded conversion in both directions.
- `GrandstreamSipClient` handles SIP digest registration and builds policy-gated INVITEs.

No telephony credential is stored in this repository.

## Live UCM inventory verified 2026-09-14

- Model: Grandstream UCM6104
- Firmware: 1.0.18.12
- UCM LAN address: 192.168.1.6
- SIP UDP: 4321
- RTP range: 10000-20000
- AMI TCP: 7777, enabled, but no AMI users currently exist
- VoIP trunks: none
- Analog trunks: two
- Cellular outbound route: `_09XXXXXXXX`, primary analog trunk index 2
- Local fixed-line outbound route: `_XXXXXXXXX`, primary analog trunk index 2

The exact dial patterns above came from the live UCM inventory. The runtime must not invent route prefixes.

## Live signaling evidence

A pre-existing unused SIP extension, 1003, was used as the temporary VoiceOps runtime identity without changing its configuration.

Observed from the Intel .4 server on the same LAN:

1. SIP REGISTER for 1003 returned a Digest challenge.
2. Authenticated REGISTER returned `200 OK`.
3. UCM inventory then showed 1003 as `Idle` registered from 192.168.1.4.
4. A bounded internal call from 1003 to physical FXS1 extension 1001 produced:
   - Digest challenge
   - `100 Trying`
   - `180 Ringing`
   - bounded `CANCEL`
   - `200 OK` to the CANCEL

This proves the live signaling path:

`VoiceOps on .4 -> SIP -> UCM6104 -> physical FXS extension`

No PSTN call was made during this proof.

## Dedicated extension migration

A dedicated plain-SIP extension 1005 named `Ralphi VoiceOps` was created in UCM configuration. The UCM returned `need_apply=yes`.

Current state:

- 1005 is visible in configuration inventory.
- Asterisk runtime still returns `404 Not Found` to REGISTER for 1005.
- Existing loaded SIP extensions return the normal Digest challenge.
- Therefore 1005 must not be used until the UCM `Apply Changes` action has completed.

Temporary runtime identity: 1003.
Target runtime identity after Apply Changes: 1005.

## Audio contract

`G711AssemblyAudioBridge` accepts RTP packets with:

- payload 0: PCMU / 8000 Hz
- payload 8: PCMA / 8000 Hz
- payload 101 telephone events are ignored by the speech-audio path

Inbound conversion:

`RTP G.711 8 kHz -> PCM16 8 kHz -> deterministic 2x interpolation -> PCM16 16 kHz`

For a conventional 20 ms RTP packet:

- 160 G.711 bytes enter the bridge.
- 320 PCM16 samples leave the bridge.
- Output size is 640 bytes.

That output matches `AssemblyAIStreamingAdapter.audio_contract`:

- encoding: `pcm_s16le`
- channels: 1
- sample rate: 16000 Hz

Outbound conversion reverses the boundary:

`PCM16 16 kHz -> 8 kHz downsample -> PCMU/PCMA -> RTP`

## Policy boundary

`GrandstreamSipClient` delegates dial authorization to `voiceops.telephony_policy.authorize_call`.

A call cannot become execution-ready unless all required policy inputs are satisfied, including a verified route and an explicit PBX dial string. The SIP layer never guesses route prefixes.

International calls remain disabled by default. Domestic PSTN calling is not implied by the internal signaling proof.

## Remote administration while traveling

Tailscale is the temporary remote path while UniFi Teleport is being repaired.

The Intel .4 server is in the tailnet and is also on the UCM LAN. Full `192.168.1.0/24` subnet advertisement is a separate network-administration step and is not required for VoiceOps running locally on .4.

No SIP/RTP public port-forward was added.

## Verification status

- Live SIP REGISTER: PASS
- Live internal physical ringing: PASS
- RTP/G.711 codec and packet bridge: unit-tested
- AssemblyAI PCM16 boundary: unit-tested
- Live bidirectional RTP through the UCM: pending bounded live media validation
- Live PSTN call: pending explicit owner-approved destination and final media validation
