#!/usr/bin/env bash
#
# _ctl/tests/upstream-coverage.test.sh — every pin says where its next version
# comes from.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike a weekly run, it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# The 4 value homes hold 56 pins (counted by this file's own reader on
# 2026-08-17) and NOTHING says where the next value of any of them comes from.
# A pin is bumped when a human happens to look. `ZSH_VERSION=5.9` carries
# `# latest LTS as of 2026-04-19`, and that comment is 4 months old: it records
# the day somebody looked, and it goes on reading as current forever.
#
# A pin nobody watches is a snapshot that looks maintained. The nightly scan
# reports a CVE in an image; it cannot report that the pin is 3 releases behind,
# because no file in this repository knows what the current release is.
#
# ============================================================================
# THE RULE THIS FILE ENCODES
# ============================================================================
#
# Every pin of the 4 value homes carries exactly 1 row in _build/upstreams.txt,
# and every row of that table names a pin that exists. A pin is answered in 1 of
# 2 ways, and nothing else counts:
#
#   a datasource   the row names the mechanism that reads the current version,
#                  and the coordinate that mechanism needs
#   no-autobump    the row states, in a sentence, WHY this pin is not resolved
#
# The test never says WHICH datasource a pin must take. That choice belongs to
# the table, and a test that made it would have to move with every pin. What the
# test enforces is that a pin cannot be SILENT: a new row in versions.env, or a
# new version-shaped ARG in a Dockerfile home, has no upstream row, so this file
# fails and names it. The author then chooses — resolve it, or write down why
# not. Both answers are a visible line in a diff. Saying nothing is not an
# answer.
#
# ============================================================================
# BOTH DIRECTIONS, AND WHY (THE #107 GHOST LESSON)
# ============================================================================
#
# A coverage rule that only asks "is every pin answered" is half a rule. The
# other half is "does every answer still describe a pin". #107 is the shape: a
# rule that reads a LISTING instead of reading the HOMES goes on reporting
# coverage after the pin it covers was deleted or renamed. The listing agrees
# with itself forever, and the number it reports is the number of rows in the
# listing.
#
# So the reader here never treats the table as a source of truth. It reads the
# pins out of the 4 value homes and holds the table to THEM:
#
#   unanswered   a pin with no row            -> report the pin
#   ghost        a row naming no pin          -> report the row
#   repeated     2 rows for 1 pin             -> report the pin
#   unknown      a datasource outside the 12  -> report the row
#   placeholder  a no-autobump row whose reason is a token, not a sentence
#
# ============================================================================
# WHAT COUNTS AS A PIN, AND WHY THE 2 HOME SHAPES READ DIFFERENTLY
# ============================================================================
#
# versions.env is the ONE home of the cloud family and every row in it is a
# pin — including PYTHON_PACKAGE, which is an apt package name and not a semver.
# The 5 Dockerfile homes also declare build parameters that pin no tool
# (TARGETPLATFORM, USERNAME, BASE_TAG), so there the reader takes the 3
# version-shaped suffixes dockerfile-args.test.sh already governs: _VERSION,
# _REF, _CHANNEL.
#
# A `<TOOL>_SHA256_<ARCH>` row is not a pin in either home. It answers "which
# bytes", its own rule is in download-coverage.test.sh, and the resolver writes
# it beside the version it belongs to.
#
# Usage: bash _ctl/tests/upstream-coverage.test.sh
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

TEST_NAME="upstream-coverage.test.sh"

# The table, as a literal. A test that discovers the path it checks agrees with
# any path, a wrong one included.
UPSTREAMS_FILE="_build/upstreams.txt"

# The homes that hold a VALUE — READ THE LIST, never a count beside it.
# `base/Dockerfile` and `cloud/Dockerfile`
# declare their ARGs value-less and take the value from versions.env, so
# neither is a home. The same list download-coverage.test.sh names, and the
# same list PIN_VALUE_HOMES holds in _ctl/lib.sh — named again rather than
# shared, because a test that reads the list it checks agrees with a shortened
# one.
#
# NAMING IT AGAIN IS NOT ENOUGH BY ITSELF, and the 2 guards below it are the
# other half. This list named `runner/Dockerfile` after that file was deleted
# and `base/Dockerfile` after that file went value-less, and all 19 checks
# passed: `home_pins` returns nothing for a file it cannot open, and nothing for
# a file that declares no value-ful pin, so both dead entries contributed 0 pins
# and every rule below narrowed silently. The `>= 50` floor could not catch it
# either: every pin either entry ever held — RUNNER_VERSION, CICTL_VERSION and
# CLAUDE_CODE_VERSION for runner, and 54 of base's 55 — was ALSO a versions.env
# row, so `sort -u` absorbed the whole loss and the total never moved.
# Coverage that shrinks with no red is what this file exists to report,
# 1 layer up.
#
# THE GUARDS SPOKE ON THE EMBEDDED FOLD, and the shape of what they said is
# worth keeping. `zephyr/Dockerfile` and `zephyr-devbox/Dockerfile` became the 1
# `embedded/Dockerfile`, and the run reported 2 checks: the stale homes, AND 4
# rows of _build/upstreams.txt — WEST_VERSION, ZEPHYR_SDK_VERSION,
# ESPTOOL_VERSION and CODE_SERVER_VERSION — as rows naming a pin no home
# declares. Those 4 were a CASCADE of the first, not a second defect: the pins
# never moved, the file that declares them was renamed, and the table was never
# touched. A reader who "fixed" the table there would have deleted 4 correct
# rows to silence a stale literal.
#
# CODE_SERVER_VERSION's row IS deleted now, and the 2 cases are the opposite of
# each other rather than the same one twice: at the fold the pin still had a
# home and the LISTING was correct; at the devbox deletion (2026-08-19) the pin
# lost its home, so the row named nothing and had to go with it. The rule that
# tells them apart is this file's own — read the HOMES, never the listing.
VALUE_HOMES=(
  "versions.env"
  "mobile/Dockerfile"
  "embedded/Dockerfile"
)

# The whole taxonomy, as a literal, exactly as platform-policy.test.sh spells
# SANCTIONED out: a test that reads the taxonomy out of the table it checks
# agrees with a 14th datasource that nothing implements.
#
# 12 of them resolve a version from an upstream and are driven, 1 stub pin each,
# by _ctl/tests/resolve-upstream.test.sh. `no-autobump` is the 13th: it resolves
# nothing, and its row carries the reason instead.
DATASOURCES=(
  "github-release"
  "pypi"
  "npm"
  "go-proxy"
  "apt"
  "go-dl"
  "node-dist"
  "oci-index"
  "k8s-dl"
  "tailscale-pkgs"
  "flutter-releases"
  "eden-manifest"
  "no-autobump"
)
DATASOURCES_TEXT="github-release, pypi, npm, go-proxy, apt, go-dl, node-dist, oci-index, k8s-dl, tailscale-pkgs, flutter-releases, eden-manifest, no-autobump"

NO_AUTOBUMP="no-autobump"

# A stated reason is a sentence. 20 characters and a space is the floor, and the
# floor exists because every non-empty test passes `n/a`, `todo` and `-`. A row
# that answers with a token is a row that was written to make this file green.
REASON_MINIMUM_LENGTH=20

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
FIXTURE_DIR="$TESTS_DIR/fixtures/upstreams/coverage"
FIXTURE_ENV_HOME="$FIXTURE_DIR/pins.env"
FIXTURE_DOCKER_HOME="$FIXTURE_DIR/pins.Dockerfile"
FIXTURE_TABLE="$FIXTURE_DIR/upstreams.txt"

# ---------------------------------------------------------------------------
# The readers.
#
# awk and not `grep | cut` throughout: grep exits 1 when it matches nothing, and
# under `set -e` with pipefail that kills the run instead of reporting an empty
# result. An empty result is a defect this file has to REPORT, so it must
# survive reading one.
# ---------------------------------------------------------------------------

# env_home_pins <file> — every pin of a versions.env-shaped home, 1 name per
# line. Every `NAME=` row is a pin except a digest row; a comment row and a
# blank row are prose.
function env_home_pins() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk -F= '
    /^[[:space:]]*#/ { next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ {
      if ($1 ~ /_SHA256_[A-Z0-9_]+$/) { next }
      print $1
    }
  ' "$file"
}

# dockerfile_home_pins <file> — every version-shaped ARG a Dockerfile home
# declares WITH a value, 1 name per line.
#
# Version-shaped is `*_VERSION`, `*_REF` or `*_CHANNEL`, the same 3 suffixes
# dockerfile-args.test.sh governs. A build parameter (TARGETPLATFORM, USERNAME,
# BASE_TAG) pins no tool, so no upstream can answer it. A value-less `ARG NAME`
# is not a home either — that is how cloud/Dockerfile takes its value from
# versions.env.
function dockerfile_home_pins() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*ARG[[:space:]]+/ {
      split($2, parts, "=")
      if (parts[1] ~ /_SHA256_[A-Z0-9_]+$/) { next }
      if (parts[1] ~ /(_VERSION|_REF|_CHANNEL)$/ && $2 ~ /=/) { print parts[1] }
    }
  ' "$file"
}

# home_pins <home path> <home label> — the pins of 1 home, whichever shape it
# is. The 2 shapes are told apart by the NAME of the home and not by a list of
# paths: `versions.env` and the fixture `pins.env` are both env homes, and
# `base/Dockerfile` and the fixture `pins.Dockerfile` are both Dockerfile homes.
# A list of paths here would send the fixture pair through the wrong reader,
# which is exactly what the first run of this file did — the env home reported
# 0 pins and 2 detectors reported a fixture defect that was mine.
function home_pins() {
  local path="$1" label="$2"
  case "$label" in
    *Dockerfile) dockerfile_home_pins "$path" ;;
    *)           env_home_pins "$path" ;;
  esac
}

# all_home_pins <root> <home...> — every pin of every named home, sorted, once
# each. A pin declared in 2 homes is 1 pin and takes 1 row.
function all_home_pins() {
  local root="$1"
  shift
  local home out=""
  for home in "$@"; do
    out="${out}$(home_pins "${root}/${home}" "$home")
"
  done
  printf '%s' "$out" | awk 'NF' | sort -u
}

# table_rows <file> — the rows of the table, comments and blank rows dropped,
# trailing whitespace stripped. Prints nothing for an absent file, and the
# caller reports that rather than dying on it.
function table_rows() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    line ~ /^[[:space:]]*$/ { next }
    { sub(/[[:space:]]+$/, "", line); print line }
  ' "$file"
}

# row_pins <rows> — the pin column of every row, in the order given.
function row_pins() {
  awk -F'|' 'NF { print $1 }' <<< "$1"
}

# malformed_rows <rows> — every row that is not 4 non-empty fields. The same
# grammar check download-coverage.test.sh runs on its neighbour file: 1 table
# grammar in _build/, not 2.
function malformed_rows() {
  awk -F'|' '
    NF == 0 { next }
    {
      bad = 0
      if (NF != 4) { bad = 1 }
      else {
        for (i = 1; i <= 4; i++) {
          field = $i
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", field)
          if (field == "") { bad = 1 }
        }
      }
      if (bad) { print $0 }
    }
  ' <<< "$1"
}

# rows_with_an_unknown_datasource <rows> — every row whose 2nd field is outside
# the taxonomy. A typo answers a pin with nothing while looking like an answer,
# and the resolver would then fail at 09:00 on a Monday instead of here.
function rows_with_an_unknown_datasource() {
  local rows="$1"
  local row datasource known valid out=""
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    datasource="$(awk -F'|' '{ print $2 }' <<< "$row")"
    known=0
    for valid in "${DATASOURCES[@]}"; do
      if [[ "$datasource" == "$valid" ]]; then
        known=1
      fi
    done
    if [[ "$known" -eq 0 ]]; then
      out="${out:+${out}
}${row}"
    fi
  done <<< "$rows"
  printf '%s' "$out"
}

# no_autobump_rows_without_a_reason <rows> — every no-autobump row whose 4th
# field is a token rather than a sentence.
#
# `n/a`, `todo` and `-` all pass a non-empty test, and each one is a pin nobody
# decided about wearing the label of a pin somebody did. The floor is stated in
# REASON_MINIMUM_LENGTH and it holds a space, because the reader of this table
# is a human deciding whether to keep the exemption.
function no_autobump_rows_without_a_reason() {
  local rows="$1"
  local row datasource reason out=""
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    datasource="$(awk -F'|' '{ print $2 }' <<< "$row")"
    [[ "$datasource" == "$NO_AUTOBUMP" ]] || continue
    reason="$(awk -F'|' '{ print $4 }' <<< "$row")"
    if [[ "${#reason}" -lt "$REASON_MINIMUM_LENGTH" || "$reason" != *" "* ]]; then
      out="${out:+${out}
}${row}"
    fi
  done <<< "$rows"
  printf '%s' "$out"
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
  awk 'NF' <<< "$1" | sort | uniq -d
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

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE COUNTER-STIMULUS — every detector FIRES, and every detector is QUIET
# ===========================================================================
#
# This runs before the real files on purpose. A verdict on _build/upstreams.txt
# means nothing until the same functions have been watched to report a table
# that is broken AND to leave a correct one alone.
if [[ ! -f "$FIXTURE_ENV_HOME" || ! -f "$FIXTURE_DOCKER_HOME" || ! -f "$FIXTURE_TABLE" ]]; then
  fail_check "counter_stimulus_fixtures_exist" \
    "the fixtures this test proves itself with are absent:" \
    "${FIXTURE_ENV_HOME}" "${FIXTURE_DOCKER_HOME}" "${FIXTURE_TABLE}"
else
  pass_check "counter_stimulus_fixtures_exist"

  fixture_pins="$(all_home_pins "$FIXTURE_DIR" "pins.env" "pins.Dockerfile")"
  fixture_rows="$(table_rows "$FIXTURE_TABLE")"
  fixture_row_pins="$(row_pins "$fixture_rows")"

  # The reader counts pins and not lines. pins.env holds 3 pins, 1 digest row
  # and 4 comment rows; pins.Dockerfile holds 3 version-shaped ARGs, 1 digest
  # row and 4 build parameters; COVERTOOL_VERSION is in both and is 1 pin.
  assert_equal "counter_stimulus_reads_5_pins_and_skips_the_digests_and_the_parameters" \
    "5" "$(count_lines "$fixture_pins")" \
    "a reader that counted USERNAME or COVERTOOL_SHA256_AMD64 would demand an upstream" \
    "row for a value no upstream publishes" \
    "it read:" "$fixture_pins"

  # The quiet direction. The fixture pair agrees, so every detector must be
  # silent. One that reports a correct table is as useless as one that reports
  # nothing.
  assert_equal "counter_stimulus_leaves_the_covering_table_alone" \
    "" "$(names_absent_from "$fixture_pins" "$fixture_row_pins")$(names_absent_from "$fixture_row_pins" "$fixture_pins")$(repeated_names "$fixture_row_pins")$(malformed_rows "$fixture_rows")$(rows_with_an_unknown_datasource "$fixture_rows")$(no_autobump_rows_without_a_reason "$fixture_rows")" \
    "the fixture homes and the fixture table cover each other exactly"

  # A new pin, and nobody said where its next value comes from. This is the
  # shape of the defect: a row is appended to versions.env and no table row
  # moves with it.
  appended_home="$(mktemp)"
  cat "$FIXTURE_ENV_HOME" > "$appended_home"
  printf 'COVERNEW_VERSION=9.9.9\n' >> "$appended_home"
  appended_report="$(names_absent_from "$(env_home_pins "$appended_home")" "$fixture_row_pins")"
  rm -f "$appended_home"
  assert_equal "counter_stimulus_reports_the_pin_that_no_row_answers" \
    "COVERNEW_VERSION" "$appended_report" \
    "a pin with no upstream row is a pin that is bumped when a human happens to look"

  # The mirror direction. A pin is deleted and its row stays behind, so the
  # table describes a home that no longer holds that name.
  deleted_home="$(mktemp)"
  grep -v '^COVERPKG=' "$FIXTURE_ENV_HOME" > "$deleted_home"
  deleted_pins="$(all_home_pins "$FIXTURE_DIR" "pins.Dockerfile")
$(env_home_pins "$deleted_home")"
  rm -f "$deleted_home"
  assert_equal "counter_stimulus_reports_the_row_whose_pin_is_gone" \
    "COVERPKG" "$(names_absent_from "$fixture_row_pins" "$(sort -u <<< "$deleted_pins")")" \
    "a row for a pin that is gone is read as coverage, and it covers nothing"

  # Exactly once, and not at least once.
  assert_equal "counter_stimulus_reports_the_pin_that_carries_2_rows" \
    "COVERPKG" "$(repeated_names "${fixture_row_pins}
COVERPKG")" \
    "2 answers for 1 pin means the reader cannot tell which upstream holds"

  assert_contains "counter_stimulus_reports_a_row_that_is_not_4_fields" \
    "$(malformed_rows "COVERTOOL_VERSION|github-release|coverowner/covertool")" \
    "COVERTOOL_VERSION" \
    "a row missing its policy field is a row nobody finished writing"

  assert_contains "counter_stimulus_reports_a_datasource_outside_the_taxonomy" \
    "$(rows_with_an_unknown_datasource "COVERPKG|probably-fine|python3.12|it looks like an answer")" \
    "probably-fine" \
    "a typo in a datasource answers a pin with a mechanism nothing implements"

  assert_contains "counter_stimulus_reports_a_no_autobump_reason_that_is_a_placeholder" \
    "$(no_autobump_rows_without_a_reason "COVERREF|no-autobump|golang.org/x/perf|n/a")" \
    "COVERREF" \
    "n/a passes every non-empty test, and it is a pin nobody decided about" \
    "wearing the label of a pin somebody did"

  # And the placeholder detector must not report a real sentence, or every
  # no-autobump row in the real table is red for being written properly.
  assert_equal "counter_stimulus_leaves_a_stated_no_autobump_reason_alone" \
    "" "$(no_autobump_rows_without_a_reason "COVERREF|no-autobump|golang.org/x/perf|the module is untagged upstream, so there is no release to compare against")" \
    "the quiet half of the placeholder rule"
fi

# ===========================================================================
# 2. THE TABLE IS THERE, AND IT PARSES
# ===========================================================================
TABLE_PATH="$REPO_ROOT/$UPSTREAMS_FILE"
if [[ -f "$TABLE_PATH" ]]; then
  pass_check "the_upstream_table_exists"
else
  fail_check "the_upstream_table_exists" \
    "want: a file at ${UPSTREAMS_FILE}" \
    "got:  no file" \
    "it is the 1 place that says where the next value of each pin comes from," \
    "and every check below reads it"
fi

REAL_ROWS="$(table_rows "$TABLE_PATH")"
REAL_ROW_PINS="$(row_pins "$REAL_ROWS")"
REAL_PINS="$(all_home_pins "$REPO_ROOT" "${VALUE_HOMES[@]}")"

# Before any rule over REAL_PINS: is every home in the list still a home? There
# are 2 ways to stop being one and `all_home_pins` is silent about both — the
# file is DELETED, or the file stops declaring a value-ful pin. So they are 2
# checks. The total below cannot stand in for either: a home whose pins are all
# ALSO versions.env rows contributes 0 to a `sort -u` total, so it can leave
# without moving the number by 1.
missing_homes=""
for home in "${VALUE_HOMES[@]}"; do
  [[ -f "$REPO_ROOT/$home" ]] || missing_homes="${missing_homes:+${missing_homes}
}${home}"
done
if [[ -n "$missing_homes" ]]; then
  fail_check "every_named_value_home_exists" \
    "the VALUE_HOMES list in this test is stale; these are named but absent:" \
    "$missing_homes" \
    "all_home_pins reads nothing out of a file it cannot open, so every rule below" \
    "goes on reporting full coverage of a set that just got smaller"
else
  pass_check "every_named_value_home_exists"
fi

silent_homes=""
for home in "${VALUE_HOMES[@]}"; do
  [[ -f "$REPO_ROOT/$home" ]] || continue
  if [[ -z "$(home_pins "$REPO_ROOT/$home" "$home")" ]]; then
    silent_homes="${silent_homes:+${silent_homes}
}${home}"
  fi
done
if [[ -n "$silent_homes" ]]; then
  fail_check "every_named_value_home_declares_a_pin" \
    "these homes are named in VALUE_HOMES and declare no version-shaped pin with a value:" \
    "$silent_homes" \
    "a home that declares nothing is not a value home — drop it from the list, or find out" \
    "why the declarations left; base/Dockerfile sat here for exactly that reason and 19 checks stayed green"
else
  pass_check "every_named_value_home_declares_a_pin"
fi

# A table that parses into 0 rows makes every rule below vacuous, and a vacuous
# rule reports a clean file it never read. So the liveness of both readers is a
# check of its own.
real_pin_total="$(count_lines "$REAL_PINS")"
real_row_total="$(count_lines "$REAL_ROWS")"

# 56 measured on 2026-08-17: 46 rows of versions.env plus the 10 pins whose only
# home is a Dockerfile. The floor is 50 rather than the measured number because
# a pin removed is a legitimate change and a reader that stopped reading is not.
#
# THE FLOOR IS NOT THE LIST GUARD, and the 2 checks above are not redundant
# with it. This total was 56 before runner/Dockerfile was deleted and 56 after,
# because every pin that home held was also a versions.env row and `sort -u`
# reports a union. A floor over a union cannot see a home leave.
if [[ "$real_pin_total" -ge 50 ]]; then
  pass_check "the_value_homes_hold_the_pins_this_rule_is_about"
else
  fail_check "the_value_homes_hold_the_pins_this_rule_is_about" \
    "the reader found ${real_pin_total} pins across the 4 value homes, and 56 were measured on 2026-08-17" \
    "every rule below is vacuous over an empty pin list, and a vacuous rule reports" \
    "a clean repository it never read" \
    "it read:" "${REAL_PINS:-<nothing>}"
fi

if [[ "$real_row_total" -ge 1 ]]; then
  pass_check "the_upstream_table_holds_at_least_one_row"
else
  fail_check "the_upstream_table_holds_at_least_one_row" \
    "no row parsed out of ${UPSTREAMS_FILE}" \
    "either the table is absent, or this test stopped reading its rows"
fi

# ===========================================================================
# 3. THE RULE, ON THE REAL TREE — both directions, from the HOMES
# ===========================================================================
unanswered="$(names_absent_from "$REAL_PINS" "$REAL_ROW_PINS")"
if [[ -z "$unanswered" ]]; then
  pass_check "every_pin_carries_an_upstream_row"
else
  fail_check "every_pin_carries_an_upstream_row" \
    "these pins of the 4 value homes carry no row in ${UPSTREAMS_FILE}:" \
    "$unanswered" \
    "give each one a datasource and its coordinate, or a no-autobump row stating why" \
    "a pin nothing watches is a snapshot that looks current forever"
fi

ghosts="$(names_absent_from "$REAL_ROW_PINS" "$REAL_PINS")"
if [[ -z "$ghosts" ]]; then
  pass_check "every_upstream_row_names_a_pin_that_exists"
else
  fail_check "every_upstream_row_names_a_pin_that_exists" \
    "these rows of ${UPSTREAMS_FILE} name no pin of any value home:" \
    "$ghosts" \
    "delete the stale row, or restore the pin it names" \
    "a row for a pin that is gone describes a file that no longer holds it"
fi

repeats="$(repeated_names "$REAL_ROW_PINS")"
if [[ -z "$repeats" ]]; then
  pass_check "every_pin_carries_exactly_one_upstream_row"
else
  fail_check "every_pin_carries_exactly_one_upstream_row" \
    "these pins carry more than 1 row:" \
    "$repeats" \
    "2 upstreams for 1 pin means the weekly run resolves it twice and the reader" \
    "cannot tell which answer wrote the bump"
fi

malformed="$(malformed_rows "$REAL_ROWS")"
if [[ -z "$malformed" ]]; then
  pass_check "every_upstream_row_is_four_non_empty_fields"
else
  fail_check "every_upstream_row_is_four_non_empty_fields" \
    "these rows are not <pin>|<datasource>|<coordinate>|<policy>:" \
    "$malformed" \
    "the grammar is the grammar of _build/download-exemptions.txt — 1 table shape in _build/, not 2"
fi

unknown="$(rows_with_an_unknown_datasource "$REAL_ROWS")"
if [[ -z "$unknown" ]]; then
  pass_check "every_upstream_row_names_one_of_the_thirteen_datasources"
else
  fail_check "every_upstream_row_names_one_of_the_thirteen_datasources" \
    "these rows name a datasource outside the taxonomy:" \
    "$unknown" \
    "the 12 are: ${DATASOURCES_TEXT}" \
    "a 13th name is not a datasource, it is a pin nothing resolves"
fi

placeholders="$(no_autobump_rows_without_a_reason "$REAL_ROWS")"
if [[ -z "$placeholders" ]]; then
  pass_check "every_no_autobump_row_states_its_reason"
else
  fail_check "every_no_autobump_row_states_its_reason" \
    "these no-autobump rows answer with a token rather than a sentence:" \
    "$placeholders" \
    "a reason under ${REASON_MINIMUM_LENGTH} characters, or with no space in it, is a placeholder" \
    "the reader of this row is a human deciding whether the exemption still holds"
fi

test_summary "$TEST_NAME"
