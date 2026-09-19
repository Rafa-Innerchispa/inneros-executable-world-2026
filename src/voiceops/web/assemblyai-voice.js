/** AssemblyAI Voice Agent layer for InnerOS VoiceOps canonical UI */
(function () {
  const liveBtn = document.getElementById("liveMicBtn");
  const stopBtn = document.getElementById("stopMicBtn");
  const statusEl = document.getElementById("voiceAgentStatus");
  const agentTranscriptEl = document.getElementById("agentTranscript");
  const userTranscriptEl = document.getElementById("transcriptBox");
  const orb = document.getElementById("voiceOrb");
  const audioBadge = document.getElementById("audioSourceBadge");
  const voiceBadge = document.getElementById("assemblyaiVoiceBadge");

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function setLiveStatus(text, kind = "") {
    if (statusEl) {
      statusEl.textContent = text;
      statusEl.className = kind ? `assemblyai-live-status ${kind}` : "assemblyai-live-status";
    }
    if (orb) orb.className = `voice-orb ${kind || "idle"}`;
    if (audioBadge) audioBadge.textContent = `AUDIO: ${kind === "ready" || kind === "active" ? "ASSEMBLYAI LIVE" : "STANDBY"}`;
  }

  const voiceAgent = {
    ws: null,
    mediaStream: null,
    audioCtx: null,
    processor: null,
    source: null,
    silentGain: null,
    ready: false,
    sessionId: null,
    lastFinalUserTranscript: "",
    pendingToolCalls: [],
    handledToolCallIds: new Set(),
    scheduledAudio: [],
    nextPlaybackTime: 0,
  };

  const inspectTool = {
    type: "function",
    name: "inspect_and_propose_action",
    execution_mode: "interactive",
    description: "Inspect operational state and propose a governed action. Never execute without approval.",
    parameters: { type: "object", properties: {}, required: [] },
  };
  const approveTool = {
    type: "function",
    name: "approve_pending_action",
    execution_mode: "interactive",
    description: "Approve a pending governed action when the user explicitly authorizes.",
    parameters: { type: "object", properties: {}, required: [] },
  };

  function voiceAgentConfig() {
    return {
      type: "session.update",
      session: {
        system_prompt: [
          "Eres la interfaz de voz de InnerOS VoiceOps. Responde en español, breve y profesional.",
          "Para solicitudes operativas llama inspect_and_propose_action. No inventes telemetría.",
          "Solo llama approve_pending_action con autorización explícita del usuario.",
        ].join(" "),
        greeting: "InnerOS VoiceOps listo. ¿Qué quieres revisar en Guayaquil?",
        output: { voice: "anna", format: { encoding: "audio/pcm" } },
        input: {
          format: { encoding: "audio/pcm" },
          keyterms: ["InnerOS", "Ralphi", "alarma", "solar", "sí autorizo"],
          language_codes: ["es"],
        },
        tools: [inspectTool],
      },
    };
  }

  function phaseUpdate(phase) {
    if (phase === "approval") {
      return {
        type: "session.update",
        session: {
          system_prompt: "Hay propuesta pendiente. Pide autorización explícita. Si autoriza, llama approve_pending_action.",
          tools: [approveTool],
        },
      };
    }
    return { type: "session.update", session: { system_prompt: "Operación completada. Confirma resultado.", tools: [] } };
  }

  function pcm16Base64(floatSamples, inputRate) {
    const ratio = inputRate / 24000;
    const outputLength = Math.max(1, Math.floor(floatSamples.length / ratio));
    const pcm = new Int16Array(outputLength);
    for (let i = 0; i < outputLength; i += 1) {
      const sample = Math.max(-1, Math.min(1, floatSamples[Math.min(floatSamples.length - 1, Math.floor(i * ratio))]));
      pcm[i] = sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767);
    }
    const bytes = new Uint8Array(pcm.buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(binary);
  }

  function flushVoicePlayback() {
    for (const source of voiceAgent.scheduledAudio) {
      try { source.stop(); } catch (_) {}
    }
    voiceAgent.scheduledAudio = [];
    if (voiceAgent.audioCtx) voiceAgent.nextPlaybackTime = voiceAgent.audioCtx.currentTime;
  }

  function playVoiceAgentAudio(data) {
    if (!voiceAgent.audioCtx) return;
    const binary = atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer);
    const buffer = voiceAgent.audioCtx.createBuffer(1, pcm.length, 24000);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 32768;
    const source = voiceAgent.audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(voiceAgent.audioCtx.destination);
    const startAt = Math.max(voiceAgent.audioCtx.currentTime, voiceAgent.nextPlaybackTime);
    source.start(startAt);
    voiceAgent.nextPlaybackTime = startAt + buffer.duration;
    voiceAgent.scheduledAudio.push(source);
    source.onended = () => {
      voiceAgent.scheduledAudio = voiceAgent.scheduledAudio.filter((item) => item !== source);
    };
  }

  async function executeVoiceTool(call) {
    const exactUserText = voiceAgent.lastFinalUserTranscript.trim();
    if (!exactUserText) return { error: "no finalized user transcript available for tool binding" };
    if (call.name === "inspect_and_propose_action") {
      return api("/api/tool/inspect-and-propose", { method: "POST", body: JSON.stringify({ intent: exactUserText }) });
    }
    if (call.name === "approve_pending_action") {
      return api("/api/tool/approve-pending", { method: "POST", body: JSON.stringify({ authorization_phrase: exactUserText }) });
    }
    return { error: `unsupported tool: ${call.name}` };
  }

  async function flushToolCalls() {
    if (!voiceAgent.ws || voiceAgent.ws.readyState !== WebSocket.OPEN) return;
    const calls = voiceAgent.pendingToolCalls.splice(0);
    for (const call of calls) {
      let result;
      try {
        result = await executeVoiceTool(call);
        if (window.refreshGovernedState) await window.refreshGovernedState();
      } catch (err) {
        result = { error: err.message };
      }
      if (call.name === "inspect_and_propose_action" && !result.error) {
        voiceAgent.ws.send(JSON.stringify(phaseUpdate(result.requires_approval ? "approval" : "complete")));
      } else if (call.name === "approve_pending_action") {
        voiceAgent.ws.send(JSON.stringify(phaseUpdate("complete")));
      }
      voiceAgent.ws.send(JSON.stringify({ type: "tool.result", call_id: call.call_id, result: JSON.stringify(result) }));
      voiceAgent.handledToolCallIds.add(call.call_id);
    }
  }

  async function handleVoiceAgentMessage(event) {
    const msg = JSON.parse(event.data);
    if (msg.type === "session.ready") {
      voiceAgent.ready = true;
      voiceAgent.sessionId = msg.session_id;
      setLiveStatus(`LIVE · ${msg.session_id}`, "ready");
      if (voiceBadge) voiceBadge.textContent = "AssemblyAI Voice Agent · anna";
    } else if (msg.type === "transcript.user") {
      voiceAgent.lastFinalUserTranscript = msg.text || "";
      if (userTranscriptEl) userTranscriptEl.textContent = voiceAgent.lastFinalUserTranscript;
    } else if (msg.type === "reply.audio" && msg.data) {
      playVoiceAgentAudio(msg.data);
    } else if (msg.type === "transcript.agent" && agentTranscriptEl) {
      agentTranscriptEl.textContent = msg.text || "";
    } else if (msg.type === "tool.call") {
      const duplicate =
        voiceAgent.handledToolCallIds.has(msg.call_id) ||
        voiceAgent.pendingToolCalls.some((call) => call.call_id === msg.call_id);
      if (!duplicate) {
        voiceAgent.pendingToolCalls.push({ call_id: msg.call_id, name: msg.name });
        setLiveStatus(`TOOL · ${msg.name}`, "active");
      }
    } else if (msg.type === "reply.done") {
      if (msg.status === "interrupted") {
        voiceAgent.pendingToolCalls = [];
        flushVoicePlayback();
        setLiveStatus("INTERRUPTED", "warning");
      } else {
        await flushToolCalls();
        if (voiceAgent.ready) setLiveStatus(`LIVE · ${voiceAgent.sessionId}`, "ready");
      }
    } else if (msg.type === "session.error") {
      setLiveStatus(`ERROR · ${msg.message || msg.code}`, "blocked");
    } else if (msg.type === "session.ended") {
      setLiveStatus("SESSION ENDED");
      cleanupVoiceAgent(false);
    }
  }

  function cleanupVoiceAgent(closeSocket = true) {
    voiceAgent.ready = false;
    voiceAgent.pendingToolCalls = [];
    voiceAgent.handledToolCallIds.clear();
    flushVoicePlayback();
    if (voiceAgent.processor) {
      voiceAgent.processor.disconnect();
      voiceAgent.processor.onaudioprocess = null;
    }
    if (voiceAgent.source) voiceAgent.source.disconnect();
    if (voiceAgent.silentGain) voiceAgent.silentGain.disconnect();
    if (voiceAgent.mediaStream) voiceAgent.mediaStream.getTracks().forEach((track) => track.stop());
    if (voiceAgent.audioCtx) voiceAgent.audioCtx.close().catch(() => {});
    if (closeSocket && voiceAgent.ws && voiceAgent.ws.readyState === WebSocket.OPEN) voiceAgent.ws.close();
    voiceAgent.ws = null;
    if (liveBtn) liveBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
  }

  async function startVoiceAgent() {
    if (!liveBtn) return;
    liveBtn.disabled = true;
    setLiveStatus("REQUESTING TOKEN…", "active");
    try {
      const current = await api("/api/state");
      if (!current.assemblyai_voice_agent_enabled) throw new Error("Live AssemblyAI disabled on server");
      await api("/api/reset", { method: "POST", body: "{}" });
      const tokenPayload = await api("/api/assemblyai/token");
      voiceAgent.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
      voiceAgent.audioCtx = new AudioContext({ sampleRate: 24000 });
      await voiceAgent.audioCtx.resume();
      voiceAgent.source = voiceAgent.audioCtx.createMediaStreamSource(voiceAgent.mediaStream);
      voiceAgent.processor = voiceAgent.audioCtx.createScriptProcessor(2048, 1, 1);
      voiceAgent.silentGain = voiceAgent.audioCtx.createGain();
      voiceAgent.silentGain.gain.value = 0;
      voiceAgent.source.connect(voiceAgent.processor);
      voiceAgent.processor.connect(voiceAgent.silentGain);
      voiceAgent.silentGain.connect(voiceAgent.audioCtx.destination);
      voiceAgent.ws = new WebSocket(`wss://agents.assemblyai.com/v1/ws?token=${encodeURIComponent(tokenPayload.token)}`);
      voiceAgent.ws.addEventListener("open", () => {
        setLiveStatus("CONNECTED", "active");
        voiceAgent.ws.send(JSON.stringify(voiceAgentConfig()));
      });
      voiceAgent.ws.addEventListener("message", (event) => {
        handleVoiceAgentMessage(event).catch((err) => setLiveStatus(`ERROR · ${err.message}`, "blocked"));
      });
      voiceAgent.ws.addEventListener("close", () => cleanupVoiceAgent(false));
      voiceAgent.ws.addEventListener("error", () => setLiveStatus("WEBSOCKET ERROR", "blocked"));
      voiceAgent.processor.onaudioprocess = (audioEvent) => {
        if (!voiceAgent.ready || !voiceAgent.ws || voiceAgent.ws.readyState !== WebSocket.OPEN) return;
        voiceAgent.ws.send(JSON.stringify({
          type: "input.audio",
          audio: pcm16Base64(audioEvent.inputBuffer.getChannelData(0), voiceAgent.audioCtx.sampleRate),
        }));
      };
      if (stopBtn) stopBtn.disabled = false;
    } catch (err) {
      setLiveStatus(`OFFLINE · ${err.message}`, "blocked");
      cleanupVoiceAgent(false);
    }
  }

  function stopVoiceAgent() {
    if (voiceAgent.ws && voiceAgent.ws.readyState === WebSocket.OPEN) {
      voiceAgent.ws.send(JSON.stringify({ type: "session.end" }));
      setLiveStatus("ENDING…", "warning");
      window.setTimeout(() => cleanupVoiceAgent(true), 1200);
    } else {
      cleanupVoiceAgent(true);
      setLiveStatus("SESSION ENDED");
    }
  }

  if (liveBtn) {
    liveBtn.replaceWith(liveBtn.cloneNode(true));
    document.getElementById("liveMicBtn").addEventListener("click", startVoiceAgent);
  }
  if (stopBtn) {
    stopBtn.replaceWith(stopBtn.cloneNode(true));
    document.getElementById("stopMicBtn").addEventListener("click", stopVoiceAgent);
  }

  window.startAssemblyAIVoice = startVoiceAgent;
  window.stopAssemblyAIVoice = stopVoiceAgent;
})();
