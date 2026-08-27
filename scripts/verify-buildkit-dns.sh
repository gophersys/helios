#!/usr/bin/env bash
set -euo pipefail

ROOT="${BUILDKIT_DNS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG="$ROOT/machines/services/macos-ci-runner/buildkitd.toml"
RUNBOOK="$ROOT/machines/services/macos-ci-runner/buildkitd-runbook.md"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
ok() { printf 'ok: %s\n' "$*"; }

[[ -f "$CONFIG" ]] || fail "missing checked-in BuildKit DNS config: ${CONFIG#"$ROOT"/}"

grep -Fq '[dns]' "$CONFIG" || fail 'BuildKit config has no [dns] section'
grep -Eq 'nameservers[[:space:]]*=[[:space:]]*\[[^]]*"1\.1\.1\.1"[^]]*"8\.8\.8\.8"' "$CONFIG" || \
  fail 'BuildKit config must use the two approved, location-independent resolvers'
grep -Fq 'eden-bk-config:/etc/buildkit:ro' "$RUNBOOK" || \
  fail 'runbook does not mount the seeded config volume read-only'
grep -Eq 'BUILDKIT_IMAGE="moby/buildkit@sha256:[0-9a-f]{64}"' "$RUNBOOK" || \
  fail 'runbook must reproduce the daemon from a pinned BuildKit image digest'
if grep -Eq 'moby/buildkit:latest' "$RUNBOOK"; then
  fail 'runbook still contains the moving moby/buildkit:latest tag'
fi
ok 'portable BuildKit DNS configuration is wired into daemon reproduction'

if [[ "${1:-}" != "--live" ]]; then
  exit 0
fi

command -v docker >/dev/null 2>&1 || fail 'docker is required for --live'
builder="${BUILDKIT_DNS_BUILDER:-gophersys}"
endpoint="${BUILDKIT_DNS_ENDPOINT:-tcp://10.168.0.92:1234}"
inspect_output="$(docker buildx inspect "$builder" 2>/dev/null)" || fail "buildx builder '$builder' is unavailable"
driver="$(awk '$1 == "Driver:" { print $2; exit }' <<<"$inspect_output")"
actual_endpoint="$(awk '$1 == "Endpoint:" { print $2; exit }' <<<"$inspect_output")"
[[ "$driver" == "remote" ]] || \
  fail "buildx builder '$builder' is not a remote builder"
[[ "$actual_endpoint" == "$endpoint" ]] || \
  fail "buildx builder '$builder' does not target $endpoint"

docker buildx build --builder "$builder" --platform linux/arm64 --no-cache --progress plain - <<'DOCKERFILE'
FROM alpine:3.22
RUN getent hosts ghcr.io >/dev/null
DOCKERFILE
ok "remote BuildKit builder '$builder' at $endpoint resolved ghcr.io inside a real executor"
