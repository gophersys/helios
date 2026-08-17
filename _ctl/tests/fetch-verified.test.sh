#!/usr/bin/env bash
#
# _ctl/tests/fetch-verified.test.sh — the fetcher is EXECUTED, not read.
#
# Hermetic: a payload this repository holds, fetched over file://, and a PATH
# this file builds. No network, no daemon, no credential.
#
# ============================================================================
# WHY THIS FILE DRIVES THE SCRIPT INSTEAD OF READING IT
# ============================================================================
#
# _build/fetch-verified.sh is the ONE thing standing between 46 downloads and
# whatever the far end decides to send. Every other check of this change is
# static: download-coverage.test.sh proves each download NAMES a digest, and
# dockerfile-args.test.sh proves the name resolves to an ARG. Not one of them
# can tell whether the helper compares anything at all.
#
# That gap has been shipped here before. `.ci/notify-failure.sh` had 287 checks
# pointing at it and every one read it as a FILENAME, so the 2-token defect in
# its close loop survived a fully green `validate` and `test`. Replace the
# `sha256sum -c` line in the helper with `true` and every static check of this
# change stays green while every download stops being verified. So the cases
# below run the real file and read the status it returns and the bytes it left
# on disk.
#
# ============================================================================
# A NON-ZERO STATUS IS NOT EVIDENCE ON ITS OWN
# ============================================================================
#
# This is the load-bearing rule of this file, and it is why every failure case
# below is 1 check with 2 conditions rather than 2 checks.
#
# The helper does not exist yet. `bash _build/fetch-verified.sh` therefore
# exits 127 — non-zero. A case that asserted "the exit status is non-zero" and
# nothing else would PASS today, against a file that is not there, and would go
# on passing against a helper that exits 1 for a reason nobody wrote down. A
# check that a missing file satisfies is the worst kind this directory can
# hold.
#
# So each failure case demands the status AND the thing the message has to
# name: the pin, or the tool. A caller reading `docker build` output has 400
# lines of layer noise around the failure, and "exit 1" in the middle of it
# tells them nothing. The name is the whole value of failing loudly.
#
# ============================================================================
# THE CONTRACT
# ============================================================================
#
#   fetch-verified.sh <url> <destination> <sha256> <pin name>
#
#   right digest      exit 0, and <destination> holds the fetched bytes
#   wrong digest      exit non-zero, message names <pin name>, and NOTHING is
#                     left at <destination> — a half-written binary on PATH is
#                     worse than no binary, because the next layer runs it
#   empty digest      exit non-zero, message names <pin name>. This is the
#                     shape of a build-arg that never arrived: ${X_SHA256_AMD64}
#                     expands to the empty string and the download would
#                     otherwise be compared against nothing
#   short digest      exit non-zero, message names <pin name>. 63 characters
#                     reads as correct in a diff
#   no sha256sum      exit non-zero, message names sha256sum. FAIL-NOT-SKIP: a
#                     helper that quietly installs the file when it cannot
#                     verify it is an unverified download wearing the name of a
#                     verified one
#
# 2 properties of the helper that the cases below depend on, and that the
# implementer therefore has to hold:
#
#   - it is EXECUTED, never sourced, and carries its own bash shebang. base
#     switches SHELL to zsh after oh-my-zsh, so a helper that relied on the
#     calling shell would behave differently in 2 of the 6 images.
#   - it does not restrict the URL scheme. The fetch here is file://, because
#     a hermetic test that runs in the pull request gate cannot reach the
#     network. `curl --proto '=https'` would harden the helper and blind this
#     file at the same time; the hardening that is worth having is the digest.
#
# Usage: bash _ctl/tests/fetch-verified.test.sh
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

TEST_NAME="fetch-verified.test.sh"

HELPER_RELATIVE="_build/fetch-verified.sh"
HELPER="$REPO_ROOT/$HELPER_RELATIVE"

PAYLOAD="$TESTS_DIR/fixtures/fetch-verified/payload.bin"

# The digest of that payload, as a LITERAL. A test that computes the value it
# checks agrees with any bytes, the wrong ones included — the same reason
# platform-policy.test.sh spells SANCTIONED out instead of reading it.
PAYLOAD_SHA256="0aab22eb0615cb7ca1440cd82fab36f1f622885a796baf2268e82edd68e57967"

# 64 hex characters that are not the payload's. This is the compromised-asset
# case: the pin is well-formed and the bytes are not the ones it names.
WRONG_SHA256="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

# 63 characters. A digest 1 character short reads as correct in a diff.
SHORT_SHA256="0aab22eb0615cb7ca1440cd82fab36f1f622885a796baf2268e82edd68e5796"

# The pin name each case passes and each message has to name. It is not a real
# pin of this repository, so a message that happens to quote versions.env
# cannot satisfy the assertion by accident.
PIN_NAME="TESTTOOL_SHA256_AMD64"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
CASE_NUMBER=0

HELPER_OUTPUT=""
HELPER_STATUS=0

# ---------------------------------------------------------------------------
# The PATH every case runs with.
#
# The developer's own PATH is left out on purpose: a tool that happens to be
# installed on this laptop and not on the runner would make the same case mean
# 2 things. What goes in is the directory holding curl, the directory holding
# sha256sum, and the 2 standard directories.
#
# A missing tool here is a FAILURE and never a skip. Without sha256sum every
# case below would fail for a reason that says nothing about the helper, and
# "sha256sum not installed — skipping" is a green result that checked nothing.
# ---------------------------------------------------------------------------
MISSING_TOOLS=""
CURL_DIRECTORY=""
SHA256SUM_DIRECTORY=""

if command -v curl > /dev/null 2>&1; then
  CURL_DIRECTORY="$(cd "$(dirname "$(command -v curl)")" && pwd)"
else
  MISSING_TOOLS="${MISSING_TOOLS:+${MISSING_TOOLS}
}curl"
fi

if command -v sha256sum > /dev/null 2>&1; then
  SHA256SUM_DIRECTORY="$(cd "$(dirname "$(command -v sha256sum)")" && pwd)"
else
  MISSING_TOOLS="${MISSING_TOOLS:+${MISSING_TOOLS}
}sha256sum"
fi

# directory_list <directory...> — the given directories, in order, with the
# empty ones and the repeats dropped.
function directory_list() {
  local directory seen="" out=""
  for directory in "$@"; do
    [[ -z "$directory" ]] && continue
    if grep -qxF -- "$directory" <<< "$seen"; then
      continue
    fi
    seen="${seen:+${seen}
}${directory}"
    out="${out:+${out}:}${directory}"
  done
  printf '%s' "$out"
}

HELPER_PATH="$(directory_list "$CURL_DIRECTORY" "$SHA256SUM_DIRECTORY" "/usr/bin" "/bin")"

# The same world with sha256sum taken out of it.
#
# Dropping the directory is not enough: on a Linux runner sha256sum lives in
# /usr/bin, which also holds curl, env and everything else the helper needs. So
# the directory is mirrored into a farm of symlinks with exactly 1 name left
# out, and the farm replaces it in PATH.
SHA256SUM_FARM="$WORK/no-sha256sum"
mkdir -p "$SHA256SUM_FARM"
if [[ -n "$SHA256SUM_DIRECTORY" ]]; then
  while IFS= read -r entry; do
    [[ -z "$entry" ]] && continue
    [[ "$(basename "$entry")" == "sha256sum" ]] && continue
    ln -sf "$entry" "$SHA256SUM_FARM/$(basename "$entry")"
  done < <(find "$SHA256SUM_DIRECTORY" -maxdepth 1 -mindepth 1)
fi

NO_SHA256SUM_PATH="${SHA256SUM_FARM}"
while IFS= read -r directory; do
  [[ -z "$directory" ]] && continue
  [[ "$directory" == "$SHA256SUM_DIRECTORY" ]] && continue
  NO_SHA256SUM_PATH="${NO_SHA256SUM_PATH}:${directory}"
done < <(tr ':' '\n' <<< "$HELPER_PATH")

# run_helper <path> <argv...> — run the REAL file, directly, so its shebang and
# its executable bit are part of what is under test. stdin is /dev/null: a
# helper that read the terminal would behave differently in a build than in
# this run, and that difference is exactly what a hermetic case must not have.
function run_helper() {
  local path="$1"
  shift
  HELPER_STATUS=0
  HELPER_OUTPUT="$(env PATH="$path" "$HELPER" "$@" < /dev/null 2>&1)" || HELPER_STATUS=$?
}

# next_case_directory — a fresh destination directory per case, with nothing in
# it. The mismatch cases assert the directory is still empty afterwards, which
# catches a temp file written beside the destination as well as the destination
# itself.
#
# It sets a variable and prints nothing, and that is not a style choice. The
# first version of this function returned the path through `$( )` and
# incremented the counter inside it. Command substitution runs in a SUBSHELL,
# so the increment was thrown away and all 5 cases shared $WORK/case-1 — the
# success case left tool.bin there, and the 3 leaves-nothing-behind checks then
# reported a helper that had written nothing. Measured against a conforming
# throwaway helper: 3 false reds, each one blaming the implementation for a
# defect in this file.
#
# The dirty-directory list below is the guard against that whole class: a case
# whose directory is not empty BEFORE it runs is reported, so a counter that
# stops counting cannot be read as a helper that misbehaves.
DIRTY_CASE_DIRECTORIES=""
CASE_DIRECTORY=""
function next_case_directory() {
  CASE_NUMBER=$((CASE_NUMBER + 1))
  CASE_DIRECTORY="$WORK/case-${CASE_NUMBER}"
  mkdir -p "$CASE_DIRECTORY"
  local before
  before="$(directory_entries "$CASE_DIRECTORY")"
  if [[ -n "$before" ]]; then
    DIRTY_CASE_DIRECTORIES="${DIRTY_CASE_DIRECTORIES:+${DIRTY_CASE_DIRECTORIES}
}case-${CASE_NUMBER} already held: ${before}"
  fi
}

# directory_entries <directory> — everything the directory holds, 1 per line.
function directory_entries() {
  local directory="$1"
  find "$directory" -mindepth 1 | sed -e "s#^${directory}/##"
}

# assert_destination_is_empty <check name> <directory> [extra evidence...]
#
# The 3 leaves-nothing-behind cases need this guard, and the guard is the point.
# An empty directory is what a helper that verified correctly leaves, and it is
# ALSO what a helper that never ran leaves. Without the first condition these 3
# checks pass today — with no _build/fetch-verified.sh on disk at all — and a
# check that a missing file satisfies proves nothing about the file.
function assert_destination_is_empty() {
  local name="$1" directory="$2"
  shift 2
  local leftovers
  if [[ ! -x "$HELPER" ]]; then
    fail_check "$name" \
      "nothing ran: ${HELPER_RELATIVE} is not an executable file" \
      "an empty destination directory is what a correct refusal leaves AND what a helper" \
      "that never started leaves, so this check cannot be read until the helper exists" "$@"
    return
  fi
  leftovers="$(directory_entries "$directory")"
  if [[ -z "$leftovers" ]]; then
    pass_check "$name"
  else
    fail_check "$name" \
      "the destination directory is not empty:" \
      "$leftovers" "$@"
  fi
}

# assert_failed_and_named <check name> <needle> [extra evidence...]
#
# 2 conditions, 1 check, on purpose. See the header: the helper is absent
# today, so a bare status assertion passes against a file that does not exist.
# Only the pair is evidence.
function assert_failed_and_named() {
  local name="$1" needle="$2"
  shift 2
  if [[ "$HELPER_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status" "got:  0" \
      "output was:" "${HELPER_OUTPUT:-<no output>}" "$@"
  elif ! grep -qF -- "$needle" <<< "$HELPER_OUTPUT"; then
    fail_check "$name" \
      "the helper exited ${HELPER_STATUS}, and its message does not name: ${needle}" \
      "a status with no name is 400 lines into a docker build log, and it tells the reader nothing" \
      "output was:" "${HELPER_OUTPUT:-<no output>}" "$@"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 0. the world this file needs --------
if [[ -n "$MISSING_TOOLS" ]]; then
  fail_check "the_tools_these_cases_need_are_on_this_host" \
    "absent:" "$MISSING_TOOLS" \
    "every case below would fail for a reason that says nothing about the helper," \
    "and a skip here would be a green result that verified no download at all"
else
  pass_check "the_tools_these_cases_need_are_on_this_host"
fi

if [[ ! -f "$PAYLOAD" ]]; then
  fail_check "the_payload_fixture_exists_and_matches_its_literal_digest" \
    "absent: ${PAYLOAD}"
else
  payload_digest=""
  payload_digest_status=0
  payload_digest="$(sha256sum "$PAYLOAD" | awk '{ print $1 }')" || payload_digest_status=$?
  if [[ "$payload_digest_status" -ne 0 ]]; then
    fail_check "the_payload_fixture_exists_and_matches_its_literal_digest" \
      "sha256sum exited ${payload_digest_status} on ${PAYLOAD}"
  else
    assert_equal "the_payload_fixture_exists_and_matches_its_literal_digest" \
      "$PAYLOAD_SHA256" "$payload_digest" \
      "the literal in this file IS the pin every case below passes," \
      "so an edit to the payload turns every case red and this check says why"
  fi
fi

# The premise of the absent-tool case, verified rather than assumed. A probe
# that runs in a shell which already holds what it claims to have removed
# reports a pass it never earned — this repository has shipped that defect.
probe_output=""
probe_status=0
probe_output="$(env PATH="$NO_SHA256SUM_PATH" bash -c 'command -v sha256sum')" || probe_status=$?
if [[ "$probe_status" -eq 0 ]]; then
  fail_check "the_no_sha256sum_world_really_has_no_sha256sum" \
    "PATH=${NO_SHA256SUM_PATH}" \
    "still resolves sha256sum at: ${probe_output}" \
    "the absent-tool case below would then run against a world that has the tool"
else
  pass_check "the_no_sha256sum_world_really_has_no_sha256sum"
fi

# -------- 1. the helper is there, and it is a standalone bash program --------
if [[ -f "$HELPER" && -x "$HELPER" ]]; then
  pass_check "the_helper_exists_and_is_executable"
else
  fail_check "the_helper_exists_and_is_executable" \
    "want: an executable file at ${HELPER_RELATIVE}" \
    "got:  $( [[ -f "$HELPER" ]] && printf 'a file that is not executable' || printf 'no file' )" \
    "every case below runs it directly, so its executable bit is part of the contract"
fi

if [[ -f "$HELPER" ]]; then
  assert_contains "the_helper_declares_its_own_bash_shebang" \
    "$(head -n 1 "$HELPER")" "bash" \
    "base switches SHELL to zsh after oh-my-zsh, so a helper that inherited the calling" \
    "shell would behave differently in 2 of the 6 images"
else
  fail_check "the_helper_declares_its_own_bash_shebang" \
    "absent: ${HELPER_RELATIVE}"
fi

# -------- 2. the right digest: exit 0, and the bytes land --------
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$HELPER_PATH" "file://${PAYLOAD}" "$destination" "$PAYLOAD_SHA256" "$PIN_NAME"

if [[ "$HELPER_STATUS" -ne 0 ]]; then
  fail_check "a_matching_digest_exits_0_and_the_file_lands" \
    "the helper exited ${HELPER_STATUS} on the digest that DOES match the payload" \
    "output was:" "${HELPER_OUTPUT:-<no output>}"
elif [[ ! -f "$destination" ]]; then
  fail_check "a_matching_digest_exits_0_and_the_file_lands" \
    "the helper exited 0 and wrote nothing to ${destination}" \
    "an exit status is not a download; the check is the file" \
    "the destination directory holds:" "$(directory_entries "$destination_directory")"
elif ! cmp -s "$PAYLOAD" "$destination"; then
  fail_check "a_matching_digest_exits_0_and_the_file_lands" \
    "the helper exited 0 and the file it left is not the payload it fetched" \
    "want ${PAYLOAD_SHA256}, got $(sha256sum "$destination" | awk '{ print $1 }')"
else
  pass_check "a_matching_digest_exits_0_and_the_file_lands"
fi

# -------- 3. a wrong digest: non-zero, named, and NOTHING left behind --------
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$HELPER_PATH" "file://${PAYLOAD}" "$destination" "$WRONG_SHA256" "$PIN_NAME"

assert_failed_and_named "a_wrong_digest_exits_nonzero_and_names_the_pin" "$PIN_NAME" \
  "the pin name is how a reader finds the row to fix in versions.env or in the ARG block"

assert_destination_is_empty "a_wrong_digest_leaves_nothing_at_the_destination" \
  "$destination_directory" \
  "fetch into a temp path and move into place only after sha256sum -c agrees" \
  "a half-written binary on PATH is worse than no binary: the next layer runs it"

# -------- 4. an empty digest: the build-arg that never arrived --------
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$HELPER_PATH" "file://${PAYLOAD}" "$destination" "" "$PIN_NAME"

assert_failed_and_named "an_empty_digest_exits_nonzero_and_names_the_pin" "$PIN_NAME" \
  "an unset build-arg expands to the empty string, so this is what a forgotten pin looks like" \
  "the download would otherwise be compared against nothing and installed anyway"

assert_destination_is_empty "an_empty_digest_leaves_nothing_at_the_destination" \
  "$destination_directory" \
  "refuse BEFORE fetching: there is nothing to compare the bytes against"

# -------- 4b. and the refusal is on the ARGUMENT, before the fetch --------
#
# The case above does not discriminate as sharply as it looks. Measured against
# a conforming throwaway helper: delete the empty-digest guard and it stays
# green, because the 64-hex guard rejects the empty string too, and both name
# the pin. The 2 guards cover each other, so neither one alone is proven.
#
# What IS worth holding, and what this case holds, is that the refusal is a
# property of the ARGUMENT and not of the download. The URL here cannot be
# fetched. A helper that checks the digest argument first still names the pin;
# a helper that fetches first dies inside curl, and curl's failure says nothing
# about which pin was wrong — which is the whole reason the pin name is an
# argument.
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$HELPER_PATH" \
  "file:///nonexistent-path-for-the-fetch-verified-test/asset.bin" \
  "$destination" "" "$PIN_NAME"

assert_failed_and_named "an_empty_digest_is_refused_before_the_fetch_is_attempted" "$PIN_NAME" \
  "the URL of this case cannot be fetched, so a helper that downloads first fails inside curl" \
  "and reports a transport error for what is really a build argument that never arrived"

# -------- 5. a 63-character digest --------
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$HELPER_PATH" "file://${PAYLOAD}" "$destination" "$SHORT_SHA256" "$PIN_NAME"

assert_failed_and_named "a_63_character_digest_exits_nonzero_and_names_the_pin" "$PIN_NAME" \
  "63 characters reads as correct in a diff, and sha256sum -c would simply not match," \
  "which reports a compromised asset for what is really a typo in the pin"

# -------- 6. sha256sum absent: a FAILURE naming the tool, never a skip --------
next_case_directory
destination_directory="$CASE_DIRECTORY"
destination="$destination_directory/tool.bin"
run_helper "$NO_SHA256SUM_PATH" "file://${PAYLOAD}" "$destination" "$PAYLOAD_SHA256" "$PIN_NAME"

assert_failed_and_named "a_missing_sha256sum_exits_nonzero_and_names_the_tool" "sha256sum" \
  "the digest here MATCHES, so a helper that cannot verify and installs anyway exits 0 and" \
  "publishes an unverified download wearing the name of a verified one"

assert_destination_is_empty "a_missing_sha256sum_leaves_nothing_at_the_destination" \
  "$destination_directory" \
  "an unverifiable download must install nothing at all"

# -------- 7. every case really ran in a world of its own --------
# Last, because it reads what the 5 cases above left behind. See
# next_case_directory: a counter that stops counting makes 3 of the checks
# above blame the helper for a file an earlier case wrote.
if [[ -z "$DIRTY_CASE_DIRECTORIES" ]]; then
  pass_check "every_case_ran_in_its_own_empty_destination_directory"
else
  fail_check "every_case_ran_in_its_own_empty_destination_directory" \
    "these cases started in a directory that already held something:" \
    "$DIRTY_CASE_DIRECTORIES" \
    "the leaves-nothing-behind checks read that directory, so they would report" \
    "an earlier case's file as this helper's leftover"
fi

test_summary "$TEST_NAME"
