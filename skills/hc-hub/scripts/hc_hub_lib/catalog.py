from dataclasses import dataclass


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class KnownAgent:
    name: str
    executable: str
    argv: tuple[str, ...]
    status_report: str
    first_task: str
    note: str


UNMEASURED = "未測定"

KNOWN_AGENTS: tuple[KnownAgent, ...] = (
    KnownAgent(
        name="claude",
        executable="claude",
        argv=("claude",),
        status_report="実測済み",
        first_task="位置引数（実測済み）",
        note="",
    ),
    KnownAgent(
        name="opencode",
        executable="opencode",
        argv=("opencode", "--prompt"),
        status_report="実測済み",
        first_task="`--prompt` の値（実測済み）",
        note="位置引数はディレクトリと解釈される",
    ),
    KnownAgent(
        name="devin",
        executable="devin",
        argv=("devin",),
        status_report="実測済み（2026-10-31）",
        first_task="未測定（`hc send` で届くことは実測済み）",
        note="承認待ちの状態と `--permission-mode` を省いたときの挙動は未測定",
    ),
    KnownAgent(
        name="codex",
        executable="codex",
        argv=("codex", "--no-daemon"),
        status_report=UNMEASURED,
        first_task=UNMEASURED,
        note="`--no-daemon` は hc のマニュアル（`hc --skill`）による",
    ),
    KnownAgent(
        name="copilot",
        executable="copilot",
        argv=("copilot",),
        status_report=UNMEASURED,
        first_task=UNMEASURED,
        note="",
    ),
    KnownAgent(
        name="pi",
        executable="pi",
        argv=("pi",),
        status_report=UNMEASURED,
        first_task=UNMEASURED,
        note="",
    ),
)


def find_agent(name: str) -> KnownAgent:
    for agent in KNOWN_AGENTS:
        if agent.name == name:
            return agent
    known = ", ".join(a.name for a in KNOWN_AGENTS)
    msg = f"既知のエージェントに無い名前: {name}（既知: {known}）"
    raise CatalogError(msg)
