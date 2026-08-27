#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/machines/services/macos-ci-runner/buildkitd.toml"
RUNBOOK="$ROOT/machines/services/macos-ci-runner/buildkitd-runbook.md"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
ok() { printf 'ok: %s\n' "$*"; }

[[ -f "$CONFIG" ]] || fail "missing checked-in BuildKit DNS config: ${CONFIG#"$ROOT"/}"

grep -Fq '[dns]' "$CONFIG" || fail 'BuildKit config has no [dns] section'
grep -Eq 'nameservers[[:space:]]*=[[:space:]]*\[[^]]*"1\.1\.1\.1"[^]]*"8\.8\.8\.8"' "$CONFIG" || \
  fail 'BuildKit config must use the two approved, network-independent resolvers'
grep -Fq 'eden-bk-config:/etc/buildkit:ro' "$RUNBOOK" || \
  fail 'runbook does not mount the seeded config volume read-only'
ok 'portable BuildKit DNS configuration is wired into daemon reproduction'

if [[ "${1:-}" != "--live" ]]; then
  exit 0
fi

command -v docker >/dev/null 2>&1 || fail 'docker is required for --live'
builder="${BUILDKIT_DNS_BUILDER:-gophersys}"
docker buildx inspect "$builder" >/dev/null 2>&1 || fail "buildx builder '$builder' is unavailable"

docker buildx build --builder "$builder" --platform linux/arm64 --no-cache --progress plain - <<'DOCKERFILE'
FROM alpine:3.22
RUN getent hosts ghcr.io >/dev/null
DOCKERFILE
ok "BuildKit builder '$builder' resolved ghcr.io inside a real build executor"
