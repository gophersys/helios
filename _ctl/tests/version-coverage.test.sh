#!/usr/bin/env bash
#
# _ctl/tests/version-coverage.test.sh — every pin is classified, exactly once.
#
# Static means static: this file reads files, and it asks .ci/smoke.sh for a
# LISTING that starts no container. It calls no daemon and it reaches no
# network, so it runs identically on a laptop and on a CI runner — and, unlike a
# real smoke run, it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# versions.env holds 44 pins and base/Dockerfile declares 33 version ARGs. The
# smoke test asserts a version for a HANDFUL of them: buildx, and nothing else.
# Every other pin is a number in a file that nothing compares against the image.
# So a build that installs another version than the pin declares publishes, and
# the gate agrees, because no check ever looked.
#
# The hole is invisible, and that is the point. A reader of .ci/smoke.sh sees a
# long list of `<tool> --version` lines and reads coverage into it, but those
# lines only prove the binary RUNS. `gh --version` is green on gh 2.40 while
# versions.env pins 2.90.
#
# ============================================================================
# THE RULE THIS FILE ENCODES
# ============================================================================
#
# Every pin carries exactly 1 classification, and the 3 classes are the whole
# taxonomy:
#
#   asserted           the smoke runs the tool and compares the reported version
#   not-a-version      the pin is a digest, a package name or a branch
#   not-in-this-image  the image does not install the tool
#
# The test never says WHICH class a pin must carry. That choice belongs to
# .ci/smoke.sh, and a test that made it would have to move with every pin. What
# the test enforces is that a pin cannot be SILENT: a new row in versions.env,
# or a new ARG in base/Dockerfile, has no class, so this file fails and names
# it. The author then chooses — assert it, or write down why it is not asserted.
# Both answers are a visible line in a diff. Saying nothing is not an answer.
#
# "not-a-version" and "not-in-this-image" are not exceptions that weaken the
# rule. They are the 2 honest answers to "why is this pin not compared", and
# every use of them is read in review.
#
# ============================================================================
# THE SEAM
# ============================================================================
#
#   SMOKE_LIST_PINS=1 bash .ci/smoke.sh <image>
#
# prints 1 record per pin, `<NAME>|<class>`, and exits 0. It runs NO docker
# command, because a classification is a property of the FILES and not of a
# container. That last clause is checked: a listing that started a container
# could not run in the pull request gate, which is the only place this rule is
# worth having.
#
# Usage: bash _ctl/tests/version-coverage.test.sh
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

TEST_NAME="version-coverage.test.sh"

STUB_BIN="$TESTS_DIR/stubs"

# The 2 homes a pin lives in, and the image that owns each one. Named pair by
# pair rather than found by a glob, for the reason platform-policy.test.sh names
# its list: a glob that stops matching leaves a green result that read nothing.
CLOUD_PIN_HOME="versions.env"
BASE_PIN_HOME="base/Dockerfile"

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
FIXTURE_PINS="$TESTS_DIR/fixtures/pin-coverage/pins.env"
FIXTURE_CLASSIFICATION="$TESTS_DIR/fixtures/pin-coverage/classification.txt"

# The classes the taxonomy allows. A 4th one is not a class, it is a hole with a
# name, so the reader below reports it.
#
# An array, and not 1 space-separated string: this file runs with IFS=$'\n\t',
# so a `for` over such a string reads the whole string as 1 word and every class
# then looks unknown. Measured here on the first run of this test.
VALID_CLASSES=("asserted" "not-a-version" "not-in-this-image")
VALID_CLASSES_TEXT="asserted, not-a-version, not-in-this-image"

# ---------------------------------------------------------------------------
# The readers.
# ---------------------------------------------------------------------------

# env_pin_names <file> — every `NAME=` row of a versions.env-shaped file, 1 name
# per line, sorted. A comment row and a blank row are not pins.
#
# awk and not `grep | cut`: grep exits 1 when it matches nothing, and under
# `set -e` with pipefail that kills the run instead of reporting an empty home.
# An empty home is a defect this file has to REPORT, so it must survive reading
# one.
function env_pin_names() {
  awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ { print $1 }' "$1" | sort -u
}

# dockerfile_pin_names <file> — every version-shaped ARG name the Dockerfile
# declares, 1 per line, sorted.
#
# Version-shaped is `*_VERSION`, `*_REF` or `*_CHANNEL`, the same 3 suffixes
# dockerfile-args.test.sh governs. The other ARGs (TARGETPLATFORM, USERNAME,
# USER_UID) pin no tool, so no smoke test can assert them.
function dockerfile_pin_names() {
  awk '
    /^[[:space:]]*ARG[[:space:]]+/ {
      split($2, parts, "=")
      if (parts[1] ~ /(_VERSION|_REF|_CHANNEL)$/) { print parts[1] }
    }
  ' "$1" | sort -u
}

# classification_records <text> — the `<NAME>|<class>` records inside a listing,
# 1 per line. Every other line is dropped, so the log lines .ci/smoke.sh prints
# around the records cannot be read as data.
function classification_records() {
  printf '%s\n' "$1" | awk -F'|' '/^[A-Za-z_][A-Za-z0-9_]*\|/ { print $1 "|" $2 }'
}

# record_names <records> — the NAME column, 1 per line, in the order given.
function record_names() {
  printf '%s\n' "$1" | awk -F'|' 'NF { print $1 }'
}

# names_absent_from <names> <reference> — every name of the first list that the
# second list does not hold. Prints nothing when the first list is covered.
function names_absent_from() {
  local names="$1" reference="$2"
  local name out=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if ! printf '%s\n' "$reference" | grep -qx -- "$name"; then
      out="${out:+${out}
}${name}"
    fi
  done <<< "$names"
  printf '%s' "$out"
}

# repeated_names <names> — every name the list holds more than once.
function repeated_names() {
  printf '%s\n' "$1" | awk 'NF' | sort | uniq -d
}

# unknown_class_records <records> — every record whose class is outside the
# taxonomy. A typo in a class name would otherwise classify a pin into nothing
# while looking like an answer.
function unknown_class_records() {
  local records="$1"
  local name class known valid out=""
  while IFS='|' read -r name class; do
    [[ -z "$name" ]] && continue
    known=0
    for valid in "${VALID_CLASSES[@]}"; do
      if [[ "$class" == "$valid" ]]; then
        known=1
      fi
    done
    if [[ "$known" -eq 0 ]]; then
      out="${out:+${out}
}${name}: '${class}'"
    fi
  done <<< "$records"
  printf '%s' "$out"
}

# count_lines <text> — how many non-empty lines the text holds.
function count_lines() {
  local text="$1" line total=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    total=$((total + 1))
  done <<< "$text"
  printf '%s' "$total"
}

LISTING_TEXT=""
LISTING_STATUS=0
LISTING_ARGV=""

# run_listing <image> — ask .ci/smoke.sh to classify the pins of 1 image.
#
# The stub docker is first on PATH and every argv it receives is recorded, so a
# listing that reached for a container is reported instead of being believed.
function run_listing() {
  local image="$1"
  local log
  log="$(mktemp)"
  LISTING_STATUS=0
  LISTING_TEXT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" SMOKE_LIST_PINS=1 \
    bash "$REPO_ROOT/.ci/smoke.sh" "$image" < /dev/null 2>&1)" || LISTING_STATUS=$?
  LISTING_ARGV="$(cat "$log")"
  rm -f "$log"
}

# assert_listing_is_static <check name> — 2 conditions, 1 check, on purpose: the
# listing exits 0, and it called docker not once. As separate checks the first
# passes on a run that smoked the whole image, which is the exact confusion this
# seam exists to prevent — a listing that needs a daemon cannot run in the pull
# request gate.
function assert_listing_is_static() {
  local name="$1"
  if [[ "$LISTING_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "SMOKE_LIST_PINS=1 exited ${LISTING_STATUS}" \
      "docker was called with:" "${LISTING_ARGV:-<no docker invocation>}" \
      "output was:" "$LISTING_TEXT"
  elif [[ -n "$LISTING_ARGV" ]]; then
    fail_check "$name" \
      "the listing exited 0, and it called docker:" \
      "$LISTING_ARGV" \
      "a classification is a property of the files, so it must run with no daemon at all"
  else
    pass_check "$name"
  fi
}

# assert_home_is_covered <check name> <pin names> <records> <home>
#
# The rule, applied to 1 pin home. Each direction is reported separately,
# because each one asks the author for a different edit.
function assert_home_is_covered() {
  local name="$1" pins="$2" records="$3" home="$4"
  local names unclassified ghosts repeats unknown
  names="$(record_names "$records")"
  unclassified="$(names_absent_from "$pins" "$names")"
  ghosts="$(names_absent_from "$names" "$pins")"
  repeats="$(repeated_names "$names")"
  unknown="$(unknown_class_records "$records")"

  if [[ -n "$unclassified" ]]; then
    fail_check "${name}_classifies_every_pin" \
      "these pins of ${home} carry no classification:" \
      "$unclassified" \
      "assert the pin in the smoke test, or classify it not-a-version or not-in-this-image" \
      "a pin nothing compares against the image is a number in a file"
  else
    pass_check "${name}_classifies_every_pin"
  fi

  if [[ -n "$repeats" ]]; then
    fail_check "${name}_classifies_each_pin_exactly_once" \
      "these pins carry more than 1 classification:" \
      "$repeats" \
      "2 answers for 1 pin means the reader of the smoke test cannot tell which one holds"
  else
    pass_check "${name}_classifies_each_pin_exactly_once"
  fi

  if [[ -n "$ghosts" ]]; then
    fail_check "${name}_classifies_only_real_pins" \
      "these names carry a classification and are no pin of ${home}:" \
      "$ghosts" \
      "delete the stale entry, or restore the pin the entry names" \
      "a classification for a pin that is gone describes a file that no longer exists"
  else
    pass_check "${name}_classifies_only_real_pins"
  fi

  if [[ -n "$unknown" ]]; then
    fail_check "${name}_uses_only_the_3_classes" \
      "these records carry a class outside the taxonomy:" \
      "$unknown" \
      "the 3 classes are: ${VALID_CLASSES_TEXT}"
  else
    pass_check "${name}_uses_only_the_3_classes"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the counter-stimulus: every detector FIRES, and stays quiet ------
# This runs before the real files on purpose. A verdict on versions.env means
# nothing until the same functions have been watched to report a pin file that
# is broken AND to leave a correct one alone.
if [[ ! -f "$FIXTURE_PINS" || ! -f "$FIXTURE_CLASSIFICATION" ]]; then
  fail_check "counter_stimulus_fixtures_exist" \
    "the fixtures this test proves itself with are absent:" \
    "${FIXTURE_PINS}" "${FIXTURE_CLASSIFICATION}"
else
  pass_check "counter_stimulus_fixtures_exist"

  fixture_pins="$(env_pin_names "$FIXTURE_PINS")"
  fixture_records="$(classification_records "$(cat "$FIXTURE_CLASSIFICATION")")"
  fixture_names="$(record_names "$fixture_records")"

  assert_equal "counter_stimulus_reads_5_pins_and_skips_the_comments" \
    "5" "$(count_lines "$fixture_pins")" \
    "the fixture holds 5 pin rows, 4 comment rows and 3 blank rows" \
    "a reader that counts a comment as a pin reports a defect that is not there"

  # The quiet direction. The fixture pair agrees, so every detector must be
  # silent. One that reports a correct file is as useless as one that reports
  # nothing.
  assert_equal "counter_stimulus_leaves_the_matching_pair_alone" \
    "" "$(names_absent_from "$fixture_pins" "$fixture_names")$(names_absent_from "$fixture_names" "$fixture_pins")$(repeated_names "$fixture_names")$(unknown_class_records "$fixture_records")" \
    "pins.env and classification.txt cover each other exactly"

  # A new pin, and nobody classified it. This is the shape of the defect: a row
  # is appended to versions.env, and the smoke test says nothing about it.
  appended_pins="$(mktemp)"
  cat "$FIXTURE_PINS" > "$appended_pins"
  printf 'FOO_VERSION=1.2.3\n' >> "$appended_pins"
  appended_report="$(names_absent_from "$(env_pin_names "$appended_pins")" "$fixture_names")"
  rm -f "$appended_pins"
  assert_equal "counter_stimulus_reports_the_pin_that_nobody_classified" \
    "FOO_VERSION" "$appended_report" \
    "a pin with no classification is the defect this whole file exists to catch"

  # The mirror direction. A pin is deleted and its classification stays behind,
  # so the smoke test describes a file that no longer holds that row.
  deleted_pins="$(mktemp)"
  grep -v '^GH_VERSION=' "$FIXTURE_PINS" > "$deleted_pins"
  deleted_report="$(names_absent_from "$fixture_names" "$(env_pin_names "$deleted_pins")")"
  rm -f "$deleted_pins"
  assert_equal "counter_stimulus_reports_the_classification_whose_pin_is_gone" \
    "GH_VERSION" "$deleted_report" \
    "a stale classification is read as coverage, and it covers nothing"

  # Exactly once, and not at least once.
  duplicated_names="${fixture_names}
GH_VERSION"
  assert_equal "counter_stimulus_reports_the_pin_that_carries_2_classes" \
    "GH_VERSION" "$(repeated_names "$duplicated_names")" \
    "2 answers for 1 pin is not coverage"

  assert_contains "counter_stimulus_reports_a_class_outside_the_taxonomy" \
    "$(unknown_class_records "GH_VERSION|probably-fine")" "GH_VERSION" \
    "a typo in a class name classifies a pin into nothing while it looks like an answer"
fi

# -------- 2. the seam: the listing runs, and it starts no container --------
run_listing cloud
assert_listing_is_static "cloud_pin_listing_runs_and_calls_no_docker"
cloud_records="$(classification_records "$LISTING_TEXT")"
cloud_record_total="$(count_lines "$cloud_records")"

run_listing base
assert_listing_is_static "base_pin_listing_runs_and_calls_no_docker"
base_records="$(classification_records "$LISTING_TEXT")"
base_record_total="$(count_lines "$base_records")"

# A listing that parses into 0 records makes every rule below vacuous, and a
# vacuous rule reports a clean file it never read. So the liveness of the reader
# is a check of its own.
if [[ "$cloud_record_total" -ge 1 ]]; then
  pass_check "cloud_pin_listing_holds_at_least_one_record"
else
  fail_check "cloud_pin_listing_holds_at_least_one_record" \
    "no <NAME>|<class> record came out of SMOKE_LIST_PINS=1 for cloud" \
    "either the seam is absent, or this test stopped reading its records"
fi
if [[ "$base_record_total" -ge 1 ]]; then
  pass_check "base_pin_listing_holds_at_least_one_record"
else
  fail_check "base_pin_listing_holds_at_least_one_record" \
    "no <NAME>|<class> record came out of SMOKE_LIST_PINS=1 for base" \
    "either the seam is absent, or this test stopped reading its records"
fi

# -------- 3. THE RULE, on both real pin homes --------
# cloud reads versions.env, the 1 home of the new mechanism. The base family
# reads the ARGs at the top of base/Dockerfile. The 2 homes must be free to move
# apart, so each is judged against the image that owns it.
assert_home_is_covered "cloud_versions_env" \
  "$(env_pin_names "$REPO_ROOT/$CLOUD_PIN_HOME")" \
  "$cloud_records" \
  "$CLOUD_PIN_HOME"

assert_home_is_covered "base_dockerfile_args" \
  "$(dockerfile_pin_names "$REPO_ROOT/$BASE_PIN_HOME")" \
  "$base_records" \
  "$BASE_PIN_HOME"

test_summary "$TEST_NAME"
