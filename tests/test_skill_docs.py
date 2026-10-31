import re

from _paths import DISCIPLINE_MAP, HERDR1, REFS, ROOT, SHARED, SKILL_DIR
from hc_hub_lib.catalog import KNOWN_AGENTS
from hc_hub_lib.roster import ALLOWED_KEYS

PLACED = {
    "references/lanes.md",
    "references/approvals.md",
    "references/agents.md",
    "references/startup.md",
    "references/messaging.md",
    "references/briefing.md",
    "references/roster.md",
    "references/context-and-handover.md",
    "references/failure-modes.md",
    "SKILL.md",
}


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(text: str, header_first_cell: str) -> list[tuple[str, ...]]:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and _cells(line)[0] == header_first_cell:
            rows: list[tuple[str, ...]] = []
            for body in lines[i + 2 :]:
                if not body.startswith("|"):
                    break
                rows.append(tuple(_cells(body)))
            return rows
    msg = f"表が見つからない: {header_first_cell}"
    raise AssertionError(msg)


def map_rows() -> list[dict[str, str]]:
    text = DISCIPLINE_MAP.read_text()
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("| ID |"))
    header = _cells(lines[start])
    rows = []
    for ln in lines[start + 2 :]:
        if not ln.startswith("|"):
            break
        row = dict(zip(header, _cells(ln), strict=True))
        if row["区分"] != "捨てる":
            rows.append(row)
    return rows


def test_discipline_map_rows_are_placed() -> None:
    for row in map_rows():
        if row["置き場所"] in PLACED:
            body = (SKILL_DIR / row["置き場所"]).read_text()
            assert row["検査語"] in body, row["ID"]


def test_no_legacy_herdr_commands_in_hc_hub() -> None:
    for f in SKILL_DIR.rglob("*.md"):
        if f.name in SHARED:
            continue
        assert not HERDR1.search(f.read_text()), f


def test_no_banned_words() -> None:
    for f in SKILL_DIR.rglob("*"):
        if f.is_file():
            assert "フォールバック" not in f.read_text(errors="ignore"), f


def test_approvals_table_matches_spec() -> None:
    rows = table_rows((REFS / "approvals.md").read_text(), "入力待ちの種類")
    assert [(r[1], r[2]) for r in rows] == [
        ("hub が答える", "hub が答える"),
        ("hub が画面を読んで答える", "人に上げる"),
        ("人に上げる", "人に上げる"),
        ("hub が答える", "hub が答える"),
        ("人に上げる", "人に上げる"),
    ]
    assert rows[1][0].startswith("通常の権限確認")
    assert "信頼" not in rows[0][0]
    assert "hub 自身が worker のために作った worktree" in rows[3][0]
    assert rows[4][0].startswith("フォルダの信頼の確認（それ以外")


def test_approvals_mentions_required_rules() -> None:
    t = (REFS / "approvals.md").read_text()
    for w in [
        "hc read",
        "hc-hub.needs-human=1",
        "今後は確認しない",
        "plan mode",
        "分類器",
        "hook",
        "逐語",
    ]:
        assert w in t, w


def test_lanes_uses_start_and_guard() -> None:
    t = (REFS / "lanes.md").read_text()
    assert "hc-hub start" in t
    assert "hc-hub guard" in t


def test_relative_links_resolve() -> None:
    for f in SKILL_DIR.rglob("*.md"):
        for link in re.findall(r"\]\(([^)#:]+\.md)\)", f.read_text()):
            assert (f.parent / link).exists(), (f, link)


def test_startup_uses_spawn_argv_and_records_after_delivery() -> None:
    t = (REFS / "startup.md").read_text()
    assert "hc-hub spawn-argv" in t
    assert "--no-notify" not in t.replace("`--no-notify` を付けない", "")
    assert t.index("ledger append") > t.index("届いた")


def test_startup_reads_screen_when_state_stays_null() -> None:
    t = (REFS / "startup.md").read_text()
    assert "null" in t
    assert "hc read" in t


def test_briefing_required_rules() -> None:
    t = (REFS / "briefing.md").read_text()
    for w in [
        "hub のアドレス",
        "レーンを越えない",
        "機構的な遮断ではない",
        "作業を進めずに待つ",
    ]:
        assert w in t, w


def test_messaging_rereads_state_after_wait() -> None:
    t = (REFS / "messaging.md").read_text()
    for w in ["hc wait --children any", "hc ls", "hc get", "未測定"]:
        assert w in t, w


def test_every_map_row_is_placed_somewhere() -> None:
    assert {r["置き場所"] for r in map_rows()} <= PLACED


def test_skill_frontmatter() -> None:
    t = (SKILL_DIR / "SKILL.md").read_text()
    assert t.startswith("---\nname: hc-hub\n")
    assert "HC_TERMINAL_ID" in t.split("---")[1]


def test_skill_indexes_every_reference() -> None:
    t = (SKILL_DIR / "SKILL.md").read_text()
    for f in REFS.glob("*.md"):
        assert f"references/{f.name}" in t, f.name


def test_skill_section0_order_and_overrides() -> None:
    t = (SKILL_DIR / "SKILL.md").read_text()
    assert t.index("hc-hub preflight") < t.index("hc --skill")
    assert "blocked" in t
    assert "--outlive-parent" in t


def test_roster_doc_lists_every_allowed_key() -> None:
    t = (REFS / "roster.md").read_text()
    for stage, keys in ALLOWED_KEYS.items():
        for k in keys:
            assert f"`{k}`" in t, (stage, k)


def test_roster_doc_states_removed_keys_and_ranges() -> None:
    t = (REFS / "roster.md").read_text()
    for w in ["`kind`", "`transport`", "`on`", "0 < x ≤ 1", "^[a-z0-9_-]{1,32}$"]:
        assert w in t, w


def test_failure_modes_has_hc_specific_traps() -> None:
    t = (REFS / "failure-modes.md").read_text()
    for w in ["exit 9", "--outlive-parent", "herdr-app do", "--id", "実測"]:
        assert w in t, w


def test_briefing_links_context_and_handover() -> None:
    t = (REFS / "briefing.md").read_text()
    assert "](context-and-handover.md)" in t


def _ref(name: str) -> str:
    return (REFS / name).read_text()


def _skill() -> str:
    return (SKILL_DIR / "SKILL.md").read_text()


DEMO = ROOT / "examples/hc-hub-demo"
OWN_WORKTREE = "hub 自身が worker のために作った worktree"


def test_command_must_resolve_on_core_path() -> None:
    for name in ["roster.md", "agents.md", "failure-modes.md"]:
        assert "core の PATH" in _ref(name), name
    assert "spawn_failed: cannot start" in _ref("failure-modes.md")
    readme = (DEMO / "README.md").read_text()
    assert "core の PATH" in readme
    assert "opencode" in readme
    roster = (DEMO / ".hc-hub.yml").read_text()
    assert "[opencode, --prompt]" in roster
    assert "/home/" not in roster + readme


def test_status_is_read_as_state_with_repeated_observation() -> None:
    texts = {
        "agents.md": _ref("agents.md"),
        "startup.md": _ref("startup.md"),
        "failure-modes.md": _ref("failure-modes.md"),
        "SKILL.md": _skill(),
    }
    for name, t in texts.items():
        assert ".status.state" in t, name
        assert "複数回" in t, name
    assert "## opencode" in texts["agents.md"]
    assert "--prompt" in texts["agents.md"]
    assert "sh -c" in texts["agents.md"]


def test_blocked_hub_send_rejection_is_documented() -> None:
    assert "`--force` を使わずに待って送り直す" in _ref("briefing.md")
    messaging = _ref("messaging.md")
    assert "blocked から戻" in messaging
    assert "hc read" in messaging.split("blocked から戻")[1].splitlines()[0]
    assert "hub が blocked" in _ref("failure-modes.md")


def test_startup_argv_expansion_is_shell_neutral() -> None:
    t = _ref("startup.md")
    assert "readarray" not in t
    assert "xargs -0" in t
    skill = _skill()
    assert "hc-hub() {" in skill
    assert "zsh" in skill


def test_worker_log_lives_inside_untracked_worktree_path() -> None:
    for f in SKILL_DIR.rglob("*.md"):
        if f.name not in SHARED:
            assert ".hc-hub/logs" not in f.read_text(), f
    for name in ["context-and-handover.md", "briefing.md"]:
        assert "<worktree>/.hc-hub/<名前>.log" in _ref(name), name
    handover = _ref("context-and-handover.md")
    assert "check-ignore" in handover
    assert "info/exclude" in handover
    assert "撤去する前" in handover


def test_demo_hub_creates_worktree() -> None:
    readme = (DEMO / "README.md").read_text()
    assert "worker は herdr-hub の worktree を作り" not in readme
    assert "hub が worktree を作" in readme
    assert ".hc-hub/" in (DEMO / "rules/worker.md").read_text()


def test_trust_dialog_is_described_as_possible_not_certain() -> None:
    for name in ["agents.md", "startup.md", "failure-modes.md", "approvals.md"]:
        t = _ref(name)
        assert "出ることがある" in t, name
    assert "出なかった" in _ref("agents.md")
    assert "で止まる。このとき" not in _ref("agents.md")
    assert "hc wait <t> --timeout 60" in _ref("startup.md")


def test_trust_dialog_answered_only_for_own_worktrees() -> None:
    for name in ["approvals.md", "agents.md", "startup.md", "failure-modes.md"]:
        assert OWN_WORKTREE in _ref(name), name
    assert OWN_WORKTREE in _skill()
    approvals = _ref("approvals.md")
    assert "Yes, I trust this folder" in approvals
    assert "例外" in approvals


def test_tab_placement_uses_terminal_id_and_mandatory_rename() -> None:
    startup = _ref("startup.md")
    assert "tab.rename" in startup
    assert "省かない" in startup
    assert "spaces[].tabs[].terminals[].terminal" in startup
    assert "`where`" in startup
    failure = _ref("failure-modes.md")
    assert "`where`" in failure
    assert "同じ tab" in failure


def test_review_round1_fixes() -> None:
    startup = _ref("startup.md")
    assert 'type == "array" and length > 0 and all(.[]; type == "string")' in startup
    assert "123" in startup
    assert "workspace の新設は人間が明示した場合だけ" in startup
    assert "worktree の新設は人間が明示" not in startup
    force = "`--force` を使わずに待って送り直す"
    after_force = _ref("briefing.md").split(force)[1].splitlines()[0]
    assert "2 回まで" in after_force
    assert "ターンを終え" in after_force
    handover = _ref("context-and-handover.md")
    assert "終了コードが 1" in handover
    assert "0 と 1 以外" in handover
    after_decision = _ref("approvals.md").split("人の判断、2026-10-31")[1]
    assert "台帳" in after_decision.splitlines()[0]
    assert "`--task` が末尾に付く" not in _ref("agents.md")


def test_rules_do_not_live_in_untracked_dir() -> None:
    files = [*SKILL_DIR.rglob("*.md"), SKILL_DIR / ".hc-hub.yml.example"]
    for f in files:
        body = f.read_text()
        assert "rules: [.hc-hub/" not in body, f
        assert ".hc-hub/worker-boundary" not in body, f


def test_agents_table_matches_catalog() -> None:
    rows = table_rows(_ref("agents.md"), "名前")
    expected = [
        (a.name, "`" + " ".join(a.argv) + "`", a.status_report, a.first_task)
        for a in KNOWN_AGENTS
    ]
    assert [r[:4] for r in rows] == expected


def test_skill_section1_describes_init_flow() -> None:
    skill = _skill()
    assert "hc-hub detect" in skill
    assert "hc-hub init" in skill
    assert "カレントディレクトリ" in skill
    assert "既定は repo 直下" not in skill


def test_roster_doc_describes_detect_init() -> None:
    roster = _ref("roster.md")
    for word in ("shell_only", "shell_alias", "hc-hub.role=probe", "info/exclude"):
        assert word in roster, word


def test_init_flow_states_git_prerequisite_and_abs_path() -> None:
    skill = _skill()
    assert "git init" in skill
    assert "--abs-path" in skill
    roster = _ref("roster.md")
    for word in ("--abs-path", "absolute_paths", "別のマシンでは書き直す"):
        assert word in roster
