# セッション引き継ぎ（handoff）



長い Cursor / Claude Code セッションは **チャット全文を次に持ち越さない**。次のエージェントが読むのは **短いアンカー文書 + backlog + Linksee recall** だけにする。



## 推奨パターン（4 層）



| 層 | 何を残す | 例 |

|----|----------|-----|

| **1. handoff 1 枚** | 索引・済・次・**運用ウォッチ**・Linksee 運用 | `docs/handoffs/YYYY-MM-DD-<topic>.md` |

| **2. backlog** | 設計・事例・未着手 ID（詳細の正） | `docs/archive/backlog-ma-home-full-2026-06-26.md` または `docs/tracks/` |

| **3. Linksee** | 開発セッションの決定・ caveat・**状況更新**（積極利用） | entity `embodied-claude-Win`、`recall` / `remember` |

| **4. ランタイム記憶** | まー／こよりが会話で使う fact | koyori `remember`（LTM）・`profile_gists`（L0） |



**Linksee 方針（ma-home 2026-06-25〜）**: 次セッション以降、Cursor 開発では Linksee で状況を更新していく。MEM-8 教訓どおり **重複 OK・抜け NG**。まーの生活 fact は koyori LTM にのみ（Linksee に二重保存しない）。



## handoff 1 枚のテンプレ



```markdown

# Handoff — YYYY-MM-DD — <topic>



## 次セッションで最初に読む

- backlog: <アンカー見出しへのリンク>

- 本ファイル

- Linksee: recall "embodied-claude <topic>"



## 済み

- ...



## 未 / 次

- ...



## 運用ウォッチ（日常・再起動後）

- いつ: check-koyori-stack / post-logon-smoke / ...

- 何を見るか: ...



## Linksee 運用

- 開始: recall

- 終了: remember（差分）+ 本ファイル更新



## 触ったファイル（代表）

- ...



## 起動・確認コマンド

- ...



## 次セッション用プロンプト（コピペ）

> ...

```



## やらないこと



- チャットログの貼り付け（トークン爆発・ノイズ）

- backlog と handoff の二重メンテ（**詳細は backlog、handoff は索引**）

- 「前のセッション覚えてる？」だけ — **handoff・backlog・Linksee のいずれかに残す**



## 次セッションの開始例



```

Linksee recall: "embodied-claude handoff 2026-06-25"

docs/handoffs/2026-06-25-mem8e-ops.md を読んでから続きを。

未着手は handoff の「次」から。チャット履歴は参照しない。

進捗があったら Linksee remember で状況を更新する。

```


