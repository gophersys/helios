#!/usr/bin/env bash
#
# _ctl/tests/resolve-upstream.test.sh — the weekly bump is EXECUTED, not read.
#
# Hermetic: a stub `curl` and a stub `gh` first on PATH, a miniature repository
# this file copies out of its fixtures, and upstream documents this repository
# holds. No network, no daemon, no credential — so every case below runs in the
# PULL REQUEST gate, where the weekly workflow itself never does.
#
# ============================================================================
# WHY THIS FILE DRIVES THE RESOLVER INSTEAD OF READING IT
# ============================================================================
#
# upstream-coverage.test.sh proves every pin NAMES a datasource. Not one line of
# it can tell whether that datasource reads anything, whether the version it
# reports is the version the pin is spelled in, or whether the digest beside it
# is the digest of the bytes the build will fetch.
#
# That gap has been shipped in this repository before, twice, and both times the
# static checks were green. `.ci/notify-failure.sh` had 287 checks pointing at it
# and every one read it as a FILENAME, so a 2-token defect in its close loop
# survived a fully green gate. Replace the digest comparison in
# _build/fetch-verified.sh with `true` and every static check of that change
# stays green while no download is verified at all.
#
# So the cases below run the real files, read the values they print, the status
# they return and the URLs they asked for.
#
# ============================================================================
# THE STALE DIGEST, AND THE 1 FIXTURE PROPERTY THAT CATCHES IT
# ============================================================================
#
# The defect this feature exists to make impossible is a bump that moves the
# version and leaves the digest: the build then dies at the download, after the
# merge, naming a pin that looks correct in the diff. A resolver can produce it
# in 1 line — resolve the version from the upstream, and copy the digest out of
# the pin it is bumping.
#
# The fixture world is built so that line cannot pass. Every digest row of
# _ctl/tests/fixtures/upstreams/resolver/versions.env reads `dddd...`, which is
# the digest of no asset in this repository, and each expected digest below is a
# LITERAL: the sha256 of the fixture asset the URL serves for the NEW version. A
# resolver that re-reads the pin reports `dddd...` and the check names both
# values. A test that computed the expected digest from the same bytes the
# resolver fetched would agree with any bytes, the wrong ones included, so the
# literals are checked against the fixture files by a guard of their own.
#
# ============================================================================
# A NON-ZERO STATUS IS NOT EVIDENCE ON ITS OWN
# ============================================================================
#
# _build/resolve-upstream.sh does not exist yet, so running it exits 127 — which
# is non-zero. A failure case that asserted "the status is non-zero" and nothing
# else would PASS today, against a file that is not there, and would go on
# passing against a resolver that exits 1 for a reason nobody wrote down. So
# every failure case here demands the status AND the name the message has to
# carry: the pin, or the secret. A reader of a 09:00 Monday run has no author
# watching it, and "exit 1" tells them nothing.
#
# ============================================================================
# THE CONTRACT THESE CASES HOLD
# ============================================================================
#
#   bash _build/resolve-upstream.sh <PIN>
#       resolves 1 pin through the datasource its _build/upstreams.txt row
#       names, and prints ONE record on stdout:
#
#           <version>|<sha256>
#
#       <version>  spelled the way the pin's CURRENT value is spelled: a leading
#                  `v` is kept when the current value carries one (cictl pins
#                  v0.1.0) and stripped when it does not (gh pins 2.90.0). An
#                  apt version drops the epoch and the debian revision, because
#                  that is what the tool reports about itself and what the smoke
#                  test compares.
#       <sha256>   the digest of the bytes the GOVERNED FILE fetches for that
#                  new version — read out of the file that performs the
#                  download, never out of the table, because a second URL home
#                  lets a resolver compute a correct digest of the wrong asset.
#                  `-` when the pin carries no digest row at all, which about 30
#                  of the 56 real pins do not (go install, corepack, pipx).
#
#   bash _build/resolve-upstream.sh --dry-run
#       resolves every row of the table and prints the pull request it WOULD
#       open, writing nothing:
#
#           bump: <PIN> <old> -> <new>      1 line per pin that moved
#           branch: <branch name>
#           title: <title>
#           body:
#           <the body>
#
#   Failure, everywhere: a non-zero status and a message NAMING THE PIN. An
#   absent credential names the secret as well.
#
#   Environment:
#       UPSTREAM_PROJECT_ROOT   the tree it reads — the table, the value homes
#                               and the governed files. Defaults to the
#                               repository. This is the seam the fixture world
#                               arrives through, and the only one these cases
#                               need.
#       EDEN_MANIFEST_READ      the credential the eden-manifest datasource
#                               reads gophersys/eden with.
#
# ============================================================================
# THE STUB UPSTREAMS
# ============================================================================
#
# `_ctl/tests/stubs/curl` answers from a map this file writes, keyed on a
# SUBSTRING of the requested URL. The exact endpoint is the resolver's choice —
# api.github.com and github.com are the same question asked 2 ways — so what
# these cases hold is the DOCUMENT each datasource reads and the value it takes
# out of it, and not the URL it reads it from. A URL no row matches exits 64
# loudly, so a datasource that reaches somewhere this file never described stops
# the run instead of collecting a cheerful 0.
#
# Usage: bash _ctl/tests/resolve-upstream.test.sh
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

TEST_NAME="resolve-upstream.test.sh"

RESOLVER_RELATIVE="_build/resolve-upstream.sh"
RESOLVER="$REPO_ROOT/$RESOLVER_RELATIVE"
NOTIFIER="$REPO_ROOT/.ci/notify-failure.sh"

STUB_CURL="$TESTS_DIR/stubs/curl"
STUB_GH="$TESTS_DIR/stubs/gh"

FIXTURE_ROOT="$TESTS_DIR/fixtures/upstreams"
FIXTURE_WORLD="$FIXTURE_ROOT/resolver"
RESPONSES="$FIXTURE_ROOT/responses"
ASSETS="$FIXTURE_ROOT/assets"

# The digest of each fixture asset, as a LITERAL. See the header: a test that
# computes the value it checks agrees with any bytes. The guard below reads the
# files and holds them to these 5 numbers, so an edit to a fixture asset turns
# 1 named check red instead of quietly agreeing with itself.
ASSET_DIGEST_STUBGITHUB="e9f2832e77a27bb6de567fecd8039919c51ba0ed73969ea5380cdfcf844ae0cb"
ASSET_DIGEST_STUBGO="17a98a1b9b1274facea20e77bd164b1746ffe5ae0f91a357d7c1f24530d62f68"
ASSET_DIGEST_STUBK8S="bccb01f0e57ae6396b3160b6c97d5222b9c8ad7f9646699b59a71efca8a5d420"
ASSET_DIGEST_STUBTAILSCALE="cc5f45fc6feea409811c787853fbc0592749b913fbe13e6bf8fa2d1226e9cbbd"
ASSET_DIGEST_STUBFLUTTER="25639dfbf55924ec4b153f8935d20178fa554a5b5190f8613206f7bcf67a2a5a"

# The index digest of an OCI manifest LIST is the sha256 of its own bytes, so
# the oci-index datasource has no separate asset: what it returns IS the digest
# of the document it fetched.
OCI_INDEX_DIGEST="6af6f8a445f77aeab618a520f5f15db4bdb185f098d1cfc62e1b2e0daea25fa3"

# `-` is the digest field of a pin that carries no digest row.
NO_DIGEST="-"

# The credential the eden-manifest datasource needs. gophersys/eden is private
# and this repository's GITHUB_TOKEN is repository-scoped, so the read needs a
# secret of its own — and its absence is a FAILURE that names it, never a skip.
EDEN_SECRET_NAME="EDEN_MANIFEST_READ"
EDEN_SECRET_VALUE="stub-eden-manifest-token"

# The 2 labels of the notifier. Literals, deliberately: a test that read the
# label out of the script it checks agrees with any label, the hardcoded one
# included.
NIGHTLY_LABEL="ci-nightly-red"
WEEKLY_LABEL="ci-weekly-red"

# The 3 real pins whose only home is a Dockerfile. A resolver that reads
# versions.env alone answers 45 of the 56 pins and cannot see these at all.
SOLE_HOME_PINS=("FLUTTER_VERSION" "ZEPHYR_SDK_VERSION" "CODE_SERVER_VERSION")

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
CASE_NUMBER=0

RESOLVER_STDOUT=""
RESOLVER_STDERR=""
RESOLVER_STATUS=0
CURL_LOG=""

NOTIFY_OUTPUT=""
NOTIFY_STATUS=0
GH_CALLS=""

# ---------------------------------------------------------------------------
# 0. THE WORLD THIS FILE NEEDS — built, and never assumed
# ---------------------------------------------------------------------------
#
# The developer's own PATH is left out on purpose: a tool that happens to be
# installed on this laptop and not on the runner would make the same case mean 2
# things. What goes in is the stub directory first, then the directory of each
# program these cases need by name, then the 2 directories holding the standard
# utilities.
#
# A missing tool is a FAILURE and never a skip. Without jq the stub gh cannot
# run the caller's own --jq expression; without sha256sum no digest can be
# computed at all; without git the dry-run case cannot state its own precondition
# — and each of those would fail every case below for a reason that says nothing
# about the resolver.
REQUIRED_TOOLS=("jq" "sha256sum" "git")
MISSING_TOOLS=""
TOOL_DIRECTORIES=""
for tool in "${REQUIRED_TOOLS[@]}"; do
  if resolved="$(command -v "$tool" 2> /dev/null)"; then
    TOOL_DIRECTORIES="${TOOL_DIRECTORIES}$(cd "$(dirname "$resolved")" && pwd):"
  else
    MISSING_TOOLS="${MISSING_TOOLS:+${MISSING_TOOLS}
}${tool}"
  fi
done

STUB_BIN="$WORK/bin"
mkdir -p "$STUB_BIN"
ln -s "$STUB_CURL" "$STUB_BIN/curl"
ln -s "$STUB_GH" "$STUB_BIN/gh"
SANDBOX_PATH="${STUB_BIN}:${TOOL_DIRECTORIES}/usr/bin:/bin"

# ---------------------------------------------------------------------------
# The map every case answers from. Written here rather than kept as a fixture
# file, because the body paths are absolute and a fixture cannot know where this
# checkout lives.
#
# The rows are ordered specific to general: an asset file name first, then the
# coordinate or the host of the index that names it. `stubowner/stubgithub` is
# inside the asset URL as well as inside the index URL, and first match wins.
# ---------------------------------------------------------------------------
BASE_MAP="$WORK/map-base.txt"
{
  printf '# assets — the bytes a digest is of, at the NEW version\n'
  printf 'stubgithub-2.4.0.tar.gz|200|%s\n'            "$ASSETS/stubgithub-2.4.0.tar.gz"
  printf 'go1.26.5.linux-amd64.tar.gz|200|%s\n'        "$ASSETS/stubgo-1.26.5.tar.gz"
  printf 'v1.35.4/bin/linux/amd64/stubk8s|200|%s\n'    "$ASSETS/stubk8s-1.35.4.bin"
  printf 'tailscale_1.96.4_amd64.tgz|200|%s\n'         "$ASSETS/stubtailscale-1.96.4.tgz"
  printf 'flutter_linux_3.41.7-stable.tar.xz|200|%s\n' "$ASSETS/stubflutter-3.41.7.tar.xz"
  printf '# indexes\n'
  printf 'auth.docker.io|200|%s\n'        "$RESPONSES/oci-registry-token.json"
  printf 'stubowner/stubgithub|200|%s\n'  "$RESPONSES/github-release-stubgithub.json"
  printf 'stubowner/stubvprefix|200|%s\n' "$RESPONSES/github-release-stubvprefix.json"
  printf 'stubowner/stubcurrent|200|%s\n' "$RESPONSES/github-release-stubcurrent.json"
  printf 'stub-pypi-package|200|%s\n'     "$RESPONSES/pypi-stub-pypi-package.json"
  printf 'stub-npm-package|200|%s\n'      "$RESPONSES/npm-stub-npm-package.json"
  printf 'stub-apt-package|200|%s\n'      "$RESPONSES/apt-launchpad-stub-apt-package.json"
  printf 'go.dev/dl|200|%s\n'             "$RESPONSES/go-dl.json"
  printf 'nodejs.org/dist|200|%s\n'       "$RESPONSES/node-dist-index.json"
  printf 'library/ubuntu|200|%s\n'        "$RESPONSES/oci-index-ubuntu.json"
  printf 'stable.txt|200|%s\n'            "$RESPONSES/k8s-dl-stable.txt"
  printf 'pkgs.tailscale.com|200|%s\n'    "$RESPONSES/tailscale-pkgs-stable.json"
  printf 'releases_linux.json|200|%s\n'   "$RESPONSES/flutter-releases-linux.json"
  printf 'gophersys/eden|200|%s\n'        "$RESPONSES/eden-harnesses-versions.env"
} > "$BASE_MAP"

# The index of 1 datasource is gone. Its asset is still served, so the case
# below cannot pass by failing at the download.
INDEX_404_MAP="$WORK/map-index-404.txt"
{
  printf 'stubgithub-2.4.0.tar.gz|200|%s\n' "$ASSETS/stubgithub-2.4.0.tar.gz"
  printf 'stubowner/stubgithub|404|-\n'
} > "$INDEX_404_MAP"

# The index answers and the asset it points at is gone. This is a re-tagged
# release, or a release whose asset name changed shape.
ASSET_404_MAP="$WORK/map-asset-404.txt"
{
  printf 'stubgithub-2.4.0.tar.gz|404|-\n'
  printf 'stubowner/stubgithub|200|%s\n' "$RESPONSES/github-release-stubgithub.json"
} > "$ASSET_404_MAP"

# Nothing answers. The 3 sole-home cases run against the REAL repository with
# this map, so what they prove is that the resolver reaches a pin whose only
# home is a Dockerfile — and fails naming it.
ALL_404_MAP="$WORK/map-all-404.txt"
printf '*|404|-\n' > "$ALL_404_MAP"

# ---------------------------------------------------------------------------
# The drivers.
# ---------------------------------------------------------------------------

# next_case_directory — a fresh directory per case: its own curl log, its own
# copy of the world when it needs to write one.
CASE_DIRECTORY=""
function next_case_directory() {
  CASE_NUMBER=$((CASE_NUMBER + 1))
  CASE_DIRECTORY="$WORK/case-${CASE_NUMBER}"
  mkdir -p "$CASE_DIRECTORY"
}

# run_resolver <map> <root> [KEY=VALUE ...] -- <resolver argv ...>
#
# Runs the REAL file, directly, so its shebang and its executable bit are part
# of what is under test. stdout and stderr are kept apart: the record the
# resolver prints is data, and a case that read a log line as a version would
# pass on a resolver that printed nothing.
#
# stdin is /dev/null. A resolver that read the terminal would behave differently
# in a workflow than in this run, and that difference is exactly what a hermetic
# case must not have.
function run_resolver() {
  local map="$1" root="$2"
  shift 2
  next_case_directory
  local log="$CASE_DIRECTORY/curl.log"
  local errors="$CASE_DIRECTORY/stderr.txt"
  : > "$log"
  : > "$errors"

  local -a environment
  environment=(
    "PATH=$SANDBOX_PATH"
    "STUB_CURL_MAP=$map"
    "STUB_CURL_LOG=$log"
    "UPSTREAM_PROJECT_ROOT=$root"
    "${EDEN_SECRET_NAME}=${EDEN_SECRET_VALUE}"
  )
  while [[ "$#" -gt 0 && "$1" != "--" ]]; do
    environment+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift

  RESOLVER_STATUS=0
  RESOLVER_STDOUT="$(env "${environment[@]}" bash "$RESOLVER" "$@" < /dev/null 2> "$errors")" \
    || RESOLVER_STATUS=$?
  RESOLVER_STDERR="$(cat "$errors")"
  CURL_LOG="$(cat "$log")"
}

# assert_resolves <check name> <pin> <want record> [note...]
#
# The record AND the status, as 1 check. A resolver that exits non-zero after
# printing the right line has not resolved anything, and a caller reading only
# the line would write a bump out of a failed run.
function assert_resolves() {
  local name="$1" pin="$2" want="$3"
  shift 3
  if [[ "$RESOLVER_STATUS" -ne 0 ]]; then
    fail_check "$name" \
      "the resolver exited ${RESOLVER_STATUS} resolving ${pin}" \
      "want: ${want}" \
      "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
      "stderr was:" "${RESOLVER_STDERR:-<none>}" \
      "the urls it asked for:" "${CURL_LOG:-<none>}" "$@"
  elif [[ "$RESOLVER_STDOUT" != "$want" ]]; then
    fail_check "$name" \
      "want: ${want}" \
      "got:  ${RESOLVER_STDOUT:-<no output>}" \
      "the urls it asked for:" "${CURL_LOG:-<none>}" "$@"
  else
    pass_check "$name"
  fi
}

# assert_resolver_failed_naming <check name> <needle...>
#
# The status AND every name, as 1 check. See the header: the resolver is absent
# today, so a bare status assertion passes against a file that does not exist.
function assert_resolver_failed_naming() {
  local name="$1"
  shift
  local combined="${RESOLVER_STDOUT}
${RESOLVER_STDERR}"
  local needle missing_names=""
  for needle in "$@"; do
    if ! grep -qF -- "$needle" <<< "$combined"; then
      missing_names="${missing_names:+${missing_names}
}${needle}"
    fi
  done
  if [[ "$RESOLVER_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status" \
      "got:  0 — the resolver reported success over an upstream it could not read" \
      "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
      "stderr was:" "${RESOLVER_STDERR:-<none>}" \
      "a resolver that swallows a failed fetch writes a bump out of nothing"
  elif [[ -n "$missing_names" ]]; then
    fail_check "$name" \
      "the resolver exited ${RESOLVER_STATUS} and its message never names:" "$missing_names" \
      "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
      "stderr was:" "${RESOLVER_STDERR:-<none>}" \
      "the reader of a 09:00 Monday run has no author watching it, and a status with" \
      "no name tells them nothing"
  else
    pass_check "$name"
  fi
}

# fixture_world <name> — a fresh copy of the miniature repository, so a case
# that writes cannot reach the fixture and the next case starts from the same
# bytes.
function fixture_world() {
  local name="$1"
  local world="$WORK/world-${name}"
  mkdir -p "$world"
  cp -R "$FIXTURE_WORLD/." "$world/"
  printf '%s' "$world"
}

# line_holding <text> <needle> — the first line of the text that holds the
# needle, or the empty string.
function line_holding() {
  awk -v needle="$2" 'index($0, needle) > 0 { print; exit }' <<< "$1"
}

# value_after <text> <marker> — what follows `<marker> ` on the first line that
# starts with it, trimmed. `branch: ci/weekly-bumps-2026-08-17` -> the branch.
function value_after() {
  awk -v marker="$2" '
    index($0, marker) == 1 {
      value = substr($0, length(marker) + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' <<< "$1"
}

# run_notifier_with_labels <issue directory> [KEY=VALUE ...] -- <argv ...>
#
# The notifier, against a gh whose issue world is keyed BY LABEL. A stub with 1
# issue file answers the nightly query and the weekly query with the same set,
# and could not tell a notifier that honours its label parameter apart from one
# that ignores it.
function run_notifier_with_labels() {
  local issues="$1"
  shift
  next_case_directory
  local calls="$CASE_DIRECTORY/gh-calls.log"
  : > "$calls"
  printf '[{"name":"%s"},{"name":"%s"}]\n' "$NIGHTLY_LABEL" "$WEEKLY_LABEL" \
    > "$CASE_DIRECTORY/labels.json"

  local -a environment
  environment=(
    "PATH=$SANDBOX_PATH"
    "GH_TOKEN=stub-token"
    "GITHUB_TOKEN="
    "GITHUB_REPOSITORY=gophersys/.devcontainer"
    "GITHUB_SERVER_URL=https://github.com"
    "GITHUB_RUN_ID=17"
    "GITHUB_WORKFLOW=weekly-bumps"
    "STUB_GH_LOG=$calls"
    "STUB_GH_ISSUES_BY_LABEL=$issues"
    "STUB_GH_LABELS=$CASE_DIRECTORY/labels.json"
    "STUB_GH_BODY_LOG=$CASE_DIRECTORY/bodies.txt"
  )
  while [[ "$#" -gt 0 && "$1" != "--" ]]; do
    environment+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift

  NOTIFY_STATUS=0
  NOTIFY_OUTPUT="$(env "${environment[@]}" bash "$NOTIFIER" "$@" < /dev/null 2>&1)" \
    || NOTIFY_STATUS=$?
  GH_CALLS="$(cat "$calls")"
}

# closed_numbers — the issue number of every `gh issue close` call, in order.
function closed_numbers() {
  awk '$1 == "gh" && $2 == "issue" && $3 == "close" { print $4 }' <<< "$GH_CALLS"
}

# calls_named <prefix> — how many logged gh calls start with <prefix>. awk and
# not `grep -c`: 0 matches is the answer 2 clauses below are asking for, and
# grep exits 1 on it.
function calls_named() {
  awk -v needle="$1" 'index($0, needle) == 1 { total++ } END { print total + 0 }' <<< "$GH_CALLS"
}

# issue_world <name> <label> <issues json> [<label> <issues json>...] — a
# directory of `<label>.json` worlds. A label with no file holds no open issue.
function issue_world() {
  local name="$1"
  shift
  local directory="$WORK/issues-${name}"
  mkdir -p "$directory"
  while [[ "$#" -ge 2 ]]; do
    printf '%s\n' "$2" > "${directory}/${1}.json"
    shift 2
  done
  printf '%s' "$directory"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 0. THE HARNESS ITSELF
# ===========================================================================

if [[ -z "$MISSING_TOOLS" ]]; then
  pass_check "the_tools_these_cases_need_are_on_this_host"
else
  fail_check "the_tools_these_cases_need_are_on_this_host" \
    "absent:" "$MISSING_TOOLS" \
    "every case below would fail for a reason that says nothing about the resolver," \
    "and a skip here would be a green result that resolved no upstream at all"
fi

# THE SENTINEL. Every case rests on this: if `curl` under the sandbox PATH is
# the real one, these cases reach the actual internet, and a green run would
# mean the upstreams answered rather than that the resolver read them correctly.
# This repository has shipped the mirror of this defect — a probe that ran in a
# shell already holding what it claimed to have removed.
resolved_curl="$(env PATH="$SANDBOX_PATH" bash -c 'command -v curl' || true)"
if [[ "$resolved_curl" == "${STUB_BIN}/curl" ]]; then
  pass_check "curl_under_the_sandbox_path_is_the_stub_and_not_the_real_one"
else
  fail_check "curl_under_the_sandbox_path_is_the_stub_and_not_the_real_one" \
    "PATH=${SANDBOX_PATH}" \
    "resolves curl at: ${resolved_curl:-<nowhere>}" \
    "want: ${STUB_BIN}/curl" \
    "a real curl here would reach the network, and every green case below would" \
    "mean the upstream answered and not that the resolver read it"
fi

resolved_gh="$(env PATH="$SANDBOX_PATH" bash -c 'command -v gh' || true)"
if [[ "$resolved_gh" == "${STUB_BIN}/gh" ]]; then
  pass_check "gh_under_the_sandbox_path_is_the_stub_and_not_the_real_one"
else
  fail_check "gh_under_the_sandbox_path_is_the_stub_and_not_the_real_one" \
    "PATH=${SANDBOX_PATH}" \
    "resolves gh at: ${resolved_gh:-<nowhere>}" \
    "want: ${STUB_BIN}/gh" \
    "a real gh would reach the API with a stub token"
fi

# The counter-stimulus for the stub: it serves what the map names, it fails a
# URL the map does not name, and it reports a 404 the way curl -f does. If it
# answered anything to everything, every case below would be green over nothing.
stub_probe_directory="$WORK/stub-probe"
mkdir -p "$stub_probe_directory"
stub_status=0
stub_output="$(env PATH="$SANDBOX_PATH" STUB_CURL_MAP="$BASE_MAP" \
  curl -fsSL "https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json" 2>&1)" \
  || stub_status=$?
if [[ "$stub_status" -eq 0 ]] && grep -qF -- '"version": "3.41.7"' <<< "$stub_output"; then
  pass_check "counter_stimulus_the_stub_serves_the_document_the_map_names"
else
  fail_check "counter_stimulus_the_stub_serves_the_document_the_map_names" \
    "want: the flutter release index, at exit 0" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}"
fi

stub_status=0
stub_output="$(env PATH="$SANDBOX_PATH" STUB_CURL_MAP="$BASE_MAP" \
  curl -fsSL "https://example.invalid/nothing-describes-this" 2>&1)" || stub_status=$?
if [[ "$stub_status" -eq 64 ]]; then
  pass_check "counter_stimulus_the_stub_refuses_a_url_no_row_describes"
else
  fail_check "counter_stimulus_the_stub_refuses_a_url_no_row_describes" \
    "want: exit 64 on a url the map does not name" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}" \
    "a stub that answered a request it did not understand would hand a case a" \
    "success for a fetch that never happened"
fi

stub_status=0
stub_output="$(env PATH="$SANDBOX_PATH" STUB_CURL_MAP="$ALL_404_MAP" \
  curl -fsSL "https://example.invalid/anything" 2>&1)" || stub_status=$?
if [[ "$stub_status" -eq 22 ]]; then
  pass_check "counter_stimulus_the_stub_reports_a_404_the_way_curl_does"
else
  fail_check "counter_stimulus_the_stub_reports_a_404_the_way_curl_does" \
    "want: exit 22, the status curl -f returns for an HTTP error" \
    "got:  exit ${stub_status}, output:" "${stub_output:-<none>}"
fi

# The 5 fixture assets are the bytes the 5 digest literals name. Without this
# guard an edit to a fixture makes 5 resolution checks red and none of them says
# why.
digest_mismatches=""
for pair in \
  "stubgithub-2.4.0.tar.gz|$ASSET_DIGEST_STUBGITHUB" \
  "stubgo-1.26.5.tar.gz|$ASSET_DIGEST_STUBGO" \
  "stubk8s-1.35.4.bin|$ASSET_DIGEST_STUBK8S" \
  "stubtailscale-1.96.4.tgz|$ASSET_DIGEST_STUBTAILSCALE" \
  "stubflutter-3.41.7.tar.xz|$ASSET_DIGEST_STUBFLUTTER"; do
  asset_name="${pair%%|*}"
  want_digest="${pair#*|}"
  if [[ ! -f "$ASSETS/$asset_name" ]]; then
    digest_mismatches="${digest_mismatches:+${digest_mismatches}
}${asset_name}: absent"
    continue
  fi
  got_digest="$(sha256sum "$ASSETS/$asset_name" | awk '{ print $1 }')"
  if [[ "$got_digest" != "$want_digest" ]]; then
    digest_mismatches="${digest_mismatches:+${digest_mismatches}
}${asset_name}: want ${want_digest}, got ${got_digest}"
  fi
done
if [[ -z "$digest_mismatches" ]]; then
  pass_check "every_fixture_asset_matches_the_literal_digest_this_file_expects"
else
  fail_check "every_fixture_asset_matches_the_literal_digest_this_file_expects" \
    "$digest_mismatches" \
    "the literals in this file are what the resolution cases below want; an asset" \
    "whose bytes moved makes those cases red for a reason that is not the resolver"
fi

oci_digest="$(sha256sum "$RESPONSES/oci-index-ubuntu.json" | awk '{ print $1 }')"
assert_equal "the_oci_index_fixture_matches_the_literal_digest_this_file_expects" \
  "$OCI_INDEX_DIGEST" "$oci_digest" \
  "the digest of a manifest LIST is the sha256 of its own bytes, so this number is" \
  "the version the oci-index datasource must return"

# ===========================================================================
# 1. THE RESOLVER IS THERE, AND IT IS A STANDALONE BASH PROGRAM
# ===========================================================================
if [[ -f "$RESOLVER" && -x "$RESOLVER" ]]; then
  pass_check "the_resolver_exists_and_is_executable"
else
  fail_check "the_resolver_exists_and_is_executable" \
    "want: an executable file at ${RESOLVER_RELATIVE}" \
    "got:  $( [[ -f "$RESOLVER" ]] && printf 'a file that is not executable' || printf 'no file' )" \
    "every case below runs it, so its executable bit is part of the contract"
fi

# ===========================================================================
# 2. EACH DATASOURCE READS A VERSION, AND A DIGEST OF THE BYTES IT FETCHED
# ===========================================================================
#
# 1 stub pin per datasource, 13 rows for the 11 fetching datasources: 3 of them
# go through github-release, because the 3 questions that datasource has to
# answer are different — a pin spelled without a `v`, a pin spelled with one,
# and a pin that is already current.
#
# The 5 rows carrying a digest are the ones whose governed file fetches an
# asset. The other 6 pins carry no digest row anywhere, which is the shape about
# 30 of the 56 real pins have, and the resolver says so with `-` rather than
# inventing a number nothing compares.
#
# The fields are: <check name>|<pin>|<version>|<digest>|<note>
RESOLUTION_CASES=(
  "github_release_reads_the_newest_tag_and_the_asset_digest|STUBGITHUB_VERSION|2.4.0|${ASSET_DIGEST_STUBGITHUB}|the tag is v2.4.0 and the pin is spelled without a v, so the v is stripped; the digest is of the asset the governed file fetches for 2.4.0"
  "github_release_keeps_the_v_a_pin_is_spelled_with|STUBVPREFIX_VERSION|v0.2.0|${NO_DIGEST}|gophersys/cictl pins v0.1.0, so a resolver that always strips the v writes a version that no release matches"
  "github_release_reports_a_pin_that_is_already_current|STUBCURRENT_VERSION|6.0.0|${NO_DIGEST}|resolving is not bumping: the pin already holds the newest tag and the value is still reported"
  "pypi_reads_the_version_of_the_newest_release|STUBPYPI_VERSION|3.1.4|${NO_DIGEST}|the pypi json carries info.version; pipx installs it, so there is no asset to digest"
  "npm_reads_the_dist_tag_latest|STUBNPM_VERSION|4.2.1|${NO_DIGEST}|the registry document carries dist-tags.latest"
  "apt_reads_the_upstream_version_without_the_epoch_or_the_revision|STUBAPT_VERSION|5.9|${NO_DIGEST}|the archive publishes 1:5.9-6ubuntu2, and 5.9 is what the tool reports about itself and what the smoke test compares"
  "go_dl_reads_the_newest_stable_release_and_the_archive_digest|STUBGO_VERSION|1.26.5|${ASSET_DIGEST_STUBGO}|the index spells it go1.26.5 and the pin is spelled 1.26.5"
  "node_dist_reads_the_newest_lts_release|STUBNODE_VERSION|24.15.0|${NO_DIGEST}|v25.1.0 is newer and is not an LTS line; nvm fetches node itself, so there is no asset here"
  "oci_index_reads_the_index_digest_the_tag_holds|STUBOCI_REF|sha256:${OCI_INDEX_DIGEST}|${NO_DIGEST}|the digest of a manifest list is the sha256 of its own bytes, and a per-platform digest would pin the wrong thing"
  "k8s_dl_reads_the_stable_channel_and_the_binary_digest|STUBK8S_VERSION|1.35.4|${ASSET_DIGEST_STUBK8S}|the channel file holds v1.35.4 and the pin is spelled 1.35.4"
  "tailscale_pkgs_reads_the_stable_package_and_its_digest|STUBTAILSCALE_VERSION|1.96.4|${ASSET_DIGEST_STUBTAILSCALE}|the package index carries Version"
  "flutter_releases_reads_the_stable_channel_and_the_archive_digest|STUBFLUTTER_VERSION|3.41.7|${ASSET_DIGEST_STUBFLUTTER}|the beta release is newer and is not the stable channel"
  "eden_manifest_reads_the_value_eden_pins|STUBEDEN_VERSION|2.1.212|${NO_DIGEST}|eden is the one decision point for a harness version, so this datasource mirrors it rather than resolving the harness upstream"
)

RESOLUTION_WORLD="$(fixture_world "resolution")"
for case_row in "${RESOLUTION_CASES[@]}"; do
  IFS='|' read -r case_name case_pin case_version case_digest case_note <<< "$case_row"
  run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "$case_pin"
  assert_resolves "$case_name" "$case_pin" "${case_version}|${case_digest}" "$case_note"
done

# -------- the digest is of the NEW version's asset, and it is re-proven ------
# The record check above already fails a resolver that copied the pinned digest,
# because `dddd...` is not any asset's. This pair reads the other side of it:
# WHICH url the resolver asked for, and how many times.
#
# The second fetch is the re-proof: the resolver runs _build/fetch-verified.sh
# against the same url with the digest it just computed, so the ONE verifier
# every image download goes through has agreed before anything is written. What
# this check reads is the fetch, not the verifier — see NOT COVERED in the phase
# report.
run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "STUBGITHUB_VERSION"
asset_url="https://github.com/stubowner/stubgithub/releases/download/v2.4.0/stubgithub-2.4.0.tar.gz"
asset_fetches="$(awk -v needle="$asset_url" '$0 == needle { total++ } END { print total + 0 }' <<< "$CURL_LOG")"
if [[ "$asset_fetches" -ge 1 ]]; then
  pass_check "the_resolver_fetches_the_asset_of_the_version_it_just_resolved"
else
  fail_check "the_resolver_fetches_the_asset_of_the_version_it_just_resolved" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "want at least 1 fetch of: ${asset_url}" \
    "the digest has to be of the bytes the BUILD will fetch, and the url of those" \
    "bytes lives in the governed file with the new version substituted in"
fi

if [[ "$asset_fetches" -ge 2 ]]; then
  pass_check "the_resolver_fetches_the_asset_again_to_re_prove_the_digest_it_computed"
else
  fail_check "the_resolver_fetches_the_asset_again_to_re_prove_the_digest_it_computed" \
    "the asset was fetched ${asset_fetches} time(s):" "${CURL_LOG:-<none>}" \
    "the resolver computes the digest and then runs _build/fetch-verified.sh against" \
    "the same url with that value, so the ONE verifier every image download goes" \
    "through has agreed before a single line is written"
fi

# 2 conditions, 1 check, on purpose. "the old url was not fetched" is TRUE of a
# run that fetched nothing at all — which is every run of this file until the
# resolver exists — so the check also demands that the new one WAS fetched.
old_asset_url="https://github.com/stubowner/stubgithub/releases/download/v2.3.0/stubgithub-2.3.0.tar.gz"
if [[ "$asset_fetches" -ge 1 ]] && ! grep -qF -- "$old_asset_url" <<< "$CURL_LOG"; then
  pass_check "the_resolver_never_fetches_the_asset_of_the_version_it_is_replacing"
else
  fail_check "the_resolver_never_fetches_the_asset_of_the_version_it_is_replacing" \
    "the asset of 2.4.0 was fetched ${asset_fetches} time(s), and the urls were:" \
    "${CURL_LOG:-<none>}" \
    "digesting the OLD asset produces a digest that matches bytes nobody will install," \
    "and a run that fetched nothing satisfies the second half of this check by itself"
fi

# ===========================================================================
# 3. AN UNREACHABLE UPSTREAM FAILS, AND NAMES THE PIN
# ===========================================================================
#
# Loudly, and never `|| true`. A weekly run that swallowed a failed fetch would
# open a pull request bumping the pins it happened to reach, and the reader
# would take the absence of the others as "nothing moved".

run_resolver "$INDEX_404_MAP" "$RESOLUTION_WORLD" -- "STUBGITHUB_VERSION"
assert_resolver_failed_naming "a_404_index_fails_naming_the_pin" "STUBGITHUB_VERSION"

run_resolver "$ASSET_404_MAP" "$RESOLUTION_WORLD" -- "STUBGITHUB_VERSION"
assert_resolver_failed_naming "a_resolved_version_with_no_fetchable_asset_fails_naming_the_pin" \
  "STUBGITHUB_VERSION"

run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" "${EDEN_SECRET_NAME}=" -- "STUBEDEN_VERSION"
assert_resolver_failed_naming "an_absent_eden_credential_fails_naming_the_pin_and_the_secret" \
  "STUBEDEN_VERSION" "$EDEN_SECRET_NAME"

# The 3 pins whose only home is a Dockerfile, against the REAL repository. A
# resolver that reads versions.env alone cannot see them at all, and this is the
# case that says so: with nothing answering, each one must fail NAMING ITSELF.
for sole_pin in "${SOLE_HOME_PINS[@]}"; do
  run_resolver "$ALL_404_MAP" "$REPO_ROOT" -- "$sole_pin"
  assert_resolver_failed_naming "an_unreachable_upstream_names_the_sole_home_pin_${sole_pin}" \
    "$sole_pin"
done

# ===========================================================================
# 4. THE DRY RUN COMPOSES A PULL REQUEST AND WRITES NOTHING
# ===========================================================================
DRY_RUN_WORLD="$(fixture_world "dry-run")"
git -C "$DRY_RUN_WORLD" init --quiet
git -C "$DRY_RUN_WORLD" add --all
git -C "$DRY_RUN_WORLD" -c user.email="test@example.invalid" -c user.name="test" \
  -c commit.gpgsign=false commit --quiet --message "the fixture world, before the dry run"

run_resolver "$BASE_MAP" "$DRY_RUN_WORLD" -- "--dry-run"
porcelain="$(git -C "$DRY_RUN_WORLD" status --porcelain)"

# 2 conditions, 1 check, on purpose. An empty porcelain is what a dry run that
# wrote nothing leaves, and it is ALSO what a resolver that does not exist
# leaves. Without the status, this check passes today with no file on disk.
#
# The status also carries the frozen pin: STUBFROZEN_VERSION takes no-autobump,
# and the map describes no upstream for it, so a dry run that tried to resolve
# it would ask the stub for a url no row names and die at 64.
if [[ "$RESOLVER_STATUS" -eq 0 && -z "$porcelain" ]]; then
  pass_check "the_dry_run_exits_zero_and_leaves_the_worktree_clean"
else
  fail_check "the_dry_run_exits_zero_and_leaves_the_worktree_clean" \
    "want: exit 0 and an empty git status --porcelain" \
    "got:  exit ${RESOLVER_STATUS}, porcelain:" "${porcelain:-<empty>}" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}"
fi

assert_contains "the_dry_run_lists_the_pin_that_moved_with_both_versions" \
  "$RESOLVER_STDOUT" "bump: STUBGITHUB_VERSION 2.3.0 -> 2.4.0" \
  "the reader of a weekly pull request decides from this list, so it carries the" \
  "pin, the value it holds and the value it would hold" \
  "stderr was:" "${RESOLVER_STDERR:-<none>}"

# The 2 negative checks below each carry the same second condition: the dry run
# has to have RUN. "no bump line for STUBCURRENT_VERSION" is true of an empty
# output, and an empty output is what a resolver that does not exist produces.
if [[ "$RESOLVER_STATUS" -eq 0 ]] && ! grep -qF -- "bump: STUBCURRENT_VERSION" <<< "$RESOLVER_STDOUT"; then
  pass_check "the_dry_run_lists_no_bump_for_a_pin_that_is_already_current"
else
  fail_check "the_dry_run_lists_no_bump_for_a_pin_that_is_already_current" \
    "the dry run exited ${RESOLVER_STATUS}, and its output was:" "${RESOLVER_STDOUT:-<none>}" \
    "STUBCURRENT_VERSION holds 6.0.0 and the newest release is 6.0.0; a bump line for" \
    "it would open a pull request that changes nothing every Monday"
fi

if [[ "$RESOLVER_STATUS" -eq 0 ]] && ! grep -qF -- "bump: STUBFROZEN_VERSION" <<< "$RESOLVER_STDOUT"; then
  pass_check "the_dry_run_lists_no_bump_for_a_no_autobump_pin"
else
  fail_check "the_dry_run_lists_no_bump_for_a_no_autobump_pin" \
    "the dry run exited ${RESOLVER_STATUS}, and its output was:" "${RESOLVER_STDOUT:-<none>}" \
    "the row states why that pin is not resolved, and a dry run that bumped it anyway" \
    "would make the stated reason a comment nothing honours"
fi

dry_run_branch="$(value_after "$RESOLVER_STDOUT" "branch:")"
if [[ -n "$dry_run_branch" ]]; then
  pass_check "the_dry_run_names_the_branch_it_would_push"
else
  fail_check "the_dry_run_names_the_branch_it_would_push" \
    "the output holds no line starting with: branch:" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}"
fi

dry_run_title="$(value_after "$RESOLVER_STDOUT" "title:")"
if [[ -n "$dry_run_title" ]]; then
  pass_check "the_dry_run_names_the_title_it_would_open_the_pull_request_with"
else
  fail_check "the_dry_run_names_the_title_it_would_open_the_pull_request_with" \
    "the output holds no line starting with: title:" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}"
fi

dry_run_body="$(awk 'body { print } /^body:/ { body = 1 }' <<< "$RESOLVER_STDOUT")"
assert_contains "the_dry_run_body_names_the_pin_that_moved" \
  "$dry_run_body" "STUBGITHUB_VERSION" \
  "the body is what a human reads in the pull request, and a body that names no pin" \
  "asks them to read the diff to find out what the change is" \
  "the whole output was:" "${RESOLVER_STDOUT:-<none>}"

# ===========================================================================
# 5. A GREEN WEEKLY DOES NOT CLOSE THE NIGHTLY ISSUE
# ===========================================================================
#
# The notifier files under 1 label, and until this change that label is a
# literal inside the script. The weekly workflow is the second scheduled run of
# this repository, so it needs its own: a green Monday must not close the issue
# the nightly scan opened about a CRITICAL CVE, and a red Monday must not
# comment on it.
#
#   ISSUE_LABEL   the label the notifier files, finds and closes under.
#                 Default ci-nightly-red, so the nightly keeps its behaviour
#                 with no edit to the workflow that calls it.
#
# The stub answers `issue list` out of a world keyed BY LABEL, so a notifier
# that ignores the parameter reports the nightly's issues to the weekly's query
# and the check below names the issue it closed.

nightly_only="$(issue_world "nightly-only" "$NIGHTLY_LABEL" '[{"number":77}]')"
run_notifier_with_labels "$nightly_only" "ISSUE_LABEL=${WEEKLY_LABEL}" -- --resolve
weekly_closes="$(closed_numbers)"
if [[ "$NOTIFY_STATUS" -eq 0 && -z "$weekly_closes" ]]; then
  pass_check "a_green_weekly_closes_no_nightly_issue"
else
  fail_check "a_green_weekly_closes_no_nightly_issue" \
    "want: exit 0 and 0 close calls — no issue carries ${WEEKLY_LABEL}" \
    "got:  exit ${NOTIFY_STATUS}, and it closed:" "${weekly_closes:-<nothing>}" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}" \
    "#77 is the nightly scan's open issue about a CRITICAL CVE, and a green bump run" \
    "retiring it is a red this repository stops being told about"
fi

both_labels="$(issue_world "both" \
  "$NIGHTLY_LABEL" '[{"number":77}]' \
  "$WEEKLY_LABEL" '[{"number":91},{"number":92}]')"
run_notifier_with_labels "$both_labels" "ISSUE_LABEL=${WEEKLY_LABEL}" -- --resolve
weekly_closes="$(closed_numbers)"
if [[ "$NOTIFY_STATUS" -eq 0 && "$(sort <<< "$weekly_closes")" == "91
92" ]]; then
  pass_check "a_green_weekly_closes_every_open_issue_of_its_own_label"
else
  fail_check "a_green_weekly_closes_every_open_issue_of_its_own_label" \
    "want: exit 0, and #91 and #92 closed and nothing else" \
    "got:  exit ${NOTIFY_STATUS}, and it closed:" "${weekly_closes:-<nothing>}" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "2 issues can exist whenever 2 runs raced past the search, and the parameter must" \
    "not cost the close-every-one rule the nightly already has"
fi

run_notifier_with_labels "$nightly_only" "ISSUE_LABEL=${WEEKLY_LABEL}" -- "resolve STUBGITHUB_VERSION: failure"
weekly_creates="$(calls_named "gh issue create")"
labelled_create="$(awk -v needle="--label ${WEEKLY_LABEL}" 'index($0, "gh issue create") == 1 && index($0, needle) > 0 { total++ } END { print total + 0 }' <<< "$GH_CALLS")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$weekly_creates" -eq 1 && "$labelled_create" -eq 1 ]]; then
  pass_check "a_red_weekly_files_its_issue_under_its_own_label"
else
  fail_check "a_red_weekly_files_its_issue_under_its_own_label" \
    "want: exit 0, 1 issue create, and that create carrying --label ${WEEKLY_LABEL}" \
    "got:  exit ${NOTIFY_STATUS}, ${weekly_creates} create call(s), ${labelled_create} of them labelled" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}" \
    "a weekly failure filed under ci-nightly-red comments on the scan's issue and" \
    "reads as the scan going red"
fi

# And the label the weekly needs is created when the repository does not carry
# it. `gh issue create --label` FAILS on a label that does not exist, and that
# failure would arrive carrying the red it was meant to report.
next_case_directory
no_labels="$CASE_DIRECTORY/no-labels.json"
printf '[]\n' > "$no_labels"
run_notifier_with_labels "$nightly_only" \
  "ISSUE_LABEL=${WEEKLY_LABEL}" "STUB_GH_LABELS=${no_labels}" -- "resolve STUBGITHUB_VERSION: failure"
weekly_label_creates="$(calls_named "gh label create ${WEEKLY_LABEL}")"
if [[ "$NOTIFY_STATUS" -eq 0 && "$weekly_label_creates" -eq 1 ]]; then
  pass_check "a_red_weekly_creates_its_label_before_it_files"
else
  fail_check "a_red_weekly_creates_its_label_before_it_files" \
    "want: exit 0 and 1 'label create ${WEEKLY_LABEL}' call" \
    "got:  exit ${NOTIFY_STATUS}, ${weekly_label_creates} label create call(s)" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

# The other direction, and it is the ratchet on the nightly: with no ISSUE_LABEL
# in the environment the notifier still behaves exactly as it does today. A
# parameter that changed the default would retire the nightly's own mechanism on
# the day it landed.
run_notifier_with_labels "$nightly_only" -- --resolve
default_closes="$(closed_numbers)"
if [[ "$NOTIFY_STATUS" -eq 0 && "$default_closes" == "77" ]]; then
  pass_check "with_no_label_in_the_environment_the_notifier_still_closes_the_nightly_issue"
else
  fail_check "with_no_label_in_the_environment_the_notifier_still_closes_the_nightly_issue" \
    "want: exit 0 and #77 closed — the default label is ${NIGHTLY_LABEL}" \
    "got:  exit ${NOTIFY_STATUS}, and it closed:" "${default_closes:-<nothing>}" \
    "the gh calls were:" "${GH_CALLS:-<none>}" \
    "output was:" "${NOTIFY_OUTPUT:-<none>}"
fi

test_summary "$TEST_NAME"
