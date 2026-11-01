---
name: hc-hub
description: herdr-core（`hc`）と Herdr app で、レーンごとの hub が複数のコーディングエージェントを起動・監視・停止する runbook。呼び出したエージェントが hub になる。「別エージェントに作業を頼みたい」「レーンごとに worker を束ねたい」「worker / reviewer を並行運用したい」「hc で agent 同士を連携させたい」で起動。HC_TERMINAL_ID が前提。hc の単発の操作や使い方の質問（hc ls の読み方、プログラムを 1 つ起動するだけ、など）には使わない。旧来の herdr には herdr-hub を使う。
license: MIT
---

# hc-hub

herdr-core（CLI は `hc`）の上で、レーンごとの hub が worker を動的に起動・監視・停止するための **hub のための runbook**。段階順に並んでいるので、**いま自分がどの段階にいるかで引く**。公式の `herdr-core` skill は user scope に入れない前提で設計している（description が広く発火し、worker の Claude にも見えて勝手に `hc run` を誘発しうるため）。

- レーンの定義・ラベル・操作前のガード → [references/lanes.md](references/lanes.md)
- 承認待ちへの対応（hub が答える範囲） → [references/approvals.md](references/approvals.md)
- エージェント固有の知識（Claude Code・opencode・Devin の実測） → [references/agents.md](references/agents.md)
- roster と台帳（スキーマ・検証・`hc-hub` の使い方） → [references/roster.md](references/roster.md)
- worker の起動・命名・配置 → [references/startup.md](references/startup.md)
- 送受信・待機・着地の作法 → [references/messaging.md](references/messaging.md)
- worker へ渡す briefing の雛形 → [references/briefing.md](references/briefing.md)
- worktree 編成と成果の束ね方 → [references/worktrees.md](references/worktrees.md)
- context 残量の観測と交代手順 → [references/context-and-handover.md](references/context-and-handover.md)
- 裁定の境界（裁く / 人間へ上げる） → [references/escalation.md](references/escalation.md)
- hub の裁定の質（裏取り・hub 自身の出力を疑う） → [references/adjudication.md](references/adjudication.md)
- 実害カタログ（hc 固有の罠・運用の罠） → [references/failure-modes.md](references/failure-modes.md)

## §0 前提

**CLI の呼び出し方。** 同梱の CLI は `uv run --script <この skill のディレクトリ>/scripts/hc-hub` で実行する（`<この skill のディレクトリ>` は、この SKILL.md があるディレクトリの絶対パス）。シェル関数として定義して使う。以降の文書の `hc-hub <サブコマンド> …` は、すべてこの呼び出しを指す。

```bash
hc-hub() { uv run --script <この skill のディレクトリ>/scripts/hc-hub "$@"; }
```

`H="uv run --script …"; $H validate` のように変数に入れて展開する形は、zsh が語分割しないので失敗する。関数なら bash でも zsh でも動く。

**この skill を読むのは hub だけ。** worker は skill を読まない。hub が投げる briefing が作法の担保になる。

**人間は hub にだけ話し、hub が全 worker へ配る。** worker から人間への直接経路を作らない。

最初に前提を検査する。失敗したら「herdr-core の管理下ではない」と報告して停止する。

```bash
hc-hub preflight
```

`preflight` は `HC_TERMINAL_ID` が設定されていることと、hc の通知が無効（`notes = false`）でないことを確かめる。通知が無いと、親への通知も `<hc>` のタグも出ず、承認待ちに気づく経路が無くなる。worker の起動に `--no-notify` は付けない。`herdr-app` のウィンドウが開いていることは前提にしない。

次に、CLI 構文の正典であるインストール済みバイナリの手引きを読む。この skill は hc の手引きの本文を写さない。

```bash
hc --skill          # 毎回読む
herdr-app --skill   # 画面（tab・split）を触るときだけ
```

旧来の `herdr` のコマンドは使わない。

**hc 公式の既定を、この skill は 2 点だけ上書きする。**

1. 「`blocked` は人に尋ねよ、`--force` で迂回するな」 → [approvals.md](references/approvals.md) の範囲では hub が画面を読んで答える。範囲外（分類器・hook・人の承認が要るルール）は人に上げる
2. 「子は親と一緒に終わる」 → worker は `--outlive-parent` で起こす。hub が落ちても、人が手で交代しても、作業中の worker が一緒に止まらないようにするため。起動は `hc-hub spawn` が組んで打つ

この版で確かめたエージェントは Claude Code・opencode・Devin。3 つとも、状態の報告と最初の依頼の渡し方まで測った（Devin は信頼の確認と承認待ちの画面も）。当面 worker は Claude に統一している。Codex は測っていない（[agents.md](references/agents.md)）。

## §1 roster（名簿）と hub の起動

hub の起動時に roster を得る。YAML は `--roster <path>` で指定し、既定はカレントディレクトリの `.hc-hub.yml`（repo の最上位で実行する）。roster が無ければ明示エラーで止まる（台帳のパス `ledger` が必須のため、引数だけで動く形は持たない）。**レーン名は起動引数で受け取る**。省略、または roster に無いレーン名はエラー。

roster が無くて止まったら、人に「init の流れで roster を作るか」を尋ねる。作るなら次の順に進む（hub が勝手に roster を書かない）。作業対象は git リポジトリであること（`detect`・`init` は git の管理下でないとエラーで止まる。無ければ人が `git init` する。hub は勝手に作らない）。

1. `hc-hub detect` で、既知のエージェントが hc の端末の中で起動できるかを調べる（書き込みはしない）
2. 結果を人に示して提案する。選べるのは判定が `available` のものと、人が絶対パスで書くと決めた `shell_only` のもの。`shell_only` には、`fix`（core の PATH を直す）と、`--abs-path` で `shell_output` の絶対パスを書く道の両方を示す。絶対パスはそのマシンに固有なので、別のマシンでは roster を書き直すことになると伝える。`shell_alias`・`missing` は選べず、`fix` を添えて示す。状態の報告や最初の依頼の渡し方が未測定のエージェントは選べるが、どの列が未測定かを明示する
3. 人が、レーン名・approval（`auto` か `manual`）・preset ごとのエージェントと役割を選ぶ
4. 選ばれた内容を `hc-hub init --lane <レーン名> --approval auto|manual --preset <preset 名>=<エージェント名> --role <preset 名>=<役割>` に、すべて明示して渡す（`--preset` と `--role` は preset の数だけ繰り返す）。絶対パスで書く preset には `--abs-path <preset 名>` を足す

`init` は `.hc-hub.yml` を書き、台帳の置き場を `.gitignore` で管理から外す。commit はしないので、`.gitignore` と `.hc-hub.yml` を commit するよう人に伝える。worker の worktree は HEAD から作るので、この commit は worker を起こす前に要る（commit がまだ 1 つも無い repo では、これが最初の commit になる）。規律のファイル（`rules`）は `init` が書かない。必要なら人が `hc-hub-rules/` などに置いて、roster に書き足す。詳細 → [references/roster.md](references/roster.md)

```bash
hc-hub validate                  # roster を検証する
hc-hub start --lane <レーン名>    # 自分に hc-hub.lane・hc-hub.role=hub を付ける
```

roster は編成の意図（desired state）で、`lanes.<名>.agents` は空でもよい（hub 単独で起き、後から動的に足す）。動的な worker は roster に書かず、台帳に記録する。スキーマ・解決順序・台帳 → [references/roster.md](references/roster.md)

**起動時に必ず検証する。** 常駐 agent の各エントリを 3 分岐で処理する。

- **live に解決できる** → そのまま
- **live に無く、`command` か `template` が解決できる** → 起動対象。**人の承認を求めずに起こす**（[references/startup.md](references/startup.md)）
- **live に無く、起動方法も無い** → **即座にエラー**。黙ってスキップ・警告で続行しない（typo 検出を守る）

あわせて `presets`・`defaults`・個別が参照する `role_def`・`rules` の file が存在し読めることを確認する（不在・不可読は即エラー）。hub の `rules` と `role_def` は hub 自身が起動時に読み、worker 向けは briefing へ注入する。

## §2 レーンとガード

- レーンは roster の `lanes:` に名前で定義する。hub と worker に `hc-hub.lane=<レーン名>`、`hc-hub.role` のラベルを付ける。1 レーンに hub は 1 人
- hub がターミナルを宛先に取る `hc` の操作（`send`・`keys`・`interrupt`・`kill`・`rm`・`label`・`put`・`attach`・`wait <t>`・`read`・`keep`）の前には、毎回 `hc-hub guard --op <操作> <t>` を通す。ラベルの無い宛先はどのレーンのものとも扱わず、操作しない
- 越境してよいのは hub 同士の `hc send` だけ。ガードはラベルという自己申告に基づく規律で、機構的な遮断ではない
- 通信は hc send に一本化する（エージェントごとの別経路は持ち込まない）

詳細と限界 → [references/lanes.md](references/lanes.md)

通信プロトコル（骨子）:

- **通常の送信は非同期。** 送って即答が要る同期照会だけが例外で、普通の指示・裁定は投げたら送信側のターンを終える
- **返信は hub 宛。** worker は hub のアドレスへ `hc send` で返信する。worker がこの手段を知るのは briefing だけなので、**briefing に自分の名前・roster・hub のアドレスを必ず書く**（command で起動した worker には `<hc>` のタグが付かない）
- **送信前に宛先を確認する。** 宛先が自分のレーンのものであることを `hc-hub guard` で確かめてから送る
- **監視禁止。** worker に、あるいは hub に、他の worker を監視させない（`hc wait` で張り付かせない）。hub 自身の `hc wait --children any` だけが例外。Claude 間の notify_when_idle は持ち込まない

詳細とエラー対処 → [references/messaging.md](references/messaging.md)

## §3 起動と寿命

- **起動前に棚卸しする。** §5 の最後の項目のとおり idle を棚卸しする。独立した仕事を 1 人に積まない
- **起動は `hc-hub spawn` で行う。** `hc run` を打ち、address を読み、配置が `tab` なら tab に名前を付けるところまでを CLI が担う（途中で失敗したら、起こした worker を片付けてからエラーで止まる）。worktree を `--cwd` に渡す（[references/worktrees.md](references/worktrees.md)）。最初の依頼は `hc run` に渡す。台帳に spawn を記録するのは、依頼が届いたと確認できてから（`hc-hub ledger append … --resolve` で、`command` を roster から解決して記録する）
- 起動後は `hc wait <t> --timeout 60` で待つ。timeout で返り、`hc get --json` の `.status.state` が `null` なら `hc read` で画面を読む（信頼確認のダイアログが出ることがある。出ないこともある）。信頼の確認に hub が答えてよいのは、hub 自身が worker のために作った worktree のフォルダーだけで、それ以外は人に上げる。ダイアログも無く状態も報告されないときは、間を置いた複数回の観測で結論を出し（1 回の観測で決めない）、報告しなければ人に知らせて止まる
- roster の `command` は hc の core の PATH から見つかる必要がある。見つからないと `hc run` が `spawn_failed: cannot start` で失敗する（[roster.md](references/roster.md)）
- **監視は `hc wait --children any`。** 1 分ごとの見回りは作らない。状態の知らせで返ったときだけ `hc ls` と `hc get` で全 worker の状態を取り直す（`reason: timeout` は待ち直すだけ）
- **動的な worker の停止は、結果を受け取った hub が `hc kill` → `hc rm` で行い、台帳に記録する。** 常駐 agent は止めない。着地したら待機のまま残し、次の依頼を `hc send` で送る。止めるのは人が指示したときだけ。常駐 agent かどうかは `hc-hub residents --lane <L>` の名前の一覧で見分ける

手順の正典 → [references/startup.md](references/startup.md)、[references/messaging.md](references/messaging.md)

## §4 承認待ち

roster の `approval: auto | manual` で hub が答える範囲を切り替える（既定値は無く、書かれていなければ roster の検証でエラー）。hub は必ず `hc read` で画面を読んでから、`hc keys` か `hc send --force` で答える。「今後は確認しない」のような設定に残る選択肢は選ばず、その回だけ許可する。ただし信頼の確認ダイアログだけは例外で、hub 自身が worker のために作った worktree のフォルダーに限り `Yes, I trust this folder` を選んでよい。それ以外のフォルダーの信頼の確認は人に上げる。plan mode は計画が依頼の範囲内かを確かめてから承認する。

分類器・hook が止めたもの、人の承認が要るルールに当たったものは、`approval` に関係なく答えず、止めた表示を逐語で添えて人に上げる（待っている worker に `hc-hub.needs-human=1` を付ける）。判断がつかなければ人に上げる。hub 自身も、拒否された操作の表面を変えて通さない。

詳細 → [references/approvals.md](references/approvals.md)

## §5 規律（骨子）

- **hub は実装しない。** 裁定と実装を分ける。検査は自分が書く側に回ると発動しない
- **hub が推奨を出すときは「これは私の裁定であり人間の決定ではない」と明記する。** 書かないと受け手には両者が同じ形で届く
- **承認済みの成果物・測定値は worker から worker へ直送してよい。判断・裁定・新規の指摘は hub 経由**
- **指摘は 1 便に合流させる**（源が非同期に届くため。blocker だけ例外）
- **ack を求めない。訂正は次便に相乗りさせる**
- **照会には終了条件を先に書く。** 往復が伸びたら、成果物ではなく自分が渡した前提を疑う
- **中継は情報を落とす。** 件数・集合の再掲を添える
- **着地したら終える。** 「終了です」通知も送らない（例外は走行中の review を止める「停止」1 行）
- **context 使用率は実測でのみ書く。** worker に定期申告させない
- **裁定の境界を先に引く。** 裁くものと人間へ上げるものを先に分ける。正典（spec・ADR）が矛盾・不在なら自分の原理で解かずに上げる → [references/escalation.md](references/escalation.md)
- **hub は不変条件を裁き、手段は worker が決める。** 手段の裁定は実測でしか決まらず、hub は走らせる側に居ない
- **裁定に worker の数値・分類を引く前に 1 問訊く**（「何を測った値か」「baseline は」）。hub 自身の出力を疑い、worker に「私の裁定を壊しにきてください」と招く → [references/adjudication.md](references/adjudication.md)
- **状態の観測を重複させない**（CI の緑 / 赤などは 1 箇所だけが測る）。**判定（主張の真偽）は独立に取り直す。** こちらの重複は価値である
- **review 役を置くなら、その出力を裏取りする経路を置く**（hub が一次資料で読み直す、または review 役に読んだ file の列挙を課す）
- **裁定は材料を出した全セッションへ戻す。** 戻すのは裁定した側の義務
- **新しい worker を起こす前に、同じレーンの idle を `hc ls --label` と `hc get` で棚卸しし、「既存で足りないか」を問う**

## §6 context 残量と交代

- **観測は `hc read` で外側から画面を読む**（worker の文脈を消費しない）
- 処置は続行 / compact / 交代の 3 択。**80% で交代判定**（`handoff_at`）、auto-compact を検出したら即交代
- 交代は前任が内容ブロックを後任へ直接送り、**hub はエンベロープを書く**
- hub 自身の交代は人が手で行う。前任が引き継ぎを書いて終了し、後任が `hc-hub start` で起動して、引き継いだ worker に新しいアドレスを知らせる

手順の正典 → [references/context-and-handover.md](references/context-and-handover.md)

## 限界

この skill は、ガード・検証・台帳をスクリプトで機械化しているが、レーンの分離は手順として守る規律で、機構による遮断ではない。hub がいない間の承認待ちは誰も気づかない。限界の一覧は [references/lanes.md](references/lanes.md) と [references/context-and-handover.md](references/context-and-handover.md) にある。
