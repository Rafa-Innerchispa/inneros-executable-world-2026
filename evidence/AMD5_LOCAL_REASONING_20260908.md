# AMD .5 Local Reasoning Evidence — 2026-09-08

## Scope
Bounded contract validation for InnerOS VoiceOps using a normalized Physical Guardian incident. This is not a production camera action and contains no customer data.

## Runtime
- Provider: `local-amd-5`
- Backend: vLLM
- Effective local endpoint reported by the local model router: `http://127.0.0.1:18000`
- Model: `QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ`
- Hardware: AMD Radeon AI PRO R9700 / gfx1201
- External fallback: false

## Input boundary
VoiceOps received an already-normalized Guardian incident with an `action_candidate` of `create_work_order`, high priority, `DEVICE_OFFLINE`, requiring human approval. VoiceOps was explicitly instructed not to invent or replace the physical diagnosis.

## Observed model result
The local model returned a compact proposal preserving:
- `action_type=create_work_order`
- `requires_approval=true`
- `priority=high`
- `reason_code=DEVICE_OFFLINE`
- routing policy `local_first`
- provider `local-amd-5`
- model `QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ`
- `external_fallback=false`

## Truth boundary
This proves a live local inference against the VoiceOps reasoning contract on AMD .5. It does **not** yet prove the full microphone -> AssemblyAI -> AMD -> approval -> action E2E path.

## Tooling anomaly found
The generic local model benchmark helper attempted model discovery against port `8000` and returned `vllm_models_unavailable`, while the health/router path showed the active OpenAI-compatible vLLM model on port `18000`. Direct local-model execution through the router succeeded. Treat this as a benchmark-helper endpoint mismatch, not as a VoiceOps inference failure.
