#!/usr/bin/env bash
#
# _ctl/tests/verify-published.test.sh — the published manifest must carry
# exactly the sanctioned platform set, and nothing else.
#
# Hermetic. The stub `docker` goes first on PATH and answers the manifest read
# from a JSON file in fixtures/manifests/, so no registry is contacted and the
# result does not change when somebody pushes.
#
# The verb under test is `verify-published`. It does not exist yet, so every
# case here is red. A reader must not have to guess that: the first check asks
# the dispatcher whether it knows the verb at all, and every later failure
# repeats the dispatcher's own reply, which is the words
#   unknown command: 'verify-published'
# rather than a shell error somebody could misdiagnose as a broken test.
#
# Contract this file fixes for the implementation:
#   - the verb is a PER-IMAGE verb, so `bash base/ctl.sh verify-published`
#     reaches it, exactly like build / push / pull / inspect;
#   - it appears in the usage block, because in this repository the output of
#     `bash ./ctl.sh help` is the specification of the interface;
#   - an entry whose platform is unknown/unknown is an ATTESTATION, not an
#     image variant. buildx attaches one per variant on every push, so a check
#     that counts entries instead of reading their platform calls a correct
#     single-platform image a 2-variant image;
#   - when the manifest cannot be read at all, the real client error is what
#     the operator needs. "no variants found" for a manifest that was never
#     read is the failure mode this repository has shipped before: a message
#     that describes a state nobody observed.
#
# Usage: bash _ctl/tests/verify-published.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="verify-published.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
MANIFESTS="$TESTS_DIR/fixtures/manifests"
BASE_CTL="$REPO_ROOT/base/ctl.sh"

# The dispatcher's answer to a verb it does not have. Finding this in the
# output means the run proved nothing about manifests — it proved the verb is
# absent — and every failure below says so instead of leaving a reader to work
# it out from an exit status.
UNKNOWN_VERB_REPLY="unknown command: 'verify-published'"
VERB_NOTE=""
VERB_MISSING=0

RUN_OUTPUT=""
RUN_STATUS=0

# run_verify [KEY=VALUE ...] — the real base/ctl.sh, the stub docker.
function run_verify() {
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" "$@" bash "$BASE_CTL" verify-published 2>&1)" || RUN_STATUS=$?
  # Carried into every failure below, so no reader has to infer the cause from
  # an exit status that a missing verb and a real verdict both produce.
  if printf '%s' "$RUN_OUTPUT" | grep -qF -- "$UNKNOWN_VERB_REPLY"; then
    VERB_MISSING=1
    VERB_NOTE="cause: base/ctl.sh answered \"${UNKNOWN_VERB_REPLY}\" — the verb does not exist yet"
  else
    VERB_MISSING=0
    VERB_NOTE="note: base/ctl.sh knows the verb, so this is the verb's own verdict"
  fi
}

# verb_is_missing <check name> [evidence...] — a dispatcher that rejected the
# verb answered nothing about any manifest, so no case may pass on that run.
# Without this the checks below pass by accident: the usage block the
# dispatcher prints on an unknown verb ends non-zero AND contains the string
# "linux/arm64", which is 2 of the 3 things an arm64 refusal is asked for. The
# first run of this file passed 2 checks that way.
function verb_is_missing() {
  local name="$1"
  shift
  if [[ "$VERB_MISSING" -eq 1 ]]; then
    fail_check "$name" \
      "the verb 'verify-published' does not exist: this run asserted nothing about a manifest" \
      "$@" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
    return 0
  fi
  return 1
}

# assert_verify_status <check name> <wanted status> [evidence...]
function assert_verify_status() {
  local name="$1" want="$2"
  shift 2
  if verb_is_missing "$name" "$@"; then
    return 0
  fi
  if [[ "$RUN_STATUS" == "$want" ]]; then
    pass_check "$name"
  else
    fail_check "$name" "want exit status: ${want}" "got  exit status: ${RUN_STATUS}" \
      "$@" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
  fi
}

# assert_verify_refused_naming <check name> <needle> [evidence...] — non-zero
# AND the reason named, as 1 check. Split apart, the "is it named" half passes
# on an accepting run whenever some log line happens to print the same string.
function assert_verify_refused_naming() {
  local name="$1" needle="$2"
  shift 2
  if verb_is_missing "$name" "$@"; then
    return 0
  fi
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" "want: a non-zero exit status, with a message naming ${needle}" \
      "got:  0 — the published set was accepted" \
      "$@" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
  elif ! printf '%s' "$RUN_OUTPUT" | grep -qF -- "$needle"; then
    fail_check "$name" \
      "the verb exited ${RUN_STATUS}, but the message never names ${needle}" \
      "$@" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

# -------- the verb exists, and the help block says so --------
help_output=""
help_status=0
help_output="$(env PATH="${STUB_BIN}:${PATH}" bash "$BASE_CTL" help 2>&1)" || help_status=$?
if [[ "$help_status" -ne 0 ]]; then
  fail_check "verify_published_is_in_the_usage_block" \
    "bash base/ctl.sh help exited ${help_status}" "output was:" "$help_output"
else
  assert_contains "verify_published_is_in_the_usage_block" "$help_output" "verify-published" \
    "in this repository the output of help IS the specification of the interface"
fi

# -------- amd64 + arm64 + attestations -> refused, naming linux/arm64 --------
run_verify STUB_MANIFEST_JSON="$MANIFESTS/amd64-arm64-attested.json"
assert_verify_refused_naming "an_arm64_variant_is_refused_and_named" "linux/arm64" \
  "manifest fixture: amd64 + arm64 + 2 unknown/unknown attestations"

# -------- amd64 + attestation -> accepted --------
# The load-bearing half of this file. buildx attaches an attestation manifest
# per variant on every push, so this shape is what a CORRECT single-platform
# image looks like today. A check that counts manifest entries reads 2 here and
# refuses a correct image.
run_verify STUB_MANIFEST_JSON="$MANIFESTS/amd64-attested.json"
assert_verify_status "an_attestation_entry_is_not_a_variant" "0" \
  "manifest fixture: amd64 + 1 unknown/unknown attestation, which is the shape" \
  "buildx publishes for a correct single-platform image"

# -------- arm64 alone -> refused --------
# Not a subset check and not a count check: the published set must EQUAL the
# sanctioned set, so 1 wrong variant fails as surely as 1 extra one.
run_verify STUB_MANIFEST_JSON="$MANIFESTS/arm64-only.json"
assert_verify_refused_naming "an_arm64_only_image_is_refused" "linux/arm64" \
  "manifest fixture: arm64 alone, with no amd64 variant at all"

# -------- the manifest cannot be read -> the REAL error survives --------
# 3 conditions, 1 check, on purpose. As 3 checks, 2 of them pass today for
# reasons that have nothing to do with the feature: an absent verb also exits
# non-zero, and an absent verb also never says "no variants". A check that
# passes before the thing it checks exists is the failure this whole phase is
# here to avoid.
run_verify \
  STUB_MANIFEST_STATUS="1" \
  STUB_MANIFEST_ERROR="ghcr.io/gophersys/base:latest: manifest unknown"
if verb_is_missing "a_failed_manifest_read_carries_the_real_error"; then
  :
elif [[ "$RUN_STATUS" -eq 0 ]]; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "want: a non-zero exit status — the registry client failed, so there is no verdict to give" \
    "got:  0" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif ! printf '%s' "$RUN_OUTPUT" | grep -qF -- "manifest unknown"; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "the run exited ${RUN_STATUS} but dropped the client's own error text" \
    "want the output to carry: ghcr.io/gophersys/base:latest: manifest unknown" \
    "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif printf '%s' "$RUN_OUTPUT" | grep -qF -- "no variants"; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "the output claims it saw no variants, but nothing was ever read" \
    "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
else
  pass_check "a_failed_manifest_read_carries_the_real_error"
fi

test_summary "$TEST_NAME"
