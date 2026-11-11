import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from _paths import ROOT

SCRIPT = ROOT / "skills/hc-session/scripts/hc-session"
SID = "cbbd6be8-6a2e-4731-a8dc-199cb980fc29"
SID2 = "b71bdc82-85b1-4c3d-b407-99c4e151669d"
BTIME = 1_794_365_000  # 起動時刻（epoch 秒）
TCK = os.sysconf("SC_CLK_TCK")

_FAKE_HC = """#!{python}
import json
import sys
from pathlib import Path

TERMINALS = json.loads({terminals!r})
DIR = Path({directory!r})
ARGS = sys.argv[1:]

def log(name):
    with (DIR / name).open("a") as f:
        f.write(json.dumps(ARGS[1:]) + "\\n")

if ARGS[:1] == ["get"] and ARGS[1] in TERMINALS:
    print(json.dumps(TERMINALS[ARGS[1]]))
elif ARGS[:1] == ["ls"]:
    rows = [{{"address": a, "state": t["state"]}} for a, t in TERMINALS.items()]
    print(json.dumps({{"terminals": rows}}))
elif ARGS[:1] == ["label"]:
    log("label.log")
    print("{{}}")
elif ARGS[:1] == ["send"]:
    log("send.log")
    print("{{}}")
else:
    print(json.dumps({{"error": {{"message": "fake: " + " ".join(ARGS)}}}}))
    sys.exit(3)
"""


def _fake_hc(tmp_path: Path, terminals: dict[str, dict[str, Any]]) -> Path:
    script = tmp_path / "fake-hc"
    script.write_text(
        _FAKE_HC.format(
            python=sys.executable,
            terminals=json.dumps(terminals),
            directory=str(tmp_path),
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _proc_entry(proc: Path, name: str, comm: str, ppid: int, start_s: float) -> None:
    ticks = round((start_s - BTIME) * TCK)
    # comm に空白と括弧を含めても、最後の ')' の後ろから数える
    fields = ["S", str(ppid), *["0"] * 17, str(ticks), "0"]
    d = proc / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "stat").write_text(f"{name} ({comm}) " + " ".join(fields) + "\n")
    (d / "comm").write_text(comm + "\n")


def _proc(tmp_path: Path) -> Path:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "stat").write_text(f"cpu 1 2 3\nbtime {BTIME}\nprocesses 9\n")
    return proc


def _run(
    hc: Path, proc: Path, *args: str, stdin: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k != "HC_TERMINAL_ID"}
    base.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--hc", str(hc), "--proc", str(proc), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=base,
    )


def _log(tmp_path: Path, name: str) -> list[list[str]]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines()]


# --- record ---


def _hook_input(tmp_path: Path) -> str:
    return json.dumps(
        {
            "session_id": SID,
            "transcript_path": str(tmp_path / f"{SID}.jsonl"),
            "cwd": "/home/u/repo/app",
            "hook_event_name": "SessionStart",
            "source": "startup",
        }
    )


def _record_tree(tmp_path: Path, *, foreground: int) -> tuple[Path, Path]:
    proc = _proc(tmp_path)
    # self(900, uv の子の python) → 800 sh → 700 claude → 600 fish
    _proc_entry(proc, "self", "python3", 800, BTIME + 50)
    _proc_entry(proc, "800", "sh", 700, BTIME + 50)
    _proc_entry(proc, "700", "claude", 600, BTIME + 40)
    _proc_entry(proc, "600", "fish", 1, BTIME + 10)
    hc = _fake_hc(
        tmp_path,
        {"t5": {"state": "live", "pid": 600, "foreground": {"pid": foreground}}},
    )
    return hc, proc


def test_record_labels_own_terminal_with_session(tmp_path: Path) -> None:
    hc, proc = _record_tree(tmp_path, foreground=700)
    p = _run(
        hc, proc, "record", stdin=_hook_input(tmp_path), env={"HC_TERMINAL_ID": "t5"}
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout == ""
    [args] = _log(tmp_path, "label.log")
    assert args[0] == "t5"
    labels = dict(a.split("=", 1) for a in args[1:])
    assert labels["claude.session"] == SID
    assert labels["claude.cwd"] == "/home/u/repo/app"
    assert labels["claude.transcript"] == str(tmp_path / f"{SID}.jsonl")
    assert int(labels["claude.at"]) > 0


def test_record_outside_hc_does_nothing(tmp_path: Path) -> None:
    hc, proc = _record_tree(tmp_path, foreground=700)
    p = _run(hc, proc, "record", stdin=_hook_input(tmp_path))
    assert p.returncode == 0
    assert p.stdout == ""
    assert _log(tmp_path, "label.log") == []


def test_record_skips_claude_that_is_not_terminal_foreground(tmp_path: Path) -> None:
    # 前面の Claude（500）が子として起こした claude -p（700）の hook
    hc, proc = _record_tree(tmp_path, foreground=500)
    p = _run(
        hc, proc, "record", stdin=_hook_input(tmp_path), env={"HC_TERMINAL_ID": "t5"}
    )
    assert p.returncode == 0
    assert p.stdout == ""
    assert _log(tmp_path, "label.log") == []


def test_record_fails_without_claude_ancestor(tmp_path: Path) -> None:
    proc = _proc(tmp_path)
    _proc_entry(proc, "self", "python3", 800, BTIME + 50)
    _proc_entry(proc, "800", "sh", 1, BTIME + 50)
    hc = _fake_hc(
        tmp_path, {"t5": {"state": "live", "pid": 800, "foreground": {"pid": 800}}}
    )
    p = _run(
        hc, proc, "record", stdin=_hook_input(tmp_path), env={"HC_TERMINAL_ID": "t5"}
    )
    assert p.returncode == 1
    assert "claude" in p.stderr
    assert p.stdout == ""


def test_record_fails_on_missing_input_key(tmp_path: Path) -> None:
    hc, proc = _record_tree(tmp_path, foreground=700)
    p = _run(
        hc,
        proc,
        "record",
        stdin=json.dumps({"session_id": SID}),
        env={"HC_TERMINAL_ID": "t5"},
    )
    assert p.returncode == 1
    assert "transcript_path" in p.stderr
    assert _log(tmp_path, "label.log") == []


# --- status / restore ---


def _labels(
    tmp_path: Path, sid: str, at_s: float, *, transcript: bool = True
) -> dict[str, str]:
    path = tmp_path / f"{sid}.jsonl"
    if transcript:
        path.write_text("{}\n")
    return {
        "claude.session": sid,
        "claude.cwd": "/home/u/my repo",
        "claude.transcript": str(path),
        "claude.at": str(int(at_s * 1000)),
    }


def _term(
    pid: int, fg: int, labels: dict[str, str], state: str = "live"
) -> dict[str, Any]:
    return {"state": state, "pid": pid, "foreground": {"pid": fg}, "labels": labels}


def _restore_world(tmp_path: Path) -> tuple[Path, Path]:
    proc = _proc(tmp_path)
    _proc_entry(proc, "10", "fish", 1, BTIME + 30)  # 再起動後の回復シェル
    _proc_entry(proc, "11", "fish", 1, BTIME - 500)  # Claude より前からあるシェル
    hc = _fake_hc(
        tmp_path,
        {
            "t1": _term(10, 10, _labels(tmp_path, SID, BTIME - 100)),
            "t2": _term(11, 11, _labels(tmp_path, SID2, BTIME - 100)),
            "t3": _term(12, 13, _labels(tmp_path, SID, BTIME + 60)),
            "t4": _term(14, 14, {}),
            "t6": _term(15, 15, _labels(tmp_path, SID, BTIME - 100), state="finished"),
        },
    )
    return hc, proc


def test_status_classifies_terminals(tmp_path: Path) -> None:
    hc, proc = _restore_world(tmp_path)
    p = _run(hc, proc, "status")
    assert p.returncode == 0, p.stderr
    lines = p.stdout.splitlines()
    assert any(line.startswith("[restore] t1 ") and SID in line for line in lines)
    assert any(line.startswith("[exited] t2 ") for line in lines)
    assert any(line.startswith("[running] t3 ") for line in lines)
    assert not any(" t4 " in line or " t6 " in line for line in lines)
    assert _log(tmp_path, "send.log") == []


def test_restore_sends_resume_only_to_restorable(tmp_path: Path) -> None:
    hc, proc = _restore_world(tmp_path)
    p = _run(hc, proc, "restore")
    assert p.returncode == 0, p.stderr
    assert _log(tmp_path, "send.log") == [
        ["t1", f"cd '/home/u/my repo' && claude --resume {SID}"]
    ]


def test_restore_dry_run_sends_nothing(tmp_path: Path) -> None:
    hc, proc = _restore_world(tmp_path)
    p = _run(hc, proc, "restore", "--dry-run")
    assert p.returncode == 0, p.stderr
    assert f"claude --resume {SID}" in p.stdout
    assert _log(tmp_path, "send.log") == []


def test_restore_named_terminal_that_is_not_restorable_fails(tmp_path: Path) -> None:
    hc, proc = _restore_world(tmp_path)
    p = _run(hc, proc, "restore", "t2")
    assert p.returncode == 1
    assert "t2" in p.stderr
    assert _log(tmp_path, "send.log") == []


def test_restore_skips_missing_transcript_and_fails(tmp_path: Path) -> None:
    proc = _proc(tmp_path)
    _proc_entry(proc, "10", "fish", 1, BTIME + 30)
    _proc_entry(proc, "20", "fish", 1, BTIME + 30)
    hc = _fake_hc(
        tmp_path,
        {
            "t1": _term(10, 10, _labels(tmp_path, SID, BTIME - 100)),
            "t7": _term(20, 20, _labels(tmp_path, SID2, BTIME - 100, transcript=False)),
        },
    )
    p = _run(hc, proc, "restore")
    assert p.returncode == 1
    assert "[missing] t7" in p.stdout
    assert [a[0] for a in _log(tmp_path, "send.log")] == ["t1"]


def test_invalid_labels_fail_status(tmp_path: Path) -> None:
    proc = _proc(tmp_path)
    _proc_entry(proc, "10", "fish", 1, BTIME + 30)
    bad = _labels(tmp_path, SID, BTIME - 100) | {"claude.session": "x; rm -rf ~"}
    hc = _fake_hc(tmp_path, {"t1": _term(10, 10, bad)})
    p = _run(hc, proc, "status")
    assert p.returncode == 1
    assert "[invalid] t1" in p.stdout
    p = _run(hc, proc, "restore")
    assert p.returncode == 1
    assert _log(tmp_path, "send.log") == []


def test_unknown_foreground_is_reported_without_stopping_others(tmp_path: Path) -> None:
    # 起動直後の端末は foreground.pid が null のことがある（2026-11-11 に実測）
    proc = _proc(tmp_path)
    _proc_entry(proc, "10", "fish", 1, BTIME + 30)
    hc = _fake_hc(
        tmp_path,
        {
            "t1": _term(10, 10, _labels(tmp_path, SID, BTIME - 100)),
            "t8": {
                "state": "live",
                "pid": 30,
                "foreground": None,
                "labels": _labels(tmp_path, SID2, BTIME - 100),
            },
        },
    )
    p = _run(hc, proc, "status")
    assert p.returncode == 1
    assert "[unknown] t8" in p.stdout
    assert "[restore] t1" in p.stdout
    p = _run(hc, proc, "restore")
    assert p.returncode == 1
    assert [a[0] for a in _log(tmp_path, "send.log")] == ["t1"]


def test_claude_as_terminal_root_program_is_running(tmp_path: Path) -> None:
    # hc-hub spawn の worker は端末の最初のプロセスが claude そのもの（2026-11-11 実測）
    proc = _proc(tmp_path)
    _proc_entry(proc, "40", "claude", 1, BTIME + 30)
    _proc_entry(proc, "41", "claude", 1, BTIME - 500)
    hc = _fake_hc(
        tmp_path,
        {
            "t9": _term(40, 40, _labels(tmp_path, SID, BTIME - 100)),
            "t10": _term(41, 41, _labels(tmp_path, SID2, BTIME - 100)),
        },
    )
    p = _run(hc, proc, "status")
    assert p.returncode == 0, p.stderr
    assert "[running] t9 " in p.stdout
    assert "[running] t10 " in p.stdout
    p = _run(hc, proc, "restore")
    assert p.returncode == 0
    assert _log(tmp_path, "send.log") == []
