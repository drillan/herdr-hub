import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hc_hub_lib.catalog import KNOWN_AGENTS

VERDICTS = ("available", "shell_only", "shell_alias", "missing")


def classify(found_in_core: bool, shell_output: str) -> str:  # noqa: FBT001
    if found_in_core:
        return "available"
    if shell_output.startswith("/"):
        return "shell_only"
    if not shell_output:
        return "missing"
    return "shell_alias"


def _fix(verdict: str, shell_output: str) -> str | None:
    if verdict == "shell_only":
        directory = shlex.quote(str(Path(shell_output).parent))
        return f"hc の core の PATH に {directory} を足す"
    if verdict == "shell_alias":
        return "シェルの alias・関数ではなく、実行ファイルを hc の core の PATH に置く"
    return None


def detect_report(
    core: Mapping[str, bool], shell: Mapping[str, str], shell_path: Path
) -> dict[str, Any]:
    agents = []
    for a in KNOWN_AGENTS:
        output = shell[a.executable]
        verdict = classify(core[a.executable], output)
        agents.append(
            {
                "name": a.name,
                "verdict": verdict,
                "shell_output": output,
                "argv": list(a.argv),
                "status_report": a.status_report,
                "first_task": a.first_task,
                "note": a.note,
                "fix": _fix(verdict, output),
            }
        )
    return {"login_shell": str(shell_path), "agents": agents}
