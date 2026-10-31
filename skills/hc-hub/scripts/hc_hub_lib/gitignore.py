import os
import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 10
LEDGER_REL = ".hc-hub/ledger.jsonl"
IGNORE_LINE = "/.hc-hub/"
GITIGNORE = ".gitignore"
EXIT_IGNORED = 0
EXIT_NOT_IGNORED = 1
EXIT_TRACKED = 0
EXIT_UNTRACKED = 1


class GitignoreError(Exception):
    pass


def _git(top: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(top), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        msg = f"git を実行できない: {e}"
        raise GitignoreError(msg) from e


def _is_ignored(top: Path) -> bool:
    proc = _git(top, "check-ignore", "-q", "--", LEDGER_REL)
    if proc.returncode == EXIT_IGNORED:
        return True
    if proc.returncode == EXIT_NOT_IGNORED:
        return False
    msg = f"git check-ignore が失敗した: {top} ({proc.stderr.strip()})"
    raise GitignoreError(msg)


def _ignored_by_tracked_gitignore(top: Path) -> bool:
    proc = _git(top, "check-ignore", "-v", "--", LEDGER_REL)
    if proc.returncode != EXIT_IGNORED:
        msg = f"git check-ignore -v が失敗した: {top} ({proc.stderr.strip()})"
        raise GitignoreError(msg)
    source = proc.stdout.split(":", 1)[0]
    if source != GITIGNORE:
        return False
    tracked = _git(top, "ls-files", "--error-unmatch", GITIGNORE)
    if tracked.returncode == EXIT_TRACKED:
        return True
    if tracked.returncode == EXIT_UNTRACKED:
        return False
    msg = f"git ls-files が失敗した: {top} ({tracked.stderr.strip()})"
    raise GitignoreError(msg)


def _read_gitignore(top: Path) -> str:
    # 追記先として壊れていないかを確かめつつ中身を返す。書き込みはしない
    path = top / GITIGNORE
    if path.is_symlink() and not path.exists():
        msg = f"{path} は壊れたシンボリックリンク。直してから実行する"
        raise GitignoreError(msg)
    if path.is_dir():
        msg = f"{path} がディレクトリ。直してから実行する"
        raise GitignoreError(msg)
    if not path.exists():
        return ""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        msg = f"{path} を読めない: {e}"
        raise GitignoreError(msg) from e


def _require_appendable(top: Path) -> None:
    path = top / GITIGNORE
    if not path.exists():
        if not os.access(top, os.W_OK):
            msg = f"{top} に {GITIGNORE} を作れない（書き込み権限が無い）"
            raise GitignoreError(msg)
        return
    if not os.access(path, os.W_OK):
        msg = f"{path} に追記できない（書き込み権限が無い）"
        raise GitignoreError(msg)


def _append_ignore_line(top: Path) -> None:
    path = top / GITIGNORE
    existing = _read_gitignore(top)
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{prefix}{IGNORE_LINE}\n")
    except OSError as e:
        msg = f"{path} に追記できない: {e}"
        raise GitignoreError(msg) from e


def require_roster_not_ignored(top: Path, roster_name: str) -> None:
    # Roster 自体が無視されていると worker の worktree に届かないので、書く前に止める。
    proc = _git(top, "check-ignore", "-q", "--", roster_name)
    if proc.returncode == EXIT_NOT_IGNORED:
        return
    if proc.returncode == EXIT_IGNORED:
        msg = (
            f"{roster_name} が git の除外設定で無視されている。"
            "無視されたファイルは commit されず、worker の worktree に届かない。"
            f"`git check-ignore -v -- {roster_name}` で出どころを確かめ、"
            f"{roster_name} を除外しないよう直してから実行する"
        )
        raise GitignoreError(msg)
    msg = f"git check-ignore が失敗した: {top} ({proc.stderr.strip()})"
    raise GitignoreError(msg)


def plan_ledger_ignore(top: Path) -> bool:
    # 追記が要るかを返す。追記できない状態なら何も書かずに例外を送出する
    existing = _read_gitignore(top)
    has_line = IGNORE_LINE in existing.splitlines()
    if _is_ignored(top) and (has_line or _ignored_by_tracked_gitignore(top)):
        return False
    _require_appendable(top)
    return True


def append_ledger_ignore(top: Path) -> None:
    # plan_ledger_ignore が True のときに追記し、無視されるか再検査する
    _append_ignore_line(top)
    if not _is_ignored(top):
        msg = (
            f"{GITIGNORE} に {IGNORE_LINE} を追記したが {LEDGER_REL} が無視されない。"
            f"`git check-ignore -v -- {LEDGER_REL}` で理由を確かめる"
        )
        raise GitignoreError(msg)


def ensure_ledger_ignored(top: Path) -> bool:
    if not plan_ledger_ignore(top):
        return False
    append_ledger_ignore(top)
    return True
