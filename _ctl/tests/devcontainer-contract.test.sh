#!/usr/bin/env bash
#
# _ctl/tests/devcontainer-contract.test.sh — the image set and the devcontainer
# set are ONE set, and every devcontainer.json opens the image of the directory
# it sits in.
#
# Static means static: this file reads files and runs `ctl.sh validate` inside a
# staged repository root of copies. It starts no container, it calls no daemon
# and it reaches no network, so it runs identically on a laptop and on a CI
# runner — and it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE PROPERTY
# ============================================================================
#
# The local/CI 1:1 workflow rests on 1 sentence: a developer opens the SAME
# published image that CI runs. `devcontainer.json` is the only file that
# carries that sentence to VS Code, and until this pass 2 ways of breaking it
# were invisible to every verb in this repository:
#
#   G1  an image of images.yaml with NO devcontainer.json. Nothing refuses it.
#       check_devcontainer_json globs */devcontainer.json and holds each file it
#       FINDS to 3 properties, so an image that ships without one is an image
#       nobody can open locally, and the gate reports OK — it only fails when
#       the glob matches NOTHING at all. The image set would then be 6 and the
#       devcontainer set 5, with no reader able to say so. The other direction
#       is the same defect wearing a different hat: a devcontainer.json in a
#       directory that no image declares is a file pointing at an image the
#       repository does not publish. `runner/` sat retired on disk for months,
#       and a devcontainer.json added to it would have been read by nothing.
#
#   G2  a devcontainer.json whose .image names ANOTHER image of this
#       repository. `ghcr.io/gophersys/second:latest` inside first/ matches the
#       shape rule exactly — `^ghcr\.io/gophersys/[a-z-]+:latest$` — so today it
#       passes. The developer then gets a container the CI job of that directory
#       never runs, silently, and every version they read is the wrong image's.
#
# Both are SET rules, and neither can be answered by reading 1 file. That is why
# they live beside images.yaml and not inside a JSON schema.
#
# ============================================================================
# WHY THE VERB, AND WHY A STAGED ROOT
# ============================================================================
#
# The shape is _ctl/tests/dispatcher-mode.test.sh's, deliberately, and for its
# stated reason: the rule is a handful of lines INSIDE cmd_validate's
# check_devcontainer_json, so there is nothing to call in isolation, and adding
# a seam would be a change to a non-test file. The whole verb is run instead, in
# a mktemp root holding a 2-image manifest and the small tree that manifest
# describes. A check written against a helper would still be green on the day
# the helper stopped being called.
#
# `validate` reaches for 4 tools, and 3 of them are real here. shellcheck and jq
# it refuses to run without, and yq answers the manifest — the position
# _ctl/tests/images-manifest.test.sh already takes, where a missing parser is a
# FAILURE and never a skip. hadolint is the 4th and is STUBBED, because it is
# the 1 tool whose resolution can leave the machine.
# _ctl/tests/stubs/validate/hadolint carries the reason.
#
# The staged tree is COPIES and never symlinks: nothing here writes to the
# repository, and a staging helper that can reach the real tree is 1 edit away
# from one that does. Each stimulus gets its OWN root, rather than accumulating
# on one, so that the "the refusal must NOT name the healthy image" clauses read
# a tree with exactly 1 defect in it.
#
# ============================================================================
# WHAT THIS FILE DOES NOT PROVE
# ============================================================================
#
# That the image a devcontainer.json names EXISTS in the registry. That is
# `verify-published`, it needs the network, and it is a different rule.
#
# That the platform a Mac pulls is the arm64 variant. devcontainer.json declares
# no platform, and pinning one there is out of scope for this pass — the
# arm64-local exception is held in _ctl/tests/platform-policy.test.sh instead,
# against the table that says which images have an arm64 variant at all.
#
# Usage: bash _ctl/tests/devcontainer-contract.test.sh
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

TEST_NAME="devcontainer-contract.test.sh"

FIXTURES="$TESTS_DIR/fixtures/devcontainer-contract"
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
# missing a Dockerfile, and `validate` would go red for that instead — a false
# red on a rule this file says nothing about.
FIXTURE_IMAGE_FILES=("ctl.sh" "Dockerfile" "devcontainer.json" "project.json")
FIXTURE_ROOT_FILES=("images.yaml" "versions.env" "project.json")

# The 2 stimulus files. Each is a COMPLETE, correct devcontainer.json in every
# property except the 1 under test, so the refusal it produces can only be the
# new rule firing.
STIMULUS_NAMES_ANOTHER_IMAGE="$FIXTURES/stimuli/first-names-second.json"
STIMULUS_UNDECLARED="$FIXTURES/stimuli/undeclared-outside.json"

# The image ref a devcontainer.json of <name> must open. The contract in 1
# format string: the published ref, at :latest, of the directory the file sits
# in. .claude/rules/00-identity.md states it, ctl.sh enforces the SHAPE of it
# today, and the `%s` is the half nothing enforces yet.
IMAGE_REF_FORMAT='ghcr.io/gophersys/%s:latest'

# ============================================================================
# THE 3 REFUSAL FORMATS, AND WHY THEY ARE SPELLED OUT HERE
# ============================================================================
#
# These are the needles every check below matches on, and each one is written as
# the FULL message rather than as the image name alone. The reason is the one
# dispatcher-mode.test.sh gives about its own remedy line: `second` on its own
# appears in `shellcheck: second/ctl.sh` and in `jq parse: second/project.json`
# in every run, clean ones included, and `second/devcontainer.json` appears in
# the `devcontainer: second/devcontainer.json` progress line of every run that
# finds the file. A check written on the bare path would pass whatever the gate
# did.
#
# They are also what a reader ACTS on. A gate that reports "invalid" and leaves
# the operator to work out WHICH image, and whether the fix is a new file or an
# edited ref, has named a defect and not a fix.
ABSENT_FORMAT='%s/devcontainer.json: absent'
UNDECLARED_FORMAT='%s/devcontainer.json: no such image in images.yaml'
SELF_REFERENCE_FORMAT="%s/devcontainer.json: .image is '%s' — must be '%s'"

# image_ref <name> — the published ref of that image.
function image_ref() {
  # shellcheck disable=SC2059
  # The format is a CONSTANT declared above, and %s is the point of it.
  printf "$IMAGE_REF_FORMAT" "$1"
}

# absent_message <name> — what the refusal must say about an image of the
# manifest with no devcontainer.json.
function absent_message() {
  # shellcheck disable=SC2059
  printf "$ABSENT_FORMAT" "$1"
}

# undeclared_message <directory> — what the refusal must say about a
# devcontainer.json that no image of the manifest declares.
function undeclared_message() {
  # shellcheck disable=SC2059
  printf "$UNDECLARED_FORMAT" "$1"
}

# self_reference_message <directory> <named image> — what the refusal must say
# about a devcontainer.json that opens another image's ref.
function self_reference_message() {
  # shellcheck disable=SC2059
  printf "$SELF_REFERENCE_FORMAT" "$1" "$(image_ref "$2")" "$(image_ref "$1")"
}

VALIDATE_OUTPUT=""
VALIDATE_STATUS=0

# stage_image_tree — a repository root holding the real ctl.sh and _ctl/lib.sh
# over the 2-image fixture manifest, complete and CORRECT. Every stimulus below
# is a departure this file makes from the root this function returns, so the
# stimulus of each run is written where a reader meets it.
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
    # 755 in every run of this file. The mode is dispatcher-mode.test.sh's
    # subject, and a 100644 here would make every refusal below carry a second
    # diagnosis that this file's checks would then be reading.
    chmod 755 "${root}/${name}/ctl.sh"
  done
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

# devcontainer_directories <root> — the directory name of every
# */devcontainer.json under that root, 1 per line, sorted.
#
# It is written HERE rather than taken from devcontainer_files in ctl.sh on
# purpose: a test that reads the implementation's own reader agrees with a
# reader that has stopped matching, which is the exact failure the set equality
# below exists to catch.
function devcontainer_directories() {
  local root="$1" path name out=""
  for path in "$root"/*/devcontainer.json; do
    [[ -f "$path" ]] || continue
    name="${path%/devcontainer.json}"
    name="${name##*/}"
    out="${out:+${out}
}${name}"
  done
  [[ -z "$out" ]] && return 0
  sort <<< "$out"
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
for name in "$STIMULUS_NAMES_ANOTHER_IMAGE" "$STIMULUS_UNDECLARED"; do
  [[ -f "$name" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${name#"$REPO_ROOT"/}"
done

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
# The liveness FOUNDATION. Every stimulus below is an edit to the relationship
# between this manifest and the devcontainer.json files beside it; a manifest
# that parsed to nothing would make each of those edits a no-op, and every
# refusal check would then be reading a gate that visited no image.
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
  "a manifest that parsed to nothing would make every stimulus below a no-op"

assert_equal "the_staged_root_carries_a_devcontainer_json_for_each_of_them" \
  "$(printf '%s\n' "${FIXTURE_IMAGES[@]}" | sort)" \
  "$(devcontainer_directories "$staged_root")" \
  "the staged root is the CORRECT tree that every stimulus departs from, so it must satisfy" \
  "the set equality itself — otherwise the clean run below is red before this file touches it"

# ===========================================================================
# 3. THE COUNTER-STIMULUS, THROUGH THE REAL VERB
# ===========================================================================
# The clean half first, and it is the half a broken gate passes: a rule that
# refused every tree would satisfy sections 4 to 6 while making the repository
# unvalidatable.
run_validate "$staged_root"
clean_status="$VALIDATE_STATUS"
clean_output="$VALIDATE_OUTPUT"

assert_equal "validate_accepts_a_tree_whose_manifest_and_devcontainer_sets_agree" \
  "0" "$clean_status" \
  "every image of the staged manifest has a devcontainer.json naming its own ref," \
  "and the gate refused it anyway; it said:" "$clean_output"

assert_not_contains "a_clean_tree_reports_no_absent_devcontainer_json" \
  "$clean_output" "$(absent_message second)" \
  "the refusal must appear only where an image really has no devcontainer.json;" \
  "a gate that prints it on a clean tree teaches the reader that the message is noise"

rm -rf "$staged_root"

# ===========================================================================
# 4. G1 — AN IMAGE OF THE MANIFEST WITH NO devcontainer.json
# ===========================================================================
# The stimulus is the first direction of the set equality: images.yaml declares
# `second`, and the file a developer would open it with is not there. Today
# check_devcontainer_json globs the files that EXIST, so the tree below is a
# tree the gate reports OK about — an image nobody can open locally, published
# green.
staged_root="$(stage_image_tree)"
rm -f "${staged_root}/second/devcontainer.json"
run_validate "$staged_root"
absent_status="$VALIDATE_STATUS"
absent_output="$VALIDATE_OUTPUT"
rm -rf "$staged_root"

assert_status_nonzero "every_manifest_image_has_a_devcontainer_json" \
  "$absent_status" \
  "images.yaml declares 'second' and second/devcontainer.json is not in the staged root," \
  "and the gate returned OK; it said:" "$absent_output" \
  "the image set and the devcontainer set are ONE set — an image with no devcontainer.json" \
  "is an image a developer cannot open, and the 1:1 workflow is the claim that they can"

assert_contains "the_missing_devcontainer_refusal_names_the_image" \
  "$absent_output" "$(absent_message second)" \
  "a gate that fails without naming the image sends the reader through 6 directories with ls" \
  "the bare name would not do: 'second' is in the shellcheck and jq lines of every run"

assert_not_contains "the_missing_devcontainer_refusal_leaves_the_healthy_image_alone" \
  "$absent_output" "$(absent_message first)" \
  "first/devcontainer.json IS in this staged root — a rule that named it too would name every" \
  "image of the repository, and the message would stop meaning anything"

# ===========================================================================
# 5. G1, THE OTHER DIRECTION — A devcontainer.json NO IMAGE DECLARES
# ===========================================================================
# Set equality owes both directions. This root holds a COMPLETE and correct
# outside/devcontainer.json — it parses, it names its own directory's ref, it
# carries the dev user and /workspace — and images.yaml declares `first` and
# `second` and nothing else. So the only thing wrong with it is that it points
# at an image this repository does not publish.
#
# Without this direction the rule could be written as "every image has a file"
# and stay green over a directory left behind by a deleted image, which is
# exactly what `runner/` was for months.
staged_root="$(stage_image_tree)"
mkdir -p "${staged_root}/${FIXTURE_OUTSIDER}"
cp "$STIMULUS_UNDECLARED" "${staged_root}/${FIXTURE_OUTSIDER}/devcontainer.json"
run_validate "$staged_root"
undeclared_status="$VALIDATE_STATUS"
undeclared_output="$VALIDATE_OUTPUT"
rm -rf "$staged_root"

assert_status_nonzero "a_devcontainer_json_that_no_image_declares_is_refused" \
  "$undeclared_status" \
  "${FIXTURE_OUTSIDER}/devcontainer.json is in the staged root and images.yaml declares no" \
  "such image, and the gate returned OK; it said:" "$undeclared_output" \
  "a devcontainer.json is a promise that ghcr.io holds that ref; for a directory no image" \
  "declares, nothing in this repository ever builds or pushes it"

assert_contains "the_undeclared_devcontainer_refusal_names_the_directory" \
  "$undeclared_output" "$(undeclared_message "$FIXTURE_OUTSIDER")" \
  "the remedy is either an images.yaml entry or a deleted directory, and the reader cannot" \
  "choose between them without being told which directory the gate is talking about"

# ===========================================================================
# 6. G2 — A devcontainer.json THAT OPENS ANOTHER IMAGE
# ===========================================================================
# first/devcontainer.json naming ghcr.io/gophersys/second:latest. It matches the
# shape rule `^ghcr\.io/gophersys/[a-z-]+:latest$` exactly, which is why the gate
# passes it today, and it is the failure the 1:1 claim cannot survive: the
# developer opens a container that the CI job of that directory never runs, and
# every version they read belongs to another image.
staged_root="$(stage_image_tree)"
cp "$STIMULUS_NAMES_ANOTHER_IMAGE" "${staged_root}/first/devcontainer.json"
run_validate "$staged_root"
cross_status="$VALIDATE_STATUS"
cross_output="$VALIDATE_OUTPUT"
rm -rf "$staged_root"

assert_status_nonzero "a_devcontainer_json_that_names_another_image_is_refused" \
  "$cross_status" \
  "first/devcontainer.json opens $(image_ref second) and the gate returned OK; it said:" \
  "$cross_output" \
  "the shape rule passes it — it is a well-formed ref of this repository — so only a" \
  "SELF-reference rule can tell this file from a correct one"

assert_contains "the_self_reference_refusal_names_the_file_the_wrong_ref_and_the_right_one" \
  "$cross_output" "$(self_reference_message first second)" \
  "both refs belong to this repository, so a message naming 1 of them leaves the reader to" \
  "work out which direction the mistake goes in"

# ===========================================================================
# 7. THE COUNTER-STIMULUS ON THE REAL TREE
# ===========================================================================
# Sections 3 to 6 hold the GATE, and every one of them would stay green over a
# repository whose ui/devcontainer.json started opening cloud's image tomorrow.
# This is what goes red on that commit, in `ctl.sh test`, with no shellcheck, no
# jq and no linter in the way — and it is the check that must PASS on the
# unmodified tree today, because the properties above are not new rules about
# how this repository is meant to look. They are rules it already satisfies and
# nothing was holding.
manifest_status=0
manifest_names=""
manifest_names="$(manifest_yq '.images | keys | .[]' 2>&1)" || manifest_status=$?

# The liveness clause first, because the equality below reads this value: an
# unreadable manifest would compare the devcontainer set against an empty one
# and report the WRONG defect — 6 files naming no image — while the real fault
# is that nothing could open images.yaml.
if [[ "$manifest_status" -eq 0 && -n "$manifest_names" ]]; then
  pass_check "the_repository_manifest_is_readable"
else
  fail_check "the_repository_manifest_is_readable" \
    "reading the image keys of ${IMAGES_MANIFEST} exited ${manifest_status}" \
    "it printed:" "${manifest_names:-<nothing>}" \
    "the manifest is the ONE declaration of the image set, so the equality below cannot be" \
    "answered without it — and an empty set would agree with a repository that has no images"
fi

if [[ "$manifest_status" -ne 0 || -z "$manifest_names" ]]; then
  fail_check "counter_stimulus_the_unmodified_tree_passes" \
    "unreadable: ${IMAGES_MANIFEST}"
else
  assert_equal "counter_stimulus_the_unmodified_tree_passes" \
    "$(sort <<< "$manifest_names")" \
    "$(devcontainer_directories "$REPO_ROOT")" \
    "want is every image key of ${IMAGES_MANIFEST}; got is every directory of this repository" \
    "holding a devcontainer.json" \
    "an image with no devcontainer.json cannot be opened locally, and a devcontainer.json" \
    "that no image declares points at a ref nothing here builds"

  real_total=0
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    real_total=$((real_total + 1))
    file="${REPO_ROOT}/${name}/devcontainer.json"
    if [[ ! -f "$file" ]]; then
      # The set equality above already reports this. Naming it again per image
      # would print the same defect twice and say nothing new.
      continue
    fi
    declared=""
    jq_status=0
    declared="$(jq -r '.image // empty' "$file" 2>&1)" || jq_status=$?
    if [[ "$jq_status" -ne 0 ]]; then
      fail_check "counter_stimulus_${name}_devcontainer_json_names_its_own_image" \
        "jq exited ${jq_status} reading ${name}/devcontainer.json" \
        "it printed:" "${declared:-<nothing>}"
      continue
    fi
    assert_equal "counter_stimulus_${name}_devcontainer_json_names_its_own_image" \
      "$(image_ref "$name")" "$declared" \
      "the file a developer opens ${name} with must open ${name}, at :latest — the published" \
      "tag CI runs; a ref belonging to a sibling image is a local environment that no CI job" \
      "of this directory has ever run"
  done <<< "$manifest_names"

  if [[ "$real_total" -ge 2 ]]; then
    pass_check "the_self_reference_check_visited_more_than_one_image"
  else
    fail_check "the_self_reference_check_visited_more_than_one_image" \
      "it visited ${real_total}" \
      "a loop that ran once, or not at all, reports a clean repository having opened nothing"
  fi
fi

test_summary "$TEST_NAME"
