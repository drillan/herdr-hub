import json
import stat
import subprocess
from pathlib import Path

import pytest
from fake_hc import make_fake_hc, run_cli
from hc_hub_lib.init_roster import (
    InitError,
    build_roster,
    check_presets,
    parse_pairs,
    render_roster,
    write_exclusive,
)
from hc_hub_lib.roster import RosterError, load_roster, load_roster_text


def test_parse_pairs_splits_on_first_equals() -> None:
    assert parse_pairs(["impl=実装 a=b"], "--role") == {"impl": "実装 a=b"}


@pytest.mark.parametrize("values", [["impl"], ["=x"], ["a=1", "a=2"]])
def test_parse_pairs_rejects_duplicates_and_missing_equals(values: list[str]) -> None:
    with pytest.raises(InitError):
        parse_pairs(values, "--role")


def test_build_roster_shape() -> None:
    cfg = build_roster(
        "be",
        "manual",
        {"impl": "claude", "rev": "opencode"},
        {"impl": "実装", "rev": "review"},
    )
    assert cfg["presets"]["rev"]["command"] == ["opencode", "--prompt"]
    assert cfg["ledger"] == ".hc-hub/ledger.jsonl"
    assert cfg["lanes"] == {"be": {"agents": {}}}
    assert cfg["defaults"] == {"approval": "manual"}


def test_build_roster_rejects_mismatched_keys_and_blank_role() -> None:
    with pytest.raises(InitError):
        build_roster("be", "auto", {"a": "claude"}, {"b": "x"})
    with pytest.raises(InitError):
        build_roster("be", "auto", {"a": "claude"}, {"a": "  "})


def test_render_roster_keeps_yaml_special_roles(tmp_path: Path) -> None:
    roles = {"a": "true", "b": "# x", "c": "独立 review: 厳しめ"}
    cfg = build_roster("be", "auto", dict.fromkeys(roles, "claude"), roles)
    roster = load_roster_text(render_roster(cfg), tmp_path / ".hc-hub.yml")
    for name, role in roles.items():
        assert roster.raw["presets"][name]["role"] == role


def test_write_exclusive_refuses_dangling_symlink(tmp_path: Path) -> None:
    link = tmp_path / ".hc-hub.yml"
    link.symlink_to(tmp_path / "nowhere")
    with pytest.raises(InitError):
        write_exclusive(link, "x")
    assert not (tmp_path / "nowhere").exists()


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S607
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\n")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR)
    fake = make_fake_hc(tmp_path, {"t7": {"labels": {}}}, [], probe_path=str(bindir))
    return repo, fake


def _init(repo: Path, fake: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "init",
        "--hc",
        str(fake),
        *args,
        env_extra={"HC_TERMINAL_ID": "t7"},
        cwd=repo,
    )


def test_init_writes_roster_and_gitignore(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "impl=claude", "--role", "impl=実装",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    load_roster(repo / ".hc-hub.yml")
    assert "/.hc-hub/" in (repo / ".gitignore").read_text()
    out = json.loads(result.stdout)
    assert out["gitignore_appended"] is True
    assert out["roster"] == str(repo / ".hc-hub.yml")
    assert out["next"] == ".gitignore と .hc-hub.yml を commit する。"


def test_init_rejects_blank_role(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "impl=claude", "--role", "impl=  ",
    )  # fmt: skip
    assert result.returncode == 2
    assert not (repo / ".hc-hub.yml").exists()
    assert not (repo / ".gitignore").exists()


def test_init_refuses_existing_roster(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    (repo / ".hc-hub.yml").write_text("keep\n")
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "impl=claude", "--role", "impl=実装",
    )  # fmt: skip
    assert result.returncode == 2
    assert (repo / ".hc-hub.yml").read_text() == "keep\n"


def test_init_rejects_agent_not_on_core_path(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "rev=opencode", "--role", "rev=review",
    )  # fmt: skip
    assert result.returncode == 2
    assert not (repo / ".hc-hub.yml").exists()
    assert not (repo / ".gitignore").exists()


def test_init_rejects_reserved_preset_name(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "hub=claude", "--role", "hub=x",
    )  # fmt: skip
    assert result.returncode == 2
    assert not (repo / ".hc-hub.yml").exists()
    assert not (repo / ".gitignore").exists()


def test_check_presets_rejects_unknown_preset(tmp_path: Path) -> None:
    cfg = build_roster("be", "auto", {"a": "claude"}, {"a": "x"})
    roster = load_roster_text(render_roster(cfg), tmp_path / ".hc-hub.yml")
    check_presets(roster, "be", ["a"])
    with pytest.raises(RosterError):
        check_presets(roster, "be", ["nope"])


_ARGS = (
    "--lane", "be", "--approval", "manual",
    "--preset", "impl=claude", "--role", "impl=実装",
)  # fmt: skip


def test_init_existing_roster_never_runs_probe(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    (repo / ".hc-hub.yml").symlink_to(repo / "nowhere")
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "run.log").exists()


def test_init_unwritable_gitignore_writes_nothing(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    gi = repo / ".gitignore"
    gi.write_text("x\n")
    gi.chmod(0o444)
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not (repo / ".hc-hub.yml").exists()
    assert gi.read_text() == "x\n"


def test_init_directory_gitignore_writes_nothing(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    (repo / ".gitignore").mkdir()
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 2
    assert not (repo / ".hc-hub.yml").exists()


def test_init_rejects_ignored_roster_before_writing(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    (repo / ".gitignore").write_text("*.yml\n")
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 2
    assert "worktree" in result.stderr
    assert not (repo / ".hc-hub.yml").exists()
    assert (repo / ".gitignore").read_text() == "*.yml\n"


def test_init_post_write_failure_says_roster_was_written(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    # git は symlink の .gitignore を読まない。追記は通るが、追記後も無視されない
    (tmp_path / "real-ignore").write_text("x\n")
    (repo / ".gitignore").symlink_to(tmp_path / "real-ignore")
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert (repo / ".hc-hub.yml").exists()
    assert "書いた" in result.stderr
    assert "再実行は不要" in result.stderr


def test_init_does_not_duplicate_existing_ignore_line(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    (repo / ".gitignore").write_text("/.hc-hub/\n")
    result = _init(repo, fake, *_ARGS)
    assert result.returncode == 0, result.stderr
    assert (repo / ".gitignore").read_text() == "/.hc-hub/\n"
    assert json.loads(result.stdout)["gitignore_appended"] is False
