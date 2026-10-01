#!/usr/bin/env python3
"""CI check for characterisation-tests/. Fail closed if the check cannot run.

The only override is the pull request label allow-characterisation-edit applied
by GitHub user bkarciauskas. Any other actor, including an agent, is denied.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROTECTED = "characterisation-tests"
LABEL = "allow-characterisation-edit"
APPROVER = "bkarciauskas"
INTRO = (
    "ALLOW: characterisation-tests/ does not exist on the base revision yet. "
    "This introduction is the only automatic exception. After it merges, further edits need Ben's label."
)
DENY = (
    "DENY: characterisation-tests/ changed ({files}) without an override. "
    "Only GitHub user bkarciauskas can authorize this, by applying the label "
    "allow-characterisation-edit to the pull request. An agent cannot apply that override itself."
)


def fail_closed(detail: str) -> None:
    print(f"FAIL CLOSED: {detail} Not passing on a skip.")
    raise SystemExit(1)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def rev_exists(rev: str) -> bool:
    return run_git(["rev-parse", "--verify", "--quiet", rev]).returncode == 0


def tree_exists(rev: str) -> bool:
    result = run_git(["cat-file", "-t", f"{rev}:{PROTECTED}"])
    return result.returncode == 0 and result.stdout.strip() == "tree"


def is_protected(path: str) -> bool:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith(("a/", "b/")):
        normalized = normalized[2:]
    if normalized == "/dev/null":
        return False
    return normalized == PROTECTED or normalized.startswith(f"{PROTECTED}/")


def paths_in_diff(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        candidates: list[str] = []
        if line.startswith("diff --git "):
            for part in line[len("diff --git ") :].split(" "):
                if part.startswith(("a/", "b/")):
                    candidates.append(part[2:])
        elif line.startswith(("+++ ", "--- ")):
            path = line[4:].strip()
            if path.startswith(("a/", "b/")):
                path = path[2:]
            candidates.append(path)
        for path in candidates:
            if is_protected(path) and path not in seen:
                seen.add(path)
                found.append(path)
    return found


def git_changed(base: str, head: str) -> list[str]:
    result = run_git(["diff", "--name-only", f"{base}...{head}"])
    if result.returncode != 0:
        detail = (result.stderr or "git diff failed").strip()
        fail_closed(f"could not compare {base} and {head} ({detail}).")
    changed: list[str] = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if is_protected(path):
            changed.append(path)
    return changed


def github_pages(url: str, token: str) -> list[dict]:
    items: list[dict] = []
    next_url: str | None = url
    pages = 0
    while next_url and pages < 10:
        pages += 1
        request = urllib.request.Request(
            next_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "bugnet-guardrails",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
            link = response.headers.get("Link")
        if not isinstance(body, list):
            break
        items.extend(item for item in body if isinstance(item, dict))
        next_url = None
        if link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
    return items


def latest_label_actor(repo: str, number: int, token: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}/issues/{number}/events?per_page=100"
    latest = None
    for event in github_pages(url, token):
        label = event.get("label") or {}
        if label.get("name") != LABEL:
            continue
        if event.get("event") not in {"labeled", "unlabeled"}:
            continue
        latest = event
    if not latest or latest.get("event") != "labeled":
        return None
    actor = latest.get("actor") or {}
    login = actor.get("login")
    return login if isinstance(login, str) else None


def load_event() -> dict:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        fail_closed("GitHub event payload is missing, so the label actor cannot be verified.")
    try:
        return json.loads(Path(event_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail_closed(f"could not read the GitHub event payload ({exc}).")
    return {}


def actor_from_event(event: dict) -> tuple[str | None, bool]:
    """Return (actor, label_is_present)."""
    pull = event.get("pull_request") or {}
    labels = []
    for item in pull.get("labels") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            labels.append(item["name"])
    action = event.get("action")
    sender = (event.get("sender") or {}).get("login")
    label_name = (event.get("label") or {}).get("name")
    if action == "labeled" and label_name == LABEL and isinstance(sender, str):
        return sender, True
    if action == "unlabeled" and label_name == LABEL:
        return None, False
    return None, LABEL in labels


def override_actor(explicit: str | None) -> str | None:
    if explicit is not None:
        return explicit
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None

    event = load_event()
    actor, label_present = actor_from_event(event)
    if actor:
        return actor
    if not label_present:
        return None

    pull = event.get("pull_request") or {}
    repo = os.environ.get("GITHUB_REPOSITORY")
    number = pull.get("number")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not repo or not isinstance(number, int) or not token:
        fail_closed(
            "allow-characterisation-edit is present but the actor who applied it cannot be verified."
        )
    try:
        return latest_label_actor(repo, number, token)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        fail_closed(f"could not verify who applied allow-characterisation-edit ({exc}).")
    return None


def allow_override(files: str) -> None:
    print(
        "ALLOW: characterisation-tests/ changed "
        f"({files}) with override label allow-characterisation-edit "
        f"applied by GitHub user {APPROVER}."
    )
    raise SystemExit(0)


def decide(changed: list[str], actor: str | None) -> None:
    if not changed:
        print("ALLOW: characterisation-tests/ is unchanged.")
        raise SystemExit(0)
    files = ", ".join(sorted(changed))
    if actor == APPROVER:
        allow_override(files)
    print(DENY.format(files=files))
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("diff_path", nargs="?")
    parser.add_argument("--diff")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--override-actor", default=None)
    args = parser.parse_args()

    diff_path = args.diff or args.diff_path
    if diff_path:
        try:
            text = Path(diff_path).read_text()
        except OSError as exc:
            fail_closed(f"could not read diff {diff_path} ({exc}).")
        decide(paths_in_diff(text), override_actor(args.override_actor))

    if not args.base or not args.head:
        fail_closed("no diff or --base/--head was provided.")
    if not rev_exists(args.base) or not rev_exists(args.head):
        fail_closed(f"could not resolve base {args.base!r} or head {args.head!r}.")
    if not tree_exists(args.base):
        print(INTRO)
        raise SystemExit(0)
    decide(git_changed(args.base, args.head), override_actor(args.override_actor))


if __name__ == "__main__":
    main()
