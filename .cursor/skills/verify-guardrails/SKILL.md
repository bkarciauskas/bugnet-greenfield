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

New tests are written in `characterisation-drafts/` (see its README): write the draft, pass it against http://15.135.1.105/, Ben reviews, then a pull request moves the files into `characterisation-tests/` with his label. The WSDL is http://15.135.1.105/Webservices/BugNetServices.asmx?WSDL. Start the instance with `aws ec2 start-instances --instance-ids i-0a5a720ebfc186d69 --region ap-southeast-2`. The Admin password is in Secrets Manager `bugnet-dryrun/admin-password`. See `docs/legacy-host.md`. Change a locked test the same way. Do not write the locked file yourself. // pragma: allowlist secret
