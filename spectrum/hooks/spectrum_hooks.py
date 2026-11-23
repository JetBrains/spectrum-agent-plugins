#!/usr/bin/env python3
"""Claude Code hooks for the Spectrum plugin: the project check, a prompt reminder and the
consult gate.

`session-check` (SessionStart) names this repository's folder and git remotes and tells the
agent to confirm, before its first Spectrum call, that a Spectrum project is this
repository's. `prompt-hint` (UserPromptSubmit) adds one reminder beside each prompt.
`consult-gate` (PreToolUse, opt-in) refuses one code search or read once several have gone
by with no Spectrum call, at most once per time window. Hook JSON arrives on stdin, the
answer goes to stdout, and every path exits 0: a hook failure must never stop the session.
Standard library only, no network.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PROMPT_HINT = (
    "When Spectrum's MCP tools (query_knowledge and its graph tools) are available, they "
    "hold a project's knowledge graph: requirements, business rules, features, design "
    "decisions and which code realizes them. Once the Spectrum project is confirmed to be "
    "this repository's, as the session-start check describes, ask Spectrum about any "
    "question this task has about intent, impact, which code realizes a feature, or a "
    "business rule before reading code, then confirm in the source what it tells you."
)

NOT_CONFIRMED_MARKER = "SPECTRUM PROJECT NOT CONFIRMED:"

SESSION_CHECK = (
    "Spectrum project check. Spectrum's answers describe one Spectrum project, and an "
    "argless call can land on a project that is not this repository's, so its answers "
    "would describe another system. Before your first call to a Spectrum tool in this "
    "session, make sure the project is this repository's: {repository}\n"
    "- When the prompt, CLAUDE.md or AGENTS.md gives a project_id, the user chose it: "
    "pass it.\n"
    "- Otherwise call list_projects and compare each project's name with the folder and "
    "remote names above. When one project's name plainly names this repository, pass its "
    "id as project_id on every Spectrum call.\n"
    "- When no name plainly matches, stop the task before any other Spectrum call. Begin "
    f"your reply with `{NOT_CONFIRMED_MARKER}`, name this repository and the projects "
    "list_projects returned, and ask the user which project belongs to this repository, "
    "or whether none does. Continue only on their answer. A run nobody can answer, such "
    "as `claude --print` or `codex exec`, ends with that reply; the user re-runs it with "
    "the project's id in the prompt."
)

_URL_CREDENTIALS = re.compile(r"(?<=://)[^/@]+@")
_GIT_TIMEOUT_SECONDS = 5


def _git(directory: str, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", directory, *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def describe_repository(directory: str) -> str:
    root = _git(directory, "rev-parse", "--show-toplevel") or directory
    configured = _git(root, "config", "--get-regexp", r"^remote\..*\.url$")
    remotes = sorted(
        {
            _URL_CREDENTIALS.sub("", line.split(maxsplit=1)[1])
            for line in configured.splitlines()
            if len(line.split(maxsplit=1)) == 2
        }
    )
    folder = f"this session works in the folder `{os.path.basename(root)}` ({root})"
    if not remotes:
        return f"{folder}, which has no git remote."
    return f"{folder}, whose git remotes are {', '.join(remotes)}."


def session_check(payload: Mapping[str, Any], working_directory: str) -> dict[str, Any]:
    directory = str(payload.get("cwd") or working_directory)
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": SESSION_CHECK.format(
                repository=describe_repository(directory)
            ),
        }
    }


SPECTRUM_TOOL = re.compile(
    r"^mcp__.+__(query_knowledge|graph_seed_by_query|graph_subgraph|graph_expand|source_quotes)$"
)
CODE_READING_TOOLS = frozenset({"Read", "Grep", "Glob"})
# Bash counts only when it searches or reads files; a build or a test run asks no question Spectrum could answer.
SEARCH_COMMANDS = frozenset(
    "grep egrep fgrep rg ag ack find fd cat head tail less more tree sed nl".split()
)
_SEGMENT_SPLIT = re.compile(r"\|\|?|&&|;|\n")
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

DEFAULT_AFTER = 3
DEFAULT_WINDOW_SECONDS = 120.0


def prompt_hint(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt or prompt.startswith("/"):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": PROMPT_HINT,
        }
    }


def _words(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def is_search_command(command: str) -> bool:
    for segment in _SEGMENT_SPLIT.split(command):
        words = [w for w in _words(segment) if not _ENV_ASSIGNMENT.match(w)]
        if not words:
            continue
        name = os.path.basename(words[0])
        if name in SEARCH_COMMANDS:
            return True
        if name == "git" and len(words) > 1 and words[1] in {"grep", "ls-files"}:
            return True
    return False


def is_code_reading(tool_name: str, tool_input: Mapping[str, Any]) -> bool:
    if tool_name in CODE_READING_TOOLS:
        return True
    return tool_name == "Bash" and is_search_command(
        str(tool_input.get("command") or "")
    )


def _setting(env: Mapping[str, str], name: str, default: float) -> float:
    for key in (f"SPECTRUM_{name}", f"CLAUDE_PLUGIN_OPTION_{name}"):
        raw = env.get(key, "").strip()
        if raw:
            try:
                return float(raw)
            except ValueError:
                break
    return default


def deny_reason(after: int) -> str:
    return (
        f"Spectrum has not been consulted during the last {after} code searches. Call "
        "Spectrum's query_knowledge tool with one focused question about this task — why "
        "something exists, what depends on it, which code realizes a feature, or which "
        "business rule applies — then continue reading the source."
    )


class GateState:
    """Per-session counter of code searches since the last Spectrum call, and the time of
    the last refusal. Parallel tool calls run their hooks concurrently, so every
    read-modify-write holds an exclusive lock on the state file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def update(self, step: Any) -> Any:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            try:
                state = json.loads(handle.read() or "{}")
            except ValueError:
                state = {}
            result = step(state)
            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(state))
            return result


def state_path(payload: Mapping[str, Any], env: Mapping[str, str]) -> Path:
    directory = env.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        tempfile.gettempdir(), "spectrum-agent-plugin"
    )
    session = re.sub(
        r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id") or "unknown")
    )
    return Path(directory) / f"consult-gate-{session}.json"


def consult_gate(
    payload: Mapping[str, Any], env: Mapping[str, str], now: float
) -> dict[str, Any] | None:
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    consulted = bool(SPECTRUM_TOOL.match(tool_name))
    if not consulted and not is_code_reading(tool_name, tool_input):
        return None

    after = max(1, int(_setting(env, "CONSULT_GATE_AFTER", DEFAULT_AFTER)))
    window = max(
        0.0, _setting(env, "CONSULT_GATE_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS)
    )

    def step(state: dict[str, Any]) -> bool:
        if consulted:
            state["since_consult"] = 0
            return False
        since = int(state.get("since_consult", 0))
        last_denial = float(state.get("last_denial", float("-inf")))
        if since >= after and now - last_denial >= window:
            state["since_consult"] = 0
            state["last_denial"] = now
            return True
        state["since_consult"] = since + 1
        return False

    if not GateState(state_path(payload, env)).update(step):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason(after),
        }
    }


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        command = argv[1] if len(argv) > 1 else ""
        if command == "session-check":
            output = session_check(payload, os.getcwd())
        elif command == "prompt-hint":
            output = prompt_hint(payload)
        elif command == "consult-gate":
            output = consult_gate(payload, os.environ, time.time())
        else:
            return 0
        if output is not None:
            sys.stdout.write(json.dumps(output))
    except Exception as exc:  # noqa: BLE001 - a hook must never fail the session
        sys.stderr.write(f"spectrum plugin hook skipped: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
