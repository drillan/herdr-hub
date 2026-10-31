import subprocess

from _paths import ROOT, SCRIPT


def _run(*cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", *cmd],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )


def test_cli_entry_is_checked_by_ruff() -> None:
    listed = _run("ruff", "check", "--show-files", ".")
    assert str(SCRIPT) in listed.stdout
    assert _run("ruff", "check", str(SCRIPT)).returncode == 0


def test_cli_entry_passes_mypy() -> None:
    # 拡張子が無く `mypy .` の探索に掛からないため、明示して検査する
    p = _run("mypy", str(SCRIPT))
    assert p.returncode == 0, p.stdout
