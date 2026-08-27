#!/usr/bin/env bash
#
# _ctl/tests/toolchain-parity.test.sh — a gate tool's VERSION is pinned, and
# `validate` refuses to judge with any other one.
#
# Static means static: this file reads files and runs `ctl.sh validate` inside a
# staged repository root of copies, with both linters stubbed. It starts no
# container, it calls no daemon and it reaches no network, so it runs identically
# on a laptop and on a CI runner — and it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE DEFECT (ledger #117)
# ============================================================================
#
# `validate` judged every shell script of this repository with whatever shell
# linter the machine happened to hold. Nothing declared a version, and nothing
# compared one.
#
# A linter's verdict is a function of its version. Measured, run 32111944450 of
# this repository: `resolve_image_platforms` in _ctl/lib.sh took its argument as
# `"${1:-${IMAGE_NAME:-}}"`, CI reported SC2120 on the declaration and SC2119 at
# each of the 3 bare calls, and the host — a mac carrying a newer shellcheck —
# said nothing about any of them. So `bash ./ctl.sh validate` was GREEN on the
# machine the change was written on and RED in the pull request, and the author
# had every reason to trust the green: it is the same verb, the same flags and
# the same files.
#
# That is the worst shape a gate can take. It is not a check that cannot fail —
# it is a check whose ANSWER depends on the operator, so the answer a developer
# reads carries no information about the answer the gate will give.
#
# The class is wider than the instance, and this file is written against the
# class: ANY tool whose version can change a verdict must declare that version
# in versions.env and be held to it, and any tool that is exempt must say in
# writing why. hadolint had the rule already — versions.env pins it, `validate`
# lints at exactly that pin or through the pinned image — and shellcheck did
# not. Nothing enumerated the difference, so nothing could report it.
#
# ============================================================================
# THE SEAM: THE VERB ITSELF, IN A STAGED ROOT
# ============================================================================
#
# The gate is a block INSIDE cmd_validate, so the whole verb is run instead of a
# helper: a check written against a helper is still green on the day the helper
# stops being called. The root is a mktemp tree holding the real ctl.sh and
# _ctl/lib.sh over a 1-image fixture manifest.
#
# BOTH linters are stubbed, and for the same reason. hadolint's resolution can
# leave the machine — a host a point release off the pin sends the verb to
# `docker run` — and shellcheck's version is the STIMULUS this file drives. The
# staged versions.env pins a version, the stub reports one, and the test moves
# the STUB rather than the pin, which is the direction the real defect took: the
# repository's declaration stood still while the machine under it changed.
#
# The staged tree is COPIES and never symlinks, the rule
# _ctl/tests/images-manifest.test.sh states: nothing here writes to the
# repository, and a staging helper that can reach the real tree is 1 edit away
# from one that does.
#
# ============================================================================
# WHAT THIS FILE DOES NOT PROVE
# ============================================================================
#
# That the pinned version is the RIGHT one. No static check can know which shell
# linter release a reviewer wants CI to judge with. What it holds instead is the
# property that makes the pin true rather than claimed: both root Dockerfiles
# install shellcheck AT the pin, so the images ship the version the gate
# demands, and a bump is 1 versions.env row that reaches the gate and the images
# together. A pin nothing installs would be a number this file could still
# verify and nobody could rely on.
#
# It also does not prove the EXEMPTIONS are true. "jq only parses" is a claim a
# human makes; what is held here is that the claim EXISTS, is disjoint from the
# asserted set, and covers every tool the verb reaches for. Saying nothing is
# what the gate refuses.
#
# Usage: bash _ctl/tests/toolchain-parity.test.sh
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

TEST_NAME="toolchain-parity.test.sh"

FIXTURES="$TESTS_DIR/fixtures/toolchain-parity"
STUB_BIN="$TESTS_DIR/stubs/validate"
ROOT_CTL="$REPO_ROOT/ctl.sh"
VERSIONS_ENV="$REPO_ROOT/versions.env"

# The 1 image the fixture manifest declares, and every file the staged root
# takes from the fixture directory. Named one by one and not found by a glob: a
# glob that stopped matching would stage a root missing a devcontainer.json, and
# `validate` would go red for that instead — a false red on a rule this file
# says nothing about.
FIXTURE_IMAGE="only"
FIXTURE_IMAGE_FILES=("ctl.sh" "Dockerfile" "devcontainer.json" "project.json")
FIXTURE_ROOT_FILES=("images.yaml" "versions.env" "project.json")

# The version the staged versions.env pins, and the 2 the stub is driven to
# report. Written as literals: a test that reads the value it checks out of the
# file under test agrees with a wrong value too, and check 2 below holds this
# literal to the fixture.
STAGED_PIN="0.9.0"
MATCHING_VERSION="0.9.0"
MISMATCHED_VERSION="0.11.0"

# Every external tool `cmd_validate` reaches for, as a hand-kept literal, held
# to SET EQUALITY with the union of the 2 tables ctl.sh declares. The literal is
# the point: reading the tables and comparing them to themselves would agree
# with any pair, an incomplete one included. Adding a tool to the verb means
# editing this list AND classifying it there, in 1 change.
#
#   the shell linter    lints every shell script    asserted
#   hadolint            lints every Dockerfile      asserted
#   jq          parses project.json + devcontainer.json
#   yq          answers images.yaml, through manifest_yq at source time
#   docker      the container route of the 2 linters, never a verdict of its own
VALIDATE_TOOLS=("shellcheck" "hadolint" "jq" "yq" "docker")

# The REMEDY line the refusal prints, as a format. It is a needle every mismatch
# check matches on, and it is the remedy rather than the diagnosis on purpose: a
# gate that reports a version and leaves the operator to work out where a
# matching one lives has named a defect and not a fix. It is the wording the
# hadolint refusal already uses, so the 2 gate tools speak with 1 voice.
REMEDY_FORMAT='run this inside the devcontainer, which ships exactly %s'

# remedy_for <version> — the exact text the refusal must carry.
function remedy_for() {
  # shellcheck disable=SC2059
  # The format is a CONSTANT declared above, and %s is the point of it.
  printf "$REMEDY_FORMAT" "$1"
}

# The progress line the lint loop writes for the fixture dispatcher. Its
# PRESENCE is what says the loop ran, and its ABSENCE is what says the gate
# refused instead of judging at the wrong version. The bare word `shellcheck`
# cannot carry either claim: the refusal names the tool too.
LINT_PROGRESS_NEEDLE="shellcheck: ${FIXTURE_IMAGE}/ctl.sh"

VALIDATE_OUTPUT=""
VALIDATE_STATUS=0

# stage_root — a repository root holding the real ctl.sh and _ctl/lib.sh over
# the 1-image fixture manifest, with the dispatcher EXECUTABLE.
function stage_root() {
  local root file
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
  mkdir -p "${root}/${FIXTURE_IMAGE}"
  for file in "${FIXTURE_IMAGE_FILES[@]}"; do
    cp "${FIXTURES}/${FIXTURE_IMAGE}/${file}" "${root}/${FIXTURE_IMAGE}/${file}"
  done
  chmod 755 "${root}/${FIXTURE_IMAGE}/ctl.sh"
  chmod 755 "${root}/ctl.sh"
  printf '%s' "$root"
}

# run_validate <staged root> <version the shellcheck stub reports>
#
# stderr is folded into stdout because the refusal IS the answer: log_error
# writes to stderr, and a check that read stdout alone would be reading the
# progress log of a gate whose verdict it had thrown away.
function run_validate() {
  local root="$1" reported="$2"
  VALIDATE_STATUS=0
  VALIDATE_OUTPUT="$(cd "$root" && env \
    PATH="${STUB_BIN}:${PATH}" \
    PROJECT_ROOT="$root" \
    REPO_ROOT="$root" \
    STUB_SHELLCHECK_VERSION="$reported" \
    bash ./ctl.sh validate 2>&1)" || VALIDATE_STATUS=$?
}

# gate_tool_tables — the 2 classification tables, out of a shell that sourced
# ctl.sh, 1 `<table>|<row>` per line.
#
# `set --` first, so the dispatcher at the foot of that script takes its help
# path and returns 0 instead of exiting 1 on an unknown command — the shape
# _ctl/tests/zsh-username.test.sh already uses to call a function of that file.
#
# stderr is kept and the status is returned: a ctl.sh that declares neither
# table is exactly the state this file must REPORT, and an unset-variable error
# swallowed into an empty answer would read as 2 empty tables that agree with
# an empty literal.
TABLES_OUTPUT=""
TABLES_STATUS=0
function gate_tool_tables() {
  TABLES_STATUS=0
  TABLES_OUTPUT="$(CTL_SCRIPT="$ROOT_CTL" bash -c '
    set --
    source "$CTL_SCRIPT" > /dev/null
    for row in "${GATE_TOOL_PINS[@]}"; do printf "pin|%s\n" "$row"; done
    for row in "${GATE_TOOL_EXEMPT[@]}"; do printf "exempt|%s\n" "$row"; done
  ' 2>&1)" || TABLES_STATUS=$?
}

# table_tools <table> — the tool names of one table, sorted.
function table_tools() {
  awk -F'|' -v want="$1" '$1 == want { print $2 }' <<< "$TABLES_OUTPUT" | sort
}

# sorted_list <word...> — the arguments as sorted lines, for a set comparison.
function sorted_list() {
  printf '%s\n' "$@" | sort
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE FIXTURE TREE AND BOTH STUBS ARE REALLY THERE
# ===========================================================================
# Every staged check below is built from these. An absent one would stage a root
# that fails `validate` for a reason this file says nothing about, and the
# refusal checks would then pass on the wrong red.
missing_fixtures=""
for name in "${FIXTURE_ROOT_FILES[@]}"; do
  [[ -f "${FIXTURES}/${name}" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${FIXTURES#"$REPO_ROOT"/}/${name}"
done
for name in "${FIXTURE_IMAGE_FILES[@]}"; do
  [[ -f "${FIXTURES}/${FIXTURE_IMAGE}/${name}" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${FIXTURES#"$REPO_ROOT"/}/${FIXTURE_IMAGE}/${name}"
done

if [[ -z "$missing_fixtures" ]]; then
  pass_check "the_fixture_repository_tree_is_present"
else
  fail_check "the_fixture_repository_tree_is_present" \
    "the staged root is built from these, and they are absent:" \
    "$missing_fixtures"
fi

missing_stubs=""
for name in "shellcheck" "hadolint"; do
  [[ -x "${STUB_BIN}/${name}" ]] || missing_stubs="${missing_stubs:+${missing_stubs} }${name}"
done
if [[ -z "$missing_stubs" ]]; then
  pass_check "both_validate_stubs_are_executable"
else
  fail_check "both_validate_stubs_are_executable" \
    "not executable under ${STUB_BIN#"$REPO_ROOT"/}: ${missing_stubs}" \
    "without them the staged runs reach the host linters and then a docker daemon," \
    "and this file stops being hermetic on every machine whose tools are off the pin"
fi

# ===========================================================================
# 2. THE FIXTURE PIN IS THE LITERAL THIS FILE DRIVES AGAINST
# ===========================================================================
# The stimulus is a DISAGREEMENT between 2 files, so both halves have to be
# known here. A fixture edited to some other version would leave the matching
# run mismatched, and every check below would pass on the wrong branch.
fixture_pin="$(awk -F= '$1 == "SHELLCHECK_VERSION" { print $2; exit }' "${FIXTURES}/versions.env")"
assert_equal "the_fixture_pins_the_version_this_file_drives_against" \
  "$STAGED_PIN" "$fixture_pin" \
  "the fixture is ${FIXTURES#"$REPO_ROOT"/}/versions.env"

if [[ "$MATCHING_VERSION" != "$MISMATCHED_VERSION" ]]; then
  pass_check "the_two_stimuli_really_differ"
else
  fail_check "the_two_stimuli_really_differ" \
    "the matching and mismatched versions are both '${MATCHING_VERSION}'," \
    "so the refusal checks and the lint checks would run the same stimulus"
fi

# ===========================================================================
# 3. THE PIN EXISTS AT HOME, AND THE IMAGES INSTALL IT
# ===========================================================================
# A pin that no build consumes is a claim about the machine rather than a
# property of it. These 2 checks are what make "the devcontainer ships exactly
# the pin" true by construction instead of by this document.
repository_pin="$(awk -F= '$1 == "SHELLCHECK_VERSION" { sub(/[[:space:]]*#.*$/, "", $2); gsub(/[[:space:]]/, "", $2); print $2; exit }' "$VERSIONS_ENV")"
if [[ "$repository_pin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  pass_check "versions_env_declares_a_semver_shellcheck_pin"
else
  fail_check "versions_env_declares_a_semver_shellcheck_pin" \
    "SHELLCHECK_VERSION in versions.env reads '${repository_pin:-<absent>}'" \
    "the gate reads that row and refuses to lint without it"
fi

uninstalled=""
for name in "base/Dockerfile" "cloud/Dockerfile"; do
  # shellcheck disable=SC2016
  # The needle is a Dockerfile's LITERAL text, and `${SHELLCHECK_VERSION}` in it
  # is the build arg the Dockerfile references. Expanding it here would search
  # for this shell's value of a name this shell does not hold.
  if ! grep -qF 'shellcheck=${SHELLCHECK_VERSION}' "${REPO_ROOT}/${name}"; then
    uninstalled="${uninstalled:+${uninstalled} }${name}"
  fi
done
if [[ -z "$uninstalled" ]]; then
  pass_check "both_root_images_install_shellcheck_at_the_pin"
else
  fail_check "both_root_images_install_shellcheck_at_the_pin" \
    "no 'shellcheck=\${SHELLCHECK_VERSION}' apt entry in: ${uninstalled}" \
    "the gate demands the pin of every host; an image that installs some other" \
    "version makes the devcontainer the one place the gate cannot run"
fi

# ===========================================================================
# 4. EVERY TOOL THE VERB REACHES FOR IS CLASSIFIED, EXACTLY ONCE
# ===========================================================================
gate_tool_tables
if [[ "$TABLES_STATUS" -eq 0 ]]; then
  pass_check "ctl_sh_declares_both_gate_tool_tables"
else
  fail_check "ctl_sh_declares_both_gate_tool_tables" \
    "sourcing ctl.sh and reading GATE_TOOL_PINS + GATE_TOOL_EXEMPT exited ${TABLES_STATUS}" \
    "$TABLES_OUTPUT"
fi

pinned_tools="$(table_tools pin)"
exempt_tools="$(table_tools exempt)"
classified="$(printf '%s\n%s\n' "$pinned_tools" "$exempt_tools" | awk 'NF' | sort)"

assert_equal "the_two_tables_cover_every_tool_validate_reaches_for" \
  "$(sorted_list "${VALIDATE_TOOLS[@]}")" "$classified" \
  "the hand-kept literal is VALIDATE_TOOLS in this file" \
  "add the tool to ctl.sh's tables and to that literal in 1 change"

# The literal has to be tied to the CODE somewhere, or the 3 lists above agree
# with each other while the verb reaches for a fourth tool nobody classified.
# `require_cmd` inside cmd_validate is the tie that can be read statically: it
# names every tool the verb refuses to run without. It does not name hadolint,
# yq or docker — each of those is resolved rather than required — so this is a
# ONE-DIRECTION check, and the set equality above is what covers the rest.
required_tools="$(awk '
  /^function cmd_validate\(\)/ { inside = 1 }
  inside && /require_cmd/ {
    sub(/^[[:space:]]*require_cmd[[:space:]]*/, "")
    print
    exit
  }
' "$ROOT_CTL")"

# awk splits the names, and shell word splitting does not: this file sets
# `IFS=$'\n\t'`, so an unquoted expansion does NOT split on the spaces that
# separate require_cmd's arguments, and the whole line would read as 1 tool name
# that no literal ever matches — a check that always fails is as useless as one
# that always passes, and this one did until it was run.
unclassified_required=""
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  found=""
  for tool in "${VALIDATE_TOOLS[@]}"; do
    [[ "$tool" == "$name" ]] && found="yes"
  done
  [[ -n "$found" ]] || unclassified_required="${unclassified_required:+${unclassified_required} }${name}"
done < <(awk '{ for (i = 1; i <= NF; i++) print $i }' <<< "$required_tools")

if [[ -z "$required_tools" ]]; then
  fail_check "every_tool_cmd_validate_requires_is_in_the_literal" \
    "no require_cmd line was found inside cmd_validate in ${ROOT_CTL#"$REPO_ROOT"/}" \
    "this check reads that line; with none, it would agree with any literal"
else
  assert_equal "every_tool_cmd_validate_requires_is_in_the_literal" \
    "" "$unclassified_required" \
    "cmd_validate requires: ${required_tools}" \
    "VALIDATE_TOOLS in this file must name each of them, and ctl.sh must classify each"
fi

overlap="$(printf '%s\n%s\n' "$pinned_tools" "$exempt_tools" | awk 'NF' | sort | uniq -d)"
assert_equal "no_tool_is_both_asserted_and_exempt" "" "$overlap" \
  "a tool in both tables has 2 answers, and the reader takes whichever it meets first"

# Every asserted tool names a pin that versions.env really declares. A table row
# pointing at an absent row would fail at the gate, on a host, long after the
# merge that wrote it.
missing_pins=""
while IFS='|' read -r _table tool pin _rest; do
  [[ -z "${tool:-}" ]] && continue
  if ! grep -qE "^${pin}=[0-9]+\.[0-9]+\.[0-9]+" "$VERSIONS_ENV"; then
    missing_pins="${missing_pins:+${missing_pins}
}${tool} names ${pin}, and versions.env declares no such semver row"
  fi
done < <(awk -F'|' '$1 == "pin"' <<< "$TABLES_OUTPUT")
assert_equal "every_asserted_tool_names_a_row_versions_env_declares" "" "$missing_pins"

# An exemption is a SENTENCE somebody wrote, and the rule _build/upstreams.txt
# already states about its own reason field applies unchanged: a reason under 20
# characters or with no space in it is a placeholder wearing the label of a
# decision.
weak_reasons=""
while IFS='|' read -r _table tool reason; do
  [[ -z "${tool:-}" ]] && continue
  if [[ "${#reason}" -lt 20 || "$reason" != *" "* ]]; then
    weak_reasons="${weak_reasons:+${weak_reasons}
}${tool}: '${reason}'"
  fi
done < <(awk -F'|' '$1 == "exempt"' <<< "$TABLES_OUTPUT")
assert_equal "every_exemption_states_a_reason_a_reviewer_can_argue_with" "" "$weak_reasons" \
  "under 20 characters, or with no space in it, is a placeholder"

# ===========================================================================
# 5. A MATCHING VERSION LINTS
# ===========================================================================
# The counter-stimulus. A gate that has only ever been observed to refuse has
# never been observed to let correct input through, and one wired to refuse
# always would pass every check in section 6.
staged_root="$(stage_root)"
run_validate "$staged_root" "$MATCHING_VERSION"

assert_equal "a_matching_shellcheck_leaves_the_gate_green" 0 "$VALIDATE_STATUS" \
  "the staged run said:" "$VALIDATE_OUTPUT"

assert_contains "a_matching_shellcheck_lints_the_staged_tree" \
  "$VALIDATE_OUTPUT" "$LINT_PROGRESS_NEEDLE"

assert_contains "a_matching_run_reports_the_pin_it_judged_with" \
  "$VALIDATE_OUTPUT" "pinned by SHELLCHECK_VERSION" \
  "the hadolint line beside it has said which version it lints at since the pin existed;" \
  "a gate that judges silently leaves a reader no way to know which answer they got"

rm -rf "$staged_root"

# ===========================================================================
# 6. A MISMATCHED VERSION IS REFUSED, BY NAME
# ===========================================================================
staged_root="$(stage_root)"
run_validate "$staged_root" "$MISMATCHED_VERSION"

assert_status_nonzero "a_mismatched_shellcheck_fails_the_gate" "$VALIDATE_STATUS" \
  "the staged run said:" "$VALIDATE_OUTPUT"

assert_contains "the_refusal_names_the_tool" "$VALIDATE_OUTPUT" "shellcheck"
assert_contains "the_refusal_names_the_version_it_found" \
  "$VALIDATE_OUTPUT" "$MISMATCHED_VERSION"
assert_contains "the_refusal_names_the_version_it_wanted" \
  "$VALIDATE_OUTPUT" "$STAGED_PIN"
assert_contains "the_refusal_names_the_remedy" \
  "$VALIDATE_OUTPUT" "$(remedy_for "$STAGED_PIN")"

# The half a status alone cannot carry. A gate that lints at the wrong version
# and then reports the mismatch has still written a verdict nobody should read,
# and the `shellcheck: <file>` lines are what a reader takes for one.
assert_not_contains "a_mismatched_shellcheck_lints_nothing" \
  "$VALIDATE_OUTPUT" "$LINT_PROGRESS_NEEDLE" \
  "the refusal has to REPLACE the lint pass, not follow it"

rm -rf "$staged_root"

# ===========================================================================
# 7. NO PIN IS A FAILURE, NEVER A FALLBACK
# ===========================================================================
# The hadolint rule, applied to the second gate tool: a gate that lost its input
# must lose it LOUDLY. Falling back to whatever the host holds is the exact
# state this whole file exists to end.
staged_root="$(stage_root)"
unpinned="$(grep -v '^SHELLCHECK_VERSION=' "${staged_root}/versions.env")"
printf '%s\n' "$unpinned" > "${staged_root}/versions.env"
run_validate "$staged_root" "$MATCHING_VERSION"

assert_status_nonzero "a_versions_env_with_no_pin_fails_the_gate" "$VALIDATE_STATUS" \
  "the staged run said:" "$VALIDATE_OUTPUT"
assert_contains "the_refusal_names_the_missing_pin" \
  "$VALIDATE_OUTPUT" "SHELLCHECK_VERSION"
assert_not_contains "an_unpinned_gate_lints_nothing" \
  "$VALIDATE_OUTPUT" "$LINT_PROGRESS_NEEDLE" \
  "with no pin there is no version to judge at, so there is no verdict to write"

rm -rf "$staged_root"

test_summary "$TEST_NAME"
