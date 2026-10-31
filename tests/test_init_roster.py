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
    script_interpreter,
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


def test_build_roster_replaces_executable_with_absolute_path() -> None:
    cfg = build_roster(
        "be",
        "manual",
        {"impl": "claude", "rev": "opencode"},
        {"impl": "実装", "rev": "review"},
        abs_paths={"rev": "/opt/oc/bin/opencode"},
    )
    assert cfg["presets"]["rev"]["command"] == ["/opt/oc/bin/opencode", "--prompt"]
    assert cfg["presets"]["impl"]["command"] == ["claude"]


def test_build_roster_rejects_abs_path_for_unknown_preset() -> None:
    with pytest.raises(InitError, match="--abs-path"):
        build_roster(
            "be",
            "auto",
            {"impl": "claude"},
            {"impl": "x"},
            abs_paths={"rev": "/opt/oc/bin/opencode"},
        )


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


def _shell_home(tmp_path: Path, rc: str) -> dict[str, str]:
    # ログインシェルは本物（passwd の pw_shell）が起きるので、HOME で rc を固定する
    home = tmp_path / "home"
    home.mkdir()
    for name in (".profile", ".zshrc"):
        (home / name).write_text(rc)
    # HOME を変えると uv がキャッシュと Python を見失うので、元の場所を明示する
    uv_dirs = {
        key: subprocess.run(
            ["uv", *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for key, args in (
            ("UV_CACHE_DIR", ["cache", "dir"]),
            ("UV_PYTHON_INSTALL_DIR", ["python", "dir"]),
        )
    }
    return {"HOME": str(home), "ZDOTDIR": str(home), **uv_dirs}


def _shell_only_opencode(tmp_path: Path) -> Path:
    shbin = tmp_path / "shbin"
    shbin.mkdir()
    exe = shbin / "opencode"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def _init_env(
    repo: Path, fake: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "init",
        "--hc",
        str(fake),
        *args,
        env_extra={"HC_TERMINAL_ID": "t7", **env},
        cwd=repo,
    )


def test_init_abs_path_writes_path_found_by_login_shell(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    exe = _shell_only_opencode(tmp_path)
    env = _shell_home(tmp_path, f'PATH="{exe.parent}:$PATH"\n')
    result = _init_env(
        repo, fake, env,
        "--lane", "be", "--approval", "manual",
        "--preset", "impl=claude", "--role", "impl=実装",
        "--preset", "rev=opencode", "--role", "rev=review",
        "--abs-path", "rev",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    roster = load_roster(repo / ".hc-hub.yml")
    assert roster.raw["presets"]["rev"]["command"] == [str(exe), "--prompt"]
    assert roster.raw["presets"]["impl"]["command"] == ["claude"]
    out = json.loads(result.stdout)
    assert out["absolute_paths"] == {"rev": str(exe)}
    assert "別のマシン" in out["next"]


def test_init_without_abs_path_reports_empty_absolute_paths(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "impl=claude", "--role", "impl=実装",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["absolute_paths"] == {}
    assert "別のマシン" not in out["next"]


def test_init_missing_on_core_path_suggests_abs_path(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "rev=opencode", "--role", "rev=review",
    )  # fmt: skip
    assert result.returncode == 2
    assert "--abs-path" in result.stderr


def test_init_abs_path_rejects_alias(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    env = _shell_home(tmp_path, "alias opencode='echo hi'\n")
    result = _init_env(
        repo, fake, env,
        "--lane", "be", "--approval", "manual",
        "--preset", "rev=opencode", "--role", "rev=review",
        "--abs-path", "rev",
    )  # fmt: skip
    assert result.returncode == 2
    assert "絶対パス" in result.stderr
    assert not (repo / ".hc-hub.yml").exists()
    assert not (repo / ".gitignore").exists()


@pytest.mark.parametrize(
    ("abs_args", "reason"),
    [
        (["--abs-path", "nope"], "--preset に無い"),
        (["--abs-path", "rev", "--abs-path", "rev"], "2 回ある"),
    ],
)
def test_init_abs_path_rejects_unknown_or_duplicate(
    tmp_path: Path, abs_args: list[str], reason: str
) -> None:
    repo, fake = _setup(tmp_path)
    result = _init(
        repo,
        fake,
        "--lane", "be", "--approval", "manual",
        "--preset", "rev=claude", "--role", "rev=review",
        *abs_args,
    )  # fmt: skip
    assert result.returncode == 2
    assert reason in result.stderr
    assert not (repo / ".hc-hub.yml").exists()


def _shell_only_script(tmp_path: Path, name: str, body: str, *, mode: int) -> Path:
    shbin = tmp_path / "shbin"
    shbin.mkdir(exist_ok=True)
    exe = shbin / name
    exe.write_text(body)
    exe.chmod(mode)
    return exe


def test_init_abs_path_rejects_missing_env_interpreter(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    exe = _shell_only_script(tmp_path, "codex", "#!/usr/bin/env node\n", mode=0o755)
    env = _shell_home(tmp_path, f'PATH="{exe.parent}:$PATH"\n')
    result = _init_env(
        repo, fake, env,
        "--lane", "be", "--approval", "manual",
        "--preset", "cx=codex", "--role", "cx=review",
        "--abs-path", "cx",
    )  # fmt: skip
    assert result.returncode == 2
    assert "node" in result.stderr
    assert not (repo / ".hc-hub.yml").exists()


def test_init_abs_path_accepts_env_interpreter_on_core_path(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    node = tmp_path / "bin" / "node"
    node.write_text("#!/bin/sh\n")
    node.chmod(0o755)
    exe = _shell_only_script(
        tmp_path, "codex", "#!/usr/bin/env -S node --flag\n", mode=0o755
    )
    env = _shell_home(tmp_path, f'PATH="{exe.parent}:$PATH"\n')
    result = _init_env(
        repo, fake, env,
        "--lane", "be", "--approval", "manual",
        "--preset", "cx=codex", "--role", "cx=review",
        "--abs-path", "cx",
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    roster = load_roster(repo / ".hc-hub.yml")
    assert roster.raw["presets"]["cx"]["command"] == [str(exe), "--no-daemon"]


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"#!/usr/bin/env node\n", "node"),
        (b"#!/usr/bin/env -S node --x\n", "node"),
        (b"#!/bin/sh\n", "/bin/sh"),
        (b"\x7fELF\x02", None),
    ],
)
def test_script_interpreter_reads_shebang(
    tmp_path: Path, head: bytes, expected: str | None
) -> None:
    f = tmp_path / "s"
    f.write_bytes(head)
    assert script_interpreter(str(f)) == expected


@pytest.mark.parametrize("head", [b"#!\n", b"#!/usr/bin/env -S\n", b"#!\xff\n"])
def test_script_interpreter_rejects_unreadable_shebang(
    tmp_path: Path, head: bytes
) -> None:
    f = tmp_path / "s"
    f.write_bytes(head)
    with pytest.raises(InitError, match="shebang"):
        script_interpreter(str(f))


def test_init_abs_path_rejects_path_with_space(tmp_path: Path) -> None:
    repo, fake = _setup(tmp_path)
    shbin = tmp_path / "sh bin"
    shbin.mkdir()
    exe = shbin / "opencode"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    env = _shell_home(tmp_path, f'PATH="{shbin}:$PATH"\n')
    result = _init_env(
        repo, fake, env,
        "--lane", "be", "--approval", "manual",
        "--preset", "rev=opencode", "--role", "rev=review",
        "--abs-path", "rev",
    )  # fmt: skip
    assert result.returncode == 2
    assert "扱えない文字" in result.stderr
    assert not (repo / ".hc-hub.yml").exists()
