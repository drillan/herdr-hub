# hc-hub の試運転用サンプル

hc-hub の skill を実機で一通り動かすための小さなプロジェクト。`textkit` に関数を 1 つ足す課題を、レーン `demo` の hub が worker（Claude）に実装させ、reviewer（opencode）にレビューさせる。

- roster: `.hc-hub.yml`（`approval: manual`、`placement: tab`）
- worker と reviewer の境界: `rules/`
- 実行のたびに変わるもの（台帳・ログ・argv）は `.hc-hub/` に置かれ、git の管理外

worker は herdr-hub の worktree を作り、その中の `examples/hc-hub-demo/` で作業する。
