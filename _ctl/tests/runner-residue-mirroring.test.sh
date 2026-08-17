#!/usr/bin/env bash
#
# _ctl/tests/runner-residue-mirroring.test.sh — the ONE pair of pin homes that
# still shares a pin holds 1 value, and the writer that bumps it edits both.
#
# ============================================================================
# WHAT DIED, AND WHY THIS SURVIVED IT
# ============================================================================
#
# `_ctl/tests/pin-mirroring.test.sh` stood here: 568 lines, 26 checks, holding
# 38 dual-home pins across 6 value homes to 1 value each. It existed only
# because `base/Dockerfile` spelled 55 inline `ARG NAME=value` pins and 54 of
# them were spelled in `versions.env` too. That file is DELETED, not
# maintained: `base/Dockerfile` went value-less on 2026-08-17, every one of its
# pins arrives as a generated `--build-arg` from `versions.env`, and 2 copies
# that cannot exist need no rule holding them equal.
#
# 3 pins survived the collapse in 2 homes, measured by this file's own reader
# and never listed here: `versions.env` ∩ `runner/Dockerfile`. `runner/` is
# RETIRED — nothing builds it, it left `BUILD_ORDER` — and it is still 1 of the
# 5 `PIN_VALUE_HOMES` in `_ctl/lib.sh`, so `bump_pin` writes into it every
# Monday. A weekly bump that edits `versions.env` and not `runner/Dockerfile`
# drifts them silently, and nothing else in the suite reports it:
# `download-coverage.test.sh` holds 2 DIGESTS equal and SKIPS a pair whose
# VERSIONS differ, because 2 versions are 2 releases and 2 releases are 2 sets
# of bytes. The version equality itself has no other reader.
#
# ============================================================================
# THIS FILE DIES WITH runner/'s DELETION WAVE
# ============================================================================
#
# The intersection is the whole subject. When `runner/` is deleted — scheduled
# with the consolidation wave, and it edits `_ctl/lib.sh`, both `_build/`
# tables and every test that names the directory in 1 change — the intersection
# is empty and this rule is vacuous. A vacuous rule reports a repository it
# never read, so the liveness check below FAILS on an empty intersection rather
# than passing over it. That red is the instruction to delete this file, not to
# widen it.
#
# ============================================================================
# THE 2 RULES HERE, AND WHY THEY LIVE IN 1 FILE
# ============================================================================
#
#   1. THE STATE. Every pin declared in BOTH homes holds the same version in
#      both, and the same digest in both where both declare a digest row.
#   2. THE WRITER. `bump_pin` in `_ctl/lib.sh` edits EVERY home of a pin — the
#      version row, the digest row beside it and that row's evidence comment —
#      and no other line of any file.
#
# They are 1 rule read twice. Rule 1 is the property the tree must hold at
# rest, and rule 2 is the only thing that will be writing these files: a writer
# that edits `versions.env` alone re-creates the state rule 1 forbids, every
# Monday, in a pull request that reads like a correct bump. So the writer is
# driven against a fixture tree, and the SAME detector rule 1 uses is then run
# over the tree it wrote.
#
# Hermetic: it reads 2 files and drives the writer against a copy of a fixture
# tree. No container, no daemon, no network — so it runs in the PULL REQUEST
# gate, which is the only place this rule is worth having.
#
# Every reader is `_ctl/lib.sh`'s. A regular expression of this file's own
# would be a second definition of "a declaration", and the 2 would then be free
# to disagree about what a pin is.
#
# Usage: bash _ctl/tests/runner-residue-mirroring.test.sh
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

TEST_NAME="runner-residue-mirroring.test.sh"

# The 2 homes, named rather than found by a glob: a glob that stops matching
# leaves a green result that read nothing. They are also the 2 homes of the
# fixture tree the writer is driven against, so the writer is proven on the
# shape it has to write.
ENV_HOME="versions.env"
DOCKERFILE_HOME="runner/Dockerfile"

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

# The second pin: 2 homes, no digest row. `-` is how a caller says "this pin has
# no bytes to digest" — the same marker _build/resolve-upstream.sh prints in the
# digest field for such a pin.
WRITER_PLAIN_PIN="WRITERPLAIN_VERSION"
WRITER_PLAIN_NEW_VERSION="3.1.0"
NO_DIGEST="-"

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

# home_declarations <label> <file> — `<label>|<name>|<value>` for every pin AND
# every digest row a home declares WITH a value, in whichever of the 2 shapes
# the home takes. A value-less `ARG NAME` declares nothing, so it yields no
# record: that is exactly how base/Dockerfile left this rule.
#
# The 2 shapes are told apart by the NAME of the home, so the fixture pair
# (versions.env-shaped agreeing.env, Dockerfile-shaped agreeing.Dockerfile)
# runs through the same code the real tree does.
function home_declarations() {
  local label="$1" file="$2"
  [[ -f "$file" ]] || return 0
  case "$label" in
    *Dockerfile)
      awk -v label="$label" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*ARG[[:space:]]+/ {
          if ($2 !~ /=/) { next }
          split($2, parts, "=")
          name = parts[1]
          if (name !~ /(_VERSION|_REF|_CHANNEL|_SHA256_[A-Z0-9_]+)$/) { next }
          position = index($0, name "=")
          rest = substr($0, position + length(name) + 1)
          split(rest, value, /[[:space:]]/)
          printf "%s|%s|%s\n", label, name, value[1]
        }
      ' "$file"
      ;;
    *)
      awk -v label="$label" '
        /^[[:space:]]*#/ { next }
        /^[A-Za-z_][A-Za-z0-9_]*=/ {
          position = index($0, "=")
          name = substr($0, 1, position - 1)
          rest = substr($0, position + 1)
          split(rest, parts, /[[:space:]]/)
          printf "%s|%s|%s\n", label, name, parts[1]
        }
      ' "$file"
      ;;
  esac
}

# version_records <records> — the records that are not a digest row.
function version_records() {
  awk -F'|' 'NF >= 3 && $2 !~ /_SHA256_[A-Z0-9_]+$/' <<< "$1"
}

# digest_records <records> — the records that are.
function digest_records() {
  awk -F'|' 'NF >= 3 && $2 ~ /_SHA256_[A-Z0-9_]+$/' <<< "$1"
}

# shared_names <records> — every name the record set declares more than once,
# which over exactly 2 homes is every name BOTH homes declare. Discovered from
# the files: a new dual-home pin is covered the day somebody adds it, and a
# hardcoded list would go on reporting coverage of a pin that was renamed.
function shared_names() {
  awk -F'|' 'NF >= 3 { print $2 }' <<< "$1" | sort | uniq -d
}

# value_disagreements <records> — every name whose homes do not agree, reported
# with EVERY home and value, 1 line per name.
#
# Per name and not per file: a detector that reported the whole file once it
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
      for (index_of_name = 1; index_of_name <= count; index_of_name++) {
        name = order[index_of_name]
        if (name in differs) { print name ": " pairs[name] }
      }
    }
  ' <<< "$1" | sort
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

# record_value <records> <home> <name> — the value 1 home holds for 1 name, or
# the empty string when that home does not declare it.
function record_value() {
  awk -F'|' -v home="$2" -v name="$3" '$1 == home && $2 == name { print $3 }' <<< "$1"
}

# declaration_line_number <file> <name> — the number of the line that declares
# <name> with a value, in either home shape. The line ITSELF is read by
# _ctl/lib.sh's declaration_line; only the number is this file's business,
# because "the writer touched no other line" is a rule about positions.
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

# run_bump_pin <argv...> — drive the writer, and survive its absence.
#
# An undefined function under `set -e` ends the run at the first call — which
# would take every check below out of the output, and a check whose name never
# prints is a check nobody can confirm ran. So its absence is recorded as
# status 127 with a message that says so, and each assertion then fails naming
# what it wanted.
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
# today: the surviving dual-home pins agree, so the real-tree check below would
# pass just as happily against a reader that read nothing at all. The fixtures
# are what separate those 2 outcomes.
if [[ ! -f "$FIXTURE_AGREEING_ENV" || ! -f "$FIXTURE_AGREEING_DOCKERFILE" || ! -f "$FIXTURE_DRIFTED_DOCKERFILE" ]]; then
  fail_check "counter_stimulus_fixtures_exist" \
    "the fixtures this test proves itself with are absent:" \
    "${FIXTURE_AGREEING_ENV}" "${FIXTURE_AGREEING_DOCKERFILE}" "${FIXTURE_DRIFTED_DOCKERFILE}"
else
  pass_check "counter_stimulus_fixtures_exist"

  agreeing_records="$(home_declarations "agreeing.env" "$FIXTURE_AGREEING_ENV")
$(home_declarations "agreeing.Dockerfile" "$FIXTURE_AGREEING_DOCKERFILE")"
  drifted_records="$(home_declarations "agreeing.env" "$FIXTURE_AGREEING_ENV")
$(home_declarations "drifted.Dockerfile" "$FIXTURE_DRIFTED_DOCKERFILE")"

  # 3 pins and 1 digest row in the env home, 2 pins and 1 digest row in the
  # Dockerfile home. The build parameters are not declarations of a pin, and a
  # reader that counted them would compare USERNAME across 2 homes.
  assert_equal "counter_stimulus_reads_7_declarations_and_skips_the_build_parameters" \
    "7" "$(count_lines "$agreeing_records")" \
    "it read:" "$agreeing_records"

  # The quiet direction.
  assert_equal "counter_stimulus_leaves_the_agreeing_pair_alone" \
    "" "$(value_disagreements "$agreeing_records")" \
    "both homes declare MIRRORTOOL_VERSION=1.4.2, MIRRORPLAIN_VERSION=3.0.0 and 1 digest," \
    "so a detector that reports anything here reports every dual-home pin of the real tree"

  # The loud direction: 1 home moved and the other did not.
  drift_report="$(value_disagreements "$(version_records "$drifted_records")")"
  assert_contains "counter_stimulus_reports_the_pin_whose_second_home_was_left_behind" \
    "$drift_report" "MIRRORTOOL_VERSION" \
    "agreeing.env has 1.4.2 and drifted.Dockerfile has 1.4.1, which is a bump that edited 1 file of 2"

  # And it reports the ONE pin that moved, not the file it found it in.
  assert_not_contains "counter_stimulus_stays_quiet_about_the_pin_that_still_agrees" \
    "$drift_report" "MIRRORPLAIN_VERSION" \
    "MIRRORPLAIN_VERSION reads 3.0.0 in both homes of the drifted pair"

  # A pin with 1 home has nothing to disagree with.
  assert_not_contains "counter_stimulus_stays_quiet_about_a_single_home_pin" \
    "$drift_report" "SOLEHOME_VERSION" \
    "SOLEHOME_VERSION is declared in agreeing.env alone, and a home that does not carry a" \
    "pin is not a home that is behind on it"

  # The digest half, on a stimulus written here rather than as a 4th fixture:
  # the input is 1 changed token, and a file on disk would only hide it. This
  # is the direction download-coverage.test.sh cannot reach — it skips a pair
  # whose versions differ, and a bump that forgot a home leaves exactly that.
  digest_drifted="$(mktemp)"
  sed 's/^ARG MIRRORTOOL_SHA256_AMD64=b*/ARG MIRRORTOOL_SHA256_AMD64=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/' \
    "$FIXTURE_DRIFTED_DOCKERFILE" > "$digest_drifted"
  digest_report="$(value_disagreements "$(digest_records "$(home_declarations "agreeing.env" "$FIXTURE_AGREEING_ENV")
$(home_declarations "digest-drifted.Dockerfile" "$digest_drifted")")")"
  rm -f "$digest_drifted"
  assert_contains "counter_stimulus_reports_the_digest_row_left_behind" \
    "$digest_report" "MIRRORTOOL_SHA256_AMD64" \
    "the version moved in 1 home and so did the digest beside it, so the pair now names" \
    "2 releases and 2 sets of bytes, and the digest half is reported on its own line"
fi

# ===========================================================================
# 1. RULE 1, ON THE REAL TREE — 2 homes, 1 value
# ===========================================================================
REAL_RECORDS="$(home_declarations "$ENV_HOME" "$REPO_ROOT/$ENV_HOME")
$(home_declarations "$DOCKERFILE_HOME" "$REPO_ROOT/$DOCKERFILE_HOME")"
REAL_VERSIONS="$(version_records "$REAL_RECORDS")"
REAL_DIGESTS="$(digest_records "$REAL_RECORDS")"
REAL_SHARED="$(shared_names "$REAL_VERSIONS")"

# The liveness of the whole file. An empty intersection makes both rules below
# vacuous, and a vacuous rule reports a repository it never read. When this
# check goes red because runner/ was deleted, DELETE THIS FILE — the rule has
# no subject left, and that is the intended end of it, not a hole to widen.
if [[ "$(count_lines "$REAL_SHARED")" -ge 1 ]]; then
  pass_check "the_two_homes_still_share_at_least_one_pin"
else
  fail_check "the_two_homes_still_share_at_least_one_pin" \
    "${ENV_HOME} and ${DOCKERFILE_HOME} share no pin, so rule 1 below judges nothing" \
    "if runner/ was deleted, delete this test file in the same change — it is the last" \
    "reader of that pair and it has no other subject" \
    "if runner/Dockerfile went value-less instead, this rule is finished and the same" \
    "deletion applies: a home that declares no value cannot drift from one that does" \
    "it read:" "${REAL_SHARED:-<nothing>}"
fi

version_drift="$(value_disagreements "$REAL_VERSIONS")"
if [[ -z "$version_drift" ]]; then
  pass_check "every_pin_in_both_homes_holds_the_same_version"
else
  fail_check "every_pin_in_both_homes_holds_the_same_version" \
    "these pins hold 2 values across ${ENV_HOME} and ${DOCKERFILE_HOME}:" \
    "$version_drift" \
    "a bump edits every home of a pin. bump_pin does that by itself, so a disagreement" \
    "here is a hand edit that reached 1 home, and the diff of it reads like a bump"
fi

digest_drift="$(value_disagreements "$REAL_DIGESTS")"
if [[ -z "$digest_drift" ]]; then
  pass_check "every_digest_row_in_both_homes_holds_the_same_digest"
else
  fail_check "every_digest_row_in_both_homes_holds_the_same_digest" \
    "these digest rows hold 2 values across ${ENV_HOME} and ${DOCKERFILE_HOME}:" \
    "$digest_drift" \
    "download-coverage.test.sh holds this pair too, and only while the 2 VERSIONS agree —" \
    "a half-applied bump moves both rows in 1 home, which is the case it skips"
fi

# ===========================================================================
# 2. RULE 2, THE WRITER — every home of the pin, and no other line
# ===========================================================================
#
# THE CONTRACT
#
#   bump_pin <root> <pin> <version> <digest> <evidence>
#
#   <root>      the tree to edit. PIN_VALUE_HOMES is looked for under it, so a
#               fixture tree and the repository run through 1 body.
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

full_records="$(home_declarations "$ENV_HOME" "${full_world}/${ENV_HOME}")
$(home_declarations "$DOCKERFILE_HOME" "${full_world}/${DOCKERFILE_HOME}")"

assert_equal "the_writer_rewrites_the_version_in_the_env_home" \
  "$WRITER_NEW_VERSION" "$(record_value "$full_records" "$ENV_HOME" "$WRITER_PIN")" \
  "output was:" "${BUMP_OUTPUT:-<none>}"

assert_equal "the_writer_rewrites_the_version_in_the_dockerfile_home" \
  "$WRITER_NEW_VERSION" "$(record_value "$full_records" "$DOCKERFILE_HOME" "$WRITER_PIN")" \
  "a writer that edits ${ENV_HOME} alone re-creates the drift rule 1 forbids," \
  "every Monday, in a pull request that reads like a bump" \
  "output was:" "${BUMP_OUTPUT:-<none>}"

# The digest and its evidence are 1 check per home on purpose: they are written
# by 1 edit to 1 row, and a row that carries a new digest under the previous
# url is not 2 defects, it is 1 row nobody may trust.
for home in "$ENV_HOME" "$DOCKERFILE_HOME"; do
  digest_line="$(declaration_line "${full_world}/${home}" "$WRITER_DIGEST_ROW")"
  digest_value="$(declaration_value "$digest_line")"
  evidence_word="$(evidence_of "$digest_line")"
  if [[ "$digest_value" == "$WRITER_NEW_DIGEST" \
    && "$evidence_word" == "upstream-published" ]] \
    && grep -qF -- "https://example.invalid/writertool/v1.5.0/checksums.txt" <<< "$digest_line"; then
    pass_check "the_writer_rewrites_the_digest_and_its_evidence_in_${home//\//_}"
  else
    fail_check "the_writer_rewrites_the_digest_and_its_evidence_in_${home//\//_}" \
      "want: ${WRITER_DIGEST_ROW}=${WRITER_NEW_DIGEST}, evidence upstream-published," \
      "      naming https://example.invalid/writertool/v1.5.0/checksums.txt" \
      "got:  value '${digest_value:-<none>}', evidence '${evidence_word:-<none>}'" \
      "the line reads:" "${digest_line:-<no such row>}" \
      "an equal version means equal bytes, so a digest left behind in 1 home makes that" \
      "image reject what the other one installs — and a digest with no evidence naming the" \
      "release it was read from is a number a reviewer has to take on faith"
  fi
done

# -------- 2b. and it touches nothing else ------------------------------------
# 2 lines per home: the version row and the digest row. Every other line — the
# 2 pins this bump is not about, the RUN block, the comments — reads the same.
for home in "$ENV_HOME" "$DOCKERFILE_HOME"; do
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
  pass_check "the_tree_the_writer_wrote_still_mirrors_both_homes"
else
  fail_check "the_tree_the_writer_wrote_still_mirrors_both_homes" \
    "the writer exited ${BUMP_STATUS}, and rule 1 over the tree it left reports:" \
    "${written_disagreements:-<nothing, but the writer did not exit 0>}" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
fi

# -------- 2d. a pin with no digest row: the version alone moves --------------
plain_world="$(writer_world "plain")"
plain_before="$WORK/plain-before"
run_bump_pin "$plain_world" "$WRITER_PLAIN_PIN" "$WRITER_PLAIN_NEW_VERSION" "$NO_DIGEST" "$NO_DIGEST"

plain_records="$(home_declarations "$ENV_HOME" "${plain_world}/${ENV_HOME}")
$(home_declarations "$DOCKERFILE_HOME" "${plain_world}/${DOCKERFILE_HOME}")"
if [[ "$BUMP_STATUS" -eq 0 \
  && "$(record_value "$plain_records" "$ENV_HOME" "$WRITER_PLAIN_PIN")" == "$WRITER_PLAIN_NEW_VERSION" \
  && "$(record_value "$plain_records" "$DOCKERFILE_HOME" "$WRITER_PLAIN_PIN")" == "$WRITER_PLAIN_NEW_VERSION" ]]; then
  pass_check "the_writer_bumps_a_pin_that_carries_no_digest_row_in_both_homes"
else
  fail_check "the_writer_bumps_a_pin_that_carries_no_digest_row_in_both_homes" \
    "want: exit 0 and ${WRITER_PLAIN_PIN}=${WRITER_PLAIN_NEW_VERSION} in both homes" \
    "got:  exit ${BUMP_STATUS}, ${ENV_HOME} has '$(record_value "$plain_records" "$ENV_HOME" "$WRITER_PLAIN_PIN")'," \
    "      ${DOCKERFILE_HOME} has '$(record_value "$plain_records" "$DOCKERFILE_HOME" "$WRITER_PLAIN_PIN")'" \
    "CICTL_VERSION and CLAUDE_CODE_VERSION are this shape in the real pair — installed by" \
    "go install and by an installer script — so a writer that requires a digest row bumps" \
    "2 of the 3 pins this file is about, and neither of them loudly" \
    "output was:" "${BUMP_OUTPUT:-<none>}"
fi

for home in "$ENV_HOME" "$DOCKERFILE_HOME"; do
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
