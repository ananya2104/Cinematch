(() => {
  "use strict";

  // Empty string = same origin (local dev, or when the backend also serves this
  // file). When the frontend is hosted separately (e.g. GitHub Pages) the page
  // sets window.__API_BASE__ to the backend's absolute URL before this file loads.
  const API_BASE = window.__API_BASE__ || "";

  const PLATFORM_COLORS = {
    "Netflix": "#e5484d",
    "Prime Video": "#22b8cf",
    "JioHotstar": "#8b5cf6",
    "Apple TV+": "#d0d0d5",
    "SonyLIV": "#22c55e",
    "Zee5": "#f2732e",
  };

  const I18N = {
    en: {
      heading: "What do you want<br>to watch today?",
      subtitle: "A favourite actor or director, a certain era, the occasion, or just genre and mood — pick a starting point, or tell me whatever's on your mind.",
      chips: ["Genre or mood", "Actor, director, or franchise", "Release era", "Occasion or company"],
      placeholder: "Ask me anything, in any language…",
      newChat: "New chat",
      platformTitle: "What do you have access to?",
      platformSubtitle: "Tick your subscriptions so every pick is actually watchable — or skip to see anything.",
      skip: "Skip — show me anything",
      continueBtn: "Continue",
      usingPrefix: "Using",
      showingAny: "Showing anything available",
      watchNow: "Watch now",
    },
    hi: {
      heading: "आप आज क्या<br>देखना चाहते हैं?",
      subtitle: "पसंदीदा एक्टर या डायरेक्टर, कोई खास दौर, कोई मौका, या बस जॉनर और मूड — शुरुआत चुनिए, या जो मन में हो वही बताइए।",
      chips: ["जॉनर या मूड", "एक्टर, डायरेक्टर या फ्रैंचाइज़ी", "पुराना दौर", "मौका या साथी"],
      placeholder: "कुछ भी लिखिए, किसी भी भाषा में…",
      newChat: "नई बातचीत",
      platformTitle: "आपके पास कौन-से ऐप्स हैं?",
      platformSubtitle: "अपनी सब्सक्रिप्शन चुनिए ताकि हर सुझाव देखा जा सके — या छोड़कर कुछ भी देखें।",
      skip: "छोड़ें — कुछ भी दिखाओ",
      continueBtn: "जारी रखें",
      usingPrefix: "उपयोग कर रहे हैं",
      showingAny: "कुछ भी दिखाया जा रहा है",
      watchNow: "अभी देखें",
    },
    es: {
      heading: "¿Qué quieres ver<br>hoy?",
      subtitle: "Un actor o director favorito, una época concreta, la ocasión, o simplemente género y estado de ánimo — elige un punto de partida, o cuéntame lo que se te ocurra.",
      chips: ["Género o ánimo", "Actor, director o franquicia", "Una época", "Ocasión o compañía"],
      placeholder: "Escribe lo que quieras, en cualquier idioma…",
      newChat: "Nuevo chat",
      platformTitle: "¿A qué plataformas tienes acceso?",
      platformSubtitle: "Marca tus suscripciones para que cada recomendación se pueda ver — o omite para ver cualquier cosa.",
      skip: "Omitir — muéstrame cualquier cosa",
      continueBtn: "Continuar",
      usingPrefix: "Usando",
      showingAny: "Mostrando cualquier disponible",
      watchNow: "Ver ahora",
    },
    ta: {
      heading: "இன்று என்ன<br>பார்க்க வேண்டும்?",
      subtitle: "விருப்பமான நடிகர் அல்லது இயக்குநர், ஒரு காலகட்டம், சந்தர்ப்பம், அல்லது வெறும் ஜானர் மற்றும் மனநிலை — ஒரு தொடக்கத்தைத் தேர்ந்தெடுங்கள், அல்லது மனதில் உள்ளதைச் சொல்லுங்கள்.",
      chips: ["ஜானர் அல்லது மனநிலை", "நடிகர், இயக்குநர் அல்லது தொடர்", "ஒரு காலகட்டம்", "சந்தர்ப்பம் அல்லது துணை"],
      placeholder: "எதுவும் தட்டச்சு செய்யுங்கள், எந்த மொழியிலும்…",
      newChat: "புதிய அரட்டை",
      platformTitle: "உங்களிடம் என்ன அணுகல் உள்ளது?",
      platformSubtitle: "உங்கள் சந்தாக்களை தேர்வு செய்யுங்கள் — அல்லது தவிர்த்து எதையும் பாருங்கள்.",
      skip: "தவிர் — எதையும் காட்டு",
      continueBtn: "தொடரவும்",
      usingPrefix: "பயன்படுத்துகிறது",
      showingAny: "கிடைப்பவற்றை காட்டுகிறது",
      watchNow: "இப்போது பார்",
    },
    bn: {
      heading: "আজ কী<br>দেখতে চান?",
      subtitle: "প্রিয় অভিনেতা বা পরিচালক, একটা নির্দিষ্ট সময়কাল, উপলক্ষ, নাকি শুধু জনরা আর মুড — একটা শুরু বেছে নিন, বা মনে যা আছে তা বলুন।",
      chips: ["জনরা বা মুড", "অভিনেতা, পরিচালক বা ফ্র্যাঞ্চাইজি", "একটা সময়কাল", "উপলক্ষ বা সঙ্গী"],
      placeholder: "যা খুশি লিখুন, যেকোনো ভাষায়…",
      newChat: "নতুন চ্যাট",
      platformTitle: "আপনার কাছে কী কী আছে?",
      platformSubtitle: "আপনার সাবস্ক্রিপশনগুলো বেছে নিন — অথবা এড়িয়ে যান।",
      skip: "এড়িয়ে যান — যেকোনো কিছু দেখাও",
      continueBtn: "চালিয়ে যান",
      usingPrefix: "ব্যবহার করছে",
      showingAny: "যা পাওয়া যাচ্ছে তা দেখানো হচ্ছে",
      watchNow: "এখনই দেখুন",
    },
    fr: {
      heading: "Que veux-tu regarder<br>aujourd'hui ?",
      subtitle: "Un acteur ou réalisateur préféré, une époque précise, l'occasion, ou juste le genre et l'humeur — choisis un point de départ, ou dis-moi ce qui te passe par la tête.",
      chips: ["Genre ou humeur", "Acteur, réalisateur ou franchise", "Une époque", "Occasion ou compagnie"],
      placeholder: "Écris ce que tu veux, dans n'importe quelle langue…",
      newChat: "Nouvelle discussion",
      platformTitle: "À quoi as-tu accès ?",
      platformSubtitle: "Coche tes abonnements pour que chaque suggestion soit vraiment regardable — ou passe pour tout voir.",
      skip: "Passer — montre-moi n'importe quoi",
      continueBtn: "Continuer",
      usingPrefix: "Utilise",
      showingAny: "Affiche tout ce qui est disponible",
      watchNow: "Regarder",
    },
  };

  const els = {
    chatArea: document.getElementById("chatArea"),
    emptyState: document.getElementById("emptyState"),
    messages: document.getElementById("messages"),
    welcomeChips: document.getElementById("welcomeChips"),
    quickReplies: document.getElementById("quickReplies"),
    composerForm: document.getElementById("composerForm"),
    messageInput: document.getElementById("messageInput"),
    langPicker: document.getElementById("langPicker"),
    resetBtn: document.getElementById("resetBtn"),
  };

  const STORAGE = {
    session: "cinematch_session_id",
    transcript: "cinematch_transcript",
    language: "cinematch_language",
  };

  let sessionId = localStorage.getItem(STORAGE.session);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(STORAGE.session, sessionId);
  }

  let uiLanguage = localStorage.getItem(STORAGE.language) || null;
  let currentUiLang = I18N[uiLanguage] ? uiLanguage : "en";
  let transcript = loadTranscript();

  function t(key) {
    return (I18N[currentUiLang] || I18N.en)[key];
  }

  function applyStaticTranslations() {
    const strings = I18N[currentUiLang] || I18N.en;
    document.querySelector("#emptyState h1").innerHTML = strings.heading;
    document.querySelector("#emptyState p").textContent = strings.subtitle;
    els.welcomeChips.querySelectorAll(".chip").forEach((chip, i) => {
      chip.textContent = strings.chips[i];
    });
    els.messageInput.placeholder = strings.placeholder;
    els.resetBtn.textContent = strings.newChat;
  }

  function loadTranscript() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE.transcript) || "[]");
    } catch {
      return [];
    }
  }

  function saveTranscript() {
    localStorage.setItem(STORAGE.transcript, JSON.stringify(transcript));
  }

  function pushEntry(entry) {
    transcript.push(entry);
    saveTranscript();
  }

  function scrollToBottom() {
    els.chatArea.scrollTop = els.chatArea.scrollHeight;
  }

  // ---------- Rendering primitives ----------

  function renderUserMessage(text) {
    const tpl = document.getElementById("tpl-message-user");
    const node = tpl.content.cloneNode(true);
    node.querySelector(".bubble").textContent = text;
    els.messages.appendChild(node);
  }

  function renderAssistantText(text) {
    const tpl = document.getElementById("tpl-message-assistant");
    const node = tpl.content.cloneNode(true);
    node.querySelector(".text").textContent = text;
    const el = node.querySelector(".msg-assistant");
    els.messages.appendChild(node);
    return el;
  }

  function showTyping() {
    const tpl = document.getElementById("tpl-typing");
    const node = tpl.content.cloneNode(true);
    const el = node.querySelector(".msg-typing");
    els.messages.appendChild(node);
    scrollToBottom();
    return el;
  }

  function renderPlatformWidget(container, available, selected, submitted, chosen, lang) {
    const strings = I18N[lang] || I18N.en;
    const tpl = document.getElementById("tpl-platform-widget");
    const node = tpl.content.cloneNode(true);
    const widget = node.querySelector(".platform-widget");
    widget.dataset.lang = lang || "en";
    widget.querySelector("h3").textContent = strings.platformTitle;
    widget.querySelector(".widget-sub").textContent = strings.platformSubtitle;
    widget.querySelector(".skip-btn").textContent = strings.skip;
    widget.querySelector(".continue-btn").textContent = strings.continueBtn;
    const grid = widget.querySelector(".platform-grid");
    const itemTpl = document.getElementById("tpl-platform-item");

    available.forEach((name) => {
      const itemNode = itemTpl.content.cloneNode(true);
      const label = itemNode.querySelector(".platform-item");
      const dot = itemNode.querySelector(".dot");
      const nameEl = itemNode.querySelector(".platform-name");
      const checkbox = itemNode.querySelector("input");
      dot.style.background = PLATFORM_COLORS[name] || "#888";
      nameEl.textContent = name;
      checkbox.checked = selected.includes(name);
      checkbox.disabled = submitted;
      grid.appendChild(itemNode);
    });

    const skipBtn = widget.querySelector(".skip-btn");
    const continueBtn = widget.querySelector(".continue-btn");

    if (submitted) {
      skipBtn.remove();
      continueBtn.textContent = chosen && chosen.length ? `${strings.usingPrefix} ${chosen.join(", ")}` : strings.showingAny;
      continueBtn.disabled = true;
    } else {
      skipBtn.addEventListener("click", () => submitPlatforms(widget, []));
      continueBtn.addEventListener("click", () => {
        const names = Array.from(grid.querySelectorAll(".platform-item"))
          .filter((item) => item.querySelector("input").checked)
          .map((item) => item.querySelector(".platform-name").textContent);
        submitPlatforms(widget, names);
      });
    }

    container.appendChild(widget);
    return widget;
  }

  function renderRecommendations(container, recs, lang) {
    const strings = I18N[lang] || I18N.en;
    const tpl = document.getElementById("tpl-recs");
    const gridNode = tpl.content.cloneNode(true);
    const grid = gridNode.querySelector(".rec-grid");
    const cardTpl = document.getElementById("tpl-rec-card");

    recs.forEach((rec) => {
      const cardNode = cardTpl.content.cloneNode(true);
      const img = cardNode.querySelector(".rec-poster img");
      img.src = rec.poster_url || "";
      img.alt = rec.title;
      if (!rec.poster_url) img.style.display = "none";
      cardNode.querySelector(".rec-platform-badge").textContent = rec.platform || "";
      const ratingEl = cardNode.querySelector(".rec-rating");
      if (rec.imdb_rating) {
        ratingEl.textContent = `★ ${rec.imdb_rating.toFixed(1)}`;
      } else {
        ratingEl.remove();
      }
      cardNode.querySelector(".rec-title").textContent = rec.title;
      cardNode.querySelector(".rec-year").textContent = rec.year || "";
      cardNode.querySelector(".rec-blurb").textContent = rec.blurb;
      const watchBtn = cardNode.querySelector(".watch-btn");
      watchBtn.href = rec.watch_url;
      watchBtn.textContent = strings.watchNow;
      grid.appendChild(cardNode);
    });

    container.appendChild(grid);
  }

  function setQuickReplies(list) {
    els.quickReplies.innerHTML = "";
    (list || []).forEach((text) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "quick-reply-chip";
      btn.textContent = text;
      btn.addEventListener("click", () => sendMessage(text));
      els.quickReplies.appendChild(btn);
    });
  }

  // ---------- Replay saved transcript on load ----------

  function replayTranscript() {
    if (transcript.length === 0) return;
    els.emptyState.style.display = "none";
    let lastAssistantEl = null;
    transcript.forEach((entry) => {
      if (entry.type === "user") {
        renderUserMessage(entry.text);
      } else if (entry.type === "assistant") {
        lastAssistantEl = renderAssistantText(entry.text);
      } else if (entry.type === "platform_widget") {
        const container = lastAssistantEl ? lastAssistantEl.querySelector(".assistant-content") : els.messages;
        renderPlatformWidget(container, entry.available, entry.selected, entry.submitted, entry.chosen, entry.lang);
      } else if (entry.type === "recs") {
        const container = lastAssistantEl ? lastAssistantEl.querySelector(".assistant-content") : els.messages;
        renderRecommendations(container, entry.recs, entry.lang);
      } else if (entry.type === "quick_replies") {
        setQuickReplies(entry.list);
      }
    });
    scrollToBottom();
  }

  // ---------- Networking ----------

  async function sendMessage(text) {
    text = (text || "").trim();
    if (!text) return;

    els.emptyState.style.display = "none";
    setQuickReplies([]);
    pushEntry({ type: "quick_replies", list: [] });

    renderUserMessage(text);
    pushEntry({ type: "user", text });
    els.messageInput.value = "";
    scrollToBottom();

    const typingEl = showTyping();

    let data;
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text, ui_language: uiLanguage }),
      });
      data = await res.json();
    } catch (err) {
      typingEl.remove();
      const el = renderAssistantText("Sorry, I couldn't reach the server. Please check your connection and try again.");
      pushEntry({ type: "assistant", text: el.querySelector(".text").textContent });
      scrollToBottom();
      return;
    }

    typingEl.remove();
    handleResponse(data);
  }

  async function submitPlatforms(widgetEl, names) {
    widgetEl.querySelectorAll("input").forEach((cb) => (cb.disabled = true));
    const continueBtn = widgetEl.querySelector(".continue-btn");
    const skipBtn = widgetEl.querySelector(".skip-btn");
    if (continueBtn) continueBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;

    const lastWidgetEntry = [...transcript].reverse().find((e) => e.type === "platform_widget" && !e.submitted);
    if (lastWidgetEntry) {
      lastWidgetEntry.submitted = true;
      lastWidgetEntry.chosen = names;
      saveTranscript();
    }
    const widgetStrings = I18N[widgetEl.dataset.lang] || I18N.en;
    if (continueBtn) {
      continueBtn.textContent = names.length
        ? `${widgetStrings.usingPrefix} ${names.join(", ")}`
        : widgetStrings.showingAny;
    }
    if (skipBtn) skipBtn.remove();

    const typingEl = showTyping();
    let data;
    try {
      const res = await fetch(`${API_BASE}/api/platforms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, platforms: names }),
      });
      data = await res.json();
    } catch (err) {
      typingEl.remove();
      const el = renderAssistantText("Sorry, I couldn't reach the server. Please try again.");
      pushEntry({ type: "assistant", text: el.querySelector(".text").textContent });
      scrollToBottom();
      return;
    }
    typingEl.remove();
    handleResponse(data);
  }

  function handleResponse(data) {
    const assistantEl = renderAssistantText(data.reply_text);
    pushEntry({ type: "assistant", text: data.reply_text });
    const container = assistantEl.querySelector(".assistant-content");

    if (data.needs_platform_selection) {
      renderPlatformWidget(container, data.available_platforms, data.selected_platforms, false, null, currentUiLang);
      pushEntry({
        type: "platform_widget",
        available: data.available_platforms,
        selected: data.selected_platforms,
        submitted: false,
        chosen: null,
        lang: currentUiLang,
      });
    }

    if (data.recommendations && data.recommendations.length) {
      renderRecommendations(container, data.recommendations, currentUiLang);
      pushEntry({ type: "recs", recs: data.recommendations, lang: currentUiLang });
    }

    setQuickReplies(data.quick_replies);
    pushEntry({ type: "quick_replies", list: data.quick_replies || [] });

    scrollToBottom();
  }

  // ---------- Wiring ----------

  els.composerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(els.messageInput.value);
  });

  els.welcomeChips.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => sendMessage(chip.textContent));
  });

  els.langPicker.querySelectorAll(".lang-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      els.langPicker.querySelectorAll(".lang-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      uiLanguage = chip.dataset.code === "auto" ? null : chip.dataset.code;
      if (uiLanguage) {
        localStorage.setItem(STORAGE.language, uiLanguage);
      } else {
        localStorage.removeItem(STORAGE.language);
      }
      // "Auto" still needs some language to render the static chrome in — English
      // is the neutral default; it only affects the UI shell, not what the model
      // replies with (that stays auto-detected per message).
      currentUiLang = I18N[uiLanguage] ? uiLanguage : "en";
      applyStaticTranslations();
    });
  });

  els.resetBtn.addEventListener("click", () => {
    localStorage.removeItem(STORAGE.transcript);
    localStorage.removeItem(STORAGE.session);
    window.location.reload();
  });

  // Restore language chip state
  if (uiLanguage) {
    const match = els.langPicker.querySelector(`.lang-chip[data-code="${uiLanguage}"]`);
    if (match) {
      els.langPicker.querySelectorAll(".lang-chip").forEach((c) => c.classList.remove("active"));
      match.classList.add("active");
    }
  }

  applyStaticTranslations();
  replayTranscript();
})();
