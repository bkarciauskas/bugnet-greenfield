# bugnet-greenfield
Greenfield .NET 8 rebuild of BugNET (migration dry run). Legacy source: bkarciauskas/bugnet

## Guardrails

- The Stop hook `.cursor/hooks/stop_tests.py` blocks the end of a turn when `bash scripts/run-tests.sh` fails, and fails closed if that command cannot run.
- `characterisation-tests/` is protected by `.cursor/hooks/protect_characterisation.py` and by `scripts/check_protected_path.py` in CI. The only override is the pull request label `allow-characterisation-edit` applied by GitHub user `bkarciauskas`.
- `bash scripts/verify-guardrails.sh` fails closed when a required check is missing. The skill is `.cursor/skills/verify-guardrails/SKILL.md`.
