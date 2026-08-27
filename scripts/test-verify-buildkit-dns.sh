#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-buildkit-dns.sh"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

failures=0
expect_fail() {
  local name="$1" expected="$2"
  shift 2
  local output
  if output="$("$@" 2>&1)"; then
    printf 'FAIL: %s unexpectedly passed\n' "$name" >&2
    failures=$((failures + 1))
  elif ! grep -Fq "$expected" <<<"$output"; then
    printf 'FAIL: %s returned the wrong diagnostic: %s\n' "$name" "$output" >&2
    failures=$((failures + 1))
  else
    printf 'ok: %s\n' "$name"
  fi
}

new_fixture() {
  local name="$1"
  local root="$TMP_ROOT/$name"
  mkdir -p "$root/machines/services/macos-ci-runner"
  cp "$HERE/../machines/services/macos-ci-runner/buildkitd.toml" "$root/machines/services/macos-ci-runner/"
  cp "$HERE/../machines/services/macos-ci-runner/buildkitd-runbook.md" "$root/machines/services/macos-ci-runner/"
  printf '%s\n' "$root"
}

good="$(new_fixture good)"
BUILDKIT_DNS_ROOT="$good" bash "$SUT" >/dev/null
printf 'ok: complete static contract passes\n'

missing="$(new_fixture missing-config)"
rm "$missing/machines/services/macos-ci-runner/buildkitd.toml"
expect_fail 'missing config fails' 'missing checked-in BuildKit DNS config' env BUILDKIT_DNS_ROOT="$missing" bash "$SUT"

wrong_dns="$(new_fixture wrong-dns)"
printf '[dns]\n  nameservers = ["192.168.1.1"]\n' >"$wrong_dns/machines/services/macos-ci-runner/buildkitd.toml"
expect_fail 'house-specific resolver fails' 'two approved, location-independent resolvers' env BUILDKIT_DNS_ROOT="$wrong_dns" bash "$SUT"

missing_gc="$(new_fixture missing-gc)"
sed -i.bak '/^\[worker\.oci\]/,$d' "$missing_gc/machines/services/macos-ci-runner/buildkitd.toml"
rm "$missing_gc/machines/services/macos-ci-runner/buildkitd.toml.bak"
expect_fail 'missing GC policy fails' 'bounded OCI worker garbage collection' env BUILDKIT_DNS_ROOT="$missing_gc" bash "$SUT"

unbounded_gc="$(new_fixture unbounded-gc)"
sed -i.bak '/maxUsedSpace/d' "$unbounded_gc/machines/services/macos-ci-runner/buildkitd.toml"
rm "$unbounded_gc/machines/services/macos-ci-runner/buildkitd.toml.bak"
expect_fail 'unbounded cache fails' 'maximum cache use at 20GB' env BUILDKIT_DNS_ROOT="$unbounded_gc" bash "$SUT"

missing_mount="$(new_fixture missing-mount)"
printf 'BUILDKIT_IMAGE="moby/buildkit@sha256:%064d"\n' 0 >"$missing_mount/machines/services/macos-ci-runner/buildkitd-runbook.md"
expect_fail 'missing config mount fails' 'does not mount the seeded config volume' env BUILDKIT_DNS_ROOT="$missing_mount" bash "$SUT"

anonymous_state="$(new_fixture anonymous-state)"
sed -i.bak 's/-v eden-bk-state:\/var\/lib\/buildkit//' "$anonymous_state/machines/services/macos-ci-runner/buildkitd-runbook.md"
rm "$anonymous_state/machines/services/macos-ci-runner/buildkitd-runbook.md.bak"
expect_fail 'anonymous state volume fails' 'does not mount named BuildKit state' env BUILDKIT_DNS_ROOT="$anonymous_state" bash "$SUT"

leaky_seed="$(new_fixture leaky-seed)"
sed -i.bak 's/docker rm -v bkseed/docker rm bkseed/' "$leaky_seed/machines/services/macos-ci-runner/buildkitd-runbook.md"
rm "$leaky_seed/machines/services/macos-ci-runner/buildkitd-runbook.md.bak"
expect_fail 'leaky seed container fails' 'seed containers must remove anonymous volumes' env BUILDKIT_DNS_ROOT="$leaky_seed" bash "$SUT"

no_repair="$(new_fixture no-repair)"
sed -i.bak '/docker rm -f eden-buildkitd/d' "$no_repair/machines/services/macos-ci-runner/buildkitd-runbook.md"
rm "$no_repair/machines/services/macos-ci-runner/buildkitd-runbook.md.bak"
expect_fail 'missing daemon replacement fails' 'capture and replace the existing daemon safely' env BUILDKIT_DNS_ROOT="$no_repair" bash "$SUT"

no_reclaim="$(new_fixture no-reclaim)"
sed -i.bak '/docker volume rm \\/d' "$no_reclaim/machines/services/macos-ci-runner/buildkitd-runbook.md"
rm "$no_reclaim/machines/services/macos-ci-runner/buildkitd-runbook.md.bak"
expect_fail 'missing bounded volume removal fails' 'explicitly verified incident volumes' env BUILDKIT_DNS_ROOT="$no_reclaim" bash "$SUT"

moving_image="$(new_fixture moving-image)"
printf 'eden-bk-config:/etc/buildkit:ro\neden-bk-state:/var/lib/buildkit\ndocker rm -v bkseed\ndocker rm -v bkconfig\ndocker inspect eden-buildkitd\ndocker rm -f eden-buildkitd\ndocker volume rm \\\nvolume-id\nBUILDKIT_IMAGE="moby/buildkit@sha256:%064d"\nmoby/buildkit:latest\n' 0 >"$moving_image/machines/services/macos-ci-runner/buildkitd-runbook.md"
expect_fail 'moving daemon image fails' 'moving moby/buildkit:latest tag' env BUILDKIT_DNS_ROOT="$moving_image" bash "$SUT"

fake_bin="$TMP_ROOT/bin"
mkdir -p "$fake_bin"
cat >"$fake_bin/docker" <<'EOF'
#!/usr/bin/env bash
if [[ "$1 $2" == 'buildx inspect' ]]; then
  printf 'Name: test\nDriver:        %s\nNodes:\nName: test0\nEndpoint:       %s\n' "${FAKE_DRIVER:-remote}" "${FAKE_ENDPOINT:-tcp://10.168.0.92:1234}"
elif [[ "$1 $2" == 'buildx build' ]]; then
  printf '%s\n' "$*" >"$DOCKER_LOG"
  cat >/dev/null
else
  exit 2
fi
EOF
chmod +x "$fake_bin/docker"

expect_fail 'local builder fails' 'is not a remote builder' env PATH="$fake_bin:$PATH" DOCKER_LOG="$TMP_ROOT/log" FAKE_DRIVER=docker BUILDKIT_DNS_ROOT="$good" BUILDKIT_DNS_BUILDER=test bash "$SUT" --live
expect_fail 'wrong remote endpoint fails' 'does not target tcp://10.168.0.92:1234' env PATH="$fake_bin:$PATH" DOCKER_LOG="$TMP_ROOT/log" FAKE_ENDPOINT=tcp://127.0.0.1:1234 BUILDKIT_DNS_ROOT="$good" BUILDKIT_DNS_BUILDER=test bash "$SUT" --live

PATH="$fake_bin:$PATH" DOCKER_LOG="$TMP_ROOT/log" BUILDKIT_DNS_ROOT="$good" BUILDKIT_DNS_BUILDER=test bash "$SUT" --live >/dev/null
grep -Fq -- '--platform linux/arm64 --no-cache' "$TMP_ROOT/log" || { printf 'FAIL: live proof omitted arm64 or --no-cache\n' >&2; failures=$((failures + 1)); }
printf 'ok: intended remote endpoint runs an uncached arm64 proof\n'

(( failures == 0 )) || exit 1
printf 'test-verify-buildkit-dns: all cases passed\n'
