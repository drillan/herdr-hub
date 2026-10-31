import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

EVENTS = ("spawn", "stop", "adopt")
APPEND_MODE = 0o644


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class LedgerEvent:
    ts: str
    lane: str
    name: str
    address: str
    event: Literal["spawn", "stop", "adopt"]
    hub: str
    preset: str | None
    command: tuple[str, ...] | None
    template: str | None
    brief: str | None


def append_event(path: Path, ev: LedgerEvent) -> None:
    # 複数レーンの hub が同時に追記する。1 行を 1 回の write で書かないと行が混ざる
    data = (json.dumps(asdict(ev), ensure_ascii=False) + "\n").encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, APPEND_MODE)
    except OSError as e:
        msg = f"台帳を開けない: {path}（{e.strerror}）"
        raise LedgerError(msg) from e
    try:
        written = os.write(fd, data)
    except OSError as e:
        msg = f"台帳へ追記できない: {path}（{e.strerror}）"
        raise LedgerError(msg) from e
    finally:
        os.close(fd)
    if written != len(data):
        msg = f"台帳への追記が途中で止まった: {path}（{written}/{len(data)} バイト）"
        raise LedgerError(msg)


def _optional_str(row: dict[str, Any], key: str) -> str | None:
    value = row[key]
    if value is not None and not isinstance(value, str):
        msg = f"{key} は文字列か null"
        raise ValueError(msg)
    return value


def _required_str(row: dict[str, Any], key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        msg = f"{key} は文字列"
        raise ValueError(msg)  # noqa: TRY004
    return value


def _command(row: dict[str, Any]) -> tuple[str, ...] | None:
    value = row["command"]
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
        msg = "command は文字列のリストか null"
        raise ValueError(msg)
    return tuple(cast("list[str]", value))


def _parse(line: str) -> LedgerEvent:
    row = json.loads(line)
    if not isinstance(row, dict):
        msg = "JSON オブジェクトではない"
        raise TypeError(msg)
    row = cast("dict[str, Any]", row)
    event = row.get("event")
    if event not in EVENTS:
        msg = f"event は {'・'.join(EVENTS)} のいずれか（{event!r}）"
        raise ValueError(msg)
    return LedgerEvent(
        ts=_required_str(row, "ts"),
        lane=_required_str(row, "lane"),
        name=_required_str(row, "name"),
        address=_required_str(row, "address"),
        event=event,
        hub=_required_str(row, "hub"),
        preset=_optional_str(row, "preset"),
        command=_command(row),
        template=_optional_str(row, "template"),
        brief=_optional_str(row, "brief"),
    )


def read_events(path: Path) -> list[LedgerEvent]:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return []
    except OSError as e:
        msg = f"台帳を読めない: {path}（{e.strerror}）"
        raise LedgerError(msg) from e
    except UnicodeDecodeError as e:
        msg = f"台帳が UTF-8 ではない: {path}（{e}）"
        raise LedgerError(msg) from e
    events: list[LedgerEvent] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            events.append(_parse(line))
        except (ValueError, TypeError, KeyError) as e:
            msg = f"台帳 {path} の {number} 行目が不正: {e!r}"
            raise LedgerError(msg) from e
    return events
