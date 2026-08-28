#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

for boundary in 'research/**' 'poc/**'; do
  grep -Fxq "$boundary" "$root/.nxignore" ||
    fail ".nxignore does not exclude $boundary"
done

[[ ! -e "$root/.ci" ]] || fail "retired .ci control plane still exists"

if rg -q 'submodule|\.github/workflows|\.ci/providers' \
  "$root/.nxignore" "$root/scripts/project.json"; then
  fail "root workspace configuration still describes the retired repository estate"
fi

if find "$root" -path '*/project.json' \
  \( -path "$root/research/*" -o -path "$root/poc/*" \) \
  -print -quit | grep -q . &&
  ! grep -Fxq 'research/**' "$root/.nxignore"; then
  fail "inactive project definitions can enter the Nx graph"
fi

bash -n "$root/ctl.sh" || fail "ctl.sh has invalid shell syntax"
jq empty "$root/package.json" "$root/nx.json" "$root/scripts/project.json" ||
  fail "root JSON configuration is invalid"

if ((failures > 0)); then
  echo "$failures root-workspace contract failure(s)" >&2
  exit 1
fi

echo "root-workspace contract: PASS"
