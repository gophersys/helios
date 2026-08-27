#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_SECRET="$ROOT/platform/services/ci/arc-runners/31-codex-review-auth-externalsecret.yaml"
POOL="$ROOT/platform/services/gitops/registry/app-arc-runners-review.yaml"

fail() {
  printf 'codex-review-auth: FAIL: %s\n' "$*" >&2
  exit 1
}

[[ -f "$EXTERNAL_SECRET" ]] || fail "missing Codex ExternalSecret"
grep -q 'key: shared/eden/codex-review-auth' "$EXTERNAL_SECRET" || fail "wrong Vaultwarden item"
grep -q 'secretKey: auth.json' "$EXTERNAL_SECRET" || fail "auth.json is not mapped"
grep -q 'secretName: codex-review-auth' "$POOL" || fail "review pool does not reference the Codex secret"
grep -q 'name: CODEX_HOME' "$POOL" || fail "review pool does not set CODEX_HOME"
grep -q 'mountPath: /var/run/codex-seed' "$POOL" || fail "seed is not mounted read-only"
grep -q 'mountPath: /home/runner/.codex' "$POOL" || fail "writable Codex home is not mounted"
grep -q 'cp /var/run/codex-seed/auth.json /home/runner/.codex/auth.json' "$POOL" || fail "auth seed is not copied"

printf 'codex-review-auth: OK\n'
