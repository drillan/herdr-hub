# startup（worker の起動・配置）

roster は**編成の意図（desired state）**を記述する（レーンと分離は [lanes.md](lanes.md)）。live に無く、起動方法が解決できるエントリは起動対象で、hub が本書の手順で起こす。起動方法（`command` か `template`）も無い未 live エントリは即エラー（typo 検出を守るため）。

hub は人の承認を求めずに worker を起こす。そのぶん、起こす前の棚卸しと、起こした後の確認は省かない。

## 起動前の棚卸し

起動対象と判定されたエントリごとに、起こす前に次を行う。

1. `hc ls --label hc-hub.lane=<L>` でレーンの候補を絞り、1 件ずつ `hc get <t> --json` で `state` とラベルを読む（`hc ls` の各行はラベルを返さない。[lanes.md](lanes.md)）
2. 同じレーンに idle で再利用できる worker がいないかを見る。空きがあるのに新規を起こすのは文脈予算の浪費。既存で足りるなら起こさず、その worker へ依頼を送る
3. 独立した仕事は 1 人に積まない。独立なら新しく起こす

人の承認を求めずに起こす（人への編成案の確認は置かない）。その代わり、この棚卸しは歯止めとして残す。

## 名前

名前は core 全体で一意（1〜32 文字、`a-z 0-9 - _`）。動的な worker の名前は hub が規則で自動に付ける。

```
<レーン>-<preset>-<連番>
```

- 連番は 2 桁の十進数から始める（`01`）。**短縮した後の接頭辞**（`<レーン>-<preset>-` を短縮規則で縮めたもの）ごとに数える。既存の名前は、全レーン共有の台帳 `hc-hub ledger list`（`--lane` で絞らない）から読み、次の連番は、その短縮後の接頭辞を持つ名前の連番の最大値に 1 を足す。`hc ls --label hc-hub.lane=<L>` は他レーンの名前を返さないので、名前の採番には使わない
- 32 文字を超えるときの短縮規則: 連番は桁が増えても削らず、名前全体が 32 文字に収まるまで、先に `<preset>`、次に `<レーン>` を末尾から削る（どちらも 4 文字を下限とする）。下限まで削っても収まらないとき（長い連番を含む）はエラーで止まり、人に上げる
- 名前が重複していれば `hc run` が失敗する。それをエラーとして扱い、自動で別の名前を試さない（連番を勝手に進めて再試行しない）。人に上げる
- 常駐 agent の名前は roster のエントリ名をそのまま使う

## 起動

起動は `hc-hub spawn-argv` の出力をそのまま `hc` に渡す。`--outlive-parent`・`hc-hub.lane`・`hc-hub.role`・`hc-hub.brief` のラベル・`herdr.space` は CLI が組み立てる。手で `hc run` を組まない。

手順は 2 段で、段の間で終了コードを確かめる。`spawn-argv` をパイプやプロセス置換の中に入れると、失敗の終了コードが捨てられ、空の引数で `hc` を打つことになる。

1. `spawn-argv` を単独で打ち、結果をファイルに受ける。終了コードが 0 でなければ、ここで止まる（理由は標準エラーに出る。ファイルは使わない）。`.hc-hub/` は台帳と同じく roster のディレクトリにある非追跡の置き場（hub の cwd に依らない）。依頼が `-` で始まるときは `--task="<最初の依頼>"` の形で渡す（`--task "-x"` はオプションと読まれて止まる）

   ```bash
   hc-hub spawn-argv --lane <L> --preset <preset> --name <名前> --cwd <worktree の絶対パス> \
     --task "<最初の依頼>" [--brief <依頼ファイルのパス>] > <roster のディレクトリ>/.hc-hub/argv-<名前>.json
   ```

2. 終了コードが 0 だったときだけ、NUL 区切りにして `xargs -0` で `hc` に渡す。配列が空なら `hc` を打たない

   ```bash
   jq -e 'type == "array" and length > 0 and all(.[]; type == "string")' <roster のディレクトリ>/.hc-hub/argv-<名前>.json > /dev/null \
     && jq -j '.[] + "\u0000"' <roster のディレクトリ>/.hc-hub/argv-<名前>.json | xargs -0 hc
   ```

   この形は bash でも zsh でも動く（bash 専用の配列読み込みは zsh では動かず、配列を変数に入れて展開する形もシェルで挙動が違う）。1 行目の `jq -e` は、配列でない・空・文字列でない要素を含む・読み込みに失敗した、のどれでも非ゼロの終了コードにして、2 行目に進ませる（bash と zsh で、これらの入力で `hc` が走らないことを実測）。空白・引用符・`*`・`$` を含む要素は、そのまま 1 要素として渡る（bash と zsh で実測）。`xargs` は `hc` の標準入力を空にする。要素が非常に多く引数の長さの上限を超えると `xargs` は `hc` を複数回に分けて打つので、`spawn-argv` の出力がそこまで大きくなったら人に上げる

   **`xargs` は `hc` の終了コードを書き換える**（GNU xargs の仕様: `hc` が 1〜125 で終わると 123、255 だと 124）。そのため `exit 9` のような `hc` の終了コードの値では分岐できない。失敗の理由は `hc` が出す標準エラーで読む。それで足りなければ `hc get` などで状態を取り直す。

- `spawn-argv` は `hc` に続く引数を JSON の配列で出す。要素の順序も中身も変えずに渡す
- 自分のレーンの hub でない端末（`hc-hub start` を打っていない、role が `hub` でない、別レーンのラベルを持つ）で打つと、`spawn-argv` はエラーで止まる
- preset ではなく常駐 agent を起こすときは `--preset <preset>` の代わりに `--agent <エントリ名>`（常駐 agent の名前の一覧は `hc-hub residents --lane <L>`）
- エージェントの指定は `command`（argv の配列）か `template`（hc の template 名）のどちらか一方。引数とオプションの正典はインストール済みバイナリの `hc run --help`
- エージェント固有の引数（必須の起動引数など）は command の argv に入れる（[agents.md](agents.md)）
- worker のログは worktree の中の非追跡の場所 `<worktree>/.hc-hub/<名前>.log` に置く。起こす前に、非追跡であることを確かめる（手順は [context-and-handover.md](context-and-handover.md)）
- 最初の依頼は hc run に渡す（`--task`）。起動中のエージェントへ後から送ると落ちうるため
- `hc run` の応答（`--json`）の `address` を新しい worker のアドレスとして読む。サイドバーの並びから推測しない
- `--no-notify` を付けない。`hc run --help` では「Don't type notes about it into its parent」で、付けると親へ知らせが届かなくなる。親への自動通知（`<hc>` のタグ）を、blocked などの知らせの経路に使う

workspace の新設は人間が明示した場合だけ（hc に workspace は無い）。worker の worktree は [worktrees.md](worktrees.md) の規約に従って hub が作る。

## 配置（placement）

配置は roster の `placement` で選ぶ（placement で選ぶ）。値は `tab` と `hidden` で、既定は `tab`。`defaults`・レーン・preset・個別のどこでも上書きできる。これら以外の値はエラー。

### `tab`（既定）

- hub は自分の `herdr.space` ラベルの値を読み（`hc-hub space`）、worker の起動時に `--label herdr.space=<その値>` を付ける。付けるのは `spawn-argv` で、手では付けない。`herdr.tab` は付けない
- worker は hub と同じ space に新しい tab として出る（その tab に worker のターミナルが 1 つだけ入る。実測）
- hub に `herdr.space` ラベルが無いのに `tab` が解決された場合は、黙って `hidden` にせずエラーで止まる
- worker が増えると tab も人の画面に増える。worker の数だけ増えることを briefing で人に伝える
- tab の名前は worker の名前にする。人数が増えても視認性が劣化せず、サイドバーで役割が読める。起動後に tab id を引いて付ける。**`tab.rename` は省かない必須の手順**（下の実測のとおり、省くと tab の見分けがつかなくなる）

```bash
herdr-app ls                                                  # ターミナル id から tab id を引く
herdr-app do tab.rename --id <tab id> --name <worker の名前>
```

- **tab の判定は `herdr-app ls` の `spaces[].tabs[].terminals[].terminal` で行う。`hc get` の `where` では行わない。** `herdr-app ls` で worker のターミナル id を探し、それを含む tab が、その worker の tab である
- 実測（2026-10-31、使い捨ての端末 4 つ）: `--label herdr.space=<space>` だけを付けて起こすと、各ターミナルは別々の新しい tab に入る（同時に 2 つ起こしても別々だった）。名前の無い tab の名前は並び順の番号で、新しい tab は 2 番目に差し込まれるため、既存の tab の番号がずれる。`hc get` の `where` ラベルは、この番号のずれでは更新されない（`tab.rename` では更新される）。そのため、別の tab にいる 2 つの worker が、どちらも `… / 2` と見えることがある。`where` が同じ番号でも「同じ tab」とは読まない。`tab.rename` を打ったあと、`where` が worker の名前に変わることで確かめる

- `herdr-app do` の引数は `--<arg> <値>` の形（`id=…` の形は拒否される。実測）
- 後片付けは `hc kill` で tab ごと消える（実測）。`tab.close` は要らない。ターミナルの記録は `hc rm` で消す

### `hidden`

画面のラベルを付けない。worker は pane を持たず、親の tab のエージェント一覧と peek で見える。

### 配置の共通ルール

- 新しいアドレスは `hc run` の応答から読む（並びから推測しない。上の「起動」）
- 人のフォーカスを奪わない（`spawn-argv` の出力は `--bg` を含む。フォーカスを奪わない状態を保つ）
- 作業ディレクトリは `hc run` で --cwd を明示する。呼び出し側の cwd を暗黙に引き継がない。`hc run` は --cwd が無いと hc を実行した場所を使う（`hc run --help`: "Working directory (default: where hc runs …)"）ので、`hc-hub spawn-argv` は `--cwd DIR` を必須にしている（絶対パスで実在するディレクトリでなければエラー。現在のディレクトリを暗黙には使わない）。worker の worktree は hub が [worktrees.md](worktrees.md) に従って作る・選び、その絶対パスを `--cwd` に渡す

## 起動後の確認

起動後は、状態の報告の有無と、依頼が届いたかを、次の順に確認する。省略しない。

1. **起動後に待つ。** `hc-hub guard --op wait <t>` の後に `hc wait <t> --timeout 60` を打つ。待ち時間の 60 秒は設計者の判断で、hc の既定（180 秒）では起動直後の確認に長すぎるため。返った理由で分ける。
   - **状態の知らせ**（`working`・`done`・`blocked` など、`reason: status`）で返った → エージェントは状態を報告している。通常どおり進める。`blocked` なら [approvals.md](approvals.md) に従う
   - **`reason: timeout`** で返った → `hc get <t> --json` の `.status.state` を見る（`status` はオブジェクトで、`{"app":…,"msg":…,"state":"working"}` の形。`turn` は最初のターンが終わるまで 0 で、それが正常）。状態が報告されていれば（`null` でなければ）通常どおり進める。`null` のままなら `hc read <t>` で画面を読む
     - 画面が確認のダイアログ（信頼の確認など）なら、[approvals.md](approvals.md) の表に従って答える。信頼の確認に hub が答えてよいのは、hub 自身が worker のために作った worktree のフォルダーだけ。それ以外のフォルダーは人に上げる。実測では、ダイアログ中は状態を報告せず、`blocked` の通知も来ず、`hc wait` は返らなかった（timeout まで）。一方、新しく作った worktree で起こした Claude Code にダイアログが出なかった実測もある。出ることがあるので、起動直後は毎回これを疑う。答えたら、もう一度 `hc wait <t> --timeout 60` から確かめる
     - ダイアログも無く、状態も報告されないなら、間を置いて複数回観測する。1 回の観測（60 秒待った後の 1 回など）では結論にしない。複数回見ても `null` のままなら、そのエージェントは状態を報告しないとみなす。承認待ちに気づけないので、人に知らせて止まる（[agents.md](agents.md)）
2. **依頼が届いたか。** `first_message.sent` は template で起動したときにしか返らない。command 起動ではタグも `first_message` も付かない（実測）。そこで、`hc get` の状態が `working` になる、またはターン（`turn`）が進むことで、依頼を受け取ったと判断する

### 届いていなければ送り直す

状態が動かず、`hc read` の画面が準備待ち（信頼の確認など）なら、[approvals.md](approvals.md) に従って答えてから、`hc-hub guard --op send <t>` の後に `hc send <t> "<依頼>"` で依頼を送り直す。送り直しは 2 回までとする。

使い切ったら、`hc-hub guard --op kill <t>` → `hc kill <t>`、`hc-hub guard --op rm <t>` → `hc rm <t>` で片付け、人に上げる（[escalation.md](escalation.md)）。記録の無い worker を残さない。

## 依頼が届いた後

依頼が届いたと確認できてから、次の順に進める。

1. 台帳に spawn を記録する

   ```bash
   hc-hub ledger append --lane <L> --name <名前> --address <t> --hub "$HC_TERMINAL_ID" \
     --event spawn --preset <preset> --command-json '<解決済みの command の JSON 配列>' [--brief <依頼ファイルのパス>]
   ```

   `--command-json` に渡すのは、台帳に記録する解決済みの `command`（`hc-hub resolve --lane <L> --preset <preset>` の出力の `command`）を JSON の配列にしたもので、`spawn-argv` の出力（`hc run` の引数）ではない。`template` で起こしたときは `--command-json` の代わりに `--template <名前>`。**記録に失敗したら、起こした worker を片付けて人に上げる。** 片付けは `hc-hub guard --op kill <t>` → `hc kill <t>`、`hc-hub guard --op rm <t>` → `hc rm <t>` の順で、guard を省かない。 台帳に無い worker は誰にも見えないまま残る
2. briefing を渡す（[briefing.md](briefing.md)）。briefing は最初の依頼に含めて渡すのが基本で、hub のアドレスを必ず書く。補う分は `hc send`。briefing は hub が書く。人間に書かせない。稼働途中の追加なら「現在の状態」入りの 8 ブロック版を使う
3. 以後の監視と後始末は [messaging.md](messaging.md)

記録を先にしない。届かなかった worker を台帳に残すと、台帳と live の突き合わせが狂う。

## 常駐 agent

`hc-hub residents --lane <L>` で、レーンの常駐 agent の名前を得る。常駐 agent は preset を持たなくてよい（ラベルは `hc-hub.role=<エントリ名>`）。起動は `--agent <エントリ名>` で上と同じ手順。常駐 agent が空でもよく、その場合 hub は単独で起き、後から動的に足す。

## 起動に関する注意

- 自動起動は、command か template が解決できるエントリに限る。人間の確認は置かない。起動方法の無い agent を hub が勝手に作らない（両方ある・どちらも無いは roster の検証でエラー）
- 起動に失敗した worker、または依頼が届かなかった worker は、送り直しの上限（2 回）を使い切ったら片付けて人に上げる。失敗した起動を握って別の経路で続けない
- 起動時に roster に無い名前・レーンを指定した場合は CLI が止まる。止まったら直さずに人に上げる
