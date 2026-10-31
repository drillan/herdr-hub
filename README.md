# herdr-hub

Herdr 管理端末上で動く複数のコーディングエージェント（Claude Code / Codex / Devin 等、種混在可）を、**hub-spoke 構成で調整するための運用 runbook skill**。

呼び出したエージェントが **hub** になり、roster（名簿）に載る worker 群へ briefing を配り、指示・裁定・レビュー依頼を一元化する。

## 設計の核

- **この skill を読むのは hub だけ。** worker は skill を読まない。hub が投げる briefing が作法の担保になるため、`.claude/skills` を読まない agent 種（codex 等）でも機能する
- **人間は hub にだけ話し、hub が全 worker へ配る。** worker → 人間の直接経路を作らない
- **hub は実装しない。** 裁定と実装を分離する
- **roster は編成の意図（desired state）を記述する。** `kind` を持つ未 live エントリは hub が起動対象として起動し、起動情報の無い未 live エントリはエラー（typo 検出）。`agents:` は空でもよい

## 要件

- **Herdr 環境**: `HERDR_ENV=1`（herdr 管理 pane 内で動作することが前提。CLI 構文の正典はインストール済みバイナリの `herdr --help`）
- **agent kind**: herdr が認識するコーディングエージェント（Claude Code / Codex / Devin 等）。一覧は `herdr agent start --help` の `--kind` で確認
- **transport ごとの追加要件**:
  - `sendmessage`（Claude → Claude）: 両端とも Claude Code **v2.1.224 以上**、かつ同一マシン上でセッション登録ファイルを共有できること（コンテナ・WSL 跨ぎは不可）
  - `codex-queue`（任意 → Codex）: `codex queue` コマンド。公式リファレンス未掲載の新機能（0.149.0 で導入との報告、実機確認は **0.154.0**）。使用前に `codex queue --help` で確認
  - `herdr`（汎用・既定）: 追加要件なし

## インストール

skill 本体は `skills/herdr-hub/`（`SKILL.md` + `references/`）にある（`skills/<name>/` 構成）。

### パッケージマネージャ経由

```bash
# skills.sh
npx skills add drillan/herdr-hub

# APM
apm install drillan/herdr-hub

# GitHub CLI（preview）
gh skill install drillan/herdr-hub herdr-hub
```

### 手動インストール（開発用）

`skills/herdr-hub/` を `~/.claude/skills/herdr-hub` へ symlink またはコピーする。

```bash
# symlink（開発中はこちら。repo の更新がそのまま反映される）
ln -s /path/to/herdr-hub/skills/herdr-hub ~/.claude/skills/herdr-hub

# コピー
cp -r /path/to/herdr-hub/skills/herdr-hub ~/.claude/skills/herdr-hub
```

### 更新

```bash
# skills.sh
npx skills update herdr-hub

# APM（apm.lock.yaml を再生成）
apm update

# GitHub CLI
gh skill update herdr-hub       # 更新の確認（適用は対話確認または --all）
gh skill update --all           # 全 skill を一括更新（非対話）

# 非対話で herdr-hub だけ更新するなら再インストール（--force）
gh skill install drillan/herdr-hub herdr-hub --force --scope user --agent claude-code

# バージョン pin（インストール時 or 張り替え）
gh skill install drillan/herdr-hub herdr-hub --pin v0.1.1
```

`gh skill` の注意: **ソース repo 内で実行すると**配布元の `skills/herdr-hub/` が「metadata なし」として検出され対話が出る — repo の外で実行する。`--agent`（`claude-code` / `codex` / `devin` 等）と `--scope user` で配置先を制御できる。

手動インストールの場合: symlink なら repo で `git pull` すれば即反映、コピーなら再コピー。

## 使い方

### 起動

hub にしたいエージェントのセッションで skill を呼び出す。呼び出し側 = hub。

### roster（名簿）

hub の起動時に「名前 → 役割」の対応表を与える。与え方は 2 経路（優先順位順）:

1. **起動引数**（最優先）: skill 起動プロンプトに `名前: 役割` をカンマ区切りで列挙

   ```
   reviewer: レビュー専任, advisor: 設計相談, worker1: 実装
   ```

2. **YAML**: `--roster <path>` で明示指定。省略時は cwd の `./.herdr-hub.yml` を読む（存在しなければ引数指定のみで動く）

```yaml
presets:                                 # 名前付きの設定テンプレート（省略可）
  impl:
    role: 実装
    # role_def: roles/impl.md            # 長文の役割定義 .md（file が要るのでコメント例）
    # rules: [.herdr-hub/worker-rules.md] # 規律 file。worker は briefing へ注入、hub は起動時に読む
    kind: claude                         # live に無いとき起動対象になるマーカー
  reviewer:
    role: レビュー専任
    kind: devin

defaults:                                # 全 agent の既定値（省略可。preset・個別の指定が優先）
                                         # ⚠ rules/transport/placement/handoff_at のみ有効
                                         #   （role/role_def/preset/kind は preset か個別のみ）
  placement: tab
  # rules: [.herdr-hub/common.md]        # 全員共通の規律（個別 rules と union）
  # transport: herdr                     # native 経路を持たない宛先への fallback
  # handoff_at: 0.8

agents:                                  # 空 `{}` でも可（hub 単独起動 → 動的追加）
  hub:      { role: 統括, rules: [.herdr-hub/merge-gate.md] }
  reviewer: { preset: reviewer }
  worker1:  { preset: impl, placement: pane }
```

| フィールド | 型 | 既定 | 意味 |
|---|---|---|---|
| `role` | string | （必須。preset が与えることも可） | 役割の説明（短いラベル）。briefing にそのまま使う |
| `role_def` | string（パス） | （なし） | 長文の役割定義 .md へのパス（roster YAML の dir 基準の相対）。worker は briefing の役割ブロックへ注入、hub のものは hub が起動時に読む。旧名 `role_file` はエラーになる |
| `rules` | string または list（パス） | （なし） | その agent が従う規律 file（群）。**worker へは briefing へ本文注入、hub は起動時に自分で読む**。`defaults.rules` + preset + 個別を union |
| `preset` | string | （なし） | `presets:` のキー名。未定義名は即エラー |
| `kind` | string | （なし） | `herdr agent start --kind` の値。未 live エントリの起動対象マーカー |
| `transport` | `herdr` \| `sendmessage` \| `codex-queue` \| `auto` | `auto` | この宛先への送信経路。`auto` は省略と同じ自動解決の明示値 |
| `handoff_at` | float (0–1) | `0.8` | 交代判定の使用率閾値（80% 使用で発火） |
| `placement` | `pane` \| `tab` | `tab` | 起動時の配置。少数を横に並べて監視したいなら `pane` |

解決順序は `defaults` → `preset` → agent 個別（個別が最優先）。**`rules` だけは例外で union** — 規律は「共通＋役割固有＋個人固有」の重ね合わせなので連結する。`role_def` / `rules` / `preset` / `kind` は起動引数（`名前: 役割` 列挙）では渡せず **YAML 経路限定**。

テンプレートは [.herdr-hub.yml.example](skills/herdr-hub/.herdr-hub.yml.example)（skill 同梱） — プロジェクトの cwd に `.herdr-hub.yml` としてコピーして使う。

起動時に各エントリを 3 分岐で検証する: **live に解決できる** → そのまま / **未 live + `kind` あり** → 人間へ編成案を確認してから hub が起動 / **未 live + `kind` 無し** → 即エラー。`rules`・`role_def` の参照 file もすべて存在確認する（不在は即エラー）。稼働中の agent 追加は roster への追記 → 同じ検証経路を通す（動的追加）。

### transport（通信経路）— 3 種

| transport | 宛先 | 形式 |
|---|---|---|
| `herdr` | 全 agent 種 | `herdr agent prompt <name> "<text>"` |
| `sendmessage` | Claude セッション | Claude が `SendMessage` ツールを呼ぶ |
| `codex-queue` | Codex セッション | `codex queue --thread <name> --message "<text>"` |

`transport:` 省略時は、宛先ごとに上から最初に合致した規則で解決する:

1. agent 個別の `transport:`（最優先・強制）
2. 送り手 = Claude かつ宛先 = Claude → `sendmessage`
3. 宛先 = Codex → `codex-queue`
4. `defaults.transport`（native 経路を持たない宛先への fallback。規則 2・3 の native 推定は潰れない）
5. それ以外 → `herdr`

明示値 `transport: auto` は省略と同じくこの優先順位で自動解決する。

### placement（配置）— pane | tab

roster の `placement` で agent の起動時配置を選ぶ。`defaults.placement` で全体既定を変えられる。

- `tab`（既定）: 新規 tab に配置。人数が増えても視認性が劣化しない
- `pane`: 現 tab に pane split。2〜3 名までが実用域

### 交代（handover）

context 使用率が `handoff_at`（既定 0.8 = 80% 使用）に達したら交代判定。流れ:

1. 前任生存中に後任を仮名 `<name>-next` で起動（live 間で名は一意のため同名を取れない）
2. briefing の内容ブロック（現在の状態・最初の一手・既知の罠）は**前任が後任へ直接送る**（hub はエンベロープを書く）
3. 前任 exit 後に正名を取る — `agent rename` に加え **pane ラベル・tab ラベルも rename が必要**（追従しない）

詳細は [context-and-handover.md](skills/herdr-hub/references/context-and-handover.md)。

## hc-hub（Herdr 2 / herdr-core 向け）

Herdr 2（herdr-core、CLI は `hc`）の上で、**レーンごとの hub** が複数のコーディングエージェントを起動・監視・停止するための runbook。呼び出したエージェントが hub になる点は herdr-hub と同じ。旧 `herdr` の環境には herdr-hub を使う。

### herdr-hub（Herdr 1 版）との違い

- 前提は `HERDR_ENV=1` ではなく `HC_TERMINAL_ID`。操作は `herdr` ではなく `hc` で行う
- roster は `.hc-hub.yml`。**レーン**（`lanes:`）ごとに hub と worker を束ね、台帳（`ledger`）に起動・停止を追記する。`kind` と `transport` は廃止し、起動方法は `command` か `template`、通信は `hc send` に一本化した
- 操作の前に `hc-hub guard` でレーンのラベルを検査し、他レーンの端末を触らない
- 承認待ちには `approval: auto | manual` の範囲で hub が答える（分類器・hook・人の承認が要るルールは人へ上げる）。フォルダの信頼の確認に hub が答えるのは、hub 自身が worker のために作った worktree だけで、それ以外は人へ上げる
- worker は hub と同じ space に 1 人 1 tab で出る。hub は tab の名前を worker の名前に付け替える（名前の無い tab は並び順の番号で、新しい tab が差し込まれると番号がずれる）
- ガード・検証・台帳・起動引数の組み立ては、skill 同梱の CLI `scripts/hc-hub`（Python、`uv run --script <skill のディレクトリ>/scripts/hc-hub` で実行）が担う。文書中の `hc-hub <サブコマンド>` はこの呼び出しを指す

### 要件

- **herdr-core**（`hc` が PATH にあり、hub が `HC_TERMINAL_ID` を持つ端末の中で動くこと）
- **`uv`**（同梱 CLI `hc-hub` の実行に使う）
- 確かめたエージェントは Claude Code と opencode（対話の画面。最初の依頼は `--prompt` で渡す）。Codex は測っていない
- roster の `command` は、hc の core の PATH から見つかること。core の PATH はユーザーのシェルの PATH と違うことがあり、見つからないと `hc run` が `spawn_failed` で失敗する。core の PATH にあるディレクトリに置くか、core の PATH にディレクトリを足す

### インストール

```bash
gh skill install drillan/herdr-hub hc-hub
```

公式の `herdr-core` skill は user scope に入れない前提（description が広く発火し、worker の Claude にも見えて勝手に `hc run` を誘発しうるため）。

### `.hc-hub.yml` の作り方

[.hc-hub.yml.example](skills/hc-hub/.hc-hub.yml.example) を作業対象 repo の直下に `.hc-hub.yml` としてコピーし、パスを実在のものに直す。`ledger` と、どの段かで `approval` の指定が必須。Claude だけで編成する最小形:

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

hub にするエージェントで skill を呼び出すと、最初に `hc-hub preflight` で前提を検査し、`hc-hub validate` → `hc-hub start --lane <レーン名>` で hub になる。スキーマの詳細は [roster.md](skills/hc-hub/references/roster.md)。

### 試運転のサンプル

[examples/hc-hub-demo/](examples/hc-hub-demo/README.md) は、hc-hub を実機で一通り動かすための小さなプロジェクト。レーン `demo` の hub が worktree を作って worker（Claude）に関数を 1 つ実装させ、reviewer（opencode）にレビューさせる。台帳や argv は `examples/hc-hub-demo/.hc-hub/`（git の管理外）に置かれる。前提と流れは同ディレクトリの README を参照。

### 長く走らせる hub には自動 compact を設定する

hub は `hc wait --children any` で長く待つため、context が膨らむと途中で自動 compact が走りうる。長く走らせる hub のエージェントには、自動 compact の設定（Claude Code なら有効化と閾値）を推奨する。hub が落ちても worker は `--outlive-parent` で続くが、hub の交代は人が手で行う（[context-and-handover.md](skills/hc-hub/references/context-and-handover.md)）。

## ファイル構成

この repo からは 3 つの skill を配布する（`gh skill install drillan/herdr-hub <name>` で個別インストール可）:

- **herdr-hub** — 上記の hub-spoke 運用 runbook（Herdr 1 向け）
- **hc-hub** — Herdr 2（herdr-core）向けの hub runbook。上の「hc-hub」節を参照
- **herdr-session** — `session stop` → `attach` でリセットされる agent 名を capture/restore するユーティリティ（`skills/herdr-session/`）。HERDR_ENV=1 の pane 内で `herdr-session capture`（stop 前・rename 後）/ `herdr-session restore`（attach 後）/ `herdr-session status` を実行。照合は native session UUID で行うため pane ID の変動に強い。詳細は同 skill の SKILL.md

```
skills/hc-hub/                             # Herdr 2 向けの hub runbook（同梱 CLI つき）
  SKILL.md                                # skill 入口
  references/                             # 12 ファイル（lanes・approvals・agents・roster・startup 等）
  scripts/hc-hub                          # 同梱 CLI（preflight・validate・start・spawn-argv・guard・ledger 等）
  scripts/hc_hub_lib/                     # CLI の実装
  .hc-hub.yml.example                     # roster YAML テンプレート
examples/hc-hub-demo/                      # hc-hub の試運転用サンプル（roster・rules・小さな Python パッケージ）
tests/                                    # hc-hub の CLI と文書のテスト（uv run pytest）
skills/herdr-session/                      # agent 名の capture/restore（HERDR_ENV=1 の pane 内で実行）
  SKILL.md                                # 使い方・照合ルール・制限
  scripts/herdr-session                   # capture / restore / status（bash+jq）
skills/herdr-hub/                         # skill 本体（この dir が ~/.claude/skills/herdr-hub へ置かれる）
  SKILL.md                                # skill 入口（骨子 + references 索引）
  references/
    roster.md                             # 名簿の形式・検証・export
    transports.md                         # transport 3 種の詳細と既定推定
    messaging.md                          # 送受信・待機・往復削減・着地の作法
    briefing.md                           # worker へ渡す briefing の雛形
    startup.md                            # agent の起動・配置・命名（roster の kind から起動対象を判定）
    worktrees.md                          # worktree 編成・複数 worktree の成果の束ね方・撤去判定
    context-and-handover.md               # context 残量の観測と交代手順
    escalation.md                         # 裁定の境界（裁く/上げる・決断の要求の時機）
    adjudication.md                       # hub の裁定の質（裏取り・hub 自身の出力を疑う）
    failure-modes.md                      # 実害カタログ（transport・運用の罠）
  .herdr-hub.yml.example                  # roster YAML テンプレート（skill 同梱）
docs/superpowers/
  specs/2026-09-21-roster-desired-state-design.md  # roster 改訂 spec（desired state・rules・presets・kind の正典）
  specs/2026-09-13-herdr-hub-design.md             # 初版設計 spec（roster 周りは上の改訂版が正典）
  plans/2026-09-13-herdr-hub.md                    # 実装計画
  specs/2026-10-31-hc-hub-design.md                # hc-hub の設計 spec
  plans/2026-10-31-hc-hub.md                       # hc-hub の実装計画
  notes/2026-10-31-hc-hub-*.md                     # hc-hub の実測と、herdr-hub から移した規律の対応表
```

## 仕様・計画

- roster 改訂 spec（正典）: [docs/superpowers/specs/2026-09-21-roster-desired-state-design.md](docs/superpowers/specs/2026-09-21-roster-desired-state-design.md)
- 初版設計 spec: [docs/superpowers/specs/2026-09-13-herdr-hub-design.md](docs/superpowers/specs/2026-09-13-herdr-hub-design.md)（roster 周りは改訂版が正典）
- 実装計画: [docs/superpowers/plans/2026-09-13-herdr-hub.md](docs/superpowers/plans/2026-09-13-herdr-hub.md)
- hc-hub の設計 spec: [docs/superpowers/specs/2026-10-31-hc-hub-design.md](docs/superpowers/specs/2026-10-31-hc-hub-design.md)
- hc-hub の実装計画: [docs/superpowers/plans/2026-10-31-hc-hub.md](docs/superpowers/plans/2026-10-31-hc-hub.md)
