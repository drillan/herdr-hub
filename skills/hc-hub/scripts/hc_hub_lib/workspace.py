import subprocess
from collections.abc import Mapping
from pathlib import Path

from hc_hub_lib.guard import HUB_ROLE, ROLE

GIT_TIMEOUT_SECONDS = 10


class WorkspaceError(Exception):
    pass


def _git(cwd: Path, *args: str) -> str:
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "-C", str(cwd), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        msg = f"git を実行できない: {e}"
        raise WorkspaceError(msg) from e
    if proc.returncode != 0:
        detail = proc.stderr.strip()
        msg = f"git の管理下ではない、または git が失敗した: {cwd} ({detail})"
        raise WorkspaceError(msg)
    return proc.stdout.strip()


def require_main_checkout_top(cwd: Path) -> Path:
    top = Path(_git(cwd, "rev-parse", "--show-toplevel")).resolve()
    if top != cwd.resolve():
        msg = f"repo の最上位で実行する（最上位: {top}）"
        raise WorkspaceError(msg)
    git_dir = (cwd / _git(cwd, "rev-parse", "--git-dir")).resolve()
    common_dir = (cwd / _git(cwd, "rev-parse", "--git-common-dir")).resolve()
    if git_dir != common_dir:
        msg = f"linked worktree では実行できない。本体の checkout で実行する: {top}"
        raise WorkspaceError(msg)
    if _git(cwd, "rev-parse", "--show-superproject-working-tree"):
        msg = f"submodule の中では実行できない。親 repo の最上位で実行する: {top}"
        raise WorkspaceError(msg)
    return top


def require_not_worker(labels: Mapping[str, str]) -> None:
    role = labels.get(ROLE)
    if role is not None and role != HUB_ROLE:
        msg = f"{ROLE}={role} の端末では実行できない（hub か未設定の端末で実行する）"
        raise WorkspaceError(msg)
