from collections.abc import Mapping, Sequence
from typing import Any

from hc_hub_lib.guard import LANE, ROLE, check_placement_tab
from hc_hub_lib.roster import NAME_PATTERN, Resolved, Roster, RosterError


class SpawnError(Exception):
    pass


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


def spawn_argv(  # noqa: PLR0913, PLR0917
    resolved: Resolved,
    lane: str,
    name: str,
    task: str,
    self_labels: Mapping[str, str],
    brief: str | None,
    *,
    role: str | None = None,
) -> list[str]:
    if not NAME_PATTERN.fullmatch(name):
        msg = f"名前 {name!r} は不正。1〜32 文字の a-z 0-9 - _ に限る"
        raise SpawnError(msg)
    role_label = role or resolved.preset or name
    argv = [
        "run",
        "--bg",
        "--json",
        "--outlive-parent",
        "--name",
        name,
        "--label",
        f"{LANE}={lane}",
        "--label",
        f"{ROLE}={role_label}",
    ]
    if brief is not None:
        argv += ["--label", f"hc-hub.brief={brief}"]
    if resolved.placement == "tab":
        argv += ["--label", f"herdr.space={check_placement_tab(self_labels)}"]
    if resolved.command is not None:
        return [*argv, "--", *resolved.command, task]
    if resolved.template is not None:
        return [*argv, resolved.template, task]
    msg = "起動方法（command も template）が無い"
    raise SpawnError(msg)
