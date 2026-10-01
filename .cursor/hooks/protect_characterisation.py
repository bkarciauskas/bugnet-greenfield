#!/usr/bin/env python3
"""Deny edits and shell writes under characterisation-tests/. Fail closed on bad input."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

PROTECTED = "characterisation-tests"
EDIT_MESSAGE = (
    "Blocked edit to characterisation-tests/ ({path}). "
    "Build agents cannot change characterisation tests. "
    "Ben (bkarciauskas) approves an intentional change by adding the label "
    "allow-characterisation-edit on the pull request."
)
SHELL_MESSAGE = (
    "Blocked shell command that would modify characterisation-tests/. "
    "Build agents cannot change characterisation tests."
)
CLOSED_MESSAGE = (
    "FAIL CLOSED: characterisation guard could not read its input. "
    "Not passing on a skip."
)
EDIT_TOOLS = {"Write", "StrReplace", "Delete", "EditNotebook", "ApplyPatch", "Edit"}
SHELL_TOOLS = {"Shell", "shell"}
PATH_KEYS = (
    "path",
    "file_path",
    "target_notebook",
    "notebook_path",
    "target_file",
    "file",
)
DEST_ONLY = {"cp", "install", "ln", "rsync"}
ANY_PATH = {
    "rm",
    "rmdir",
    "mv",
    "touch",
    "mkdir",
    "truncate",
    "chmod",
    "chown",
    "unlink",
    "shred",
    "tee",
}
GIT_WRITERS = {"checkout", "restore", "reset", "rm", "mv", "apply", "am", "clean", "switch"}
INTERPRETERS = {
    "python",
    "python3",
    "python2",
    "perl",
    "ruby",
    "node",
    "deno",
    "php",
}
WRITE_SNIPPET = re.compile(
    r"write_text|write_bytes|os\.remove|os\.unlink|shutil\.rmtree|Path\.unlink|"
    r"mkdir|open\(\s*[^)]*['\"][wax+]",
    re.IGNORECASE,
)
REDIR_TOKEN = re.compile(r"^(?:\d*>{1,2}|&>{1,2}|>\|)(.*)$")


def emit_deny(message: str) -> None:
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": message,
                "agent_message": message,
            }
        )
    )
    raise SystemExit(2)


def emit_allow() -> None:
    print(json.dumps({"permission": "allow"}))
    raise SystemExit(0)


def fail_closed() -> None:
    emit_deny(CLOSED_MESSAGE)


def is_protected(path: str, cwd: str) -> bool:
    if not path or path == "/dev/null":
        return False
    candidate = path
    if not os.path.isabs(path):
        candidate = os.path.join(cwd or ".", path)
    parts = [part for part in os.path.normpath(candidate).split(os.sep) if part not in ("", ".")]
    return PROTECTED in parts


def path_is_protected(path: str) -> bool:
    normalized = os.path.normpath(path.replace("\\", "/"))
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    return PROTECTED in parts


def split_segments(command: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(command):
        char = command[i]
        if char == "'" and not in_double:
            in_single = not in_single
            buf.append(char)
            i += 1
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            buf.append(char)
            i += 1
            continue
        if not in_single and not in_double and (command.startswith("&&", i) or command.startswith("||", i)):
            parts.append("".join(buf))
            buf = []
            i += 2
            continue
        if not in_single and not in_double and char in "|;":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(char)
        i += 1
    parts.append("".join(buf))
    return [part.strip() for part in parts if part.strip()]


def positional(tokens: list[str]) -> list[str]:
    args = tokens[1:]
    if "--" in args:
        index = args.index("--")
        head = [arg for arg in args[:index] if not arg.startswith("-")]
        return head + args[index + 1 :]
    return [arg for arg in args if not arg.startswith("-")]


def basename(token: str) -> str:
    return os.path.basename(token)


def redirect_hits(tokens: list[str], cwd: str) -> bool:
    for index, token in enumerate(tokens):
        if token in {">", ">>", ">|", "&>", "&>>"} or re.fullmatch(r"\d*>&?", token):
            if index + 1 < len(tokens) and is_protected(tokens[index + 1], cwd):
                return True
            continue
        match = REDIR_TOKEN.fullmatch(token)
        if match and match.group(1) and is_protected(match.group(1), cwd):
            return True
    return False


def tokens_modify(tokens: list[str], segment: str, cwd: str) -> bool:
    if not tokens:
        return False
    command = basename(tokens[0])
    paths = positional(tokens)
    if command == "cd":
        return False
    if redirect_hits(tokens, cwd):
        return True
    if command in ANY_PATH:
        return any(is_protected(path, cwd) for path in paths)
    if command in DEST_ONLY and paths:
        return is_protected(paths[-1], cwd)
    if command == "dd":
        for arg in tokens[1:]:
            if arg.startswith("of=") and is_protected(arg[3:], cwd):
                return True
        return False
    if command in {"sed", "perl"} and any(arg == "-i" or arg.startswith("-i") or arg == "--in-place" for arg in tokens):
        return any(is_protected(path, cwd) for path in paths)
    if command in INTERPRETERS and PROTECTED in segment and WRITE_SNIPPET.search(segment):
        return True
    if command == "git":
        sub = next((arg for arg in tokens[1:] if not arg.startswith("-")), "")
        if sub in GIT_WRITERS:
            if any(is_protected(path, cwd) for path in paths):
                return True
            if sub in {"apply", "am", "clean"} and PROTECTED in segment:
                return True
    return False


def command_modifies_protected(command: str, cwd: str) -> bool:
    current = cwd or os.getcwd()
    for segment in split_segments(command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            if PROTECTED in segment:
                return True
            continue
        if not tokens:
            continue
        if basename(tokens[0]) == "cd" and len(tokens) >= 2 and tokens[1] != "-":
            target = tokens[1]
            current = target if os.path.isabs(target) else os.path.normpath(os.path.join(current, target))
            continue
        if tokens_modify(tokens, segment, current):
            return True
    return False


def as_dict(value: object) -> dict | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None
    return {}


def protected_edit_path(tool_name: str, tool_input: dict) -> str | None:
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and path_is_protected(value):
            return value
    if tool_name in {"ApplyPatch", "Edit"}:
        blob = json.dumps(tool_input)
        if f"{PROTECTED}/" in blob or f"/{PROTECTED}" in blob:
            return f"{PROTECTED}/"
    return None


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        fail_closed()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        fail_closed()
    if not isinstance(payload, dict):
        fail_closed()

    event = payload.get("hook_event_name")
    tool_name = payload.get("tool_name")
    if event == "beforeShellExecution" or tool_name in SHELL_TOOLS:
        command = payload.get("command") if isinstance(payload.get("command"), str) else ""
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else os.getcwd()
        if tool_name in SHELL_TOOLS:
            tool_input = as_dict(payload.get("tool_input"))
            if tool_input is None:
                fail_closed()
            command = tool_input.get("command", command)
            cwd = tool_input.get("working_directory") or tool_input.get("cwd") or cwd
        if isinstance(command, str) and command_modifies_protected(command, str(cwd)):
            emit_deny(SHELL_MESSAGE)
        emit_allow()

    if tool_name not in EDIT_TOOLS and event not in {None, "preToolUse"}:
        emit_allow()
    if event == "preToolUse" and tool_name not in EDIT_TOOLS:
        emit_allow()

    tool_input = as_dict(payload.get("tool_input"))
    if tool_input is None:
        fail_closed()
    path = protected_edit_path(str(tool_name or ""), tool_input)
    if path:
        emit_deny(EDIT_MESSAGE.format(path=path))
    emit_allow()


if __name__ == "__main__":
    main()
