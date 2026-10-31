import argparse
import importlib.machinery
import importlib.util
import re
from pathlib import Path

import pytest
from _paths import SCRIPT, SKILL_DIR
from hc_hub_lib.guard import GUARDED_OPS

INLINE = re.compile(r"`(hc-hub [a-z][^`]*)`")
STOP_TOKENS = {"|", ">", "&&", ";"}
OP_FLAG = "--op"


def _load_parser() -> argparse.ArgumentParser:
    loader = importlib.machinery.SourceFileLoader("hc_hub_entry", str(SCRIPT))
    spec = importlib.util.spec_from_loader("hc_hub_entry", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    parser: argparse.ArgumentParser = module.build_parser()
    return parser


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return dict(action.choices)
    msg = "サブコマンドが無い"
    raise AssertionError(msg)


def _snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            in_fence = not in_fence
        elif in_fence and line.strip().startswith("hc-hub "):
            joined = line.strip()
            while joined.endswith("\\") and index + 1 < len(lines):
                index += 1
                joined = joined[:-1] + " " + lines[index].strip()
            snippets.append(joined)
        elif not in_fence:
            snippets.extend(INLINE.findall(line))
        index += 1
    return snippets


def problems(snippet: str, parser: argparse.ArgumentParser) -> list[str]:
    tokens: list[str] = []
    for raw in snippet.replace("\\|", " ").split():
        if raw in STOP_TOKENS:
            break
        tokens.append(raw.strip("[]"))
    subs = _subparsers(parser)
    command = tokens[1] if len(tokens) > 1 else ""
    if command not in subs:
        return [f"未知のサブコマンド {command!r}"]
    current = subs[command]
    rest = tokens[2:]
    if command == "ledger":
        ledger_subs = _subparsers(current)
        if not rest or rest[0] not in ledger_subs:
            return [f"未知の ledger サブコマンド {rest[:1]!r}"]
        current = ledger_subs[rest[0]]
        rest = rest[1:]
    known = {opt for a in current._actions for opt in a.option_strings}  # noqa: SLF001
    found: list[str] = []
    for i, token in enumerate(rest):
        if token.startswith("--") and token not in known:
            found.append(f"未知のオプション {token}")
        if token == OP_FLAG and i + 1 < len(rest):
            value = rest[i + 1]
            if not value.startswith("<") and value not in GUARDED_OPS:
                found.append(f"--op の値 {value!r} がガード対象外")
    return found


def _markdown_files() -> list[Path]:
    return [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]


def test_every_documented_hc_hub_line_parses_with_the_cli() -> None:
    parser = _load_parser()
    checked = 0
    for path in _markdown_files():
        for snippet in _snippets(path):
            checked += 1
            assert problems(snippet, parser) == [], (path.name, snippet)
    assert checked > 30


@pytest.mark.parametrize(
    "snippet",
    [
        "hc-hub bogus --lane x",
        "hc-hub start --lane x --nope",
        "hc-hub guard --op fly <t>",
        "hc-hub ledger rewrite --lane x",
    ],
)
def test_checker_rejects_bad_lines(snippet: str) -> None:
    assert problems(snippet, _load_parser()) != []
