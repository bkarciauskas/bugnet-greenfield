#!/usr/bin/env bash
# Build and test the .NET projects. Fail closed when the SDK is missing.
set -euo pipefail
cd "$(dirname "$0")/.."

export DOTNET_NOLOGO=1
export DOTNET_CLI_TELEMETRY_OPTOUT=1

if ! command -v dotnet >/dev/null 2>&1; then
  if [[ -n "${DOTNET_ROOT:-}" && -x "${DOTNET_ROOT}/dotnet" ]]; then
    export PATH="${DOTNET_ROOT}:${PATH}"
  elif [[ -n "${HOME:-}" && -x "${HOME}/.dotnet/dotnet" ]]; then
    export DOTNET_ROOT="${HOME}/.dotnet"
    export PATH="${DOTNET_ROOT}:${PATH}"
  fi
fi

if ! command -v dotnet >/dev/null 2>&1; then
  printf '%s\n' "FAIL CLOSED: required check 'dotnet' is missing and cannot run. Not passing on a skip."
  exit 127
fi

dotnet build -warnaserror
dotnet test -warnaserror
