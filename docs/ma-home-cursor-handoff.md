# ma-home Cursor 引き継ぎプロンプト

ma-server（Remote SSH）から **ma-home ローカル** に開発場所を移したあと、  
`git pull` した直後の **新しい Cursor Agent チャット** に貼る用。

---

## pull してから（1回だけ）

```powershell
cd C:\Users\ma\src\embodied-claude
git pull
# 秘密ファイルを触った場合は必要に応じて:
# .\scripts\sync-ma-home-git.ps1
```

Cursor: **File → Open Folder** → `C:\Users\ma\src\embodied-claude`（Remote SSH は使わない）

---

## 貼るプロンプト（全文コピー）

```
@docs/VISION.md
@docs/cursor-session-export-2026-06.md
@CLAUDE.md

あなたは embodied-claude（こより fork）の開発アシスタント。
ワークスペースは ma-home ローカル: C:\Users\ma\src\embodied-claude
以前は ma-server へ SSH Remote で開発していた。チャット履歴は引き継がれていない。

## 前提（必ず守る）

- **本番ランタイムは ma-home のみ**（LM Studio + Claude Code + MCP + claude-code-webui）
- **koyori** は Firefox キオスク → ma-home **presence-ui (:8090)** の表示端末（8080 直結ではない。git pull はキオスク更新時だけ）
- **ma-server** はもう開発に使わない（任意の旧箱）
- エージェント名は **こより**。まーは幼馴染。人格は SOUL.md（リポジトリ直下、gitignore）
- LLM: **google/gemma-4-12b-qat** @ LM Studio `http://127.0.0.1:1234`
- 設定: `.claude/settings.local.json`、`.mcp.json`（Windows パス）、`lmstudio.token`
- 長期記憶は ma-home の `%USERPROFILE%\.claude\memories\`（memory-mcp）

## セットアップ会話の全文が必要なら

@docs/cursor_system_setup_for_local_llm_with.md を読む（5800行超。詳細な経緯・トラブルシュート）

## いまの優先バックログ

1. 開発を ma-home Cursor に固定（完了扱いでよい）
2. webui 常時起動 → `scripts/install-webui-task.ps1`（`docs/backlog-ma-home.md`）
3. desire / sociality / memory 自動化の安定運用
4. koyori 内蔵カメラ（近目）は PoC 段階。本番の目は Tapo wifi-cam

## 最初にやってほしいこと

1. 上記ファイルを読んで文脈を把握する
2. リポジトリを軽く確認し、ma-home 前提で矛盾する記述があれば教える
3. 次に進めるなら **webui 常時起動** か、私が指定するタスクを聞いてから着手する

質問があれば先に聞いて。勝手に大きなリファクタはしない。
```

---

## 短い版（要約だけで足りるとき）

```
@docs/VISION.md @docs/cursor-session-export-2026-06.md @CLAUDE.md

ma-home ローカルで embodied-claude（こより）開発を続ける。
本番は ma-home（LM Studio + MCP + webui :8080 + presence-ui :8090）、koyori キオスクは :8090。
以前 ma-server SSH で開発していたが履歴は無い。上記3ファイルで文脈を読んで、次のタスクを聞いてから進めて。
```

---

## 補足

| ファイル | 役割 |
|----------|------|
| `VISION.md` | なぜ・何を目指すか |
| `cursor-session-export-2026-06.md` | 移行直前の要約（アーキ・完了事項・バックログ） |
| `cursor_system_setup_for_local_llm_with.md` | セットアップ会話の全文 Export |
| `CLAUDE.md` | MCP・運用・Heartbeat |

Cursor の `@` でファイルを添付してから送ると、パス解決が確実。
