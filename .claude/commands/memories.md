---
description: "長期記憶を検索・一覧する（ローカル LLM 向け — MCP ツール名の正規ルート）"
allowed-tools:
  - "mcp__memory__list_recent_memories"
  - "mcp__memory__recall"
  - "mcp__memory__search_memories"
  - "mcp__memory__get_memory_stats"
  - "mcp__memory__remember"
---

# /memories — 記憶を触る

## 必須（ローカル LLM 向け）

記憶は **MCP ツール**。.mcp.json のサーバー名は `memory`（`memory-mcp` ではない）。

| やりたいこと | 呼ぶツール |
|--------------|------------|
| 最近の記憶一覧 | `mcp__memory__list_recent_memories` |
| 文脈で想起 | `mcp__memory__recall` |
| キーワード検索 | `mcp__memory__search_memories` |
| 統計 | `mcp__memory__get_memory_stats` |
| 新しく残す | `mcp__memory__remember` |

1. 上表の **MCP ツールを1回以上** 呼ぶ（`Skill(...)` / Bash / シェルではない）
2. ツール結果を要約して答える。記憶に無いことを「覚えてる」と言わない

## 禁止（これが Unknown skill になる）

- `Skill(memory-mcp:list_recent_memories)` — **存在しないスキル名**
- `Skill(mcp_memory_mcp_list_recent_memories)` — **存在しない**
- `Skill(list_skills)` — **存在しない**
- `memory-mcp` / `list_recent_memories` を Skill 名や Bash コマンドとして実行

MCP ツール名の形: `mcp__<サーバー名>__<ツール名>` → 例: `mcp__memory__list_recent_memories`

## 補足

- 毎ターンの連想想起は Hook（`[associative_recall]`）が自動注入。明示的に一覧・検索したいときだけこのコマンドを使う。
- ファイルを読んだあと文脈を補うなら `recall` にファイル名や話題を `context` に入れる。

入力: $ARGUMENTS
