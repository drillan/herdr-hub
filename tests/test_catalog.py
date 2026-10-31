import pytest
from hc_hub_lib.catalog import KNOWN_AGENTS, CatalogError, find_agent


def test_catalog_matches_spec() -> None:
    assert [(a.name, a.executable, a.argv) for a in KNOWN_AGENTS] == [
        ("claude", "claude", ("claude",)),
        ("opencode", "opencode", ("opencode", "--prompt")),
        ("devin", "devin", ("devin", "--")),
        ("codex", "codex", ("codex", "--no-daemon")),
        ("copilot", "copilot", ("copilot",)),
        ("pi", "pi", ("pi",)),
    ]
    status = {a.name: (a.status_report, a.first_task) for a in KNOWN_AGENTS}
    assert status["claude"] == ("実測済み", "位置引数（実測済み）")
    assert status["opencode"] == ("実測済み", "`--prompt` の値（実測済み）")
    assert status["devin"] == ("実測済み（2026-10-31）", "`--` の後ろの値（実測済み）")
    assert status["codex"] == ("未測定", "未測定")


def test_catalog_notes_match_spec() -> None:
    notes = {a.name: a.note for a in KNOWN_AGENTS}
    assert notes == {
        "claude": "",
        "opencode": "位置引数はディレクトリと解釈される",
        "devin": (
            "`--permission-mode` を省くと、書き込みと `hc send` のたびに"
            "承認待ち（blocked）で止まる"
        ),
        "codex": "`--no-daemon` は hc のマニュアル（`hc --skill`）による",
        "copilot": "",
        "pi": "",
    }


def test_find_agent_rejects_unknown() -> None:
    assert find_agent("devin").argv == ("devin", "--")
    with pytest.raises(CatalogError, match="gemini"):
        find_agent("gemini")
