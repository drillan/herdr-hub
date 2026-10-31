import subprocess
from pathlib import Path

import hc_hub_lib.gitignore as gitignore_mod
import pytest
from hc_hub_lib.gitignore import (
    GitignoreError,
    ensure_ledger_ignored,
    plan_ledger_ignore,
    require_roster_not_ignored,
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


def _track_gitignore(repo: Path, content: str) -> None:
    (repo / ".gitignore").write_text(content, encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "gitignore")


def test_tracked_gitignore_entry_is_kept(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _track_gitignore(repo, "/.hc-hub/\n")

    assert ensure_ledger_ignored(repo) is False
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "/.hc-hub/\n"


def test_trailing_slash_pattern_counts_as_ignored(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _track_gitignore(repo, ".hc-hub/\n")

    assert ensure_ledger_ignored(repo) is False
    assert (repo / ".gitignore").read_text(encoding="utf-8") == ".hc-hub/\n"


def test_missing_gitignore_is_created(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert ensure_ledger_ignored(repo) is True
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "/.hc-hub/\n"


def test_append_keeps_last_line_without_newline(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("x", encoding="utf-8")

    assert ensure_ledger_ignored(repo) is True
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "x\n/.hc-hub/\n"


def test_ignored_only_by_info_exclude_appends(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text("/.hc-hub/\n", encoding="utf-8")

    assert ensure_ledger_ignored(repo) is True
    assert "/.hc-hub/" in (repo / ".gitignore").read_text(encoding="utf-8")


def test_untracked_gitignore_with_exact_line_is_not_duplicated(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("/.hc-hub/\n", encoding="utf-8")

    assert ensure_ledger_ignored(repo) is False
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "/.hc-hub/\n"


def test_untracked_gitignore_with_other_pattern_is_appended(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".hc-hub/\n", encoding="utf-8")

    assert ensure_ledger_ignored(repo) is True
    assert (repo / ".gitignore").read_text(encoding="utf-8") == ".hc-hub/\n/.hc-hub/\n"


def test_recheck_failure_is_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setattr(gitignore_mod, "_is_ignored", lambda _top: False)

    with pytest.raises(GitignoreError, match="check-ignore -v"):
        ensure_ledger_ignored(repo)


def test_gitignore_directory_is_error(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").mkdir()

    with pytest.raises(GitignoreError):
        ensure_ledger_ignored(repo)


def test_broken_symlink_gitignore_is_error(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").symlink_to(repo / "nowhere")

    with pytest.raises(GitignoreError):
        ensure_ledger_ignored(repo)
    assert not (repo / "nowhere").exists()


def test_non_utf8_gitignore_is_error(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_bytes(b"\xff\xfe\n")

    with pytest.raises(GitignoreError):
        ensure_ledger_ignored(repo)


def test_not_a_git_repo_is_error(tmp_path: Path) -> None:
    with pytest.raises(GitignoreError):
        ensure_ledger_ignored(tmp_path)


def test_ls_files_failure_is_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path / "repo")
    _track_gitignore(repo, ".hc-hub/\n")
    real_run = subprocess.run

    def failing_ls_files(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if "ls-files" in argv:
            return subprocess.CompletedProcess(argv, 128, "", "fatal: broken")
        return real_run(argv, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "run", failing_ls_files)

    with pytest.raises(GitignoreError, match="ls-files"):
        ensure_ledger_ignored(repo)
    assert (repo / ".gitignore").read_text(encoding="utf-8") == ".hc-hub/\n"


def test_plan_writes_nothing_and_reports_need(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert plan_ledger_ignore(repo) is True
    assert not (repo / ".gitignore").exists()


def test_plan_rejects_unwritable_gitignore(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    gi = repo / ".gitignore"
    gi.write_text("x\n", encoding="utf-8")
    gi.chmod(0o444)

    with pytest.raises(GitignoreError, match="書き込み権限"):
        plan_ledger_ignore(repo)
    assert gi.read_text(encoding="utf-8") == "x\n"


@pytest.mark.parametrize("kind", ["directory", "broken-link", "non-utf8"])
def test_plan_rejects_unappendable_gitignore(tmp_path: Path, kind: str) -> None:
    repo = _init_repo(tmp_path / "repo")
    gi = repo / ".gitignore"
    if kind == "directory":
        gi.mkdir()
    elif kind == "broken-link":
        gi.symlink_to(repo / "nowhere")
    else:
        gi.write_bytes(b"\xff\xfe\n")

    with pytest.raises(GitignoreError):
        plan_ledger_ignore(repo)


def test_roster_ignored_is_error(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("*.yml\n", encoding="utf-8")

    with pytest.raises(GitignoreError, match="worker の worktree"):
        require_roster_not_ignored(repo, ".hc-hub.yml")


def test_roster_not_ignored_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    require_roster_not_ignored(repo, ".hc-hub.yml")
