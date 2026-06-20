# koyori バックログ

ma-home 側の全体優先順・記憶 E2E: [backlog-ma-home.md](./backlog-ma-home.md)（2026-06-19 更新）。

## LW — 自律の文学散歩・青空（ma-home）

こよりが自分で青空文庫を読む／Web 散歩する動機・実装。希望/恐れの整理と LW-1〜6 → [backlog-ma-home.md#lw--自律の文学散歩青空文庫--web-散歩合意-2026-06-19](./backlog-ma-home.md)。

## OBS — 能動観察 `/observe`（ma-home）

`/observe` 完遂不能（初手で止まる・「続けて」で再起動）の構造整理と gateway フェーズ化。OBS-0〜5 → [backlog-ma-home.md#obs--能動観察observe-完遂不能--gateway-フェーズ化合意-2026-06-20](./backlog-ma-home.md)。

## CAM — Tapo PTZ / ONVIF（ma-home）

細かい pan/tilt。**DS Cam では PTZ 可・SS Web ブラウザでは不可**（経路差）。直 ONVIF は embodied-claude 別問題。CAM-1〜3 → [backlog-ma-home.md#cam--tapo-ptz--onvif-細かい操作が効かない合意-2026-06-20](./backlog-ma-home.md)。

## EAR — 耳・環境音（ma-home）

Surface マイクで部屋の気配（会話・TV・静寂）を social に渡す計画。EAR-0〜5 → [backlog-ma-home.md#ear--耳環境音--surface-マイク合意-2026-06-19](./backlog-ma-home.md)。

## MEM — 記憶層・Dreaming（BIO-8 の次）

4 層（WM≈セッション → STM≈日次 → LTM → Deep/SOUL）と昇格パイプライン。詳細 → [backlog-ma-home.md#mem--記憶層セッション跨ぎ--dreaming](./backlog-ma-home.md)。

## RP — 人格の基底化（SOUL → 重み）

口調・まーとの関係（Deep 層）をプロンプト毎ターンから **stable append / LM Studio system / LoRA** へ。Phase 0→1→2→3（Phase 3 = MEM-6 接続）。

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | `presets/koyori-SOUL.core.md` → stable append | **済** |
| 1 | LM Studio 固定 system（append と二重回避） | **済**（ma-home 運用） |
| 2 | persona LoRA + 学習 JSONL export | **2a 済** |
| 3 | arc → SOUL パッチ提案 → LoRA v2（人間承認） | 未（MEM-6） |

手順 → [role-persistence-ma-home.md](./role-persistence-ma-home.md)

## WS — 会話中 WebSearch（ma-home）

まーが「調べて」と言ったときの CC `WebSearch`（LM Studio + Gemma）が **空結果 → 捏造 Sources** になりやすい問題。表示層修復は **済**；根本（gateway 差し替え等）は **MEM-5j / WS-1〜4** → [backlog-ma-home.md#mem-5j--会話中-websearchlm-studio--cc-websearch2026-06-20](./backlog-ma-home.md)。

## BIO-8 — 神経系（体調の自覚）

ma-home バックログ **BIO-8a〜d** と同じ。こより端では **目・声の不調がキオスクに届く**のがゴール（ステータス／着信／一声）。詳細 → [backlog-ma-home.md#bio-8--somatic-loop神経系体調の自覚](./backlog-ma-home.md)。

## VIS — VL 安定性（まー向け運用）

こよりの「目が曇った」叙述（BIO-8）とは別。**まーがログを見なくても** corrupt 率と相関が追える仕組み。受動計測（既存の see / observe_room）+ しきい値 ntfy。詳細 → [backlog-ma-home.md#vis--vision-healthvl-安定性相関ログ](./backlog-ma-home.md)。

## 本番: Keychron K4 MAX Bluetooth

手順: `docs/koyori-input-sharing.md`（MAC はランダムでも名前でペア）  
`koyori-pair-keychron.sh` / `koyori-connect-keychron.sh`

## キオスク URL（フェーズ3）

既定は **presence-ui `:8090`**（8080 直結ではない）。

```bash
# repo 更新後、koyori 実機で再インストール
cd ~/src/embodied-claude/scripts/koyori-kiosk
sudo ./install-koyori-kiosk.sh
```

`/etc/default/koyori-kiosk` の `KOYORI_WEBUI_URL` を手で直す場合:

`http://ma-home.local:8090/`（`/projects/...` は 8080 用。8090 だと JSON 404 画面になる）

キオスク起動時は `koyori-kiosk.sh` が自動で **`?kiosk=1`** を付与（C11b: 全幅チャット + ドロワー）。`kiosk=0` が設定されていても **強制で 1 に差し替え**。手動確認: `http://ma-home.local:8090/?kiosk=1`

repo 更新後は `sudo ./install-koyori-kiosk.sh` で `/usr/local/bin/koyori-kiosk` を再配置してから reboot。

## Input Leap — 済（V5, 2026-06-17）

ma-home KB/マウス → koyori キオスク。**動作確認済み。**

| 側 | 起動 |
|----|------|
| **ma-home** | `Get-Process input-leaps -EA 0 \| Stop-Process -Force` のあと `input-leaps.exe -c default.sgc --disable-client-cert-checking --disable-crypto` |
| **koyori** | `/etc/default/koyori-kiosk`: `KOYORI_INPUT_LEAP_SERVER`, `KOYORI_INPUT_LEAP_CRYPTO=0` → キオスク起動 + **watch**（client 落ちたら再起動） |

Surface だけ再起動した直後は ma-home Server がまだなら client が待つ/リトライ。`koyori-diagnose-input-leap` で確認。

手順・トラブル: `docs/koyori-input-sharing.md`（`libei1`、fingerprint、**Server 二重起動**に注意）。

診断: `koyori-diagnose-input-leap` / ma-home: `scripts/ma-home-input-leap-server.ps1`

ログオン自動起動: `.\scripts\install-input-leap-task.ps1`  

**日本語（Input Leap）**: 半/全 → **`'` リピート**の既知症状あり（使わない）。**Ctrl+Shift+Space**（Mozc）が本番。BT なら半/全可。

## タッチキーボード（onboard）— 保留

再有効化:

```bash
KOYORI_ONBOARD=1
KOYORI_OSK_BACKEND=onboard
sudo apt install -y onboard at-spi2-core
```
