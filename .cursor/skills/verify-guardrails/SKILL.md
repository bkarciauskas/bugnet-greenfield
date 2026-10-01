---
name: verify-guardrails
description: Fail-closed check that BugNET greenfield guardrails are present and blocking. Use before ending a turn that changes this repo, and whenever a required hook or CI check might be missing.
---

# Verify guardrails

Run this from the greenfield repo root before ending a turn:

```bash
bash scripts/verify-guardrails.sh
bash scripts/run-tests.sh
```

Both commands must exit 0. If a required hook, script, workflow, or fixture is missing or cannot run, `scripts/verify-guardrails.sh` exits 1 and prints:

```text
FAIL CLOSED: required check '<path>' is missing and cannot run. Not passing on a skip.
```

Do not skip a missing check. Do not treat a skip as a pass.

The Stop hook (`.cursor/hooks/stop_tests.py`) runs `bash scripts/run-tests.sh` when a turn ends. A failing suite blocks the turn. If that command cannot run, the hook fails closed and the turn still cannot end.

`characterisation-tests/` is protected. Do not edit it, do not create a new file in it, and do not shell-redirect into it. The only override is the pull request label `allow-characterisation-edit` applied by GitHub user `bkarciauskas`. Applying that label yourself does not authorize the change. CI (`scripts/check_protected_path.py`, workflow `guardrails`) denies every other actor.

New tests are written in `characterisation-drafts/` (see its README): write the draft, pass it against the legacy BugNET host, Ben reviews, then a pull request moves the files into `characterisation-tests/` with his label. Change a locked test the same way. Do not write the locked file yourself.
