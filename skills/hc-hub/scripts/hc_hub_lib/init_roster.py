from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from hc_hub_lib.catalog import find_agent
from hc_hub_lib.roster import Roster, load_roster_text, resolve_worker

ROSTER_NAME = ".hc-hub.yml"
LEDGER_PATH = ".hc-hub/ledger.jsonl"


class InitError(Exception):
    pass


def parse_pairs(values: Sequence[str], flag: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for value in values:
        key, sep, rest = value.partition("=")
        if not sep or not key:
            msg = f"{flag} は NAME=VALUE の形で書く（左辺は空にできない）: {value!r}"
            raise InitError(msg)
        if key in pairs:
            msg = f"{flag} に同じ名前 {key!r} が 2 回ある"
            raise InitError(msg)
        pairs[key] = rest
    return pairs


def build_roster(
    lane: str,
    approval: str,
    presets: Mapping[str, str],
    roles: Mapping[str, str],
) -> dict[str, Any]:
    if set(presets) != set(roles):
        msg = (
            f"--preset の名前 {sorted(presets)} と --role の名前 {sorted(roles)} が"
            "一致しない"
        )
        raise InitError(msg)
    for name, role in roles.items():
        if not role.strip():
            msg = f"--role {name} の役割が空"
            raise InitError(msg)
    return {
        "presets": {
            name: {
                "role": roles[name],
                "command": list(find_agent(agent).argv),
            }
            for name, agent in presets.items()
        },
        "defaults": {"approval": approval},
        "ledger": LEDGER_PATH,
        "lanes": {lane: {"agents": {}}},
    }


def render_roster(cfg: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(cfg), allow_unicode=True, sort_keys=False)


def check_presets(roster: Roster, lane: str, preset_names: Iterable[str]) -> None:
    for name in preset_names:
        resolve_worker(roster, lane, name)


def check_roster_text(
    text: str, path: Path, lane: str, preset_names: Iterable[str]
) -> None:
    check_presets(load_roster_text(text, path), lane, preset_names)


def write_exclusive(path: Path, text: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(text)
    except FileExistsError as e:
        msg = f"{path} が既にある（壊れたシンボリックリンクを含む）。上書きしない"
        raise InitError(msg) from e
    except OSError as e:
        msg = f"{path} を書けない: {e}"
        raise InitError(msg) from e
