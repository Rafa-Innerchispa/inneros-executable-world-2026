# AssemblyAI technology matrix — InnerOS VoiceOps

Status reflects implemented code in this repository, not marketing intent.

| AssemblyAI capability | VoiceOps use | Status | Truth boundary |
|---|---|---|---|
| Voice Agent API | Browser speech-in/speech-out lane | IMPLEMENTED / LIVE VALIDATION PENDING | Requires server-side API key and explicit live enable flag |
| Universal-3.5 Pro Realtime | Custom STT lane when InnerOS owns reasoning/TTS | IMPLEMENTED | Provider session still requires live key validation |
| Neural turn detection | Managed Voice Agent API conversation turn-taking | IMPLEMENTED BY PROVIDER LANE | Only claimed live after provider session |
| `end_of_turn_confidence` | Gate low-confidence final turns before expensive reasoning in custom STT lane | IMPLEMENTED | Threshold defaults to 0.5 and is configurable |
| Dynamic `agent_context` | Refresh STT context after InnerOS reply | IMPLEMENTED | Evidence records metadata, not context text |
| Browser temporary tokens | Keep AssemblyAI API key server-side | IMPLEMENTED | Token endpoint disabled by default; 120 s TTL + rate limit |
| Native TTS | Play `reply.audio` PCM16 from managed Voice Agent API | IMPLEMENTED | Live audio requires provider session |
| Tool calling | Bridge spoken requests to governed InnerOS tools | IMPLEMENTED | Tool requests are deferred until `reply.done` |
| Barge-in / interruption | Discard pending tool requests and flush queued audio on interrupted replies | IMPLEMENTED | Prevents interrupted agent reply from triggering queued backend action |
| Explicit `session.end` | Close billable live session intentionally | IMPLEMENTED | Browser sends explicit end on stop/unload |
| LLM Gateway | Read-only post-action QA critic | IMPLEMENTED / LIVE VALIDATION PENDING | No execution authority; minimized evidence only |
| LLM Gateway Structured Outputs | Typed QA scores for task success, approval adherence, evidence completeness | IMPLEMENTED | JSON schema + JSON repair request |
| PII Redaction | Post-session archival transcript privacy | IMPLEMENTED AS REQUEST BUILDER | Not used on realtime control path |
| Entity Detection | Optional post-session structured speech understanding | IMPLEMENTED AS REQUEST BUILDER | Raw entities must not be exposed in public evidence automatically |
| Content Moderation | Post-session guardrail metadata | IMPLEMENTED AS REQUEST BUILDER | Does not authorize or block physical actions by itself |
| Sentiment Analysis | Not used in current Spanish demo | INTENTIONALLY NOT ENABLED | Current documented language support is English |
| Automatic LLM Gateway fallback | Possible recovery lane | INTENTIONALLY NOT DEFAULT | Local-first AMD remains primary; external fallback requires policy/evidence |
| AssemblyAI MCP / coding-agent skill | Developer tooling | NOT COUNTED AS PRODUCT FEATURE | Useful for development, not a judge-facing VoiceOps capability |

## Canonical live architecture

```text
Browser microphone
  -> AssemblyAI Voice Agent API
       - realtime speech recognition
       - neural turn detection
       - partial/final transcript
       - TTS
       - barge-in
       - tool calling
  -> governed tool call
  -> InnerOS Voice Gateway
  -> Physical Guardian normalized incident
  -> Resource Fabric / AMD .5 local reasoning
  -> explicit approval gate
  -> synthetic Service Operations action
  -> Decision Evidence / Forensic Replay / HTR
  -> tool result back to AssemblyAI
  -> spoken confirmation
```

## Safety rule for tool calling

`tool.call` is not treated as authorization.

The browser waits for `reply.done` before dispatching queued tool calls. If the reply is interrupted, pending calls are discarded. For approval, the backend receives the latest finalized user transcript, not arbitrary authorization text invented by the model. The InnerOS approval gate then evaluates that phrase fail-closed.

## Secondary custom lane

VoiceOps also retains the lower-level Streaming STT architecture:

```text
AssemblyAI Universal-3.5 Pro Realtime
  -> end_of_turn + end_of_turn_confidence
  -> dynamic agent_context
  -> InnerOS / AMD .5
  -> local XTTS/Piper
```

This proves VoiceOps is not locked to a single managed agent topology and lets the submission demonstrate both the sponsor's managed Voice Agent API and the composable Streaming API.

## Post-session privacy and QA

For recordings that are intentionally retained for evaluation, the adapter can build an AssemblyAI asynchronous request using Universal-3 Pro with PII Redaction, Entity Detection, and Content Moderation. The LLM Gateway critic receives minimized operational evidence rather than raw transcript text and returns structured 1-5 QA scores.

No post-session cloud analysis is required for the core governed action loop. It is an optional evaluation layer.
