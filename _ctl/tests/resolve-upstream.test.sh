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
#           <version>|<row>=<sha256> [<row>=<sha256> ...]
#
#       <version>  spelled the way the pin's CURRENT value is spelled: a leading
#                  `v` is kept when the current value carries one (cictl pins
#                  v0.6.0) and stripped when it does not (gh pins 2.90.0). An
#                  apt version drops the epoch and the debian revision, because
#                  that is what the tool reports about itself and what the smoke
#                  test compares.
#       <row>=...  1 pair per `<tool>_SHA256_<ARCH>` row beside the pin: the row
#                  NAME, and the digest of the bytes the GOVERNED FILE fetches
#                  for that new version ON THE ARM THAT ROW ANSWERS FOR. The URL
#                  is read out of the file that performs the download, never out
#                  of the table, because a second URL home lets a resolver
#                  compute a correct digest of the wrong asset. `-` when the pin
#                  carries no digest row at all, which about 30 of the 56 real
#                  pins do not (go install, corepack, pipx).
#
#       THE ROW NAME IS HALF THE RECORD, and the half a bare digest could not
#       carry. A pin whose governed file names 2 case arms has 2 digest rows,
#       and the writer refuses a partial set — so a record that carried 1
#       unlabelled number could not say WHICH row it answered for, and the
#       reader that put it somewhere would have picked the amd64 one. Every
#       resolution case below therefore asserts the name beside the value.
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

# The second world, and it is separate because it is BROKEN BY DESIGN: 1 digest
# row claimed by 2 case arms that resolve to 2 different assets. Every aggregate
# run over a world holding that pin fails, and the cases that assert a clean
# --dry-run and a clean --apply need a world where every row resolves.
ONE_ROW_WORLD="$FIXTURE_ROOT/one-row-two-assets"

# The digest of each fixture asset, as a LITERAL. See the header: a test that
# computes the value it checks agrees with any bytes. The guard below reads the
# files and holds them to these 10 numbers, so an edit to a fixture asset turns
# 1 named check red instead of quietly agreeing with itself.
ASSET_DIGEST_STUBGITHUB="e9f2832e77a27bb6de567fecd8039919c51ba0ed73969ea5380cdfcf844ae0cb"
ASSET_DIGEST_STUBGO="17a98a1b9b1274facea20e77bd164b1746ffe5ae0f91a357d7c1f24530d62f68"
ASSET_DIGEST_STUBK8S="bccb01f0e57ae6396b3160b6c97d5222b9c8ad7f9646699b59a71efca8a5d420"
ASSET_DIGEST_STUBTAILSCALE="cc5f45fc6feea409811c787853fbc0592749b913fbe13e6bf8fa2d1226e9cbbd"
ASSET_DIGEST_STUBFLUTTER="25639dfbf55924ec4b153f8935d20178fa554a5b5190f8613206f7bcf67a2a5a"

# The 5 per-platform assets. The 2 halves of a dual-arch pin carry DIFFERENT
# bytes on purpose: with 1 asset serving both arms, a resolver that fetched the
# amd64 url twice would produce 2 equal digests and every check below would
# agree with it.
ASSET_DIGEST_STUBDUAL_AMD64="791cfaaa8adeb264a81d1c066decb0ae744171c4e63c4b10f491a179a5d71c40"
ASSET_DIGEST_STUBDUAL_ARM64="ee7724f82f736bf19dcb53da446d4648cbfaa0826ad77600d9dd4047ad56363d"
ASSET_DIGEST_STUBSHARED_AMD64="f8543e6d6007e31fb6e5a9b21143db948188226eeb8be5c344cc1da40229621b"
ASSET_DIGEST_STUBSHARED_ARM64="3d6744ee021fb02c2860638571dcab592a51eb05dbfb70b5a2c9baf2ae41e446"
ASSET_DIGEST_STUBNOARCH="089dd314a4e23725420d06e5819b1bc1020671705cc1dabc6b0acdbec7b8250c"

# The digest ROWS those assets answer for. Literals for the same reason the
# digests are: the row name is the half of the record the old contract could not
# express, and a check that read it out of the fixture would agree with a
# resolver that named the sibling.
ROW_STUBDUAL_AMD64="STUBDUAL_SHA256_AMD64"
ROW_STUBDUAL_ARM64="STUBDUAL_SHA256_ARM64"
ROW_STUBSHARED_AMD64="STUBSHARED_SHA256_AMD64"
ROW_STUBSHARED_ARM64="STUBSHARED_SHA256_ARM64"
ROW_STUBNOARCH="STUBNOARCH_SHA256_NOARCH"

# The stale evidence the arm64 row of STUBDUAL carries in the fixture: an
# upstream checksum file of the version being bumped AWAY from. After a bump no
# row may still claim it.
STALE_ARM64_EVIDENCE_URL="https://github.com/stubowner/stubdual/releases/download/v1.2.2/checksums.sha256"

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

# The real pins whose only home is a Dockerfile. A resolver that reads
# versions.env alone cannot see these at all. It was 3 and it is 2:
# CODE_SERVER_VERSION left with the devbox deletion (2026-08-19), and its row
# in _build/upstreams.txt left in the same change — a listing row for a pin no
# home declares is what upstream-coverage.test.sh reports.
SOLE_HOME_PINS=("FLUTTER_VERSION" "ZEPHYR_SDK_VERSION")

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
  printf '# the per-platform assets — 1 row per ARM, keyed on the asset spelling\n'
  printf 'stubdual-1.2.3-linux-x86_64.tar.gz|200|%s\n'  "$ASSETS/stubdual-1.2.3-amd64.tar.gz"
  printf 'stubdual-1.2.3-linux-aarch64.tar.gz|200|%s\n' "$ASSETS/stubdual-1.2.3-arm64.tar.gz"
  printf 'stubshared_Linux_amd64.tar.gz|200|%s\n'       "$ASSETS/stubshared-0.9.1-amd64.tar.gz"
  printf 'stubshared_Linux_arm64.tar.gz|200|%s\n'       "$ASSETS/stubshared-0.9.1-arm64.tar.gz"
  printf 'stubnoarch-7.1.0-any.tar.gz|200|%s\n'         "$ASSETS/stubnoarch-7.1.0.tar.gz"
  # The 2 assets of the one-row-two-assets world. They are served so that a
  # resolver which SWALLOWED the second record would succeed rather than die at
  # the download: the case that reads that refusal must be able to tell a
  # refusal from a 404, and a world where the wrong behaviour also fails proves
  # nothing about which failure it read.
  printf 'stubonerow-1.2.3-linux-x86_64.tar.gz|200|%s\n'  "$ASSETS/stubdual-1.2.3-amd64.tar.gz"
  printf 'stubonerow-1.2.3-linux-aarch64.tar.gz|200|%s\n' "$ASSETS/stubdual-1.2.3-arm64.tar.gz"
  printf '# indexes\n'
  printf 'auth.docker.io|200|%s\n'        "$RESPONSES/oci-registry-token.json"
  printf 'stubowner/stubgithub|200|%s\n'  "$RESPONSES/github-release-stubgithub.json"
  printf 'stubowner/stubvprefix|200|%s\n' "$RESPONSES/github-release-stubvprefix.json"
  printf 'stubowner/stubcurrent|200|%s\n' "$RESPONSES/github-release-stubcurrent.json"
  printf 'stubowner/stubdual|200|%s\n'    "$RESPONSES/github-release-stubdual.json"
  printf 'stubowner/stubshared|200|%s\n'  "$RESPONSES/github-release-stubshared.json"
  printf 'stubowner/stubnoarch|200|%s\n'  "$RESPONSES/github-release-stubnoarch.json"
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
# The 2 MIXED worlds: 1 index is gone and every other row still answers. The
# maps above are all-or-nothing, and an aggregate run over an all-or-nothing map
# cannot show what a failure does to the pins BESIDE it — which is the whole
# question section 5 asks.
#
# Each is the base map with 1 row rewritten, so the 12 rows that answer stay the
# 12 rows every case above already proved. Where the failing row sits in
# _build/upstreams.txt decides what the case can see:
#
#   EARLY  the FIRST row of the table fails, so every mover comes after it —
#          the run has to reach them, and report them.
#   LATE   the 12th row of 17 fails, so 11 movers were resolved before it — the
#          ordering that makes a partial write possible at all.
# ---------------------------------------------------------------------------
EARLY_FAILURE_MAP="$WORK/map-early-failure.txt"
awk -F'|' -v OFS='|' '
  $1 == "stubowner/stubgithub" && $2 == "200" { print $1, "404", "-"; next }
  { print }
' "$BASE_MAP" > "$EARLY_FAILURE_MAP"

LATE_FAILURE_MAP="$WORK/map-late-failure.txt"
awk -F'|' -v OFS='|' '
  $1 == "releases_linux.json" && $2 == "200" { print $1, "404", "-"; next }
  { print }
' "$BASE_MAP" > "$LATE_FAILURE_MAP"

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

# committed_fixture_world <name> — a fixture world under git, every file
# committed, so `git status --porcelain` is empty until the run under test
# writes something. That emptiness is the only evidence a case has that a run
# which failed left the tree alone.
function committed_fixture_world() {
  local name="$1" world
  world="$(fixture_world "$name")"
  git -C "$world" -c init.defaultBranch=main init --quiet
  git -C "$world" add --all
  git -C "$world" -c user.email="test@example.invalid" -c user.name="test" \
    -c commit.gpgsign=false commit --quiet --message "the fixture world, before the run"
  printf '%s' "$world"
}

# empty_version_bump_lines <text> — every reported bump whose NEW value is
# empty: a line carrying `->` with nothing after the last arrow.
#
# This is the smoking gun of a swallowed failure. A pin that could not be
# resolved has no new version, so a run that reports one anyway is reporting the
# nothing it got back from a subshell that died, and `bump: PIN 2.3.0 -> ` is
# what that looks like in a pull request body a human is asked to approve.
function empty_version_bump_lines() {
  awk '
    index($0, "->") > 0 {
      after = $0
      sub(/^.*->[[:space:]]*/, "", after)
      if (after == "") { print }
    }
  ' <<< "$1"
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

# The 2 derived maps are the base map with 1 row rewritten. An awk needle that
# stopped matching — a renamed fixture response, a reordered row — would leave a
# map identical to the base one, and section 5 would then drive 3 cases over a
# world where NOTHING fails and read their green as a resolver that stops. So
# each derived map is held to the same row COUNT and to exactly 1 more 404 than
# the base map has.
derived_map_faults=""
base_map_rows="$(awk 'NF && $0 !~ /^#/ { total++ } END { print total + 0 }' "$BASE_MAP")"
base_map_404s="$(awk -F'|' '$2 == "404" { total++ } END { print total + 0 }' "$BASE_MAP")"
for derived in "EARLY_FAILURE_MAP|$EARLY_FAILURE_MAP" "LATE_FAILURE_MAP|$LATE_FAILURE_MAP"; do
  derived_name="${derived%%|*}"
  derived_map="${derived#*|}"
  derived_rows="$(awk 'NF && $0 !~ /^#/ { total++ } END { print total + 0 }' "$derived_map")"
  derived_404s="$(awk -F'|' '$2 == "404" { total++ } END { print total + 0 }' "$derived_map")"
  if [[ "$derived_rows" -ne "$base_map_rows" || "$derived_404s" -ne $((base_map_404s + 1)) ]]; then
    derived_map_faults="${derived_map_faults:+${derived_map_faults}
}${derived_name}: ${derived_rows} rows and ${derived_404s} 404 row(s); the base map has ${base_map_rows} rows and ${base_map_404s}"
  fi
done
if [[ -z "$derived_map_faults" ]]; then
  pass_check "each_derived_map_turns_exactly_one_row_of_the_base_map_into_a_404"
else
  fail_check "each_derived_map_turns_exactly_one_row_of_the_base_map_into_a_404" \
    "$derived_map_faults" \
    "a needle that matches nothing leaves the base map unchanged, and the aggregate" \
    "failure cases below would then be green over a world in which nothing failed"
fi

# The 10 fixture assets are the bytes the 10 digest literals name. Without this
# guard an edit to a fixture makes the resolution checks red and none of them
# says why.
digest_mismatches=""
for pair in \
  "stubgithub-2.4.0.tar.gz|$ASSET_DIGEST_STUBGITHUB" \
  "stubgo-1.26.5.tar.gz|$ASSET_DIGEST_STUBGO" \
  "stubk8s-1.35.4.bin|$ASSET_DIGEST_STUBK8S" \
  "stubtailscale-1.96.4.tgz|$ASSET_DIGEST_STUBTAILSCALE" \
  "stubflutter-3.41.7.tar.xz|$ASSET_DIGEST_STUBFLUTTER" \
  "stubdual-1.2.3-amd64.tar.gz|$ASSET_DIGEST_STUBDUAL_AMD64" \
  "stubdual-1.2.3-arm64.tar.gz|$ASSET_DIGEST_STUBDUAL_ARM64" \
  "stubshared-0.9.1-amd64.tar.gz|$ASSET_DIGEST_STUBSHARED_AMD64" \
  "stubshared-0.9.1-arm64.tar.gz|$ASSET_DIGEST_STUBSHARED_ARM64" \
  "stubnoarch-7.1.0.tar.gz|$ASSET_DIGEST_STUBNOARCH"; do
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
# Each of those 5 asserts a `<row>=<digest>` PAIR and not a bare number. All 5
# are single-arm pins whose 1 row is the `_AMD64` one, so the name is the part
# of the assertion a wrong resolver fails: a reader that answered for the
# sibling, or that dropped the name it could not choose, is red here rather than
# equal to a digest that happens to match.
#
# The fields are: <check name>|<pin>|<version>|<row>=<digest> ...|<note>
RESOLUTION_CASES=(
  "github_release_reads_the_newest_tag_and_the_asset_digest|STUBGITHUB_VERSION|2.4.0|STUBGITHUB_SHA256_AMD64=${ASSET_DIGEST_STUBGITHUB}|the tag is v2.4.0 and the pin is spelled without a v, so the v is stripped; the digest is of the asset the governed file fetches for 2.4.0, and the pair names the row it answers for"
  "github_release_keeps_the_v_a_pin_is_spelled_with|STUBVPREFIX_VERSION|v0.2.0|${NO_DIGEST}|gophersys/cictl pins v0.6.0, so a resolver that always strips the v writes a version that no release matches"
  "github_release_reports_a_pin_that_is_already_current|STUBCURRENT_VERSION|6.0.0|${NO_DIGEST}|resolving is not bumping: the pin already holds the newest tag and the value is still reported"
  "pypi_reads_the_version_of_the_newest_release|STUBPYPI_VERSION|3.1.4|${NO_DIGEST}|the pypi json carries info.version; pipx installs it, so there is no asset to digest"
  "npm_reads_the_dist_tag_latest|STUBNPM_VERSION|4.2.1|${NO_DIGEST}|the registry document carries dist-tags.latest"
  "apt_reads_the_upstream_version_without_the_epoch_or_the_revision|STUBAPT_VERSION|5.9|${NO_DIGEST}|the archive publishes 1:5.9-6ubuntu2, and 5.9 is what the tool reports about itself and what the smoke test compares"
  "go_dl_reads_the_newest_stable_release_and_the_archive_digest|STUBGO_VERSION|1.26.5|STUBGO_SHA256_AMD64=${ASSET_DIGEST_STUBGO}|the index spells it go1.26.5 and the pin is spelled 1.26.5"
  "node_dist_reads_the_newest_lts_release|STUBNODE_VERSION|24.15.0|${NO_DIGEST}|v25.1.0 is newer and is not an LTS line; nvm fetches node itself, so there is no asset here"
  "oci_index_reads_the_index_digest_the_tag_holds|STUBOCI_REF|sha256:${OCI_INDEX_DIGEST}|${NO_DIGEST}|the digest of a manifest list is the sha256 of its own bytes, and a per-platform digest would pin the wrong thing"
  "k8s_dl_reads_the_stable_channel_and_the_binary_digest|STUBK8S_VERSION|1.35.4|STUBK8S_SHA256_AMD64=${ASSET_DIGEST_STUBK8S}|the channel file holds v1.35.4 and the pin is spelled 1.35.4"
  "tailscale_pkgs_reads_the_stable_package_and_its_digest|STUBTAILSCALE_VERSION|1.96.4|STUBTAILSCALE_SHA256_AMD64=${ASSET_DIGEST_STUBTAILSCALE}|the package index carries Version"
  "flutter_releases_reads_the_stable_channel_and_the_archive_digest|STUBFLUTTER_VERSION|3.41.7|STUBFLUTTER_SHA256_AMD64=${ASSET_DIGEST_STUBFLUTTER}|the beta release is newer and is not the stable channel"
  "eden_manifest_reads_the_value_eden_pins|STUBEDEN_VERSION|2.1.212|${NO_DIGEST}|eden is the one decision point for a harness version, so this datasource mirrors it rather than resolving the harness upstream"
)

RESOLUTION_WORLD="$(fixture_world "resolution")"
for case_row in "${RESOLUTION_CASES[@]}"; do
  IFS='|' read -r case_name case_pin case_version case_pairs case_note <<< "$case_row"
  run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "$case_pin"
  assert_resolves "$case_name" "$case_pin" "${case_version}|${case_pairs}" "$case_note"
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
# 3. A PIN ANSWERS FOR 1 DIGEST PER ARM ITS GOVERNED FILE WRITES
# ===========================================================================
#
# Section 2 drives 13 pins whose governed file names ONE case arm. That world
# cannot see the defect this section exists for, and the defect shipped: a
# reader that stopped at the first arm computed 1 digest for a pin whose rows
# are a set of 2, so every weekly bump moved the version and the `_AMD64` row
# and left `_ARM64` on the digest of the release it was bumping AWAY from. The
# arm64 leg of the build then died at that download, in the bump pull request,
# every Monday a pin moved.
#
# The rule the 4 cases below hold is not "2 platforms". It is THE ARMS THAT
# EXIST: a record per `linux/<arch>)` arm in scope at the fetch, and never a
# record per sanctioned platform. That single rule is what makes the 3 shapes
# correct without a branch for any of them —
#
#   STUBDUAL     2 arms -> 2 records, 2 rows, 2 assets, 2 different digests.
#                Its arm64 arm fetches an asset spelled `aarch64` and answers
#                for the row spelled `_ARM64`: the row names the PLATFORM and
#                never the upstream's asset spelling.
#   STUBGO       1 arm -> 1 record. mobile's shape, and Flutter publishes no
#                linux-arm64 SDK at any version, so an arm64 row here would be
#                a row no asset can ever answer for.
#   STUBNOARCH   no arm at all -> 1 record, and the row is `_SHA256_NOARCH`.
#   STUBSHARED   2 arms, fetched by 2 governed files at 1 url -> still 2
#                records. k9s and buildx have this shape in the real tree.
#
# A reader that consulted SANCTIONED_PLATFORMS would demand an arm64 asset from
# STUBGO and from STUBNOARCH, and would name each row after the platform it
# assumed rather than after the token the arm wrote.

# record_pairs <record> — the pair list of a resolver record: everything after
# the first `|`. A version can hold no `|`, which is why the grammar puts it
# first.
function record_pairs() {
  printf '%s' "${1#*|}"
}

# pair_count <pair list> — how many `<row>=<digest>` pairs it holds. awk and not
# a `wc -w`, because 0 is an answer 2 checks below read.
function pair_count() {
  awk '{ print NF } END { if (NR == 0) print 0 }' <<< "$1"
}

# fetches_of <url> — how many times the run under test asked for that exact url.
# 2 is correct for a moved asset: the digest, and the re-proof through
# _build/fetch-verified.sh.
function fetches_of() {
  awk -v needle="$1" '$0 == needle { total++ } END { print total + 0 }' <<< "$CURL_LOG"
}

# platforms_of_row <governed file> <row> — field 1 of every fetch_urls record
# that answers for <row>, 1 per line, in the order the file writes its arms.
#
# THE RESOLVER'S RECORD DOES NOT CARRY THIS FIELD, so nothing else in this file
# can see it. `<version>|<row>=<digest>` is what the CLI prints, and a reader
# that set the platform of every record to a constant would leave every check
# above green — measured: with the field replaced by a literal, all 56 passed.
# The platform is what `expand_url` names in its refusal and what a maintainer
# reads to know WHICH leg a record answers for, so it is asserted here against
# the library reader itself.
function platforms_of_row() {
  awk -F'|' -v want="$2" '$2 == want { print $1 }' <<< "$(fetch_urls "$1")"
}

run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "STUBDUAL_VERSION"
assert_resolves "a_dual_arch_pin_resolves_one_digest_per_arm" "STUBDUAL_VERSION" \
  "1.2.3|${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64} ${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}" \
  "cloud/Dockerfile names 2 arms, so this pin has 2 assets and 2 rows. The 2 fixture" \
  "assets carry different bytes, so a resolver that fetched 1 url twice answers with 2" \
  "equal digests and this check names both; a resolver that stopped at the first arm" \
  "answers with 1 pair, and the row it did not compute is the one the build dies on"

# The 2 urls, and the 2 spellings. `aarch64` is the ASSET and `_ARM64` is the
# ROW, and the check above is what holds them together.
dual_amd64_url="https://github.com/stubowner/stubdual/releases/download/v1.2.3/stubdual-1.2.3-linux-x86_64.tar.gz"
dual_arm64_url="https://github.com/stubowner/stubdual/releases/download/v1.2.3/stubdual-1.2.3-linux-aarch64.tar.gz"
dual_amd64_fetches="$(fetches_of "$dual_amd64_url")"
dual_arm64_fetches="$(fetches_of "$dual_arm64_url")"
if [[ "$dual_amd64_fetches" -ge 1 && "$dual_arm64_fetches" -ge 1 ]]; then
  pass_check "a_dual_arch_pin_fetches_the_asset_of_each_arm_at_its_own_spelling"
else
  fail_check "a_dual_arch_pin_fetches_the_asset_of_each_arm_at_its_own_spelling" \
    "the x86_64 asset was fetched ${dual_amd64_fetches} time(s) and the aarch64 asset ${dual_arm64_fetches}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "each arm carries the spelling ITS OWN asset uses — buf spells this platform" \
    "aarch64 and grpcurl spells it arm64 — so a resolver that expanded 1 url per pin" \
    "computes a correct digest of the wrong architecture's bytes"
fi

run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "STUBGO_VERSION"
amd64_only_record="$RESOLVER_STDOUT"
amd64_only_pairs="$(record_pairs "$amd64_only_record")"
if [[ "$RESOLVER_STATUS" -eq 0 ]] \
  && [[ "$(pair_count "$amd64_only_pairs")" -eq 1 ]] \
  && [[ "$amd64_only_pairs" == "STUBGO_SHA256_AMD64=${ASSET_DIGEST_STUBGO}" ]]; then
  pass_check "an_amd64_only_pin_gains_no_arm64_row"
else
  fail_check "an_amd64_only_pin_gains_no_arm64_row" \
    "want: exit 0 and exactly 1 pair — STUBGO_SHA256_AMD64=${ASSET_DIGEST_STUBGO}" \
    "got:  exit ${RESOLVER_STATUS}, and the pairs were:" "${amd64_only_pairs:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "base/Dockerfile names linux/amd64 alone for this pin, which is mobile's shape and" \
    "is CORRECT rather than incomplete: no bump reaches an asset upstream does not" \
    "publish. A reader that consulted the sanctioned set instead of the arms that exist" \
    "either invents a row no home declares, or dies expanding a url whose \${ARCH} the" \
    "absent arm never set"
fi

run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "STUBNOARCH_VERSION"
noarch_pairs="$(record_pairs "$RESOLVER_STDOUT")"
if [[ "$RESOLVER_STATUS" -eq 0 ]] \
  && [[ "$(pair_count "$noarch_pairs")" -eq 1 ]] \
  && [[ "$noarch_pairs" == "${ROW_STUBNOARCH}=${ASSET_DIGEST_STUBNOARCH}" ]]; then
  pass_check "a_noarch_pin_keeps_its_single_row"
else
  fail_check "a_noarch_pin_keeps_its_single_row" \
    "want: exit 0 and exactly 1 pair — ${ROW_STUBNOARCH}=${ASSET_DIGEST_STUBNOARCH}" \
    "got:  exit ${RESOLVER_STATUS}, and the pairs were:" "${noarch_pairs:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "this asset sits in a RUN with no case at all, so it spells its pin literally and" \
    "1 row answers for every platform. A reader that defaulted an armless fetch to" \
    "amd64 writes the digest into a _SHA256_AMD64 row, which no home declares and no" \
    "download reads — while _SHA256_NOARCH keeps the value it is being bumped away from"
fi

run_resolver "$BASE_MAP" "$RESOLUTION_WORLD" -- "STUBSHARED_VERSION"
shared_pairs="$(record_pairs "$RESOLVER_STDOUT")"
shared_amd64_url="https://github.com/stubowner/stubshared/releases/download/v0.9.1/stubshared_Linux_amd64.tar.gz"
shared_amd64_fetches="$(fetches_of "$shared_amd64_url")"
if [[ "$RESOLVER_STATUS" -eq 0 ]] \
  && [[ "$(pair_count "$shared_pairs")" -eq 2 ]] \
  && [[ "$shared_pairs" == "${ROW_STUBSHARED_AMD64}=${ASSET_DIGEST_STUBSHARED_AMD64} ${ROW_STUBSHARED_ARM64}=${ASSET_DIGEST_STUBSHARED_ARM64}" ]] \
  && [[ "$shared_amd64_fetches" -eq 2 ]]; then
  pass_check "a_row_two_governed_files_fetch_is_answered_once"
else
  fail_check "a_row_two_governed_files_fetch_is_answered_once" \
    "want: exit 0, exactly 2 pairs, and the amd64 asset fetched exactly 2 times" \
    "      ${ROW_STUBSHARED_AMD64}=${ASSET_DIGEST_STUBSHARED_AMD64} ${ROW_STUBSHARED_ARM64}=${ASSET_DIGEST_STUBSHARED_ARM64}" \
    "got:  exit ${RESOLVER_STATUS}, ${shared_amd64_fetches} fetch(es) of the amd64 asset, and the pairs were:" \
    "${shared_pairs:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "cloud/Dockerfile and _delta/components/stubshared.sh fetch this pin at the SAME" \
    "url for the SAME 2 rows — the k9s and buildx shape. A row is deduplicated and" \
    "never a url: without it each row is answered twice, the record carries 4 pairs," \
    "and every Monday spends 2 extra whole-asset downloads per pin of that shape"
fi

# -------- the PLATFORM field, which no check above reads --------
# The 3 checks above assert the resolver's record, and that record carries the
# row and the digest and NOT the platform. So the whole set stayed green when
# the platform expression in `fetch_urls` was replaced by a literal — 56 checks,
# 0 failed, over a reader that had stopped saying which leg each record answers
# for. It is the field `expand_url` names in its refusal ("neither the
# linux/arm64 case arm nor a value home declares it"), and the field a
# maintainer reads to tell 2 records of 1 pin apart.
DUAL_GOVERNED_FILE="${RESOLUTION_WORLD}/cloud/Dockerfile"
dual_amd64_platforms="$(platforms_of_row "$DUAL_GOVERNED_FILE" "$ROW_STUBDUAL_AMD64")"
dual_arm64_platforms="$(platforms_of_row "$DUAL_GOVERNED_FILE" "$ROW_STUBDUAL_ARM64")"
if [[ "$dual_amd64_platforms" == "linux/amd64" && "$dual_arm64_platforms" == "linux/arm64" ]]; then
  pass_check "each_record_of_a_dual_arch_pin_names_the_platform_of_its_own_arm"
else
  fail_check "each_record_of_a_dual_arch_pin_names_the_platform_of_its_own_arm" \
    "want: exactly 1 record per row — ${ROW_STUBDUAL_AMD64} on linux/amd64 and ${ROW_STUBDUAL_ARM64} on linux/arm64" \
    "got:  ${ROW_STUBDUAL_AMD64} on:" "${dual_amd64_platforms:-<no record>}" \
    "      ${ROW_STUBDUAL_ARM64} on:" "${dual_arm64_platforms:-<no record>}" \
    "every record fetch_urls emits:" "$(fetch_urls "$DUAL_GOVERNED_FILE")" \
    "the platform is the arm's OWN name, taken from the \`linux/<arch>)\` token the file" \
    "writes. A constant there — or the sanctioned set read positionally — labels the" \
    "aarch64 asset as the amd64 leg, and every message about that record then names the" \
    "wrong architecture to the person fixing it"
fi

noarch_platforms="$(platforms_of_row "$DUAL_GOVERNED_FILE" "$ROW_STUBNOARCH")"
if [[ "$noarch_platforms" == "-" ]]; then
  pass_check "an_armless_fetch_records_its_platform_as_a_dash"
else
  fail_check "an_armless_fetch_records_its_platform_as_a_dash" \
    "want: exactly 1 record for ${ROW_STUBNOARCH}, on platform '-'" \
    "got:" "${noarch_platforms:-<no record>}" \
    "every record fetch_urls emits:" "$(fetch_urls "$DUAL_GOVERNED_FILE")" \
    "no case arm is in scope at that fetch, so there is no platform to name and '-' says" \
    "so. A reader that put a platform there would be inventing the one fact the file" \
    "deliberately does not state — which is how flutter's own SDK row, unarmed and" \
    "_AMD64, gets read as an arm64 download that upstream has never published"
fi

# ===========================================================================
# 4. THE WRITER TAKES THE WHOLE ROW SET, OR REFUSES AND WRITES NOTHING
# ===========================================================================
#
# `bump_pin` in _ctl/lib.sh is the ONLY writer, and section 3 is only half of
# the guarantee. Reading every arm is what makes a CORRECT call possible; what
# makes an incorrect one impossible is the refusal here — every
# `<tool>_SHA256_<ARCH>` row beside the pin gets a value in the SAME call, or
# nothing is written and the message names the row that got none.
#
# They are not the same guarantee, and the day a `_SHA256_RISCV64` row is
# written it is the refusal that reports every caller which does not yet compute
# one. So these cases call the writer DIRECTLY, as the library function it is:
# the resolver's --apply path is 1 caller, and a refusal has to be readable by
# the caller that made the incorrect call rather than only by the run that
# happened to make a correct one.

BUMP_OUTPUT=""
BUMP_STATUS=0

# run_bump_pin <root> <pin> <version> <evidence> [<row>=<digest> ...] — the
# writer, with its status and its message kept. stderr is folded in because
# every refusal it makes is a log_error line, and a refusal nobody can read is
# the `exit 1` this repository refuses to ship.
function run_bump_pin() {
  BUMP_STATUS=0
  BUMP_OUTPUT="$(bump_pin "$@" 2>&1)" || BUMP_STATUS=$?
}

# row_line <world> <name> — the declaration line of 1 row of a fixture world,
# read with the repository's own reader.
function row_line() {
  declaration_line "${1}/versions.env" "$2"
}

# row_value <world> <name> — the value that line carries.
function row_value() {
  declaration_value "$(row_line "$1" "$2")"
}

TODAY="$(date +%Y-%m-%d)"

APPLY_WORLD="$(committed_fixture_world "apply-per-platform")"
run_resolver "$BASE_MAP" "$APPLY_WORLD" -- "--apply"
apply_status="$RESOLVER_STATUS"
apply_stderr="$RESOLVER_STDERR"
applied_version="$(row_value "$APPLY_WORLD" "STUBDUAL_VERSION")"
applied_amd64="$(row_value "$APPLY_WORLD" "$ROW_STUBDUAL_AMD64")"
applied_arm64="$(row_value "$APPLY_WORLD" "$ROW_STUBDUAL_ARM64")"

if [[ "$apply_status" -eq 0 ]] \
  && [[ "$applied_version" == "1.2.3" ]] \
  && [[ "$applied_amd64" == "$ASSET_DIGEST_STUBDUAL_AMD64" ]] \
  && [[ "$applied_arm64" == "$ASSET_DIGEST_STUBDUAL_ARM64" ]]; then
  pass_check "apply_moves_every_sha256_sibling"
else
  fail_check "apply_moves_every_sha256_sibling" \
    "want: exit 0, STUBDUAL_VERSION=1.2.3, and both rows on the digest of their own arm" \
    "      ${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
    "      ${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}" \
    "got:  exit ${apply_status}, STUBDUAL_VERSION=${applied_version:-<none>}" \
    "      ${ROW_STUBDUAL_AMD64}=${applied_amd64:-<none>}" \
    "      ${ROW_STUBDUAL_ARM64}=${applied_arm64:-<none>}" \
    "stderr was:" "${apply_stderr:-<none>}" \
    "the fixture holds dddd... in both rows, which is the digest of no asset at all, so" \
    "a sibling this run did not move is a sibling still reading dddd... here — and in a" \
    "real bump it reads the digest of the release the pin was moved away from"
fi

applied_amd64_line="$(row_line "$APPLY_WORLD" "$ROW_STUBDUAL_AMD64")"
applied_arm64_line="$(row_line "$APPLY_WORLD" "$ROW_STUBDUAL_ARM64")"
if [[ "$apply_status" -eq 0 ]] \
  && [[ "$(evidence_of "$applied_amd64_line")" == "computed-at-pin" ]] \
  && [[ "$(evidence_of "$applied_arm64_line")" == "computed-at-pin" ]] \
  && grep -qF -- "computed-at-pin: ${TODAY}" <<< "$applied_amd64_line" \
  && grep -qF -- "computed-at-pin: ${TODAY}" <<< "$applied_arm64_line" \
  && ! grep -qF -- "$STALE_ARM64_EVIDENCE_URL" <<< "$applied_arm64_line"; then
  pass_check "each_row_gets_its_own_evidence"
else
  fail_check "each_row_gets_its_own_evidence" \
    "want: exit 0, and BOTH rows carrying '# computed-at-pin: ${TODAY}' — the provenance" \
    "      of the bytes THIS run fetched for that row" \
    "got:  exit ${apply_status}, and the 2 lines are:" \
    "${applied_amd64_line:-<none>}" \
    "${applied_arm64_line:-<none>}" \
    "the fixture's arm64 row carries an upstream-published url of v1.2.2 — the release" \
    "the pin is being bumped AWAY from. A writer that stamped the first row and left the" \
    "sibling's comment alone leaves that url attesting bytes it is not the digest of," \
    "and a digest a reviewer has to take on faith is not a pin"
fi

PARTIAL_WORLD="$(committed_fixture_world "partial-digest-set")"
run_bump_pin "$PARTIAL_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}"
partial_porcelain="$(git -C "$PARTIAL_WORLD" status --porcelain)"
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && grep -qF -- "$ROW_STUBDUAL_ARM64" <<< "$BUMP_OUTPUT" \
  && [[ -z "$partial_porcelain" ]]; then
  pass_check "a_partial_digest_set_is_refused_naming_the_row"
else
  fail_check "a_partial_digest_set_is_refused_naming_the_row" \
    "want: a non-zero status, a message naming ${ROW_STUBDUAL_ARM64}, and an empty porcelain" \
    "got:  exit ${BUMP_STATUS}, porcelain:" "${partial_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "the diff it left behind:" "$(git -C "$PARTIAL_WORLD" diff)" \
    "this call moves the version and answers for 1 of the 2 rows the pin declares. A" \
    "writer that accepted it writes a pull request that reads as a correct bump and" \
    "fails the build on the arm64 leg, after the merge, naming a pin the diff showed as" \
    "correct. The status alone is not the check: a refusal that does not NAME the row" \
    "leaves the caller to diff 2 files to find out which digest it owes"
fi

# -------- one row, two assets: the shape the dedupe must NOT swallow --------
# The k9s reading above and this one are the same 2 records to a reader that
# keys on the row: same row, 2 records, drop the second. What tells them apart
# is the ASSET each arm names — the url with that arm's own ARCH resolved into
# it — and the difference is the whole guarantee. Same asset means one download
# read twice and is deduplicated; 2 assets under 1 row means the row can attest
# at most one of them, and the OTHER architecture installs bytes nothing
# answered for. The build cannot see it: the digest it compares is the one that
# matches, on the leg that matches.
#
# The fixture is named mobile/Dockerfile because that is where the live seed
# is. ANDROID_CMDLINE_TOOLS_SHA256_NOARCH is a _NOARCH row emitted under
# mobile's `linux/amd64) : ;;` guard arm today — 1 arm, correct — and the day
# that RUN gains an arm64 arm without splitting the row, the tree IS this
# fixture. Whoever writes that arm meets this failure and has to choose: 2 rows
# for 2 assets, or 1 asset for both arms.
run_resolver "$BASE_MAP" "$ONE_ROW_WORLD" -- "STUBONEROW_VERSION"
one_row_output="${RESOLVER_STDOUT}
${RESOLVER_STDERR}"
one_row_missing=""
for expected in \
  "STUBONEROW_SHA256_NOARCH" \
  "stubonerow-\${STUBONEROW_VERSION}-linux-x86_64.tar.gz" \
  "stubonerow-\${STUBONEROW_VERSION}-linux-aarch64.tar.gz"; do
  if ! grep -qF -- "$expected" <<< "$one_row_output"; then
    one_row_missing="${one_row_missing:+${one_row_missing}
}${expected}"
  fi
done
if [[ "$RESOLVER_STATUS" -ne 0 && -z "$one_row_missing" ]]; then
  pass_check "one_row_naming_two_different_assets_is_refused_naming_both"
else
  fail_check "one_row_naming_two_different_assets_is_refused_naming_both" \
    "want: a non-zero exit, and a message naming the row AND both assets" \
    "got:  exit ${RESOLVER_STATUS}, and the message never names:" "${one_row_missing:-<nothing>}" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the urls it asked for:" "${CURL_LOG:-<none>}" \
    "naming the row alone would leave the reader diffing 2 arms to find out which asset" \
    "it is being asked to choose between; a silent dedupe would leave them nothing at all," \
    "and the writer would then be satisfied by a row set it had only half resolved"
fi

# The counter-stimulus for it, stated where the rule is: the OTHER 2-record
# shape must still pass silently. STUBSHARED is fetched by cloud/Dockerfile and
# by _delta/components/stubshared.sh at 1 url for the same 2 rows — same row,
# same resolved asset — and the check above in section 3 reads it resolving to
# exactly 2 pairs with 2 fetches per asset. A refusal that fired on identity as
# well as on difference would turn k9s and buildx red in the real tree.
if [[ "$shared_pairs" == "${ROW_STUBSHARED_AMD64}=${ASSET_DIGEST_STUBSHARED_AMD64} ${ROW_STUBSHARED_ARM64}=${ASSET_DIGEST_STUBSHARED_ARM64}" ]]; then
  pass_check "counter_stimulus_one_row_naming_one_asset_in_two_files_is_still_silent"
else
  fail_check "counter_stimulus_one_row_naming_one_asset_in_two_files_is_still_silent" \
    "want: ${ROW_STUBSHARED_AMD64}=${ASSET_DIGEST_STUBSHARED_AMD64} ${ROW_STUBSHARED_ARM64}=${ASSET_DIGEST_STUBSHARED_ARM64}" \
    "got:  ${shared_pairs:-<none>}" \
    "the refusal above must fire on 2 DIFFERENT assets under 1 row and never on 1 asset" \
    "read twice; k9s and docker buildx are fetched by base/Dockerfile and by a component" \
    "at one url, and a refusal that could not tell the 2 apart would make the real tree red"
fi

UNDECLARED_WORLD="$(committed_fixture_world "undeclared-digest-row")"
run_bump_pin "$UNDECLARED_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}" \
  "STUBDUAL_SHA256_RISCV64=${ASSET_DIGEST_STUBDUAL_AMD64}"
undeclared_porcelain="$(git -C "$UNDECLARED_WORLD" status --porcelain)"
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && grep -qF -- "STUBDUAL_SHA256_RISCV64" <<< "$BUMP_OUTPUT" \
  && [[ -z "$undeclared_porcelain" ]]; then
  pass_check "an_undeclared_digest_row_is_refused_naming_it"
else
  fail_check "an_undeclared_digest_row_is_refused_naming_it" \
    "want: a non-zero status, a message naming STUBDUAL_SHA256_RISCV64, and an empty porcelain" \
    "got:  exit ${BUMP_STATUS}, porcelain:" "${undeclared_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "the diff it left behind:" "$(git -C "$UNDECLARED_WORLD" diff)" \
    "this call answers for both rows the pin declares AND for one no home does. The" \
    "digest of that third row would be written NOWHERE, and a caller that computed it" \
    "believes a platform is pinned that nothing verifies — which is the same silence as" \
    "a missing row, wearing the shape of a complete call"
fi

# -------- the argument that used to abort the write MIDWAY --------
# A comment holds no newline, and the evidence reaches awk as a `-v` assignment.
# A newline in it aborts awk in the MIDDLE of the write loop, so the version row
# was already rewritten and the digest rows were not: version moved, digests
# stale, which is the precise state this whole feature exists to make
# impossible — and it is the state no build can detect until the download fails
# after the merge.
#
# 2 things now make it unreachable, and this case reads BOTH: the argument is
# refused before any file is opened, and every home is staged on a copy that is
# verified before a single byte is written back. So the check is not only "it
# said no" — it is "it said no and the tree is byte for byte what it was".
NEWLINE_WORLD="$(committed_fixture_world "newline-evidence")"
newline_version_before="$(row_value "$NEWLINE_WORLD" "STUBDUAL_VERSION")"
run_bump_pin "$NEWLINE_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}
this second line is what aborted awk halfway through the write loop" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}"
newline_porcelain="$(git -C "$NEWLINE_WORLD" status --porcelain)"
newline_version_after="$(row_value "$NEWLINE_WORLD" "STUBDUAL_VERSION")"
# The message has to be the WRITER'S OWN refusal, naming the pin and the
# argument. `awk: newline in string ... at source line 1` also carries the word
# newline, and a check that took it would pass against a writer with no guard at
# all — the staging below catches that one, so the tree is clean either way and
# the status cannot tell them apart. What the up-front guard adds is a reader
# who learns WHICH ARGUMENT they got wrong instead of a line number in an awk
# program they did not write.
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && grep -qF -- "bump_pin: STUBDUAL_VERSION: the evidence carries a newline" <<< "$BUMP_OUTPUT" \
  && [[ -z "$newline_porcelain" ]] \
  && [[ "$newline_version_after" == "$newline_version_before" ]]; then
  pass_check "an_evidence_carrying_a_newline_is_refused_before_anything_is_written"
else
  fail_check "an_evidence_carrying_a_newline_is_refused_before_anything_is_written" \
    "want: a non-zero status, the writer's OWN refusal naming the pin and the evidence," \
    "      an empty porcelain, and STUBDUAL_VERSION still ${newline_version_before}" \
    "got:  exit ${BUMP_STATUS}, STUBDUAL_VERSION=${newline_version_after:-<none>}, porcelain:" \
    "${newline_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "the diff it left behind:" "$(git -C "$NEWLINE_WORLD" diff)" \
    "a version row moved and its digest rows left stale is the exact defect this writer" \
    "exists to prevent, and it is the one state a build cannot detect until the download" \
    "fails after the merge — the status alone does not prove it, the clean tree does"
fi

# -------- and the SECOND wall, on a stimulus that walks past the first --------
# `\n` — a backslash and an n — is not a newline, so both argument guards accept
# it. awk expands escape sequences in a `-v` assignment, so the comment it
# writes carries a REAL newline and the rewritten file gains a line. That is a
# mid-write corruption reachable today, with every guard in place, and it is
# what the staging is for: every home is rewritten on a COPY and the copy is
# verified before a byte goes back. The refusal has therefore touched no tracked
# file, and this case reads the tree rather than the status to say so.
STAGED_WORLD="$(committed_fixture_world "staged-write")"
staged_version_before="$(row_value "$STAGED_WORLD" "STUBDUAL_VERSION")"
run_bump_pin "$STAGED_WORLD" "STUBDUAL_VERSION" "1.2.3" 'computed-at-pin: 2026-08-18\nand a second line' \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}"
staged_porcelain="$(git -C "$STAGED_WORLD" status --porcelain)"
staged_version_after="$(row_value "$STAGED_WORLD" "STUBDUAL_VERSION")"
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && [[ -z "$staged_porcelain" ]] \
  && [[ "$staged_version_after" == "$staged_version_before" ]]; then
  pass_check "a_rewrite_that_corrupts_a_home_writes_no_byte_of_it"
else
  fail_check "a_rewrite_that_corrupts_a_home_writes_no_byte_of_it" \
    "want: a non-zero status, an empty porcelain, and STUBDUAL_VERSION still ${staged_version_before}" \
    "got:  exit ${BUMP_STATUS}, STUBDUAL_VERSION=${staged_version_after:-<none>}, porcelain:" \
    "${staged_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "the diff it left behind:" "$(git -C "$STAGED_WORLD" diff)" \
    "the version row is rewritten BEFORE the digest rows, so a writer that edited the" \
    "real file in place leaves exactly the state this feature exists to make impossible:" \
    "version moved, digest rows stale or mangled, and a build that only finds out at the" \
    "download after the merge"
fi

# -------- 1 row, 2 answers in 1 call --------
# A duplicate pair is a caller saying the same thing twice or 2 different things
# at once, and the 2 cost very different amounts. Identical is a caller
# repeating itself. CONTRADICTORY means the call cannot say which asset the row
# attests, and whichever of last-wins or first-wins the writer happened to
# implement would pick by ARGUMENT ORDER — a digest chosen by the order a loop
# ran in, written with an evidence comment claiming it was read from bytes.
CONTRADICTION_WORLD="$(committed_fixture_world "contradictory-duplicate")"
run_bump_pin "$CONTRADICTION_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_ARM64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}"
contradiction_porcelain="$(git -C "$CONTRADICTION_WORLD" status --porcelain)"
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && grep -qF -- "$ASSET_DIGEST_STUBDUAL_AMD64" <<< "$BUMP_OUTPUT" \
  && grep -qF -- "$ASSET_DIGEST_STUBDUAL_ARM64" <<< "$BUMP_OUTPUT" \
  && [[ -z "$contradiction_porcelain" ]]; then
  pass_check "a_row_given_two_different_digests_is_refused_naming_both_values"
else
  fail_check "a_row_given_two_different_digests_is_refused_naming_both_values" \
    "want: a non-zero status, a message naming BOTH digests, and an empty porcelain" \
    "      ${ASSET_DIGEST_STUBDUAL_AMD64}" \
    "      ${ASSET_DIGEST_STUBDUAL_ARM64}" \
    "got:  exit ${BUMP_STATUS}, porcelain:" "${contradiction_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "naming 1 value tells the caller which answer was kept and not which 2 disagreed," \
    "and the disagreement is the bug: 2 digests for 1 row means the run resolved 2 assets" \
    "and believes they are the same one"
fi

# The counter-stimulus, and it is what keeps the refusal from being a blanket
# ban: 1 row named twice with the SAME digest says one thing twice. A resolver
# whose 2 governed files agree produces exactly that, and refusing it would make
# a correct call fail on a repetition that changes nothing.
IDENTICAL_WORLD="$(committed_fixture_world "identical-duplicate")"
run_bump_pin "$IDENTICAL_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}"
identical_amd64="$(row_value "$IDENTICAL_WORLD" "$ROW_STUBDUAL_AMD64")"
identical_arm64="$(row_value "$IDENTICAL_WORLD" "$ROW_STUBDUAL_ARM64")"
if [[ "$BUMP_STATUS" -eq 0 ]] \
  && [[ "$identical_amd64" == "$ASSET_DIGEST_STUBDUAL_AMD64" ]] \
  && [[ "$identical_arm64" == "$ASSET_DIGEST_STUBDUAL_ARM64" ]]; then
  pass_check "counter_stimulus_a_row_given_the_same_digest_twice_is_accepted"
else
  fail_check "counter_stimulus_a_row_given_the_same_digest_twice_is_accepted" \
    "want: exit 0, and both rows on their own digest" \
    "got:  exit ${BUMP_STATUS}" \
    "      ${ROW_STUBDUAL_AMD64}=${identical_amd64:-<none>}" \
    "      ${ROW_STUBDUAL_ARM64}=${identical_arm64:-<none>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "a refusal that fired on repetition as well as on contradiction would fail a call" \
    "whose 2 sources AGREE, which is the shape a correct resolver produces"
fi

# -------- a pair with nothing before its '=' --------
# `=<digest>` is a pair whose row name is the empty string, and it is what a
# caller building pairs from an empty variable produces. Without a refusal it
# passes every other guard: the completeness check is satisfied by the real
# pairs beside it, the unknown-row check skips an empty name, and the write loop
# looks for a declaration of "" and finds none. So the call reports success
# having written a digest nowhere, and the caller believes a row it named is
# pinned.
EMPTY_ROW_WORLD="$(committed_fixture_world "empty-row-name")"
run_bump_pin "$EMPTY_ROW_WORLD" "STUBDUAL_VERSION" "1.2.3" "computed-at-pin: ${TODAY}" \
  "${ROW_STUBDUAL_AMD64}=${ASSET_DIGEST_STUBDUAL_AMD64}" \
  "${ROW_STUBDUAL_ARM64}=${ASSET_DIGEST_STUBDUAL_ARM64}" \
  "=${ASSET_DIGEST_STUBDUAL_AMD64}"
empty_row_porcelain="$(git -C "$EMPTY_ROW_WORLD" status --porcelain)"
if [[ "$BUMP_STATUS" -ne 0 ]] \
  && grep -qF -- "=${ASSET_DIGEST_STUBDUAL_AMD64}" <<< "$BUMP_OUTPUT" \
  && [[ -z "$empty_row_porcelain" ]]; then
  pass_check "a_pair_with_an_empty_row_name_is_refused_naming_it"
else
  fail_check "a_pair_with_an_empty_row_name_is_refused_naming_it" \
    "want: a non-zero status, a message quoting the pair, and an empty porcelain" \
    "got:  exit ${BUMP_STATUS}, porcelain:" "${empty_row_porcelain:-<empty>}" \
    "the writer said:" "${BUMP_OUTPUT:-<nothing>}" \
    "the diff it left behind:" "$(git -C "$EMPTY_ROW_WORLD" diff)" \
    "every other guard passes this call: the rows beside it satisfy the completeness" \
    "check, the unknown-row reader skips an empty name, and the write loop finds no" \
    "declaration to edit — so the digest is written nowhere and the run says it worked"
fi

# ===========================================================================
# 5. AN UNREACHABLE UPSTREAM FAILS, AND NAMES THE PIN
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
# 6. THE DRY RUN COMPOSES A PULL REQUEST AND WRITES NOTHING
# ===========================================================================
DRY_RUN_WORLD="$(committed_fixture_world "dry-run")"

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
# 7. ONE FAILING ROW FAILS THE WHOLE AGGREGATE RUN, AND WRITES NOTHING
# ===========================================================================
#
# Section 5 hands the resolver 1 PIN and reads the refusal. That is the shape
# every failure case of this file had until now, and it is the shape that cannot
# see the defect: with 1 pin on the argv, `fail_pin`'s `exit 1` runs at the top
# level of the script and the status reaches the caller. The weekly workflow
# never invokes the resolver that way. It invokes `--dry-run` and `--apply`, and
# on that path every resolution happens inside a command substitution:
#
#     collect_bumps:  record="$(resolve_pin "$pin")"
#     dry_run:        bumps="$(collect_bumps)"
#
# bash does not carry errexit into `$( )` unless `shopt -s inherit_errexit` is
# set, and `set -Eeuo pipefail` alone does not set it. So `exit 1` kills the
# subshell, the caller reads an empty string, and the run continues. Measured on
# this repository at 8e705f1, base image, linux/amd64: 1 dead index makes the
# resolver print 3 cascading `[error]` lines, then
#
#     bump: STUBGITHUB_VERSION 2.3.0 ->
#
# with an EMPTY new version, then a whole pull request body listing it, and then
# exit 0. `--apply` additionally leaves a PARTIAL WRITE: the movers ahead of the
# failing row are already on disk when the writer finally refuses the empty
# version. That is precisely what the header of _build/resolve-upstream.sh says
# is impossible — "a resolver that swallowed a failed fetch would open a pull
# request bumping the pins it happened to reach".
#
# ---------------------------------------------------------------------------
# THE CONTRACT THESE 3 CASES CHOOSE: COLLECT, THEN FAIL
# ---------------------------------------------------------------------------
#
# 2 designs answer "what does an aggregate run do with 1 unreachable upstream":
#
#   ABORT AT THE FIRST FAILURE   stop the moment a row fails. Simple, and it
#                                costs the reader everything the run had already
#                                learned: 1 dead coordinate hides the 13 real
#                                bumps behind it, every Monday, and the log
#                                names 1 pin when 1 pin is the only thing that
#                                is wrong.
#   COLLECT, THEN FAIL           resolve every row, report every mover AND every
#                                failure, write nothing, exit non-zero.
#
# These cases specify COLLECT-THEN-FAIL, for the 2 reasons this repository has
# already written down. FAIL-NOT-SKIP says a red run must be red AND must say
# what it found; and the nightly beside it already works this way — its notify
# job reduces the verdict of the jobs it needs rather than dying at the first
# one, so 1 scan failure never hides the other 5 images. A weekly that aborts at
# row 1 turns a 1-row problem into a run that reports nothing, and the reader of
# a 09:00 Monday with no author watching cannot tell that apart from a quiet
# week.
#
# The 3 clauses that follow from it, and every case below holds them together:
#
#   1. the run exits NON-ZERO — a failure is never reported as a bump;
#   2. the report NAMES the failing pin and still names the movers;
#   3. NOTHING is written — not the movers, not a partial file. A weekly that
#      wrote 11 of 12 rows and died would leave a branch that reads like a
#      correct bump and is 1 pin short of the change it claims.

AGGREGATE_FAILURE_WORLD="$(committed_fixture_world "aggregate-failure")"
run_resolver "$INDEX_404_MAP" "$AGGREGATE_FAILURE_WORLD" -- "--dry-run"
aggregate_failure_output="${RESOLVER_STDOUT}
${RESOLVER_STDERR}"
aggregate_empty_bumps="$(empty_version_bump_lines "$RESOLVER_STDOUT")"

# 3 conditions, 1 check, on purpose. The status alone would pass against a
# resolver that died for a reason nobody wrote down; the name alone is already
# printed today, by a run that then exits 0; and "no empty-version bump line" is
# true of a run that printed nothing at all. Together they are the defect:
# exit non-zero, say which pin, and never report a bump to a version that was
# never resolved.
if [[ "$RESOLVER_STATUS" -ne 0 ]] \
  && grep -qF -- "STUBGITHUB_VERSION" <<< "$aggregate_failure_output" \
  && [[ -z "$aggregate_empty_bumps" ]]; then
  pass_check "an_aggregate_dry_run_with_one_failing_row_fails_naming_the_pin"
else
  fail_check "an_aggregate_dry_run_with_one_failing_row_fails_naming_the_pin" \
    "want: a non-zero exit, a message naming STUBGITHUB_VERSION, and no bump line" \
    "      whose new version is empty" \
    "got:  exit ${RESOLVER_STATUS}, and these lines report a bump to nothing:" \
    "${aggregate_empty_bumps:-<none>}" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the index of stubowner/stubgithub is a 404 and its asset is still served, so this" \
    "run cannot pass by failing at the download; a resolver that reports 'PIN 2.3.0 -> '" \
    "has read a version out of a subshell that died and is asking a human to approve it"
fi

# --apply, with the failing row placed AFTER 11 movers. The write loop reaches
# the good rows first, so this is the ordering in which a swallowed failure
# leaves half a bump on disk — and the only ordering in which the porcelain can
# tell the 2 designs apart.
APPLY_FAILURE_WORLD="$(committed_fixture_world "apply-failure")"
run_resolver "$LATE_FAILURE_MAP" "$APPLY_FAILURE_WORLD" -- "--apply"
apply_failure_porcelain="$(git -C "$APPLY_FAILURE_WORLD" status --porcelain)"
apply_failure_diff="$(git -C "$APPLY_FAILURE_WORLD" diff)"

if [[ "$RESOLVER_STATUS" -ne 0 && -z "$apply_failure_porcelain" ]]; then
  pass_check "an_aggregate_apply_with_one_failing_row_writes_nothing"
else
  fail_check "an_aggregate_apply_with_one_failing_row_writes_nothing" \
    "want: a non-zero exit and an empty git status --porcelain" \
    "got:  exit ${RESOLVER_STATUS}, porcelain:" "${apply_failure_porcelain:-<empty>}" \
    "the diff it left behind:" "${apply_failure_diff:-<none>}" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the flutter index is the 12th row of 17 and the 11 rows ahead of it resolve, so a" \
    "writer that runs before the run's verdict is known rewrites them and then dies;" \
    "the branch that leaves behind reads like a correct bump and is 1 pin short of it"
fi

# The other direction of the same contract, and the reason it is COLLECT and not
# ABORT: the row that failed is the FIRST of the table, and the run still has to
# report the movers behind it. STUBVPREFIX is the row immediately after the
# failure and STUBNOARCH is the last resolvable row of the table, so naming both
# proves the run went all the way through rather than stopping at row 1.
COLLECT_WORLD="$(committed_fixture_world "collect-then-fail")"
run_resolver "$EARLY_FAILURE_MAP" "$COLLECT_WORLD" -- "--dry-run"
collect_output="${RESOLVER_STDOUT}
${RESOLVER_STDERR}"
collect_porcelain="$(git -C "$COLLECT_WORLD" status --porcelain)"
collect_missing=""
for expected in \
  "bump: STUBVPREFIX_VERSION v0.1.0 -> v0.2.0" \
  "bump: STUBNOARCH_VERSION 7.0.0 -> 7.1.0" \
  "STUBGITHUB_VERSION"; do
  if ! grep -qF -- "$expected" <<< "$collect_output"; then
    collect_missing="${collect_missing:+${collect_missing}
}${expected}"
  fi
done

if [[ "$RESOLVER_STATUS" -ne 0 && -z "$collect_missing" && -z "$collect_porcelain" ]]; then
  pass_check "a_failing_row_does_not_hide_the_report_of_later_movers"
else
  fail_check "a_failing_row_does_not_hide_the_report_of_later_movers" \
    "want: a non-zero exit, an empty porcelain, and a report naming the failing pin" \
    "      AND every mover behind it" \
    "got:  exit ${RESOLVER_STATUS}, and the report never names:" "${collect_missing:-<nothing>}" \
    "porcelain:" "${collect_porcelain:-<empty>}" \
    "stdout was:" "${RESOLVER_STDOUT:-<none>}" \
    "stderr was:" "${RESOLVER_STDERR:-<none>}" \
    "the contract is collect-then-fail: resolve every row, report every mover and every" \
    "failure, write nothing, exit non-zero. 1 dead coordinate must not hide the 13 real" \
    "bumps behind it, and a run that reports nothing reads like a quiet week"
fi

# ===========================================================================
# 8. A GREEN WEEKLY DOES NOT CLOSE THE NIGHTLY ISSUE
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
