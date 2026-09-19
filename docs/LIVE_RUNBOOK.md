# InnerOS VoiceOps — Live AssemblyAI Runbook

## Goal
Run the governed VoiceOps demo through AssemblyAI Universal-3.5 Pro Realtime without bypassing InnerOS approval, evidence, or Physical Guardian boundaries.

## Current live contract
- AssemblyAI streaming endpoint: v3 SDK / `wss://streaming.assemblyai.com/v3/ws`
- Speech model: `universal-3-5-pro`
- Audio: PCM16, mono, 16 kHz
- Chunk pacing: 50–1000 ms and no faster than real time
- Session shutdown: always terminate explicitly
- Agent context: seed on connect and refresh after each InnerOS reply

## Secret policy
`ASSEMBLYAI_API_KEY` must be supplied by the runtime environment or secret store. Never commit it to this repository, evidence, screenshots, or demo fixtures.

The repository `.env.example` intentionally contains an empty value only.

## Install
Core tests do not require AssemblyAI or microphone libraries.

For live WAV streaming:

```bash
pip install -e '.[assemblyai]'
```

For microphone mode:

```bash
pip install -e '.[microphone]'
```

PyAudio may require the host PortAudio package depending on the operating system.

## Preflight

```bash
voiceops-live --preflight
```

A successful preflight requires:
- AssemblyAI SDK importable
- `ASSEMBLYAI_API_KEY` present in the runtime environment

The preflight reports only whether the key exists. It never prints the key.

## Reproducible WAV path
Use a WAV fixture that is already PCM16 mono 16 kHz:

```bash
voiceops-live --wav path/to/demo.wav --evidence evidence/live_wav_e2e.json
```

`WavPCM16Source` validates the WAV before opening a paid streaming session. Invalid channels, bit depth, or sample rate fail before streaming.

## Microphone path

```bash
voiceops-live --microphone --evidence evidence/live_microphone_e2e.json
```

Stop with Ctrl+C. The `finally` path terminates the AssemblyAI session and writes the evidence bundle.

## Governed conversation
Recommended demo conversation:

1. User: `Ralphi, revisa la incidencia del acceso norte y abre una orden si corresponde.`
2. Physical Guardian supplies the normalized incident/action candidate.
3. InnerOS local-first reasoning proposes a bounded action.
4. VoiceOps replies that explicit authorization is required.
5. AssemblyAI receives that agent reply as refreshed `agent_context`.
6. User: `Sí, autorizo.`
7. VoiceOps executes only the synthetic/demo work-order action.
8. Evidence Bundle records transcript, route, proposal, approval, action, and HTR classification.

## Cross-repo boundary
VoiceOps must not infer physical anomalies from raw camera state. Physical Guardian owns perception and normalized incident/action candidates. VoiceOps owns speech, turn handling, approval semantics, and voice-to-capability routing. Service Operations owns the real work-order lifecycle.

## Current truth boundary
Implemented and tested locally:
- Audio contract validation
- AssemblyAI streaming adapter lifecycle
- partial vs final turn behavior
- automatic agent-context refresh
- explicit approval gate
- synthetic action path
- Evidence/Replay/HTR contracts
- AMD .5 local reasoning evidence

Still requires external live validation:
- valid AssemblyAI API key in runtime
- one real v3 streaming session
- real microphone or controlled WAV transcription
- capture of provider session/termination evidence

Do not mark the hackathon live E2E complete until those external checks pass.
