# hc-hub init Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同梱 CLI `hc-hub` に `detect`（hc の core から起動できるエージェントを調べる）と `init`（人が選んだ内容で `.hc-hub.yml` を書く）を足し、skill の文書と雛形を揃える。

**Architecture:** 一覧（catalog）・作業場所の検査（workspace）・調べる処理（probe）・判定（detect）・roster の組み立て（init_roster）・`.gitignore` の扱い（gitignore）を `scripts/hc_hub_lib/` の小さなモジュールに分け、`scripts/hc-hub` は引数の受け取りと JSON の出力だけを持つ。hc は既存の `tests/fake_hc.py` を拡張した偽物で差し替え、偽物は渡されたスクリプトを本物の `/bin/sh` で、テストが決めた PATH のもとで実行する。

**Tech Stack:** Python 3.13、PEP 723（`uv run --script`）、PyYAML、pytest、ruff（ALL）、mypy（strict）、git

**Spec:** `docs/superpowers/specs/2026-10-31-hc-hub-init-design.md`

## Global Constraints

- Python 3.13、PEP 723 の同梱 CLI の流儀を守る（ruff は ALL、mypy は strict）。コマンドは `uv run pytest`、`uv run ruff check . && uv run ruff format --check . && uv run mypy`
- テストファースト。実際の hc 端末を起こさない。hc は `tests/fake_hc.py` の偽物、対話シェルは本物の `/bin/sh` に一時ディレクトリの `HOME` と `PATH` を与えて差し替える
- 判定できないとき・前提が無いときは、既定値や空の結果で続けず、エラーで止まる
- エラーは標準エラーに `hc-hub: <1 行>` を出して終了コード 2。新しい例外の型は `scripts/hc-hub` の `main()` の `except` に足す。`git`・シェルを呼ぶ `subprocess` の `OSError` と `TimeoutExpired` も、各モジュールの例外に変換する
- `skills/hc-hub` の下のファイル（コードのコメントを含む）に「フォールバック」の語を書かない（`tests/test_skill_docs.py::test_no_banned_words`）
- roster に絶対パスを書かない。`command` は一覧の argv をそのまま使う
- `references/adjudication.md`・`escalation.md`・`worktrees.md` は herdr-hub と同一の複製。触らない
- コミットメッセージは日本語で「なぜ」を書き、末尾に `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- git にプロジェクト名（仕事の案件名）を出さない

## Review Focus

1. 対話シェルで alias・関数として定義されたエージェント → `missing` ではなく `shell_alias`（Task 4 の `test_classify_alias_output`）
2. 最後が改行で終わらない `.gitignore` → 先に改行を足してから `/.hc-hub/` を追記し、既存の最後の行を壊さない（Task 5 の `test_append_keeps_last_line_without_newline`）
3. `info/exclude` でだけ無視されている台帳 → `.gitignore` に追記する（Task 5 の `test_ignored_only_by_info_exclude_appends`）
4. probe の端末の `hc wait` が `reason: timeout` で返る → エラーで止まり、それでも `hc rm` は呼ばれる（Task 3 の `test_probe_core_timeout_still_removes`）
5. `--role impl="  "`（空白だけの役割）→ 何も書かずにエラー（Task 6 の `test_init_rejects_blank_role`）

---

### Task 1: 一覧（catalog）と、文字列から roster を検査する入口

**Files:**
- Create: `skills/hc-hub/scripts/hc_hub_lib/catalog.py`
- Modify: `skills/hc-hub/scripts/hc_hub_lib/roster.py:283-307`（`load_roster` を `load_roster_text` に委ねる）
- Test: `tests/test_catalog.py`、`tests/test_roster.py`（追記）

**Interfaces:**
- Produces:
  - `catalog.py`: `class CatalogError(Exception)`、`@dataclass(frozen=True) class KnownAgent: name: str; executable: str; argv: tuple[str, ...]; status_report: str; first_task: str; note: str`、`KNOWN_AGENTS: tuple[KnownAgent, ...]`、`def find_agent(name: str) -> KnownAgent`（一覧に無ければ `CatalogError`）
  - `roster.py`: `def load_roster_text(text: str, path: Path) -> Roster`（`path` はその roster が置かれる予定の場所。相対パスの基準は `path.parent`。YAML の読み込みは既存の `_Yaml12BoolLoader`、検査は `load_roster` と同一）。`load_roster(path)` はファイルを読み、`load_roster_text` を呼ぶだけにする（読めない・UTF-8 でないときのメッセージは今のまま）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_catalog.py`:

```python
from hc_hub_lib.catalog import KNOWN_AGENTS, CatalogError, find_agent
import pytest

def test_catalog_matches_spec() -> None:
    assert [(a.name, a.executable, a.argv) for a in KNOWN_AGENTS] == [
        ("claude", "claude", ("claude",)),
        ("opencode", "opencode", ("opencode", "--prompt")),
        ("devin", "devin", ("devin",)),
        ("codex", "codex", ("codex", "--no-daemon")),
        ("copilot", "copilot", ("copilot",)),
        ("pi", "pi", ("pi",)),
    ]
    status = {a.name: (a.status_report, a.first_task) for a in KNOWN_AGENTS}
    assert status["claude"] == ("実測済み", "位置引数（実測済み）")
    assert status["opencode"] == ("実測済み", "`--prompt` の値（実測済み）")
    assert status["devin"] == ("実測済み（2026-10-31）", "未測定（`hc send` で届くことは実測済み）")
    assert status["codex"] == ("未測定", "未測定")

def test_find_agent_rejects_unknown() -> None:
    assert find_agent("devin").argv == ("devin",)
    with pytest.raises(CatalogError, match="gemini"):
        find_agent("gemini")
```

`note` の文言は spec §4.5 の「注記」列をそのまま写す（空欄は `""`）。

`tests/test_roster.py` に追記:

```python
def test_load_roster_text_matches_file_loader(tmp_path: Path) -> None:
    text = "presets:\n  impl: {role: 実装, command: [claude]}\ndefaults: {approval: manual}\nledger: .hc-hub/ledger.jsonl\nlanes:\n  be: {agents: {}}\n"
    path = tmp_path / ".hc-hub.yml"
    roster = load_roster_text(text, path)
    assert roster.ledger == tmp_path / ".hc-hub/ledger.jsonl"
    assert roster.lanes == ("be",)

def test_load_roster_text_rejects_reserved_preset(tmp_path: Path) -> None:
    text = "presets:\n  hub: {role: x, command: [claude]}\ndefaults: {approval: auto}\nledger: l.jsonl\nlanes: {be: {agents: {}}}\n"
    with pytest.raises(RosterError):
        load_roster_text(text, tmp_path / ".hc-hub.yml")
```

- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_catalog.py tests/test_roster.py -q` / Expected: ImportError（`catalog`・`load_roster_text` が無い）
- [ ] **Step 3: `catalog.py` と `load_roster_text` を実装する**
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest -q` / Expected: 全件 PASS（既存の roster のテストも通る）
- [ ] **Step 5: Commit** — `git add` の対象は上の 4 ファイル。メッセージ例: `feat: hc-hub に既知のエージェントの一覧と文字列からの roster 検査を足す`

---

### Task 2: 作業場所の検査（workspace）

**Files:**
- Create: `skills/hc-hub/scripts/hc_hub_lib/workspace.py`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces: `class WorkspaceError(Exception)`、`def require_main_checkout_top(cwd: Path) -> Path`（`resolve()` 済みの最上位を返す）、`def require_not_worker(labels: Mapping[str, str]) -> None`
- 検査の中身（spec §4.2）:
  - `git -C <cwd> rev-parse --show-toplevel` の結果と `cwd` を、どちらも `resolve()` して比べる。違えば「repo の最上位で実行する（最上位: <path>）」
  - `--git-dir` と `--git-common-dir`（`resolve()` 済み）が違えば linked worktree としてエラー
  - `--show-superproject-working-tree` の出力が空でなければ submodule としてエラー
  - git の管理下でない（`rev-parse` が 0 以外）、git が無い（`OSError`）もエラー
  - `require_not_worker`: `labels.get("hc-hub.role")` が `None` か `"hub"` なら通る。それ以外の値はエラー

- [ ] **Step 1: 失敗するテストを書く** — 一時ディレクトリに `git init` した repo で:
  - `test_top_of_main_checkout_passes`: 最上位で呼ぶと最上位の `Path` が返る
  - `test_subdirectory_is_rejected`: `sub/` で呼ぶと `WorkspaceError`、メッセージに最上位のパスが入る
  - `test_linked_worktree_is_rejected`: 空コミットを作り `git worktree add <tmp>/wt` した先で呼ぶと `WorkspaceError`（メッセージに `worktree`）
  - `test_submodule_is_rejected`: 別の repo を `git -c protocol.file.allow=always submodule add` した先で呼ぶと `WorkspaceError`（メッセージに `submodule`）
  - `test_not_a_git_repo_is_rejected`
  - `test_require_not_worker`: `{}` と `{"hc-hub.role": "hub"}` は通り、`{"hc-hub.role": "worker"}` は `WorkspaceError`
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_workspace.py -q` / Expected: ImportError
- [ ] **Step 3: `workspace.py` を実装する**
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest tests/test_workspace.py -q` / Expected: PASS
- [ ] **Step 5: Commit**

---

### Task 3: hc の端末の中で調べる（probe_core）と、偽の hc の拡張

**Files:**
- Create: `skills/hc-hub/scripts/hc_hub_lib/probe.py`
- Modify: `tests/fake_hc.py`
- Test: `tests/test_probe.py`

**Interfaces:**
- Consumes: `hc_client.run_hc(hc, args) -> str`、`hc_client.HC_TIMEOUT_SECONDS`
- Produces:
  - `class ProbeError(Exception)`
  - `PROBE_WAIT_SECONDS: int = 20`（`HC_TIMEOUT_SECONDS` の 30 より短い）
  - `def probe_core(hc: str, executables: Sequence[str], cwd: Path) -> dict[str, bool]`
  - `tests/fake_hc.py`: `make_fake_hc(tmp_path, terminals, ls, *, probe_path: str | None = None, wait_override: dict[str, Any] | None = None, read_override: str | None = None, rm_fails: bool = False) -> Path`。既存の呼び出し（位置引数 3 つ）はそのまま動く
- 振る舞い（spec §4.3「hc の端末の中で調べる」）:
  - `hc run --json --bg --no-parent --name hc-hub-probe-<pid> --label hc-hub.role=probe --cwd <cwd> -- sh -c <script>` の応答の `address` を読む
  - スクリプトは名前ごとに `if command -v <q> >/dev/null 2>&1; then echo "<nonce> <name> 1"; else echo "<nonce> <name> 0"; fi`（`<q>` は `shlex.quote`）、最後に `echo "<nonce> END"; exit 0`。nonce は `secrets.token_hex(8)`
  - `hc wait --json <t> --timeout 20` の JSON が `ended is True`・`reason == "exit"`・`exit_code == 0` のときだけ先へ進む
  - `hc read <t>` から `<nonce> ` で始まる行だけを読む。名前ごとにちょうど 1 回、`END` が 1 回。欠け・重複・未知の名前・`1`/`0` 以外はエラー
  - `hc rm <t>` は `finally` で必ず呼ぶ。`rm` が失敗したら、アドレスを添えた `ProbeError`（本体の処理がすでに例外なら、その例外を優先し、rm の失敗はメッセージに添える）
- 偽の hc の拡張: `run` は引数を `run.log` に記録し、`sh -c` の後ろのスクリプトを `script.sh` に保存して `{"address": "t90", ...}` を返す。`wait` は `wait_override` があればそれを、無ければ `{"ended": true, "exit_code": 0, "reason": "exit", ...}` を返す。`read` は `read_override` があればそれを、無ければ保存したスクリプトを `/bin/sh` で `PATH=<probe_path>` のもとで実行した標準出力を返す。`rm` は `rm.log` に記録し、`rm_fails` なら終了コード 3

- [ ] **Step 1: 失敗するテストを書く** — `tmp_path/bin` に実行可能な空ファイル `claude`・`devin` を置き、`probe_path=str(tmp_path / "bin")` の偽 hc で:
  - `test_probe_core_reports_found_and_missing`: `probe_core(fake, ["claude", "opencode", "devin"], tmp_path) == {"claude": True, "opencode": False, "devin": True}`。`run.log` に `--no-parent` と `--label hc-hub.role=probe` があり、`--rm` が無い。`rm.log` に `t90`
  - `test_probe_core_timeout_still_removes`: `wait_override={"ended": False, "reason": "timeout", "exit_code": None}` で `ProbeError`、`rm.log` に `t90`
  - `test_probe_core_nonzero_exit_is_error`: `wait_override={"ended": True, "reason": "exit", "exit_code": 2}` で `ProbeError`
  - `test_probe_core_rejects_missing_line`: `read_override="garbage\n"` で `ProbeError`
  - `test_probe_core_rm_failure_is_error`: `rm_fails=True` で `ProbeError`、メッセージに `t90`
  - `test_script_checks_names_one_by_one`: `script.sh` に `command -v` が名前の数だけ現れる（1 回の `command -v` に複数の名前を渡さない。dash は最初の名前しか調べない）
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_probe.py -q` / Expected: ImportError
- [ ] **Step 3: `probe_core` と偽の hc の拡張を実装する**
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest -q` / Expected: 全件 PASS（既存の偽 hc を使うテストも通る）
- [ ] **Step 5: Commit**

---

### Task 4: 対話シェルで調べる処理・判定・`detect` サブコマンド

**Files:**
- Modify: `skills/hc-hub/scripts/hc_hub_lib/probe.py`（追記）
- Create: `skills/hc-hub/scripts/hc_hub_lib/detect.py`
- Modify: `skills/hc-hub/scripts/hc-hub`（`detect` の引数・呼び出し・`except`）
- Test: `tests/test_probe.py`（追記）、`tests/test_detect.py`

**Interfaces:**
- Consumes: Task 1 の `KNOWN_AGENTS`、Task 2 の `require_main_checkout_top`・`require_not_worker`、Task 3 の `probe_core`、`hc_client.get_labels`・`terminal_id`
- Produces:
  - `probe.py`: `SUPPORTED_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})`、`def login_shell() -> Path`（`pwd.getpwuid(os.getuid()).pw_shell`。名前が `SUPPORTED_SHELLS` に無ければ `ProbeError`）、`def probe_shell(shell: Path, executables: Sequence[str], env: Mapping[str, str] | None = None) -> dict[str, str]`（値は `command -v` の出力。見つからなければ `""`）
  - `detect.py`: `VERDICTS = ("available", "shell_only", "shell_alias", "missing")`、`def classify(found_in_core: bool, shell_output: str) -> str`、`def detect_report(core: Mapping[str, bool], shell: Mapping[str, str], shell_path: Path) -> dict[str, Any]`
  - CLI: `hc-hub detect [--hc HC]`。標準出力に `detect_report` の JSON（`ensure_ascii=False`）
- 振る舞い:
  - `probe_shell` は `[shell, "-l", "-i", "-c", script]` を `timeout=HC_TIMEOUT_SECONDS`・`capture_output`・`env` で実行する。スクリプトは名前ごとに `printf '%s %s %s\n' <nonce> <name> "$(command -v <q> 2>/dev/null)"`、最後に `printf '%s END\n' <nonce>; exit 0`
  - 終了コードが 0 でない・`END` が無い・名前が欠けるか重複する・タイムアウト・`OSError` はどれも `ProbeError`
  - 行は `split(" ", 2)` で 3 つに分ける（パスに空白が入ってよい）。末尾の空白だけの出力は `""` とみなす
  - `classify`: core で見つかれば `available`。見つからず、シェルの出力が `/` で始まれば `shell_only`、空なら `missing`、それ以外（`alias claude=…`、関数名など）は `shell_alias`
  - `detect_report` の形: `{"login_shell": str, "agents": [{"name", "verdict", "shell_output", "argv", "status_report", "first_task", "note", "fix"}]}`。`fix` は `shell_only` のとき「hc の core の PATH に <shlex.quote したディレクトリ> を足す」、`shell_alias` のとき「シェルの alias・関数ではなく、実行ファイルを hc の core の PATH に置く」、それ以外は `None`
  - CLI の `detect` は、`require_main_checkout_top(Path.cwd())` → `require_not_worker(get_labels(hc, terminal_id(env)))` → `probe_core` → `probe_shell(login_shell(), …)` → 出力、の順。対話シェルの結果が取れなければ、判定を出さずにエラーで止まる

- [ ] **Step 1: 失敗するテストを書く**
  - `tests/test_probe.py`:
    - `test_probe_shell_reads_paths_with_spaces`: `tmp/my bin/claude` を置き、`env={"HOME": str(tmp), "PATH": f"{tmp}/my bin:/usr/bin:/bin"}`、`shell=Path("/bin/sh")` で `probe_shell(..., ["claude", "pi"], env)` が `{"claude": f"{tmp}/my bin/claude", "pi": ""}`
    - `test_probe_shell_ignores_noise_from_profile`: `HOME/.profile` に `echo hello; echo "x claude /fake"` を書いても結果が変わらない
    - `test_probe_shell_nonzero_is_error`: `HOME/.profile` に `exit 5` を書くと `ProbeError`
    - `test_login_shell_rejects_fish`: `pwd.getpwuid` を monkeypatch して `/usr/bin/fish` を返すと `ProbeError`
  - `tests/test_detect.py`:
    - `test_classify_alias_output`: `classify(False, "alias claude=~/.claude/local/claude") == "shell_alias"`
    - `test_classify_table`: `(True, "") → available`、`(False, "/x/opencode") → shell_only`、`(False, "") → missing`
    - `test_report_fix_is_quoted`: `shell_only` で shell の出力が `/a b/opencode` のとき、`fix` に `'/a b'` が入る
    - `test_detect_cli_rejects_worker`: 最上位の一時 repo で、`HC_TERMINAL_ID=t7` の偽 hc が `t7` のラベルに `hc-hub.role: worker` を返すと、終了コード 2・標準エラーが `hc-hub: ` で始まる
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_probe.py tests/test_detect.py -q` / Expected: ImportError か AttributeError
- [ ] **Step 3: `probe_shell`・`login_shell`・`detect.py`・CLI の `detect` を実装する**（`ProbeError`・`WorkspaceError`・`CatalogError` を `main()` の `except` に足す）
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest -q && uv run ruff check . && uv run mypy` / Expected: 全件 PASS、違反なし
- [ ] **Step 5: Commit**

---

### Task 5: 台帳の置き場を git の管理から外す（gitignore）

**Files:**
- Create: `skills/hc-hub/scripts/hc_hub_lib/gitignore.py`
- Test: `tests/test_gitignore.py`

**Interfaces:**
- Produces: `class GitignoreError(Exception)`、`LEDGER_REL = ".hc-hub/ledger.jsonl"`、`IGNORE_LINE = "/.hc-hub/"`、`def ensure_ledger_ignored(top: Path) -> bool`（`.gitignore` に追記したら `True`、何もしなければ `False`）
- 振る舞い（spec §4.4「台帳の置き場を git の管理から外す」）:
  - `git -C <top> check-ignore -q -- .hc-hub/ledger.jsonl`。0 なら `git check-ignore -v -- .hc-hub/ledger.jsonl` の出力の出どころ（最初の `:` の前）を見る。`<top>/.gitignore` そのもので、かつ `git ls-files --error-unmatch .gitignore` が 0（追跡されている）なら `False` を返す。それ以外の出どころなら追記へ進む。1 なら追記へ進む。それ以外はエラー
  - 追記: `.gitignore` が無ければ作る。ディレクトリ・壊れたシンボリックリンク・UTF-8 でない・書き込めないはエラー。最後が改行で終わらなければ先に `\n` を足し、`/.hc-hub/\n` を足す
  - 追記のあとに `check-ignore -q` を打ち直し、0 でなければエラー（メッセージに、`git check-ignore -v` で理由を確かめるよう書く）。`check-ignore -q` の呼び出しは内部関数 `_is_ignored(top: Path) -> bool` にまとめる（0 → True、1 → False、それ以外 → `GitignoreError`）

- [ ] **Step 1: 失敗するテストを書く** — 一時 repo で:
  - `test_untracked_gitignore_entry_is_kept`: 追跡済みの `.gitignore` が `/.hc-hub/` を含むとき `False`、ファイルは変わらない
  - `test_trailing_slash_pattern_counts_as_ignored`: 追跡済みの `.gitignore` が `.hc-hub/` のとき `False`
  - `test_missing_gitignore_is_created`: `.gitignore` が無いとき `True`、中身が `"/.hc-hub/\n"`
  - `test_append_keeps_last_line_without_newline`: 中身が `"x"` のとき `True`、中身が `"x\n/.hc-hub/\n"`
  - `test_ignored_only_by_info_exclude_appends`: `.git/info/exclude` にだけ `/.hc-hub/` があるとき `True`、`.gitignore` に `/.hc-hub/` が入る
  - `test_recheck_failure_is_error`: 追記のあとの打ち直しで無視されていない場合に `GitignoreError` になる。git は親ディレクトリが無視されていると中の否定のパターンを評価せず、追記した行は最後の行なので、実際の `.gitignore` ではこの状態を作れない。そのため、無視されているかを返す内部関数 `_is_ignored(top: Path) -> bool` を設け、`monkeypatch` で 1 回目は `False`・2 回目も `False` を返させて確かめる
  - `test_gitignore_directory_is_error`: `.gitignore` がディレクトリのとき `GitignoreError`
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_gitignore.py -q` / Expected: ImportError
- [ ] **Step 3: `gitignore.py` を実装する**
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest tests/test_gitignore.py -q` / Expected: PASS
- [ ] **Step 5: Commit**


---

### Task 6: `init` サブコマンド

**Files:**
- Create: `skills/hc-hub/scripts/hc_hub_lib/init_roster.py`
- Modify: `skills/hc-hub/scripts/hc-hub`（`init` の引数・呼び出し・`except`）
- Test: `tests/test_init_roster.py`

**Interfaces:**
- Consumes: Task 1 の `find_agent`・`load_roster_text`、既存の `roster.resolve_worker`、Task 2 の検査、Task 3 の `probe_core`、Task 5 の `ensure_ledger_ignored`
- Produces:
  - `class InitError(Exception)`
  - `ROSTER_NAME = ".hc-hub.yml"`
  - `def parse_pairs(values: Sequence[str], flag: str) -> dict[str, str]`（最初の `=` で分ける。`=` が無い・左が空・同じ左辺が 2 回はエラー）
  - `def build_roster(lane: str, approval: str, presets: Mapping[str, str], roles: Mapping[str, str]) -> dict[str, Any]`（`presets` は preset 名 → エージェント名。キーの集合が一致しない・役割が `strip()` で空はエラー。形は `{"presets": {<名>: {"role": <役割>, "command": [<argv>...]}}, "defaults": {"approval": <approval>}, "ledger": ".hc-hub/ledger.jsonl", "lanes": {<lane>: {"agents": {}}}}`）
  - `def render_roster(cfg: Mapping[str, Any]) -> str`（`yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)`）
  - `def check_roster_text(text: str, path: Path, lane: str, preset_names: Iterable[str]) -> None`（`load_roster_text` のあと、preset ごとに `resolve_worker(roster, lane, name)`。`RosterError` はそのまま上げる）
  - `def write_exclusive(path: Path, text: str) -> None`（`open(path, "x", encoding="utf-8")`。既にあれば—壊れたシンボリックリンクを含め—`InitError`）
  - CLI: `hc-hub init [--hc HC] --lane L --approval {auto,manual} --preset NAME=AGENT [--preset …] --role NAME=ROLE [--role …]`。`--preset` と `--role` は `action="append"`、どちらも `required=True`。標準出力に `{"roster": <path>, "gitignore_appended": <bool>, "next": "<.gitignore と .hc-hub.yml を commit する、という 1 文>"}`
- CLI の順序: 引数の検査（`parse_pairs`・`find_agent`・`build_roster`）→ `require_main_checkout_top` → `require_not_worker` → `render_roster` → `check_roster_text`（書く前）→ `probe_core` で選ばれたエージェントの実行ファイルを確かめ直し、1 つでも `False` ならエラー → `write_exclusive` → `ensure_ledger_ignored` → ファイルを `load_roster` で読み直して `check_roster_text` と同じ検査 → 出力。対話シェルは調べない

- [ ] **Step 1: 失敗するテストを書く**
  - 関数のテスト:
    - `test_parse_pairs_splits_on_first_equals`: `parse_pairs(["impl=実装 a=b"], "--role") == {"impl": "実装 a=b"}`
    - `test_parse_pairs_rejects_duplicates_and_missing_equals`
    - `test_build_roster_shape`: `build_roster("be", "manual", {"impl": "claude", "rev": "opencode"}, {"impl": "実装", "rev": "review"})` の `presets.rev.command == ["opencode", "--prompt"]`、`ledger == ".hc-hub/ledger.jsonl"`、`lanes == {"be": {"agents": {}}}`
    - `test_render_roster_keeps_yaml_special_roles`: 役割 `"true"`・`"# x"`・`"独立 review: 厳しめ"` が `load_roster_text` を通って文字列のまま読める
    - `test_write_exclusive_refuses_dangling_symlink`
  - CLI のテスト（一時 repo の最上位を `cwd` に、偽 hc は `t7` に `{}` のラベル、`probe_path` に `claude` だけを置く）:
    - `test_init_writes_roster_and_gitignore`: `init --lane be --approval manual --preset impl=claude --role impl=実装` が終了コード 0。`.hc-hub.yml` が `load_roster` を通り、`.gitignore` に `/.hc-hub/`、出力 JSON の `gitignore_appended` が `true`
    - `test_init_rejects_blank_role`: `--role "impl=  "` で終了コード 2、`.hc-hub.yml` と `.gitignore` が作られていない
    - `test_init_refuses_existing_roster`: 既存の `.hc-hub.yml` があると終了コード 2、中身が変わらない
    - `test_init_rejects_agent_not_on_core_path`: `--preset rev=opencode`（`probe_path` に無い）で終了コード 2、何も書かれていない
    - `test_init_rejects_reserved_preset_name`: `--preset hub=claude --role hub=x` で終了コード 2、何も書かれていない
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_init_roster.py -q` / Expected: ImportError
- [ ] **Step 3: `init_roster.py` と CLI の `init` を実装する**（`InitError`・`GitignoreError` を `main()` の `except` に足す）
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy` / Expected: 全件 PASS、違反なし
- [ ] **Step 5: Commit**

---

### Task 7: skill の文書・雛形・README を揃える

**Files:**
- Modify: `skills/hc-hub/SKILL.md`（§0 の「確かめたエージェント」、§1）
- Modify: `skills/hc-hub/references/roster.md`
- Modify: `skills/hc-hub/references/agents.md`
- Modify: `skills/hc-hub/.hc-hub.yml.example`
- Modify: `README.md`（hc-hub 節の「`.hc-hub.yml` の作り方」）
- Test: `tests/test_skill_docs.py`（追記）

**Interfaces:**
- Consumes: Task 1 の `KNOWN_AGENTS`、Task 4・6 の CLI の引数（文書の `hc-hub …` の行は `tests/test_skill_cli_snippets.py` がパーサーと突き合わせる）

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_skill_docs.py`）
  - `test_rules_do_not_live_in_untracked_dir`: `SKILL_DIR` の下の `.md` と `.hc-hub.yml.example` に `rules: [.hc-hub/` と `.hc-hub/worker-boundary` が現れない
  - `test_agents_table_matches_catalog`: agents.md の、最初のセルが `名前` の表（既存の `table_rows` で読む）の行が、`KNOWN_AGENTS` の `(name, "`" + " ".join(argv) + "`", status_report, first_task)` と順序ごと一致する
  - `test_skill_section1_describes_init_flow`: SKILL.md に `hc-hub detect`・`hc-hub init`・「カレントディレクトリ」が現れ、「既定は repo 直下」が現れない
  - `test_roster_doc_describes_detect_init`: roster.md に `shell_only`・`shell_alias`・`hc-hub.role=probe`・`info/exclude` が現れる
- [ ] **Step 2: 失敗を確かめる** — Run: `uv run pytest tests/test_skill_docs.py -q` / Expected: 新しいテストが FAIL
- [ ] **Step 3: 文書を直す**（spec §5 の各項目）
  - SKILL.md §0: 「確かめたエージェント」を一覧に合わせる（Claude Code・opencode は状態の報告と依頼の渡し方、Devin は状態の報告まで。詳しくは agents.md）
  - SKILL.md §1: 既定の roster はカレントディレクトリの `.hc-hub.yml`、repo の最上位で実行する。roster が無いときは、エラーで止まったあと人に init の流れで作るかを尋ね、作るなら `hc-hub detect` → 提案（`available` だけを選べる。未測定の列を明示）→ 人が選ぶ → `hc-hub init …` の順。規律のファイルは init のあとに人が置いて書き足す
  - roster.md: detect と init の節（判定 4 つの表、`fix`、probe の端末の例外、`.gitignore` と worker の worktree の `info/exclude` の関係、init は commit しないこと）。15 行目の手順に init を並べる。YAML スキーマの例の `rules` を `hc-hub-rules/…` に直す
  - agents.md: 一覧の表（`| 名前 | 起動の argv | 状態の報告 | 最初の依頼の渡し方 |`）を置く。`## Devin` の節（2026-10-31 に hc 0.1.15・Devin CLI v3000.11.234 で、状態の報告・`hc send` の到達・`hc read` で context の使用率が読めることを実測。承認待ちと `--permission-mode` は未測定）を立て、55 行目の「hc では未測定」の例を差し替える
  - `.hc-hub.yml.example`: `rules` の置き場を `hc-hub-rules/` に移す
  - README: 「`.hc-hub.yml` の作り方」の先頭に detect → init の流れを足し、最小形の例を `init` の出力（`ledger: .hc-hub/ledger.jsonl`、`lanes.<L>.agents: {}`）と揃える
  - 既存の `test_discipline_map_rows_are_placed` が検査語の消失で落ちたら、文書側に検査語を残す形で直す（対応表は変えない）
- [ ] **Step 4: 通ることを確かめる** — Run: `uv run pytest -q && uv run ruff check . && uv run mypy` / Expected: 全件 PASS
- [ ] **Step 5: Commit**
