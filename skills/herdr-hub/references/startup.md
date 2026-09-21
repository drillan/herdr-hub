# startup（agent の起動・配置）

roster は**編成の意図（desired state）**を記述する（[roster.md](roster.md)）。live に無いが `kind` を持つエントリは起動対象であり、hub が本書の手順で起動する。`kind` を持たない未 live エントリは即エラー（typo 検出を守るため）。

## agent の配置（2 形態 — roster の `placement` で選択。既定は `tab`）

### `placement: tab`（既定）— 新規 tab に置く

```bash
herdr tab create --cwd "$PWD" --label <name> --no-focus
# 応答の .result.root_pane.pane_id に agent start する
```

- 人数が増えても視認性が劣化しない。tab label に agent 名を付けるとサイドバーで役割が読める
- export（[roster.md](roster.md)）で tab label が役割の初期値になる関係とも相性がよい

### `placement: pane` — 現 tab に分割

```bash
herdr pane layout --pane "$HERDR_PANE_ID"    # 呼び出し pane の形状を見る
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

- 広い pane は `right`、狭い/縦長は `down`。同方向の連続 split は使い物にならない列・行を生む
- **2〜3 名までが実用域。** hub と並べて監視したい少数精鋭の編成向け

### 共通ルール・事後の移動

- **`--no-focus` を付ける** — 人間のフォーカスを奪わない
- **`--cwd "$PWD"` を明示する** — 呼び出し側の cwd を引き継ぐ
- 新 pane ID は応答の `.result.pane.pane_id`（tab なら `.result.root_pane.pane_id`）を読む。サイドバーの並びから推測しない
- 既存 pane を後から tab 化できる: `herdr pane move <pane_id> --new-tab --tab-label <name> --no-focus`（移動後は `.result.move_result.pane.pane_id` の新 ID を使う）。`pane move` には `--label`（pane 側のラベルと推定）と `--tab-label`（新規 tab のラベル）の 2 フラグがあり、tab 名を付ける意図では `--tab-label` を使う。`--label` の意味差は help に記載がなく実機未検証
- workspace / worktree の新設は人間が明示した場合だけ

## agent の起動

`agent start` は**利用可能な shell pane が前提**（対話 prompt にあり、foreground にコマンド・editor・agent が無い）。layout は作らない。

```bash
herdr agent start worker1 --kind codex --pane <pane-id>
herdr agent start reviewer --kind claude --pane <pane-id> -- --name reviewer
```

- 名前は `[a-z][a-z0-9_-]{0,31}`、live agent 間で一意。**roster の名前をそのまま使う**
- kind 一覧とオプションは `herdr agent start --help` で確認（`--kind` の possible values に列挙される。インストール済みバイナリが正典）
- agent 固有の引数は `--` 以降に渡す
- 起動 timeout は既定 30 秒。`agent_not_ready` で返っても**名前は保持され**、`agent read`/`send-keys` は使える。idle になるまで待ってから prompt する

### roster からの起動（`kind` を持つ未 live エントリ）

roster 検証（[roster.md](roster.md)）で起動対象と判定されたエントリを起動する手順:

1. `agent list` で **idle の live agent を棚卸し**し、「既存で足りないか」を先に問う — 空きがあるのに新規を起動するのは文脈予算の浪費。既存で足りるなら起動せず、その旨を人間へ提案する
2. **起動前に人間へ編成案を 1 行で確認する**（「roster の `worker1` `worker2` を `kind: claude` で起動します」）。agent の起動は pane が増え briefing 受信でトークンを消費し始める **環境への変更**なので、確認なしに自動で spawn しない
3. `placement` に従い tab/pane を用意し、`agent start <name> --kind <kind> --pane <pane-id>`
4. `agent list` で live 解決を再確認 → briefing 送信（**稼働途中の追加なら「現在の状態」入り 8 ブロック版**）

## 命名規約（重要）

宛先解決を 1 つの roster で済ませるため **3 系統の名前を揃える**:

| 系統 | 付け方 |
|---|---|
| herdr agent name | `herdr agent start <name>` の引数 |
| Claude セッション名 | `herdr agent start <name> --kind claude --pane <id> -- --name <同じ名前>`（`--` 以降は claude バイナリの argv になるため `claude` は書かない） |
| Codex セッション名 | codex 側の session name を同名に |

揃っていれば `herdr` / `sendmessage` / `codex-queue` どの transport でも roster の 1 名前で届く。

## 起動後

1. `herdr agent list` で live を確認
2. roster 検証（[roster.md](roster.md)）へ進む
3. briefing を送る（[briefing.md](briefing.md)）。briefing は **hub が書く** — 人間に書かせない

## 注意

- 自動起動は **`kind` を持つエントリ限定 + 人間の確認付き**。roster に無い agent を hub が勝手に作らない
- `agent start` に失敗した pane は残る — 閉じる判断は人間の指示があるまで行わない
