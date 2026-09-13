---
name: release
description: herdr-hub のリリース手順（gh skill publish で GitHub release を作成し配布を更新する）。「リリースしたい」「バージョンを上げて」「publish して」で起動。repo 内部の開発者向け skill であり、配布パッケージには含まれない。
---

# release（herdr-hub 内部手順）

**この skill は配布対象外。** `skills/` 配下に置くと `gh skill publish` の発見規約に拾われてしまうため、正本は `.agents/skills/release/` に置き、`.claude/` `.codex/` `.devin/` からは symlink で参照する。

## 手順

1. **検証**: `gh skill publish --dry-run` — name=dir 照合・frontmatter 必須項目・install metadata の残留を確認。error があれば先に直す
2. **semver 判定**: main の前回 tag からの差分を見て決める
   - docs/表現の修正のみ → patch（例: v0.1.0 → v0.1.1）
   - skill の振る舞い・規約の意味変更 → minor 以上
   - tag は `vX.Y.Z` 固定（ruleset `protect-release-tags` が `refs/tags/v*` の update/delete を禁じている。**打ち間違いは取り消せない**）
3. **公開**: `gh skill publish --tag vX.Y.Z`（main 上で実行。`agent-skills` topic は publish が自動付与する）
4. **確認**: `gh skill preview drillan/herdr-hub herdr-hub` でパッケージ内容を確認
5. **周知**: README のインストール手順が pin を伴う場合は最新 tag を案内する

## 罠

- publish は **GitHub release を作成する**。コミットしていない変更は含まれない — main に push 済みか先に確認
- tag ruleset で immutable なので、誤った tag は二度と消せない。救済は Settings → Rules で ruleset を一時 disabled にするのみ
- この repo の配布 skill は `skills/herdr-hub/` のみ。`.agents/` は publish の発見対象外
