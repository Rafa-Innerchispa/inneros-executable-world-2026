# Roadmap — AssemblyAI Voice Agent Hackathon

Target submission window ends: **2026-09-30**. Internal target: submit before deadline day.

## P0 — Foundation | Sep 8–10

- [x] Create public GitHub repository
- [x] Canonical README
- [x] Apache-2.0 license
- [x] Project truth document
- [ ] Bootstrap local project/runtime
- [ ] Add Python package/test scaffold
- [ ] Add `.env.example`
- [ ] Implement AssemblyAI realtime adapter contract
- [ ] Add synthetic demo fixture contract

Exit: repository can run tests locally and has a bounded AssemblyAI streaming interface.

## P0 — Voice E2E | Sep 11–15

- [ ] Connect realtime audio → transcript
- [ ] Voice session IDs + correlation IDs
- [ ] turn lifecycle and interruption handling
- [ ] route transcript to InnerOS orchestration
- [ ] return text response
- [ ] bind TTS path
- [ ] record latency measurements

Exit: user can hold a basic realtime voice interaction end-to-end.

## P0 — Governed Execution | Sep 16–19

- [ ] bind one synthetic Service Operations / building workflow
- [ ] approval gate before consequential action
- [ ] tool result captured
- [ ] Decision Evidence visible
- [ ] Routing Evidence visible
- [ ] HTR captured
- [ ] replay/evidence link available

Exit: canonical demo story works from voice intent through operational result and evidence.

## P1 — Judge UI + Reliability | Sep 20–23

- [ ] minimal public judge UI
- [ ] transcript / action timeline
- [ ] approval state
- [ ] HTR card
- [ ] evidence/replay card
- [ ] local/cloud routing indicator
- [ ] reconnect/error UX
- [ ] synthetic demo reset
- [ ] E2E test repeated successfully

Exit: a judge can understand the system without developer narration.

## P0 — Public Demo | Sep 24–25

- [ ] safe deployment
- [ ] no secrets in browser/repo
- [ ] judge URL tested from clean session
- [ ] mobile/desktop sanity check
- [ ] fallback demo path documented

Exit: externally accessible demo works.

## P0 — Submission Package | Sep 26–28

- [ ] project title and short description
- [ ] long description
- [ ] architecture diagram
- [ ] screenshots
- [ ] pitch deck
- [ ] demo script frozen
- [ ] demo video recorded
- [ ] public claims checked against evidence
- [ ] README final refresh
- [ ] submission form drafted

Exit: submission is ready even if development stops.

## P0 — Submit Early | Sep 29

- [ ] final smoke test
- [ ] final evidence snapshot
- [ ] final repo SHA recorded
- [ ] submit to lablab.ai
- [ ] verify submission page

## Sep 30 — Buffer only

Deadline day is not the development plan. Use only for emergency corrections or organizer-required changes.

## Scope discipline

Do not add a second major demo scenario until the canonical one is reliable. Do not rebuild existing InnerOS modules. Do not replace working local infrastructure because a fashionable library appeared on social media three days before judging.
