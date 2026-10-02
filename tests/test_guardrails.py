#!/usr/bin/env python3
"""Eighteen checks for the stop hook, protected path, and fail-closed verify script."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / ".cursor" / "hooks" / "stop_tests.py"
PROTECT = ROOT / ".cursor" / "hooks" / "protect_characterisation.py"
CHECKER = ROOT / "scripts" / "check_protected_path.py"
FIXTURE = ROOT / "scripts" / "fixtures" / "characterisation-touch.diff"
VERIFY = ROOT / "scripts" / "verify-guardrails.sh"

DENY_PATH = (
    "DENY: characterisation-tests/ changed (characterisation-tests/README.md) without an override. "
    "Only GitHub user bkarciauskas can authorize this, by applying the label "
    "allow-characterisation-edit to the pull request. An agent cannot apply that override itself."
)
INTRO = (
    "ALLOW: characterisation-tests/ does not exist on the base revision yet. "
    "This introduction is the only automatic exception. After it merges, further edits need Ben's label."
)
EDIT_MESSAGE = (
    "Blocked edit to characterisation-tests/ (characterisation-tests/README.md). "
    "Build agents cannot change characterisation tests. "
    "Ben (bkarciauskas) approves an intentional change by adding the label "
    "allow-characterisation-edit on the pull request."
)
SHELL_MESSAGE = (
    "Blocked shell command that would modify characterisation-tests/. "
    "Build agents cannot change characterisation tests."
)
STOP_DENY = (
    "DENY: tests failed, so this turn cannot end. Command `false` exited 1. "
    "Fix the failure and run it again. Do not skip the tests.\n"
)
STOP_MISSING = (
    "FAIL CLOSED: test command could not run (`definitely-missing-guardrail-test-bin` exited 127). "
    "This turn cannot end.\n"
    "/bin/sh: 1: definitely-missing-guardrail-test-bin: not found"
)
VERIFY_MISSING = (
    "FAIL CLOSED: required check '.cursor/hooks/stop_tests.py' is missing and cannot run. "
    "Not passing on a skip."
)

GIT_ENV = os.environ.copy()
GIT_ENV.update(
    {
        "GIT_AUTHOR_NAME": "guardrails",
        "GIT_AUTHOR_EMAIL": "guardrails@example.com",
        "GIT_COMMITTER_NAME": "guardrails",
        "GIT_COMMITTER_EMAIL": "guardrails@example.com",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
)


def run(args: list[str], stdin: str = "", cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = GIT_ENV.copy()
    env.pop("GITHUB_ACTIONS", None)
    env.pop("GITHUB_EVENT_PATH", None)
    return subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
        env=env,
    )


def git(root: Path, *args: str) -> None:
    command = [
        "git",
        "-c",
        "user.name=guardrails",
        "-c",
        "user.email=guardrails@example.com",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "safe.directory=*",
        *args,
    ]
    subprocess.check_call(command, cwd=root, env=GIT_ENV, stdout=subprocess.DEVNULL)


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, env=GIT_ENV).strip()


class GuardrailTests(unittest.TestCase):
    def test_stop_allows_when_command_passes(self) -> None:
        result = run([str(STOP), "--command", "true"], '{"status":"completed"}')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "{}\n")
        self.assertEqual(result.stderr, "")

    def test_stop_denies_when_command_fails(self) -> None:
        result = run([str(STOP), "--command", "false"], '{"status":"completed"}')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout), {"followup_message": STOP_DENY})
        self.assertEqual(result.stderr, "")

    def test_stop_fails_closed_when_command_missing(self) -> None:
        result = run(
            [str(STOP), "--command", "definitely-missing-guardrail-test-bin"],
            '{"status":"completed"}',
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout), {"followup_message": STOP_MISSING})
        self.assertEqual(result.stderr, "")

    def test_stop_fails_closed_on_unreadable_input(self) -> None:
        result = run([str(STOP), "--command", "true"], "not-json")
        self.assertEqual(result.returncode, 2)
        message = json.loads(result.stdout)["followup_message"]
        self.assertIn("FAIL CLOSED:", message)
        self.assertIn("could not run", message)

    def test_edit_denies_protected_write(self) -> None:
        payload = json.dumps(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Write",
                "tool_input": {"path": "characterisation-tests/README.md", "contents": "agent"},
            }
        )
        result = run([str(PROTECT)], payload)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout),
            {"permission": "deny", "user_message": EDIT_MESSAGE, "agent_message": EDIT_MESSAGE},
        )

    def test_edit_allows_unprotected_write(self) -> None:
        payload = json.dumps(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Write",
                "tool_input": {"path": "README.md", "contents": "ok"},
            }
        )
        result = run([str(PROTECT)], payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"permission": "allow"})

    def test_edit_denies_strreplace_delete_and_absolute_path(self) -> None:
        absolute = str(ROOT / "characterisation-tests" / "README.md")
        payloads = [
            {"tool_name": "StrReplace", "tool_input": {"path": "characterisation-tests/README.md"}},
            {"tool_name": "Delete", "tool_input": {"path": "characterisation-tests/README.md"}},
            {"tool_name": "EditNotebook", "tool_input": {"target_notebook": absolute}},
        ]
        for payload in payloads:
            payload["hook_event_name"] = "preToolUse"
            result = run([str(PROTECT)], json.dumps(payload))
            self.assertEqual(result.returncode, 2, payload["tool_name"])
            self.assertEqual(json.loads(result.stdout)["permission"], "deny")

    def test_shell_denies_append_redirect(self) -> None:
        payload = json.dumps(
            {
                "hook_event_name": "beforeShellExecution",
                "command": "echo agent >> characterisation-tests/README.md",
                "cwd": str(ROOT),
            }
        )
        result = run([str(PROTECT)], payload)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout),
            {"permission": "deny", "user_message": SHELL_MESSAGE, "agent_message": SHELL_MESSAGE},
        )

    def test_shell_allows_read_and_unrelated_write(self) -> None:
        commands = [
            "cat characterisation-tests/README.md",
            "echo hi > /tmp/out",
            "cp characterisation-tests/README.md /tmp/out",
            "git diff characterisation-tests/README.md",
        ]
        for command in commands:
            payload = json.dumps(
                {"hook_event_name": "beforeShellExecution", "command": command, "cwd": str(ROOT)}
            )
            result = run([str(PROTECT)], payload)
            self.assertEqual(result.returncode, 0, command)
            self.assertEqual(json.loads(result.stdout)["permission"], "allow", command)

    def test_shell_denies_cd_redirect_tee_and_rm(self) -> None:
        commands = [
            "cd characterisation-tests && echo agent >> README.md",
            "echo agent | tee characterisation-tests/README.md",
            "rm -rf characterisation-tests",
            'python3 -c \'open("characterisation-tests/README.md","w").write("x")\'',
        ]
        for command in commands:
            payload = json.dumps(
                {"hook_event_name": "beforeShellExecution", "command": command, "cwd": str(ROOT)}
            )
            result = run([str(PROTECT)], payload)
            self.assertEqual(result.returncode, 2, command)
            self.assertEqual(json.loads(result.stdout)["user_message"], SHELL_MESSAGE, command)

    def test_fixture_diff_denied_without_override(self) -> None:
        result = run([str(CHECKER), str(FIXTURE)])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, DENY_PATH + "\n")

    def test_fixture_diff_denied_for_other_actor(self) -> None:
        result = run([str(CHECKER), str(FIXTURE), "--override-actor", "some-agent"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, DENY_PATH + "\n")

    def test_edit_denies_new_file_in_protected_tree(self) -> None:
        payload = json.dumps(
            {
                "hook_event_name": "preToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "path": "characterisation-tests/CreateIssueTests.cs",
                    "contents": "new test",
                },
            }
        )
        result = run([str(PROTECT)], payload)
        self.assertEqual(result.returncode, 2)
        message = json.loads(result.stdout)["user_message"]
        self.assertIn("characterisation-tests/CreateIssueTests.cs", message)
        self.assertTrue(message.startswith("Blocked edit to characterisation-tests/"))
        shell = run(
            [str(PROTECT)],
            json.dumps(
                {
                    "hook_event_name": "beforeShellExecution",
                    "command": "touch characterisation-tests/CreateIssueTests.cs",
                    "cwd": str(ROOT),
                }
            ),
        )
        self.assertEqual(shell.returncode, 2)
        self.assertEqual(json.loads(shell.stdout)["user_message"], SHELL_MESSAGE)

    def test_edit_and_shell_allow_draft_writes(self) -> None:
        write = run(
            [str(PROTECT)],
            json.dumps(
                {
                    "hook_event_name": "preToolUse",
                    "tool_name": "Write",
                    "tool_input": {
                        "path": "characterisation-drafts/CreateIssueTests.cs",
                        "contents": "draft",
                    },
                }
            ),
        )
        self.assertEqual(write.returncode, 0)
        self.assertEqual(json.loads(write.stdout), {"permission": "allow"})
        shell = run(
            [str(PROTECT)],
            json.dumps(
                {
                    "hook_event_name": "beforeShellExecution",
                    "command": "echo draft >> characterisation-drafts/CreateIssueTests.cs",
                    "cwd": str(ROOT),
                }
            ),
        )
        self.assertEqual(shell.returncode, 0)
        self.assertEqual(json.loads(shell.stdout), {"permission": "allow"})

    def test_fixture_new_file_denied_and_draft_diff_allowed(self) -> None:
        new_file = run([str(CHECKER), str(ROOT / "scripts/fixtures/characterisation-new-file.diff")])
        self.assertEqual(new_file.returncode, 1)
        self.assertIn("characterisation-tests/CreateIssueTests.cs", new_file.stdout)
        self.assertTrue(new_file.stdout.startswith("DENY:"))
        draft = run([str(CHECKER), str(ROOT / "scripts/fixtures/characterisation-draft.diff")])
        self.assertEqual(draft.returncode, 0)
        self.assertEqual(draft.stdout, "ALLOW: characterisation-tests/ is unchanged.\n")

    def test_fixture_diff_allowed_for_approver(self) -> None:
        result = run([str(CHECKER), str(FIXTURE), "--override-actor", "bkarciauskas"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("ALLOW:", result.stdout)
        self.assertIn("bkarciauskas", result.stdout)

    def test_introduction_allowed_when_absent_on_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            (root / "README.md").write_text("greenfield\n")
            base = commit_all(root, "base")
            protected = root / "characterisation-tests"
            protected.mkdir()
            (protected / "README.md").write_text("protected\n")
            head = commit_all(root, "introduce")
            result = run(
                [str(CHECKER), "--base", base, "--head", head],
                cwd=root,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, INTRO + "\n")

    def test_existing_tree_change_denied_without_override(self) -> None:
        root, base, head = self.changed_tree()
        denied = run([str(CHECKER), "--base", base, "--head", head], cwd=root)
        self.assertEqual(denied.returncode, 1)
        self.assertEqual(denied.stdout, DENY_PATH + "\n")
        other = run(
            [str(CHECKER), "--base", base, "--head", head, "--override-actor", "some-agent"],
            cwd=root,
        )
        self.assertEqual(other.returncode, 1)
        self.assertEqual(other.stdout, DENY_PATH + "\n")
        same = run([str(CHECKER), "--base", base, "--head", base], cwd=root)
        self.assertEqual(same.returncode, 0)
        self.assertEqual(same.stdout, "ALLOW: characterisation-tests/ is unchanged.\n")

    def test_existing_tree_change_allowed_for_approver(self) -> None:
        root, base, head = self.changed_tree()
        result = run(
            [str(CHECKER), "--base", base, "--head", head, "--override-actor", "bkarciauskas"],
            cwd=root,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("applied by GitHub user bkarciauskas", result.stdout)

    def test_verify_fails_closed_when_stop_hook_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "repo"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            (copy / ".cursor" / "hooks" / "stop_tests.py").unlink()
            result = run(["bash", str(copy / "scripts" / "verify-guardrails.sh")], cwd=copy)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, VERIFY_MISSING + "\n")

    def test_verify_passes_and_hooks_fail_closed(self) -> None:
        config = json.loads((ROOT / ".cursor" / "hooks.json").read_text())
        stop = config["hooks"]["stop"][0]
        pre = config["hooks"]["preToolUse"][0]
        shell = config["hooks"]["beforeShellExecution"][0]
        self.assertEqual(stop["command"], "python3 .cursor/hooks/stop_tests.py")
        self.assertTrue(stop["failClosed"])
        self.assertIsNone(stop["loop_limit"])
        self.assertTrue(pre["failClosed"])
        self.assertTrue(shell["failClosed"])
        result = run(["bash", str(VERIFY)], cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("ALLOW:"))

    def changed_tree(self) -> tuple[Path, str, str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        git(root, "init", "-q", "-b", "main")
        protected = root / "characterisation-tests"
        protected.mkdir()
        readme = protected / "README.md"
        readme.write_text("protected\n")
        base = commit_all(root, "base")
        readme.write_text("protected\nagent\n")
        head = commit_all(root, "change")
        return root, base, head


if __name__ == "__main__":
    unittest.main()
