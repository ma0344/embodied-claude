# Claude Code セッション Export（ma-home）

こよりが文脈を失ったとき、`~/.claude/projects/` の JSONL から **まーのプロンプト含む全履歴** を Markdown に書き出す。

## スクリプト

```powershell
cd C:\Users\ma\src\embodied-claude

# セッション一覧（複数あるときはここで特定）
.\scripts\export-claude-session.ps1 -List

# 最新セッションを export（既定）
.\scripts\export-claude-session.ps1

# UUID または先頭数文字で指定
.\scripts\export-claude-session.ps1 -SessionId 6afd3195

# 出力先を指定
.\scripts\export-claude-session.ps1 -SessionId 6afd3195 -Output C:\temp\koyori-session.md
```

出力先（未指定時）: `%USERPROFILE%\.claude\memories\session-exports\`

## MD の構成

| セクション | 内容 |
|------------|------|
| **Dialogue** | まーの `user · prompt` とこよりの返答テキストだけ（復旧用に先に読む） |
| **Full log** | JSONL 全行（hook / tool / thinking / attachment 含む）。**編集用** |

`user · tool_result` はツール応答行として別ラベル。まーが打った文字列は **`user · prompt`** として必ず拾う。

## セッションの特定（複数 JSONL があるとき）

Claude Code のルール:

| 何 | 場所 |
|----|------|
| プロジェクト | `~/.claude/projects/<encoded-path>/` |
| 1 セッション = 1 ファイル | `<session-uuid>.jsonl`（ファイル名が session ID） |
| webui / CLI 履歴の見出し | `~/.claude/history.jsonl` の `display` + `sessionId` |

**encoded-path** の例:

- `C:\Users\ma\src\embodied-claude` → `C--Users-ma-src-embodied-claude`

### 一覧の見方（`-List`）

```
* 1  6afd3195-1f52-4474-b3be-714d48e958aa  2026-06-05 21:37     42  List recent memories
  2  80291241-b516-4b19-9731-1dcb08de8acb  2026-06-04 12:10      8  こんにちは
```

- `*` = 最新（`-SessionId` 無し export の既定）
- **session_id** 列 = `-SessionId` に渡す値（フル UUID または **一意な先頭 prefix**）
- 右端 = `ai-title` または `history.jsonl` の最後の `display`

### 指定の優先順位

1. `-SessionId <uuid>` … 完全一致、または prefix が **1 件だけ** にマッチ
2. 省略 … **更新日時が最新** の `.jsonl`
3. prefix が複数ヒット … エラー（もっと長く指定）

### webui の History との対応

webui 左の履歴タイトル ≒ JSONL 内の `ai-title` または `history.jsonl` の `display`。  
迷ったら `-List` で時刻と先頭プロンプトを見比べる。

## 復旧への使い方

1. `.\scripts\export-claude-session.ps1 -List` でセッションを選ぶ
2. export した MD を編集（不要な tool 行を削るなど）
3. 新規チャットで `@<export.md>` を添付するか、Dialogue 部分を貼って「ここから続けて」
4. 人格は `SOUL.md` + `/recover-from-compact` が本体。MD は会話の逐語の補助

## 注意

- export 先は git 外（秘密・パスが混ざることがある）
- Full log は長い。こよりに毎回丸ごと読ませるより、編集後の Dialogue 部分を使う
