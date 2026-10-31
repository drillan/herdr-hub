import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

APPROVALS = ("auto", "manual")
PLACEMENTS = ("tab", "hidden")
DEFAULT_HANDOFF_AT = 0.8
DEFAULT_PLACEMENT: Literal["tab"] = "tab"
NAME_PATTERN = re.compile(r"[a-z0-9_-]{1,32}")

ALLOWED_KEYS: Mapping[str, frozenset[str]] = {
    "top": frozenset({"presets", "defaults", "ledger", "lanes"}),
    "preset": frozenset(
        {
            "role",
            "role_def",
            "rules",
            "approval",
            "placement",
            "handoff_at",
            "command",
            "template",
        }
    ),
    "defaults": frozenset({"rules", "approval", "placement", "handoff_at"}),
    "lane": frozenset(
        {"rules", "approval", "placement", "handoff_at", "role_def", "hub", "agents"}
    ),
    "lane_hub": frozenset({"rules", "approval", "handoff_at", "role_def"}),
    "resident": frozenset(
        {
            "preset",
            "role",
            "role_def",
            "rules",
            "approval",
            "placement",
            "handoff_at",
            "command",
            "template",
        }
    ),
}

# 置き換え先を示すため、未知のキーの判定より先に見る
REMOVED_KEYS = {
    "kind": "kind は廃止。command か template を書く",
    "transport": "transport は廃止。hc send に一本化",
    "role_file": "role_file は廃止。role_def に改名する",
    "on": "on は使えない。別マシンを指す指定は未対応",
}


class RosterError(Exception):
    pass


@dataclass(frozen=True)
class Resolved:
    role: str | None
    role_def: Path | None
    rules: tuple[Path, ...]
    approval: Literal["auto", "manual"]
    placement: Literal["tab", "hidden"] | None
    handoff_at: float
    command: tuple[str, ...] | None
    template: str | None
    preset: str | None


@dataclass(frozen=True)
class Roster:
    path: Path
    ledger: Path
    lanes: tuple[str, ...]
    raw: Mapping[str, Any]


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        msg = f"{where} はマッピングで書く"
        raise RosterError(msg)
    return cast("Mapping[str, Any]", value)


def _check_name(name: object, where: str) -> str:
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        msg = f"{where} の名前 {name!r} は不正。1〜32 文字の a-z 0-9 - _ に限る"
        raise RosterError(msg)
    return name


def _check_keys(node: Mapping[str, Any], stage: str, where: str) -> None:
    for key in node:
        if key in REMOVED_KEYS:
            msg = f"{where}: {REMOVED_KEYS[key]}"
            raise RosterError(msg)
    for key in node:
        if key not in ALLOWED_KEYS[stage]:
            hint = ""
            if stage == "lane_hub" and key == "placement":
                hint = "（hub に placement は意味を持たない）"
            msg = f"{where}: 未知のキー {key}{hint}"
            raise RosterError(msg)


def _check_enums(node: Mapping[str, Any], where: str) -> None:
    if "approval" in node and node["approval"] not in APPROVALS:
        msg = f"{where}: approval は auto か manual（{node['approval']!r}）"
        raise RosterError(msg)
    if "placement" in node and node["placement"] not in PLACEMENTS:
        msg = f"{where}: placement は tab か hidden（{node['placement']!r}）"
        raise RosterError(msg)
    if "handoff_at" in node:
        value = node["handoff_at"]
        valid = (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and 0 < value <= 1
        )
        if not valid:
            msg = f"{where}: handoff_at は 0 より大きく 1 以下の数（{value!r}）"
            raise RosterError(msg)


def _check_files(node: Mapping[str, Any], base: Path, where: str) -> None:
    if "rules" in node:
        rules = node["rules"]
        if not isinstance(rules, list) or not all(isinstance(r, str) for r in rules):
            msg = f"{where}: rules は文字列のリスト"
            raise RosterError(msg)
        for rule in rules:
            _require_file(base / rule, f"{where}.rules")
    if "role_def" in node:
        if not isinstance(node["role_def"], str):
            msg = f"{where}: role_def は文字列"
            raise RosterError(msg)
        _require_file(base / node["role_def"], f"{where}.role_def")


def _check_launch(node: Mapping[str, Any], where: str) -> None:
    for key in ("role", "template"):
        if key in node and not isinstance(node[key], str):
            msg = f"{where}: {key} は文字列"
            raise RosterError(msg)
    if "command" in node:
        command = node["command"]
        valid = (
            isinstance(command, list)
            and bool(command)
            and all(isinstance(c, str) and c for c in command)
        )
        if not valid:
            msg = f"{where}: command は空でない文字列のリスト"
            raise RosterError(msg)
    if "command" in node and "template" in node:
        msg = f"{where}: command と template は同時に書けない"
        raise RosterError(msg)


def _check_values(node: Mapping[str, Any], base: Path, where: str) -> None:
    _check_enums(node, where)
    _check_files(node, base, where)
    _check_launch(node, where)


def _require_file(path: Path, where: str) -> None:
    if not path.is_file():
        msg = f"{where}: 読めないファイル {path}"
        raise RosterError(msg)


def _validate_stage(
    node: object, stage: str, base: Path, where: str
) -> Mapping[str, Any]:
    mapping = _mapping(node, where)
    _check_keys(mapping, stage, where)
    _check_values(mapping, base, where)
    return mapping


class _Yaml12BoolLoader(yaml.SafeLoader):
    # YAML 1.1 では on/off/yes/no が真偽値になり、未引用の `on:` キーが
    # True に化けて廃止キーの案内に届かない。真偽は true/false だけにする
    pass


_Yaml12BoolLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12BoolLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _read_yaml(path: Path) -> object:
    try:
        text = path.read_text()
    except OSError as e:
        msg = f"roster を読めない: {path}（{e.strerror}）"
        raise RosterError(msg) from e
    except UnicodeDecodeError as e:
        msg = f"roster が UTF-8 ではない: {path}（{e}）"
        raise RosterError(msg) from e
    try:
        return yaml.load(text, Loader=_Yaml12BoolLoader)  # noqa: S506
    except yaml.YAMLError as e:
        msg = f"roster の YAML が壊れている: {path}（{e}）"
        raise RosterError(msg) from e


def _validate_lane(
    lane_name: str,
    lane: object,
    presets: Mapping[str, Any],
    base: Path,
    seen_residents: dict[str, str],
) -> None:
    _check_name(lane_name, "lanes")
    where = f"lanes.{lane_name}"
    lane_map = _validate_stage(lane, "lane", base, where)
    if "hub" in lane_map:
        _validate_stage(lane_map["hub"], "lane_hub", base, f"{where}.hub")
    agents = _mapping(lane_map.get("agents", {}), f"{where}.agents")
    for agent_name, agent in agents.items():
        agent_where = f"{where}.agents.{agent_name}"
        _check_name(agent_name, f"{where}.agents")
        if agent_name in seen_residents:
            msg = (
                f"{agent_where}: 常駐 agent の名前がレーン "
                f"{seen_residents[agent_name]} と重複"
            )
            raise RosterError(msg)
        seen_residents[agent_name] = lane_name
        agent_map = _validate_stage(agent, "resident", base, agent_where)
        if "preset" in agent_map:
            preset = agent_map["preset"]
            if not isinstance(preset, str) or preset not in presets:
                msg = f"{agent_where}: preset は定義済みの preset 名（{preset!r}）"
                raise RosterError(msg)


def load_roster(path: Path) -> Roster:
    path = path.resolve()
    top = _mapping(_read_yaml(path), "roster")
    base = path.parent
    _check_keys(top, "top", "roster")
    if "ledger" not in top or not isinstance(top["ledger"], str) or not top["ledger"]:
        msg = "roster: ledger は必須（台帳のパスを文字列で書く）"
        raise RosterError(msg)
    presets = _mapping(top.get("presets", {}), "presets")
    for name, preset in presets.items():
        _check_name(name, "presets")
        _validate_stage(preset, "preset", base, f"presets.{name}")
    _validate_stage(top.get("defaults", {}), "defaults", base, "defaults")
    lanes = _mapping(top.get("lanes", {}), "lanes")
    seen_residents: dict[str, str] = {}
    for lane_name, lane in lanes.items():
        _validate_lane(lane_name, lane, presets, base, seen_residents)
    roster = Roster(
        path=path,
        ledger=base / top["ledger"],
        lanes=tuple(lanes),
        raw=top,
    )
    _check_approval_resolvable(roster)
    return roster


def _check_approval_resolvable(roster: Roster) -> None:
    for lane in roster.lanes:
        resolve_hub(roster, lane)
        for preset in roster.raw.get("presets", {}):
            _resolve_chain(
                roster, lane, preset=preset, where=f"lanes.{lane} x presets.{preset}"
            )
        for name in resident_names(roster, lane):
            resolve_resident(roster, lane, name)


def _lane_node(roster: Roster, lane: str) -> Mapping[str, Any]:
    if lane not in roster.lanes:
        msg = f"未知のレーン {lane!r}（roster: {roster.path}）"
        raise RosterError(msg)
    return cast("Mapping[str, Any]", roster.raw["lanes"][lane])


def _merge(
    roster: Roster,
    stages: list[Mapping[str, Any]],
    *,
    where: str,
    is_hub: bool,
    preset: str | None,
) -> Resolved:
    base = roster.path.parent
    merged: dict[str, Any] = {}
    rules: list[Path] = []
    for stage in stages:
        merged.update({k: v for k, v in stage.items() if k != "rules"})
        rules.extend(base / r for r in stage.get("rules", []))
    if "approval" not in merged:
        msg = f"{where}: approval がどの段にも書かれていない（既定値は持たない）"
        raise RosterError(msg)
    command = merged.get("command")
    if command is not None and "template" in merged:
        msg = f"{where}: 段をまたいで command と template の両方が解決された"
        raise RosterError(msg)
    role_def = merged.get("role_def")
    return Resolved(
        role=merged.get("role"),
        role_def=base / role_def if role_def is not None else None,
        rules=tuple(rules),
        approval=merged["approval"],
        placement=None if is_hub else merged.get("placement", DEFAULT_PLACEMENT),
        handoff_at=float(merged.get("handoff_at", DEFAULT_HANDOFF_AT)),
        command=tuple(command) if command is not None else None,
        template=merged.get("template"),
        preset=preset,
    )


def _resolve_chain(
    roster: Roster,
    lane: str,
    *,
    preset: str | None,
    where: str,
    individual: Mapping[str, Any] | None = None,
) -> Resolved:
    stages: list[Mapping[str, Any]] = [roster.raw.get("defaults", {})]
    lane_node = {
        k: v for k, v in _lane_node(roster, lane).items() if k not in ("hub", "agents")
    }
    stages.append(lane_node)
    if preset is not None:
        stages.append(roster.raw["presets"][preset])
    if individual is not None:
        stages.append({k: v for k, v in individual.items() if k != "preset"})
    return _merge(roster, stages, where=where, is_hub=False, preset=preset)


def _require_role(resolved: Resolved, where: str) -> None:
    if not isinstance(resolved.role, str) or not resolved.role:
        msg = f"{where}: role が解決できない（preset か個別に空でない文字列で書く）"
        raise RosterError(msg)


def resolve_hub(roster: Roster, lane: str) -> Resolved:
    lane_node = _lane_node(roster, lane)
    stages = [
        roster.raw.get("defaults", {}),
        {k: v for k, v in lane_node.items() if k not in ("hub", "agents")},
        lane_node.get("hub", {}),
    ]
    return _merge(roster, stages, where=f"lanes.{lane}.hub", is_hub=True, preset=None)


def resolve_worker(roster: Roster, lane: str, preset: str) -> Resolved:
    _lane_node(roster, lane)
    if preset not in roster.raw.get("presets", {}):
        msg = f"未定義の preset {preset!r}（roster: {roster.path}）"
        raise RosterError(msg)
    resolved = _resolve_chain(
        roster, lane, preset=preset, where=f"lanes.{lane} x presets.{preset}"
    )
    if resolved.command is None and resolved.template is None:
        msg = f"preset {preset} に command も template も無く、worker を起こせない"
        raise RosterError(msg)
    _require_role(resolved, f"preset {preset}")
    return resolved


def resolve_resident(roster: Roster, lane: str, name: str) -> Resolved:
    agents = _lane_node(roster, lane).get("agents", {})
    if name not in agents:
        msg = f"レーン {lane} に常駐 agent {name!r} は無い"
        raise RosterError(msg)
    agent = agents[name]
    where = f"lanes.{lane}.agents.{name}"
    resolved = _resolve_chain(
        roster, lane, preset=agent.get("preset"), where=where, individual=agent
    )
    if resolved.command is None and resolved.template is None:
        msg = f"{where}: command も template も解決できず、起動方法が無い"
        raise RosterError(msg)
    _require_role(resolved, where)
    return resolved


def resident_names(roster: Roster, lane: str) -> tuple[str, ...]:
    return tuple(_lane_node(roster, lane).get("agents", {}))
