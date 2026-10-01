#!/usr/bin/env bash
# Fail closed when a required guardrail is missing or cannot run.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."

fail_closed() {
  printf '%s\n' "FAIL CLOSED: required check '$1' is missing and cannot run. Not passing on a skip."
}

required=(
  .cursor/hooks/stop_tests.py
  .cursor/hooks/protect_characterisation.py
  .cursor/hooks.json
  scripts/check_protected_path.py
  scripts/run-tests.sh
  scripts/fixtures/characterisation-touch.diff
  .github/workflows/guardrails.yml
  .cursor/skills/verify-guardrails/SKILL.md
  characterisation-tests/README.md
)

missing=0
for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    fail_closed "$path"
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

for path in .cursor/hooks/stop_tests.py .cursor/hooks/protect_characterisation.py scripts/check_protected_path.py; do
  if ! python3 -m py_compile "$path"; then
    fail_closed "$path"
    exit 1
  fi
done

if ! bash -n scripts/run-tests.sh || ! bash -n scripts/verify-guardrails.sh; then
  fail_closed "scripts/run-tests.sh"
  exit 1
fi

if ! python3 - <<'PY'
import json
import sys

with open(".cursor/hooks.json", encoding="utf-8") as handle:
    config = json.load(handle)
hooks = config.get("hooks") or {}
stop = (hooks.get("stop") or [None])[0]
pre = (hooks.get("preToolUse") or [None])[0]
shell = (hooks.get("beforeShellExecution") or [None])[0]
ok = (
    isinstance(stop, dict)
    and stop.get("command") == "python3 .cursor/hooks/stop_tests.py"
    and stop.get("failClosed") is True
    and stop.get("loop_limit") is None
    and isinstance(pre, dict)
    and pre.get("command") == "python3 .cursor/hooks/protect_characterisation.py"
    and pre.get("failClosed") is True
    and isinstance(shell, dict)
    and shell.get("command") == "python3 .cursor/hooks/protect_characterisation.py"
    and shell.get("failClosed") is True
)
sys.exit(0 if ok else 1)
PY
then
  fail_closed ".cursor/hooks.json"
  exit 1
fi

expect() {
  local label="$1"
  local want="$2"
  local needle="$3"
  local payload="$4"
  shift 4
  local output code
  set +e
  output=$(printf '%s' "$payload" | "$@" 2>&1)
  code=$?
  set -e
  if [[ "$code" -ne "$want" ]] || [[ "$output" != *"$needle"* ]]; then
    fail_closed "$label"
    printf '%s\n' "$output"
    exit 1
  fi
}

expect ".cursor/hooks/stop_tests.py" 0 "{}" '{"status":"completed"}' \
  python3 .cursor/hooks/stop_tests.py --command true
expect ".cursor/hooks/stop_tests.py" 2 "DENY: tests failed" '{"status":"completed"}' \
  python3 .cursor/hooks/stop_tests.py --command false
expect ".cursor/hooks/stop_tests.py" 2 "FAIL CLOSED: test command could not run" '{"status":"completed"}' \
  python3 .cursor/hooks/stop_tests.py --command definitely-missing-guardrail-test-bin
expect ".cursor/hooks/protect_characterisation.py" 2 "Blocked edit to characterisation-tests/" \
  '{"hook_event_name":"preToolUse","tool_name":"Write","tool_input":{"path":"characterisation-tests/README.md"}}' \
  python3 .cursor/hooks/protect_characterisation.py
expect ".cursor/hooks/protect_characterisation.py" 2 "Blocked shell command that would modify characterisation-tests/" \
  '{"hook_event_name":"beforeShellExecution","command":"echo agent >> characterisation-tests/README.md"}' \
  python3 .cursor/hooks/protect_characterisation.py
expect "scripts/check_protected_path.py" 1 "DENY: characterisation-tests/ changed" "" \
  python3 scripts/check_protected_path.py scripts/fixtures/characterisation-touch.diff
expect "scripts/check_protected_path.py" 1 "DENY: characterisation-tests/ changed" "" \
  python3 scripts/check_protected_path.py scripts/fixtures/characterisation-touch.diff --override-actor some-agent

if git rev-parse --verify --quiet origin/main >/dev/null; then
  base=origin/main
elif git rev-parse --verify --quiet main >/dev/null; then
  base=main
else
  fail_closed "characterisation-tests base comparison"
  exit 1
fi

set +e
comparison=$(python3 scripts/check_protected_path.py --base "$base" --head HEAD 2>&1)
code=$?
set -e
if [[ "$code" -ne 0 ]] || [[ "$comparison" != ALLOW:* ]]; then
  fail_closed "scripts/check_protected_path.py"
  printf '%s\n' "$comparison"
  exit 1
fi

printf '%s\n' "$comparison"
exit 0
