#!/usr/bin/env bash
#
# _ctl/tests/download-coverage.test.sh — every download is answered for.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike a real build, it runs in the PULL REQUEST gate.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# The Dockerfiles and _delta/components/*.sh performed 55 URL fetches between
# them the day this rule was written, and 4 of the 55
# compared the bytes against a digest: docker-compose and docker-buildx, twice
# each. The other 51 took whatever the far end sent. TLS says the bytes came
# from the host the URL names; it says nothing about WHICH bytes that host
# served, so a compromised release asset, a re-tagged upstream release, or a
# mirror that answers first all install silently and publish to ghcr.io under
# the repository's own name.
#
# The hole is invisible in review. `curl -fsSL "https://.../yq_linux_amd64" -o
# /usr/local/bin/yq` is a correct-looking line. Nothing in it is wrong. What is
# missing is a comparison that nobody can see is missing, which is why this has
# to be a rule and not a habit.
#
# ============================================================================
# THE RULE THIS FILE ENCODES
# ============================================================================
#
# Every URL fetch in a governed file is answered exactly once, in 1 of 2 ways:
#
#   VERIFIED   the fetch goes through _build/fetch-verified.sh and passes it a
#              ${<TOOL>_SHA256_<ARCH>} in the SAME command;
#   EXEMPT     the fetch carries exactly 1 row in _build/download-exemptions.txt
#              naming a stated class and a reason.
#
# Nothing else counts. A download that is neither is a download nobody decided
# about, and the test names it.
#
# The classes that are NOT in the exemption file, because the reader never sees
# a URL for them and so this rule cannot reach them, are named here so the
# reader knows what is out of scope and what covers each one instead:
#
#   apt packages          the repository signature over the Release file
#   go install ...@vX     GOSUMDB + the module checksum database
#   corepack / npm        the registry's own integrity field
#   uv pip / pipx         PyPI
#
# ============================================================================
# BOTH DIRECTIONS, AND WHY (THE #107 GHOST LESSON)
# ============================================================================
#
# A coverage rule that only asks "is every download answered" is half a rule.
# The other half is "does every answer still describe a download". #107 is the
# shape: a rule that reads a LISTING instead of reading what the FILE CONSUMES
# goes on reporting coverage after the thing it covers was deleted or rewritten.
# The listing agrees with itself forever, and the number it reports is the
# number of rows in the listing.
#
# So the reader here never reads the exemption file as a source of truth. It
# reads the fetch commands out of the governed files, and it then holds the
# exemption file to THEM:
#
#   unclassified   a fetch with no digest and no row     -> report the fetch
#   ghost          a row naming a (file, url) no fetch holds -> report the row
#   double         a fetch that carries BOTH answers     -> report the fetch
#   repeated       2 rows for 1 fetch                    -> report the row
#
# ============================================================================
# THE EXEMPTION FILE GRAMMAR
# ============================================================================
#
#   <governed file>|<url exactly as the file writes it>|<class>|<reason>
#
# 4 fields, none empty. `#` rows and blank rows are prose. The url field is the
# token the file itself writes — `${OH_MY_ZSH_INSTALL_URL}` and
# `https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz` are both written
# exactly as they appear — because a row that paraphrases the URL is a row that
# survives a rewrite of the line it claims to answer.
#
# The 2 classes:
#
#   unversioned-url      the bytes move with no version to pin, so a digest
#                        would break the build the day upstream edits the file
#   not-installed-today  no image consumes this file (ledger #103)
#
# ============================================================================
# WHY THE DIGEST MUST BE NAMED AT THE FETCH, AND NOT VIA A LOCAL
# ============================================================================
#
# The 4 verified downloads that exist today set `SHA256=` in a `case` arm and
# then compare `${SHA256}`. The reader would have to follow that assignment to
# know which pin is in play, and a reader that follows assignments is a reader
# that can be fooled by one. So the rule asks for the pin NAME in the fetch
# command itself. That is also what the sanctioned-platform policy already
# implies: 1 platform means 1 arm, so the `case` has nothing left to choose.
#
# ============================================================================
# THE COPY THAT PUTS THE HELPER IN THE IMAGE, AND WHY IT IS ASSERTED HERE
# ============================================================================
#
# Every rule above reads a fetch COMMAND. Not one of them reads whether the
# file that command calls is in the image at the moment it runs. The verifier
# measured the hole on 2026-08-17: delete `COPY _build/ /usr/local/lib/gophersys/`
# from cloud/Dockerfile and all 378 checks the suite held that day stayed green,
# while every routed download dies at build time with "not found" — the whole
# verification programme resting on a line nothing watched.
#
# It is 2 conditions and not 1, because presence alone is satisfied by a COPY
# that arrives too late. A layer runs against the filesystem the layers ABOVE
# it left, so the COPY must sit above the FIRST call:
#
#   base and cloud   build FROM ubuntu with the repository root as their build
#                    context, so each carries the COPY itself, above its first
#                    fetch. base/ctl.sh and cloud/ctl.sh set
#                    IMAGE_BUILD_CONTEXT for exactly this reason.
#   the other 4      build FROM an image of this repository and inherit the
#                    file through their FROM. The body of a verb lives 1 time,
#                    and this is that rule applied to the fetch-and-compare
#                    body.
#
# Usage: bash _ctl/tests/download-coverage.test.sh
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

TEST_NAME="download-coverage.test.sh"

# The helper every verified download goes through, and the file that answers
# for the ones that take a class instead. Both are named as literals: a test
# that discovers the path it checks agrees with any path, a wrong one included.
FETCH_HELPER="_build/fetch-verified.sh"
EXEMPTIONS_FILE="_build/download-exemptions.txt"

# The 2 halves of the COPY that puts that helper into an image, and the path
# the RUN layers then call. Literals, for the reason above them: a test that
# reads the path it checks agrees with any path, a wrong one included.
HELPER_BUILD_DIRECTORY="_build/"
HELPER_IMAGE_DIRECTORY="/usr/local/lib/gophersys/"
HELPER_IMAGE_PATH="/usr/local/lib/gophersys/fetch-verified.sh"
HELPER_COPY_TEXT="COPY ${HELPER_BUILD_DIRECTORY} ${HELPER_IMAGE_DIRECTORY}"

# The 2 Dockerfiles that build FROM ubuntu with the repository root as their
# build context, and therefore carry that COPY themselves. The other 4 build
# FROM an image of this repository and inherit the file through their FROM.
HELPER_COPY_DOCKERFILES=(
  "base/Dockerfile"
  "cloud/Dockerfile"
)

# Every file this rule governs. Named file by file rather than found by a glob,
# for the reason platform-policy.test.sh names its list: a glob that stops
# matching leaves a green result that read nothing. The component list is
# checked against the directory below, so adding a component is an edit HERE.
GOVERNED_DOCKERFILES=(
  "base/Dockerfile"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
  "cloud/Dockerfile"
)

# ===========================================================================
# THE DOCKERFILES THIS RULE DELIBERATELY DOES NOT GOVERN, AND WHY
# ===========================================================================
#
# A rule that governs 5 of 6 files is a rule with a hole in it, unless the 6th
# is a DECISION somebody wrote down. `hardware/Dockerfile` is that decision, and
# it is recorded here the way the exemption FILE records one — a class, a reason
# and a check — rather than by being absent from a list nobody reads.
#
# The reason: it performs ZERO URL fetches. Its 2 install layers are
# `add-apt-repository` + `apt-get install` and `pip3 install`, and both are in
# the "out of scope" list at the top of this file: apt is covered by the
# repository signature over the Release file, and pip by PyPI. The KiCad PPA's
# signing key is fetched by add-apt-repository itself and then SIGNS that
# Release file, so the packages ride apt's own chain — there is no URL written
# in this file for a digest or an exemption row to answer.
#
# An empty answer is exactly what a broken reader also produces, which is why
# the exemption is CHECKED rather than stated. The rule below reads the same
# fetch_sites this file reads its governed files with, and demands that it find
# NOTHING here. Add a `curl` to hardware/Dockerfile tomorrow and the file stops
# being exempt: the check goes red naming the fetch, instead of the download
# living in the 1 Dockerfile no coverage rule opens.
#
# It is a LIST and not a single path because the decision generalises: an image
# whose whole install surface is apt and pip belongs here, and one that fetches
# a tarball belongs in GOVERNED_DOCKERFILES. The check under section 2 holds the
# 2 lists to the set of Dockerfiles that really exist, so a 7th image can land
# in neither only by turning that check red.
UNGOVERNED_DOCKERFILES=(
  "hardware/Dockerfile"
)
UNGOVERNED_REASON="every install is apt or pip, which this rule states are out of its scope"

COMPONENT_DIRECTORY="_delta/components"
GOVERNED_COMPONENTS=(
  "agents.sh"
  "ansible.sh"
  "aws.sh"
  "buildx.sh"
  "comforts.sh"
  "db-clients.sh"
  "delve.sh"
  "k9s.sh"
  "oci.sh"
  "protocols.sh"
  "runner.sh"
  "terraform.sh"
)

# The 4 pin homes that hold a VALUE. `base/Dockerfile` and `cloud/Dockerfile`
# declare their ARGs value-less and take the value from versions.env, so
# neither is a home. It is the same list as PIN_VALUE_HOMES in _ctl/lib.sh, and
# it is spelled as a LITERAL on purpose: a test that reads the list it checks
# agrees with any list, a wrong one included.
#
# THIS LIST WAS WRONG AND GREEN, and the 2 guards below it are why it cannot be
# again. It named `runner/Dockerfile` after that file was deleted and
# `base/Dockerfile` after that file went value-less, and all 61 checks passed:
# `declared_digest_names` returns nothing for a file it cannot open, and
# nothing for a file that declares no value, so both dead entries contributed 0
# digests and every rule below narrowed silently. Coverage that shrinks with no
# red is the exact failure this whole file exists to prevent, 1 layer up.
CLOUD_HOME="versions.env"
CLOUD_DOCKERFILE="cloud/Dockerfile"
VALUE_HOMES=(
  "versions.env"
  "flutter/Dockerfile"
  "zephyr/Dockerfile"
  "zephyr-devbox/Dockerfile"
)

# The 1 arch vocabulary. A literal, exactly as platform-policy.test.sh spells
# SANCTIONED as a literal: a test that reads the vocabulary it checks agrees
# with 2 vocabularies as happily as with 1, and the second one is where a pin
# hides. _NOARCH is the spelling for an asset that serves every platform.
#
# The vocabulary names the PLATFORM and never the upstream asset spelling —
# compose writes x86_64/aarch64 and buildx writes amd64/arm64 for the same 2
# platforms, and following the asset gave 2 vocabularies per arch.
#
# _SHA256_ARM64 is HERE and it was not, and the rule that kept it out was
# INVERTED rather than deleted. "No _ARM64 row while the set is linux/amd64
# alone" was correct then: a digest for a platform nothing builds is a check
# that cannot fail. A row now exists for every SANCTIONED platform, and the
# failure the rule names is the other one — a platform in the set with no row,
# whose leg of the build reaches its download with an empty digest.
DIGEST_SUFFIXES=("AMD64" "ARM64" "NOARCH")
DIGEST_SUFFIXES_TEXT="_SHA256_AMD64, _SHA256_ARM64, _SHA256_NOARCH"

# The exemption taxonomy. A 3rd class is not a class, it is a hole with a name.
EXEMPTION_CLASSES=("unversioned-url" "not-installed-today")
EXEMPTION_CLASSES_TEXT="unversioned-url, not-installed-today"

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
FIXTURE_DIR="$TESTS_DIR/fixtures/download-coverage"
FIXTURE_DOCKERFILE="$FIXTURE_DIR/Dockerfile"
FIXTURE_COMPONENT="$FIXTURE_DIR/component.sh"
FIXTURE_EXEMPTIONS="$FIXTURE_DIR/exemptions.txt"
FIXTURE_HOME_GOOD="$FIXTURE_DIR/home-good.Dockerfile"
FIXTURE_HOME_BAD="$FIXTURE_DIR/home-bad.Dockerfile"
FIXTURE_HOME_OTHER="$FIXTURE_DIR/home-other.env"
FIXTURE_COPY_ABOVE="$FIXTURE_DIR/copy-above.Dockerfile"
FIXTURE_COPY_BELOW="$FIXTURE_DIR/copy-below.Dockerfile"
FIXTURE_COPY_ABSENT="$FIXTURE_DIR/copy-absent.Dockerfile"

# The fixture for the reader capability the 2-platform set introduced: a fetch
# that names a case arm's LOCAL instead of its pin. Every other fixture here
# spells its digest literally in the fetch command, so all of them pass against
# a reader that ignores locals — which is exactly the reader this file had.
FIXTURE_ARM_LOCAL="$FIXTURE_DIR/arm-local.Dockerfile"
FIXTURE_ARM_LOCAL_LABEL="download-coverage/arm-local.Dockerfile"

# ---------------------------------------------------------------------------
# The readers.
#
# awk and not `grep | cut` throughout: grep exits 1 when it matches nothing, and
# under `set -e` with pipefail that kills the run instead of reporting an empty
# result. An empty result is a defect this file has to REPORT, so it must
# survive reading one.
# ---------------------------------------------------------------------------

# fetch_sites <label> <file> — 1 record per URL fetch the file performs:
#
#   <label>|<url>|<state>|<digest pin name>
#
#   state = verified              the fetch calls the helper AND names a digest
#           helper-without-digest the fetch calls the helper and names none
#           plain                 curl or wget, no helper
#
# The reader joins continuation lines first, because a Dockerfile writes 1
# command across 4 lines and a line-at-a-time reader sees a `curl` with no URL
# and a URL with no `curl`. It then splits the joined text on the shell's
# command separators, so a 20-command RUN layer yields 20 commands and each one
# is judged on its own.
#
# A comment line is dropped BEFORE the join, which is what the builder itself
# does with a comment inside a RUN continuation — and it is why the URL written
# in prose at the bottom of the fixture is not read as a download.
#
# ===========================================================================
# IT FOLLOWS THE CASE ARM'S LOCALS, BECAUSE THE FETCH STOPPED SPELLING THE PIN
# ===========================================================================
#
# With 1 sanctioned platform the `case` had nothing to choose, so every fetch
# named its digest literally: `"${YQ_SHA256_AMD64}"` sat in the fetch-verified
# argument list and a reader that matched that token in the command was enough.
# With 2 platforms the arm chooses, so the arm sets `SHA256` and `SHA256_PIN`
# and the fetch spells `"${SHA256}" "${SHA256_PIN}"`. The token is no longer in
# the command.
#
# So this reader reported EVERY verified download in the repository as a helper
# call that passes no digest — 39 of them, all correct. That is not a literal to
# flip: the reader has to learn the shape, and the shape is the one `fetch_urls`
# in _ctl/lib.sh already reads. Both are the same 3 functions on purpose. A
# second shape here would be a second answer to "what does this fetch verify".
#
# ===========================================================================
# EVERY ARM, AND THAT SENTENCE ABOVE WAS FALSE FOR A WHILE
# ===========================================================================
#
# The twin claim was written when both readers collected from `linux/amd64)`
# arms alone. `fetch_urls` then learned every arm — it has to, because it emits
# a record per arm and the writer refuses a partial row set — and this half did
# not move. The comment went on promising a twin-ness that no longer existed,
# which is the worse half of the defect: the 2 readers disagreed about what the
# same file says, and the comment said they could not.
#
# What an amd64-only reader gets wrong here is a FALSE RED, and it is reachable
# from the real tree in both directions: a download published for arm64 alone is
# assigned by the arm64 arm only, and flutter's Android RUN opens
# `linux/amd64) : ;;` — a guard arm that assigns nothing at all. Either way the
# amd64 arm is empty-handed and a correct, verified download reads as a helper
# call passing no digest. This file's whole purpose is to report unanswered
# downloads, so a false red here costs it the reader's trust in every real one.
#
# ONE RECORD PER FETCH is still the shape, and that is the 1 deliberate
# difference from `fetch_urls`: the coverage rule keys on `<file>|<url>`, and a
# record per arm would make 2 rows out of 1 download whose URL template is
# written once. So the arms are tried IN THE ORDER THE FILE WRITES THEM and the
# first one that resolves a `${<TOOL>_SHA256_<ARCH>}` token answers. Every real
# 2-armed RUN writes amd64 first, so this changes no answer that was already
# right; it adds the ones the amd64 arm could not give.
#
# It resolves a local ONLY where an arm assigned it a
# `${<TOOL>_SHA256_<ARCH>}` token. A general assignment-follower is a reader an
# assignment can fool: `SHA256=deadbeef` in an arm would then read as a verified
# download, and the whole rule is about what the helper COMPARES.
#
# An arm is read as the text between `linux/<arch>)` and the `;;` that follows
# it on the same logical line, which is why "a case arm stays on ONE line" is a
# rule of this repository and not a taste. The scope resets at each RUN, so one
# layer's SHA256 cannot answer for the next layer's fetch; a component .sh has
# no RUN line, its case sits at the top of the file, and the scope it builds
# reaches every fetch below it — which is exactly how those files are written.
function fetch_sites() {
  local label="$1" file="$2"
  awk -v label="$label" '
    function reset_scope(   key) {
      for (key in scope) { delete scope[key] }
      for (key in scope_names) { delete scope_names[key] }
      for (key in platform_seen) { delete platform_seen[key] }
      platform_count = 0
    }

    # The arms keep the order the file writes them in. awk iterates an array in
    # no order at all, and "the first arm that answers" has to mean the first
    # one WRITTEN or the reader gives 2 answers on 2 runs of the same file.
    function remember_platform(platform) {
      if (platform in platform_seen) { return }
      platform_seen[platform] = 1
      platform_order[++platform_count] = platform
    }

    function collect_scope(text,   rest, platform, terminator, arm, count, index_of_word, words, name, value) {
      rest = text
      while (match(rest, /linux\/[a-z0-9]+(\/[a-z0-9]+)*\)/)) {
        platform = substr(rest, RSTART, RLENGTH - 1)
        rest = substr(rest, RSTART + RLENGTH)
        terminator = index(rest, ";;")
        if (terminator > 0) {
          arm = substr(rest, 1, terminator - 1)
          rest = substr(rest, terminator + 2)
        } else {
          arm = rest
          rest = ""
        }
        remember_platform(platform)
        count = split(arm, words, /[;[:space:]]+/)
        for (index_of_word = 1; index_of_word <= count; index_of_word++) {
          if (words[index_of_word] !~ /^[A-Za-z_][A-Za-z0-9_]*=/) { continue }
          name = words[index_of_word]
          sub(/=.*$/, "", name)
          value = substr(words[index_of_word], length(name) + 2)
          gsub(/^"|"$/, "", value)
          gsub(/^'\''|'\''$/, "", value)
          if (!((platform, name) in scope)) {
            scope_names[platform] = scope_names[platform] (scope_names[platform] == "" ? "" : " ") name
          }
          scope[platform, name] = value
        }
      }
    }

    function resolve_in_arm(text, platform,   count, index_of_name, names, key, out) {
      out = text
      if (scope_names[platform] == "") { return out }
      count = split(scope_names[platform], names, / /)
      for (index_of_name = 1; index_of_name <= count; index_of_name++) {
        key = names[index_of_name]
        if (scope[platform, key] !~ /^\$\{[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+\}$/) { continue }
        gsub("\\$\\{" key "\\}", scope[platform, key], out)
      }
      return out
    }

    # Every arm, in written order, and the FIRST that resolves a digest token
    # answers. An amd64-only reader reports a download that only the arm64 arm
    # assigns as a helper call passing no digest — a red naming a defect nobody
    # committed.
    function resolve_digest_locals(text,   index_of_platform, candidate) {
      for (index_of_platform = 1; index_of_platform <= platform_count; index_of_platform++) {
        candidate = resolve_in_arm(text, platform_order[index_of_platform])
        if (match(candidate, /\$\{[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+\}/)) { return candidate }
      }
      return text
    }

    function classify(text,   count, i, parts, part, resolved, url, state, digest) {
      gsub(/&&/, "\n", text)
      gsub(/\|\|/, "\n", text)
      gsub(/;/, "\n", text)
      gsub(/\|/, "\n", text)
      count = split(text, parts, "\n")
      for (i = 1; i <= count; i++) {
        part = parts[i]
        sub(/^[[:space:]]*RUN[[:space:]]+/, "", part)
        sub(/^[[:space:]]+/, "", part)

        if (part ~ /^(curl|wget)[[:space:]]/) {
          state = "plain"
        } else if (part ~ /^[^[:space:]]*fetch-verified\.sh[[:space:]]/) {
          state = "helper-without-digest"
        } else {
          continue
        }

        digest = ""
        resolved = resolve_digest_locals(part)
        if (match(resolved, /\$\{[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+\}/)) {
          digest = substr(resolved, RSTART + 2, RLENGTH - 3)
          if (state == "helper-without-digest") { state = "verified" }
        }

        # The URL is matched in the ORIGINAL text. The record carries it exactly
        # as the file writes it, ${ARCH} unexpanded, because that token is what
        # a _build/download-exemptions.txt row keys on.
        url = "<no-url>"
        if (match(part, /https?:\/\/[^"'\''[:space:]\\]+/)) {
          url = substr(part, RSTART, RLENGTH)
        } else if (match(part, /\$\{[A-Za-z_][A-Za-z0-9_]*_URL\}/)) {
          url = substr(part, RSTART, RLENGTH)
        }

        printf "%s|%s|%s|%s\n", label, url, state, digest
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
      classify(buffer line)
      buffer = ""
    }
    END { if (buffer != "") { collect_scope(buffer); classify(buffer) } }
  ' "$file"
}

# exemption_rows <file> — the rows of an exemption file, comments and blank
# rows dropped, trailing whitespace stripped. Prints nothing for a file with no
# rows, and the caller reports that rather than dying on it.
function exemption_rows() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    line ~ /^[[:space:]]*$/ { next }
    { sub(/[[:space:]]+$/, "", line); print line }
  ' "$file"
}

# row_keys <rows> — the `<file>|<url>` key of every row, in the order given.
function row_keys() {
  local rows="$1"
  awk -F'|' 'NF >= 2 { print $1 "|" $2 }' <<< "$rows"
}

# site_keys <sites> — the `<file>|<url>` key of every fetch site.
function site_keys() {
  local sites="$1"
  awk -F'|' 'NF >= 2 { print $1 "|" $2 }' <<< "$sites"
}

# sites_in_state <sites> <state> — the keys of every site in 1 state.
function sites_in_state() {
  local sites="$1" state="$2"
  awk -F'|' -v want="$state" '$3 == want { print $1 "|" $2 }' <<< "$sites"
}

# keys_absent_from <keys> <reference> — every key of the first list the second
# list does not hold. Prints nothing when the first list is covered.
function keys_absent_from() {
  local keys="$1" reference="$2"
  local key out=""
  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    if ! grep -qxF -- "$key" <<< "$reference"; then
      out="${out:+${out}
}${key}"
    fi
  done <<< "$keys"
  printf '%s' "$out"
}

# keys_present_in <keys> <reference> — the mirror: every key of the first list
# the second list DOES hold. This is how a double-classified fetch is found.
function keys_present_in() {
  local keys="$1" reference="$2"
  local key out=""
  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    if grep -qxF -- "$key" <<< "$reference"; then
      out="${out:+${out}
}${key}"
    fi
  done <<< "$keys"
  printf '%s' "$out"
}

# repeated_keys <keys> — every key the list holds more than once.
function repeated_keys() {
  printf '%s\n' "$1" | awk 'NF' | sort | uniq -d
}

# malformed_rows <rows> — every row that is not 4 non-empty fields.
function malformed_rows() {
  local rows="$1"
  awk -F'|' '
    NF == 0 { next }
    {
      bad = 0
      if (NF != 4) { bad = 1 }
      else {
        for (i = 1; i <= 4; i++) {
          field = $i
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", field)
          if (field == "") { bad = 1 }
        }
      }
      if (bad) { print $0 }
    }
  ' <<< "$rows"
}

# rows_with_an_unknown_class <rows> — every row whose 3rd field is outside the
# taxonomy. A typo classifies a download into nothing while looking like an
# answer.
function rows_with_an_unknown_class() {
  local rows="$1"
  local row class known valid out=""
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    class="$(awk -F'|' '{ print $3 }' <<< "$row")"
    known=0
    for valid in "${EXEMPTION_CLASSES[@]}"; do
      if [[ "$class" == "$valid" ]]; then
        known=1
      fi
    done
    if [[ "$known" -eq 0 ]]; then
      out="${out:+${out}
}${row}"
    fi
  done <<< "$rows"
  printf '%s' "$out"
}

# count_lines <text> — how many non-empty lines the text holds.
function count_lines() {
  local text="$1" line total=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    total=$((total + 1))
  done <<< "$text"
  printf '%s' "$total"
}

# joined <item...> — 1 item per line, sorted. For comparing 2 sets in 1 check.
function joined() {
  printf '%s\n' "$@" | sort
}

# ---------------------------------------------------------------------------
# The readers of rule 2: a digest lives where its version lives, and it says
# where its value came from.
# ---------------------------------------------------------------------------

# digest_references <file> — every ${<TOOL>_SHA256_<ARCH>} the file references,
# 1 name per line, comments excluded.
#
# The arch suffix is [A-Z0-9_]+ and not [A-Z0-9]+, and the underscore is the
# whole point: the 2 spellings this change REMOVES are `_X86_64` and
# `_AARCH64`, and a pattern without the underscore reads neither. Measured
# here on the first run of this file — the vocabulary rule reported
# DOCKER_COMPOSE_SHA256_AARCH64 and stayed silent about
# DOCKER_COMPOSE_SHA256_X86_64, which is the exact pin the migration exists to
# move. A detector blind to the shape it is hunting is a detector that cannot
# fail on it.
function digest_references() {
  local file="$1"
  awk '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    {
      while (match(line, /\$\{[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+\}/)) {
        print substr(line, RSTART + 2, RLENGTH - 3)
        line = substr(line, RSTART + RLENGTH)
      }
    }
  ' "$file"
}

# declaration_line, declaration_value, homes_of and evidence_of are NOT here.
#
# They live in _ctl/lib.sh, which this file already sources, by the rule that
# puts a verb body in the library 1 time (ledger #100). They were written here
# first and moved out when a second caller appeared: _build/resolve-upstream.sh
# reads the same pin homes to decide what a bump would write.
# `_ctl/tests/runner-residue-mirroring.test.sh` was a third caller, holding the
# 2 homes of a pin to 1 value; it is deleted with `runner/`, because the pair it
# read was `versions.env` ∩ `runner/Dockerfile` and no pin has 2 homes now.
# 2 copies of "what does this file declare for that name" are 2 answers
# that are free to disagree, and the one that disagrees is the one nothing runs.
#
# `homes_of` takes a ROOT first there — `homes_of <root> <name> [home...]` —
# because the resolver runs against a fixture tree as readily as against this
# repository. Every call below passes "$REPO_ROOT" and its own home list, so the
# library never falls back to its default set.

# declared_digest_names <file> — every <TOOL>_SHA256_<ARCH> the file declares
# WITH a value, 1 per line.
function declared_digest_names() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    match(line, /^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+=/) {
      token = substr(line, RSTART, RLENGTH)
      sub(/^[[:space:]]*ARG[[:space:]]+/, "", token)
      sub(/=$/, "", token)
      print token
      next
    }
    match(line, /^[A-Za-z_][A-Za-z0-9_]*_SHA256_[A-Z0-9_]+=/) {
      token = substr(line, RSTART, RLENGTH)
      sub(/=$/, "", token)
      print token
    }
  ' "$file"
}

# valueless_args <file> — every name declared as a bare `ARG NAME`, which is
# how cloud/Dockerfile takes a value from versions.env.
function valueless_args() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    match(line, /^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*(#.*)?$/) {
      sub(/^[[:space:]]*ARG[[:space:]]+/, "", line)
      sub(/[[:space:]].*$/, "", line)
      print line
    }
  ' "$file"
}

# pin_gate_names <file> — every name cloud/Dockerfile's `: "${NAME:?...}"` gate
# refuses to build without.
function pin_gate_names() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    {
      line = $0
      while (match(line, /\$\{[A-Za-z_][A-Za-z0-9_]*:\?/)) {
        token = substr(line, RSTART + 2, RLENGTH - 4)
        print token
        line = substr(line, RSTART + RLENGTH)
      }
    }
  ' "$file"
}

# version_name_of <digest name> — the pin the digest belongs beside:
# YQ_SHA256_AMD64 -> YQ. The caller then looks for YQ_VERSION, YQ_REF or
# YQ_CHANNEL, which are the 3 version-shaped suffixes dockerfile-args.test.sh
# governs.
function tool_of() {
  local name="$1"
  printf '%s' "${name%%_SHA256_*}"
}

# version_pin_of <tool> <home...> — the version-shaped pin name that <tool>
# carries, and the homes it lives in, as `<NAME>|<home>,<home>`. Prints nothing
# when no home names the tool at all.
function version_pin_of() {
  local tool="$1"
  shift
  local suffix candidate found=""
  for suffix in "_VERSION" "_REF" "_CHANNEL"; do
    candidate="${tool}${suffix}"
    found="$(homes_of "$REPO_ROOT" "$candidate" "$@")"
    if [[ -n "$found" ]]; then
      printf '%s|%s' "$candidate" "$(tr '\n' ',' <<< "$found")"
      return 0
    fi
  done
  return 0
}

# ---------------------------------------------------------------------------
# The rule-2 detectors. Each takes an explicit home list, so the fixture world
# and the real tree run through the SAME code.
# ---------------------------------------------------------------------------

# bad_vocabulary <names> — every referenced digest name outside the 1 arch
# vocabulary.
function bad_vocabulary() {
  local names="$1"
  local name suffix known valid out=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    suffix="${name##*_SHA256_}"
    known=0
    for valid in "${DIGEST_SUFFIXES[@]}"; do
      if [[ "$suffix" == "$valid" ]]; then
        known=1
      fi
    done
    if [[ "$known" -eq 0 ]]; then
      out="${out:+${out}
}${name}"
    fi
  done <<< "$(sort -u <<< "$names")"
  printf '%s' "$out"
}

# home_mismatches <names> <home...> — every referenced digest whose home set is
# not its version pin's home set, reported with both sets.
function home_mismatches() {
  local names="$1"
  shift
  local name tool pin pin_name pin_homes digest_homes out=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    tool="$(tool_of "$name")"
    pin="$(version_pin_of "$tool" "$@")"
    [[ -z "$pin" ]] && continue
    pin_name="${pin%%|*}"
    pin_homes="${pin#*|}"
    pin_homes="${pin_homes%,}"
    digest_homes="$(tr '\n' ',' <<< "$(homes_of "$REPO_ROOT" "$name" "$@")")"
    digest_homes="${digest_homes%,}"
    if [[ "$digest_homes" != "$pin_homes" ]]; then
      out="${out:+${out}
}${name} lives in [${digest_homes:-nowhere}] and ${pin_name} lives in [${pin_homes}]"
    fi
  done <<< "$(sort -u <<< "$names")"
  printf '%s' "$out"
}

# digests_without_a_version_pin <names> <home...> — every referenced digest
# whose tool carries no version-shaped pin in any home.
function digests_without_a_version_pin() {
  local names="$1"
  shift
  local name tool out=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    tool="$(tool_of "$name")"
    if [[ -z "$(version_pin_of "$tool" "$@")" ]]; then
      out="${out:+${out}
}${name} (no ${tool}_VERSION, ${tool}_REF or ${tool}_CHANNEL in any home)"
    fi
  done <<< "$(sort -u <<< "$names")"
  printf '%s' "$out"
}

# malformed_digest_values <home...> — every declared digest whose value is not
# 64 lowercase hex characters. A truncated digest reads as correct in a diff
# and dies at build time, after the merge.
function malformed_digest_values() {
  local home name line value out=""
  for home in "$@"; do
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      line="$(declaration_line "$REPO_ROOT/$home" "$name")"
      value="$(declaration_value "$line")"
      if [[ ! "$value" =~ ^[0-9a-f]{64}$ ]]; then
        out="${out:+${out}
}${home}: ${name} = '${value}' (${#value} characters)"
      fi
    done <<< "$(declared_digest_names "$REPO_ROOT/$home")"
  done
  printf '%s' "$out"
}

# digests_without_evidence <home...> — every declared digest whose declaring
# line carries neither evidence comment.
function digests_without_evidence() {
  local home name line out=""
  for home in "$@"; do
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      line="$(declaration_line "$REPO_ROOT/$home" "$name")"
      if [[ -z "$(evidence_of "$line")" ]]; then
        out="${out:+${out}
}${home}: ${name}"
      fi
    done <<< "$(declared_digest_names "$REPO_ROOT/$home")"
  done
  printf '%s' "$out"
}

# dual_home_disagreements <home a> <home b> — every digest that both homes
# declare, whose tool carries the SAME version in both, and whose 2 digest
# values differ. Equal versions are the same release, so they are the same
# bytes; 2 answers means 1 image verifies what the other rejects.
function dual_home_disagreements() {
  local first="$1" second="$2"
  local name tool pin pin_name first_version second_version first_value second_value out=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    [[ -z "$(declaration_line "$REPO_ROOT/$second" "$name")" ]] && continue
    tool="$(tool_of "$name")"
    pin="$(version_pin_of "$tool" "$first" "$second")"
    [[ -z "$pin" ]] && continue
    pin_name="${pin%%|*}"
    first_version="$(declaration_value "$(declaration_line "$REPO_ROOT/$first" "$pin_name")")"
    second_version="$(declaration_value "$(declaration_line "$REPO_ROOT/$second" "$pin_name")")"
    [[ "$first_version" != "$second_version" ]] && continue
    first_value="$(declaration_value "$(declaration_line "$REPO_ROOT/$first" "$name")")"
    second_value="$(declaration_value "$(declaration_line "$REPO_ROOT/$second" "$name")")"
    if [[ "$first_value" != "$second_value" ]]; then
      out="${out:+${out}
}${name} at ${pin_name} ${first_version}: ${first} has ${first_value}, ${second} has ${second_value}"
    fi
  done <<< "$(declared_digest_names "$REPO_ROOT/$first")"
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# The readers and detectors of rule 3: the helper the fetches call is IN the
# image, and it is there before the first fetch. Each detector takes an
# explicit file list, so the fixture world and the real tree run through the
# SAME code.
# ---------------------------------------------------------------------------

# helper_copy_lines <file> — the number of every line that COPYs the _build/
# directory of the build context into the helper's directory in the image.
#
# A `COPY --from=` is not this copy: it takes bytes out of another stage rather
# than out of the build context, so the helper would not be there.
#
# There is no comment filter here, unlike the reader below, and the anchor is
# why: a Dockerfile comment begins with `#`, so `^[[:space:]]*COPY` can never
# match one. The filter was written first and then deleted — mutation-tested
# by removing it, and not 1 check went red. Dead code in a detector is a line
# a reader trusts and nothing holds.
function helper_copy_lines() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk -v source="$HELPER_BUILD_DIRECTORY" -v target="$HELPER_IMAGE_DIRECTORY" '
    { line = $0 }
    line ~ /^[[:space:]]*COPY[[:space:]]/ {
      if (index(line, "--from=") > 0) { next }
      if (index(line, source) > 0 && index(line, target) > 0) { print NR }
    }
  ' "$file"
}

# first_helper_call_line <file> — the number of the first line that calls the
# helper at its in-image path, or the empty string when the file never calls
# it.
#
# This reader HAS a comment filter, and it is load-bearing: the match is an
# unanchored `index`, and a Dockerfile that writes the helper's path in prose
# above its COPY — which is exactly what copy-above.Dockerfile does, and what
# the real files are 1 sentence away from doing — would otherwise report a
# first call above the COPY and fail a correctly wired image.
function first_helper_call_line() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk -v helper="$HELPER_IMAGE_PATH" '
    { line = $0 }
    line ~ /^[[:space:]]*#/ { next }
    index(line, helper) > 0 { print NR; exit }
  ' "$file"
}

# dockerfiles_missing_the_helper_copy <relative...> — every named Dockerfile
# that does not carry exactly 1 helper COPY, with what it carries instead.
function dockerfiles_missing_the_helper_copy() {
  local relative path lines total numbers out=""
  for relative in "$@"; do
    path="$REPO_ROOT/$relative"
    if [[ ! -f "$path" ]]; then
      out="${out:+${out}
}${relative}: the file is absent"
      continue
    fi
    lines="$(helper_copy_lines "$path")"
    total="$(count_lines "$lines")"
    if [[ "$total" -eq 1 ]]; then
      continue
    fi
    numbers="$(tr '\n' ' ' <<< "$lines")"
    out="${out:+${out}
}${relative}: ${total} lines carry '${HELPER_COPY_TEXT}' (want exactly 1) [${numbers% }]"
  done
  printf '%s' "$out"
}

# dockerfiles_that_copy_the_helper_too_late <relative...> — every named
# Dockerfile whose helper COPY sits below the first layer that calls the
# helper. A file carrying no COPY at all is left to the detector above, and a
# file that never calls the helper has no first call to sit above.
function dockerfiles_that_copy_the_helper_too_late() {
  local relative path lines copy_line call_line out=""
  for relative in "$@"; do
    path="$REPO_ROOT/$relative"
    [[ -f "$path" ]] || continue
    lines="$(helper_copy_lines "$path")"
    copy_line="${lines%%$'\n'*}"
    call_line="$(first_helper_call_line "$path")"
    [[ -z "$copy_line" || -z "$call_line" ]] && continue
    if [[ "$copy_line" -gt "$call_line" ]]; then
      out="${out:+${out}
}${relative}: the COPY is at line ${copy_line} and the first ${HELPER_IMAGE_PATH} call is at line ${call_line}"
    fi
  done
  printf '%s' "$out"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE COUNTER-STIMULUS. Every detector FIRES, and every detector stays quiet.
#
# This runs before the real files on purpose. A verdict on base/Dockerfile
# means nothing until the same functions have been watched to report a file
# that is broken AND to leave a correct one alone.
# ===========================================================================
missing_fixtures=""
for fixture in "$FIXTURE_DOCKERFILE" "$FIXTURE_COMPONENT" "$FIXTURE_EXEMPTIONS" \
               "$FIXTURE_HOME_GOOD" "$FIXTURE_HOME_BAD" "$FIXTURE_HOME_OTHER"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_fixtures_exist" \
    "the fixtures this test proves itself with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_fixtures_exist"

  fixture_sites="$(fetch_sites "download-coverage/Dockerfile" "$FIXTURE_DOCKERFILE")
$(fetch_sites "download-coverage/component.sh" "$FIXTURE_COMPONENT")"
  fixture_rows="$(exemption_rows "$FIXTURE_EXEMPTIONS")"
  fixture_row_keys="$(row_keys "$fixture_rows")"
  fixture_site_keys="$(site_keys "$fixture_sites")"

  # 7 fetches: 6 in the Dockerfile fixture, 1 in the component fixture. A
  # reader that finds 8 read the apt package list or the prose comment; a
  # reader that finds 6 stopped reading the .sh half.
  assert_equal "counter_stimulus_reads_7_fetches_and_skips_apt_and_prose" \
    "7" "$(count_lines "$fixture_sites")" \
    "the fixtures hold 7 URL fetches, an apt layer naming curl and wget as packages," \
    "and a URL written in a comment" \
    "sites read:" "$fixture_sites"

  assert_not_contains "counter_stimulus_does_not_read_the_url_in_the_comment" \
    "$fixture_sites" "prose-only.tar.gz" \
    "that URL appears only inside a comment, and base/Dockerfile writes URLs in prose too"

  # -----------------------------------------------------------------------
  # THE CASE-ARM LOCAL, watched in all 4 of its answers.
  #
  # This is the capability the widening cost, and no other fixture exercises
  # it: with 1 sanctioned platform every fetch spelled its own pin, so the
  # reader that shipped here reported all 39 verified downloads of the real
  # tree as helper calls that pass no digest. The rule did not change; the
  # SHAPE the rule reads did.
  # -----------------------------------------------------------------------
  if [[ ! -f "$FIXTURE_ARM_LOCAL" ]]; then
    fail_check "counter_stimulus_the_arm_local_fixture_exists" \
      "absent: ${FIXTURE_ARM_LOCAL}" \
      "without it the local-following reader is a capability nobody has watched work"
    fail_check "counter_stimulus_follows_a_case_arm_local_to_its_pin" "no fixture to read"
    fail_check "counter_stimulus_is_not_fooled_by_a_non_digest_assignment" "no fixture to read"
    fail_check "counter_stimulus_still_reads_a_fetch_that_names_its_pin_literally" "no fixture to read"
    fail_check "counter_stimulus_the_arm_scope_does_not_leak_into_the_next_RUN" "no fixture to read"
  else
    pass_check "counter_stimulus_the_arm_local_fixture_exists"

    arm_sites="$(fetch_sites "$FIXTURE_ARM_LOCAL_LABEL" "$FIXTURE_ARM_LOCAL")"

    # 1. The arm assigned SHA256 a ${<TOOL>_SHA256_<ARCH>} token, so the fetch
    #    that spells ${SHA256} is answered by ARMTOOL_SHA256_AMD64 — the pin
    #    whose home, evidence and 64 hex digits every rule below can then check.
    assert_contains "counter_stimulus_follows_a_case_arm_local_to_its_pin" \
      "$arm_sites" "armtool-v\${ARMTOOL_VERSION}-linux-\${ARCH}.tar.gz|verified|ARMTOOL_SHA256_AMD64" \
      "the pin name is nowhere in the fetch command; it is in the arm above it" \
      "sites read:" "$arm_sites"

    # 2. THE HALF THAT MAKES IT A READER AND NOT A GUESS. The arm assigns a bare
    #    hex string, no pin answers for that download, and a general
    #    assignment-follower would call it verified. `helper-without-digest` is
    #    the only honest answer.
    assert_contains "counter_stimulus_is_not_fooled_by_a_non_digest_assignment" \
      "$arm_sites" "fooltool-v\${FOOLTOOL_VERSION}-linux-\${ARCH}.tar.gz|helper-without-digest|" \
      "SHA256=<64 hex> in an arm is a value no home declares and no bump can move," \
      "so a reader that resolved it would report coverage of a pin that does not exist" \
      "sites read:" "$arm_sites"

    # 3. The old shape still reads. A _NOARCH asset has nothing to choose, so it
    #    keeps naming its pin in the fetch itself, and both shapes live in the
    #    real tree today.
    assert_contains "counter_stimulus_still_reads_a_fetch_that_names_its_pin_literally" \
      "$arm_sites" "literaltool-v\${LITERALTOOL_VERSION}.tar.gz|verified|LITERALTOOL_SHA256_NOARCH" \
      "sites read:" "$arm_sites"

    # 4. The scope resets at the RUN. A layer that spells ${SHA256} and sets it
    #    nowhere would compare against the empty string at build time; read as
    #    ARMTOOL's digest it would look answered by a pin that has nothing to do
    #    with it, which is worse than unanswered because nothing would report it.
    assert_contains "counter_stimulus_the_arm_scope_does_not_leak_into_the_next_RUN" \
      "$arm_sites" "orphantool-v\${ORPHANTOOL_VERSION}.tar.gz|helper-without-digest|" \
      "layer 1 of the fixture sets SHA256 from a real pin and no later arm reassigns that" \
      "name, so this record is what a leaking scope would turn into ARMTOOL_SHA256_AMD64" \
      "sites read:" "$arm_sites"

    # 5. ONE ARM, TWO TOOLS. _delta/components/protocols.sh is exactly this
    #    shape, and it is why the locals there carry the tool's name. Each fetch
    #    must be answered by ITS OWN pin: a reader that took "the digest of this
    #    arm" would hand the first tool's digest to the second and report full
    #    coverage while the build compared the wrong bytes.
    assert_contains "counter_stimulus_one_arm_two_tools_answers_the_first_with_its_own_pin" \
      "$arm_sites" "paira-v\${PAIRA_VERSION}.tar.gz|verified|PAIRA_SHA256_AMD64" \
      "sites read:" "$arm_sites"

    # 6. THE ARM THAT IS NOT THE FIRST ONE. A download that exists on arm64 and
    #    on no other platform is answered by the arm64 arm, because that is the
    #    only arm that assigns anything. A reader that collects locals from
    #    `linux/amd64)` alone reports `helper-without-digest` here — a red naming
    #    a defect nobody committed, against a download that IS verified on the
    #    platform that reaches it. The real tree holds the mirror of this shape:
    #    flutter's Android RUN opens `linux/amd64) : ;;`, a guard arm that
    #    assigns nothing at all.
    assert_contains "counter_stimulus_answers_a_fetch_whose_only_assigning_arm_is_arm64" \
      "$arm_sites" "onlyarm-v\${ONLYARM_VERSION}-linux-\${ARCH}.tar.gz|verified|ONLYARM_SHA256_ARM64" \
      "this reader is the twin of fetch_urls in _ctl/lib.sh, which reads EVERY arm; an" \
      "amd64-only twin makes this file report a false red on a correct download, and" \
      "makes the 2 readers disagree about what the same file says" \
      "sites read:" "$arm_sites"

    # 7. THE TWIN-NESS ITSELF, as a check rather than as a sentence. The header
    #    above promised that this reader and `fetch_urls` in _ctl/lib.sh are the
    #    same 3 functions, and that promise went FALSE and stayed in the file:
    #    fetch_urls learned every arm, this half did not, and the comment went on
    #    asserting they agreed. So the agreement is executed here — every URL
    #    fetch_urls answers with a digest row must be `verified` here, naming a
    #    row fetch_urls names for that same URL.
    #
    #    The 2 readers are not identical and must not be: fetch_urls emits 1
    #    record per ARM because the writer needs a digest per row, and this one
    #    emits 1 record per FETCH because the coverage rule keys on <file>|<url>.
    #    What they owe each other is the ANSWER, and this is that debt.
    twin_disagreements=""
    while IFS= read -r library_record; do
      [[ -z "$library_record" ]] && continue
      twin_url="$(awk -F'|' '{ print $3 }' <<< "$library_record")"
      twin_rows="$(awk -F'|' -v want="$twin_url" '$3 == want { print $2 }' <<< "$(fetch_urls "$FIXTURE_ARM_LOCAL")")"
      twin_site="$(awk -F'|' -v want="$twin_url" '$2 == want { print $3 "|" $4 }' <<< "$arm_sites")"
      twin_site_state="${twin_site%%|*}"
      twin_site_row="${twin_site#*|}"
      if [[ "$twin_site_state" != "verified" ]] || ! grep -qxF -- "$twin_site_row" <<< "$twin_rows"; then
        twin_disagreements="${twin_disagreements:+${twin_disagreements}
}${twin_url}
  _ctl/lib.sh fetch_urls says: ${twin_rows//$'\n'/, }
  this file's fetch_sites says: ${twin_site:-<no record at all>}"
      fi
    done <<< "$(fetch_urls "$FIXTURE_ARM_LOCAL")"
    if [[ -z "$twin_disagreements" ]]; then
      pass_check "the_two_readers_agree_on_every_verified_download_of_the_arm_local_fixture"
    else
      fail_check "the_two_readers_agree_on_every_verified_download_of_the_arm_local_fixture" \
        "$twin_disagreements" \
        "the header of fetch_sites claims both readers are the same 3 functions. A claim" \
        "that only a comment holds goes false the next time either half learns something," \
        "and it did: fetch_urls learned to read every arm and this one kept reading" \
        "linux/amd64) alone, so the same file meant 2 things and the comment said it could not"
    fi

    assert_contains "counter_stimulus_one_arm_two_tools_answers_the_second_with_its_own_pin" \
      "$arm_sites" "pairb-v\${PAIRB_VERSION}.tar.gz|verified|PAIRB_SHA256_AMD64" \
      "this is the half that fails when a reader keeps 1 digest per arm, and it fails" \
      "SILENTLY: the record still says verified, it just names the wrong pin" \
      "sites read:" "$arm_sites"
  fi

  # The unclassified direction — the defect this whole file exists for.
  fixture_unclassified="$(keys_absent_from "$(sites_in_state "$fixture_sites" "plain")" "$fixture_row_keys")"
  assert_contains "counter_stimulus_reports_the_download_that_nobody_answered" \
    "$fixture_unclassified" "unclassified-tool.tar.gz" \
    "a fetch with no digest and no exemption row is the shape of the 51 downloads this change replaced"

  assert_contains "counter_stimulus_reports_the_unanswered_download_in_a_component_script" \
    "$fixture_unclassified" "component-tool.tar.gz" \
    "_delta/components/*.sh fetch 8 real downloads, and a reader that only met a Dockerfile covers none of them"

  # The quiet half of the same direction.
  assert_not_contains "counter_stimulus_does_not_report_the_verified_download" \
    "$fixture_unclassified" "verified-tool" \
    "that fetch passes \${TOOL_SHA256_AMD64} to the helper in its own command"

  assert_not_contains "counter_stimulus_does_not_report_the_exempt_download" \
    "$fixture_unclassified" "exempt-installer" \
    "that fetch carries exactly 1 exemption row"

  # The ghost direction — the #107 shape.
  fixture_ghosts="$(keys_absent_from "$fixture_row_keys" "$fixture_site_keys")"
  assert_contains "counter_stimulus_reports_the_row_whose_download_is_gone" \
    "$fixture_ghosts" "removed-tool.tar.gz" \
    "a row naming a URL no governed file fetches reports coverage of nothing"

  assert_not_contains "counter_stimulus_does_not_report_the_row_that_answers_a_real_download" \
    "$fixture_ghosts" "exempt-installer" \
    "a detector that reports every row is as useless as one that reports none"

  # 2 answers for 1 download.
  fixture_double="$(keys_present_in "$(sites_in_state "$fixture_sites" "verified")" "$fixture_row_keys")"
  assert_contains "counter_stimulus_reports_the_download_that_carries_2_answers" \
    "$fixture_double" "double-classified.tar.gz" \
    "a digest AND an exemption row means the reader cannot tell which one holds"

  assert_not_contains "counter_stimulus_does_not_report_the_singly_answered_download" \
    "$fixture_double" "verified-tool" \
    "that fetch carries a digest and no row, which is 1 answer"

  # The class taxonomy and the row grammar.
  assert_contains "counter_stimulus_reports_the_row_with_a_class_outside_the_taxonomy" \
    "$(rows_with_an_unknown_class "$fixture_rows")" "bad-class.tar.gz" \
    "the 2 classes are: ${EXEMPTION_CLASSES_TEXT}"

  assert_contains "counter_stimulus_reports_the_row_that_is_missing_its_reason" \
    "$(malformed_rows "$fixture_rows")" "malformed-row.tar.gz" \
    "the reason is what a human reads in review, so a row without one is an exemption nobody agreed to"

  assert_not_contains "counter_stimulus_does_not_report_the_well_formed_row" \
    "$(malformed_rows "$fixture_rows")" "exempt-installer" \
    "that row carries all 4 fields"

  # 5 rows, not 8. The fixture holds 5 rows, 6 comment blocks and 6 blank lines.
  assert_equal "counter_stimulus_reads_5_rows_and_skips_the_comments" \
    "5" "$(count_lines "$fixture_rows")" \
    "a reader that counts a comment as a row reports defects that are not there" \
    "rows read:" "$fixture_rows"
fi

# ===========================================================================
# 1b. THE COUNTER-STIMULUS for rule 2 — the same-home and evidence detectors.
# ===========================================================================
if [[ ! -f "$FIXTURE_HOME_GOOD" || ! -f "$FIXTURE_HOME_BAD" || ! -f "$FIXTURE_HOME_OTHER" ]]; then
  fail_check "counter_stimulus_home_fixtures_exist" \
    "the fixtures the same-home rule proves itself with are absent:" \
    "$FIXTURE_HOME_GOOD" "$FIXTURE_HOME_BAD" "$FIXTURE_HOME_OTHER"
else
  pass_check "counter_stimulus_home_fixtures_exist"

  good_home="_ctl/tests/fixtures/download-coverage/home-good.Dockerfile"
  bad_home="_ctl/tests/fixtures/download-coverage/home-bad.Dockerfile"
  other_home="_ctl/tests/fixtures/download-coverage/home-other.env"

  good_references="$(digest_references "$FIXTURE_HOME_GOOD")"
  bad_references="$(digest_references "$FIXTURE_HOME_BAD")"

  assert_contains "counter_stimulus_reports_the_legacy_arch_vocabulary" \
    "$(bad_vocabulary "$bad_references")" "LEGACY_SHA256_X86_64" \
    "the 1 vocabulary is: ${DIGEST_SUFFIXES_TEXT}"

  assert_equal "counter_stimulus_leaves_the_sanctioned_vocabulary_alone" \
    "" "$(bad_vocabulary "$good_references")" \
    "${DIGEST_SUFFIXES_TEXT} are the vocabulary, so none of them may be reported"

  assert_contains "counter_stimulus_reports_the_digest_that_lives_in_no_home" \
    "$(home_mismatches "$bad_references" "$bad_home")" "HOMELESS_SHA256_AMD64" \
    "its version is declared and its digest is declared nowhere, so the helper compares against the empty string"

  assert_equal "counter_stimulus_leaves_the_correctly_homed_digests_alone" \
    "" "$(home_mismatches "$good_references" "$good_home")" \
    "every digest of home-good.Dockerfile sits beside its version in that same file"

  assert_contains "counter_stimulus_reports_the_digest_with_no_version_pin" \
    "$(digests_without_a_version_pin "$bad_references" "$bad_home")" "ORPHANDIGEST_SHA256_AMD64" \
    "a digest whose tool carries no version pins the bytes of a release nothing names"

  assert_equal "counter_stimulus_leaves_the_digests_that_have_a_version_alone" \
    "" "$(digests_without_a_version_pin "$good_references" "$good_home")" \
    "all 3 digests of home-good.Dockerfile sit beside a *_VERSION"

  assert_contains "counter_stimulus_reports_the_digest_that_is_not_64_hex" \
    "$(malformed_digest_values "$bad_home")" "SHORTHEX_SHA256_AMD64" \
    "63 characters reads as correct in a diff and dies at build time, after the merge"

  assert_equal "counter_stimulus_leaves_the_64_hex_digests_alone" \
    "" "$(malformed_digest_values "$good_home")" \
    "every value in home-good.Dockerfile is 64 lowercase hex"

  assert_contains "counter_stimulus_reports_the_digest_with_no_evidence_comment" \
    "$(digests_without_evidence "$bad_home")" "NOEVIDENCE_SHA256_AMD64" \
    "a digest with no provenance is a number a reviewer has to take on faith"

  assert_equal "counter_stimulus_leaves_both_evidence_spellings_alone" \
    "" "$(digests_without_evidence "$good_home")" \
    "home-good.Dockerfile carries 1 upstream-published row and 2 computed-at-pin rows"

  assert_contains "counter_stimulus_reports_the_dual_home_digests_that_disagree" \
    "$(dual_home_disagreements "$good_home" "$other_home")" "GOODTOOL_SHA256_AMD64" \
    "the same version in 2 homes is the same release, so 1 image verifies what the other rejects"

  assert_not_contains "counter_stimulus_leaves_the_agreeing_dual_home_pair_alone" \
    "$(dual_home_disagreements "$good_home" "$other_home")" "PAIRTOOL_SHA256_AMD64" \
    "PAIRTOOL carries the same version AND the same digest in both fixture homes"
fi

# ===========================================================================
# 1c. THE COUNTER-STIMULUS for rule 3 — the helper-wiring detectors.
#
# Both real Dockerfiles are correctly wired today, so on the real tree these
# 2 detectors report nothing and would report nothing if they read no file at
# all. The fixtures are the only place they are ever watched to fire.
# ===========================================================================
if [[ ! -f "$FIXTURE_COPY_ABOVE" || ! -f "$FIXTURE_COPY_BELOW" || ! -f "$FIXTURE_COPY_ABSENT" ]]; then
  fail_check "counter_stimulus_copy_fixtures_exist" \
    "the fixtures the helper-wiring rule proves itself with are absent:" \
    "$FIXTURE_COPY_ABOVE" "$FIXTURE_COPY_BELOW" "$FIXTURE_COPY_ABSENT"
else
  pass_check "counter_stimulus_copy_fixtures_exist"

  copy_above="_ctl/tests/fixtures/download-coverage/copy-above.Dockerfile"
  copy_below="_ctl/tests/fixtures/download-coverage/copy-below.Dockerfile"
  copy_absent="_ctl/tests/fixtures/download-coverage/copy-absent.Dockerfile"

  assert_contains "counter_stimulus_reports_the_dockerfile_that_never_copies_the_helper" \
    "$(dockerfiles_missing_the_helper_copy "$copy_absent")" "copy-absent.Dockerfile" \
    "it calls ${HELPER_IMAGE_PATH} and nothing puts that file in the image," \
    "which is what deleting 1 line from cloud/Dockerfile leaves behind"

  assert_equal "counter_stimulus_leaves_the_dockerfile_that_copies_the_helper_alone" \
    "" "$(dockerfiles_missing_the_helper_copy "$copy_above")" \
    "copy-above.Dockerfile carries exactly 1 '${HELPER_COPY_TEXT}'," \
    "and a detector that reports it reports base/Dockerfile and cloud/Dockerfile too"

  assert_contains "counter_stimulus_reports_the_copy_that_sits_below_the_first_fetch" \
    "$(dockerfiles_that_copy_the_helper_too_late "$copy_below")" "copy-below.Dockerfile" \
    "the COPY is PRESENT in that file, so a presence-only rule passes it" \
    "a layer runs against the filesystem the layers above it left, and the helper is not there yet"

  assert_equal "counter_stimulus_leaves_the_copy_above_the_first_fetch_alone" \
    "" "$(dockerfiles_that_copy_the_helper_too_late "$copy_above")" \
    "its COPY sits above its only fetch layer, which is the shape the rule requires" \
    "it also writes the helper's path in PROSE above that COPY, so a reader that counted" \
    "comment lines would report this correctly wired file — the real Dockerfiles write prose there too"
fi

# ===========================================================================
# 2. THE GOVERNED SET IS THE WHOLE SET.
# ===========================================================================
missing_governed=""
for relative in "${GOVERNED_DOCKERFILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || missing_governed="${missing_governed:+${missing_governed}
}${relative}"
done
for relative in "${GOVERNED_COMPONENTS[@]}"; do
  [[ -f "$REPO_ROOT/$COMPONENT_DIRECTORY/$relative" ]] \
    || missing_governed="${missing_governed:+${missing_governed}
}${COMPONENT_DIRECTORY}/${relative}"
done
# The exempt list is held to the same question, and for a sharper reason: every
# rule about an exempt file asks it to hold NOTHING, and a path that does not
# exist holds nothing too. An exemption naming a deleted file would pass forever
# while covering a file that is not there.
for relative in "${UNGOVERNED_DOCKERFILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || missing_governed="${missing_governed:+${missing_governed}
}${relative}"
done
if [[ -n "$missing_governed" ]]; then
  fail_check "every_governed_file_exists" \
    "the file list in this test is stale; these are named but absent:" \
    "$missing_governed"
else
  pass_check "every_governed_file_exists"
fi

# The mirror the Dockerfile half never had. The component list has one — a
# literal against the directory glob — and the Dockerfiles had a literal alone,
# so an image added tomorrow could sit in NEITHER list and every rule in this
# file would narrow silently. That is the failure this file's own header names
# one layer up, and the failure `VALUE_HOMES` above already shipped once.
#
# Governed + exempt = every `<image>/Dockerfile` of the repository. A new image
# forces its author to choose which one it is, and neither answer can be
# silence.
all_dockerfiles=""
for path in "$REPO_ROOT"/*/Dockerfile; do
  [[ -f "$path" ]] || continue
  all_dockerfiles="${all_dockerfiles:+${all_dockerfiles}
}$(basename "$(dirname "$path")")/Dockerfile"
done
assert_equal "every_dockerfile_is_governed_or_exempt" \
  "$(joined "${GOVERNED_DOCKERFILES[@]}" "${UNGOVERNED_DOCKERFILES[@]}")" \
  "$(printf '%s\n' "$all_dockerfiles" | sort)" \
  "either an image was added, renamed or deleted — GOVERNED_DOCKERFILES is the list you edit," \
  "and UNGOVERNED_DOCKERFILES is where a Dockerfile that fetches nothing goes, with its reason —" \
  "or the glob in this test stopped matching, which would leave a downloading file unread"

# The same 2 questions asked of VALUE_HOMES, and they are 2 and not 1. Every
# rule below that takes VALUE_HOMES reads it through `declared_digest_names`,
# which returns nothing for a file it cannot open AND nothing for a file that
# declares no value. So a home can leave this list's subject in 2 ways, and
# both of them are silent: the file is DELETED, or the file stops declaring.
# `runner/Dockerfile` left the first way and `base/Dockerfile` left the second,
# and 61 checks stayed green through both.
missing_homes=""
for relative in "${VALUE_HOMES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || missing_homes="${missing_homes:+${missing_homes}
}${relative}"
done
if [[ -n "$missing_homes" ]]; then
  fail_check "every_named_value_home_exists" \
    "the VALUE_HOMES list in this test is stale; these are named but absent:" \
    "$missing_homes" \
    "every digest rule below reads nothing out of a file it cannot open, and reports clean"
else
  pass_check "every_named_value_home_exists"
fi

silent_homes=""
for relative in "${VALUE_HOMES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  if [[ -z "$(declared_digest_names "$REPO_ROOT/$relative")" ]]; then
    silent_homes="${silent_homes:+${silent_homes}
}${relative}"
  fi
done
if [[ -n "$silent_homes" ]]; then
  fail_check "every_named_value_home_declares_a_digest" \
    "these homes are named in VALUE_HOMES and declare no <TOOL>_SHA256_<ARCH> with a value:" \
    "$silent_homes" \
    "a home that declares nothing is not a value home — drop it from the list, or find out" \
    "why the declarations left, because every digest rule below just narrowed and stayed green"
else
  pass_check "every_named_value_home_declares_a_digest"
fi

# The mirror. A literal list catches a glob that stopped matching; a glob
# catches a component added without an edit here. Neither alone is enough.
component_files=""
for path in "$REPO_ROOT/$COMPONENT_DIRECTORY"/*.sh; do
  [[ -f "$path" ]] || continue
  component_files="${component_files:+${component_files}
}$(basename "$path")"
done
assert_equal "the_component_list_in_this_test_is_the_component_directory" \
  "$(joined "${GOVERNED_COMPONENTS[@]}")" \
  "$(printf '%s\n' "$component_files" | sort)" \
  "either a component was added, renamed or deleted — and GOVERNED_COMPONENTS is what you edit —" \
  "or the glob in this test stopped matching, which would leave a governed file unread"

# ===========================================================================
# 3. THE READERS ARE ALIVE ON THE REAL TREE.
#
# A rule over 0 fetch sites reports a clean repository it never read. Every one
# of the 5 Dockerfiles fetches at least 1 URL today — 53 fetch sites across the
# governed set, 45 of them verified, measured by this file's own reader on
# 2026-08-17 after runner/ was deleted — so a Dockerfile with none
# is a reader that stopped matching, not a Dockerfile that stopped downloading.
# ===========================================================================
ALL_SITES=""
for relative in "${GOVERNED_DOCKERFILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  file_sites="$(fetch_sites "$relative" "$REPO_ROOT/$relative")"
  if [[ -z "$file_sites" ]]; then
    fail_check "${relative}_fetches_at_least_one_url" \
      "no curl, wget or ${FETCH_HELPER} command was read out of ${relative}" \
      "either the file stopped downloading, or the reader in this test stopped matching"
  else
    pass_check "${relative}_fetches_at_least_one_url"
  fi
  ALL_SITES="${ALL_SITES:+${ALL_SITES}
}${file_sites}"
done

for relative in "${GOVERNED_COMPONENTS[@]}"; do
  path="$REPO_ROOT/$COMPONENT_DIRECTORY/$relative"
  [[ -f "$path" ]] || continue
  file_sites="$(fetch_sites "${COMPONENT_DIRECTORY}/${relative}" "$path")"
  [[ -z "$file_sites" ]] && continue
  ALL_SITES="${ALL_SITES:+${ALL_SITES}
}${file_sites}"
done

# The exemption, CHECKED. The mirror image of the rule above it: a governed file
# that fetches nothing is a reader that stopped matching, and an EXEMPT file that
# fetches anything is a download in the 1 Dockerfile no coverage rule opens.
#
# The same reader answers both, so the exemption cannot outlive its reason. It is
# stated as "this file performs no URL fetch", which is a property of the file
# and not of anybody's memory of it — and the day somebody adds a curl here it
# stops being true, loudly, at pull request time.
for relative in "${UNGOVERNED_DOCKERFILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  file_sites="$(fetch_sites "$relative" "$REPO_ROOT/$relative")"
  if [[ -z "$file_sites" ]]; then
    pass_check "${relative}_fetches_no_url_and_is_exempt"
  else
    fail_check "${relative}_fetches_no_url_and_is_exempt" \
      "${relative} is in UNGOVERNED_DOCKERFILES because ${UNGOVERNED_REASON}," \
      "and it now performs these fetches, which no digest and no exemption row answers:" \
      "$file_sites" \
      "move it to GOVERNED_DOCKERFILES and answer every fetch there, or take the download out"
  fi
done

ALL_SITE_KEYS="$(site_keys "$ALL_SITES")"

# The key of a fetch is (file, url). 2 fetches of 1 URL in 1 file would make
# the exemption file unable to answer them separately, so the model is held.
repeated_sites="$(repeated_keys "$ALL_SITE_KEYS")"
if [[ -z "$repeated_sites" ]]; then
  pass_check "no_governed_file_fetches_the_same_url_twice"
else
  fail_check "no_governed_file_fetches_the_same_url_twice" \
    "these (file, url) pairs appear more than once, so 1 exemption row cannot answer them separately:" \
    "$repeated_sites" \
    "give the 2 fetches distinct URLs, or fold them into 1 command"
fi

unkeyed_sites="$(sites_in_state "$ALL_SITES" "plain" | grep -F '|<no-url>' || true)"
if [[ -z "$unkeyed_sites" ]]; then
  pass_check "every_fetch_the_reader_finds_carries_a_url"
else
  fail_check "every_fetch_the_reader_finds_carries_a_url" \
    "these fetch commands hold no URL the reader can key on:" \
    "$unkeyed_sites" \
    "the exemption file keys on the URL, so a fetch with none cannot be answered"
fi

# ===========================================================================
# 4. THE HELPER AND THE EXEMPTION FILE EXIST.
# ===========================================================================
if [[ -f "$REPO_ROOT/$FETCH_HELPER" ]]; then
  pass_check "the_verified_fetch_helper_exists"
else
  fail_check "the_verified_fetch_helper_exists" \
    "absent: ${FETCH_HELPER}" \
    "every verified download goes through it, so the rule below can be satisfied by nothing until it lands"
fi

REAL_ROWS=""
if [[ -f "$REPO_ROOT/$EXEMPTIONS_FILE" ]]; then
  pass_check "the_download_exemptions_file_exists"
  REAL_ROWS="$(exemption_rows "$REPO_ROOT/$EXEMPTIONS_FILE")"
else
  fail_check "the_download_exemptions_file_exists" \
    "absent: ${EXEMPTIONS_FILE}" \
    "a download that takes a stated class instead of a digest is answered THERE," \
    "so with no file every unversioned URL below reads as unanswered — which it is"
fi
REAL_ROW_KEYS="$(row_keys "$REAL_ROWS")"

# ===========================================================================
# 4b. THE HELPER REACHES THE IMAGE, ABOVE THE FIRST FETCH THAT CALLS IT.
#
# Everything above this point reads a COMMAND. This reads the 1 line that
# makes those commands able to run at all. Measured by the verifier on
# 2026-08-17: delete the COPY from cloud/Dockerfile and all 378 checks the
# suite held that day stayed green, while every routed download 404s at build
# time.
# ===========================================================================
copy_report="$(dockerfiles_missing_the_helper_copy "${HELPER_COPY_DOCKERFILES[@]}")"
if [[ -z "$copy_report" ]]; then
  pass_check "base_and_cloud_copy_the_verified_fetch_helper_into_the_image"
else
  fail_check "base_and_cloud_copy_the_verified_fetch_helper_into_the_image" \
    "these Dockerfiles do not carry exactly 1 '${HELPER_COPY_TEXT}':" \
    "$copy_report" \
    "every verified download calls ${HELPER_IMAGE_PATH}, and without that COPY the file" \
    "is not in the image: the build dies at its first fetch layer, after the merge" \
    "the build context of these 2 is the repository root, which is what IMAGE_BUILD_CONTEXT" \
    "in base/ctl.sh and cloud/ctl.sh, and 'context: .' in both copies of build-and-push.yml, are for"
fi

order_report="$(dockerfiles_that_copy_the_helper_too_late "${HELPER_COPY_DOCKERFILES[@]}")"
if [[ -z "$order_report" ]]; then
  pass_check "the_helper_copy_sits_above_the_first_fetch_that_calls_it"
else
  fail_check "the_helper_copy_sits_above_the_first_fetch_that_calls_it" \
    "these Dockerfiles carry the COPY below a layer that already calls the helper:" \
    "$order_report" \
    "a layer runs against the filesystem the layers ABOVE it left, so a present COPY" \
    "that arrives late is not a wired COPY — move it above the first fetch"
fi

# ===========================================================================
# 5. THE RULE, ON THE REAL TREE. Both directions.
# ===========================================================================
unclassified="$(keys_absent_from "$(sites_in_state "$ALL_SITES" "plain")" "$REAL_ROW_KEYS")"
if [[ -z "$unclassified" ]]; then
  pass_check "every_download_passes_a_digest_or_carries_an_exemption_row"
else
  fail_check "every_download_passes_a_digest_or_carries_an_exemption_row" \
    "these downloads verify nothing and no exemption row answers for them:" \
    "$unclassified" \
    "route each one through ${FETCH_HELPER} with its \${<TOOL>_SHA256_<ARCH>}," \
    "or add exactly 1 row to ${EXEMPTIONS_FILE} naming its class and reason" \
    "the 2 classes are: ${EXEMPTION_CLASSES_TEXT}"
fi

helper_without_digest="$(sites_in_state "$ALL_SITES" "helper-without-digest")"
if [[ -z "$helper_without_digest" ]]; then
  pass_check "every_helper_call_names_its_digest_pin"
else
  fail_check "every_helper_call_names_its_digest_pin" \
    "these calls go through the helper and pass it no \${*_SHA256_*}:" \
    "$helper_without_digest" \
    "the helper with an empty digest argument is a download with no verification and an extra hop"
fi

ghost_rows="$(keys_absent_from "$REAL_ROW_KEYS" "$ALL_SITE_KEYS")"
if [[ -z "$ghost_rows" ]]; then
  pass_check "every_exemption_row_answers_a_download_that_exists"
else
  fail_check "every_exemption_row_answers_a_download_that_exists" \
    "these rows name a (file, url) that no governed file fetches:" \
    "$ghost_rows" \
    "delete the stale row, or restore the download it names" \
    "a row for a download that is gone reports coverage of nothing — the #107 shape"
fi

double_answered="$(keys_present_in "$(sites_in_state "$ALL_SITES" "verified")" "$REAL_ROW_KEYS")"
if [[ -z "$double_answered" ]]; then
  pass_check "no_download_carries_both_a_digest_and_an_exemption_row"
else
  fail_check "no_download_carries_both_a_digest_and_an_exemption_row" \
    "these downloads verify a digest AND claim an exemption:" \
    "$double_answered" \
    "2 answers for 1 download means the reader of the exemption file cannot tell which one holds"
fi

repeated_rows="$(repeated_keys "$REAL_ROW_KEYS")"
if [[ -z "$repeated_rows" ]]; then
  pass_check "every_exempt_download_carries_exactly_one_row"
else
  fail_check "every_exempt_download_carries_exactly_one_row" \
    "these (file, url) pairs carry more than 1 exemption row:" \
    "$repeated_rows" \
    "2 rows for 1 download means 2 stated reasons, and only 1 of them was reviewed"
fi

bad_rows="$(malformed_rows "$REAL_ROWS")"
if [[ -z "$bad_rows" ]]; then
  pass_check "every_exemption_row_carries_all_4_fields"
else
  fail_check "every_exemption_row_carries_all_4_fields" \
    "these rows are not <file>|<url>|<class>|<reason> with every field non-empty:" \
    "$bad_rows"
fi

bad_class_rows="$(rows_with_an_unknown_class "$REAL_ROWS")"
if [[ -z "$bad_class_rows" ]]; then
  pass_check "every_exemption_row_names_a_class_in_the_taxonomy"
else
  fail_check "every_exemption_row_names_a_class_in_the_taxonomy" \
    "these rows carry a class outside the taxonomy:" \
    "$bad_class_rows" \
    "the 2 classes are: ${EXEMPTION_CLASSES_TEXT}"
fi

# ===========================================================================
# 6. pins_live_in_the_same_home_and_carry_their_evidence
#
# The coverage rule above says a download names a digest. This one says the
# digest it names is real, is reachable, and can be bumped: it sits beside its
# version in the SAME home, cloud refuses to build without it, it is 64 hex,
# it records where its value came from, and the ~17 tools that live in 2 homes
# carry 1 digest between them.
# ===========================================================================
REAL_REFERENCES=""
for relative in "${GOVERNED_DOCKERFILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  REAL_REFERENCES="${REAL_REFERENCES:+${REAL_REFERENCES}
}$(digest_references "$REPO_ROOT/$relative")"
done
for relative in "${GOVERNED_COMPONENTS[@]}"; do
  path="$REPO_ROOT/$COMPONENT_DIRECTORY/$relative"
  [[ -f "$path" ]] || continue
  file_references="$(digest_references "$path")"
  [[ -z "$file_references" ]] && continue
  REAL_REFERENCES="${REAL_REFERENCES:+${REAL_REFERENCES}
}${file_references}"
done
REAL_REFERENCES="$(printf '%s\n' "$REAL_REFERENCES" | awk 'NF' | sort -u)"

if [[ -n "$REAL_REFERENCES" ]]; then
  pass_check "the_tree_references_at_least_one_digest_pin"
else
  fail_check "the_tree_references_at_least_one_digest_pin" \
    "no \${*_SHA256_*} reference was read out of any governed file" \
    "either no download verifies anything, or the reader in this test stopped matching"
fi

vocabulary_violations="$(bad_vocabulary "$REAL_REFERENCES")"
if [[ -z "$vocabulary_violations" ]]; then
  pass_check "every_referenced_digest_uses_the_one_arch_vocabulary"
else
  fail_check "every_referenced_digest_uses_the_one_arch_vocabulary" \
    "these digest names sit outside the 1 vocabulary:" \
    "$vocabulary_violations" \
    "the vocabulary is: ${DIGEST_SUFFIXES_TEXT}" \
    "it names the PLATFORM and never the upstream asset spelling — a row spelled" \
    "_X86_64 or _AARCH64 is a second vocabulary for a platform that already has one," \
    "and the second is where a pin hides from every reader that knows the first"
fi

home_report="$(home_mismatches "$REAL_REFERENCES" "${VALUE_HOMES[@]}")"
if [[ -z "$home_report" ]]; then
  pass_check "every_referenced_digest_lives_in_the_same_home_as_its_version"
else
  fail_check "every_referenced_digest_lives_in_the_same_home_as_its_version" \
    "these digests and their versions live in different homes:" \
    "$home_report" \
    "a bump edits 1 line and its digest line; 2 homes apart means the bump misses one"
fi

no_version_report="$(digests_without_a_version_pin "$REAL_REFERENCES" "${VALUE_HOMES[@]}")"
if [[ -z "$no_version_report" ]]; then
  pass_check "every_referenced_digest_belongs_to_a_version_pin"
else
  fail_check "every_referenced_digest_belongs_to_a_version_pin" \
    "these digests name a tool that carries no version-shaped pin in any home:" \
    "$no_version_report" \
    "check the spelling of the digest name, or add the version pin it belongs beside"
fi

hex_report="$(malformed_digest_values "${VALUE_HOMES[@]}")"
if [[ -z "$hex_report" ]]; then
  pass_check "every_declared_digest_is_64_lowercase_hex"
else
  fail_check "every_declared_digest_is_64_lowercase_hex" \
    "these declared digests are not 64 lowercase hex characters:" \
    "$hex_report" \
    "a truncated digest reads as correct in a diff and dies at build time, after the merge"
fi

evidence_report="$(digests_without_evidence "${VALUE_HOMES[@]}")"
if [[ -z "$evidence_report" ]]; then
  pass_check "every_declared_digest_carries_its_evidence_comment"
else
  fail_check "every_declared_digest_carries_its_evidence_comment" \
    "these declared digests say nothing about where their value came from:" \
    "$evidence_report" \
    "append '# upstream-published: <checksum file url>' when the release ships one and the 2 agreed," \
    "otherwise '# computed-at-pin: <yyyy-mm-dd>' — TLS plus an immutable release URL is then the whole evidence"
fi

# cloud takes its values from versions.env through generated --build-arg, so
# every digest there needs its value-less ARG and its place in the pin gate.
# Without the gate an absent pin expands to the empty string and surfaces much
# later as a digest comparison against nothing.
cloud_args="$(valueless_args "$REPO_ROOT/$CLOUD_DOCKERFILE")"
cloud_gate="$(pin_gate_names "$REPO_ROOT/$CLOUD_DOCKERFILE")"
gate_report=""
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  if ! grep -qx -- "$name" <<< "$cloud_args"; then
    gate_report="${gate_report:+${gate_report}
}${name}: no 'ARG ${name}' in ${CLOUD_DOCKERFILE}"
  fi
  if ! grep -qx -- "$name" <<< "$cloud_gate"; then
    gate_report="${gate_report:+${gate_report}
}${name}: not named in the ${CLOUD_DOCKERFILE} pin gate"
  fi
done <<< "$(declared_digest_names "$REPO_ROOT/$CLOUD_HOME")"

if [[ -z "$gate_report" ]]; then
  pass_check "every_versions_env_digest_is_declared_and_gated_by_cloud"
else
  fail_check "every_versions_env_digest_is_declared_and_gated_by_cloud" \
    "these ${CLOUD_HOME} digests do not reach the cloud build, or reach it ungated:" \
    "$gate_report" \
    "add 'ARG <NAME>' at the top and ': \"\${<NAME>:?not in versions.env}\"' to the pin gate"
fi

dual_report=""
for home in "${VALUE_HOMES[@]}"; do
  [[ "$home" == "$CLOUD_HOME" ]] && continue
  home_disagreements="$(dual_home_disagreements "$CLOUD_HOME" "$home")"
  [[ -z "$home_disagreements" ]] && continue
  dual_report="${dual_report:+${dual_report}
}${home_disagreements}"
done
if [[ -z "$dual_report" ]]; then
  pass_check "a_tool_in_2_homes_at_1_version_carries_1_digest"
else
  fail_check "a_tool_in_2_homes_at_1_version_carries_1_digest" \
    "these tools carry the same version in 2 homes and 2 different digests:" \
    "$dual_report" \
    "the same version is the same release, so 1 image verifies bytes the other rejects"
fi

test_summary "$TEST_NAME"
