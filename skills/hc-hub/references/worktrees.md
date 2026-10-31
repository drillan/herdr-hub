# worktrees（worker 編成と git worktree）

複数 worker が同じ repo の別 worktree で作業する編成の作法。agent のローカルルール（permission・skill 依存の worktree 手順）には踏み込まない。

## 基本規約

- **作業は worktree が既定。** 例外は、置き場が main checkout に固定された非追跡 file の作成で、main checkout で走らせ、git の write 系を打たせない（隔離 worktree からは書けない）
- **review 担当（read-only の走査・判定）は、hub が担当ごとに作る detached worktree で走らせる。** `git worktree add --detach <path> <対象の SHA>` で作り、巡ごとに hub が `git -C <path> checkout --detach <新しい SHA>` で対象を進めてから再依頼する。review 担当には git の write 系を打たせない（checkout も hub が打つ）。main checkout で走らせない理由は 3 つ
  - 対象の版が SHA で物理的に固定される（[briefing.md](briefing.md)「review 担当への差分」の SHA の固定を、置き場でも満たす）
  - 信頼の確認に hub が答えられる。hub が答えてよいのは hub 自身が worker のために作った worktree だけで、main checkout では毎回人に上げることになる（[approvals.md](approvals.md)。Claude Code と Devin で、信頼の確認が出ることを実測）
  - 実装担当の worktree と干渉しない
- 🔴 **base は `origin/main` を名指しする**（`git switch -c <name> origin/main`）。local の `main` は遅れうる。起点を書かず「branch を切って」と渡すと、worker は共有 checkout の HEAD（前の作業の branch のまま残りうる）から切る
- **origin が無い repo**（init したばかり、など）では、ローカルの既定 branch（`main` や `master`）の SHA を名指しする。hub が `git rev-parse <既定 branch>` で取り、`git switch -c <name> <SHA>` の形で渡す。遅れる remote が無いので、名指しするのは「どの commit から切るか」を固定するため
- **他セッションの worktree に触らない**を briefing に明記する
- **merge 済みの branch に積み増さない** — 次の作業は `origin/main`（origin が無ければ既定 branch の SHA）から新しく切る

## 複数 worktree の成果を 1 本の PR へ束ねる

同じ issue の変更を 1 本の review に収めたいとき、worker ごとに別 PR へ割らず束ねる。

- 🔴 **push を経由しない — 同じ clone の worktree は object を共有する。** 相手の commit は push されていなくても引ける（`git cat-file -t <SHA>` → `commit`）。⚠ 同一マシン・同一 clone 限定
- **PR 所有者を 1 人決める。** 他の worker は branch 名と SHA を報告するだけ。所有者は `git cherry-pick <SHA>`（連続 commit なら `git merge --no-ff <branch>`）で取り込む。⛔ diff/patch の受け渡しにしない（例外: branch を持つべきでない read-only 担当のみ）
- 🔴 **着手前に 2 つ決める** — PR 所有者は誰か / **append される file の所有者は誰か**（索引・登録簿など。2 人が別々に足すと片側が黙って消える）。書き始めてから決めない
- 所有者は**取り込みの前に `origin/main` へ rebase を済ませる**。`merge --no-ff` の後に rebase すると merge commit が落ちる
- 取り込んだら**中身を検算する** — `git diff <相手 branch>..HEAD -- <対象 file>` が空、`git diff --stat` が名指し以外を動かしていない。⛔「clean に通った」は「中身が一致した」ではない

## 「merge 済みか」の判定は PR 側から引く

ancestry 系の判定は信用しない:

- `git rev-list --count origin/main..<branch>` — squash・rebase merge は祖先を切るので、merge 済みでも「未 merge の N 件」と出る
- `gh pr list --head <branch>` — 既定は open のみで merge 済みは 0 件に見える
- `git branch --merged` — squash・rebase merge の branch は現れない

```bash
gh pr list --state all --json number,headRefName,state,mergedAt   # branch 名を突合する
```

## 撤去の判定

- **撤去の候補は、PR が MERGED であることを PR 側から照会した branch の worktree だけにする**
- 🔴 **撤去の判定述語は「未保存の作業が無いか」でなく「使用中か」。** 「未 commit の変更なし / main と内容一致」は「新規作成直後」と「用済みの残骸」の両方に当てはまる。区別できない観測の上で不可逆操作をしない
- ⚠ **稼働中のセッションの worktree は撤去しない**（使用中）。worktree の `locked` フラグは「使用中」の十分条件であって必要条件ではない — 無いことは使われていないを意味しない
- `git worktree remove` は branch を消さない — branch の撤去は別途。撤去前に `git status --short` が空であることを worktree ごとに確認する
- **撤去の前に、ログと所見を写す。** worker のログ（`<worktree>/.hc-hub/<名前>.log`）と review 担当の所見ファイルは worktree の中にあり、撤去すると消える。hub が roster のディレクトリの `.hc-hub/archive/<名前>/` へ写してから撤去する（`mkdir -p` してから `cp`）。`.hc-hub/` は git の管理外なので commit されず、そのマシンにだけ残る。引き継ぎのときの扱いは [context-and-handover.md](context-and-handover.md)

## 「溜める」運用

数十分〜数時間先に人間の判断が控えているなら、**worktree に溜めさせて PR を作らせない**。報告に「溜めているもの」を 1 行で書かせる。止まった担当の分は、外して出すかを hub が決める — 全員を待たせない。
