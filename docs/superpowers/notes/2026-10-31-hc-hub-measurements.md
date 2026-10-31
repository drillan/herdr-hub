# hc-hub 実装前の実測結果

実測日: 2026-10-31。環境: hc 0.1.15（spec §3 は 0.1.14 で確認）。使い捨てのターミナルで確かめ、すべて `hc kill` → `hc rm` で片付けた。

## spec と違う結果

- **項目 7**: 本体の「7.」に 4 要素を書いた。要点は、command 起動ではタグも `first_message` も付かないこと。spec はすでに `first_message` を template 起動に限っているので、spec と違うのは `<hc from=… reach=…>` のタグだけ。
- **項目 5**: symlink が梱包されるかは公開前に確定できない。確定できないので、複製と同一性の検査を採る（spec 4.8 の後段）。
- **項目 2**: Codex の状態報告は未確認。コマンドと失敗は本体の「2.」に書いた。

## 項目ごとの結果

### 1. `hc wait --children any` はターン終了で返るか: 返る

- コマンド: `hc run --bg --name m-claude --cwd <worktree> claude "Bash で sleep 25 を実行し、終わったら ok とだけ返事して"` → `hc wait --children any --timeout 90`
- 結果: 依頼の sleep 25 より早く返った（所要時間は計測していない）。`{"children":[{"reason":"status","status":"done","terminal":"t17","turn":1,"ended":true}],"reason":"children",…}`
- この worker は「sleep 25 はバックグラウンドで実行中です。終わったら ok と返します」と宣言してターンを終え（画面末尾 `1 shell still running`）、status は `done`。つまり spec が懸念した「再開すると宣言しただけでターンを終える止まり方」も `wait --children any` で拾える。
- 影響: Task 6 は worker ごとの `hc wait <t>` を走らせる代替手順にしなくてよい。ただし返ったあとは画面を読み、宣言だけで終わったか完了かを見分ける。
- 追試（完了済みの子が残っているときの `wait --children any`）: 使い捨ての子を 2 つ起こし（`hc run --bg --name f-a sh -c "sleep 2"` と `hc run --bg --name f-b sh -c "sleep 40"`）、f-a が終わった後に `hc wait --children any --timeout 10` を 3 回続けて実行した。
  - f-a は終了済み（`state: finished, reason: exited`、`hc get` の `reported: false`）なのに、3 回とも即時には返らず、f-b だけを `reason: running` で列挙して 10 秒の timeout まで待った（`reason: timeout`、exit 0）。終了済みの子は一覧に出ず、報告もされなかった。
  - 続けて `hc wait --children any --timeout 40` を実行すると、f-b の終了で返った（子の `reason: exit`、`exit_code: 0`、全体は `reason: children`）。もう一度実行すると、子が 0 件の `{"children":[],"ended":true,…,"reason":"children"}` が即時に返った（待たなかった）。
  - 意味: 完了済みの子は `wait --children any` の対象から外れる。wait を走らせていない間に終わった子は、次の wait では報告されない。エージェントの子がターン終了で `done` になっても `state: live` のままである場合（上の実測）は別で、対象に残る。ここで測ったのは終了済み（exit）の子だけで、live で idle の子を 2 回目の wait で再び拾うかは測っていない。
  - Task 6 への影響: 待機ループは wait が返るたびに `hc ls`（または `hc get`）で全 worker の状態を取り直し、wait の戻り値だけで子の完了を数えない。wait の戻り値が「子 0 件」のときは、もう待つ子が無いと解釈してループを抜ける。

### 2. Codex の状態報告: 未確認

- 試したコマンド: `hc run --bg --name m-codex codex --no-daemon "1 行だけ返事をして"`（計画の Step 2 の形そのまま）。
- 結果: 起動直後にターミナルが exit 1 で終了した（`state: finished`、`exit_code: 1`）。画面のメッセージは `account/read failed … refresh token was revoked`（認証の失効）。全文は保存していない。`status` は一度も得られず、承認待ちで `blocked` になるかも見られていない。
- 再測定でやること: 開発者が Codex に再ログインした後、同じコマンドを起こし、`hc get m-codex --json` の `status` と、承認が要る作業を頼んだときの `blocked` を確かめる。
- 影響: それまでは「Codex が blocked を報告するか不明」として、4.4 の起動時の検査を前提にする。


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
  - blocked の再現: `hc send m-kid "AskUserQuestion ツールで…質問して"` の後 `hc wait m-kid --timeout 60` は（所要時間は計測していない。timeout の 60 秒以内に） `{"reason":"status","status":"blocked","turn":3}` を返した。親でない hub の `wait` も blocked で返る。
  - blocked の子への `hc send m-kid "x"` は exit 9: `{"error":{"kind":"blocked","message":"t19 is blocked (question)","hint":"typing would answer its dialog; read its screen first (hc read t19), or --force"}}`
  - `hc kill m-kid` → 通り、`state: finished, reason: killed`。`hc rm` も通る。
- 影響: Task 6 の「引き継いだ worker の見張り」は `hc wait <t>` でよい（作り直し不要）。

### 5. symlink の梱包: 確定できない（上記「spec と違う結果」）

- 確かめたコマンド: この repo（worktree）で `gh skill publish --dry-run` を 1 回だけ実行した（公開はしていない）。
- 出力: 検証結果の warning 3 行（`.agents/skills/`・`.claude/skills/`・`.devin/skills/` が導入済み skill を含むので `.gitignore` に入れるべき、という内容）と、最後の `Dry run complete. Use without --dry-run to publish.` だけだった。梱包する（される）ファイルの一覧も、symlink の扱いも出ない。`gh skill preview` は公開後にしか使えない（計画のレビューで確認済み）。
- 判断: 出力が検証結果だけで梱包物を一覧しないので symlink が梱包されるかを確定できない。そこで複製と同一性の検査を採る（spec 4.8 の後段）。この実測では symlink も branch も作っていない。
- 影響: 配布の手順では、symlink に頼らず複製を置き、複製と原本の同一性を検査する。

### 6. `notes = false` を確かめる方法: 問い合わせる手段は無い

- `hc --help`・`hc server --help`（サブコマンドは start/stop/status/restart のみ）・`hc server status`（core の id・pid・version などのみ）・`hc schema`（`config` という語は出るが notes の現在値を返す操作ではない）を調べた。`hc --help` 末尾に「Settings: ~/.config/herdr-core/config.toml. notes = false: hc types nothing on its own」とある。
- 検査方法: `${XDG_CONFIG_HOME:-$HOME/.config}/herdr-core/config.toml` を読み、`notes = false` の行があるかを見る。ファイルが無ければ notes は有効（hc の既定）。この環境ではファイルは存在せず（`ls ~/.config/herdr-core/` が not found）、`XDG_CONFIG_HOME` も未設定。
- 注意: `HC_SESSION` や XDG を変えた core では別の場所になる。設定ファイルは core 起動時に読まれるかどうかは未確認（反映に再起動が要るかもしれない）。
- 影響: Task 4 はこの検査方法を使う。

### 7. command 起動のタグと `first_message`: 付かない

- 確かめたこと: `hc run --bg --name X claude "<依頼>"` のように command 起動で依頼を argv に渡したとき、`<hc from=… reach=…>` のタグと `first_message` が付くか。
- コマンド: 上の項目 1・4 で使った `hc run --bg --name m-claude --cwd <worktree> claude "<依頼>"` など。
- 結果: タグは付かず、`first_message` も返らない。依頼は argv そのままの文字列として claude の最初の入力になる。`hc run` の出力は `{"address","agent","cwd","name","parent","state","turn"}` のみ。後続の `hc send` は `<hc from="t7">…</hc>` のタグが付くが、`reach=` は付かない。`reach=` が付かないのは送り手が親でないためだと推定している（未検証。親からの `hc send` では測っていない）。タグ付きで届くのは template 経由（`hc run <template> "<依頼>"`）と `hc --skill` の記述から読めるが、template では未実測。
- spec との差: spec 4.5（109 行目）はすでに `first_message.sent` を template 起動に限っている。したがって spec と違うのは、command 起動の依頼に `<hc from=… reach=…>` のタグが付くと想定していた点だけ。
- 影響: Task 7（startup.md の briefing に hub のアドレスを書く）。報告の宛先（`hc send <hub> …`）はタグから得られないので、briefing に hub のアドレスを自分で書く。依頼が届いた確認は `first_message` ではなく、`hc get` の状態遷移で行う（spec 4.5 の通り）。

### 9. `herdr.space` だけを付けた worker の新しい tab: 保留（開発者の了承待ち）

- 確かめること: worker を `herdr.space` ラベル付きで起こしたとき、`herdr-app ls` に新しい tab ができるか。その tab の名前を `herdr-app do tab.rename` で付けられるか。
- 保留の理由: 人の画面に tab が出るため、了承を得るまで実測していない。`herdr.space` / `herdr.tab` ラベル付きのターミナルは一切作っていない。
- 予定のコマンド: `hc run --bg --name m-tab --label herdr.space=<hub の herdr.space> -- sleep 120` → `herdr-app ls` → `herdr-app commands` で引数を確認 → `herdr-app do tab.rename …`。
- 影響: Task 7 の tab の作り方は未確定。この項目が済むまで、Task 7 は worker を tab に出す手順を確定させない。

## その他の観察（後続タスクに関係するもの）

- Claude Code を起こす cwd が未信頼のフォルダー（今回は `/tmp`）だと、信頼確認ダイアログ（`Is this a project you created or one you trust?`、選択肢 `No, exit` / `Yes, I trust this folder`）で止まる。このとき status は `null` のまま（ダイアログ中は OSC 7501 を報告しない）で、`hc wait --children any` は返らず、`blocked` の通知も来なかった（待ち時間は計測していないが、待っても返らなかった）。`hc read` で画面を見て初めて分かる。信頼済みの cwd で起こせば発生しない。
  - 影響: Task 7 の startup.md に、起動後に状態が `null` のままなら `hc read` で画面を確かめる手順を入れる。
- `hc wait --children any` の結果 JSON は子ごとに `reason: status`、`status`、`turn` を持つ。
- core は `hc server status` で version 0.1.15。
