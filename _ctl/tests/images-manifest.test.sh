#!/usr/bin/env bash
#
# _ctl/tests/images-manifest.test.sh — the manifest parses, its order is a build
# order, and the generator that reads it is idempotent.
#
# Static means static: this file reads files and runs 2 shell scripts. It starts
# no container, it calls no daemon and it reaches no network, so it runs
# identically on a laptop and on a CI runner. The YAML parser is the 1 tool it
# needs, and a missing parser is a FAILURE here and never a skip.
#
# ============================================================================
# WHAT THIS FILE EXISTS FOR
# ============================================================================
#
# images.yaml replaced 6 hand-kept declarations of the image graph, and the
# tests that held those 6 to each other went with them. What replaced them was
# 1 file that everything DERIVES from — BUILD_ORDER in both control scripts, the
# input path table in .ci/affected.sh, the check groups in .ci/smoke.sh, the 5
# publish jobs and the nightly scan matrix through _ctl/generate.sh.
#
# A single source of truth moves the failure mode rather than deleting it. The
# 6 copies could drift; 1 file cannot drift from itself. What it CAN do is:
#
#   1. stop parsing, at which point every derived home fails at once — loudly,
#      which is the good case, and this file pins the parse anyway because a
#      manifest that stopped parsing must fail HERE, in the pull request gate,
#      and not in the publish job;
#   2. put a child above its parent. Document order IS build order, so that
#      emits a workflow whose job builds a layer FROM a `:<sha>` tag no job of
#      that run pushed. The failure is on main, after the merge, and the file
#      that caused it looks fine;
#   3. drift from what the generator last wrote. A hand edit to
#      .ci/providers/github/build-and-push.yml survives until somebody runs the
#      generator again, and it is then silently deleted — the generated file
#      reads like a file a human may edit, because nothing says otherwise.
#
# .claude/rules/00-identity.md names 1 and 2 as the replacement for the
# BUILD_ORDER-agreement step of validate.yml, which greps `^BUILD_ORDER=(...)`
# out of both control scripts and compares 2 strings that are both `BUILD_ORDER=()`
# today: a step that cannot fail. This file is what that step becomes.
#
# The set EQUALITY half — the manifest declares exactly the images the policy
# literal names — lives in _ctl/tests/publish-order.test.sh, beside the workflow
# job set it is compared against. It is deliberately not repeated here: 2 homes
# for 1 literal is the drift this manifest exists to end.
#
# ============================================================================
# THE GUARD IS WATCHED FIRING, ON A FIXTURE, IN BOTH DIRECTIONS
# ============================================================================
#
# The ordering rule is enforced by image_names in _ctl/lib.sh, and a guard whose
# refusal nobody has watched is a guard nobody can say fires. So it is fed 2
# fixture manifests, and both verdicts are asserted: the one that writes a child
# above its parent must be REFUSED with both names in the message, and the one
# that writes the parent first must be ACCEPTED. Without the second half a guard
# stuck on "refuse everything" passes the first.
#
# Neither fixture is a copy of the real manifest. A fixture that tracked the
# real image set would need an edit every time an image is added, and it would
# then be testing the set instead of the rule.
#
# Usage: bash _ctl/tests/images-manifest.test.sh
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

TEST_NAME="images-manifest.test.sh"

LIBRARY="_ctl/lib.sh"
GENERATOR="_ctl/generate.sh"
PROVIDER_DIRECTORY=".ci/providers/github"

# The guest script, and the function in it that dispatches a check group name.
# The manifest's `groups` field is a list of keys into that case statement, and
# nothing else in this repository resolves them at gate time.
GUEST_SCRIPT=".ci/image-checks.sh"
GUEST_GROUP_FUNCTION="run_functional_groups"

# The 2 files the generator declares it writes, and the 1 file of that directory
# it must leave alone. weekly-bumps.yml is hand-written and is the check that
# "it writes 2 things" is a fact and not a sentence in a header.
GENERATED_FILES=(
  "build-and-push.yml"
  "security-nightly.yml"
)
UNGENERATED_FILES=(
  "weekly-bumps.yml"
)

FIXTURES="$TESTS_DIR/fixtures/images-manifest"
FIXTURE_BAD_ORDER="$FIXTURES/child-above-parent.yaml"
FIXTURE_GOOD_ORDER="$FIXTURES/parent-above-child.yaml"

# The 2 images the fixtures use. The refusal has to NAME both — a guard that
# fails with "invalid manifest" sends the reader back to read the file by hand.
FIXTURE_PARENT="base"
FIXTURE_CHILD="flutter"

# ---------------------------------------------------------------------------
# The probes.
# ---------------------------------------------------------------------------

# GUARD_OUTPUT / GUARD_STATUS — set by the probe below, the way
# read_build_order in publish-order.test.sh publishes its results.
GUARD_OUTPUT=""
GUARD_STATUS=0

# run_order_guard <manifest path> — source _ctl/lib.sh against a repository root
# whose images.yaml is that file, and ask it for the image names.
#
# No seam is added to the library for this, and none is needed: manifest_yq
# reads "${REPO_ROOT}/images.yaml", so a directory holding that name and a
# versions.env is the whole world the reader looks at. The staged root is a
# directory of COPIES rather than symlinks — nothing here writes, but a staging
# helper that can reach the real tree is 1 edit away from one that does.
#
# stderr is folded into stdout because the refusal is the answer: a guard that
# refused and said nothing readable is a guard this check must fail on.
function run_order_guard() {
  local manifest="$1"
  local root library_path
  # Resolved BEFORE the assignment prefix below, and not inside its argument
  # list: the prefix rebinds REPO_ROOT for the forked shell only, so a
  # "$REPO_ROOT/..." written there would still expand to THIS shell's value.
  # It happens to be the value wanted — the real library — and that is exactly
  # why it must not be written that way. shellcheck says so as SC2097/SC2098,
  # and a reader has no way to tell the intent from the accident.
  library_path="$REPO_ROOT/$LIBRARY"
  root="$(mktemp -d)"
  cp "$manifest" "${root}/images.yaml"
  cp "$REPO_ROOT/versions.env" "${root}/versions.env"
  GUARD_STATUS=0
  GUARD_OUTPUT="$(PROJECT_ROOT="$root" REPO_ROOT="$root" bash -c '
    source "$1"
    image_names
  ' probe "$library_path" 2>&1)" || GUARD_STATUS=$?
  rm -rf "$root"
}

# stage_generator_root — a repository root holding ONLY what _ctl/generate.sh
# says it reads and writes, in real copies.
#
# The narrowness is a check in itself. The generator's header claims it reads
# nothing outside images.yaml and _ctl/lib.sh; a staged root that holds nothing
# else makes that claim testable, because a generator that reached for a 3rd
# file would fail here naming it.
#
# COPIES and not symlinks, for 1 reason: this function's output is a directory
# the generator WRITES INTO. A symlinked .ci/ would send both runs into the real
# provider files, and the idempotence check would then be comparing the
# repository against itself while quietly editing it.
function stage_generator_root() {
  local root name
  root="$(mktemp -d)"
  mkdir -p "${root}/_ctl" "${root}/${PROVIDER_DIRECTORY}"
  cp "$REPO_ROOT/$LIBRARY" "${root}/_ctl/lib.sh"
  cp "$REPO_ROOT/$GENERATOR" "${root}/_ctl/generate.sh"
  cp "$REPO_ROOT/images.yaml" "${root}/images.yaml"
  cp "$REPO_ROOT/versions.env" "${root}/versions.env"
  for name in "${GENERATED_FILES[@]}" "${UNGENERATED_FILES[@]}"; do
    cp "$REPO_ROOT/${PROVIDER_DIRECTORY}/${name}" "${root}/${PROVIDER_DIRECTORY}/${name}"
  done
  printf '%s' "$root"
}

# guest_group_labels — the check group names .ci/image-checks.sh implements, 1
# per line, `*` excluded.
#
# A case-arm reader of exactly this shape was DELETED from
# _ctl/tests/publish-order.test.sh in the same change that added this file,
# because the 2 tables it read — image_own_paths in .ci/affected.sh and
# image_check_groups in .ci/smoke.sh — became manifest fields. This third table
# did not move: the group names are keys into a case statement in the GUEST
# script, which runs inside the container and is not derived from anything. So
# the reader reappears here, over the 1 table that is still a case statement.
function guest_group_labels() {
  awk -v want="$GUEST_GROUP_FUNCTION" '
    $0 == "function " want "() {" { inside = 1; next }
    inside && /^}/ { exit }
    inside {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      if (line ~ /^#/) { next }
      if (line !~ /\)/) { next }
      label = line
      sub(/\).*$/, "", label)
      if (label == "*") { next }
      # An arm label is a name or a `|` alternation of names. Anything else is a
      # line this reader does not understand, and the liveness clause below is
      # what turns "understood nothing" into a failure.
      if (label ~ /[^A-Za-z0-9_.|-]/) { next }
      total = split(label, parts, "|")
      for (item = 1; item <= total; item++) {
        if (parts[item] != "") { print parts[item] }
      }
    }
  ' "$1"
}

# GENERATE_OUTPUT / GENERATE_STATUS — set by the runner below.
GENERATE_OUTPUT=""
GENERATE_STATUS=0

# run_generator <staged root> — 1 generator run inside a staged tree.
function run_generator() {
  local root="$1"
  GENERATE_STATUS=0
  GENERATE_OUTPUT="$(bash "${root}/_ctl/generate.sh" 2>&1)" || GENERATE_STATUS=$?
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE MANIFEST PARSES, AND IT DECLARES A GRAPH
# ===========================================================================
# The expression is written here and the RESOLUTION comes from manifest_yq in
# _ctl/lib.sh — yq 4.x on PATH, else mikefarah/yq at the versions.env pin
# through docker, else a failure naming the tool. A second resolver written into
# this file would be the duplication that library function exists to end, and it
# would be the copy that never learns the container route.
#
# The accessors are NOT used to answer this section. image_names holds the
# ordering rule, so asking it whether the order is valid is asking the
# implementation to grade itself; the records below come out of the document.
records_status=0
records=""
records="$(manifest_yq '.images | to_entries | .[] |
  [.key, .value.parent] | join("|")' 2>&1)" || records_status=$?

if [[ "$records_status" -eq 0 && -n "$records" ]]; then
  pass_check "the_image_manifest_parses"
else
  fail_check "the_image_manifest_parses" \
    "reading ${IMAGES_MANIFEST} exited ${records_status}" \
    "it printed:" "${records:-<nothing>}" \
    "every mechanical home in this repository is derived from this file, so a manifest that" \
    "stopped parsing takes BUILD_ORDER, the input path table, the check groups, the 5 publish" \
    "jobs and the nightly matrix with it — and it must fail here, in the gate, not on main"
fi

if [[ "$records_status" -ne 0 || -z "$records" ]]; then
  fail_check "the_manifest_declares_at_least_one_parent_edge" \
    "unreadable: ${IMAGES_MANIFEST}"
  fail_check "document_order_is_a_valid_build_order" \
    "unreadable: ${IMAGES_MANIFEST}"
else
  # THE LIVENESS CLAUSE for the rule below. A manifest in which no image
  # declares a parent satisfies a topological check trivially — every image is a
  # root — so the rule would be green over a graph with no edges in it at all,
  # including one that lost its edges to a bad edit.
  edges="$(awk -F'|' '$2 != "" { print }' <<< "$records")"
  edge_total="$(grep -c . <<< "$edges")" || edge_total=0
  if [[ "$edge_total" -ge 1 ]]; then
    pass_check "the_manifest_declares_at_least_one_parent_edge"
  else
    fail_check "the_manifest_declares_at_least_one_parent_edge" \
      "no image of ${IMAGES_MANIFEST} declares a parent" \
      "the records read were:" "$(tr '\n' ' ' <<< "$records")" \
      "either every image FROMs ubuntu now — which is a change to the image architecture and" \
      "not a manifest edit — or the parent field stopped being read, and the ordering rule" \
      "below would then pass over a graph with no edges"
  fi

  # -- the rule: every parent appears ABOVE its children --
  # Document order IS build order. This walks the records in that order and
  # keeps the names already seen, which is the same property image_names holds
  # and is deliberately computed here a second time, from the document.
  seen_names=""
  order_defects=""
  while IFS='|' read -r name parent; do
    [[ -z "$name" ]] && continue
    if [[ -n "$parent" ]]; then
      if ! grep -qxF -- "$parent" <<< "$seen_names"; then
        order_defects="${order_defects:+${order_defects}
}'${name}' is written above its parent '${parent}'"
      fi
    fi
    seen_names="${seen_names:+${seen_names}
}${name}"
  done <<< "$records"

  if [[ -z "$order_defects" ]]; then
    pass_check "document_order_is_a_valid_build_order"
  else
    fail_check "document_order_is_a_valid_build_order" \
      "${IMAGES_MANIFEST} — document order IS build order:" \
      "$order_defects" \
      "the order read was: $(cut -d'|' -f1 <<< "$records" | tr '\n' ' ')" \
      "a child above its parent emits a job that builds FROM a :<sha> tag no job of that run" \
      "pushed, and the failure lands on main after the merge"
  fi
fi

# ===========================================================================
# 2. THE COUNTER-STIMULUS: THE ORDER GUARD FIRES, AND IT STAYS QUIET
# ===========================================================================
# Section 1 reads the real manifest and the real manifest is correct, so on its
# own it is a rule nobody has seen fail. These 2 fixtures are what make the
# guard in _ctl/lib.sh an observed behaviour rather than a claim.
missing_fixtures=""
for fixture in "$FIXTURE_BAD_ORDER" "$FIXTURE_GOOD_ORDER"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_the_order_fixtures_exist" \
    "the fixtures this test proves the guard with are absent:" \
    "$missing_fixtures"
  fail_check "counter_stimulus_the_guard_refuses_a_child_above_its_parent" \
    "no fixture to feed it"
  fail_check "counter_stimulus_the_guard_accepts_a_parent_above_its_child" \
    "no fixture to feed it"
else
  pass_check "counter_stimulus_the_order_fixtures_exist"

  run_order_guard "$FIXTURE_BAD_ORDER"
  if [[ "$GUARD_STATUS" -eq 0 ]]; then
    fail_check "counter_stimulus_the_guard_refuses_a_child_above_its_parent" \
      "want: a non-zero exit status on ${FIXTURE_BAD_ORDER#"$REPO_ROOT"/}" \
      "got:  0, with output:" "${GUARD_OUTPUT:-<nothing>}" \
      "that fixture holds the exact defect the guard exists for — a child written above its" \
      "parent — so a reader quiet on it is quiet on the real manifest too"
  elif ! grep -qF -- "$FIXTURE_CHILD" <<< "$GUARD_OUTPUT"; then
    fail_check "counter_stimulus_the_guard_refuses_a_child_above_its_parent" \
      "it exited ${GUARD_STATUS} and its message never names the misplaced image '${FIXTURE_CHILD}'" \
      "it said:" "${GUARD_OUTPUT:-<nothing>}"
  elif ! grep -qF -- "$FIXTURE_PARENT" <<< "$GUARD_OUTPUT"; then
    fail_check "counter_stimulus_the_guard_refuses_a_child_above_its_parent" \
      "it exited ${GUARD_STATUS} and its message never names the parent '${FIXTURE_PARENT}'" \
      "it said:" "${GUARD_OUTPUT:-<nothing>}" \
      "the reader of a red gate needs the pair and the direction, or the next step is to read" \
      "the manifest by hand and guess which of the 2 names has to move"
  else
    pass_check "counter_stimulus_the_guard_refuses_a_child_above_its_parent"
  fi

  run_order_guard "$FIXTURE_GOOD_ORDER"
  if [[ "$GUARD_STATUS" -ne 0 ]]; then
    fail_check "counter_stimulus_the_guard_accepts_a_parent_above_its_child" \
      "the guard exited ${GUARD_STATUS} on a manifest whose order is valid:" \
      "${FIXTURE_GOOD_ORDER#"$REPO_ROOT"/}" \
      "it said:" "${GUARD_OUTPUT:-<nothing>}" \
      "a guard that refuses a correct manifest passes the case above by refusing everything"
  else
    expected_order="${FIXTURE_PARENT}
${FIXTURE_CHILD}"
    assert_equal "counter_stimulus_the_guard_accepts_a_parent_above_its_child" \
      "$expected_order" "$GUARD_OUTPUT" \
      "the accepted manifest must also come back in document order, which IS the build order"
  fi
fi

# ===========================================================================
# 3. EVERY GROUP THE MANIFEST NAMES IS A GROUP THE GUEST IMPLEMENTS
# ===========================================================================
# _ctl/tests/publish-order.test.sh holds every image to a NON-EMPTY groups list.
# Non-empty is not the whole property: `content-ghots` is non-empty, and the
# only reader that would ever notice is .ci/image-checks.sh — inside the
# container, on the publish path, after the merge. Its `*)` arm fails the run
# naming the group, which is the right behaviour and the wrong MOMENT.
#
# Both directions, and they fail for different reasons:
#
#   manifest -> guest  a group nothing implements turns the smoke red at
#                      publish time on a typo a static reader could have caught
#   guest -> manifest  a group no image names is dead code that reads as
#                      coverage — the same defect an extra row of the retired
#                      per-image tables used to be
#
# This pair is the reason .ci/image-checks.sh is read by this file at all. It is
# otherwise the guest's business, and _ctl/tests/functional-groups.test.sh runs
# the groups themselves with names it passes in by hand.
manifest_groups=""
manifest_groups_status=0
manifest_groups="$(manifest_yq '.images | to_entries | .[] | .value.groups | .[]' 2>&1)" \
  || manifest_groups_status=$?

if [[ ! -f "$REPO_ROOT/$GUEST_SCRIPT" ]]; then
  fail_check "the_guest_check_group_table_is_readable" \
    "absent: ${GUEST_SCRIPT}"
  fail_check "the_manifest_groups_and_the_guest_groups_are_one_set" \
    "absent: ${GUEST_SCRIPT}"
else
  guest_groups="$(guest_group_labels "$REPO_ROOT/$GUEST_SCRIPT" | sort -u)"
  guest_total="$(grep -c . <<< "$guest_groups")" || guest_total=0
  if [[ "$guest_total" -ge 2 ]]; then
    pass_check "the_guest_check_group_table_is_readable"
  else
    fail_check "the_guest_check_group_table_is_readable" \
      "the reader found ${guest_total} arm(s) in ${GUEST_GROUP_FUNCTION} of ${GUEST_SCRIPT}" \
      "it read:" "${guest_groups:-<nothing>}" \
      "either the dispatch moved out of that function — and guest_group_labels in this test is" \
      "what you edit — or it stopped matching, and the rule below would report every group the" \
      "manifest names as unimplemented"
  fi

  if [[ "$manifest_groups_status" -ne 0 || -z "$manifest_groups" ]]; then
    fail_check "the_manifest_groups_and_the_guest_groups_are_one_set" \
      "reading the groups of ${IMAGES_MANIFEST} exited ${manifest_groups_status}" \
      "it printed:" "${manifest_groups:-<nothing>}"
  else
    assert_equal "the_manifest_groups_and_the_guest_groups_are_one_set" \
      "$guest_groups" \
      "$(sort -u <<< "$manifest_groups")" \
      "want is ${GUEST_GROUP_FUNCTION} in ${GUEST_SCRIPT}; got is every 'groups' entry of ${IMAGES_MANIFEST}" \
      "a group the manifest names and the guest does not implement fails the smoke INSIDE the" \
      "container, on the publish path, after the merge — the guest's own \`*)\` arm is the only" \
      "reader of it today, and it reads too late" \
      "a group the guest implements and no image names is dead code that reads as coverage"
  fi
fi

# ===========================================================================
# 4. THE GENERATOR IS IDEMPOTENT, AND THE COMMITTED FILES ARE ITS OUTPUT
# ===========================================================================
# Both properties are what makes a generated file safe to trust:
#
#   idempotent  the same manifest gives the same bytes, so a second run is a
#               no-op and `git diff` after a regeneration shows only what the
#               manifest change caused. A generator that appends, re-wraps or
#               reorders on the second pass makes every regeneration a diff
#               nobody can read.
#   committed   what is checked in IS what the generator emits. Without this, a
#               hand edit to the provider workflow survives until the next
#               regeneration deletes it silently — and the file gives the reader
#               no sign that it may not be edited.
#
# It runs in a staged tree of copies. Nothing here writes to the repository, and
# a red in this section names a file under a mktemp directory for exactly that
# reason.
staged_root="$(stage_generator_root)"

run_generator "$staged_root"
first_status="$GENERATE_STATUS"
first_output="$GENERATE_OUTPUT"

if [[ "$first_status" -eq 0 ]]; then
  pass_check "the_generator_runs_against_the_manifest_alone"
else
  fail_check "the_generator_runs_against_the_manifest_alone" \
    "${GENERATOR} exited ${first_status} in a root holding images.yaml, versions.env," \
    "_ctl/lib.sh, _ctl/generate.sh and ${PROVIDER_DIRECTORY}/ and nothing else" \
    "it said:" "${first_output:-<nothing>}" \
    "its header states it reads nothing outside images.yaml and _ctl/lib.sh — a failure here" \
    "means it reads a file that claim does not name, and the claim or the file has to go"
fi

# The output of run 1, kept before run 2 overwrites it.
first_copies="$(mktemp -d)"
if [[ "$first_status" -eq 0 ]]; then
  for name in "${GENERATED_FILES[@]}"; do
    cp "${staged_root}/${PROVIDER_DIRECTORY}/${name}" "${first_copies}/${name}"
  done
fi

# -- 3a. what is committed is what the generator emits --
if [[ "$first_status" -ne 0 ]]; then
  fail_check "the_committed_provider_files_are_the_generator_output" \
    "the generator did not run, so there is nothing to compare"
else
  generated_drift=""
  # `generated_file` and not the obvious `emitted`: `shellcheck -x` follows the
  # source line at the top of this file and carries a name's TYPE across the
  # join, and _ctl/lib.sh declares `emitted` as an ARRAY inside image_names. A
  # plain string of that name here reads as SC2178 + SC2128, and `validate`
  # lints this file with -x. The library's own comment states the rule from the
  # other side; this is what obeying it looks like.
  for name in "${GENERATED_FILES[@]}"; do
    committed_file="$REPO_ROOT/${PROVIDER_DIRECTORY}/${name}"
    generated_file="${first_copies}/${name}"
    cmp_status=0
    diff_text=""
    cmp -s "$committed_file" "$generated_file" || cmp_status=$?
    [[ "$cmp_status" -eq 0 ]] && continue
    diff_text="$(diff -u "$committed_file" "$generated_file" || true)"
    generated_drift="${generated_drift:+${generated_drift}
}${PROVIDER_DIRECTORY}/${name}: committed vs generated, --- is the committed file
${diff_text}"
  done
  if [[ -z "$generated_drift" ]]; then
    pass_check "the_committed_provider_files_are_the_generator_output"
  else
    fail_check "the_committed_provider_files_are_the_generator_output" \
      "$generated_drift" \
      "run 'bash ${GENERATOR}' and commit what it writes, or move the edit into images.yaml" \
      "or into the generator's template — a hand edit to a generated file survives until the" \
      "next regeneration and is then deleted with no diff anybody reviewed"
  fi
fi

# -- 3b. the second run changes nothing --
if [[ "$first_status" -ne 0 ]]; then
  fail_check "a_second_generator_run_changes_nothing" \
    "the first run failed, so a second one proves nothing"
  fail_check "the_generator_leaves_the_hand_written_files_alone" \
    "the first run failed, so nothing can be said about what it wrote"
else
  run_generator "$staged_root"
  second_status="$GENERATE_STATUS"
  second_output="$GENERATE_OUTPUT"

  if [[ "$second_status" -ne 0 ]]; then
    fail_check "a_second_generator_run_changes_nothing" \
      "the second run exited ${second_status} over the output of the first" \
      "it said:" "${second_output:-<nothing>}" \
      "a generator that cannot read what it just wrote is not idempotent in the only way" \
      "that matters: nobody can run it twice"
  else
    idempotence_drift=""
    for name in "${GENERATED_FILES[@]}"; do
      cmp_status=0
      cmp -s "${first_copies}/${name}" "${staged_root}/${PROVIDER_DIRECTORY}/${name}" || cmp_status=$?
      [[ "$cmp_status" -eq 0 ]] && continue
      idempotence_drift="${idempotence_drift:+${idempotence_drift}
}${PROVIDER_DIRECTORY}/${name}: run 2 differs from run 1
$(diff -u "${first_copies}/${name}" "${staged_root}/${PROVIDER_DIRECTORY}/${name}" || true)"
    done
    if [[ -z "$idempotence_drift" ]]; then
      pass_check "a_second_generator_run_changes_nothing"
    else
      fail_check "a_second_generator_run_changes_nothing" \
        "$idempotence_drift" \
        "same manifest, same output, byte for byte — the property ${GENERATOR} states about" \
        "itself, and the one that makes a regeneration diff readable" \
        "the nightly matrix is rewritten IN PLACE, so this is the clause an edit there breaks"
    fi
  fi

  # -- 3c. it writes the 2 files it declares, and no other --
  untouched_drift=""
  for name in "${UNGENERATED_FILES[@]}"; do
    cmp_status=0
    cmp -s "$REPO_ROOT/${PROVIDER_DIRECTORY}/${name}" "${staged_root}/${PROVIDER_DIRECTORY}/${name}" || cmp_status=$?
    [[ "$cmp_status" -eq 0 ]] && continue
    untouched_drift="${untouched_drift:+${untouched_drift}
}${PROVIDER_DIRECTORY}/${name}: rewritten by the generator
$(diff -u "$REPO_ROOT/${PROVIDER_DIRECTORY}/${name}" "${staged_root}/${PROVIDER_DIRECTORY}/${name}" || true)"
  done
  if [[ -z "$untouched_drift" ]]; then
    pass_check "the_generator_leaves_the_hand_written_files_alone"
  else
    fail_check "the_generator_leaves_the_hand_written_files_alone" \
      "$untouched_drift" \
      "${GENERATOR} declares 2 outputs, and weekly-bumps.yml is hand-written: its schedule," \
      "its token and its 2-job shape are not image facts and no manifest entry describes them" \
      "a generator that widened its reach would delete them on the next run"
  fi
fi

rm -rf "$staged_root" "$first_copies"

test_summary "$TEST_NAME"
