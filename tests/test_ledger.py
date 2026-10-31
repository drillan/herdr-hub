import json
import multiprocessing
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from _paths import SCRIPT
from fake_hc import make_fake_hc
from fake_hc import run_cli as fake_run_cli
from hc_hub_lib.ledger import LedgerError, LedgerEvent, append_event, read_events

EV = LedgerEvent(
    ts="2026-10-31T00:00:00+00:00",
    lane="be",
    name="w1",
    address="tab:1",
    event="spawn",
    hub="be-hub",
    preset="impl",
    command=("claude", "--x"),
    template=None,
    brief="やること",
)


def test_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    append_event(p, EV)
    append_event(p, replace(EV, event="stop", command=None, preset=None, brief=None))
    events = read_events(p)
    assert events[0] == EV
    assert events[1].event == "stop"
    assert events[1].command is None


def test_missing_file_reads_as_empty_and_first_append_creates(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    assert read_events(p) == []
    append_event(p, EV)
    assert p.exists()


def test_missing_parent_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(LedgerError):
        append_event(tmp_path / "no" / "l.jsonl", EV)


def test_corrupt_line_raises_with_line_number(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    append_event(p, EV)
    with p.open("a") as f:
        f.write("{broken\n")
    with pytest.raises(LedgerError, match="2"):
        read_events(p)


def _line(**edits: Any) -> str:  # noqa: ANN401
    data: dict[str, Any] = {
        "ts": "t",
        "lane": "be",
        "name": "w",
        "address": "a",
        "event": "spawn",
        "hub": "h",
        "preset": None,
        "command": ["c"],
        "template": None,
        "brief": None,
    }
    data.update(edits)
    return json.dumps(data) + "\n"


@pytest.mark.parametrize(
    "line",
    [
        _line(event="start"),
        _line(lane=1),
        _line(command="claude"),
        _line(command=[1]),
        _line(preset=3),
        "[]\n",
        "\n",
    ],
)
def test_invalid_line_raises(tmp_path: Path, line: str) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(line)
    with pytest.raises(LedgerError, match="1"):
        read_events(p)


def test_missing_key_raises(tmp_path: Path) -> None:
    data = json.loads(_line())
    del data["hub"]
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(data) + "\n")
    with pytest.raises(LedgerError, match="hub"):
        read_events(p)


def test_unreadable_path_raises(tmp_path: Path) -> None:
    with pytest.raises(LedgerError):
        read_events(tmp_path)


def test_append_is_single_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bytes] = []
    real = os.write

    def counting(fd: int, data: bytes) -> int:
        calls.append(bytes(data))
        return real(fd, data)

    monkeypatch.setattr(os, "write", counting)
    append_event(tmp_path / "l.jsonl", EV)
    assert len(calls) == 1
    assert calls[0].endswith(b"\n")


def test_short_write_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "write", lambda _fd, data: len(data) - 1)
    with pytest.raises(LedgerError):
        append_event(tmp_path / "l.jsonl", EV)


def _worker(path: str, tag: str) -> None:
    for i in range(200):
        append_event(Path(path), replace(EV, name=f"{tag}{i}", brief="あ" * 500))


def test_concurrent_appends_do_not_interleave(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    procs = [
        multiprocessing.Process(target=_worker, args=(str(p), tag)) for tag in "ab"
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
        assert proc.exitcode == 0
    assert len(read_events(p)) == 400


HUB_LABELS = {"hc-hub.lane": "be", "hc-hub.role": "hub"}


def _roster(directory: Path) -> Path:
    path = directory / ".hc-hub.yml"
    cfg = {
        "ledger": "ledger.jsonl",
        "defaults": {"approval": "auto"},
        "presets": {"impl": {"role": "実装", "command": ["claude"]}},
        "lanes": {"be": {}, "fe": {}},
    }
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _append_cli(
    roster: Path,
    labels: dict[str, str] | None,
    overrides: dict[str, str],
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    hc = make_fake_hc(
        roster.parent, {} if labels is None else {"t5": {"labels": labels}}, []
    )
    values = {
        "--lane": "be",
        "--name": "w",
        "--address": "tab:1",
        "--event": "spawn",
        "--hub": "h",
        "--command-json": '["claude"]',
    }
    values.update(overrides)
    flat = [x for pair in values.items() for x in pair]
    return fake_run_cli(
        "ledger", "append", "--roster", str(roster), "--hc", str(hc), *flat, *extra,
        env_extra={"HC_TERMINAL_ID": "t5"},
    )  # fmt: skip


def _append(roster: Path, lane: str, name: str, *extra: str) -> None:
    labels = {"hc-hub.lane": lane, "hc-hub.role": "hub"}
    hc = make_fake_hc(roster.parent, {"t5": {"labels": labels}}, [])
    p = fake_run_cli(
        "ledger", "append", "--roster", str(roster), "--hc", str(hc),
        "--lane", lane, "--name", name, "--address", "tab:1",
        "--event", "spawn", "--hub", "h", *extra,
        env_extra={"HC_TERMINAL_ID": "t5"},
    )  # fmt: skip
    assert p.returncode == 0, p.stderr


def test_cli_append_and_list(tmp_path: Path) -> None:
    roster = _roster(tmp_path)
    _append(roster, "be", "w1", "--command-json", '["claude","-x"]', "--brief", "b")
    _append(roster, "fe", "w2", "--template", "t")
    p = run_cli("ledger", "list", "--roster", str(roster), "--lane", "be")
    rows = json.loads(p.stdout)
    assert [r["name"] for r in rows] == ["w1"]
    assert rows[0]["command"] == ["claude", "-x"]
    assert rows[0]["ts"].endswith("+00:00")
    p = run_cli("ledger", "list", "--roster", str(roster))
    assert len(json.loads(p.stdout)) == 2


def test_cli_list_without_ledger_file_is_empty(tmp_path: Path) -> None:
    p = run_cli("ledger", "list", "--roster", str(_roster(tmp_path)))
    assert json.loads(p.stdout) == []


def test_cli_append_rejects_bad_command_json(tmp_path: Path) -> None:
    p = _append_cli(_roster(tmp_path), HUB_LABELS, {"--command-json": "{x"})
    assert p.returncode == 2
    assert "command-json" in p.stderr


def test_cli_append_unknown_lane_fails(tmp_path: Path) -> None:
    p = _append_cli(
        _roster(tmp_path), {**HUB_LABELS, "hc-hub.lane": "zz"}, {"--lane": "zz"}
    )
    assert p.returncode == 2


@pytest.mark.parametrize(
    "labels",
    [
        {"hc-hub.lane": "fe", "hc-hub.role": "hub"},
        {"hc-hub.lane": "be", "hc-hub.role": "impl"},
        {"hc-hub.role": "hub"},
        {},
        None,
    ],
    ids=["other-lane", "not-hub", "no-lane", "no-labels", "unreadable-self"],
)
def test_cli_append_requires_own_lane_hub(
    tmp_path: Path, labels: dict[str, str] | None
) -> None:
    roster = _roster(tmp_path)
    p = _append_cli(roster, labels, {})
    assert p.returncode == 2
    assert not (tmp_path / "ledger.jsonl").exists()


@pytest.mark.parametrize("flag", ["--name", "--address", "--hub"])
def test_cli_append_rejects_empty_strings(tmp_path: Path, flag: str) -> None:
    p = _append_cli(_roster(tmp_path), HUB_LABELS, {flag: ""})
    assert p.returncode == 2
    assert flag in p.stderr
    assert not (tmp_path / "ledger.jsonl").exists()


@pytest.mark.parametrize("raw", ["[]", '[""]', "[1]", '"claude"', "{}"])
def test_cli_append_rejects_bad_command_list(tmp_path: Path, raw: str) -> None:
    p = _append_cli(_roster(tmp_path), HUB_LABELS, {"--command-json": raw})
    assert p.returncode == 2
    assert "command-json" in p.stderr


def test_cli_append_preset_must_be_defined(tmp_path: Path) -> None:
    roster = _roster(tmp_path)
    p = _append_cli(roster, HUB_LABELS, {}, "--preset", "nope")
    assert p.returncode == 2
    assert "nope" in p.stderr
    p = _append_cli(roster, HUB_LABELS, {}, "--preset", "impl")
    assert p.returncode == 0, p.stderr


def test_cli_list_corrupt_ledger_exits_2(tmp_path: Path) -> None:
    roster = _roster(tmp_path)
    (tmp_path / "ledger.jsonl").write_text("{broken\n")
    p = run_cli("ledger", "list", "--roster", str(roster))
    assert p.returncode == 2
    assert "1" in p.stderr


@pytest.mark.parametrize(
    "sep", ["\u2028", "\u2029", "\u0085", "\u000c", "\u001c", "\r"]
)
def test_unicode_line_separators_in_brief_roundtrip(tmp_path: Path, sep: str) -> None:
    p = tmp_path / "l.jsonl"
    ev = replace(EV, brief=f"a{sep}b")
    append_event(p, ev)
    append_event(p, EV)
    assert read_events(p) == [ev, EV]


def test_empty_line_in_middle_raises_with_line_number(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(_line() + "\n" + _line())
    with pytest.raises(LedgerError, match="2"):
        read_events(p)


def test_empty_file_reads_as_empty(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text("")
    assert read_events(p) == []


def test_extra_key_raises_with_line_number(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(_line() + _line(extra=1))
    with pytest.raises(LedgerError, match="2"):
        read_events(p)


BOTH = {"command": ["c"], "template": "t"}


def test_event_rejects_command_and_template_together() -> None:
    with pytest.raises(LedgerError):
        replace(EV, command=("c",), template="t")


def test_spawn_requires_command_or_template() -> None:
    with pytest.raises(LedgerError):
        replace(EV, command=None, template=None)


def test_non_spawn_may_have_neither(tmp_path: Path) -> None:
    ev = replace(EV, event="adopt", command=None, template=None)
    append_event(tmp_path / "l.jsonl", ev)
    assert read_events(tmp_path / "l.jsonl") == [ev]


@pytest.mark.parametrize(
    "line",
    [
        _line(**BOTH),
        _line(event="stop", **BOTH),
        _line(command=None, template=None),
    ],
)
def test_read_rejects_launch_rule_violations(tmp_path: Path, line: str) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(line)
    with pytest.raises(LedgerError, match="1"):
        read_events(p)
