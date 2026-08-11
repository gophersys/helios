#!/usr/bin/env bash
# Assert the 2 structural rules that a reader depends on and a grep cannot see.
#
#   1. Every contract in contracts/*.md opens with YAML front-matter and carries
#      the 5 sections that contracts/README.md promises. A contract is the
#      app-facing interface: a missing "Guarantees" section is a promise nobody
#      wrote down.
#   2. Every chart archetype in charts/*/ has a README.md. An archetype with no
#      README is a chart nobody can adopt without reading its templates.
#
# These 2 checks are all that survived .ci/ctl.sh. The rest of that layer was
# deleted on 2026-08-10: nothing invoked it, and its validate-platform verb
# demanded a README in every directory under platform/, including directories
# that hold only a script or only Argo AppProject YAML. It reported 9 errors that
# were all the check being wrong. A check that is wrong is worse than no check.
#
# Deliberately NOT checked here: README presence anywhere else. A README-presence
# rule over a stub tree fails for the tree being a stub, which is not a defect.
#
# Exit 0 = every rule holds. Exit 1 = at least one does not.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The sections contracts/README.md requires.
#
# Matched as a whole heading, optionally followed by whitespace and a qualifier:
# "## Interface (TBD)" counts, "## GuaranteesXX" does not. The .ci/ check this
# replaces used `grep -F`, so a renamed heading still satisfied it — proven by
# renaming "## Guarantees" to "## GuaranteesXX" and watching the check pass.
REQUIRED_SECTIONS=(
  "## Abstract"
  "## Interface"
  "## Guarantees"
  "## Caveats"
  "## Example"
)

red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

checked=0
fail=0

note_fail() {
  # $1 = relative path, $2 = what is wrong
  printf '  %s %-28s %s\n' "$(red FAIL)" "$1" "$2"
  echo "::error file=$1::$2"
  fail=$((fail + 1))
}

echo "contracts: front-matter + required sections"
for f in "$ROOT"/contracts/*.md; do
  rel="${f#"$ROOT"/}"
  [ "$(basename "$f")" = "README.md" ] && continue

  bad=0
  if [ "$(head -1 "$f")" != "---" ]; then
    note_fail "$rel" "no YAML front-matter (line 1 is not '---')"
    bad=1
  fi
  for sec in "${REQUIRED_SECTIONS[@]}"; do
    if ! grep -qE "^${sec}([[:space:]].*)?$" "$f"; then
      note_fail "$rel" "missing section '$sec'"
      bad=1
    fi
  done

  if [ "$bad" -eq 0 ]; then
    printf '  %s %-28s %s\n' "$(grn PASS)" "$rel" "front-matter + 5 sections"
    checked=$((checked + 1))
  fi
done

echo
echo "charts: every archetype has a README"
for d in "$ROOT"/charts/*/; do
  rel="${d#"$ROOT"/}"
  if [ -f "$d/README.md" ]; then
    printf '  %s %-28s %s\n' "$(grn PASS)" "${rel%/}" "README.md"
    checked=$((checked + 1))
  else
    note_fail "${rel%/}" "chart archetype has no README.md"
  fi
done

echo
echo "  checked=$checked fail=$fail"
[ "$fail" -eq 0 ] || exit 1
