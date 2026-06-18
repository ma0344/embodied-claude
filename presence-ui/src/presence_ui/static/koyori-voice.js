/**
 * Translate raw API data into Koyori-style natural language for the room UI.
 */
const KoyoriVoice = (() => {
  const DESIRE_PHRASES = {
    記憶を刻む: "いまの知見を、きちんと残しておきたい気分",
    振り返り: "少し立ち止まって、最近のことを振り返りたい",
    読書: "読みかけの本に、また目を通したい",
    休息: "ほんの少し、休みたい気持ちがある",
    記憶整理: "頭の中を、静かに整理したい",
    look_outside: "外の様子が、ちょっと気になる",
    miss_companion: "まーの近くに、もう少しいたいな",
    speak_up: "何か、声に出して伝えたいことがある",
    reflect: "自分のことを、少し考えたい",
  };

  const PHASE_VIBES = {
    idle: "静かな時間",
    listening: "まーの声を、聞いている",
    conversation: "まったりおしゃべり",
    deep_talk: "少し深い話",
    reflection: "じっくり考えごと",
    autonomous: "ひとりで、何かをしている",
    awaiting_reply: "返事を待っている",
    quiet_focus: "静かに集中している",
    ongoing: "会話の続き",
    cooling_down: "少し間を置いている",
    unknown: "穏やかな空気",
  };

  const AVAILABILITY_VIBES = {
    interruptible: "話しかけやすい",
    maybe_interruptible: "タイミング次第",
    do_not_interrupt: "静かにしていたい",
    available: "話しかけやすい感じ",
    busy: "少し集中している",
    do_not_disturb: "静かにしていたい",
    away: "そばにいないみたい",
  };

  const AFFECT_LABELS = {
    tired: "疲れ気味",
    stressed: "しんどそう",
  };

  const PRESENCE_VIBES = {
    absent: "そばにいない",
    possible: "いるかも",
    present: "そばにいる",
    speaking: "話している",
  };

  const ACTIVITY_VIBES = {
    working: "作業中",
    commuting: "移動中",
    eating: "食事中",
    resting: "休憩中",
    sleeping: "休んでいる",
    chatting: "おしゃべり中",
    unknown: "様子不明",
  };

  const ENERGY_WORDS = {
    low: "ゆったり",
    medium: "ふつう",
    high: "元気いっぱい",
  };

  const EXPERIENCE_KINDS = {
    agent_response: "さっきの応答",
    agent_voice_utterance: "声で話したこと",
    agent_observation: "気づいたこと",
    agent_autonomous_action: "自律の一手",
    body_affliction: "体の不調",
    open_loop_progress: "続きの話",
    boundary_respected: "境界を守った瞬間",
    desire_satisfied: "やりたかったことをした",
  };

  function desirePhrase(id) {
    return DESIRE_PHRASES[id] || `「${id}」が、心の隅にある`;
  }

  function sanitizeStatusText(text) {
    const t = String(text || "").trim();
    if (!t) return "（なし）";
    const compact = t.replace(/\s/g, "");
    if (compact.length >= 8 && [...compact].every((ch) => ch === "?")) {
      return "（視覚説明が壊れている — LM Studio vision を確認）";
    }
    if (t.length >= 8 && (t.match(/\?/g) || []).length / t.length > 0.4) {
      return "（説明テキスト不明瞭 — vision 要確認）";
    }
    return t;
  }

  function intensityLabel(level) {
    if (level >= 0.75) return "強く感じてる";
    if (level >= 0.45) return "ちょっと気になってる";
    return "ゆるやかに";
  }

  function formatDesires(desires, dominant) {
    if (!desires?.length) {
      return {
        headline: "いまは、特に強い衝動はない",
        lines: [],
        dominantLine: null,
      };
    }

    const sorted = [...desires].sort((a, b) => b.level - a.level);
    const top = sorted[0];
    const dominantItem = dominant
      ? sorted.find((d) => d.id === dominant) || top
      : top;

    const lines = sorted.slice(0, 4).map((d) => ({
      text: desirePhrase(d.id),
      intensity: intensityLabel(d.level),
      level: d.level,
    }));

    return {
      headline: `いま、${desirePhrase(dominantItem.id)}`,
      subline: `${intensityLabel(dominantItem.level)}感じてる`,
      lines,
      dominantLine: desirePhrase(dominantItem.id),
    };
  }

  function formatTemperature(temp) {
    if (!temp) {
      return { label: "体温", body: "まだわからない", mood: "neutral", icon: "○" };
    }

    const c = temp.celsius;
    const feeling = (temp.feeling || "").trim();

    if (feeling && feeling !== "unknown") {
      let mood = "comfortable";
      if (/熱|あっつ|しんど|やば/.test(feeling)) mood = "warm";
      else if (/涼|ひんや|静か/.test(feeling)) mood = "cool";
      else if (/快適|ええ感じ/.test(feeling)) mood = "comfortable";

      return {
        label: "からだの感覚",
        body: feeling,
        detail: c != null ? `${c.toFixed(1)}°C` : null,
        mood,
        icon: mood === "warm" ? "◎" : mood === "cool" ? "◇" : "○",
      };
    }

    if (c == null) {
      return { label: "からだの感覚", body: "まだわからない", mood: "neutral", icon: "○" };
    }
    if (c >= 75) {
      return {
        label: "からだの感覚",
        body: "ちょっと熱いかも…",
        detail: `${c.toFixed(1)}°C`,
        mood: "warm",
        icon: "◎",
      };
    }
    if (c >= 60) {
      return {
        label: "からだの感覚",
        body: "ほんのりあったかい",
        detail: `${c.toFixed(1)}°C`,
        mood: "comfortable",
        icon: "○",
      };
    }
    if (c >= 45) {
      return {
        label: "からだの感覚",
        body: "快適やで",
        detail: `${c.toFixed(1)}°C`,
        mood: "comfortable",
        icon: "○",
      };
    }
    return {
      label: "からだの感覚",
      body: "ひんやりしてる",
      detail: `${c.toFixed(1)}°C`,
      mood: "cool",
      icon: "◇",
    };
  }

  function formatSocialVibe(social) {
    if (!social) {
      return {
        headline: "部屋の空気",
        body: "まだ読み取れていない",
        tags: [],
      };
    }

    const phase = PHASE_VIBES[social.interaction_phase] || social.interaction_phase;
    const avail =
      AVAILABILITY_VIBES[social.availability] || social.availability;
    const energy = ENERGY_WORDS[social.energy] || social.energy;

    let body = social.summary;
    if (!body || body.length < 8) {
      body = `${phase}。${avail}。`;
    } else if (body.length > 120) {
      body = `${body.slice(0, 118)}…`;
    } else if (/^The person seems /i.test(body)) {
      const presence = PRESENCE_VIBES[social.presence] || "";
      const activity = ACTIVITY_VIBES[social.activity] || "";
      const parts = [presence, activity, avail].filter(Boolean);
      body = parts.length ? `${parts.join("、")}。` : body;
    }

    const tags = [phase, avail, energy].filter(Boolean);
    if (social.affect_label && social.affect_label !== "uncertain") {
      tags.push(AFFECT_LABELS[social.affect_label] || social.affect_label);
    }

    return {
      headline: "部屋の空気",
      body,
      tags,
      vibe: phase,
    };
  }

  function formatJourney(arcs) {
    if (!arcs?.length) {
      return {
        headline: "いまの旅",
        body: "静かに、次の一歩を探している",
        items: [],
      };
    }

    const items = arcs.slice(0, 3).map((arc) => ({
      title: arc.title,
      summary: arc.summary?.length > 90 ? `${arc.summary.slice(0, 88)}…` : arc.summary,
      status: arc.status,
    }));

    const lead = arcs[0];
    const body = lead.summary?.length
      ? lead.summary.length > 100
        ? `${lead.summary.slice(0, 98)}…`
        : lead.summary
      : `「${lead.title}」の途中`;

    return {
      headline: "いまの旅",
      body,
      items,
    };
  }

  function formatExperiences(experiences) {
    if (!experiences?.length) {
      return { headline: "さっきまで", body: "特に記録はない", items: [] };
    }

    const items = experiences.slice(0, 5).map((exp) => ({
      kind: EXPERIENCE_KINDS[exp.kind] || exp.kind,
      summary: sanitizeStatusText(
        exp.summary?.length > 80 ? `${exp.summary.slice(0, 78)}…` : exp.summary,
      ),
      ts: exp.ts,
    }));

    return {
      headline: "さっきまで",
      body: items[0]?.summary || "少し前のことが、まだ残っている",
      items,
    };
  }

  function formatPulse(pulse) {
    if (!pulse?.next_wake_at) {
      return {
        headline: "次の wake",
        body: "まだスケジュールされていない",
        lines: [],
      };
    }
    const sec = pulse.next_wake_in_sec;
    let when = pulse.next_wake_at;
    try {
      when = new Date(pulse.next_wake_at).toLocaleString("ja-JP", {
        timeZone: "Asia/Tokyo",
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      /* keep raw */
    }
    let inText = "";
    if (sec != null) {
      if (sec <= 0) inText = "もうすぐ（予定時刻を過ぎている）";
      else if (sec < 120) inText = `あと ${Math.round(sec)} 秒`;
      else inText = `あと ${Math.round(sec / 60)} 分`;
    }
    const lines = [
      inText ? `起きる: ${when}（${inText}）` : `起きる: ${when}`,
      pulse.last_action ? `前回: ${pulse.last_action}` : "",
      pulse.reason ? `理由: ${sanitizeStatusText(pulse.reason)}` : "",
      pulse.dominant_desire ? `pulse dominant: ${pulse.dominant_desire}` : "",
    ].filter(Boolean);
    return {
      headline: "次の wake",
      body: lines[0] || when,
      lines: lines.slice(1),
    };
  }

  function formatPlanPreview(plan) {
    if (!plan?.primary_move) {
      return {
        headline: "次の一手（plan）",
        body: "いまは読めない",
        lines: [],
      };
    }
    const allowed = (plan.allowed_actions || []).join(", ") || "（なし）";
    const forbidden = (plan.forbidden_actions || []).slice(0, 4).join(", ");
    const lines = [
      `move: ${plan.primary_move}`,
      plan.why ? `why: ${plan.why}` : "",
      `allowed: ${allowed}`,
      forbidden ? `forbidden: ${forbidden}` : "",
      plan.quiet_hours_active ? "quiet hours: ON" : "",
    ].filter(Boolean);
    return {
      headline: "次の一手（plan）",
      body: `${plan.primary_move}`,
      lines,
    };
  }

  return {
    formatDesires,
    formatTemperature,
    formatSocialVibe,
    formatJourney,
    formatExperiences,
    formatPulse,
    formatPlanPreview,
  };
})();
