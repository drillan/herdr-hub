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
| `pane move` 後に旧 pane ID で宛先不明 | 旧 ID が解決しない | `.result.move_result.pane.pane_id` か live agent 名で継続。旧 ID は移動プロセスの caller context でしか解決しない |
| `agent wait --until idle` が作業中に返る | prompt 入力中・typing 中の隙間で `idle` を観測して settled と判定 | 回収には status だけでなく pane 文面の poll を併用する |
| Devin が permission prompt で停止 | `blocked`・画面に承認 UI（`git grep` 等の実行許可） | 人間に「always allow in repo」を選んでもらう。hub は UI を回答しない |

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
