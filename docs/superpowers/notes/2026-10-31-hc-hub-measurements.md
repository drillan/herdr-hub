# hc-hub 実装前の実測結果

実測日: 2026-10-31。環境: hc 0.1.15（spec §3 は 0.1.14 で確認）。使い捨てのターミナルで確かめ、すべて `hc kill` → `hc rm` で片付けた。

## spec と違う結果

- **項目 7**: command 起動（`hc run --bg --name X claude "<依頼>"`）で依頼を argv に渡しても、`<hc from=… reach=…>` のタグは付かず、`first_message` も返らない。依頼は argv そのままの文字列として claude の最初の入力になる。`hc run` の出力は `{"address","agent","cwd","name","parent","state","turn"}` のみ。タグ付きで届くのはテンプレート経由（`hc run <template> "<依頼>"`）の場合と読める（`hc --skill` の記述。テンプレートでは未実測）。後続の `hc send` は送り主のタグ（`<hc from="t7">…</hc>`）が付くが、`reach=` は付かない（親でない送り手のため）。したがって、報告の宛先（`hc send <hub> …`）は依頼文に自分で書く。
- **項目 5**: symlink が梱包されるかは公開前に確定できない。確定できないので、複製と同一性の検査を採る（spec 4.8 の後段）。
- **項目 2**: この環境の Codex は認証が失効しており（`account/read failed … refresh token was revoked`）、起動直後に exit 1 で終了した。状態の報告は**未確認**。開発者が Codex に再ログインした後に実測し直す必要がある。それまでは「Codex が blocked を報告するか不明」として 4.4 の起動時の検査を前提にする。

## 項目ごとの結果

### 1. `hc wait --children any` はターン終了で返るか: 返る

- コマンド: `hc run --bg --name m-claude --cwd <worktree> claude "Bash で sleep 25 を実行し、終わったら ok とだけ返事して"` → `hc wait --children any --timeout 90`
- 結果: 約 2 秒で返った。`{"children":[{"reason":"status","status":"done","terminal":"t17","turn":1,"ended":true}],"reason":"children",…}`
- この worker は「sleep 25 はバックグラウンドで実行中です。終わったら ok と返します」と宣言してターンを終え（画面末尾 `1 shell still running`）、status は `done`。つまり spec が懸念した「再開すると宣言しただけでターンを終える止まり方」も `wait --children any` で拾える。
- 影響: Task 6 は worker ごとの `hc wait <t>` を走らせる代替手順にしなくてよい。ただし返ったあとは画面を読み、宣言だけで終わったか完了かを見分ける。
- 注意: `wait` は返ったあとで同じ子がまだ idle/done のとき、次の `wait --children any` が即時に返る可能性がある（今回は完了済みの子を片付けてから測ったため未検証）。

### 2. Codex の状態報告: 未確認（上記）

### 3・8. ラベルのキーに `-` と `.`、値に `/` を入れられるか: 入れられる

- コマンド: `hc label m-lbl hc-hub.lane=x hc-hub.brief=tmp/a/b.md`、続けて `hc label m-lbl hc-hub.abs=/home/x/y.md`
- `hc get m-lbl --json` の `labels`: `{"hc-hub.abs":"/home/x/y.md","hc-hub.brief":"tmp/a/b.md","hc-hub.lane":"x"}`
- `hc ls --label hc-hub.lane=x` と `hc ls --label hc-hub.brief=tmp/a/b.md` は該当ターミナルだけを返し、一致しない値（`hc-hub.lane=nope`）では `terminals: []`。絶対パスの値も可。
- 注意: `hc ls` の一覧 JSON には labels 本体は出ない（`where` のみ別枠で出る）。labels を読むには `hc get <t> --json`。`hc get` には、herdr-app 由来でないターミナルにも `where` ラベルが後から付くことがある（今回は `labels:{"where":"herdr-hub / 1"}`）。
- 影響: Task 4・7 のラベル設計（`hc-hub.lane`、`hc-hub.brief`）はそのまま使える。

### 4. `--outlive-parent` の子に新しい hub から操作できるか: すべて通る

- コマンド: 使い捨ての親 `hc run --bg --name m-par sh -c "hc run --bg --outlive-parent --name m-kid --cwd <worktree> claude '…'; sleep 1"`
- 親 m-par は `state: finished, reason: exited`。子 m-kid は `live`、`die_with_parent: false`、`parent: "t18"`（終了した親）のまま。
- 別ターミナル（t7）から:
  - `hc send m-kid "…"` → `{"started":true,"status":"done","turn":1}`、子の画面には `<hc from="t7">…</hc>` として届いた。
  - `hc wait m-kid` → 作業完了で `reason: status, status: done` を返した。
  - blocked の再現: `hc send m-kid "AskUserQuestion ツールで…質問して"` の後 `hc wait m-kid --timeout 60` は約数秒で `{"reason":"status","status":"blocked","turn":3}` を返した。親でない hub の `wait` も blocked で返る。
  - blocked の子への `hc send m-kid "x"` は exit 9: `{"error":{"kind":"blocked","message":"t19 is blocked (question)","hint":"typing would answer its dialog; read its screen first (hc read t19), or --force"}}`
  - `hc kill m-kid` → 通り、`state: finished, reason: killed`。`hc rm` も通る。
- 影響: Task 6 の「引き継いだ worker の見張り」は `hc wait <t>` でよい（作り直し不要）。

### 5. symlink の梱包: 確定できない（上記「spec と違う結果」）

`gh skill publish --dry-run` は検証結果のみで梱包物を一覧せず、`gh skill preview` は公開後にしか使えない（計画のレビューで確認済み）。確定できないので、複製と同一性の検査を採る（spec 4.8 の後段）。この実測では symlink も branch も作っていない。

### 6. `notes = false` を確かめる方法: 問い合わせる手段は無い

- `hc --help`・`hc server --help`（サブコマンドは start/stop/status/restart のみ）・`hc server status`（core の id・pid・version などのみ）・`hc schema`（`config` という語は出るが notes の現在値を返す操作ではない）を調べた。`hc --help` 末尾に「Settings: ~/.config/herdr-core/config.toml. notes = false: hc types nothing on its own」とある。
- 検査方法: `${XDG_CONFIG_HOME:-$HOME/.config}/herdr-core/config.toml` を読み、`notes = false` の行があるかを見る。ファイルが無ければ notes は有効（hc の既定）。この環境ではファイルは存在せず（`ls ~/.config/herdr-core/` が not found）、`XDG_CONFIG_HOME` も未設定。
- 注意: `HC_SESSION` や XDG を変えた core では別の場所になる。設定ファイルは core 起動時に読まれるかどうかは未確認（反映に再起動が要るかもしれない）。
- 影響: Task 4 はこの検査方法を使う。

### 7. command 起動のタグと `first_message`: 付かない（上記「spec と違う結果」）

### 9. `herdr.space` だけを付けた worker の新しい tab: 保留（開発者の了承待ち）

人の画面に tab が出るため、了承を得るまで実測していない。`herdr.space` / `herdr.tab` ラベル付きのターミナルは一切作っていない。

## その他の観察（後続タスクに関係するもの）

- Claude Code を起こす cwd が未信頼のフォルダー（今回は `/tmp`）だと、信頼確認ダイアログ（`Is this a project you created or one you trust?`、選択肢 `No, exit` / `Yes, I trust this folder`）で止まる。このとき status は `null` のまま（ダイアログ中は OSC 7501 を報告しない）で、`hc wait --children any` は返らず、`blocked` の通知も来なかった（約 2 分待っても返らなかった）。`hc read` で画面を見て初めて分かる。信頼済みの cwd で起こせば発生しない。Task 6 の起動時の検査では、起動後に `status` が `null` のままのときは画面を読む手順を入れるとよい。
- `hc wait --children any` の結果 JSON は子ごとに `reason: status`、`status`、`turn` を持つ。
- core は `hc server status` で version 0.1.15。
