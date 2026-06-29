# VIS-e4b POC 合格判定（2026-06-29）— 最小チェック追記

**総合: ✅ e4b vision 本番切替（2026-06-29 · ma-home 合意）** — corrupt なし。e4b は表現豊かだが `finish=length` のぶれは vis-health で継続監視。

参照: [vis-health.md](../docs/tracks/vis-health.md) · 実行 `scripts/run-vis-e4b-min-check.ps1`

---

## 最小チェック（2026-06-29 · v2 条件）

共通: `WIFI_CAM_VISION_PROMPT` 73字（local.env）· system role · `-Isolate` · Qwen vs e4b

| 画角 | レポート | Qwen | e4b | e4b finish | 判定 |
|------|----------|------|-----|------------|------|
| USB 外向き | [usb-outside-v2-check](vis-e4b-poc-2026-06-29-usb-outside-v2-check.md) | 128字·stop·4文 | **52字·length·途中切れ** | ❌ | 同日の [v2](vis-e4b-poc-2026-06-29-usb-outside-v2.md) は 259字·stop — **再現性△** |
| Tapo desk | [tapo-desk-v2](vis-e4b-poc-2026-06-29-desk-tapo-desk-v2.md) | 93字·stop·短文 | 169字·**length**·デスク途中 | ❌ | 内容は当たりだが未完 |
| Tapo dining（リビング） | [tapo-dining-v2](vis-e4b-poc-2026-06-29-dining-tapo-dining-v2.md) | 124字·stop | **293字·stop·6文** | ✅ | **e4b 明確に勝ち**（掲示板・窓・ソファ・人物なし） |

### 所感

- **dining 画角**: e4b は手動 LM Studio テストに近い厚み。Qwen より具体性・否定（人物なし）が明確。
- **USB / desk**: 同一プロンプトでも e4b が `length` で切れる run あり。Markdown 化し始めてトークンを食うパターン（前回 isolate 33字 run と同型）。
- **local.env のプロンプト**に「箇条書き・見出し禁止」が無い（コード側デフォルト 90字には含む）。切替前に追記推奨。

---

## 合格基準 vs 結果

| # | 基準 | 結果 |
|---|------|------|
| 1 | 日本語 5〜8 文 | dining e4b ✅ / 他は△〜❌ |
| 2 | grounded | dining e4b ✅ / Qwen desk「窓やモニタ見えない」は画像と要確認 |
| 3 | corrupt なし | ✅ 全 run |
| 4 | e4b finish=stop（3画角） | **1/3 安定**（dining）。USB は同日 good/bad 混在 |
| 5 | model-agnostic reload | 未（別 PR） |

---

## 判定まとめ（更新）

| 項目 | 結果 |
|------|------|
| **e4b vision 切替** | **✅ 実施** — `scripts/enable-vis-e4b-ma-home.ps1` · local.env + `.mcp.json` |
| **切替後** | LM Studio: Qwen unload · e4b のみ · `restart-presence-ui` |
| **残リスク** | e4b の length 切れ — 夕方クラスター・isolate 直後の不安定さは継続観測 |

**Script `ok` フラグ**は corrupt のみのため全 ✅ だが、**人間基準では dining 1 本が確実、他 2 本はぶれ**。
