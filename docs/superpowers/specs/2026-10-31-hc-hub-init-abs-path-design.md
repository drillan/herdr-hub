# hc-hub init の `--abs-path`（#8 の 1 点目）と init の前提（#7 の 1 点目）

## 1. 何のためか

`hc-hub detect` が `shell_only` と判定したエージェント（実行ファイルが対話シェルの PATH にだけあり、hc の core の PATH には無い）は、`init` で選べない。opencode はインストーラーが PATH を `~/.zshrc` に足すので、ふつうに入れると必ず `shell_only` になる。今は roster を手で書き足すしかなく、手で足した分には `init` が書く前に行う検査（core から起動できるか）が効かない。

絶対パスはマシンに固有の値で、commit して共有する roster に入れると別のマシンでは起動できない。そのため、絶対パスを書くかどうかは人が決め、書く作業を `init` が受け持つ。

## 2. 振る舞い

- `init` に `--abs-path <preset 名>` を足す（繰り返せる）。名前は `--preset` に出たものに限る。無い名前・重複はエラー
- 指定が無ければ、今までどおり core の PATH で見つからないエージェントはエラー。エラーのメッセージで `--abs-path` を案内する
- 指定した preset のエージェントは、ログインシェル（passwd の `pw_shell`）を `-l -i -c` で起こして `command -v` で探す（detect と同じ `probe_shell`）。結果が `/` で始まらない（alias・関数・見つからない）ときはエラー
- 指定した preset の `command` は、エージェントの argv の先頭を絶対パスに置き換えたもの（opencode なら `[<絶対パス>, --prompt]`）
- 書く前の core の検査（`probe_core`）は、絶対パスの preset については絶対パスそのものを確かめる。`command -v /絶対パス` は存在しか見ないので、実行できる通常のファイルか（`-f` と `-x`）を見る。スクリプトなら shebang のインタープリター（`env` の後ろの名前、またはその絶対パス）も core で見つかるかを確かめる。nvm で入れた codex のような `#!/usr/bin/env node` のスクリプトは、node が core の PATH に無いと起動で失敗するため。`probe_core` が受け付けるのは、実行ファイル名（`[A-Za-z0-9._-]+`）か、`/` で始まり `[A-Za-z0-9._/+-]` だけからなる絶対パス
- core の PATH で見つかるエージェントに `--abs-path` を付けてもよい（明示されたとおりに書く）
- 出力の JSON に `absolute_paths`（preset 名 → 書いた絶対パス。無ければ `{}`）を足す。空でなければ、`next` に「このマシンの絶対パスなので、別のマシンでは書き直す」ことを足す
- 対話シェルを起こすのは `--abs-path` があるときだけ

## 3. init の前提（#7 の 1 点目）

SKILL.md §1 の init の流れの先頭に、作業対象が git リポジトリであること（無ければ人が `git init` する。hub は勝手に作らない）を書く。init のあとの commit は、worker の worktree を HEAD から作るために要る（まだ commit が無い repo では、これが最初の commit になる）。`preflight` には git の検査を足さない。`preflight` は roster のある repo の中で hub を起こすときにも打つ汎用の検査で、git の検査は detect と init がすでに持つため。

## 4. 設計者の判断

- 絶対パスは人に打たせず、ログインシェルから取る。detect と同じ探し方で、人が detect の出力を写し間違えないため
- 名前は issue の案に合わせて `--abs-path` とした
