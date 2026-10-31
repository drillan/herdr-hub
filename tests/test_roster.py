import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from _paths import SCRIPT
from hc_hub_lib.roster import (
    ALLOWED_KEYS,
    RosterError,
    load_roster,
    resident_names,
    resolve_hub,
    resolve_resident,
    resolve_worker,
)

RULE_FILES = ("d.md", "l.md", "p.md", "h.md", "x.md")


def base() -> dict[str, Any]:
    return {
        "presets": {
            "impl": {"role": "実装", "command": ["claude"], "rules": ["p.md"]},
            "reviewer": {"role": "review", "command": ["codex", "--no-daemon"]},
            "advisor": {"role": "設計相談", "template": "advisor"},
        },
        "defaults": {"rules": ["d.md"], "approval": "auto"},
        "ledger": "ledger.jsonl",
        "lanes": {
            "be": {
                "rules": ["l.md"],
                "hub": {"rules": ["h.md"]},
                "agents": {
                    "be-rev": {
                        "role": "review",
                        "command": ["codex", "--no-daemon"],
                        "approval": "auto",
                    },
                },
            },
            "fe": {"approval": "manual", "agents": {}},
        },
    }


def write(directory: Path, cfg: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name in RULE_FILES:
        (directory / name).write_text("")
    path = directory / ".hc-hub.yml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return path


def cfg_of(**edits: Any) -> dict[str, Any]:  # noqa: ANN401
    cfg = copy.deepcopy(base())
    for dotted, value in edits.items():
        keys = dotted.split("__")
        node = cfg
        for key in keys[:-1]:
            node = node[key]
        if value is _DELETE:
            del node[keys[-1]]
        else:
            node[keys[-1]] = value
    return cfg


_DELETE = object()


def test_resolve_order_lane_overrides_defaults_and_preset_overrides_lane(
    tmp_path: Path,
) -> None:
    cfg = cfg_of(
        defaults__approval="manual",
        lanes__be__approval="auto",
        presets__impl__approval="manual",
    )
    r = resolve_worker(load_roster(write(tmp_path, cfg)), "be", "impl")
    assert r.approval == "manual"


def test_resolve_order_lane_overrides_defaults(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert resolve_worker(rs, "fe", "impl").approval == "manual"


def test_rules_union_keeps_all_stages(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert [p.name for p in resolve_worker(rs, "be", "impl").rules] == [
        "d.md",
        "l.md",
        "p.md",
    ]


def test_hub_gets_lane_and_hub_rules_but_not_preset_rules(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert [p.name for p in resolve_hub(rs, "be").rules] == ["d.md", "l.md", "h.md"]


def test_resident_rules_union_includes_individual_rules(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["be-rev"] = {"preset": "impl", "rules": ["x.md"]}
    rs = load_roster(write(tmp_path, cfg))
    names = [p.name for p in resolve_resident(rs, "be", "be-rev").rules]
    assert names == ["d.md", "l.md", "p.md", "x.md"]


def test_placement_defaults_to_tab_and_hub_has_none(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert resolve_worker(rs, "be", "impl").placement == "tab"
    assert resolve_hub(rs, "be").placement is None


def test_placement_override_follows_resolution_order(tmp_path: Path) -> None:
    cfg = cfg_of(defaults__placement="hidden", presets__impl__placement="tab")
    rs = load_roster(write(tmp_path, cfg))
    assert resolve_worker(rs, "be", "impl").placement == "tab"
    assert resolve_worker(rs, "be", "reviewer").placement == "hidden"


def test_handoff_at_defaults_to_0_8(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert resolve_worker(rs, "be", "impl").handoff_at == 0.8


def test_handoff_at_override_applies(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, cfg_of(lanes__be__handoff_at=0.5)))
    assert resolve_worker(rs, "be", "impl").handoff_at == 0.5


@pytest.mark.parametrize("value", ["high", 0, 1.5, True])
def test_invalid_handoff_at_raises(tmp_path: Path, value: object) -> None:
    with pytest.raises(RosterError, match="handoff_at"):
        load_roster(write(tmp_path, cfg_of(defaults__handoff_at=value)))


def test_approval_missing_everywhere_raises(tmp_path: Path) -> None:
    cfg = cfg_of(defaults__approval=_DELETE)
    with pytest.raises(RosterError, match="approval"):
        load_roster(write(tmp_path, cfg))


@pytest.mark.parametrize(
    ("where", "key", "value", "expected"),
    [
        (("presets", "impl"), "kind", "claude", "command か template"),
        (("lanes", "be", "agents", "be-rev"), "transport", "herdr", "hc send"),
        (("presets", "impl"), "placement", "pane", "tab か hidden"),
        (("presets", "impl"), "role_file", "r.md", "role_def"),
        (("presets", "impl"), "on", "vps", "別マシン"),
    ],
)
def test_removed_keys_raise_with_replacement(
    tmp_path: Path,
    where: tuple[str, ...],
    key: str,
    value: str,
    expected: str,
) -> None:
    cfg = cfg_of()
    node = cfg
    for part in where:
        node = node[part]
    node[key] = value
    with pytest.raises(RosterError, match=expected):
        load_roster(write(tmp_path, cfg))


def test_unquoted_on_key_is_reported_as_remote_machine(tmp_path: Path) -> None:
    path = write(tmp_path, base())
    text = path.read_text().replace("  impl:\n", "  impl:\n    on: vps\n", 1)
    path.write_text(text)
    with pytest.raises(RosterError, match="別マシン"):
        load_roster(path)


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        ({"defaults__approval": "yes"}, "approval は auto か manual.*'yes'"),
        ({"presets__impl__placement": "off"}, "placement は tab か hidden.*'off'"),
        ({"presets__impl__handoff_at": True}, "handoff_at"),
    ],
)
def test_yaml_1_1_booleans_stay_strings(
    tmp_path: Path, edit: dict[str, Any], match: str
) -> None:
    path = write(tmp_path, base())
    value = next(iter(edit.values()))
    text = yaml.safe_dump(cfg_of(**edit), allow_unicode=True)
    if isinstance(value, str):
        text = text.replace(f"'{value}'", value)
    path.write_text(text)
    with pytest.raises(RosterError, match=match):
        load_roster(path)


def test_remote_machine_key_raises(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match="別マシン"):
        load_roster(write(tmp_path, cfg_of(presets__impl__on="vps")))


def test_command_and_template_exclusive(tmp_path: Path) -> None:
    cfg = cfg_of(presets__impl__template="advisor")
    with pytest.raises(RosterError, match="command"):
        load_roster(write(tmp_path, cfg))


def test_worker_of_preset_without_launch_method_raises(tmp_path: Path) -> None:
    cfg = cfg_of(presets__bare={"role": "x"})
    rs = load_roster(write(tmp_path, cfg))
    with pytest.raises(RosterError, match="bare"):
        resolve_worker(rs, "be", "bare")


def test_unknown_key_raises(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match="bogus"):
        load_roster(write(tmp_path, cfg_of(bogus=1)))


def test_unknown_preset_raises(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    with pytest.raises(RosterError, match="nope"):
        resolve_worker(rs, "be", "nope")


def test_resident_with_unknown_preset_raises_at_load(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["be-rev"]["preset"] = "nope"
    with pytest.raises(RosterError, match="nope"):
        load_roster(write(tmp_path, cfg))


def test_ledger_required(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match="ledger"):
        load_roster(write(tmp_path, cfg_of(ledger=_DELETE)))


def test_missing_roster_file_raises_with_path(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match=r"nothing\.yml"):
        load_roster(tmp_path / "nothing.yml")


def test_missing_rules_file_raises_with_path(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match=r"gone\.md"):
        load_roster(write(tmp_path, cfg_of(lanes__be__rules=["gone.md"])))


def test_missing_role_def_file_raises_with_path(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match=r"gone-role\.md"):
        load_roster(write(tmp_path, cfg_of(presets__impl__role_def="gone-role.md")))


def test_lane_name_follows_hc_rule(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["Back End"] = cfg["lanes"].pop("fe")
    with pytest.raises(RosterError, match="Back End"):
        load_roster(write(tmp_path, cfg))


def test_resident_name_follows_hc_rule(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["x" * 33] = {"preset": "reviewer"}
    with pytest.raises(RosterError, match=r"x{33}"):
        load_roster(write(tmp_path, cfg))


def test_resident_names_unique_across_lanes(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["fe"]["agents"]["be-rev"] = {"preset": "reviewer"}
    with pytest.raises(RosterError, match="be-rev"):
        load_roster(write(tmp_path, cfg))


def test_hub_section_rejects_placement(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match="placement"):
        load_roster(write(tmp_path, cfg_of(lanes__be__hub__placement="tab")))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("command", ["claude"]),
        ("template", "advisor"),
        ("preset", "impl"),
        ("role", "x"),
        ("role_def", "x.md"),
    ],
)
def test_defaults_rejects_launch_and_role_keys(
    tmp_path: Path, key: str, value: object
) -> None:
    cfg = cfg_of()
    cfg["defaults"][key] = value
    with pytest.raises(RosterError, match=key):
        load_roster(write(tmp_path, cfg))


@pytest.mark.parametrize("key", ["command", "template", "preset"])
def test_lane_rejects_launch_keys(tmp_path: Path, key: str) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"][key] = "impl"
    with pytest.raises(RosterError, match=key):
        load_roster(write(tmp_path, cfg))


def test_resident_without_preset_resolves(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    r = resolve_resident(rs, "be", "be-rev")
    assert (r.preset, r.command) == (None, ("codex", "--no-daemon"))


def test_resident_with_preset_inherits_preset_fields(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["be-rev"] = {"preset": "reviewer"}
    r = resolve_resident(load_roster(write(tmp_path, cfg)), "be", "be-rev")
    assert (r.preset, r.role, r.command) == (
        "reviewer",
        "review",
        ("codex", "--no-daemon"),
    )


def test_resident_placement_defaults_to_tab(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert resolve_resident(rs, "be", "be-rev").placement == "tab"


def test_resident_names_lists_lane_agents_only(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    assert resident_names(rs, "be") == ("be-rev",)
    assert resident_names(rs, "fe") == ()


def test_unknown_resident_raises(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    with pytest.raises(RosterError, match="nope"):
        resolve_resident(rs, "be", "nope")


def test_invalid_enum_values_raise(tmp_path: Path) -> None:
    with pytest.raises(RosterError, match="placement"):
        load_roster(write(tmp_path, cfg_of(defaults__placement="foo")))
    with pytest.raises(RosterError, match="approval"):
        load_roster(write(tmp_path, cfg_of(defaults__approval="maybe")))


def test_paths_resolve_relative_to_roster_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub = tmp_path / "sub"
    path = write(sub, base())
    monkeypatch.chdir(tmp_path)
    rs = load_roster(path.relative_to(tmp_path))
    assert rs.ledger == sub.resolve() / "ledger.jsonl"
    rules = resolve_worker(rs, "be", "impl").rules
    assert all(p.is_absolute() and p.parent == sub.resolve() for p in rules)


def test_unknown_lane_raises(tmp_path: Path) -> None:
    rs = load_roster(write(tmp_path, base()))
    with pytest.raises(RosterError, match="nope"):
        resolve_hub(rs, "nope")
    with pytest.raises(RosterError, match="nope"):
        resolve_worker(rs, "nope", "impl")
    with pytest.raises(RosterError, match="nope"):
        resolve_resident(rs, "nope", "be-rev")
    with pytest.raises(RosterError, match="nope"):
        resident_names(rs, "nope")


def test_allowed_keys_cover_every_stage() -> None:
    assert set(ALLOWED_KEYS) == {
        "top",
        "preset",
        "defaults",
        "lane",
        "lane_hub",
        "resident",
    }
    assert "placement" not in ALLOWED_KEYS["lane_hub"]
    assert ALLOWED_KEYS["top"] == {"presets", "defaults", "ledger", "lanes"}


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def test_cli_resolve_prints_json(tmp_path: Path) -> None:
    cfg = cfg_of(defaults__approval="manual", lanes__be__approval="auto")
    roster = write(tmp_path, cfg)
    p = run_cli(
        "resolve", "--roster", str(roster), "--lane", "be", "--preset", "reviewer"
    )
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["approval"] == "auto"
    assert out["command"] == ["codex", "--no-daemon"]


def test_cli_resolve_hub_and_agent(tmp_path: Path) -> None:
    roster = write(tmp_path, base())
    hub = run_cli("resolve", "--roster", str(roster), "--lane", "be", "--hub")
    assert json.loads(hub.stdout)["placement"] is None
    assert json.loads(hub.stdout)["rules"] == [
        str(tmp_path.resolve() / n) for n in ("d.md", "l.md", "h.md")
    ]
    agent = run_cli(
        "resolve", "--roster", str(roster), "--lane", "be", "--agent", "be-rev"
    )
    assert json.loads(agent.stdout)["preset"] is None


def test_cli_validate_success_is_silent(tmp_path: Path) -> None:
    p = run_cli("validate", "--roster", str(write(tmp_path, base())))
    assert (p.returncode, p.stdout, p.stderr) == (0, "", "")


def test_cli_residents_and_default_roster_path(tmp_path: Path) -> None:
    write(tmp_path, base())
    p = run_cli("residents", "--lane", "be", cwd=tmp_path)
    assert json.loads(p.stdout) == ["be-rev"]


def test_cli_missing_default_roster_exits_2(tmp_path: Path) -> None:
    p = run_cli("residents", "--lane", "be", cwd=tmp_path)
    assert p.returncode == 2
    assert ".hc-hub.yml" in p.stderr


def test_cli_validate_error_exits_2_with_message(tmp_path: Path) -> None:
    bad = write(tmp_path, cfg_of(defaults__approval=_DELETE))
    p = run_cli("validate", "--roster", str(bad))
    assert p.returncode == 2
    assert "approval" in p.stderr
    assert len(p.stderr.strip().splitlines()) == 1


def test_cli_unknown_lane_exits_2(tmp_path: Path) -> None:
    roster = write(tmp_path, base())
    p = run_cli("residents", "--roster", str(roster), "--lane", "nope")
    assert p.returncode == 2
    assert "nope" in p.stderr


def test_non_string_resident_preset_raises_roster_error(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["be-rev"]["preset"] = ["reviewer"]
    with pytest.raises(RosterError, match="preset"):
        load_roster(write(tmp_path, cfg))


def test_null_resident_preset_raises(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["be-rev"]["preset"] = None
    with pytest.raises(RosterError, match="preset"):
        load_roster(write(tmp_path, cfg))


@pytest.mark.parametrize(
    ("preset_key", "preset_value", "agent_key", "agent_value"),
    [
        ("template", "advisor", "command", ["claude"]),
        ("command", ["claude"], "template", "advisor"),
    ],
)
def test_merged_command_and_template_conflict_raises(
    tmp_path: Path,
    preset_key: str,
    preset_value: object,
    agent_key: str,
    agent_value: object,
) -> None:
    cfg = cfg_of()
    cfg["presets"]["mix"] = {preset_key: preset_value}
    cfg["lanes"]["be"]["agents"]["be-rev"] = {
        "preset": "mix",
        agent_key: agent_value,
    }
    with pytest.raises(RosterError, match="command"):
        load_roster(write(tmp_path, cfg))


def test_resident_without_launch_method_raises_at_load(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["lanes"]["be"]["agents"]["x"] = {"approval": "auto"}
    with pytest.raises(RosterError, match=r"lanes\.be\.agents\.x"):
        load_roster(write(tmp_path, cfg))


def test_non_utf8_roster_raises(tmp_path: Path) -> None:
    path = tmp_path / ".hc-hub.yml"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(RosterError, match=r"\.hc-hub\.yml"):
        load_roster(path)


def test_preset_name_follows_hc_rule(tmp_path: Path) -> None:
    cfg = cfg_of()
    cfg["presets"]["Bad Name"] = {"command": ["claude"]}
    with pytest.raises(RosterError, match="Bad Name"):
        load_roster(write(tmp_path, cfg))


def test_resident_without_role_raises_at_load(tmp_path: Path) -> None:
    cfg = cfg_of()
    del cfg["lanes"]["be"]["agents"]["be-rev"]["role"]
    with pytest.raises(RosterError, match=r"lanes\.be\.agents\.be-rev.*role"):
        load_roster(write(tmp_path, cfg))


@pytest.mark.parametrize("value", ["", 3])
def test_worker_without_valid_role_raises(tmp_path: Path, value: object) -> None:
    cfg = cfg_of()
    cfg["presets"]["bare"] = {"command": ["claude"]}
    rs = load_roster(write(tmp_path, cfg))
    with pytest.raises(RosterError, match=r"preset bare.*role"):
        resolve_worker(rs, "be", "bare")
    cfg["presets"]["bad"] = {"command": ["claude"], "role": value}
    with pytest.raises(RosterError, match="role"):
        resolve_worker(load_roster(write(tmp_path, cfg)), "be", "bad")
