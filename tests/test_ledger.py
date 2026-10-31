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
        "command": None,
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


def _roster(directory: Path) -> Path:
    path = directory / ".hc-hub.yml"
    cfg = {
        "ledger": "ledger.jsonl",
        "defaults": {"approval": "auto"},
        "lanes": {"be": {}, "fe": {}},
    }
    path.write_text(yaml.safe_dump(cfg))
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _append(roster: Path, lane: str, name: str, *extra: str) -> None:
    p = run_cli(
        "ledger", "append", "--roster", str(roster), "--lane", lane,
        "--name", name, "--address", "tab:1", "--event", "spawn",
        "--hub", "h", *extra,
    )  # fmt: skip
    assert p.returncode == 0, p.stderr


def test_cli_append_and_list(tmp_path: Path) -> None:
    roster = _roster(tmp_path)
    _append(roster, "be", "w1", "--command-json", '["claude","-x"]', "--brief", "b")
    _append(roster, "fe", "w2")
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
    p = run_cli(
        "ledger", "append", "--roster", str(_roster(tmp_path)), "--lane", "be",
        "--name", "w", "--address", "a", "--event", "spawn", "--hub", "h",
        "--command-json", "{x",
    )  # fmt: skip
    assert p.returncode == 2
    assert "command-json" in p.stderr


def test_cli_append_unknown_lane_fails(tmp_path: Path) -> None:
    p = run_cli(
        "ledger", "append", "--roster", str(_roster(tmp_path)), "--lane", "zz",
        "--name", "w", "--address", "a", "--event", "spawn", "--hub", "h",
    )  # fmt: skip
    assert p.returncode == 2


def test_cli_list_corrupt_ledger_exits_2(tmp_path: Path) -> None:
    roster = _roster(tmp_path)
    (tmp_path / "ledger.jsonl").write_text("{broken\n")
    p = run_cli("ledger", "list", "--roster", str(roster))
    assert p.returncode == 2
    assert "1" in p.stderr
