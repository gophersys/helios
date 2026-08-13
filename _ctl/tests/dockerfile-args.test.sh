#!/usr/bin/env bash
#
# _ctl/tests/dockerfile-args.test.sh — every version reference resolves.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike .ci/smoke.sh, it runs in the PULL REQUEST gate.
#
# What it encodes: the ARGs-at-top convention in .claude/rules/00-identity.md
# says every tool version is an ARG at the top of its Dockerfile and a RUN line
# threads it in. That leaves one way to break a Dockerfile silently — rename or
# delete the ARG and leave the reference behind. `${GONE_VERSION}` expands to the
# empty string, so `curl` fetches a URL with no version in it and the build dies
# with a 404, at push time, in a job nobody is watching.
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
)

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
FIXTURE="$TESTS_DIR/fixtures/dangling-arg/Dockerfile"

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
      if ! printf '%s\n' "$declared" | grep -qx -- "$name"; then
        hits="${hits:+${hits}
}${line_number}:${name}"
      fi
    done < <(printf '%s\n' "$text" | grep -oE "$VERSION_REFERENCE" | sed -e 's/^\${//' -e 's/}$//' | sort -u)
  done < "$file"

  printf '%s' "$hits"
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
done

test_summary "$TEST_NAME"
