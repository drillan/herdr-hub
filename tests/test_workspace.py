import subprocess
from pathlib import Path

import pytest
from hc_hub_lib.workspace import (
    WorkspaceError,
    require_main_checkout_top,
    require_not_worker,
)

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *GIT_ID, "-C", str(cwd), *args],  # noqa: S607
        check=True,
        capture_output=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "commit", "-q", "--allow-empty", "-m", "init")
    return path


def test_top_of_main_checkout_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    assert require_main_checkout_top(repo) == repo.resolve()


def test_subdirectory_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    sub = repo / "sub"
    sub.mkdir()
    with pytest.raises(WorkspaceError, match=str(repo.resolve())):
        require_main_checkout_top(sub)


def test_linked_worktree_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt))
    with pytest.raises(WorkspaceError, match="worktree"):
        require_main_checkout_top(wt)


def test_submodule_is_rejected(tmp_path: Path) -> None:
    inner = _init_repo(tmp_path / "inner")
    outer = _init_repo(tmp_path / "outer")
    _git(
        outer,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(inner),
        "mod",
    )
    with pytest.raises(WorkspaceError, match="submodule"):
        require_main_checkout_top(outer / "mod")


def test_not_a_git_repo_is_rejected(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(WorkspaceError, match="git"):
        require_main_checkout_top(plain)


def test_missing_git_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(WorkspaceError, match="git"):
        require_main_checkout_top(tmp_path)


def test_require_not_worker() -> None:
    require_not_worker({})
    require_not_worker({"hc-hub.role": "hub"})
    with pytest.raises(WorkspaceError):
        require_not_worker({"hc-hub.role": "worker"})
