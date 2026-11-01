# hc-hub（herdr-core 向け）

herdr-core（CLI は `hc`）の上で、**レーンごとの hub** が複数のコーディングエージェントを起動・監視・停止するための runbook。呼び出したエージェントが hub になる点は herdr-hub と同じ。旧来の `herdr` の環境には herdr-hub を使う。

## herdr-hub（旧来の `herdr` 版）との違い

- 前提は `HERDR_ENV=1` ではなく `HC_TERMINAL_ID`。操作は `herdr` ではなく `hc` で行う
- roster は `.hc-hub.yml`。**レーン**（`lanes:`）ごとに hub と worker を束ね、台帳（`ledger`）に起動・停止を追記する。`kind` と `transport` は廃止し、起動方法は `command` か `template`、通信は `hc send` に一本化した
- 操作の前に `hc-hub guard` でレーンのラベルを検査し、他レーンの端末を触らない
- 承認待ちには `approval: auto | manual` の範囲で hub が答える（分類器・hook・人の承認が要るルールは人へ上げる）。フォルダの信頼の確認に hub が答えるのは、hub 自身が worker のために作った worktree だけで、それ以外は人へ上げる
- worker は hub と同じ space に 1 人 1 tab で出る。hub は tab の名前を worker の名前に付け替える（名前の無い tab は並び順の番号で、新しい tab が差し込まれると番号がずれる）
- ガード・検証・台帳・起動引数の組み立ては、skill 同梱の CLI `scripts/hc-hub`（Python、`uv run --script <skill のディレクトリ>/scripts/hc-hub` で実行）が担う。文書中の `hc-hub <サブコマンド>` はこの呼び出しを指す

## 要件

- **herdr-core**（`hc` が PATH にあり、hub が `HC_TERMINAL_ID` を持つ端末の中で動くこと）
- **`uv`**（同梱 CLI `hc-hub` の実行に使う）
- 確かめたエージェントは Claude Code・opencode・Devin。3 つとも状態の報告と最初の依頼の渡し方まで（opencode は `--prompt`、Devin は `--` の後ろで渡す）。Codex は測っていない
- roster の `command` は、hc の core の PATH から見つかること。core の PATH はユーザーのシェルの PATH と違うことがあり、見つからないと `hc run` が `spawn_failed` で失敗する。core の PATH にあるディレクトリに置くか、core の PATH にディレクトリを足す

## インストール

```bash
gh skill install drillan/herdr-hub hc-hub
```

ほかの入れ方・更新・バージョンの pin は [README](../README.md#インストール) を参照。

公式の `herdr-core` skill は user scope に入れない前提（description が広く発火し、worker の Claude にも見えて勝手に `hc run` を誘発しうるため）。

## `.hc-hub.yml` の作り方

作業対象 repo の最上位で、hub にするエージェントから `hc-hub detect` で既知のエージェント（claude・opencode・devin・codex・copilot・pi）が hc の端末の中で起動できるかを調べる（書き込みはしない）。作業対象は git リポジトリであること（無ければ先に `git init` する）。選べるのは判定が `available` のものだけで、`shell_only`・`shell_alias`・`missing` は `fix` に従って直してから選ぶ。ただし `shell_only` は、`--abs-path <preset 名>` を付ければ、ログインシェルで見つけた絶対パスを `command` に書いて選べる（マシンに固有のパスになる）。人がレーン名・approval・preset ごとのエージェントと役割を選び、`hc-hub init --lane <レーン名> --approval auto|manual --preset <preset 名>=<エージェント名> --role <preset 名>=<役割>` で `.hc-hub.yml` を書く。`init` は台帳の置き場を `.gitignore` に足す（追跡された `.gitignore` ですでに無視されていれば足さない）が、commit はしないので、`.gitignore` と `.hc-hub.yml` を commit する。worker の worktree は HEAD から作るので、この commit は worker を起こす前に要る。

手で書くなら、[.hc-hub.yml.example](../skills/hc-hub/.hc-hub.yml.example) を作業対象 repo の直下に `.hc-hub.yml` としてコピーし、パスを実在のものに直す。`ledger` と、どの段かで `approval` の指定が必須。Claude だけで編成する最小形（`init` の出力と同じ形）:

```yaml
presets:
  impl: { role: 実装, command: [claude] }
defaults:
  approval: manual
ledger: .hc-hub/ledger.jsonl
lanes:
  backend:
    agents: {}
```

hub にするエージェントで skill を呼び出すと、最初に `hc-hub preflight` で前提を検査し、`hc-hub validate` → `hc-hub start --lane <レーン名>` で hub になる。スキーマの詳細は [roster.md](../skills/hc-hub/references/roster.md)。

## 試運転のサンプル

[examples/hc-hub-demo/](../examples/hc-hub-demo/README.md) は、hc-hub を実機で一通り動かすための小さなプロジェクト。レーン `demo` の hub が worktree を作って worker（Claude）に関数を 1 つ実装させ、reviewer（opencode）にレビューさせる。台帳や argv は `examples/hc-hub-demo/.hc-hub/`（git の管理外）に置かれる。前提と流れは同ディレクトリの README を参照。

## 長く走らせる hub には自動 compact を設定する

hub は `hc wait --children any` で長く待つため、context が膨らむと途中で自動 compact が走りうる。長く走らせる hub のエージェントには、自動 compact の設定（Claude Code なら有効化と閾値）を推奨する。hub が落ちても worker は `--outlive-parent` で続くが、hub の交代は人が手で行う（[context-and-handover.md](../skills/hc-hub/references/context-and-handover.md)）。

## ファイル構成

```
skills/hc-hub/                            # skill の本体（同梱 CLI つき）
  SKILL.md                                # skill 入口
  references/                             # 12 ファイル（lanes・approvals・agents・roster・startup 等）
  scripts/hc-hub                          # 同梱 CLI（preflight・validate・start・spawn・spawn-argv・guard・ledger 等）
  scripts/hc_hub_lib/                     # CLI の実装
  .hc-hub.yml.example                     # roster YAML テンプレート
examples/hc-hub-demo/                      # hc-hub の試運転用サンプル（roster・rules・小さな Python パッケージ）
tests/                                    # hc-hub の CLI と文書のテスト（uv run pytest）
docs/superpowers/notes/2026-10-31-hc-hub-*.md   # 実測と、herdr-hub から移した規律の対応表
```

## 仕様・計画

- hc-hub の設計 spec: [docs/superpowers/specs/2026-10-31-hc-hub-design.md](superpowers/specs/2026-10-31-hc-hub-design.md)
- hc-hub の実装計画: [docs/superpowers/plans/2026-10-31-hc-hub.md](superpowers/plans/2026-10-31-hc-hub.md)
- 以後の追加の設計（init・`--abs-path`・spawn など）: [docs/superpowers/specs/](superpowers/specs/) の `2026-10-31-hc-hub-*-design.md`
