# hc-hub init — 新しいプロジェクトに roster を用意する機能の設計

2026-10-31。`skills/hc-hub` の同梱 CLI に、新しいプロジェクト向けの roster（`.hc-hub.yml`）を用意する機能を足す。手元の環境で使えるコーディングエージェントを調べ、その中から人が選んだものを roster に書く。

## 1. 意図

hc-hub は roster が無いと明示エラーで止まる（台帳のパス `ledger` が必須のため）。今は、同梱の `.hc-hub.yml.example` を手でコピーし、パスやコマンドを直す前提になっている。

新しいプロジェクトで hc-hub を使い始めるときに、次の 2 つでつまずく。

- **どのエージェントを roster に書けるかが分からない。** 試運転では、シェルからは見える opencode が hc の core からは見えず、`hc run` が `spawn_failed` で失敗した。「インストールされている」と「`hc run` で起動できる」は別物である。
- **雛形を手で直す手間と、直し忘れ。** 雛形のパスは実在を前提にしていない。`.hc-hub/` を git の管理から外す手順も、別に要る。

## 2. 目標・目標外・失敗とみなすもの

**目標**

- hc の core から起動できるエージェントを、`hc run` と同じ環境で調べる
- 調べた結果を、人が選べる形で示す。シェルからは見えるのに core からは見えないものは、その旨と直し方を添えて示す
- 人が選んだ内容だけを roster に書く。書いた roster が `hc-hub validate` を通る

**目標外**

- 選ばれなかった項目を、CLI が既定値で埋めること
- 既存の `.hc-hub.yml` を書き換えること（追記・統合を含む）
- 規律のファイル（`rules`）や役割定義（`role_def`）の中身を作ること
- core の PATH を書き換えること

**失敗とみなすもの（動いても不可）**

- core から起動できないエージェントを、起動できるものとして roster に書く
- 個人の絶対パス（`/home/<ユーザー名>/…`）を roster に書く
- 人が選んでいない approval やエージェントが、roster に入る

## 3. 前提となる実測（2026-10-31）

同じマシンで `which claude codex opencode devin copilot pi` を 3 か所で実行した。

| 実行した場所 | claude | codex | opencode | devin | copilot | pi |
|---|---|---|---|---|---|---|
| hc の端末の中（`hc run -- which …`） | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| ユーザーの対話の zsh（`zsh -ic`） | ✓ | ✓ | ✓（`~/.opencode/bin`） | ✓ | ✓ | ✗ |
| エージェントの Bash ツール（対話でないシェル） | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |

- `hc run` が起動できるかどうかと一致するのは、hc の端末の中の結果だけである
- `hc run --rm` で起動すると、結果を読む前に端末が消える（実測）
- `which` は、見つからないものがあると終了コード 1 で終わる（実測）

hc の使い捨て端末の扱い（hc 0.1.15 で実測）:

- `hc run --json --bg --no-parent --name <名前> -- sh -c '<スクリプト>'` は `{"address":"t28","agent":"sh",…}` を返す。端末の識別子は `address`
- `hc wait --json <t> --timeout <秒>` は、中のプログラムが 0 以外で終わっても、自身は終了コード 0 で返る。中の終了コードは JSON の `exit_code` に入り（例: `{"ended":true,"exit_code":3,"reason":"exit",…}`）、`reason` は `exit`。`wait` 自体の失敗とは、`wait` の終了コードと `reason` で区別できる
- `hc read <t>` は画面の文字を返す。制御文字は混ざらなかった。**タブは空白に変わる**ので、区切りにタブを使わない
- `/bin/sh` は dash で、**`command -v a b c` は最初の名前しか調べない**（`command -v claude opencode devin` が claude の行だけを出し、終了コード 0 だった）。名前ごとにループで 1 回ずつ呼ぶ
- 名前ごとのループで `<名前> <パス>`（見つからなければ `<名前>` だけ）を 1 行ずつ出す形は、意図どおりに読めた

## 4. 振る舞い

### 4.1 二段に分ける

調べることと書くことを、別のサブコマンドに分ける。そのあいだで、人が選ぶ。

1. `hc-hub detect` — 調べて、結果を JSON で出す（書き込みはしない）
2. hub を務めるエージェントが、結果を人に示す。どのエージェントにどの役割を割り当てるか、approval を `auto` と `manual` のどちらにするかを、人に選んでもらう
3. `hc-hub init` — 選ばれた内容を、すべて明示した引数で受け取り、roster を書く

### 4.2 共通の前提検査（detect・init）

- hc に届かない（`HC_TERMINAL_ID` が無い、core が動いていない）ときは、エラーで止まる
- 自分の端末のラベルを `hc get` で読み、`hc-hub.role` が `hub` 以外の値ならエラーで止まる。ラベルが無いこと（まだ `start` していない）は許す。worker が自分の判断で detect・init を打つのを防ぐため
- カレントディレクトリが git の作業ツリーの最上位でなければ、エラーで止まる（`git rev-parse --show-toplevel` と比べる。どちらも `resolve()` してから比べる）
- linked worktree（`--git-dir` と `--git-common-dir` が違う）と submodule（`--show-superproject-working-tree` が空でない）の中では、エラーで止まる。roster は repo のメインのチェックアウトの直下に 1 つ、という既存の設計（roster.md）を守るため
- 両サブコマンドは、既存のサブコマンドと同じく `--hc`（既定 `hc`）を持つ。テストで偽の hc に差し替えるため

### 4.3 `hc-hub detect`

**hc の端末の中で調べる（起動できるかの判定）**

- 使い捨ての端末を `hc run --json --bg --no-parent --name hc-hub-probe-<pid> --label hc-hub.role=probe -- sh -c '<スクリプト>'` で起こす。`--rm` は付けない（§3）
  - 名前は実行ごとに一意にする（固定の名前だと、残った端末と衝突し続ける）
  - `hc-hub.role=probe` のラベルを付ける。SKILL.md §2 の「ラベルの無い宛先は操作しない」の例外として、CLI が自分で起こした probe の端末だけは、CLI の中で `wait`・`read`・`rm` してよい、と roster.md に書く
- スクリプトは、名前ごとに `command -v` を 1 回ずつ呼び、印付きの短い行を出す。形は `<nonce> <名前> 1`（見つかった）か `<nonce> <名前> 0`（見つからない）。最後に `<nonce> END` を出し、`exit 0` で終わる
  - `<nonce>` は実行ごとのランダムな文字列。印の付いた行だけを読む
  - パスは出さない。roster に絶対パスは書かないので要らない。長いパスが画面の幅で折り返されて読めなくなるのも避けられる
  - `which` ではなく `command -v` を使う（`which` は最小構成の環境に無いことがある）
- `hc wait --json <t> --timeout <秒>` で待つ。秒数は `HC_TIMEOUT_SECONDS`（30 秒）より短くする（Python 側の打ち切りが先に来ないように）。`ended` が `true`、`reason` が `exit`、`exit_code` が 0 のときだけ先へ進む。それ以外はエラーで止まる
- `hc read <t>` の出力から、既知の名前がすべてちょうど 1 回ずつ現れ、`END` の行があることを確かめる。欠け・重複・未知の名前の行があれば、エラーで止まる
- 端末は、成功したときも途中でエラーになったときも、`hc rm` で必ず消す（`finally`）。`hc rm` が失敗したら、端末のアドレスを添えてエラーで止まる

**対話シェルで調べる（シェルからは見えるのかの判定）**

- シェルは、ユーザーのログインシェル（`pwd.getpwuid(os.getuid()).pw_shell`）を使う。`SHELL` 環境変数は使わない。detect は hc の端末の中で動き、`SHELL` は core から受け継いだ値で、ユーザーの普段のシェルとは限らないため。使ったシェルのパスは JSON に出す
- 対応するのは sh 系のシェル（sh・bash・zsh・dash・ksh）。それ以外（fish・csh など）は、エラーで止まる
  - 2026-11-11 追記: fish（3.4 以降）にも対応した。同じスクリプトが fish でも動く（`$(…)` は fish 3.4 から使える）。fish の `command -v` は関数（fish の alias）を出さないので、関数のときは `function <名前>` を出し、sh 系の alias と同じく `shell_alias` と判定する。csh などは引き続きエラー
- `<シェル> -l -i -c '<スクリプト>'` で実行する。`-l` を付けるのは、`.profile`・`.zprofile`・`.bash_profile` で PATH に足したディレクトリも読むため
- スクリプトは、名前ごとに `command -v` を 1 回ずつ呼び、`<nonce> <名前> <command -v の出力>` を出す。見つからなければ出力の部分は空。初期化ファイルが何か出力しても、印の付いた行だけを読むので混ざらない
- 印の付いた行は、最初の 2 つの空白で 3 つに分ける（パスに空白が入ってもよい）
- `HC_TIMEOUT_SECONDS` で打ち切り、打ち切ったらエラーで止まる。対話シェルの結果を使わずに判定を続けることはしない
- 既知の名前がすべてちょうど 1 回ずつ現れることを確かめる。欠けていればエラーで止まる

**判定**

エージェントごとに、次のどれかを返す。

| 判定 | hc の端末の中 | 対話シェル | 人への示し方 |
|---|---|---|---|
| `available` | 見つかった | （問わない） | 選べる |
| `shell_only` | 見つからない | 絶対パスで見つかった | 選べない。見つかったディレクトリと、直し方（core の PATH にそのディレクトリを足す）を添える。ディレクトリはシェルで引用した形で示す |
| `shell_alias` | 見つからない | 絶対パスでない出力（alias・関数・組み込み） | 選べない。シェルの出力をそのまま示し、実体の実行ファイルを core の PATH に置くよう伝える |
| `missing` | 見つからない | 出力なし | 選べない |

- 出力の JSON は、エージェントごとに名前・判定・対話シェルでの出力・起動の argv・測定の状態（§4.5 の 2 つの列）・注記を持つ。加えて、使ったログインシェルのパスを持つ

### 4.4 `hc-hub init`

引数（すべて明示。既定値は持たない）:

```bash
hc-hub init --lane <レーン名> --approval auto|manual \
  --preset <preset 名>=<エージェント名> --role <preset 名>=<役割> \
  [--preset … --role …]
```

**引数の検査**

- `--preset` は 1 つ以上必須。同じ preset 名には、`--role` が 1 つずつ必要。片方だけならエラー
- 値は最初の `=` で分ける（役割の文言には `=`・空白・日本語が入ってよい）。同じ preset 名を 2 回指定したらエラー
- 役割の文言は、前後の空白を除いても空でないこと。空ならエラー
- 同じエージェントを複数の preset に割り当ててよい（例: `impl=claude` と `reviewer=claude`）
- `<エージェント名>` は §4.5 の一覧の名前。一覧に無い名前はエラー
- `--roster` は持たない。書く場所は、§4.2 の検査を通ったカレントディレクトリ（= メインのチェックアウトの最上位）の `.hc-hub.yml`

**起動できるかの確かめ直し**

- 選ばれたエージェントが hc の端末の中で見つかるかを、§4.3 の「hc の端末の中で調べる」と同じ方法で確かめ直す。見つからなければエラーで止まる（detect を飛ばして init を打った場合への備え）
- 対話シェルは調べない。判定に関係が無く、fish を使う人などが init できなくなるため

**roster を組み立てて書く**

- 書く内容は、`presets`・`defaults.approval`・`ledger: .hc-hub/ledger.jsonl`・`lanes.<レーン名>.agents: {}`。`command` は一覧の argv をそのまま使い、絶対パスは書かない
- YAML は `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)` で書き出す。文字列を手で組み立てない（`#` や `true` のような役割の文言で、YAML が壊れたり型が変わったりするため）
- 書く前に、書き出す予定の文字列を同じ loader で読み直し、`validate` と同じ処理で検査する。さらに preset ごとに `resolve_worker` まで通す（role が空でないかなど、読み込み時の検査だけでは見ない項目まで確かめるため）。通らなければ、何も書かずにエラーで止まる。`load_roster` は `Path` しか受け取らないので、文字列から検査する入口を足す
- `.hc-hub.yml` は `open(path, "x")`（O_EXCL）で作る。既にあれば（壊れたシンボリックリンクを含む）、上書きせずにエラーで止まる
- init が書く roster には `rules` も `role_def` も入らない。どちらも roster の任意の項目で、無くても検査に通り、hub も動く。規律のファイルが要るなら、人があとから置いて roster に書き足す

**台帳の置き場を git の管理から外す**

- 調べるパスは、roster に書く台帳の実際のパス `.hc-hub/ledger.jsonl`。`git check-ignore -q -- .hc-hub/ledger.jsonl` を打つ
  - 終了コード 0（無視されている）: `git check-ignore -v` で、当たったパターンの出どころを見る。出どころがこの repo の追跡された `.gitignore` なら、何もしない。`info/exclude` や global の excludesFile なら、ほかの人が clone したときには無視されないので、下の 1 と同じく `.gitignore` に追記する
  - 終了コード 1（無視されていない）: `.gitignore` に `/.hc-hub/` を追記する
  - それ以外: エラーで止まる
- 追記の仕方
  - `.gitignore` が無ければ作る。あって、最後が改行で終わっていなければ、先に改行を足す
  - `.gitignore` がディレクトリ・壊れたシンボリックリンク・書き込み不可・UTF-8 でないときは、エラーで止まる
  - 追記したあとに `git check-ignore -q -- .hc-hub/ledger.jsonl` を打ち直す。0 でなければ（後ろの否定のパターンなどで無視されない）、エラーで止まる
- init は commit しない。`.gitignore` と `.hc-hub.yml` を commit するよう、出力で人に伝える。commit されるまでは、hub が HEAD から作る worker の worktree に追記が入らない。そのあいだは、worker の worktree の側で既存の手順（context-and-handover.md の `info/exclude` への追記）が要る。この関係を roster.md に書く

**書いたあと**

- 書いたファイルを読み直して、もう一度検査する。書く前の検査に通っていれば落ちない想定だが、落ちたら書いた `.hc-hub.yml` を残したままエラーで止まる（直すのは人）

### 4.5 既知のエージェントの一覧

CLI の中に持つ。新しいエージェントは、実測してからここに足す。

| 名前 | 実行ファイル | 起動の argv | 状態の報告 | 最初の依頼の渡し方 | 注記 |
|---|---|---|---|---|---|
| `claude` | `claude` | `[claude]` | 実測済み | 位置引数（実測済み） | |
| `opencode` | `opencode` | `[opencode, --prompt]` | 実測済み | `--prompt` の値（実測済み） | 位置引数はディレクトリと解釈される |
| `devin` | `devin` | `[devin]` | 実測済み（2026-10-31） | 未測定（`hc send` で届くことは実測済み） | 承認待ちの状態と `--permission-mode` を省いたときの挙動は未測定 |
| `codex` | `codex` | `[codex, --no-daemon]` | 未測定 | 未測定 | `--no-daemon` は hc のマニュアル（`hc --skill`）による |
| `copilot` | `copilot` | `[copilot]` | 未測定 | 未測定 | |
| `pi` | `pi` | `[pi]` | 未測定 | 未測定 | |

- `spawn-argv` は、最初の依頼を argv の末尾に足す（`[*command, task]`）。「最初の依頼の渡し方」が未測定のエージェントは、この形で依頼が届くかが分からない
- 未測定のエージェントも選べる。ただし detect の出力と、hub が人に示す提案に、どの列が未測定かを明示する

## 5. skill の文書の変更

- **SKILL.md §0**: 「確かめたエージェントは Claude Code と opencode」を、§4.5 の一覧に合わせて直す（devin の状態の報告は実測済み）
- **SKILL.md §1**:
  - 「既定は repo 直下の `.hc-hub.yml`」を、CLI の実際の既定に合わせて「カレントディレクトリの `.hc-hub.yml`。repo の最上位で実行する」に直す
  - roster が無いときは、エラーで止まったあと、人に「init の流れで roster を作るか」を尋ねる。作るなら detect → 提案 → 人が選ぶ → init の順に進む
  - 規律のファイルは、init のあとに人が置いて roster に書き足す流れを書く
- **references/roster.md**:
  - detect と init の使い方、判定の 4 つ、一覧の置き場を書く
  - 15 行目の「雛形をコピーしてパスを直す」に、init の流れを並べて書く
  - YAML スキーマの例の `rules` の置き場を、`.hc-hub/` から `hc-hub-rules/` に直す
  - probe の端末（`hc-hub.role=probe`）は、CLI の中でだけ `wait`・`read`・`rm` してよい、という例外を書く
  - init の `.gitignore` への追記と、worker の worktree での `info/exclude` の手順（context-and-handover.md）の関係を書く
- **references/agents.md**: `## Devin` の節を立て、実測の日付と範囲を書く。55 行目の「hc では未測定」の例を差し替える。一覧の測定の状態と揃える
- **`.hc-hub.yml.example`**: 規律のファイルの置き場を `.hc-hub/` から `hc-hub-rules/` に移す。`.hc-hub/` は台帳などの非追跡の置き場で、規律のファイルは git で管理するものだからである
- **README の hc-hub 節**: 「`.hc-hub.yml` の作り方」に init の流れを足す。最小形の例は init の出力と揃える
- **元の設計書**（`2026-10-31-hc-hub-design.md`）の YAML の例: 履歴として残し、書き換えない

## 6. 制約

- Python 3.13、PEP 723 の同梱 CLI の流儀を守る（ruff は ALL、mypy は strict）
- テストファースト。hc は既存の `tests/fake_hc.py` の流儀で偽物に差し替え、実際の hc 端末を起こさない。偽物は `run --json`（`address`）、`wait --json`（`ended`・`exit_code`・`reason`）、`read`（画面の文字）、`rm`（呼ばれたことの記録）を返せるよう拡張する
- 対話シェルの呼び出しと git の呼び出しも、テストで差し替えられる形にする
- 判定できないとき・前提が無いときは、既定値や空の結果で続けず、エラーで止まる
- エラーは既存の CLI と同じく、標準エラーに 1 行を出して終了コード 2。新しい例外の型は `scripts/hc-hub` の `except` に足す。`git`・シェルを呼ぶ `subprocess` の `OSError` と `TimeoutExpired` も、同じ形のエラーに変換する
- `tests/test_skill_docs.py` は、`skills/hc-hub` の下のすべてのファイルで、既定値で続行することを指すカタカナ語（同テストの禁止語）を禁じている。コードのコメントや文書にその語を書かない
- 文書の検査を足す: `skills/hc-hub` の .md と雛形に `rules: [.hc-hub/` が無いこと。一覧の名前と測定の状態が agents.md と一致すること

## 7. 設計者の判断（確認してほしいもの）

- `--role` を preset ごとに必須にした。役割の文言に既定値を置かないため
- 台帳の置き場が無視されていなければ、`.gitignore` に追記する（`info/exclude` ではない）。roster をチームで共有するなら、無視の設定も共有したほうがよいため。同じ理由で、`info/exclude` や global の設定でだけ無視されている場合も、`.gitignore` に追記する
- 規律のファイルの置き場を `hc-hub-rules/` にした
- 書く場所はメインのチェックアウトの最上位に限り、init はそこで実行させる。linked worktree と submodule の中ではエラーにする。roster は repo の直下に 1 つ、という既存の設計に揃えた
- 書く前に検査し、通らなければ何も書かない。中途半端な roster や `.gitignore` の追記を残さないため
- 対話シェルの検出が打ち切りになったら、エラーで止める。シェルの結果を使わずに判定を続けると、`shell_only` を見落として `missing` と誤って伝えるため
- 対話シェルは `SHELL` ではなく、ログインシェル（passwd）を `-l -i` で起動する。hc の端末の中の `SHELL` は core から受け継いだ値で、普段のシェルとは限らないため
- alias・関数で定義されたものは `shell_alias` という別の判定にした。`missing` と言うと誤りで、`shell_only` と言うと直し方（ディレクトリを PATH に足す）が当てはまらないため

## 8. builder に任せること

- detect と init のコードの分け方（`hc_hub_lib/` の新しいモジュール名など）
- JSON の出力のキーの細かい名前
- nonce の作り方と、hc の端末の中・対話シェルで走らせるスクリプトの細部（§4.3 の行の形を守ること）
