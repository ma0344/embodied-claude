const REFRESH_MS = 7000;
const SCROLL_PIN_THRESHOLD = 56;
/** Local LLM + MCP can be slow; beyond this, unlock compose and abort upstream. */
const CHAT_SEND_TIMEOUT_MS = 180_000;
const PROJECT_STORAGE_KEY = "koyori-cc-encoded-project";
const SESSION_STORAGE_KEY = "koyori-cc-session-id";
const NATIVE_TOKEN_STORAGE_KEY = "koyori-native-token";
const NATIVE_HIDDEN_SESSIONS_KEY = "koyori-native-hidden-v1";
const NATIVE_SESSIONS_API = "/api/v1/native/sessions";
const SHOW_DEBUG_INJECTION_KEY = "koyori-show-debug-injection";
const KIOSK_LAYOUT_STORAGE_KEY = "koyori-kiosk-layout";

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
let activeRequestId = null;
let sendStartedAt = 0;
let sendTimeoutId = null;
let uiConfig = { chat_backend: "proxy8080", native_chat: false };
let nativeAuthToken = sessionStorage.getItem(NATIVE_TOKEN_STORAGE_KEY) || "";
let nativeSessionList = [];
let showDebugInjection = localStorage.getItem(SHOW_DEBUG_INJECTION_KEY) === "1";

function isNativeChat() {
  return uiConfig.chat_backend === "native" || uiConfig.native_chat === true;
}

function nativePassword() {
  return new URLSearchParams(location.search).get("pw") || "koyori-poc";
}

async function loadUiConfig() {
  const data = await fetchJson("/api/v1/ui-config");
  uiConfig = {
    chat_backend: data.chat_backend || "proxy8080",
    native_chat: Boolean(data.native_chat),
    native_login_path: data.native_login_path || "/api/native/login",
    native_chat_path: data.native_chat_path || "/api/native/chat",
    native_sessions_path: data.native_sessions_path || NATIVE_SESSIONS_API,
  };
}

async function ensureNativeLogin() {
  if (nativeAuthToken) return;
  const res = await fetch(uiConfig.native_login_path || "/api/native/login", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ password: nativePassword() }),
  });
  if (!res.ok) {
    throw new Error(
      `native login → ${res.status}（パスワードが違うかも。?pw= で PRESENCE_CCS_PASSWORD を指定）`,
    );
  }
  const data = await res.json();
  nativeAuthToken = data.token || "";
  if (nativeAuthToken) {
    sessionStorage.setItem(NATIVE_TOKEN_STORAGE_KEY, nativeAuthToken);
  }
}

function clearNativeAuthToken() {
  nativeAuthToken = "";
  sessionStorage.removeItem(NATIVE_TOKEN_STORAGE_KEY);
}

async function validateNativeAuthToken() {
  if (!nativeAuthToken) return;
  try {
    const res = await fetch("/api/native/auth/check", {
      headers: { Authorization: `Bearer ${nativeAuthToken}` },
    });
    if (!res.ok) clearNativeAuthToken();
  } catch {
    // presence-ui unreachable — keep token; send path will surface errors
  }
}

async function postNativeChatRequest(payload, signal) {
  const url = uiConfig.native_chat_path || "/api/native/chat";
  const headers = () => ({
    "Content-Type": "application/json; charset=utf-8",
    Authorization: `Bearer ${nativeAuthToken}`,
  });

  await ensureNativeLogin();
  let response = await fetch(url, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
    signal,
  });
  if (response.status === 401) {
    clearNativeAuthToken();
    await ensureNativeLogin();
    response = await fetch(url, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload),
      signal,
    });
  }
  return response;
}

function applyNativeSessionUi() {
  const bar = document.querySelector(".session-bar");
  if (bar) {
    bar.querySelectorAll("label[for='project-select'], #project-select").forEach((el) => {
      el.hidden = true;
    });
  }
  const reloadButton = document.getElementById("session-reload");
  if (reloadButton) {
    reloadButton.hidden = false;
    reloadButton.title = "JSONL から会話を再読み込み";
  }
  const historyLabel = document.querySelector("label[for='history-select']");
  if (historyLabel) {
    historyLabel.hidden = false;
    historyLabel.textContent = "会話";
  }
  const historySelect = document.getElementById("history-select");
  if (historySelect) historySelect.hidden = false;
  const newBtn = document.getElementById("session-new");
  const deleteBtn = document.getElementById("session-delete");
  const cancelBtn = document.getElementById("chat-cancel");
  if (newBtn) newBtn.hidden = false;
  if (deleteBtn) deleteBtn.hidden = false;
  if (cancelBtn) cancelBtn.hidden = false;
}

function loadNativeHiddenSessions() {
  try {
    const raw = localStorage.getItem(NATIVE_HIDDEN_SESSIONS_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function saveNativeHiddenSessions(hidden) {
  localStorage.setItem(NATIVE_HIDDEN_SESSIONS_KEY, JSON.stringify([...hidden]));
}

function nativeSessionsApiPath() {
  return uiConfig.native_sessions_path || NATIVE_SESSIONS_API;
}

function mapServerSession(row) {
  return {
    sessionId: row.session_id,
    title: row.title || row.session_id?.slice(0, 8) || "",
    preview: row.preview || "",
    updatedAt: row.updated_at || "",
    createdAt: row.updated_at || "",
    messageCount: row.message_count || 0,
  };
}

async function refreshNativeSessionList() {
  const data = await fetchJson(`${nativeSessionsApiPath()}?limit=40`);
  const hidden = loadNativeHiddenSessions();
  nativeSessionList = (data.sessions || [])
    .filter((row) => row.session_id && !hidden.has(row.session_id))
    .map(mapServerSession);
  renderNativeSessionSwitcher();
  return nativeSessionList;
}

async function loadNativeMessagesFromServer(sessionId, { fullRebuild = false } = {}) {
  if (!sessionId) {
    chatMessages = [];
    clearChatLog();
    showChatPlaceholder("まだ会話がありません");
    return;
  }
  const path = `${nativeSessionsApiPath()}/${encodeURIComponent(sessionId)}/messages`;
  const data = await fetchJson(path);
  const fresh = (data.messages || []).map((msg) => ({
    sender: msg.sender,
    message: msg.message,
    timestamp: msg.timestamp || "",
  }));
  if (!fresh.length && !fullRebuild) return;
  applyChatMessages(fresh, { fullRebuild, forceScroll: fullRebuild });
}

function renderNativeSessionSwitcher() {
  const select = document.getElementById("history-select");
  if (!select) return;
  if (!nativeSessionList.length) {
    select.innerHTML = '<option value="">（まだ会話なし）</option>';
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = nativeSessionList
    .map((entry) => {
      const when = formatTimestamp(entry.updatedAt || entry.createdAt);
      const title = entry.title || entry.preview || entry.sessionId.slice(0, 8);
      return `<option value="${escapeHtml(entry.sessionId)}"${
        entry.sessionId === activeSessionId ? " selected" : ""
      }>${escapeHtml(title)} · ${escapeHtml(when)}</option>`;
    })
    .join("");
}

async function selectNativeSession(sessionId, { force = false } = {}) {
  if (!sessionId || (!force && sessionId === activeSessionId && !sendInProgress)) return;
  activeSessionId = sessionId;
  persistActiveSession();
  renderNativeSessionSwitcher();
  chatPinnedToBottom = true;
  renderedMessageKeys = new Set();
  try {
    await loadNativeMessagesFromServer(sessionId, { fullRebuild: true });
  } catch (err) {
    clearChatLog();
    showChatPlaceholder(`履歴の読み込みに失敗: ${err.message}`);
  }
}

function deleteNativeSession() {
  if (!activeSessionId) return;
  if (
    !globalThis.confirm(
      "この会話を一覧から外す？（Claude Code の JSONL ログは ma-home に残る）",
    )
  ) {
    return;
  }
  const hidden = loadNativeHiddenSessions();
  hidden.add(activeSessionId);
  saveNativeHiddenSessions(hidden);
  const removedId = activeSessionId;
  nativeSessionList = nativeSessionList.filter((item) => item.sessionId !== removedId);
  renderNativeSessionSwitcher();
  if (nativeSessionList.length) {
    void selectNativeSession(nativeSessionList[0].sessionId, { force: true });
    return;
  }
  startNewNativeSession();
}

function startNewNativeSession() {
  activeSessionId = null;
  localStorage.removeItem(SESSION_STORAGE_KEY);
  chatMessages = [];
  renderedMessageKeys = new Set();
  clearChatLog();
  showChatPlaceholder("新しい会話を始められる");
  const select = document.getElementById("history-select");
  if (select) select.value = "";
}

async function initNativeSessions() {
  applyNativeSessionUi();
  await validateNativeAuthToken();
  await refreshNativeSessionList();
  activeSessionId = localStorage.getItem(SESSION_STORAGE_KEY) || null;
  activeProjectEncoded = null;
  activeProjectPath = null;
  if (activeSessionId && nativeSessionList.some((item) => item.sessionId === activeSessionId)) {
    await selectNativeSession(activeSessionId, { force: true });
  } else if (nativeSessionList.length) {
    await selectNativeSession(nativeSessionList[0].sessionId, { force: true });
  } else {
    chatMessages = [];
    renderedMessageKeys = new Set();
    clearChatLog();
    showChatPlaceholder("まだ会話がありません");
  }
}

function parseNativeSseBlock(block) {
  const lines = block.split("\n");
  let evt = "message";
  let data = "";
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("event:")) evt = trimmed.slice(6).trim();
    if (trimmed.startsWith("data:")) data = trimmed.slice(5).trim();
  }
  return { evt, data };
}

function applyNativeSessionEvent(payload, userPreview) {
  if (!payload?.session_id || payload.claude_session === false) return;
  activeSessionId = payload.session_id;
  persistActiveSession();
  if (userPreview) {
    const preview = String(userPreview).trim().slice(0, 48);
    let entry = nativeSessionList.find((item) => item.sessionId === activeSessionId);
    if (!entry) {
      entry = {
        sessionId: activeSessionId,
        title: preview.slice(0, 24) || activeSessionId.slice(0, 8),
        preview,
        updatedAt: new Date().toISOString(),
        createdAt: new Date().toISOString(),
        messageCount: 0,
      };
      nativeSessionList.unshift(entry);
    }
    renderNativeSessionSwitcher();
  }
}

function appendAssistantMessage(text) {
  const body = String(text || "").trim();
  if (!body) return;
  const msg = {
    sender: "koyori",
    message: body,
    timestamp: new Date().toISOString(),
  };
  chatMessages = [...chatMessages, msg];
  appendMessagesToDom([msg], { animate: true });
  if (chatPinnedToBottom) scrollChatToBottom();
}

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

/** randomUUID needs a secure context (HTTPS / localhost). Kiosk uses http://ma-home.local. */
function newRequestId() {
  try {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
  } catch {
    // non-secure context (e.g. http://192.168.x.x:8090)
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
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
  await loadUiConfig();
  if (isNativeChat()) {
    await initNativeSessions();
    return;
  }
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
      if (isNativeChat()) {
        void selectNativeSession(historySelect.value, { force: true });
      } else {
        void selectSession(historySelect.value, { force: true });
      }
    });
  }
  if (reloadButton) {
    reloadButton.addEventListener("click", () => {
      if (isNativeChat()) {
        void (async () => {
          await refreshNativeSessionList();
          if (activeSessionId) {
            await loadNativeMessagesFromServer(activeSessionId, { fullRebuild: true });
          }
        })();
        return;
      }
      void loadConversationMessages();
    });
  }
  const newButton = document.getElementById("session-new");
  if (newButton) {
    newButton.addEventListener("click", () => {
      if (!isNativeChat()) return;
      startNewNativeSession();
    });
  }
  const deleteButton = document.getElementById("session-delete");
  if (deleteButton) {
    deleteButton.addEventListener("click", () => {
      if (!isNativeChat()) return;
      deleteNativeSession();
    });
  }
  const cancelButton = document.getElementById("chat-cancel");
  if (cancelButton) {
    cancelButton.addEventListener("click", () => {
      if (!sendInProgress) return;
      activeStreamController?.abort();
      releaseComposeState();
      setChatSendHint("止めた");
    });
  }
}

function displayTextForMessage(msg) {
  const raw = CcMessages.sanitizeDisplayText(msg.message || "");
  if (msg.sender === "ma" && typeof CcMessages.displayMessageText === "function") {
    return CcMessages.displayMessageText(raw, { showDebugInjection });
  }
  return raw;
}

function renderMessageBodyHtml(msg) {
  const body = displayTextForMessage(msg);
  if (typeof ChatMarkdown !== "undefined") {
    return ChatMarkdown.toSafeHtml(body);
  }
  return escapeHtml(body);
}

function setMessageBodyContent(bodyEl, msg) {
  if (!bodyEl) return;
  const html = renderMessageBodyHtml(msg);
  if (html.includes("<")) {
    bodyEl.classList.add("message-body--md");
    bodyEl.innerHTML = html;
  } else {
    bodyEl.classList.remove("message-body--md");
    bodyEl.textContent = displayTextForMessage(msg);
  }
}

function confirmNativeUserMessage(trimmed, timestamp) {
  const userMsg = {
    sender: "ma",
    message: trimmed,
    timestamp: timestamp || new Date().toISOString(),
  };
  chatMessages = [...chatMessages.filter((msg) => !msg._pending), userMsg];
  const root = document.getElementById("chat-log");
  const pendingEl = root?.querySelector(".message.ma.is-pending");
  if (pendingEl) {
    pendingEl.classList.remove("is-pending");
    pendingEl.dataset.messageKey = messageKey(userMsg);
    updateMessageElement(pendingEl, userMsg);
  } else {
    appendMessagesToDom([userMsg], { animate: false });
  }
  renderedMessageKeys = new Set(chatMessages.map(messageKey));
  return userMsg;
}

function refreshChatDisplay() {
  if (!chatMessages.length) return;
  applyChatMessages(chatMessages, { fullRebuild: true, forceScroll: false });
}

function setupDebugInjectionToggle() {
  const toggle = document.getElementById("debug-injection-toggle");
  if (!toggle) return;
  toggle.checked = showDebugInjection;
  toggle.addEventListener("change", () => {
    showDebugInjection = toggle.checked;
    localStorage.setItem(SHOW_DEBUG_INJECTION_KEY, showDebugInjection ? "1" : "0");
    refreshChatDisplay();
  });
}

function messageKey(msg) {
  const body = CcMessages.sanitizeDisplayText(msg.message || "");
  return `${msg.sender}|${body}`;
}

function messageElementForKey(root, key) {
  if (!root || !key) return null;
  return root.querySelector(`[data-message-key="${CSS.escape(key)}"]`);
}

function updateMessageElement(el, msg) {
  const body = CcMessages.sanitizeDisplayText(msg.message || "");
  const bodyEl = el.querySelector(".message-body");
  setMessageBodyContent(bodyEl, msg);
  if (msg.timestamp) {
    const who = msg.sender === "ma" ? "まー" : "こより";
    const label = msg.sender === "ma" ? "M" : "K";
    const meta = el.querySelector(".meta-line");
    if (meta) {
      meta.innerHTML = `<span class="sender-badge">${label}</span> ${who} · ${formatTimestamp(msg.timestamp)}`;
    }
  }
  el.classList.remove("is-pending", "is-streaming", "is-thinking");
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
        <div class="message-body"></div>`;
  setMessageBodyContent(el.querySelector(".message-body"), { ...msg, message: body });
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
    const existingEl = messageElementForKey(root, key);
    if (renderedMessageKeys.has(key) || existingEl) {
      if (existingEl) {
        updateMessageElement(existingEl, msg);
        renderedMessageKeys.add(key);
      }
      continue;
    }
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
    setMessageBodyContent(
      streamingBubbleEl.querySelector(".message-body"),
      { sender: "koyori", message: body },
    );
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

function setChatThinking(active, label = "送ってる…") {
  const root = document.getElementById("chat-log");
  if (!root) return;

  const existing = root.querySelector(".message.is-thinking");
  if (active) {
    if (existing) {
      const body = existing.querySelector(".message-body");
      if (body && label) body.textContent = label;
      return;
    }
    const thinking = buildMessageElement(
      {
        sender: "koyori",
        message: label,
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

const MCP_ACTIVITY_ICONS = {
  remember: "📌",
  recall: "💭",
  see: "👁",
  listen: "👂",
  say: "🔊",
  reflect: "📝",
  mcp: "🔧",
};

function appendMcpActivityLine(event) {
  const root = document.getElementById("chat-log");
  if (!root || !event) return;
  root.querySelector(".placeholder")?.remove();
  const el = document.createElement("div");
  el.className = `message mcp-activity${event.ok === false ? " is-error" : ""}`;
  const icon = MCP_ACTIVITY_ICONS[event.kind] || MCP_ACTIVITY_ICONS.mcp;
  el.textContent = `${icon} ${event.label || "MCP"}`;
  if (event.detail) el.title = event.detail;
  root.appendChild(el);
  if (chatPinnedToBottom) scrollChatToBottom();
}

function appendActivityLine(event) {
  appendMcpActivityLine(event);
}

function setComposeEnabled(enabled) {
  const input = document.getElementById("chat-input");
  const button = document.getElementById("chat-send");
  if (input) input.disabled = !enabled;
  if (button) button.disabled = !enabled;
}

function setChatSendHint(text) {
  const hint = document.getElementById("chat-hint");
  if (!hint) return;
  if (text) {
    hint.textContent = text;
    return;
  }
  updateChatHint();
}

async function abortActiveChatRequest() {
  if (isNativeChat()) return;
  const requestId = activeRequestId;
  if (!requestId) return;
  try {
    await fetch(`/api/abort/${encodeURIComponent(requestId)}`, { method: "POST" });
  } catch {
    // best-effort
  }
}

function releaseComposeState() {
  if (sendTimeoutId) {
    clearTimeout(sendTimeoutId);
    sendTimeoutId = null;
  }
  activeStreamController = null;
  activeRequestId = null;
  sendStartedAt = 0;
  sendInProgress = false;
  sendTargetSessionId = null;
  setComposeEnabled(true);
  clearStreamingBubble();
  setChatThinking(false);
  setChatSendHint("");
}

function forceResetComposeIfStuck() {
  if (!sendInProgress || !sendStartedAt) return;
  if (Date.now() - sendStartedAt < CHAT_SEND_TIMEOUT_MS) return;
  void abortActiveChatRequest();
  activeStreamController?.abort();
  releaseComposeState();
  const root = document.getElementById("chat-log");
  if (root && !root.querySelector(".message.send-timeout")) {
    const note = document.createElement("p");
    note.className = "error send-timeout";
    note.textContent = "応答が長すぎて送信を解除した。もう一度送ってみて。";
    root.appendChild(note);
  }
}

async function sendChatMessageNative(trimmed) {
  const optimistic = {
    sender: "ma",
    message: trimmed,
    timestamp: new Date().toISOString(),
    _pending: true,
  };
  chatMessages = [...chatMessages, optimistic];
  appendMessagesToDom([optimistic], { animate: true });
  if (chatPinnedToBottom) scrollChatToBottom();
  setChatThinking(true, "送ってる…");
  if (activeSessionId) {
    applyNativeSessionEvent({ session_id: activeSessionId, claude_session: true }, trimmed);
  }

  sendStartedAt = Date.now();
  activeStreamController = new AbortController();
  sendTimeoutId = setTimeout(() => {
    activeStreamController?.abort();
  }, CHAT_SEND_TIMEOUT_MS);
  setChatSendHint("返事を待ってる…");

  try {
    const response = await postNativeChatRequest(
      {
        prompt: trimmed,
        session_id: activeSessionId || undefined,
      },
      activeStreamController.signal,
    );

    if (response.status === 401) {
      throw new Error("native login に失敗した。?pw= でパスワードを確認してね");
    }
    if (!response.ok) {
      throw new Error(`${uiConfig.native_chat_path || "/api/native/chat"} → ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let assistantDraft = "";
    let doneMeta = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const block of parts) {
        const { evt, data } = parseNativeSseBlock(block);
        if (evt === "session" && data) {
          try {
            applyNativeSessionEvent(JSON.parse(data), trimmed);
          } catch {
            // ignore malformed session event
          }
        }
        if (evt === "text" && data) {
          try {
            const payload = JSON.parse(data);
            const piece = payload.content || "";
            if (piece) {
              setChatThinking(false);
              assistantDraft += piece;
              updateStreamingBubble(assistantDraft);
            }
          } catch {
            // ignore malformed text event
          }
        }
        if (evt === "error" && data) {
          let message = data;
          try {
            const payload = JSON.parse(data);
            message = payload.message || payload.error || data;
          } catch {
            // keep raw data
          }
          throw new Error(message);
        }
        if (evt === "done" && data) {
          try {
            doneMeta = JSON.parse(data);
          } catch {
            doneMeta = {};
          }
        }
      }
    }

    clearStreamingBubble();
    setChatThinking(false);

    if (doneMeta?.silent && !assistantDraft.trim()) {
      assistantDraft = "（いまは静かにしている）";
    }

    confirmNativeUserMessage(trimmed, optimistic.timestamp);

    if (assistantDraft.trim()) {
      appendAssistantMessage(assistantDraft);
    }

    try {
      await refreshNativeSessionList();
      if (activeSessionId) {
        await loadNativeMessagesFromServer(activeSessionId, { fullRebuild: true });
      }
    } catch {
      // JSONL flush can lag one beat; 7s poll will catch up
    }

    await refreshStatus();
  } catch (err) {
    clearStreamingBubble();
    setChatThinking(false);
    confirmNativeUserMessage(trimmed, optimistic.timestamp);
    throw err;
  }
}

async function sendChatMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;
  if (sendInProgress) {
    setChatSendHint("まだ前の送信を処理中。しばらく待つか、再読み込みしてね");
    return;
  }

  sendInProgress = true;
  setComposeEnabled(false);
  chatPinnedToBottom = true;

  try {
    if (isNativeChat()) {
      await sendChatMessageNative(trimmed);
      return;
    }

  const targetSessionId = syncActiveSessionFromSelect();
  sendTargetSessionId = targetSessionId || null;
    const optimistic = {
      sender: "ma",
      message: trimmed,
      timestamp: new Date().toISOString(),
      _pending: true,
    };
    chatMessages = [...chatMessages, optimistic];
    appendMessagesToDom([optimistic], { animate: true });
    if (chatPinnedToBottom) scrollChatToBottom();
    setChatThinking(true, "送ってる…");

    const requestId = newRequestId();
    activeRequestId = requestId;
    sendStartedAt = Date.now();
    activeStreamController = new AbortController();
    sendTimeoutId = setTimeout(() => {
      void abortActiveChatRequest();
      activeStreamController?.abort();
    }, CHAT_SEND_TIMEOUT_MS);
    setChatSendHint("返事を待ってる…");

    const payload = {
      message: trimmed,
      requestId,
      workingDirectory: activeProjectPath || undefined,
      sessionId: targetSessionId || undefined,
      // Kiosk has no :8080 permission dialog; gateway also sets acceptEdits server-side.
      permissionMode: "acceptEdits",
    };
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8", Accept: "application/x-ndjson" },
      body: JSON.stringify(payload),
      signal: activeStreamController.signal,
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

        if (chunk.type === "room_progress") {
          setChatThinking(true, chunk.label || "考えてる…");
        } else if (chunk.type === "mcp_activity") {
          appendMcpActivityLine(chunk);
        } else if (chunk.type === "room_activity") {
          appendMcpActivityLine(chunk);
        } else if (chunk.type === "social_silent") {
          setChatThinking(false);
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
          if (chunk.data?.type === "assistant" && piece) {
            setChatThinking(false);
            assistantDraft = (assistantDraft || "") + piece;
          }
        }

        if (assistantDraft) {
          updateStreamingBubble(assistantDraft);
        }
      }
    }

    clearStreamingBubble();
    setChatThinking(false);

    if (activeProjectEncoded && activeSessionId) {
      await loadConversationMessages({ fullRebuild: true });
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
      const message =
        err.name === "AbortError"
          ? "応答がタイムアウトした。もう一度送ってみて。"
          : `送信できなかった: ${err.message}`;
      note.textContent = message;
      root.appendChild(note);
    }
  } finally {
    if (sendTimeoutId) {
      clearTimeout(sendTimeoutId);
      sendTimeoutId = null;
    }
    activeStreamController = null;
    activeRequestId = null;
    sendStartedAt = 0;
    sendInProgress = false;
    sendTargetSessionId = null;
    setComposeEnabled(true);
    clearStreamingBubble();
    setChatThinking(false);
    setChatSendHint("");
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
    void sendChatMessage(text).catch((err) => {
      console.error("sendChatMessage failed", err);
    });
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
  if (isNativeChat()) {
    try {
      await refreshNativeSessionList();
      if (activeSessionId) {
        await loadNativeMessagesFromServer(activeSessionId, { fullRebuild: false });
      }
    } catch {
      // polling must not break the room UI
    }
    return;
  }
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

function setupKioskLayout() {
  const room = document.querySelector(".room");
  if (!room) return;
  const params = new URLSearchParams(location.search);
  if (params.get("kiosk") === "1") {
    room.classList.add("room--kiosk");
    localStorage.setItem(KIOSK_LAYOUT_STORAGE_KEY, "1");
    return;
  }
  if (params.get("kiosk") === "0") {
    room.classList.remove("room--kiosk");
    localStorage.removeItem(KIOSK_LAYOUT_STORAGE_KEY);
    return;
  }
  if (localStorage.getItem(KIOSK_LAYOUT_STORAGE_KEY) === "1") {
    room.classList.add("room--kiosk");
  }
}

setupKioskLayout();
setupChatScroll();
setupChatCompose();
setupDebugInjectionToggle();
releaseComposeState();
document.addEventListener("visibilitychange", forceResetComposeIfStuck);
setInterval(forceResetComposeIfStuck, 15_000);
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
