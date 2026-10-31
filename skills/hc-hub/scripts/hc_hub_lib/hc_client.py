import json
import subprocess
from collections.abc import Mapping
from typing import Any, cast


class HcError(Exception):
    pass


def terminal_id(env: Mapping[str, str]) -> str:
    value = env.get("HC_TERMINAL_ID")
    if not value:
        msg = "HC_TERMINAL_ID が無い。herdr-core の管理下で実行する"
        raise HcError(msg)
    return value


def _error_message(stdout: str, stderr: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stderr.strip() or stdout.strip()
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and "message" in error:
        return str(error["message"])
    if error is not None:
        return str(error)
    return stderr.strip() or stdout.strip()


def run_hc(hc: str, args: list[str]) -> str:
    try:
        proc = subprocess.run(  # noqa: S603
            [hc, *args], capture_output=True, text=True, check=False
        )
    except OSError as e:
        msg = f"{hc} を実行できない: {e}"
        raise HcError(msg) from e
    if proc.returncode != 0:
        detail = _error_message(proc.stdout, proc.stderr)
        msg = f"{hc} {' '.join(args)} が終了コード {proc.returncode} で失敗: {detail}"
        raise HcError(msg)
    return proc.stdout


def hc_json(hc: str, args: list[str]) -> Mapping[str, Any]:
    out = run_hc(hc, args)
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        msg = f"{hc} {' '.join(args)} の出力が JSON ではない: {e}"
        raise HcError(msg) from e
    if not isinstance(payload, dict):
        msg = f"{hc} {' '.join(args)} の出力が JSON オブジェクトではない"
        raise HcError(msg)
    return cast("Mapping[str, Any]", payload)


def get_terminal(hc: str, target: str) -> Mapping[str, Any]:
    return hc_json(hc, ["get", target, "--json"])


def get_labels(hc: str, target: str) -> Mapping[str, str]:
    labels = get_terminal(hc, target).get("labels")
    if not isinstance(labels, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in labels.items()
    ):
        msg = f"hc get {target} の labels が文字列の対応表ではない"
        raise HcError(msg)
    return cast("Mapping[str, str]", labels)
