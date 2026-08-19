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

# One row for each pinned harness: `<binary>:<variable in the manifest>:<tier>`.
#
# The tier is the honesty of the row. `exercised` means the conformance suite really drives this
# harness through an adapter. `unexercised` means the pin is installed and version-checked here and
# nothing else in the suite touches it — true for codex, which has no adapter yet: the pin is bumped
# and the tier is declared loudly rather than left to read like the other 2. The label takes nothing
# away. An unexercised row keeps every assert of an exercised one, so drift, an absent binary and a
# failing `--version` each still stop the run. It only stops a reader from taking
# "3 harness pin(s) verified" for 3 proven adapters.
PINNED_HARNESSES=(
  claude:CLAUDE_CODE_VERSION:exercised
  omp:OMP_VERSION:exercised
  codex:CODEX_VERSION:unexercised
)

failures=()
unexercised=()

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
  IFS=':' read -r binary variable tier <<<"$row"
  pin="${!variable:-}"

  label=''
  case "$tier" in
    exercised) : ;;
    unexercised)
      label='   [UNEXERCISED — no adapter drives this harness; this version check is the only proof]'
      unexercised+=("$binary")
      ;;
    *)
      failures+=("row '${row}' carries the unknown tier '${tier}' — a tier this script cannot read is a row it cannot report honestly")
      continue
      ;;
  esac

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

  printf '%s --version -> %s   (pin %s=%s)%s\n' "$binary" "$installed" "$variable" "$pin" "$label"
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

# The summary carries the tier split too. A pin that no adapter drives is verified in exactly one
# sense — it is installed and it carries its pin — and the line says which sense it is.
tiers="$((${#PINNED_HARNESSES[@]} - ${#unexercised[@]})) exercised"
if [[ ${#unexercised[@]} -gt 0 ]]; then
  unexercised_list="$(printf '%s,' "${unexercised[@]}")"
  tiers="${tiers}, ${#unexercised[@]} UNEXERCISED: ${unexercised_list%,}"
fi

printf 'assert-harness-conformance-preconditions: OK — %d credential(s) present, %d harness pin(s) verified (%s)\n' \
  "${#REQUIRED_CREDENTIALS[@]}" "${#PINNED_HARNESSES[@]}" "$tiers"
