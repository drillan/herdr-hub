# roster（名簿と台帳）

hc-hub が調整対象を知るための設定。roster の**正は編成の意図（desired state）**であり、live のターミナルはその記述に合わせて照合・起動される。live に無く、起動方法（`command` か `template`）が解決できるエントリは「起動対象」である（手順は [startup.md](startup.md)）。名簿（roster）は人が書く不変の設定、台帳（ledger）は hub が起動・停止・引き継ぎのたびに追記する記録で、この 2 つを分ける。

## 与え方と優先順位

1. **起動引数**: `hc-hub start --lane <L>`。起動引数で渡せるのはレーン名であり、「名前: 役割」を渡す経路は持たない。省略・roster に無いレーン名はエラー
2. **`--roster <path>`**: YAML を明示指定する
3. **既定パス**: cwd の `.hc-hub.yml`

`ledger` が必須の項目なので、引数だけで動く形は持たない。roster が無ければ明示エラーで止まる。`role_def`・`rules`・`preset`・`command`・`template` を使うなら YAML 経路限定である。

## YAML スキーマ

テンプレートはこの skill 同梱の [.hc-hub.yml.example](../.hc-hub.yml.example)。作業対象 repo の直下に `.hc-hub.yml` としてコピーし、パスを実在のものに直して使う。

```yaml
presets:                      # 名前付きの設定テンプレート
  impl:     { role: 実装, command: [claude], rules: [.hc-hub/worker-boundary.md] }
  advisor:  { role: 設計相談, template: advisor }
defaults:                     # 全員の既定値（書けるキーは限られる）
  rules: [.hc-hub/lane-scope.md]
  approval: auto              # auto | manual。どの段にも無ければエラー
ledger: .hc-hub/ledger.jsonl  # 必須
lanes:
  backend:
    rules: [.hc-hub/backend-scope.md]       # このレーンの全員（hub と worker）
    hub: { rules: [.hc-hub/merge-gate.md] } # このレーンの hub だけ
    agents: {}                               # 常駐させたい agent だけ
```

### 段ごとに書けるキー

下の表にないキーは未知のキーとして、`hc-hub validate` が段の場所つきのエラーにする。

| 段 | 書けるキー |
|---|---|
| 最上位 | `presets`・`defaults`・`ledger`・`lanes` |
| `presets.<名>` | `role`・`role_def`・`rules`・`approval`・`placement`・`handoff_at`・`command`・`template` |
| `defaults` | `rules`・`approval`・`placement`・`handoff_at` |
| `lanes.<名>` | `rules`・`approval`・`placement`・`handoff_at`・`role_def`・`hub`・`agents` |
| `lanes.<名>.hub` | `rules`・`approval`・`handoff_at`・`role_def`（`placement` は hub に意味がないのでエラー） |
| `lanes.<名>.agents.<名>` | `preset`・`role`・`role_def`・`rules`・`approval`・`placement`・`handoff_at`・`command`・`template` |

### 個別フィールド

| フィールド | 型 | 意味 |
|---|---|---|
| `role` | 文字列 | 役割の短いラベルで、worker と常駐 agent に必須（preset が与えてもよい）。briefing にそのまま使う。解決結果が空でない文字列でなければエラー（常駐 agent は読み込み時、worker は起こすとき。hub には要らない） |
| `role_def` | 文字列（パス） | 長文の役割定義 .md。roster ファイルのあるディレクトリ基準の相対パス。worker には briefing の役割ブロックへ内容をそのまま注入し、hub のものは hub が起動時に読む |
| `rules` | 文字列のリスト（パス） | その agent が従う規律 file（群）。delivery は宛先で分かれる（下記） |
| `preset` | 文字列 | `presets` のキー名。未定義の preset は即エラー。`preset: null` や文字列以外もエラー |
| `command` | 空でない文字列のリスト | 起動する argv。空要素もエラー |
| `template` | 文字列 | hc の template 名 |
| `approval` | `auto` \| `manual` | hub が答える範囲（[approvals.md](approvals.md)）。既定値は持たず、どの段にも書かれていなければエラー |
| `placement` | `tab` \| `hidden` | worker の見せ方。それ以外の値はエラー。既定は `tab`（[startup.md](startup.md)） |
| `handoff_at` | 数 | 交代判定の使用率閾値（既定 0.8）。真偽値は不可、範囲は 0 < x ≤ 1（[context-and-handover.md](context-and-handover.md)） |
| `ledger` | 文字列（パス） | 台帳のパス。最上位だけ。必須 |
| `hub` | マッピング | そのレーンの hub だけに効く段 |
| `agents` | マッピング | 常駐させたい agent。キーが名前 |
| `lanes` | マッピング | レーンの定義。キーがレーン名 |

- レーン名・preset 名・常駐 agent の名前は `^[a-z0-9_-]{1,32}$` に限る（hc の名前とラベルの値に使うため）。常駐 agent の名前は core 全体で一意なので、レーンをまたいで重複していればエラー
- `command` と `template` は 1 つの段に両方は書けない。統合後の解決結果は、ちょうど一方を持たなければならない。起動方法が解決できない常駐 agent は、roster の読み込み時にエラー。起動方法を持たない preset は読み込みでは通り、worker として起こそうとしたときにエラーになる（常駐 agent に個別に `command` を足す土台に使えるため）
- `kind` は廃止（`command` か `template` に置き換える）、`transport` も廃止（通信は `hc send` に一本化）、`on`（別マシンを指す指定）は未対応。書かれていたら置き換え先を表示してエラーにする。`role_file` は `role_def` に改名済みで、書かれていたら改名を案内してエラーにする。別名として黙って読まない
- roster の YAML が壊れている・読めない・UTF-8 でない場合もエラー
- 参照される `rules`・`role_def` の file は、preset・defaults 経由の分も含め、存在し読めること。不在・不可読は即エラー

## 解決順序

| 対象 | 順序 |
|---|---|
| hub | `defaults` → `lanes.<名>` → `lanes.<名>.hub` |
| 動的な worker | `defaults` → `lanes.<名>` → preset |
| 常駐 agent | `defaults` → `lanes.<名>` → preset（あれば）→ `lanes.<名>.agents.<名>` |

後のものが優先する。`rules` だけは例外（次節）。

**defaults が与えられるのは限られたフィールドのみ**（`rules`・`approval`・`placement`・`handoff_at`）。`role`・`role_def`・`preset`・`command`・`template` は preset か個別に限る。defaults で `role` を許すと必須フィールド検証を潜り抜け、起動方法を許すと typo した名前まで起動対象になって「起動方法が無ければエラー」（下記）が死ぬ。レーンの直下に書けるのも `role_def` までで、`command`・`template`・`preset` は書けない。

### rules の merge（union）

`rules` だけは上書きでなく union（連結）する。規律は共通 + 役割固有 + 個人固有の重ね合わせで、個別指定が共通を潰すと境界が消える。全段をこの順に連結したものが最終セットになる。重複するパスは 1 度だけ適用する。

⚠ 他フィールドの「個別が優先」と merge 規則が違う。混同しない。

### rules の delivery（宛先で届け方が違う）

| 宛先 | delivery |
|---|---|
| worker | briefing の境界ブロックへ本文を注入し、file パスも併記して再読みできるようにする（[briefing.md](briefing.md)） |
| hub | hub が起動時に自分で読む。briefing を受け取る側ではないので、注入先が無い |

⚠ worker に file のパスだけを渡して済ませない。注入が本経路で、パスは再読み用の補助である。読まなくても規律が届いている状態にする。

## 起動時検証（必須）

起動時検証は必須。roster を得たら、各エントリを 3 分岐で処理する。live の判定は `hc ls --label hc-hub.lane=<L>` で絞り、1 件ずつ `hc get <t> --json` で読む（[lanes.md](lanes.md)）。

| 状態 | 扱い |
|---|---|
| live に解決できる | そのまま |
| live に無く、起動方法が解決できる | 起動対象。`command` か `template` が解決できれば起動し、起動後に live 解決を再確認する（[startup.md](startup.md)） |
| live に無く、起動方法も無い | 即座にエラー。黙ってスキップ・警告で続行しない |

⚠ 起動方法が無い未解決を起動対象にしない。起動方法の不在は名前の typo か陳腐化の可能性で、黙って起動すると間違った名前の agent が spawn する。typo の検出を守るため、この分岐は厳密に扱う。

あわせて確認する。

- preset 参照が `presets` で定義されていること。未定義名は即エラー
- `role_def`・`rules` で参照される file がすべて存在し読めること
- worker の返信宛先の hub が live に解決すること。返信先は briefing に書く hub のアドレスで示す（[briefing.md](briefing.md)）
- 逆方向も見る。live だが roster に無い agent は名簿の陳腐化として扱う。hub の起動時点検では、ラベルはあるのに台帳に無い worker を引き継がずに人に上げる（[context-and-handover.md](context-and-handover.md)）
- roster が古い・矛盾する場合の修復は人間の判断。hub が勝手に roster を書き換えない。動的な worker は roster に書かないので、動的追加という例外は持たない

## 動的追加（稼働中に worker を足す）

動的な worker は roster に書かない（名簿と台帳を分ける）。追加は台帳への記録で扱う。

1. preset を選ぶ（`hc-hub resolve --lane <L> --preset <p>` で解決結果を見られる）
2. 起動時検証と同じ検証を動的な worker にも適用する。起動方法が解決できれば起動し、無ければエラー（`resolve` が止まる）
3. 起動する（[startup.md](startup.md)）。稼働途中の参加なので「現在の状態」ブロックを含む 8 ブロック版の briefing を送る（[briefing.md](briefing.md)）
4. 台帳に spawn を記録する（依頼が届いたと確認できてから）

⛔ 記録せずに live にだけ追加しない。起こした worker は台帳に記録し、記録の無い worker を残さない。記録に失敗したら片付けて人に上げる。

## 交代時の仮名

交代では前任生存中に後任を起こすため、同名を取れない。後任は `<name>-next` の仮名で起動し、前任の exit 後も仮名のまま運用し、台帳の記録を後任へ付け替える（hc には端末の名前を起動後に変える操作が無いので、名前そのものは変えない）。前任の `stop` と後任の仮名を台帳に記録する。手順は [context-and-handover.md](context-and-handover.md)。

## `hc-hub` の使い方

どのサブコマンドも、roster 系は `--roster <path>`（既定は cwd の `.hc-hub.yml`）を取る。検証に失敗すると標準エラーに理由を出し、終了コード 2 で止まる。

| コマンド | 用途 |
|---|---|
| `hc-hub validate` | roster を検証する。書いた直後と、起動の前に実行する |
| `hc-hub resolve --lane <L> --hub` | hub の解決結果を JSON で出す。`--preset <p>`（動的な worker）、`--agent <名>`（常駐 agent）も同様 |
| `hc-hub residents --lane <L>` | レーンの常駐 agent 名を JSON 配列で出す |
| `hc-hub ledger append --lane <L> --name <名> --address <t> --event spawn\|stop\|adopt --hub <hub のアドレス> [--preset …] [--command-json …] [--template …] [--brief …]` | 台帳へ 1 行追記する |
| `hc-hub ledger list [--lane <L>]` | 台帳を JSON 配列で出す。`--lane` で絞れる。ファイルがまだ無ければ空 |

起動・ガードの `hc-hub start`・`spawn-argv`・`guard`・`space`・`preflight` は [lanes.md](lanes.md) と [startup.md](startup.md)。

## 台帳（ledger）

hub が起動・停止・引き継ぎのたびに 1 行の JSON を追記する。項目は `ts`・`lane`・`name`・`address`・`event`・`hub`・`preset`・`command`・`template`・`brief` で、過不足があれば読み込みでエラー。

- `event` は `spawn`・`stop`・`adopt` のいずれか。`spawn` は `command` か `template` のちょうど一方を持つ。どの event でも両方は持てない
- 行は `\n` だけで区切る。余分なキーのある行も不正
- `ledger:` は必須。無ければ roster の検証でエラー。パスは roster ファイルのあるディレクトリ基準で、全レーンで 1 つを共有し、各行にレーンを書く。プロジェクト側に置く非追跡のファイルを想定する
- ファイルがまだ無いのは clone 直後の正常な状態なので、最初の追記で作る。親ディレクトリが無い・書き込めない場合はエラー
- 追記は `O_APPEND` で 1 行を 1 回の write で書くので、レーンの異なる hub が同時に書いても行は混ざらない
- 読めない・壊れた行があればエラー（行番号つき）。読み飛ばさない
- `ledger append` は roster に無いレーンを拒否する
- 追記に失敗したら、その操作をエラーとして止める。spawn の記録に失敗したときは、起こした worker を片付けてから人に上げる

## チェックアウトとパスの基準

すべてのレーンの hub は repo のメインのチェックアウトを共有し、worker は worktree で作業する（[worktrees.md](worktrees.md)）。roster は repo の直下に 1 つで、全レーンが同じファイルを読む。roster 内の相対パス（`rules`・`role_def`・`ledger`）は、roster ファイルのあるディレクトリを基準にする。
