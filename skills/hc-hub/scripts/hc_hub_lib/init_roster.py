import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from hc_hub_lib.catalog import find_agent
from hc_hub_lib.probe import is_probeable_path, login_shell, probe_shell
from hc_hub_lib.roster import Roster, load_roster_text, resolve_worker

ROSTER_NAME = ".hc-hub.yml"
LEDGER_PATH = ".hc-hub/ledger.jsonl"
# shebang の行として読む上限。長い 1 行のファイルを丸ごと読まない
SHEBANG_LIMIT = 256


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


def _command(argv: Sequence[str], abs_path: str | None) -> list[str]:
    if abs_path is None:
        return list(argv)
    return [abs_path, *argv[1:]]


def build_roster(
    lane: str,
    approval: str,
    presets: Mapping[str, str],
    roles: Mapping[str, str],
    *,
    abs_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    paths = dict(abs_paths or {})
    unknown = sorted(set(paths) - set(presets))
    if unknown:
        msg = f"--abs-path の名前 {unknown} が --preset に無い"
        raise InitError(msg)
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
                "command": _command(find_agent(agent).argv, paths.get(name)),
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


def parse_abs_paths(
    values: Sequence[str] | None, presets: Mapping[str, str]
) -> list[str]:
    names = list(values or [])
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        msg = f"--abs-path に同じ名前が 2 回ある: {dup}"
        raise InitError(msg)
    unknown = sorted(set(names) - set(presets))
    if unknown:
        msg = f"--abs-path の名前 {unknown} が --preset に無い"
        raise InitError(msg)
    return names


def shell_abs_paths(names: Sequence[str], presets: Mapping[str, str]) -> dict[str, str]:
    # 絶対パスは人に写させず、detect と同じくログインシェルの command -v から取る
    if not names:
        return {}
    executables = sorted({find_agent(presets[n]).executable for n in names})
    found = probe_shell(login_shell(), executables)
    paths: dict[str, str] = {}
    for name in names:
        exe = find_agent(presets[name]).executable
        output = found[exe]
        if not output.startswith("/"):
            msg = (
                f"--abs-path {name}: ログインシェルで {exe} の絶対パスが得られない"
                f"（command -v の結果: {output!r}。alias・関数か、見つからない）"
            )
            raise InitError(msg)
        if not is_probeable_path(output):
            msg = (
                f"--abs-path {name}: 絶対パス {output!r} に扱えない文字がある"
                "（使えるのは英数字と ._/+-）。core の PATH を直す"
            )
            raise InitError(msg)
        paths[name] = output
    return paths


def script_interpreter(path: str) -> str | None:
    # `#!/usr/bin/env node` のスクリプトは、core の PATH に node が無いと起動で失敗する
    try:
        with Path(path).open("rb") as f:
            head = f.readline(SHEBANG_LIMIT)
    except OSError as e:
        msg = f"{path} を読めない: {e}"
        raise InitError(msg) from e
    if not head.startswith(b"#!"):
        return None
    try:
        tokens = head[2:].decode("utf-8").split()
    except UnicodeDecodeError as e:
        msg = f"{path} の shebang が UTF-8 でない: {head!r}"
        raise InitError(msg) from e
    if not tokens:
        msg = f"{path} の shebang が空"
        raise InitError(msg)
    if Path(tokens[0]).name != "env":
        return tokens[0]
    rest = [t for t in tokens[1:] if not t.startswith("-")]
    if not rest:
        msg = f"{path} の shebang からインタープリターが読めない: {head!r}"
        raise InitError(msg)
    return rest[0]


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


def require_roster_absent(path: Path) -> None:
    if os.path.lexists(path):
        msg = f"{path} が既にある（壊れたシンボリックリンクを含む）。上書きしない"
        raise InitError(msg)
