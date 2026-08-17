#!/usr/bin/env bash
#
# _ctl/tests/dockerfile-args.test.sh — every version ARG and reference agree.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike .ci/smoke.sh, it runs in the PULL REQUEST gate.
#
# What it encodes: the ARGs-at-top convention in .claude/rules/00-identity.md
# says every tool version is an ARG at the top of its Dockerfile and a RUN line
# threads it in. That leaves TWO ways to break a Dockerfile silently, and this
# file checks both directions of the ARG-to-reference correspondence:
#
#   DANGLING — a version-shaped ${NAME} is referenced but no ARG declares it.
#   Rename or delete the ARG and leave the reference behind: `${GONE_VERSION}`
#   expands to the empty string, so `curl` fetches a URL with no version in it
#   and the build dies with a 404, at push time, in a job nobody is watching.
#
#   ORPHAN — a version-shaped `ARG NAME_VERSION` is declared but no RUN line
#   references it. Delete a RUN-install and leave its `ARG *_VERSION` at the top,
#   or rename an ARG and drop its last use: the build still SUCCEEDS, so nothing
#   fails — but the ARG is now a stale pin for a tool the image no longer
#   installs, which is the tell that image content changed under a pull request.
#   The full "does the built image contain the tool" check is build-only and
#   stays post-merge; this static invariant catches the common partial deletion
#   at PR time, with no external tool list to drift.
#
# Nothing caught that. `ctl.sh validate` runs shellcheck, jq, hadolint and the
# no-hardcoded-semver check, and a dangling reference passes all 4: it is
# well-formed Dockerfile, well-formed shell, and it names no version at all,
# which is precisely what the semver check asks for. Measured on this repository:
# rename ARG DOCKER_BUILDX_VERSION so line 511 dangles, and
# `bash ./ctl.sh validate` still exits 0.
#
# Scope, deliberately narrow: only VERSION-SHAPED names are checked
# (*_VERSION, *_REF, *_CHANNEL). Those are the names the convention governs, and
# they are never shell locals or inherited ENV, so the rule holds with ZERO
# exceptions across all 5 Dockerfiles — 48 references, no allowlist. A wider
# rule needs one: ${VERSION_CODENAME} comes from `. /etc/os-release`, ${WEST_VENV}
# from the parent image's ENV, ${USERNAME} from zsh itself. An allowlist is a
# place for a real defect to hide, so this test does not open one.
#
# Usage: bash _ctl/tests/dockerfile-args.test.sh
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

TEST_NAME="dockerfile-args.test.sh"

# Every Dockerfile the repository builds. Named file by file rather than found by
# a glob, for the reason platform-policy.test.sh names its list: a glob that
# stops matching leaves a green result that read nothing.
DOCKERFILES=(
  "base/Dockerfile"
  "runner/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
  "cloud/Dockerfile"
)

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire. One fixture per direction: the dangling one
# carries a reference no ARG declares, the orphan one carries an ARG no RUN
# references.
FIXTURE="$TESTS_DIR/fixtures/dangling-arg/Dockerfile"
ORPHAN_FIXTURE="$TESTS_DIR/fixtures/orphan-arg/Dockerfile"

# The shape of a name this test governs.
VERSION_REFERENCE='\$\{[A-Za-z_][A-Za-z0-9_]*(_VERSION|_REF|_CHANNEL)\}'

# version_references <file> — every version-shaped ${NAME} the file REFERENCES,
# 1 per line, comments excluded.
function version_references() {
  local file="$1"
  grep -vE '^[[:space:]]*#' "$file" \
    | grep -oE "$VERSION_REFERENCE" \
    | sed -e 's/^\${//' -e 's/}$//' \
    | sort -u
}

# declared_args <file> — every name an ARG in that file DECLARES, 1 per line.
function declared_args() {
  local file="$1"
  grep -oE '^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' "$file" | awk '{print $2}' | sort -u
}

# dangling_references <file> — `line:NAME` for every version-shaped reference
# that no ARG in the same file declares. Prints nothing when the file is clean.
#
# The walk is line by line because a reader needs the LINE, not just the name:
# "DOCKER_BUILDX_VERSION is undeclared" sends you searching, and
# "base/Dockerfile:511: DOCKER_BUILDX_VERSION" does not.
function dangling_references() {
  local file="$1"
  local declared hits="" text name trimmed
  local line_number=0
  declared="$(declared_args "$file")"

  while IFS= read -r text; do
    line_number=$((line_number + 1))
    # A comment is prose, not an instruction. zephyr/Dockerfile explains a zsh
    # parameter expansion in prose, and a detector that reads prose reports it.
    trimmed="${text#"${text%%[![:space:]]*}"}"
    case "$trimmed" in '#'*) continue ;; esac

    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      if ! grep -qx -- "$name" <<< "$declared"; then
        hits="${hits:+${hits}
}${line_number}:${name}"
      fi
    done < <(printf '%s\n' "$text" | grep -oE "$VERSION_REFERENCE" | sed -e 's/^\${//' -e 's/}$//' | sort -u)
  done < "$file"

  printf '%s' "$hits"
}

# orphan_args <file> — every version-shaped name an ARG in the file DECLARES
# that no braced ${NAME} in the same file REFERENCES. Prints nothing when clean,
# 1 name per line otherwise.
#
# The mirror of dangling_references. A dangling reference names a version with
# no ARG; an orphan ARG declares a version with no reference — the residue of a
# deleted RUN-install whose `ARG *_VERSION` was left at the top, or a rename that
# dropped the ARG's last use. The build still succeeds, so nothing else catches
# it: the ARG is simply a stale pin for a tool the image no longer installs.
#
# Only version-shaped names are considered, for the reason stated in the header:
# a non-version ARG (BASE_IMAGE, USERNAME, DOCKER_GROUP_GID) is governed by no
# convention that requires a reference, so it must never be flagged. "Reference"
# is the SAME braced ${NAME} the dangling detector uses; the real tree threads
# every version ARG in braced form, so the two directions agree.
function orphan_args() {
  local file="$1"
  local declared referenced name orphans=""
  declared="$(declared_args "$file")"
  referenced="$(version_references "$file")"

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    [[ "$name" =~ (_VERSION|_REF|_CHANNEL)$ ]] || continue
    if ! grep -qx -- "$name" <<< "$referenced"; then
      orphans="${orphans:+${orphans}
}${name}"
    fi
  done < <(printf '%s\n' "$declared")

  printf '%s' "$orphans"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. every named Dockerfile is really there --------
missing_files=""
for relative in "${DOCKERFILES[@]}"; do
  if [[ ! -f "$REPO_ROOT/$relative" ]]; then
    missing_files="${missing_files:+${missing_files}
}${relative}"
  fi
done
if [[ -n "$missing_files" ]]; then
  fail_check "every_named_Dockerfile_exists" \
    "the file list in this test is stale; these are named but absent:" \
    "$missing_files"
else
  pass_check "every_named_Dockerfile_exists"
fi

# -------- 2. the counter-stimulus: the detector FIRES --------
# This runs before the real files on purpose. A clean verdict on the repository
# means nothing until the same function has been watched to report a file that
# is broken.
if [[ ! -f "$FIXTURE" ]]; then
  fail_check "counter_stimulus_fixture_exists" \
    "the fixture this test proves itself with is absent: ${FIXTURE}"
else
  pass_check "counter_stimulus_fixture_exists"

  fixture_hits="$(dangling_references "$FIXTURE")"

  if [[ -z "$fixture_hits" ]]; then
    fail_check "counter_stimulus_dangling_reference_is_reported" \
      "the fixture carries a reference no ARG declares and the detector found nothing" \
      "the detector cannot fail, so its verdict on the real Dockerfiles is worthless"
  else
    pass_check "counter_stimulus_dangling_reference_is_reported"
  fi

  assert_contains "counter_stimulus_names_the_undeclared_ARG" \
    "$fixture_hits" "TOOL_RELEASE_VERSION" \
    "the report has to name the reference, not only count it"

  # The other half of a usable detector. One that reports every reference is as
  # useless as one that reports none, and it is the failure mode a wider rule has.
  assert_not_contains "counter_stimulus_does_not_report_the_declared_ARG" \
    "$fixture_hits" "TOOL_VERSION:" \
    "TOOL_VERSION is declared by an ARG in the fixture and must not be reported"

  assert_not_contains "counter_stimulus_does_not_read_comments" \
    "$fixture_hits" "NEVER_DECLARED_VERSION" \
    "that name appears only inside a comment in the fixture"
fi

# -------- 2b. the orphan counter-stimulus: the detector FIRES --------
# The mirror of section 2. A declared-but-unreferenced version ARG is a real
# defect too — a deleted RUN-install leaves its `ARG *_VERSION` at the top — and
# a detector that has never reported one has never been watched to work.
if [[ ! -f "$ORPHAN_FIXTURE" ]]; then
  fail_check "counter_stimulus_orphan_fixture_exists" \
    "the fixture this test proves the orphan detector with is absent: ${ORPHAN_FIXTURE}"
else
  pass_check "counter_stimulus_orphan_fixture_exists"

  orphan_hits="$(orphan_args "$ORPHAN_FIXTURE")"

  if [[ -z "$orphan_hits" ]]; then
    fail_check "counter_stimulus_orphan_ARG_is_reported" \
      "the fixture carries a declared-unreferenced version ARG and the detector found nothing" \
      "the detector cannot fail, so its verdict on the real Dockerfiles is worthless"
  else
    pass_check "counter_stimulus_orphan_ARG_is_reported"
  fi

  assert_contains "counter_stimulus_names_the_orphan_ARG" \
    "$orphan_hits" "ABANDONED_TOOL_VERSION" \
    "the report has to name the orphan, not only count it"

  # The other half of a usable detector. One that reports every declared ARG is
  # as useless as one that reports none: a declared AND referenced ARG is not an
  # orphan, and reporting it would fire on every version ARG in the repository.
  assert_not_contains "counter_stimulus_does_not_report_a_referenced_ARG" \
    "$orphan_hits" "KEPT_TOOL_VERSION" \
    "KEPT_TOOL_VERSION is declared AND referenced in the fixture and must not be reported"

  assert_not_contains "counter_stimulus_orphan_ignores_commented_ARG" \
    "$orphan_hits" "COMMENTED_OUT_VERSION" \
    "that name appears only inside a commented '# ARG' line, which is not a declaration"
fi

# -------- 3. every reference in every Dockerfile resolves --------
for relative in "${DOCKERFILES[@]}"; do
  file="$REPO_ROOT/$relative"
  [[ -f "$file" ]] || continue

  # A file whose reference set is empty is not a clean file; it is a regex that
  # stopped matching. Every Dockerfile here threads at least 1 version ARG.
  references="$(version_references "$file")"
  reference_count=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    reference_count=$((reference_count + 1))
  done <<< "$references"

  if [[ "$reference_count" -eq 0 ]]; then
    fail_check "${relative}_references_at_least_one_version_ARG" \
      "no ${VERSION_REFERENCE} matched in ${relative}" \
      "either the file stopped threading its versions, or this test stopped reading them"
  else
    pass_check "${relative}_references_at_least_one_version_ARG"
  fi

  hits="$(dangling_references "$file")"
  if [[ -z "$hits" ]]; then
    pass_check "${relative}_declares_every_version_it_references"
  else
    fail_check "${relative}_declares_every_version_it_references" \
      "these references expand to the empty string, so the build fetches a URL with no version in it:" \
      "$hits" \
      "declare each one as an ARG at the top of ${relative}, or fix the name the RUN line asks for"
  fi

  # The mirror direction: every version ARG the file DECLARES is threaded by a
  # RUN line. An orphan is a version pin for a tool the image no longer installs
  # — the tell of a deleted RUN-install that left its `ARG *_VERSION` behind.
  orphans="$(orphan_args "$file")"
  if [[ -z "$orphans" ]]; then
    pass_check "${relative}_references_every_version_it_declares"
  else
    fail_check "${relative}_references_every_version_it_declares" \
      "these version ARGs are declared but no RUN line references them, so they pin a tool nothing installs:" \
      "$orphans" \
      "remove the stale ARG, or restore the RUN line that threaded it"
  fi
done

test_summary "$TEST_NAME"
