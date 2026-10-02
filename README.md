# bugnet-greenfield

Greenfield .NET 8 rebuild of BugNET (migration dry run). Legacy source: bkarciauskas/bugnet

Discovery notes live in `docs/`. The first slice, creating an issue and the email that follows, is mapped in [docs/soap-create-issue.md](docs/soap-create-issue.md). The .NET 8 layout for that slice is [docs/create-issue-slice-architecture.md](docs/create-issue-slice-architecture.md). The build has not started.

## Legacy host

The dry-run host is http://15.135.1.105/. The WSDL is http://15.135.1.105/Webservices/BugNetServices.asmx?WSDL. Start the instance with `aws ec2 start-instances --instance-ids i-0a5a720ebfc186d69 --region ap-southeast-2`. The Admin password is in Secrets Manager `bugnet-dryrun/admin-password`. See [docs/legacy-host.md](docs/legacy-host.md). // pragma: allowlist secret

## Guardrails

- The Stop hook `.cursor/hooks/stop_tests.py` blocks the end of a turn when `bash scripts/run-tests.sh` fails, and fails closed if that command cannot run.
- `characterisation-tests/` is protected by `.cursor/hooks/protect_characterisation.py` and by `scripts/check_protected_path.py` in CI. The only override is the pull request label `allow-characterisation-edit` applied by GitHub user `bkarciauskas`.
- New characterisation tests are written in `characterisation-drafts/` until they pass against the legacy host at http://15.135.1.105/ and Ben reviews them. A later pull request moves them into `characterisation-tests/` with his label. See `characterisation-drafts/README.md` and `docs/legacy-host.md`.
- `bash scripts/verify-guardrails.sh` fails closed when a required check is missing. The skill is `.cursor/skills/verify-guardrails/SKILL.md`.
