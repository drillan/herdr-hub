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

- 連番は 2 桁の十進数から始める（`01`）。同じ `<レーン>-<preset>-` の接頭辞を持つ live なターミナルと、`hc-hub ledger list --lane <L>` の記録の最大値に 1 を足す
- 32 文字を超えるときの短縮規則: 連番は削らない。先に `<preset>` を末尾から削って 4 文字まで縮め、それでも超えるときは `<レーン>` を末尾から 4 文字まで縮める。それでも 32 文字に収まらなければエラーで止まり、人に上げる
- 名前が重複していれば `hc run` が失敗する。それをエラーとして扱い、黙って別名にしない（連番を勝手に進めて再試行しない）
- 常駐 agent の名前は roster のエントリ名をそのまま使う

## 起動

起動は `hc-hub spawn-argv` の出力をそのまま `hc` に渡す。`--outlive-parent`・`hc-hub.lane`・`hc-hub.role`・`hc-hub.brief` のラベル・`herdr.space` は CLI が組み立てる。手で `hc run` を組まない。

```bash
readarray -d '' -t ARGV < <(
  hc-hub spawn-argv --lane <L> --preset <preset> --name <名前> \
    --task "<最初の依頼>" [--brief <依頼ファイルのパス>] | jq -j '.[] + "\u0000"'
)
hc "${ARGV[@]}"
```

- `spawn-argv` は `hc` に続く引数を JSON の配列で出す。要素の順序も中身も変えずに渡す
- preset ではなく常駐 agent を起こすときは `--preset <preset>` の代わりに `--agent <エントリ名>`（常駐 agent の名前の一覧は `hc-hub residents --lane <L>`）
- エージェントの指定は `command`（argv の配列）か `template`（hc の template 名）のどちらか一方。引数とオプションの正典はインストール済みバイナリの `hc run --help`
- エージェント固有の引数（必須の起動引数など）は command の argv に入れる（[agents.md](agents.md)）
- 最初の依頼は hc run に渡す（`--task`）。起動中のエージェントへ後から送ると落ちうるため
- `hc run` の応答（`--json`）の `address` を新しい worker のアドレスとして読む。サイドバーの並びから推測しない
- `--no-notify` を付けない。親への自動通知（`<hc>` のタグ）を、blocked などの知らせの経路に使うため

workspace や worktree の新設は人間が明示した場合だけ。hc に workspace は無く、worktree の新設は [worktrees.md](worktrees.md) の規約に従う。

## 配置（placement）

配置は roster の `placement` で選ぶ（placement で選ぶ）。値は `tab` と `hidden` で、既定は `tab`。`defaults`・レーン・preset・個別のどこでも上書きできる。これら以外の値はエラー。

### `tab`（既定）

- hub は自分の `herdr.space` ラベルの値を読み（`hc-hub space`）、worker の起動時に `--label herdr.space=<その値>` を付ける。付けるのは `spawn-argv` で、手では付けない。`herdr.tab` は付けない
- worker は hub と同じ space に新しい tab として出る（その tab に worker のターミナルが 1 つだけ入る。実測）
- hub に `herdr.space` ラベルが無いのに `tab` が解決された場合は、黙って `hidden` にせずエラーで止まる
- worker が増えると tab も人の画面に増える。worker の数だけ増えることを briefing で人に伝える
- tab の名前は worker の名前にする。人数が増えても視認性が劣化せず、サイドバーで役割が読める。起動後に tab id を引いて付ける。

```bash
herdr-app ls                                                  # ターミナル id から tab id を引く
herdr-app do tab.rename --id <tab id> --name <worker の名前>
```

- `herdr-app do` の引数は `--<arg> <値>` の形（`id=…` の形は拒否される。実測）
- 後片付けは `hc kill` で tab ごと消える（実測）。`tab.close` は要らない。ターミナルの記録は `hc rm` で消す

### `hidden`

画面のラベルを付けない。worker は pane を持たず、親の tab のエージェント一覧と peek で見える。

### 配置の共通ルール

- 新しいアドレスは `hc run` の応答から読む（並びから推測しない。上の「起動」）
- 人のフォーカスを奪わない（`spawn-argv` の出力は `--bg` を含む。フォーカスを奪わない状態を保つ）
- 作業ディレクトリは `hc run` で --cwd を明示する。呼び出し側の cwd を暗黙に引き継がない。ただし現行の `spawn-argv` の出力は `--cwd` を含まず、`hc run` の cwd の既定は本書では未測定。別ディレクトリで動かす worker を起こす前に、この点を人に確認する

## 起動後の確認

起動後は次の順に確認する。省略しない。

1. **状態の報告があるか。** `hc get <t>` で `state` を見る。状態の報告が無いエージェントは、承認待ちに気づけない。人に知らせて止まる（[agents.md](agents.md)）
2. **状態が `null` のままなら `hc read` で画面を読む。** 起動後に状態が `null` のまま動かないのは、未信頼の cwd での信頼の確認ダイアログなど、状態を報告しない画面で止まっている兆候（実測: ダイアログ中は状態を報告せず、`blocked` の通知も来ず、`hc wait` は返らなかった）。読んで画面に従い、[approvals.md](approvals.md) の表に従って答える
3. **依頼が届いたか。** `first_message.sent` は template で起動したときにしか返らない。command 起動ではタグも `first_message` も付かない（実測）。そこで、`hc get` の状態が `working` になる、またはターン（`turn`）が進むことで、依頼を受け取ったと判断する

### 届いていなければ送り直す

状態が動かず、`hc read` の画面が準備待ち（信頼の確認など）なら、[approvals.md](approvals.md) に従って答えてから、`hc-hub guard --op send <t>` の後に `hc send <t> "<依頼>"` で依頼を送り直す。送り直しは 2 回までとする。

使い切ったら、`hc-hub guard --op kill <t>` → `hc kill <t>`、`hc-hub guard --op rm <t>` → `hc rm <t>` で片付け、人に上げる（[escalation.md](escalation.md)）。記録の無い worker を残さない。

## 依頼が届いた後

依頼が届いたと確認できてから、次の順に進める。

1. 台帳に spawn を記録する

   ```bash
   hc-hub ledger append --lane <L> --name <名前> --address <t> --hub "$HC_TERMINAL_ID" \
     --event spawn --preset <preset> --command-json '<argv の JSON>' [--brief <依頼ファイルのパス>]
   ```

   `template` で起こしたときは `--command-json` の代わりに `--template <名前>`。**記録に失敗したら、起こした worker を `hc kill` → `hc rm` で片付けて人に上げる。** 台帳に無い worker は誰にも見えないまま残る
2. briefing を渡す（[briefing.md](briefing.md)）。briefing は最初の依頼に含めて渡すのが基本で、hub のアドレスを必ず書く。補う分は `hc send`。briefing は hub が書く。人間に書かせない。稼働途中の追加なら「現在の状態」入りの 8 ブロック版を使う
3. 以後の監視と後始末は [messaging.md](messaging.md)

記録を先にしない。届かなかった worker を台帳に残すと、台帳と live の突き合わせが狂う。

## 常駐 agent

`hc-hub residents --lane <L>` で、レーンの常駐 agent の名前を得る。常駐 agent は preset を持たなくてよい（ラベルは `hc-hub.role=<エントリ名>`）。起動は `--agent <エントリ名>` で上と同じ手順。常駐 agent が空でもよく、その場合 hub は単独で起き、後から動的に足す。

## 起動に関する注意

- 自動起動は、command か template が解決できるエントリに限る。人間の確認は置かない。起動方法の無い agent を hub が勝手に作らない（両方ある・どちらも無いは roster の検証でエラー）
- 起動に失敗した worker、または依頼が届かなかった worker は、送り直しの上限（2 回）を使い切ったら片付けて人に上げる。失敗した起動を握って別の経路で続けない
- 起動時に roster に無い名前・レーンを指定した場合は CLI が止まる。止まったら直さずに人に上げる
