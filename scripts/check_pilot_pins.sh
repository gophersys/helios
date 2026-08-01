#!/usr/bin/env bash
# scripts/check_pilot_pins.sh — assert the pilot corpus sits on its pinned commits.
#
# clone_pilots.sh falls back to the default branch when a host refuses to serve
# an arbitrary SHA. That keeps a developer unblocked, but in CI an unpinned
# corpus means assertions are being made against whatever upstream happened to
# push — so here it is an error, not a warning.
#
# Usage: bash scripts/check_pilot_pins.sh [data_dir]

set -euo pipefail

DATA_DIR="${1:-./data/raw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLONE_SCRIPT="${SCRIPT_DIR}/clone_pilots.sh"

[ -f "${CLONE_SCRIPT}" ] || { echo "missing ${CLONE_SCRIPT}" >&2; exit 1; }

fails=0
checked=0

# Read the (name, sha) pairs straight out of clone_pilots.sh so the two files
# can never disagree about what "pinned" means.
while IFS='|' read -r name sha; do
  [ -n "${name}" ] || continue
  checked=$((checked + 1))
  target="${DATA_DIR}/${name}"

  if [ ! -d "${target}" ]; then
    echo "::error::${name} — not cloned"
    fails=$((fails + 1))
    continue
  fi

  actual="$(git -C "${target}" rev-parse HEAD 2>/dev/null || echo '')"
  if [ "${actual}" != "${sha}" ]; then
    if [ -z "${actual}" ]; then
      found="not a git checkout"
    else
      found="${actual:0:8}"
    fi
    echo "::error::${name} — expected ${sha:0:8}, found ${found}"
    fails=$((fails + 1))
  fi
done < <(
  grep -A2 '^clone_sparse ' "${CLONE_SCRIPT}" \
    | grep -oE '"[a-z0-9_.-]+__[a-zA-Z0-9_.-]+"|"[0-9a-f]{40}"' \
    | tr -d '"' \
    | paste - - \
    | tr '\t' '|'
)

if [ "${checked}" -eq 0 ]; then
  echo "::error::parsed no pins out of ${CLONE_SCRIPT} — parser is broken" >&2
  exit 1
fi

if [ "${fails}" -gt 0 ]; then
  echo "${fails}/${checked} pilot repos are not on their pinned commit" >&2
  exit 1
fi

echo "  [pins] ✓ all ${checked} pilot repos on pinned commits"
