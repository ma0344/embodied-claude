/**
 * Parse Claude Code SDK messages for Koyori's Room.
 * Display speech is selected by content block type (text only).
 */

const DISPLAY_BLOCK_TYPE = "text";
const SKIPPED_BLOCK_TYPES = new Set(["thinking", "tool_use", "tool_result"]);

const SYSTEM_BLOCK_RES = [
  /^\[Social context\]\s*$/i,
  /^\[interaction_context\]\s*$/i,
  /^\[response_contract\]\s*$/i,
  /^\[recent_room_context\b/i,
  /^\[Must include\]/i,
  /^\[Must avoid\]/i,
  /^\[Social move\b/i,
];

const ROOM_CONTEXT_BODY_RES = [
  /^Room arc:/i,
  /^Last speaker:/i,
  /^Conversation in THIS room only/i,
  /^(まー|こより):\s+/,
];

const CONTRACT_BODY_RES = [/^treat_user_as:/i, /^avoid:/i, /^prefer:/i, /^initiative:/i, /^[a-z_]+=/i];

const CONTEXT_HEADER_RES = [/^\[Social context\]\s*$/i, /^\[interaction_context\]\s*$/i];

function isSystemBlockHeader(line) {
  const stripped = line.trim();
  return SYSTEM_BLOCK_RES.some((pattern) => pattern.test(stripped));
}

function isContextHeader(headerLine) {
  const stripped = headerLine.trim();
  return CONTEXT_HEADER_RES.some((pattern) => pattern.test(stripped));
}

function isRoomContextBody(line) {
  const stripped = line.trim();
  if (!stripped) return true;
  return ROOM_CONTEXT_BODY_RES.some((pattern) => pattern.test(stripped));
}

function isContractBody(line) {
  const stripped = line.trim();
  if (!stripped) return true;
  return CONTRACT_BODY_RES.some((pattern) => pattern.test(stripped));
}

function blockIndices(lines, headerIndex, nextHeader) {
  if (nextHeader !== undefined) {
    return Array.from({ length: nextHeader - headerIndex }, (_, offset) => headerIndex + offset);
  }

  const header = lines[headerIndex];
  let start = headerIndex + 1;
  const end = lines.length;

  if (/^\[recent_room_context\b/i.test(header.trim())) {
    while (start < end && isRoomContextBody(lines[start])) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (header.trim().toLowerCase() === "[response_contract]") {
    while (start < end && isContractBody(lines[start])) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (isContextHeader(header)) {
    while (start < end && lines[start].trim()) start += 1;
    while (start < end && !lines[start].trim()) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  return [headerIndex];
}

/** Phase 1 fallback for history JSONL until sociality leaves user text (Phase 2). */
function stripEnrichedUserPrompt(text) {
  const raw = String(text ?? "");
  if (!raw.trim()) return "";

  const lines = raw.split("\n");
  const headerIndices = [];
  lines.forEach((line, index) => {
    if (isSystemBlockHeader(line)) headerIndices.push(index);
  });
  if (!headerIndices.length) return raw.trim();

  const blocked = new Set();
  headerIndices.forEach((headerIndex, position) => {
    const nextHeader = headerIndices[position + 1];
    blockIndices(lines, headerIndex, nextHeader).forEach((index) => blocked.add(index));
  });

  const kept = lines.filter((_, index) => !blocked.has(index));
  while (kept.length && !kept[0].trim()) kept.shift();
  while (kept.length && !kept[kept.length - 1].trim()) kept.pop();
  return kept.join("\n").trim();
}

function extractTextBlocks(content) {
  if (typeof content === "string") {
    const text = content.trim();
    return text ? [text] : [];
  }
  if (!Array.isArray(content)) return [];

  const parts = [];
  for (const block of content) {
    if (!block || typeof block !== "object") continue;
    if (SKIPPED_BLOCK_TYPES.has(block.type)) continue;
    if (block.type !== DISPLAY_BLOCK_TYPE) continue;
    if (typeof block.text === "string" && block.text) parts.push(block.text);
  }
  return parts;
}

function joinTextBlocks(content) {
  return extractTextBlocks(content).join("\n").trim();
}

function extractUserText(sdkMessage) {
  if (!sdkMessage || sdkMessage.type !== "user") return "";
  const inner = sdkMessage.message || sdkMessage;
  const combined = joinTextBlocks(inner.content ?? inner.message?.content ?? inner.message);
  return stripEnrichedUserPrompt(combined);
}

function extractAssistantText(sdkMessage) {
  if (!sdkMessage || sdkMessage.type !== "assistant") return "";
  const inner = sdkMessage.message || sdkMessage;
  return joinTextBlocks(inner.content);
}

function flattenHistoryMessages(messages) {
  const rows = [];
  for (const msg of messages || []) {
    if (msg.type === "system" || msg.type === "result") continue;

    const ts = msg.timestamp || msg.ts || new Date().toISOString();
    const userText = extractUserText(msg);
    if (userText) {
      rows.push({ sender: "ma", message: userText, timestamp: ts });
      continue;
    }
    const assistantText = extractAssistantText(msg);
    if (assistantText) {
      rows.push({ sender: "koyori", message: assistantText, timestamp: ts });
    }
  }
  return rows;
}

function extractStreamText(chunk) {
  if (!chunk || chunk.type !== "claude_json") return "";
  return extractAssistantText(chunk.data) || extractUserText(chunk.data);
}

function extractStreamSessionId(chunk) {
  const data = chunk?.data;
  if (!data) return null;
  if (data.type === "system" && data.subtype === "init" && data.session_id) {
    return data.session_id;
  }
  if (data.session_id) return data.session_id;
  if (data.sessionId) return data.sessionId;
  return null;
}

function sanitizeDisplayText(text) {
  return String(text ?? "").trim();
}

window.CcMessages = {
  flattenHistoryMessages,
  extractStreamText,
  extractStreamSessionId,
  sanitizeDisplayText,
  extractTextBlocks,
};
