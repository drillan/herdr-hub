# herdr-hub

複数のコーディングエージェント（Claude Code・Codex・Devin など、種類が混ざってよい）を、hub-spoke 構成で調整するための runbook skill を配布する repo。呼び出したエージェントが **hub** になり、worker に依頼を配り、指示・裁定・レビュー依頼を一か所にまとめる。

## どの skill を使うか

| skill | 対象の環境 | 前提 | ドキュメント |
|---|---|---|---|
| **hc-hub** | herdr-core（`hc`）と Herdr app | `HC_TERMINAL_ID`、`uv` | [docs/hc-hub.md](docs/hc-hub.md) |
| **herdr-hub** | 旧来の herdr | `HERDR_ENV=1` | [docs/herdr-hub.md](docs/herdr-hub.md) |
| **herdr-session** | 旧来の herdr | `HERDR_ENV=1` | [skills/herdr-session/SKILL.md](skills/herdr-session/SKILL.md) |

- **hc-hub** は、レーンごとの hub が worker を起動・監視・停止する。ガード・検証・台帳・起動は同梱の CLI（`scripts/hc-hub`）が担う
- **herdr-hub** は、roster（名簿）に載る worker へ briefing を配り、transport（`herdr`・`sendmessage`・`codex-queue`）で送る
- **herdr-session** は、`herdr session stop` → `attach` でリセットされるエージェント名を capture・restore する道具

両方の hub に共通する考え方:

- skill を読むのは hub だけで、worker は読まない。hub が送る briefing が作法を伝えるので、skill を読まない種類のエージェントでも機能する
- 人は hub にだけ話し、hub が worker へ配る。worker から人への直接の経路は作らない
- hub は実装しない。裁定と実装を分ける

## インストール

skill ごとに入れる（`skills/<名前>/` の構成）。

```bash
# GitHub CLI（preview）
gh skill install drillan/herdr-hub hc-hub
gh skill install drillan/herdr-hub herdr-hub
gh skill install drillan/herdr-hub herdr-session

# skills.sh
npx skills add drillan/herdr-hub

# APM
apm install drillan/herdr-hub
```

手で入れるなら（開発用）、`skills/<名前>/` を `~/.claude/skills/<名前>` へ symlink かコピーする。symlink なら repo で `git pull` すれば反映され、コピーなら再コピーが要る。

```bash
ln -s /path/to/herdr-hub/skills/hc-hub ~/.claude/skills/hc-hub
```

### 更新

```bash
# GitHub CLI
gh skill update hc-hub          # 更新の確認（適用は対話の確認か --all）
gh skill update --all           # すべての skill を非対話で更新

# 1 つだけ非対話で更新するなら、--force で入れ直す
gh skill install drillan/herdr-hub hc-hub --force --scope user --agent claude-code

# バージョンの pin（インストール時か張り替え）
gh skill install drillan/herdr-hub hc-hub --pin v0.4.0

# skills.sh
npx skills update hc-hub

# APM（apm.lock.yaml を作り直す）
apm update
```

`gh skill` の注意: この repo の中で実行すると、配布元の `skills/<名前>/` が「metadata なし」として検出され、対話が出る。repo の外で実行する。`--agent`（`claude-code`・`codex`・`devin` など）と `--scope user` で置き場所を選べる。

## repo の構成

```
skills/hc-hub/          # hc-hub の本体（SKILL.md・references/・同梱 CLI）
skills/herdr-hub/       # herdr-hub の本体（SKILL.md・references/）
skills/herdr-session/   # herdr-session の本体（SKILL.md・scripts/）
examples/hc-hub-demo/   # hc-hub の試運転のサンプル
tests/                  # hc-hub の CLI と文書のテスト（uv run pytest）
docs/hc-hub.md          # hc-hub の説明
docs/herdr-hub.md       # herdr-hub の説明
docs/superpowers/       # 設計 spec・実装計画・実測のメモ
```

各 skill の詳しいファイル構成と、設計 spec・実装計画へのリンクは、それぞれのドキュメントにある。
