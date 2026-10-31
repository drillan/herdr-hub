# hc-hub — herdr-core（`hc`）向け hub skill の設計

2026-10-31。新しい配布 skill `hc-hub` を同じ repo の `skills/hc-hub/` に追加する設計。既存の `herdr-hub`・`herdr-session`（旧来の `herdr` 0.9 系向け）は変更しない。

本文中の「開発者の決定」はこの設計の対話で開発者が決めたこと、「設計者の判断」は対話で開発者に確認していない設計者の選択であり、builder が覆してよい。

## 1. 目的と背景

herdr-core（CLI は `hc`）は、ターミナルを動かし続ける常駐の core で、その表示役はデスクトップアプリの Herdr app（`herdr-app`）が担う。旧来の `herdr` の `herdr agent …`・`HERDR_ENV`・session に依存する `herdr-hub` は、herdr-core の端末内では §0 の前提検査で停止し、使えない。

ある業務プロジェクトでは、旧来の `herdr` の上で `herdr-hub` を次の形で運用してきた。herdr-core の上でも同じ運用を続けたい。

- 1 つの repo を複数のレーン（例: バックエンドとフロントエンドの並行実装）に分け、レーンごとに hub が 1 人いる
- hub は長く走り続け、自分の判断で worker・reviewer・advisor を起こし、要らなくなったら止める（起動に開発者の承認は求めない）
- worker の承認待ち（plan mode など）には hub がキー入力で答え、自律的な進行を止めない
- レーンを越えて話してよいのは hub 同士だけ

## 2. 目標・非目標・反目標

**目標**

- hub が worker を動的に起動・監視・停止し、開発者の介入なしに進行を続けられる
- 1 つのマシンの上で、複数のレーンが互いに干渉せずに並行して動く
- どのコーディングエージェントを使うかは、ユーザーが設定ファイルで選ぶ（OSS として配布するため、特定のエージェントを前提にしない）

**非目標（最初の版）**

- 別マシンで worker や hub を動かすこと（`hc run --on` など）。開発者の決定で、最初の版は同じマシンの同じ core に限る
- hub の自動交代。hub の交代は人が手で行う（開発者の決定。Claude の hub は `autoCompactWindow` の設定で交代の頻度が下がっている）
- 旧来の `herdr` との両対応。旧来の `herdr` は既存の `herdr-hub` が受け持つ
- 機構による遮断（ACL）。レーンの分離は手順として守る規律であり、その限界を runbook に明記する

**反目標（動いても失敗とみなすもの）**

- **worker が承認待ちで止まり、自律的な進行が途切れること**。開発者が最も避けたいこととして挙げた
- hub が分類器や hook の拒否を、表面を変えて通すこと
- 他のレーンの worker に干渉すること

## 3. 前提となる herdr-core と Herdr app の性質（2026-10-30〜31 に hc 0.1.14・herdr-app 0.1.9 で確認）

| 性質 | 確認方法 |
|---|---|
| core はユーザーごとに 1 つ。`hc ls` は全 space・全プロジェクトのターミナルを返す | 実測 |
| `--name` は live なターミナル全体で一意（1〜32 文字、`a-z 0-9 - _`） | `hc run --help` |
| `hc run` で起こした子は `parent` に親のアドレスが入る。ラベルは継承されない | 実測（子の `labels` が `{}`） |
| 子は既定で親と一緒に終了する（`die_with_parent: true`）。`--outlive-parent` を付けると親の終了後も live のまま、`parent` には終了した親のアドレスが残る | 実測 |
| 起動後に親を付け替える操作は見当たらない | `hc schema` を検索（確証はない） |
| 子が自分で報告できない状態（blocked・error・exited）は hc が親に通知する。報告は `<hc from="t7 name">…</hc>` の形で親の次の入力に届く | `hc --skill` |
| 最初の依頼を `hc run` に渡すと、子には `<hc from="tN 名" reach="hc send tN when done or stuck">` のタグ付きで届く | `hc --skill` |
| herdr-app が開いたターミナルには `herdr.space` / `herdr.tab` のラベルが付く。space を作り直すと、同名でも ID が変わる | 実測 |
| `blocked` の子への `hc send` は `--force` が無いと拒否される。`hc keys <t> down enter` などでキーを押せる | `hc send --help`・`hc --skill` |
| Claude Code は状態（OSC 7501）を報告する | 実測（`status: working`） |
| Codex は `--no-daemon` を付けないと、コマンドが hc の外で実行される | `hc --skill` |
| 公式 skill `herdrdev/herdr-core` の `skills/herdr-core/SKILL.md` は、`hc --skill` を読ませる入口だけの skill（2026-10-27 追加） | GitHub を読み取りで確認 |

## 4. 開発者の決定と設計

### 4.1 名前と置き場所（開発者の決定）

- skill 名は `hc-hub`。`skills/hc-hub/` に置き、`gh skill publish` の配布対象にする
- `herdr-hub`・`herdr-session` は旧来の `herdr` 用として残し、中身は変えない。`herdr-session` に当たるものは作らない（herdr-core では再起動でプログラムが消えるため、名前を付け直す対象がない）

### 4.2 §0 の前提と、hc の手引きの扱い

- 前提は `HC_TERMINAL_ID` が設定されていること。無ければ「herdr-core の管理下ではない」と報告して停止する。`herdr-app` のウィンドウが開いていることは前提にしない
- hc の通知が無効になっていないこと。`~/.config/herdr-core/config.toml` の `notes = false` では、親への通知も `<hc>` のタグも出ず、承認待ちに気づく経路が無くなる。§0 で確かめ、無効ならエラーにする（確かめ方は §5-6）。worker の起動に `--no-notify` は付けない
- hc の手引きの本文は写さない。§0 で毎回 `hc --skill` を実行して読ませる。画面（tab・split）を操作するときだけ `herdr-app --skill` を読ませる。CLI 構文の正典はインストール済みのバイナリとする（既存 `herdr-hub` と同じ方針）
- 公式 `herdr-core` skill から取り込むのは入口の指示（`HC_TERMINAL_ID` での判定・`hc --skill` を読む・旧来の `herdr` は使わない）だけで、言い換えて書く。公式 skill は user scope に入れない前提で設計する（description が広く発火し、worker の Claude にも見えて勝手に `hc run` を誘発しうるため）
- 公式 skill の hc 側の既定のうち、次の 2 点を hc-hub は明示的に上書きする。上書きであることを runbook に書く
  - 「`blocked` は人に尋ねよ、`--force` で迂回するな」 → 4.6 の範囲で hub が答える
  - 「子は親と一緒に終わる」 → 4.5 のとおり worker は `--outlive-parent` で起こす

### 4.3 レーンと分離（開発者の決定: レーンを続ける。分離の単位は設計者の判断）

- レーンは roster の `lanes:` に名前で定義する。分離の単位は space ID ではなくレーン名とする（space は作り直すと ID が変わるため）
- hc-hub が付けるラベル（キー名は設計者の判断）:
  - `hc-hub.lane=<レーン名>`: すべての hub・worker に付ける
  - `hc-hub.role=hub`、worker は `hc-hub.role=<preset 名>`、常駐 agent は preset を持つ場合も含めて `hc-hub.role=<エントリ名>`（実装で確定。`hub` は予約語）
  - `hc-hub.brief=<依頼ファイルのパス>`: 依頼ファイルがある worker に、起動時の `--label` で付ける（ラベルの値にパスの文字を入れられるかは §5-3）
  - `hc-hub.needs-human=1`: 人の判断を待っている worker に、hub が付ける（4.6）
- `hc ls` の各行はラベル・名前・親を返さない（確認済み）。`hc ls --label` で候補を絞り、ラベル・`parent`・`state` は 1 件ずつ `hc get <t> --json` で読む
- hub がラベルを付けてよいのは、自分自身と、自分が起こした worker・引き継いだ worker だけ
- 人に見せたい場合のレーンと space の対応（例: space `backend` と `frontend`）は任意。hc-hub は space の存在に依存しない
- **hub の起動時**:
  - レーン名は起動引数で受け取る。省略した場合、または roster に無いレーン名の場合はエラーにする
  - hub は自分のターミナルに `hc label "$HC_TERMINAL_ID" hc-hub.lane=<レーン> hc-hub.role=hub` を付ける
  - 同じレーンに `role=hub` の live なターミナルがすでにあればエラーにする（1 レーンに hub は 1 人）
  - hub のターミナルは人が起こすため名前が無いことがある。hc には起動後に名前を付ける操作が見当たらないので、hub はラベルとアドレスで識別する（設計者の判断）
- **操作前のガード**: hub がターミナルを宛先に取る hc の操作（`send`・`keys`・`interrupt`・`kill`・`rm`・`label`・`put`・`attach`・`wait <t>`・`read` など、宛先を取るものすべて）を打つ前に、毎回 `hc get <t> --json` で宛先のラベルを読む。次のどちらにも当たらなければ、操作せずにエラーとして止まる
  1. 宛先の `hc-hub.lane` が自分と同じ
  2. 自分が hub で、宛先が `hc-hub.role=hub`（他レーンの hub）で、操作が `hc send` である
- ラベルの無い宛先は、どのレーンのものとも扱わない。操作せず、必要なら人に上げる
- ガードの限界: ラベルは誰でも `hc label` で書き換えられる自己申告であり、ガードは hub が自分に課す規律である。他の hub や worker の誤り・偽装は防げない。worker が勝手に起こした子はラベルを持たないので、hub はそれを自分のレーンのものとして扱えない。runbook にこれらを書く
- **レーンの越境（開発者の決定）**: hub 同士はレーンを越えて会話してよい。用途は限定しない（API の取り決めの擦り合わせなど）。他レーンの hub は自分の子ではないので、返事は相手の `hc send` として届く
- worker はレーンを越えない。worker が送るのは、briefing に書かれた hub のアドレスと、hub に指示された相手だけ。hub のアドレスは `<hc>` のタグに頼らず、briefing に必ず書く（command で起動した場合にタグが付くかは未確認、§5-7）。worker の briefing にこの規律と、ガードの限界（機構的な遮断ではないこと）を書く
- worker の briefing には、「hub への `hc send` が失敗したら（hub が交代中など）、作業を進めずに失敗の表示を画面に残して待つ」と書く。後任の hub が新しいアドレスを送ってくる（4.5）
- 通信経路は `hc send` に一本化する。既存 `herdr-hub` の `sendmessage`・`codex-queue` は持ち込まない（エージェントごとの経路で、エージェントを設定で選ぶ方針と合わない。どちらもマシン全域で名前を解決し、レーンの分離をすり抜ける）

### 4.4 エージェントの選び方（開発者の決定: 設定ファイルで選ぶ）

- preset・個別エントリに `command`（argv の配列）か `template`（hc の template 名）のどちらか一方を書く。両方ある・どちらも無い場合はエラーにする。スキル本体はエージェント固有の分岐を持たない
- 起動直後に `hc get` で状態の報告があるかを確かめる。報告が無ければ、そのエージェントでは承認待ちに気づけないので、人に知らせて止まる（設計者の判断。待つ時間は builder が決める）
- エージェント固有の知識（入力待ちに答えるキー、`blocked` を報告するか、`--no-daemon` のような必須の引数）は reference に分け、Claude Code と Codex について確かめたものを例として載せる。他のエージェントはユーザーが書き足す

### 4.5 worker の寿命（開発者の決定）

- **起動前の棚卸し**: 起こす前に、同じレーンに idle で再利用できる worker がいないかを見る（既存 `herdr-hub` の規律を引き継ぐ。人の承認を外すぶん、この歯止めは残す）。独立した仕事を 1 人に積まない（独立なら新しく起こす）
- **起動**: hub は人の承認を求めずに worker を起こす。`hc run --bg --outlive-parent --name <名> --cwd <dir> --label hc-hub.lane=… --label hc-hub.role=… [--label hc-hub.brief=…] <command|template> "<最初の依頼>"`。最初の依頼は `hc run` に渡す（起動中の agent への後からの `send` は落ちうるため）
- **依頼が届いたかの確認**: `first_message.sent` は template で起動したときにしか返らない（hc schema の説明「Template runs: whether the first message went in」）。そこで、command・template のどちらでも、起動後に `hc get` の状態が working になる・ターンが進むことで、依頼を受け取ったと判断する。受け取っていなければ `hc read` で画面を読み、準備待ち（信頼の確認など）なら 4.6 に従って答えてから `hc send` で依頼を送り直す。送り直しは回数上限つき（回数は builder が決める）とし、使い切ったら worker を `hc kill` → `hc rm` で片付け、人に上げる。依頼が届いたと確認できてから、台帳に spawn を記録する
- **名前**: 動的な worker の名前は hub が規則で自動で付ける（例: `<レーン>-<preset>-<連番>`。規則の細部は builder が決める）。core 全体で一意でなければ `hc run` が失敗するので、それをエラーとして扱い、黙って別名にしない
- **監視**: hub は `hc wait --children any` で子の知らせを待つ。1 分ごとの見回りは作らない
- **停止**: 結果を受け取ったら hub が `hc kill` → `hc rm` で片付け、台帳に記録する
- **`--outlive-parent` を既定にする理由**: hub が落ちたときや人が手で交代したときに、作業中の worker が一緒に止まらないようにするため（反目標「自律的な進行が途切れる」への対処）
- **手での hub の交代（設計者の判断）**: 前任の hub は引き継ぎファイル（`context-and-handover` reference の形）を書いてから終了する。後任はその後に起動する。「1 レーンに hub は 1 人」の検査には例外を設けない。後任は、引き継いだ worker の全員に、自分のアドレスを新しい返信先として `hc send` で必ず知らせる（briefing に書かれた返信先は前任のアドレスのままのため）
- **hub 起動時の点検**: 起動した hub は `hc ls --label hc-hub.lane=<レーン>` で候補を絞り、1 件ずつ `hc get` で `parent` と `state` を読んで、親がもう生きていない worker を一覧にする。これを台帳と突き合わせる。引き継ぐものは台帳に adopt を記録し、要らないものは片付ける。どれを引き継ぐかの判断は hub が行い、判断できなければ人に尋ねる。ラベルはあるのに台帳に無い worker は、引き継がずに人に上げる
- **引き継いだ worker の見張り**: 引き継いだ worker は後任の子ではないので、hc の自動の通知も `hc wait --children` も後任には届かない。後任は、引き継いだ worker ごとに `hc wait <t>` をバックグラウンドで並べて走らせ、`--children any` と同じ扱いで知らせを受ける。`hc wait <t>` が blocked で返るかは §5-4 で確かめる
- **hub がいない間の限界**: 前任が終わってから後任が点検を終えるまでの間に worker が承認待ちになっても、誰も気づかない。hub の交代は人が行う短い作業である前提で、この空白は限界として runbook に書く（自動の見回り役は置かない。hub の自動交代は非目標）

### 4.6 承認待ちへの対応（開発者の決定）

- roster の `approval: auto | manual`（開発者の決定）で、hub が答える範囲を切り替える。解決は 4.7 の順序に従う。値が `auto`・`manual` 以外ならエラーにする。既定値は持たず、どこにも書かれていなければ roster の検証でエラーにする（設計者の判断。暗黙の既定で hub の権限の範囲が決まらないようにするため）

| 入力待ちの種類 | `auto` | `manual` |
|---|---|---|
| plan mode の承認、フォルダの信頼の確認、選択肢のメニュー、続行の確認 | hub が答える | hub が答える |
| 通常の権限確認（分類器でも hook でもない「この Bash を実行してよいか」など） | hub が画面を読んで答える | 人に上げる |
| 分類器・hook が止めた、人の承認が要るルールに当たった | 人に上げる | 人に上げる |

- hub が答えるときは、必ず `hc read` で画面を読んでから、`hc keys` か `hc send --force` で答える
- 「今後は確認しない」のような、設定に残る選択肢は選ばず、その回だけを許可する（開発者の決定）
- plan mode の承認は、計画が依頼の範囲から外れていないかを確かめてから答える。外れていれば承認せず、その点を worker に返す（開発者の決定）
- この設定は hc-hub の層のもので、エージェント自身の権限モード（例: Claude Code の `--permission-mode`）とは独立している。後者は `command` の引数で選ぶ
- 次の 3 つに当たったら、`approval` に関係なく答えず、人に上げる。止めた表示を逐語で添える
  1. エージェントの分類器が止めた
  2. hook が止めた
  3. 人の承認が要るルールに当たった（ルールの中身はプロジェクト側の rules ファイルにある前提。スキル本体は「書かれていれば上げる」という枠だけを持つ）
- 判断がつかない場合は人に上げる
- **人に上げていることの印（設計者の判断）**: 人に上げるとき、hub は待っている worker に `hc-hub.needs-human=1` のラベルを付け、解決したら外す（値を固定にするのは、`hc ls --label` が完全一致でしか絞れず、複数の worker が同時に待つこともあるため）。人は `hc ls --label hc-hub.needs-human=1` で、どの worker が人を待っているかを全レーン分一覧できる（行の `where` でレーンの場所もわかる）。hub の画面には、止めた表示の逐語と、何を決めてほしいかを書く
- hub 自身も、拒否された操作の表面を変えて通そうとしない（既存 `worker-boundary` 相当の規律を hub にも適用する）
- 人に上げている間も、他の worker は止めない

### 4.7 roster（開発者の決定: 名簿と台帳を分け、動的な worker は roster に書かない）

既定のパスは cwd の `.hc-hub.yml`。`--roster <path>` で上書きできる（ファイル名は設計者の判断）。

```yaml
presets:
  impl:     { role: 実装,       command: [claude],             rules: [.hc-hub/worker-boundary.md] }
  reviewer: { role: 独立 review, command: [codex, --no-daemon], rules: [.hc-hub/reviewer-boundary.md] }
  advisor:  { role: 設計相談,   template: advisor }

defaults:
  rules: [.hc-hub/lane-scope.md]
  approval: auto        # auto | manual（4.6）

ledger: .hc-hub/ledger.jsonl

lanes:
  backend:
    rules: [.hc-hub/backend-scope.md]       # このレーンの全員（hub と worker）に効く
    hub: { rules: [.hc-hub/merge-gate.md] } # このレーンの hub だけに効く
    agents: {}          # 常駐させたい agent だけ。例: { backend-rev: { preset: reviewer } }
  frontend:
    approval: manual    # レーン単位の上書きの例
    hub: { rules: [.hc-hub/merge-gate.md] }
    agents: {}
```

- **解決の順序（設計者の判断）**: `defaults` → `lanes.<名>` → preset → 個別（後のものが優先）。既存 `herdr-hub` の `defaults` → preset → 個別の間にレーンを挟む
  - 動的な worker: `defaults` → レーン → preset（個別は無い）
  - 常駐 agent: `defaults` → レーン → preset（あれば）→ `lanes.<名>.agents.<名>`
  - hub: `defaults` → レーン → `lanes.<名>.hub`
  - `rules` だけは上書きでなく、全段の union（連結）。それ以外のフィールドは後のものが優先
  - `lanes.<名>` の直下と `lanes.<名>.hub` に書けるのは、`rules`・`approval`・`placement`・`handoff_at`・`role_def` だけ（`lanes.<名>.hub` では `placement` は意味を持たないのでエラーにする）。`command`・`template`・`preset` は preset か個別だけに書ける
- 既存 `herdr-hub` の roster から引き継ぐもの: `rules` の union、`role_def`、`handoff_at`、未知のキー・未定義の preset・読めないファイルは即エラー、worker 向けの rules は briefing に本文を改変せず全文を注入し、hub 向けは hub 自身が読む
- 廃止するもの（設計者の判断）: `kind`（`command`・`template` に置き換え）、`transport`（`hc send` に一本化、4.3）。これらが書かれていたら、未知のキーとしてエラーにし、置き換え先を表示する。`placement` は値を `tab | hidden` に変えて残す（4.10）
- 変えるもの:
  - `kind` の代わりに `command` か `template` を書く
  - `lanes:` を一段目に置く
  - `ledger:` はトップレベルに置く（例では最初 `defaults` 配下に置いていたが、`defaults` は agent ごとに解決するフィールドなので外に出した。設計者の判断）
  - 常駐させたい agent は `lanes.<名>.agents` に書き、そのレーンの hub が受け持つ。トップレベルの `agents:` は置かない（設計者の判断）。名前は core 全体で一意であることが必要なので、roster 全体で重複していればエラーにする
  - 常駐 agent が live でなく、`command` か `template` が解決できれば、hub が人の承認を求めずに起こす（開発者の決定「起動は伺わない」を常駐 agent にも適用する。既存 `herdr-hub` の「編成案を人に 1 行確認」は持ち込まない）。live でもなく起動方法も無ければ即エラー（typo の検出を引き継ぐ）
  - 別マシンを指す指定（`on:` など）はエラーにする
- レーン名は hc の名前とラベルに使うため、`a-z 0-9 - _` に限る
- **チェックアウトとパスの基準（設計者の判断。今の運用に合わせる）**: すべてのレーンの hub は repo のメインのチェックアウトを共有し、worker は worktree で作業する（`worktrees` reference の規律）。roster は repo の直下に 1 つで、全レーンが同じファイルを読む。roster 内の相対パスは roster ファイルのあるディレクトリを基準にする。台帳は全レーンで 1 つを共有し、各行にレーンを書く（1 行ずつの追記なので、hub どうしが同時に書いても行は混ざらない前提。builder は追記の仕方でこれを保つ）
- **台帳**: hub が起動・停止・引き継ぎのたびに 1 行の JSON を追記する。最低限の項目は、時刻・レーン・名前・アドレス・preset（無ければ null）・command か template・依頼ファイル・出来事（spawn / stop / adopt）・記録した hub のアドレス。台帳はプロジェクト側に置かれる非追跡のファイルを想定する
  - `ledger:` は必須。無ければ roster の検証でエラーにする
  - ファイルがまだ無いのは clone 直後の正常な状態なので、最初の追記で作る。親ディレクトリが無い・書き込めない場合はエラーにする
  - 読めない・壊れた行がある場合はエラーにする（読み飛ばさない）
  - 追記に失敗したら、その操作をエラーとして止める。spawn の記録に失敗したときは、起こした worker を片付けてから人に上げる（記録の無い worker を残さない）

### 4.8 既存 references の扱い

- バックエンドに依存しない規律は、`herdr-hub` から `hc-hub` へ写す。対象は `adjudication`・`escalation`・`worktrees` の 3 つ（grep で旧来の `herdr` のコマンドを含まないことを確認済み）。skill はディレクトリ単位でインストールされるため、skill をまたぐ参照はできない
- 写した 3 つの中身が同一であることを確かめる検査を置き、release skill の手順で必ず実行する。repo 内の symlink で共有できるか（`gh skill publish`・`npx skills`・`apm` が実体として梱包するか）を先に確かめ、できるなら複製と検査の代わりに symlink を使う
- `context-and-handover`・`briefing` は旧来の `herdr` のコマンド（`herdr pane read`・`herdr agent rename`・`herdr agent prompt hub`・SendMessage）を含むので写さず、hc 向けに書き直す。規律の文は元の文を下敷きにしてよい。`herdr-hub` 側は変えない（設計者の判断）
- `transports`・`messaging`・`startup`・`failure-modes`・`roster` も hc 向けに書き直す
- **書き直すときの原則**: 書き直す references（`context-and-handover`・`briefing`・`messaging`・`startup`・`failure-modes`・`roster`）に含まれる規律のうち、バックエンドに依存しないものはすべて引き継ぐ。差し替えるのは旧来の `herdr` の仕組みに依存する部分（コマンド、pane・session、transport）だけ。例: go・承認は報告された版（sha256 の先頭 12 桁）にだけ掛かる、送信ごとの通し番号と総通数、訂正の 1 行目に前便が生きているかを書く、着地後は送らない、review 担当への差分（SHA での pin・期待値の事前登録など）、報告の作法（数値は実行出力の逐語）、worker の文脈の観測と `handoff_at` での交代、恒久性クラス、共有メモリの writer は hub 単独
- builder は計画の最初の成果物として、これら 6 つの references の規律を「そのまま引き継ぐ / hc 向けに変える / 捨てる（理由）」の 3 つに分けた対応表を作る。「捨てる」は旧来の `herdr` の仕組みそのものに限り、規律を黙って落とさない
- worker の文脈の観測は、旧来の `herdr` の `pane read` の代わりに `hc read` で画面を外から読む
- release skill に「公式 `herdr-core` skill の最新コミットを確認する」項目を足す

### 4.9 文書

- README に `hc-hub` の節（要件・インストール・旧来の `herdr` 版との違い）を足す。長く走らせる hub には自動 compact の設定を推奨する、と一行書く
- CHANGELOG がある場合は更新する
- この repo の追跡ファイル・コミットに、運用元の業務プロジェクトの名前を出さない（開発者の指示）
- ライセンスは MIT のまま（開発者の決定で保留）

### 4.10 worker の見せ方（`placement`）

- roster の `placement: tab | hidden` で選ぶ。**既定は `tab`**（開発者の決定。今の運用と同じく worker ごとに tab を持つ）。解決は 4.7 の順序に従い、`defaults`・レーン・preset・個別のどこでも上書きできる。`tab`・`hidden` 以外の値はエラーにする
  - `tab`: hub は自分の `herdr.space` ラベルの値を読み、worker の起動時に `--label herdr.space=<その値>` を付ける。`herdr.tab` は付けない。herdr-app は知らない tab の指定が無いターミナルに新しい tab を作る（`defaults/AGENTS.md`「without it, Herdr creates a tab in that space」）。tab の名前は worker の名前にする（付け方は §5-9）
  - `hidden`: 画面のラベルを付けない。worker は pane を持たず、親の tab のエージェント一覧と peek で見える
- hub に `herdr.space` ラベルが無い（ウィンドウの外で hub を起こした等）のに `tab` が解決された場合は、黙って `hidden` にせずエラーにする
- 画面のラベルが付いたターミナルは、herdr-app によって core の keep も有効になる（`defaults/AGENTS.md`「Adoption also enables core keep」）。人が tab を閉じると worker は終了する。worker が終了すると pane が閉じ、最後の pane なら tab も消える。hub は、人が閉じた worker を「終了した worker」として扱い、台帳に stop を記録する
- 既存 `herdr-hub` の `placement` の `pane`（hub の tab を分割する形）は持ち込まない（設計者の判断。必要になったら追加する）

## 5. 実装前に実測すること

次の項目は未確認。結果によって手順が変わるので、実装の前に使い捨てのターミナルで確かめる。

1. `hc wait --children any` が、子のターン終了（working → idle / done）で返るか。返らなければ、「再開します」と宣言しただけでターンを終える止まり方を拾えない。その場合は worker ごとに `hc wait <t>` をバックグラウンドで走らせる手順に変える
2. Codex（`--no-daemon` 付き）が `blocked` などの状態を報告するか。報告しなければ 4.4 の起動時の検査で止まることになる
3. ラベルのキーに `-` と `.` を含められるか（`hc-hub.lane`）
4. `--outlive-parent` で残った子に、新しい hub から `hc send` / `hc wait` / `hc kill` がすべて通るか。親でない hub が `hc wait <t>` で待っているとき、その子が blocked になると wait が返るか（返らなければ 4.5 の引き継いだ worker の見張りを作り直す）
5. 4.8 の symlink の梱包
6. `notes = false` を §0 で確かめる方法（設定ファイルを読むか、hc に問い合わせる手段があるか）
7. command で起動し、依頼を argv で渡したときに、`<hc from=… reach=…>` のタグが付くか、`first_message` が返るか
8. ラベルの値にパスの文字（`/` など）を入れられるか（3 と合わせて確かめる）
9. `herdr.space` だけを付けて起こした worker に、本当に新しい tab ができるか。その tab に worker の名前を付ける方法（`herdr-app do tab.rename` を使うか、起動時に指定できるか）。確かめるときは開発者に一言断ってから行う（人の画面に tab が出るため）

## 6. builder に任せること

- SKILL.md と references の章立て、文の書き方
- 名前の自動付与の規則の細部、状態の報告を待つ時間、台帳の JSON の項目名
- 起動引数の書式
- 写す references の同一性検査の実装（スクリプトの言語と置き場所）
