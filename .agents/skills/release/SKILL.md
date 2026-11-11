---
name: release
description: herdr-hub のリリース手順（gh skill publish で GitHub release を作成し配布を更新する）。「リリースしたい」「バージョンを上げて」「publish して」で起動。repo 内部の開発者向け skill であり、配布パッケージには含まれない。
---

# release（herdr-hub 内部手順）

**この skill は配布対象外。** `skills/` 配下に置くと `gh skill publish` の発見規約に拾われてしまうため、正本は `.agents/skills/release/` に置き、`.claude/` `.codex/` `.devin/` からは symlink で参照する。

## 手順

0. **テストと静的検査**: `uv run pytest` と `uv run ruff check . && uv run mypy .` を通す。通らなければ先に直す
   - あわせて、`herdr-hub` から `hc-hub` へ写した 2 つの references が同一であることを確かめる（`worktrees.md` は 2026-10-31 に共有をやめた）: `for f in adjudication escalation; do cmp skills/herdr-hub/references/$f.md skills/hc-hub/references/$f.md; done`（差分があれば一方を直して揃える）
1. **検証**: `gh skill publish --dry-run` — name=dir 照合・frontmatter 必須項目・install metadata の残留を確認。error があれば先に直す
   - 公式 `herdrdev/herdr-core` の `skills/herdr-core/SKILL.md` の最新コミットを**読み取りだけで**確認し、hc-hub の §0 の入口の指示（公式 skill を user scope に入れない前提、`hc --skill` を読ませる指示）と食い違っていないかを見る。GitHub の Web ページで開くか、`curl -fsSL https://raw.githubusercontent.com/herdrdev/herdr-core/master/skills/herdr-core/SKILL.md` で取る（既定ブランチ名は `git ls-remote --symref https://github.com/herdrdev/herdr-core HEAD` で確かめる。2026-10-31 時点は `master`）。外部リポジトリに対して `gh` の API は使わない
2. **semver 判定**: main の前回 tag からの差分を見て決める
   - docs/表現の修正のみ → patch（例: v0.1.0 → v0.1.1）
   - skill の振る舞い・規約の意味変更 → minor 以上
   - tag は `vX.Y.Z` 固定（ruleset `protect-release-tags` が `refs/tags/v*` の update/delete を禁じている。**打ち間違いは取り消せない**）
3. **公開**: `gh skill publish --tag vX.Y.Z`（main 上で実行。`agent-skills` topic は publish が自動付与する）
4. **確認**: `gh skill preview drillan/herdr-hub herdr-hub` でパッケージ内容を確認
   - `gh skill preview drillan/herdr-hub hc-hub` では、梱包に `scripts/hc-hub`・`scripts/hc_hub_lib/`・共有の 2 references（`adjudication`・`escalation`）と `worktrees.md`が入っていることを見る。`--dry-run` は梱包の中身を一覧しないため、公開後にここで確かめる
5. **周知**: README のインストール手順が pin を伴う場合は最新 tag を案内する

## 罠

- publish は **GitHub release を作成する**。コミットしていない変更は含まれない — main に push 済みか先に確認
- tag ruleset で immutable なので、誤った tag は二度と消せない。救済は Settings → Rules で ruleset を一時 disabled にするのみ
- この repo の配布 skill は `skills/` 配下（現在 `herdr-hub`・`hc-hub`・`hc-session`・`herdr-session`）。`.agents/` は publish の発見対象外
- **publish が tag だけ作成して失敗することがある**（GitHub API の 500 等）。`git ls-remote --tags origin` で tag を確認し、指すコミットが正しければ `gh release create <tag> --generate-notes`（または `gh api -X POST repos/<owner>/<repo>/releases -f tag_name=<tag> -f name=<tag>`）で後追い作成できる。tag が間違ったコミットを指す場合は ruleset を一時 disabled にして削除し直す
