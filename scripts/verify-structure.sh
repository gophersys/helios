#!/usr/bin/env bash
# Assert the structural contract of contracts/ and charts/.
#
# Usage: bash scripts/verify-structure.sh
#
# WHAT IT ASSERTS
#   1. Every contracts/<name>.md opens with YAML front-matter and carries the 5
#      sections: Abstract, Interface, Guarantees, Caveats, Example.
#   2. Every charts/<archetype>/ has a README.md.
#
# The 2 rules come from .claude/rules/40-platform-contracts.md, which has named
# this script as the enforcement of that rule since before the script existed.
# The workflow called it and it was absent, so every pull request exited 127.
#
# WHAT IT DELIBERATELY DOES NOT ASSERT
# A README in every platform/<tier>/<path>/ directory. The deleted .ci/ layer
# had that rule. It demanded a README in directories that hold only a script or
# only Argo AppProject YAML, so it reported 9 errors that were all the rule being
# wrong. A check that fires on a correct tree teaches people to ignore red.
#
# It also does not assert that a "fulfills contract X" claim points at a real
# file. That check does not exist yet; see .claude/rules/40-platform-contracts.md.
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# The 5 sections are ordered here as they must appear in a contract document.
SECTIONS=(Abstract Interface Guarantees Caveats Example)

fail=0
ok()  { printf '  \033[0;32mPASS\033[0m  %s\n' "$1"; }
bad() { printf '  \033[0;31mFAIL\033[0m  %s\n' "$1"; fail=1; }

echo "contracts/ — front-matter and the 5 sections"
# A plain glob loop, NOT a pipeline. A `... | while read` runs its body in a
# subshell, so the failure counter dies with it: that exact defect made
# verify-exposure.sh print FAIL and exit 0.
shopt -s nullglob
contracts=(contracts/*.md)
shopt -u nullglob
[ "${#contracts[@]}" -gt 0 ] || bad "contracts/ holds no .md file at all"

for f in "${contracts[@]}"; do
  name="$(basename "$f")"
  # README.md is the index of the directory, not a contract. It is the only
  # exclusion, and it is by name so a new contract can never slip through it.
  [ "$name" = "README.md" ] && continue

  if [ "$(head -n 1 "$f")" != "---" ]; then
    bad "$f does not open with YAML front-matter"
    continue
  fi

  missing=""
  for s in "${SECTIONS[@]}"; do
    grep -qE "^## +${s}\b" "$f" || missing="${missing:+$missing, }$s"
  done
  if [ -n "$missing" ]; then
    bad "$f is missing the section(s): $missing"
  else
    ok "$name"
  fi
done

echo "charts/ — a README for every archetype"
shopt -s nullglob
archetypes=(charts/*/)
shopt -u nullglob
[ "${#archetypes[@]}" -gt 0 ] || bad "charts/ holds no archetype directory at all"

for d in "${archetypes[@]}"; do
  name="$(basename "$d")"
  # _common holds the shared template helpers. It is not an archetype an app can
  # adopt, so it has no app-facing surface to document. The leading underscore is
  # the marker, matching go/_ctl in gophersys/libs.
  case "$name" in _*) continue ;; esac

  if [ -f "${d}README.md" ]; then
    ok "$name"
  else
    bad "charts/$name/ has no README.md"
  fi
done

if [ "$fail" -eq 0 ]; then
  printf '\n  \033[0;32mstructure OK\033[0m\n'
else
  printf '\n  \033[0;31mstructure FAILED\033[0m\n'
fi
exit "$fail"
