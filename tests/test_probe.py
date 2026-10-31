import stat
from pathlib import Path
from typing import Any

import pytest
from fake_hc import make_fake_hc
from hc_hub_lib.probe import ProbeError, probe_core


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
