#!/usr/bin/env bash
# Assert every Argo Application path that points at THIS repo actually exists.
#
# Why this is not a one-liner:
#
#   1. Some registry entries deploy from a SIBLING repo. `gophersys/home` carries
#      rayne's page, for example. Their paths are not expected to resolve in this
#      checkout, and failing a PR for that would be failing it for being correct.
#   2. Registry files are written in three shapes, and a naive grep silently
#      skips two of them:
#        - block style      source:\n  repoURL: ...\n  path: ...
#        - inline flow      source: { repoURL: ..., path: ... }
#        - multi-source     sources:\n  - repoURL: ...\n  - repoURL: ..., path: ...
#      Anchoring on `^\s*repoURL:` misses the inline and list forms, so those
#      Applications stop being checked at all while the gate still reports green.
#
# So: scan line by line, remember the most recent repoURL seen, and pair each
# path with it. A repoURL and a path on the SAME line pair with each other.
#
# Exit 0 = every in-repo path resolves. Exit 1 = at least one does not.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/platform/services/gitops/registry"
SELF_REPO="gophersys/infrastructure"

red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ylw() { printf '\033[0;33m%s\033[0m' "$1"; }

# Emit "<repoURL>|<path>" for every path in a file, paired with its source.
pairs() {
  awk '
    {
      line = $0
      # A commented line declares nothing.
      sub(/^[[:space:]]*#.*/, "", line)
      if (line == "") next

      if (match(line, /repoURL:[[:space:]]*[^,}[:space:]]+/)) {
        repo = substr(line, RSTART, RLENGTH)
        sub(/repoURL:[[:space:]]*/, "", repo)
        gsub(/["'"'"']/, "", repo)
        last_repo = repo
      }
      if (match(line, /(^|[[:space:],{])path:[[:space:]]*[^,}]+/)) {
        p = substr(line, RSTART, RLENGTH)
        sub(/.*path:[[:space:]]*/, "", p)
        gsub(/["'"'"']/, "", p)
        sub(/[[:space:]]+$/, "", p)
        if (p != "") print last_repo "|" p
      }
    }
  ' "$1"
}

checked=0; skipped=0; fail=0
echo "verifying Argo registry paths against this checkout"

for f in "$REGISTRY"/*.yaml; do
  base="$(basename "$f")"
  while IFS='|' read -r repo path; do
    [ -n "$path" ] || continue
    case "$path" in *'{{'*) continue ;; esac        # templated — not a real path
    case "$repo" in
      *"$SELF_REPO"*) ;;
      *)
        printf '  %s %-32s %s\n' "$(ylw SKIP)" "$base" "deploys from ${repo:-<none>}"
        skipped=$((skipped + 1)); continue ;;
    esac
    # An ApplicationSet git directory generator uses a glob on purpose
    # (one Application per matching directory). A glob passes when
    # it matches at least one thing; a glob matching nothing is a dead generator
    # and worth failing on, because it looks identical to a working one.
    case "$path" in
      *'*'*|*'?'*|*'['*)
        # shellcheck disable=SC2206  # word-splitting is the expansion we want
        matches=($ROOT/$path)
        if [ -e "${matches[0]}" ]; then
          printf '  %s %-32s %s (%d match(es))\n' "$(grn PASS)" "$base" "$path" "${#matches[@]}"
          checked=$((checked + 1))
        else
          printf '  %s %-32s %s\n' "$(red FAIL)" "$base" "glob matches nothing: $path"
          echo "::error::registry glob matches nothing: $path (in $base)"
          fail=$((fail + 1))
        fi
        continue ;;
    esac
    if [ -e "$ROOT/$path" ]; then
      printf '  %s %-32s %s\n' "$(grn PASS)" "$base" "$path"
      checked=$((checked + 1))
    else
      printf '  %s %-32s %s\n' "$(red FAIL)" "$base" "missing: $path"
      echo "::error::registry references missing path: $path (in $base)"
      fail=$((fail + 1))
    fi
  done < <(pairs "$f")
done

echo
echo "  checked=$checked skipped=$skipped fail=$fail"
[ "$fail" -eq 0 ] || exit 1
