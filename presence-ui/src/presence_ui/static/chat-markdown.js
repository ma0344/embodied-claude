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
          return `<a href="${safe}" rel="noopener noreferrer"${title}>${text}</a>`;
        },
      },
    });
    configured = true;
  }

  function toSafeHtml(text) {
    const body = String(text ?? "").trim();
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

  window.ChatMarkdown = { toSafeHtml };
})();
