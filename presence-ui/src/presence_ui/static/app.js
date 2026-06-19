const REFRESH_MS = 7000;
const OUTBOUND_POLL_MS_DEFAULT = 3000;
const OUTBOUND_SINCE_KEY = "koyori-outbound-since";
const ROOM_SAY_SINCE_KEY = "koyori-room-say-since";
const OUTBOUND_CLIENT_ID_KEY = "koyori-outbound-client-id";
const OUTBOUND_BROWSER_NOTIFIED_KEY = "koyori-outbound-browser-notified";
const SCROLL_PIN_THRESHOLD = 56;
/** Local LLM + MCP can be slow; beyond this, unlock compose and abort upstream. */
const CHAT_SEND_TIMEOUT_MS = 180_000;
const PROJECT_STORAGE_KEY = "koyori-cc-encoded-project";
const SESSION_STORAGE_KEY = "koyori-cc-session-id";
const NATIVE_TOKEN_STORAGE_KEY = "koyori-native-token";
const NATIVE_HIDDEN_SESSIONS_KEY = "koyori-native-hidden-v1";
const NATIVE_SESSIONS_API = "/api/v1/native/sessions";
const NATIVE_HIDDEN_API = "/api/v1/native/hidden";
const SHOW_DEBUG_INJECTION_KEY = "koyori-show-debug-injection";
const KIOSK_LAYOUT_STORAGE_KEY = "koyori-kiosk-layout";
const KIOSK_AUDIO_VOLUME_KEY = "koyori-kiosk-audio-volume";
const KIOSK_AUDIO_VOLUME_DEFAULT = 1;
const KIOSK_SLEEP_MINUTES_KEY = "koyori-kiosk-sleep-minutes";
const KIOSK_SLEEP_MINUTES_DEFAULT = 10;
const KIOSK_SLEEP_WAKE_ON_NOTIFY_KEY = "koyori-kiosk-sleep-wake-on-notify";
const CONTEXT_RAIL_PINS_KEY = "koyori-context-rail-pins";
const STATUS_EXPAND_KEY = "koyori-status-expand";
const INBOUND_SEEDS_STORAGE_KEY = "koyori-inbound-seeds-v1";
const EPISODE_IDLE_MINUTES_DEFAULT = 20;

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
let uiConfig = { chat_backend: "proxy8080", native_chat: false, display_timezone: "Asia/Tokyo" };
let nativeAuthToken = sessionStorage.getItem(NATIVE_TOKEN_STORAGE_KEY) || "";
let nativeSessionList = [];
let showDebugInjection = localStorage.getItem(SHOW_DEBUG_INJECTION_KEY) === "1";
let roomDrawerOpen = false;
let contextRailPins = loadContextRailPins();
let outboundPollTimer = null;
let roomSayPollTimer = null;
const roomSayInFlight = new Set();
const roomSayPlayed = new Set();
let outboundEventSource = null;
let outboundSseConnected = false;
let speechUnlocked = false;
let wakeLock = null;
let idleTimer = null;
let idleActive = false;
let roomInboundQueue = [];
let roomInboundCurrent = null;
/** A4j+: first user send after「返事する」carries inbound meta to gateway. */
let pendingInboundReply = null;
let episodeIdleTimer = null;

function loadContextRailPins() {
  const defaults = { vision: true, status: false };
  try {
    const raw = localStorage.getItem(CONTEXT_RAIL_PINS_KEY);
    if (!raw) return { ...defaults };
    const parsed = JSON.parse(raw);
    return {
      vision: parsed.vision !== false,
      status: parsed.status === true,
    };
  } catch {
    return { ...defaults };
  }
}

function saveContextRailPins() {
  localStorage.setItem(CONTEXT_RAIL_PINS_KEY, JSON.stringify(contextRailPins));
}

function isContextRailPinned(kind) {
  return Boolean(contextRailPins[kind]);
}

function setContextRailPin(kind, pinned) {
  if (!Object.hasOwn(contextRailPins, kind)) return;
  contextRailPins[kind] = pinned;
  saveContextRailPins();
  applyContextRailLayout();
  void refreshStatus();
  void refreshCamera();
}

function applyContextRailLayout() {
  const room = document.querySelector(".room");
  const rail = document.getElementById("context-rail");
  if (!room || !rail) return;

  const hasRail = isKioskLayout() && (isContextRailPinned("vision") || isContextRailPinned("status"));
  room.classList.toggle("room--has-context-rail", hasRail);
  rail.hidden = !hasRail;

  for (const kind of ["vision", "status"]) {
    const block = document.getElementById(`context-rail-${kind}`);
    const pinned = isKioskLayout() && isContextRailPinned(kind);
    if (block) block.hidden = !pinned;

    for (const btn of document.querySelectorAll(`[data-rail-pin="${kind}"]`)) {
      btn.setAttribute("aria-pressed", pinned ? "true" : "false");
      btn.textContent = pinned ? "固定中" : "固定";
    }
  }
}

function setupContextRail() {
  if (!document.body.dataset.contextRailBound) {
    document.body.dataset.contextRailBound = "1";
    document.addEventListener("click", (event) => {
      const pinBtn = event.target.closest("[data-rail-pin]");
      if (pinBtn) {
        const kind = pinBtn.getAttribute("data-rail-pin");
        if (!kind) return;
        setContextRailPin(kind, !isContextRailPinned(kind));
        return;
      }
      const unpinBtn = event.target.closest("[data-rail-unpin]");
      if (unpinBtn) {
        const kind = unpinBtn.getAttribute("data-rail-unpin");
        if (!kind) return;
        setContextRailPin(kind, false);
      }
    });
  }
  applyContextRailLayout();
}

function isKioskLayout() {
  return Boolean(document.querySelector(".room")?.classList.contains("room--kiosk"));
}

function isDebugMode() {
  return new URLSearchParams(location.search).get("debug") === "1";
}

function relocateSessionControls() {
  const block = document.getElementById("session-controls");
  const home = document.getElementById("session-controls-home");
  const drawer = document.getElementById("drawer-session-slot");
  if (!block || !home || !drawer) return;
  const target = isKioskLayout() ? drawer : home;
  if (block.parentElement !== target) {
    target.appendChild(block);
  }
}

function applyDebugInjectionVisibility() {
  const wrap = document.getElementById("debug-injection-wrap");
  if (!wrap) return;
  wrap.hidden = isKioskLayout() && !isDebugMode();
}

function ensureSessionControlsMounted() {
  const block = document.getElementById("session-controls");
  if (!block || block.dataset.mounted === "1") return;
  block.dataset.mounted = "1";
  block.hidden = false;
  relocateSessionControls();
  applyDebugInjectionVisibility();
}

function setRoomDrawerOpen(open) {
  const drawer = document.getElementById("room-drawer");
  const openBtn = document.getElementById("room-drawer-open");
  if (!drawer) return;
  roomDrawerOpen = open;
  drawer.classList.toggle("room-drawer--open", open);
  drawer.setAttribute("aria-hidden", open ? "false" : "true");
  if (openBtn) {
    openBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  document.body.classList.toggle("room-drawer-body-lock", open && isKioskLayout());
  if (open) {
    document.getElementById("room-drawer-close")?.focus();
  } else if (openBtn && isKioskLayout()) {
    openBtn.focus();
  }
}

function setupRoomDrawer() {
  const openBtn = document.getElementById("room-drawer-open");
  const closeBtn = document.getElementById("room-drawer-close");
  const backdrop = document.getElementById("room-drawer-backdrop");
  const reloadBtn = document.getElementById("page-reload");

  if (openBtn && !openBtn.dataset.bound) {
    openBtn.dataset.bound = "1";
    openBtn.addEventListener("click", () => setRoomDrawerOpen(true));
  }
  if (closeBtn && !closeBtn.dataset.bound) {
    closeBtn.dataset.bound = "1";
    closeBtn.addEventListener("click", () => setRoomDrawerOpen(false));
  }
  if (backdrop && !backdrop.dataset.bound) {
    backdrop.dataset.bound = "1";
    backdrop.addEventListener("click", () => setRoomDrawerOpen(false));
  }
  if (reloadBtn && !reloadBtn.dataset.bound) {
    reloadBtn.dataset.bound = "1";
    reloadBtn.addEventListener("click", () => {
      setRoomDrawerOpen(false);
      globalThis.location.reload();
    });
  }

  if (openBtn) {
    openBtn.hidden = !isKioskLayout();
  }
  if (!isKioskLayout()) {
    setRoomDrawerOpen(false);
  }

  if (!document.body.dataset.roomDrawerKeyBound) {
    document.body.dataset.roomDrawerKeyBound = "1";
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && roomDrawerOpen) {
        setRoomDrawerOpen(false);
      }
    });
  }
}

function visualFeedTargets() {
  if (isKioskLayout()) {
    const targets = [];
    const drawer = document.getElementById("visual-feed-drawer");
    if (drawer) targets.push(drawer);
    if (isContextRailPinned("vision")) {
      const rail = document.getElementById("visual-feed-rail");
      if (rail) targets.push(rail);
    }
    return targets;
  }
  const main = document.getElementById("visual-feed");
  return main ? [main] : [];
}

function statusTargets() {
  if (isKioskLayout()) {
    const targets = [];
    const drawer = document.getElementById("status-content-drawer");
    if (drawer) targets.push(drawer);
    if (isContextRailPinned("status")) {
      const rail = document.getElementById("status-content-rail");
      if (rail) targets.push(rail);
    }
    return targets;
  }
  const main = document.getElementById("status-content");
  return main ? [main] : [];
}

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
    display_timezone: data.display_timezone || "Asia/Tokyo",
    outbound_pending_path: data.outbound_pending_path || "/api/v1/outbound/pending",
    outbound_ack_path: data.outbound_ack_path || "/api/v1/outbound/ack",
    outbound_stream_path: data.outbound_stream_path || "/api/v1/outbound/stream",
    outbound_sse_enabled: data.outbound_sse_enabled !== false,
    outbound_surface_tts_enabled: Boolean(data.outbound_surface_tts_enabled),
    surface_tts_ready: Boolean(data.surface_tts_ready),
    surface_tts_status: data.surface_tts_status || "",
    surface_tts_synthesize_path: data.surface_tts_synthesize_path || "/api/v1/tts/surface",
    kiosk_primary_enabled: data.kiosk_primary_enabled !== false,
    kiosk_primary_active: Boolean(data.kiosk_primary_active),
    outbound_poll_ms: Number(data.outbound_poll_ms) || OUTBOUND_POLL_MS_DEFAULT,
    outbound_poll_fallback_ms: Number(data.outbound_poll_fallback_ms) || 60000,
    outbound_web_speech_suppress_on_localhost: Boolean(
      data.outbound_web_speech_suppress_on_localhost,
    ),
    episode_idle_close_minutes:
      Number(data.episode_idle_close_minutes) || EPISODE_IDLE_MINUTES_DEFAULT,
  };
  syncKioskTtsHealthFromConfig();
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

function displayTimeZone() {
  return uiConfig.display_timezone || "Asia/Tokyo";
}

async function migrateNativeHiddenToServer() {
  const hidden = loadNativeHiddenSessions();
  if (!hidden.size) return;
  try {
    await fetch(NATIVE_HIDDEN_API, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ session_ids: [...hidden] }),
    });
    localStorage.removeItem(NATIVE_HIDDEN_SESSIONS_KEY);
  } catch {
    // keep local ids until next successful migrate
  }
}

async function hideNativeSessionOnServer(sessionId) {
  const res = await fetch(
    `${nativeSessionsApiPath()}/${encodeURIComponent(sessionId)}/hide`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`hide session → ${res.status}`);
  }
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
  nativeSessionList = (data.sessions || [])
    .filter((row) => row.session_id)
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
  const fresh = mergeInboundSeedMessages(
    sessionId,
    (data.messages || []).map((msg) => ({
      sender: msg.sender,
      message: msg.message,
      timestamp: msg.timestamp || "",
    })),
  );
  if (!fresh.length && !fullRebuild) return;
  applyChatMessages(fresh, { fullRebuild, forceScroll: fullRebuild });
  resetEpisodeIdleTimer();
}

function loadInboundSeedMap() {
  try {
    const raw = sessionStorage.getItem(INBOUND_SEEDS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveInboundSeed(sessionId, text, timestamp) {
  if (!sessionId || !text) return;
  const map = loadInboundSeedMap();
  map[sessionId] = { text, timestamp: timestamp || new Date().toISOString() };
  try {
    sessionStorage.setItem(INBOUND_SEEDS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // quota — non-fatal
  }
}

function mergeInboundSeedMessages(sessionId, messages) {
  const seed = loadInboundSeedMap()[sessionId];
  if (!seed?.text) return messages;
  const trimmed = String(seed.text).trim();
  if (!trimmed) return messages;
  const already = messages.some(
    (msg) => msg.sender === "koyori" && String(msg.message || "").trim() === trimmed,
  );
  if (already) return messages;
  return [
    {
      sender: "koyori",
      message: trimmed,
      timestamp: seed.timestamp || "",
      _inboundSeed: true,
    },
    ...messages,
  ];
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

async function deleteNativeSession() {
  if (!activeSessionId) return;
  if (
    !globalThis.confirm(
      "この会話を一覧から外す？（全デバイスで非表示。JSONL ログは ma-home に残る）",
    )
  ) {
    return;
  }
  const removedId = activeSessionId;
  try {
    await hideNativeSessionOnServer(removedId);
  } catch (err) {
    globalThis.alert(`一覧から外せなかった: ${err.message}`);
    return;
  }
  await refreshNativeSessionList();
  if (nativeSessionList.length) {
    await selectNativeSession(nativeSessionList[0].sessionId, { force: true });
    return;
  }
  startNewNativeSession();
}

function startNewNativeSession() {
  void startNewNativeSessionAsync();
}

async function startNewNativeSessionAsync() {
  await closeEpisodeBeforeNewSession();
  activeSessionId = null;
  localStorage.removeItem(SESSION_STORAGE_KEY);
  chatMessages = [];
  renderedMessageKeys = new Set();
  clearChatLog();
  showChatPlaceholder("新しい会話を始められる");
  const select = document.getElementById("history-select");
  if (select) select.value = "";
  clearEpisodeIdleTimer();
}

function collectEpisodeTurns() {
  return chatMessages
    .filter((msg) => !msg._pending && !msg._thinking && !msg._streaming)
    .map((msg) => ({
      sender: msg.sender,
      message: displayTextForMessage(msg),
      timestamp: msg.timestamp || null,
    }))
    .filter((turn) => turn.message && (turn.sender === "ma" || turn.sender === "koyori"));
}

async function closeEpisodeForCurrentSession({ trigger = "manual" } = {}) {
  const sessionId = activeSessionId;
  if (!sessionId || !chatMessages.length) return;
  const turns = collectEpisodeTurns();
  if (!turns.length) return;
  try {
    await postJson("/api/v1/stm/close-episode", {
      person_id: "ma",
      session_id: sessionId,
      trigger,
      turns,
    });
  } catch (err) {
    console.warn("STM episode close failed:", err);
  }
}

async function closeEpisodeBeforeNewSession() {
  await closeEpisodeForCurrentSession({ trigger: "new_session" });
}

function episodeIdleCloseMs() {
  const minutes = Number(uiConfig.episode_idle_close_minutes) || EPISODE_IDLE_MINUTES_DEFAULT;
  return Math.max(5, minutes) * 60 * 1000;
}

function clearEpisodeIdleTimer() {
  if (episodeIdleTimer) {
    clearTimeout(episodeIdleTimer);
    episodeIdleTimer = null;
  }
}

function resetEpisodeIdleTimer() {
  clearEpisodeIdleTimer();
  if (!isNativeChat() || !activeSessionId || sendInProgress) return;
  if (!collectEpisodeTurns().length) return;
  episodeIdleTimer = setTimeout(() => {
    void closeEpisodeForCurrentSession({ trigger: "idle" });
  }, episodeIdleCloseMs());
}

async function initNativeSessions() {
  applyNativeSessionUi();
  await validateNativeAuthToken();
  await migrateNativeHiddenToServer();
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
  if (pendingInboundReply?.text) {
    saveInboundSeed(
      activeSessionId,
      pendingInboundReply.text,
      pendingInboundReply.ts || new Date().toISOString(),
    );
  }
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
  return date.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: displayTimeZone(),
  });
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
      timeZone: displayTimeZone(),
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

function escapeAttr(text) {
  return escapeHtml(text).replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

/** randomUUID needs a secure context (HTTPS / localhost). Room UI often uses http://ma-home.local. */
function newRandomToken() {
  try {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
  } catch {
    // non-secure context (e.g. http://192.168.x.x:8090)
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 11)}`;
}

function newRequestId() {
  return `req-${newRandomToken()}`;
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
  relocateSessionControls();
  applyContextRailLayout();
  applyDebugInjectionVisibility();
  setupOutboundPoll();
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
      if (isKioskLayout()) setRoomDrawerOpen(false);
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

async function copyTextToClipboard(text) {
  const trimmed = (text || "").trim();
  if (!trimmed) return false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(trimmed);
      return true;
    }
  } catch {
    /* fallback below */
  }
  const ta = document.createElement("textarea");
  ta.value = trimmed;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(ta);
  }
}

function wireMessageCopyButton(el, msg) {
  if (!el || msg._thinking || msg._pending) return;
  const btn = el.querySelector(".message-copy-btn");
  if (!btn) return;
  const text = displayTextForMessage(msg);
  if (!text.trim()) {
    btn.hidden = true;
    return;
  }
  btn.hidden = false;
  btn.onclick = async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const ok = await copyTextToClipboard(text);
    if (ok) {
      btn.classList.add("is-copied");
      const prev = btn.textContent;
      btn.textContent = "コピー済";
      window.setTimeout(() => {
        btn.classList.remove("is-copied");
        btn.textContent = prev || "コピー";
      }, 1500);
      setChatSendHint("コピーした");
    } else {
      setChatSendHint("コピーできなかった");
    }
  };
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
  if (msg.nudge_id) return `outbound|${msg.nudge_id}`;
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
      meta.innerHTML = `<span class="meta-line-main"><span class="sender-badge">${label}</span> ${who} · ${formatTimestamp(msg.timestamp)}</span><button type="button" class="message-copy-btn" title="メッセージをコピー" aria-label="メッセージをコピー">コピー</button>`;
    }
  }
  wireMessageCopyButton(el, msg);
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
  el.innerHTML = `<span class="meta-line"><span class="meta-line-main"><span class="sender-badge">${label}</span> ${who} · ${formatTimestamp(msg.timestamp)}</span><button type="button" class="message-copy-btn" title="メッセージをコピー" aria-label="メッセージをコピー">コピー</button></span>
        <div class="message-body"></div>`;
  setMessageBodyContent(el.querySelector(".message-body"), { ...msg, message: body });
  wireMessageCopyButton(el, { ...msg, message: body });
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

function resizeChatInput(input) {
  if (!input) return;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 96)}px`;
}

function restoreChatDraft(text) {
  const input = document.getElementById("chat-input");
  if (!input || !text) return;
  input.value = text;
  resizeChatInput(input);
  input.focus();
}

function clearChatDraft() {
  const input = document.getElementById("chat-input");
  if (!input) return;
  input.value = "";
  input.style.height = "auto";
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
    const requestPayload = {
      prompt: trimmed,
      session_id: activeSessionId || undefined,
    };
    if (pendingInboundReply?.text) {
      requestPayload.inbound_nudge = pendingInboundReply.text;
      if (pendingInboundReply.nudge_id) {
        requestPayload.inbound_nudge_id = pendingInboundReply.nudge_id;
      }
    }

    const response = await postNativeChatRequest(
      requestPayload,
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
    pendingInboundReply = null;
    resetEpisodeIdleTimer();
  } catch (err) {
    clearStreamingBubble();
    setChatThinking(false);
    confirmNativeUserMessage(trimmed, optimistic.timestamp);
    pendingInboundReply = null;
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
  clearChatDraft();
  chatPinnedToBottom = true;
  // C11g: 送信でアイドルタイマーをリセット
  document.dispatchEvent(new Event("chat-send"));

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
    restoreChatDraft(trimmed);
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
    void sendChatMessage(input.value);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  input.addEventListener("input", () => {
    resizeChatInput(input);
  });
}

function buildStatusCard({ id, label, icon, extraClass = "", innerHtml, open }) {
  const openClass = open ? " status-card--open" : "";
  const expanded = open ? "true" : "false";
  const iconHtml = icon
    ? `<span class="status-card__icon" aria-hidden="true">${escapeHtml(icon)}</span>`
    : "";
  return `
    <article class="status-card status-card--expandable${extraClass}${openClass} is-updated" data-status-card="${escapeHtml(id)}">
      <button type="button" class="status-card__toggle" aria-expanded="${expanded}">
        ${iconHtml}
        <span class="status-card__toggle-label">${escapeHtml(label)}</span>
        <span class="status-card__chevron" aria-hidden="true"></span>
      </button>
      <div class="status-card__panel"${open ? "" : " hidden"}>
        ${innerHtml}
      </div>
    </article>`;
}

function getStatusExpandPrefs() {
  try {
    const raw = localStorage.getItem(STATUS_EXPAND_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function setStatusExpandPref(id, open) {
  const prefs = getStatusExpandPrefs();
  prefs[id] = open;
  localStorage.setItem(STATUS_EXPAND_KEY, JSON.stringify(prefs));
}

function isStatusCardOpen(id, compactDefault) {
  const prefs = getStatusExpandPrefs();
  if (Object.hasOwn(prefs, id)) return Boolean(prefs[id]);
  return !compactDefault;
}

function syncStatusCardOpen(card, open) {
  if (!card) return;
  const btn = card.querySelector(".status-card__toggle");
  const panel = card.querySelector(".status-card__panel");
  card.classList.toggle("status-card--open", open);
  if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
  if (panel) panel.hidden = !open;
}

function setupStatusCardExpand() {
  if (document.body.dataset.statusExpandBound) return;
  document.body.dataset.statusExpandBound = "1";
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".status-card__toggle");
    if (!btn) return;
    const card = btn.closest(".status-card--expandable");
    if (!card) return;
    const id = card.getAttribute("data-status-card");
    const open = !card.classList.contains("status-card--open");
    if (id) {
      for (const peer of document.querySelectorAll(`[data-status-card="${id}"]`)) {
        syncStatusCardOpen(peer, open);
      }
      setStatusExpandPref(id, open);
    } else {
      syncStatusCardOpen(card, open);
    }
  });
}

function buildStatusHtml(data, { compact = false } = {}) {
  const temp = KoyoriVoice.formatTemperature(data.temperature);
  const desires = KoyoriVoice.formatDesires(data.desires, data.dominant_desire);
  const social = KoyoriVoice.formatSocialVibe(data.social_state);
  const journey = KoyoriVoice.formatJourney(data.active_arcs);
  const recent = KoyoriVoice.formatExperiences(data.recent_experiences);
  const innerVoice = KoyoriVoice.formatLiveInnerVoice(data.live_inner_voice);
  const pulse = KoyoriVoice.formatPulse(data.agent_pulse);
  const plan = KoyoriVoice.formatPlanPreview(data.autonomous_plan);
  const open = (id) => {
    if (id === "inner_voice" && compact) return true;
    return isStatusCardOpen(id, compact);
  };
  const reminders = data.reminders || [];

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

  const recentList = recent.items
    .map((item) => {
      const when = item.ts ? formatTimestamp(item.ts) : "";
      return `<li><span class="tag">${escapeHtml(item.kind)}</span> ${
        when ? `<time class="status-time">${escapeHtml(when)}</time> ` : ""
      }${escapeHtml(item.summary || "")}</li>`;
    })
    .join("");

  const pulseLines = pulse.lines
    .map((line) => `<p class="status-card__sub">${escapeHtml(line)}</p>`)
    .join("");

  const planLines = plan.lines
    .map((line) => `<p class="status-card__sub">${escapeHtml(line)}</p>`)
    .join("");

  const tempReadings = (data.temperature?.readings || [])
    .slice(0, 4)
    .map(
      (row) =>
        `<li>${escapeHtml(row.name)}: ${Number(row.celsius).toFixed(1)}°C</li>`,
    )
    .join("");

  const socialTags = social.tags
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join("");

  const reminderItems = reminders.length
    ? reminders
        .map((r) => {
          const speak = (r.speak_line || "").replaceAll("\n", " ").trim();
          const due = r.due_at ? formatTimestamp(r.due_at) : "";
          const title = speak || r.title || "";
          return `
            <li class="reminder-item" data-reminder-item data-reminder-id="${escapeHtml(
              r.commitment_id
            )}">
              <div class="reminder-meta">
                <strong>${escapeHtml(due || "—")}</strong>
                <span class="reminder-title">${escapeHtml(title)}</span>
              </div>
              <div class="reminder-edit">
                <input
                  data-reminder-speak
                  class="reminder-input"
                  type="text"
                  value="${escapeAttr(speak)}"
                  placeholder="しゃべる文面（speak_line）"
                />
                <button type="button" data-reminder-save="${escapeHtml(
                  r.commitment_id
                )}">保存</button>
                <button type="button" data-reminder-cancel="${escapeHtml(
                  r.commitment_id
                )}">キャンセル</button>
              </div>
            </li>
          `;
        })
        .join("")
    : "";

  return [
    buildStatusCard({
      id: "temp",
      label: temp.label,
      icon: temp.icon || "○",
      extraClass: ` status-card--temp mood-${escapeHtml(temp.mood || "neutral")}`,
      open: open("temp"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(temp.body)}</p>
        ${temp.detail ? `<span class="status-card__detail">${escapeHtml(temp.detail)}</span>` : ""}
        ${tempReadings ? `<ul class="temp-readings">${tempReadings}</ul>` : ""}`,
    }),
    buildStatusCard({
      id: "inner_voice",
      label: innerVoice.headline,
      icon: "♡",
      extraClass: " status-card--inner-voice",
      open: open("inner_voice"),
      innerHtml: `
        <p class="status-card__body status-card__body--inner-voice">${escapeHtml(innerVoice.body)}</p>
        ${
          innerVoice.subline
            ? `<p class="status-card__sub">${escapeHtml(innerVoice.subline)}</p>`
            : ""
        }`,
    }),
    buildStatusCard({
      id: "recent",
      label: recent.headline,
      open: open("recent"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(recent.body)}</p>
        ${recentList ? `<ul class="experience-list">${recentList}</ul>` : ""}`,
    }),
    buildStatusCard({
      id: "desires",
      label: "いまの気持ち",
      open: open("desires"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(desires.headline)}</p>
        <p class="status-card__sub">${escapeHtml(desires.subline || "")}</p>
        ${desireList ? `<ul class="desire-lines">${desireList}</ul>` : ""}`,
    }),
    buildStatusCard({
      id: "journey",
      label: journey.headline,
      open: open("journey"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(journey.body)}</p>
        ${journeyList ? `<ul class="journey-list">${journeyList}</ul>` : ""}`,
    }),
    buildStatusCard({
      id: "social",
      label: social.headline,
      open: open("social"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(social.body)}</p>
        ${socialTags ? `<div class="tag-row">${socialTags}</div>` : ""}`,
    }),
    buildStatusCard({
      id: "pulse",
      label: pulse.headline,
      icon: "⏰",
      open: open("pulse"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(pulse.body)}</p>
        ${pulseLines}`,
    }),
    buildStatusCard({
      id: "plan",
      label: plan.headline,
      icon: "◎",
      open: open("plan"),
      innerHtml: `
        <p class="status-card__body">${escapeHtml(plan.body)}</p>
        ${planLines}`,
    }),
    buildStatusCard({
      id: "reminders",
      label: "リマインド（編集）",
      icon: "R",
      open: open("reminders"),
      innerHtml: reminders.length
        ? `
          <p class="status-card__body">active（キャンセル/文面変更のみ）</p>
          <ul class="reminder-list">${reminderItems}</ul>
        `
        : `<p class="status-card__body">（いまはなし）</p>`,
    }),
  ].join("");
}

function renderStatus(data) {
  const tempEl = document.getElementById("temperature");
  const temp = KoyoriVoice.formatTemperature(data.temperature);

  if (tempEl) {
    tempEl.textContent = temp.detail ? `${temp.body} · ${temp.detail}` : temp.body;
  }

  try {
    for (const root of statusTargets()) {
      const compact =
        root.classList.contains("status-grid--rail") ||
        root.classList.contains("status-grid--drawer");
      root.innerHTML = buildStatusHtml(data, { compact });
      window.setTimeout(() => {
        root.querySelectorAll(".status-card.is-updated").forEach((card) => {
          card.classList.remove("is-updated");
        });
      }, 700);
    }
  } catch (err) {
    console.error("renderStatus failed:", err);
    const message = `<p class="error">${escapeHtml(err.message || String(err))}</p>`;
    for (const root of statusTargets()) {
      root.innerHTML = message;
    }
  }
}

function renderCameraInto(root, data) {
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
  const alt = `こよりの視界${preset}`;
  const src = `data:image/jpeg;base64,${data.image_base64}`;
  const img = root.querySelector("img");
  if (img) {
    if (img.getAttribute("src") !== src) {
      img.setAttribute("src", src);
    }
    img.alt = alt;
    return;
  }
  root.innerHTML = `<img src="${src}" alt="${alt}" loading="lazy" />`;
}

function renderCamera(data) {
  for (const root of visualFeedTargets()) {
    renderCameraInto(root, data);
  }
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
    console.warn("status refresh failed:", err.message);
    const message = `<p class="error">${escapeHtml(err.message)}</p>`;
    for (const root of statusTargets()) {
      root.innerHTML = message;
    }
  }
}

async function refreshCamera() {
  try {
    const data = await fetchJson("/api/v1/camera/snapshot");
    renderCamera(data);
  } catch (err) {
    const message = `<p class="error">${escapeHtml(err.message)}</p>`;
    for (const root of visualFeedTargets()) {
      root.innerHTML = message;
    }
  }
}

async function refreshAll() {
  await refreshChat();
  void refreshStatus();
  void refreshCamera();
}

function setupReminderCardActions() {
  if (document.body.dataset.reminderActionsBound) return;
  document.body.dataset.reminderActionsBound = "1";

  document.addEventListener("click", (event) => {
    const cancelBtn = event.target.closest("[data-reminder-cancel]");
    if (cancelBtn) {
      const id = cancelBtn.getAttribute("data-reminder-cancel") || "";
      if (!id) return;
      void (async () => {
        try {
          await postJson("/api/v1/reminders/cancel", {
            commitment_id: id,
            source_text: "ui_cancel",
          });
        } finally {
          void refreshStatus();
        }
      })();
      return;
    }

    const saveBtn = event.target.closest("[data-reminder-save]");
    if (saveBtn) {
      const id = saveBtn.getAttribute("data-reminder-save") || "";
      if (!id) return;
      const item = saveBtn.closest("[data-reminder-item]");
      const input = item ? item.querySelector('input[data-reminder-speak]') : null;
      const speak_line = input ? input.value.trim() : "";
      if (!speak_line) return;
      void (async () => {
        try {
          await postJson("/api/v1/reminders/speak-line", {
            commitment_id: id,
            speak_line,
            source_text: "ui_speak_line",
          });
        } finally {
          void refreshStatus();
        }
      })();
    }
  });
}

function outboundClientId() {
  if (isKioskLayout()) {
    localStorage.setItem(OUTBOUND_CLIENT_ID_KEY, "kiosk");
    return "kiosk";
  }
  let id = localStorage.getItem(OUTBOUND_CLIENT_ID_KEY);
  if (!id || id === "kiosk") {
    id = `web-${newRandomToken().slice(0, 12)}`;
    localStorage.setItem(OUTBOUND_CLIENT_ID_KEY, id);
  }
  return id;
}

function outboundPendingPath() {
  return uiConfig.outbound_pending_path || "/api/v1/outbound/pending";
}

function outboundAckPath() {
  return uiConfig.outbound_ack_path || "/api/v1/outbound/ack";
}

function outboundStreamPath() {
  return uiConfig.outbound_stream_path || "/api/v1/outbound/stream";
}

function outboundSseEnabled() {
  return uiConfig.outbound_sse_enabled !== false;
}

function outboundPollMs() {
  const ms = Number(uiConfig.outbound_poll_ms);
  return Number.isFinite(ms) && ms >= 1000 ? ms : OUTBOUND_POLL_MS_DEFAULT;
}

function outboundPollFallbackMs() {
  const ms = Number(uiConfig.outbound_poll_fallback_ms);
  return Number.isFinite(ms) && ms >= 5000 ? ms : 60000;
}

function activeOutboundPollMs() {
  if (outboundSseConnected && outboundSseEnabled()) {
    return outboundPollFallbackMs();
  }
  return outboundPollMs();
}

function roomSayPollMs() {
  const ms = Number(uiConfig.room_say_poll_ms);
  return Number.isFinite(ms) && ms >= 1000 ? ms : 3000;
}

function roomSayPendingPath() {
  return uiConfig.room_say_pending_path || "/api/v1/tts/room-say/pending";
}

function roomSayAckPath() {
  return uiConfig.room_say_ack_path || "/api/v1/tts/room-say/ack";
}

async function deliverRoomSayLine(itemOrText, { source = "say" } = {}) {
  // C11g: say 到着で画面復帰
  void wakeFromSleepOnNotify();
  const text = (
    typeof itemOrText === "string" ? itemOrText : itemOrText?.text || ""
  ).trim();
  const sayId = typeof itemOrText === "object" && itemOrText ? itemOrText.say_id : null;
  const audioUrl =
    typeof itemOrText === "object" && itemOrText ? itemOrText.audio_url : null;
  if (!text) return { ok: false, detail: "empty text" };
  if (sayId) {
    if (roomSayPlayed.has(sayId)) {
      return { ok: true, detail: "already-played" };
    }
    if (roomSayInFlight.has(sayId)) {
      return { ok: false, detail: "duplicate in flight" };
    }
    roomSayInFlight.add(sayId);
  }
  unlockSpeechOnce();
  if (isKioskLayout()) {
    setKioskAudioStatus("こよりが話す…", "warn");
  }
  let result;
  try {
    result = audioUrl
      ? await playAudioUrl(audioUrl)
      : await playOutboundNudgeAudio(text);
  } finally {
    if (sayId) roomSayInFlight.delete(sayId);
  }
  if (result.ok && sayId) {
    roomSayPlayed.add(sayId);
  }
  if (isKioskLayout()) {
    if (result.ok) {
      const via = kioskAudioPathLabel(result.detail);
      setKioskAudioStatus(`再生OK（${via}）`, "ok");
    } else {
      setKioskAudioStatus(`再生できず: ${result.detail}`, "error");
    }
  }
  if (!result.ok) {
    console.warn(`room_say playback failed (${source}):`, result.detail);
  }
  return result;
}

async function pollRoomSayPending() {
  if (!isKioskLayout()) return;
  const since = sessionStorage.getItem(ROOM_SAY_SINCE_KEY) || "";
  const params = new URLSearchParams({ client_id: outboundClientId() });
  if (since) params.set("since", since);
  try {
    const data = await fetchJson(`${roomSayPendingPath()}?${params.toString()}`);
    for (const item of data.items || []) {
      if (!item.text) continue;
      const result = await deliverRoomSayLine(item, { source: item.source || "poll" });
      if (!result.ok) {
        continue;
      }
      if (item.ts) {
        const prev = sessionStorage.getItem(ROOM_SAY_SINCE_KEY) || "";
        if (!prev || item.ts > prev) {
          sessionStorage.setItem(ROOM_SAY_SINCE_KEY, item.ts);
        }
      }
      if (item.say_id) {
        await fetch(roomSayAckPath(), {
          method: "POST",
          headers: { "Content-Type": "application/json; charset=utf-8" },
          body: JSON.stringify({
            say_id: item.say_id,
            client_id: outboundClientId(),
          }),
        });
      }
    }
  } catch (err) {
    console.warn("room_say poll failed:", err.message);
  }
}

function restartRoomSayPollTimer() {
  if (!isKioskLayout()) return;
  if (roomSayPollTimer) {
    clearInterval(roomSayPollTimer);
    roomSayPollTimer = null;
  }
  roomSayPollTimer = setInterval(() => void pollRoomSayPending(), roomSayPollMs());
}

function restartOutboundPollTimer() {
  if (outboundPollTimer) {
    clearInterval(outboundPollTimer);
    outboundPollTimer = null;
  }
  outboundPollTimer = setInterval(() => {
    void pollOutboundNudges();
  }, activeOutboundPollMs());
  restartRoomSayPollTimer();
}

function unlockSpeechOnce() {
  if (speechUnlocked) return;
  speechUnlocked = true;
  if (typeof speechSynthesis === "undefined") return;
  try {
    const warmup = new SpeechSynthesisUtterance("");
    warmup.volume = 0;
    speechSynthesis.speak(warmup);
  } catch {
    /* ignore autoplay policy */
  }
}

function shouldOutboundWebSpeech() {
  if (!uiConfig.outbound_web_speech_suppress_on_localhost) return true;
  const host = location.hostname;
  return host !== "localhost" && host !== "127.0.0.1";
}

function speakOutboundNudge(text) {
  if (!text || typeof speechSynthesis === "undefined") return;
  if (!shouldOutboundWebSpeech()) return;
  unlockSpeechOnce();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "ja-JP";
  utter.rate = 1.02;
  const voices = speechSynthesis.getVoices?.() || [];
  const jaVoice = voices.find((voice) => voice.lang && voice.lang.startsWith("ja"));
  if (jaVoice) utter.voice = jaVoice;
  utter.volume = getKioskPlaybackVolume();
  speechSynthesis.cancel();
  speechSynthesis.speak(utter);
}

function surfaceTtsSynthesizePath() {
  return uiConfig.surface_tts_synthesize_path || "/api/v1/tts/surface";
}

function outboundSurfaceTtsEnabled() {
  return Boolean(uiConfig.outbound_surface_tts_enabled);
}

async function playAudioUrl(url) {
  if (!url) return { ok: false, detail: "missing audio_url" };
  unlockSpeechOnce();
  try {
    const audio = new Audio(url);
    audio.preload = "auto";
    audio.volume = getKioskPlaybackVolume();
    await audio.play();
    return { ok: true, detail: "surface-tts-prepared" };
  } catch (err) {
    return { ok: false, detail: err.message || "audio-play-failed" };
  }
}

async function playOutboundNudgeAudio(text) {
  if (!text) return { ok: false, detail: "empty text" };
  unlockSpeechOnce();
  if (!outboundSurfaceTtsEnabled()) {
    speakOutboundNudge(text);
    return { ok: true, detail: "web-speech" };
  }
  try {
    const res = await fetch(surfaceTtsSynthesizePath(), {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      let detail = `surface TTS ${res.status}`;
      try {
        const errBody = await res.json();
        if (errBody?.detail) detail = String(errBody.detail);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    const data = await res.json();
    const url = data.audio_url;
    if (!url) {
      throw new Error("surface TTS missing audio_url");
    }
    const audio = new Audio(url);
    audio.preload = "auto";
    audio.volume = getKioskPlaybackVolume();
    await audio.play();
    return { ok: true, detail: "surface-tts" };
  } catch (err) {
    console.warn("surface TTS failed:", err.message);
    if (isKioskLayout()) {
      return { ok: false, detail: err.message || "surface-tts-failed" };
    }
    console.warn("falling back to Web Speech:", err.message);
    try {
      speakOutboundNudge(text);
      return { ok: true, detail: "web-speech-fallback" };
    } catch (inner) {
      return { ok: false, detail: err.message || String(inner) };
    }
  }
}

function kioskAudioPathLabel(detail) {
  if (detail === "surface-tts" || detail === "surface-tts-prepared") return "Aivis";
  if (detail === "web-speech") return "Web Speech";
  if (detail === "web-speech-fallback") return "Web Speech（予備）";
  return detail || "不明";
}

function getKioskPlaybackVolume() {
  if (!isKioskLayout()) return 1;
  try {
    const raw = localStorage.getItem(KIOSK_AUDIO_VOLUME_KEY);
    if (raw == null) return KIOSK_AUDIO_VOLUME_DEFAULT;
    const n = Number(raw);
    if (!Number.isFinite(n)) return KIOSK_AUDIO_VOLUME_DEFAULT;
    return Math.min(1, Math.max(0, n));
  } catch {
    return KIOSK_AUDIO_VOLUME_DEFAULT;
  }
}

function setKioskPlaybackVolume(level) {
  const clamped = Math.min(1, Math.max(0, level));
  try {
    localStorage.setItem(KIOSK_AUDIO_VOLUME_KEY, String(clamped));
  } catch {
    /* ignore quota */
  }
  syncKioskAudioVolumeUi(clamped);
  return clamped;
}

function syncKioskAudioVolumeUi(level = getKioskPlaybackVolume()) {
  const slider = document.getElementById("kiosk-audio-volume");
  const pct = document.getElementById("kiosk-audio-volume-pct");
  const pctValue = Math.round(level * 100);
  if (slider) slider.value = String(pctValue);
  if (pct) pct.textContent = String(pctValue);
}

function setKioskAudioStatus(message, tone = "neutral") {
  const section = document.getElementById("kiosk-audio-section");
  const statusEl = document.getElementById("kiosk-audio-status");
  if (!section || !statusEl || section.hidden) return;
  statusEl.textContent = message;
  statusEl.classList.remove("is-ok", "is-warn", "is-error");
  if (tone === "ok") statusEl.classList.add("is-ok");
  if (tone === "warn") statusEl.classList.add("is-warn");
  if (tone === "error") statusEl.classList.add("is-error");
}

async function runKioskAudioTest() {
  unlockSpeechOnce();
  setKioskAudioStatus("再生中…", "warn");
  const result = await playOutboundNudgeAudio("まー、聞こえる？");
  if (result.ok) {
    const via = kioskAudioPathLabel(result.detail);
    setKioskAudioStatus(`再生OK（${via}）。音量は下のスライダー`, "ok");
    return;
  }
  const blocked = /notallowed|gesture|interact/i.test(result.detail || "");
  if (blocked) {
    setKioskAudioStatus("画面をタップしてからもう一度", "warn");
    return;
  }
  setKioskAudioStatus(`失敗: ${result.detail}`, "error");
}

function setupKioskAudio() {
  const section = document.getElementById("kiosk-audio-section");
  const testBtn = document.getElementById("kiosk-audio-test");
  const slider = document.getElementById("kiosk-audio-volume");
  if (!section || !testBtn) return;
  if (isKioskLayout()) {
    section.hidden = false;
    syncKioskAudioVolumeUi();
    if (uiConfig.surface_tts_ready === false && uiConfig.surface_tts_status) {
      setKioskAudioStatus(uiConfig.surface_tts_status, "error");
    } else {
      setKioskAudioStatus("画面タップでブラウザ音声を解除", "warn");
    }
  } else {
    section.hidden = true;
    return;
  }
  testBtn.addEventListener("click", () => {
    void runKioskAudioTest();
  });
  if (slider) {
    slider.addEventListener("input", () => {
      setKioskPlaybackVolume(Number(slider.value) / 100);
    });
  }
  const onFirstGesture = () => {
    unlockSpeechOnce();
    if (isKioskLayout()) {
      setKioskAudioStatus("ブラウザ音声は解除済み", "ok");
    }
  };
  document.addEventListener("click", onFirstGesture, { once: true, passive: true });
  document.addEventListener("touchstart", onFirstGesture, { once: true, passive: true });
}

// ── C11g スリープ / 画面消灯 ──────────────────────────────────────

function getKioskSleepMinutes() {
  try {
    const raw = localStorage.getItem(KIOSK_SLEEP_MINUTES_KEY);
    if (raw == null) return KIOSK_SLEEP_MINUTES_DEFAULT;
    const n = Number(raw);
    return [5, 10, 15].includes(n) ? n : KIOSK_SLEEP_MINUTES_DEFAULT;
  } catch {
    return KIOSK_SLEEP_MINUTES_DEFAULT;
  }
}

function setKioskSleepMinutes(minutes) {
  const valid = [5, 10, 15].includes(Number(minutes)) ? Number(minutes) : KIOSK_SLEEP_MINUTES_DEFAULT;
  try {
    localStorage.setItem(KIOSK_SLEEP_MINUTES_KEY, String(valid));
  } catch {
    /* ignore quota */
  }
  return valid;
}

function getKioskSleepWakeOnNotify() {
  try {
    const raw = localStorage.getItem(KIOSK_SLEEP_WAKE_ON_NOTIFY_KEY);
    return raw !== "0";  // default ON
  } catch {
    return true;
  }
}

function setKioskSleepWakeOnNotify(enabled) {
  try {
    localStorage.setItem(KIOSK_SLEEP_WAKE_ON_NOTIFY_KEY, enabled ? "1" : "0");
  } catch {
    /* ignore quota */
  }
}

function kioskScreenIdleUrl(path) {
  return `http://127.0.0.1:18790${path}`;
}

function kioskScreenOff() {
  if (!isKioskLayout()) return;
  releaseWakeLock();
  fetch(kioskScreenIdleUrl("/screen-off"), { mode: "no-cors", keepalive: true }).catch(() => {});
}

function kioskScreenOn() {
  if (!isKioskLayout()) return;
  fetch(kioskScreenIdleUrl("/screen-on"), { mode: "no-cors", keepalive: true }).catch(() => {});
}

async function acquireWakeLock() {
  if (!("wakeLock" in navigator)) return;
  kioskScreenOn();
  if (wakeLock && !wakeLock.released) return;
  try {
    wakeLock = await navigator.wakeLock.request("screen");
    wakeLock.addEventListener("release", () => {
      // OS が手動で解放した場合（例: 画面オフ後の復帰）
    });
  } catch {
    wakeLock = null;
  }
}

function releaseWakeLock() {
  if (!wakeLock || wakeLock.released) return;
  try {
    wakeLock.release();
  } catch {
    /* ignore */
  }
  wakeLock = null;
}

function resetIdleTimer() {
  if (!isKioskLayout() || !idleActive) return;
  void acquireWakeLock();
  if (idleTimer) clearTimeout(idleTimer);
  const ms = getKioskSleepMinutes() * 60 * 1000;
  idleTimer = setTimeout(() => {
    if (!isKioskLayout()) return;
    kioskScreenOff();
  }, ms);
}

function setupIdleSleep() {
  if (!isKioskLayout()) return;
  idleActive = true;
  const resetEvents = ["pointerdown", "pointermove", "touchstart", "keydown"];
  for (const ev of resetEvents) {
    document.addEventListener(ev, resetIdleTimer, { passive: true });
  }
  // 送信でもリセット
  document.addEventListener("chat-send", resetIdleTimer, { passive: true });
  // visibilitychange: 画面復帰時に wakeLock を再取得
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && isKioskLayout()) {
      void acquireWakeLock();
      resetIdleTimer();
    }
  });
  void acquireWakeLock();
  resetIdleTimer();
}

/** say / 着信 到着時に画面を戻す（自動復帰 ON の場合）。
 *  wakeLock.request は visible でないと拒否されるため、document.title 変更で
 *  OSレベルの通知は出せないが、SSE 自体は hidden でも届く。
 *  audio 再生が成功すると OS が Surface 画面を戻すことが多い。 */
async function wakeFromSleepOnNotify() {
  if (!isKioskLayout() || !getKioskSleepWakeOnNotify()) return;
  if (!document.hidden) {
    // すでに見えている場合は wakeLock を念のため再取得してタイマーをリセット
    await acquireWakeLock();
    resetIdleTimer();
    return;
  }
  // document が hidden の間は wakeLock.request は失敗するが、
  // 音声再生でブラウザが前面に出ることを期待（Chromium Edge は kiosk で全画面のため問題ない）
  await acquireWakeLock();
  resetIdleTimer();
}

function syncKioskSleepUi() {
  const minutes = getKioskSleepMinutes();
  const wakeOnNotify = getKioskSleepWakeOnNotify();
  const select = document.getElementById("kiosk-sleep-minutes");
  const checkbox = document.getElementById("kiosk-sleep-wake-notify");
  if (select) select.value = String(minutes);
  if (checkbox) checkbox.checked = wakeOnNotify;
}

function setupKioskSleep() {
  if (!isKioskLayout()) {
    const section = document.getElementById("kiosk-sleep-section");
    if (section) section.hidden = true;
    return;
  }
  const section = document.getElementById("kiosk-sleep-section");
  if (section) section.hidden = false;
  syncKioskSleepUi();

  const select = document.getElementById("kiosk-sleep-minutes");
  if (select) {
    select.addEventListener("change", () => {
      setKioskSleepMinutes(Number(select.value));
      resetIdleTimer();
    });
  }
  const checkbox = document.getElementById("kiosk-sleep-wake-notify");
  if (checkbox) {
    checkbox.addEventListener("change", () => {
      setKioskSleepWakeOnNotify(checkbox.checked);
    });
  }
  setupIdleSleep();
}

// ── Claude Code permissions UI ─────────────────────────────────────

let claudePermsEditable = false;
let claudePermsDirty = false;

function setClaudePermsStatus(message, tone = "neutral") {
  const el = document.getElementById("claude-perms-status");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("is-ok", "is-warn", "is-error");
  if (tone === "ok") el.classList.add("is-ok");
  if (tone === "warn") el.classList.add("is-warn");
  if (tone === "error") el.classList.add("is-error");
}

function syncClaudePermsSaveButton() {
  const btn = document.getElementById("claude-perms-save");
  if (!btn) return;
  btn.disabled = !claudePermsEditable || !claudePermsDirty;
}

function renderClaudePermissions(data) {
  const list = document.getElementById("claude-perms-list");
  if (!list) return;
  claudePermsEditable = Boolean(data.editable);
  const presets = data.presets || [];
  list.innerHTML = presets
    .map(
      (p) => `
    <label class="claude-perms__row">
      <input type="checkbox" data-perm-id="${escapeAttr(p.id)}" ${
        p.enabled ? "checked" : ""
      } ${claudePermsEditable ? "" : "disabled"} />
      <span class="claude-perms__row-label">
        ${escapeHtml(p.label)}
        <span class="claude-perms__row-rule">${escapeHtml(p.rule)}</span>
      </span>
    </label>`,
    )
    .join("");

  const preserved = data.preserved_rules || [];
  let preservedEl = document.getElementById("claude-perms-preserved");
  if (!preservedEl) {
    preservedEl = document.createElement("p");
    preservedEl.id = "claude-perms-preserved";
    preservedEl.className = "claude-perms__preserved";
    list.after(preservedEl);
  }
  preservedEl.textContent = preserved.length
    ? `その他（UI外・保持）: ${preserved.join(" · ")}`
    : "";

  if (!claudePermsEditable) {
    setClaudePermsStatus("閲覧のみ（保存は ma-home ローカルかログイン後）", "warn");
  } else {
    setClaudePermsStatus("", "neutral");
  }
  claudePermsDirty = false;
  syncClaudePermsSaveButton();
}

async function loadClaudePermissions() {
  try {
    const data = await fetchJson("/api/v1/claude/permissions");
    renderClaudePermissions(data);
  } catch (err) {
    setClaudePermsStatus(`読み込み失敗: ${err.message}`, "error");
  }
}

async function saveClaudePermissions() {
  const list = document.getElementById("claude-perms-list");
  if (!list || !claudePermsEditable) return;
  const enabledIds = [...list.querySelectorAll("input[data-perm-id]:checked")].map(
    (el) => el.getAttribute("data-perm-id"),
  );
  setClaudePermsStatus("保存中…", "warn");
  try {
    if (usesNativeChat()) {
      await ensureNativeLogin();
    }
    const headers = { "Content-Type": "application/json; charset=utf-8" };
    if (nativeAuthToken) {
      headers.Authorization = `Bearer ${nativeAuthToken}`;
    }
    const res = await fetch("/api/v1/claude/permissions", {
      method: "POST",
      headers,
      body: JSON.stringify({ enabled_ids: enabledIds }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`${res.status} ${detail}`);
    }
    const data = await res.json();
    renderClaudePermissions({ ...data, editable: true });
    setClaudePermsStatus(data.note || "保存した", "ok");
  } catch (err) {
    setClaudePermsStatus(`保存できなかった: ${err.message}`, "error");
  }
}

function setupClaudePermissions() {
  const section = document.getElementById("claude-permissions-section");
  const list = document.getElementById("claude-perms-list");
  const saveBtn = document.getElementById("claude-perms-save");
  if (!section || !list || !saveBtn) return;
  list.addEventListener("change", () => {
    if (!claudePermsEditable) return;
    claudePermsDirty = true;
    syncClaudePermsSaveButton();
  });
  saveBtn.addEventListener("click", () => {
    void saveClaudePermissions();
  });
  void loadClaudePermissions();
}

// ── Claude permissions ここまで ──────────────────────────────────

async function playKioskSpeech(text) {
  if (!isKioskLayout()) {
    await playOutboundNudgeAudio(text);
    return;
  }
  setKioskAudioStatus("こよりが話す…", "warn");
  const result = await playOutboundNudgeAudio(text);
  if (result.ok) {
    const via = kioskAudioPathLabel(result.detail);
    setKioskAudioStatus(`再生OK（${via}）`, "ok");
    return;
  }
  setKioskAudioStatus(`再生できず: ${result.detail}`, "error");
}

async function ackOutboundNudge(nudgeId, channels) {
  await fetch(outboundAckPath(), {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      nudge_id: nudgeId,
      client_id: outboundClientId(),
      channels: channels || [],
    }),
  });
}

function roomInboundRoot() {
  return document.getElementById("room-inbound");
}

function showRoomInboundModal(item) {
  const root = roomInboundRoot();
  const messageEl = document.getElementById("room-inbound-message");
  if (!root || !messageEl) return;
  messageEl.textContent = item.text || "";
  root.hidden = false;
  root.classList.add("is-open");
  root.setAttribute("aria-hidden", "false");
  document.body.classList.add("room-inbound-body-lock");
  const replyBtn = document.getElementById("room-inbound-reply");
  replyBtn?.focus();
}

function hideRoomInboundModal() {
  const root = roomInboundRoot();
  if (!root) return;
  root.classList.remove("is-open");
  root.hidden = true;
  root.setAttribute("aria-hidden", "true");
  document.body.classList.remove("room-inbound-body-lock");
}

function enqueueRoomInbound(item) {
  if (!item?.nudge_id || !item.text) return;
  if (roomInboundCurrent?.nudge_id === item.nudge_id) return;
  if (roomInboundQueue.some((row) => row.nudge_id === item.nudge_id)) return;
  // C11g: 着信で画面復帰
  void wakeFromSleepOnNotify();
  roomInboundQueue.push(item);
  void pumpRoomInbound();
}

async function pumpRoomInbound() {
  if (roomInboundCurrent || !roomInboundQueue.length) return;
  roomInboundCurrent = roomInboundQueue.shift();
  showRoomInboundModal(roomInboundCurrent);
  if (roomInboundCurrent.speak) {
    void playKioskSpeech(roomInboundCurrent.text);
  }
}

function buildInboundReplyPrompt(nudgeText) {
  const line = (nudgeText || "").trim();
  if (!line) {
    return "[こよりからの着信への返事]\nまーとして、ひとこと返して。";
  }
  return (
    `[こよりからの着信への返事]\n` +
    `こより: 「${line}」\n\n` +
    `まーとして、こよりの言葉に自然にひとこと返して。` +
    `定型句に偏らず、そのときの気分で。`
  );
}

async function beginInboundReply(item) {
  unlockSpeechOnce();
  if (isKioskLayout()) setRoomDrawerOpen(false);
  const inboundText = (item?.text || "").trim();
  pendingInboundReply = inboundText
    ? {
        text: inboundText,
        nudge_id: item?.nudge_id || null,
        ts: item?.ts || new Date().toISOString(),
      }
    : null;

  if (isNativeChat()) {
    await startNewNativeSessionAsync();
    const root = document.getElementById("chat-log");
    if (root) root.querySelector(".placeholder")?.remove();
    if (inboundText) {
      const msg = {
        sender: "koyori",
        message: inboundText,
        timestamp: pendingInboundReply.ts,
        _inboundSeed: true,
      };
      chatMessages = [msg];
      renderedMessageKeys = new Set();
      appendMessagesToDom([msg], { animate: true });
    }
    const input = document.getElementById("chat-input");
    if (input) {
      input.placeholder = inboundText ? "こよりに返事を書いて…" : "こよりに話しかける...";
      input.value = "";
      input.focus();
    }
    chatPinnedToBottom = true;
    scrollChatToBottom();
    return;
  }

  const input = document.getElementById("chat-input");
  if (input) {
    input.placeholder = "こよりに話しかける...";
    input.value = buildInboundReplyPrompt(inboundText);
    input.focus();
  }
}

async function closeRoomInbound({ reply = false } = {}) {
  const current = roomInboundCurrent;
  if (!current) return;
  hideRoomInboundModal();
  roomInboundCurrent = null;
  const channels = ["room_inbound"];
  if (reply) channels.push("chat_compose");
  if (current.speak) channels.push("voice_surface");
  try {
    await ackOutboundNudge(current.nudge_id, channels);
    if (current.ts) {
      const since = sessionStorage.getItem(OUTBOUND_SINCE_KEY) || "";
      if (!since || current.ts > since) {
        sessionStorage.setItem(OUTBOUND_SINCE_KEY, current.ts);
      }
    }
  } catch (err) {
    console.warn("outbound ack failed:", err.message);
  }
  if (reply) await beginInboundReply(current);
  void pumpRoomInbound();
}

function setupRoomInbound() {
  const replyBtn = document.getElementById("room-inbound-reply");
  const laterBtn = document.getElementById("room-inbound-later");
  if (replyBtn) {
    replyBtn.addEventListener("click", () => {
      void closeRoomInbound({ reply: true });
    });
  }
  if (laterBtn) {
    laterBtn.addEventListener("click", () => {
      void closeRoomInbound({ reply: false });
    });
  }
}

function browserNotificationsEnabled() {
  return typeof Notification !== "undefined" && Notification.permission === "granted";
}

async function requestBrowserNotificationPermission() {
  if (typeof Notification === "undefined") return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    const result = await Notification.requestPermission();
    return result === "granted";
  } catch {
    return false;
  }
}

function browserNotificationSeen(nudgeId) {
  if (!nudgeId) return false;
  try {
    const raw = sessionStorage.getItem(OUTBOUND_BROWSER_NOTIFIED_KEY) || "[]";
    const ids = JSON.parse(raw);
    return Array.isArray(ids) && ids.includes(nudgeId);
  } catch {
    return false;
  }
}

function markBrowserNotificationSeen(nudgeId) {
  if (!nudgeId) return;
  try {
    const raw = sessionStorage.getItem(OUTBOUND_BROWSER_NOTIFIED_KEY) || "[]";
    const ids = Array.isArray(JSON.parse(raw)) ? JSON.parse(raw) : [];
    if (!ids.includes(nudgeId)) ids.push(nudgeId);
    sessionStorage.setItem(OUTBOUND_BROWSER_NOTIFIED_KEY, JSON.stringify(ids.slice(-50)));
  } catch {
    /* ignore */
  }
}

async function showBrowserOutboundNotification(item) {
  if (!item?.nudge_id || !item.text || !browserNotificationsEnabled()) return;
  if (browserNotificationSeen(item.nudge_id)) return;
  markBrowserNotificationSeen(item.nudge_id);
  try {
    const toast = new Notification("Koyori", {
      body: item.text,
      tag: item.nudge_id,
    });
    toast.onclick = () => {
      window.focus();
      toast.close();
      enqueueRoomInbound(item);
    };
    await ackOutboundNudge(item.nudge_id, ["browser_notification"]);
    if (item.ts) {
      const since = sessionStorage.getItem(OUTBOUND_SINCE_KEY) || "";
      if (!since || item.ts > since) {
        sessionStorage.setItem(OUTBOUND_SINCE_KEY, item.ts);
      }
    }
  } catch (err) {
    console.warn("browser notification failed:", err.message);
  }
}

function deliverOutboundItem(item) {
  if (!item?.nudge_id || !item.text) return;
  if (uiConfig.kiosk_primary_active && !isKioskLayout()) return;
  const kiosk = isKioskLayout();
  if (kiosk) {
    enqueueRoomInbound(item);
    return;
  }
  if (browserNotificationsEnabled()) {
    void showBrowserOutboundNotification(item);
    return;
  }
  if (!document.hidden) {
    enqueueRoomInbound(item);
  }
}

function closeOutboundSse() {
  outboundSseConnected = false;
  if (outboundEventSource) {
    outboundEventSource.close();
    outboundEventSource = null;
  }
}

function setupOutboundSse() {
  if (!outboundSseEnabled() || typeof EventSource === "undefined") return;
  closeOutboundSse();
  const params = new URLSearchParams({ client_id: outboundClientId() });
  const since = sessionStorage.getItem(OUTBOUND_SINCE_KEY) || "";
  if (since) params.set("since", since);
  const source = new EventSource(`${outboundStreamPath()}?${params.toString()}`);
  outboundEventSource = source;
  source.addEventListener("connected", () => {
    outboundSseConnected = true;
    restartOutboundPollTimer();
  });
  source.addEventListener("room_inbound", (event) => {
    try {
      deliverOutboundItem(JSON.parse(event.data));
    } catch (err) {
      console.warn("outbound SSE parse failed:", err.message);
    }
  });
  source.addEventListener("room_say", (event) => {
    try {
      const data = JSON.parse(event.data);
      if (!data.text) return;
      void (async () => {
        const result = await deliverRoomSayLine(data, { source: "sse" });
        if (!result.ok || !data.say_id) return;
        try {
          await fetch(roomSayAckPath(), {
            method: "POST",
            headers: { "Content-Type": "application/json; charset=utf-8" },
            body: JSON.stringify({
              say_id: data.say_id,
              client_id: outboundClientId(),
            }),
          });
        } catch (ackErr) {
          console.warn("room_say ack failed:", ackErr.message);
        }
      })();
    } catch (err) {
      console.warn("room_say SSE parse failed:", err.message);
    }
  });
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) {
      outboundSseConnected = false;
      restartOutboundPollTimer();
    }
  };
}

function syncKioskTtsHealthFromConfig() {
  if (!isKioskLayout()) return;
  const section = document.getElementById("kiosk-audio-section");
  if (!section || section.hidden) return;
  if (uiConfig.outbound_surface_tts_enabled && uiConfig.surface_tts_ready === false) {
    setKioskAudioStatus(uiConfig.surface_tts_status || "TTS エンジンが止まっています", "error");
  }
}

async function refreshOutboundRoutingConfig() {
  try {
    const data = await fetchJson("/api/v1/ui-config");
    uiConfig.kiosk_primary_active = Boolean(data.kiosk_primary_active);
    uiConfig.kiosk_primary_enabled = data.kiosk_primary_enabled !== false;
    uiConfig.surface_tts_ready = Boolean(data.surface_tts_ready);
    uiConfig.surface_tts_status = data.surface_tts_status || "";
    syncKioskTtsHealthFromConfig();
  } catch {
    /* ignore */
  }
}

async function pollOutboundNudges() {
  await refreshOutboundRoutingConfig();
  const kiosk = isKioskLayout();
  if (kiosk && document.hidden) return;
  const since = sessionStorage.getItem(OUTBOUND_SINCE_KEY) || "";
  const params = new URLSearchParams({ client_id: outboundClientId() });
  if (since) params.set("since", since);
  try {
    const data = await fetchJson(`${outboundPendingPath()}?${params.toString()}`);
    const items = data.items || [];
    for (const item of items) {
      deliverOutboundItem(item);
    }
  } catch (err) {
    console.warn("outbound poll failed:", err.message);
  }
}

function setupOutboundPoll() {
  try {
    if (outboundPollTimer) {
      clearInterval(outboundPollTimer);
      outboundPollTimer = null;
    }
    document.addEventListener("click", unlockSpeechOnce, { once: true, passive: true });
    document.addEventListener("touchstart", unlockSpeechOnce, { once: true, passive: true });
    if (!isKioskLayout()) {
      document.addEventListener(
        "click",
        () => {
          void requestBrowserNotificationPermission().then((ok) => {
            if (ok) void pollOutboundNudges();
          });
        },
        { once: true, passive: true },
      );
      if (typeof Notification !== "undefined" && Notification.permission === "default") {
        console.info(
          "[koyori] Allow browser notifications on this page for outbound toasts (title: Koyori).",
        );
      }
    }
    setupOutboundSse();
    restartOutboundPollTimer();
    void pollOutboundNudges();
    void pollRoomSayPending();
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        void pollOutboundNudges();
        void pollRoomSayPending();
        if (outboundSseEnabled() && outboundEventSource?.readyState === EventSource.CLOSED) {
          setupOutboundSse();
        }
      }
    });
  } catch (err) {
    console.warn("outbound poll setup failed (chat/status still work):", err.message);
  }
}

function setupKioskLayout() {
  const room = document.querySelector(".room");
  if (!room) return;
  const params = new URLSearchParams(location.search);
  if (params.get("kiosk") === "1") {
    room.classList.add("room--kiosk");
    localStorage.setItem(KIOSK_LAYOUT_STORAGE_KEY, "1");
  } else if (params.get("kiosk") === "0") {
    room.classList.remove("room--kiosk");
    localStorage.removeItem(KIOSK_LAYOUT_STORAGE_KEY);
  } else if (localStorage.getItem(KIOSK_LAYOUT_STORAGE_KEY) === "1") {
    room.classList.add("room--kiosk");
  }
  if (isKioskLayout()) {
    localStorage.setItem(OUTBOUND_CLIENT_ID_KEY, "kiosk");
  }
  ensureSessionControlsMounted();
  relocateSessionControls();
  applyDebugInjectionVisibility();
  setupRoomDrawer();
  setupContextRail();
  setupKioskAudio();
  setupKioskSleep();
  setupOutboundPoll();
}

setupRoomInbound();
setupKioskLayout();
setupClaudePermissions();
setupStatusCardExpand();
setupReminderCardActions();
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
