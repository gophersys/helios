#!/usr/bin/env bash
#
# _ctl/tests/pin-mirroring.test.sh — a pin with 2 homes holds 1 value, and the
# writer that bumps it edits both.
#
# Hermetic: this file reads the 6 value homes, and it drives the writer against
# a fixture tree it copies to a temporary directory. No container, no daemon, no
# network — so it runs in the PULL REQUEST gate, which is the only place this
# rule is worth having.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# 38 pins are declared in 2 homes (counted by this file's own reader on
# 2026-08-17): once in versions.env for the cloud family, and once as an ARG in
# base/Dockerfile or runner/Dockerfile for the base family. Bumping one is 2
# edits in 2 files, and NOTHING holds the 2 values equal.
#
# A bump that edits 1 of them publishes 2 different toolchains under 1 commit.
# The cloud image gets Go 1.26.5 and the base image goes on shipping 1.26.4,
# both from the same merge, and the pull request diff reads like a bump. The
# consequence is not a build failure — it is 2 CI runtimes that disagree, which
# is the exact property this repository exists to remove.
#
# `dual_home_disagreements` in download-coverage.test.sh does NOT cover this. It
# holds 2 DIGESTS equal, and it does so only for a tool whose 2 versions already
# agree: a pair whose versions differ is skipped, because 2 versions are 2
# releases and 2 releases are 2 sets of bytes. The version equality itself has
# had no rule until this file.
#
# ============================================================================
# THE 2 RULES HERE, AND WHY THEY LIVE IN 1 FILE
# ============================================================================
#
#   1. THE STATE. Every pin declared in 2 or more value homes holds the same
#      value in all of them.
#   2. THE WRITER. `bump_pin` in _ctl/lib.sh edits EVERY home of a pin — the
#      version row, the digest row beside it and that row's evidence comment —
#      and no other line of any file.
#
# They are 1 rule read twice. Rule 1 is the property the repository must hold at
# rest, and rule 2 is the only thing that will be writing these files once the
# weekly bump lands: a writer that edits versions.env alone re-creates the exact
# state rule 1 forbids, every Monday, automatically. So the writer is driven
# against a fixture tree, and the SAME detector rule 1 uses is then run over the
# tree it wrote.
#
# ============================================================================
# WHAT COUNTS AS A PIN, AND WHAT IS DELIBERATELY NOT COMPARED
# ============================================================================
#
# The pin reader is the one upstream-coverage.test.sh uses: every non-digest row
# of a versions.env-shaped home, and every version-shaped ARG with a value in a
# Dockerfile home. A `<TOOL>_SHA256_<ARCH>` row is not a pin here — whether 2
# homes carry the same DIGEST is download-coverage.test.sh's rule, and a second,
# weaker copy of it in this file would be a rule 2 files could disagree about.
#
# A single-home pin has nothing to disagree with. The rule passes over it.
#
# Usage: bash _ctl/tests/pin-mirroring.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses. The writer under test lives there too,
# so this source line is also how `bump_pin` arrives.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="pin-mirroring.test.sh"

# The 6 homes that hold a VALUE, named home by home rather than found by a
# glob: a glob that stops matching leaves a green result that read nothing.
VALUE_HOMES=(
  "versions.env"
  "base/Dockerfile"
  "runner/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
)

# The 2 homes of the fixture tree the writer is driven against.
WRITER_HOMES=(
  "versions.env"
  "base/Dockerfile"
)

FIXTURE_DIR="$TESTS_DIR/fixtures/upstreams/mirroring"
FIXTURE_AGREEING_ENV="$FIXTURE_DIR/agreeing.env"
FIXTURE_AGREEING_DOCKERFILE="$FIXTURE_DIR/agreeing.Dockerfile"
FIXTURE_DRIFTED_DOCKERFILE="$FIXTURE_DIR/drifted.Dockerfile"
WRITER_FIXTURE="$TESTS_DIR/fixtures/upstreams/writer"

# The bump the writer is asked to make. Literals, so the assertions below name
# the value they want and never read it back out of the writer's own output.
WRITER_PIN="WRITERTOOL_VERSION"
WRITER_DIGEST_ROW="WRITERTOOL_SHA256_AMD64"
WRITER_OLD_VERSION="1.4.2"
WRITER_NEW_VERSION="1.5.0"
WRITER_NEW_DIGEST="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
WRITER_EVIDENCE="upstream-published: https://example.invalid/writertool/v1.5.0/checksums.txt"

# The second pin: 2 homes, no digest row. About 30 of the real 56 pins are this
# shape (`go install`, corepack, pipx), and `-` is how a caller says "this pin
# has no bytes to digest" — the same marker _build/resolve-upstream.sh prints in
# the digest field for such a pin.
WRITER_PLAIN_PIN="WRITERPLAIN_VERSION"
WRITER_PLAIN_NEW_VERSION="3.1.0"
NO_DIGEST="-"

# 30 rather than the measured 38: a pin removed is a legitimate change, and a
# reader that stopped reading is not. Without a floor, rule 1 passes over an
# empty list and reports a repository it never read.
DUAL_HOME_FLOOR=30

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BUMP_OUTPUT=""
BUMP_STATUS=0

# ---------------------------------------------------------------------------
# The readers.
#
# awk and not `grep | cut` throughout: grep exits 1 when it matches nothing, and
# under `set -e` with pipefail that kills the run instead of reporting an empty
# result. An empty result is a defect this file has to REPORT, so it must
# survive reading one.
# ---------------------------------------------------------------------------

# env_home_records <label> <file> — `<label>|<name>|<value>` for every pin of a
# versions.env-shaped home. A digest row is not a pin; a comment row is prose.
function env_home_records() {
  local label="$1" file="$2"
  [[ -f "$file" ]] || return 0
  awk -v label="$label" '
    /^[[:space:]]*#/ { next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ {
      position = index($0, "=")
      name = substr($0, 1, position - 1)
      if (name ~ /_SHA256_[A-Z0-9_]+$/) { next }
      rest = substr($0, position + 1)
      split(rest, parts, /[[:space:]]/)
      printf "%s|%s|%s\n", label, name, parts[1]
    }
  ' "$file"
}

# dockerfile_home_records <label> <file> — the same records for a Dockerfile
# home: every version-shaped ARG that carries a value.
function dockerfile_home_records() {
  local label="$1" file="$2"
  [[ -f "$file" ]] || return 0
  awk -v label="$label" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*ARG[[:space:]]+/ {
      split($2, parts, "=")
      name = parts[1]
      if (name ~ /_SHA256_[A-Z0-9_]+$/) { next }
      if (name !~ /(_VERSION|_REF|_CHANNEL)$/) { next }
      if ($2 !~ /=/) { next }
      position = index($0, name "=")
      rest = substr($0, position + length(name) + 1)
      split(rest, value, /[[:space:]]/)
      printf "%s|%s|%s\n", label, name, value[1]
    }
  ' "$file"
}

# home_records <label> <file> — whichever shape the home is. The 2 are told
# apart by the NAME of the home, so the fixture pair (pins.env-shaped
# agreeing.env, Dockerfile-shaped agreeing.Dockerfile) runs through the same
# code the real tree does.
function home_records() {
  local label="$1" file="$2"
  case "$label" in
    *Dockerfile) dockerfile_home_records "$label" "$file" ;;
    *)           env_home_records "$label" "$file" ;;
  esac
}

# tree_records <root> <home...> — the records of every home of a tree.
function tree_records() {
  local root="$1"
  shift
  local home
  for home in "$@"; do
    home_records "$home" "${root}/${home}"
  done
}

# value_disagreements <records> — every pin whose homes do not agree, reported
# with EVERY home and value, 1 line per pin.
#
# Per pin and not per file: a detector that reported the whole file once it
# found 1 defect would name 2 pins where 1 moved, and the reader would then go
# looking for a second bump that never happened.
function value_disagreements() {
  awk -F'|' '
    NF < 3 { next }
    {
      name = $2
      if (!(name in first)) { first[name] = $3; order[++count] = name }
      pairs[name] = pairs[name] (pairs[name] == "" ? "" : ", ") $1 " has " $3
      if ($3 != first[name]) { differs[name] = 1 }
    }
    END {
      for (index_of_pin = 1; index_of_pin <= count; index_of_pin++) {
        name = order[index_of_pin]
        if (name in differs) { print name ": " pairs[name] }
      }
    }
  ' <<< "$1" | sort
}

# dual_home_pins <records> — every pin the record set declares more than once.
function dual_home_pins() {
  awk -F'|' 'NF >= 3 { print $2 }' <<< "$1" | sort | uniq -d
}

# record_value <records> <home> <name> — the value 1 home holds for 1 pin, or
# the empty string when that home does not declare it.
function record_value() {
  awk -F'|' -v home="$2" -v name="$3" '$1 == home && $2 == name { print $3 }' <<< "$1"
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

# declaration_line <file> <name> — the line that declares <name> WITH a value,
# in either home shape.
function declaration_line() {
  local file="$1" name="$2"
  [[ -f "$file" ]] || return 0
  awk -v name="$name" '
    $0 ~ ("^[[:space:]]*ARG[[:space:]]+" name "=") { print; next }
    $0 ~ ("^" name "=") { print }
  ' "$file"
}

# declaration_line_number <file> <name> — the number of that line, or nothing.
function declaration_line_number() {
  local file="$1" name="$2"
  [[ -f "$file" ]] || return 0
  awk -v name="$name" '
    $0 ~ ("^[[:space:]]*ARG[[:space:]]+" name "=") { print NR; next }
    $0 ~ ("^" name "=") { print NR }
  ' "$file"
}

# changed_line_numbers <before> <after> — the number of every line whose text
# moved, and a report when the 2 files are no longer the same length.
#
# This is the "touches no other line" rule. A diff of the whole file would tell
# the reader that something changed; the line numbers tell them WHICH, and the
# check below compares that set against the 2 lines the bump is allowed to
# touch.
function changed_line_numbers() {
  local before="$1" after="$2"
  awk '
    NR == FNR { previous[FNR] = $0; total = FNR; next }
    { if ($0 != previous[FNR]) { print FNR } }
    END { if (FNR != total) { printf "the file is now %d lines and it was %d\n", FNR, total } }
  ' "$before" "$after"
}

# evidence_word_of <line> — `upstream-published`, `computed-at-pin` or the empty
# string, read by the library's own reader.
#
# The reader is _ctl/lib.sh's, deliberately: ledger #100 moves `evidence_of`,
# `homes_of` and `fetch_urls` out of download-coverage.test.sh and into the
# library so the resolver and the tests share 1 body. A copy of the regular
# expression here would be the 3rd, and the 3 would then be free to disagree
# about what counts as evidence.
function evidence_word_of() {
  if declare -F evidence_of > /dev/null 2>&1; then
    evidence_of "$1"
    return 0
  fi
  printf '<_ctl/lib.sh defines no evidence_of>'
}

# run_bump_pin <argv...> — drive the writer, and survive its absence.
#
# `bump_pin` does not exist yet, and an undefined function under `set -e` ends
# the run at the first call — which would take every check below out of the
# output, and a check whose name never prints is a check nobody can confirm ran.
# So its absence is recorded as status 127 with a message that says so, and each
# assertion below then fails naming what it wanted.
function run_bump_pin() {
  BUMP_STATUS=0
  if ! declare -F bump_pin > /dev/null 2>&1; then
    BUMP_OUTPUT="_ctl/lib.sh defines no bump_pin"
    BUMP_STATUS=127
    return 0
  fi
  BUMP_OUTPUT="$(bump_pin "$@" 2>&1 < /dev/null)" || BUMP_STATUS=$?
}

# writer_world <name> — a fresh copy of the fixture tree, and a `before` copy of
# it beside the copy, so every assertion can read what the writer changed.
function writer_world() {
  local name="$1"
  local world="$WORK/${name}"
  local before="$WORK/${name}-before"
  mkdir -p "$world" "$before"
  cp -R "$WRITER_FIXTURE/." "$world/"
  cp -R "$WRITER_FIXTURE/." "$before/"
  printf '%s' "$world"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 0. THE COUNTER-STIMULUS — the detector FIRES, and the detector is QUIET
# ===========================================================================
#
# This runs before the real tree on purpose. Rule 1 is GREEN on this repository
# today: all 38 dual-home pins agree, so the real-tree check below would pass
# just as happily against a reader that read nothing at all. The fixtures are
# what separate those 2 outcomes.
if [[ ! -f "$FIXTURE_AGREEING_ENV" || ! -f "$FIXTURE_AGREEING_DOCKERFILE" || ! -f "$FIXTURE_DRIFTED_DOCKERFILE" ]]; then
  fail_check "counter_stimulus_fixtures_exist" \
    "the fixtures this test proves itself with are absent:" \
    "${FIXTURE_AGREEING_ENV}" "${FIXTURE_AGREEING_DOCKERFILE}" "${FIXTURE_DRIFTED_DOCKERFILE}"
else
  pass_check "counter_stimulus_fixtures_exist"

  agreeing_records="$(home_records "agreeing.env" "$FIXTURE_AGREEING_ENV")
$(home_records "agreeing.Dockerfile" "$FIXTURE_AGREEING_DOCKERFILE")"
  drifted_records="$(home_records "agreeing.env" "$FIXTURE_AGREEING_ENV")
$(home_records "drifted.Dockerfile" "$FIXTURE_DRIFTED_DOCKERFILE")"

  # 3 pins in the env home and 2 in the Dockerfile home. The digest row and the
  # build parameters are not pins, and a reader that counted them would compare
  # USERNAME across 2 homes.
  assert_equal "counter_stimulus_reads_5_records_and_skips_the_digests_and_the_parameters" \
    "5" "$(count_lines "$agreeing_records")" \
    "it read:" "$agreeing_records"

  # The quiet direction.
  assert_equal "counter_stimulus_leaves_the_agreeing_pair_alone" \
    "" "$(value_disagreements "$agreeing_records")" \
    "both homes declare MIRRORTOOL_VERSION=1.4.2 and MIRRORPLAIN_VERSION=3.0.0," \
    "so a detector that reports anything here reports all 38 dual-home pins of the real tree"

  # The loud direction: 1 home moved and the other did not.
  drift_report="$(value_disagreements "$drifted_records")"
  assert_contains "counter_stimulus_reports_the_pin_whose_second_home_was_left_behind" \
    "$drift_report" "MIRRORTOOL_VERSION" \
    "agreeing.env has 1.4.2 and drifted.Dockerfile has 1.4.1, which is a bump that edited 1 file of 2"

  assert_contains "counter_stimulus_names_both_values_it_disagreed_about" \
    "$drift_report" "1.4.1" \
    "the report has to carry both values, or the reader cannot tell which home is behind"

  # And it reports the ONE pin that moved, not the file it found it in.
  assert_not_contains "counter_stimulus_stays_quiet_about_the_pin_that_still_agrees" \
    "$drift_report" "MIRRORPLAIN_VERSION" \
    "MIRRORPLAIN_VERSION reads 3.0.0 in both homes of the drifted pair"

  # A pin with 1 home has nothing to disagree with.
  assert_not_contains "counter_stimulus_stays_quiet_about_a_single_home_pin" \
    "$drift_report" "SOLEHOME_VERSION" \
    "SOLEHOME_VERSION is declared in agreeing.env alone; reporting it would demand a" \
    "second home for all 11 pins whose only home is a Dockerfile"
fi

# ===========================================================================
# 1. RULE 1, ON THE REAL TREE — 2 homes, 1 value
# ===========================================================================
REAL_RECORDS="$(tree_records "$REPO_ROOT" "${VALUE_HOMES[@]}")"
REAL_DUAL_HOME="$(dual_home_pins "$REAL_RECORDS")"
real_dual_home_total="$(count_lines "$REAL_DUAL_HOME")"

if [[ "$real_dual_home_total" -ge "$DUAL_HOME_FLOOR" ]]; then
  pass_check "the_value_homes_hold_the_dual_home_pins_this_rule_is_about"
else
  fail_check "the_value_homes_hold_the_dual_home_pins_this_rule_is_about" \
    "the reader found ${real_dual_home_total} dual-home pins, and 38 were measured on 2026-08-17" \
    "the rule below is vacuous over an empty list, and a vacuous rule reports a" \
    "repository it never read" \
    "it read:" "${REAL_DUAL_HOME:-<nothing>}"
fi

real_disagreements="$(value_disagreements "$REAL_RECORDS")"
if [[ -z "$real_disagreements" ]]; then
  pass_check "every_dual_home_pin_holds_the_same_version_in_every_home"
else
  fail_check "every_dual_home_pin_holds_the_same_version_in_every_home" \
    "these pins hold 2 values across their homes:" \
    "$real_disagreements" \
    "a bump edits every home of a pin, or the cloud family and the base family" \
    "ship 2 different toolchains out of 1 commit"
fi

# ===========================================================================
# 2. RULE 2, THE WRITER — every home of the pin, and no other line
# ===========================================================================
#
# The writer is the thing that will be editing these files every Monday. A
# writer that edits versions.env alone re-creates the state rule 1 forbids,
# automatically, with a pull request that reads like a correct bump.
#
# THE CONTRACT
#
#   bump_pin <root> <pin> <version> <digest> <evidence>
#
#   <root>      the tree to edit. The 6 value homes are looked for under it,
#               so a fixture tree and the repository run through 1 body.
#   <digest>    64 lowercase hex, or `-` when the pin carries no digest row —
#               the marker _build/resolve-upstream.sh prints for such a pin.
#   <evidence>  the comment the digest row carries: `upstream-published: <url>`
#               or `computed-at-pin: <yyyy-mm-dd>`, and `-` alongside a `-`
#               digest.
#
#   exit 0        every home of the pin was rewritten
#   exit non-zero NAMING THE PIN, when it was not. A caller reads this inside a
#                 weekly run nobody is watching, and "exit 1" tells them nothing.
if declare -F bump_pin > /dev/null 2>&1; then
  pass_check "the_library_defines_the_bump_pin_writer"
else
  fail_check "the_library_defines_the_bump_pin_writer" \
    "want: a function bump_pin in _ctl/lib.sh" \
    "got:  no such function" \
    "the body of a verb lives in the library 1 time — the weekly workflow and this" \
    "test then drive the same writer, and a copy in the workflow would be a second one"
fi

# -------- 2a. the full bump: version, digest and evidence, in BOTH homes -----
full_world="$(writer_world "full")"
full_before="$WORK/full-before"
run_bump_pin "$full_world" "$WRITER_PIN" "$WRITER_NEW_VERSION" "$WRITER_NEW_DIGEST" "$WRITER_EVIDENCE"

if [[ "$BUMP_STATUS" -eq 0 ]]; then
  pass_check "the_writer_exits_zero_on_a_pin_it_can_rewrite"
else
  fail_check "the_writer_exits_zero_on_a_pin_it_can_rewrite" \
    "want: exit 0 bumping ${WRITER_PIN} from ${WRITER_OLD_VERSION} to ${WRITER_NEW_VERSION}" \
    "got:  ${BUMP_STATUS}" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
fi

full_records="$(tree_records "$full_world" "${WRITER_HOMES[@]}")"
assert_equal "the_writer_rewrites_the_version_in_the_env_home" \
  "$WRITER_NEW_VERSION" "$(record_value "$full_records" "versions.env" "$WRITER_PIN")" \
  "output was:" "${BUMP_OUTPUT:-<none>}"

assert_equal "the_writer_rewrites_the_version_in_the_dockerfile_home" \
  "$WRITER_NEW_VERSION" "$(record_value "$full_records" "base/Dockerfile" "$WRITER_PIN")" \
  "a writer that edits versions.env alone re-creates the drift rule 1 forbids," \
  "every Monday, in a pull request that reads like a bump" \
  "output was:" "${BUMP_OUTPUT:-<none>}"

for home in "${WRITER_HOMES[@]}"; do
  digest_line="$(declaration_line "${full_world}/${home}" "$WRITER_DIGEST_ROW")"
  digest_value="$(awk '{ position = index($0, "="); rest = substr($0, position + 1); split(rest, parts, /[[:space:]]/); print parts[1] }' <<< "$digest_line")"
  assert_equal "the_writer_rewrites_the_digest_in_${home//\//_}" \
    "$WRITER_NEW_DIGEST" "$digest_value" \
    "an equal version means equal bytes, so a digest left behind in 1 home makes that" \
    "image reject what the other one installs" \
    "the line reads:" "${digest_line:-<no such row>}"

  assert_equal "the_writer_rewrites_the_evidence_comment_in_${home//\//_}" \
    "upstream-published" "$(evidence_word_of "$digest_line")" \
    "a digest with no evidence is a number a reviewer has to take on faith" \
    "the line reads:" "${digest_line:-<no such row>}"

  assert_contains "the_evidence_comment_in_${home//\//_}_names_the_checksum_file" \
    "$digest_line" "https://example.invalid/writertool/v1.5.0/checksums.txt" \
    "the evidence the caller passed names the release this digest was read from," \
    "and the row must carry that url and not the previous one"
done

# -------- 2b. and it touches nothing else ------------------------------------
# 2 lines per home: the version row and the digest row. Every other line — the
# 2 pins this bump is not about, the RUN block, the comments — reads the same.
for home in "${WRITER_HOMES[@]}"; do
  expected_lines="$(printf '%s\n%s\n' \
    "$(declaration_line_number "${full_before}/${home}" "$WRITER_PIN")" \
    "$(declaration_line_number "${full_before}/${home}" "$WRITER_DIGEST_ROW")" | sort -n | awk 'NF')"
  assert_equal "the_writer_touches_only_the_two_rows_of_the_pin_in_${home//\//_}" \
    "$expected_lines" \
    "$(changed_line_numbers "${full_before}/${home}" "${full_world}/${home}" | sort -n | awk 'NF')" \
    "the bump of a pin is its version row and its digest row, and nothing else:" \
    "a writer that rewrites a whole file makes every weekly pull request unreviewable"
done

# -------- 2c. the tree it wrote satisfies rule 1 -----------------------------
# The 2 rules closed into 1 loop. This is the check that goes red the day the
# writer learns to edit 1 home.
written_disagreements="$(value_disagreements "$full_records")"
if [[ "$BUMP_STATUS" -eq 0 && -z "$written_disagreements" ]]; then
  pass_check "the_tree_the_writer_wrote_still_mirrors_every_dual_home_pin"
else
  fail_check "the_tree_the_writer_wrote_still_mirrors_every_dual_home_pin" \
    "the writer exited ${BUMP_STATUS}, and rule 1 over the tree it left reports:" \
    "${written_disagreements:-<nothing, but the writer did not exit 0>}" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
fi

# -------- 2d. a pin with no digest row: the version alone moves --------------
plain_world="$(writer_world "plain")"
plain_before="$WORK/plain-before"
run_bump_pin "$plain_world" "$WRITER_PLAIN_PIN" "$WRITER_PLAIN_NEW_VERSION" "$NO_DIGEST" "$NO_DIGEST"

plain_records="$(tree_records "$plain_world" "${WRITER_HOMES[@]}")"
if [[ "$BUMP_STATUS" -eq 0 \
  && "$(record_value "$plain_records" "versions.env" "$WRITER_PLAIN_PIN")" == "$WRITER_PLAIN_NEW_VERSION" \
  && "$(record_value "$plain_records" "base/Dockerfile" "$WRITER_PLAIN_PIN")" == "$WRITER_PLAIN_NEW_VERSION" ]]; then
  pass_check "the_writer_bumps_a_pin_that_carries_no_digest_row_in_both_homes"
else
  fail_check "the_writer_bumps_a_pin_that_carries_no_digest_row_in_both_homes" \
    "want: exit 0 and ${WRITER_PLAIN_PIN}=${WRITER_PLAIN_NEW_VERSION} in both homes" \
    "got:  exit ${BUMP_STATUS}, versions.env has '$(record_value "$plain_records" "versions.env" "$WRITER_PLAIN_PIN")'," \
    "      base/Dockerfile has '$(record_value "$plain_records" "base/Dockerfile" "$WRITER_PLAIN_PIN")'" \
    "about 30 of the 56 real pins are installed by go install, corepack or pipx and carry" \
    "no digest row at all, so a writer that requires one bumps none of them" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
fi

for home in "${WRITER_HOMES[@]}"; do
  assert_equal "the_no_digest_bump_touches_one_line_in_${home//\//_}" \
    "$(declaration_line_number "${plain_before}/${home}" "$WRITER_PLAIN_PIN")" \
    "$(changed_line_numbers "${plain_before}/${home}" "${plain_world}/${home}" | sort -n | awk 'NF')" \
    "there is no digest row for this pin, so a writer that invented one would add a" \
    "line that nothing compares — a check that cannot fail"
done

# -------- 2e. FAIL-LOUD: a pin no home declares ------------------------------
# The weekly run reads its pins out of _build/upstreams.txt. A row whose pin was
# renamed in the homes must stop the run naming the pin, not silently write
# nothing and report a green Monday.
absent_world="$(writer_world "absent")"
run_bump_pin "$absent_world" "NOSUCHTOOL_VERSION" "1.0.0" "$NO_DIGEST" "$NO_DIGEST"
if [[ "$BUMP_STATUS" -eq 0 ]]; then
  fail_check "the_writer_fails_naming_a_pin_no_home_declares" \
    "want: a non-zero exit status for NOSUCHTOOL_VERSION, which no home of the fixture tree declares" \
    "got:  0" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
elif ! grep -qF -- "NOSUCHTOOL_VERSION" <<< "$BUMP_OUTPUT"; then
  fail_check "the_writer_fails_naming_a_pin_no_home_declares" \
    "the writer exited ${BUMP_STATUS} and its message does not name NOSUCHTOOL_VERSION" \
    "a status with no name reaches a reader inside a weekly run nobody watched" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
else
  pass_check "the_writer_fails_naming_a_pin_no_home_declares"
fi

test_summary "$TEST_NAME"
