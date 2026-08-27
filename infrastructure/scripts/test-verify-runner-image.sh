#!/usr/bin/env bash
# Spec for scripts/verify-runner-image.sh — the verb verifies the REPOSITORY it
# was asked about.
#
# THE DEFECT THESE CASES PIN (live in scripts/verify-runner-image.sh today)
# Line 27 is `IMAGE_REPO="ghcr.io/gophersys/base-runner"`, a constant, and the
# only argument is the tag. The verb therefore cannot answer a question about any
# other image. The arc-build pool pins `ghcr.io/gophersys/cloud`, so the
# precondition in docs/ci-runners.md — "verify-runner-image passed for that sha
# before you pin it" — is unanswerable for that pool with the verb as written.
#
# Worse than unanswerable: `verify-runner-image cloud <sha>` today reads `cloud`
# as the TAG and probes `ghcr.io/gophersys/base-runner:cloud`. It then reports
# PASS or FAIL about an image nobody asked about, in the same words it would use
# for the right one. That is the class this repository has already shipped twice
# — a check that is believed while it measures something else.
#
# THE CONTRACT THESE CASES PIN
#   C1  `verify-runner-image <repo> <tag>` probes `ghcr.io/gophersys/<repo>:<tag>`.
#       The image reaches BOTH the announce line a human reads AND the runner
#       container of the Job that is applied. Fixing only the first would leave
#       the harness testing base-runner while the log claims cloud.
#   C2  `base-runner` is not privileged. It is one value of arg 1, and it must
#       still resolve to `ghcr.io/gophersys/base-runner:<tag>`.
#   C3  a call that names a repository but no tag exits 2 with a usage line and
#       contacts the cluster ZERO times. There is no default repository and no
#       default tag: with arg 1 promoted to the repository, a 1-argument call is
#       ambiguous, and the silent guess is exactly the defect above. FAIL-NOT-SKIP.
#
# NOT PINNED HERE, ON PURPOSE: the pod shape. The dind sidecar, the gid, the
# volumes and the 15 in-pod assertions are the value of this verb and none of
# them changes. These cases touch the 2 lines that choose an image.
#
# HOW THESE CASES REACH THE REAL SCRIPT
# verify-runner-image.sh takes its namespace from $VERIFY_NS and calls `kubectl`
# by name, so a FAKE kubectl first on PATH intercepts every call: it appends its
# argv to $CAPTURE_DIR/kubectl.log, saves the stdin of `apply` to
# $CAPTURE_DIR/applied.yaml, and answers `wait`, `get` and `logs` with a passing
# run. The subject is then driven live — no copy, no edit — and the applied Job
# is read back with yq. Everything lives under mktemp; nothing is written into
# the repo tree and no cluster is contacted.
#
# Run: bash scripts/test-verify-runner-image.sh            # every case
#      bash scripts/test-verify-runner-image.sh <name>...  # one case, by name
#      bash scripts/test-verify-runner-image.sh --list     # the case names
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUT="$HERE/verify-runner-image.sh"
ESC="$(printf '\033')"

REGISTRY_HOST="ghcr.io/gophersys"
SHA="3d05c74"

CASES="
the_repository_argument_selects_the_repository
the_base_runner_repository_still_resolves
a_call_without_a_tag_never_probes_a_default_repository
"

# A missing tool is a failure, never a skip: without yq the applied Job cannot be
# read back, and every case below would assert the announce line alone — half the
# contract, reading green.
if ! command -v yq >/dev/null 2>&1; then
  echo "test-verify-runner-image: missing required tool: yq" >&2
  exit 127
fi
if [ ! -f "$SUT" ]; then
  echo "test-verify-runner-image: subject not found: $SUT" >&2
  exit 2
fi

# mktemp dirs to shred on exit. The guard form ${arr[@]+"${arr[@]}"} is for bash
# 3.2 (the macOS system bash) under set -u, where "${empty[@]}" aborts.
TMPDIRS=()
cleanup() {
  local d
  for d in ${TMPDIRS[@]+"${TMPDIRS[@]}"}; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

failures=0
case_failures=0
out=""
rc=0
ENV_DIR=""

note() { echo "    $*"; }

bad() {
  note "FAIL: $*"
  failures=$((failures + 1))
  case_failures=$((case_failures + 1))
}

# A fresh sandbox with a fake kubectl. It records every call, so a case can ask
# what the subject did as well as what it said, and it answers the read-back
# calls with a passing run so the subject reaches its own exit 0. Nothing here
# reaches a cluster: the fake is the whole cluster.
new_env() {
  ENV_DIR="$(mktemp -d)"; TMPDIRS+=("$ENV_DIR")
  mkdir -p "$ENV_DIR/bin"
  cat >"$ENV_DIR/bin/kubectl" <<'EOSH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$CAPTURE_DIR/kubectl.log"
case "${1:-}" in
  apply) cat >"$CAPTURE_DIR/applied.yaml" ;;
  get)   echo "verify-runner-image-fake" ;;
  logs)  echo "ALL CHECKS PASSED" ;;
esac
exit 0
EOSH
  chmod +x "$ENV_DIR/bin/kubectl"
}

# Drive the REAL script, fake kubectl first on PATH. set +e wraps the call so a
# non-zero exit does not abort the run, and rc=$? sits on the line right after
# the substitution so nothing runs between them. A pipeline would report its last
# stage instead — a misreading that has produced false findings here.
run_verify() { # <args...>
  set +e
  out="$(CAPTURE_DIR="$ENV_DIR" VERIFY_NS=arc-runners PATH="$ENV_DIR/bin:$PATH" \
    bash "$SUT" "$@" 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
  set -e
}

expect_rc() { # <want> <why>
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
}

expect_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
  printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
}

refute_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    bad "a line matched /$1/ but must not — $2"
    printf '%s\n' "$out" | grep -E "$1" | sed 's/^/      | /'
  fi
}

# The half of C1 that the announce line cannot prove. The Job that was applied is
# the thing that actually pulls an image, so it is read back from the fake's
# capture rather than from what the subject printed about itself.
expect_applied_image() { # <want> <why>
  local got
  if [ ! -f "$ENV_DIR/applied.yaml" ]; then
    bad "no Job was applied at all — $2"
    return 0
  fi
  got="$(yq '.spec.template.spec.containers[] | select(.name == "runner") | .image' \
    "$ENV_DIR/applied.yaml" 2>/dev/null | head -1)"
  if [ "$got" = "$1" ]; then
    return 0
  fi
  bad "the applied Job runs '${got:-<none>}', want '$1' — $2"
}

expect_no_kubectl() { # <why>
  if [ ! -f "$ENV_DIR/kubectl.log" ]; then
    return 0
  fi
  bad "the subject called kubectl $(wc -l <"$ENV_DIR/kubectl.log" | tr -d ' ') time(s) — $1"
  sed 's/^/      | /' "$ENV_DIR/kubectl.log"
}

# -------- the cases --------

# 1. C1 — THE REPOSITORY IS AN ARGUMENT, NOT A CONSTANT. arc-build pins the
# `cloud` image, and its sha must be verifiable in the pod shape before it is
# pinned. Both channels are checked: the line a human reads and the Job that is
# actually applied. RED now: IMAGE_REPO is the base-runner constant and `cloud`
# is swallowed as the tag, so the run announces and applies
# ghcr.io/gophersys/base-runner:cloud.
test_the_repository_argument_selects_the_repository() {
  new_env
  run_verify cloud "$SHA"
  expect_rc 0 "a passing pod-shape run must exit 0 (C1)"
  expect_line "$REGISTRY_HOST/cloud:$SHA" "the run must announce the image it was asked about (C1)"
  refute_line 'base-runner' "nothing about base-runner belongs in a run about cloud (C1)"
  expect_applied_image "$REGISTRY_HOST/cloud:$SHA" \
    "the Job must pull the image the caller named, not the one the script prints (C1)"
}

# 2. C2 — THE OLD SUBJECT IS NOW ONE VALUE OF ARG 1. base-runner keeps working,
# and it keeps working through the same path as every other repository. RED now:
# arg 1 is the tag, so this probes ghcr.io/gophersys/base-runner:base-runner —
# a tag that does not exist, verified against nothing.
test_the_base_runner_repository_still_resolves() {
  new_env
  run_verify base-runner "$SHA"
  expect_rc 0 "a passing pod-shape run must exit 0 (C2)"
  expect_line "$REGISTRY_HOST/base-runner:$SHA" "base-runner must resolve through the same argument (C2)"
  expect_applied_image "$REGISTRY_HOST/base-runner:$SHA" \
    "the Job must pull base-runner at the tag asked for, not at the repository name (C2)"
}

# 3. C3 — NO DEFAULT, AND NO CLUSTER CONTACT WHILE THE QUESTION IS AMBIGUOUS.
# With arg 1 promoted to the repository, `verify-runner-image cloud` names no
# tag. A default repository or a default tag would resurrect the exact failure
# this change removes: a confident verdict about an image the caller did not
# name. It must refuse, say so, and touch nothing. RED now: `cloud` is read as a
# tag, a Job for base-runner:cloud is applied, and the run exits 0.
test_a_call_without_a_tag_never_probes_a_default_repository() {
  new_env
  run_verify cloud
  expect_rc 2 "an incomplete invocation must refuse, not guess (C3)"
  expect_line 'usage' "the refusal must say how to call it (C3)"
  expect_no_kubectl "an ambiguous call must not touch the cluster (C3)"
}

# -------- runner --------

run_case() {
  local name="$1"
  case_failures=0
  echo "== $name"
  "test_$name"
  if [ "$case_failures" -eq 0 ]; then
    note "ok"
  fi
}

main() {
  local selected="" name known found
  if [ "$#" -eq 0 ]; then
    selected="$CASES"
  elif [ "$1" = "--list" ]; then
    printf '%s' "$CASES" | sed '/^$/d'
    return 0
  else
    for name in "$@"; do
      found=0
      for known in $CASES; do
        [ "$name" = "$known" ] && found=1
      done
      if [ "$found" -eq 0 ]; then
        echo "test-verify-runner-image: no such case: $name" >&2
        echo "  known: $(printf '%s' "$CASES" | tr '\n' ' ')" >&2
        exit 2
      fi
      selected="$selected$name
"
    done
  fi

  local total=0
  for name in $selected; do
    run_case "$name"
    total=$((total + 1))
  done

  echo
  echo "cases=$total assertion-failures=$failures"
  [ "$failures" -eq 0 ] || exit 1
}

main "$@"
