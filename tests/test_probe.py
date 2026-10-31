import os
import pwd
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fake_hc import make_fake_hc
from hc_hub_lib.probe import ProbeError, login_shell, probe_core, probe_shell


def _fake(tmp_path: Path, **kwargs: Any) -> str:  # noqa: ANN401
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in ("claude", "devin"):
        exe = bindir / name
        exe.write_text("")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return str(make_fake_hc(tmp_path, {}, [], probe_path=str(bindir), **kwargs))


def test_probe_core_reports_found_and_missing(tmp_path: Path) -> None:
    fake = _fake(tmp_path)
    result = probe_core(fake, ["claude", "opencode", "devin"], tmp_path)
    assert result == {"claude": True, "opencode": False, "devin": True}
    run_log = (tmp_path / "run.log").read_text()
    assert "--no-parent" in run_log
    assert "--label hc-hub.role=probe" in run_log
    assert "--rm" not in run_log
    assert "t90" in (tmp_path / "rm.log").read_text()


def test_probe_core_timeout_still_removes(tmp_path: Path) -> None:
    fake = _fake(
        tmp_path,
        wait_override={"ended": False, "reason": "timeout", "exit_code": None},
    )
    with pytest.raises(ProbeError):
        probe_core(fake, ["claude"], tmp_path)
    assert "t90" in (tmp_path / "rm.log").read_text()


def test_probe_core_nonzero_exit_is_error(tmp_path: Path) -> None:
    fake = _fake(
        tmp_path,
        wait_override={"ended": True, "reason": "exit", "exit_code": 2},
    )
    with pytest.raises(ProbeError):
        probe_core(fake, ["claude"], tmp_path)


def test_probe_core_rejects_missing_line(tmp_path: Path) -> None:
    fake = _fake(tmp_path, read_override="garbage\n")
    with pytest.raises(ProbeError):
        probe_core(fake, ["claude"], tmp_path)


def test_probe_core_rm_failure_is_error(tmp_path: Path) -> None:
    fake = _fake(tmp_path, rm_fails=True)
    with pytest.raises(ProbeError, match="t90"):
        probe_core(fake, ["claude"], tmp_path)


def test_script_checks_names_one_by_one(tmp_path: Path) -> None:
    fake = _fake(tmp_path)
    probe_core(fake, ["claude", "opencode", "devin"], tmp_path)
    script = (tmp_path / "script.sh").read_text()
    assert script.count("command -v") == 3


def test_probe_core_removes_on_unexpected_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object) -> dict[str, bool]:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr("hc_hub_lib.probe._parse", boom)
    fake = _fake(tmp_path)
    with pytest.raises(RuntimeError, match="boom"):
        probe_core(fake, ["claude"], tmp_path)
    assert "t90" in (tmp_path / "rm.log").read_text()


SH = Path("/bin/sh")


def _home(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "my bin").mkdir(exist_ok=True)
    exe = tmp_path / "my bin" / "claude"
    exe.write_text("")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return {"HOME": str(tmp_path), "PATH": f"{tmp_path}/my bin:/usr/bin:/bin"}


def test_probe_shell_reads_paths_with_spaces(tmp_path: Path) -> None:
    env = _home(tmp_path)
    result = probe_shell(SH, ["claude", "pi"], env)
    assert result == {"claude": f"{tmp_path}/my bin/claude", "pi": ""}


def test_probe_shell_ignores_noise_from_profile(tmp_path: Path) -> None:
    env = _home(tmp_path)
    (tmp_path / ".profile").write_text('echo hello; echo "x claude /fake"\n')
    result = probe_shell(SH, ["claude", "pi"], env)
    assert result == {"claude": f"{tmp_path}/my bin/claude", "pi": ""}


def test_probe_shell_nonzero_is_error(tmp_path: Path) -> None:
    env = _home(tmp_path)
    (tmp_path / ".profile").write_text("exit 5\n")
    with pytest.raises(ProbeError):
        probe_shell(SH, ["claude"], env)


def test_probe_shell_rejects_bad_names(tmp_path: Path) -> None:
    with pytest.raises(ProbeError):
        probe_shell(SH, ["a b"], _home(tmp_path))
    with pytest.raises(ProbeError):
        probe_shell(SH, ["pi", "pi"], _home(tmp_path))


def test_probe_shell_missing_shell_is_error(tmp_path: Path) -> None:
    with pytest.raises(ProbeError):
        probe_shell(tmp_path / "no-such-shell", ["pi"], _home(tmp_path))


def test_login_shell_rejects_fish(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = pwd.struct_passwd(("u", "x", 1, 1, "", "/home/u", "/usr/bin/fish"))
    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: entry)
    with pytest.raises(ProbeError, match="fish"):
        login_shell()


def test_login_shell_accepts_bash(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = pwd.struct_passwd(("u", "x", 1, 1, "", "/home/u", "/bin/bash"))
    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: entry)
    assert login_shell() == Path("/bin/bash")


def test_probe_shell_detaches_stdin_and_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    real_run = subprocess.run

    def spy(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        seen.update(kwargs)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    probe_shell(SH, ["pi"], _home(tmp_path))
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["start_new_session"] is True


def test_probe_shell_survives_profile_output_without_newline(tmp_path: Path) -> None:
    env = _home(tmp_path)
    (tmp_path / ".profile").write_text("printf 'no newline'\n")
    result = probe_shell(SH, ["claude", "pi"], env)
    assert result == {"claude": f"{tmp_path}/my bin/claude", "pi": ""}


def test_probe_core_names_probe_terminal_when_response_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hc_hub_lib.probe._hc", lambda *_a: "not json")
    with pytest.raises(ProbeError, match=f"hc-hub-probe-{os.getpid()}"):
        probe_core("hc", ["claude"], tmp_path)


def test_probe_core_names_probe_terminal_when_address_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hc_hub_lib.probe._hc", lambda *_a: "{}")
    with pytest.raises(ProbeError, match=f"hc-hub-probe-{os.getpid()}"):
        probe_core("hc", ["claude"], tmp_path)


def test_probe_core_accepts_absolute_path(tmp_path: Path) -> None:
    fake = _fake(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    exe = other / "opencode"
    exe.write_text("")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    result = probe_core(fake, [str(exe), str(other / "nope")], tmp_path)
    assert result == {str(exe): True, str(other / "nope"): False}


@pytest.mark.parametrize("bad", ["bin/opencode", "/a b/opencode", "/a;b"])
def test_probe_core_rejects_relative_or_unsafe_paths(tmp_path: Path, bad: str) -> None:
    fake = _fake(tmp_path)
    with pytest.raises(ProbeError, match="扱えない"):
        probe_core(fake, [bad], tmp_path)
