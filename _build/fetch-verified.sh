#!/usr/bin/env bash
#
# _build/fetch-verified.sh — download an asset and install it only when its
# bytes are the bytes the pin names.
#
#   fetch-verified.sh <url> <destination> <sha256> <pin name>
#
# TLS says the bytes came from the host the URL names. It says nothing about
# WHICH bytes that host served, so a compromised release asset, a re-tagged
# upstream release or a mirror that answers first all install silently. The
# comparison below is the whole difference, and every download of every image
# goes through this one file — base and cloud COPY it to
# /usr/local/lib/gophersys/ above their first download layer, and the 4 child
# images inherit it through their FROM.
#
# The contract, in the order the failures matter:
#
#   empty <sha256>      REFUSED before the fetch, naming <pin name>. An unset
#                       build-arg expands to the empty string, so this is the
#                       shape of a pin that never arrived — and the download
#                       would otherwise be compared against nothing.
#   not 64 hex          REFUSED before the fetch, naming <pin name>. 63
#                       characters reads as correct in a diff.
#   sha256sum absent    REFUSED. FAIL-NOT-SKIP: a helper that installs what it
#                       cannot verify is an unverified download wearing the
#                       name of a verified one.
#   digest mismatch     REFUSED, naming <pin name>, and NOTHING is left at
#                       <destination> — a half-written binary on PATH is worse
#                       than no binary, because the next layer runs it.
#
# Every refusal names the pin because the caller reads this inside 400 lines of
# `docker build` layer noise, where "exit 1" tells them nothing and
# `YQ_SHA256_AMD64` tells them the row to fix.
#
# It carries its own bash shebang and is EXECUTED, never sourced: base switches
# SHELL to zsh after oh-my-zsh, so a helper that inherited the calling shell
# would behave differently in 2 of the 6 images.
#
# The URL scheme is deliberately not restricted. `curl --proto '=https'` would
# harden this against a plaintext URL nobody writes, and it would blind
# _ctl/tests/fetch-verified.test.sh, which drives this file over file:// because
# a hermetic case in the pull request gate cannot reach the network. The
# hardening worth having is the digest.
#
set -Eeuo pipefail
IFS=$'\n\t'

PROGRAM="fetch-verified.sh"

function fatal() {
  echo "FATAL: ${PROGRAM}: $*" >&2
  exit 1
}

if [[ "$#" -ne 4 ]]; then
  fatal "want 4 arguments — <url> <destination> <sha256> <pin name> — and got $#"
fi

URL="$1"
DESTINATION="$2"
DIGEST="$3"
PIN="$4"

[[ -n "$URL" ]]         || fatal "${PIN}: the url argument is empty"
[[ -n "$DESTINATION" ]] || fatal "${PIN}: the destination argument is empty"
[[ -n "$PIN" ]]         || fatal "the pin-name argument is empty, so no failure below could name the row to fix"

# The digest is judged on the ARGUMENT, before anything is fetched. A helper
# that downloaded first would die inside curl on a build-arg that never
# arrived, and curl's transport error says nothing about which pin was wrong.
if [[ -z "$DIGEST" ]]; then
  fatal "${PIN} is empty — no pin reached this build, so the download would be compared against nothing"
fi
if [[ ! "$DIGEST" =~ ^[0-9a-f]{64}$ ]]; then
  fatal "${PIN} is not 64 lowercase hex characters: '${DIGEST}' (${#DIGEST} characters)"
fi

if ! command -v sha256sum > /dev/null 2>&1; then
  fatal "${PIN}: sha256sum is not on PATH, so nothing here can verify ${URL}"
fi

# The staging directory is NOT beside the destination. The mismatch case has to
# leave the destination directory exactly as it found it, and a temp file
# written next to the target is a leftover a later layer can pick up.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGED="${WORK}/asset"

if ! curl -fsSL "$URL" -o "$STAGED"; then
  fatal "${PIN}: the fetch of ${URL} failed"
fi

if ! printf '%s  %s\n' "$DIGEST" "$STAGED" | sha256sum -c - > /dev/null 2>&1; then
  fatal "${PIN} does not match ${URL}: want ${DIGEST}, got $(sha256sum "$STAGED" | awk '{ print $1 }')"
fi

mkdir -p "$(dirname "$DESTINATION")"
mv "$STAGED" "$DESTINATION"
