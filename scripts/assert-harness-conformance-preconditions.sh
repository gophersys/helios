#!/usr/bin/env bash
#
# scripts/assert-harness-conformance-preconditions.sh — the harness-conformance job (ADR-0021)
# refuses to run in a degraded mode.
#
# That job exists to prove a harness pin bump is safe. The proof needs 2 REAL inputs: the exact
# pinned harness binaries, and live provider credentials. Before this script the job checked
# neither. `claude --version || true` swallowed a drift and swallowed an absent binary, and an
# absent CLAUDEADAPTER_LIVE_TOKEN made the live tests skip, so the job reported success while it
# proved nothing. A missing input is a FAILURE here. It is never a skip.
#
# The version assert is the same drift-assert as deploy/image/agent-runtime.Dockerfile:63-71. The
# pin has ONE home (harnesses/versions.env). The installed binary must carry it, or the run stops.
#
# Every failure is collected and reported together, so one run names every missing input.
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS_FILE="${HARNESS_VERSIONS_FILE:-${ROOT}/harnesses/versions.env}"

# The credentials the LIVE arm of the conformance suite needs. Absent -> the live tests skip and
# only the fixtures run, which is not a merge-eligible verification of a pin bump.
REQUIRED_CREDENTIALS=(CLAUDEADAPTER_LIVE_TOKEN OPENROUTER_API_KEY)

# One row for each pinned harness: `<binary>:<variable in the manifest>`.
PINNED_HARNESSES=(
  claude:CLAUDE_CODE_VERSION
  omp:OMP_VERSION
  codex:CODEX_VERSION
)

failures=()

for name in "${REQUIRED_CREDENTIALS[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    failures+=("credential '${name}' is unset or empty — the live conformance arm would SKIP")
  fi
done

if [[ ! -f "$VERSIONS_FILE" ]]; then
  printf 'assert-harness-conformance-preconditions: FAILED — version manifest absent: %s\n' \
    "$VERSIONS_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$VERSIONS_FILE"

for row in "${PINNED_HARNESSES[@]}"; do
  binary="${row%%:*}"
  variable="${row##*:}"
  pin="${!variable:-}"

  if [[ -z "$pin" ]]; then
    failures+=("${variable} is unset in ${VERSIONS_FILE}")
    continue
  fi
  if ! command -v "$binary" >/dev/null 2>&1; then
    failures+=("harness '${binary}' is not installed — the pin ${variable}=${pin} cannot be proven")
    continue
  fi
  if ! installed="$("$binary" --version 2>&1)"; then
    failures+=("'${binary} --version' failed: ${installed}")
    continue
  fi

  printf '%s --version -> %s   (pin %s=%s)\n' "$binary" "$installed" "$variable" "$pin"
  case "$installed" in
    *"$pin"*) : ;;
    *) failures+=("harness pin drift: '${binary}' reports '${installed}', which does not carry ${variable}='${pin}'") ;;
  esac
done

if [[ ${#failures[@]} -gt 0 ]]; then
  printf 'assert-harness-conformance-preconditions: FAILED\n' >&2
  printf '  - %s\n' "${failures[@]}" >&2
  exit 1
fi

printf 'assert-harness-conformance-preconditions: OK — %d credential(s) present, %d harness pin(s) verified\n' \
  "${#REQUIRED_CREDENTIALS[@]}" "${#PINNED_HARNESSES[@]}"
