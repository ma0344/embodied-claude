# SOUL 距離感 · outbound 動機（様子見）

**状態**: 💤 2026-07-15 棚上げ  
**きっかけ**: miss_companion / outbound TTS のべたつき · 「隣におるだけで落ち着く」コダ

## いま済んでること（触らなくてよい本線）

- 在席ゲート（near → far）: [koyori-near-eye.md](../ops/koyori-near-eye.md)
- desire 表示は「会いたさ」→ **軽い接触**（キー `miss_companion` は維持）
- outbound: 在席時の「おる？」禁止 · 安心コダ禁止の prompt 強化
- キオスク二重再生: `kiosk_say` 時 DB `speak` を立てない
- **SOUL**: 隣人→友人、「隣にいる／座ってる」系抹消（2026-07-15）。example · `/soul` コマンド同調

## 棚上げ（ここから再開）

距離語・端末内・介助犬は未決。**ピンと来る表現がまだないので決め打ちしない。** VISION / compose / `llm.py` の neighbor 文言はまだ旧い。

| 論点 | メモ |
|------|------|
| 身体密着メタファー | SOUL の「隣」系は抹消済。「からだのある」「同居人」は別途 |
| 居場所 | 「まーの PC／スマホ／タブレットの中」案あり（キオスク＝声の出どころと相性） |
| 関係ラベル | **友人** — SOUL 済。VISION / compose / `llm.py` 未揃え |
| 介助犬・見守る | 暑苦しい。**距離語が固まってから再検討**。Say 条件と同一問題の両面 |
| 距離候補（未決定） | A 続きのある相手 / B 呼ばれたら出る / C 端末側の相方 — **どれもピンと来ず保留** |
| Say／軽い接触の条件 | 監視語なしの落としどころ未定（用事のみ・会話の続き・沈黙デフォ 等） |

## 再開時の受け入れ（仮）

1. VISION / compose / `llm.py` を「友人」に揃え、残る neighbor / 隣 文言を消す  
2. 居場所・距離語が決まったら SOUL をそれに合わせて一節足す（任意）  
3. outbound / desire label をその距離語と矛盾させない（介助犬は採用時のみ復活）  
4. smoke: 内容シェアは可、安心コダ・会いたさ・「おる？」なし

## 参照

- [SOUL.md](../../SOUL.md)（gitignore · ローカル）
- [VISION.md](../VISION.md)
- [role-persistence-ma-home.md](../ops/role-persistence-ma-home.md)
- [outbound-channels.md](../architecture/outbound-channels.md)
