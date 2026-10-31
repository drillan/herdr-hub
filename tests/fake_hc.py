import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from _paths import SCRIPT

_TEMPLATE = """#!{python}
import json
import subprocess
import sys
from pathlib import Path

TERMINALS = json.loads({terminals!r})
LS = json.loads({ls!r})
LOG = Path({log!r})
DIR = LOG.parent
PROBE_PATH = {probe_path!r}
WAIT_OVERRIDE = json.loads({wait_override!r})
READ_OVERRIDE = {read_override!r}
RM_FAILS = {rm_fails!r}
ARGS = sys.argv[1:]

if len(ARGS) == 3 and ARGS[0] == "get" and ARGS[2] == "--json" and ARGS[1] in TERMINALS:
    print(json.dumps(TERMINALS[ARGS[1]]))
elif ARGS and ARGS[0] == "ls":
    print(json.dumps({{"terminals": LS}}))
elif len(ARGS) >= 3 and ARGS[0] == "label":
    with LOG.open("a") as f:
        f.write(" ".join(ARGS[1:]) + "\\n")
    print("{{}}")
elif ARGS and ARGS[0] == "run":
    with (DIR / "run.log").open("a") as f:
        f.write(" ".join(ARGS[1:]) + "\\n")
    i = ARGS.index("--")
    (DIR / "script.sh").write_text(ARGS[i + 3])
    print(json.dumps({{"address": "t90", "agent": "sh"}}))
elif ARGS and ARGS[0] == "wait":
    default = {{"ended": True, "exit_code": 0, "reason": "exit", "signal": None}}
    print(json.dumps(WAIT_OVERRIDE if WAIT_OVERRIDE is not None else default))
elif ARGS and ARGS[0] == "read":
    if READ_OVERRIDE is not None:
        sys.stdout.write(READ_OVERRIDE)
    else:
        proc = subprocess.run(
            ["/bin/sh", str(DIR / "script.sh")],
            capture_output=True,
            text=True,
            env={{"PATH": PROBE_PATH}},
            check=True,
        )
        sys.stdout.write(proc.stdout)
elif ARGS and ARGS[0] == "rm":
    with (DIR / "rm.log").open("a") as f:
        f.write(" ".join(ARGS[1:]) + "\\n")
    if RM_FAILS:
        sys.exit(3)
    print("{{}}")
else:
    msg = "fake: " + " ".join(ARGS)
    print(json.dumps({{"error": {{"kind": "unknown", "message": msg}}}}))
    sys.exit(3)
"""


def make_fake_hc(  # noqa: PLR0913
    tmp_path: Path,
    terminals: dict[str, dict[str, Any]],
    ls: list[dict[str, Any]],
    *,
    probe_path: str | None = None,
    wait_override: dict[str, Any] | None = None,
    read_override: str | None = None,
    rm_fails: bool = False,
) -> Path:
    script = tmp_path / "fake-hc"
    script.write_text(
        _TEMPLATE.format(
            python=sys.executable,
            terminals=json.dumps(terminals),
            ls=json.dumps(ls),
            log=str(tmp_path / "label.log"),
            probe_path=probe_path,
            wait_override=json.dumps(wait_override),
            read_override=read_override,
            rm_fails=rm_fails,
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def run_cli(
    *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "HC_TERMINAL_ID"}
    env.update(env_extra or {})
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
