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
| コマンドが無い | `queue` 不明エラー | 公式リファレンス未掲載の新機能（0.154.0 で実在確認）。古い版なら `herdr` transport へ |

## 運用固有

| 失敗 | 観測 | 手 |
|---|---|---|
| hub の中継で情報が落ちる | 受け手が「来なかったもの」を観測できず後で発覚 | 件数・集合の再掲、本文同梱、[messaging.md](messaging.md)「中継は情報を落とす」の表 |
| 「追います」「監視します」を書かせる | ターンを終えた agent は何もしない。wait を回す agent は文脈を浪費 | 書くのは「いま何を区切ったか」「次に誰が動くか」だけ。起こすのは受け手 |
| 指摘が非同期に届き受け手が何度も直す | 同じ対象への修正 push が繰り返される | 指摘は 1 便に合流。blocker のみ例外 |
| auto-compact 後に handoff を書く | 要約済み記憶からの二次記述で品質が劣る | auto-compact 検出で即交代（閾値無視） |
| 着地後の挨拶往復 | 「終了です」「了解です」が往復する | 着地したら何も送らない。例外は走行中への「停止」1 行だけ |
