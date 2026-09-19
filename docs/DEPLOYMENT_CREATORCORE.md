# VoiceOps public deployment — CreatorCore

Canonical public hostname: `voiceops.creatorcore.ai`

## Runtime contract

The application is container-ready and starts through `voiceops-web`.

Runtime environment:

- `PORT`: injected by the hosting platform. Default local port remains 8765.
- `VOICEOPS_HOST=0.0.0.0`: required inside the container.
- `VOICEOPS_REASONER=synthetic`: safe public default. Do not label public runs as AMD live unless a real `local-amd-5` response is present.
- `VOICEOPS_ENABLE_LIVE_ASSEMBLYAI=true`: enables the server endpoint that mints temporary browser Voice Agent tokens.
- `ASSEMBLYAI_API_KEY`: secret, server-side only. Never commit, log, expose to JavaScript, screenshots, evidence JSON, or public configuration.

Health endpoint: `GET /healthz`.

The health response reports only whether a credential is configured, never the credential itself.

## AssemblyAI browser boundary

The browser never receives the AssemblyAI API key. The server calls the Voice Agent token endpoint and returns a short-lived, single-use temporary token. The browser then opens the AssemblyAI Voice Agent WebSocket with that temporary token.

## Public truth boundary

Cloud-hosted public mode defaults to the deterministic synthetic reasoner because the local AMD .5 runtime is not implicitly reachable from Cloud Run. This is deliberate.

The UI may show `AMD .5 LIVE` only when route evidence contains a real `local-amd-5` model response with `truth=LIVE_MODEL_RESPONSE`.

A complete live proof remains:

`browser microphone -> AssemblyAI -> InnerOS -> AMD .5 -> approval -> synthetic action -> evidence -> spoken completion`

That same-run chain must be captured before the submission claims full live E2E.

## Domain

Use `voiceops.creatorcore.ai`, alongside the existing InnerOS family such as `inneros.creatorcore.ai` and `workforce.creatorcore.ai`.

Do not use a PC Doctor hostname for this hackathon product.

## Security

- no production writes;
- no customer PII;
- no camera credentials or private topology;
- API key remains server-side;
- browser receives temporary single-use tokens only;
- approval remains fail-closed;
- ambiguous authorization cannot execute the consequential action.
