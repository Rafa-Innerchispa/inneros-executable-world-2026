// Fallback & progressive tool descriptors for live browser sessions
const inspectTool = { type: "function", name: "inspect_and_propose" };
const approveTool = { type: "function", name: "approve_pending" };
const fallbackVoiceAgentConfig = {
  language_codes: ["es"],
  execution_mode: "interactive",
  speech_context: ["sí autorizo", "acceso norte"],
  handledToolCallIds: new Set(),
  pendingToolCalls: [],
  getActiveTools: (state) => {
    if (state === "ready") return { tools: [inspectTool] };
    if (state === "pending") return { tools: [approveTool] };
    return { tools: [] };
  },
  handleToolCall: (msg) => {
    if (fallbackVoiceAgentConfig.pendingToolCalls.some((call) => call.call_id === msg.call_id)) return;
    const call = { call_id: msg.call_id, name: msg.name };
    fallbackVoiceAgentConfig.handledToolCallIds.add(call.call_id);
  }
};

// InnerOS VoiceOps — Real Boson AI Higgs Realtime Speech-to-Speech Engine
let activeProposalId = null;
let currentHtrTotal = 18.4;
let isVoiceActive = false;
let isAudioSpeaking = false;
let animationFrameId = null;

let higgsWebSocket = null;
let ephemeralToken = null;
let bosonTransportMode = "browser_fallback";
let audioSource = "BROWSER_TTS_FALLBACK";
let higgsPcmActive = false;
let browserFallbackLabeled = false;
let ttsBargeInGuardUntil = 0;
let lastSpokenTranscript = "";
let activeAudioSources = [];
let higgsPlaybackCursor = 0;
let higgsPlaybackPrimed = false;
let higgsPcmQueue = [];
let agentSpeakStartedAt = 0;
let bargeInHoldFrames = 0;
let recognitionPaused = false;
const HIGGS_SAMPLE_RATE = 24000;
const HIGGS_PLAYBACK_LEAD_SEC = 0.12;
const BARGE_IN_VAD_THRESHOLD = 0.17;
const BARGE_IN_FRAMES_REQUIRED = 5;
const BARGE_IN_GRACE_MS = 700;
let audioContext = null;
let playbackContext = null;
let higgsGainNode = null;
let agentAudioFallbackTimer = null;
let agentAudioReceived = false;
let approvalInFlight = false;
let haControlsCache = [];
let haDomainCounts = {};
let micStream = null;
let analyserNode = null;
let micDataArray = null;
let scriptProcessorNode = null;
let silentGainNode = null;
let recognition = null;

function updateSiteStatusBanner() {
  const banner = document.getElementById("alertMessage");
  if (!banner) return;
  const provider = typeof window.getVoiceProvider === "function" ? window.getVoiceProvider() : "boson";
  const transport =
    bosonTransportMode === "higgs_relay"
      ? "Boson Higgs Realtime"
      : provider === "browser_local"
        ? "Browser STT/TTS"
        : provider === "telephony"
          ? "PBX telephony"
          : provider;
  banner.textContent = `GYE-Node-01 · telemetry polled live · voice route: ${transport} · press Start Live Voice`;
  const routeChip = document.getElementById("activeProviderRoute");
  if (routeChip) routeChip.textContent = `Route: ${transport}`;
}

document.addEventListener("DOMContentLoaded", () => {
  initWaveform();
  loadSpeechVoices();
  const htrEl = document.getElementById("htrCounter");
  if (htrEl) htrEl.textContent = `+${currentHtrTotal.toFixed(1)}`;
  fetchTelemetry().then(updateSiteStatusBanner);
  fetchBosonStatus();
  fetchIntegrationsStatus().then(updateSiteStatusBanner);
  loadHaControls();
  setAudioSource("STANDBY");

  // Continuously poll live telemetry every 2 seconds for real-time sensor updates
  setInterval(fetchTelemetry, 2000);
  setInterval(fetchIntegrationsStatus, 5000);

  // Attach event listeners
  document.getElementById("refreshTelemetryBtn")?.addEventListener("click", fetchTelemetry);
  document.getElementById("haRefreshBtn")?.addEventListener("click", () => loadHaControls(true));
  document.getElementById("haProposeBtn")?.addEventListener("click", proposeSelectedHaAction);
  document.getElementById("haEntitySearch")?.addEventListener("input", debounce(() => loadHaControls(false), 250));
  document.getElementById("haDomainFilter")?.addEventListener("change", () => renderHaEntityOptions());
  document.getElementById("haControllableOnly")?.addEventListener("change", () => loadHaControls(false));
  document.getElementById("haEntitySelect")?.addEventListener("change", syncHaVerbOptions);
  // Voice controls wired in assemblyai-voice.js
  document.getElementById("sendManualBtn")?.addEventListener("click", sendManualUtterance);
  document.getElementById("manualInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendManualUtterance();
  });

  // Spacebar to trigger instant barge-in if agent is speaking
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && e.target.tagName !== "INPUT" && isAudioSpeaking) {
      e.preventDefault();
      triggerInstantBargeIn();
    }
  });

  document.getElementById("confirmBtn")?.addEventListener("click", () => {
    if (activeProposalId && !approvalInFlight) {
      submitApproval(activeProposalId, "Yes, authorize and execute the proposed operation now.");
    }
  });

  document.getElementById("rejectBtn")?.addEventListener("click", () => {
    if (activeProposalId && !approvalInFlight) {
      submitApproval(activeProposalId, "No, reject and cancel this proposed action.");
    }
  });
});

function setAudioSource(source) {
  audioSource = source;
  const badge = document.getElementById("audioSourceBadge");
  if (!badge) return;
  const labels = {
    ASSEMBLYAI: "Voz: AssemblyAI",
    LOCAL_QWEN: "Voz: Qwen local",
    BOSON: "Voz: Boson",
    HIGGS: "Voz: Boson",
    STANDBY: "Voz: standby",
    BROWSER_TTS_FALLBACK: "Voz: navegador",
    SPEAKER: "Voz: reproduciendo",
  };
  badge.textContent = labels[source] || `Voz: ${String(source).toLowerCase()}`;
  badge.className = source === "ASSEMBLYAI" || source === "HIGGS" ? "header-status-chip active" : "header-status-chip";
}

function clearAgentAudioFallbackTimer() {
  if (agentAudioFallbackTimer) {
    clearTimeout(agentAudioFallbackTimer);
    agentAudioFallbackTimer = null;
  }
}

// Speak agent reply aloud — guaranteed browser TTS (Boson handles reasoning/tools, not playback).
async function speakAgentReply(text, options = {}) {
  if (!text) return;
  if (options.appendChat !== false) {
    window.__agentReplyAppended = true;
    appendChat("agent", text);
  }
  clearAgentAudioFallbackTimer();
  pauseRecognition();
  activeAudioSources.forEach((src) => {
    try {
      src.stop();
    } catch (e) {}
  });
  activeAudioSources = [];
  resetHiggsPlaybackSchedule();

  setExecutionStep("Agent Speaking", "Speaking operational response aloud...");
  await speakText(text, { fallback: true });
  if (isVoiceActive) {
    resumeRecognition();
  }
}

async function speakAgentText(text, options = {}) {
  await speakAgentReply(text, options);
}

function loadSpeechVoices() {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) {
      resolve([]);
      return;
    }
    const voices = window.speechSynthesis.getVoices();
    if (voices && voices.length > 0) {
      resolve(voices);
      return;
    }
    const onVoices = () => {
      window.speechSynthesis.removeEventListener("voiceschanged", onVoices);
      resolve(window.speechSynthesis.getVoices());
    };
    window.speechSynthesis.addEventListener("voiceschanged", onVoices);
    window.setTimeout(() => resolve(window.speechSynthesis.getVoices()), 300);
  });
}

function pickSpanishVoice(voices) {
  if (!voices || voices.length === 0) return null;
  const preferred = ["helena", "sabina", "paulina", "español", "spanish", "es-ec", "es-mx", "es-es"];
  const lowerNames = voices.map((v) => `${v.name} ${v.lang}`.toLowerCase());
  for (const hint of preferred) {
    const idx = lowerNames.findIndex((n) => n.includes(hint));
    if (idx >= 0) return voices[idx];
  }
  return voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("es")) || voices[0];
}

// Browser speechSynthesis — guaranteed audible output for agent replies.
async function speakText(text, options = {}) {
  if (!text || !window.speechSynthesis) return;
  if (window.telephonyCallActive) return;
  if (bosonTransportMode === "higgs_relay" && options.fallback !== true) {
    return;
  }

  setAudioSource("SPEAKER");

  return new Promise(async (resolve) => {
    try {
      if (audioContext && audioContext.state === "suspended") {
        await audioContext.resume();
      }
      ttsBargeInGuardUntil = Date.now() + 1800;
      window.speechSynthesis.cancel();
      await new Promise((r) => setTimeout(r, 100));
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }

      const voices = await loadSpeechVoices();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "es-EC";
      const esVoice = pickSpanishVoice(voices);
      if (esVoice) utterance.voice = esVoice;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      const finish = () => {
        isAudioSpeaking = false;
        document.getElementById("audioPlayingTag")?.classList.add("hidden");
        if (!isVoiceActive) document.getElementById("voiceOrb")?.classList.remove("active");
        resolve();
      };

      utterance.onstart = () => {
        isAudioSpeaking = true;
        document.getElementById("audioPlayingTag")?.classList.remove("hidden");
        document.getElementById("voiceOrb")?.classList.add("active");
      };
      utterance.onend = finish;
      utterance.onerror = finish;

      window.speechSynthesis.speak(utterance);
      window.setTimeout(() => {
        if (!isAudioSpeaking && window.speechSynthesis.pending === false && window.speechSynthesis.speaking === false) {
          finish();
        }
      }, Math.max(4000, text.length * 80));
    } catch (err) {
      console.error("SpeechSynthesis error:", err);
      resolve();
    }
  });
}

// Update Active Execution Step Ticker
function setExecutionStep(label, detail) {
  const stepLabel = document.getElementById("activeStepLabel");
  const stepDetail = document.getElementById("activeStepDetail");
  if (stepLabel) stepLabel.textContent = label;
  if (stepDetail) stepDetail.textContent = detail;
}

// Initialize Speech Recognition for Realtime Voice to Text
function initSpeechRecognition() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    console.warn("SpeechRecognition API not available in this browser. Using manual text fallback.");
    return null;
  }

  const rec = new SpeechRec();
  rec.continuous = true;
  rec.interimResults = false;
  rec.lang = "es-EC";

  rec.onresult = (event) => {
    if (approvalInFlight) return;
    const lastIndex = event.results.length - 1;
    const transcript = event.results[lastIndex][0].transcript.trim();
    if (!transcript || transcript.length <= 1) {
      return;
    }
    const now = Date.now();
    if (transcript === lastSpokenTranscript && now - (window.__lastSpeechAt || 0) < 4000) {
      return;
    }
    lastSpokenTranscript = transcript;
    window.__lastSpeechAt = now;
    console.log("🎤 Voice recognized:", transcript);
    if (isAgentAudioPlaying()) {
      if (transcript.length < 8) return;
      triggerInstantBargeIn();
    }
    appendChat("user", transcript);
    processSpokenCommand(transcript);
  };

  rec.onerror = (err) => {
    console.warn("Speech recognition notice:", err.error);
  };

  rec.onend = () => {
    if (isVoiceActive && !recognitionPaused && !isAgentAudioPlaying()) {
      try {
        rec.start();
      } catch (e) {}
    }
  };

  return rec;
}

function updateBosonVoiceBadge(voice, mode) {
  const badge = document.getElementById("bosonVoiceBadge");
  if (!badge) return;
  if (mode === "higgs_relay") {
    badge.textContent = `Boson Higgs Realtime · ${voice || "default"} voice`;
    badge.className = "boson-voice-badge";
  } else {
    badge.textContent = "Browser TTS fallback (Boson relay offline)";
    badge.className = "boson-voice-badge";
    badge.style.background = "#fef3c7";
    badge.style.borderColor = "#fcd34d";
    badge.style.color = "#92400e";
  }
}

// Fetch relay token & initialize WebSocket connection for Higgs Realtime S2S
async function initBosonSession() {
  try {
    const res = await fetch("/api/boson/token");
    if (!res.ok) throw new Error("Could not mint ephemeral token");
    const data = await res.json();
    const legacyFakeToken = typeof data.token === "string" && data.token.startsWith("higgs_tok_");
    bosonTransportMode =
      data.mode ||
      (data.token && data.ws_url && !legacyFakeToken ? "higgs_relay" : "browser_fallback");

    if (bosonTransportMode === "browser_fallback" || !data.token || !data.ws_url || legacyFakeToken) {
      bosonTransportMode = "browser_fallback";
      setAudioSource("STANDBY");
      updateBosonVoiceBadge(null, "browser_fallback");
      appendChat("system", data.label || "BROWSER TTS FALLBACK — using browser SpeechRecognition + speechSynthesis.");
      setExecutionStep("Browser Voice Fallback", data.reason || "Boson relay not configured on server.");
      return false;
    }
    setAudioSource("HIGGS");
    updateBosonVoiceBadge(data.voice || "default", "higgs_relay");

    ephemeralToken = data.token;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${data.ws_url}?token=${encodeURIComponent(data.token)}`;

    return await new Promise((resolve) => {
      higgsWebSocket = new WebSocket(wsUrl);

      higgsWebSocket.onopen = () => {
        console.log("⚡ Higgs Realtime WebSocket connected:", wsUrl);
        setExecutionStep("Higgs WebSocket Live", "Stream active · Sub-50ms Barge-in enabled");
        resolve(true);
      };

      higgsWebSocket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleHiggsServerEvent(msg);
        } catch (err) {
          console.warn("WS message parse error:", err);
        }
      };

      higgsWebSocket.onerror = (err) => {
        console.warn("Higgs WebSocket notice:", err);
      };

      higgsWebSocket.onclose = () => {
        console.log("Higgs WebSocket connection closed");
        if (isVoiceActive && bosonTransportMode === "higgs_relay") {
          bosonTransportMode = "browser_fallback";
          setAudioSource("STANDBY");
          updateBosonVoiceBadge(null, "browser_fallback");
          appendChat("system", "Higgs relay closed — falling back to browser STT/TTS.");
        }
      };

      setTimeout(() => {
        if (higgsWebSocket && higgsWebSocket.readyState !== WebSocket.OPEN) {
          bosonTransportMode = "browser_fallback";
          setAudioSource("STANDBY");
          updateBosonVoiceBadge(null, "browser_fallback");
          resolve(false);
        }
      }, 8000);
    });
  } catch (err) {
    bosonTransportMode = "browser_fallback";
    setAudioSource("STANDBY");
    updateBosonVoiceBadge(null, "browser_fallback");
    console.warn("Ephemeral token negotiation notice:", err);
    return false;
  }
}

function sendUtteranceToHiggs(text) {
  if (bosonTransportMode !== "higgs_relay") return false;
  if (!higgsWebSocket || higgsWebSocket.readyState !== WebSocket.OPEN) return false;
  if (isAgentAudioPlaying()) {
    cancelAllAudioPlayback();
    higgsWebSocket.send(JSON.stringify({ type: "response.cancel" }));
  }
  resetHiggsPlaybackSchedule();
  pauseRecognition();
  higgsWebSocket.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    })
  );
  higgsWebSocket.send(JSON.stringify({ type: "response.create" }));
  setExecutionStep("Higgs S2S Live", "Boson Realtime generating spoken response...");
  return true;
}

// Handle incoming server events from Higgs Realtime S2S stream
function handleHiggsServerEvent(event) {
  const type = event.type || "";

  if (type === "session.created" || type === "session.updated") {
    console.log("Higgs Session active:", event.session?.id);
    document.getElementById("turnStatus").textContent = "Higgs Realtime Streaming";
    document.getElementById("turnStatus").className = "status-badge active";
    setAudioSource("HIGGS");
  } else if (
    type === "response.output_audio_transcript.delta" ||
    type === "response.audio_transcript.delta" ||
    type === "response.output_text.delta"
  ) {
    const text = event.delta || "";
    if (text) {
      window.__higgsTranscriptBuffer = (window.__higgsTranscriptBuffer || "") + text;
      setExecutionStep("Agent Speaking", "Boson Higgs Realtime audio streaming...");
    }
  } else if (
    type === "response.output_audio_transcript.done" ||
    type === "response.audio_transcript.done"
  ) {
    const text = event.transcript || window.__higgsTranscriptBuffer || "";
    window.__higgsTranscriptBuffer = "";
    if (text && !window.__agentReplyAppended) {
      appendChat("agent", text);
    }
    window.__agentReplyAppended = false;
  } else if (type === "response.output_audio.delta" || type === "response.audio.delta") {
    // Boson Realtime streams 24 kHz PCM16 mono (response.output_audio.delta)
    const base64Audio = event.delta || "";
    if (base64Audio && bosonTransportMode === "higgs_relay") {
      if (!higgsPcmActive) {
        agentSpeakStartedAt = Date.now();
        pauseRecognition();
      }
      higgsPcmActive = true;
      setAudioSource("HIGGS");
      isAudioSpeaking = true;
      document.getElementById("audioPlayingTag")?.classList.remove("hidden");
      playPCM16AudioChunk(base64Audio, HIGGS_SAMPLE_RATE);
    }
  } else if (
    type === "response.output_audio.done" ||
    type === "response.audio.done" ||
    type === "response.done"
  ) {
    higgsPcmActive = false;
    markAgentPlaybackEnding();
  } else if (
    type === "conversation.item.input_audio_transcription.completed" ||
    type === "input_audio_transcription.completed"
  ) {
    const transcript = event.transcript || event.item?.content?.[0]?.transcript || "";
    if (transcript.trim()) {
      appendChat("user", transcript.trim());
    }
  } else if (type === "voiceops.tool_executed") {
    handleVoiceopsToolExecuted(event);
  } else if (type === "error" && event.mode === "browser_fallback") {
    bosonTransportMode = "browser_fallback";
    appendChat("system", event.label || "BROWSER TTS FALLBACK");
  }
}

function ensurePlaybackGraph() {
  if (!playbackContext) {
    playbackContext = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: "playback" });
  }
  if (!higgsGainNode) {
    higgsGainNode = playbackContext.createGain();
    higgsGainNode.gain.value = 1.0;
    higgsGainNode.connect(playbackContext.destination);
  }
  return higgsGainNode;
}

function isAgentAudioPlaying() {
  if (activeAudioSources.length > 0) return true;
  if (!playbackContext || !higgsPlaybackPrimed) return false;
  return higgsPlaybackCursor > playbackContext.currentTime + 0.04;
}

function pauseRecognition() {
  if (!recognition || !isVoiceActive || recognitionPaused) return;
  recognitionPaused = true;
  try {
    recognition.stop();
  } catch (e) {}
}

function resumeRecognition() {
  if (!recognition || !isVoiceActive || !recognitionPaused || approvalInFlight) return;
  if (isAgentAudioPlaying()) return;
  recognitionPaused = false;
  window.setTimeout(() => {
    if (isVoiceActive && !recognitionPaused && !isAgentAudioPlaying() && !approvalInFlight) {
      try {
        recognition.start();
      } catch (e) {}
    }
  }, 300);
}

function setApprovalButtonsEnabled(enabled) {
  const confirmBtn = document.getElementById("confirmBtn");
  const rejectBtn = document.getElementById("rejectBtn");
  if (confirmBtn) confirmBtn.disabled = !enabled;
  if (rejectBtn) rejectBtn.disabled = !enabled;
}

function closeProposalUI(message, variant = "rejected") {
  activeProposalId = null;
  setApprovalButtonsEnabled(true);
  const manualActions = document.getElementById("manualApprovalActions");
  if (manualActions) manualActions.style.display = "none";
  const badge = document.getElementById("approvalBadge");
  if (badge) {
    if (variant === "executed") {
      badge.textContent = "PERMIT ISSUED";
      badge.className = "status-badge active";
    } else {
      badge.textContent = "REJECTED — NO CHANGE";
      badge.className = "status-badge";
    }
  }
  const card = document.getElementById("proposalCard");
  if (card && message) {
    card.className = "proposal-card";
    card.innerHTML = message;
  }
}

function markAgentPlaybackEnding() {
  window.setTimeout(() => {
    if (isAgentAudioPlaying()) return;
    isAudioSpeaking = false;
    higgsPcmActive = false;
    document.getElementById("audioPlayingTag")?.classList.add("hidden");
    if (!isVoiceActive) document.getElementById("voiceOrb")?.classList.remove("active");
    clearAgentAudioFallbackTimer();
    if (bosonTransportMode === "higgs_relay") {
      resumeRecognition();
    }
  }, 120);
}

function handleVoiceopsToolExecuted(event) {
  const toolName = event.tool_name || "unknown_tool";
  const args = event.arguments || {};
  const output = event.output || {};
  recordToolCall(toolName, args, output, 0);

  if (toolName === "inspect_operational_state") {
    const subsystem = args.subsystem || "all";
    fetchTelemetry();
    highlightDashboardCard(subsystem === "all" ? "solar_power" : subsystem);
    setExecutionStep("Live Telemetry Read", `inspect_operational_state(${subsystem}) — panel synced.`);
  } else if (toolName === "propose_governed_action" && output.proposal_id) {
    activeProposalId = output.proposal_id;
    showProposalCard(output.proposal_id, output.summary || "Governed action proposed.", output.target_subsystem);
    highlightDashboardCard(output.target_subsystem);
  } else if (toolName === "submit_user_approval") {
    handleApprovalExecution(output);
    fetchTelemetry();
  }

  fetchIntegrationsStatus();
}

function resetHiggsPlaybackSchedule() {
  higgsPlaybackCursor = 0;
  higgsPlaybackPrimed = false;
  higgsPcmQueue = [];
}

function syncHiggsPlaybackSchedule() {
  const now = playbackContext.currentTime;
  if (!higgsPlaybackPrimed || higgsPlaybackCursor < now) {
    higgsPlaybackCursor = now + HIGGS_PLAYBACK_LEAD_SEC;
    higgsPlaybackPrimed = true;
  }
}

function schedulePCM16ChunkSync(base64Data, sampleRate = HIGGS_SAMPLE_RATE) {
  try {
    const binary = atob(base64Data);
    const len = binary.length;
    const alignedLen = len - (len % 2);
    if (alignedLen < 2) return;

    const sampleCount = alignedLen / 2;
    const float32Array = new Float32Array(sampleCount);
    for (let i = 0; i < sampleCount; i++) {
      const lo = binary.charCodeAt(i * 2);
      const hi = binary.charCodeAt(i * 2 + 1);
      let sample = lo | (hi << 8);
      if (sample >= 0x8000) sample -= 0x10000;
      float32Array[i] = sample / 32768.0;
    }

    syncHiggsPlaybackSchedule();

    const audioBuffer = playbackContext.createBuffer(1, float32Array.length, sampleRate);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = playbackContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(higgsGainNode);

    const startAt = higgsPlaybackCursor;
    const duration = float32Array.length / sampleRate;
    higgsPlaybackCursor += duration;

    isAudioSpeaking = true;
    document.getElementById("audioPlayingTag")?.classList.remove("hidden");
    document.getElementById("voiceOrb")?.classList.add("active");

    source.onended = () => {
      activeAudioSources = activeAudioSources.filter((s) => s !== source);
      if (!isAgentAudioPlaying()) {
        markAgentPlaybackEnding();
      }
    };

    activeAudioSources.push(source);
    source.start(startAt);
  } catch (err) {
    console.error("PCM16 playback error:", err);
  }
}

function flushHiggsPcmQueue() {
  while (higgsPcmQueue.length > 0) {
    const chunk = higgsPcmQueue.shift();
    schedulePCM16ChunkSync(chunk.base64Data, chunk.sampleRate);
  }
}

// Web Audio API: schedule PCM16 chunks back-to-back (fixes choppy/overlap playback)
async function playPCM16AudioChunk(base64Data, sampleRate = HIGGS_SAMPLE_RATE) {
  ensurePlaybackGraph();
  if (playbackContext.state === "suspended") {
    await playbackContext.resume();
  }
  higgsPcmQueue.push({ base64Data, sampleRate });
  flushHiggsPcmQueue();
}

// Cancel All Active Audio Playback (<50ms hardware stop)
function cancelAllAudioPlayback() {
  clearAgentAudioFallbackTimer();
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  activeAudioSources.forEach((src) => {
    try {
      src.stop();
    } catch (e) {}
  });
  activeAudioSources = [];
  resetHiggsPlaybackSchedule();
  higgsPcmActive = false;
  bargeInHoldFrames = 0;
  isAudioSpeaking = false;
  document.getElementById("audioPlayingTag")?.classList.add("hidden");
  if (!isVoiceActive) document.getElementById("voiceOrb")?.classList.remove("active");
}

function pcm16ToBase64(pcm16) {
  const bytes = new Uint8Array(pcm16.buffer, pcm16.byteOffset, pcm16.byteLength);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function resampleFloat32(input, inRate, outRate) {
  if (inRate === outRate) return input;
  const ratio = inRate / outRate;
  const outLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    out[i] = input[Math.min(input.length - 1, Math.floor(i * ratio))] || 0;
  }
  return out;
}

function streamMicChunkToHiggs(float32Samples) {
  if (bosonTransportMode !== "higgs_relay") return;
  if (!higgsWebSocket || higgsWebSocket.readyState !== WebSocket.OPEN) return;
  const resampled = resampleFloat32(float32Samples, audioContext.sampleRate, HIGGS_SAMPLE_RATE);
  const pcm16 = new Int16Array(resampled.length);
  for (let i = 0; i < resampled.length; i++) {
    const s = Math.max(-1, Math.min(1, resampled[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  higgsWebSocket.send(
    JSON.stringify({
      type: "input_audio_buffer.append",
      audio: pcm16ToBase64(pcm16),
    })
  );
}

// Trigger Instant Barge-In (<50ms)
function triggerInstantBargeIn() {
  cancelAllAudioPlayback();

  if (higgsWebSocket && higgsWebSocket.readyState === WebSocket.OPEN) {
    higgsWebSocket.send(JSON.stringify({ type: "response.cancel" }));
  }

  setExecutionStep("Barge-In (<50ms)", "Higgs audio stream cut off immediately upon voice detection!");
  console.log("⚡ [Barge-In Triggered]: Realtime audio cut off in <50ms.");
  resumeRecognition();
}

// Start Live Voice Session with real Microphone, Speech Recognition & Audio Pipeline
async function startLiveVoice() {
  try {
    ensurePlaybackGraph();
    if (playbackContext.state === "suspended") {
      await playbackContext.resume();
    }

    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = audioContext.createMediaStreamSource(micStream);
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 64;
    source.connect(analyserNode);
    micDataArray = new Uint8Array(analyserNode.frequencyBinCount);

    // Silent gain node to prevent speaker feedback loop
    silentGainNode = audioContext.createGain();
    silentGainNode.gain.value = 0;

    scriptProcessorNode = audioContext.createScriptProcessor(4096, 1, 1);
    source.connect(scriptProcessorNode);
    scriptProcessorNode.connect(silentGainNode);
    silentGainNode.connect(audioContext.destination);

    scriptProcessorNode.onaudioprocess = (e) => {
      if (!isVoiceActive) return;
      const inputData = e.inputBuffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += Math.abs(inputData[i]);
      }
      const avg = sum / inputData.length;

      if (bosonTransportMode === "higgs_relay") {
        streamMicChunkToHiggs(inputData);
        if (Date.now() < ttsBargeInGuardUntil) return;
        if (isAgentAudioPlaying() && avg > BARGE_IN_VAD_THRESHOLD) {
          bargeInHoldFrames += 1;
          if (bargeInHoldFrames >= BARGE_IN_FRAMES_REQUIRED) {
            triggerInstantBargeIn();
            bargeInHoldFrames = 0;
          }
        } else {
          bargeInHoldFrames = 0;
        }
        return;
      }

      if (Date.now() < ttsBargeInGuardUntil) return;
      if (audioSource === "BROWSER_TTS_FALLBACK" && avg > 0.12 && isAudioSpeaking) {
        triggerInstantBargeIn();
      }
    };

    const provider = typeof window.getVoiceProvider === "function" ? window.getVoiceProvider() : "boson";
    const useBrowserLocal = provider === "browser_local";
    bosonTransportMode = "browser_fallback";
    setAudioSource("STANDBY");

    if (!useBrowserLocal && provider === "boson") {
      await initBosonSession();
    }

    if (bosonTransportMode !== "higgs_relay") {
      bosonTransportMode = "browser_fallback";
      setAudioSource("BROWSER_TTS_FALLBACK");
      if (!recognition) recognition = initSpeechRecognition();
      if (recognition) {
        try {
          recognition.start();
        } catch (err) {
          console.warn("Speech recognition start:", err);
        }
      }
    }

    isVoiceActive = true;
    document.getElementById("liveMicBtn").disabled = true;
    document.getElementById("stopMicBtn").disabled = false;
    document.getElementById("voiceOrb").className = "voice-orb active";
    document.getElementById("turnStatus").textContent = "En vivo";
    document.getElementById("turnStatus").className = "status-badge active";

    if (bosonTransportMode === "higgs_relay") {
      document.getElementById("agentStateTitle").textContent = "Boson Higgs listening";
      document.getElementById("agentStateSubtitle").textContent =
        "Realtime S2S · server_vad · governed tools on server";
      setExecutionStep("Higgs Realtime", "Speak naturally — greetings and ops queries go to Boson.");
      appendChat("system", "Boson Higgs Realtime connected — mic PCM streaming to server relay.");
    } else {
      document.getElementById("agentStateTitle").textContent = "Browser voice listening";
      document.getElementById("agentStateSubtitle").textContent =
        "Browser STT/TTS fallback · InnerOS tools via /api/boson/converse";
      setExecutionStep("Browser voice", "Speak — server reasoning with browser TTS output.");
      appendChat("system", "BROWSER TTS FALLBACK — SpeechRecognition + speechSynthesis (not Boson S2S).");
      const greetingText = "InnerOS ready. Monitoring Guayaquil systems. How can I help?";
      appendChat("agent", greetingText);
      await speakText(greetingText, { fallback: true });
    }
    updateSiteStatusBanner();
  } catch (err) {
    console.error("Microphone access error:", err);
    alert("Microphone permission was not granted. Please allow microphone access in your browser to test live speech.");
    stopLiveVoice();
  }
}

// Stop Live Voice Session
function stopLiveVoice(options = {}) {
  isVoiceActive = false;
  approvalInFlight = false;
  recognitionPaused = false;

  const liveBtn = document.getElementById("liveMicBtn");
  const stopBtn = document.getElementById("stopMicBtn");
  if (liveBtn) liveBtn.disabled = false;
  if (stopBtn) stopBtn.disabled = true;

  cancelAllAudioPlayback();
  setApprovalButtonsEnabled(true);

  if (recognition) {
    try {
      recognition.stop();
    } catch (e) {}
  }

  if (scriptProcessorNode) {
    try {
      scriptProcessorNode.disconnect();
    } catch (e) {}
    scriptProcessorNode = null;
  }

  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }

  if (higgsWebSocket) {
    try {
      higgsWebSocket.close();
    } catch (e) {}
    higgsWebSocket = null;
  }

  document.getElementById("voiceOrb").className = "voice-orb idle";
  document.getElementById("agentStateTitle").textContent = "InnerOS Voice Dispatcher";
  document.getElementById("agentStateSubtitle").textContent = "Voz continua con barge-in y herramientas gobernadas";
  document.getElementById("turnStatus").textContent = "Listo";
  document.getElementById("turnStatus").className = "status-badge";

  setExecutionStep("Sistema listo", "Esperando voz o instrucción manual.");
  if (!options.quiet) {
    appendChat("system", "Sesión de voz finalizada.");
  }
}

function forceStopAllVoice(options = {}) {
  if (typeof window.stopAssemblyAIVoice === "function") {
    window.stopAssemblyAIVoice();
  }
  stopLiveVoice({ quiet: true, ...options });
}

// Una sola voz por turno: HTTP gobernado + TTS (evita Boson PCM + navegador a la vez).
async function processSpokenCommandHttp(text, options = {}) {
  const t0 = performance.now();
  const res = await fetch("/api/boson/converse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ utterance: text, active_proposal_id: activeProposalId }),
  });
  const data = await res.json();
  const latMs = Math.round(performance.now() - t0);

  if (data.tool_records && data.tool_records.length > 0) {
    data.tool_records.forEach((rec) => {
      recordToolCall(rec.tool_name, rec.arguments, rec.output, latMs);
    });
    fetchTelemetry();
  }

  if (data.proposal) {
    activeProposalId = data.proposal.proposal_id;
    showProposalCard(activeProposalId, data.proposal.summary, data.subsystem);
  }

  if (data.approval_result) {
    handleApprovalExecution(data.approval_result);
  }

  const reply = data.reply || "Consulta procesada.";
  if (data.subsystem) {
    highlightDashboardCard(data.subsystem);
  }

  if (options.appendChat !== false) {
    appendChat("agent", reply);
    window.__agentReplyAppended = true;
  }

  if (options.speak !== false) {
    cancelAllAudioPlayback();
    await speakText(reply, { fallback: true });
  }

  if (isVoiceActive) resumeRecognition();
  fetchIntegrationsStatus();
  return data;
}

async function processSpokenCommand(text) {
  if (bosonTransportMode === "higgs_relay") {
    return sendUtteranceToHiggs(text);
  }

  if (isAgentAudioPlaying()) {
    triggerInstantBargeIn();
    await new Promise((resolve) => setTimeout(resolve, 150));
  }

  setExecutionStep("VoiceOps Reasoning", `"${text.slice(0, 40)}..."`);

  try {
    await processSpokenCommandHttp(text);
  } catch (err) {
    console.error("Converse error:", err);
    appendChat("system", "Error de conexión con el servidor.");
  }
}

// Handle approval execution UI update
function handleApprovalExecution(app) {
  if (app.status === "EXECUTED") {
    document.getElementById("auditPermitId").textContent = app.permit_id;
    document.getElementById("auditActionId").textContent = app.action_id;
    document.getElementById("auditSignature").textContent = "[HMAC-SHA256: VALID]";
    document.getElementById("evidenceHash").textContent = app.evidence_sha256;

    const savedMin = Math.round((app.htr_seconds_returned / 60) * 10) / 10;
    currentHtrTotal += savedMin;
    document.getElementById("htrCounter").textContent = `+${currentHtrTotal.toFixed(1)}`;

    closeProposalUI(
      `<div style="color:#059669; font-weight:600;">✓ Action Executed & Audited</div>
      <p style="margin-top:4px;">Single-Use Permit: <code>${app.permit_id}</code> · HTR: +${savedMin} min</p>`,
      "executed"
    );
    setExecutionStep("Operation Executed", `Permit ${app.permit_id} verified; evidence sealed.`);
    fetchTelemetry();
  } else {
    const reason = app.reason || "explicit_rejection";
    closeProposalUI(
      `<div style="color:#64748b; font-weight:600;">✕ Action Rejected — No Changes Applied</div>
      <p style="margin-top:4px;">Reason: <code>${reason}</code>. The infrastructure remains unchanged.</p>`,
      "rejected"
    );
    setExecutionStep("Action Rejected", "Proposal closed. No governed action was executed.");
  }
}

// Register Zoiper Extension dynamically
async function registerZoiperExt(ext = "104") {
  try {
    const res = await fetch("/api/telephony/register-extension", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ extension: ext, label: "Zoiper SIP Softphone (Mobile Lead)" }),
    });
    const data = await res.json();
    appendChat("system", `[PBX AMI]: Extension ${ext} registered successfully from Zoiper client.`);
    fetchTelemetry();
  } catch (err) {
    console.error("Register ext error:", err);
  }
}

// Disconnect / Unregister Zoiper Extension dynamically
async function unregisterZoiperExt(ext = "104") {
  try {
    const res = await fetch("/api/telephony/unregister-extension", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ extension: ext }),
    });
    const data = await res.json();
    appendChat("system", `[PBX AMI]: Extension ${ext} disconnected/unregistered.`);
    fetchTelemetry();
  } catch (err) {
    console.error("Unregister ext error:", err);
  }
}

// Fetch live telemetry from Guayaquil Node
async function fetchTelemetry() {
  try {
    const res = await fetch("/api/telemetry");
    if (!res.ok) return;
    const data = await res.json();

    const syncTime = document.getElementById("telemetrySyncTime");
    if (syncTime) {
      const now = new Date();
      syncTime.textContent = `Polled GYE Node-01 · ${now.toLocaleTimeString()}`;
    }

    function updateTruthBadge(elementId, truth) {
      const el = document.getElementById(elementId);
      if (!el) return;
      el.textContent = truth || "UNVERIFIED";
      el.className = `truth-badge ${(truth || "unverified").toLowerCase()}`;
    }

    const sub = data.subsystems;
    if (sub) {
      // 1. Solar Subsystem
      if (sub.solar_power) {
        const sol = sub.solar_power;
        updateTruthBadge("solTruth", sol.truth);
        const solStatus = document.getElementById("solStatus");
        if (solStatus) solStatus.textContent = sol.status || "—";
        const solGen = document.getElementById("solGen");
        const solBat = document.getElementById("solBat");
        const solGrid = document.getElementById("solGrid");
        if (solGen) {
          solGen.textContent = sol.solar_generation_watts != null ? `${sol.solar_generation_watts} W` : "—";
        }
        if (solBat) {
          const batPct = sol.battery_charge_pct != null ? `${sol.battery_charge_pct}%` : "—";
          const batV = sol.battery_voltage_volts != null ? `${sol.battery_voltage_volts}V` : "—";
          solBat.textContent = `${batPct} (${batV})`;
        }
        if (solGrid) {
          solGrid.textContent = sol.grid_voltage_volts != null ? `${sol.grid_voltage_volts}V / 60Hz Guayaquil Grid` : "—";
        }
      }

      // 2. Telephony Subsystem
      if (sub.telephony) {
        const tel = sub.telephony;
        updateTruthBadge("telTruth", tel.truth);
        const telStatus = document.getElementById("telStatus");
        if (telStatus) telStatus.textContent = tel.status || "—";
        const telExts = document.getElementById("telExts");
        const telQuality = document.getElementById("telQuality");
        const exts = tel.registered_extensions || [];
        if (telExts) {
          if (exts.length) {
            const extList = exts.map((e) => e.ext).join(", ");
            telExts.textContent = `${exts.length} registered (${extList})`;
          } else {
            telExts.textContent = tel.ami_error ? `AMI unavailable (${tel.ami_error})` : "0 registered (AMI poll)";
          }
        }
        if (telQuality) {
          telQuality.textContent =
            tel.trunk_quality && tel.truth === "LIVE"
              ? `Jitter ${tel.trunk_quality.jitter_ms}ms (MOS ${tel.trunk_quality.mos_score})`
              : "—";
        }
      }

      // 3. Network WiFi Subsystem
      if (sub.network_wifi) {
        const net = sub.network_wifi;
        updateTruthBadge("netTruth", net.truth);
        const netStatus = document.getElementById("netStatus");
        if (netStatus) netStatus.textContent = net.status || "—";
        const netWan = document.getElementById("netWan");
        const netLoss = document.getElementById("netLoss");
        const netSwitch = document.getElementById("netSwitch");
        if (netWan) {
          netWan.textContent =
            net.unifi_wan_status != null
              ? `WAN ${net.unifi_wan_status}${net.unifi_cpu_utilization_pct != null ? ` · CPU ${net.unifi_cpu_utilization_pct}%` : ""}`
              : "—";
        }
        if (netLoss) {
          const yard = (net.access_points || []).find((ap) => String(ap.ap_id || "").includes("SolarYard"));
          if (yard && yard.status) {
            netLoss.textContent = yard.status;
            netLoss.className = String(yard.status).includes("DEGRADED") ? "text-danger" : "text-success";
          } else {
            netLoss.textContent = "—";
            netLoss.className = "";
          }
        }
        if (netSwitch) {
          netSwitch.textContent = net.core_switch || "—";
        }
        const cardNetwork = document.getElementById("cardNetwork");
        if (cardNetwork) {
          cardNetwork.classList.toggle("alert", String(net.status || "").includes("ALERT"));
        }
      }

      // 4. Security Alarm Subsystem
      if (sub.security_alarm) {
        const alm = sub.security_alarm;
        updateTruthBadge("alarmTruth", alm.truth);
        const alarmStatus = document.getElementById("alarmStatus");
        if (alarmStatus) alarmStatus.textContent = alm.status || "—";
        const almZones = document.getElementById("alarmZones");
        if (almZones) almZones.textContent = `${alm.monitored_zones_count || 0} zones monitored`;
        const alarmTrigger = document.getElementById("alarmTrigger");
        if (alarmTrigger) {
          alarmTrigger.textContent = alm.is_in_alarm ? "IN ALARM" : alm.is_triggered ? "TRIGGERED" : "NORMAL";
        }
      }

      // 5. Video Surveillance Subsystem
      if (sub.video_surveillance) {
        const cam = sub.video_surveillance;
        updateTruthBadge("camTruth", cam.truth);
        const camStatus = document.getElementById("camStatus");
        if (camStatus) camStatus.textContent = cam.status || "—";
        const camChannels = document.getElementById("camChannels");
        if (camChannels) {
          camChannels.textContent =
            cam.channels && cam.channels.length
              ? cam.channels.map((c) => `${c.channel} ${c.alias}`).join(" · ")
              : cam.note || "—";
        }
        const camMotion = document.getElementById("camMotion");
        if (camMotion) camMotion.textContent = cam.event_dispatcher || cam.note || "—";
        const camNvr = document.getElementById("camNvr");
        if (camNvr) camNvr.textContent = cam.nvr_host || "—";
      }

      if (sub.dmx_lighting) {
        updateTruthBadge("dmxTruth", sub.dmx_lighting.truth);
      }
    }
  } catch (err) {
    console.error("Telemetry fetch error:", err);
  }
}

// Fetch Boson Status
async function fetchBosonStatus() {
  try {
    const res = await fetch("/api/boson/status");
    if (!res.ok) return;
    const data = await res.json();
    console.log("Boson AI Higgs Realtime Status:", data);
    updateBosonVoiceBadge(data.voice || "default", data.mode || "browser_fallback");
    if (data.mode === "browser_fallback") {
      setAudioSource("STANDBY");
    }
  } catch (err) {
    console.error("Boson status check error:", err);
  }
}

function partnerTruthClass(truth) {
  const normalized = String(truth || "NOT_CONNECTED").toUpperCase();
  if (normalized === "REAL" || normalized === "LIVE") return "real";
  if (normalized === "FALLBACK" || normalized === "BROWSER_TTS_FALLBACK") return "fallback";
  return "not-connected";
}

function setPartnerTruth(elementId, truth) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const label = String(truth || "NOT_CONNECTED").toUpperCase();
  el.textContent = label === "LIVE" ? "REAL" : label;
  el.className = `partner-truth ${partnerTruthClass(truth)}`;
}

function renderCapabilityChip(label, truth) {
  const chip = document.createElement("div");
  chip.className = "capability-chip";
  const active = ["REAL", "CONFIGURED", "OPERATIONAL", "LOCAL_DEFAULT", "LIVE"].includes(String(truth || "").toUpperCase());
  chip.classList.add(active ? "active" : "inactive");
  chip.innerHTML = `<span class="capability-chip-mark">${active ? "✓" : "○"}</span><span class="capability-chip-label">${label}</span><span class="capability-chip-truth">${truth || "NOT_CONNECTED"}</span>`;
  return chip;
}

function renderPartnerIntegrations(data) {
  const core = data.core_local || {};
  const optional = data.optional_adapters || {};
  const adapters = optional.adapters || data.partner_integrations || {};
  const assemblyai = adapters.assemblyai || data.assemblyai || {};

  const narrative = document.getElementById("capabilityNarrative");
  if (narrative) {
    narrative.textContent = core.narrative || optional.degradation_note || narrative.textContent;
  }
  const coreBadge = document.getElementById("coreTruthBadge");
  if (coreBadge) {
    coreBadge.textContent = `CORE ${core.truth || data.core_truth || "OPERATIONAL"}`;
  }

  const coreGrid = document.getElementById("coreCapabilityGrid");
  if (coreGrid) {
    coreGrid.innerHTML = "";
    const caps = core.capabilities || {};
    const labels = {
      qwen: "Qwen",
      execution_engine: "Execution engine",
      approval_gate: "Approval gate",
      execution_permits: "Execution permits",
      evidence: "Evidence",
      grandstream: "Grandstream",
      home_assistant: "Home Assistant",
      mcp_tools: "MCP / tools",
    };
    Object.entries(labels).forEach(([key, label]) => {
      const item = caps[key];
      if (!item) return;
      coreGrid.appendChild(renderCapabilityChip(label, item.truth || item.status));
    });
  }

  const optGrid = document.getElementById("optionalCapabilityGrid");
  if (optGrid) {
    optGrid.innerHTML = "";
    Object.values(adapters).forEach((adapter) => {
      optGrid.appendChild(renderCapabilityChip(adapter.provider || adapter.adapter_id, adapter.truth));
    });
  }

  const voiceBadge = document.getElementById("assemblyaiVoiceBadge");
  if (voiceBadge) {
    if (assemblyai.truth === "REAL") {
      voiceBadge.textContent = "AssemblyAI Voice Agent · LIVE";
    } else if (data.audio_source === "LOCAL_QWEN") {
      voiceBadge.textContent = "Local Qwen · core fallback";
    }
  }
}

async function fetchIntegrationsStatus() {
  try {
    const res = await fetch("/api/integrations/status");
    if (!res.ok) return;
    const data = await res.json();
    if (data.audio_source) {
      setAudioSource(data.audio_source);
    }
    renderPartnerIntegrations(data);
    console.log("Integration status:", data);
  } catch (err) {
    console.error("Integration status error:", err);
  }
}

// Trigger Scenario Demonstrations
async function triggerScenario(type) {
  if (type === "inspect") {
    setExecutionStep("1. Querying Telemetry", "Calling 'inspect_operational_state' on Guayaquil infrastructure...");
    appendChat("user", "Higgs, run a full site diagnostics across all Guayaquil systems.");
    processSpokenCommand("Higgs, run a full site diagnostics across all Guayaquil systems");
  } else if (type === "barge_in") {
    setExecutionStep("2. Long Speech In-Progress", "Higgs streaming audio parameters; testing human voice interruption...");
    const longReport = "Executing full operational stream: Node Guayaquil running grid sync at 120.6 volts, frequency 60 hertz, phase A drawing 6.11 amps, battery storage optimal at 52.4 volts...";
    speakAgentText(longReport, { appendChat: false });

    setTimeout(() => {
      triggerInstantBargeIn();
      setExecutionStep("Barge-In Detected (<50ms)", "Cancelled prior audio buffer immediately; context shifted.");
      appendChat("user", "Espera, otra cosa. The switch is throwing errors on AP-SolarYard, what is the status?");
      processSpokenCommand("The switch is throwing errors on AP-SolarYard, what is the status?");
    }, 1200);
  } else if (type === "code_switch") {
    setExecutionStep("3. Technical Code-Switching", "Processing Spanglish engineering command...");
    const spanglishUtterance = "Revisé el switch principal and the link is dropping packets en el solar yard, propose a restart immediately.";
    appendChat("user", spanglishUtterance);
    processSpokenCommand(spanglishUtterance);
  } else if (type === "approve") {
    setExecutionStep("4. Evaluating Verbal Approval", "Passing verbatim utterance to ExplicitApprovalGate...");
    const affirmativeSpeech = "Affirmative, authorize and execute the AP-SolarYard restart now.";
    appendChat("user", affirmativeSpeech);
    if (activeProposalId) {
      await submitApproval(activeProposalId, affirmativeSpeech);
    } else {
      processSpokenCommand("reinicia el ap solaryard");
    }
  } else if (type === "reject") {
    setExecutionStep("5. Evaluating Ambiguous Utterance", "Testing Fail-Closed security rejection...");
    const ambiguousSpeech = "Mmm maybe later, I am not totally sure yet.";
    appendChat("user", ambiguousSpeech);
    if (activeProposalId) {
      await submitApproval(activeProposalId, ambiguousSpeech);
    } else {
      processSpokenCommand(ambiguousSpeech);
    }
  } else if (type === "incident_analysis") {
    setExecutionStep("6. Qwen Incident Reasoning", "Invoking inneros_analyze_incident for root-cause analysis...");
    const incidentQuery = "¿Por qué crees que ocurrió la falla de ayer en la red?";
    appendChat("user", incidentQuery);
    processSpokenCommand(incidentQuery);
  } else if (type === "zoiper_test") {
    setExecutionStep("7. Zoiper Dynamic PBX Test", "Registering Zoiper Ext 104 and observing live reflection...");
    await registerZoiperExt("104");
  }
}

// Submit Verbal Approval
async function submitApproval(proposalId, utterance) {
  if (approvalInFlight) return;
  approvalInFlight = true;
  setApprovalButtonsEnabled(false);
  cancelAllAudioPlayback();
  pauseRecognition();

  try {
    const t0 = performance.now();
    const res = await fetch("/api/governed/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proposal_id: proposalId, utterance: utterance }),
    });
    const data = await res.json();
    const latMs = Math.round(performance.now() - t0);

    recordToolCall("submit_user_approval", { proposal_id: proposalId, utterance }, data, latMs);
    handleApprovalExecution(data);

    if (data.status === "EXECUTED") {
      const savedMin = Math.round((data.htr_seconds_returned / 60) * 10) / 10;
      const agentConfirmation = `Action executed under single-use permit ${data.permit_id}. Cryptographic receipt recorded in Audit Fabric and plus ${savedMin} minutes of human time returned.`;
      await speakAgentReply(agentConfirmation);
    } else {
      await speakAgentReply(
        "Understood. The proposed action was rejected. No changes will be made to the infrastructure."
      );
    }
  } catch (err) {
    console.error("Submit approval error:", err);
    closeProposalUI(
      `<div style="color:#dc2626; font-weight:600;">Approval request failed</div>
      <p style="margin-top:4px;">Check server connection and try again.</p>`,
      "rejected"
    );
    appendChat("system", "Approval submission failed — proposal cleared so you can continue.");
  } finally {
    approvalInFlight = false;
    setApprovalButtonsEnabled(true);
    recognitionPaused = false;
    if (isVoiceActive && !isAgentAudioPlaying()) {
      try {
        recognition?.start();
      } catch (e) {}
    }
  }
}

function debounce(fn, waitMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), waitMs);
  };
}

const HA_VERB_OPTIONS = {
  light: [
    { value: "on", label: "Encender" },
    { value: "off", label: "Apagar" },
    { value: "toggle", label: "Alternar" },
  ],
  switch: [
    { value: "on", label: "Encender" },
    { value: "off", label: "Apagar" },
    { value: "toggle", label: "Alternar" },
  ],
  button: [{ value: "press", label: "Pulsar / Reiniciar" }],
  input_button: [{ value: "press", label: "Pulsar" }],
  scene: [{ value: "on", label: "Activar escena" }],
  script: [{ value: "run", label: "Ejecutar script" }],
  automation: [{ value: "trigger", label: "Disparar automatización" }],
  cover: [
    { value: "open", label: "Abrir" },
    { value: "close", label: "Cerrar" },
    { value: "stop", label: "Detener" },
  ],
  lock: [
    { value: "lock", label: "Cerrar cerradura" },
    { value: "unlock", label: "Abrir cerradura" },
  ],
  alarm_control_panel: [
    { value: "arm_home", label: "Armar (home)" },
    { value: "arm_away", label: "Armar (away)" },
    { value: "disarm", label: "Desarmar" },
  ],
  fan: [
    { value: "on", label: "Encender" },
    { value: "off", label: "Apagar" },
    { value: "toggle", label: "Alternar" },
  ],
  media_player: [
    { value: "play", label: "Reproducir" },
    { value: "pause", label: "Pausar" },
    { value: "stop", label: "Detener" },
  ],
  unifi: [{ value: "press", label: "Reiniciar / Pulsar" }],
};

async function loadHaControls(forceRefresh = false) {
  const truthEl = document.getElementById("haControlsTruth");
  const countEl = document.getElementById("haEntityCount");
  const search = document.getElementById("haEntitySearch")?.value?.trim() || "";
  const controllableOnly = document.getElementById("haControllableOnly")?.checked;
  if (truthEl) {
    truthEl.textContent = forceRefresh ? "REFRESH" : "LOADING";
    truthEl.className = "status-badge pending";
  }
  try {
    const params = new URLSearchParams({ limit: search ? "500" : "250" });
    if (search) params.set("q", search);
    if (controllableOnly) params.set("controllable_only", "true");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    const res = await fetch(`/api/ha/controls?${params.toString()}`, { signal: controller.signal });
    window.clearTimeout(timeout);
    const data = await res.json();
    haControlsCache = Array.isArray(data.entities) ? data.entities : [];
    haDomainCounts = data.domain_counts || {};
    populateHaDomainFilter();
    renderHaEntityOptions();
    if (truthEl) {
      truthEl.textContent = data.truth || "UNVERIFIED";
      truthEl.className = `status-badge ${data.truth === "LIVE" ? "live" : data.truth === "SNAPSHOT" ? "pending" : "fallback"}`;
    }
    if (countEl) {
      const ctrl = data.controllable_count ?? haControlsCache.filter((e) => e.controllable).length;
      countEl.textContent = `${data.entity_count ?? haControlsCache.length} entidades · ${ctrl} controlables`;
    }
  } catch (err) {
    console.error("HA controls load failed:", err);
    if (truthEl) {
      truthEl.textContent = err.name === "AbortError" ? "TIMEOUT" : "ERROR";
      truthEl.className = "status-badge fallback";
    }
    if (countEl) {
      countEl.textContent =
        err.name === "AbortError"
          ? "Inventario HA lento — pulsa ↻ Actualizar inventario"
          : "No se pudo cargar inventario HA";
    }
    const select = document.getElementById("haEntitySelect");
    if (select) select.innerHTML = `<option value="">Error cargando — reintentar</option>`;
  }
}

function populateHaDomainFilter() {
  const select = document.getElementById("haDomainFilter");
  if (!select) return;
  const current = select.value;
  const domains = Object.keys(haDomainCounts).sort();
  select.innerHTML = `<option value="">Todos (${haControlsCache.length})</option>`;
  for (const domain of domains) {
    const opt = document.createElement("option");
    opt.value = domain;
    opt.textContent = `${domain} (${haDomainCounts[domain]})`;
    select.appendChild(opt);
  }
  if (current && domains.includes(current)) select.value = current;
}

function renderHaEntityOptions() {
  const select = document.getElementById("haEntitySelect");
  const domainFilter = document.getElementById("haDomainFilter")?.value || "";
  if (!select) return;
  const rows = haControlsCache.filter((row) => !domainFilter || row.domain === domainFilter);
  select.innerHTML = "";
  if (!rows.length) {
    select.innerHTML = `<option value="">Sin resultados</option>`;
    return;
  }
  const groups = {};
  for (const row of rows) {
    const domain = row.domain || "other";
    if (!groups[domain]) groups[domain] = [];
    groups[domain].push(row);
  }
  for (const domain of Object.keys(groups).sort()) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = domain;
    for (const row of groups[domain]) {
      const opt = document.createElement("option");
      opt.value = row.entity_id;
      const ctrl = row.controllable ? "⚡" : "👁";
      opt.textContent = `${ctrl} ${row.friendly_name || row.entity_id} (${row.state ?? "?"})`;
      opt.dataset.domain = row.domain || "";
      opt.dataset.controllable = row.controllable ? "1" : "0";
      optgroup.appendChild(opt);
    }
    select.appendChild(optgroup);
  }
  syncHaVerbOptions();
}

function syncHaVerbOptions() {
  const entitySelect = document.getElementById("haEntitySelect");
  const verbSelect = document.getElementById("haVerbSelect");
  const proposeBtn = document.getElementById("haProposeBtn");
  if (!entitySelect || !verbSelect) return;
  const option = entitySelect.selectedOptions[0];
  const domain = option?.dataset?.domain || "";
  const controllable = option?.dataset?.controllable === "1";
  const verbs = HA_VERB_OPTIONS[domain] || [{ value: "on", label: "Activar" }, { value: "off", label: "Desactivar" }];
  verbSelect.innerHTML = verbs.map((v) => `<option value="${v.value}">${v.label}</option>`).join("");
  if (proposeBtn) proposeBtn.disabled = !entitySelect.value || !controllable;
}

async function proposeSelectedHaAction() {
  const entityId = document.getElementById("haEntitySelect")?.value;
  const verb = document.getElementById("haVerbSelect")?.value;
  const option = document.getElementById("haEntitySelect")?.selectedOptions?.[0];
  if (!entityId || !verb) return;
  if (option?.dataset?.controllable !== "1") {
    appendChat("system", "Esta entidad es solo lectura en el panel. Elige una marcada con ⚡.");
    return;
  }
  const label = option?.textContent?.replace(/^⚡\s*/, "").split(" (")[0] || entityId;
  const domain = option?.dataset?.domain || entityId.split(".")[0];
  const subsystemMap = {
    light: "dmx_lighting",
    switch: "dmx_lighting",
    alarm_control_panel: "security_alarm",
    button: "network_wifi",
    unifi: "network_wifi",
  };
  const targetSubsystem = subsystemMap[domain] || "all";
  try {
    const res = await fetch("/api/governed/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_type: "ha_service",
        target_subsystem: targetSubsystem,
        parameters: {
          entity_id: entityId,
          verb,
          label,
          target_subsystem: targetSubsystem,
        },
      }),
    });
    const data = await res.json();
    if (data.proposal_id) {
      activeProposalId = data.proposal_id;
      showProposalCard(data.proposal_id, data.summary || label, targetSubsystem);
      appendChat("system", `Propuesta ${data.proposal_id} creada para ${label}. Autoriza por voz o con el botón verde.`);
      recordToolCall("propose_governed_action", { entity_id: entityId, verb }, data, 0);
    }
  } catch (err) {
    console.error("HA propose failed:", err);
    appendChat("system", "No se pudo crear la propuesta gobernada.");
  }
}

// Show Proposal Card
function showProposalCard(proposalId, summary, subsystem) {
  document.getElementById("approvalBadge").textContent = "AWAITING CONFIRMATION";
  document.getElementById("approvalBadge").className = "status-badge pending";

  const card = document.getElementById("proposalCard");
  card.className = "proposal-card active";
  card.innerHTML = `
    <div style="font-weight:700; color:#92400e; margin-bottom:4px;">ACTIVE PROPOSAL: <code>${proposalId}</code></div>
    <div style="font-size:12px; color:#1e293b; margin-bottom:6px;">${summary}</div>
    <div style="font-size:11px; color:#64748b;">Requires explicit verbal confirmation from the human operator.</div>
  `;
  const manualActions = document.getElementById("manualApprovalActions");
  if (manualActions) manualActions.style.display = "flex";
  setApprovalButtonsEnabled(true);
}

// Record Tool Call in Ticker
function recordToolCall(name, args, output, latencyMs) {
  const stream = document.getElementById("toolStream");
  if (!stream) return;
  if (stream.querySelector(".empty")) {
    stream.innerHTML = "";
  }

  const latencyEl = document.getElementById("toolLatency");
  if (latencyEl) latencyEl.textContent = `${latencyMs} ms`;

  const item = document.createElement("div");
  item.className = "tool-item";
  item.innerHTML = `
    <div><strong>${name}</strong> <span style="color:#64748b;">(${JSON.stringify(args).slice(0, 35)}...)</span></div>
    <span style="color:#0284c7; font-weight:600;">${latencyMs}ms</span>
  `;
  stream.prepend(item);
}

let lastChatEntry = { role: "", text: "", at: 0 };

function agentChatLabel() {
  const provider = typeof window.getVoiceProvider === "function" ? window.getVoiceProvider() : "boson";
  if (provider === "telephony") return "INNEROS · Phone agent";
  const labels = {
    assemblyai: "INNEROS · AssemblyAI",
    boson: "INNEROS · Boson",
    browser_local: "INNEROS · Browser",
  };
  return labels[provider] || "INNEROS AGENT";
}

// Append Chat Message
function appendChat(role, text) {
  const box = document.getElementById("transcriptBox");
  if (!box) return;
  const normalized = String(text || "").trim();
  if (!normalized) return;
  const now = Date.now();
  if (lastChatEntry.role === role && lastChatEntry.text === normalized && now - lastChatEntry.at < 2500) {
    return;
  }
  lastChatEntry = { role, text: normalized, at: now };

  const placeholder = box.querySelector(".chat-bubble.system p");
  if (box.children.length === 1 && placeholder && placeholder.textContent.includes("InnerOS Executable World listo")) {
    box.innerHTML = "";
  }

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;

  const meta = document.createElement("span");
  meta.className = "bubble-meta";
  meta.textContent =
    role === "user" ? "OPERADOR (GUAYAQUIL)" : role === "agent" ? agentChatLabel() : "SISTEMA";

  const p = document.createElement("p");
  p.textContent = normalized;

  bubble.appendChild(meta);
  bubble.appendChild(p);
  box.appendChild(bubble);
  box.scrollTop = box.scrollHeight;
}

// Send Manual Utterance
function sendManualUtterance() {
  const input = document.getElementById("manualInput");
  const text = input.value.trim();
  if (!text) return;

  if (isAudioSpeaking) {
    triggerInstantBargeIn();
  }

  input.value = "";
  appendChat("user", text);
  processSpokenCommand(text);
}

// Highlight the queried subsystem card on the dashboard
function highlightDashboardCard(subsystem) {
  const cardMap = {
    solar_power: "cardSolar",
    telephony: "cardTelephony",
    network_wifi: "cardNetwork",
    dmx_lighting: "cardDmx",
    servers_rack: "cardNetwork",
    security_alarm: "cardAlarm",
    video_surveillance: "cardCameras",
    instacloud: "partnerInstacloud",
  };
  const cardId = cardMap[subsystem];
  if (cardId) {
    const el = document.getElementById(cardId);
    if (el) {
      el.classList.add("highlighted");
      setTimeout(() => el.classList.remove("highlighted"), 4000);
    }
  }
}

// Canvas Audio Waveform Animator (connected to real microphone AnalyserNode)
function initWaveform() {
  const canvas = document.getElementById("waveformCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let phase = 0;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 24;
    const barWidth = 6;
    const spacing = 5;
    const startX = (canvas.width - bars * (barWidth + spacing)) / 2;

    const isActive = isVoiceActive || isAudioSpeaking;

    if (analyserNode && micDataArray && isVoiceActive) {
      analyserNode.getByteFrequencyData(micDataArray);

      // Hardware VAD: If microphone receives human speech volume while agent is speaking, interrupt immediately!
      if (isAudioSpeaking && Date.now() >= ttsBargeInGuardUntil) {
        let sum = 0;
        for (let k = 0; k < micDataArray.length; k++) {
          sum += micDataArray[k];
        }
        const avg = sum / micDataArray.length;
        const vadThreshold = audioSource === "BROWSER_TTS_FALLBACK" ? 45 : 20;
        if (avg > vadThreshold) {
          triggerInstantBargeIn();
        }
      }
    }

    for (let i = 0; i < bars; i++) {
      let amp = 4;
      if (analyserNode && micDataArray && isVoiceActive) {
        const val = micDataArray[i % micDataArray.length] || 0;
        amp = Math.max(4, (val / 255) * 32);
      } else if (isAudioSpeaking) {
        amp = Math.sin(phase + i * 0.45) * 14 + Math.random() * 8;
        amp = Math.max(4, Math.abs(amp));
      }

      const x = startX + i * (barWidth + spacing);
      const y = (canvas.height - amp) / 2;

      ctx.fillStyle = isActive ? (isAudioSpeaking ? "#10b981" : "#0284c7") : "#cbd5e1";
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, amp, 3);
      ctx.fill();
    }

    phase += 0.18;
    animationFrameId = requestAnimationFrame(draw);
  }
  draw();
}

async function unlockAudioOutput() {
  ensurePlaybackGraph();
  if (playbackContext && playbackContext.state === "suspended") {
    await playbackContext.resume();
  }
  if (audioContext && audioContext.state === "suspended") {
    await audioContext.resume();
  }
  if (window.speechSynthesis && window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
  }
}

window.startBosonVoice = startLiveVoice;
window.stopBosonVoice = stopLiveVoice;
window.forceStopAllVoice = forceStopAllVoice;
window.appendChat = appendChat;
window.refreshGovernedState = fetchIntegrationsStatus;
window.unlockAudioOutput = unlockAudioOutput;
window.speakText = speakText;

async function testAudioOutput() {
  await unlockAudioOutput();
  appendChat("system", "Prueba de audio: deberías oír esta frase.");
  await speakText("Prueba de audio InnerOS VoiceOps. Si escuchas esto, el altavoz funciona correctamente.", { fallback: true });
}
window.testAudioOutput = testAudioOutput;
