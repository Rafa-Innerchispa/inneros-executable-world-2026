# Resource Fabric Route Evidence — 2026-09-08

Project: `inneros-voiceops-assemblyai`
Task: `ops_e6fefdbe0e3d`

## Capability binding

The project was linked to:

- capability: `heavy_reasoning`
- provider: `local-amd-5`
- policy: `local_first`

## Route result

`resource_fabric_route(project_id="inneros-voiceops-assemblyai", task_class="heavy_reasoning", prefer_cloud=false)` returned a local route:

- provider: `local-amd-5`
- node: AMD .5
- runtime: `vllm`
- model: `QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ`
- reason codes: `local_first`, `capacity_available`

## Runtime observation

The AMD runtime inventory confirms the resident Qwen model and ROCm 10 container on the Radeon AI PRO R9700. A separate benchmark helper currently reports `vllm_models_unavailable` because its node probe checks the AMD host at port `8000`, while the aggregate local model health plane exposes the working OpenAI-compatible model proxy at `127.0.0.1:18000` and returns the Qwen model from `/v1/models`.

This checkpoint therefore claims **routing/binding evidence**, not a successful live VoiceOps model inference yet. The live inference benchmark remains pending until the endpoint/proxy mismatch is reconciled or the existing InnerOS routing callable is bound directly.
