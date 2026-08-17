#!/usr/bin/env bash
#
# _ctl/lib.sh — the shared ctl library for gophersys/.devcontainer.
#
# The body of every per-image verb lives here, 1 time only. Each per-image
# ctl.sh sets its metadata, sources this file, and dispatches into it. Before
# this file existed, the 5 per-image scripts each carried the same 140 lines,
# and 6 scripts each carried a copy of the push guard.
#
# The repo-root ctl.sh and .ci/ctl.sh source this file for the logging, the
# tool gate and the guard. Their own verbs act on the whole set of images, so
# they keep those verbs themselves.
#
# The pattern is the same one that gophersys/libs uses in go/_ctl/lib.sh. The
# directory name starts with an underscore, so Nx and Go ignore it. It is not
# an image directory.
#
# A sourcing script sets this metadata BEFORE the source line, because this
# file reads it while it loads:
#   PROJECT_ROOT           Required. The directory that holds the script.
#   IMAGE_NAME             Required for the image verbs. Example: flutter.
#   IMAGE_PLATFORMS        Optional. The default is SANCTIONED_PLATFORMS. Set it
#                          only to declare a measured narrower target, and give
#                          the measurement. Every entry must still be sanctioned.
#   IMAGE_BUILD_ARGS       Optional array. Extra arguments for docker build.
#   IMAGE_BUILD_CONTEXT    Optional. The build context directory. The default
#                          is PROJECT_ROOT. The cloud image sets the repository
#                          root, because versions.env and _delta/ sit one level
#                          above its directory.
#   IMAGE_DOCKERFILE       Optional. An explicit --file for docker build. The
#                          default is empty, which keeps docker's own default:
#                          <context>/Dockerfile. Set it whenever
#                          IMAGE_BUILD_CONTEXT is not the image directory.
#
# This metadata is read at call time, so a script can set it after the source
# line, for example to use a value that this file computes:
#   IMAGE_USAGE_HEADER     Optional text. Extra lines below the Image: header.
#   IMAGE_USAGE_COMMANDS   Optional text. Extra lines below the command list.
#
# shellcheck shell=bash

set -Eeuo pipefail
IFS=$'\n\t'

: "${PROJECT_ROOT:?_ctl/lib.sh: the sourcing ctl.sh must set PROJECT_ROOT}"

# REPO_ROOT is advisory. A script that runs inside the container reads a
# bind-mounted repository, where a different uid trips the dubious-ownership
# guard of git. Fall back to PROJECT_ROOT, so no script stops at startup.
if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PROJECT_ROOT")"
fi
export REPO_ROOT

# Every image of this repository is published under 1 registry namespace.
IMAGE_REGISTRY_NAMESPACE="ghcr.io/gophersys"

# The platforms a published image of this repository may carry. This list is the
# single source of truth: the guard, the build, the push and verify-published
# all read it, and nothing else declares a platform.
#
# 1 entry. No arm64 consumer can be verified for any image — gophersys/
# infrastructure docs/debt-register.md D42 — and the arm64 half that was
# published was an amd64 Ubuntu userland carrying aarch64 Go binaries, so it was
# mislabelled rather than native. Widen this list on the day a consumer exists,
# and not before.
SANCTIONED_PLATFORMS="linux/amd64"

# The platforms THIS image builds. Overridable, so an image can declare a
# measured narrower target the way runner/ctl.sh once did. Wider is not a
# choice: require_sanctioned_platforms refuses an entry outside the set above,
# and BOTH image_build and image_push call it. `build` needs it as much as
# `push` does, because `build` tags the official ref on the developer's host.
: "${IMAGE_PLATFORMS:=$SANCTIONED_PLATFORMS}"

if [[ -n "${IMAGE_NAME:-}" ]]; then
  IMAGE_REF="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:latest"
fi

# Extra arguments for docker build. The runner layer threads its parent through
# BASE_IMAGE here. Declare the array only if the sourcing script did not.
if ! declare -p IMAGE_BUILD_ARGS >/dev/null 2>&1; then
  IMAGE_BUILD_ARGS=()
fi

# versions_env_build_args <file> — append one `--build-arg NAME=value` to
# IMAGE_BUILD_ARGS for every pin line of a versions.env file. This is how the
# one-home rule reaches docker: versions.env holds the value, the Dockerfile
# declares a value-less ARG, and this function is the only bridge between them.
# A trailing `# comment` on a line is stripped; a non-empty line without `=` is
# a FAILURE that names the line, because a silently skipped pin would surface
# later as an empty version in a download URL.
function versions_env_build_args() {
  local file="$1" line name value
  if [[ ! -f "$file" ]]; then
    log_error "versions file not found: ${file}"
    exit 1
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" ]] && continue
    if [[ "$line" != *=* ]]; then
      log_error "unreadable pin line in ${file}: '${line}' — want NAME=value"
      exit 1
    fi
    name="${line%%=*}"
    value="${line#*=}"
    IMAGE_BUILD_ARGS+=(--build-arg "${name}=${value}")
  done < "$file"
}

# -------- logging --------
function log_info()  { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()  { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# -------- tripwire: the retired platform-list variable --------
# IMAGE_PLATFORMS was named MULTI_ARCH_* until arm64 was dropped. Both names now
# hold the same string, so a caller that still sets the old one gets the right
# platform by accident and nothing ever says the rename was missed. This fires
# at source time, on the name being set, whatever its value.
#
# The prefix match is why the retired name appears in the message and nowhere in
# this file: the same name check that finds a missed rename would otherwise find
# the tripwire itself.
_retired_platform_vars=("${!MULTI_ARCH@}")
if [[ ${#_retired_platform_vars[@]} -gt 0 ]]; then
  _retired_names="$(IFS=' '; printf '%s' "${_retired_platform_vars[*]}")"
  log_error "retired variable set: ${_retired_names} — rename it to IMAGE_PLATFORMS"
  log_error "it holds the same string IMAGE_PLATFORMS does, so nothing else would report the miss"
  exit 1
fi
unset _retired_platform_vars

# -------- tool gate --------
# A missing tool is a failure, never a skip.
function require_cmd() {
  local missing=()
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

# Guard: docker and docker buildx must be present. A verb that acts on the
# whole set of images calls this alone, because the platform list is not the
# same for every image.
function require_buildx() {
  require_cmd docker
  if ! docker buildx version >/dev/null 2>&1; then
    log_error "docker buildx is not installed — every publish of this repository goes through buildx"
    exit 127
  fi
}

# Guard: the platform list must be non-empty, and every entry must be in the
# sanctioned set. This is the condition that makes a re-added arm64 fail loudly
# at the guard instead of quietly restoring an emulated build, so it names the
# offending platform rather than only the list.
function require_sanctioned_platforms() {
  if [[ -z "${IMAGE_PLATFORMS:-}" ]]; then
    log_error "IMAGE_PLATFORMS is empty — the guard cannot enforce a platform"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$IMAGE_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if [[ ",${SANCTIONED_PLATFORMS}," != *",${p},"* ]]; then
      log_error "unsanctioned platform: ${p}"
      log_error "the sanctioned set is ${SANCTIONED_PLATFORMS}, declared in _ctl/lib.sh"
      log_error "widen SANCTIONED_PLATFORMS there, with a consumer you measured, before you publish another one"
      exit 1
    fi
  done
}

# Guard: the platform list must be sanctioned AND buildx must be able to build
# every entry on it. A verb that pushes MUST call this first.
#
# The guard fails closed in 5 conditions: a platform outside the sanctioned set,
# an empty platform list, buildx absent, no builder active, or the active
# builder unable to build 1 of the required platforms.
function require_buildx_and_platforms() {
  require_sanctioned_platforms
  require_buildx
  if ! docker buildx inspect >/dev/null 2>&1; then
    log_error "no active buildx builder — run: docker buildx create --use --name gophersys"
    exit 1
  fi
  local platforms
  platforms="$(docker buildx inspect --bootstrap 2>/dev/null | awk -F': ' '/^Platforms/ {print $2}' | head -1)"
  if [[ -z "$platforms" ]]; then
    log_error "buildx builder reports no platforms; cannot enforce a platform"
    exit 1
  fi
  local p
  local -a _platforms
  IFS=',' read -r -a _platforms <<< "$IMAGE_PLATFORMS"
  for p in "${_platforms[@]}"; do
    if ! printf '%s' "$platforms" | grep -q -- "$p"; then
      log_error "buildx builder missing required platform: $p"
      log_error "current builder platforms: $platforms"
      # Not a binfmt problem. An amd64 host builds linux/amd64 natively, and
      # Docker Desktop on Apple Silicon offers it too, so a builder that does not
      # list the 1 sanctioned platform did not bootstrap rather than lacking
      # emulation. The binfmt hint that used to be here was for the arm64 half.
      log_error "the builder did not bootstrap; recreate it: docker buildx create --use --name gophersys"
      exit 1
    fi
  done
}

# -------- the base OS pin, and its currency --------
# base/Dockerfile and cloud/Dockerfile build FROM ubuntu at a DIGEST, so the
# commit decides the image: under the moving tag, 2 builds of 1 commit produce 2
# different operating systems and verify-published cannot say which one it read.
#
# The pin freezes the base OS until a bump merges, which is why the 2 readers
# below ship with it. A pin that nothing watches is a snapshot that looks current
# forever, and the nightly is what reports the move.
BASE_IMAGE_REFERENCE="ubuntu:24.04"
BASE_IMAGE_PIN_NAME="UBUNTU_BASE_REF"
BASE_IMAGE_PIN_HOME="versions.env"

# base_image_digest [reference] — the digest the REGISTRY holds for that
# reference now, 1 line on stdout.
#
# It asks the registry and never a file: a reader that answered out of
# versions.env would agree with the pin on every night, including the ones where
# upstream moved. A read that fails is a FAILURE and never a digest, because a
# digest returned on a read that did not happen reports the base OS as current on
# a night when nothing could be read at all.
#
# The client is the one a human runs by hand to resolve a bump, so the pin and
# the check are read the same way.
function base_image_digest() {
  local reference="${1:-$BASE_IMAGE_REFERENCE}"
  require_cmd docker
  local digest="" read_status=0
  digest="$(docker buildx imagetools inspect "$reference" --format '{{.Manifest.Digest}}')" || read_status=$?
  if [[ "$read_status" -ne 0 ]]; then
    log_error "cannot read the digest of ${reference}: the registry client exited ${read_status}"
    return 1
  fi
  if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    log_error "the registry client answered something that is not a digest for ${reference}: '${digest}'"
    return 1
  fi
  printf '%s\n' "$digest"
}

# base_image_pin — the digest BASE_IMAGE_PIN_HOME declares, comment stripped.
function base_image_pin() {
  local home="${REPO_ROOT}/${BASE_IMAGE_PIN_HOME}"
  if [[ ! -f "$home" ]]; then
    log_error "the base OS pin home is absent: ${home}"
    return 1
  fi
  awk -v name="$BASE_IMAGE_PIN_NAME" '
    index($0, name "=") == 1 {
      value = substr($0, length(name) + 2)
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$home"
}

# require_base_image_current [reference] — exit 0 while the registry still holds
# the digest the pin names, non-zero naming BOTH digests when it moved. The
# reader of a 09:00 UTC — 02:00 MST — nightly failure needs both, or the next
# step is to run the read by hand.
function require_base_image_current() {
  local reference="${1:-$BASE_IMAGE_REFERENCE}"
  local pinned=""
  pinned="$(base_image_pin)" || return 1
  if [[ -z "$pinned" ]]; then
    log_error "${BASE_IMAGE_PIN_HOME} declares no ${BASE_IMAGE_PIN_NAME}, so there is no pin to compare the registry with"
    return 1
  fi
  local current=""
  current="$(base_image_digest "$reference")" || return 1
  if [[ "$current" == "$pinned" ]]; then
    log_info "${reference} still holds the pinned digest ${pinned}"
    return 0
  fi
  log_error "${reference} moved — the registry no longer holds the digest this repository pins"
  log_error "  pinned in ${BASE_IMAGE_PIN_HOME}: ${pinned}"
  log_error "  held by the registry now:        ${current}"
  log_error "bump ${BASE_IMAGE_PIN_NAME} in ${BASE_IMAGE_PIN_HOME} and in the base/Dockerfile ARG block, in 1 commit"
  return 1
}

# -------- the pin homes: the readers, and the writer --------
# A pin is declared in 1 or 2 of the 6 value homes: a `NAME=value` row in
# versions.env for the cloud family, and an `ARG NAME=value` at the top of a
# Dockerfile for the base family. 3 callers read that shape — the coverage
# tests, the mirroring test and _build/resolve-upstream.sh — so the readers live
# here once, by the rule that puts a verb body in this file 1 time (ledger #100).
#
# Every one of them takes an explicit ROOT. The resolver runs against a fixture
# tree as readily as against this repository, and a reader that assumed
# REPO_ROOT would answer about the wrong files.
PIN_VALUE_HOMES=(
  "versions.env"
  "base/Dockerfile"
  "runner/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
)

# declaration_line <file> <name> — the line that declares <name> WITH a value,
# in either home shape. Prints nothing when the file does not declare it, or
# declares it value-less as cloud/Dockerfile does.
function declaration_line() {
  local file="$1" name="$2"
  [[ -f "$file" ]] || return 0
  awk -v name="$name" '
    $0 ~ ("^[[:space:]]*ARG[[:space:]]+" name "=") { print; next }
    $0 ~ ("^" name "=") { print }
  ' "$file"
}

# declaration_value <line> — the value a declaration line carries: everything
# after the first `=`, up to the first whitespace. The trailing comment and the
# alignment spaces before it are not part of the value.
function declaration_value() {
  local line="$1"
  awk '
    {
      position = index($0, "=")
      if (position == 0) { print ""; next }
      rest = substr($0, position + 1)
      split(rest, parts, /[[:space:]]/)
      print parts[1]
    }
  ' <<< "$line"
}

# homes_of <root> <name> [home...] — every home that declares <name> with a
# value, 1 relative path per line, in the order the home list gives. With no
# home named the 6 value homes are read.
function homes_of() {
  local root="$1" name="$2"
  shift 2
  local -a homes=("$@")
  if [[ "${#homes[@]}" -eq 0 ]]; then
    homes=("${PIN_VALUE_HOMES[@]}")
  fi
  local home out=""
  for home in "${homes[@]}"; do
    if [[ -n "$(declaration_line "${root}/${home}" "$name")" ]]; then
      out="${out:+${out}
}${home}"
    fi
  done
  printf '%s' "$out"
}

# pin_value <root> <name> — the value the first home holding <name> declares.
#
# The explicit `return 0` at the foot of this function and of digest_row_of is
# load-bearing for _build/resolve-upstream.sh, which runs under
# `shopt -s inherit_errexit`: a `for` loop whose last statement was a false test
# returns 1, that status leaves the command substitution, and the caller dies
# with no message. "No home declares it" is an ANSWER, and the caller decides
# what it means.
function pin_value() {
  local root="$1" name="$2"
  local home
  for home in "${PIN_VALUE_HOMES[@]}"; do
    local line
    line="$(declaration_line "${root}/${home}" "$name")"
    if [[ -n "$line" ]]; then
      declaration_value "$line"
      return 0
    fi
  done
  return 0
}

# digest_row_of <root> <name> — the `<tool>_SHA256_<ARCH>` row that sits beside
# the pin, or nothing when the pin has no bytes to answer for. YQ_VERSION ->
# YQ_SHA256_AMD64; about 30 of the 56 pins (go install, corepack, pipx) have no
# such row at all.
function digest_row_of() {
  local root="$1" name="$2"
  local tool="$name" home found
  tool="${tool%_VERSION}"
  tool="${tool%_REF}"
  tool="${tool%_CHANNEL}"
  for home in "${PIN_VALUE_HOMES[@]}"; do
    [[ -f "${root}/${home}" ]] || continue
    found="$(awk -v tool="$tool" '
      /^[[:space:]]*#/ { next }
      {
        line = $0
        sub(/^[[:space:]]*ARG[[:space:]]+/, "", line)
        position = index(line, "=")
        if (position == 0) { next }
        candidate = substr(line, 1, position - 1)
        if (candidate !~ ("^" tool "_SHA256_[A-Z0-9_]+$")) { next }
        print candidate
        exit
      }
    ' "${root}/${home}")"
    if [[ -n "$found" ]]; then
      printf '%s' "$found"
      return 0
    fi
  done
  return 0
}

# evidence_of <line> — `upstream-published`, `computed-at-pin` or the empty
# string. The 2 spellings are the whole vocabulary: either upstream published a
# checksum file and the 2 agreed, or the value was computed when the pin was
# taken and the row says on what day.
function evidence_of() {
  local line="$1"
  if [[ "$line" =~ \#[[:space:]]*upstream-published:[[:space:]]*https?://[^[:space:]]+ ]]; then
    printf 'upstream-published'
  elif [[ "$line" =~ \#[[:space:]]*computed-at-pin:[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
    printf 'computed-at-pin'
  fi
}

# fetch_urls <file> — 1 record per VERIFIED download the file performs:
#
#   <digest pin name>|<url exactly as the file writes it>|<var>=<value> ...
#
# The URL of a download lives in the file that FETCHES it and nowhere else, so
# this is how the resolver learns which bytes a digest answers for. A second
# copy of the URL in a table would let it compute a correct digest of the wrong
# asset.
#
# The 3rd field is the `linux/amd64)` case arm in scope at that fetch. `${ARCH}`
# is not a pin and not a table field: it is a shell variable the RUN block sets
# from the 1 sanctioned platform, and the same file spells it amd64, x64 and
# x86_64 in different arms — so the arm is read per RUN and not per file. A
# Dockerfile RUN resets the set; a component script has 1 arm for the whole
# file and accumulates.
#
# `ARCH="$(dpkg --print-architecture)"` is the SECOND shape of that same
# question, and zephyr-devbox asks it that way. It is read only while
# SANCTIONED_PLATFORMS holds 1 platform, because that is the only condition
# under which the answer is known without running dpkg — and a guessed
# architecture would compute a correct digest of the wrong asset.
#
# Continuation lines are joined first, because a Dockerfile writes 1 command
# across 4 lines and a line-at-a-time reader sees a fetch with no URL and a URL
# with no fetch.
function fetch_urls() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  local sanctioned_arch=""
  if [[ "$SANCTIONED_PLATFORMS" != *,* ]]; then
    sanctioned_arch="${SANCTIONED_PLATFORMS##*/}"
  fi
  awk -v sanctioned_arch="$sanctioned_arch" '
    function reset_scope(   key) { for (key in scope) { delete scope[key] } }

    function collect_scope(text,   rest, position, terminator, arm, count, index_of_word, words, name, value) {
      rest = text
      while ((position = index(rest, "linux/amd64)")) > 0) {
        rest = substr(rest, position + 12)
        terminator = index(rest, ";;")
        if (terminator > 0) {
          arm = substr(rest, 1, terminator - 1)
          rest = substr(rest, terminator + 2)
        } else {
          arm = rest
          rest = ""
        }
        count = split(arm, words, /[;[:space:]]+/)
        for (index_of_word = 1; index_of_word <= count; index_of_word++) {
          if (words[index_of_word] !~ /^[A-Za-z_][A-Za-z0-9_]*=/) { continue }
          name = words[index_of_word]
          sub(/=.*$/, "", name)
          value = substr(words[index_of_word], length(name) + 2)
          gsub(/^["'"'"']|["'"'"']$/, "", value)
          scope[name] = value
        }
      }
      if (sanctioned_arch == "") { return }
      rest = text
      while (match(rest, /[A-Za-z_][A-Za-z0-9_]*="?\$\(dpkg --print-architecture\)"?/)) {
        arm = substr(rest, RSTART, RLENGTH)
        rest = substr(rest, RSTART + RLENGTH)
        name = arm
        sub(/=.*$/, "", name)
        scope[name] = sanctioned_arch
      }
    }

    function scope_text(   key, out) {
      out = ""
      for (key in scope) { out = out (out == "" ? "" : " ") key "=" scope[key] }
      return out
    }

    function emit(text,   count, index_of_part, parts, part, digest, url) {
      count = split(text, parts, /&&/)
      for (index_of_part = 1; index_of_part <= count; index_of_part++) {
        part = parts[index_of_part]
        if (part !~ /fetch-verified\.sh/) { continue }
        if (!match(part, /\$\{[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+\}/)) { continue }
        digest = substr(part, RSTART + 2, RLENGTH - 3)
        if (!match(part, /https?:\/\/[^"'"'"'[:space:]\\]+/)) { continue }
        url = substr(part, RSTART, RLENGTH)
        printf "%s|%s|%s\n", digest, url, scope_text()
      }
    }

    {
      line = $0
      if (line ~ /^[[:space:]]*#/) { next }
      sub(/[[:space:]]+$/, "", line)
      if (line ~ /\\$/) {
        sub(/\\$/, "", line)
        if (buffer == "" && line ~ /^[[:space:]]*RUN[[:space:]]/) { reset_scope() }
        buffer = buffer line " "
        next
      }
      if (buffer == "" && line ~ /^[[:space:]]*RUN[[:space:]]/) { reset_scope() }
      collect_scope(buffer line)
      emit(buffer line)
      buffer = ""
    }
    END { if (buffer != "") { collect_scope(buffer); emit(buffer) } }
  ' "$file"
}

# bump_pin <root> <pin> <version> <digest> <evidence> — write 1 bump into EVERY
# home of the pin, and into no other line.
#
#   <digest>    64 lowercase hex, or `-` when the pin carries no digest row —
#               the marker _build/resolve-upstream.sh prints for such a pin.
#   <evidence>  the comment the digest row carries: `upstream-published: <url>`
#               or `computed-at-pin: <yyyy-mm-dd>`, and `-` beside a `-` digest.
#
# A pin no home declares is a FAILURE that names it. The weekly run reads its
# pins out of _build/upstreams.txt, and a row whose pin was renamed in the homes
# would otherwise write nothing and report a green Monday.
function bump_pin() {
  local root="$1" pin="$2" version="$3" digest="$4" evidence="$5"
  if [[ -z "$version" ]]; then
    log_error "bump_pin: ${pin}: the version argument is empty"
    return 1
  fi
  if [[ "$digest" != "-" && ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then
    log_error "bump_pin: ${pin}: the digest '${digest}' is neither 64 lowercase hex nor '-'"
    return 1
  fi
  local homes
  homes="$(homes_of "$root" "$pin")"
  if [[ -z "$homes" ]]; then
    log_error "bump_pin: no value home under ${root} declares ${pin}"
    log_error "the 6 homes are: ${PIN_VALUE_HOMES[*]}"
    return 1
  fi
  local digest_row=""
  if [[ "$digest" != "-" ]]; then
    digest_row="$(digest_row_of "$root" "$pin")"
    if [[ -z "$digest_row" ]]; then
      log_error "bump_pin: ${pin}: a digest was given and no home declares a <tool>_SHA256_<ARCH> row beside the pin"
      return 1
    fi
  fi
  local today home
  today="$(date +%Y-%m-%d)"
  while IFS= read -r home; do
    [[ -z "$home" ]] && continue
    rewrite_declaration "${root}/${home}" "$pin" "$version" "version" "$today" || return 1
    if [[ -n "$digest_row" && -n "$(declaration_line "${root}/${home}" "$digest_row")" ]]; then
      rewrite_declaration "${root}/${home}" "$digest_row" "$digest" "digest" "$evidence" || return 1
    fi
  done <<< "$homes"
  return 0
}

# rewrite_declaration <file> <name> <value> <mode> <extra> — replace the value
# of 1 declaration, in place, and leave every other line of the file alone.
#
#   mode version   <extra> is today's date, and it replaces the yyyy-mm-dd the
#                  trailing comment claims. The convention is that a version row
#                  and its date comment move together: the date records the day
#                  somebody looked, and a stale one reads as current forever.
#   mode digest    <extra> is the evidence, and it becomes the whole comment.
#                  A digest with no evidence is a number a reviewer takes on
#                  faith.
#
# The comment keeps the column it had, so a bump stays a 1-token diff in a file
# whose comments are aligned.
function rewrite_declaration() {
  local file="$1" name="$2" value="$3" mode="$4" extra="$5"
  if [[ ! -f "$file" ]]; then
    log_error "rewrite_declaration: no such file: ${file}"
    return 1
  fi
  local staged
  staged="$(mktemp)"
  if ! awk -v name="$name" -v value="$value" -v mode="$mode" -v extra="$extra" '
    function is_declaration(line) {
      return (line ~ ("^[[:space:]]*ARG[[:space:]]+" name "=")) || (line ~ ("^" name "="))
    }
    {
      if (!is_declaration($0)) { print; next }
      position = index($0, name "=")
      head = substr($0, 1, position + length(name))
      rest = substr($0, position + length(name) + 1)
      match(rest, /^[^ \t]*/)
      old = substr(rest, RSTART, RLENGTH)
      tail = substr(rest, RSTART + RLENGTH)
      comment = tail
      sub(/^[ \t]+/, "", comment)
      spacing = length(tail) - length(comment)
      if (mode == "digest") {
        comment = "# " extra
      } else if (comment != "") {
        gsub(/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/, extra, comment)
      }
      if (comment == "") { print head value; next }
      padding = length(old) + spacing - length(value)
      if (padding < 2) { padding = 2 }
      printf "%s%s%*s%s\n", head, value, padding, "", comment
    }
  ' "$file" > "$staged"; then
    rm -f "$staged"
    log_error "rewrite_declaration: could not rewrite ${name} in ${file}"
    return 1
  fi
  # Written back through the existing file rather than moved over it: a mv from
  # the temporary directory would carry mktemp's 0600 mode onto a tracked file.
  cat "$staged" > "$file"
  rm -f "$staged"
}

# -------- no EXIT trap, and that is deliberate --------
# The 8 scripts of this repository each carried the same cleanup block: a
# BG_PIDS array, an on_exit function that killed the pids, and `trap on_exit
# EXIT`. Nothing ever added a pid to BG_PIDS, and no script starts a background
# job. The block killed nothing.
#
# It was not free. On bash 3.2, which is the bash of macOS and the bash that
# runs these scripts on a developer host, `$?` is 0 when the EXIT trap starts
# after the shell aborts on an unbound variable. Measured on this repository:
# with the trap, a script that aborts on an unbound variable exits 0. Without
# the trap, it exits 1. The block turned a fatal abort into a reported success.
#
# A script that starts a background job must clean up its own job, and it must
# not add an EXIT trap that returns a status.

# -------- image verbs --------
function image_build() {
  require_cmd docker
  # The same membership rule `push` uses. `build` tags the OFFICIAL ref, so an
  # unsanctioned platform here puts a mislabelled image on the developer's host
  # under the name the registry publishes — the exact defect this policy ends.
  require_sanctioned_platforms
  # --platform is explicit because a bare `docker build` builds for the HOST.
  # On an Apple Silicon host that is arm64, so the local image would not be the
  # image that gets published.
  if [[ "$IMAGE_PLATFORMS" == *,* ]]; then
    log_error "IMAGE_PLATFORMS holds more than 1 platform: ${IMAGE_PLATFORMS}"
    log_error "docker build produces 1 image; use push, which builds through buildx"
    exit 1
  fi
  log_info "building ${IMAGE_REF} (${IMAGE_PLATFORMS})"
  local -a file_args=()
  if [[ -n "${IMAGE_DOCKERFILE:-}" ]]; then
    file_args=(--file "${IMAGE_DOCKERFILE}")
  fi
  docker build \
    --platform "${IMAGE_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    "${file_args[@]+"${file_args[@]}"}" \
    -t "${IMAGE_REF}" \
    "${IMAGE_BUILD_CONTEXT:-$PROJECT_ROOT}"
}

function image_push() {
  require_buildx_and_platforms
  require_cmd git
  local short_sha image_ref_sha
  short_sha="$(git -C "$PROJECT_ROOT" rev-parse --short=7 HEAD 2>/dev/null || true)"
  if [[ -z "$short_sha" ]]; then
    log_error "cannot determine short SHA for tag; is $PROJECT_ROOT a git repo?"
    exit 1
  fi
  image_ref_sha="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:${short_sha}"
  log_info "buildx (${IMAGE_PLATFORMS}) + push to ${IMAGE_REF} and ${image_ref_sha}"
  local -a file_args=()
  if [[ -n "${IMAGE_DOCKERFILE:-}" ]]; then
    file_args=(--file "${IMAGE_DOCKERFILE}")
  fi
  docker buildx build \
    --platform "${IMAGE_PLATFORMS}" \
    "${IMAGE_BUILD_ARGS[@]+"${IMAGE_BUILD_ARGS[@]}"}" \
    "${file_args[@]+"${file_args[@]}"}" \
    --tag "${IMAGE_REF}" \
    --tag "${image_ref_sha}" \
    --push \
    "${IMAGE_BUILD_CONTEXT:-$PROJECT_ROOT}"
}

# verify-published [tag] — read the manifest of a published tag and assert it
# carries EXACTLY the sanctioned set. A push declares a platform; this reads
# what the registry actually holds.
#
# An entry whose platform is unknown/unknown is an attestation manifest, not an
# image. buildx attaches 1 per variant on every push, so counting the entries
# reads a correct single-platform image as 2 platforms.
function image_verify_published() {
  require_buildx
  require_cmd jq
  local tag="${1:-latest}"
  local ref="${IMAGE_REGISTRY_NAMESPACE}/${IMAGE_NAME}:${tag}"
  log_info "reading the published manifest of ${ref}"

  # The 2 streams are kept apart on purpose. Merged, a client that writes a
  # warning to stderr on an otherwise successful read puts that warning inside
  # the JSON, and the parse fails for a reason that has nothing to do with the
  # manifest.
  local raw="" read_status=0 client_stderr
  client_stderr="$(mktemp)"
  raw="$(docker buildx imagetools inspect --raw "$ref" 2>"$client_stderr")" || read_status=$?
  if [[ "$read_status" -ne 0 ]]; then
    # The client's own words. A verdict about a manifest that was never read
    # describes a state nobody observed, which is how this repository once
    # documented a cluster it had not looked at.
    log_error "cannot read the manifest of ${ref}: the registry client exited ${read_status}"
    cat "$client_stderr" >&2
    rm -f "$client_stderr"
    exit 1
  fi
  rm -f "$client_stderr"

  local published="" parse_status=0
  published="$(printf '%s' "$raw" | jq -r '
    [ .manifests[]?
      | select(.platform != null)
      | select(.platform.os != "unknown" and .platform.architecture != "unknown")
      | .platform.os + "/" + .platform.architecture
        + (if .platform.variant then "/" + .platform.variant else "" end)
    ] | unique | join(",")
  ')" || parse_status=$?
  if [[ "$parse_status" -ne 0 ]]; then
    log_error "the manifest of ${ref} is not an image index this verb can read (jq exited ${parse_status})"
    printf '%s\n' "$raw" >&2
    exit 1
  fi

  local sanctioned
  sanctioned="$(jq -rn --arg s "$SANCTIONED_PLATFORMS" '$s | split(",") | unique | join(",")')"

  if [[ "$published" == "$sanctioned" ]]; then
    log_info "verify-published: ${ref} carries exactly ${published}"
    return 0
  fi

  log_error "verify-published: ${ref} does not carry the sanctioned platform set"
  log_error "  published:  ${published:-<the index declares no image platform>}"
  log_error "  sanctioned: ${sanctioned}"
  local p
  local -a _published
  IFS=',' read -r -a _published <<< "$published"
  for p in "${_published[@]+"${_published[@]}"}"; do
    if [[ ",${sanctioned}," != *",${p},"* ]]; then
      log_error "  published but not sanctioned: ${p}"
    fi
  done
  exit 1
}

function image_pull() {
  require_cmd docker
  log_info "pulling ${IMAGE_REF}"
  docker pull "${IMAGE_REF}"
}

function image_inspect() {
  require_cmd docker
  docker image inspect "${IMAGE_REF}"
}

# -------- usage --------
# This block is the specification of the per-image interface. An image that adds
# a verb adds its line through IMAGE_USAGE_COMMANDS.
function image_usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Image: ${IMAGE_REF}${IMAGE_USAGE_HEADER:-}

Commands:
  build                   Build for ${IMAGE_PLATFORMS} (fast local loop)
  push                    GUARDED buildx build + push for ${IMAGE_PLATFORMS}
  verify-published [tag]  Assert the manifest published at [tag] (default latest)
                          carries exactly ${SANCTIONED_PLATFORMS}
  pull                    docker pull ${IMAGE_REF}
  inspect                 docker image inspect ${IMAGE_REF}${IMAGE_USAGE_COMMANDS:-}
  help                    Show this message
EOF
}

# -------- dispatcher --------
# A per-image ctl.sh that adds a verb handles that verb itself, then sends every
# other verb here.
function image_main() {
  : "${IMAGE_NAME:?_ctl/lib.sh: the sourcing ctl.sh must set IMAGE_NAME}"
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)             image_build             "$@" ;;
    push)              image_push              "$@" ;;
    verify-published)  image_verify_published  "$@" ;;
    pull)              image_pull              "$@" ;;
    inspect)           image_inspect           "$@" ;;
    help|"")           image_usage ;;
    *)                 log_error "unknown command: '$cmd'"; image_usage; exit 1 ;;
  esac
}
