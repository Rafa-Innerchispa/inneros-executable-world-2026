# Canonical Demo Script

## Goal

Demonstrate one voice request becoming governed execution with visible evidence and measurable Human Time Returned.

## Scene

Synthetic technical-services/building environment. No real customer or security data.

## Conversation

**User:** “Ralphi, tenemos una alarma en el acceso norte. Revisa qué ocurre y abre una orden para el técnico si corresponde.”

VoiceOps should:

1. show realtime AssemblyAI transcription;
2. resolve the synthetic site/asset context;
3. inspect demo alarm/device state;
4. explain the detected issue briefly;
5. propose the appropriate operational action;
6. request explicit approval.

**VoiceOps:** “Detecté pérdida de señal en la cámara del acceso norte. Puedo crear una orden prioritaria y asignarla al técnico disponible. ¿Autorizas?”

**User:** “Sí, autoriza y avísame cuando quede creada.”

VoiceOps should:

7. capture approval evidence;
8. execute the synthetic work-order action;
9. capture result evidence;
10. calculate/show HTR;
11. expose Decision Evidence / Routing Evidence / replay reference;
12. answer by voice.

**VoiceOps:** concise completion response with work-order identifier and evidence status.

## What the judge sees

- live transcript;
- current VoiceOps state;
- local-first routing decision;
- proposed action;
- approval event;
- tool execution;
- result;
- HTR metric;
- audit/evidence link.

## Demo fallback

If live microphone/browser permissions fail, provide a deterministic synthetic audio fixture that runs the exact same backend workflow. The fallback must still use AssemblyAI and must be labeled as prerecorded test input, not live speech.

## Forbidden shortcuts

- fake tool results presented as production results;
- hidden manual clicks that actually perform the workflow;
- precomputed HTR labeled MEASURED without evidence;
- a prerecorded video as the only functional prototype;
- production customer/security data.
