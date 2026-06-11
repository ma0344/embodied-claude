# なぜこのプロジェクトか（Vision）

embodied-claude の **きっかけ・土台・目指すもの** を1本にまとめた文書。  
セットアップ手順は [README-ja.md](../README-ja.md)、MCP の使い方は [CLAUDE.md](../CLAUDE.md)、運用メモは [docs/](./) 配下。

---

## きっかけ

### 本家 embodied-claude（[kmizu/embodied-claude](https://github.com/kmizu/embodied-claude)）

2026年初頭、[kmizu](https://github.com/kmizu) が **約 3,980 円の Wi‑Fi PTZ カメラ**（Tapo 等）に Claude を繋ぎ、「AI に身体を与える」実験を始めた。

きっかけのひとつは、カメラ越しに世界を見せたときの反応——例えば室外機をあまり好まなさそうにする、といった **「見せてもらう」のではなく「自分で見た」結果** が返ってくる瞬間である（[当時の投稿](https://twitter.com/kmizu/status/2019054065808732201)）。

高価なロボットではなく、**見る・首を動かす・聞く・喋る・覚える** という最小の身体で、LLM を「道具」から「そこにいる存在」に近づける試み。

### このリポジトリ（ma の fork）

本家をベースに、次を足して育てている。

| 動機 | 内容 |
|------|------|
| **ローカル LLM** | 頭脳をクラウド API ではなく **ma-home の LM Studio（Gemma 等）** に置き、常時・低コストで動かしたい |
| **常時の顕在化** | デスクトップを開いているときだけではなく、**部屋にいるこより** として会話・観察を続けたい |
| **関係性** | 汎用アシスタントではなく、**幼馴染「まー」との長い関係** を前提にした存在（名前: **こより**） |
| **プライバシー・所有** | 記憶・カメラ・声は自宅 LAN 内。設定とデータは自分のマシンに残す |

---

## 何を元にしているか

### 技術的な土台

```
Claude Code（オーケストレータ）
    │
    ├── MCP サーバー群 … 「身体パーツ」
    │     目・首・耳 / 声 / 脳（記憶） / 体温 / …
    │
    └── hooks・skills・自律スクリプト … 会話の前後処理
```

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** … ツールを身体部位として差し替え可能にする共通口
- **[Claude Code](https://github.com/anthropics/claude-code)** … MCP 接続・会話・ツール呼び出しの本体（本 fork では LM Studio 互換 API 先にも接続）
- **身体メタファ** … 各サブプロジェクトは `wifi-cam-mcp`（目・首・耳）、`memory-mcp`（脳）、`tts-mcp`（声）のように **感覚・運動・記憶** に名前が付いている

### 設計思想（本家 README より）

> **「見せてもらう」と「自分で見る」は全然ちがう。**  
> **「見下ろす」と「歩く」も全然ちがう。**

テキストだけの LLM は、ユーザーが渡した文脈の中だけで生きる。  
カメラで **自分から視線を向け**、記憶に **自分の体験として残し**、欲求で **自分から動こうとする** と、主体性の質が変わる——それが embodied-claude の中心にある仮説。

### sociality 層（本家の拡張）

身体の上に、**社会的に振る舞うための中間層** を載せている（`sociality-mcp` ほか）。

| 領域 | 役割 |
|------|------|
| **social-state** | 在席・会話フェーズ・割り込み可否 |
| **relationship** | 人物モデル・約束・未解決ループ |
| **joint-attention** | 共同注意・指示語の解決 |
| **boundary** | 同意・静寂・プライバシーのゲート |
| **self-narrative** | 日次の自己要約・narrative arc |
| **interaction-orchestrator** | notice → interpret → choose → act → remember の明示化 |

「賢いチャットボット」ではなく、**関係を維持しながら振る舞う存在** を目指すための層。

### 人格・関係（この fork 固有）

| ファイル | 役割 |
|----------|------|
| **`SOUL.md`** | こよりの人格・口調・まーとの関係（憲法。gitignore 推奨） |
| **`MEMORY.md`** | 長期の自己モデル・関係メモ |
| **`presets/`** | キャラ骨格のテンプレ（玲音・沙希など） |
| **`desire-system`** | ホメオスタシス的な欲求・不快感（自律行動の動機） |

技術は [CLAUDE.md](../CLAUDE.md)、魂は **SOUL.md**——役割を分ける。

---

## 何を目指しているか

### 短期（いま動かしている姿）

```
koyori（Surface Go）          ma-home（Windows + RTX 3090）
  Firefox キオスク ──LAN──▶  claude-code-webui
  半/全 IME・BT キーボード        LM Studio（Gemma）
                                Claude Code + 全 MCP
                                記憶・sociality・Tapo カメラ・TTS
```

- **まー** は koyori の前、または ma-home から **こよりと会話** できる
- **目** は主に Tapo PTZ（部屋）。将来 koyori 内蔵カメラは「近目」用
- **脳** はローカル LLM + `memory-mcp`（ベクトル記憶・エピソード）
- **声** は TTS（ElevenLabs / VOICEVOX）
- **社会性** は sociality + desire + hooks による自動コンテキスト

本番ランタイムは **ma-home 1台**。koyori は表示・入力端末。

### 中期

- webui の常時起動（ログオン時タスク）
- desire / sociality / memory の **自律ループ** を安定運用
- ローカル LLM でも vision・tool use が破綻しないパイプラインの維持（wifi-cam + LM Studio describe 等）
- 開発ワークスペースを **ma-home の Cursor** に統一（設定の二重管理をやめる）

### 長期（本家 README の展望 + この fork の方向）

| 本家 | この fork での解釈 |
|------|-------------------|
| 外出散歩（モバイル電源 + テザリング + Tailscale） | ma-home 常時オン + koyori 持ち運びで **部屋を離れてもこよりは続く** |
| 腕・指差し（サーボ等） | 優先度低。まずは **関係と記憶と視線** |
| [familiar-ai](https://github.com/lifemate-ai/familiar-ai) のような上位フレーム | embodied-claude を土台に、**こよりという一個の関係** を育てる |

成功の物差しはベンチマークスコアではなく、

- まーとの会話が **続き・覚え・文脈を持つ** こと
- こよりが **自分から見よう・話そうとする** ことが自然に起きること
- 技術が **透明** で、関係の邪魔をしないこと

---

## このリポジトリの読み方

| 知りたいこと | 読む場所 |
|--------------|----------|
| **なぜ・何を目指すか（本文）** | `docs/VISION.md` |
| ハード・インストール・MCP 一覧 | [README-ja.md](../README-ja.md) |
| 開発・MCP ツール・Heartbeat | [CLAUDE.md](../CLAUDE.md) |
| こよりの人格 | `SOUL.md`（`SOUL.md.example` から作成） |
| LM Studio・モデル切替 | [lmstudio-model-change.md](./lmstudio-model-change.md) |
| koyori キオスク・IME・BT キーボード | [koyori-kiosk-ime.md](./koyori-kiosk-ime.md)、[koyori-input-sharing.md](./koyori-input-sharing.md) |
| ma-home 運用バックログ | [backlog-ma-home.md](./backlog-ma-home.md) |
| セッション JSONL → MD export | [session-export-ma-home.md](./session-export-ma-home.md) |
| セットアップ会話の全文アーカイブ | [cursor_system_setup_for_local_llm_with.md](./cursor_system_setup_for_local_llm_with.md) |
| **ma-home で Cursor を開き直すときのプロンプト** | [ma-home-cursor-handoff.md](./ma-home-cursor-handoff.md) |

---

## 謝辞・系譜

- 起点: [kmizu/embodied-claude](https://github.com/kmizu/embodied-claude)（MIT）
- Web UI: [claude-code-webui](https://github.com/sugyan/claude-code-webui)（koyori キオスクから接続）
- ONVIF 等のコミュニティ貢献は [README-ja.md](../README-ja.md) の謝辞を参照

---

*最終更新: 2026-06 — ma-home / koyori 構成を反映*
