const REFRESH_MS = 7000;
const SCROLL_PIN_THRESHOLD = 56;
const PROJECT_STORAGE_KEY = "koyori-cc-encoded-project";
const SESSION_STORAGE_KEY = "koyori-cc-session-id";

let chatPinnedToBottom = true;
let chatMessages = [];
let renderedMessageKeys = new Set();
let streamingBubbleEl = null;
let sendInProgress = false;
let activeSessionId = null;
let activeProjectEncoded = null;
let activeProjectPath = null;
let projectList = [];
let conversationList = [];
let sendTargetSessionId = null;
let activeStreamController = null;

function formatTime(date) {
  return date.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
}

function formatTimestamp(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ja-JP", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function updateClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = formatTime(new Date());
}

async function fetchJson(path, options = {}) {
  const res = await fetch(path, {
    cache: "no-store",
    headers: { Accept: "application/json; charset=utf-8", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = `${path} → ${res.status}`;
    try {
      const buffer = await res.arrayBuffer();
      const text = new TextDecoder("utf-8").decode(buffer);
      const body = JSON.parse(text);
      if (body.detail) {
        if (Array.isArray(body.detail)) {
          detail = body.detail.map((item) => item.msg || JSON.stringify(item)).join(" / ");
        } else {
          detail = String(body.detail);
        }
      }
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }
  const buffer = await res.arrayBuffer();
  const text = new TextDecoder("utf-8").decode(buffer);
  return JSON.parse(text);
}

async function postJson(path, payload) {
  return fetchJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });
}

async function deleteJson(path) {
  return fetchJson(path, { method: "DELETE" });
}

function historyApiPath(encodedProject, sessionId) {
  return `/api/projects/${encodeURIComponent(encodedProject)}/histories/${encodeURIComponent(sessionId)}`;
}

function getSelectedSessionId() {
  return activeSessionId;
}

function syncActiveSessionFromSelect() {
  const select = document.getElementById("history-select");
  const sessionId = select?.value?.trim();
  if (sessionId && sessionId !== activeSessionId) {
    activeSessionId = sessionId;
    persistActiveSession();
  }
  return activeSessionId;
}

function isCurrentSession(sessionId) {
  return getSelectedSessionId() === sessionId;
}

function persistActiveSession() {
  if (activeSessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
  }
  if (activeProjectEncoded) {
    localStorage.setItem(PROJECT_STORAGE_KEY, activeProjectEncoded);
  }
}

function currentConversation() {
  return conversationList.find((item) => item.sessionId === activeSessionId);
}

function currentSessionTitle() {
  const conv = currentConversation();
  return conv?.lastMessagePreview?.slice(0, 42) || activeSessionId || "このセッション";
}

function renderProjectSwitcher() {
  const select = document.getElementById("project-select");
  if (!select) return;
  select.innerHTML = projectList
    .map(
      (project) =>
        `<option value="${escapeHtml(project.encodedName)}"${
          project.encodedName === activeProjectEncoded ? " selected" : ""
        }>${escapeHtml(project.path)}</option>`,
    )
    .join("");
}

function renderHistorySwitcher() {
  const select = document.getElementById("history-select");
  if (!select) return;
  if (!conversationList.length) {
    select.innerHTML = '<option value="">セッションがありません</option>';
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = conversationList
    .map((conv) => {
      const when = formatTimestamp(conv.lastTime || conv.startTime);
      const count = conv.messageCount > 0 ? ` · ${conv.messageCount}件` : "";
      const preview = conv.lastMessagePreview ? ` — ${conv.lastMessagePreview.slice(0, 36)}` : "";
      return `<option value="${escapeHtml(conv.sessionId)}"${
        conv.sessionId === activeSessionId ? " selected" : ""
      }>${escapeHtml(conv.sessionId.slice(0, 8))}…${escapeHtml(count)}${escapeHtml(preview)} · ${escapeHtml(when)}</option>`;
    })
    .join("");
}

async function loadProjects() {
  const data = await fetchJson("/api/projects");
  projectList = data.projects || [];
}

async function loadConversations(encodedProject) {
  const data = await fetchJson(
    `/api/projects/${encodeURIComponent(encodedProject)}/histories`,
  );
  conversationList = data.conversations || [];
}

async function loadConversationMessages({ fullRebuild = false } = {}) {
  if (!activeProjectEncoded || !activeSessionId) {
    chatMessages = [];
    clearChatLog();
    showChatPlaceholder("まだ会話がありません");
    return;
  }
  const data = await fetchJson(historyApiPath(activeProjectEncoded, activeSessionId));
  const fresh = CcMessages.flattenHistoryMessages(data.messages);
  applyChatMessages(fresh, { fullRebuild });
}

async function selectProject(encodedName, { force = false } = {}) {
  if (!encodedName || (!force && encodedName === activeProjectEncoded)) return;
  activeProjectEncoded = encodedName;
  const project = projectList.find((item) => item.encodedName === encodedName);
  activeProjectPath = project?.path || null;
  persistActiveSession();
  await loadConversations(encodedName);
  renderProjectSwitcher();
  renderHistorySwitcher();

  const savedSession = localStorage.getItem(SESSION_STORAGE_KEY);
  const target =
    conversationList.find((item) => item.sessionId === savedSession) ||
    conversationList[0];
  if (target) {
    await selectSession(target.sessionId, { force: true });
  } else {
    activeSessionId = null;
    chatMessages = [];
    clearChatLog();
    showChatPlaceholder("まだ会話がありません");
  }
}

async function selectSession(sessionId, { force = false } = {}) {
  if (!sessionId || (!force && sessionId === activeSessionId && !sendInProgress)) return;
  activeSessionId = sessionId;
  persistActiveSession();
  chatPinnedToBottom = true;
  renderedMessageKeys = new Set();
  renderHistorySwitcher();
  await loadConversationMessages({ fullRebuild: true });
}

async function initSessions() {
  await loadProjects();
  if (!projectList.length) {
    throw new Error(
      "Claude Code プロジェクトが見つかりません。8080 の claude-code-webui が起動しているか確認してください。",
    );
  }
  const saved = localStorage.getItem(PROJECT_STORAGE_KEY);
  const initial =
    projectList.find((project) => project.encodedName === saved)?.encodedName ||
    projectList[0].encodedName;
  await selectProject(initial, { force: true });
}

function setupSessionSwitcher() {
  const projectSelect = document.getElementById("project-select");
  const historySelect = document.getElementById("history-select");
  const reloadButton = document.getElementById("session-reload");

  if (projectSelect) {
    projectSelect.addEventListener("change", () => {
      void selectProject(projectSelect.value, { force: true });
    });
  }
  if (historySelect) {
    historySelect.addEventListener("change", () => {
      void selectSession(historySelect.value, { force: true });
    });
  }
  if (reloadButton) {
    reloadButton.addEventListener("click", () => {
      void loadConversationMessages();
    });
  }
}

function messageKey(msg) {
  const body = CcMessages.sanitizeDisplayText(msg.message || "");
  return `${msg.sender}|${msg.timestamp}|${body}`;
}

function clearChatLog() {
  const root = document.getElementById("chat-log");
  if (!root) return;
  root.innerHTML = "";
  renderedMessageKeys = new Set();
  clearStreamingBubble();
}

function showChatPlaceholder(text) {
  const root = document.getElementById("chat-log");
  if (!root) return;
  root.innerHTML = `<p class="placeholder">${escapeHtml(text)}</p>`;
  renderedMessageKeys = new Set();
  clearStreamingBubble();
}

function scrollChatToBottom() {
  const root = document.getElementById("chat-log");
  if (!root) return;
  requestAnimationFrame(() => {
    root.scrollTop = root.scrollHeight;
  });
}

function buildMessageElement(msg, { animate = false } = {}) {
  const who = msg.sender === "ma" ? "まー" : "こより";
  const label = msg.sender === "ma" ? "M" : "K";
  const extraClass = msg._pending ? " is-pending" : msg._thinking ? " is-thinking" : "";
  const enterClass = animate ? " message-enter" : "";
  const body = CcMessages.sanitizeDisplayText(msg.message || "");
  const el = document.createElement("div");
  el.className = `message ${msg.sender}${extraClass}${enterClass}`;
  el.dataset.sender = msg.sender;
  el.dataset.messageKey = messageKey({ ...msg, message: body });
  el.innerHTML = `<span class="meta-line"><span class="sender-badge">${label}</span> ${who} · ${formatTimestamp(msg.timestamp)}</span>
        <div class="message-body">${escapeHtml(body)}</div>`;
  return el;
}

function appendMessagesToDom(messages, { animate = false } = {}) {
  const root = document.getElementById("chat-log");
  if (!root || !messages.length) return 0;

  const placeholder = root.querySelector(".placeholder");
  if (placeholder) placeholder.remove();

  let added = 0;
  for (const msg of messages) {
    const key = messageKey(msg);
    if (renderedMessageKeys.has(key)) continue;
    root.appendChild(buildMessageElement(msg, { animate }));
    renderedMessageKeys.add(key);
    added += 1;
  }
  return added;
}

function applyChatMessages(fresh, { fullRebuild = false, forceScroll = false } = {}) {
  if (!fresh.length) {
    chatMessages = [];
    clearChatLog();
    showChatPlaceholder("まだ会話がありません");
    return 0;
  }

  if (fullRebuild) {
    chatMessages = fresh;
    clearChatLog();
    const added = appendMessagesToDom(fresh, { animate: false });
    if (added > 0 && (chatPinnedToBottom || forceScroll)) scrollChatToBottom();
    updateChatHint();
    return added;
  }

  const existingKeys = new Set(chatMessages.map(messageKey));
  const newOnes = fresh.filter((msg) => !existingKeys.has(messageKey(msg)));

  if (fresh.length < chatMessages.length) {
    chatMessages = fresh;
    clearChatLog();
    const added = appendMessagesToDom(fresh, { animate: false });
    if (added > 0 && chatPinnedToBottom) scrollChatToBottom();
    updateChatHint();
    return added;
  }

  if (!newOnes.length) return 0;

  chatMessages = fresh;
  const added = appendMessagesToDom(newOnes, { animate: true });
  if (added > 0 && (chatPinnedToBottom || forceScroll)) scrollChatToBottom();
  updateChatHint();
  return added;
}

function clearStreamingBubble() {
  if (streamingBubbleEl) {
    streamingBubbleEl.remove();
    streamingBubbleEl = null;
  }
}

function updateStreamingBubble(text) {
  const root = document.getElementById("chat-log");
  if (!root) return;
  const placeholder = root.querySelector(".placeholder");
  if (placeholder) placeholder.remove();

  const body = CcMessages.sanitizeDisplayText(text || "");
  if (!body) return;

  if (!streamingBubbleEl) {
    streamingBubbleEl = buildMessageElement(
      {
        sender: "koyori",
        message: body,
        timestamp: new Date().toISOString(),
        _streaming: true,
      },
      { animate: true },
    );
    streamingBubbleEl.classList.add("is-streaming");
    root.appendChild(streamingBubbleEl);
  } else {
    const bodyEl = streamingBubbleEl.querySelector(".message-body");
    if (bodyEl) bodyEl.textContent = body;
  }

  if (chatPinnedToBottom) scrollChatToBottom();
}

function setupChatScroll() {
  const root = document.getElementById("chat-log");
  if (!root || root.dataset.scrollBound) return;
  root.dataset.scrollBound = "1";
  root.addEventListener("scroll", () => {
    const dist = root.scrollHeight - root.scrollTop - root.clientHeight;
    chatPinnedToBottom = dist < SCROLL_PIN_THRESHOLD;
    updateChatHint();
  });
}

function updateChatHint() {
  const hint = document.getElementById("chat-hint");
  if (!hint) return;
  hint.textContent = chatPinnedToBottom ? "" : "上にスクロール中";
}

function setChatThinking(active) {
  const root = document.getElementById("chat-log");
  if (!root) return;

  const existing = root.querySelector(".message.is-thinking");
  if (active) {
    if (existing) return;
    const thinking = buildMessageElement(
      {
        sender: "koyori",
        message: "考えてる…",
        timestamp: new Date().toISOString(),
        _thinking: true,
      },
      { animate: true },
    );
    thinking.classList.add("is-thinking");
    root.appendChild(thinking);
    if (chatPinnedToBottom) scrollChatToBottom();
    return;
  }
  if (existing) existing.remove();
}

function setComposeEnabled(enabled) {
  const input = document.getElementById("chat-input");
  const button = document.getElementById("chat-send");
  if (input) input.disabled = !enabled;
  if (button) button.disabled = !enabled;
}

async function sendChatMessage(text) {
  const trimmed = text.trim();
  if (!trimmed || sendInProgress) return;

  const targetSessionId = syncActiveSessionFromSelect();
  sendInProgress = true;
  sendTargetSessionId = targetSessionId || null;
  setComposeEnabled(false);
  chatPinnedToBottom = true;

  const optimistic = {
    sender: "ma",
    message: trimmed,
    timestamp: new Date().toISOString(),
    _pending: true,
  };
  chatMessages = [...chatMessages, optimistic];
  appendMessagesToDom([optimistic], { animate: true });
  if (chatPinnedToBottom) scrollChatToBottom();
  setChatThinking(true);

  const requestId = crypto.randomUUID();
  const payload = {
    message: trimmed,
    requestId,
    workingDirectory: activeProjectPath || undefined,
    sessionId: targetSessionId || undefined,
  };

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8", Accept: "application/x-ndjson" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`/api/chat → ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantDraft = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        let chunk;
        try {
          chunk = JSON.parse(line);
        } catch {
          continue;
        }

        if (chunk.type === "social_silent") {
          assistantDraft = "（いまは静かにしている）";
        } else if (chunk.type === "error") {
          throw new Error(chunk.error || "chat stream error");
        } else if (chunk.type === "claude_json") {
          const sid = CcMessages.extractStreamSessionId(chunk);
          if (sid) {
            activeSessionId = sid;
            persistActiveSession();
          }
          const piece = CcMessages.extractStreamText(chunk);
          if (piece) {
            assistantDraft = piece;
          }
        }

        if (assistantDraft) {
          updateStreamingBubble(assistantDraft);
        }
      }
    }

    clearStreamingBubble();
    setChatThinking(false);

    const root = document.getElementById("chat-log");
    const pendingEl = root?.querySelector(".message.is-pending");
    if (pendingEl) {
      pendingEl.classList.remove("is-pending");
      const key = messageKey(optimistic);
      pendingEl.dataset.messageKey = key;
      renderedMessageKeys.add(key);
    }

    chatMessages = chatMessages.filter((msg) => !msg._pending && !msg._thinking && !msg._streaming);
    const finalizedUser = { ...optimistic, _pending: false };
    chatMessages.push(finalizedUser);

    if (assistantDraft) {
      const reply = {
        sender: "koyori",
        message: assistantDraft,
        timestamp: new Date().toISOString(),
      };
      chatMessages.push(reply);
      appendMessagesToDom([reply], { animate: true });
      if (chatPinnedToBottom) scrollChatToBottom();
    }

    if (activeProjectEncoded) {
      await loadConversations(activeProjectEncoded);
      renderHistorySwitcher();
    }
    await refreshStatus();
  } catch (err) {
    clearStreamingBubble();
    setChatThinking(false);
    chatMessages = chatMessages.filter((msg) => !msg._pending && !msg._thinking && !msg._streaming);
    const root = document.getElementById("chat-log");
    root?.querySelector(".message.is-pending")?.remove();
    renderedMessageKeys = new Set(chatMessages.map(messageKey));
    if (root) {
      const note = document.createElement("p");
      note.className = "error";
      note.textContent = `送信できなかった: ${err.message}`;
      root.appendChild(note);
    }
  } finally {
    sendInProgress = false;
    sendTargetSessionId = null;
    setComposeEnabled(true);
    clearStreamingBubble();
    setChatThinking(false);
    const input = document.getElementById("chat-input");
    if (input) input.focus();
  }
}

function setupChatCompose() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  if (!form || !input) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value;
    input.value = "";
    input.style.height = "auto";
    sendChatMessage(text);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 96)}px`;
  });
}

function renderStatus(data) {
  const root = document.getElementById("status-content");
  const tempEl = document.getElementById("temperature");
  if (!root) return;

  const temp = KoyoriVoice.formatTemperature(data.temperature);
  const desires = KoyoriVoice.formatDesires(data.desires, data.dominant_desire);
  const social = KoyoriVoice.formatSocialVibe(data.social_state);
  const journey = KoyoriVoice.formatJourney(data.active_arcs);
  const moments = KoyoriVoice.formatExperiences(data.recent_experiences);

  if (tempEl) {
    tempEl.textContent = temp.detail ? `${temp.body} · ${temp.detail}` : temp.body;
  }

  const desireList = desires.lines
    .map(
      (line) =>
        `<li><span class="tag">${escapeHtml(line.intensity)}</span> ${escapeHtml(line.text)}</li>`,
    )
    .join("");

  const journeyList = journey.items
    .map(
      (item) =>
        `<li><strong>${escapeHtml(item.title)}</strong> — ${escapeHtml(item.summary || "")}</li>`,
    )
    .join("");

  const socialTags = social.tags
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join("");

  const momentList = moments.items
    .map(
      (item) =>
        `<li>${escapeHtml(item.kind)}: ${escapeHtml(item.summary || "")}</li>`,
    )
    .join("");

  root.innerHTML = `
    <article class="status-card status-card--temp mood-${escapeHtml(temp.mood || "neutral")} is-updated">
      <span class="status-card__icon" aria-hidden="true">${escapeHtml(temp.icon || "○")}</span>
      <span class="status-card__label">${escapeHtml(temp.label)}</span>
      <p class="status-card__body">${escapeHtml(temp.body)}</p>
      ${temp.detail ? `<span class="status-card__detail">${escapeHtml(temp.detail)}</span>` : ""}
    </article>

    <article class="status-card is-updated">
      <span class="status-card__label">いまの気持ち</span>
      <p class="status-card__body">${escapeHtml(desires.headline)}</p>
      <p class="status-card__sub">${escapeHtml(desires.subline || "")}</p>
      ${desireList ? `<ul class="desire-lines">${desireList}</ul>` : ""}
    </article>

    <article class="status-card is-updated">
      <span class="status-card__label">${escapeHtml(journey.headline)}</span>
      <p class="status-card__body">${escapeHtml(journey.body)}</p>
      ${journeyList ? `<ul class="journey-list">${journeyList}</ul>` : ""}
    </article>

    <article class="status-card is-updated">
      <span class="status-card__label">${escapeHtml(social.headline)}</span>
      <p class="status-card__body">${escapeHtml(social.body)}</p>
      ${socialTags ? `<div class="tag-row">${socialTags}</div>` : ""}
    </article>`;

  window.setTimeout(() => {
    root.querySelectorAll(".status-card.is-updated").forEach((card) => {
      card.classList.remove("is-updated");
    });
  }, 700);
}

function renderCamera(data) {
  const root = document.getElementById("visual-feed");
  if (!root) return;
  if (data.error) {
    root.innerHTML = `<p class="error">視界はまだ届いていない… (${escapeHtml(data.error)})</p>`;
    return;
  }
  if (!data.image_base64) {
    root.innerHTML = '<p class="placeholder">いまは、静かな壁だけ</p>';
    return;
  }
  const preset = data.camera_preset ? ` · ${escapeHtml(data.camera_preset)}` : "";
  root.innerHTML = `<img src="data:image/jpeg;base64,${data.image_base64}" alt="こよりの視界${preset}" loading="lazy" />`;
}

async function refreshChat({ force = false } = {}) {
  if (sendInProgress && !force) return;
  if (!activeProjectEncoded || !activeSessionId) {
    const root = document.getElementById("chat-log");
    if (root) root.innerHTML = '<p class="placeholder">セッションを選んでください</p>';
    return;
  }
  try {
    await loadConversationMessages();
  } catch (err) {
    const root = document.getElementById("chat-log");
    if (root) root.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  }
}

async function refreshStatus() {
  try {
    const data = await fetchJson("/api/v1/koyori/status");
    renderStatus(data);
  } catch (err) {
    const root = document.getElementById("status-content");
    if (root) root.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  }
}

async function refreshCamera() {
  try {
    const data = await fetchJson("/api/v1/camera/snapshot");
    renderCamera(data);
  } catch (err) {
    const root = document.getElementById("visual-feed");
    if (root) root.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  }
}

async function refreshAll() {
  await refreshChat();
  void refreshStatus();
  void refreshCamera();
}

setupChatScroll();
setupChatCompose();
setupSessionSwitcher();
updateClock();
setInterval(updateClock, 1000);
initSessions()
  .then(async () => {
    await refreshStatus();
    void refreshCamera();
  })
  .catch((err) => {
    const root = document.getElementById("chat-log");
    if (root) root.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  });
setInterval(refreshAll, REFRESH_MS);
