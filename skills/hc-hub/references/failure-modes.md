# failure-modes（実害カタログ）

何が起きたか / 区別できた最小の観測 / 打った手、の 3 列で書く。新しい失敗が出たらここへ足す。「実測」と書いたものは、hc 0.1.15 で使い捨てのターミナルを使って確かめたもの。それ以外は旧来の `herdr` での運用の実績を hc の道具に置き換えたもので、hc 上では未再測定。

## hc 固有の罠

| 失敗 | 観測 | 手 |
|---|---|---|
| blocked を完了と誤読 | `hc get` の `state` に `blocked` が出る。`hc wait` が `"status":"blocked"` で返る | 承認や質問の画面であり、完了ではない。`hc read` で画面を見て、[approvals.md](approvals.md) の範囲で答える。範囲外は人に上げる |
| 状態が null のまま動かない（実測） | 起動後に `hc get --json` の `.status.state` が `null`（`.status` ごと `null` の場合を含む）のまま。`blocked` の通知も来ず、`hc wait` も返らなかった | 未信頼の cwd で起こした Claude Code は、信頼確認ダイアログが出ることがある。出ている間は状態を報告しない（新しく作った worktree で出なかった実測もある）。状態が null のままなのは完了の証明ではない。`hc read` で画面を読み、ダイアログなら [approvals.md](approvals.md) に従う。hub が答えてよいのは hub 自身が worker のために作った worktree のフォルダーだけで、それ以外は人に上げる。待ちは `hc wait <t> --timeout 60` で、timeout で返って null のままなら読む（[startup.md](startup.md)「起動後の確認」）。ダイアログも無いのに null のときも、1 回の観測で「状態を報告しない」と結論にしない。間を置いた複数回の観測で出す（試運転では、60 秒待った後の 1 回の観測で誤判定した）。状態は `.status.state` で読み、`turn` は最初のターンが終わるまで 0 で正常 |
| `hc run` が `spawn_failed: cannot start "<コマンド>"` で失敗する（実測） | roster の `command` の実行ファイル（例: `~/.opencode/bin` の opencode）が hub のシェルからは見えるのに、`hc run` が失敗する。`hc-hub validate` と `spawn-argv` は通る | hc の core の PATH は、ユーザーのシェルの PATH と違う。直し方は 2 つ。roster の `command` の先頭を絶対パスにするか、core の PATH にそのディレクトリを入れる。直したら `hc run` をやり直す。この不一致は `validate`・`spawn-argv` では検出できない（[agents.md](agents.md)） |
| worker から hub への `hc send` が拒否される（hub が blocked）（実測） | worker の `hc send <hub>` が exit 9。hub が人に質問している最中などで `blocked` だった | worker は `--force` を使わずに待ち、送り直す（[briefing.md](briefing.md)）。hub は blocked から戻ったら、`hc read` で worker の画面から届かなかった報告を読む（[messaging.md](messaging.md)） |
| `hc get` の `where` が別の tab の worker と同じ tab 番号を示す（実測） | 別の tab にいる 2 つの worker が、どちらも `… / 2` と見える。「同じ tab かもしれない」と迷って `tab.rename` を省いた | 名前の無い tab の名前は並び順の番号で、新しい tab は 2 番目に差し込まれるため番号がずれ、`where` はそのずれで更新されない（`tab.rename` では更新される）。tab の判定は `herdr-app ls` の `spaces[].tabs[].terminals[].terminal` で行い、`where` では行わない。`tab.rename` は省かない（[startup.md](startup.md)「配置」） |
| `unknown` や分類不能な状態を完了と誤読 | 状態が分類できない | 分類不能は完了の証明ではない。応答を `hc read` で確認する |
| 完了した子が `hc wait --children any` に出てこない（実測） | 終了済みの子は一覧から外れ、待機を走らせていない間に終わった子は、次の待機でも報告されない。子が 0 件のときは待たずに即座に返る | 待機の戻り値だけで子の完了を数えない。返るたびに `hc ls --label hc-hub.lane=<L>` と `hc get` で全 worker の状態を取り直す（[messaging.md](messaging.md)） |
| `hc wait` がターン終了で返り、完了と誤読（実測） | worker が「バックグラウンドで実行中です」と宣言しただけでターンを終え、`status: done` で返った | 返ったあとは画面を読み、宣言だけで終わったか完了かを見分ける。回収には状態だけでなく画面の文面の確認を併用する。旧来の `herdr` では、prompt の入力中の隙間で idle を観測して settled と判定され、作業中に wait が返る形でも出た |
| `blocked` の子に `hc send` が通らない（実測） | exit 9、`kind: blocked`。`hint` は「画面を読め、または `--force`」 | 先に `hc read <t>` で画面を読む。選択肢の画面なら `hc keys <t> …` で押し、文字を送る必要があるときだけ `hc send --force <t> "…"`。画面を読まずに `--force` を使わない |
| command で起こした worker に `<hc from=… reach=…>` のタグも `first_message` も付かない（実測） | `hc run` の出力は `address`・`agent`・`cwd`・`name`・`parent`・`state`・`turn` のみ。依頼は argv の文字列がそのまま最初の入力になる | 返信先をタグに頼らない。briefing に hub のアドレスを必ず書く（[briefing.md](briefing.md)）。依頼が届いたかは `hc get` の状態遷移で確かめる（[startup.md](startup.md)） |
| hub が終わると worker が一緒に終わる | hub の終了・交代のあと worker の `state` が `finished` になる | hc の既定では子は親と一緒に終わる。worker は必ず `--outlive-parent` で起こす。手で `hc run` を組むとこれを落とす。起動は `hc-hub spawn-argv` の出力をそのまま使う（[startup.md](startup.md)） |
| `herdr-app do` の引数が拒否される（実測） | `id=…` の形は `expected --<arg>` で拒否される | 引数は `--<arg> <値>` の形（例: `herdr-app do tab.rename --id <tab id> --name <名前>`）。引数の一覧は `herdr-app commands` で引く |
| timeout や stalled を未配送と誤読して再送 | 送信が timeout や stalled を返す | 配送は済んでいる可能性が高い。再送前に hc read で届いたか確認する |
| 画面から応答が読めない | `hc read` で行数を増やしても出ない | alternate screen 上で描画される応答は、host の scrollback に残らない。受け手に完全な応答をファイルに書いて、パスだけ返すよう依頼する（`hc read` で同じ現象が起きるかは未確認） |
| エージェントが権限確認の画面で止まる | `blocked`。画面に承認 UI（「この Bash を実行してよいか」など） | hub は approval の範囲で画面を読んで答え、範囲外は人に上げる（従来の「hub は UI を回答しない」から変えた。[approvals.md](approvals.md)） |
| worker の tab が意図しない space に出る | 想定と別の space に新しい tab が出る | tab の置き先を指定しないと意図しない space に出る。worker の `herdr.space` ラベルは hub 自身の値から決める（`hc-hub space`）。hub に無ければエラーで止まり、黙って `hidden` にしない（[startup.md](startup.md)） |
| 制御コマンドが permission に拒否される | `hc send`・`hc run` などが分類器に拒否される | 複合コマンド（`cd`・`;`・パイプ・`echo >>` の同梱）は permission の allow の先頭一致から外れ、分類器の判定に回る。制御コマンドは単独で打つ（roster・ログの更新は別コマンドに分ける）。`hc-hub spawn-argv` の出力も、単独で打って終了コードを確かめてから `hc` に渡す。プロセス置換の中に入れると失敗の終了コードが捨てられる（[startup.md](startup.md)） |
| 宛先が別集団の同名 agent に届く | 意図しないターミナルが応答する | 名前の解決がマシン全域の経路は、別集団の同名 agent に届く。集団が混在する環境では宛先を限定する。hc の名前は core 全体で一意で、`hc-hub guard` が宛先のレーンラベルを確かめる（[lanes.md](lanes.md)） |
| agent 終了後に空のターミナルが残る | `hc ls` に `state: finished` のターミナルが残る | agent の終了と後始末は別。hub の停止は `hc kill` → `hc rm` まで行い、台帳に `stop` を記録する（[messaging.md](messaging.md)）。tab は `hc kill` で自動で消える（実測） |
| 人が tab を閉じて worker が終わる | worker が `finished` で見つかる | 画面のラベルが付いたターミナルは、tab を閉じると終了する（spec）。終了した worker として扱い、台帳に `stop` を記録する |

## 運用固有の罠

| 失敗 | 観測 | 手 |
|---|---|---|
| hub の中継で情報が落ちる | 受け手が「来なかったもの」を観測できず、後で発覚する | 中継で情報が落ちる。件数・集合の再掲と本文の同梱で防ぐ（[messaging.md](messaging.md)「中継は情報を落とす」） |
| 「追います」「監視します」を書かせる | ターンを終えた agent は何もしない。wait を回す agent は文脈を浪費する | 「監視します」を書かせない。書くのは「いま何を区切ったか」「次に誰が動くか」だけ。起こすのは受け手 |
| 指摘が非同期に届き、受け手が何度も直す | 同じ対象への修正 push が繰り返される | 指摘は 1 便に合流する。blocker のみ例外 |
| auto-compact 後に handoff を書く | 要約済みの記憶から書くので、二次記述で品質が劣る | auto-compact を検出したら即交代する（閾値は無視。[context-and-handover.md](context-and-handover.md)） |
| 着地後の挨拶往復 | 「終了です」「了解です」が往復する | 着地したら何も送らない。例外は走行中への「停止」1 行だけ |
| 直列待ちが構造化される | 複数の判定が open のまま、受け手が順に止まる | 裁定に「誰が・いつ着手」を書く。hub が閉じられるものは閉じる（[messaging.md](messaging.md)「直列待ちを作らない」） |
| worker の枠組みを hub が追認する | 裁定文に worker の数値がそのまま入り、母集団違いが後で発覚する | 書く直前に「何を測った値か」「baseline は」と 1 問訊く（[adjudication.md](adjudication.md)） |
| hub の出力が検算されず成果物へ入る | hub が書いた symbol・パス・数値を worker が転記する | hub は自分の出力に照会出力を添える。worker に「私の裁定を壊しにきてください」と招く |
| `file:line` の ref 不一致 | worker の branch と hub の checkout で行番号が違う | ref を併記する。作業 ref は `git show <branch>:<path>` で読む（同じ repo の worktree なら local ref が正。push 済みの固定点を見るときは `origin/<branch>`） |
| 母集団を検索範囲で切る | 「見つかった N 件」が実は検索パターンの当たり数 | 母集団の定義を独立に確認してから数える（[adjudication.md](adjudication.md)） |
| 規約の手順を目的から切り離して適用 | 「照会できない = gate を通せない」と読んで判断を上げたが、最終の起動と実行の上界が現在を桁で超えており、「実行中でない」は推測できた | 問うべきは「照会できたか」でなく、規約が守っている物（実行中に code が入れ替わりうるか）。⛔「推測でよい」と一般化しない。上界が桁で離れているときだけ、推測が照会の代わりになる |
| 空きがあるのに新規 agent を起動 | idle の live な worker が居るのに `hc run` が走る | 起動前に `hc ls --label` と `hc get` で idle を棚卸しし、「既存で足りないか」を先に問う（[startup.md](startup.md)） |
| review が進行中 branch で腐る | 指摘した時点の SHA と実装の head がずれ、指摘が stale になる | 対象を SHA で pin する。動く branch は報告直前の再取得を課す（[briefing.md](briefing.md)「review 担当への差分」） |
| `gh issue comment --edit-last` が他人のコメントを上書き | 他セッションの直後のコメントが書き換わる | 全 agent の author が同一なので `--edit-last` は他人のコメントを掴む。comment ID を指定した `gh api -X PATCH` を使う |
| `pgrep -f` が自分自身を拾う | 走査対象が無いのに 1 件ヒットする | 自分のコマンド行にパターンが入るため。`pgrep -af '[p]ytest'` のようにブラケット記法で自分を除外する |
| 「確かめる」と「走らせる」を 1 コマンドに並べる | `pgrep ...; make test` で他の agent の実行と衝突する | 結果を読む前に走り始めるので、確かめていないのと同じ。別コマンドに分け、出力を読んでから走らせる。確かめた事実を次の実行に使い回さない |
| merge 済みかを ancestry で判定 | `git rev-list --count origin/main..<branch>` が N 件で「未 merge」と出る | squash・rebase merge は祖先を切るので、merge 済みでも N 件になる。PR 側から引く: `gh pr list --state all --json number,headRefName,state,mergedAt`（`--head` は既定で open のみ） |
| `2>/dev/null` 付きの照会が 0 件 | 「remote に無い」と読んで撤去などに進む | 「無い」と「訊けなかった（DNS・SSH の不通）」が同じ出力になる。0 件を不在の証拠にしない。エラー出力を落とさない |
