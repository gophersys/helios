#!/usr/bin/env bash
#
# _ctl/generate.sh — images.yaml -> the mechanical workflow homes.
#
# It writes 2 things:
#
#   .ci/providers/github/build-and-push.yml   the whole file, 1 job per image
#   .ci/providers/github/security-nightly.yml the `image:` line of the scan
#                                             matrix, and nothing else
#
# The direction is the one this repository already uses: the provider directory
# is the source of truth, .github/workflows/ holds a hand-made copy of each of
# its files, and _ctl/tests/platform-policy.test.sh compares the 2 with `cmp`.
# So the loop is: edit images.yaml or this template, run this script, copy the
# provider file to .github/workflows/, and let the `cmp` hold the pair.
#
# ============================================================================
# WHY IT EXISTS
# ============================================================================
#
# The 5 publish jobs were 119, 111, 115, 126 and 117 hand-written lines that
# differed only in a name, a context, a file and a `needs:`. `cmp` caught drift
# between the workflow and its provider copy; NOTHING caught drift between the
# 5 jobs, and this repository shipped that defect twice — a provider copy that
# listed 3 images, and commit d9089b2 adding 5 `timeout-minutes` blocks to one
# file and to neither copy of the other. A job that is a template applied to a
# manifest entry cannot diverge from its siblings, because there is only 1 of
# it.
#
# ============================================================================
# WHAT BELONGS IN THE TEMPLATE, AND WHAT BELONGS IN THE MANIFEST
# ============================================================================
#
# Anything TRUE OF EVERY JOB is in this file: the step order, the gate on
# `steps.filter.outputs.build`, the smoke-before-push order, the cache refs, the
# timeout, the runner. Anything true of ONE image is in images.yaml — its
# parent, its context, its dockerfile, its smoke ref, its pin home, and the
# prose its job carries. That split is what stops a per-image edit from reaching
# a shared step, which is the drift the 5 copies allowed.
#
# The comments are LOAD-BEARING and are reproduced, not dropped. A generator
# that emits bare YAML would delete the measurements this repository writes
# beside its decisions, and the next reader would restore the free-disk action.
#
# ============================================================================
# IDEMPOTENT AND DETERMINISTIC
# ============================================================================
#
# Same manifest, same output, byte for byte: the images are emitted in document
# order, which is BUILD_ORDER, and nothing reads the clock, the environment or
# the filesystem outside images.yaml and _ctl/lib.sh. Running it twice leaves an
# empty `git diff`, and that is the property to check after any edit here.
#
# Usage: bash _ctl/generate.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

CTL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set before the source line, the way .ci/affected.sh sets it: the git fallback
# in _ctl/lib.sh reads the wrong root when this repository is a submodule
# worktree.
REPO_ROOT="$(cd "$CTL_DIR/.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib.sh
source "$CTL_DIR/lib.sh"

PROVIDER_DIR="$REPO_ROOT/.ci/providers/github"
BUILD_WORKFLOW="$PROVIDER_DIR/build-and-push.yml"
NIGHTLY_WORKFLOW="$PROVIDER_DIR/security-nightly.yml"

# The pinned action refs, spelled once. A bump is 1 edit here and it reaches
# every job, which is the whole reason the jobs stopped being copies.
ACTION_CHECKOUT="actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4"
ACTION_LOGIN="docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9 # v3"
ACTION_BUILD_PUSH="docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8 # v6"

# The gate every step below the filter carries.
BUILD_GATE="\${{ steps.filter.outputs.build == 'true' }}"

# The 2 mode-aware gates. Both OPEN with the filter reference, and that order is
# load-bearing: _ctl/tests/publish-order.test.sh reads the FIRST
# `steps.<id>.outputs.<key>` on an `if:` line as the gate a step carries, and it
# requires every step that publishes, smokes or reads a manifest to be guarded by
# `steps.filter.outputs.build`. `inputs.mode` is not a step output, so it adds a
# condition without moving that reference.
#
# `!= 'rehearsal'` and not `== 'publish'`: on a `push` event there is no input at
# all and `inputs.mode` is the empty string. Written as an equality against
# 'publish', every push to main would take the rehearsal branch and publish
# nothing — the failure would be a workflow that runs green and ships no image.
PUBLISH_GATE="\${{ steps.filter.outputs.build == 'true' && inputs.mode != 'rehearsal' }}"
REHEARSAL_GATE="\${{ steps.filter.outputs.build == 'true' && inputs.mode == 'rehearsal' }}"

# ---------------------------------------------------------------------------
# The manifest, beyond what _ctl/lib.sh already answers.
# ---------------------------------------------------------------------------

# The prose of each job, as a stream of `<<<image/key>>>` blocks. Read once, for
# the reason image_records gives: on the container route each parse is a docker
# run, and this generator asks about 6 images.
_NOTES=""
_NOTES_LOADED=""


# The `$name` below is yq's own variable, bound by `as` inside the expression,
# so it must reach yq unexpanded. The single quotes are the point.
# shellcheck disable=SC2016
function notes_stream() {
  if [[ -n "$_NOTES_LOADED" ]]; then
    printf '%s\n' "$_NOTES"
    return 0
  fi
  local stream status=0
  stream="$(manifest_yq '.images | to_entries | .[] | .key as $name | (.value.notes // {}) | to_entries | .[] | "<<<" + $name + "/" + .key + ">>>" + "\n" + .value')" || status=$?
  if [[ "$status" -ne 0 ]]; then
    log_error "the notes of ${IMAGES_MANIFEST} could not be read"
    return 1
  fi
  _NOTES="$stream"
  _NOTES_LOADED="yes"
  printf '%s\n' "$_NOTES"
}

# note <image> <key> — the note's text, 1 line per line, empty when the image
# declares no note under that key. The trailing blank lines yq leaves between
# blocks are stripped; a blank line INSIDE a note is kept, because cloud's job
# note has one.
function note() {
  local image="$1" key="$2" stream
  stream="$(notes_stream)" || return 1
  printf '%s\n' "$stream" | awk -v want="<<<${image}/${key}>>>" '
    $0 == want { collecting = 1; next }
    /^<<<.*>>>$/ { collecting = 0 }
    collecting { lines[++count] = $0 }
    END {
      while (count > 0 && lines[count] == "") { count-- }
      for (index_ = 1; index_ <= count; index_++) { print lines[index_] }
    }
  '
}

# emit_note <indent> <image> <key> — the note as YAML comment lines. An empty
# line becomes a bare `#`, which is how every multi-paragraph comment in these
# workflows is already written. Emits nothing at all for an absent note.
function emit_note() {
  local indent="$1" image="$2" key="$3" text line
  text="$(note "$image" "$key")" || return 1
  [[ -z "$text" ]] && return 0
  while IFS= read -r line; do
    if [[ -z "$line" ]]; then
      printf '%s#\n' "$indent"
    else
      printf '%s# %s\n' "$indent" "$line"
    fi
  done <<< "$text"
}

# image_children <name> — every image whose parent is <name>, in build order.
function image_children() {
  local name="$1" other
  while IFS= read -r other; do
    [[ "$(image_parent "$other")" == "$name" ]] && printf '%s\n' "$other"
  done < <(image_names)
}

# image_root <name> — the ancestor of <name> that builds FROM ubuntu. An image
# with no parent is its own root. It is the job that owns the short SHA every
# job of the run tags with, which is why the children read `needs.<root>`.
function image_root() {
  local name="$1" parent
  parent="$(image_parent "$name")" || return 1
  if [[ -z "$parent" ]]; then
    printf '%s' "$name"
    return 0
  fi
  image_root "$parent"
}

# image_has_descendants <name> — true when any image has <name> as an ancestor.
function image_has_descendants() {
  local name="$1" other parent
  while IFS= read -r other; do
    [[ "$other" == "$name" ]] && continue
    parent="$other"
    while parent="$(image_parent "$parent")" && [[ -n "$parent" ]]; do
      [[ "$parent" == "$name" ]] && return 0
    done
  done < <(image_names)
  return 1
}

# ---------------------------------------------------------------------------
# The job template.
# ---------------------------------------------------------------------------

# Every `${{ ... }}` and every `$GITHUB_OUTPUT` below belongs to GitHub Actions
# and must reach the workflow file unexpanded, so the single quotes are the
# point rather than an oversight — the shape .ci/smoke.sh uses for the guest
# shell's own `$`.
# shellcheck disable=SC2016
function emit_job() {
  local name="$1" leading_blank="$2"
  local parent context dockerfile smoke_ref root
  parent="$(image_parent "$name")"
  context="$(image_context "$name")"
  dockerfile="$(image_dockerfile "$name")"
  smoke_ref="$(image_smoke_ref "$name")"
  root="$(image_root "$name")"

  # A ROOT image computes the short SHA its own tags carry; a child reads the
  # one its root job published, because every job of a run shares 1 commit.
  local sha_expression
  if [[ -z "$parent" ]]; then
    sha_expression="\${{ steps.sha.outputs.short }}"
  else
    sha_expression="\${{ needs.${root}.outputs.short }}"
  fi

  local has_children=""
  [[ -n "$(image_children "$name")" ]] && has_children="yes"

  # `jobs:` is followed straight by its first key; every job after that is
  # separated from the one above by a blank line.
  [[ -n "$leading_blank" ]] && printf '\n'
  emit_note '  ' "$name" job
  printf '  %s:\n' "$name"
  cat <<'JOB_TIMEOUT'
    # A job with no limit inherits the GitHub default of 360 minutes. arc-build
    # has 6 slots and one build wave takes all of them, so a hung job holds a
    # slot for 6 hours. Every timeout in this file is a CEILING sized on the
    # HOSTED runner; the first run on arc-build is what measures the real
    # runtime, and a resize comes from that measurement rather than from a guess.
    timeout-minutes: 90
JOB_TIMEOUT

  # `needs:` is the graph: the parent, so this layer FROMs what the run just
  # pushed, and the root, for the one short SHA every job tags with. They are
  # the same job for a direct child of the root, and the list carries it once.
  if [[ -n "$parent" ]]; then
    emit_note '    ' "$name" needs
    if [[ "$parent" == "$root" ]]; then
      printf '    needs: [%s]\n' "$root"
    else
      printf '    needs: [%s, %s]\n' "$root" "$parent"
    fi
  fi

  cat <<'JOB_RUNNER'
    runs-on: arc-build
    permissions:
      contents: read
      packages: write
JOB_RUNNER

  # `short` is published by a root job that has descendants to read it; `built`
  # by any job with a direct child, which is what tells that child whether a
  # :<sha> tag exists to FROM.
  local wants_short="" wants_built=""
  if [[ -z "$parent" ]] && image_has_descendants "$name"; then
    wants_short="yes"
  fi
  [[ -n "$has_children" ]] && wants_built="yes"
  if [[ -n "$wants_short" || -n "$wants_built" ]]; then
    printf '    outputs:\n'
    [[ -n "$wants_short" ]] && printf '      short: ${{ steps.sha.outputs.short }}\n'
    if [[ -n "$wants_built" ]]; then
      emit_note '      ' "$name" outputs
      printf '      built: ${{ steps.filter.outputs.build }}\n'
    fi
  fi

  cat <<'JOB_ENV'
    env:
      # The tag the build below LOADS into the local docker image store, and the
      # ref the smoke test then runs. It carries no registry on purpose: nothing
      # can pull it, so a load that did not happen fails the smoke step instead
      # of quietly asserting against the last image that was published.
JOB_ENV
  printf '      SMOKE_REF: %s\n' "$smoke_ref"
  # A job-level key OVERRIDES the workflow-level one for this job only, so the
  # narrower image carries its exception where it applies and the other 4 read
  # the sanctioned set. It is emitted only where the 2 differ: a key repeating
  # the value above it is a second declaration waiting to drift.
  local platforms
  platforms="$(image_platforms "$name")" || return 1
  if [[ "$platforms" != "$SANCTIONED_PLATFORMS" ]]; then
    printf '      # This image publishes a NARROWER set than the sanctioned one, and\n'
    printf '      # images.yaml carries the measurement that justifies it. Never wider:\n'
    printf '      # image_platforms refuses an entry outside SANCTIONED_PLATFORMS.\n'
    printf '      PLATFORMS: %s\n' "$platforms"
  fi
  if [[ -n "$parent" ]]; then
    emit_note '      ' "$name" base_tag
    cat <<'JOB_BASE_TAG'
      # REHEARSAL takes 'latest', and that is a limitation with a name.
      #
      # A rehearsal publishes nothing, so the parent job pushed no :<sha> for
      # this commit and there is nothing for this layer's FROM to resolve.
      # Rehearsal #2 (run 32114973844) is the measurement: base and cloud went
      # green on both platforms, and zephyr and flutter died resolving
      # ghcr.io/gophersys/base:<sha> — a tag that a mode which ships nothing
      # never created.
      #
      # So a rehearsal proves each image's OWN content builds on every sanctioned
      # platform, against the parent that is currently published. It does NOT
      # prove the child-at-NEW-parent seam. That seam is reachable only in
      # publish mode, where it is smoke-gated, or by pushing quarantined tags —
      # which this repository deliberately does not do, for the reason the arm64
      # note at the top of _ctl/tests/publish-order.test.sh gives.
      #
      # GitHub's && / || yield OPERANDS and not booleans, so this reads: when the
      # mode is rehearsal take 'latest' (a non-empty string, therefore the value
      # of the first branch), otherwise fall through to exactly the expression
      # this line carried before rehearsal existed.
JOB_BASE_TAG
    printf "      BASE_TAG: \${{ inputs.mode == 'rehearsal' && 'latest' || (needs.%s.outputs.built == 'true' && needs.%s.outputs.short || 'latest') }}\n" \
      "$parent" "$root"
  fi

  printf '    steps:\n'
  printf '      - uses: %s\n' "$ACTION_CHECKOUT"
  if [[ -z "$parent" ]]; then
    cat <<'JOB_SHA'
      - name: short-sha
        id: sha
        run: echo "short=$(echo ${{ github.sha }} | cut -c1-7)" >> "$GITHUB_OUTPUT"
JOB_SHA
  fi

  cat <<'JOB_SEMVER'
      - name: extract semver tag
        id: semver
        run: |
          if [[ "${GITHUB_REF}" == refs/tags/v* ]]; then
            echo "tag=${GITHUB_REF#refs/tags/}" >> "$GITHUB_OUTPUT"
          else
            echo "tag=" >> "$GITHUB_OUTPUT"
          fi
JOB_SEMVER

  printf '      - name: does this commit change %s\n' "$name"
  emit_note '        ' "$name" filter
  printf '        id: filter\n'
  printf '        run: bash .ci/affected.sh %s >> "$GITHUB_OUTPUT"\n' "$name"

  printf '      - uses: %s\n' "$ACTION_LOGIN"
  printf '        if: %s\n' "$BUILD_GATE"
  cat <<'JOB_LOGIN'
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: keep the BuildKit mirror populated
        # The builder step below boots from a ghcr.io image — see the header of
        # .ci/buildx-node.sh. This step is what makes that true on the day the
        # pin moves; every other run is 1 authenticated read of our registry.
        # It sits after the login because the mirror package is private.
JOB_LOGIN
  printf '        if: %s\n' "$BUILD_GATE"
  printf '        run: bash .ci/mirror-buildkit.sh\n'

  printf '      - name: point buildx at the build nodes\n'
  emit_note '        ' "$name" buildx
  printf '        if: %s\n' "$BUILD_GATE"
  printf '        run: bash .ci/buildx-node.sh\n'

  # An image feeds in the pins of its pin home, the 1 tag it FROMs, or both.
  # Those are 1 rule seen from the 2 ends of the graph: an image takes the pins
  # it reads and the parent it has, and the 2 are independent.
  #
  # The DEFAULT is the rule that stood here before the `pins` key existed: an
  # image with no parent reads versions.env. It is written out rather than left
  # implicit, because a root image declaring `pins` explicitly must produce the
  # same job — the key is an addition to the manifest's vocabulary and not a new
  # requirement on the 2 images that were already correct.
  local pin_home build_args_block
  pin_home="$(image_pins "$name")" || return 1
  if [[ -z "$pin_home" && -z "$parent" ]]; then
    pin_home="versions.env"
  fi

  if [[ -n "$pin_home" ]]; then
    printf '      - name: generate the build args from %s\n' "$pin_home"
    printf '        # The one-home rule reaching CI: one --build-arg per pin line, the same\n'
    printf '        # list `%s/ctl.sh` generates locally. The Dockerfile'"'"'s pin gate fails\n' "$name"
    printf '        # the build naming any pin this step failed to carry.\n'
    printf '        if: %s\n' "$BUILD_GATE"
    cat <<'JOB_VERSIONS_HEAD'
        id: versions
        run: |
          {
            echo 'args<<VERSIONS_EOF'
JOB_VERSIONS_HEAD
    # The pin home is the only variable part of the reader, so it is the only
    # part printf writes. `\$` keeps the sed anchors out of the shell.
    printf "            sed -e 's/#.*\$//' -e 's/[[:space:]]*\$//' -e '/^\$/d' %s\n" "$pin_home"
    cat <<'JOB_VERSIONS_TAIL'
            echo 'VERSIONS_EOF'
          } >> "$GITHUB_OUTPUT"
JOB_VERSIONS_TAIL
  fi

  # A child that also reads a pin home carries BOTH, and the pins go BELOW the
  # tag: the expression expands to a multi-line string after the YAML is parsed,
  # so anything written under it would land inside that expansion.
  build_args_block=""
  if [[ -n "$parent" ]]; then
    build_args_block='          build-args: |
            BASE_TAG=${{ env.BASE_TAG }}'
  fi
  if [[ -n "$pin_home" ]]; then
    if [[ -n "$build_args_block" ]]; then
      build_args_block="${build_args_block}
            \${{ steps.versions.outputs.args }}"
    else
      build_args_block='          build-args: ${{ steps.versions.outputs.args }}'
    fi
  fi

  cat <<'JOB_BUILD_HEAD'
      - name: build the image, load it locally, publish nothing yet
        # The gate has to run before the irreversible action. A push cannot be
        # undone and no job here rolls one back, so a smoke test placed after it
        # reports a broken image but cannot stop one reaching a consumer.
        # buildx loads this build into the local docker image store instead, the
        # step after it asserts the content, and only then does the publish step
        # ship the same build. The second build reads the cache this one writes,
        # so publishing costs a layer copy rather than a rebuild.
        #
        # SMOKE_PLATFORM and not PLATFORMS: `load: true` takes 1 platform, and
        # the arm64 half of the publish below is therefore NOT gated by a smoke
        # run in this phase. The env block at the top of this file states that
        # in full.
JOB_BUILD_HEAD
  printf '        if: %s\n' "$BUILD_GATE"
  printf '        uses: %s\n' "$ACTION_BUILD_PUSH"
  printf '        with:\n'
  printf '          context: %s\n' "$context"
  printf '          file: %s\n' "$dockerfile"
  printf '          platforms: ${{ env.SMOKE_PLATFORM }}\n'
  printf '          push: false\n'
  printf '          load: true\n'
  printf '%s\n' "$build_args_block"
  printf '          tags: ${{ env.SMOKE_REF }}\n'
  printf '          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.OWNER }}/%s-cache\n' "$name"
  printf '          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.OWNER }}/%s-cache,mode=max\n' "$name"

  printf '      - name: smoke test (native amd64)\n'
  emit_note '        ' "$name" smoke
  printf '        if: %s\n' "$BUILD_GATE"
  printf '        run: bash .ci/smoke.sh %s ${{ env.SMOKE_REF }}\n' "$name"

  cat <<'JOB_PUBLISH_HEAD'
      - name: publish the image the smoke test passed
        # The same build definition as the load step above — same context, same
        # build-args — so buildx resolves every amd64 layer from the cache that
        # step wrote and uploads it. It writes no cache of its own for that
        # reason.
        #
        # The platform list is WIDER here than in the gate step: the amd64 leg
        # comes from that cache, and every other leg is built now, on the node
        # buildx appended for it. So this step is the one that runs the arm64
        # build, and an arm64 failure surfaces HERE rather than in the gate.
JOB_PUBLISH_HEAD
  printf '        if: %s\n' "$PUBLISH_GATE"
  printf '        uses: %s\n' "$ACTION_BUILD_PUSH"
  printf '        with:\n'
  printf '          context: %s\n' "$context"
  printf '          file: %s\n' "$dockerfile"
  printf '          platforms: ${{ env.PLATFORMS }}\n'
  printf '          push: true\n'
  printf '%s\n' "$build_args_block"
  printf '          tags: |\n'
  printf '            ${{ env.REGISTRY }}/${{ env.OWNER }}/%s:latest\n' "$name"
  printf '            ${{ env.REGISTRY }}/${{ env.OWNER }}/%s:%s\n' "$name" "$sha_expression"
  printf "            \${{ steps.semver.outputs.tag != '' && format('{0}/{1}/%s:{2}', env.REGISTRY, env.OWNER, steps.semver.outputs.tag) || '' }}\n" "$name"
  printf '          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.OWNER }}/%s-cache\n' "$name"

  cat <<'JOB_REHEARSAL_HEAD'
      - name: rehearsal — build what the publish step would build, ship nothing
        # The step above with `push: false`. Same context, same build-args, same
        # PLATFORMS, same builders — so the arm64 leg is really built, on the
        # arm64 node, and a failure that would have surfaced at publish time
        # surfaces here instead, on a branch, with no tag moved.
        #
        # It carries no `tags:` because it produces no image to name, and no
        # cache-to for the reason the publish step has none: the gate build
        # above is the writer.
JOB_REHEARSAL_HEAD
  printf '        if: %s\n' "$REHEARSAL_GATE"
  printf '        uses: %s\n' "$ACTION_BUILD_PUSH"
  printf '        with:\n'
  printf '          context: %s\n' "$context"
  printf '          file: %s\n' "$dockerfile"
  printf '          platforms: ${{ env.PLATFORMS }}\n'
  printf '          push: false\n'
  printf '%s\n' "$build_args_block"
  printf '          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.OWNER }}/%s-cache\n' "$name"

  cat <<'JOB_VERIFY_HEAD'
      - name: verify the published manifest and every blob it references
        # A push DECLARES a platform; this reads what the registry actually
        # holds. At the SHA tag, never at :latest, so a concurrent run cannot
        # make this describe somebody else's image. It runs only when this job
        # published, because an unbuilt image has no SHA tag for this commit.
        #
        # A rehearsal pushed nothing, so there is no :<sha> of this run to read.
        # Left ungated it would read the tag a PREVIOUS run published and report
        # a verdict about somebody else's build — a green that checked an image
        # this run never made.
        #
        # It also walks every layer of every published platform and asks the
        # registry for 1 byte of each (Range: bytes=0-0). Ledger #118: ghcr.io
        # answered 404 for a layer 4 manifests referenced while HEAD of the same
        # url answered 200, and a manifest-only check stayed green over an image
        # nobody could pull. GITHUB_TOKEN is what that probe reads the private
        # packages with — the same secret this job pushed with.
JOB_VERIFY_HEAD
  printf '        if: %s\n' "$PUBLISH_GATE"
  printf '        env:\n'
  printf '          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n'
  printf '        run: bash ./ctl.sh verify-published %s %s\n' "$name" "$sha_expression"
}

# ---------------------------------------------------------------------------
# The file.
# ---------------------------------------------------------------------------

function emit_build_and_push() {
  local names_text set_phrase count name
  names_text="$(image_names)" || return 1
  set_phrase="$(printf '%s' "$names_text" | tr '\n' '@' | sed -e 's/@$//' -e 's/@/ + /g')"
  count="$(printf '%s\n' "$names_text" | grep -c .)"

  cat <<'FILE_BANNER'
# GENERATED FILE — do not edit it here.
#
#   generator: _ctl/generate.sh
#   manifest:  images.yaml
#
# Every job below is 1 template applied to 1 entry of the manifest. An edit made
# here is lost on the next `bash _ctl/generate.sh`: change the template in the
# generator for anything true of every job, and the image's own entry in the
# manifest for anything true of one. .github/workflows/build-and-push.yml is a
# hand-made copy of this file, and _ctl/tests/platform-policy.test.sh holds the
# 2 byte for byte.

name: build-and-push

FILE_BANNER

  printf '# Publishes the IDP image set (%s)\n' "$set_phrase"
  cat <<'FILE_HEADER_A'
# to the GitHub Container Registry, for every platform the env PLATFORMS key
# names. On semver tag pushes (v*) we also publish a :v<semver> tag.
# mobile and embedded consume base via a BASE_TAG build-arg set to the commit
# short SHA, so the child layer FROMs the freshly pushed parent.
#
# Every job reads back the manifest it just pushed, at the SHA tag it pushed
# rather than at :latest, so a concurrent run cannot make the assertion describe
# somebody else's image.
#
# ============================================================================
# THE RUNNER IS OURS
# ============================================================================
#
# Every job here runs on the `arc-build` pool: the homelab ARC scale set of that
# name, 6 slots on the three 14Gi pve-00 workers, running this repository's own
# `cloud` image (gophersys/infrastructure docs/ci-substrate.md). It costs no
# GitHub Actions minutes, and this repository moved because the account had 195
# of 2,000 minutes left against a $0 budget.
#
# Every job carried a `jlumbroso/free-disk-space` step and none does now. That
# action reclaims ~25-30 GB by deleting the preinstalled SDKs of a GitHub-hosted
# runner, which is a throwaway VM. On this pool the same deletion would strip
# the NODE, and the blast radius is every pod on it. A build pod gets its
# headroom from the `work` volume the scale set sizes instead. Do not add one
# back: _ctl/tests/workflow-yaml.test.sh reads `uses:` through yq, so this
# sentence is safe to write and the step is not.
#
# ============================================================================
# ONLY WHAT CHANGED IS BUILT
# ============================================================================
#
# A warm rebuild of the whole set measured ~35 minutes on every push to main,
# and most pushes to main touch 1 image or none of them. Each job asks
# `.ci/affected.sh <image>` whether this commit changes that image's inputs, and
# gates its build, its smoke, its push and its manifest read on the answer. The
# path table lives in images.yaml, once — read it for what counts as an input,
# and for why a child declares its parent's paths.
#
# Everything builds on workflow_dispatch, on a tag, and whenever a workflow or
# anything under .ci/ changes.
#
# AN UNBUILT IMAGE KEEPS THE :latest IT ALREADY HAS, and publishes no :<sha> tag
# for this commit. A :<sha> tag is therefore not a promise that every image
# carries that sha. That is the point of the mechanism and not a defect of it.
#
# WHAT IS A DEFECT, AND IS KNOWN: the comparison is against `github.event.before`
# — the previous head of main — and NOT against the commit the published image
# was actually built from. Those differ whenever a run does not finish:
#
#   - push A changes base/ and push B lands while A is still building. The
#     concurrency group below QUEUES B, so A runs to the end and publishes.
#     B's range starts at A's head, and B's no-op on base is SAFE for exactly
#     that reason: A finished. This bullet read "A is CANCELLED by B" until the
#     group stopped cancelling, and that is what happened on 2026-08-19 — the
#     rename publish was killed in flight, the successor run compared a range
#     starting at the killed commit, every image read as unaffected, and
#     ghcr.io/gophersys/mobile was never created while 6 badges went green.
#   - a THIRD push while A builds is the hole QUEUEING leaves. GitHub holds at
#     most 1 pending run per group, so push C replaces the pending B, and C's
#     `before` is B's head — the range starts AFTER the changes B carried and
#     nothing ever builds them. Narrower than the old hole, the same shape.
#   - push A's base job FAILS. The next push's range starts at A, so nothing
#     retries it.
#
# In all 3 cases the answer today is to re-run the job, or to dispatch the
# workflow, which builds everything. The durable fix is to diff against the
# revision the registry holds — label each published image with
# org.opencontainers.image.revision and read it back — so the range starts at
# the last SUCCESSFUL build rather than at the last push. That is a separate
# change and it is not made here.
#
# ============================================================================
# THE LAYER CACHE IS IN THE REGISTRY
# ============================================================================
#
# type=gha is the Actions cache service, 10 GB per repository across all scopes,
FILE_HEADER_A

  printf '# which %s images at mode=max cannot fit — the measured hit rate was not worth\n' "$count"
  cat <<'FILE_HEADER_B'
# the quota. type=registry puts each image's cache in its own ghcr package,
# ghcr.io/gophersys/<image>-cache, which the pool can read and write with the
# same GITHUB_TOKEN it already pushes with. Those packages do not exist until
# the first run creates them, so the first build logs a cache-from miss and that
# is expected exactly once per image.
#
# base-runner is retired. All 3 ARC pools run `cloud` now, so nothing pulls the
# image and no job builds it. `runner/` is deleted (D2, 2026-08-18); the CI fold
# it carried is `_delta/components/runner.sh`, which the cloud job builds in.

on:
  push:
    branches: [main]
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      mode:
        description: "publish = build and ship. rehearsal = build everything, ship nothing."
        type: choice
        default: publish
        options:
          - publish
          - rehearsal

# REHEARSAL MODE, and the hole it closes.
#
# The stated risk of a multi-platform publish is that a platform the gate does
# not smoke fails at PUBLISH time — after the merge, on `main`, with :latest
# already moving. Before this input the only way to exercise a branch's real
# build was to publish it, so the branch could not be proven without taking the
# risk it exists to measure.
#
# In rehearsal every job does everything except ship:
#
#   - the gate build and the amd64 smoke run EXACTLY as in publish mode. They
#     are not conditional on the mode at all.
#   - the publish-shaped build runs with the same context, the same build-args
#     and the same per-image PLATFORMS, on the same builders — including the
#     arm64 node for the platforms that need it — with `push: false`.
#   - the manifest read-back is skipped, because nothing was pushed and reading
#     the PREVIOUS :<sha> would report a verdict about somebody else's build.
#
# `inputs.mode` is empty on a `push` event, and empty is not 'rehearsal', so a
# push to main behaves exactly as it did before this input existed. Rehearsal is
# reachable only by dispatching it deliberately.
#
# It is 2 steps and not 1 `push: ${{ ... }}` expression on purpose.
# _ctl/tests/publish-order.test.sh finds a publishing step by the LITERAL line
# `push: true`, and the whole smoke-gates-publish rule rests on that detector:
# an expression there would make every job read as a job that publishes nothing,
# and the rule that guards the irreversible action would pass while checking
# nothing. Both steps sit AFTER the smoke, so the ordering rule holds in either
# mode.

# QUEUE the runs of a ref. A rapid second push waits for the run in flight
# instead of killing it, so 2 expensive image builds still never run in
# parallel and a publish that is half done gets to finish.
#
# It cancelled in progress until 2026-08-19, when that cost the image rename:
# the publish run was killed part way through, and the run that superseded it
# asked .ci/affected.sh about a range starting at the killed push's own head —
# so every image read as unaffected, ghcr.io/gophersys/mobile was never created,
# hardware kept a :latest from before the rename, and 6 green badges said the
# set had published. A push is not an atomic unit of work here: it moves tags,
# and the run that replaces it does not know which ones it moved.
#
# This is a MITIGATION and not the fix. GitHub keeps at most 1 PENDING run per
# group, so a third push replaces the queued second and that push's changes take
# the same hole — see WHAT IS A DEFECT above, and the registry-revision fix it
# defers. _ctl/tests/workflow-yaml.test.sh holds this value and the semantics of
# every other workflow in the repository.
concurrency:
  group: build-and-push-${{ github.ref }}
  cancel-in-progress: false

env:
  REGISTRY: ghcr.io
  OWNER: gophersys
  # The platforms an image of this workflow PUBLISHES by default. This value is
  # SANCTIONED_PLATFORMS in _ctl/lib.sh, written in by the generator, and the
  # verify-published step in each job is what proves the registry agrees. It is
  # not a key to edit here: edit the library and regenerate.
  #
  # A job may carry a PLATFORMS key of its OWN, which overrides this one for that
  # job. It comes from the image's `platforms` key in images.yaml, it may only be
  # NARROWER, and the manifest carries the measurement beside it. mobile is the
  # 1 image that declares one today: Flutter publishes no linux-arm64 SDK.
FILE_HEADER_B

  printf '  PLATFORMS: %s\n' "$SANCTIONED_PLATFORMS"
  cat <<'FILE_HEADER_C'
  # The platform the SMOKE step builds and asserts, and the ONE architecture
  # this workflow gates content on.
  #
  # `load: true` takes 1 platform — buildx writes a manifest LIST for 2 and the
  # docker image store holds a single image — so the gate build names 1, and
  # this is the one the arc-build pool runs NATIVELY. The version checks the
  # Dockerfiles dropped are the reason it has to be native: they cannot run
  # under emulation.
  #
  # SAY IT PLAINLY: the arm64 content of every image is NOT smoke-gated at
  # publish time in this phase. The amd64 smoke gates the publish for both
  # variants, and the arm64 variant ships on the strength of the same build
  # definition, the same pins and the per-download digest comparison. Smoking
  # arm64 out of the registry after the push is the recorded follow-up, and it
  # is a decision about what "publish" means to this repository — read the arm64
  # note at the top of _ctl/tests/publish-order.test.sh before taking it.
  #
  # .ci/smoke.sh reads this same name: it is a choice WITHIN the sanctioned set
  # and never a way around it, so a value outside PLATFORMS fails there.
  SMOKE_PLATFORM: linux/amd64
FILE_HEADER_C
  printf '\njobs:\n'

  local leading_blank=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    emit_job "$name" "$leading_blank"
    leading_blank="yes"
  done <<< "$names_text"
}

# The nightly is HAND-WRITTEN except for 1 line: the image list of the scan
# matrix, which is the image set and nothing else. So this rewrites that line in
# place rather than emitting the file — a generator that owned the whole file
# would have to carry the trivy pin, the waiver rules and the notify job, none
# of which is an image fact.
#
# The match is the whole `image:` line under `matrix:`, which appears once. A
# line-offset edit is what silently drops a neighbour, so the old line is found
# by its own text and replaced by its own text.
function rewrite_nightly_matrix() {
  local names_text list before after
  names_text="$(image_names)" || return 1
  list="$(printf '%s' "$names_text" | tr '\n' '@' | sed -e 's/@$//' -e 's/@/, /g')"

  local matches
  matches="$(grep -c '^        image: \[' "$NIGHTLY_WORKFLOW" || true)"
  if [[ "$matches" != "1" ]]; then
    log_error "${NIGHTLY_WORKFLOW}: found ${matches} scan-matrix image lines, want exactly 1"
    log_error "the generator replaces that line by matching its text; it will not guess at an offset"
    return 1
  fi

  before="$(mktemp)"
  after="$(mktemp)"
  cat "$NIGHTLY_WORKFLOW" > "$before"
  awk -v replacement="        image: [${list}]" '
    /^        image: \[/ { print replacement; next }
    { print }
  ' "$before" > "$after"
  cat "$after" > "$NIGHTLY_WORKFLOW"
  rm -f "$before" "$after"
  log_info "wrote the scan matrix: image: [${list}]"
}

function main() {
  if [[ ! -d "$PROVIDER_DIR" ]]; then
    log_error "the provider directory is absent: ${PROVIDER_DIR}"
    return 1
  fi

  local staging
  staging="$(mktemp)"
  emit_build_and_push > "$staging"
  cat "$staging" > "$BUILD_WORKFLOW"
  rm -f "$staging"
  log_info "wrote ${BUILD_WORKFLOW#"$REPO_ROOT"/}"

  rewrite_nightly_matrix

  log_info "copy both files to .github/workflows/ — platform-policy.test.sh holds the pairs with cmp"
}

main "$@"
