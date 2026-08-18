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
# the test enforces is that a pin cannot be SILENT: a new row in versions.env
# has no class in one of the 2 tables, so this file fails and names it. The
# author then chooses — assert it, or write down why it is not asserted. Both
# answers are a visible line in a diff. Saying nothing is not an answer.
#
# ============================================================================
# THE ABSENCE PROBE, AND WHERE IT MAY APPEAR (ledger #103)
# ============================================================================
#
# The class field of a TABLE row takes an optional absence probe, and exactly 1
# class may carry one:
#
#   not-in-this-image:<binary>[,<binary>...]
#
# The guest then asserts `! command -v <binary>` for each one. Without it the
# class is an assertion nobody checks — the row says the image does not install
# the tool, no command runs, and a tool that leaked in reads exactly like a tool
# that stayed out.
#
# 3 rules, and this file holds all 3 statically, because the driver's own
# refusals only fire on the image it is asked to smoke and this gate reads every
# table of every image at once:
#
#   1. a probe may appear ONLY on not-in-this-image. An image that INSTALLS a
#      tool cannot also be asserted not to have it, and `asserted:gh` reads like
#      a 4th class.
#   2. the probe field is not empty. `not-in-this-image:` is a colon that
#      promises a check and names no binary to run one against.
#   3. it is a comma-separated list of BINARY NAMES. An empty element —
#      `not-in-this-image:aws,` — is the shape the driver silently drops:
#      class_probes pipes through `tr` inside a `$( )`, which strips the
#      trailing empty field, so that row reaches the guest as 1 probe and the
#      driver's empty-probe refusal never fires. Measured 2026-08-17. The rule
#      is enforced HERE, where the whole table is read as text.
#
# The suffix is a property of the TABLE and never of the LISTING: the seam
# prints the BARE class, so a consumer of it reads the 3-word taxonomy and never
# has to know this grammar. `the_listing_prints_the_bare_class` holds that.
#
# ============================================================================
# 2 HOMES, 5 TABLES
# ============================================================================
#
# There were 2 homes: the cloud family read versions.env and the base family
# read the version ARGs at the top of base/Dockerfile. base/Dockerfile went
# value-less on 2026-08-17 — every pin of it arrives as a generated
# --build-arg out of versions.env — so it declares no value for any reader to
# find, and this file read it for 19 pins that are not there any more.
#
# A second home came back, and it is a DIFFERENT file. flutter, zephyr and
# zephyr-devbox declare their own `ARG NAME=value` blocks and consume no build
# arg from versions.env, so each one's own Dockerfile is a pin home, and
# .ci/smoke.sh reads it as one with a class table of its own. 2 kinds of home,
# 5 tables:
#
#   versions.env              PIN_CLASSES_CLOUD, PIN_CLASSES_BASE
#   flutter/Dockerfile        PIN_CLASSES_FLUTTER
#   zephyr/Dockerfile         PIN_CLASSES_ZEPHYR
#   zephyr-devbox/Dockerfile  PIN_CLASSES_DEVBOX
#
# The 2 tables over the 1 shared home are deliberate: `cloud` asserts the CI
# fold and the base family asserts what `base` installs, so a pin one of them
# does not carry takes `not-in-this-image` in that table. So the rule below runs
# TWICE over the SAME home, once per table. Both directions still bite. A row
# added to versions.env is unclassified in whichever table forgot it, and a
# table row whose pin was deleted is a classification of a file that no longer
# holds it.
#
# A child image reads 2 homes, so its listing carries the records of both. The
# records are FILTERED to the home under judgement before the rule reads them:
# unfiltered, every versions.env pin reads as a row PIN_CLASSES_FLUTTER forgot.
# The filter is by name and it is unambiguous — measured 2026-08-17, no name is
# declared in versions.env and in a child Dockerfile at the same time.
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
# prints 1 record per pin of every home that image has, `<NAME>|<class>`, and
# exits 0. It runs NO docker command, because a classification is a property of
# the FILES and not of a container. That last clause is checked: a listing that
# started a container could not run in the pull request gate, which is the only
# place this rule is worth having.
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

# The 1 home every image's pins live in, named rather than found by a glob, for
# the reason platform-policy.test.sh names its list: a glob that stops matching
# leaves a green result that read nothing. .ci/smoke.sh calls it PIN_HOME and
# spells the same path, because a second spelling here would let this test
# report coverage of a file the driver does not read.
PIN_HOME="versions.env"

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

# The 1 class an absence probe may hang off, and the shape of a binary name. The
# shape is deliberately narrow: a probe reaches the guest as `command -v <name>`,
# so a name with a space, a slash or a shell metacharacter in it is not a binary
# the guest can look for and it must be reported here rather than run there.
PROBE_CLASS="not-in-this-image"
BINARY_NAME_SHAPE='^[A-Za-z0-9][A-Za-z0-9._+-]*$'

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

# dockerfile_pin_names <file> — every VALUE-FUL `ARG NAME=value` of a Dockerfile,
# 1 name per line, sorted.
#
# This reader stood here for base/Dockerfile, went with that home when
# base/Dockerfile went value-less, and is back for a DIFFERENT file: the 3
# per-image Dockerfiles, which declare their pins inline and are each a pin home
# of their own image. A value-less `ARG NAME` declares nothing to classify and is
# not matched, which is why base/Dockerfile and cloud/Dockerfile could be handed
# to this reader and would answer with nothing at all.
#
# It takes the WHOLE file and not a "top block". The ARGs-at-top convention is a
# rule of this repository and not a property a reader can measure, so an ARG
# somebody adds further down is CLASSIFIED rather than silently skipped — the
# same choice `home_pin_names` in .ci/smoke.sh makes, and it must stay the same
# choice or the 2 readers disagree about what a pin is.
#
# WHAT THIS DOES NOT CLOSE. The comment that stood here said no reader covered
# those 3 files and called it ledger #102 whole. That is now true of half of it:
# the CLASSIFICATION half is closed, here and in the driver, so a new `ARG
# NAME=value` in a child Dockerfile with no table row is red in the PULL REQUEST
# gate and not only at build time. The VALUE-HOME half is open and unchanged —
# those 4 files still spell their own pin values, `PIN_VALUE_HOMES` in
# _ctl/lib.sh is still 5, and `bump_pin` still writes into every one of them
# every Monday. So does the other half of #102 that no reader here can see: a
# pin a child inherits from ANOTHER child (WEST_VERSION lives in
# zephyr/Dockerfile and zephyr-devbox carries west) is in no home this file
# reads, because closing it means walking the FROM graph in the driver.
function dockerfile_pin_names() {
  awk '
    match($0, /^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*=/) {
      name = substr($0, RSTART, RLENGTH)
      sub(/^[[:space:]]*ARG[[:space:]]+/, "", name)
      sub(/=$/, "", name)
      print name
    }
  ' "$1" | sort -u
}

# classification_records <text> — the `<NAME>|<class>` records inside a listing,
# 1 per line. Every other line is dropped, so the log lines .ci/smoke.sh prints
# around the records cannot be read as data.
function classification_records() {
  printf '%s\n' "$1" | awk -F'|' '/^[A-Za-z_][A-Za-z0-9_]*\|/ { print $1 "|" $2 }'
}

# class_table_records <table variable name> — the `<NAME>|<class>` rows of 1
# classification table, read out of the TEXT of .ci/smoke.sh.
#
# This is a second reader of a file that already offers a seam, which needs the
# reason stated. The seam prints the LISTING, and a listing is built by walking
# versions.env: it therefore cannot carry a row for a pin that versions.env no
# longer holds, and it prints 1 record for a pin the table answers twice. Those
# 2 defects are properties of the TABLE, so they are only visible in the table.
# Widening the seam to emit them is a change to .ci/smoke.sh and is open work;
# until then this reader is how the 2 directions stay able to fail, and
# `_class_table_agrees_with_the_listing` holds it against the seam so the 2
# cannot drift apart quietly.
#
# The heredoc delimiter is matched on its own line, exactly as .ci/smoke.sh
# writes it, so the reader stops where the table stops.
function class_table_records() {
  awk -v want="$1" '
    $0 ~ ("^read -r -d .. " want " <<") { inside = 1; next }
    /^PIN_CLASS_TABLE$/ { inside = 0; next }
    inside && /^[A-Za-z_][A-Za-z0-9_]*\|/ {
      position = index($0, "|")
      rest = substr($0, position + 1)
      second = index(rest, "|")
      if (second == 0) { print substr($0, 1, position - 1) "|" rest; next }
      print substr($0, 1, position - 1) "|" substr(rest, 1, second - 1)
    }
  ' "$REPO_ROOT/.ci/smoke.sh"
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
    if ! grep -qx -- "$name" <<< "$reference"; then
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

# bare_class <class field> — the class without its absence probe, which is the
# word the taxonomy governs. It is `${field%%:*}` for the reason .ci/smoke.sh
# spells it the same way: the probe is a SUFFIX on the class, so the class is
# everything before the first colon and a field with no colon is its own class.
function bare_class() {
  printf '%s' "${1%%:*}"
}

# probe_binaries <class field> — the binaries a class field names, 1 per line,
# INCLUDING the empty ones. Prints nothing when the field names no probe.
#
# The empty ones are the point, so this splits with parameter expansion and never
# with `tr` inside a `$( )`: command substitution strips trailing newlines, so
# `printf '%s' "aws," | tr ',' '\n'` comes back as the single word `aws` and the
# malformed row reads as a correct one. That is the exact hole in the driver's
# own reader which rule 3 of the header exists to cover.
function probe_binaries() {
  local field="$1" remaining
  [[ "$field" == *:* ]] || return 0
  remaining="${field#*:}"
  while :; do
    printf '%s\n' "${remaining%%,*}"
    [[ "$remaining" == *,* ]] || return 0
    remaining="${remaining#*,}"
  done
}

# unknown_class_records <records> — every record whose class is outside the
# taxonomy. A typo in a class name would otherwise classify a pin into nothing
# while looking like an answer.
#
# The comparison is against the BARE class. Reading the raw field made every
# probe-carrying row of every table report as a 4th class the day the probe
# arrived — 14 rows, 2 checks, and the taxonomy this file guards was not the
# thing that had changed.
function unknown_class_records() {
  local records="$1"
  local name class known valid out=""
  while IFS='|' read -r name class; do
    [[ -z "$name" ]] && continue
    known=0
    for valid in "${VALID_CLASSES[@]}"; do
      if [[ "$(bare_class "$class")" == "$valid" ]]; then
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

# probe_carrying_records <records> — every record whose class field names an
# absence probe at all, whatever the class. Legal in a table, and never in the
# listing: the seam's contract is the 3-word taxonomy.
function probe_carrying_records() {
  local records="$1"
  local name class out=""
  while IFS='|' read -r name class; do
    [[ -z "$name" ]] && continue
    [[ "$class" == *:* ]] || continue
    out="${out:+${out}
}${name}: '${class}'"
  done <<< "$records"
  printf '%s' "$out"
}

# misplaced_probe_records <records> — every record that hangs an absence probe
# off a class other than not-in-this-image. Rule 1 of the probe grammar.
function misplaced_probe_records() {
  local records="$1"
  local name class out=""
  while IFS='|' read -r name class; do
    [[ -z "$name" ]] && continue
    [[ "$class" == *:* ]] || continue
    [[ "$(bare_class "$class")" == "$PROBE_CLASS" ]] && continue
    out="${out:+${out}
}${name}: '${class}'"
  done <<< "$records"
  printf '%s' "$out"
}

# malformed_probe_records <records> — every record whose probe field is not 1 or
# more comma-separated binary names. Rules 2 and 3 of the probe grammar, reported
# together because both ask the author for the same edit: write a binary name.
function malformed_probe_records() {
  local records="$1"
  local name class binary out=""
  while IFS='|' read -r name class; do
    [[ -z "$name" ]] && continue
    [[ "$class" == *:* ]] || continue
    # `< <(...)` and not `<<< "$(...)"`, for the reason probe_binaries gives: a
    # command substitution strips the trailing newlines, and the empty binary
    # this rule exists to report is exactly what a trailing newline carries.
    while IFS= read -r binary; do
      [[ "$binary" =~ $BINARY_NAME_SHAPE ]] && continue
      out="${out:+${out}
}${name}: '${class}' names '${binary}', which is no binary the guest can look for"
    done < <(probe_binaries "$class")
  done <<< "$records"
  printf '%s' "$out"
}

# records_for_names <records> <names> — the records whose NAME the list holds.
#
# A child image reads 2 homes and its listing carries both, so the rule needs the
# records of the home it is judging. Without this filter every versions.env pin
# reads as a pin the child's own table forgot to hold a row for.
function records_for_names() {
  local records="$1" names="$2"
  local record out=""
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    if grep -qx -- "${record%%|*}" <<< "$names"; then
      out="${out:+${out}
}${record}"
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

# assert_home_is_covered <check name> <pin names> <listing records>
#                        <table records> <home>
#
# The rule, applied to 1 pin home. Each direction is reported separately,
# because each one asks the author for a different edit.
#
# ============================================================================
# WHY 2 RECORD SETS, AND WHICH DIRECTION READS WHICH
# ============================================================================
#
# The LISTING cannot express a stale classification, and it could until the pin
# homes collapsed to 1. .ci/smoke.sh builds it by walking versions.env and
# printing the class it finds for each row, so every name it emits IS a row of
# versions.env by construction, and it emits nothing for a table entry whose
# pin was deleted. While the base family read base/Dockerfile and the table read
# versions.env, that mismatch is what surfaced a ghost; with 1 home the ghost
# direction over the listing became a check that CANNOT FAIL. Measured on
# 2026-08-17 by deleting GREMLINS_VERSION from versions.env: the suite stayed
# green, and the 2 classifications of the deleted pin were never reported.
#
# So the 2 directions ABOUT TABLE ENTRIES — a stale entry, and an entry written
# twice — read the table itself, and the 2 directions ABOUT PINS read the
# listing, which is the seam and applies the shape rule for `*_SHA256_*` names
# that no table row covers. `${name}_class_table_agrees_with_the_listing` ties
# the 2 readers together, so a table reader that drifted is reported rather
# than believed: a parser that returned nothing would make both table
# directions vacuous in exactly the way this note exists to prevent.
function assert_home_is_covered() {
  local name="$1" pins="$2" records="$3" table_records="$4" home="$5"
  local names table_names unclassified ghosts repeats unknown untabled
  local misplaced_probes malformed_probes
  names="$(record_names "$records")"
  table_names="$(record_names "$table_records")"
  unclassified="$(names_absent_from "$pins" "$names")"
  ghosts="$(names_absent_from "$table_names" "$pins")"
  repeats="$(repeated_names "$table_names")"
  unknown="$(unknown_class_records "$table_records")"
  misplaced_probes="$(misplaced_probe_records "$table_records")"
  malformed_probes="$(malformed_probe_records "$table_records")"
  untabled="$(names_absent_from "$(printf '%s\n' "$names" | grep -v '_SHA256_' || true)" "$table_names")"

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
      "these pins carry more than 1 row in the classification table:" \
      "$repeats" \
      "2 answers for 1 pin means the reader of the smoke test cannot tell which one holds," \
      "and the listing hides it: class_row returns the FIRST match and the second row is dead text"
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
      "these table rows carry a class outside the taxonomy:" \
      "$unknown" \
      "the 3 classes are: ${VALID_CLASSES_TEXT}"
  else
    pass_check "${name}_uses_only_the_3_classes"
  fi

  if [[ -n "$misplaced_probes" ]]; then
    fail_check "${name}_probes_absence_only_on_${PROBE_CLASS//-/_}" \
      "these table rows hang an absence probe off another class:" \
      "$misplaced_probes" \
      "only ${PROBE_CLASS} takes one — an image that INSTALLS a tool cannot also be asserted not to have it" \
      "the guest runs '! command -v <binary>' for every probe, and there is nothing to run it against here"
  else
    pass_check "${name}_probes_absence_only_on_${PROBE_CLASS//-/_}"
  fi

  if [[ -n "$malformed_probes" ]]; then
    fail_check "${name}_names_a_binary_in_every_absence_probe" \
      "these table rows carry a probe that names no binary the guest can look for:" \
      "$malformed_probes" \
      "write ${PROBE_CLASS}:<binary>[,<binary>...], or drop the colon and take the bare class" \
      "a trailing comma is the shape the driver's own reader drops, so this rule is the only one that sees it"
  else
    pass_check "${name}_names_a_binary_in_every_absence_probe"
  fi

  if [[ -n "$untabled" ]]; then
    fail_check "${name}_class_table_agrees_with_the_listing" \
      "the listing classifies these pins and this file's table reader found no row for them:" \
      "$untabled" \
      "the 2 readers disagree, so the 2 directions above judge a table nobody is sure was read" \
      "— fix the reader in this file, never the answer it is compared against"
  else
    pass_check "${name}_class_table_agrees_with_the_listing"
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

  # -------- the absence probe, both directions of all 3 of its rules --------
  #
  # These are written inline rather than into fixtures/pin-coverage/, and that is
  # deliberate: classification.txt models a LISTING, the listing carries the BARE
  # class, and a probe written into that file would contradict the seam contract
  # the check at the bottom of section 2 holds.

  # The taxonomy reader reads the BARE class. Its raw-field reading is what made
  # every probe-carrying row of both versions.env tables red on the day the probe
  # arrived, so the quiet direction comes first.
  assert_equal "counter_stimulus_leaves_a_probe_on_a_valid_class_alone" \
    "" "$(unknown_class_records "TERRAFORM_VERSION|not-in-this-image:terraform")" \
    "not-in-this-image:terraform IS the class not-in-this-image, carrying a probe"
  assert_contains "counter_stimulus_reports_a_class_outside_the_taxonomy_that_carries_a_probe" \
    "$(unknown_class_records "GH_VERSION|not-in-the-image:gh")" "GH_VERSION" \
    "a typo in the class does not stop being a typo because a probe follows it"

  # Rule 1: only not-in-this-image takes a probe.
  assert_contains "counter_stimulus_reports_a_probe_on_the_wrong_class" \
    "$(misplaced_probe_records "GH_VERSION|asserted:gh")" "GH_VERSION" \
    "an image that installs gh cannot also be asserted not to have it"
  assert_equal "counter_stimulus_leaves_a_probe_on_not_in_this_image_alone" \
    "" "$(misplaced_probe_records "TERRAFORM_VERSION|not-in-this-image:terraform")" \
    "this is the 1 place a probe belongs, and a reader that reports it reports every real row"

  # Rule 2: the probe field is not empty.
  assert_contains "counter_stimulus_reports_a_probe_that_names_no_binary" \
    "$(malformed_probe_records "TERRAFORM_VERSION|not-in-this-image:")" "TERRAFORM_VERSION" \
    "a colon with nothing after it promises a check and gives the guest nothing to run"

  # Rule 3: every element of the list is a binary name. The trailing comma is the
  # case the driver's own reader cannot see, so it is the case that most needs a
  # counter-stimulus here.
  assert_contains "counter_stimulus_reports_the_empty_binary_of_a_trailing_comma" \
    "$(malformed_probe_records "AWS_CLI_VERSION|not-in-this-image:aws,")" "AWS_CLI_VERSION" \
    "class_probes in .ci/smoke.sh drops that empty element inside a \$( ), so the driver accepts this row"
  assert_contains "counter_stimulus_reports_a_probe_that_is_not_a_binary_name" \
    "$(malformed_probe_records "AWS_CLI_VERSION|not-in-this-image:aws --version")" "AWS_CLI_VERSION" \
    "the guest runs 'command -v <binary>', which is not a place to put a command line"
  assert_equal "counter_stimulus_leaves_a_comma_separated_probe_list_alone" \
    "" "$(malformed_probe_records "ANSIBLE_CORE_VERSION|not-in-this-image:ansible,ansible-playbook")" \
    "2 binaries for 1 pin is the shape the real tables use, and it is correct"

  # The seam contract. A probe in a LISTING record is the reader below finding
  # what only a table may carry.
  assert_contains "counter_stimulus_reports_a_probe_that_reached_a_listing_record" \
    "$(probe_carrying_records "TERRAFORM_VERSION|not-in-this-image:terraform")" "TERRAFORM_VERSION" \
    "legal in a table, and never in the listing: the seam's contract is the 3-word taxonomy"
  assert_equal "counter_stimulus_leaves_a_bare_class_record_alone" \
    "" "$(probe_carrying_records "TERRAFORM_VERSION|not-in-this-image")" \
    "the bare class is what every listing record must look like"
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

# -------- 3. THE RULE, on the 1 pin home, once per classification table -----
# Both tables read versions.env now. They are still 2 tables, because the CI
# fold is asserted in cloud and `not-in-this-image` in base and vice versa, so
# each one is judged against the SAME home separately: a pin classified in the
# cloud table and forgotten in the base table is a silent pin for 4 of the 5
# images, and 1 combined check would report it as covered.
#
# The pin names are read out of the home and never out of a table. A rule that
# read the listing would go on reporting coverage after the pin it covers was
# renamed — the listing and the reference would move together and agree about
# a file neither of them opened.
pin_names="$(env_pin_names "$REPO_ROOT/$PIN_HOME")"

assert_home_is_covered "cloud_versions_env" \
  "$pin_names" \
  "$cloud_records" \
  "$(class_table_records "PIN_CLASSES_CLOUD")" \
  "$PIN_HOME"

assert_home_is_covered "base_family_versions_env" \
  "$pin_names" \
  "$base_records" \
  "$(class_table_records "PIN_CLASSES_BASE")" \
  "$PIN_HOME"

# -------- 4. THE SAME RULE, on the 3 child Dockerfiles -----------------------
#
# A child image declares its own `ARG NAME=value` block and consumes no build arg
# from versions.env, so its own Dockerfile is a pin home with a table of its own.
# The driver refuses to run an image with an unclassified pin in EITHER home —
# and it refuses at build time, in the publish job, after the image is built.
# This loop is the same rule at pull request time: add an ARG to
# zephyr-devbox/Dockerfile with no row in PIN_CLASSES_DEVBOX, and the gate is red
# before the branch is merged rather than red 20 minutes into a publish.
#
# 3 parallel arrays and not 1 map, for the reason .ci/smoke.sh gives at
# PIN_HOMES: the mac's bash is 3.2 and has no associative array.
CHILD_IMAGES=("flutter" "zephyr" "zephyr-devbox")
CHILD_HOMES=("flutter/Dockerfile" "zephyr/Dockerfile" "zephyr-devbox/Dockerfile")
CHILD_TABLES=("PIN_CLASSES_FLUTTER" "PIN_CLASSES_ZEPHYR" "PIN_CLASSES_DEVBOX")

# Every record of every listing, for the seam check in section 5.
all_listing_records="${cloud_records}
${base_records}"

for child_index in "${!CHILD_IMAGES[@]}"; do
  child_image="${CHILD_IMAGES[$child_index]}"
  child_home="${CHILD_HOMES[$child_index]}"
  child_table="${CHILD_TABLES[$child_index]}"
  # The check names carry the image, so a reader finds the broken one in the list
  # of names and not only in the evidence. `-` is not a character a check name
  # takes here, because every other name in this file separates with `_`.
  child_label="$(printf '%s' "$child_image" | tr '-' '_')"

  run_listing "$child_image"
  assert_listing_is_static "${child_label}_pin_listing_runs_and_calls_no_docker"
  child_records="$(classification_records "$LISTING_TEXT")"
  all_listing_records="${all_listing_records}
${child_records}"

  # A child listing carries BOTH homes: versions.env through PIN_CLASSES_BASE,
  # and the file below. The rule judges 1 home, so the records are filtered to it.
  child_pins="$(dockerfile_pin_names "$REPO_ROOT/$child_home")"
  child_home_records="$(records_for_names "$child_records" "$child_pins")"

  # The direct statement of "the driver reads this home at all". Without it, a
  # driver that dropped the child home would be reported by the check below as 9
  # unclassified pins, which names the wrong edit: the table is not the thing
  # that went missing.
  if [[ "$(count_lines "$child_home_records")" -ge 1 ]]; then
    pass_check "${child_label}_pin_listing_reaches_its_own_Dockerfile"
  else
    fail_check "${child_label}_pin_listing_reaches_its_own_Dockerfile" \
      "SMOKE_LIST_PINS=1 for ${child_image} named no pin of ${child_home}" \
      "these are the pins that home declares:" \
      "${child_pins:-<the ARG reader in this file found none>}" \
      "either the driver stopped reading the child home, or this file stopped filtering to it"
  fi

  assert_home_is_covered "${child_label}_dockerfile" \
    "$child_pins" \
    "$child_home_records" \
    "$(class_table_records "$child_table")" \
    "$child_home"
done

# -------- 5. the seam prints the BARE class ---------------------------------
# The absence probe is a property of the TABLE. .ci/smoke.sh says so in its own
# header — "the class it prints is the BARE class" — and every consumer of the
# listing depends on it: smoke-contract.test.sh selects `<NAME>|asserted` rows
# with an anchored match, and this file's own taxonomy reader would have to learn
# the probe grammar. Nothing held that sentence until this check.
probe_carrying_listing_records="$(probe_carrying_records "$all_listing_records")"
if [[ -z "$probe_carrying_listing_records" ]]; then
  pass_check "the_listing_prints_the_bare_class"
else
  fail_check "the_listing_prints_the_bare_class" \
    "these listing records carry an absence probe, and a listing record is a bare class:" \
    "$probe_carrying_listing_records" \
    "the seam's contract is the 3-word taxonomy — a consumer of it must not have to parse a probe" \
    "the probe belongs in the table, where .ci/smoke.sh builds ABSENT_TABLE out of it"
fi

test_summary "$TEST_NAME"
