#!/usr/bin/env bash
#
# _ctl/tests/verify-published.test.sh — the published manifest must carry
# exactly the platform set THAT IMAGE publishes, and nothing else.
#
# Hermetic. The stub `docker` goes first on PATH and answers the manifest read
# from a JSON file in fixtures/manifests/, and the stub `curl` beside it answers
# every registry-API request out of a map the case writes, so no registry is
# contacted and the result does not change when somebody pushes.
#
# ============================================================================
# A MANIFEST IS NOT AN IMAGE — THE SECOND SUBJECT OF THIS FILE
# ============================================================================
#
# The incident (ledger #118): ghcr.io answered 404 for layer `d14f6240…` while 4
# manifests still referenced it. Every manifest parsed, every platform was
# declared, `verify-published` was GREEN — and `docker pull` failed for every
# consumer of those images until an unrelated rebuild re-uploaded the blob.
#
# The class is wider than the incident: manifest-level verification proves
# STRUCTURE and says nothing about PULLABILITY. The obvious repair — a HEAD per
# blob — does not close it either, and that is measured rather than argued.
# Read on 2026-08-18 against a real layer of ghcr.io/gophersys/base:
#
#   HEAD /v2/gophersys/base/blobs/sha256:966c39…  ->  HTTP/2 200, content-length
#                                                     29751109, served by ghcr.io
#                                                     ITSELF, with no redirect
#   GET  /v2/gophersys/base/blobs/sha256:966c39…  ->  HTTP 307 to
#                                                     pkg-containers.githubusercontent.com,
#                                                     which is where the bytes are
#
# A HEAD is answered by the metadata tier and never reaches the object store. So
# HEAD 200 is not evidence that anything can be pulled, and a registry that has
# lost an object while keeping its metadata answers exactly that way.
#
# The check this file holds is therefore a RANGED GET — `Range: bytes=0-0` — of
# every blob each published manifest references: 1 byte per blob, which proves
# the object SERVES. The stimulus below stages the divergence directly: one
# referenced blob answers HEAD 200 and GET 404, and the verb has to refuse it
# naming the image, the platform, the digest and the status.
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
REGISTRY_FIXTURES="$TESTS_DIR/fixtures/registry"
BASE_CTL="$REPO_ROOT/base/ctl.sh"

# The 3 manifest shapes, and what each one IS. Every one of them carries the
# attestation entries buildx really attaches, because a fixture without them
# would let a counting implementation pass.
MANIFEST_DUAL="$MANIFESTS/amd64-arm64-attested.json"    # amd64 + arm64 + 2 attestations
MANIFEST_AMD64="$MANIFESTS/amd64-attested.json"         # amd64 + 1 attestation
MANIFEST_ARM64="$MANIFESTS/arm64-only.json"             # arm64 alone, no attestation

# The 2 image-manifest digests the index fixtures above point at. They are
# LITERALS here on purpose: a test that read them out of the same document the
# verb reads would agree with a verb that walked the wrong entries.
AMD64_MANIFEST_DIGEST="sha256:1d5f8c7b3a9e4602b17c8d3f5a2e9410c6b7d84f0e13a5c29b6d7e8f4a0c1b23"
ARM64_MANIFEST_DIGEST="sha256:2e6a9d8c4b0f5713c28d9e4a6b3f0521d7c8e95a1f24b6d3ac7e8f9b5b1d2c34"

# What each of those manifests references: 1 config + 3 layers, so a healthy
# dual-platform publish is 8 blob probes.
IMAGE_MANIFEST_AMD64="$REGISTRY_FIXTURES/image-manifest-amd64.json"
IMAGE_MANIFEST_ARM64="$REGISTRY_FIXTURES/image-manifest-arm64.json"
IMAGE_MANIFEST_NO_LAYERS="$REGISTRY_FIXTURES/image-manifest-no-layers.json"
REGISTRY_TOKEN_DOCUMENT="$REGISTRY_FIXTURES/token.json"
BLOB_FIRST_BYTE="$REGISTRY_FIXTURES/blob-first-byte"
BLOBS_PER_PLATFORM=4
BLOBS_DUAL_PLATFORM=$((BLOBS_PER_PLATFORM * 2))

# The layer of the incident. It sits in the amd64 manifest fixture, and the
# stimulus map below makes it answer HEAD 200 and GET 404 — the exact shape
# ghcr.io produced when it lost the object and kept the metadata.
INCIDENT_BLOB="sha256:d14f6240a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c"

# The credential the blob probe exchanges for a pull token. Hermetic: the stub
# curl never looks at it, and the point of setting it is that the verb must
# REFUSE when it is absent rather than fall back to an anonymous read.
STUB_REGISTRY_SECRET="stub-registry-secret"

CURL_MAP="$(mktemp)"
REQUEST_LOG="$(mktemp)"
EMPTY_DOCKER_CONFIG="$(mktemp -d)"
trap 'rm -f "$CURL_MAP" "$REQUEST_LOG"; rm -rf "$EMPTY_DOCKER_CONFIG"' EXIT

# write_registry_map [row...] — the world the stub curl answers from. The
# case's own rows go FIRST, because the stub takes the first row whose substring
# matches and a case states an exception to the healthy default.
function write_registry_map() {
  : > "$CURL_MAP"
  local row
  for row in "$@"; do
    printf '%s\n' "$row" >> "$CURL_MAP"
  done
  {
    printf '/token?service=|200|%s\n' "$REGISTRY_TOKEN_DOCUMENT"
    printf '/manifests/%s|200|%s\n' "$AMD64_MANIFEST_DIGEST" "$IMAGE_MANIFEST_AMD64"
    printf '/manifests/%s|200|%s\n' "$ARM64_MANIFEST_DIGEST" "$IMAGE_MANIFEST_ARM64"
    printf '/blobs/sha256:|200|%s\n' "$BLOB_FIRST_BYTE"
  } >> "$CURL_MAP"
}

# The dispatcher's answer to a verb it does not have. Finding this in the
# output means the run proved nothing about manifests — it proved the verb is
# absent — and every failure below says so instead of leaving a reader to work
# it out from an exit status.
UNKNOWN_VERB_REPLY="unknown command: 'verify-published'"
VERB_NOTE=""
VERB_MISSING=0

RUN_OUTPUT=""
RUN_STATUS=0
RUN_REQUESTS=""

# run_verify <ctl.sh> [KEY=VALUE ...] — a real per-image ctl.sh, the stub docker
# and the stub curl. The case's own KEY=VALUE pairs come LAST, so a case can
# override any default here — an absent credential is stated that way.
function run_verify() {
  local ctl="$1"
  shift
  RUN_STATUS=0
  : > "$REQUEST_LOG"
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" \
    GHCR_TOKEN="$STUB_REGISTRY_SECRET" \
    STUB_CURL_MAP="$CURL_MAP" \
    STUB_CURL_REQUEST_LOG="$REQUEST_LOG" \
    "$@" bash "$ctl" verify-published 2>&1)" || RUN_STATUS=$?
  RUN_REQUESTS="$(cat "$REQUEST_LOG")"
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

# The healthy registry, until a case states an exception to it.
write_registry_map

if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

if [[ -x "$STUB_BIN/curl" ]]; then
  pass_check "the_curl_stub_is_executable"
else
  fail_check "the_curl_stub_is_executable" \
    "not executable: ${STUB_BIN}/curl" \
    "without it the real curl answers the blob probe, and this file would contact ghcr.io"
fi

missing_manifests=""
for fixture in "$MANIFEST_DUAL" "$MANIFEST_AMD64" "$MANIFEST_ARM64" \
               "$IMAGE_MANIFEST_AMD64" "$IMAGE_MANIFEST_ARM64" "$IMAGE_MANIFEST_NO_LAYERS" \
               "$REGISTRY_TOKEN_DOCUMENT" "$BLOB_FIRST_BYTE"; do
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

# ===========================================================================
# THE BLOBS — a manifest that parses over an image nobody can pull
# ===========================================================================
#
# Ledger #118. Every check below drives the SAME dual-platform index the
# platform section above accepts, so nothing here can pass on a manifest the
# verb already refuses: the only thing that moves is what the registry does with
# the blobs those manifests reference.

# count_requests <extended regex> — how many stub-curl requests matched.
function count_requests() {
  grep -cE -- "$1" <<< "$RUN_REQUESTS" || true
}

# -------- every blob serves -> accepted, and the count is REPORTED --------
write_registry_map
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"
assert_verify_status "a_publish_whose_every_blob_serves_is_accepted" "0" \
  "manifest fixture: amd64 + arm64 + 2 attestations, and a registry that serves every referenced blob" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# A verdict that does not say how much it read is a verdict a reader cannot
# size. This is also the check that fails when the walk quietly probes nothing.
assert_contains "the_accepting_verdict_names_how_many_blobs_it_read" "$RUN_OUTPUT" \
  "serves all ${BLOBS_DUAL_PLATFORM} referenced blob" \
  "the 2 manifest fixtures carry 1 config + 3 layers each, so a full walk is ${BLOBS_DUAL_PLATFORM} probes" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# THE LOAD-BEARING COUNT. Not "at least 1 blob was read": every blob of every
# platform, or a lost object in the half nobody probed is still invisible.
blob_gets="$(count_requests "^GET 0-0 https://ghcr\.io/v2/gophersys/base/blobs/sha256:")"
assert_equal "every_blob_of_every_platform_is_probed_with_a_ranged_get" \
  "$BLOBS_DUAL_PLATFORM" "$blob_gets" \
  "1 config + 3 layers, on each of 2 platforms" \
  "a ranged GET is Range: bytes=0-0 — it costs 1 byte and it proves the object SERVES" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# THE ANTI-HEAD CHECK. The reason this file has a section of its own: a HEAD is
# answered by ghcr.io's metadata tier and a GET is answered by the object store
# behind a 307, so a HEAD that 200s is not evidence of anything. Revert the probe
# to HEAD and this check says so, whatever the stimulus below does.
#
# 2 conditions, 1 check, on purpose. "no HEAD was sent" is TRUE of an
# implementation that sends nothing at all, and that is the shape this verb had
# before ledger #118 — so a bare count of HEADs would have passed against the
# very defect the section is about.
head_requests="$(count_requests "^HEAD ")"
if [[ "$blob_gets" -lt 1 ]]; then
  fail_check "the_blob_probe_is_a_get_and_never_a_head" \
    "no blob was probed at all, so this run asserted nothing about the METHOD" \
    "requests were:" "${RUN_REQUESTS:-<none>}"
elif [[ "$head_requests" -ne 0 ]]; then
  fail_check "the_blob_probe_is_a_get_and_never_a_head" \
    "want: 0 HEAD requests" "got:  ${head_requests}" \
    "measured 2026-08-18: HEAD of a real ghcr.io layer answers 200 with no redirect," \
    "while GET of the same url answers 307 to pkg-containers.githubusercontent.com," \
    "so a HEAD never reaches the store that holds the bytes" \
    "requests were:" "${RUN_REQUESTS:-<none>}"
else
  pass_check "the_blob_probe_is_a_get_and_never_a_head"
fi

# -------- the incident: HEAD 200, GET 404 -------------------------------
# The whole point. A checker built on HEAD sees 200 and reports the image fine;
# the ranged GET sees the 404 that every `docker pull` of this image sees.
write_registry_map \
  "GET /blobs/${INCIDENT_BLOB}|404|" \
  "HEAD /blobs/${INCIDENT_BLOB}|200|${BLOB_FIRST_BYTE}"
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"

assert_verify_refused_naming "a_blob_that_answers_head_200_and_get_404_is_refused_naming_the_digest" \
  "$INCIDENT_BLOB" \
  "the index parses, both platforms are declared, and 1 referenced layer is GONE from the store" \
  "this is ledger #118 exactly: 4 manifests referenced d14f6240 and every one of them still parsed" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# Each of the 3 below is a REFUSAL that names something, and never a bare
# `assert_contains`. The accepting run of this verb already prints the ref and
# both platform names, so "the output mentions linux/amd64" is true of a run
# that found nothing wrong — the assertion has to carry the non-zero half with
# it or it is 2 unrelated facts wearing 1 name.
assert_verify_refused_naming "the_refusal_names_the_platform_the_bad_blob_belongs_to" \
  "linux/amd64" \
  "a digest with no platform beside it leaves an operator to search both manifests by hand" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

assert_verify_refused_naming "the_refusal_names_the_http_status_the_registry_gave" \
  "404" \
  "404 and 403 are different incidents — one is a lost object, the other is a lost grant" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

assert_verify_refused_naming "the_refusal_names_the_image_it_is_about" \
  "ghcr.io/gophersys/base" \
  "the verb runs once per image in CI, and a log line with no ref in it is a line no reader can place"

# -------- a per-platform manifest the registry will not serve ------------
# The manifest of a variant is a blob too. An index whose entries are dangling
# is the same defect one level up, and it must not read as a healthy publish.
write_registry_map "/manifests/${ARM64_MANIFEST_DIGEST}|404|"
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"
assert_verify_refused_naming "a_per_platform_manifest_the_registry_will_not_serve_is_refused" \
  "$ARM64_MANIFEST_DIGEST" \
  "the index declares linux/arm64 and the manifest it points at is not there" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# -------- a manifest that references nothing ----------------------------
# A walk over an empty layer list probes 0 blobs and finds 0 failures, which is
# a green that read nothing — the exact shape this repository refuses everywhere
# else. It has to be a refusal, not a pass.
write_registry_map "/manifests/${AMD64_MANIFEST_DIGEST}|200|${IMAGE_MANIFEST_NO_LAYERS}"
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL"
assert_verify_refused_naming "a_manifest_that_references_no_layer_is_refused" \
  "references no layer" \
  "an image manifest with an empty layers array is not an image, and a walk over it" \
  "reports 0 failures out of 0 probes — a verdict about nothing" \
  "requests were:" "${RUN_REQUESTS:-<none>}"

# -------- no credential -> a refusal that NAMES the credential -----------
# ghcr.io answers an anonymous token request for a private package with a 403,
# and the packages of this repository are private. A probe that fell back to an
# anonymous read would report every blob of every image as unreachable — a red
# that is about the credential and says it is about the image. Worse, a probe
# that treated "no credential" as "nothing to check" would be green over
# nothing, which is the FAIL-NOT-SKIP rule.
#
# 3 conditions, 1 check. "0 requests were made" is true of an implementation
# that makes no request ever, so it may not stand as a check of its own.
write_registry_map
run_verify "$BASE_CTL" STUB_MANIFEST_JSON="$MANIFEST_DUAL" \
  GHCR_TOKEN= GITHUB_TOKEN= GH_TOKEN= DOCKER_CONFIG="$EMPTY_DOCKER_CONFIG"
credential_requests="$(count_requests "^(GET|HEAD) ")"
if verb_is_missing "an_absent_registry_credential_is_a_refusal_that_names_it"; then
  :
elif [[ "$RUN_STATUS" -eq 0 ]]; then
  fail_check "an_absent_registry_credential_is_a_refusal_that_names_it" \
    "want: a non-zero exit status — with no credential nothing about the blobs was checked" \
    "got:  0" "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif ! grep -qF -- "GITHUB_TOKEN" <<< "$RUN_OUTPUT"; then
  fail_check "an_absent_registry_credential_is_a_refusal_that_names_it" \
    "the run exited ${RUN_STATUS} and never named a variable the reader can set" \
    "$VERB_NOTE" "output was:" "$RUN_OUTPUT"
elif [[ "$credential_requests" -ne 0 ]]; then
  fail_check "an_absent_registry_credential_is_a_refusal_that_names_it" \
    "it refused, but it made ${credential_requests} request(s) first" \
    "an anonymous read of a private package 403s, and a red about the credential must not" \
    "be dressed up as a red about the image" \
    "requests were:" "${RUN_REQUESTS:-<none>}"
else
  pass_check "an_absent_registry_credential_is_a_refusal_that_names_it"
fi

test_summary "$TEST_NAME"
