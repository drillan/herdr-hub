# worker の境界（hc-hub 試運転）

- 作業してよいのは `examples/hc-hub-demo/` の中だけ。それ以外のファイルを変えない。例外は、hub が briefing で指す自分のログ（worktree 直下の `.hc-hub/<名前>.log`）への追記だけ
- 依頼された機能だけを足す。ほかの関数を書き換えない
- テストを先に書き、`uv run pytest` が通ってからコミットする
- 終わったら、hub のアドレスへ `hc send` で、コミットの SHA と、テストの結果を 1 行で報告する
