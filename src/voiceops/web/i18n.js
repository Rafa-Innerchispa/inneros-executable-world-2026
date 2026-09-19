/** Panel i18n — English default, optional Spanish toggle. */
(function () {
  const STORAGE_KEY = "inneros_panel_lang";
  let lang = localStorage.getItem(STORAGE_KEY) || "en";

  const T = {
    en: {
      "brand.sub": "Governed operations · Guayaquil",
      "header.refresh": "Refresh",
      "header.lang": "Español",
      "alert.connecting": "Connecting site telemetry…",
      "voice.subtitle": "Governed voice with live telemetry and authorized actions",
      "voice.channel": "Voice channel:",
      "voice.test": "Test audio",
      "voice.reasoning": "Reasoning: select a voice channel",
      "tel.title": "IP Phone — call my extension",
      "tel.help":
        "Keep Zoiper on your phone (extension below). InnerOS calls you via the server; pick AssemblyAI, Boson, or server-local InnerOS. If a cloud provider fails, the server auto-falls back.",
      "tel.ext": "Your extension",
      "tel.provider": "Voice provider for the call",
      "tel.call": "Call extension with voice agent",
      "tel.cancel": "Cancel call",
      "tel.status": "Ready — select Telephony channel, then call your extension",
      "chat.welcome":
        "InnerOS Executable World ready. Use the microphone or type an instruction; actions require explicit approval.",
      "chat.system": "SYSTEM",
      "scenario.summary": "Test scenarios",
    },
    es: {
      "brand.sub": "Operaciones gobernadas · Guayaquil",
      "header.refresh": "Actualizar",
      "header.lang": "English",
      "alert.connecting": "Conectando telemetría del sitio…",
      "voice.subtitle": "Voz gobernada con telemetría en vivo y acciones autorizadas",
      "voice.channel": "Canal de voz:",
      "voice.test": "Probar audio",
      "voice.reasoning": "Razonamiento: selecciona canal de voz",
      "tel.title": "Teléfono IP — llamar a mi extensión",
      "tel.help":
        "Mantén Zoiper en tu teléfono (extensión abajo). InnerOS llama vía el servidor; elige AssemblyAI, Boson o InnerOS local. Si falla un proveedor cloud, el servidor hace fallback automático.",
      "tel.ext": "Tu extensión",
      "tel.provider": "Proveedor de voz para la llamada",
      "tel.call": "Llamar extensión con agente de voz",
      "tel.cancel": "Cancelar llamada",
      "tel.status": "Listo — canal Telefonía, luego llama a tu extensión",
      "chat.welcome":
        "InnerOS Executable World listo. Usa el micrófono o escribe una instrucción; las acciones requieren aprobación explícita.",
      "chat.system": "SISTEMA",
      "scenario.summary": "Escenarios de prueba",
    },
  };

  function t(key) {
    return (T[lang] && T[lang][key]) || (T.en[key] || key);
  }

  function applyI18n() {
    document.documentElement.lang = lang === "es" ? "es" : "en";
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.setAttribute("placeholder", t(key));
    });
    const toggle = document.getElementById("langToggleBtn");
    if (toggle) toggle.textContent = t("header.lang");
    if (typeof window.updateSiteStatusBanner === "function") window.updateSiteStatusBanner();
  }

  function setLang(next) {
    lang = next === "es" ? "es" : "en";
    localStorage.setItem(STORAGE_KEY, lang);
    applyI18n();
  }

  function toggleLang() {
    setLang(lang === "en" ? "es" : "en");
  }

  window.innerosI18n = { t, applyI18n, setLang, toggleLang, getLang: () => lang };

  document.addEventListener("DOMContentLoaded", () => {
    applyI18n();
    const btn = document.getElementById("langToggleBtn");
    if (btn) btn.addEventListener("click", toggleLang);
  });
})();
