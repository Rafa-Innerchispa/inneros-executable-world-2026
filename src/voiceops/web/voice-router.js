/** Unified voice channel selector — AssemblyAI, Boson, browser local, telephony (PBX) */

(function () {

  const STORAGE_KEY = "inneros_voice_provider";

  const select = document.getElementById("voiceProviderSelect");

  const liveBtn = document.getElementById("liveMicBtn");

  const stopBtn = document.getElementById("stopMicBtn");

  const badge = document.getElementById("assemblyaiVoiceBadge");

  const statusEl = document.getElementById("voiceAgentStatus");



  const LABELS = {

    assemblyai: "AssemblyAI · Lola (cloud)",

    boson: "Boson Higgs · InnerOS + TTS",

    browser_local: "Browser · local STT/TTS",

    telephony: "IP Phone · PBX call to your extension",

  };



  const REASONING = {

    assemblyai: "Voice: AssemblyAI cloud · Execution / HA: InnerOS local (.4)",

    boson: "Single voice (Spanish TTS) · Reasoning: InnerOS server · Tools: local HA",

    browser_local: "Single voice (browser TTS) · Reasoning: InnerOS local rules + Qwen",

    telephony:

      "InnerOS calls your Zoiper extension · Voice agent speaks over RTP (server SIP bridge)",

  };



  function currentProvider() {

    return (select && select.value) || localStorage.getItem(STORAGE_KEY) || "boson";

  }



  function isTelephonyMode() {

    return currentProvider() === "telephony";

  }



  function telephonyVoiceProvider() {

    const tel = document.getElementById("telephonyVoiceSelect");

    return (tel && tel.value) || "assemblyai";

  }



  function stopAnyVoiceSession() {

    if (typeof window.forceStopAllVoice === "function") {

      window.forceStopAllVoice({ quiet: true });

      return;

    }

    if (typeof window.stopAssemblyAIVoice === "function") window.stopAssemblyAIVoice();

    if (typeof window.stopBosonVoice === "function") window.stopBosonVoice({ quiet: true });

  }



  function syncVoiceControls() {

    const telephony = isTelephonyMode();

    const panel = document.getElementById("telephonyPanel");

    const telVoice = document.getElementById("telephonyVoiceSelect");

    const live = document.getElementById("liveMicBtn");

    const stop = document.getElementById("stopMicBtn");

    if (panel) panel.classList.toggle("hidden", !telephony);

    if (telVoice) telVoice.classList.toggle("hidden", !telephony);

    if (live) {

      live.disabled = telephony;

      const label = live.querySelector("span");

      if (label) {

        label.textContent = telephony ? "Use “Call extension” below" : "Start Live Voice";

      }

    }

    if (stop && telephony) stop.disabled = true;

  }



  function setProvider(value) {

    if (select) select.value = value;

    localStorage.setItem(STORAGE_KEY, value);

    if (badge) badge.textContent = LABELS[value] || value;

    const reasoningEl = document.getElementById("reasoningBadge");

    if (reasoningEl) reasoningEl.textContent = REASONING[value] || "";

    if (statusEl) {

      if (value === "telephony") {

        statusEl.textContent =

          window.innerosI18n?.t("tel.status") ||

          "Ready — Telephony channel: call your extension";

      } else {

        statusEl.textContent = "Ready — press Start Live Voice";

      }

      statusEl.className = "assemblyai-live-status";

    }

    syncVoiceControls();

    if (typeof window.updateSiteStatusBanner === "function") window.updateSiteStatusBanner();
    const routeChip = document.getElementById("activeProviderRoute");
    if (routeChip) routeChip.textContent = `Route: ${LABELS[value] || value}`;

    if (typeof window.innerosI18n?.applyI18n === "function") window.innerosI18n.applyI18n();

  }



  async function refreshProviderAvailability() {

    try {

      const res = await fetch("/api/integrations/status");

      const data = await res.json();

      const adapters = data.optional_adapters?.adapters || data.partner_integrations || {};

      const assemblyaiOk = adapters.assemblyai?.truth === "REAL" || data.assemblyai?.truth === "REAL";

      const bosonOk = adapters.boson?.truth === "REAL";

      if (select) {

        for (const opt of select.options) {

          if (opt.value === "assemblyai") opt.disabled = !assemblyaiOk;

          if (opt.value === "boson") opt.disabled = !bosonOk;

        }

      }

      const preferred = localStorage.getItem(STORAGE_KEY) || "boson";

      if ((preferred === "assemblyai" && !assemblyaiOk) || (preferred === "boson" && !bosonOk)) {

        setProvider(bosonOk ? "boson" : assemblyaiOk ? "assemblyai" : "browser_local");

      } else {

        setProvider(preferred);

      }

      await refreshTelephonyProviders();

    } catch (err) {

      console.warn("Voice provider status:", err);

    }

  }



  async function refreshTelephonyProviders() {

    const telSelect = document.getElementById("telephonyVoiceSelect");

    if (!telSelect) return;

    try {

      const data = await fetch("/api/telephony/providers").then((r) => r.json());

      const providers = data.providers || {};

      for (const opt of telSelect.options) {

        const meta = providers[opt.value];

        if (!meta) continue;

        const suffix = meta.configured ? "" : " (needs server config)";

        if (meta.label && !opt.textContent.includes("(needs")) {

          opt.textContent = `${meta.label}${suffix}`;

        }

        opt.disabled = opt.value !== "browser_local" && meta.configured === false;

      }

    } catch (err) {

      console.warn("Telephony provider status:", err);

    }

  }



  async function startVoice() {

    const provider = currentProvider();

    if (provider === "telephony") {

      syncVoiceControls();

      document.getElementById("telephonyPanel")?.scrollIntoView({ behavior: "smooth", block: "center" });

      return;

    }



    stopAnyVoiceSession();

    setProvider(provider);

    if (statusEl) {

      statusEl.textContent = "Connecting…";

      statusEl.className = "assemblyai-live-status active";

    }

    if (typeof window.unlockAudioOutput === "function") {

      await window.unlockAudioOutput();

    }

    if (provider === "boson" || provider === "browser_local") {

      if (typeof window.startBosonVoice === "function") {

        await window.startBosonVoice();

        return;

      }

      alert("Voice module not loaded.");

      return;

    }

    if (typeof window.startAssemblyAIVoice === "function") {

      await window.startAssemblyAIVoice();

      return;

    }

    alert("AssemblyAI module not loaded.");

  }



  function stopVoice() {

    const stop = document.getElementById("stopMicBtn");

    const live = document.getElementById("liveMicBtn");

    if (stop) stop.disabled = true;

    if (live) live.disabled = false;

    stopAnyVoiceSession();

    if (statusEl) {

      statusEl.textContent = "Stopped — change channel and press Start";

      statusEl.className = "assemblyai-live-status";

    }

    if (typeof window.appendChat === "function") {

      window.appendChat("system", "Voice session stopped.");

    }

    syncVoiceControls();

  }



  function appendChatSystem(text) {

    if (typeof window.appendChat === "function") {

      window.appendChat("system", text);

    }

  }



  window.getVoiceProvider = currentProvider;

  window.updateSiteStatusBanner = updateSiteStatusBanner;



  function updateSiteStatusBanner() {

    const banner = document.getElementById("alertMessage");

    if (!banner) return;

    banner.textContent = `GYE-Node-01 · ${LABELS[currentProvider()] || currentProvider()} · Stop + channel selector (no browser restart)`;

  }



  let telephonyPollTimer = null;

  let telephonyUiBusy = false;

  let telephonyLastUser = 0;

  let telephonyLastAgent = 0;



  function telephonyCallLabel() {

    return window.innerosI18n?.t("tel.call") || "Call extension with voice agent";

  }



  function telephonyCancelLabel() {

    return window.innerosI18n?.t("tel.cancel") || "Cancel call";

  }



  function setTelephonyDialButtonMode(mode) {

    const btn = document.getElementById("telephonyDialBtn");

    if (!btn) return;

    if (mode === "cancel") {

      btn.textContent = telephonyCancelLabel();

      btn.classList.remove("btn-primary");

      btn.classList.add("btn-danger");

      btn.disabled = false;

      return;

    }

    btn.textContent = telephonyCallLabel();

    btn.classList.remove("btn-danger");

    btn.classList.add("btn-primary");

    btn.disabled = false;

  }



  function stopTelephonyPoll() {

    if (telephonyPollTimer) {

      clearInterval(telephonyPollTimer);

      telephonyPollTimer = null;

    }

  }



  function resetTelephonyUi() {

    stopTelephonyPoll();

    telephonyUiBusy = false;

    window.telephonyCallActive = false;

    telephonyLastUser = 0;

    telephonyLastAgent = 0;

    setTelephonyDialButtonMode("call");

    syncVoiceControls();

  }



  async function pollTelephonySessionOnce() {

    const session = await fetch("/api/telephony/call-session").then((r) => r.json());

    const userLines = session.user_lines || [];

    const agentLines = session.agent_lines || [];

    for (let i = telephonyLastUser; i < userLines.length; i += 1) {

      window.appendChat("user", userLines[i]);

    }

    telephonyLastUser = userLines.length;

    for (let i = telephonyLastAgent; i < agentLines.length; i += 1) {

      window.appendChat("agent", agentLines[i]);

    }

    telephonyLastAgent = agentLines.length;

    if (statusEl && session.phase) {

      const live = [session.user_partial && `You: ${session.user_partial}`, session.agent_partial && `Agent: ${session.agent_partial}`]

        .filter(Boolean)

        .join(" · ");

      statusEl.textContent = live || `Phone call · ${session.phase}`;

      statusEl.className = session.active ? "assemblyai-live-status active" : "assemblyai-live-status ready";

    }

    const out = document.getElementById("telephonyPlanOut");

    if (out && session.debug) {

      const dbg = session.debug;

      const parts = [

        dbg.voice_mode && `voice: ${dbg.voice_mode}`,

        dbg.rtp_in != null && `RTP in: ${dbg.rtp_in}`,

        dbg.rtp_out != null && `RTP out: ${dbg.rtp_out}`,

        dbg.learned_remote && `peer: ${dbg.learned_remote}`,

        dbg.aai_ready && "agent ready",

        dbg.aai_error && `agent err: ${dbg.aai_error}`,

        dbg.playout_buffer_ms != null && `buf: ${dbg.playout_buffer_ms}ms`,

      ].filter(Boolean);

      if (parts.length) out.textContent = parts.join(" · ");

    }

    return session;

  }



  async function cancelTelephonyCall() {

    appendChatSystem("Cancelling phone call…");

    try {

      await fetch("/api/telephony/cancel-call", { method: "POST" });

      await pollTelephonySessionOnce();

    } catch (err) {

      appendChatSystem(`Cancel error: ${err.message || err}`);

    }

  }



  async function callExtensionWithAgent() {

    const ext = document.getElementById("telephonyExtInput")?.value?.trim() || "1004";

    const provider = telephonyVoiceProvider();

    const out = document.getElementById("telephonyPlanOut");



    if (telephonyUiBusy) {

      await cancelTelephonyCall();

      return;

    }



    telephonyUiBusy = true;

    window.telephonyCallActive = true;

    setTelephonyDialButtonMode("cancel");



    if (statusEl) {

      statusEl.textContent = `Calling ext. ${ext}… answer Zoiper on your phone`;

      statusEl.className = "assemblyai-live-status active";

    }

    if (out) out.textContent = `Calling extension ${ext} with ${provider}…`;

    appendChatSystem(`Placing agent call to extension ${ext} (${provider}). Audio stays on your phone; transcript appears here.`);



    try {

      const res = await fetch("/api/telephony/agent-call", {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ extension: ext, voice_provider: provider }),

      });

      const data = await res.json();

      if (!data.ok || !data.started) {

        const msg = data.error || data.message || "Could not start phone call.";

        if (out) out.textContent = msg;

        appendChatSystem(msg);

        if (statusEl) {

          statusEl.textContent = msg;

          statusEl.className = "assemblyai-live-status error";

        }

        resetTelephonyUi();

        return;

      }



      if (out) out.textContent = data.message || `Calling ${ext}…`;

      telephonyPollTimer = setInterval(() => {

        pollTelephonySessionOnce()

          .then((session) => {

            if (!session.active) {

              const summary = [session.phase, session.error].filter(Boolean).join(" · ");

              if (summary) appendChatSystem(`Phone call ended · ${summary}`);

              if (out && summary) out.textContent = summary;

              resetTelephonyUi();

            }

          })

          .catch(() => {});

      }, 450);

    } catch (err) {

      const msg = `Call error: ${err.message || err}`;

      if (out) out.textContent = msg;

      appendChatSystem(msg);

      if (statusEl) {

        statusEl.textContent = msg;

        statusEl.className = "assemblyai-live-status error";

      }

      resetTelephonyUi();

    }

  }



  if (select) {

    select.addEventListener("change", () => {

      stopAnyVoiceSession();

      setProvider(select.value);

    });

    refreshProviderAvailability();

    setInterval(refreshProviderAvailability, 15000);

  }



  if (liveBtn) {

    liveBtn.replaceWith(liveBtn.cloneNode(true));

    document.getElementById("liveMicBtn").addEventListener("click", () => {

      startVoice().catch((err) => {

        console.error(err);

        if (statusEl) {

          statusEl.textContent = `Error: ${err.message || err}`;

          statusEl.className = "assemblyai-live-status error";

        }

      });

    });

  }

  if (stopBtn) {

    stopBtn.replaceWith(stopBtn.cloneNode(true));

    document.getElementById("stopMicBtn").addEventListener("click", stopVoice);

  }



  const testBtn = document.getElementById("testAudioBtn");

  if (testBtn) {

    testBtn.addEventListener("click", () => {

      if (typeof window.testAudioOutput === "function") {

        window.testAudioOutput().catch(console.error);

      }

    });

  }



  const telephonyDialBtn = document.getElementById("telephonyDialBtn");

  if (telephonyDialBtn) {

    telephonyDialBtn.addEventListener("click", () => {

      callExtensionWithAgent().catch(console.error);

    });

  }



  syncVoiceControls();

})();

