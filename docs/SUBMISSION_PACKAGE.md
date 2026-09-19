# AssemblyAI Voice Agent Hackathon — Submission Package

## Final title

**InnerOS VoiceOps — Governed Voice-to-Action for Real Operations**

## Short description

InnerOS VoiceOps turns spoken operational intent into safe, auditable action. AssemblyAI handles realtime voice; InnerOS binds finalized speech to explicit approval and a single-use execution permit; local AMD/Qwen reasoning proposes the action; Evidence/Replay records exactly what happened and Human Time Returned shows the operational impact.

## Long description

Most voice agents stop at conversation. InnerOS VoiceOps crosses the harder boundary: from spoken intent to governed execution.

A user speaks naturally. AssemblyAI provides the realtime voice layer with turn handling, speech context, tool calling and interruption-aware interaction. InnerOS then treats the finalized transcript as evidence, not as automatic authorization. The system inspects operational state, proposes a bounded action, requests explicit approval and issues a short-lived single-use Voice Execution Permit bound to the exact session, event, transcript, proposal, state and action.

Only after that permit validates can the demo action execute. Every step is captured in Decision Evidence, replayable afterwards, with Human Time Returned separated into measured and estimated claims.

The project is local-first. AMD .5/Qwen provides the private reasoning path in the live local stack. AssemblyAI is a reusable platform provider rather than a product-specific secret. WhatsApp voice notes use the same reusable Voice Fabric with managed AssemblyAI STT and local Whisper fallback. Physical Guardian contributes sanitized `NormalizedEvent` incidents without duplicating camera logic inside VoiceOps.

For judging, the public Cloud Run surface intentionally runs a safe synthetic reasoner and never performs production writes. The same governance state machine is used in the captured live AssemblyAI + AMD .5 E2E evidence. This keeps the public demo honest while showing the architecture that matters: **Intent -> Governed Execution -> Evidence -> Human Time Returned**.

## What is novel

VoiceOps does not equate a tool call with permission. It creates a cryptographically bound, short-lived, single-use execution permit only after exact finalized speech and explicit approval. Barge-in/cancellation and ambiguous approval fail closed. This makes voice usable for operational workflows where merely hearing the user is not enough.

## Technologies

- AssemblyAI Voice Agents / Streaming v3
- semantic turn detection and end-of-turn handling
- keyterms and dynamic `agent_context`
- tool calling and interruption/barge-in handling
- session lifecycle/resume capabilities
- PII redaction, entity detection and content moderation capabilities
- InnerOS Resource Fabric and governance layer
- AMD Radeon AI PRO R9700 node `.5` with local Qwen reasoning
- Voice Execution Permits: HMAC, TTL, event/transcript/proposal/state/action binding, single-use consumption
- WhatsApp / Evolution reusable Voice Fabric with local Whisper fallback
- Physical Guardian sanitized `NormalizedEvent` contract
- Decision Evidence / Forensic Replay / Human Time Returned
- Google Cloud Run + Cloudflare public judge surface
- Python 3.11/3.12

## Public links

- Repository: `https://github.com/Rafa-Innerchispa/inneros-voiceops-assemblyai`
- Demo: `https://voiceops.creatorcore.ai/`

Video and pitch-deck URLs should be inserted here after media upload; do not invent placeholders in the final organizer form.

## Judge flow

1. Open the public demo.
2. Reset the demo state.
3. Submit an operational intent such as: `Review the north access incident and create a technical work order if appropriate.`
4. Observe that the system proposes an action but does not execute it.
5. Try an ambiguous phrase such as `If you think it is necessary.` The action stays blocked.
6. Give explicit authorization: `Yes, I authorize it.`
7. Observe the synthetic work order, execution-permit evidence, correlation/session identifiers and HTR result.
8. Open Evidence / Replay and inspect the chronological decision trail.

The public surface has `production_writes=false`. It is intentionally judge-safe.

## 75-second spoken pitch

Voice agents are very good at talking. Real operations need something harder: knowing when speech is actually permission to act.

InnerOS VoiceOps turns spoken intent into governed execution. AssemblyAI gives us the realtime voice layer. InnerOS takes the finalized transcript, inspects the operational state and asks our local AMD/Qwen reasoning layer what should happen next. But a recommendation is not authorization.

Before any consequential action, VoiceOps requires explicit approval and creates a short-lived, single-use execution permit cryptographically bound to the session, the incident, the exact approval transcript, the proposal and the state the agent saw. Ambiguous approval fails closed. Interruption does not become accidental execution.

Then we create the bounded demo action and preserve the entire decision as replayable evidence. We also show Human Time Returned, because the real product is not tokens per second. It is how much coordination humans no longer have to do.

The result is a voice agent designed not just to answer, but to act safely, locally and accountably.

## Demo recording outline

- 0–10 s: problem statement and one-screen UI
- 10–25 s: spoken incident request through AssemblyAI
- 25–38 s: proposal appears, ambiguous approval is rejected
- 38–52 s: explicit approval, single-use permit, action result
- 52–65 s: Evidence / Replay and HTR
- 65–75 s: architecture card: AssemblyAI + InnerOS + AMD local reasoning + reusable WhatsApp/Guardian contracts

## Evidence-backed claims allowed in submission

- 60/60 canonical tests PASS on final technical verification.
- Explicit approval fails closed for ambiguous phrases.
- Voice Execution Permit is bound and single-use.
- Public judge surface is deployed and returns a working `/api/state`.
- Reusable AssemblyAI provider preflight is PASS with credentials kept server-side.
- Prior captured local live E2E includes AssemblyAI STT -> InnerOS -> AMD .5 -> approval -> synthetic action -> Evidence/Replay -> spoken completion.
- Reusable WhatsApp Voice Fabric has AssemblyAI routing and local Whisper fallback tests PASS.

## Claims to avoid

- Do not claim the public Cloud Run revision currently uses AMD .5; it runs the synthetic reasoner.
- Do not claim live AssemblyAI is enabled on the public revision until a Secret Manager binding is deployed.
- Do not claim production work-order or building-control writes; the hackathon action is bounded/synthetic.
- Do not claim `/healthz` is healthy until its current 404 discrepancy is fixed; `/api/state` is the verified operational endpoint.

## Submission status

Technical build: **ready**.

Still manual before organizer submission:

- attach/create the team/project entry on the event page if not already attached
- capture final judge screenshots
- record/upload demo video
- upload pitch deck/media if the form accepts them
- paste the final copy/links into the lablab.ai submission form
- verify the organizer's exact closing hour before final submit

Internal freeze target: **September 29, 2026 at 22:00 America/Guayaquil**. The event build window is September 1–30, 2026; the accessible official page previously did not expose an exact closing hour, so the project should not depend on late September 30.
