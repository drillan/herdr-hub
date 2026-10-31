# hc-hub の試運転用サンプル

hc-hub の skill を実機で一通り動かすための小さなプロジェクト。`textkit` に関数を 1 つ足す課題を、レーン `demo` の hub が worker（Claude）に実装させ、reviewer（opencode）にレビューさせる。

- roster: `.hc-hub.yml`（`approval: manual`、`placement: tab`）
- worker と reviewer の境界: `rules/`
- 実行のたびに変わるもの（台帳・argv）は `.hc-hub/` に置かれ、git の管理外。worker のログは worker の worktree の中の `.hc-hub/<名前>.log` に置かれる（hub が非追跡であることを確かめる）

## 前提

- reviewer の `command` は `opencode` を PATH から探す。hc の core の PATH はユーザーのシェルの PATH と違うことがあり、`~/.opencode/bin` のように追加した場所にある opencode は core から見つからない。見つからないと `hc run` が `spawn_failed: cannot start "opencode"` で失敗する。試運転の前に、opencode を core の PATH にあるディレクトリに置くか、core の PATH にそのディレクトリを入れる。個人の絶対パスはこの roster に書かない
- opencode の対話の画面は、最初の依頼を `--prompt` で受ける（roster の `command` が `--prompt` を含む）

## 流れ

hub が worktree を作り、その絶対パスを `--cwd` に渡して worker を起こす。worker はその worktree の中の `examples/hc-hub-demo/` で作業する。worktree の作り方は skill の `references/worktrees.md` に従う。
