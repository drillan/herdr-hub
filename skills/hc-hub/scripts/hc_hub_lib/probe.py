import json
import os
import pwd
import re
import secrets
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from hc_hub_lib.hc_client import HC_TIMEOUT_SECONDS, HcError, run_hc

# HC_TIMEOUT_SECONDS（30 秒）より短くする。Python 側の打ち切りを先に来させない
PROBE_WAIT_SECONDS = 20

_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")
# init --abs-path が core に確かめさせる絶対パス。行を空白で区切るため空白は不可
_ABS_PATH_RE = re.compile(r"/[A-Za-z0-9._/+-]+")


class ProbeError(Exception):
    pass


def _hc(hc: str, args: list[str]) -> str:
    try:
        return run_hc(hc, args)
    except HcError as e:
        raise ProbeError(str(e)) from e


def _hc_object(hc: str, args: list[str]) -> dict[str, object]:
    return _parse_object(_hc(hc, args), args)


def _parse_object(out: str, args: list[str]) -> dict[str, object]:
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
    names = _check_names(executables)
    nonce = secrets.token_hex(8)
    probe_name = f"hc-hub-probe-{os.getpid()}"
    run_args = [
        "run",
        "--json",
        "--bg",
        "--no-parent",
        "--name",
        probe_name,
        "--label",
        "hc-hub.role=probe",
        "--cwd",
        str(cwd),
        "--",
        "sh",
        "-c",
        _build_script(nonce, names),
    ]
    run_out = _hc(hc, run_args)
    # 応答を読めないと rm できず端末が残る。名前を添えて探せるようにする
    leftover = (
        f"（端末 {probe_name} が残っているかもしれない。`hc ls` で探して `hc rm` する）"
    )
    try:
        started = _parse_object(run_out, run_args)
    except ProbeError as e:
        msg = f"{e}{leftover}"
        raise ProbeError(msg) from e
    address = started.get("address")
    if not isinstance(address, str) or not address:
        msg = f"hc run の応答に address が無い: {started}{leftover}"
        raise ProbeError(msg)
    rm_error: ProbeError | None = None
    try:
        _check_ended(hc, address)
        result = _parse(_hc(hc, ["read", address]), nonce, names)
    except BaseException as body_error:
        # 本体の例外を優先し、rm の失敗は添えるだけにする
        try:
            _hc(hc, ["rm", address])
        except ProbeError as e:
            note = f"さらに端末 {address} の hc rm も失敗: {e}"
            if isinstance(body_error, ProbeError):
                msg = f"{body_error}（{note}）"
                raise ProbeError(msg) from body_error
            body_error.add_note(note)
        raise
    try:
        _hc(hc, ["rm", address])
    except ProbeError as e:
        rm_error = e
    if rm_error is not None:
        msg = f"probe の端末 {address} を hc rm で消せなかった: {rm_error}"
        raise ProbeError(msg) from rm_error
    return result


SUPPORTED_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})


def _check_names(executables: Sequence[str]) -> list[str]:
    names = list(executables)
    for n in names:
        if not (_NAME_RE.fullmatch(n) or _ABS_PATH_RE.fullmatch(n)):
            msg = f"実行ファイル名・絶対パスとして扱えない: {n!r}"
            raise ProbeError(msg)
    if len(set(names)) != len(names):
        msg = f"実行ファイル名が重複している: {names}"
        raise ProbeError(msg)
    return names


def login_shell() -> Path:
    # SHELL 環境変数は core から受け継いだ値で、普段のシェルとは限らない
    shell = Path(pwd.getpwuid(os.getuid()).pw_shell)
    if shell.name not in SUPPORTED_SHELLS:
        msg = (
            f"ログインシェル {shell} は未対応"
            f"（対応: {', '.join(sorted(SUPPORTED_SHELLS))}）"
        )
        raise ProbeError(msg)
    return shell


def _build_shell_script(nonce: str, names: Sequence[str]) -> str:
    # rc の出力が改行で終わらなくても、印の行が行頭から始まるようにする
    lines = ["printf '\\n'"] + [
        f"printf '%s %s %s\\n' {nonce} {n} "
        f'"$(command -v {shlex.quote(n)} 2>/dev/null)"'
        for n in names
    ]
    lines.append(f"printf '%s END\\n' {nonce}")
    lines.append("exit 0")
    return "\n".join(lines) + "\n"


def _parse_shell(output: str, nonce: str, names: Sequence[str]) -> dict[str, str]:
    prefix = f"{nonce} "
    found: dict[str, str] = {}
    ends = 0
    for raw in output.splitlines():
        if not raw.startswith(prefix):
            continue
        body = raw[len(prefix) :]
        if body == "END":
            ends += 1
            continue
        parts = body.split(" ", 1)
        name = parts[0]
        if name not in names:
            msg = f"対話シェルの出力に未知の名前がある: {name!r}"
            raise ProbeError(msg)
        if name in found:
            msg = f"対話シェルの出力に名前 {name!r} が重複している"
            raise ProbeError(msg)
        found[name] = parts[1].strip() if len(parts) > 1 else ""
    missing = [n for n in names if n not in found]
    if missing:
        msg = f"対話シェルの出力に行が無い名前がある: {missing}"
        raise ProbeError(msg)
    if ends != 1:
        msg = f"対話シェルの出力の END の行が {ends} 回ある（1 回のはず）"
        raise ProbeError(msg)
    return found


def probe_shell(
    shell: Path,
    executables: Sequence[str],
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    names = _check_names(executables)
    nonce = secrets.token_hex(8)
    script = _build_shell_script(nonce, names)
    try:
        proc = subprocess.run(  # noqa: S603
            [str(shell), "-l", "-i", "-c", script],
            stdin=subprocess.DEVNULL,
            # 制御端末を切り離す。打ち切りで子を殺しても前面グループを奪われない
            start_new_session=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=HC_TIMEOUT_SECONDS,
            env=None if env is None else dict(env),
        )
    except subprocess.TimeoutExpired as e:
        msg = f"対話シェル {shell} が {HC_TIMEOUT_SECONDS:g} 秒以内に終わらない"
        raise ProbeError(msg) from e
    except OSError as e:
        msg = f"対話シェル {shell} を実行できない: {e}"
        raise ProbeError(msg) from e
    if proc.returncode != 0:
        msg = f"対話シェル {shell} が終了コード {proc.returncode} で終わった"
        raise ProbeError(msg)
    return _parse_shell(proc.stdout, nonce, names)
