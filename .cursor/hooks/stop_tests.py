#!/usr/bin/env python3
"""Stop hook. Block the end of a turn when tests fail. Fail closed if they cannot run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMAND = "bash scripts/run-tests.sh"
CANNOT_RUN = {126, 127}


def emit_followup(message: str) -> None:
    print(json.dumps({"followup_message": message}))
    raise SystemExit(2)


def fail_closed(command: str, code: int, detail: str) -> None:
    message = (
        f"FAIL CLOSED: test command could not run (`{command}` exited {code}). "
        "This turn cannot end."
    )
    detail = detail.strip()
    if detail:
        message = f"{message}\n{detail}"
    else:
        message = f"{message}\n"
    emit_followup(message)


def deny_failed(command: str, code: int) -> None:
    emit_followup(
        "DENY: tests failed, so this turn cannot end. "
        f"Command `{command}` exited {code}. "
        "Fix the failure and run it again. Do not skip the tests.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    args = parser.parse_args()

    raw = sys.stdin.read()
    if raw.strip():
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            emit_followup(
                "FAIL CLOSED: stop hook could not read its input, so the tests "
                "could not run. This turn cannot end.\n"
            )

    os.chdir(ROOT)
    command = args.command
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        fail_closed(command, 127, str(exc))

    if result.returncode == 0:
        print("{}")
        raise SystemExit(0)

    if result.returncode in CANNOT_RUN:
        fail_closed(command, result.returncode, result.stderr or result.stdout or "")

    deny_failed(command, result.returncode)


if __name__ == "__main__":
    main()
