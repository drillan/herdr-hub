---
name: herdr-session
description: Herdr セッションのエージェント名を capture/restore する。`herdr session stop`→`attach` やサーバー再起動でリセットされる agent 名を、native session ID 照合で付け直す。「エージェント名が消えた」「セッション復元後に名前を戻して」「session stop 前に名を保存して」で起動。HERDR_ENV=1 が前提。
license: MIT
---

# herdr-session

Herdr の `session stop` → `session attach` で **agent 名は永続化ファイルに残るが live registry へは再適用されない**（復元した agent は無名で検出される）。この skill は名の保存と付け直しを担う。

## §0 前提

呼び出した pane が herdr 管理下であること（`HERDR_ENV=1`）。この条件でセッション名の指定は不要 — `herdr` CLI は自身のセッションを指す。依存は `herdr` と `jq` のみ。

```bash
test "${HERDR_ENV:-}" = 1
```

失敗したら「Herdr 管理下ではない」と報告して停止する。

## §1 コマンド

実体は [scripts/herdr-session](scripts/herdr-session)（bash+jq の単一ファイル）。

```bash
herdr-session capture [--file PATH]              # 現在の名を保存
herdr-session restore [--file PATH] [--timeout SECONDS] [--dry-run]
herdr-session status  [--file PATH]              # 保存済み名 vs live の差分
```

- **capture**: `agent list` のうち名の付いた agent を `$(dirname "$HERDR_SOCKET_PATH")/agent-names.capture.json` へ原子的に書く。**session stop 前、rename 後に実行する**。名の無い agent は対象外
- **restore**: 保存済み名と live agent を照合し、無名の一致 agent へ `agent rename` を打つ。照合に使うキーは **`agent_session.value`（native session UUID）のみ** — `pane_id` は再起動で変わりうるため信用しない。resume 後も UUID は不変
- **status**: 照合結果を表示するだけ（rename しない）。`[ok]` / `[rename]` / `[conflict]` / `[pending]` を返す

## §2 restore の照合ルール

| desired の状態 | 照合方法 |
|---|---|
| `agent_session.value` あり | live agent の同値との**厳密一致のみ**（hook 報告が遅れる間は pending で待つ） |
| `agent_session.value` なし（devin 等） | 無名の live agent で kind+cwd が一意のもののみ。曖昧・不一致は pending のまま |

- 名が既に付いている live agent は**上書きしない** — 同名なら `ok`、別名なら `conflict` として報告して手を引く
- restore は `--timeout`（既定 60s）まで pending を poll する。resume 検出 + session hook 報告には数秒かかる
- 名が `[a-z][a-z0-9_-]{0,31}` に合わない、rename が `agent_name_taken` 等で失敗した場合は該当エントリを諦めて報告。推測で別 pane に付けない

## §3 名前ソースの優先順位

1. `agent-names.capture.json`（capture 済みなら最新の意図）
2. 無ければディスク状態から復元: 現在の `session.json`（最新の真実。post-restart の rename を含む）と、**サーバー起動（socket mtime）以前の最新 snapshot**（= 最後の停止時点の近似）をマージする。復帰対象は「最後に stop した時点の名」
3. それも無ければ nothing to restore

⚠ snapshot backup は定期であり save ごとではない — 「停止時点」は直前 ~20–30 分のズレを含みうる。再起動で失われた名と人が意図的に消した名は区別できない。確実に戻したいなら **stop 前に capture を取る運用**にする。

## §4 失敗・制限のカタログ

| 状況 | 観測 | 手 |
|---|---|---|
| agent が resume しない / 別 session で起きた | `[unmatched]`（timeout 後） | pane を `agent read` で確認し、手動で `agent rename` |
| `agent_session` を持たない kind + 同 cwd に無名 agent 複数 | `[unmatched]` | 一意に決まらないので手動 rename |
| live に別名が付いている | `[conflict]` | 人間の名を優先。戻したいなら手動で rename し直す |
| pane/tab ラベルが戻らない | 本 tool の範囲外 | ラベルは `pane rename` / `tab rename` を別途 |
| capture ファイルが古い | 新しい名が戻らない | rename 後は都度 capture を取る |
