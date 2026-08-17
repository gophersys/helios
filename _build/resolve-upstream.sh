#!/usr/bin/env bash
#
# _build/resolve-upstream.sh — what is the newest value of this pin, and what
# are the bytes it names.
#
# Every pin of this repository carries a row in _build/upstreams.txt saying
# where its next value comes from. This file is the other half: it reads that
# row, asks the upstream, and answers with the version AND the sha256 of the
# asset THAT version names — so the digest can never be of the release the pin
# is being bumped away from.
#
#   bash _build/resolve-upstream.sh <PIN>
#       1 record on stdout:  <version>|<sha256>
#
#       <version>  spelled the way the pin's CURRENT value is spelled. A leading
#                  `v` is kept when the pin carries one (cictl pins v0.1.0) and
#                  dropped when it does not (gh pins 2.90.0); `go1.26.5` and
#                  `bun-v1.3.14` lose their word prefix the same way.
#       <sha256>   the digest of the bytes the GOVERNED FILE fetches for that
#                  new version, or `-` when the pin has no digest row at all,
#                  which about 30 of the 56 pins (go install, corepack, pipx)
#                  do not.
#
#   bash _build/resolve-upstream.sh --dry-run
#       resolve every row and print the pull request it WOULD open. It writes
#       nothing to the repository. It does write temporary files and it does
#       download every asset that moved, twice — see the re-proof below.
#
#   bash _build/resolve-upstream.sh --apply
#       the same resolution, and then the write: bump_pin edits EVERY home of
#       each pin that moved. The caller commits, pushes and opens the pull
#       request; this file never touches git and never calls gh.
#
#   Environment:
#       UPSTREAM_PROJECT_ROOT  the tree to read and write. Defaults to this
#                              repository, and the tests point it at a fixture.
#       EDEN_MANIFEST_READ     the credential the eden-manifest datasource reads
#                              the private gophersys/eden with.
#       GH_TOKEN, GITHUB_TOKEN authenticate the github API reads. Optional, and
#                              only the rate limit depends on them.
#
# ============================================================================
# WHY THE DIGEST IS COMPUTED HERE AND NOT COPIED
# ============================================================================
#
# The defect this file exists to make impossible is a bump that moves the
# version and leaves the digest: the build then dies at the download, after the
# merge, naming a pin that looked correct in the diff. A resolver can produce it
# in 1 line — resolve the version, and re-read the digest out of the pin it is
# bumping.
#
# So the digest is of bytes this run fetched, at the URL the GOVERNED FILE
# writes with the NEW version substituted in — never a URL out of the table,
# because a second URL home lets a correct digest be computed of the wrong
# asset. The value is then handed back to _build/fetch-verified.sh, the ONE
# verifier every image download goes through, which fetches that same URL a
# second time and compares. There are 3 HTTP reads per digested pin — the index,
# the digest, the re-proof — and the property is not that they are 1 fetch: it
# is that the digest is of the asset of the version this run just resolved, and
# that the verifier agreed before anything was written.
#
# ============================================================================
# EVERY FAILURE NAMES THE PIN, AND AN AGGREGATE RUN COLLECTS BEFORE IT FAILS
# ============================================================================
#
# The reader of this output is a 09:00 Monday run with no author watching it.
# `exit 1` tells them nothing, so every refusal here names the pin, and an
# absent credential names the secret as well. There is no `|| true` and no
# `2>/dev/null` in this file.
#
# Every resolution happens inside a command substitution, and bash UNSETS
# errexit in that subshell unless `inherit_errexit` is on. So `exit 1` killed
# only the subshell, the caller read an empty string, and the run continued.
# Measured on this repository at 8e705f1 — 1 dead index produced
# `bump: STUBGITHUB_VERSION 2.3.0 -> ` with an empty new version, a full pull
# request body listing it, and exit 0. That is the exact defect the paragraph
# above claims is impossible.
#
# `capture` below is the fix, and it does not depend on the shell option:
# `inherit_errexit` arrived in bash 4.4, this repository's scripts also run
# under the bash 3.2 of a mac developer host, and `shopt -s` on an option that
# version does not know is a FATAL error there. The option is set where it
# exists — belt — and every substitution whose failure matters goes through
# `capture`, which reads the status itself — braces. A rule that held only on
# the runner would be a rule the pull request gate could not see.
#
# The aggregate path is COLLECT-THEN-FAIL and not abort-at-the-first-failure:
# every row is resolved, every mover AND every failure is reported, nothing is
# written, and the run exits non-zero. FAIL-NOT-SKIP says a red run must be red
# and must say what it found; the nightly beside it already reduces the verdict
# of the jobs it needs rather than dying at the first one. A weekly that aborted
# at row 1 would let 1 dead coordinate hide the 13 real bumps behind it, and a
# run that reports nothing reads like a quiet week.
#
set -Eeuo pipefail
if [[ "${BASH_VERSINFO[0]}" -gt 4 || ( "${BASH_VERSINFO[0]}" -eq 4 && "${BASH_VERSINFO[1]}" -ge 4 ) ]]; then
  shopt -s inherit_errexit
fi
IFS=$'\n\t'

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIRECTORY"
# Set before the source line, the way .ci/notify-failure.sh sets it: the git
# fallback in _ctl/lib.sh reads the wrong root when this repository is a
# submodule worktree.
REPO_ROOT="$(cd "$SCRIPT_DIRECTORY/.." && pwd)"

# The pin readers and the writer live in _ctl/lib.sh, 1 time only — this file
# and _ctl/tests/pin-mirroring.test.sh drive the same body.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$SCRIPT_DIRECTORY/../_ctl/lib.sh"

# The tree under test. Everything below reads the table, the value homes and the
# governed files under it.
UPSTREAM_ROOT="${UPSTREAM_PROJECT_ROOT:-$REPO_ROOT}"
UPSTREAM_TABLE_RELATIVE="_build/upstreams.txt"
UPSTREAM_TABLE="${UPSTREAM_ROOT}/${UPSTREAM_TABLE_RELATIVE}"

# The verifier comes from THIS file's own directory and not from the tree under
# test: it is the one this repository ships, and a fixture tree carries no copy
# of it.
VERIFIER="${SCRIPT_DIRECTORY}/fetch-verified.sh"

# The files that perform a download. The 6 Dockerfiles are named file by file,
# the way download-coverage.test.sh names them. The components are globbed
# instead, and the difference is deliberate: there, a glob that stopped matching
# would leave a green result that read nothing, and here it makes the pin whose
# URL is in that component FAIL naming itself.
GOVERNED_DOCKERFILES=(
  "base/Dockerfile"
  "runner/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
  "cloud/Dockerfile"
)
COMPONENT_DIRECTORY="_delta/components"

# The ubuntu series the apt datasource asks about when a coordinate names none.
# The archive publishes a different version of a package for every series, and
# the one an image installs is the series its base OS is.
DEFAULT_UBUNTU_SERIES="noble"

# `-` is the digest of a pin that has no bytes to answer for, and the evidence
# beside it.
NO_DIGEST="-"

# ---------------------------------------------------------------------------
# The failures.
# ---------------------------------------------------------------------------

# fail_pin <pin> <message...> — stop, naming the pin.
function fail_pin() {
  local pin="$1"
  shift
  log_error "${pin}: $*"
  exit 1
}

# capture <variable> <command...> — run the command, keep its stdout in
# <variable>, and STOP with its status when it failed.
#
# This is the load-bearing line of the whole file. `x="$(f)"` where f exits 1
# leaves x empty and carries on, because bash unsets errexit inside a command
# substitution on every version before 4.4 and inside every subshell this file's
# resolution runs in. `capture` reads the status instead of trusting the shell
# option, so a dead upstream stops the pin it belongs to on the runner's bash
# 5.2 AND on a mac's bash 3.2 — and the message fail_pin already printed to
# stderr is the last word either way.
#
# `capture` is a function, not a subshell, so its `exit` ends the shell that
# called it: the top-level shell for a single-pin run, and the resolve_pin
# substitution for an aggregate one, where collect_bumps reads the status and
# records the pin. Never capture into a variable named target, output or status.
function capture() {
  local target="$1"
  shift
  local output="" status=0
  output="$("$@")" || status=$?
  if [[ "$status" -ne 0 ]]; then
    exit "$status"
  fi
  printf -v "$target" '%s' "$output"
}

function usage() {
  cat <<EOF
Usage: bash _build/resolve-upstream.sh <PIN>
       bash _build/resolve-upstream.sh --dry-run
       bash _build/resolve-upstream.sh --apply

  <PIN>       resolve 1 pin and print <version>|<sha256>
  --dry-run   resolve every row of ${UPSTREAM_TABLE_RELATIVE} and print the pull
              request it would open, writing nothing
  --apply     the same, and write each bump into every home of its pin
EOF
}

# ---------------------------------------------------------------------------
# The table.
# ---------------------------------------------------------------------------

# table_rows — every row, comments and blank lines dropped.
function table_rows() {
  [[ -f "$UPSTREAM_TABLE" ]] || return 0
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    { line = $0; sub(/[[:space:]]+$/, "", line); print line }
  ' "$UPSTREAM_TABLE"
}

# table_row <pin> — the row that names the pin, or nothing.
#
# The explicit `return 0` at the foot of this function and of the 4 below is not
# tidiness. A `while` or a `for` whose last body statement was a false test
# returns 1, and under `shopt -s inherit_errexit` that status leaves the
# substitution and aborts the caller with no message at all. "I found nothing"
# is an ANSWER here, and the caller decides what it means.
function table_row() {
  local pin="$1" row
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    if [[ "${row%%|*}" == "$pin" ]]; then
      printf '%s' "$row"
      return 0
    fi
  done <<< "$(table_rows)"
  return 0
}

# row_field <row> <index> — 1 field of a row.
function row_field() {
  awk -F'|' -v want="$2" '{ print $want }' <<< "$1"
}

# ---------------------------------------------------------------------------
# The fetches. Both of them name the pin when they fail, and neither has a
# fallback: an unreachable upstream is an answer this run does not have.
# ---------------------------------------------------------------------------

# fetch_document <pin> <url> [header...] — the body, on stdout.
function fetch_document() {
  local pin="$1" url="$2"
  shift 2
  local -a request=(curl -fsSL --max-time 30)
  local header
  for header in "$@"; do
    request+=(-H "$header")
  done
  request+=("$url")
  local body="" status=0
  body="$("${request[@]}")" || status=$?
  if [[ "$status" -ne 0 ]]; then
    fail_pin "$pin" "the fetch of ${url} failed — curl exited ${status}"
  fi
  if [[ -z "$body" ]]; then
    fail_pin "$pin" "${url} answered with an empty document"
  fi
  printf '%s' "$body"
}

# fetch_to_file <pin> <url> <destination> — the bytes, on disk, exactly as
# served. A digest has to be of bytes and not of a shell variable.
function fetch_to_file() {
  local pin="$1" url="$2" destination="$3"
  if ! curl -fsSL --max-time 300 "$url" -o "$destination"; then
    fail_pin "$pin" "the fetch of ${url} failed, so the version that was just resolved has no digest"
  fi
  if [[ ! -s "$destination" ]]; then
    fail_pin "$pin" "${url} served 0 bytes"
  fi
}

# json_value <pin> <document> <filter> — 1 value out of a JSON document.
function json_value() {
  local pin="$1" document="$2" filter="$3"
  local value="" status=0
  value="$(jq -r "$filter" <<< "$document")" || status=$?
  if [[ "$status" -ne 0 ]]; then
    fail_pin "$pin" "the upstream document is not JSON this resolver can read — jq exited ${status}"
  fi
  if [[ -z "$value" || "$value" == "null" ]]; then
    fail_pin "$pin" "the upstream document holds nothing at ${filter}"
  fi
  printf '%s' "$value"
}

# github_headers — the argv the github API reads. The token is optional: only
# the rate limit depends on it.
function github_headers() {
  printf 'Accept: application/vnd.github+json\n'
  local token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  if [[ -n "$token" ]]; then
    printf 'Authorization: Bearer %s\n' "$token"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# The spelling rule.
# ---------------------------------------------------------------------------

# respell <upstream version> <current pin value> — the resolved version, spelled
# the way THIS pin is spelled.
#
# The word an upstream puts in front of the digits is its own convention: a tag
# reads v2.4.0, go1.26.5 or bun-v1.3.14 for the same kind of number. The pin's
# spelling is what the Dockerfile writes into a URL and what the smoke test
# compares, so the prefix of the value being replaced is the prefix that stays.
function respell() {
  local resolved="$1" current="$2"
  local core prefix=""
  core="${resolved#"${resolved%%[0-9]*}"}"
  if [[ -z "$core" ]]; then
    printf '%s' "$resolved"
    return 0
  fi
  if [[ "$current" == *[0-9]* ]]; then
    prefix="${current%%[0-9]*}"
  fi
  printf '%s%s' "$prefix" "$core"
}

# ---------------------------------------------------------------------------
# The datasources. One function each, and each one reads a DOCUMENT the upstream
# publishes rather than scraping a page.
# ---------------------------------------------------------------------------

function resolve_github_release() {
  local pin="$1" coordinate="$2" current="$3"
  local -a headers=()
  local header
  while IFS= read -r header; do
    [[ -z "$header" ]] && continue
    headers+=("$header")
  done <<< "$(github_headers)"

  local document tag shipped
  capture document fetch_document "$pin" \
    "https://api.github.com/repos/${coordinate}/releases/latest" "${headers[@]}"
  capture tag json_value "$pin" "$document" '.tag_name // empty'
  # 1 read for both flags, so there is no bare jq here whose status nothing
  # examines. `releases/latest` already excludes a draft and a prerelease; this
  # is the assertion that it did.
  capture shipped json_value "$pin" "$document" \
    'if (.draft // false) or (.prerelease // false) then "refused" else "shipped" end'
  if [[ "$shipped" != "shipped" ]]; then
    fail_pin "$pin" "the release ${coordinate} marks latest is a draft or a prerelease (${tag}), and a pin never takes one"
  fi
  respell "$tag" "$current"
}

function resolve_pypi() {
  local pin="$1" coordinate="$2" current="$3"
  local document version
  capture document fetch_document "$pin" "https://pypi.org/pypi/${coordinate}/json"
  capture version json_value "$pin" "$document" '.info.version // empty'
  respell "$version" "$current"
}

function resolve_npm() {
  local pin="$1" coordinate="$2" current="$3"
  local document version
  capture document fetch_document "$pin" "https://registry.npmjs.org/${coordinate}"
  capture version json_value "$pin" "$document" '.["dist-tags"].latest // empty'
  respell "$version" "$current"
}

# The archive publishes `1:5.9-6ubuntu2`. The epoch and the debian revision are
# the archive's own bookkeeping: `zsh --version` says 5.9, and 5.9 is what the
# pin holds and what the smoke test compares.
function resolve_apt() {
  local pin="$1" coordinate="$2" current="$3"
  local package="${coordinate%%@*}"
  local series="$DEFAULT_UBUNTU_SERIES"
  if [[ "$coordinate" == *@* ]]; then
    series="${coordinate#*@}"
  fi
  local url document published upstream
  url="https://api.launchpad.net/devel/ubuntu/+archive/primary?ws.op=getPublishedBinaries"
  url="${url}&binary_name=${package}&exact_match=true&status=Published&order_by_date=true"
  url="${url}&distro_arch_series=https%3A%2F%2Fapi.launchpad.net%2Fdevel%2Fubuntu%2F${series}%2Famd64"
  capture document fetch_document "$pin" "$url"
  capture published json_value "$pin" "$document" '.entries[0].binary_package_version // empty'
  upstream="${published#*:}"
  upstream="${upstream%-*}"
  respell "$upstream" "$current"
}

function resolve_go_dl() {
  local pin="$1" coordinate="$2" current="$3"
  local document version
  capture document fetch_document "$pin" "https://${coordinate}.dev/dl/?mode=json"
  capture version json_value "$pin" "$document" '[.[] | select(.stable == true)][0].version // empty'
  respell "$version" "$current"
}

# `lts: false` is a current release and not an LTS line. The newest entry of the
# index is usually one, so a reader that took `.[0]` would pin this image to the
# line node itself calls unsupported for production.
function resolve_node_dist() {
  local pin="$1" coordinate="$2" current="$3"
  local document version filter
  case "$coordinate" in
    lts) filter='[.[] | select(.lts != false)][0].version // empty' ;;
    current) filter='.[0].version // empty' ;;
    *) fail_pin "$pin" "the node-dist coordinate is '${coordinate}', and the 2 this resolver reads are lts and current" ;;
  esac
  capture document fetch_document "$pin" "https://nodejs.org/dist/index.json"
  capture version json_value "$pin" "$document" "$filter"
  respell "$version" "$current"
}

# The digest of a manifest LIST is the sha256 of its own bytes, so this
# datasource returns what it fetched rather than a value out of the document.
# A per-platform digest would take away the choice buildx has to make for the
# platform it builds, and pin the wrong thing.
#
# Which is why the media type of what came back is ASSERTED and not assumed. The
# `Accept` headers below ask for an index; a registry that ignores content
# negotiation answers with the manifest of 1 platform, and hashing that produces
# a perfectly well-formed digest of exactly the wrong thing — silently, with
# every check in this repository still green.
OCI_INDEX_MEDIA_TYPES=(
  "application/vnd.oci.image.index.v1+json"
  "application/vnd.docker.distribution.manifest.list.v2+json"
)

function resolve_oci_index() {
  local pin="$1" coordinate="$2"
  local repository="${coordinate%:*}"
  local reference="${coordinate##*:}"
  if [[ -z "$repository" || -z "$reference" || "$repository" == "$coordinate" ]]; then
    fail_pin "$pin" "the oci-index coordinate is '${coordinate}', and the shape it reads is <repository>:<tag>"
  fi

  local token_document token
  capture token_document fetch_document "$pin" \
    "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${repository}:pull"
  capture token json_value "$pin" "$token_document" '.token // .access_token // empty'

  local staged digest
  staged="$(mktemp)"
  if ! curl -fsSL --max-time 60 \
    -H "Authorization: Bearer ${token}" \
    -H "Accept: application/vnd.oci.image.index.v1+json" \
    -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json" \
    "https://registry-1.docker.io/v2/${repository}/manifests/${reference}" -o "$staged"; then
    rm -f "$staged"
    fail_pin "$pin" "the registry would not serve the manifest of ${coordinate}"
  fi

  local media_type="" known=0 accepted read_status=0
  media_type="$(jq -r '.mediaType // empty' < "$staged")" || read_status=$?
  if [[ "$read_status" -ne 0 ]]; then
    rm -f "$staged"
    fail_pin "$pin" "${coordinate} answered with something that is not JSON, so its media type cannot be read"
  fi
  for accepted in "${OCI_INDEX_MEDIA_TYPES[@]}"; do
    if [[ "$media_type" == "$accepted" ]]; then
      known=1
    fi
  done
  if [[ "$known" -ne 1 ]]; then
    rm -f "$staged"
    log_error "${pin}: ${coordinate} answered with mediaType '${media_type:-<none>}', which is not a manifest list"
    # IFS is $'\n\t' in this file, so [*] would join the 2 names with a newline
    # and the message would read as 2 unrelated log lines.
    log_error "the 2 index media types are: $(IFS=','; printf '%s' "${OCI_INDEX_MEDIA_TYPES[*]}")"
    log_error "hashing a per-platform manifest pins the digest of 1 architecture and takes the choice away from buildx"
    exit 1
  fi

  digest="$(sha256sum "$staged" | awk '{ print $1 }')"
  rm -f "$staged"
  printf 'sha256:%s' "$digest"
}

function resolve_k8s_dl() {
  local pin="$1" coordinate="$2" current="$3"
  local document
  capture document fetch_document "$pin" "https://dl.k8s.io/release/${coordinate}.txt"
  respell "${document//[[:space:]]/}" "$current"
}

function resolve_tailscale_pkgs() {
  local pin="$1" coordinate="$2" current="$3"
  local document version
  capture document fetch_document "$pin" "https://pkgs.tailscale.com/${coordinate}/?mode=json"
  capture version json_value "$pin" "$document" '.Version // empty'
  respell "$version" "$current"
}

# current_release names the hash the channel holds NOW, and the releases list is
# every release of every channel. Reading the first entry of the list instead
# would take whichever release was published last, beta included.
function resolve_flutter_releases() {
  local pin="$1" coordinate="$2" current="$3"
  local document version filter
  filter=".current_release[\"${coordinate}\"] as \$hash"
  filter="${filter} | [.releases[] | select(.channel == \"${coordinate}\" and .hash == \$hash)][0].version // empty"
  capture document fetch_document "$pin" \
    "https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json"
  capture version json_value "$pin" "$document" "$filter"
  respell "$version" "$current"
}

# eden is the ONE decision point for a harness version — its
# harness-upgrade-check is where a new claude/omp/codex is accepted — so this
# datasource mirrors that file rather than resolving the harness upstream.
#
# gophersys/eden is private and this repository's GITHUB_TOKEN is
# repository-scoped, so the read needs a credential of its own. Its absence is a
# FAILURE that names it and never a skip: a resolver that quietly reported the
# current value would report every harness pin as current forever.
# eden_manifest_row <pin> <document> — the `NAME=value` row that manifest holds
# for the pin, or nothing.
function eden_manifest_row() {
  awk -v name="$1" '$0 ~ ("^" name "=") { print; exit }' <<< "$2"
}

function resolve_eden_manifest() {
  local pin="$1" coordinate="$2" current="$3"
  if [[ -z "${EDEN_MANIFEST_READ:-}" ]]; then
    log_error "${pin}: EDEN_MANIFEST_READ is not set, so nothing here can read ${coordinate}"
    log_error "gophersys/eden is private and this repository's GITHUB_TOKEN is repository-scoped"
    log_error "the secret is a fine-grained PAT with contents:read on gophersys/eden alone"
    exit 1
  fi
  local repository="${coordinate%%:*}"
  local path="${coordinate#*:}"
  if [[ -z "$path" || "$path" == "$coordinate" ]]; then
    fail_pin "$pin" "the eden-manifest coordinate is '${coordinate}', and the shape it reads is <owner/repo>:<path>"
  fi

  local document row value
  capture document fetch_document "$pin" "https://api.github.com/repos/${repository}/contents/${path}" \
    "Accept: application/vnd.github.raw" \
    "Authorization: Bearer ${EDEN_MANIFEST_READ}"
  capture row eden_manifest_row "$pin" "$document"
  capture value declaration_value "$row"
  if [[ -z "$value" ]]; then
    fail_pin "$pin" "${coordinate} declares no ${pin}, so there is nothing to mirror"
  fi
  respell "$value" "$current"
}

# ---------------------------------------------------------------------------
# The digest half: which bytes this new version names.
# ---------------------------------------------------------------------------

# governed_files — every file that performs a download, absolute, one per line.
function governed_files() {
  local candidate component
  for candidate in "${GOVERNED_DOCKERFILES[@]}"; do
    if [[ -f "${UPSTREAM_ROOT}/${candidate}" ]]; then
      printf '%s\n' "${UPSTREAM_ROOT}/${candidate}"
    fi
  done
  for component in "${UPSTREAM_ROOT}/${COMPONENT_DIRECTORY}/"*.sh; do
    if [[ -f "$component" ]]; then
      printf '%s\n' "$component"
    fi
  done
  return 0
}

# asset_record <pin> — `<digest pin>|<url>|<case arm>` for the download whose
# URL embeds this pin, or nothing when the pin has no bytes to answer for.
function asset_record() {
  local pin="$1"
  local file record url
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    while IFS= read -r record; do
      [[ -z "$record" ]] && continue
      url="${record#*|}"
      url="${url%%|*}"
      if [[ "$url" == *"\${${pin}}"* ]]; then
        printf '%s' "$record"
        return 0
      fi
    done <<< "$(fetch_urls "$file")"
  done <<< "$(governed_files)"
  return 0
}

# scope_value <case arm> <name> — the value the `linux/amd64)` arm gives a
# variable, or nothing.
function scope_value() {
  awk -v name="$2" '
    {
      for (index_of_field = 1; index_of_field <= NF; index_of_field++) {
        if (index($index_of_field, name "=") == 1) {
          print substr($index_of_field, length(name) + 2)
          exit
        }
      }
    }
  ' <<< "$1"
}

# expand_url <pin> <version> <url> <case arm> — the URL the build will fetch.
#
# 3 kinds of token appear in a download URL, and each has exactly 1 answer: the
# pin being resolved takes the NEW version, a `${ARCH}`-shaped variable takes the
# value the linux/amd64 case arm of that same RUN gives it, and any other name
# is another pin and takes the value its home holds. A token with no answer is a
# FAILURE naming the pin — a URL fetched with `${ARCH}` still in it asks the far
# end for a file whose name carries a dollar sign.
function expand_url() {
  local pin="$1" version="$2" url="$3" scope="$4"
  local rounds=0 name value token
  while [[ "$url" == *"\${"* ]]; do
    rounds=$((rounds + 1))
    if [[ "$rounds" -gt 20 ]]; then
      fail_pin "$pin" "the download url still holds a token after 20 expansions: ${url}"
    fi
    if [[ ! "$url" =~ \$\{([A-Za-z_][A-Za-z0-9_]*)\} ]]; then
      fail_pin "$pin" "the download url holds a token this resolver cannot read: ${url}"
    fi
    name="${BASH_REMATCH[1]}"
    if [[ "$name" == "$pin" ]]; then
      value="$version"
    else
      value="$(scope_value "$scope" "$name")"
      if [[ -z "$value" ]]; then
        value="$(pin_value "$UPSTREAM_ROOT" "$name")"
      fi
    fi
    if [[ -z "$value" ]]; then
      fail_pin "$pin" "the download url reads \${${name}}, and neither the linux/amd64 case arm nor a value home declares it: ${url}"
    fi
    token="\${${name}}"
    url="${url//"$token"/$value}"
  done
  printf '%s' "$url"
}

# digest_of <pin> <url> — the sha256 of the bytes that URL serves now.
function digest_of() {
  local pin="$1" url="$2"
  local staged value
  staged="$(mktemp)"
  fetch_to_file "$pin" "$url" "$staged"
  value="$(sha256sum "$staged" | awk '{ print $1 }')"
  rm -f "$staged"
  printf '%s' "$value"
}

# reprove_digest <pin> <url> <digest> — hand the value back to the ONE verifier
# every image download goes through, before anything is written.
#
# It fetches the asset a second time. That is the point: the digest this run
# computed is proven against the file _build/fetch-verified.sh would compare at
# build time, by that file, rather than by a second copy of its comparison.
function reprove_digest() {
  local pin="$1" url="$2" digest="$3"
  local work
  work="$(mktemp -d)"
  if ! bash "$VERIFIER" "$url" "${work}/asset" "$digest" "$pin"; then
    rm -rf "$work"
    fail_pin "$pin" "the verifier rejected the digest this run computed for ${url}"
  fi
  rm -rf "$work"
}

# ---------------------------------------------------------------------------
# Resolution.
# ---------------------------------------------------------------------------

# resolve_pin <pin> — `<version>|<sha256>` on stdout. Nothing else prints
# there: a caller reads this record, and a log line inside it would be read as
# a version.
function resolve_pin() {
  local pin="$1"
  local row=""
  capture row table_row "$pin"
  if [[ -z "$row" ]]; then
    fail_pin "$pin" "no row of ${UPSTREAM_TABLE_RELATIVE} names it, so nothing says where its next value comes from"
  fi

  local datasource="" coordinate="" reason="" current=""
  capture datasource row_field "$row" 2
  capture coordinate row_field "$row" 3
  capture reason row_field "$row" 4
  capture current pin_value "$UPSTREAM_ROOT" "$pin"
  if [[ -z "$current" ]]; then
    fail_pin "$pin" "no value home under ${UPSTREAM_ROOT} declares it, so there is no value to replace"
  fi

  # Every arm goes through `capture`: the datasource runs in a subshell, and a
  # subshell that died has to end this pin rather than hand back an empty
  # version that reads like a resolution.
  local version=""
  case "$datasource" in
    github-release)   capture version resolve_github_release   "$pin" "$coordinate" "$current" ;;
    pypi)             capture version resolve_pypi             "$pin" "$coordinate" "$current" ;;
    npm)              capture version resolve_npm              "$pin" "$coordinate" "$current" ;;
    apt)              capture version resolve_apt              "$pin" "$coordinate" "$current" ;;
    go-dl)            capture version resolve_go_dl            "$pin" "$coordinate" "$current" ;;
    node-dist)        capture version resolve_node_dist        "$pin" "$coordinate" "$current" ;;
    oci-index)        capture version resolve_oci_index        "$pin" "$coordinate" ;;
    k8s-dl)           capture version resolve_k8s_dl           "$pin" "$coordinate" "$current" ;;
    tailscale-pkgs)   capture version resolve_tailscale_pkgs   "$pin" "$coordinate" "$current" ;;
    flutter-releases) capture version resolve_flutter_releases "$pin" "$coordinate" "$current" ;;
    eden-manifest)    capture version resolve_eden_manifest    "$pin" "$coordinate" "$current" ;;
    no-autobump)
      fail_pin "$pin" "its row resolves nothing, and states why: ${reason}"
      ;;
    *)
      fail_pin "$pin" "its row names the datasource '${datasource}', which nothing here implements"
      ;;
  esac
  if [[ -z "$version" ]]; then
    fail_pin "$pin" "the ${datasource} datasource answered with an empty version"
  fi

  local digest="$NO_DIGEST"
  local record="" url=""
  capture record asset_record "$pin"
  if [[ -n "$record" ]]; then
    url="${record#*|}"
    url="${url%%|*}"
    capture url expand_url "$pin" "$version" "$url" "${record##*|}"
    capture digest digest_of "$pin" "$url"
    reprove_digest "$pin" "$url" "$digest"
  fi

  printf '%s|%s\n' "$version" "$digest"
}

# collect_bumps <movers file> <failures file> — resolve EVERY row, and separate
# what moved from what could not be read.
#
#   <movers file>    `<pin>|<old>|<new>|<digest>`, 1 line per pin that moved
#   <failures file>  the name of every pin whose upstream this run could not
#                    read. Its message is already on stderr, printed at the
#                    moment it happened.
#
#   exit 0        every row resolved
#   exit non-zero at least 1 did, and the failures file names them
#
# 2 files and a status, rather than 1 stream: a caller that read movers and
# failures out of the same stdout would have to tell them apart by shape, and
# the whole point of this function is that a failure can never be read as a
# bump. A row that resolves nothing is skipped BEFORE the resolver is called, so
# the reason its no-autobump row states is honoured rather than being a comment.
#
# The status of each resolution is CAPTURED. `record="$(resolve_pin "$pin")"`
# under `set -e` + `inherit_errexit` would end this loop at the first bad row,
# which is the abort-at-row-1 design this file rejects at the top.
function collect_bumps() {
  local movers_file="$1" failures_file="$2"
  : > "$movers_file"
  : > "$failures_file"
  local row pin datasource current record version digest status
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    pin="${row%%|*}"
    datasource="$(row_field "$row" 2)"
    [[ "$datasource" == "no-autobump" ]] && continue
    current="$(pin_value "$UPSTREAM_ROOT" "$pin")"
    status=0
    record="$(resolve_pin "$pin")" || status=$?
    if [[ "$status" -ne 0 ]]; then
      printf '%s\n' "$pin" >> "$failures_file"
      continue
    fi
    version="${record%%|*}"
    digest="${record#*|}"
    if [[ "$version" != "$current" ]]; then
      printf '%s|%s|%s|%s\n' "$pin" "$current" "$version" "$digest" >> "$movers_file"
    fi
  done <<< "$(table_rows)"
  [[ ! -s "$failures_file" ]]
}

# bump_lines <bumps> — the mover report, 1 line per pin. It is printed on the
# failure path too: 1 dead coordinate must not hide the bumps behind it.
function bump_lines() {
  local bump
  while IFS= read -r bump; do
    [[ -z "$bump" ]] && continue
    printf 'bump: %s %s -> %s\n' \
      "$(row_field "$bump" 1)" "$(row_field "$bump" 2)" "$(row_field "$bump" 3)"
  done <<< "$1"
  return 0
}

# report_failures <failures file> — name every pin this run could not read, and
# say what was NOT done about it.
function report_failures() {
  local failures_file="$1" total pin
  total="$(awk 'NF { total++ } END { print total + 0 }' "$failures_file")"
  log_error "the weekly resolution could not read ${total} upstream(s):"
  while IFS= read -r pin; do
    [[ -z "$pin" ]] && continue
    log_error "  ${pin}"
  done < "$failures_file"
  log_error "nothing was written and no pull request is composed: a run that bumped the pins"
  log_error "it happened to reach would let the absence of the others read as 'nothing moved'"
  log_error "each message above names the pin it belongs to; fix the row or the upstream"
}

# pull_request <bumps> — the pull request the caller would open, on stdout.
function pull_request() {
  local bumps="$1"
  local today total bump
  today="$(date +%Y-%m-%d)"
  total="$(awk 'NF { total++ } END { print total + 0 }' <<< "$bumps")"

  bump_lines "$bumps"

  printf 'branch: ci/weekly-bumps-%s\n' "$today"
  if [[ "$total" -eq 1 ]]; then
    printf 'title: chore(bumps): 1 upstream pin moves (%s)\n' "$today"
  else
    printf 'title: chore(bumps): %s upstream pins move (%s)\n' "$total" "$today"
  fi
  printf 'body:\n'
  printf 'The weekly upstream resolution read %s and these pins moved:\n\n' "$UPSTREAM_TABLE_RELATIVE"
  while IFS= read -r bump; do
    [[ -z "$bump" ]] && continue
    printf -- '- %s: %s -> %s\n' "$(row_field "$bump" 1)" "$(row_field "$bump" 2)" "$(row_field "$bump" 3)"
  done <<< "$bumps"
  printf '\n'
  printf 'Every sha256 above is the digest of the asset for the version beside it, read\n'
  printf 'from that release and re-proven through _build/fetch-verified.sh before this\n'
  printf 'branch was written. Every home of each pin was edited, so the cloud family and\n'
  printf 'the base family move together. Every row of the table resolved: a run with one\n'
  printf 'unreadable upstream writes nothing and opens nothing.\n\n'
  printf 'This pull request merges the way every other one does: validate, review,\n'
  printf 'build-smoke, and a human.\n'
}

# collected_bumps <movers file> <failures file> — resolve everything, report
# every failure, and return the run's verdict. Both callers below start here, so
# the verdict is known BEFORE either of them writes or composes anything.
function collected_bumps() {
  local movers_file="$1" failures_file="$2"
  local status=0
  collect_bumps "$movers_file" "$failures_file" || status=$?
  if [[ "$status" -ne 0 ]]; then
    # The movers first: the reader of a red Monday still needs to know what WOULD
    # have moved, or 1 dead coordinate reads like a quiet week.
    bump_lines "$(cat "$movers_file")"
    report_failures "$failures_file"
  fi
  return "$status"
}

function dry_run() {
  local movers failures status=0
  movers="$(mktemp)"
  failures="$(mktemp)"
  collected_bumps "$movers" "$failures" || status=$?
  if [[ "$status" -ne 0 ]]; then
    rm -f "$movers" "$failures"
    return "$status"
  fi
  local bumps
  bumps="$(cat "$movers")"
  rm -f "$movers" "$failures"
  if [[ -z "$bumps" ]]; then
    printf 'no pin moved\n'
    return 0
  fi
  pull_request "$bumps"
}

function apply_bumps() {
  local movers failures status=0
  movers="$(mktemp)"
  failures="$(mktemp)"
  collected_bumps "$movers" "$failures" || status=$?
  if [[ "$status" -ne 0 ]]; then
    rm -f "$movers" "$failures"
    return "$status"
  fi
  local bumps
  bumps="$(cat "$movers")"
  rm -f "$movers" "$failures"

  local bump pin new digest evidence today
  if [[ -z "$bumps" ]]; then
    printf 'no pin moved\n'
    return 0
  fi
  today="$(date +%Y-%m-%d)"
  while IFS= read -r bump; do
    [[ -z "$bump" ]] && continue
    pin="$(row_field "$bump" 1)"
    new="$(row_field "$bump" 3)"
    digest="$(row_field "$bump" 4)"
    # The digest was computed from the bytes this run fetched, and not read out
    # of a checksum file upstream published, so that is what the row says.
    evidence="computed-at-pin: ${today}"
    if [[ "$digest" == "$NO_DIGEST" ]]; then
      evidence="$NO_DIGEST"
    fi
    bump_pin "$UPSTREAM_ROOT" "$pin" "$new" "$digest" "$evidence" \
      || fail_pin "$pin" "the writer could not put ${new} into every home of it"
  done <<< "$bumps"
  pull_request "$bumps"
}

# ---------------------------------------------------------------------------
# A missing tool is a FAILURE, never a skip. Without sha256sum no digest can be
# computed at all, and a resolver that reported a version with no digest would
# open a bump the build refuses.
# ---------------------------------------------------------------------------
require_cmd curl jq sha256sum

if [[ ! -f "$UPSTREAM_TABLE" ]]; then
  log_error "no upstream table at ${UPSTREAM_TABLE}"
  log_error "it is the 1 place that says where the next value of each pin comes from"
  exit 1
fi

case "${1:-}" in
  --dry-run)
    dry_run
    ;;
  --apply)
    apply_bumps
    ;;
  -h | --help)
    usage
    ;;
  "")
    log_error "usage: bash _build/resolve-upstream.sh <PIN> | --dry-run | --apply"
    exit 2
    ;;
  -*)
    log_error "unknown option: ${1}"
    usage >&2
    exit 2
    ;;
  *)
    resolve_pin "$1"
    ;;
esac
