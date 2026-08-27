#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_VERSION="29.7.2"
EXPECTED_DIGEST="sha256:12e683a161823b2a839aeea999b9d960e6e1f9a97b1679ad6b441982e2d9cf07"
EXPECTED_REF="docker.io/library/docker:${EXPECTED_VERSION}-dind@${EXPECTED_DIGEST}"
FILES=(
  "$ROOT/platform/services/gitops/registry/app-arc-runners-org.yaml"
  "$ROOT/platform/services/gitops/registry/app-arc-runners-build.yaml"
  "$ROOT/platform/services/ci/arc-runners/42-image-warmer-daemonset.yaml"
  "$ROOT/scripts/verify-runner-image.sh"
)

failures=0
for file in "${FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "verify-dind-pins: FAIL: missing ${file#"$ROOT"/}" >&2
    failures=$((failures + 1))
    continue
  fi
  refs="$(grep -oE '(docker\.io/library/)?docker:[^[:space:]"}]+' "$file" | sort -u || true)"
  if [[ "$refs" != "$EXPECTED_REF" ]]; then
    echo "verify-dind-pins: FAIL: ${file#"$ROOT"/} must contain exactly ${EXPECTED_REF}; found ${refs:-none}" >&2
    failures=$((failures + 1))
  fi
done

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
echo "verify-dind-pins: OK — 4 homes pin Docker ${EXPECTED_VERSION}@${EXPECTED_DIGEST}"
