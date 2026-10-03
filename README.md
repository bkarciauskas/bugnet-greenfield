# bugnet-greenfield

Greenfield .NET 8 rebuild of BugNET (migration dry run). Legacy source: bkarciauskas/bugnet

Discovery notes live in `docs/`. The first slice, creating an issue and the email that follows, is mapped in [docs/soap-create-issue.md](docs/soap-create-issue.md). The .NET 8 layout for that slice is [docs/create-issue-slice-architecture.md](docs/create-issue-slice-architecture.md). Empty `BugNet.Web`, `BugNet.Core`, and `BugNet.Data` projects exist so the build guardrails can run. Create-issue behaviour has not been built.

## Legacy host

The dry-run host is http://15.135.1.105/. The WSDL is http://15.135.1.105/Webservices/BugNetServices.asmx?WSDL. Start the instance with `aws ec2 start-instances --instance-ids i-0a5a720ebfc186d69 --region ap-southeast-2`. The Admin password is in Secrets Manager `bugnet-dryrun/admin-password`. See [docs/legacy-host.md](docs/legacy-host.md). // pragma: allowlist secret

## Guardrails

- `Directory.Build.props` enables nullable reference types, treats warnings as errors, sets `AnalysisLevel` to `latest-all`, and enforces code style in the build. `.editorconfig` sets those analyzer severities, including nullable warnings, to error.
- The Stop hook `.cursor/hooks/stop_tests.py` runs `bash scripts/run-tests.sh` and then `bash scripts/run-dotnet.sh`. The dotnet script runs `dotnet build -warnaserror` and `dotnet test -warnaserror`. A failure blocks the turn. A missing SDK fails closed.
- `tests/BugNet.Architecture.Tests` checks the layers. Core does not reference Web, Data, EF Core, or ASP.NET. Data references Core only, and its EF Core package does not flow compile assets. Web references Core and may reference Data for wiring, not EF Core or Data internals. No project references the legacy host, its stored procedures, the legacy code, or CoreWCF. CoreWCF is not in this repo.
- CI jobs `guardrails`, `build`, `test`, and `architecture` are the checks `main` should require.
- `characterisation-tests/` is protected by `.cursor/hooks/protect_characterisation.py` and by `scripts/check_protected_path.py` in CI. The only override is the pull request label `allow-characterisation-edit` applied by GitHub user `bkarciauskas`.
- New characterisation tests are written in `characterisation-drafts/` until they pass against the legacy host at http://15.135.1.105/ and Ben reviews them. A later pull request moves them into `characterisation-tests/` with his label. See `characterisation-drafts/README.md` and `docs/legacy-host.md`.
- `bash scripts/verify-guardrails.sh` fails closed when a required check is missing. The skill is `.cursor/skills/verify-guardrails/SKILL.md`.
