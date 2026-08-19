#!/usr/bin/env bash
#
# _ctl/tests/size-gate.test.sh — the size gate compares UNPACKED bytes.
#
# Hermetic: a stub `docker` first on PATH, and every argv it receives is
# recorded. No daemon, no network, no image.
#
# ============================================================================
# THE DEFECT (ledger #119)
# ============================================================================
#
# Every `size_budget_gb` in images.yaml was set on the UNPACKED basis — the
# number `docker images` reports as the size of a stored image, and the number
# the first cloud build was refused on:
#
#   run 31977905169, 2026-08-16T23:16Z
#   cloud size gate: cloud:smoke is 6303346803 bytes, over the 5500000000-byte
#   (5.5 GB) budget
#
# The R4 levers were then measured against that basis one by one and Mateo set
# 5.75 GB on 2026-08-16 against a measured floor of ~5.63 GB — run 32020729843
# read 5,626,948,253 bytes, which is 2.1% of headroom.
#
# The gate read that number with `docker image inspect --format '{{.Size}}'`,
# and that template is NOT store-invariant. Under the CONTAINERD image store it
# answers the CONTENT size instead: the sum of the
# COMPRESSED layer blobs. The daemon the CI smoke talks to changed basis under
# the gate between 2026-08-17T14:33Z (run 32039450157, 5,627,002,516 bytes) and
# 2026-08-17T18:32Z (run 32055368934, 2,059,410,281 bytes). Nothing failed,
# because a smaller number is still under the budget. Read on 2026-08-18, run
# 32193984249:
#
#   cloud     1,647,722,465 compared against 5,750,000,000  — 3.5x under
#   ui        1,934,334,888 compared against 6,500,000,000  — 3.4x under
#   hardware  2,608,220,360 compared against 11,000,000,000 — 4.2x under
#
# So all 3 budgets were unfailable: an image would have had to more than TRIPLE
# before the acceptance metric that exists to stop it said a word. A check that
# cannot fail is worse than no check, because it is believed.
#
# ============================================================================
# WHY THIS FILE EXISTS BESIDE smoke-contract.test.sh
# ============================================================================
#
# smoke-contract.test.sh already holds the COMPARISON at its 2 sides, for all 3
# images that declare a budget — 1 byte over is refused, exactly at the budget
# passes. Every one of those checks was GREEN throughout the whole period above,
# and correctly so: the stub handed the driver a number and the driver compared
# it. The defect was never in the comparison. It was in WHICH NUMBER the driver
# asks the daemon for, and a stub that answers one number to every question
# cannot express that difference.
#
# So the stub answers 2 different numbers now — STUB_IMAGE_SIZE through
# `docker history` and STUB_IMAGE_CONTENT_SIZE through
# `docker image inspect --format '{{.Size}}'`, whose default is the real
# compressed figure above — and this file is the basis contract:
#
#   1. an image whose UNPACKED size is over the budget is refused, even when its
#      content size is comfortably under. This is the case the shipped gate
#      passes, and it is the red this file was written to produce.
#   2. an image whose CONTENT size is over the budget is NOT refused while its
#      unpacked size is under it. The mirror of rule 1: it fails a gate that
#      reads both, or that reads the wrong one and happens to be red anyway.
#   3. the gate SUMS the layers. A per-layer read that compared the largest
#      layer, or the first, would satisfy rules 1 and 2 on a 1-layer stub.
#   4. a layer size that is not a count of bytes FAILS, naming it. `docker
#      history` prints "4GB" without `--human=false`, and shell arithmetic reads
#      that as 0 — the same class of silent unit error as the defect itself, one
#      flag away.
#   5. a history that cannot be READ fails, and 6. a history with no layer in it
#      fails. Both are FAILURES and never skips: a sum over nothing is 0, and 0
#      is under every budget anybody will ever write.
#
# Rules 1 and 5 are asserted with the `refused without running` shape
# smoke-contract.test.sh:420 uses, and for the same reason: a non-zero status
# alone also comes out of an unrelated abort, and only "no container was
# started" cannot be faked.
#
# Usage: bash _ctl/tests/size-gate.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="size-gate.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
SMOKE="$REPO_ROOT/.ci/smoke.sh"

# The image and the local ref the CI job smokes before it publishes. Written as
# literals: they are the shape build-and-push.yml uses, and a test that read
# them out of the workflow would agree with a wrong workflow.
IMAGE="cloud"
SMOKE_REF="cloud:smoke"

# The budget images.yaml declares for cloud: 5.75 GB, in the decimal bytes
# image_size_budget_bytes computes. A hand-kept literal, for the reason
# .claude/rules/00-identity.md gives about every policy literal in this
# directory — a test that reads the value it checks agrees with any value, a
# wrong one included. It moves when the manifest row moves, in the same change,
# and the measurement that moves it lives beside the key.
CLOUD_SIZE_BUDGET="5750000000"

# The COMPRESSED reading of cloud that the shipped gate compared, measured in
# run 32151769443 on 2026-08-18. Every case below hands it to the stub as the
# answer to `docker image inspect --format '{{.Size}}'`, so the world each case
# states is the world CI was really in: a real image, a real content size, and a
# budget that number cannot fail.
CLOUD_CONTENT_SIZE="1647731708"

RUN_OUTPUT=""
RUN_STATUS=0
RUN_ARGV=""

# run_smoke <image> <ref> [KEY=VALUE ...] — a real smoke run against the stub
# docker. The trailing KEY=VALUE arguments are the stub's own knobs; they are
# passed here rather than exported by the caller, so a knob cannot leak from 1
# case into the next.
#
# RUN_ARGV holds every docker invocation, 1 per line, which is how a check tells
# "it refused" apart from "it ran the container quietly".
#
# The run reads /dev/null on stdin. Without that, `docker run` inherits the
# stdin of this test file, and the stub would sit and wait on a terminal.
function run_smoke() {
  local image="$1" reference="$2"
  shift 2
  local log
  log="$(mktemp)"
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" \
    STUB_DOCKER_STDIN=/dev/null \
    "$@" bash "$SMOKE" "$image" "$reference" < /dev/null 2>&1)" || RUN_STATUS=$?
  RUN_ARGV="$(cat "$log")"
  rm -f "$log"
}

# docker_run_lines <argv log> — how many containers this run started.
function docker_run_lines() {
  awk '/^docker run / { total++ } END { print total + 0 }' <<< "$1"
}

# assert_refused_without_running <check name> <needle> [evidence...]
#
# 3 conditions, 1 check, on purpose. A non-zero status and a named number each
# pass on runs that have nothing to do with the rule; only "no container was
# started" cannot be faked, because a container that ran has already reported an
# image as smoked.
function assert_refused_without_running() {
  local name="$1" needle="$2"
  shift 2
  local runs
  runs="$(docker_run_lines "$RUN_ARGV")"
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status, with a message naming ${needle}" \
      "got:  0 — the smoke was accepted" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif ! grep -qF -- "$needle" <<< "$RUN_OUTPUT"; then
    fail_check "$name" \
      "the smoke exited ${RUN_STATUS}, and the message never names ${needle}" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif [[ "$runs" -ne 0 ]]; then
    fail_check "$name" \
      "the smoke exited ${RUN_STATUS} and said the right thing, and it had ALREADY started a container:" \
      "$RUN_ARGV" "$@" \
      "a run that starts the container first has reported an image as smoked"
  else
    pass_check "$name"
  fi
}

# assert_smoked <check name> [evidence...] — the counter-stimulus shape. Exit 0
# is not enough on its own: a gate that ate the whole smoke also exits 0, and it
# would report every image as checked while starting no container at all.
function assert_smoked() {
  local name="$1"
  shift
  local runs
  runs="$(docker_run_lines "$RUN_ARGV")"
  if [[ "$RUN_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "want: exit 0" "got:  ${RUN_STATUS}" "$@" \
      "output was:" "$RUN_OUTPUT"
  elif [[ "$runs" -ne 1 ]]; then
    fail_check "$name" \
      "the run exited 0 and started ${runs} containers, want exactly 1" \
      "an exit 0 with no container is a size gate that ate the whole smoke" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_stub_docker_is_executable"
else
  fail_check "the_stub_docker_is_executable" \
    "${STUB_BIN}/docker is not executable, so the real docker would answer every case below"
fi

# -------- 1. the basis: an image over the budget UNPACKED is refused --------
#
# The stimulus is the whole defect in 1 world. The unpacked size is 1 byte over
# the 5.75 GB budget; the content size is the 1.65 GB the daemon really reports
# for this image. A gate reading the content size sees 1.65 GB, passes, and
# smokes an oversize image on to the push step.
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_SIZE=$((CLOUD_SIZE_BUDGET + 1))" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_refused_without_running "an_image_over_the_budget_in_unpacked_bytes_is_refused" \
  "$((CLOUD_SIZE_BUDGET + 1))" \
  "the image is $((CLOUD_SIZE_BUDGET + 1)) unpacked bytes, 1 byte over the 5.75 GB budget," \
  "and its content size is ${CLOUD_CONTENT_SIZE} — the number the shipped gate compared" \
  "the gate runs before the push, so an oversize image that smokes green reaches every consumer"

# The refusal is READ by a human deciding whether to shrink the image or move
# the budget, so it owes that human 3 things: which image, what it measured, and
# what it measured against. It also owes them the BASIS — an operator holding a
# log line from before 2026-08-17 is comparing 2 numbers in 2 different units.
assert_contains "the_refusal_names_the_image" "$RUN_OUTPUT" "$IMAGE" \
  "a size failure with no image name is unreadable in a 7-job run"
assert_contains "the_refusal_names_the_budget" "$RUN_OUTPUT" "$CLOUD_SIZE_BUDGET" \
  "the number to compare against is half the finding"
assert_contains "the_refusal_names_the_basis" "$RUN_OUTPUT" "unpacked" \
  "the same image has 2 sizes, and a bare byte count says which one only by luck"

# -------- 2. the mirror: the CONTENT size is not what is compared --------
#
# Impossible in nature — compressed bytes do not exceed unpacked bytes — and
# that is exactly what makes it a discriminator. It separates "reads the
# unpacked size" from "reads both and refuses on either", which rule 1 alone
# does not.
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_SIZE=${CLOUD_SIZE_BUDGET}" \
  "STUB_IMAGE_CONTENT_SIZE=$((CLOUD_SIZE_BUDGET + 1))"
assert_smoked "an_image_over_the_budget_in_content_bytes_alone_is_smoked" \
  "the budget is declared on the unpacked basis, so the content size gates nothing"

# -------- 3. the counter-stimulus, and it is the boundary --------
#
# 1 byte from case 1 on purpose. A budget checked far from its edge passes with
# `>` written as `>=`, with the wrong constant, and with a comparison the shell
# reads as a string.
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_SIZE=${CLOUD_SIZE_BUDGET}" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_smoked "an_image_exactly_at_the_budget_is_smoked" \
  "${CLOUD_SIZE_BUDGET} unpacked bytes is the budget, and the budget is inclusive" \
  "a gate that refuses its own limit hands back a budget nobody can meet"

# -------- 4. the gate sums every layer --------
#
# 3 layers, none of them over the budget, summing to 1 byte over it. A reader
# that took the first line, the last line or the largest one passes cases 1 to 3
# on a 1-layer stub and blesses this image.
LAYER_A="3000000000"
LAYER_B="2000000000"
LAYER_C="750000001"
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_LAYER_SIZES=${LAYER_A}
${LAYER_B}
${LAYER_C}" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_refused_without_running "the_gate_sums_every_layer_of_the_history" \
  "$((CLOUD_SIZE_BUDGET + 1))" \
  "3 layers of ${LAYER_A}, ${LAYER_B} and ${LAYER_C} bytes sum to $((CLOUD_SIZE_BUDGET + 1))" \
  "no single layer is over the budget, so a gate reading one line of the history passes this image"

# -------- 5. a layer size that is not a count of bytes FAILS --------
#
# `docker history` prints "4GB" unless it is asked for bytes, and the stub
# answers exactly that when the flag is missing. Shell arithmetic reads "4GB" as
# 0, so a gate that summed it would compare 0 against the budget and pass every
# image ever built. This is the defect's own class, one flag away, and the
# refusal has to NAME the text it could not read.
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_LAYER_SIZES=5.65GB" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_refused_without_running "a_layer_size_that_is_not_bytes_is_refused_and_named" \
  "5.65GB" \
  "a human-readable size sums to 0 in shell arithmetic, and 0 passes every budget" \
  "the gate must refuse the reading rather than compare a number it invented"

# -------- 6. a history that cannot be read is a FAILURE, not a skip --------
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_HISTORY_STATUS=1" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_refused_without_running "an_unreadable_history_fails_the_run_and_starts_no_container" \
  "$IMAGE" \
  "the daemon would not report the layers, so the budget compared nothing" \
  "a gate that cannot run is a FAILURE and never a skip"

# -------- 7. a history with no layer in it is a FAILURE, not a skip --------
run_smoke "$IMAGE" "$SMOKE_REF" \
  "STUB_IMAGE_LAYER_SIZES=" \
  "STUB_IMAGE_CONTENT_SIZE=${CLOUD_CONTENT_SIZE}"
assert_refused_without_running "a_history_with_no_layer_fails_the_run_and_starts_no_container" \
  "$IMAGE" \
  "an empty history sums to 0, and 0 is under every budget anybody will ever write" \
  "this is the shape a wrong ref, a wrong platform or a store change takes"

test_summary "$TEST_NAME"
