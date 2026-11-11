import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fake_hc import herdr_ls, make_fake_hc, make_fake_herdr_app, run_cli
from hc_hub_lib.guard import GuardError
from hc_hub_lib.roster import (
    Resolved,
    RosterError,
    load_roster,
    resolve_resident,
    resolve_worker,
)
from hc_hub_lib.spawn import SpawnError, find_tab, spawn_argv, start_hub

L = "hc-hub.lane"
R = "hc-hub.role"
SELF = {L: "be", R: "hub", "herdr.space": "sp1"}
CWD = Path(__file__).resolve().parent


def write_roster(directory: Path) -> Path:
    cfg = {
        "presets": {
            "impl": {"role": "実装", "command": ["claude"], "placement": "tab"},
            "quiet": {
                "role": "静か",
                "command": ["claude", "--x"],
                "placement": "hidden",
            },
            "advisor": {"role": "設計相談", "template": "advisor", "placement": "tab"},
        },
        "defaults": {"approval": "auto"},
        "ledger": "ledger.jsonl",
        "lanes": {
            "be": {
                "agents": {
                    "be-rev": {
                        "role": "review",
                        "command": ["codex"],
                        "placement": "tab",
                    }
                }
            },
        },
    }
    path = directory / ".hc-hub.yml"
    path.write_text(yaml.safe_dump(cfg))
    return path


@pytest.fixture
def roster_path(tmp_path: Path) -> Path:
    return write_roster(tmp_path)


def worker(roster_path: Path, preset: str) -> Resolved:
    return resolve_worker(load_roster(roster_path), "be", preset)


def test_start_hub_returns_self_labels(roster_path: Path) -> None:
    rs = load_roster(roster_path)
    assert start_hub(rs, "be", "t5", []) == ["hc-hub.lane=be", "hc-hub.role=hub"]


def test_start_hub_refuses_second_hub(roster_path: Path) -> None:
    rs = load_roster(roster_path)
    with pytest.raises(SpawnError):
        start_hub(rs, "be", "t5", [{"address": "t3", "state": "live"}])


def test_start_hub_ignores_self_in_ls(roster_path: Path) -> None:
    rs = load_roster(roster_path)
    assert start_hub(rs, "be", "t5", [{"address": "t5", "state": "live"}])


def test_start_hub_ignores_finished_hub(roster_path: Path) -> None:
    rs = load_roster(roster_path)
    assert start_hub(rs, "be", "t5", [{"address": "t3", "state": "finished"}])


def test_start_hub_unknown_lane(roster_path: Path) -> None:
    rs = load_roster(roster_path)
    with pytest.raises(RosterError):
        start_hub(rs, "nope", "t5", [])


def test_spawn_argv_tab_adds_space_not_tab(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "impl"),
        "be",
        "be-impl-1",
        "do x",
        SELF,
        None,
        role="impl",
        cwd=CWD,
    )
    assert a[:6] == [
        "run",
        "--bg",
        "--json",
        "--outlive-parent",
        "--name",
        "be-impl-1",
    ]
    assert "herdr.space=sp1" in a
    assert not any(x.startswith("herdr.tab=") for x in a)
    assert "--no-notify" not in a
    assert "hc-hub.role=impl" in a
    assert a[-3:] == ["--", "claude", "do x"]
    assert a[-1] == "do x"


def test_spawn_argv_hidden_has_no_herdr_labels(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "quiet"),
        "be",
        "be-q-1",
        "x",
        SELF,
        None,
        role="quiet",
        cwd=CWD,
    )
    assert not any(x.startswith("herdr.") for x in a)
    assert a[-4:] == ["--", "claude", "--x", "x"]


def test_spawn_argv_brief_label(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "impl"),
        "be",
        "be-impl-1",
        "x",
        SELF,
        "t/b.md",
        role="impl",
        cwd=CWD,
    )
    assert "hc-hub.brief=t/b.md" in a


def test_spawn_argv_template_task_follows_template(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "advisor"),
        "be",
        "be-adv-1",
        "ask",
        SELF,
        None,
        role="advisor",
        cwd=CWD,
    )
    assert a[-3:] == ["--", "advisor", "ask"]


def test_spawn_argv_tab_without_space_refuses(roster_path: Path) -> None:
    with pytest.raises(GuardError, match=r"herdr\.space"):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            "be-impl-1",
            "x",
            {L: "be", R: "hub"},
            None,
            role="impl",
            cwd=CWD,
        )


@pytest.mark.parametrize("bad", ["Be Impl", "", "a" * 33, "x/y"])
def test_spawn_argv_bad_name(roster_path: Path, bad: str) -> None:
    with pytest.raises(SpawnError):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            bad,
            "x",
            SELF,
            None,
            role="impl",
            cwd=CWD,
        )


def test_spawn_argv_resident_without_preset_uses_entry_name_as_role(
    roster_path: Path,
) -> None:
    res = resolve_resident(load_roster(roster_path), "be", "be-rev")
    a = spawn_argv(res, "be", "be-rev", "x", SELF, None, role="be-rev", cwd=CWD)
    assert "hc-hub.role=be-rev" in a


def test_spawn_argv_resident_with_preset_uses_entry_name_as_role(
    tmp_path: Path,
) -> None:
    cfg = {
        "presets": {"impl": {"role": "実装", "command": ["claude"]}},
        "defaults": {"approval": "auto"},
        "ledger": "l.jsonl",
        "lanes": {"be": {"agents": {"be-main": {"preset": "impl"}}}},
    }
    path = tmp_path / ".hc-hub.yml"
    path.write_text(yaml.safe_dump(cfg))
    res = resolve_resident(load_roster(path), "be", "be-main")
    a = spawn_argv(res, "be", "be-main", "x", SELF, None, role="be-main", cwd=CWD)
    assert "hc-hub.role=be-main" in a
    assert "hc-hub.role=impl" not in a


def test_cli_start_labels_self(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {}}}, [])
    p = run_cli(
        "start",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "label.log").read_text() == "t5 hc-hub.lane=be hc-hub.role=hub\n"


def test_cli_start_creates_state_dir(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {}}}, [])
    state_dir = roster_path.parent / ".hc-hub"
    assert not state_dir.exists()
    p = run_cli(
        "start",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 0, p.stderr
    assert state_dir.is_dir()


def test_cli_start_rejects_state_dir_that_is_a_file(
    tmp_path: Path, roster_path: Path
) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {}}}, [])
    (roster_path.parent / ".hc-hub").write_text("x")
    p = run_cli(
        "start",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 2
    assert ".hc-hub" in p.stderr
    assert not (tmp_path / "label.log").exists()


def test_cli_start_refuses_when_other_hub_live(
    tmp_path: Path, roster_path: Path
) -> None:
    hc = make_fake_hc(
        tmp_path,
        {
            "t3": {"address": "t3", "state": "live", "labels": {}},
            "t5": {"address": "t5", "state": "live", "labels": {}},
        },
        [{"address": "t3"}],
    )
    p = run_cli(
        "start",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 2
    assert "t3" in p.stderr
    assert not (tmp_path / "label.log").exists()


def test_cli_spawn_argv_prints_json_array(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": SELF}}, [])
    p = run_cli(
        "spawn-argv",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--preset",
        "impl",
        "--name",
        "be-impl-1",
        "--task",
        "do x",
        "--brief",
        "t/b.md",
        "--cwd",
        str(CWD),
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 0, p.stderr
    argv = json.loads(p.stdout)
    assert argv[0] == "run"
    assert "hc-hub.brief=t/b.md" in argv
    assert argv[-1] == "do x"


def test_cli_spawn_argv_agent_role_is_entry_name(
    tmp_path: Path, roster_path: Path
) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": SELF}}, [])
    p = run_cli(
        "spawn-argv",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--agent",
        "be-rev",
        "--name",
        "be-rev",
        "--task",
        "x",
        "--cwd",
        str(CWD),
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 0, p.stderr
    assert "hc-hub.role=be-rev" in json.loads(p.stdout)


@pytest.mark.parametrize("bad", ["", "Bad Role", "a" * 33])
def test_spawn_argv_bad_role(roster_path: Path, bad: str) -> None:
    with pytest.raises(SpawnError, match="role"):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            "be-impl-1",
            "x",
            SELF,
            None,
            role=bad,
            cwd=CWD,
        )


def test_cli_start_ls_row_without_address_is_error(
    tmp_path: Path, roster_path: Path
) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {}}}, [{"state": "live"}])
    p = run_cli(
        "start",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 2
    assert "address" in p.stderr
    assert "Traceback" not in p.stderr


def test_spawn_argv_emits_cwd_before_command(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "impl"),
        "be",
        "be-impl-1",
        "x",
        SELF,
        None,
        role="impl",
        cwd=CWD,
    )
    i = a.index("--cwd")
    assert a[i + 1] == str(CWD)
    assert i < a.index("--")


def test_spawn_argv_relative_cwd_refuses(roster_path: Path) -> None:
    with pytest.raises(SpawnError, match="絶対"):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            "be-impl-1",
            "x",
            SELF,
            None,
            role="impl",
            cwd=Path("rel/dir"),
        )


def test_spawn_argv_missing_cwd_refuses(roster_path: Path, tmp_path: Path) -> None:
    with pytest.raises(SpawnError, match="存在"):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            "be-impl-1",
            "x",
            SELF,
            None,
            role="impl",
            cwd=tmp_path / "nope",
        )


def test_cli_spawn_argv_requires_cwd(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": SELF}}, [])
    p = run_cli(
        "spawn-argv",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--preset",
        "impl",
        "--name",
        "be-impl-1",
        "--task",
        "x",
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode != 0
    assert "--cwd" in p.stderr


def test_cli_spawn_argv_passes_cwd(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": SELF}}, [])
    p = run_cli(
        "spawn-argv",
        "--roster",
        str(roster_path),
        "--lane",
        "be",
        "--preset",
        "impl",
        "--name",
        "be-impl-1",
        "--task",
        "x",
        "--cwd",
        str(tmp_path),
        "--hc",
        str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 0, p.stderr
    argv = json.loads(p.stdout)
    assert argv[argv.index("--cwd") + 1] == str(tmp_path)


def _spawn(roster_path: Path, labels: dict[str, str], lane: str = "be") -> list[str]:
    return spawn_argv(
        worker(roster_path, "impl"),
        lane,
        "be-impl-1",
        "x",
        labels,
        None,
        role="impl",
        cwd=CWD,
    )


@pytest.mark.parametrize(
    "labels",
    [
        {L: "fe", R: "hub", "herdr.space": "sp1"},
        {L: "be", R: "impl", "herdr.space": "sp1"},
        {R: "hub", "herdr.space": "sp1"},
        {L: "be", "herdr.space": "sp1"},
        {},
    ],
    ids=["other-lane", "not-hub", "no-lane", "no-role", "no-labels"],
)
def test_spawn_argv_requires_own_lane_hub(
    roster_path: Path, labels: dict[str, str]
) -> None:
    with pytest.raises(SpawnError, match=r"hc-hub start|自分のレーン"):
        _spawn(roster_path, labels)


def test_spawn_argv_reserves_hub_role(roster_path: Path) -> None:
    with pytest.raises(SpawnError, match="hub"):
        spawn_argv(
            worker(roster_path, "impl"),
            "be",
            "be-impl-1",
            "x",
            SELF,
            None,
            role="hub",
            cwd=CWD,
        )


def test_spawn_argv_template_puts_task_after_separator(roster_path: Path) -> None:
    a = spawn_argv(
        worker(roster_path, "advisor"),
        "be",
        "be-adv-1",
        "-x を調べて",
        SELF,
        None,
        role="advisor",
        cwd=CWD,
    )
    assert a[-3:] == ["--", "advisor", "-x を調べて"]


def test_cli_spawn_argv_refuses_non_hub_self(tmp_path: Path, roster_path: Path) -> None:
    hc = make_fake_hc(tmp_path, {"t5": {"labels": {L: "be", R: "impl"}}}, [])
    p = run_cli(
        "spawn-argv", "--roster", str(roster_path), "--lane", "be",
        "--preset", "impl", "--name", "be-impl-1", "--task", "x",
        "--cwd", str(tmp_path), "--hc", str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )  # fmt: skip
    assert p.returncode == 2
    assert p.stdout == ""


def test_find_tab_returns_tab_holding_address() -> None:
    payload = herdr_ls(("tA", ["t5"]), ("tB", ["t90", "t91"]))
    assert find_tab(payload, "t90") == "tB"
    assert find_tab(payload, "t99") is None


def test_find_tab_rejects_address_in_two_tabs() -> None:
    with pytest.raises(SpawnError, match="2 つ以上"):
        find_tab(herdr_ls(("tA", ["t90"]), ("tB", ["t90"])), "t90")


def test_find_tab_rejects_malformed_payload() -> None:
    with pytest.raises(SpawnError, match="spaces"):
        find_tab({"spaces": "x"}, "t90")


def _spawn_cli(  # noqa: PLR0913
    tmp_path: Path,
    roster_path: Path,
    *args: str,
    labels: dict[str, str] | None = None,
    herdr: list[dict[str, object]] | None = None,
    rename_fails: bool = False,
    run_response: str | None = None,
) -> subprocess.CompletedProcess[str]:
    hc = make_fake_hc(
        tmp_path,
        {"t5": {"labels": SELF if labels is None else labels}},
        [],
        run_response=run_response,
    )
    app = make_fake_herdr_app(
        tmp_path,
        herdr if herdr is not None else [herdr_ls(("tA", ["t5"]), ("tB", ["t90"]))],
        rename_fails=rename_fails,
    )
    return run_cli(
        "spawn", "--roster", str(roster_path), "--lane", "be",
        "--name", "be-impl-01", "--cwd", str(tmp_path), "--task", "依頼です",
        "--hc", str(hc), "--herdr-app", str(app), *args,
        env_extra={"HC_TERMINAL_ID": "t5"},
    )  # fmt: skip


def test_cli_spawn_runs_hc_and_renames_tab(tmp_path: Path, roster_path: Path) -> None:
    later = [
        herdr_ls(("tA", ["t5"])),
        herdr_ls(("tA", ["t5"]), ("tB", ["t90"])),
    ]
    p = _spawn_cli(tmp_path, roster_path, "--preset", "impl", herdr=later)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == {
        "address": "t90",
        "name": "be-impl-01",
        "tab": "tB",
        "command": ["claude"],
        "template": None,
    }
    run_log = (tmp_path / "run.log").read_text()
    assert "--outlive-parent" in run_log
    assert "-- claude 依頼です" in run_log
    assert (tmp_path / "rename.log").read_text() == "--id tB --name be-impl-01\n"


def test_cli_spawn_hidden_does_not_touch_tabs(
    tmp_path: Path, roster_path: Path
) -> None:
    p = _spawn_cli(tmp_path, roster_path, "--preset", "quiet")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["tab"] is None
    assert not (tmp_path / "herdr-ls.count").exists()
    assert not (tmp_path / "rename.log").exists()


def test_cli_spawn_template_reports_template(tmp_path: Path, roster_path: Path) -> None:
    p = _spawn_cli(tmp_path, roster_path, "--preset", "advisor")
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["command"] is None
    assert out["template"] == "advisor"


def test_cli_spawn_cleans_up_when_tab_never_appears(
    tmp_path: Path, roster_path: Path
) -> None:
    p = _spawn_cli(
        tmp_path, roster_path, "--preset", "impl", herdr=[herdr_ls(("tA", ["t5"]))]
    )
    assert p.returncode == 2
    assert "t90" in p.stderr
    assert (tmp_path / "kill.log").read_text() == "t90\n"
    assert (tmp_path / "rm.log").read_text() == "t90\n"


def test_cli_spawn_cleans_up_when_rename_fails(
    tmp_path: Path, roster_path: Path
) -> None:
    p = _spawn_cli(tmp_path, roster_path, "--preset", "impl", rename_fails=True)
    assert p.returncode == 2
    assert (tmp_path / "kill.log").read_text() == "t90\n"
    assert (tmp_path / "rm.log").read_text() == "t90\n"


def test_cli_spawn_names_worker_when_response_has_no_address(
    tmp_path: Path, roster_path: Path
) -> None:
    p = _spawn_cli(tmp_path, roster_path, "--preset", "impl", run_response="{}")
    assert p.returncode == 2
    assert "be-impl-01" in p.stderr
    assert not (tmp_path / "rename.log").exists()


def test_cli_spawn_refuses_non_hub(tmp_path: Path, roster_path: Path) -> None:
    p = _spawn_cli(tmp_path, roster_path, "--preset", "impl", labels={})
    assert p.returncode == 2
    assert not (tmp_path / "run.log").exists()


SID = "b71bdc82-85b1-4c3d-b407-99c4e151669d"


def _start(roster_path: Path, hc: Path) -> "subprocess.CompletedProcess[str]":
    return run_cli(
        "start",
        "--roster", str(roster_path),
        "--lane", "be",
        "--hc", str(hc),
        env_extra={"HC_TERMINAL_ID": "t5"},
    )  # fmt: skip


def test_cli_start_refuses_in_worker_terminal(
    tmp_path: Path, roster_path: Path
) -> None:
    labels = {"hc-hub.lane": "be", "hc-hub.role": "impl"}
    hc = make_fake_hc(tmp_path, {"t5": {"labels": labels}}, [])
    p = _start(roster_path, hc)
    assert p.returncode == 2
    assert "worker の端末" in p.stderr
    assert not (tmp_path / "label.log").exists()


def test_cli_start_refuses_when_own_session_is_elsewhere(
    tmp_path: Path, roster_path: Path
) -> None:
    mine = {"claude.session": SID}
    hc = make_fake_hc(
        tmp_path,
        {
            "t5": {"address": "t5", "state": "live", "labels": mine},
            "t1": {"address": "t1", "state": "live", "labels": mine},
        },
        [{"address": "t5"}, {"address": "t1"}],
    )
    p = _start(roster_path, hc)
    assert p.returncode == 2
    assert "t1" in p.stderr
    assert not (tmp_path / "label.log").exists()
