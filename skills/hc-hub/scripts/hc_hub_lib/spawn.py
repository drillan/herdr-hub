from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from hc_hub_lib.guard import HUB_ROLE, LANE, ROLE, check_placement_tab
from hc_hub_lib.roster import NAME_PATTERN, Resolved, Roster, RosterError

STATE_DIR = ".hc-hub"


class SpawnError(Exception):
    pass


def ensure_state_dir(roster: Roster) -> Path:
    # spawn-argv の出力を受ける置き場。台帳に書く前の最初の起動でも要る
    path = roster.path.parent / STATE_DIR
    try:
        path.mkdir(exist_ok=True)
    except OSError as e:
        msg = f"{path} を作れない: {e}"
        raise SpawnError(msg) from e
    return path


def start_hub(
    roster: Roster,
    lane: str,
    self_address: str,
    ls_hubs: Sequence[Mapping[str, Any]],
) -> list[str]:
    if lane not in roster.lanes:
        msg = f"未知のレーン {lane!r}（roster: {roster.path}）"
        raise RosterError(msg)
    others = [
        h["address"]
        for h in ls_hubs
        if h.get("state") == "live" and h.get("address") != self_address
    ]
    if others:
        msg = f"レーン {lane} にはすでに live な hub がいる: {', '.join(others)}"
        raise SpawnError(msg)
    return [f"{LANE}={lane}", f"{ROLE}=hub"]


def require_lane_hub(self_labels: Mapping[str, str], lane: str) -> None:
    if LANE not in self_labels or ROLE not in self_labels:
        msg = f"自分に {LANE} か {ROLE} が無い。先に hc-hub start を実行する"
        raise SpawnError(msg)
    if self_labels[ROLE] != HUB_ROLE:
        msg = (
            f"自分の {ROLE} が {HUB_ROLE} でない（{self_labels[ROLE]!r}）。"
            "hub だけが操作できる（先に hc-hub start）"
        )
        raise SpawnError(msg)
    if self_labels[LANE] != lane:
        msg = (
            f"自分のレーンは {self_labels[LANE]!r} で、{lane!r} ではない。"
            "自分のレーンでしか起動・記録できない"
        )
        raise SpawnError(msg)


def spawn_argv(  # noqa: PLR0913, PLR0917
    resolved: Resolved,
    lane: str,
    name: str,
    task: str,
    self_labels: Mapping[str, str],
    brief: str | None,
    *,
    role: str,
    cwd: Path,
) -> list[str]:
    require_lane_hub(self_labels, lane)
    if not cwd.is_absolute():
        msg = f"cwd {str(cwd)!r} は絶対パスでなければならない"
        raise SpawnError(msg)
    if not cwd.is_dir():
        msg = f"cwd {str(cwd)!r} は存在するディレクトリでない"
        raise SpawnError(msg)
    if not NAME_PATTERN.fullmatch(name):
        msg = f"名前 {name!r} は不正。1〜32 文字の a-z 0-9 - _ に限る"
        raise SpawnError(msg)
    if not NAME_PATTERN.fullmatch(role):
        msg = f"role {role!r} は不正。1〜32 文字の a-z 0-9 - _ に限る"
        raise SpawnError(msg)
    if role == HUB_ROLE:
        msg = f"role {HUB_ROLE!r} は hub 専用の予約語で、worker には使えない"
        raise SpawnError(msg)
    argv = [
        "run",
        "--bg",
        "--json",
        "--outlive-parent",
        "--name",
        name,
        "--cwd",
        str(cwd),
        "--label",
        f"{LANE}={lane}",
        "--label",
        f"{ROLE}={role}",
    ]
    if brief is not None:
        argv += ["--label", f"hc-hub.brief={brief}"]
    if resolved.placement == "tab":
        argv += ["--label", f"herdr.space={check_placement_tab(self_labels)}"]
    # task が `-` で始まってもオプションとして読まれないよう、どちらも `--` の後に置く
    if resolved.command is not None:
        return [*argv, "--", *resolved.command, task]
    if resolved.template is not None:
        return [*argv, "--", resolved.template, task]
    msg = "起動方法（command も template）が無い"
    raise SpawnError(msg)
