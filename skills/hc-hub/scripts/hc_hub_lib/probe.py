import json
import os
import re
import secrets
import shlex
from collections.abc import Sequence
from pathlib import Path

from hc_hub_lib.hc_client import HcError, run_hc

# HC_TIMEOUT_SECONDS（30 秒）より短くする。Python 側の打ち切りを先に来させない
PROBE_WAIT_SECONDS = 20

_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")


class ProbeError(Exception):
    pass


def _hc(hc: str, args: list[str]) -> str:
    try:
        return run_hc(hc, args)
    except HcError as e:
        raise ProbeError(str(e)) from e


def _hc_object(hc: str, args: list[str]) -> dict[str, object]:
    out = _hc(hc, args)
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        msg = f"hc {' '.join(args)} の出力が JSON ではない: {e}"
        raise ProbeError(msg) from e
    if not isinstance(payload, dict):
        msg = f"hc {' '.join(args)} の出力が JSON オブジェクトではない"
        raise ProbeError(msg)
    return payload


def _build_script(nonce: str, names: Sequence[str]) -> str:
    # dash の `command -v a b c` は最初の名前しか調べないので、名前ごとに 1 回呼ぶ
    lines = [
        f'if command -v {shlex.quote(n)} >/dev/null 2>&1; then echo "{nonce} {n} 1"; '
        f'else echo "{nonce} {n} 0"; fi'
        for n in names
    ]
    lines.append(f'echo "{nonce} END"')
    lines.append("exit 0")
    return "\n".join(lines) + "\n"


def _parse(output: str, nonce: str, names: Sequence[str]) -> dict[str, bool]:
    prefix = f"{nonce} "
    found: dict[str, bool] = {}
    ends = 0
    for raw in output.splitlines():
        if not raw.startswith(prefix):
            continue
        parts = raw[len(prefix) :].split()
        if parts == ["END"]:
            ends += 1
            continue
        if len(parts) != 2 or parts[1] not in {"0", "1"}:  # noqa: PLR2004
            msg = f"probe の出力の行が読めない: {raw!r}"
            raise ProbeError(msg)
        name, flag = parts
        if name not in names:
            msg = f"probe の出力に未知の名前がある: {name!r}"
            raise ProbeError(msg)
        if name in found:
            msg = f"probe の出力に名前 {name!r} が重複している"
            raise ProbeError(msg)
        found[name] = flag == "1"
    missing = [n for n in names if n not in found]
    if missing:
        msg = f"probe の出力に行が無い名前がある: {missing}"
        raise ProbeError(msg)
    if ends != 1:
        msg = f"probe の出力の END の行が {ends} 回ある（1 回のはず）"
        raise ProbeError(msg)
    return found


def _check_ended(hc: str, address: str) -> None:
    waited = _hc_object(
        hc, ["wait", "--json", address, "--timeout", str(PROBE_WAIT_SECONDS)]
    )
    if (
        waited.get("ended") is not True
        or waited.get("reason") != "exit"
        or waited.get("exit_code") != 0
    ):
        msg = f"probe の端末 {address} が正常に終わらなかった: {waited}"
        raise ProbeError(msg)


def probe_core(hc: str, executables: Sequence[str], cwd: Path) -> dict[str, bool]:
    names = list(executables)
    for n in names:
        if not _NAME_RE.fullmatch(n):
            msg = f"実行ファイル名として扱えない: {n!r}"
            raise ProbeError(msg)
    if len(set(names)) != len(names):
        msg = f"実行ファイル名が重複している: {names}"
        raise ProbeError(msg)
    nonce = secrets.token_hex(8)
    started = _hc_object(
        hc,
        [
            "run",
            "--json",
            "--bg",
            "--no-parent",
            "--name",
            f"hc-hub-probe-{os.getpid()}",
            "--label",
            "hc-hub.role=probe",
            "--cwd",
            str(cwd),
            "--",
            "sh",
            "-c",
            _build_script(nonce, names),
        ],
    )
    address = started.get("address")
    if not isinstance(address, str) or not address:
        msg = f"hc run の応答に address が無い: {started}"
        raise ProbeError(msg)
    try:
        _check_ended(hc, address)
        result = _parse(_hc(hc, ["read", address]), nonce, names)
    except ProbeError as body_error:
        try:
            _hc(hc, ["rm", address])
        except ProbeError as rm_error:
            msg = f"{body_error}（さらに端末 {address} の hc rm も失敗: {rm_error}）"
            raise ProbeError(msg) from body_error
        raise
    try:
        _hc(hc, ["rm", address])
    except ProbeError as rm_error:
        msg = f"probe の端末 {address} を hc rm で消せなかった: {rm_error}"
        raise ProbeError(msg) from rm_error
    return result
