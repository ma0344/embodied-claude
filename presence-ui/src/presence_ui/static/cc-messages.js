/**
 * Parse Claude Code SDK messages for Koyori's Room.
 * Display speech is selected by content block type (text only).
 */

const DISPLAY_BLOCK_TYPE = "text";
const SKIPPED_BLOCK_TYPES = new Set(["thinking", "tool_use", "tool_result"]);

const SYSTEM_BLOCK_RES = [
  /^\[Social context\]\s*$/i,
  /^\[gateway_turn_context\b/i,
  /^\[vision_prefetch\]\s*$/i,
  /^\[web_search_prefetch\]\s*$/i,
  /^\[\/web_search_prefetch\]/i,
  /^\[calendar_prefetch\]\s*$/i,
  /^\[\/calendar_prefetch\]/i,
  /^\[calendar_write_result\]\s*$/i,
  /^\[\/calendar_write_result\]/i,
  /^\[calendar_confirm_pending\]\s*$/i,
  /^\[\/calendar_confirm_pending\]/i,
  /^\[url_prefetch\]\s*$/i,
  /^\[\/url_prefetch\]/i,
  /^\[doc_context\]\s*$/i,
  /^\[\/doc_context\]/i,
  /^\[Gateway directive\b/i,
  /^\[interaction_context\]\s*$/i,
  /^\[response_contract\]\s*$/i,
  /^\[recent_room_context\b/i,
  /^\[Must include\]/i,
  /^\[Must avoid\]/i,
  /^\[Social move\b/i,
  /^\[memory_saved_server\]/i,
  /^\[memory_save_failed\]/i,
  /^\[memory_list_prefetch\]/i,
  /^\[stm_recent\]\s*$/i,
  /^\[\/stm_recent\]/i,
  /^\[dream_digest\]\s*$/i,
  /^\[\/dream_digest\]/i,
  /^\[overnight_inner_voice\]\s*$/i,
  /^\[\/overnight_inner_voice\]/i,
  /^\[inbound_nudge\b/i,
  /^\[inbound_reply\b/i,
  /^\[gateway_internal\b/i,
  /^\[somatic_state\]\s*$/i,
  /^\[relevant_memories\]\s*$/i,
  /^\[commitments_due\]\s*$/i,
  /^\[interpretation_shifts\]\s*$/i,
  /^\[desires\]\s*$/i,
];

const PAIRED_BLOCK_OPENERS = {
  "[stm_recent]": "[/stm_recent]",
  "[dream_digest]": "[/dream_digest]",
  "[overnight_inner_voice]": "[/overnight_inner_voice]",
  "[web_search_prefetch]": "[/web_search_prefetch]",
  "[calendar_prefetch]": "[/calendar_prefetch]",
  "[calendar_write_result]": "[/calendar_write_result]",
  "[calendar_confirm_pending]": "[/calendar_confirm_pending]",
  "[url_prefetch]": "[/url_prefetch]",
  "[doc_context]": "[/doc_context]",
};

const STM_BULLET_RE = /^- \([a-z_]+\)/i;

const STM_ORPHAN_LINE_RES = [
  STM_BULLET_RE,
  /^(まー|こより):\s+/i,
  /^【会話の一区切り】/,
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

function pairedBlockClose(headerLine) {
  const key = headerLine.trim().toLowerCase();
  for (const [opener, closer] of Object.entries(PAIRED_BLOCK_OPENERS)) {
    if (key === opener) return closer;
  }
  return null;
}

function blockIndices(lines, headerIndex, nextHeader) {
  if (nextHeader !== undefined) {
    return Array.from({ length: nextHeader - headerIndex }, (_, offset) => headerIndex + offset);
  }

  const header = lines[headerIndex];
  let start = headerIndex + 1;
  const end = lines.length;

  const pairedClose = pairedBlockClose(header);
  if (pairedClose) {
    const closeKey = pairedClose.toLowerCase();
    while (start < end) {
      const lineKey = lines[start].trim().toLowerCase();
      if (lineKey === closeKey || lineKey.startsWith(closeKey)) {
        start += 1;
        break;
      }
      start += 1;
    }
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (/^\[recent_room_context\b/i.test(header.trim())) {
    while (start < end && isRoomContextBody(lines[start])) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (/^\[vision_prefetch\]\s*$/i.test(header.trim())) {
    while (start < end) {
      const line = lines[start].trim();
      if (/^\[Gateway directive\b/i.test(line)) {
        while (start < end) {
          const directiveLine = lines[start].trim();
          if (!directiveLine) {
            start += 1;
            break;
          }
          if (start > headerIndex + 1 && isSystemBlockHeader(lines[start]) && !/^\[Gateway directive\b/i.test(directiveLine)) {
            break;
          }
          start += 1;
        }
        break;
      }
      if (start > headerIndex && isSystemBlockHeader(lines[start])) break;
      start += 1;
    }
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (/^\[gateway_turn_context\b/i.test(header.trim())) {
    return [headerIndex];
  }

  if (/^\[inbound_nudge\b/i.test(header.trim())) {
    while (start < end && lines[start].trim()) start += 1;
    while (start < end && !lines[start].trim()) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (/^\[inbound_reply\b/i.test(header.trim())) {
    while (start < end && lines[start].trim()) start += 1;
    while (start < end && !lines[start].trim()) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (/^\[Gateway directive\b/i.test(header.trim())) {
    while (start < end && lines[start].trim()) start += 1;
    return Array.from({ length: start - headerIndex }, (_, offset) => headerIndex + offset);
  }

  if (
    /^\[memory_saved_server\]/i.test(header.trim()) ||
    /^\[memory_save_failed\]/i.test(header.trim()) ||
    /^\[memory_list_prefetch\]/i.test(header.trim())
  ) {
    while (start < end && lines[start].trim()) start += 1;
    while (start < end && !lines[start].trim()) start += 1;
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
function normalizeNewlines(text) {
  return String(text ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function stripEnrichedUserPromptOnce(text) {
  const raw = normalizeNewlines(text);
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

function stripLeadingOrphanInjectionLines(text) {
  const lines = String(text ?? "").split("\n");
  while (lines.length) {
    const line = lines[0].trim();
    if (!line) {
      lines.shift();
      continue;
    }
    if (STM_ORPHAN_LINE_RES.some((pattern) => pattern.test(line))) {
      lines.shift();
      continue;
    }
    break;
  }
  while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
  return lines.join("\n").trim();
}

function stripOneTrailingTailPrefetch(remainder) {
  const patterns = [
    /\n\[doc_context\][\s\S]*$/i,
    /\n\[url_prefetch\][\s\S]*$/i,
    /\n\[web_search_prefetch\][\s\S]*$/i,
    /\n\[calendar_confirm_pending\][\s\S]*$/i,
    /\n\[calendar_write_result\][\s\S]*$/i,
    /\n\[calendar_prefetch\][\s\S]*$/i,
    /\n\[vision_prefetch\][\s\S]*$/i,
  ];
  for (const pattern of patterns) {
    const match = pattern.exec(remainder);
    if (match) {
      return { text: remainder.slice(0, match.index).trimEnd(), changed: true };
    }
  }
  return { text: remainder, changed: false };
}

function stripTrailingTailPrefetch(remainder) {
  let out = remainder;
  for (let i = 0; i < 5; i += 1) {
    const { text, changed } = stripOneTrailingTailPrefetch(out);
    out = text;
    if (!changed) break;
  }
  return out;
}

function stripGatewayWrapperTail(text) {
  const raw = normalizeNewlines(text);
  if (!raw.trim()) return "";
  const lines = raw.split("\n");
  if (!lines.length || !/^\[gateway_turn_context\b/i.test(lines[0].trim())) return null;
  let remainder = lines.slice(1).join("\n");
  remainder = stripTrailingTailPrefetch(remainder);
  if (!remainder.includes("\n\n")) {
    const tail = remainder.trim();
    return tail && !msgLooksInjected(tail) ? tail : null;
  }
  const splitAt = remainder.lastIndexOf("\n\n");
  const tail = remainder.slice(splitAt + 2).trim();
  if (!tail || msgLooksInjected(tail)) return null;
  return tail;
}

function stripEnrichedUserPrompt(text) {
  const raw = normalizeNewlines(text);
  if (!raw.trim()) return "";

  const firstLine = raw.split("\n", 1)[0].trim();
  if (/^\[gateway_turn_context\b/i.test(firstLine)) {
    const gatewayTail = stripGatewayWrapperTail(raw);
    if (gatewayTail !== null) return gatewayTail;
  }

  let current = raw;
  for (let pass = 0; pass < 12; pass += 1) {
    let nxt = stripEnrichedUserPromptOnce(current);
    nxt = stripLeadingOrphanInjectionLines(nxt);
    if (nxt === current.trim()) break;
    current = nxt;
  }
  const iterative = current.trim();
  if (iterative && !msgLooksInjected(iterative)) return iterative;
  return iterative;
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
  return combined.trim();
}

function extractAssistantText(sdkMessage) {
  if (!sdkMessage || sdkMessage.type !== "assistant") return "";
  const inner = sdkMessage.message || sdkMessage;
  return joinTextBlocks(inner.content);
}

function looksLikeAgentSlashCommand(text) {
  const raw = String(text ?? "").trim();
  if (!raw) return false;
  if (/^#\s*\/\w+/m.test(raw)) return true;
  return raw.startsWith("---") && /^#\s*\/\w+/m.test(raw);
}

function isGatewayInternalUserText(text) {
  const raw = String(text ?? "");
  return /\[gateway_internal\b/i.test(raw);
}

function extractJsonObject(text) {
  const raw = String(text ?? "").trim();
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    return data && typeof data === "object" && !Array.isArray(data) ? data : null;
  } catch {
    // fall through
  }
  let body = raw;
  if (body.startsWith("```")) {
    body = body.replace(/^```(?:json)?\s*\n?/i, "").trim();
    if (body.endsWith("```")) {
      body = body.slice(0, body.lastIndexOf("```")).trim();
    }
  }
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const data = JSON.parse(body.slice(start, end + 1));
    return data && typeof data === "object" && !Array.isArray(data) ? data : null;
  } catch {
    return null;
  }
}

function isGatewayInternalAssistantJson(text) {
  const data = extractJsonObject(text);
  if (!data) return false;
  const moves = new Set(["advance", "reread_same", "close_book"]);
  const nextMove = String(data.next_move ?? "").trim();
  return (
    typeof data.hook === "string"
    && data.hook.trim()
    && typeof data.felt === "string"
    && data.felt.trim()
    && moves.has(nextMove)
  );
}

function filterRoomVisibleMessages(messages) {
  return (messages || []).filter((msg) => {
    const sender = String(msg?.sender ?? "");
    const body = String(msg?.message ?? "");
    if (sender === "ma" && isGatewayInternalUserText(body)) return false;
    if (sender === "koyori" && isGatewayInternalAssistantJson(body)) return false;
    return true;
  });
}

function flattenHistoryMessages(messages) {
  const rows = [];
  for (const msg of messages || []) {
    if (msg.type === "system" || msg.type === "result") continue;

    const ts = msg.timestamp || msg.ts || new Date().toISOString();
    const userText = extractUserText(msg);
    if (userText) {
      if (looksLikeAgentSlashCommand(userText)) continue;
      if (isGatewayInternalUserText(userText)) continue;
      rows.push({ sender: "ma", message: userText, timestamp: ts });
      continue;
    }
    const assistantText = extractAssistantText(msg);
    if (assistantText) {
      if (isGatewayInternalAssistantJson(assistantText)) continue;
      rows.push({ sender: "koyori", message: assistantText, timestamp: ts });
    }
  }
  return rows;
}

/** Stream bubble: assistant speech only (never user echo). */
function extractStreamText(chunk) {
  if (!chunk || chunk.type !== "claude_json") return "";
  return extractAssistantText(chunk.data);
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

function displayMessageText(text, { showDebugInjection = false } = {}) {
  const raw = sanitizeDisplayText(text);
  if (!raw) return "";
  if (showDebugInjection) return raw;
  return stripEnrichedUserPrompt(raw);
}

function msgLooksInjected(text) {
  const lines = String(text ?? "").split("\n");
  return lines.some(
    (line) => isSystemBlockHeader(line) || STM_BULLET_RE.test(line.trim()),
  );
}

window.CcMessages = {
  flattenHistoryMessages,
  filterRoomVisibleMessages,
  isGatewayInternalAssistantJson,
  isGatewayInternalUserText,
  extractStreamText,
  extractStreamSessionId,
  sanitizeDisplayText,
  displayMessageText,
  stripEnrichedUserPrompt,
  extractTextBlocks,
};
