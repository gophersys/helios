#!/usr/bin/env bash
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-dind-pins.sh"

if [[ ! -x "$SUT" ]]; then
  echo "test-verify-dind-pins: FAIL: verifier is absent or not executable" >&2
  exit 1
fi

output="$(bash "$SUT" 2>&1)" || {
  echo "test-verify-dind-pins: FAIL: repository pins are not coherent" >&2
  printf '%s\n' "$output" >&2
  exit 1
}

grep -q '29.7.2@sha256:12e683a161823b2a839aeea999b9d960e6e1f9a97b1679ad6b441982e2d9cf07' <<< "$output" || {
  echo "test-verify-dind-pins: FAIL: verdict did not name the immutable version and digest" >&2
  exit 1
}

echo "test-verify-dind-pins: OK"
