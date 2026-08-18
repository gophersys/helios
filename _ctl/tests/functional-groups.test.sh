#!/usr/bin/env bash
#
# _ctl/tests/functional-groups.test.sh — a failing functional group must fail
# the guest.
#
# Hermetic: a stub TOOLCHAIN first on PATH, the real .ci/fixtures/ copied to a
# temporary directory, and a 1-row comparator table this file writes. No daemon,
# no network, no image.
#
# ============================================================================
# WHY THIS IS A FILE OF ITS OWN, NEXT TO guest-checks.test.sh
# ============================================================================
#
# guest-checks.test.sh drives the COMPARATOR half of .ci/image-checks.sh: 2
# version stubs, a PATH built for reading `<tool> --version`, and evidence that
# reads "this pin was compared against that observed version".
#
# This file drives the FUNCTIONAL half: 13 stubbed tools, the real fixture tree,
# and evidence that reads "this step failed, so the run failed". The 2 halves
# share nothing but the script under test — a different stub surface, a
# different failure signature — and `bash ./ctl.sh test` names the file that
# broke, so keeping them apart names the contract that broke.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# .ci/image-checks.sh wraps 2 prerequisite steps in a subshell:
#
#     ( cd "$module"   && run_step "go build" ... ) || return 0     :215
#     ( cd "$fixtures" && run_step "buf build" ... ) || return 0    :281
#
# `fail` sets FAILED=1, and it sets it INSIDE the subshell. The parent never
# sees the assignment, `|| return 0` then discards the status the subshell did
# carry out, and the run ends with:
#
#     FAIL: go build: exited 1
#     image-checks.sh: every check passed
#     EXIT=0
#
# A FAIL line, a success banner and exit 0, in 1 run. That is the
# check-that-cannot-fail class this repository has shipped before, and the whole
# reason .ci/image-checks.sh was made a testable file at all. Reproduced by
# drill on 2026-08-16 for both lines.
#
# So every case below asserts 3 things as 1 check — the STATUS, the FAIL line,
# and the ABSENCE of the success banner. Split into 3, a reader could see 2 of
# them green and believe the group is guarded; the defect above shows up as
# exactly that combination.
#
# ============================================================================
# WHAT THE CASES COVER
# ============================================================================
#
#   1 case per functional group (go-gate, dockerfile-lint, compose, debugger,
#     protocols) and 2 content groups (content-flutter, content-hardware): 1 step
#     of the group is made to fail, and the run must fail.
#
#   the 3 KiCad library FLOORS of content-hardware, all 3 branches: an absent
#     directory, a directory under its floor, and one over it. This paragraph
#     said the floors were NOT COVERED and named the reason — kicad_library_floor
#     took an absolute /usr/share/kicad path, so a case over it would have
#     asserted a property of the HOST this file runs on. SMOKE_KICAD_ROOT is the
#     seam that answered it: the default is the image's own path, so a real run is
#     unchanged, and the cases below point it at a tree this file builds.
#   reachability: 2 groups named together both run. The guest splits SMOKE_CHECKS
#     by hand because it runs with IFS=$'\n\t', and a split that regressed would
#     make every group unknown at once.
#   collection: the header of .ci/image-checks.sh states "every failure is
#     collected rather than fatal". A failure in the FIRST group must fail the
#     run AND leave the second group running.
#
# Usage: bash _ctl/tests/functional-groups.test.sh
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

TEST_NAME="functional-groups.test.sh"

GUEST="$REPO_ROOT/.ci/image-checks.sh"
STUB_TOOLCHAIN="$TESTS_DIR/stubs/toolchain"
FIXTURES="$REPO_ROOT/.ci/fixtures"

# The stubs this file needs on PATH. Named as a list because the precondition
# check below has to say WHICH one is missing: a stub that is not executable
# makes its group fail for a reason no case here chose, and the case would then
# be green about nothing.
STUB_TOOLS=(
  go gofumpt golangci-lint hnslint
  hadolint docker dlv buf grpcurl
  flutter adb java
  kicad-cli
)

# The PATH every case runs with: the stub toolchain, then the 2 directories that
# hold the standard utilities the guest needs (mktemp, cat, awk, rm, chmod). The
# developer's own PATH is left out on purpose, so a real `go` or a real
# `hadolint` on this machine cannot answer.
GUEST_PATH="${STUB_TOOLCHAIN}:/usr/bin:/bin"

# The comparator has to pass, so that every non-zero status below comes from a
# functional group and from nothing else. 1 row, read by the stub hnslint.
# An empty PIN_TABLE fails by contract, so "no table" is not an option here.
PIN_TABLE_OK="HNSLINT_VERSION|0.1.0|hnslint --version"

# The banner the guest prints when it believes everything passed. It is a
# literal here, and deliberately so: a test that read the sentence out of the
# file it checks would agree with any sentence, a wrong one included.
SUCCESS_BANNER="image-checks.sh: every check passed"

GUEST_OUTPUT=""
GUEST_STATUS=0

# run_groups <SMOKE_CHECKS> [KEY=VALUE ...] — the guest, on the host, against the
# stub toolchain and a fresh copy of the real fixture tree.
#
# The fixtures are COPIED and not pointed at: the go-gate group writes caches and
# a binary under a temporary root, and a case must not be able to modify the tree
# the next case reads.
function run_groups() {
  local groups="$1"
  shift
  local fixture_dir
  fixture_dir="$(mktemp -d)"
  cp -R "${FIXTURES}/." "${fixture_dir}/"
  GUEST_STATUS=0
  GUEST_OUTPUT="$(env PATH="$GUEST_PATH" \
    PIN_TABLE="$PIN_TABLE_OK" \
    SMOKE_CHECKS="$groups" \
    SMOKE_FIXTURE_DIR="$fixture_dir" \
    "$@" bash "$GUEST" < /dev/null 2>&1)" || GUEST_STATUS=$?
  rm -rf "$fixture_dir"
}

# ---------------------------------------------------------------------------
# THE KiCad SHARE TREE, BUILT RATHER THAN COMMITTED
# ---------------------------------------------------------------------------
#
# The 3 floors are 10000 footprints, 100 symbol libraries and 1000 STEP models,
# and those numbers are gophersys/research-hardware's own, from the assertion at
# the foot of its ci/Dockerfile. So a committed fixture would be 11100 empty
# files in this repository's history, which is not a fixture; it is a payload.
# The tree is therefore BUILT into a temporary directory per case and removed
# after it — measured at ~0.4s for the 10001-file directory, which is the whole
# cost of driving the branch that reports a thin library.
#
# The FLOOR CONSTANTS are literals here, and they are the same literals
# .ci/image-checks.sh spells. That is 2 homes for 1 number and it is deliberate,
# for the reason platform-policy.test.sh spells SANCTIONED as a literal: a case
# that read the floor out of the file it drives would agree with any floor,
# including 0 — and a floor of 0 is precisely the defect a floor exists to
# prevent, since `kicad` under --no-install-recommends leaves /usr/share/kicad
# present and EMPTY.
KICAD_FOOTPRINT_FLOOR=10000
KICAD_SYMBOL_FLOOR=100
KICAD_MODEL_FLOOR=1000

# make_kicad_root <footprints> <symbols> <models> — a KiCad share tree holding
# exactly those counts, printed as a path the caller must remove.
#
# A count of -1 means the DIRECTORY IS ABSENT, which is a different world from a
# directory holding 0 files: an absent directory is a package that never
# installed, and `find` over one answers 0 while reporting an error nobody reads.
# kicad_library_floor tests for the directory before it counts, and that branch
# needs a stimulus of its own.
#
# awk + a single xargs, and not a shell loop: 10001 forks of `touch` takes
# minutes, and a case slow enough to skip is a case that gets skipped.
function make_kicad_root() {
  local footprints="$1" symbols="$2" models="$3"
  local root
  root="$(mktemp -d)"
  make_kicad_directory "${root}/footprints" "$footprints" "kicad_mod"
  make_kicad_directory "${root}/symbols" "$symbols" "kicad_sym"
  make_kicad_directory "${root}/3dmodels" "$models" "step"
  printf '%s' "$root"
}

# make_kicad_directory <path> <count> <extension> — <count> empty files of that
# extension, or nothing at all when the count is negative.
function make_kicad_directory() {
  local path="$1" count="$2" extension="$3"
  [[ "$count" -lt 0 ]] && return 0
  mkdir -p "$path"
  [[ "$count" -eq 0 ]] && return 0
  awk -v directory="$path" -v total="$count" -v extension="$extension" \
    'BEGIN { for (index_of_file = 1; index_of_file <= total; index_of_file++) {
       printf "%s/part%06d.%s\n", directory, index_of_file, extension } }' \
    | xargs touch
}

# assert_group_failed <check name> <needle> [needle...]
#
# 3 conditions, 1 check. See the header: the defect under test prints a FAIL
# line, prints the success banner and exits 0, so a check that read any one of
# those alone would report 2 greens on a run that swallowed a failure.
function assert_group_failed() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! grep -qF -- "$needle" <<< "$GUEST_OUTPUT"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$GUEST_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status — a step of this group failed" \
      "got:  0 — the guest reported the image as checked" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the guest exited ${GUEST_STATUS}, and its output names none of:" \
      "$missing_names" \
      "a run that fails without naming the step sends the reader to read every group" \
      "output was:" "$GUEST_OUTPUT"
  elif grep -qF -- "$SUCCESS_BANNER" <<< "$GUEST_OUTPUT"; then
    fail_check "$name" \
      "the guest exited ${GUEST_STATUS} and named the step, and it ALSO printed:" \
      "$SUCCESS_BANNER" \
      "a run that reports a failure and success at once is read as success by a human" \
      "output was:" "$GUEST_OUTPUT"
  else
    pass_check "$name"
  fi
}

# assert_group_passed <check name> <needle> [needle...] — the mirror. Exit 0, and
# every named step really ran. The names matter: a guest that dispatched no group
# at all also exits 0, and that is a whole functional half silently unreachable.
function assert_group_passed() {
  local name="$1"
  shift
  local needle missing_names=""
  for needle in "$@"; do
    if ! grep -qF -- "$needle" <<< "$GUEST_OUTPUT"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$GUEST_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "want: exit 0 — every stubbed tool answers" \
      "got:  ${GUEST_STATUS}" \
      "output was:" "$GUEST_OUTPUT"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the guest exited 0, and its output names none of:" \
      "$missing_names" \
      "a group that is named and never dispatched exits 0 while checking nothing" \
      "output was:" "$GUEST_OUTPUT"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 0. the preconditions every case below depends on --------
if [[ -f "$GUEST" ]]; then
  pass_check "the_guest_checker_is_a_file"
else
  fail_check "the_guest_checker_is_a_file" \
    "absent: ${GUEST}" \
    "the functional groups live in that file, and nothing here can run them without it"
fi

missing_stubs=""
for stub in "${STUB_TOOLS[@]}"; do
  [[ -x "${STUB_TOOLCHAIN}/${stub}" ]] && continue
  missing_stubs="${missing_stubs:+${missing_stubs} }${stub}"
done
if [[ -z "$missing_stubs" ]]; then
  pass_check "every_toolchain_stub_is_executable"
else
  fail_check "every_toolchain_stub_is_executable" \
    "not executable under ${STUB_TOOLCHAIN}: ${missing_stubs}" \
    "a stub that cannot run makes its group fail for a reason no case here chose"
fi

# -------- 1. go-gate: the prerequisite step fails --------
# The subshell at .ci/image-checks.sh:215. `go build` is the step, and it is the
# prerequisite of the debugger group, so its failure is the one that matters most.
run_groups "go-gate" STUB_FAIL_GO=1
assert_group_failed "a_failing_go_build_fails_the_run" \
  "FAIL: go build"

# -------- 2. dockerfile-lint --------
run_groups "dockerfile-lint" STUB_FAIL_HADOLINT=1
assert_group_failed "a_failing_hadolint_fails_the_run" \
  "FAIL: hadolint"

# -------- 3. compose --------
run_groups "compose" STUB_FAIL_DOCKER_COMPOSE=1
assert_group_failed "a_failing_compose_config_fails_the_run" \
  "FAIL: docker compose config"

# -------- 4. debugger --------
# go-gate runs first and passes, so the debugger group gets the binary it needs
# and the ONLY failing step is the debugger itself. Without that, this case would
# fail on the "no binary to trace" precondition and prove nothing about dlv.
run_groups "go-gate debugger" STUB_FAIL_DLV=1
assert_group_failed "a_failing_debugger_fails_the_run" \
  "FAIL: dlv exec"

# -------- 5. protocols: the second prerequisite step --------
# The subshell at .ci/image-checks.sh:281, the same shape as :215.
run_groups "protocols" STUB_FAIL_BUF=1
assert_group_failed "a_failing_buf_build_fails_the_run" \
  "FAIL: buf build"

# The other half of the same group, which is NOT in a subshell. Both halves are
# checked, so a fix that repairs 1 line and leaves the other cannot read as done.
run_groups "protocols" STUB_FAIL_GRPCURL=1
assert_group_failed "a_failing_grpcurl_fails_the_run" \
  "FAIL: grpcurl"

# -------- 6. a content group --------
run_groups "content-flutter" STUB_FAIL_FLUTTER=1
assert_group_failed "a_failing_content_step_fails_the_run" \
  "FAIL: flutter"
# ... and the steps after it still ran. This is the collected-failures rule of
# the header, inside 1 group: 3 tools with 1 broken should report 1 broken tool,
# not stop at the first.
assert_contains "a_failing_content_step_does_not_stop_the_steps_after_it" \
  "$GUEST_OUTPUT" "ok   java" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "a group that stops at its first failure reports 1 broken tool out of an unknown number"

# -------- 6b. the SECOND content group, and the newest one --------
#
# content-hardware is the group `hardware` adds, and nothing exercised it: a
# content group is reachable only through the `case` in run_functional_groups,
# and a group name that reaches no arm falls through to `unknown check group`.
# Both outcomes exit non-zero, so a status alone cannot tell "kicad-cli failed"
# from "this group does not exist" — which is why the needles below name the
# STEP and the group's own header line, and not the status.
run_groups "content-hardware" STUB_FAIL_KICAD_CLI=1
assert_group_failed "a_failing_kicad_cli_fails_the_run" \
  "FAIL: kicad-cli" "--- hardware content ---"

# -------- 6c. the 3 library floors, all 3 branches --------
#
# WHY THE FLOORS ARE THE POINT OF THIS GROUP. `kicad` does NOT pull the symbol,
# footprint and 3D-model packages in under --no-install-recommends. Without them
# /usr/share/kicad EXISTS and is EMPTY, so an image carrying kicad-cli passes
# every presence check — `kicad-cli version` runs perfectly — and then fails the
# consumer's entire resolver suite at runtime on `assert 0 > 10000`, which reads
# like a code bug rather than a missing package.
#
# WHICH HALF RUNS WHERE. These cases are the PULL REQUEST half: they drive the
# comparator itself, on this host, against a tree this file builds, so a floor
# that stopped being able to fail is red before the branch merges. The SMOKE half
# runs in CI, inside the built image, against the real /usr/share/kicad — that is
# what says the packages really installed. Neither replaces the other: this one
# cannot see the image, and that one cannot run in the gate.
#
# DELETING kicad-packages3d FROM THE APT LINE IS CAUGHT BY THE UNDER-FLOOR CASE
# BELOW. That is the concrete regression: the models package leaves
# hardware/Dockerfile, the image builds green, kicad-cli runs, and every
# footprint ships with no 3D geometry. In the image the directory would be absent
# and the first case is its shape; if a later KiCad release ships a stub
# directory instead, the second case is its shape. Both are driven here.

# The absent directory: the package never installed. `find` over a path that is
# not there answers 0 and prints an error nobody reads, so a reader that counted
# first would report a thin library where the truth is no library at all.
kicad_root="$(make_kicad_root -1 "$KICAD_SYMBOL_FLOOR" "$KICAD_MODEL_FLOOR")"
run_groups "content-hardware" "SMOKE_KICAD_ROOT=${kicad_root}"
assert_group_failed "an_absent_kicad_library_directory_fails_and_names_the_path" \
  "FAIL: kicad footprints" "${kicad_root}/footprints"
rm -rf "$kicad_root"

# Under the floor by 1. The boundary and not a round number: a floor compared
# with `<=` where `<` was meant, or against the wrong constant, passes every
# stimulus that is far from its edge.
kicad_root="$(make_kicad_root $((KICAD_FOOTPRINT_FLOOR - 1)) "$KICAD_SYMBOL_FLOOR" "$KICAD_MODEL_FLOOR")"
run_groups "content-hardware" "SMOKE_KICAD_ROOT=${kicad_root}"
assert_group_failed "a_kicad_library_under_its_floor_fails_and_names_the_count_and_the_floor" \
  "FAIL: kicad footprints" "$((KICAD_FOOTPRINT_FLOOR - 1))" "$KICAD_FOOTPRINT_FLOOR"
rm -rf "$kicad_root"

# The 3rd package specifically, so all 3 floors are known to be wired to their
# own directory. A single reader pointed at 1 path would pass the 2 cases above
# and report a green tree with no STEP models in it.
kicad_root="$(make_kicad_root "$KICAD_FOOTPRINT_FLOOR" "$KICAD_SYMBOL_FLOOR" $((KICAD_MODEL_FLOOR - 1)))"
run_groups "content-hardware" "SMOKE_KICAD_ROOT=${kicad_root}"
assert_group_failed "a_thin_kicad_3dmodels_tree_fails_and_names_that_floor" \
  "FAIL: kicad STEP models" "$((KICAD_MODEL_FLOOR - 1))" "$KICAD_MODEL_FLOOR"
rm -rf "$kicad_root"

# EXACTLY AT the floor, on all 3, and the run passes. Without this half a
# comparator stuck on "fail always" satisfies every case above, and the floor is
# inclusive — an image sitting on its own limit must not be refused.
kicad_root="$(make_kicad_root "$KICAD_FOOTPRINT_FLOOR" "$KICAD_SYMBOL_FLOOR" "$KICAD_MODEL_FLOOR")"
run_groups "content-hardware" "SMOKE_KICAD_ROOT=${kicad_root}"
assert_group_passed "kicad_libraries_at_their_floors_pass_and_name_all_3_counts" \
  "ok   kicad footprints: ${KICAD_FOOTPRINT_FLOOR}" \
  "ok   kicad symbol libraries: ${KICAD_SYMBOL_FLOOR}" \
  "ok   kicad STEP models: ${KICAD_MODEL_FLOOR}"
rm -rf "$kicad_root"

# -------- 7. every named group is reached --------
# The guest runs with IFS=$'\n\t' and splits SMOKE_CHECKS by hand. A regression
# there reads the whole list as 1 word, every group becomes unknown at once, and
# the functional half of the smoke silently stops running.
run_groups "go-gate protocols"
assert_group_passed "naming_two_groups_runs_both_of_them" \
  "ok   go build" "ok   buf build" "ok   grpcurl list"

# -------- 8. a failure in the first group is collected, not fatal --------
# 2 angles, because the 2 failure paths of the guest behave in opposite ways and
# a fix for either one can break the other.
#
# The swallowed path first: the first group is go-gate, whose failing step is
# inside the `|| return 0` subshell. The run must fail.
run_groups "go-gate protocols" STUB_FAIL_GO=1
assert_group_failed "a_failure_in_the_first_group_fails_the_whole_run" \
  "FAIL: go build"
# The second group runs today only BECAUSE that failure was swallowed, so this
# check is here to hold the fix: repairing the subshell must not turn a failing
# group into an abort that takes every later group with it.
assert_contains "a_failure_in_the_first_group_does_not_stop_the_second" \
  "$GUEST_OUTPUT" "ok   buf build" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "44 pins with 3 drifts must report 3 drifts, and a fatal first failure reports 1"

# The fatal path second: the first group is dockerfile-lint, whose failing step
# is a bare `run_step` and not a subshell, so `set -e` ends the guest there.
run_groups "dockerfile-lint protocols" STUB_FAIL_HADOLINT=1
assert_group_failed "a_fatal_first_group_still_fails_the_whole_run" \
  "FAIL: hadolint"
assert_contains "a_failing_first_group_leaves_the_second_group_running" \
  "$GUEST_OUTPUT" "ok   buf build" \
  "the header of .ci/image-checks.sh states that every failure is collected rather than fatal" \
  "an image with a broken hadolint AND a broken buf must report both, and a run that" \
  "stops at the first one publishes the reader an incomplete list of what is wrong"

test_summary "$TEST_NAME"
