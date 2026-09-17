(() => {
  "use strict";

  const API_BASE = window.CONSIVA_API_BASE || "http://localhost:8000";

  const el = {
    sidebar: document.getElementById("sidebar"),
    sidebarToggle: document.getElementById("sidebarToggle"),
    sidebarClose: document.getElementById("sidebarClose"),
    sidebarScrim: document.getElementById("sidebarScrim"),
    historyList: document.getElementById("historyList"),
    historyEmpty: document.getElementById("historyEmpty"),
    newChatBtn: document.getElementById("newChatBtn"),
    userStatus: document.getElementById("userStatus"),
    chatWindow: document.getElementById("chatWindow"),
    typingIndicator: document.getElementById("typingIndicator"),
    composerForm: document.getElementById("composerForm"),
    messageInput: document.getElementById("messageInput"),
    sendBtn: document.getElementById("sendBtn"),
    micBtn: document.getElementById("micBtn"),
    headerCallBtn: document.getElementById("headerCallBtn"),
    languageSelect: document.getElementById("languageSelect"),
    voicePanel: document.getElementById("voicePanel"),
    voiceOrb: document.getElementById("voiceOrb"),
    voiceCanvas: document.getElementById("voiceCanvas"),
    voiceStatus: document.getElementById("voiceStatus"),
    voiceTranscript: document.getElementById("voiceTranscript"),
    voiceReply: document.getElementById("voiceReply"),
    voiceInterruptBtn: document.getElementById("voiceInterruptBtn"),
    voiceMuteBtn: document.getElementById("voiceMuteBtn"),
    voiceEndBtn: document.getElementById("voiceEndBtn"),
    voiceMinimizeBtn: document.getElementById("voiceMinimizeBtn"),
    callTimer: document.getElementById("callTimer"),
    devPanel: document.getElementById("devPanel"),
    devUserUsage: document.getElementById("devUserUsage"),
    devGlobalUsage: document.getElementById("devGlobalUsage"),
    devUserBar: document.getElementById("devUserBar"),
    devGlobalBar: document.getElementById("devGlobalBar"),
    devResetBtn: document.getElementById("devResetBtn"),
    toastContainer: document.getElementById("toastContainer"),
  };

  const state = {
    token: localStorage.getItem("consiva_token") || null,
    userId: localStorage.getItem("consiva_user_id") || null,
    isGuest: localStorage.getItem("consiva_is_guest") === "true",
    conversationId: null,
    conversations: [],
    isSending: false,
  };

  const SUGGESTIONS = [
    { topic: "ROPA", text: "What is ROPA software and does Consiva offer it?" },
    { topic: "Breaches", text: "How does Consiva help with CERT-In and DPDP breach timelines?" },
    { topic: "Consent", text: "Can I use Google Consent Mode instead of a full CMP?" },
    { topic: "Discovery", text: "How does Consiva find personal data in our databases?" },
  ];

  const SHOW_SOURCES = false;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // ---------- Small DOM helpers ----------
  function icon(name, className = "icon") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#${name}`);
    svg.appendChild(use);
    return svg;
  }

  function h(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  // ---------- Toasts ----------
  // In-app notifications (never the browser's alert()). `type`: "success" | "error" | "info".
  const TOAST_ICONS = { success: "i-check", error: "i-alert", info: "i-info" };
  const MAX_TOASTS = 3;

  function showToast(message, typeOrIsError = "success", { title = null, duration } = {}) {
    const type = typeOrIsError === true ? "error" : typeOrIsError === false ? "success" : typeOrIsError;
    const ms = duration ?? (type === "error" ? 6000 : 4000);

    const close = () => {
      if (toast.classList.contains("leaving")) return;
      clearTimeout(timer);
      toast.classList.add("leaving");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
      setTimeout(() => toast.remove(), 400);
    };

    const closeBtn = h("button", { class: "toast-close", type: "button", "aria-label": "Dismiss notification" }, icon("i-x"));
    closeBtn.addEventListener("click", close);

    const progress = h("span", { class: "toast-progress", "aria-hidden": "true" });
    progress.style.animationDuration = `${ms}ms`;

    const toast = h(
      "div",
      { class: `toast ${type}`, role: type === "error" ? "alert" : "status" },
      h("span", { class: "toast-icon" }, icon(TOAST_ICONS[type] || TOAST_ICONS.info)),
      h("div", { class: "toast-body" }, title ? h("strong", { class: "toast-title" }, title) : null, message),
      closeBtn,
      progress
    );

    // Pause auto-dismiss while hovered, so people can finish reading.
    let timer = setTimeout(close, ms);
    let remaining = ms;
    let startedAt = Date.now();
    toast.addEventListener("mouseenter", () => {
      clearTimeout(timer);
      remaining -= Date.now() - startedAt;
    });
    toast.addEventListener("mouseleave", () => {
      startedAt = Date.now();
      timer = setTimeout(close, Math.max(remaining, 800));
    });

    el.toastContainer.appendChild(toast);
    const live = [...el.toastContainer.querySelectorAll(".toast:not(.leaving)")];
    if (live.length > MAX_TOASTS) live.slice(0, live.length - MAX_TOASTS).forEach((t) => t.remove());
  }

  // ---------- Dialog ----------
  // In-app confirmation dialog (replaces the browser's confirm()). Resolves true/false.
  function confirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", danger = false }) {
    return new Promise((resolve) => {
      const previousFocus = document.activeElement;
      const titleId = `dlg-title-${Date.now()}`;
      const cancelBtn = h("button", { class: "btn btn-secondary", type: "button" }, cancelLabel);
      const confirmBtn = h("button", { class: `btn ${danger ? "btn-danger" : "btn-primary"}`, type: "button" }, confirmLabel);

      const dialog = h(
        "div",
        { class: `dialog${danger ? " danger" : ""}`, role: "alertdialog", "aria-modal": "true", "aria-labelledby": titleId },
        h("div", { class: "dialog-icon" }, icon(danger ? "i-trash" : "i-info")),
        h("h2", { id: titleId }, title),
        message ? h("p", {}, message) : null,
        h("div", { class: "dialog-actions" }, cancelBtn, confirmBtn)
      );
      const backdrop = h("div", { class: "dialog-backdrop" }, dialog);

      const finish = (result) => {
        document.removeEventListener("keydown", onKey, true);
        backdrop.classList.add("leaving");
        setTimeout(() => backdrop.remove(), 180);
        if (previousFocus && previousFocus.focus) previousFocus.focus();
        resolve(result);
      };

      const onKey = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          finish(false);
        } else if (e.key === "Tab") {
          // Keep keyboard focus inside the dialog.
          const focusables = [cancelBtn, confirmBtn];
          const index = focusables.indexOf(document.activeElement);
          e.preventDefault();
          focusables[(index + (e.shiftKey ? -1 : 1) + focusables.length) % focusables.length].focus();
        }
      };

      cancelBtn.addEventListener("click", () => finish(false));
      confirmBtn.addEventListener("click", () => finish(true));
      backdrop.addEventListener("mousedown", (e) => {
        if (e.target === backdrop) finish(false);
      });
      document.addEventListener("keydown", onKey, true);

      document.body.appendChild(backdrop);
      requestAnimationFrame(() => (danger ? cancelBtn : confirmBtn).focus());
    });
  }

  // ---------- Auth ----------
  async function ensureAuth() {
    if (state.token) return;
    try {
      const res = await fetch(`${API_BASE}/api/auth/guest`, { method: "POST" });
      if (!res.ok) throw new Error("Guest login failed");
      const data = await res.json();
      state.token = data.access_token;
      state.userId = data.user_id;
      state.isGuest = data.is_guest;
      localStorage.setItem("consiva_token", state.token);
      localStorage.setItem("consiva_user_id", state.userId);
      localStorage.setItem("consiva_is_guest", String(state.isGuest));
    } catch (err) {
      showToast("We're having trouble connecting. Check your internet connection and refresh the page.", true);
      throw err;
    }
  }

  function authHeaders(body) {
    const headers = { Authorization: `Bearer ${state.token}` };
    // FormData (audio uploads) must let the browser set its own multipart Content-Type.
    if (typeof body === "string") headers["Content-Type"] = "application/json";
    return headers;
  }

  async function apiFetch(path, options = {}, retried = false) {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...authHeaders(options.body), ...(options.headers || {}) },
    });
    // Token expired or server DB reset: get a fresh guest session and retry once.
    if (res.status === 401 && !retried) {
      localStorage.removeItem("consiva_token");
      state.token = null;
      await ensureAuth();
      updateUserStatus();
      return apiFetch(path, options, true);
    }
    return res;
  }

  function updateUserStatus() {
    el.userStatus.textContent = state.isGuest ? "Guest session" : "Signed in";
  }

  // ---------- Answer formatting ----------
  // Minimal, safe markdown: paragraphs, bullet/numbered lists, **bold**, `code`, ### headings.
  // Built with DOM nodes (never innerHTML) so model output can't inject markup.
  function appendInline(parent, text) {
    const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
    let last = 0;
    for (const match of text.matchAll(pattern)) {
      if (match.index > last) parent.appendChild(document.createTextNode(text.slice(last, match.index)));
      const token = match[0];
      parent.appendChild(token.startsWith("**") ? h("strong", {}, token.slice(2, -2)) : h("code", {}, token.slice(1, -1)));
      last = match.index + token.length;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }

  function renderAnswer(text) {
    const root = h("div", { class: "answer", dir: "auto" });
    let list = null;
    let paragraph = null;

    const closeBlocks = () => {
      list = null;
      paragraph = null;
    };

    for (const rawLine of text.replace(/【[^】]*】/g, "").split("\n")) {
      const line = rawLine.trim();
      if (!line) {
        closeBlocks();
        continue;
      }
      const bullet = line.match(/^[-*•]\s+(.*)$/);
      const numbered = line.match(/^\d+[.)]\s+(.*)$/);
      const heading = line.match(/^#{1,6}\s+(.*)$/);

      if (bullet || numbered) {
        const type = bullet ? "ul" : "ol";
        if (!list || list.tagName.toLowerCase() !== type) {
          list = h(type);
          root.appendChild(list);
        }
        const li = h("li");
        appendInline(li, (bullet || numbered)[1]);
        list.appendChild(li);
        paragraph = null;
      } else if (heading) {
        closeBlocks();
        const node = h("h3");
        appendInline(node, heading[1].replace(/\*\*/g, ""));
        root.appendChild(node);
      } else {
        list = null;
        if (!paragraph) {
          paragraph = h("p");
          root.appendChild(paragraph);
        } else {
          paragraph.appendChild(h("br"));
        }
        appendInline(paragraph, line);
      }
    }
    return root;
  }

  function plainText(text) {
    return text
      .replace(/【[^】]*】/g, "")
      .replace(/\*\*|`|^#{1,6}\s+/gm, "")
      .replace(/^\s*[-*•]\s+/gm, "")
      .replace(/\s*\n+\s*/g, " ")
      .trim();
  }

  function sourceLabel(source) {
    const name = (source.document_name || "")
      .replace(/\.(pdf|docx?|txt|md|html?|csv)$/i, "")
      .replace(/consiva_public_rag_knowledge_base/i, "Consiva knowledge base")
      .replace(/[_-]+/g, " ")
      .trim();
    return source.page_number ? `${name} · p.${Math.round(source.page_number)}` : name;
  }

  // ---------- Rendering ----------
  function scrollToBottom() {
    el.chatWindow.scrollTop = el.chatWindow.scrollHeight;
  }

  function renderWelcome() {
    el.chatWindow.replaceChildren(
      h(
        "div",
        { class: "welcome" },
        (() => {
          const mark = icon("consiva-mark", "welcome-mark");
          return mark;
        })(),
        h("h2", {}, "Get ", h("em", {}, "DPDP-ready"), " with answers in seconds."),
        h(
          "p",
          {},
          "Consent, data discovery, breach response, ROPA: ask in plain language and get clear, practical guidance. Prefer talking? Tap Talk for a hands-free conversation."
        ),
        h(
          "ul",
          { class: "suggestions", "aria-label": "Suggested questions" },
          SUGGESTIONS.map((s) =>
            h(
              "li",
              {},
              h(
                "button",
                { class: "suggestion", type: "button", onClick: () => sendMessage(s.text) },
                h("span", { class: "suggestion-topic" }, s.topic),
                h("span", { class: "suggestion-text" }, s.text),
                icon("i-arrow-right")
              )
            )
          )
        )
      )
    );
  }

  function renderMessage({ role, content, sources, isError, messageId }) {
    el.chatWindow.querySelector(".welcome")?.remove();

    if (role === "user") {
      const row = h("div", { class: "message-row user" }, h("div", { class: "bubble", dir: "auto" }, content));
      el.chatWindow.appendChild(row);
      scrollToBottom();
      return row;
    }

    const bubble = h("div", { class: "bubble" });
    if (isError) {
      bubble.append(icon("i-alert"), h("span", {}, content));
    } else {
      bubble.appendChild(renderAnswer(content));
    }

    // Internal document references aren't shown to customers.
    if (SHOW_SOURCES && !isError && sources && sources.length) {
      // Several chunks often come from the same page; show each page once.
      const labels = [...new Set(sources.map(sourceLabel))];
      bubble.appendChild(
        h(
          "div",
          { class: "sources" },
          h("span", { class: "sources-title" }, "Sources"),
          labels.map((label) => h("span", { class: "source-chip" }, icon("i-file"), label))
        )
      );
    }

    if (!isError && content && messageId) {
      const listenBtn = h("button", { class: "action-btn", type: "button", "aria-pressed": "false" }, icon("i-volume"), h("span", {}, "Listen"));
      listenBtn.addEventListener("click", () => voice.toggleListen(listenBtn, messageId));

      const copyBtn = h("button", { class: "action-btn", type: "button" }, icon("i-copy"), h("span", {}, "Copy"));
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(plainText(content));
          copyBtn.replaceChildren(icon("i-check"), h("span", {}, "Copied"));
          setTimeout(() => copyBtn.replaceChildren(icon("i-copy"), h("span", {}, "Copy")), 1800);
        } catch {
          showToast("Couldn't copy. Select the text and copy it manually.", true);
        }
      });
      bubble.appendChild(h("div", { class: "bubble-actions" }, listenBtn, copyBtn));
    }

    const row = h("div", { class: `message-row bot${isError ? " error" : ""}` }, icon("consiva-mark", "avatar-mark"), bubble);
    el.chatWindow.appendChild(row);
    scrollToBottom();
    return row;
  }

  function setTyping(visible) {
    // Keep the indicator as the last item in the conversation, right under the user's question.
    if (visible) el.chatWindow.appendChild(el.typingIndicator);
    el.typingIndicator.hidden = !visible;
    if (visible) scrollToBottom();
  }

  // ---------- Chat ----------
  async function sendMessage(text, { voiceMode = false, language = null } = {}) {
    if (!text.trim() || state.isSending) return null;
    state.isSending = true;
    el.sendBtn.disabled = true;

    renderMessage({ role: "user", content: text });
    setTyping(true);

    const langChoice = el.languageSelect.value;
    const payload = {
      message: text,
      conversation_id: state.conversationId,
      language: langChoice === "auto" ? language : langChoice,
      voice_mode: voiceMode,
    };

    try {
      const res = await apiFetch("/api/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "Something went wrong on our side. Please try again.");
      }

      const data = await res.json();
      state.conversationId = data.conversation_id;
      renderMessage({ role: "bot", content: data.answer, sources: data.sources, messageId: data.message_id });
      refreshHistory();
      return data;
    } catch (err) {
      renderMessage({
        role: "bot",
        content: "Sorry, I hit a snag answering that. Please try again in a moment.",
        isError: true,
      });
      showToast(err.message || "Request failed", true);
      return null;
    } finally {
      setTyping(false);
      state.isSending = false;
      updateSendState();
    }
  }

  // ---------- History ----------
  async function refreshHistory() {
    try {
      const res = await apiFetch("/api/history");
      if (!res.ok) return;
      state.conversations = await res.json();
      renderHistoryList();
    } catch {
      // silent - history is non-critical
    }
  }

  function historyGroup(dateString) {
    // The API stores UTC timestamps without a zone suffix; parse them as UTC, not local time.
    const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(dateString) ? dateString : `${dateString}Z`);
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);
    const days = (startOfToday - date) / 86_400_000;
    if (days <= 0) return "Today";
    if (days <= 1) return "Yesterday";
    if (days <= 7) return "Previous 7 days";
    return "Older";
  }

  function renderHistoryList() {
    el.historyList.replaceChildren();
    el.historyEmpty.hidden = state.conversations.length > 0;
    let currentGroup = null;

    state.conversations.forEach((conv) => {
      const group = historyGroup(conv.updated_at);
      if (group !== currentGroup) {
        currentGroup = group;
        el.historyList.appendChild(h("li", { class: "history-group-label", role: "presentation" }, group));
      }

      const isActive = conv.id === state.conversationId;
      const title = h(
        "button",
        { class: "title", type: "button", "aria-current": isActive ? "true" : null, dir: "auto" },
        conv.title || "Untitled conversation"
      );
      title.addEventListener("click", () => loadConversation(conv.id));

      const del = h("button", { class: "delete-btn", type: "button", "aria-label": `Delete “${conv.title || "conversation"}”` }, icon("i-trash"));
      del.addEventListener("click", async (e) => {
        e.stopPropagation();
        const confirmed = await confirmDialog({
          title: "Delete this conversation?",
          message: `“${conv.title || "Untitled conversation"}” will be permanently removed. This can't be undone.`,
          confirmLabel: "Delete",
          danger: true,
        });
        if (!confirmed) return;
        try {
          const res = await apiFetch(`/api/history/${conv.id}`, { method: "DELETE" });
          if (!res.ok && res.status !== 404) throw new Error("Couldn't delete that conversation. Try again.");
          if (state.conversationId === conv.id) startNewConversation();
          await refreshHistory();
          showToast("Conversation deleted.");
        } catch (err) {
          showToast(err.message || "Couldn't delete that conversation. Try again.", true);
        }
      });

      el.historyList.appendChild(h("li", { class: "history-item" + (isActive ? " active" : "") }, title, del));
    });
  }

  async function loadConversation(id) {
    try {
      const res = await apiFetch(`/api/history/${id}`);
      if (!res.ok) throw new Error("Couldn't open that conversation.");
      const data = await res.json();
      state.conversationId = data.id;
      el.chatWindow.replaceChildren();
      data.messages.forEach((m) => {
        renderMessage({
          role: m.role === "user" ? "user" : "bot",
          content: m.content,
          sources: m.sources,
          messageId: m.id,
        });
      });
      renderHistoryList();
      closeSidebar();
    } catch (err) {
      showToast(err.message, true);
    }
  }

  function startNewConversation() {
    state.conversationId = null;
    setTyping(false);
    renderWelcome();
    renderHistoryList();
    closeSidebar();
    el.messageInput.focus();
  }

  // ---------- Voice orb (canvas) ----------
  // A liquid sphere: drifting colour fields clipped to a softly deforming edge, a slow light
  // sweep, depth shading and a specular highlight. Energy comes from the real mic signal while
  // listening and from the real TTS audio while speaking, so the orb moves with the voice.
  const ORB_PALETTES = {
    idle: ["#312e81", "#4f46e5", "#818cf8", "#22d3ee"],
    listening: ["#312e81", "#4f46e5", "#818cf8", "#22d3ee"],
    hearing: ["#3730a3", "#6366f1", "#a5b4fc", "#22d3ee"],
    processing: ["#1e1b4b", "#4f46e5", "#f59e0b", "#818cf8"],
    speaking: ["#0e3a5c", "#0891b2", "#67e8f9", "#818cf8"],
    muted: ["#1e293b", "#334155", "#64748b", "#475569"],
    error: ["#4c0519", "#e11d48", "#fb7185", "#f59e0b"],
  };
  const ORB_SPEED = { idle: 0.25, listening: 0.35, hearing: 0.6, processing: 1.5, speaking: 0.8, muted: 0.12, error: 0.3 };

  function hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

  const orb = {
    canvas: el.voiceCanvas,
    ctx: el.voiceCanvas.getContext("2d"),
    raf: 0,
    state: "idle",
    colors: ORB_PALETTES.idle.map(hexToRgb),
    speed: ORB_SPEED.idle,
    energy: 0,
    targetEnergy: 0,
    phase: 0,
    lastTime: 0,
    ripples: [],
    lastRipple: 0,
    levelSource: null, // () => number in 0..1

    setState(next) {
      this.state = ORB_PALETTES[next] ? next : "idle";
    },

    start() {
      if (this.raf) return;
      this.lastTime = performance.now();
      const loop = (now) => {
        this.frame(now);
        this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    },

    stop() {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
      this.ripples = [];
      this.energy = 0;
    },

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(rect.width * dpr);
      if (w && this.canvas.width !== w) {
        this.canvas.width = w;
        this.canvas.height = w;
      }
    },

    frame(now) {
      const dt = Math.min((now - this.lastTime) / 1000, 0.05);
      this.lastTime = now;
      const still = reduceMotion.matches;

      // Ease colours, speed and energy toward the current state.
      const target = ORB_PALETTES[this.state].map(hexToRgb);
      const k = 1 - Math.exp(-dt * 4);
      this.colors = this.colors.map((c, i) => c.map((v, j) => v + (target[i][j] - v) * k));
      this.speed += ((still ? 0.05 : ORB_SPEED[this.state]) - this.speed) * k;

      let level = this.levelSource ? this.levelSource() : 0;
      if (this.state === "processing") level = 0.18 + 0.08 * Math.sin(now / 260);
      this.targetEnergy = Math.max(0, Math.min(1, level));
      const attack = this.targetEnergy > this.energy ? 18 : 5;
      this.energy += (this.targetEnergy - this.energy) * (1 - Math.exp(-dt * attack));
      this.phase += dt * this.speed;

      if (!still && (this.state === "hearing" || this.state === "speaking") && this.energy > 0.32 && now - this.lastRipple > 420) {
        this.ripples.push({ r: 1.0, a: 0.35 * this.energy });
        this.lastRipple = now;
      }

      this.resize();
      this.draw(now, still);
    },

    draw(now, still) {
      const { ctx, canvas } = this;
      const size = canvas.width;
      const c = size / 2;
      const R = (size / 1.44) / 2; // canvas is 144% of the orb box
      const t = this.phase;
      const e = this.energy;
      const [deep, base, light, accent] = this.colors;

      ctx.clearRect(0, 0, size, size);

      // Outer glow breathes with energy.
      const glow = ctx.createRadialGradient(c, c, R * 0.7, c, c, R * 1.42);
      glow.addColorStop(0, rgba(base, 0.32 + e * 0.3));
      glow.addColorStop(0.55, rgba(accent, 0.08 + e * 0.12));
      glow.addColorStop(1, rgba(base, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, size, size);

      // Ripples expand out of the sphere on voice peaks.
      this.ripples = this.ripples.filter((rp) => rp.a > 0.01 && rp.r < 1.4);
      for (const rp of this.ripples) {
        rp.r += 0.012;
        rp.a *= 0.955;
        ctx.beginPath();
        ctx.arc(c, c, R * rp.r, 0, Math.PI * 2);
        ctx.strokeStyle = rgba(light, rp.a);
        ctx.lineWidth = Math.max(1, R * 0.012);
        ctx.stroke();
      }

      // Processing: a thin orbiting arc of light.
      if (this.state === "processing") {
        const angle = (now / 1000) * 2.4;
        ctx.save();
        ctx.translate(c, c);
        ctx.rotate(angle);
        const arc = ctx.createLinearGradient(-R, 0, R, 0);
        arc.addColorStop(0, rgba(accent, 0));
        arc.addColorStop(1, rgba(accent, 0.9));
        ctx.strokeStyle = arc;
        ctx.lineWidth = Math.max(1.5, R * 0.018);
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.arc(0, 0, R * 1.14, -Math.PI * 0.65, 0);
        ctx.stroke();
        ctx.restore();
      }

      // Sphere body with an organic, voice-driven edge.
      const points = 120;
      const wobble = still ? 0 : 0.012 + e * 0.055;
      ctx.save();
      ctx.beginPath();
      for (let i = 0; i <= points; i++) {
        const a = (i / points) * Math.PI * 2;
        const n =
          Math.sin(a * 3 + t * 2.1) * 0.5 +
          Math.sin(a * 5 - t * 1.7 + 1.3) * 0.3 +
          Math.sin(a * 2 + t * 0.9 + 2.6) * 0.2;
        const r = R * (1 + e * 0.05 + n * wobble);
        const x = c + Math.cos(a) * r;
        const y = c + Math.sin(a) * r;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.clip();

      const body = ctx.createRadialGradient(c - R * 0.2, c - R * 0.25, R * 0.1, c, c, R * 1.1);
      body.addColorStop(0, rgba(base, 1));
      body.addColorStop(1, rgba(deep, 1));
      ctx.fillStyle = body;
      ctx.fillRect(0, 0, size, size);

      // Drifting colour fields (lissajous orbits), blended like light.
      ctx.globalCompositeOperation = "screen";
      const fields = [
        { col: light, r: 0.95, fx: 0.9, fy: 1.3, ox: 0.0, amp: 0.42 },
        { col: accent, r: 0.8, fx: 1.2, fy: 0.7, ox: 2.1, amp: 0.48 },
        { col: base, r: 1.0, fx: 0.6, fy: 1.1, ox: 4.2, amp: 0.36 },
        { col: light, r: 0.55, fx: 1.6, fy: 1.4, ox: 1.1, amp: 0.3 + e * 0.2 },
      ];
      for (const f of fields) {
        const x = c + Math.cos(t * f.fx + f.ox) * R * f.amp;
        const y = c + Math.sin(t * f.fy + f.ox * 1.3) * R * f.amp;
        const g = ctx.createRadialGradient(x, y, 0, x, y, R * f.r);
        g.addColorStop(0, rgba(f.col, 0.6 + e * 0.25));
        g.addColorStop(0.55, rgba(f.col, 0.16));
        g.addColorStop(1, rgba(f.col, 0));
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, size, size);
      }

      // Silk bands: two soft, flattened light ellipses drifting and turning inside the sphere.
      ctx.globalCompositeOperation = "overlay";
      for (let i = 0; i < 2; i++) {
        ctx.save();
        ctx.translate(c, c);
        ctx.rotate(t * (0.35 + i * 0.12) + i * 2.2);
        ctx.scale(1, 0.26 + 0.06 * Math.sin(t * 0.8 + i));
        const bx = Math.sin(t * 0.5 + i * 1.7) * R * 0.25;
        const band = ctx.createRadialGradient(bx, 0, 0, bx, 0, R * 0.95);
        band.addColorStop(0, `rgba(255,255,255,${0.5 + e * 0.25})`);
        band.addColorStop(0.45, "rgba(255,255,255,0.12)");
        band.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = band;
        ctx.fillRect(-R * 1.2, -R * 4, R * 2.4, R * 8);
        ctx.restore();
      }

      // Depth: darker rim, bright specular highlight.
      ctx.globalCompositeOperation = "source-over";
      const shade = ctx.createRadialGradient(c, c, R * 0.55, c, c, R * 1.05);
      shade.addColorStop(0, "rgba(3,7,15,0)");
      shade.addColorStop(1, "rgba(3,7,15,0.62)");
      ctx.fillStyle = shade;
      ctx.fillRect(0, 0, size, size);

      const spec = ctx.createRadialGradient(c - R * 0.38, c - R * 0.45, 0, c - R * 0.38, c - R * 0.45, R * 0.62);
      spec.addColorStop(0, "rgba(255,255,255,0.3)");
      spec.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = spec;
      ctx.fillRect(0, 0, size, size);
      ctx.restore();

      // Hairline rim light.
      ctx.beginPath();
      ctx.arc(c, c, R * (1 + e * 0.05), 0, Math.PI * 2);
      const rim = ctx.createLinearGradient(c - R, c - R, c + R, c + R);
      rim.addColorStop(0, "rgba(255,255,255,0.45)");
      rim.addColorStop(0.5, "rgba(255,255,255,0.04)");
      rim.addColorStop(1, rgba(accent, 0.3));
      ctx.strokeStyle = rim;
      ctx.lineWidth = Math.max(1, R * 0.008);
      ctx.stroke();
    },
  };

  // ---------- Hands-free voice conversation ----------
  // Flow: Silero VAD (in-browser) detects when the user starts/stops talking -> audio is sent
  // to the backend for Whisper transcription -> chat answer -> ElevenLabs audio streamed back.
  // The mic stays open while the assistant speaks so the user can interrupt (barge-in).
  const VAD_ASSETS = "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.31/dist/";
  const ORT_ASSETS = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/";

  const VAD_LISTENING = { positiveSpeechThreshold: 0.5, negativeSpeechThreshold: 0.35, minSpeechMs: 250 };
  // While the assistant talks, require clearer, longer speech so speaker echo doesn't interrupt it.
  const VAD_WHILE_SPEAKING = { positiveSpeechThreshold: 0.85, negativeSpeechThreshold: 0.6, minSpeechMs: 450 };

  const PHASE_STATUS = {
    starting: "Connecting…",
    listening: "I'm listening, ask me anything",
    hearing: "Listening…",
    transcribing: "Got it…",
    thinking: "Finding the best answer…",
    speaking: "Speaking · jump in anytime",
    muted: "You're muted",
  };

  const PHASE_ORB = {
    starting: "idle",
    listening: "listening",
    hearing: "hearing",
    transcribing: "processing",
    thinking: "processing",
    speaking: "speaking",
    muted: "muted",
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) return resolve();
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Couldn't load voice components. Check your connection and try again."));
      document.head.appendChild(script);
    });
  }

  // 16 kHz mono Float32 samples (from the VAD) -> 16-bit PCM WAV blob.
  function encodeWav(samples, sampleRate = 16000) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeString = (offset, str) => [...str].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)));
    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([view], { type: "audio/wav" });
  }

  function appendToSourceBuffer(sourceBuffer, chunk) {
    return new Promise((resolve, reject) => {
      sourceBuffer.addEventListener("updateend", resolve, { once: true });
      sourceBuffer.addEventListener("error", () => reject(new Error("Audio playback failed.")), { once: true });
      sourceBuffer.appendBuffer(chunk);
    });
  }

  async function readErrorDetail(res, fallback) {
    const body = await res.json().catch(() => ({}));
    return body.detail || fallback;
  }

  const voice = {
    active: false,
    muted: false,
    phase: "idle",
    vad: null,
    audio: new Audio(),
    audioCtx: null,
    analyser: null,
    analyserData: null,
    micLevel: 0,
    playback: null, // { controller, finish, button } for the audio currently playing
    turn: 0, // incremented to invalidate in-flight work after stop/interrupt
    timerId: 0,
    startedAt: 0,

    // Route TTS audio through an analyser so the orb can follow the real voice.
    ensureAudioGraph() {
      if (this.audioCtx) {
        if (this.audioCtx.state === "suspended") this.audioCtx.resume();
        return;
      }
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        this.audioCtx = new Ctx();
        const source = this.audioCtx.createMediaElementSource(this.audio);
        this.analyser = this.audioCtx.createAnalyser();
        this.analyser.fftSize = 512;
        this.analyserData = new Uint8Array(this.analyser.fftSize);
        source.connect(this.analyser);
        this.analyser.connect(this.audioCtx.destination);
      } catch {
        this.audioCtx = null;
        this.analyser = null;
      }
    },

    outputLevel() {
      if (!this.analyser || this.audio.paused) return 0;
      this.analyser.getByteTimeDomainData(this.analyserData);
      let sum = 0;
      for (const v of this.analyserData) {
        const x = (v - 128) / 128;
        sum += x * x;
      }
      return Math.min(1, Math.sqrt(sum / this.analyserData.length) * 4.5);
    },

    setPhase(phase, detail) {
      this.phase = phase;
      orb.setState(PHASE_ORB[phase] || "idle");
      el.voiceOrb.dataset.state = PHASE_ORB[phase] || "idle";
      el.voiceStatus.textContent = detail || PHASE_STATUS[phase] || "";
      el.voiceInterruptBtn.disabled = phase !== "speaking";
      if (phase !== "hearing" && phase !== "listening") this.micLevel = 0;
      if (this.vad) this.vad.setOptions(phase === "speaking" ? VAD_WHILE_SPEAKING : VAD_LISTENING);
    },

    openCallScreen() {
      el.voicePanel.hidden = false;
      el.voiceTranscript.textContent = "";
      el.voiceReply.textContent = "";
      el.micBtn.setAttribute("aria-pressed", "true");
      this.startedAt = Date.now();
      el.callTimer.textContent = "00:00";
      this.timerId = setInterval(() => {
        const s = Math.floor((Date.now() - this.startedAt) / 1000);
        el.callTimer.textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
      }, 1000);
      orb.levelSource = () => (this.phase === "speaking" ? this.outputLevel() : this.phase === "hearing" || this.phase === "listening" ? this.micLevel : 0);
      orb.start();
      requestAnimationFrame(() => el.voiceEndBtn.focus());
    },

    async start() {
      if (this.active) return;
      if (!navigator.mediaDevices?.getUserMedia) {
        showToast("Voice conversations aren't supported in this browser. Try the latest Chrome, Edge or Safari.", true);
        return;
      }
      this.active = true;
      this.muted = false;
      this.turn++;
      this.stopPlayback();
      this.openCallScreen();
      this.setPhase("starting");
      this.updateMuteButton();

      // Playback later happens after async work, which some browsers (Safari) block unless audio
      // was first unlocked during this click.
      this.ensureAudioGraph();
      this.audio.src = URL.createObjectURL(encodeWav(new Float32Array(160)));
      this.audio.play().catch(() => {});

      try {
        await ensureAuth();
        const cfgRes = await apiFetch("/api/voice/config");
        const cfg = cfgRes.ok ? await cfgRes.json() : { enabled: false };
        if (!cfg.enabled) throw new Error("Voice conversations aren't available right now. You can keep chatting by text.");

        await loadScript(`${ORT_ASSETS}ort.wasm.min.js`);
        await loadScript(`${VAD_ASSETS}bundle.min.js`);
        window.ort.env.wasm.numThreads = 1;
        window.ort.env.logLevel = "error";

        const vad = await window.vad.MicVAD.new({
          model: "v5",
          baseAssetPath: VAD_ASSETS,
          onnxWASMBasePath: ORT_ASSETS,
          redemptionMs: 700, // silence that ends the user's turn
          preSpeechPadMs: 300,
          ...VAD_LISTENING,
          onFrameProcessed: (probs, frame) => {
            let sum = 0;
            for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
            const rms = Math.sqrt(sum / frame.length);
            this.micLevel = Math.min(1, rms * 9) * (0.35 + 0.65 * probs.isSpeech);
          },
          onSpeechStart: () => {
            if (this.phase === "listening") this.setPhase("hearing");
          },
          onSpeechRealStart: () => {
            if (this.phase === "speaking") {
              this.interrupt();
              this.setPhase("hearing");
            }
          },
          onVADMisfire: () => {
            if (this.phase === "hearing") this.setPhase("listening");
          },
          onSpeechEnd: (samples) => {
            if (this.phase === "hearing" || this.phase === "listening") this.handleUtterance(samples);
          },
        });

        if (!this.active) {
          vad.destroy();
          return;
        }
        this.vad = vad;
        await vad.start();
        this.setPhase("listening");
      } catch (err) {
        const name = err && err.name;
        showToast(
          name === "NotAllowedError" || name === "SecurityError"
            ? "Microphone access is blocked. Allow it in your browser's site settings, then tap Talk again."
            : name === "NotFoundError"
              ? "No microphone found. Connect one and try again."
              : err.message || "Couldn't start the voice conversation.",
          true
        );
        this.stop();
      }
    },

    async handleUtterance(samples) {
      const turn = ++this.turn;
      this.setPhase("transcribing");

      const form = new FormData();
      form.append("audio", encodeWav(samples), "speech.wav");
      const langChoice = el.languageSelect.value;
      if (langChoice !== "auto") form.append("language", langChoice);

      try {
        const res = await apiFetch("/api/voice/transcribe", { method: "POST", body: form });
        if (turn !== this.turn) return;
        if (!res.ok) throw new Error(await readErrorDetail(res, "Voice input failed. Try again."));
        const { text, language } = await res.json();
        if (turn !== this.turn) return;

        if (!text) {
          this.setPhase("listening", "Sorry, I missed that. Could you say it again?");
          return;
        }
        el.voiceTranscript.textContent = text;
        el.voiceReply.textContent = "";
        this.setPhase("thinking");

        const data = await sendMessage(text, { voiceMode: true, language });
        if (turn !== this.turn || !this.active) return;
        if (!data) {
          this.setPhase("listening");
          return;
        }
        el.voiceReply.textContent = plainText(data.answer);
        await this.playAnswer(data.message_id, { turn });
      } catch (err) {
        if (turn !== this.turn) return;
        showToast(err.message || "Voice request failed.", true);
        this.setPhase(this.muted ? "muted" : "listening");
      }
    },

    // Per-message Listen button: toggles playback of that answer.
    toggleListen(button, messageId) {
      if (this.playback && this.playback.button === button) {
        this.stopPlayback();
        return;
      }
      this.ensureAudioGraph();
      this.playAnswer(messageId, { button });
    },

    setListenButton(button, playing) {
      if (!button) return;
      button.setAttribute("aria-pressed", String(playing));
      button.replaceChildren(icon(playing ? "i-stop" : "i-volume"), h("span", {}, playing ? "Stop" : "Listen"));
    },

    // Stream ElevenLabs audio for an answer. Used by voice calls and by each message's Listen button.
    async playAnswer(messageId, { turn = null, button = null } = {}) {
      this.stopPlayback();
      const controller = new AbortController();
      let finish;
      const done = new Promise((resolve) => (finish = resolve));
      this.playback = { controller, finish, button };
      this.setListenButton(button, true);
      const inConversation = this.active && turn !== null;

      try {
        const res = await apiFetch("/api/voice/speak", {
          method: "POST",
          body: JSON.stringify({ message_id: messageId }),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(await readErrorDetail(res, "Voice is taking a short break. Keep chatting by text."));

        const audio = this.audio;
        audio.onended = finish;
        audio.onerror = finish;
        if (inConversation) this.setPhase(this.muted ? "muted" : "speaking");
        if (this.audioCtx && this.audioCtx.state === "suspended") await this.audioCtx.resume();

        const canStream = window.MediaSource && MediaSource.isTypeSupported("audio/mpeg") && res.body;
        if (canStream) {
          const mediaSource = new MediaSource();
          audio.src = URL.createObjectURL(mediaSource);
          await new Promise((resolve) => mediaSource.addEventListener("sourceopen", resolve, { once: true }));
          const sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");
          const reader = res.body.getReader();
          let started = false;
          for (;;) {
            const { done: streamDone, value } = await reader.read();
            if (streamDone || controller.signal.aborted) break;
            await appendToSourceBuffer(sourceBuffer, value);
            if (!started) {
              started = true;
              audio.play().catch(finish);
            }
          }
          if (mediaSource.readyState === "open" && !controller.signal.aborted) mediaSource.endOfStream();
          if (!started) finish();
        } else {
          const blob = await res.blob();
          if (controller.signal.aborted) return;
          audio.src = URL.createObjectURL(blob);
          await audio.play();
        }
        await done;
      } catch (err) {
        if (err.name !== "AbortError") {
          showToast(err.message || "Couldn't play the voice reply.", true);
          if (inConversation && this.active && this.turn === turn) {
            this.setPhase(this.muted ? "muted" : "listening", "Voice paused · your answer is in the chat");
          }
        }
      } finally {
        if (this.playback?.controller === controller) {
          this.playback = null;
          this.setListenButton(button, false);
        }
        devTools.refresh();
        // Whatever happened (finished, failed, quota reached), never leave the call stuck mid-turn.
        const midTurn = ["speaking", "thinking", "transcribing"].includes(this.phase);
        if (inConversation && this.active && this.turn === turn && midTurn) {
          this.setPhase(this.muted ? "muted" : "listening");
        }
      }
    },

    stopPlayback() {
      if (!this.playback) return;
      const { controller, finish, button } = this.playback;
      this.playback = null;
      controller.abort();
      this.audio.pause();
      finish();
      this.setListenButton(button, false);
    },

    interrupt() {
      this.turn++;
      this.stopPlayback();
      if (this.active) this.setPhase(this.muted ? "muted" : "listening");
    },

    updateMuteButton() {
      el.voiceMuteBtn.setAttribute("aria-pressed", String(this.muted));
      el.voiceMuteBtn.replaceChildren(
        h("span", { class: "call-btn-circle" }, icon(this.muted ? "i-mic-off" : "i-mic")),
        h("span", { class: "call-btn-label" }, this.muted ? "Unmute" : "Mute")
      );
    },

    async toggleMute() {
      if (!this.active || !this.vad) return;
      this.muted = !this.muted;
      this.updateMuteButton();
      if (this.muted) {
        await this.vad.pause();
        if (this.phase === "listening" || this.phase === "hearing") this.setPhase("muted");
      } else {
        await this.vad.start();
        if (this.phase === "muted") this.setPhase("listening");
      }
    },

    stop() {
      if (!this.active && el.voicePanel.hidden) return;
      this.turn++;
      this.active = false;
      this.stopPlayback();
      if (this.vad) {
        this.vad.destroy();
        this.vad = null;
      }
      clearInterval(this.timerId);
      orb.stop();
      orb.levelSource = null;
      this.phase = "idle";
      el.voicePanel.hidden = true;
      el.micBtn.setAttribute("aria-pressed", "false");
      el.micBtn.focus();
    },
  };

  // ---------- TEMPORARY testing panel: voice limit usage + reset ----------
  const devTools = {
    enabled: false,

    async init() {
      try {
        const res = await apiFetch("/api/voice/config");
        if (!res.ok) return;
        const cfg = await res.json();
        this.enabled = Boolean(cfg.dev_tools);
        el.devPanel.hidden = !this.enabled;
        if (this.enabled) await this.refresh();
      } catch {
        // testing aid only; ignore
      }
    },

    render(usage) {
      const fmt = new Intl.NumberFormat();
      const show = (textEl, barEl, used, limit) => {
        textEl.textContent = `${fmt.format(used)} / ${fmt.format(limit)}`;
        const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
        barEl.style.width = `${pct}%`;
        barEl.classList.toggle("full", pct >= 100);
      };
      show(el.devUserUsage, el.devUserBar, usage.user_characters, usage.user_limit);
      show(el.devGlobalUsage, el.devGlobalBar, usage.global_characters, usage.global_limit);
    },

    async refresh() {
      if (!this.enabled) return;
      try {
        const res = await apiFetch("/api/voice/usage");
        if (res.ok) this.render(await res.json());
      } catch {
        // ignore
      }
    },

    async reset() {
      el.devResetBtn.disabled = true;
      try {
        const res = await apiFetch("/api/voice/usage/reset", { method: "POST" });
        if (!res.ok) throw new Error("Reset isn't available on this server.");
        this.render(await res.json());
        showToast("Voice limits reset for today.");
      } catch (err) {
        showToast(err.message || "Couldn't reset voice limits.", true);
      } finally {
        el.devResetBtn.disabled = false;
      }
    },
  };

  // ---------- UI helpers ----------
  function autoGrow() {
    el.messageInput.style.height = "auto";
    el.messageInput.style.height = Math.min(el.messageInput.scrollHeight, 180) + "px";
    updateSendState();
  }

  function updateSendState() {
    el.sendBtn.disabled = state.isSending || !el.messageInput.value.trim();
  }

  function openSidebar() {
    el.sidebar.classList.add("open");
    el.sidebarScrim.hidden = false;
  }

  function closeSidebar() {
    el.sidebar.classList.remove("open");
    el.sidebarScrim.hidden = true;
  }

  // ---------- Event wiring ----------
  el.composerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    // Keep the typed text if a reply is still in progress, instead of silently dropping it.
    if (state.isSending) return;
    const text = el.messageInput.value;
    if (!text.trim()) return;
    el.messageInput.value = "";
    autoGrow();
    sendMessage(text);
  });

  el.messageInput.addEventListener("input", autoGrow);
  el.messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      el.composerForm.requestSubmit();
    }
  });

  const toggleCall = () => (voice.active ? voice.stop() : voice.start());
  el.micBtn.addEventListener("click", toggleCall);
  el.headerCallBtn.addEventListener("click", toggleCall);
  el.voiceEndBtn.addEventListener("click", () => voice.stop());
  el.voiceMinimizeBtn.addEventListener("click", () => voice.stop());
  el.voiceMuteBtn.addEventListener("click", () => voice.toggleMute());
  el.voiceInterruptBtn.addEventListener("click", () => voice.interrupt());
  el.voiceOrb.addEventListener("click", () => {
    if (voice.phase === "speaking") voice.interrupt();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (voice.active) voice.stop();
      else closeSidebar();
    }
  });
  el.newChatBtn.addEventListener("click", startNewConversation);
  el.devResetBtn.addEventListener("click", () => devTools.reset());
  el.sidebarToggle.addEventListener("click", openSidebar);
  el.sidebarClose.addEventListener("click", closeSidebar);
  el.sidebarScrim.addEventListener("click", closeSidebar);

  // ---------- Init ----------
  async function init() {
    updateUserStatus();
    renderWelcome();
    renderHistoryList();
    updateSendState();

    try {
      await ensureAuth();
      updateUserStatus();
      await refreshHistory();
      devTools.init();
    } catch {
      // toast already shown
    }
  }

  init();
})();
