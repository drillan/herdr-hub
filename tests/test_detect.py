import subprocess
from pathlib import Path

from fake_hc import make_fake_hc, run_cli
from hc_hub_lib.catalog import KNOWN_AGENTS
from hc_hub_lib.detect import classify, detect_report


def test_classify_alias_output() -> None:
    assert classify(False, "alias claude=~/.claude/local/claude") == "shell_alias"  # noqa: FBT003


def test_classify_table() -> None:
    assert classify(True, "") == "available"  # noqa: FBT003
    assert classify(False, "/x/opencode") == "shell_only"  # noqa: FBT003
    assert classify(False, "") == "missing"  # noqa: FBT003


def test_report_fix_is_quoted() -> None:
    core = {a.executable: True for a in KNOWN_AGENTS}
    shell = {a.executable: "" for a in KNOWN_AGENTS}
    core["opencode"] = False
    shell["opencode"] = "/a b/opencode"
    report = detect_report(core, shell, Path("/bin/zsh"))
    assert report["login_shell"] == "/bin/zsh"
    by_name = {a["name"]: a for a in report["agents"]}
    assert by_name["opencode"]["verdict"] == "shell_only"
    assert "'/a b'" in by_name["opencode"]["fix"]
    assert by_name["claude"]["verdict"] == "available"
    assert by_name["claude"]["fix"] is None
    assert by_name["opencode"]["argv"] == ["opencode", "--prompt"]


def test_detect_cli_rejects_worker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S607
    fake = make_fake_hc(tmp_path, {"t7": {"labels": {"hc-hub.role": "worker"}}}, [])
    result = run_cli(
        "detect", "--hc", str(fake), env_extra={"HC_TERMINAL_ID": "t7"}, cwd=repo
    )
    assert result.returncode == 2
    assert result.stderr.startswith("hc-hub: ")
