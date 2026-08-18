#!/usr/bin/env bash
#
# _ctl/tests/dispatcher-mode.test.sh — a per-image ctl.sh is EXECUTABLE, and
# `validate` is what holds it there.
#
# Static means static: this file reads files and runs `ctl.sh validate` inside a
# staged repository root of copies. It starts no container, it calls no daemon
# and it reaches no network, so it runs identically on a laptop and on a CI
# runner — and it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# A dispatcher's MODE is not something the gate could see. `validate` reads each
# per-image ctl.sh with shellcheck, and a reader is blind to the executable bit,
# so a file committed 100644 passed every check and died later in image_ctl —
# which refuses a non-executable dispatcher, and which runs AFTER the push.
# hardware/ctl.sh shipped that way (run 32133161779): the publish job pushed
# :latest and :<sha>, and `verify-published` then failed on the mode, leaving 2
# tags that no verb of this repository could read back. That is the exact
# ordering the build -> smoke -> push rule exists to avoid — the check that could
# have stopped it ran after the irreversible action.
#
# cmd_validate watches it now. This file is what holds the watcher.
#
# ============================================================================
# WHY THIS FILE EXISTS SEPARATELY FROM THE GATE
# ============================================================================
#
# The `[[ ! -x ]]` block in cmd_validate landed with NO test over it. A refactor
# of that verb that dropped the block would leave `ctl.sh validate` green,
# `ctl.sh test` green and the whole pull request gate green, and the next 100644
# dispatcher would reach the registry exactly as hardware's did. A gate nothing
# holds is a gate that lasts until the next person tidies the function.
#
# ============================================================================
# THE SEAM: THE VERB ITSELF, IN A STAGED ROOT
# ============================================================================
#
# The rule is 4 lines INSIDE cmd_validate and not a function, so there is
# nothing to call in isolation — and adding one would be a change to a
# non-test file. The whole verb is run instead, in a mktemp root holding a
# 2-image manifest and the small tree that manifest describes. That is the
# end-to-end read: a check written against a helper would still be green on the
# day the helper stopped being called.
#
# `validate` reaches for 4 tools, and 3 of them are real here. shellcheck and jq
# it refuses to run without, and yq answers the manifest — the position
# _ctl/tests/images-manifest.test.sh already takes, where a missing parser is a
# FAILURE and never a skip. hadolint is the 4th and is STUBBED, because it is
# the 1 tool whose resolution can leave the machine: a host whose hadolint is a
# point release off the pin sends the verb to `docker run`, and this suite
# promises no daemon. _ctl/tests/stubs/validate/hadolint carries the reason.
#
# The staged tree is COPIES and never symlinks, the rule
# _ctl/tests/images-manifest.test.sh states: nothing here writes to the
# repository, and a staging helper that can reach the real tree is 1 edit away
# from one that does. The chmods below act on the copies.
#
# ============================================================================
# WHAT THIS FILE DOES NOT PROVE
# ============================================================================
#
# The GIT INDEX mode. Every check here reads the filesystem, which is what
# `validate` reads, so a file that is -x on a developer's disk and 100644 in the
# index passes locally and fails in CI on a fresh checkout. CI is where it would
# be caught, and catching it a step earlier would be a NEW rule rather than a
# holder of this one.
#
# Usage: bash _ctl/tests/dispatcher-mode.test.sh
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

TEST_NAME="dispatcher-mode.test.sh"

FIXTURES="$TESTS_DIR/fixtures/dispatcher-mode"
STUB_BIN="$TESTS_DIR/stubs/validate"

# The 2 images the fixture manifest declares, and the 1 directory it does not.
# Written as literals for the reason platform-policy.test.sh writes its own: a
# test that reads the set it checks out of the file under test agrees with a
# wrong set too, and the liveness clause below compares this array against what
# the library really parsed.
FIXTURE_IMAGES=("first" "second")
FIXTURE_OUTSIDER="outside"

# Every file the staged root takes from the fixture directory. Named one by one
# and not found by a glob: a glob that stopped matching would stage a root
# missing a devcontainer.json, and `validate` would go red for that instead —
# a false red on a rule this file says nothing about.
FIXTURE_IMAGE_FILES=("ctl.sh" "Dockerfile" "devcontainer.json" "project.json")
FIXTURE_ROOT_FILES=("images.yaml" "versions.env" "project.json")

# The REMEDY line the refusal prints, as a format. It is the needle every check
# below matches on, and it is the remedy rather than the diagnosis on purpose:
# `second/ctl.sh` on its own appears in the `shellcheck: second/ctl.sh` log line
# of every run, clean ones included, so a check written on the bare path would
# pass whatever the gate did.
#
# It is also the half of the message that a reader ACTS on. A gate that reports
# a mode and leaves the operator to work out that git records it, and that the
# sibling dispatchers are all 100755, has named a defect and not a fix.
REMEDY_FORMAT='chmod +x %s/ctl.sh'

# remedy_for <image name> — the exact text the refusal must carry for it.
function remedy_for() {
  # shellcheck disable=SC2059
  # The format is a CONSTANT declared above, and %s is the point of it.
  printf "$REMEDY_FORMAT" "$1"
}

VALIDATE_OUTPUT=""
VALIDATE_STATUS=0

# stage_image_tree — a repository root holding the real ctl.sh and _ctl/lib.sh
# over the 2-image fixture manifest, with every dispatcher EXECUTABLE.
#
# The modes are set here rather than carried in the fixtures' git index. Both
# would work, and this way the stimulus of each run is written in this file
# where a reader meets it, instead of in a mode they would have to run
# `git ls-files -s` to see.
function stage_image_tree() {
  local root name file
  root="$(mktemp -d)"
  mkdir -p "${root}/_ctl"
  cp "$REPO_ROOT/ctl.sh" "${root}/ctl.sh"
  cp "$REPO_ROOT/_ctl/lib.sh" "${root}/_ctl/lib.sh"
  # The gate hands this path to hadolint. The stub refuses a config that does
  # not exist, so the staged root carries the real one.
  cp "$REPO_ROOT/.hadolint.yaml" "${root}/.hadolint.yaml"
  for file in "${FIXTURE_ROOT_FILES[@]}"; do
    cp "${FIXTURES}/${file}" "${root}/${file}"
  done
  for name in "${FIXTURE_IMAGES[@]}"; do
    mkdir -p "${root}/${name}"
    for file in "${FIXTURE_IMAGE_FILES[@]}"; do
      cp "${FIXTURES}/${name}/${file}" "${root}/${name}/${file}"
    done
    chmod 755 "${root}/${name}/ctl.sh"
  done
  # The dispatcher-shaped file that is NOT an image, 100644 in every run.
  mkdir -p "${root}/${FIXTURE_OUTSIDER}"
  cp "${FIXTURES}/${FIXTURE_OUTSIDER}/ctl.sh" "${root}/${FIXTURE_OUTSIDER}/ctl.sh"
  chmod 644 "${root}/${FIXTURE_OUTSIDER}/ctl.sh"
  chmod 755 "${root}/ctl.sh"
  printf '%s' "$root"
}

# run_validate <staged root> — `bash ./ctl.sh validate` inside that root.
#
# stderr is folded into stdout because the refusal IS the answer: log_error
# writes to stderr, and a check that read stdout alone would be reading the
# progress log of a gate whose verdict it had thrown away.
function run_validate() {
  local root="$1"
  VALIDATE_STATUS=0
  VALIDATE_OUTPUT="$(cd "$root" && env \
    PATH="${STUB_BIN}:${PATH}" \
    PROJECT_ROOT="$root" \
    REPO_ROOT="$root" \
    bash ./ctl.sh validate 2>&1)" || VALIDATE_STATUS=$?
}

# staged_image_names <staged root> — the images the LIBRARY reads out of that
# root's manifest, which is the list cmd_validate walks.
#
# The shape run_order_guard in _ctl/tests/images-manifest.test.sh uses: no seam
# is added to the library for it, because a directory holding an images.yaml and
# a versions.env is the whole world image_names looks at.
function staged_image_names() {
  local root="$1" library_path
  library_path="$REPO_ROOT/_ctl/lib.sh"
  PROJECT_ROOT="$root" REPO_ROOT="$root" bash -c '
    source "$1"
    image_names
  ' probe "$library_path" 2>&1
}

# reported_images <output> — every image the refusal named, 1 per line, sorted.
# The count of these is what the liveness clause reads.
#
# THE STATUS IS READ EXPLICITLY, and NOT with `|| true`. grep exits 1 when it
# matches nothing, this file sets `set -Eeuo pipefail`, and the one-pipeline
# version of this function took the whole test file down inside its command
# substitution — measured on the break test, where deleting the rule from
# cmd_validate is exactly the condition that produces no match. 3 checks were
# reported, 2 never ran and test_summary never printed, so the file exited 1
# with no verdict on itself: the shape harness.sh exists to make impossible.
#
# Empty is an ANSWER here and not a failure. A gate that named no image is
# precisely what the liveness clause has to report. A status ABOVE 1 is a reader
# that broke, and it is passed on.
function reported_images() {
  local hits="" status=0
  hits="$(grep -oE 'chmod \+x [A-Za-z0-9_-]+/ctl\.sh' <<< "$1")" || status=$?
  if [[ "$status" -gt 1 ]]; then
    printf 'reported_images: grep exited %d reading the gate output\n' "$status" >&2
    return "$status"
  fi
  [[ -z "$hits" ]] && return 0
  sed -e 's#^chmod +x ##' -e 's#/ctl\.sh$##' <<< "$hits" | sort -u
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE FIXTURE TREE AND THE STUB ARE REALLY THERE
# ===========================================================================
# Every check below stages from these. An absent one would stage a root that
# fails `validate` for a reason this file says nothing about, and the refusal
# checks would then pass on the wrong red.
missing_fixtures=""
for name in "${FIXTURE_ROOT_FILES[@]}"; do
  [[ -f "${FIXTURES}/${name}" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${FIXTURES#"$REPO_ROOT"/}/${name}"
done
for name in "${FIXTURE_IMAGES[@]}"; do
  for file in "${FIXTURE_IMAGE_FILES[@]}"; do
    [[ -f "${FIXTURES}/${name}/${file}" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${FIXTURES#"$REPO_ROOT"/}/${name}/${file}"
  done
done
[[ -f "${FIXTURES}/${FIXTURE_OUTSIDER}/ctl.sh" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${FIXTURES#"$REPO_ROOT"/}/${FIXTURE_OUTSIDER}/ctl.sh"

if [[ -z "$missing_fixtures" ]]; then
  pass_check "the_fixture_repository_tree_is_present"
else
  fail_check "the_fixture_repository_tree_is_present" \
    "the staged root is built from these, and they are absent:" \
    "$missing_fixtures"
fi

if [[ -x "${STUB_BIN}/hadolint" ]]; then
  pass_check "the_hadolint_stub_is_executable"
else
  fail_check "the_hadolint_stub_is_executable" \
    "not executable: ${STUB_BIN}/hadolint" \
    "without it hadolint_resolve reaches for the host binary and then for docker, and this" \
    "file stops being hermetic on every machine whose hadolint is a point release off the pin"
fi

# ===========================================================================
# 2. THE STAGED ROOT IS THE 2-IMAGE MANIFEST THE LIBRARY READS
# ===========================================================================
# The liveness FOUNDATION. Sections 3 and 4 count what the gate reported and
# compare it against the image set; if the staged manifest were unreadable, or
# declared 1 image, or declared none, every one of those counts would agree with
# a rule that judged nothing.
staged_root="$(stage_image_tree)"

# The status is read rather than let errexit act on it: an unreadable staged
# manifest has to be REPORTED by the check below, and a file that died here
# would exit non-zero having printed no verdict about itself.
staged_names=""
staged_names_status=0
staged_names="$(staged_image_names "$staged_root")" || staged_names_status=$?

expected_names="$(printf '%s\n' "${FIXTURE_IMAGES[@]}")"
assert_equal "the_staged_manifest_declares_the_images_this_file_names" \
  "$expected_names" "$staged_names" \
  "image_names exited ${staged_names_status}" \
  "want is the FIXTURE_IMAGES literal of this file; got is what image_names read out of the" \
  "staged images.yaml — the same list cmd_validate walks" \
  "a manifest that parsed to nothing would make every count below agree with a rule that" \
  "visited no image at all"

image_total=0
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  image_total=$((image_total + 1))
done <<< "$staged_names"

if [[ "$image_total" -ge 2 ]]; then
  pass_check "the_staged_manifest_declares_more_than_one_image"
else
  fail_check "the_staged_manifest_declares_more_than_one_image" \
    "it declares ${image_total}" \
    "the property under test is a LOOP: a rule that judged the first image and stopped passes" \
    "every check a 1-image manifest can carry, and the next 100644 dispatcher is the second one"
fi

# ===========================================================================
# 3. THE COUNTER-STIMULUS, THROUGH THE REAL VERB
# ===========================================================================
# The clean half first, and it is the half a broken gate passes: a rule that
# refused every tree would satisfy section 3b while making the repository
# unvalidatable.
run_validate "$staged_root"
clean_status="$VALIDATE_STATUS"
clean_output="$VALIDATE_OUTPUT"

assert_equal "validate_accepts_a_tree_whose_dispatchers_are_all_executable" \
  "0" "$clean_status" \
  "every dispatcher of the staged root is 755 and the gate refused it anyway" \
  "it said:" "$clean_output"

assert_not_contains "a_clean_tree_is_not_reported_for_its_dispatcher_modes" \
  "$clean_output" "chmod +x " \
  "the remedy line must appear only where a dispatcher really is non-executable;" \
  "a gate that prints it on a clean tree teaches the reader that the message is noise"

# -- 3b. ONE non-executable dispatcher --
# The stimulus is exactly the shipped defect: a per-image ctl.sh committed 100644
# in a tree where every sibling is 100755.
chmod 644 "${staged_root}/second/ctl.sh"
run_validate "$staged_root"
broken_status="$VALIDATE_STATUS"
broken_output="$VALIDATE_OUTPUT"

assert_status_nonzero "validate_refuses_a_tree_holding_a_non_executable_dispatcher" \
  "$broken_status" \
  "second/ctl.sh is 100644 in the staged root and the gate returned OK" \
  "it said:" "$broken_output" \
  "image_ctl refuses that file, so every per-image verb of that image fails — and the verb" \
  "that finds out is verify-published, AFTER the push moved :latest"

assert_contains "the_refusal_names_the_file_and_the_chmod_that_fixes_it" \
  "$broken_output" "$(remedy_for second)" \
  "a gate that fails without naming the file sends the reader through 6 image directories" \
  "with ls, and without the remedy it leaves them to work out that git records the mode"

assert_not_contains "the_refusal_leaves_the_executable_dispatcher_alone" \
  "$broken_output" "$(remedy_for first)" \
  "first/ctl.sh is 755 in this run — a rule that reported it too would report every" \
  "dispatcher of the repository, and the message would stop meaning anything"

# ===========================================================================
# 4. THE RULE VISITS EVERY IMAGE THE MANIFEST DECLARES
# ===========================================================================
# The liveness clause, and the reason section 3b alone is not enough: a rule
# written over `${BUILD_ORDER[0]}` instead of over the loop would pass every
# check above, because `second` is not the first image of the manifest only by
# accident of which one this file chose to break.
#
# So BOTH dispatchers go 100644, and both must be named. The count is compared
# against the image total read in section 2, so a rule that judged 0 images
# fails here rather than reporting a tree it never opened.
chmod 644 "${staged_root}/first/ctl.sh"
run_validate "$staged_root"
every_output="$VALIDATE_OUTPUT"
every_status="$VALIDATE_STATUS"

assert_status_nonzero "validate_refuses_a_tree_whose_dispatchers_are_all_non_executable" \
  "$every_status" \
  "it said:" "$every_output"

reported="$(reported_images "$every_output")"
reported_total=0
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  reported_total=$((reported_total + 1))
done <<< "$reported"

assert_equal "the_rule_judged_every_image_the_manifest_declares" \
  "$image_total" "$reported_total" \
  "want is the number of images image_names read out of the staged manifest;" \
  "got is the number of distinct images the refusal named, and every one of them was 100644" \
  "the gate output was:" "$every_output" \
  "0 here is the failure this clause exists for: a rule that visited no image reports a clean" \
  "tree, and the reader believes it"

assert_equal "the_rule_named_each_of_them" \
  "$expected_names" "$reported" \
  "want is the FIXTURE_IMAGES literal; got is what the refusal named" \
  "the gate output was:" "$every_output"

# ===========================================================================
# 5. THE RULE IS DERIVED FROM THE MANIFEST, NOT FROM A GLOB
# ===========================================================================
# `outside/ctl.sh` is 100644 in every run above, including the one that reported
# both real images. It is dispatcher-SHAPED and it is not an image, so the gate
# must be silent about it — the property .claude/rules/00-identity.md states,
# and the reason _ctl/tests/fixtures/no-platform-list/ctl.sh may exist at all.
#
# Rewrite the rule as a `*/ctl.sh` glob and every check above stays green while
# the gate starts failing on every dispatcher-shaped fixture in the tree.
assert_not_contains "a_dispatcher_shaped_file_outside_the_manifest_is_not_held" \
  "$every_output" "$(remedy_for "$FIXTURE_OUTSIDER")" \
  "${FIXTURE_OUTSIDER}/ctl.sh is 100644 in this run and the manifest does not declare it" \
  "the check derives its list from images.yaml like every other loop in cmd_validate, so a" \
  "directory that is not an image of the manifest is not held to it"

rm -rf "$staged_root"

# ===========================================================================
# 6. EVERY DISPATCHER OF THIS REPOSITORY IS EXECUTABLE
# ===========================================================================
# The tree itself, read the way `validate` reads it. Sections 3 to 5 hold the
# GATE and would stay green over a repository whose hardware/ctl.sh went back to
# 100644 tomorrow; this is what goes red on that commit, in `ctl.sh test`, with
# no shellcheck, no jq and no linter in the way.
real_names=""
real_names_status=0
real_names="$(image_names)" || real_names_status=$?

if [[ "$real_names_status" -eq 0 && -n "$real_names" ]]; then
  pass_check "the_repository_manifest_names_its_images"
else
  fail_check "the_repository_manifest_names_its_images" \
    "image_names exited ${real_names_status} and printed:" "${real_names:-<nothing>}" \
    "with no list to walk, the per-image checks below would run 0 times and this file would" \
    "report a repository whose dispatchers it never opened"
fi

real_total=0
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  real_total=$((real_total + 1))
  if [[ -x "${REPO_ROOT}/${name}/ctl.sh" ]]; then
    pass_check "${name}_ctl_sh_is_executable"
  else
    fail_check "${name}_ctl_sh_is_executable" \
      "not executable: ${name}/ctl.sh" \
      "$(remedy_for "$name") — git records the mode, and the sibling dispatchers are all 100755" \
      "image_ctl refuses it, so every per-image verb of ${name} fails; the verb that finds out" \
      "is verify-published, and it runs after the push has already moved :latest"
  fi
done <<< "$real_names"

if [[ "$real_total" -ge 2 ]]; then
  pass_check "the_dispatcher_check_visited_more_than_one_image"
else
  fail_check "the_dispatcher_check_visited_more_than_one_image" \
    "it visited ${real_total}" \
    "a loop that ran once, or not at all, reports a clean repository having opened nothing"
fi

test_summary "$TEST_NAME"
