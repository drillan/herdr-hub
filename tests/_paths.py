import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills/hc-hub"
REFS = SKILL_DIR / "references"
SCRIPT = SKILL_DIR / "scripts/hc-hub"
DISCIPLINE_MAP = ROOT / "docs/superpowers/notes/2026-10-31-hc-hub-discipline-map.md"
SHARED = ("adjudication.md", "escalation.md", "worktrees.md")
HERDR1 = re.compile(
    r"\bherdr (agent|pane|tab|session|workspace)\b"
    r"|HERDR_[A-Z_]+|SendMessage|codex queue"
)
