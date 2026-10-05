# failure-modes（実害カタログ）

何が起きたか / 区別できた最小の観測 / 打った手。新しい失敗が出たらここへ足す。

## herdr 固有

| 失敗 | 観測 | 手 |
|---|---|---|
| `blocked` を完了と誤読 | `agent get` の状態が `blocked` | 承認/質問 UI。`agent read` で画面を見て人間に判断を仰ぐ。**完了ではない** |
| `unknown` を完了と誤読 | 状態が `unknown` | 分類不能というだけ。応答を `agent read` で確認する |
| timeout/stalled を未配送と誤読して再送 | `agent_prompt_stalled` / `timeout` | **配送は済んでいる可能性が高い。** 再送前に `agent read` で届いたか確認する |
| pane から応答が読めない | `pane read --lines` を増やしても出ない | alternate screen 上で描画されている。host scrollback に残らない。受け手に「応答をファイルに書いてパスだけ返せ」と依頼する |
| agent exit で名が消える | `agent list` に名が無い | 名は live agent に紐づく。交代・再起動時は `agent start` で付け直す（[context-and-handover.md](context-and-handover.md)） |
| `session stop`→`attach` で全 agent 名が消える | 復元された agent が無名で検出される（`agent list` の name が null） | agent 名は session.json に残るが live registry へは再適用されない。`herdr-session restore`（herdr-session skill）で agent_session UUID 照合により付け直す。stop 前に `herdr-session capture` を取ると確実 |
| `pane move` 後に旧 pane ID で宛先不明 | 旧 ID が解決しない | `.result.move_result.pane.pane_id` か live agent 名で継続。旧 ID は移動プロセスの caller context でしか解決しない |
| `agent wait --until idle` が作業中に返る | prompt 入力中・typing 中の隙間で `idle` を観測して settled と判定 | 回収には status だけでなく pane 文面の poll を併用する |
| Devin が permission prompt で停止 | `blocked`・画面に承認 UI（`git grep` 等の実行許可） | 人間に「always allow in repo」を選んでもらう。hub は UI を回答しない |
| `tab create` が別 workspace に作られる | 意図しない workspace に空の tab が出現 | `--workspace` 省略時は **UI フォーカス中の workspace** に作られる。必ず `--workspace "$HERDR_WORKSPACE_ID"` を付ける（実害: 他人の workspace に tab 3 個） |
| herdr 制御コマンドが permission に拒否される | `agent prompt`/`agent start`/`tab create` が分類器に拒否される | 複合コマンド（`cd`・`;`・パイプ・`echo >>` の同梱）は permission allow の**先頭一致**から外れ、分類器の判定に回る。**制御コマンドは単独で打つ**（roster・log 更新は別コマンドに分ける） |
| SendMessage / `codex queue` が別集団の同名 agent に届く | 意図しない pane で応答・別 herdr セッションの agent が動く | 名前解決は**マシン全域**（セッション・workspace を跨ぐ）。集団が混在する環境では宛先を `herdr agent prompt` に限定する（[transports.md](transports.md)） |
| agent 終了後に空の pane/tab が残る | `pane list` に agent の消えた pane が残る | agent の exit と pane/tab の回収は別。worker には自分の `herdr pane close "$HERDR_PANE_ID"` を、hub の retire は `pane close <pane_id>` を（[messaging.md](messaging.md)「着地」） |

## SendMessage 固有

| 失敗 | 観測 | 手 |
|---|---|---|
| メッセージが held で届かない | 送り手に held 通知 / 受け手に承認 dialog | 両者の permission mode の組（受け手 bypass × 送り手プロンプト系で held）。`crossSessionInbound: accept` または組を揃える |
| 自分宛で拒否 | 送信が refuse される | roster の自分の名を外す |
| 届かない環境跨ぎ | `ListAgents` に対象が無い | コンテナ / WSL / 別マシン（Remote Control 未接続）は同一マシンの登録ファイルを共有しない。`herdr`/`codex-queue` へ逃がす |
| サイズ/バースト超過 | 送信側で拒否 | 分割・間引く。長文はファイルに書いてパスを送る |

## codex queue 固有

| 失敗 | 観測 | 手 |
|---|---|---|
| `--thread` が解決しない | name 不一致エラー | **厳密なセッション名か UUID** が必要。`codex` 側の一覧で確認。命名規約で揃える（[startup.md](startup.md)） |
| コマンドが無い | `queue` 不明エラー | 公式リファレンス未掲載の新機能（0.149.0 で導入との報告、実機確認は 0.154.0）。古い版なら `herdr` transport へ |

## 運用固有

| 失敗 | 観測 | 手 |
|---|---|---|
| hub の中継で情報が落ちる | 受け手が「来なかったもの」を観測できず後で発覚 | 件数・集合の再掲、本文同梱、[messaging.md](messaging.md)「中継は情報を落とす」の表 |
| 「追います」「監視します」を書かせる | ターンを終えた agent は何もしない。wait を回す agent は文脈を浪費 | 書くのは「いま何を区切ったか」「次に誰が動くか」だけ。起こすのは受け手 |
| 指摘が非同期に届き受け手が何度も直す | 同じ対象への修正 push が繰り返される | 指摘は 1 便に合流。blocker のみ例外 |
| auto-compact 後に handoff を書く | 要約済み記憶からの二次記述で品質が劣る | auto-compact 検出で即交代（閾値無視） |
| 着地後の挨拶往復 | 「終了です」「了解です」が往復する | 着地したら何も送らない。例外は走行中への「停止」1 行だけ |
| 直列待ちが構造化される | 複数判定が open のまま受け手が順に止まる | 裁定に「誰が・いつ着手」を書く。hub が閉じられるものは hub が閉じる（[messaging.md](messaging.md)「直列待ちを作らない」） |
| worker の枠組みを hub が追認する | 裁定文に worker の数値がそのまま入り、後で母集団違いが発覚 | 裁定を書く直前に「何を測った値か」「baseline は」を 1 問訊く（[adjudication.md](adjudication.md)） |
| hub の出力が検算されず成果物へ入る | hub が書いた symbol・パス・数値を worker が転記 | hub は自分の出力に照会出力を添える。worker に「私の裁定を壊しにきてください」と招く |
| `file:line` の ref 不一致 | worker の branch と hub の checkout で行番号が違う | ref を併記する。worker の作業 ref は `git show <branch>:<path>` で読む（同じ repo の worktree なら local ref が正。push 済みの固定点を見たいときは `origin/<branch>`） |
| 母集団を検索範囲で切る | 「見つかった N 件」が実は検索パターンの当たり数 | 母集団の定義を独立に確認してから数える（[adjudication.md](adjudication.md)「1 つ質問する」） |
| 規約の手順を目的から切り離して適用 | 「照会できない = gate を通せない」と読んで判断を上げた — 最終起動 + 実行上界が現在を桁で超えており「実行中でない」は推測できた | 問うべきは「照会できたか」ではなく規約が守っている物（実行中に code が入れ替わりうるか）。⛔「推測でよい」と一般化しない — 上界が桁で離れているときだけ推測が照会の代わりになる |
| 空きがあるのに新規 agent を起動 | idle の live agent が居るのに `agent start` が走る | 起動前に `agent list` で idle を棚卸しし、「既存で足りないか」を先に問う |
| review が進行中 branch で腐る | 指摘した時点の SHA と実装の head がずれて指摘が stale | 対象を SHA で pin。動く branch なら報告直前の再取得を課す（[briefing.md](briefing.md)「review 担当への差分」） |
| `gh issue comment --edit-last` が他人のコメントを上書き | 他セッションの直後コメントが書き換わる | 全 agent の author は同一なので `--edit-last` は他人を掴む。**comment ID 指定の `gh api -X PATCH`** を使う |
| `pgrep -f` が自分自身を拾う | 走査対象が無いのに 1 件ヒット | 自分のコマンド行にパターンが入るため。`pgrep -af '[p]ytest'` のようにブラケット記法で自分を除外する |
| 「確かめる」と「走らせる」を 1 コマンドに並べる | `pgrep ...; make test` で他 agent の実行と衝突 | 結果を読む前に走り始めるので確かめていないのと同じ。**別コマンドに分け、出力を読んでから走らせる**。確かめた事実を次の実行に使い回さない |
| merge 済みかを ancestry で判定 | `git rev-list --count origin/main..<branch>` が N 件で「未 merge」 | squash・rebase merge は祖先を切るため merge 済みでも N 件になる。**PR 側から引く**: `gh pr list --state all --json number,headRefName,state,mergedAt`（`--head` は既定 open のみ → merge 済みは 0 件に見える） |
| `2>/dev/null` 付き照会の 0 件 | 「remote に無い」と読んで撤去などに進む | 「無い」と「訊けなかった（DNS・SSH 不通）」が同じ出力。**0 件を不在の証拠にしない** — エラー出力を落とさない |
