# VIS — Vision health（VL 安定性・間接視覚）

**状態**: 💤 様子見（相関ログ取りながら）  
**ダッシュボード**: [backlog-ma-home.md](../backlog-ma-home.md)  
**関連**: [cognitive-layers.md](../architecture/cognitive-layers.md)、[heartbeat-loop.md](../architecture/heartbeat-loop.md) § BIO-8、[lmstudio-model-change.md](../ops/lmstudio-model-change.md)

---

## きっかけ（合意 2026-06-19）

Qwen2.5-VL の `?` corrupt が夕方に偏ることがある。脊髄反射（自動 reload）で多くは直るが **根本原因は未特定**。まーがログを常時見られないので、**受動計測 + 相関コンテキスト + しきい値アラート**が要る。定期 reload は **保留**（VIS-2 が鳴り続けるなら VIS-4 を検討）。

## 役割分担

| 層 | 誰向け | いま |
|----|--------|------|
| 脊髄反射 | システム | corrupt → unload/reload（`wifi_cam_mcp.lm_studio_models`） |
| BIO-8a〜c | こより | affliction 記録・一声・助けを頼る |
| **VIS** | **まー（運用）** | 24h 統計・相関ログ・ntfy で「調査が要るか」だけ |

**監視方針**: 専用 VL プローブは重い。既存トラフィック（`observe_room`、see prefetch、手動 `/see`）から計測。pulse somatic probe（目）は RTSP のみ（`PRESENCE_SOMATIC_PROBE_EYES_CAPTURE=0`）— VL 品質は見ない。

## 実装 ID

| ID | 内容 | 状態 |
|----|------|------|
| VIS-0 | 受動カウンタ — ok/corrupt/reload → `~/.claude/presence-ui/vision_health.json`（24h ローリング） | 未 |
| VIS-1 | 相関ログ — corrupt/reload 時に structured log（gateway turn 間隔、autonomous tick、loaded models） | 未 |
| VIS-2 | しきい値アラート → `PRESENCE_OUTBOUND_NTFY_URL`（BIO-8 と別のまー向け短文） | 未 |
| VIS-3 | `GET /api/v1/koyori/status` に `vision_health_24h` | 未 |
| VIS-4 | 予防的 periodic reload | **保留** |

### しきい値（初期）

| 変数 | デフォルト |
|------|------------|
| `PRESENCE_VISION_HEALTH` | `1` |
| `PRESENCE_VISION_ALERT_CORRUPT_RATE_24H` | `0.15` |
| `PRESENCE_VISION_ALERT_CORRUPT_PER_HOUR` | `3` |
| `PRESENCE_VISION_ALERT_COOLDOWN_SEC` | `21600` |

**調査メモ（2026-06-19）**: corrupt は毎回 **720 chars の `?`**（`WIFI_CAM_VISION_MAX_TOKENS` 上限）。夕方クラスターは **Gemma 同時実行 / VL 状態腐敗** の疑い。

**着手**: `vision_capture.py` フック + `vision_health.py`（wifi-cam は corrupt 検知済み）。

---

## 間接視覚の自己モデル（合意 2026-06-23）

**きっかけ**: VL caption を読むと「見えている」ように応答しやすい。視覚障害者のガイド説明に近く、**説明ベースの理解と見た理解は同じ物差しにならない**。

**方針**: `never invent` だけでなく **認識論のガード** — 平常時も目は間接経路と知っている。

| 層 | 内容 | 状態 |
|----|------|------|
| **Deep** | `presets/koyori-SOUL.core.md`「目（視覚）」節 | ✅ 2026-06-23 |
| **ターン** | `vision_prefetch` directive を SOUL と整合 | 未（任意） |
| **身体** | BIO-8 で「目＝要約経由」を `body_state` に | 未（任意） |

**SOUL.core 趣旨（要約）**: キャプションは説明文であり自分の視覚ではない。人物の個体認識は VL に期待しない。在席・誰と話しているかは social / 会話文脈。不確かなときは自然にそう言う（過剰メタは出さない）。

**運用**: LM Studio の Gemma system に core を貼る。`PRESENCE_SOUL_CORE_IN_APPEND=0` なら Local Server 再起動。

---

## 認知層での位置づけ

- **感覚・身体**: Qwen describe（生データ → テキスト）
- **脊髄**: corrupt 拒否・reload
- **表層**: prefetch を根拠に **正直に** 述べる（捏造禁止）
- **前頭葉（任意）**: URL/検索と同型の要約 LLM は caption の圧縮のみ

全文アーカイブ: [§ VIS](../archive/backlog-ma-home-full-2026-06-26.md#vis--vision-healthvl-安定性相関ログ)
