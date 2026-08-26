#!/usr/bin/env bash
#
# .ci/ghcr-retention.sh — what this repository is allowed to delete from ghcr.io,
# and what it may never delete.
#
#   bash .ci/ghcr-retention.sh            every image of images.yaml
#   bash .ci/ghcr-retention.sh <image>... the named images
#
# It DRY RUNS by default. Nothing is deleted until RETENTION_MODE=enforce.
#
# ============================================================================
# THE DEFECT THIS FILE EXISTS FOR
# ============================================================================
#
# GitHub Actions and GitHub Packages share ONE storage quota, and it is
# exhausted. Every `review` job across gophersys fails with
# `Failed to CreateArtifact: Artifact storage quota has been hit` AFTER posting
# its verdict, so the check goes red on a review that succeeded. The Actions
# artifacts are ~5 MB across the organization; the containers are the consumer.
#
# The cause is in build-and-push.yml and it is not a leak: every publish pushes
# `<image>:latest` and `<image>:<short sha>`, and nothing has ever pruned. A
# permanent tag per merge, forever — 753 versions across the 6 images and 242 of
# them created in the 7 days to 2026-08-26, which is ~34 a day.
#
# READ THE PER-IMAGE COUNTS OUT OF A RUN, never out of this comment. An earlier
# version of this paragraph listed all 6, and 2 of them were 45% high within the
# hour: the estate moved WHILE it was being measured — an unrelated cleanup was
# deleting versions between one read and the next — so `embedded 115, ui 99`
# and `embedded 79, ui 69` were both true on 2026-08-26 and the pair read as a
# contradiction. Every run prints the live number for every package it touches.
#
# ============================================================================
# THE FOOTGUN: AN UNTAGGED VERSION IS USUALLY A LIVE CHILD
# ============================================================================
#
# A gophersys tagged image is an OCI image INDEX
# (application/vnd.oci.image.index.v1+json). Its children — the per-platform
# manifests, and the attestation manifest buildx attaches to each — appear in
# the packages API as separate UNTAGGED versions. So "untagged" does not mean
# "orphan", and the prune that every retention example performs — delete all
# untagged versions — destroys the live content of the tags it is keeping.
#
# Measured on `base`, 2026-08-26, by resolving all 91 tagged versions:
#
#   tagged versions ............................. 91
#   untagged versions ........................... 225
#   untagged that ARE children of a live tag .... 225
#   true orphans ................................ 0
#
# Every untagged version of `base` is load-bearing today.
#
# THE SECOND HALF OF THE FOOTGUN: A CHILD HAS MORE THAN ONE PARENT. Those 91
# indexes make 300 child references that resolve to 225 distinct digests, so 75
# references are shared. A prune that computed "the children of the indexes I am
# deleting" would remove content a SURVIVING index still points at. That is why
# the delete set below is `all versions - protected closure`, and never a walk
# down from the doomed.
#
# 32 of the 91 indexes carry 2 children and 59 carry 4 — the single-arch era and
# the dual-arch era — so "4 children each" is not an invariant either. The
# closure walks what each manifest says.
#
# ============================================================================
# WHAT IS PROTECTED, AND WHY NO CLASS IS OPTIONAL
# ============================================================================
#
#   1. `latest`. Every devcontainer.json here, and every consumer, opens
#      `ghcr.io/gophersys/<image>:latest`.
#
#   2. Any `v<semver>` tag. build-and-push.yml pushes one on a tag ref.
#      MEASURED 2026-08-26: there are ZERO such tags in the estate. The class is
#      here because the publish path can create one, and a rule written after
#      the first release is a rule written after the first loss. Nothing below
#      asserts this class is non-empty: a liveness guard over a set that is
#      legitimately empty is a check somebody has to disable to pass.
#
#   3. Any short-SHA tag a LIVE SUBMODULE POINTER names. gophersys/eden pins
#      this repository at a full git SHA and the published image carries the
#      SHORT sha of that same commit. eden main AND every open pull request
#      count. Measured 2026-08-26: eden main pins 685ac28 while its open pull
#      requests pin 69fc6a9 (#14) and e67d6cd (#7), so a sweep of the default
#      branch alone would delete the images 2 open pull requests build against.
#
#   4. Any TAG or DIGEST a consuming repository pins. ADR-0028 has eden releases
#      open promotion pull requests into gophersys/infrastructure pinning image
#      DIGESTS. Measured 2026-08-26 against the real trees:
#
#        ghcr.io/gophersys/cloud@sha256:ffdcf504…   the ARC image-warmer
#                                                   DaemonSet — cloud tag 440f6c8
#        ghcr.io/gophersys/cloud@sha256:9a150cbf…   cloud tag 997bb6b
#        ghcr.io/gophersys/base:e0c6bc5             pinned by tag
#
#      Their recency ranks inside their own package are 3, 35 and 56. A
#      keep-the-10-most-recent policy with no pin sweep deletes 997bb6b and
#      e0c6bc5 outright, and 440f6c8 eight publishes later. Every ARC pool in
#      the homelab runs the image that DaemonSet warms.
#
#      THE `:tag@sha256:` TRAP, and it is the sharpest lesson here. A pin can
#      name a tag AND a digest:
#
#        research-hardware  ghcr.io/gophersys/hardware:latest@sha256:ad5851…
#        research-ui        ghcr.io/gophersys/ui:latest@sha256:26547a…
#
#      Git says `latest` in both. THE REGISTRY DISAGREES: on 2026-08-26 each of
#      those digests carried only the tag `efe48e1`, while `:latest` had moved
#      on to `449d5f4`. A reader that believed the tag half would conclude both
#      pins were covered by protection class 1 and delete the digests anyway.
#
#      So the DIGEST is the pin and the tag beside it is decoration. The sweep
#      below takes every `sha256:<64 hex>` token of every swept tree, whatever
#      syntax surrounds it, which answers both forms and any third one.
#
#      This is measured and not argued: the first real dry run of this script
#      planned to delete `ad5851…` and `26547a…`, because the 2 research
#      repositories were not yet in RETENTION_PIN_REPOS. The mechanism was
#      right and its INPUT SET was short by 2 repositories, which is the failure
#      a maintained list of consumers will keep having — a new consumer is a new
#      row here, and nothing but review will catch a missing one.
#
#   5. Every child manifest of anything protected by 1-4, transitively.
#
#   6. A safety margin: the RETENTION_KEEP most recent tagged versions that
#      classes 1-5 did not already reach. It answers for the pins nobody wrote
#      down.
#
# ============================================================================
# FAIL-NOT-SKIP, AND WHAT "DELETES NOTHING" MEANS HERE
# ============================================================================
#
# Every protection above is a READ of something outside this repository, and a
# read that fails quietly does not weaken the policy — it EMPTIES the class, and
# the run then deletes exactly what that class existed to keep. So every read
# failure is fatal and names what it could not reach. No `|| true` over an
# error, no `2>/dev/null`, no skip on a missing credential. `grep_lines` below
# is where "no match" is separated from "grep failed", because those are the
# same exit status to a caller that only asks whether the command succeeded.
#
# The liveness guards assert that each MECHANISM RAN, never that it found
# something:
#
#   - the version list of a package is non-empty
#   - every tag matched a known shape, or the run ABORTS naming it before it
#     deletes anything
#   - the protected set of a package is non-empty
#   - the closure walk read at least 1 manifest
#   - the submodule sweep produced at least 1 pointer
#   - the pin sweep read every repository it was given
#
# DELETING NOTHING IS DELIBERATELY NOT ASSERTED AGAINST. Once the backlog is
# gone, a weekly run with an empty delete set is the policy WORKING, and failing
# on it would put a red on the board every week that nobody can act on — which
# is how a reader is taught to ignore red, the reason
# .claude/rules/00-identity.md gives for not gating HIGH CVEs. What the guards
# make impossible is deleting nothing SILENTLY: a run that read nothing fails at
# the stage that read nothing, and every stage prints its count.
#
# ============================================================================
# ENVIRONMENT
# ============================================================================
#
#   RETENTION_MODE              dry-run (default) | enforce
#   RETENTION_KEEP              the margin of class 6. Default 10.
#   GHCR_RETENTION_TOKEN        REQUIRED. read:packages + delete:packages on the
#                               organization, and contents:read on every
#                               repository named below. The workflow
#                               GITHUB_TOKEN cannot stand in: it carries no
#                               delete:packages, and it is scoped to this
#                               repository alone so it can read neither eden nor
#                               infrastructure. GH_TOKEN and GITHUB_TOKEN are
#                               read as fallbacks so `gh auth` covers a local
#                               dry run.
#   RETENTION_SUBMODULE_REPOS   repositories that pin this one as a submodule.
#                               Default: gophersys/eden
#   RETENTION_PIN_REPOS         repositories swept for image refs and digests.
#                               Default: gophersys/infrastructure gophersys/eden
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/affected.sh sets it: the git fallback
# in _ctl/lib.sh reads the wrong root when this repository is a submodule
# worktree.
REPO_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

# The logging, the tool gate, the image set and the registry token exchange all
# live in _ctl/lib.sh, 1 time only.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../_ctl/lib.sh
source "$PROJECT_ROOT/../_ctl/lib.sh"

RETENTION_MODE="${RETENTION_MODE:-dry-run}"
RETENTION_KEEP="${RETENTION_KEEP:-10}"
RETENTION_SUBMODULE_REPOS="${RETENTION_SUBMODULE_REPOS:-gophersys/eden}"
# Every repository that pins an image of this one. It is a DEFAULT and not a
# discovery: there is no API that answers "who pins me", so the list is
# maintained, and a consumer missing from it is a consumer whose pins this
# policy will delete. That is not hypothetical — see the `:tag@sha256:` trap in
# the header: research-hardware and research-ui were absent from the first
# version of this line, and the first real dry run planned to delete the exact
# digests both of them pin.
RETENTION_PIN_REPOS="${RETENTION_PIN_REPOS:-gophersys/infrastructure gophersys/eden gophersys/research-hardware gophersys/research-ui}"

# The owner the packages hang off. IMAGE_REGISTRY_NAMESPACE in _ctl/lib.sh is
# `ghcr.io/gophersys` and the packages API addresses the same owner by name, so
# it is derived rather than spelled a second time.
RETENTION_ORG="${IMAGE_REGISTRY_NAMESPACE#*/}"

# The path gophersys/eden mounts this repository at. It is what turns a
# consumer's submodule pointer into a tag of ours.
SUBMODULE_PATH=".devcontainer"

# The tag shapes this repository publishes, and the ONLY ones.
# build-and-push.yml writes `latest` and the 7-character short sha, plus a
# `v<semver>` on a tag ref. Measured 2026-08-26 across base, cloud, mobile,
# embedded, hardware, ui and the retired flutter: 265 tags, every one `latest`
# or exactly 7 hex characters, and not one outside those shapes.
#
# A tag matching none of them is a decision nobody in this repository recorded,
# and it stops the run before anything is deleted. Keeping it silently would be
# a permanent exception written as an accident; deleting it silently would
# destroy whatever it was for.
TAG_LATEST="latest"
TAG_SEMVER_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+'
TAG_SHORT_SHA_PATTERN='^[0-9a-f]{7}$'

# The media types a manifest read must accept, as ONE comma-separated header.
#
# GHCR DOES NOT HONOUR `Accept: */*`. It answers 404 MANIFEST_UNKNOWN for a
# manifest that exists and serves perfectly under an explicit media type, and
# curl sends `Accept: */*` by default when no Accept header is given. A walk
# that inherited that default would read "no such manifest" for a live index,
# conclude it has no children, and put every one of them in the delete plan —
# an under-protection that looks exactly like a clean read. That is why a
# non-200 during the walk is fatal below rather than an empty child list.
#
# One header rather than 4 repeated ones: a comma-separated list is the form
# RFC 9110 defines for Accept, and a server is free to read only the first of 4
# repeated headers.
#
# This is NOT registry_get_status from _ctl/lib.sh, and the reason is this list:
# that reader accepts the 2 IMAGE manifest types because verify-published probes
# per-platform manifests and blobs with it. Widening a shared reader so one
# caller can fetch an index changes what the other caller negotiates.
MANIFEST_ACCEPT="application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"

WORK_DIRECTORY=""
function retention_cleanup() {
  if [[ -n "$WORK_DIRECTORY" && -d "$WORK_DIRECTORY" ]]; then
    rm -rf "$WORK_DIRECTORY"
  fi
  return 0
}
trap retention_cleanup EXIT

# ---------------------------------------------------------------------------
# The readers.
# ---------------------------------------------------------------------------

# jq_to_file <destination> <jq argument>... — jq's output at <destination>, and
# a FAILURE naming the expression when jq refuses it.
#
# THE TRAP THIS EXISTS FOR, and it bit this file on its first real run.
# `retention_plan ... || return 1` reads correctly and is wrong: bash turns
# errexit OFF for the whole body of a function whose status is tested that way,
# and re-arming it inside does not bring it back. Two jq expressions here
# carried a context bug — `$array | index(.name)` re-binds `.` to the array, so
# `.name` indexed an array and jq exited 5 — both wrote an EMPTY file, both
# printed to stderr, and the run reported `DELETE 0` and exited 0.
#
# An empty delete plan is exactly the shape of a healthy steady-state week, so
# that failure was invisible in the one place it mattered most. Every jq that
# produces protection or plan data goes through here, and its status is read
# from jq itself rather than from anything wrapped around it.
function jq_to_file() {
  local destination="$1"
  shift
  local status=0
  set +e
  jq "$@" > "$destination"
  status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    log_error "jq exited ${status} for: $*"
    return 1
  fi
  return 0
}

# grep_lines <destination> <grep argument>... — write grep's matches to
# <destination>, and tell "no match" apart from "grep failed".
#
# grep exits 1 for a pattern that matched nothing and 2 for a real error — an
# unreadable file, a bad expression — and every caller here has a legitimate
# empty answer. `|| true` would flatten the 2 into a green, which is the exact
# shape this repository refuses everywhere else, and it is worse here than
# usual: the empty file it leaves behind becomes an empty PROTECTION class.
function grep_lines() {
  local destination="$1"
  shift
  local status=0
  set +e
  grep "$@" > "$destination"
  status=$?
  set -e
  if [[ "$status" -gt 1 ]]; then
    log_error "grep exited ${status} for: $*"
    return 1
  fi
  return 0
}

# list_items <space separated list> — 1 item per line.
#
# IFS is $'\n\t' in this file, the way it is in every script of this repository,
# so a bare `for x in $LIST` over a SPACE separated value yields 1 element
# holding the whole string. Every list this script takes from the environment
# comes through here.
function list_items() {
  local value="$1"
  local -a parts=()
  IFS=' ' read -r -a parts <<< "$value"
  local part
  for part in "${parts[@]}"; do
    [[ -z "$part" ]] && continue
    printf '%s\n' "$part"
  done
}

# joined <element>... — the elements separated by a single space.
# `${array[*]}` joins on the first character of IFS, which is a newline here.
# The root ctl.sh usage block does the same thing for the same reason.
function joined() {
  local out
  out="$(IFS=' '; printf '%s' "$*")"
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# The credential.
# ---------------------------------------------------------------------------

# retention_token — the secret every read and every delete below goes through.
#
# A missing credential is a FAILURE that names the secret. A retention run
# without one could only report "nothing to do", which is a green that checked
# nothing.
function retention_token() {
  local secret="${GHCR_RETENTION_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"
  if [[ -z "$secret" ]]; then
    log_error "no credential: set GHCR_RETENTION_TOKEN"
    log_error "  it needs read:packages + delete:packages on the ${RETENTION_ORG} organization,"
    log_error "  and contents:read on: ${RETENTION_PIN_REPOS} ${RETENTION_SUBMODULE_REPOS}"
    log_error "  the workflow GITHUB_TOKEN cannot stand in: no delete:packages, and no read of"
    log_error "  any repository but this one"
    return 1
  fi
  printf '%s' "$secret"
}

# ---------------------------------------------------------------------------
# The packages API.
# ---------------------------------------------------------------------------

# package_versions <package> — the version list as a JSON array on stdout.
#
# gh merges the pages of an array endpoint under --paginate. An empty array is a
# FAILURE: a package this repository publishes has versions, so an empty answer
# is a read that did not work and must not read as a package with nothing in it.
function package_versions() {
  local package="$1"
  local body="" status=0
  set +e
  body="$(gh api --paginate "/orgs/${RETENTION_ORG}/packages/container/${package}/versions?per_page=100")"
  status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    log_error "the packages API refused the version list of ${package} — gh exited ${status}"
    return 1
  fi
  local count=""
  count="$(printf '%s' "$body" | jq 'length')"
  if [[ "$count" -eq 0 ]]; then
    log_error "${package} answered 0 versions — a package this repository publishes has"
    log_error "versions, so this is a read that failed and not a package with nothing in it"
    return 1
  fi
  printf '%s' "$body"
}

# delete_version <package> <version id> — remove one version from the registry.
function delete_version() {
  local package="$1" version_id="$2"
  local status=0
  set +e
  gh api --silent --method DELETE \
    "/orgs/${RETENTION_ORG}/packages/container/${package}/versions/${version_id}"
  status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    log_error "DELETE of ${package} version ${version_id} failed — gh exited ${status}"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# The registry, for the parent -> child closure.
# ---------------------------------------------------------------------------

# manifest_children <package> <digest> <token> — every child digest that
# manifest declares, 1 per line. An image manifest declares none and prints
# nothing.
#
# A read that does not answer 200 is FATAL. This walk is the whole of protection
# class 5, so a manifest it could not read is a set of live children that falls
# out of the protected set and into the delete plan.
function manifest_children() {
  local package="$1" digest="$2" token="$3"
  local host repository url code="" status=0
  host="$(registry_host)"
  repository="$(registry_repository "$package")"
  url="https://${host}/v2/${repository}/manifests/${digest}"

  local staged="${WORK_DIRECTORY}/manifest.json"
  set +e
  code="$(curl -sSL --max-time 60 --retry 3 --retry-delay 2 --retry-all-errors \
    --output "$staged" --write-out '%{http_code}' \
    --header "Authorization: Bearer ${token}" \
    --header "Accept: ${MANIFEST_ACCEPT}" \
    "$url")"
  status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    log_error "the manifest read of ${package}@${digest} did not complete — curl exited ${status}"
    return 1
  fi
  if [[ "$code" != "200" ]]; then
    log_error "${host} answered ${code} for the manifest of ${package}@${digest}"
    log_error "this walk is what keeps the children of a protected tag alive, so an unread"
    log_error "manifest would put live content into the delete plan"
    log_error "a 404 here is NOT 'no such manifest': ghcr.io answers 404 MANIFEST_UNKNOWN for a"
    log_error "manifest it serves, when the Accept header does not name its media type"
    return 1
  fi
  if ! jq empty "$staged"; then
    log_error "the manifest of ${package}@${digest} is not JSON"
    return 1
  fi
  jq -r '.manifests[]?.digest' "$staged"
}

# ---------------------------------------------------------------------------
# The live pins, read from the consumers.
# ---------------------------------------------------------------------------

# submodule_pointers <destination> — every short sha a consumer's submodule
# pointer names, written to <destination> as
# `<short sha>|<repository>|<ref>`, 1 per line.
#
# It writes to a FILE and not to stdout, because log_info writes to stdout in
# this repository and a caller capturing this function would read its own log as
# data. .ci/affected.sh carries the same note about the same hazard.
#
# main AND every open pull request: eden main pinned 685ac28 on 2026-08-26 while
# open pull requests #14 and #7 pinned 69fc6a9 and e67d6cd.
function submodule_pointers() {
  local destination="$1"
  : > "$destination"

  local -a repositories=()
  local entry
  while IFS= read -r entry; do
    repositories+=("$entry")
  done < <(list_items "$RETENTION_SUBMODULE_REPOS")
  if [[ "${#repositories[@]}" -eq 0 ]]; then
    log_error "RETENTION_SUBMODULE_REPOS is empty — protection class 3 would read nothing"
    return 1
  fi

  local repository default_branch="" heads="" head ref sha="" status=0
  local produced=0
  for repository in "${repositories[@]}"; do
    set +e
    default_branch="$(gh api "repos/${repository}" --jq '.default_branch')"
    status=$?
    set -e
    if [[ "$status" -ne 0 ]]; then
      log_error "cannot read ${repository} — gh exited ${status}"
      log_error "its submodule pointer is protection class 3, so an unread consumer means the"
      log_error "tag it pins goes into the delete plan"
      return 1
    fi

    local -a refs=("$default_branch")
    set +e
    heads="$(gh api --paginate "repos/${repository}/pulls?state=open&per_page=100" --jq '.[].head.sha')"
    status=$?
    set -e
    if [[ "$status" -ne 0 ]]; then
      log_error "cannot list the open pull requests of ${repository} — gh exited ${status}"
      return 1
    fi
    while IFS= read -r head; do
      [[ -z "$head" ]] && continue
      refs+=("$head")
    done <<< "$heads"

    for ref in "${refs[@]}"; do
      sha=""
      set +e
      sha="$(gh api "repos/${repository}/contents/${SUBMODULE_PATH}?ref=${ref}" \
        --jq 'select(.type == "submodule") | .sha')"
      status=$?
      set -e
      if [[ "$status" -ne 0 ]]; then
        # A ref carrying no such submodule is a real answer and not a failed
        # read — a branch that predates the submodule, or one that removed it.
        # The repository-level reads above are what catch a broken grant.
        log_info "  ${repository}@${ref}: no ${SUBMODULE_PATH} submodule"
        continue
      fi
      [[ -z "$sha" ]] && continue
      printf '%s|%s|%s\n' "${sha:0:7}" "$repository" "$ref" >> "$destination"
      produced=$((produced + 1))
    done
  done

  if [[ "$produced" -eq 0 ]]; then
    log_error "no submodule pointer was read from: ${RETENTION_SUBMODULE_REPOS}"
    log_error "protection class 3 would be empty, so every tag a consumer pins goes into the plan"
    return 1
  fi
  return 0
}

# sweep_pin_sources <destination> — put every tree and every open pull request
# patch that may hold a pin under <destination>.
#
# The default branch arrives as a tarball, which is 1 request for a whole tree.
# An open pull request arrives as its PATCH text, which is 1 request and catches
# a digest a promotion pull request ADDS without paying a tarball per branch.
function sweep_pin_sources() {
  local destination="$1"

  local -a repositories=()
  local entry
  while IFS= read -r entry; do
    repositories+=("$entry")
  done < <(list_items "$RETENTION_PIN_REPOS")
  if [[ "${#repositories[@]}" -eq 0 ]]; then
    log_error "RETENTION_PIN_REPOS is empty — protection class 4 would read nothing"
    return 1
  fi

  # THIS REPOSITORY IS DELIBERATELY NOT A SOURCE, and it was until the counter-
  # stimulus below refused to fire.
  #
  # The sweep is a grep over a whole tree, so it reads PROSE as readily as
  # configuration. This file's own header names `ghcr.io/gophersys/base:e0c6bc5`
  # while explaining that infrastructure pins it — and that sentence alone
  # protected the tag. With RETENTION_PIN_REPOS pointed at a repository holding
  # no pin at all, `e0c6bc5` was still protected, so class 4 could not be
  # observed to do anything. A policy that documents a pin and thereby CREATES
  # it is not a policy.
  #
  # `.claude/rules/00-identity.md` carries the same hazard independently: it
  # names `ghcr.io/gophersys/base:69b4f11` in a sentence about an old incident,
  # which would have pinned that tag for the life of the repository.
  #
  # Nothing is lost by the removal. Every reference this repository makes to its
  # own images is `:latest` — 29 of them across the devcontainer.json files and
  # the documents, measured 2026-08-26 — and `latest` is protection class 1. A
  # pin is read from a CONSUMER, which is the only place one can exist.
  #
  # A consumer's prose stays in scope, and the asymmetry is deliberate: an
  # over-protection sourced from somebody else's document keeps a version that
  # could have gone, which is the safe direction. An over-protection sourced
  # from our own document is a policy grading its own homework.
  local status=0
  local repository slug archive numbers="" number
  local swept=0
  for repository in "${repositories[@]}"; do
    slug="${repository//\//_}"
    archive="${WORK_DIRECTORY}/${slug}.tar.gz"
    mkdir -p "${destination}/${slug}"
    set +e
    gh api "repos/${repository}/tarball" > "$archive"
    status=$?
    set -e
    if [[ "$status" -ne 0 ]]; then
      log_error "cannot read the tree of ${repository} — gh exited ${status}"
      log_error "protection class 4 reads its digest pins there, so an unread consumer means"
      log_error "every digest it pins goes into the delete plan"
      return 1
    fi
    set +e
    tar -xzf "$archive" -C "${destination}/${slug}"
    status=$?
    set -e
    if [[ "$status" -ne 0 ]]; then
      log_error "the tarball of ${repository} did not extract — tar exited ${status}"
      return 1
    fi
    rm -f "$archive"

    set +e
    numbers="$(gh api --paginate "repos/${repository}/pulls?state=open&per_page=100" --jq '.[].number')"
    status=$?
    set -e
    if [[ "$status" -ne 0 ]]; then
      log_error "cannot list the open pull requests of ${repository} — gh exited ${status}"
      return 1
    fi
    : > "${destination}/${slug}-pulls.patch"
    while IFS= read -r number; do
      [[ -z "$number" ]] && continue
      set +e
      gh api --paginate "repos/${repository}/pulls/${number}/files?per_page=100" \
        --jq '.[].patch // empty' >> "${destination}/${slug}-pulls.patch"
      status=$?
      set -e
      if [[ "$status" -ne 0 ]]; then
        log_error "cannot read the files of ${repository}#${number} — gh exited ${status}"
        return 1
      fi
    done <<< "$numbers"
    swept=$((swept + 1))
  done

  log_info "  swept ${swept} consumer repositories"

  # THE CENSUS. Every `ghcr.io/<owner>/…@sha256:…` pin the sweep can see, listed
  # rather than counted-and-trusted, because this is the class whose silent
  # emptiness is most expensive and least visible.
  #
  # The expression matches BOTH forms — `<name>@sha256:` and
  # `<name>:<tag>@sha256:` — and the second one is why it is written out here.
  # A regex that stopped at the tag reported the research-repository pins as
  # `:latest` refs and the digest they actually pin was never seen.
  #
  # It is REPORTED and not gated. A day when no consumer pins a digest is a
  # legitimate day, and a guard that went red on it would be a guard somebody
  # has to disable. What IS gated is the read of each repository above, which
  # can never legitimately fail.
  grep_lines "${WORK_DIRECTORY}/census" \
    -rIhoE "ghcr\.io/${RETENTION_ORG}/[A-Za-z0-9._/-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}" \
    "$destination" || return 1
  sort -u "${WORK_DIRECTORY}/census" -o "${WORK_DIRECTORY}/census"
  local census_count pin
  census_count="$(wc -l < "${WORK_DIRECTORY}/census" | tr -d ' ')"
  log_info "  ${census_count} digest pins found across those repositories"
  local pin_digest
  while IFS= read -r pin; do
    [[ -z "$pin" ]] && continue
    pin_digest="sha256:${pin##*@sha256:}"
    log_info "    ${pin}"
    if pin_is_fixture_only "$pin_digest" "$destination"; then
      log_info "      ^ every reference to this digest is in a TEST FIXTURE. It is protected"
      log_info "        anyway, and the fix belongs in the consumer: a fixture that spells a"
      log_info "        REAL digest pins it here for as long as the fixture stands."
    fi
  done < "${WORK_DIRECTORY}/census"
  return 0
}

# pin_is_fixture_only <digest> <sweep directory> — true when every file
# referencing that digest looks like a test fixture.
#
# It CLASSIFIES and never excludes. A path heuristic that dropped a pin from the
# protected set would trade a bounded cost — 1 index and its children kept
# forever — for the unbounded one this whole file exists to prevent: a real pin
# living in a file whose name happens to say `test`, deleted, and an ARC pool or
# a consumer's CI broken by it. Over-protection is the safe direction; the
# report is how it stops being invisible.
#
# Measured 2026-08-26: `cloud@sha256:9a150cbf…` is referenced only by
# infrastructure/scripts/test-verify-warmer-pins.sh, which states in its own
# header that the suite never reads the real manifests.
function pin_is_fixture_only() {
  local digest="$1" sweep="$2"
  local file
  local any=0
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    any=1
    case "${file##*/}" in
      test-*|*-test.sh|*_test.*|*.test.*) ;;
      *) return 1 ;;
    esac
  done < <(grep -rIlF "$digest" "$sweep")
  [[ "$any" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# The report.
# ---------------------------------------------------------------------------

# retention_row <label> <count> <note> — 1 line of the per-package board. Every
# caller passes all 3; an empty note is passed as an empty string rather than
# left off, because a defaulted parameter is what shellcheck 0.9.0 reports as
# SC2119/SC2120 and this repository lints at exactly that version.
function retention_row() {
  printf '  %-32s %6s  %s\n' "$1" "$2" "$3"
}

# ---------------------------------------------------------------------------
# The policy, per package.
# ---------------------------------------------------------------------------

# retention_plan <package> <token> <sweep directory> <pointer file> — write the
# delete plan for 1 package and print its board.
#
# The plan file holds `<version id>|<digest>|<tags>` for every version the
# policy would remove.
function retention_plan() {
  local package="$1" token="$2" sweep="$3" pointers="$4"
  local directory="${WORK_DIRECTORY}/${package}"
  mkdir -p "$directory"

  local versions=""
  versions="$(package_versions "$package")" || return 1
  printf '%s' "$versions" > "${directory}/versions.json"

  local total tagged untagged
  total="$(jq 'length' "${directory}/versions.json")"
  tagged="$(jq '[.[] | select((.metadata.container.tags | length) > 0)] | length' "${directory}/versions.json")"
  untagged=$((total - tagged))

  jq -r '.[] | .metadata.container.tags[]?' "${directory}/versions.json" \
    | sort -u > "${directory}/tags"

  # Every tag, classified. An unknown shape aborts before anything is deleted.
  local tag unknown=""
  while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    [[ "$tag" == "$TAG_LATEST" ]] && continue
    [[ "$tag" =~ $TAG_SEMVER_PATTERN ]] && continue
    [[ "$tag" =~ $TAG_SHORT_SHA_PATTERN ]] && continue
    unknown="${unknown:+${unknown} }${tag}"
  done < "${directory}/tags"
  if [[ -n "$unknown" ]]; then
    log_error "${package} carries tags of a shape this policy does not know: ${unknown}"
    log_error "build-and-push.yml writes 'latest', '<7 hex>' and 'v<semver>' and nothing else, so"
    log_error "each of these is a decision nobody recorded — classify it in TAG_* before this"
    log_error "run is allowed to delete anything from ${package}"
    return 1
  fi

  # ---- classes 1 and 2: latest, and every semver ----
  grep_lines "${directory}/latest-tags" -xF "$TAG_LATEST" "${directory}/tags" || return 1
  grep_lines "${directory}/semver-tags" -E "$TAG_SEMVER_PATTERN" "${directory}/tags" || return 1
  local latest_count semver_count
  latest_count="$(wc -l < "${directory}/latest-tags" | tr -d ' ')"
  semver_count="$(wc -l < "${directory}/semver-tags" | tr -d ' ')"
  cat "${directory}/latest-tags" "${directory}/semver-tags" > "${directory}/protected-tags"

  # ---- class 3: a live submodule pointer ----
  : > "${directory}/pin-tags"
  local short repository ref
  while IFS='|' read -r short repository ref; do
    [[ -z "$short" ]] && continue
    if grep -qxF "$short" "${directory}/tags"; then
      printf '%s\n' "$short" >> "${directory}/pin-tags"
      log_info "  ${package}:${short} is pinned by ${repository}@${ref}"
    fi
  done < "$pointers"
  sort -u "${directory}/pin-tags" -o "${directory}/pin-tags"
  local pointer_count
  pointer_count="$(wc -l < "${directory}/pin-tags" | tr -d ' ')"
  cat "${directory}/pin-tags" >> "${directory}/protected-tags"

  # ---- class 4: a tag or a digest a consumer pins ----
  #
  # The tag half is exact: `ghcr.io/<owner>/<package>:<tag>`. The digest half is
  # deliberately OVER-BROAD — every sha256 token of every swept tree, whether or
  # not it sits beside an image reference. Over-protecting keeps a version that
  # could have gone; under-protecting deletes one a cluster is running. There
  # were 12 distinct sha256 tokens in gophersys/infrastructure on 2026-08-26, so
  # the wide net costs 12 lookups.
  #
  # -I skips a binary file. Every pin is text, and a `-o` over a binary blob
  # reports a match nobody can act on.
  grep_lines "${directory}/ref-lines" -rIhoE "ghcr\.io/${RETENTION_ORG}/${package}:[A-Za-z0-9._-]+" "$sweep" || return 1
  sed 's|.*:||' "${directory}/ref-lines" | sort -u > "${directory}/ref-tags"
  local ref_hits=0 ref_tag
  while IFS= read -r ref_tag; do
    [[ -z "$ref_tag" ]] && continue
    if grep -qxF "$ref_tag" "${directory}/tags"; then
      printf '%s\n' "$ref_tag" >> "${directory}/protected-tags"
      ref_hits=$((ref_hits + 1))
      log_info "  ${package}:${ref_tag} is pinned by tag in a consumer"
    fi
  done < "${directory}/ref-tags"

  grep_lines "${directory}/ref-digest-lines" -rIhoE 'sha256:[0-9a-f]{64}' "$sweep" || return 1
  sort -u "${directory}/ref-digest-lines" > "${directory}/ref-digests"

  # ---- the seed set of protected DIGESTS ----
  sort -u "${directory}/protected-tags" -o "${directory}/protected-tags"
  # shellcheck disable=SC2016  # $tags/$seed/$safe/$v are jq variables, not shell ones
  jq_to_file "${directory}/seed" -r --rawfile wanted "${directory}/protected-tags" '
      ($wanted | split("\n") | map(select(length > 0))) as $tags
      | .[]
      | select(any(.metadata.container.tags[]?; . as $t | $tags | index($t) != null))
      | .name
    ' "${directory}/versions.json" || return 1

  local digest_hits=0 ref_digest
  while IFS= read -r ref_digest; do
    [[ -z "$ref_digest" ]] && continue
    if jq -e --arg d "$ref_digest" 'any(.[]; .name == $d)' "${directory}/versions.json" > /dev/null; then
      printf '%s\n' "$ref_digest" >> "${directory}/seed"
      digest_hits=$((digest_hits + 1))
      log_info "  ${package}@${ref_digest} is pinned by digest in a consumer"
    fi
  done < "${directory}/ref-digests"
  sort -u "${directory}/seed" -o "${directory}/seed"

  # ---- class 6: the margin ----
  #
  # The RETENTION_KEEP most recent TAGGED versions classes 1-5 did not already
  # reach, ordered by created_at and never by the tag text: a short sha carries
  # no order.
  # `. as $v` before the lookup is the whole fix for the defect jq_to_file's
  # header records: inside `index(...)` the input is the ARRAY, so a bare
  # `.name` there indexes the array instead of the version.
  # shellcheck disable=SC2016  # $tags/$seed/$safe/$v are jq variables, not shell ones
  jq_to_file "${directory}/margin" -r --rawfile already "${directory}/seed" --argjson keep "$RETENTION_KEEP" '
      ($already | split("\n") | map(select(length > 0))) as $seed
      | [ .[]
          | . as $v
          | select((.metadata.container.tags | length) > 0)
          | select(($seed | index($v.name)) == null)
        ]
      | sort_by(.created_at) | reverse | .[0:$keep] | .[].name
    ' "${directory}/versions.json" || return 1
  local margin_count
  margin_count="$(wc -l < "${directory}/margin" | tr -d ' ')"
  cat "${directory}/margin" >> "${directory}/seed"
  sort -u "${directory}/seed" -o "${directory}/seed"

  local seed_count
  seed_count="$(wc -l < "${directory}/seed" | tr -d ' ')"
  if [[ "$seed_count" -eq 0 ]]; then
    log_error "${package}: the protected set is EMPTY, and every package carries :latest — so"
    log_error "this is a classification that read nothing, not a package with nothing to keep"
    return 1
  fi

  # ---- class 5: the transitive closure over the children ----
  #
  # A worklist rather than 1 pass. An index whose child is itself an index would
  # otherwise leave a generation of live content unprotected, and the walk costs
  # 1 request per protected version either way. The cursor is an INDEX and the
  # array is never resliced: `"${array[@]}"` on an emptied array is an unbound
  # reference under `set -u` on bash 3.2, which is the bash this repository's
  # gate still runs on a mac.
  cp "${directory}/seed" "${directory}/protected"
  local -a worklist=()
  local item
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    worklist+=("$item")
  done < "${directory}/seed"

  local cursor=0 reads=0 child children=""
  while [[ "$cursor" -lt "${#worklist[@]}" ]]; do
    item="${worklist[$cursor]}"
    cursor=$((cursor + 1))
    children="$(manifest_children "$package" "$item" "$token")" || return 1
    reads=$((reads + 1))
    while IFS= read -r child; do
      [[ -z "$child" ]] && continue
      if ! grep -qxF "$child" "${directory}/protected"; then
        printf '%s\n' "$child" >> "${directory}/protected"
        worklist+=("$child")
      fi
    done <<< "$children"
  done

  if [[ "$reads" -eq 0 ]]; then
    log_error "${package}: the closure walk read 0 manifests, so no child is protected"
    return 1
  fi
  sort -u "${directory}/protected" -o "${directory}/protected"

  local protected_count child_count
  protected_count="$(wc -l < "${directory}/protected" | tr -d ' ')"
  child_count=$((protected_count - seed_count))

  # ---- the delete plan ----
  #
  # `all versions - protected closure`, and never a walk down from the doomed: a
  # child digest has more than 1 parent, so that walk removes content a
  # surviving index still points at.
  #
  # A TAGGED version comes first in the plan. The tagged index is what holds the
  # reference to its children, so removing the parent before the children never
  # leaves the registry holding an index whose content has gone.
  # shellcheck disable=SC2016  # $tags/$seed/$safe/$v are jq variables, not shell ones
  jq_to_file "${directory}/plan" -r --rawfile keep "${directory}/protected" '
      ($keep | split("\n") | map(select(length > 0))) as $safe
      | [ .[] | . as $v | select(($safe | index($v.name)) == null) ]
      | sort_by([ (if (.metadata.container.tags | length) > 0 then 0 else 1 end), .created_at ])
      | .[]
      | "\(.id)|\(.name)|\(.metadata.container.tags | join(","))"
    ' "${directory}/versions.json" || return 1

  local delete_count
  delete_count="$(wc -l < "${directory}/plan" | tr -d ' ')"

  # THE SECOND OPINION. The delete set is recomputed by a DIFFERENT TOOL over
  # the same 2 inputs, and the 2 answers must agree.
  #
  # An earlier version of this block compared `kept + planned == versions`, and
  # the review agent was right to refuse it. `kept` and `planned` were 2 jq
  # selections partitioning ONE array by ONE predicate, so their sum was that
  # array's length for every possible input, a corrupted `$safe` included. It
  # passed on the exact DELETE-0 regression it was advertised to catch:
  # simulated 2026-08-26, a plan predicate that is always false leaves every
  # version in `kept`, and `316 + 0 == 316` holds. A check that cannot fail,
  # presented in 3 places as the safety net.
  #
  # THE REAL CATCH FOR THAT REGRESSION IS `jq_to_file`, which reads jq's own
  # exit status, and it is sufficient for a jq that ERRORS. What it cannot see
  # is a jq expression that exits 0 and answers wrongly, and that is this
  # block's job: `comm` cannot share a bug with a jq filter, so a disagreement
  # between them is a real one.
  jq_to_file "${directory}/all-digests" -r '.[].name' "${directory}/versions.json" || return 1
  LC_ALL=C sort -u "${directory}/all-digests" -o "${directory}/all-digests"
  LC_ALL=C sort -u "${directory}/protected" -o "${directory}/protected"
  LC_ALL=C comm -23 "${directory}/all-digests" "${directory}/protected" \
    > "${directory}/delete-digests"

  local second_opinion
  second_opinion="$(wc -l < "${directory}/delete-digests" | tr -d ' ')"
  if [[ "$second_opinion" -ne "$delete_count" ]]; then
    log_error "${package}: the plan holds ${delete_count} versions and set arithmetic over the"
    log_error "same 2 files says ${second_opinion} — 2 tools disagree about what is unprotected,"
    log_error "so one of them is wrong and nothing is deleted"
    return 1
  fi

  # Every protected digest ought to be a version this package lists. One that is
  # not means the closure walked to a manifest the packages API does not report.
  # It is REPORTED and not fatal: it protects something that does not exist,
  # which costs nothing, and a reader is better off seeing the number than
  # having it asserted away. Measured 0 on every package, 2026-08-26.
  local unlisted_protected
  unlisted_protected="$(LC_ALL=C comm -13 "${directory}/all-digests" "${directory}/protected" | wc -l | tr -d ' ')"

  printf '\n'
  log_info "package ${package}"
  retention_row "versions" "$total" ""
  retention_row "tagged" "$tagged" ""
  retention_row "untagged" "$untagged" ""
  retention_row "protect: latest" "$latest_count" ""
  retention_row "protect: semver" "$semver_count" ""
  retention_row "protect: submodule pin" "$pointer_count" ""
  retention_row "protect: consumer tag ref" "$ref_hits" ""
  retention_row "protect: consumer digest" "$digest_hits" ""
  retention_row "protect: margin" "$margin_count" "the ${RETENTION_KEEP} most recent left over"
  retention_row "protected parents" "$seed_count" ""
  retention_row "protected children" "$child_count" "from ${reads} manifest reads"
  retention_row "PROTECTED total" "$protected_count" "${unlisted_protected} not listed as a version"
  retention_row "DELETE" "$delete_count" "agreed by set arithmetic"

  local version_id digest tags
  while IFS='|' read -r version_id digest tags; do
    [[ -z "$version_id" ]] && continue
    printf '      delete %-12s %s %s\n' "$version_id" "$digest" "${tags:+[${tags}]}"
  done < "${directory}/plan"
  return 0
}

# retention_apply <package> — delete every version of that package's plan.
function retention_apply() {
  local package="$1"
  local plan="${WORK_DIRECTORY}/${package}/plan"
  local version_id digest tags applied=0
  while IFS='|' read -r version_id digest tags; do
    [[ -z "$version_id" ]] && continue
    log_info "  DELETE ${package} ${version_id} ${digest} ${tags:+[${tags}]}"
    delete_version "$package" "$version_id" || return 1
    applied=$((applied + 1))
  done < "$plan"
  log_info "  ${package}: ${applied} versions deleted"
  return 0
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

function main() {
  require_cmd gh jq curl tar sed

  case "$RETENTION_MODE" in
    dry-run|enforce) ;;
    *)
      log_error "RETENTION_MODE is '${RETENTION_MODE}' — it is 'dry-run' or 'enforce'"
      return 2
      ;;
  esac
  if [[ ! "$RETENTION_KEEP" =~ ^[0-9]+$ ]]; then
    log_error "RETENTION_KEEP is '${RETENTION_KEEP}' — it is a non-negative integer"
    return 2
  fi

  local -a packages=()
  local name
  if [[ "$#" -gt 0 ]]; then
    packages=("$@")
  else
    local names=""
    names="$(image_names)" || return 1
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      packages+=("$name")
    done <<< "$names"
  fi

  for name in "${packages[@]}"; do
    # The API path is built by concatenation, and a name carrying a `/` would
    # address a package this policy has never been measured against. eden
    # publishes `eden/agentgateway` and 3 siblings that way, and they are not
    # this repository's to prune.
    if [[ "$name" == */* ]]; then
      log_error "'${name}' is not a package of this repository — the retention policy of"
      log_error "gophersys/.devcontainer covers the images images.yaml declares, and nothing else"
      return 2
    fi
  done

  local secret=""
  secret="$(retention_token)" || return 1
  export GH_TOKEN="$secret"

  WORK_DIRECTORY="$(mktemp -d)"

  log_info "ghcr retention — mode ${RETENTION_MODE}, keep ${RETENTION_KEEP}"
  log_info "packages: $(joined "${packages[@]}")"

  log_info "reading the live submodule pointers of: ${RETENTION_SUBMODULE_REPOS}"
  submodule_pointers "${WORK_DIRECTORY}/pointers" || return 1
  local short repository ref
  while IFS='|' read -r short repository ref; do
    [[ -z "$short" ]] && continue
    log_info "  ${short}  ${repository}@${ref}"
  done < "${WORK_DIRECTORY}/pointers"

  log_info "sweeping the consumers for pinned tags and digests: ${RETENTION_PIN_REPOS}"
  local sweep="${WORK_DIRECTORY}/sweep"
  mkdir -p "$sweep"
  sweep_pin_sources "$sweep" || return 1

  local host token repository_path
  host="$(registry_host)"

  local planned=0 count
  for name in "${packages[@]}"; do
    repository_path="$(registry_repository "$name")"
    token="$(registry_pull_token "$host" "$repository_path" "$secret")"
    retention_plan "$name" "$token" "$sweep" "${WORK_DIRECTORY}/pointers" || return 1
    count="$(wc -l < "${WORK_DIRECTORY}/${name}/plan" | tr -d ' ')"
    planned=$((planned + count))
  done

  printf '\n'
  if [[ "$RETENTION_MODE" == "dry-run" ]]; then
    log_info "DRY RUN — ${planned} versions would be deleted, and NOTHING was"
    log_info "set RETENTION_MODE=enforce to make this run act"
    return 0
  fi

  local deleted=0
  for name in "${packages[@]}"; do
    count="$(wc -l < "${WORK_DIRECTORY}/${name}/plan" | tr -d ' ')"
    retention_apply "$name" || return 1
    deleted=$((deleted + count))
  done
  log_info "ENFORCED — ${deleted} versions deleted of ${planned} planned"
  return 0
}

main "$@"
