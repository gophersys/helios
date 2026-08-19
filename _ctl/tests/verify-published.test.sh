#!/usr/bin/env bash
#
# _ctl/tests/verify-published.test.sh — the published manifest must carry
# exactly the platform set THAT IMAGE publishes, and nothing else.
#
# Hermetic. The stub `docker` goes first on PATH and answers the manifest read
# from a JSON file in fixtures/manifests/, so no registry is contacted and the
# result does not change when somebody pushes.
#
# ============================================================================
# THE SET IS PER-IMAGE, AND THAT IS WHAT THIS FILE CHANGED
# ============================================================================
#
# The verb compared every image against SANCTIONED_PLATFORMS while the set held
# 1 platform, and the 2 questions had 1 answer. They do not any more:
#
#   base    publishes linux/amd64,linux/arm64 — no `platforms` key, so it takes
#           the sanctioned set;
#   mobile publishes linux/amd64 alone, declared in images.yaml and measured —
#           Flutter ships no linux-arm64 SDK at any version.
#
# So the same amd64-only manifest is a BROKEN publish for base and a CORRECT
# publish for mobile, and this file drives both images against it. Against the
# sanctioned set, mobile's correct manifest would read as broken forever; a
# rule that only asked "is every published platform sanctioned" would call
# base's missing arm64 half fine. Only the per-image set answers both.
#
# Contract this file holds for the implementation:
#   - the verb is a PER-IMAGE verb, so `bash base/ctl.sh verify-published`
#     reaches it, exactly like build / push / pull / inspect;
#   - it appears in the usage block, because in this repository the output of
#     `bash ./ctl.sh help` is the specification of the interface;
#   - an entry whose platform is unknown/unknown is an ATTESTATION, not an
#     image variant. buildx attaches one per variant on every push — 2 of them
#     on a dual-platform image — so a check that counts entries instead of
#     reading their platform calls a correct 2-variant image a 4-variant image;
#   - when the manifest cannot be read at all, the real client error is what
#     the operator needs. "no variants found" for a manifest that was never
#     read is the failure mode this repository has shipped before: a message
#     that describes a state nobody observed.
#
# The dispatcher check below is kept from the run in which the verb did not
# exist. It is not decoration: every later failure repeats the dispatcher's own
# reply, so a reader is never left inferring "the verb is gone" from an exit
# status that a missing verb and a real verdict both produce.
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
MOBILE_CTL="$REPO_ROOT/mobile/ctl.sh"

# The 3 manifest shapes, and what each one IS. Every one of them carries the
# attestation entries buildx really attaches, because a fixture without them
# would let a counting implementation pass.
MANIFEST_DUAL="$MANIFESTS/amd64-arm64-attested.json"    # amd64 + arm64 + 2 attestations
MANIFEST_AMD64="$MANIFESTS/amd64-attested.json"         # amd64 + 1 attestation
MANIFEST_ARM64="$MANIFESTS/arm64-only.json"             # arm64 alone, no attestation

# The dispatcher's answer to a verb it does not have. Finding this in the
# output means the run proved nothing about manifests — it proved the verb is
# absent — and every failure below says so instead of leaving a reader to work
# it out from an exit status.
UNKNOWN_VERB_REPLY="unknown command: 'verify-published'"
VERB_NOTE=""
VERB_MISSING=0

RUN_OUTPUT=""
RUN_STATUS=0

# run_verify <ctl.sh> [KEY=VALUE ...] — a real per-image ctl.sh, the stub docker.
function run_verify() {
  local ctl="$1"
  shift
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" "$@" bash "$ctl" verify-published 2>&1)" || RUN_STATUS=$?
  # Carried into every failure below, so no reader has to infer the cause from
  # an exit status that a missing verb and a real verdict both produce.
  if grep -qF -- "$UNKNOWN_VERB_REPLY" <<< "$RUN_OUTPUT"; then
    VERB_MISSING=1
    VERB_NOTE="cause: ${ctl} answered \"${UNKNOWN_VERB_REPLY}\" — the verb does not exist"
  else
    VERB_MISSING=0
    VERB_NOTE="note: ${ctl} knows the verb, so this is the verb's own verdict"
  fi
}

# verb_is_missing <check name> [evidence...] — a dispatcher that rejected the
# verb answered nothing about any manifest, so no case may pass on that run.
# Without this the checks below pass by accident: the usage block the
# dispatcher prints on an unknown verb ends non-zero AND contains the string
# "linux/arm64", which is 2 of the 3 things a refusal is asked for. The first
# run of this file passed 2 checks that way.
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
  elif ! grep -qF -- "$needle" <<< "$RUN_OUTPUT"; then
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

missing_manifests=""
for fixture in "$MANIFEST_DUAL" "$MANIFEST_AMD64" "$MANIFEST_ARM64"; do
  [[ -f "$fixture" ]] || missing_manifests="${missing_manifests:+${missing_manifests}
}${fixture}"
done
if [[ -n "$missing_manifests" ]]; then
  fail_check "every_manifest_fixture_exists" \
    "these fixtures are named below and absent:" "$missing_manifests" \
    "the stub answers the manifest read out of them, so a missing one makes the stub" \
    "print nothing and the verb judge an empty document"
else
  pass_check "every_manifest_fixture_exists"
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

# ===========================================================================
# base publishes BOTH platforms
# ===========================================================================
# The inversion. `an_arm64_variant_is_refused_and_named` stood here while the
# set held 1 platform; an arm64 variant is now REQUIRED of base, and this is the
# shape a correct dual-platform publish has in the registry — 2 image manifests
# and the 2 attestation manifests buildx attaches to them.
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"
assert_verify_status "a_dual_platform_manifest_is_accepted_for_base" "0" \
  "manifest fixture: amd64 + arm64 + 2 unknown/unknown attestations" \
  "base declares no platforms key in images.yaml, so it publishes the sanctioned set"

# THE LOAD-BEARING HALF. buildx attaches an attestation manifest per variant on
# every push, so the fixture above holds 4 entries for 2 platforms. An
# implementation that counted entries reads 4 and refuses a correct image; one
# that counted them and expected 2 would refuse this too.
assert_contains "an_attestation_entry_is_not_counted_as_a_variant" "$RUN_OUTPUT" \
  "carries exactly linux/amd64,linux/arm64" \
  "the fixture holds 4 manifest entries and exactly 2 of them are image variants" \
  "output was:" "$RUN_OUTPUT"

# -------- base with the arm64 half missing -> refused, naming it --------
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_AMD64"
assert_verify_refused_naming "an_amd64_only_manifest_is_refused_for_base_naming_linux_arm64" \
  "linux/arm64" \
  "manifest fixture: amd64 + 1 attestation — a publish whose arm64 leg never landed" \
  "this is the exact shape mobile publishes CORRECTLY, which is why the set has to be" \
  "read per image and not from SANCTIONED_PLATFORMS"

# -------- base with only the arm64 half -> refused, naming the missing amd64 --------
# Not a subset check and not a count check: the published set must EQUAL the set
# the image publishes, so 1 missing variant fails as surely as 1 extra one.
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_ARM64"
assert_verify_refused_naming "an_arm64_only_manifest_is_refused_for_base_naming_linux_amd64" \
  "linux/amd64" \
  "manifest fixture: arm64 alone, with no amd64 variant and no attestation at all"

# ===========================================================================
# mobile publishes linux/amd64 ALONE
# ===========================================================================
# The same amd64-only fixture the check above refuses. If this passes and that
# one fails on one document, the verb is reading the image's own set — and no
# weaker statement proves it.
run_verify "$MOBILE_CTL" STUB_MANIFEST_JSON="$MANIFEST_AMD64"
assert_verify_status "an_amd64_only_manifest_is_accepted_for_mobile" "0" \
  "mobile declares platforms: [linux/amd64] in images.yaml, and the manifest carries" \
  "the measurement beside the key: Flutter publishes no linux-arm64 SDK at any version" \
  "against SANCTIONED_PLATFORMS this correct publish would read as broken forever"

# -------- mobile with an arm64 variant it must not have -> refused --------
# The other direction, and the one a narrower set makes possible: an EXTRA
# variant. A rule that only asked "is every published platform sanctioned" would
# accept this, because linux/arm64 is sanctioned — it is just not mobile's.
run_verify "$MOBILE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"
assert_verify_refused_naming "an_arm64_variant_is_refused_for_mobile_and_named" \
  "published but not expected: linux/arm64" \
  "manifest fixture: amd64 + arm64 + 2 attestations, which base accepts" \
  "the refusal has to name the OFFENDING variant and not only the 2 sets, or an" \
  "operator reading it has to diff 2 comma lists by eye"

# -------- the manifest cannot be read -> the REAL error survives --------
# 3 conditions, 1 check, on purpose. As 3 checks, 2 of them pass for reasons
# that have nothing to do with the feature: any abort exits non-zero, and a verb
# that printed nothing also never says "no variants". A check that passes
# without the behaviour is the failure this whole phase is here to avoid.
run_verify "$BASE_CTL" \
  STUB_MANIFEST_STATUS="1" \
  STUB_MANIFEST_ERROR="ghcr.io/gophersys/base:latest: manifest unknown"
if verb_is_missing "a_failed_manifest_read_carries_the_real_error"; then
  :
elif [[ "$RUN_STATUS" -eq 0 ]]; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "want: a non-zero exit status — the registry client failed, so there is no verdict to give" \
    "got:  0" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif ! grep -qF -- "manifest unknown" <<< "$RUN_OUTPUT"; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "the run exited ${RUN_STATUS} but dropped the client's own error text" \
    "want the output to carry: ghcr.io/gophersys/base:latest: manifest unknown" \
    "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif grep -qF -- "no variants" <<< "$RUN_OUTPUT"; then
  fail_check "a_failed_manifest_read_carries_the_real_error" \
    "the output claims it saw no variants, but nothing was ever read" \
    "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
else
  pass_check "a_failed_manifest_read_carries_the_real_error"
fi

test_summary "$TEST_NAME"
