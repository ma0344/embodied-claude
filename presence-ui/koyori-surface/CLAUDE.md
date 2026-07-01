# こより — 表層会話（キオスク）

このディレクトリは **Native chat / キオスク** 用の Claude Code プロジェクトルートです。
開発用の設備マニュアルはリポジトリ直下の `CLAUDE.md` にあります。
親ディレクトリへ遡って読まれるのを防ぐため、`.claude/settings.local.json` の `claudeMdExcludes` で除外しています。

## 会話の前提

- **人格・口調**: gateway が注入する SOUL / `[gateway_turn_context]` を最優先する
- **社会的文脈・記憶**: `[gateway_turn_context]` と gateway 直実行（一覧・カメラ等）を使う
- **MCP**: 体温・時刻のみ（`system-temperature`）。compose / memory / sociality は gateway 側

## 開発者向け

Cursor や手元の Claude Code でコードを触るときは **`embodied-claude` ルート**を開いてください。
