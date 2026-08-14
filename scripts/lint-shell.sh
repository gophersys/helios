#!/usr/bin/env bash
# lint-shell.sh — the shellcheck gate with a FLOOR, one home for CI and ctl.sh.
#
# The old gate went green over ZERO files: validate.yml piped an empty find into
# `xargs -0 -r shellcheck` (-r, --no-run-if-empty, runs shellcheck 0 times and
# exits 0), and ctl.sh looped over an empty array and logged "shellcheck clean".
# A future path narrowing to zero scripts would have read as a pass. This script
# discovers the scripts once, FAILS if it finds none (the floor), runs bash -n
# then shellcheck at full strictness with findings VISIBLE, and prints a witness
# count. Both validate.yml and `ctl.sh validate` call it, so the floor guards
# both paths and cannot be bypassed by one.
#
# Usage: lint-shell.sh [dir]   # dir defaults to the repo root
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIR="${1:-$ROOT}"

# A missing linter is a FAILURE, never a skip: a gate that cannot run its tool
# has checked nothing while reading green.
command -v shellcheck >/dev/null 2>&1 || {
  echo "lint-shell: shellcheck is required and is not installed" >&2
  exit 127
}

# Discover once. bash 3.2 (the macOS system bash) has no mapfile, so read -d ''.
# NO `xargs -0 -r`: the -r is exactly the swallow this script replaces.
files=()
while IFS= read -r -d '' f; do
  files+=("$f")
done < <(find "$DIR" -name '*.sh' -not -path '*/node_modules/*' -not -path '*/.git/*' -print0)

# THE FLOOR. Zero scripts means the gate measured nothing — the one false green
# this whole change exists to kill.
if [ "${#files[@]}" -eq 0 ]; then
  echo "lint-shell: no shell scripts found under $DIR" >&2
  exit 1
fi

rc=0

# Syntax first, so a parse error is named as such rather than buried in the
# findings that follow.
for f in "${files[@]}"; do
  if ! bash -n "$f"; then
    echo "lint-shell: bash syntax error: $f" >&2
    rc=1
  fi
done

# Full strictness, no -S filter, findings VISIBLE — the old ctl.sh hid them
# behind >/dev/null, so a violation passed as long as it counted a file.
if ! shellcheck "${files[@]}"; then
  rc=1
fi

if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi

echo "lint-shell: linted ${#files[@]} shell script(s)"
