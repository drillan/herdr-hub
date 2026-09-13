# herdr-hub

Herdr 管理端末上で動く複数のコーディングエージェント（Claude Code / Codex / Devin 等、種混在可）を、**hub-spoke 構成で調整するための運用 runbook skill**。

呼び出したエージェントが **hub** になり、roster（名簿）に載る worker 群へ briefing を配り、指示・裁定・レビュー依頼を一元化する。

## 設計の核

- **この skill を読むのは hub だけ。** worker は skill を読まない。hub が投げる briefing が作法の担保になるため、`.claude/skills` を読まない agent 種（codex 等）でも機能する
- **人間は hub にだけ話し、hub が全 worker へ配る。** worker → 人間の直接経路を作らない
- **hub は実装しない。** 裁定と実装を分離する
- **roster の正は live の agent。** YAML はその記述であって逆ではない

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

⚠ `gh skill install` は **`gh skill publish` によるリリース公開後にのみ有効**。現時点では未実施のため、上 2 つまたは下記の手動インストールを使う。

### 手動インストール（開発用）

`skills/herdr-hub/` を `~/.claude/skills/herdr-hub` へ symlink またはコピーする。

```bash
# symlink（開発中はこちら。repo の更新がそのまま反映される）
ln -s /path/to/herdr-hub/skills/herdr-hub ~/.claude/skills/herdr-hub

# コピー
cp -r /path/to/herdr-hub/skills/herdr-hub ~/.claude/skills/herdr-hub
```

## 使い方

### 起動

hub にしたいエージェントのセッションで skill を呼び出す。呼び出し側 = hub。

### roster（名簿）の与え方 — 2 経路

hub の起動時に「名前 → 役割」の対応表を与える。

1. **起動引数**（最優先）: skill 起動プロンプトに `名前: 役割` をカンマ区切りで列挙

   ```
   reviewer: レビュー専任, advisor: 設計相談, worker1: 実装
   ```

2. **YAML**: `--roster <path>` で明示指定。省略時は cwd の `./.herdr-hub.yml` を読む（存在しなければ引数指定のみで動く）

```yaml
defaults:                                # 全 agent の既定値（省略可）
  placement: tab

agents:
  hub:      { role: 統括,        transport: sendmessage }
  reviewer: { role: レビュー専任 }                        # transport 省略時は既定推定
  worker1:  { role: 実装,        transport: herdr, handoff_at: 0.9, placement: pane }
```

テンプレートは [.herdr-hub.yml.example](skills/herdr-hub/.herdr-hub.yml.example)（skill 同梱） — プロジェクトの cwd に `.herdr-hub.yml` としてコピーして使う。

起動時に roster の全名前が `herdr agent list` で live に解決することを検証し、解決できない名前があれば即座にエラーとする。

### transport（通信経路）— 3 種

| transport | 宛先 | 形式 | 既定推定 |
|---|---|---|---|
| `herdr` | 全 agent 種 | `herdr agent prompt <name> "<text>"` | 既定・汎用 |
| `sendmessage` | Claude セッション | Claude が `SendMessage` ツールを呼ぶ | Claude → Claude |
| `codex-queue` | Codex セッション | `codex queue --thread <name> --message "<text>"` | 宛先が Codex |

roster YAML の `transport:` で宛先ごとに上書きできる。省略時は優先順位順に解決（個別指定 > Claude→Claude は `sendmessage` > `defaults.transport` > 宛先=Codex は `codex-queue` > `herdr`）。`defaults.transport` は sendmessage 適格でない宛先への fallback として効く（Codex 宛の codex-queue 推定も潰れる点に注意）。

### placement（配置）— pane | tab

roster の `placement` で agent の起動時配置を選ぶ。`defaults.placement` で全体既定を変えられる。

- `tab`（既定）: 新規 tab に配置。人数が増えても視認性が劣化しない
- `pane`: 現 tab に pane split。2〜3 名までが実用域

## ファイル構成

```
skills/herdr-hub/                         # skill 本体（この dir が ~/.claude/skills/herdr-hub へ置かれる）
  SKILL.md                                # skill 入口（骨子 + references 索引）
  references/
    roster.md                             # 名簿の形式・検証・export
    transports.md                         # transport 3 種の詳細と既定推定
    messaging.md                          # 送受信・待機・往復削減・着地の作法
    briefing.md                           # worker へ渡す briefing の雛形
    startup.md                            # agent の起動・配置・命名（補助）
    context-and-handover.md               # context 残量の観測と交代手順
    failure-modes.md                      # 実害カタログ（transport・運用の罠）
  .herdr-hub.yml.example                  # roster YAML テンプレート（skill 同梱）
docs/superpowers/
  specs/2026-09-13-herdr-hub-design.md    # 設計 spec
  plans/2026-09-13-herdr-hub.md           # 実装計画
```

## 仕様・計画

- 設計 spec: [docs/superpowers/specs/2026-09-13-herdr-hub-design.md](docs/superpowers/specs/2026-09-13-herdr-hub-design.md)
- 実装計画: [docs/superpowers/plans/2026-09-13-herdr-hub.md](docs/superpowers/plans/2026-09-13-herdr-hub.md)
