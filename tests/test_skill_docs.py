import re

from _paths import DISCIPLINE_MAP, HERDR1, REFS, SHARED, SKILL_DIR
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


def test_no_herdr1_commands_in_hc_hub() -> None:
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
    ]
    assert rows[1][0].startswith("通常の権限確認")


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
