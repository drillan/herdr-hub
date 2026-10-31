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
import sys
from pathlib import Path

TERMINALS = json.loads({terminals!r})
LS = json.loads({ls!r})
LOG = Path({log!r})
ARGS = sys.argv[1:]

if len(ARGS) == 3 and ARGS[0] == "get" and ARGS[2] == "--json" and ARGS[1] in TERMINALS:
    print(json.dumps(TERMINALS[ARGS[1]]))
elif ARGS and ARGS[0] == "ls":
    print(json.dumps({{"terminals": LS}}))
elif len(ARGS) >= 3 and ARGS[0] == "label":
    with LOG.open("a") as f:
        f.write(" ".join(ARGS[1:]) + "\\n")
    print("{{}}")
else:
    msg = "fake: " + " ".join(ARGS)
    print(json.dumps({{"error": {{"kind": "unknown", "message": msg}}}}))
    sys.exit(3)
"""


def make_fake_hc(
    tmp_path: Path, terminals: dict[str, dict[str, Any]], ls: list[dict[str, Any]]
) -> Path:
    script = tmp_path / "fake-hc"
    script.write_text(
        _TEMPLATE.format(
            python=sys.executable,
            terminals=json.dumps(terminals),
            ls=json.dumps(ls),
            log=str(tmp_path / "label.log"),
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
