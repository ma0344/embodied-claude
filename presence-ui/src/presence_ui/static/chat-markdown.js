/**
 * Safe Markdown rendering for chat bubbles (marked + DOMPurify).
 */
(function () {
  const ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "del",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "a",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
  ];
  const ALLOWED_ATTR = ["href", "title", "class", "align", "start"];

  let configured = false;

  const GOOGLE_SEARCH_RESULTS_LABEL_RE =
    /^Google Search Results for (.+)$/i;

  function rebuildGoogleSearchUrl(query) {
    return `https://www.google.com/search?q=${encodeURIComponent(String(query || "").trim())}`;
  }

  function hrefLooksCorrupt(href) {
    const raw = String(href || "");
    if (!raw) return true;
    if (/[\u3000-\u9fff]/.test(raw)) return true;
    return /%[0-9A-Fa-f](?![0-9A-Fa-f])/i.test(raw) || /%(?![0-9A-Fa-f]{2})/i.test(raw);
  }

  function isValidHttpUrl(href) {
    try {
      const url = new URL(String(href || ""));
      return /^https?:$/i.test(url.protocol) && !hrefLooksCorrupt(href);
    } catch {
      return false;
    }
  }

  /** WS-1: drop Sources blocks that cite no real URL (empty WebSearch hallucination). */
  function stripFabricatedSourcesBlock(text) {
    let raw = String(text ?? "");
    const trailMatch = raw.match(/\n(?:\*\*)?Sources(?:\*\*)?:?\s*\n([\s\S]*)$/i);
    if (trailMatch) {
      const body = trailMatch[1].trim();
      if (!/https?:\/\/[^\s)<>"]+/i.test(body)) {
        raw = raw.slice(0, trailMatch.index).trimEnd();
      }
    }
    const inlineMatch = raw.match(/\n(?:\*\*)?Sources(?:\*\*)?:\s*[^\n]+$/i);
    if (inlineMatch && !/https?:\/\//i.test(inlineMatch[0])) {
      raw = raw.slice(0, inlineMatch.index).trimEnd();
    }
    return raw;
  }

  /** Fix model-fabricated Google citation links after empty WebSearch tool results. */
  function repairCitationMarkdown(text) {
    return String(text ?? "").replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/gi,
      (match, label, href) => {
        const trimmed = String(label || "").trim();
        const labelMatch = GOOGLE_SEARCH_RESULTS_LABEL_RE.exec(trimmed);
        if (labelMatch) {
          return trimmed;
        }
        if (!isValidHttpUrl(href)) {
          return trimmed;
        }
        return match;
      },
    );
  }

  function escapePlain(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function configureMarked() {
    if (configured || typeof marked === "undefined") return;
    marked.setOptions({ breaks: true, gfm: true });
    marked.use({
      renderer: {
        link(token) {
          const href = token.href || "";
          const safe =
            /^(https?:|mailto:)/i.test(href) ? href : "#";
          const title = token.title
            ? ` title="${String(token.title).replaceAll('"', "&quot;")}"`
            : "";
          const text = token.text || safe;
          return `<a href="${safe}" target="_blank" rel="noopener noreferrer"${title}>${text}</a>`;
        },
      },
    });
    configured = true;
  }

  function toSafeHtml(text) {
    const body = stripFabricatedSourcesBlock(
      repairCitationMarkdown(String(text ?? "").trim()),
    );
    if (!body) return "";
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      return escapePlain(body);
    }
    configureMarked();
    const raw = marked.parse(body);
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS,
      ALLOWED_ATTR,
      ALLOW_DATA_ATTR: false,
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
    });
  }

  window.ChatMarkdown = {
    toSafeHtml,
    repairCitationMarkdown,
    stripFabricatedSourcesBlock,
    rebuildGoogleSearchUrl,
  };
})();
