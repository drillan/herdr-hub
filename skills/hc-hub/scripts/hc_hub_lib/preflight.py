import tomllib
from collections.abc import Mapping
from pathlib import Path


class PreflightError(Exception):
    pass


def _config_path(env: Mapping[str, str]) -> Path:
    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "herdr-core/config.toml"
    home = env.get("HOME")
    if not home:
        msg = "XDG_CONFIG_HOME も HOME も無く、herdr-core の config.toml を探せない"
        raise PreflightError(msg)
    return Path(home) / ".config/herdr-core/config.toml"


def run_preflight(env: Mapping[str, str]) -> None:
    if not env.get("HC_TERMINAL_ID"):
        msg = "herdr-core の管理下ではない（HC_TERMINAL_ID が無い）"
        raise PreflightError(msg)
    path = _config_path(env)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as e:
        msg = f"{path} を読めない: {e}"
        raise PreflightError(msg) from e
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        msg = f"{path} を TOML として読めない: {e}"
        raise PreflightError(msg) from e
    notes = config.get("notes", True)
    if not isinstance(notes, bool):
        msg = f"{path} の notes は true か false（{notes!r}）"
        raise PreflightError(msg)
    if not notes:
        msg = (
            f"{path} が notes = false で、hc が通知を入力しない。"
            "hub は完了通知を受け取れないため、notes を有効にする"
        )
        raise PreflightError(msg)
