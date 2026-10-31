import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 10
LEDGER_REL = ".hc-hub/ledger.jsonl"
IGNORE_LINE = "/.hc-hub/"
GITIGNORE = ".gitignore"
EXIT_IGNORED = 0
EXIT_NOT_IGNORED = 1


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
    return tracked.returncode == 0


def _append_ignore_line(top: Path) -> None:
    path = top / GITIGNORE
    if path.is_symlink() and not path.exists():
        msg = f"{path} は壊れたシンボリックリンク。直してから実行する"
        raise GitignoreError(msg)
    try:
        existing = path.read_bytes().decode("utf-8") if path.exists() else ""
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{prefix}{IGNORE_LINE}\n")
    except (OSError, UnicodeDecodeError) as e:
        msg = f"{path} に追記できない: {e}"
        raise GitignoreError(msg) from e


def ensure_ledger_ignored(top: Path) -> bool:
    if _is_ignored(top) and _ignored_by_tracked_gitignore(top):
        return False
    _append_ignore_line(top)
    if not _is_ignored(top):
        msg = (
            f"{GITIGNORE} に {IGNORE_LINE} を追記したが {LEDGER_REL} が無視されない。"
            f"`git check-ignore -v -- {LEDGER_REL}` で理由を確かめる"
        )
        raise GitignoreError(msg)
    return True
