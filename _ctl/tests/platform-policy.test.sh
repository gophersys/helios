#!/usr/bin/env bash
#
# _ctl/tests/platform-policy.test.sh — the static half of the sanctioned-platform
# policy.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and
# on a CI runner. The 1 exception is the YAML parser `manifest_yq` resolves,
# which is yq on PATH inside the devcontainer.
#
# What it encodes:
#
#   - 2 platforms are sanctioned for a published image, the library declares the
#     set once, and every other place on the build path either names a member of
#     it or names no platform at all;
#   - an IMAGE may publish a NARROWER set than the sanctioned one, declared in
#     images.yaml and measured. It may never publish a wider one, and a manifest
#     that tries is refused NAMING the image and the platform;
#   - the generated workflow repeats the sanctioned set at the workflow level and
#     carries a job-level override ONLY where the image is narrower.
#
# The sanctioned value is written here as a literal ON PURPOSE, and so is the
# per-image table below it. A test that reads the value out of the
# implementation and then compares it to itself agrees with any value the
# implementation happens to hold, including a wrong one. The literals are the
# policy; _ctl/lib.sh and images.yaml are the implementation of it.
#
# WHAT CHANGED WHEN THE SET WIDENED, because the shape of 2 rules inverted
# rather than their values:
#
#   - "no linux/arm64 on the build path" is GONE. arm64 is sanctioned, the
#     library writes it, both workflow copies carry it and .ci/buildx-node.sh
#     switches on it — 6 legitimate hits in the library alone. The rule that
#     replaces it forbids an UNSANCTIONED platform token, and it is driven from
#     SANCTIONED_PLATFORMS so it needs no edit the next time the set moves.
#     linux/riscv64 is the tripwire the reader is watched firing on.
#   - "every PLATFORMS key equals the sanctioned set" is now a SUBSET rule at the
#     job level, and equality at the workflow level. Equality everywhere would
#     fail mobile's measured amd64-only override, which is correct; a bare
#     subset rule everywhere would pass a workflow-level key that quietly
#     narrowed the whole publish. Each occurrence is keyed by its scope, because
#     the 2 keys emitted the SAME check name before and a failure could not say
#     which line it was about.
#
# Usage: bash _ctl/tests/platform-policy.test.sh
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

TEST_NAME="platform-policy.test.sh"

LIBRARY="_ctl/lib.sh"

# The policy. 2 platforms, and their names.
SANCTIONED="linux/amd64,linux/arm64"

# What each image PUBLISHES, as a literal table, for the same reason SANCTIONED
# is a literal: reading images.yaml here would make this file agree with any
# manifest, including one that had silently dropped an architecture.
#
# 5 of the 6 declare no `platforms` key and take the sanctioned set. mobile
# declares linux/amd64 and the manifest carries the measurement beside the key:
# Flutter publishes no linux-arm64 SDK at any version.
#
# `embedded` takes the sanctioned set, and it is the row that replaced 2. As
# `zephyr-devbox` the pod half had a NARROWING measurement available to it —
# every node of the cluster it ran on is amd64 — and it never took the key
# either. The fold settles the question rather than inheriting it: the same
# image is what a developer opens locally in its default mode, so linux/arm64 is
# a platform this image is CONSUMED on and not merely one it could be built for.
#
# `hardware` takes the sanctioned set, and that is a MEASURED answer rather than
# the default falling through unexamined. The 4 packages its whole reason to
# exist installs — kicad, kicad-symbols, kicad-footprints, kicad-packages3d —
# were read on Launchpad at the pinned major and are Published for BOTH
# ubuntu/noble/amd64 and ubuntu/noble/arm64; the citation sits beside
# KICAD_PPA_VERSION in versions.env. An image whose upstream served 1
# architecture would need a narrowing key with its own measurement, the way
# mobile has one.
#
# `ui` takes the sanctioned set for the same KIND of reason, and it is the row
# that was nearly written the other way: the plan, research-ui's ADR-0003 risk
# R3 and that repository's own ci/Dockerfile all state that Chrome is published
# for amd64 alone, and a narrowing key written on that premise would have
# narrowed this image on a reason that is FALSE. Google's stable component
# declares `Architectures: amd64 arm64` and carries google-chrome-stable at ONE
# version, 151.0.7922.137-1, in both indexes (read 2026-08-18; the record with
# its byte counts sits beside the images.yaml entry). So the absence of a key is
# a measurement here, and this row is the literal that says so.
IMAGE_PLATFORM_TABLE=(
  "base|linux/amd64,linux/arm64"
  "mobile|linux/amd64"
  "embedded|linux/amd64,linux/arm64"
  "cloud|linux/amd64,linux/arm64"
  "hardware|linux/amd64,linux/arm64"
  "ui|linux/amd64,linux/arm64"
)

# The 1 image the table says is narrower than the sanctioned set. It is named
# here so the LIVENESS clause below can check that the table still holds an
# exception at all — a table in which every row equalled the sanctioned set
# would satisfy the per-image rule while proving nothing about the mechanism
# that makes an exception possible.
NARROWER_IMAGE="mobile"

# The build path, named file by file. This is deliberately NOT a repository-wide
# grep. A document must stay free to say the words "linux/riscv64" while it
# explains why riscv64 is not sanctioned, and a repository-wide grep would
# forbid the explanation along with the defect. The Dockerfiles are absent for a
# different kind of reason: their TARGETPLATFORM case blocks are how a binary
# install resolves its architecture, and an arm for a platform outside the set
# is dead code rather than a publish. The `_delta/components/*.sh` install
# scripts are absent for that same reason.
#
# .ci/buildx-node.sh is IN the list, and it was not before. It reads
# SANCTIONED_PLATFORMS and appends the arm64 builder node when that list names
# linux/arm64, so it is a file that acts on a platform name and it belongs under
# the rule that governs them.
#
# THE PER-IMAGE HALF OF THIS LIST IS BOUND TO THE MANIFEST, and it was not. The
# ui image landed with its `ctl.sh` and its `project.json` in NEITHER this list
# nor any other, so both files could name linux/riscv64 and every check in this
# file would stay green — coverage that shrinks with no red, which is the
# failure IMAGE_PLATFORM_TABLE already carries a set-equality clause against.
# This is the third time the class has bitten (GOVERNED_DOCKERFILES,
# IMAGE_PLATFORM_TABLE, here), so the clause below closes it here too, in both
# directions.
#
# The per-image half is every entry spelled `<name>/ctl.sh` or
# `<name>/project.json` whose `<name>` begins with neither `.` nor `_`. That is
# not a fudge: .claude/rules/00-identity.md says the leading underscore is what
# marks `_ctl/` as not an image directory, and `.ci/` is the CI layer by the same
# convention. `embedded/embedded-entrypoint.sh` is deliberately outside the
# pair — it is a script an image COPYs in, not one of the 2 files every image
# directory carries — and the clause therefore says nothing about it. It is
# still IN the list, and it earned its place twice over with the fold: it is PID
# 1 of both modes now, and the mode dispatch it gained is the 1 place in the
# tree where a platform name would decide which identity a container runs as.
BUILD_PATH_FILES=(
  "_ctl/lib.sh"
  "ctl.sh"
  "base/ctl.sh"
  "cloud/ctl.sh"
  "mobile/ctl.sh"
  "embedded/ctl.sh"
  "embedded/embedded-entrypoint.sh"
  "hardware/ctl.sh"
  "ui/ctl.sh"
  ".ci/ctl.sh"
  ".ci/smoke.sh"
  ".ci/buildx-node.sh"
  ".github/workflows/build-and-push.yml"
  ".github/workflows/validate.yml"
  ".ci/providers/github/build-and-push.yml"
  "project.json"
  "base/project.json"
  "cloud/project.json"
  "mobile/project.json"
  "embedded/project.json"
  "hardware/project.json"
  "ui/project.json"
  ".ci/project.json"
)

# The 2 files every image directory of the manifest carries, and the 2 this list
# owes set equality on. Literals, because the per-image file rule is a rule of
# .claude/rules/00-identity.md and not something a reader of the tree measures.
IMAGE_BUILD_PATH_FILE_NAMES=(
  "ctl.sh"
  "project.json"
)

# The retired variable name. It is a NAME rule and not a platform rule: both
# names hold the same string, so a caller that still sets the old one gets the
# right platform by accident and only a name check finds the missed rename.
RETIRED_PLATFORM_VARIABLE="MULTI_ARCH_PLATFORMS"

# The tripwire platform. Not sanctioned, no digest row answers for it, and no
# Dockerfile case arm has an arm for it — so a build path that names it would
# reach every download with an empty digest.
TRIPWIRE_PLATFORM="linux/riscv64"

WORKFLOW="$REPO_ROOT/.github/workflows/build-and-push.yml"

# The provider directory is the SOURCE OF TRUTH for the GitHub provider, and
# .github/workflows/ holds a copy of each of its files (.ci/providers/README.md).
# Every file here is compared with its twin, and not build-and-push.yml alone:
# that narrow rule left a second provider file with no check at all the day one
# was added, which is how the first copy became an old copy listing 3 images.
#
# The direction is provider -> workflow. .github/workflows/ may hold a file that
# the provider directory does not — validate.yml and pr-review.yml are both
# provider-native and have no source-of-truth copy — so the reverse direction is
# not a rule here.
PROVIDER_DIRECTORY=".ci/providers/github"
WORKFLOW_DIRECTORY=".github/workflows"

# What that directory holds, as a literal. The comparison below is discovered by
# a glob, so a file added tomorrow is compared with no edit here — and a glob
# that matched nothing would leave a green result that read no file at all. This
# list is what makes the set non-empty, and it is the 1 line to edit when a
# provider file is added or renamed.
EXPECTED_PROVIDER_FILES=(
  "build-and-push.yml"
  "security-nightly.yml"
  "weekly-bumps.yml"
)

# The fixtures that prove the manifest rule fires, in both directions.
PLATFORM_FIXTURES="$TESTS_DIR/fixtures/platform-policy"
FIXTURE_UNSANCTIONED="$PLATFORM_FIXTURES/unsanctioned-platform.yaml"
FIXTURE_NARROWER="$PLATFORM_FIXTURES/sanctioned-narrower.yaml"

# The image and the platform the stimulus fixture holds. The refusal must name
# BOTH — a guard that says "invalid manifest" sends the reader back to read the
# file by hand.
FIXTURE_IMAGE="mobile"
FIXTURE_BAD_PLATFORM="linux/riscv64"

# ---------------------------------------------------------------------------
# The readers.
# ---------------------------------------------------------------------------

# joined <element...> — 1 element per line, sorted, for a set comparison.
function joined() {
  printf '%s\n' "$@" | sort
}

# platform_tokens <file> — every `linux/<arch>` token the file writes, as
# `<line number>:<token>`, 1 per line.
#
# The token shape is buildx's own: lowercase alphanumerics, with an optional
# `/vN` variant arm. It deliberately does NOT take a trailing `.`, because
# _ctl/lib.sh ends a sentence with the word linux/arm64 and a reader that swept
# the period into the token would report a platform nobody wrote.
function platform_tokens() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  grep -noE 'linux/[a-z0-9]+(/v[0-9]+)?' "$file" || true
}

# unsanctioned_platform_tokens <label> <file> — every token of that file whose
# platform is NOT in SANCTIONED, as `<label>:<line>:<token>`.
#
# The membership test is the library's own shape — a comma-fenced substring —
# and not a substring of the raw list. `linux/arm` is a prefix of `linux/arm64`,
# so a naive reader would call an unsanctioned 32-bit arm platform sanctioned.
function unsanctioned_platform_tokens() {
  local label="$1" file="$2"
  local record line token out=""
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    line="${record%%:*}"
    token="${record#*:}"
    if [[ ",${SANCTIONED}," == *",${token},"* ]]; then
      continue
    fi
    out="${out:+${out}
}${label}:${line}:${token}"
  done <<< "$(platform_tokens "$file")"
  printf '%s' "$out"
}

# workflow_platform_keys <file> — every `PLATFORMS*` key of a workflow, as
#
#   <scope>|<line number>|<key>|<value>
#
# where <scope> is the job the key sits in, or `workflow` for the top-level env
# block. The scope is what makes each check name UNIQUE. Before it, both keys
# of this file emitted `workflow_PLATFORMS_is_the_sanctioned_set`, the harness
# printed that name twice, and a failure could not say which of the 2 lines it
# was about — 2 checks wearing 1 name is 1 check a reader can act on.
function workflow_platform_keys() {
  local file="$1"
  awk '
    /^jobs:[[:space:]]*$/ { in_jobs = 1; job = ""; next }
    in_jobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {
      job = $0
      sub(/^[[:space:]]+/, "", job)
      sub(/:[[:space:]]*$/, "", job)
      next
    }
    /^[[:space:]]+PLATFORMS[A-Z_]*:/ {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      key = line
      sub(/:.*$/, "", key)
      value = line
      sub(/^[^:]*:[[:space:]]*/, "", value)
      sub(/[[:space:]]+$/, "", value)
      scope = (in_jobs && job != "") ? job : "workflow"
      printf "%s|%d|%s|%s\n", scope, NR, key, value
    }
  ' "$file"
}

# IMAGE_PLATFORMS_OUTPUT / IMAGE_PLATFORMS_STATUS — set by the probe below.
IMAGE_PLATFORMS_OUTPUT=""
IMAGE_PLATFORMS_STATUS=0

# run_image_platforms <repository root> <image> — ask the real library what that
# image publishes, against a repository root of the caller's choosing.
#
# No seam is added to the library for this and none is needed: manifest_yq reads
# "${REPO_ROOT}/images.yaml", so a directory holding that name and a versions.env
# is the whole world the reader looks at. That is the shape run_order_guard in
# images-manifest.test.sh already uses.
#
# stderr is folded into stdout because the refusal IS the answer here: a rule
# that refused and printed nothing readable is a rule this file must fail on.
function run_image_platforms() {
  local root="$1" name="$2"
  local library_path
  # Resolved BEFORE the assignment prefix below, and not inside its argument
  # list: the prefix rebinds REPO_ROOT for the forked shell only, so a
  # "$REPO_ROOT/..." written there would still expand to THIS shell's value.
  # SC2097 and SC2098 report exactly that, and a reader cannot tell the intent
  # from the accident. (A comment whose first word after the hash is the linter's
  # own name is read as a DIRECTIVE, which is how this line first failed the gate.)
  library_path="$REPO_ROOT/$LIBRARY"
  IMAGE_PLATFORMS_STATUS=0
  IMAGE_PLATFORMS_OUTPUT="$(PROJECT_ROOT="$root" REPO_ROOT="$root" bash -c '
    source "$1"
    image_platforms "$2"
  ' probe "$library_path" "$name" 2>&1)" || IMAGE_PLATFORMS_STATUS=$?
}

# stage_manifest_root <manifest> — a repository root whose images.yaml is that
# file. COPIES and not symlinks: nothing here writes, but a staging helper that
# can reach the real tree is 1 edit away from one that does.
function stage_manifest_root() {
  local manifest="$1" root
  root="$(mktemp -d)"
  cp "$manifest" "${root}/images.yaml"
  cp "$REPO_ROOT/versions.env" "${root}/versions.env"
  printf '%s' "$root"
}

printf '=== RUN  %s\n' "$TEST_NAME"

# -------- 1. the library declares the sanctioned set --------
# Read the VALUE, not the text of the line. A declaration is only worth
# anything if the running shell ends up holding it.
lib_probe_status=0
lib_probe_value=""
lib_probe_value="$(PROJECT_ROOT="$REPO_ROOT" bash -c '
  source "$1"
  printf "%s" "${SANCTIONED_PLATFORMS:-<undeclared>}"
' probe "$REPO_ROOT/_ctl/lib.sh")" || lib_probe_status=$?

if [[ "$lib_probe_status" -ne 0 ]]; then
  fail_check "lib_declares_SANCTIONED_PLATFORMS" \
    "sourcing _ctl/lib.sh exited ${lib_probe_status}; its stderr is above" \
    "partial value read: ${lib_probe_value}"
else
  assert_equal "lib_declares_SANCTIONED_PLATFORMS" "$SANCTIONED" "$lib_probe_value" \
    "_ctl/lib.sh must declare SANCTIONED_PLATFORMS as the single source of truth"
fi

# -------- 2. each image publishes the set the policy gives it --------
#
# ============================================================================
# 2a. THE TABLE IS THE WHOLE IMAGE SET — THE CLAUSE THAT WAS MISSING
# ============================================================================
#
# The per-image rule below loops the TABLE. So an image with no row here is
# asserted by NOTHING, and the file stays green while its coverage shrinks —
# which is not a hypothetical: `hardware` landed with the manifest, the loop
# read 5 rows, and nothing in this file could say that a 6th image had started
# publishing to 2 architectures unwatched.
#
# The remedy is NOT to loop the manifest. That would make this file agree with
# any manifest, a wrong one included, which is the reason the table is a literal
# at all. The remedy is SET EQUALITY between the literal and the manifest, in
# BOTH directions — the pattern publish-order.test.sh applies to
# PUBLISHED_IMAGES, and for the same reason:
#
#   an image in the manifest and not in this table   publishes with no platform
#                                                    policy watching it
#   a row here naming no image of the manifest       is a policy this file goes
#                                                    on asserting about an image
#                                                    that was deleted
#
# Adding an image is therefore an images.yaml entry plus a row here, in 1
# change, and neither half can be forgotten quietly.
#
# WHICH READER. manifest_yq from _ctl/lib.sh — its RESOLUTION only, with the
# EXPRESSION written here, exactly as publish-order.test.sh does it. The
# accessor `image_names` is deliberately not used: it also enforces the
# topological order of the document, so a manifest that wrote a child above its
# parent would fail HERE, naming a platform rule, about an ordering defect that
# images-manifest.test.sh owns and reports properly.
manifest_status=0
manifest_names=""
manifest_names="$(manifest_yq '.images | keys | .[]' 2>&1)" || manifest_status=$?

# The liveness clause comes first, because the equality below reads this value:
# an unreadable manifest would otherwise compare the table against an empty set
# and report the WRONG defect — 6 rows that name no image — while the real fault
# is that nothing could open the file.
if [[ "$manifest_status" -eq 0 && -n "$manifest_names" ]]; then
  pass_check "the_image_manifest_is_readable"
else
  fail_check "the_image_manifest_is_readable" \
    "reading the image keys of ${IMAGES_MANIFEST} exited ${manifest_status}" \
    "it printed:" "${manifest_names:-<nothing>}" \
    "the manifest is the ONE declaration of the image set, so the equality below cannot be" \
    "answered without it — and an empty set would agree with a repository that has no images"
fi

if [[ "$manifest_status" -ne 0 || -z "$manifest_names" ]]; then
  fail_check "the_platform_table_names_exactly_the_manifest_images" \
    "unreadable: ${IMAGES_MANIFEST}"
else
  table_names=""
  for row in "${IMAGE_PLATFORM_TABLE[@]}"; do
    table_names="${table_names:+${table_names}
}${row%%|*}"
  done
  assert_equal "the_platform_table_names_exactly_the_manifest_images" \
    "$(sort <<< "$manifest_names")" \
    "$(sort <<< "$table_names")" \
    "${IMAGES_MANIFEST} is the ONE declaration of the image set, and IMAGE_PLATFORM_TABLE is" \
    "the hand-kept policy it owes set equality to — edit both in the same change" \
    "the per-image rule below loops the TABLE, so an image missing from it is an image whose" \
    "published architectures this file asserts nothing about, silently and in green"
fi

# THE LIVENESS CLAUSE first. If every row of the table equalled the sanctioned
# set, the rule below would pass over a manifest in which the `platforms`
# mechanism had stopped being read at all — every image would take the default
# and every row would agree.
narrower_rows=""
for row in "${IMAGE_PLATFORM_TABLE[@]}"; do
  [[ "${row#*|}" == "$SANCTIONED" ]] && continue
  narrower_rows="${narrower_rows:+${narrower_rows}
}${row}"
done
if [[ -n "$narrower_rows" ]]; then
  pass_check "the_image_platform_table_still_holds_a_narrower_exception"
else
  fail_check "the_image_platform_table_still_holds_a_narrower_exception" \
    "every row of IMAGE_PLATFORM_TABLE equals the sanctioned set" \
    "the per-image rule below would then be satisfied by a library that had stopped" \
    "reading the manifest's platforms key at all — every image would take the default" \
    "and every comparison would agree"
fi

assert_contains "the_narrower_exception_is_${NARROWER_IMAGE}" \
  "$narrower_rows" "${NARROWER_IMAGE}|" \
  "the measurement that justifies the exception lives beside the key in images.yaml," \
  "and this name is what ties that measurement to this policy file"

for row in "${IMAGE_PLATFORM_TABLE[@]}"; do
  image_name="${row%%|*}"
  want_platforms="${row#*|}"
  run_image_platforms "$REPO_ROOT" "$image_name"
  if [[ "$IMAGE_PLATFORMS_STATUS" -ne 0 ]]; then
    fail_check "image_platforms_${image_name}_is_its_declared_set" \
      "image_platforms ${image_name} exited ${IMAGE_PLATFORMS_STATUS}" \
      "want: ${want_platforms}" \
      "it printed:" "${IMAGE_PLATFORMS_OUTPUT:-<nothing>}"
  else
    assert_equal "image_platforms_${image_name}_is_its_declared_set" \
      "$want_platforms" "$IMAGE_PLATFORMS_OUTPUT" \
      "an image publishes the sanctioned set unless images.yaml declares a measured" \
      "narrower one; this table is the policy and images.yaml is the implementation"
  fi
done

# -------- 2b. a manifest may NARROW the set and may never widen it --------
# THE RULE IS WATCHED FIRING, ON A FIXTURE, IN BOTH DIRECTIONS. A rule that has
# only ever seen the correct manifest has never been observed to fail, and a
# rule that refused every declared `platforms` key would make mobile's correct
# amd64-only row a broken manifest forever.
missing_fixtures=""
for fixture in "$FIXTURE_UNSANCTIONED" "$FIXTURE_NARROWER"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_the_platform_fixtures_exist" \
    "the fixtures this rule is proven with are absent:" "$missing_fixtures"
  fail_check "a_manifest_platform_outside_the_sanctioned_set_is_refused" "no fixture to feed it"
  fail_check "counter_stimulus_a_narrower_manifest_set_is_accepted" "no fixture to feed it"
else
  pass_check "counter_stimulus_the_platform_fixtures_exist"

  staged_root="$(stage_manifest_root "$FIXTURE_UNSANCTIONED")"
  run_image_platforms "$staged_root" "$FIXTURE_IMAGE"
  rm -rf "$staged_root"
  if [[ "$IMAGE_PLATFORMS_STATUS" -eq 0 ]]; then
    fail_check "a_manifest_platform_outside_the_sanctioned_set_is_refused" \
      "want: a non-zero exit status naming '${FIXTURE_IMAGE}' and '${FIXTURE_BAD_PLATFORM}'" \
      "got:  0 — the manifest widened the policy and nothing said so" \
      "it printed:" "${IMAGE_PLATFORMS_OUTPUT:-<nothing>}" \
      "a manifest that could widen the sanctioned set would BE the policy"
  elif ! grep -qF -- "$FIXTURE_IMAGE" <<< "$IMAGE_PLATFORMS_OUTPUT"; then
    fail_check "a_manifest_platform_outside_the_sanctioned_set_is_refused" \
      "it exited ${IMAGE_PLATFORMS_STATUS} and never named the image '${FIXTURE_IMAGE}'" \
      "output was:" "$IMAGE_PLATFORMS_OUTPUT"
  elif ! grep -qF -- "$FIXTURE_BAD_PLATFORM" <<< "$IMAGE_PLATFORMS_OUTPUT"; then
    fail_check "a_manifest_platform_outside_the_sanctioned_set_is_refused" \
      "it exited ${IMAGE_PLATFORMS_STATUS} and never named the platform '${FIXTURE_BAD_PLATFORM}'" \
      "output was:" "$IMAGE_PLATFORMS_OUTPUT"
  else
    pass_check "a_manifest_platform_outside_the_sanctioned_set_is_refused"
  fi

  staged_root="$(stage_manifest_root "$FIXTURE_NARROWER")"
  run_image_platforms "$staged_root" "$FIXTURE_IMAGE"
  rm -rf "$staged_root"
  if [[ "$IMAGE_PLATFORMS_STATUS" -ne 0 ]]; then
    fail_check "counter_stimulus_a_narrower_manifest_set_is_accepted" \
      "the same image declaring linux/amd64 alone exited ${IMAGE_PLATFORMS_STATUS}" \
      "output was:" "$IMAGE_PLATFORMS_OUTPUT" \
      "a rule that refuses every declared platforms key makes mobile's correct row" \
      "a broken manifest forever, and the stimulus above would pass on it"
  else
    assert_equal "counter_stimulus_a_narrower_manifest_set_is_accepted" \
      "linux/amd64" "$IMAGE_PLATFORMS_OUTPUT"
  fi
fi

# -------- 3. every PLATFORMS* key of the workflow, keyed by its scope --------
platform_keys=""
platform_keys="$(workflow_platform_keys "$WORKFLOW")"

if [[ -z "$platform_keys" ]]; then
  # No key found means the test is reading the wrong file or the wrong shape.
  # That is a failure, never a silent pass over an empty set.
  fail_check "workflow_declares_at_least_one_PLATFORMS_key" \
    "no PLATFORMS key found in ${WORKFLOW}" \
    "the reader keys each one by the job it sits in, so a shape change here" \
    "would leave every rule below passing over an empty set"
else
  pass_check "workflow_declares_at_least_one_PLATFORMS_key"

  workflow_level_values=""
  job_level_scopes=""
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    scope="$(cut -d'|' -f1 <<< "$record")"
    line_number="$(cut -d'|' -f2 <<< "$record")"
    key="$(cut -d'|' -f3 <<< "$record")"
    value="$(cut -d'|' -f4 <<< "$record")"

    if [[ "$scope" == "workflow" ]]; then
      workflow_level_values="${workflow_level_values:+${workflow_level_values}
}${value}"
      # The workflow-level key is SANCTIONED_PLATFORMS written in by the
      # generator, so it is held to EQUALITY. A subset rule here would pass a
      # key that quietly narrowed the whole publish to 1 architecture.
      assert_equal "workflow_${key}_at_the_workflow_level_is_exactly_the_sanctioned_set" \
        "$SANCTIONED" "$value" \
        "in ${WORKFLOW}:${line_number}" \
        "edit SANCTIONED_PLATFORMS in _ctl/lib.sh and regenerate; this key is not a home"
      continue
    fi

    job_level_scopes="${job_level_scopes:+${job_level_scopes}
}${scope}"
    # A job-level key is an image's own NARROWER set. Every entry must still be
    # sanctioned, and the list must not be the sanctioned set itself: a key that
    # repeats the value above it is a second declaration waiting to drift.
    outside=""
    IFS=',' read -r -a job_platforms <<< "$value"
    for platform in ${job_platforms[@]+"${job_platforms[@]}"}; do
      if [[ ",${SANCTIONED}," != *",${platform},"* ]]; then
        outside="${outside:+${outside} }${platform}"
      fi
    done
    if [[ -n "$outside" ]]; then
      fail_check "workflow_${key}_in_job_${scope}_is_within_the_sanctioned_set" \
        "these entries are outside the sanctioned set ${SANCTIONED}:" "$outside" \
        "in ${WORKFLOW}:${line_number}, value '${value}'" \
        "a job may NARROW what it publishes; it may never widen the policy"
    elif [[ "$value" == "$SANCTIONED" ]]; then
      fail_check "workflow_${key}_in_job_${scope}_is_within_the_sanctioned_set" \
        "the job-level key repeats the workflow-level value: ${value}" \
        "in ${WORKFLOW}:${line_number}" \
        "the generator emits a job-level key only where the 2 differ; a key that repeats" \
        "the one above it is a second declaration waiting to drift"
    else
      pass_check "workflow_${key}_in_job_${scope}_is_within_the_sanctioned_set"
    fi
  done <<< "$platform_keys"

  assert_equal "the_workflow_declares_exactly_one_workflow_level_PLATFORMS_key" \
    "$SANCTIONED" "$workflow_level_values" \
    "more than 1 line here means 2 workflow-level declarations, and the second wins silently"

  assert_equal "the_only_job_with_a_job_level_PLATFORMS_key_is_${NARROWER_IMAGE}" \
    "$(joined "$NARROWER_IMAGE")" \
    "$(printf '%s\n' "$job_level_scopes" | awk 'NF' | sort)" \
    "the generator emits a job-level key only for an image whose set differs from the" \
    "sanctioned one, and images.yaml declares exactly 1 such image today" \
    "a new name here is either a new measured exception — which needs its row in" \
    "IMAGE_PLATFORM_TABLE and in images.yaml — or a hand edit of a generated file"
fi

# -------- 4. EVERY provider copy is byte-identical to its workflow --------
# The 2 build-and-push.yml files drifted in commit d9089b2, which added 5
# `timeout-minutes: 90` blocks to the workflow and to neither copy of the
# provider file, while .claude/rules/00-identity.md called them identical byte
# for byte. Nothing checked it, so nothing said so.
#
# The rule now covers every file of the provider directory rather than that 1
# pair. The narrow version had the same hole one level up: a second provider
# file got no check at all on the day it was added, and .ci/providers/README.md
# said so in prose — "a second provider file added here gets no such check until
# you add 1 for it". A rule that has to be extended by hand for each new file is
# a rule that will not be.
provider_files=""
for path in "$REPO_ROOT/$PROVIDER_DIRECTORY"/*; do
  [[ -f "$path" ]] || continue
  provider_files="${provider_files:+${provider_files}
}$(basename "$path")"
done

assert_equal "the_provider_directory_holds_the_expected_files" \
  "$(joined "${EXPECTED_PROVIDER_FILES[@]}")" \
  "$(printf '%s\n' "$provider_files" | sort)" \
  "either a provider file was added, renamed or deleted — and this list is what you edit —" \
  "or the glob in this test stopped matching, which would make the comparison below" \
  "pass over an empty set of files"

if [[ -z "$provider_files" ]]; then
  fail_check "the_provider_directory_holds_at_least_one_file" \
    "no file under ${PROVIDER_DIRECTORY}" \
    "the comparison below reads that set, so an empty one checks nothing"
else
  pass_check "the_provider_directory_holds_at_least_one_file"
fi

while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  provider_path="$REPO_ROOT/$PROVIDER_DIRECTORY/$name"
  workflow_path="$REPO_ROOT/$WORKFLOW_DIRECTORY/$name"
  check_name="provider_copy_of_${name}_is_byte_identical_to_the_workflow"

  if [[ ! -f "$workflow_path" ]]; then
    fail_check "$check_name" \
      "${PROVIDER_DIRECTORY}/${name} has no twin at ${WORKFLOW_DIRECTORY}/${name}" \
      "the provider directory is the source of truth and the provider reads the other path," \
      "so a file that exists only here is a workflow that never runs"
    continue
  fi

  cmp_status=0
  cmp_message=""
  cmp_message="$(cmp "$provider_path" "$workflow_path" 2>&1)" || cmp_status=$?
  if [[ "$cmp_status" -eq 0 ]]; then
    pass_check "$check_name"
  else
    diff_status=0
    diff_text=""
    diff_text="$(diff -u "$provider_path" "$workflow_path")" || diff_status=$?
    fail_check "$check_name" \
      "cmp exited ${cmp_status}: ${cmp_message}" \
      "diff exited ${diff_status}; the drift is:" \
      "$diff_text"
  fi
done <<< "$provider_files"

# -------- 5. no UNSANCTIONED platform token on the named build path --------
missing_files=""
for relative in "${BUILD_PATH_FILES[@]}"; do
  if [[ ! -f "$REPO_ROOT/$relative" ]]; then
    missing_files="${missing_files:+${missing_files}
}${relative}"
  fi
done
if [[ -n "$missing_files" ]]; then
  fail_check "every_named_build_path_file_exists" \
    "the file list in this test is stale; these are named but absent:" \
    "$missing_files"
else
  pass_check "every_named_build_path_file_exists"
fi

# The other direction, and the one that was silent: the file above answers "is
# every named file there" and nothing answered "is every image's pair named".
# See the note at BUILD_PATH_FILES — an image whose ctl.sh and project.json are
# in no list is an image whose build path this whole section reads past.
if [[ "$manifest_status" -ne 0 || -z "$manifest_names" ]]; then
  fail_check "the_build_path_names_the_pair_of_every_manifest_image" \
    "unreadable: ${IMAGES_MANIFEST}"
else
  wanted_pairs=""
  while IFS= read -r image_name; do
    [[ -z "$image_name" ]] && continue
    for pair_file in "${IMAGE_BUILD_PATH_FILE_NAMES[@]}"; do
      wanted_pairs="${wanted_pairs:+${wanted_pairs}
}${image_name}/${pair_file}"
    done
  done <<< "$manifest_names"

  # Every entry of the list that CLAIMS to be an image's own file. `.ci/` and
  # `_ctl/` are excluded by the convention that names them, and a root-level
  # `ctl.sh` has no directory to name an image with.
  listed_pairs=""
  for relative in "${BUILD_PATH_FILES[@]}"; do
    case "$relative" in
      */*/*) continue ;;
      .*|_*) continue ;;
      */ctl.sh|*/project.json) ;;
      *) continue ;;
    esac
    listed_pairs="${listed_pairs:+${listed_pairs}
}${relative}"
  done

  assert_equal "the_build_path_names_the_pair_of_every_manifest_image" \
    "$(sort <<< "$wanted_pairs")" \
    "$(sort <<< "$listed_pairs")" \
    "${IMAGES_MANIFEST} is the ONE declaration of the image set, and every image directory" \
    "carries ctl.sh + project.json by the per-image file rule of .claude/rules/00-identity.md" \
    "an image whose 2 files are in no list is an image that may name any platform it likes," \
    "silently and in green — and a listed pair naming no image of the manifest is a rule" \
    "this file goes on asserting about a directory that was deleted"
fi

# THE READER IS WATCHED FIRING FIRST, on a file written for the purpose. The
# real tree is expected to be clean, so a reader that had stopped matching would
# report the same empty result as a tree that is correct — the difference is
# invisible without a stimulus.
probe_file="$(mktemp)"
{
  printf 'PLATFORMS="linux/amd64,linux/arm64"\n'
  printf 'EXTRA="%s"\n' "$TRIPWIRE_PLATFORM"
  printf 'VARIANT="linux/arm/v7"\n'
  printf 'PREFIX="linux/arm"\n'
  printf '# a sentence that ends on the word linux/arm64.\n'
} > "$probe_file"
probe_hits="$(unsanctioned_platform_tokens "probe" "$probe_file")"
rm -f "$probe_file"

probe_reported_unsanctioned=1
for probe_token in "$TRIPWIRE_PLATFORM" "linux/arm/v7" "linux/arm"; do
  grep -q ":${probe_token}\$" <<< "$probe_hits" || probe_reported_unsanctioned=0
done
probe_reported_sanctioned=0
for probe_token in "linux/amd64" "linux/arm64"; do
  grep -q ":${probe_token}\$" <<< "$probe_hits" && probe_reported_sanctioned=1
done

if [[ "$probe_reported_unsanctioned" -eq 1 && "$probe_reported_sanctioned" -eq 0 ]]; then
  pass_check "counter_stimulus_the_platform_token_reader_reports_only_unsanctioned_tokens"
else
  fail_check "counter_stimulus_the_platform_token_reader_reports_only_unsanctioned_tokens" \
    "a file holding linux/amd64, linux/arm64, ${TRIPWIRE_PLATFORM}, linux/arm/v7 and linux/arm" \
    "must report the last 3 and neither of the first 2; it reported:" \
    "${probe_hits:-<nothing>}" \
    "the bare linux/arm is in the stimulus because it is a PREFIX of linux/arm64, so a" \
    "substring membership test calls an unsanctioned 32-bit arm platform sanctioned" \
    "the trailing sentence is there because _ctl/lib.sh ends one on 'linux/arm64.', and a" \
    "reader that swept the period into the token would report a platform nobody wrote"
fi

hits=""
for relative in "${BUILD_PATH_FILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  file_hits="$(unsanctioned_platform_tokens "$relative" "$REPO_ROOT/$relative")"
  [[ -z "$file_hits" ]] && continue
  hits="${hits:+${hits}
}${file_hits}"
done

if [[ -z "$hits" ]]; then
  pass_check "no_unsanctioned_platform_token_on_the_named_build_path"
else
  fail_check "no_unsanctioned_platform_token_on_the_named_build_path" \
    "these files name a platform outside the sanctioned set ${SANCTIONED}:" \
    "$hits" \
    "the rule is membership of SANCTIONED_PLATFORMS and not a deny-list, so it needs" \
    "no edit here when the set moves — widen the library, with a consumer you measured," \
    "and every digest row and case arm that the new platform costs"
fi

retired_hits=""
for relative in "${BUILD_PATH_FILES[@]}"; do
  [[ -f "$REPO_ROOT/$relative" ]] || continue
  file_hits=""
  hit_status=0
  file_hits="$(grep -nF -- "$RETIRED_PLATFORM_VARIABLE" "$REPO_ROOT/$relative")" || hit_status=$?
  [[ "$hit_status" -eq 0 ]] || continue
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    retired_hits="${retired_hits:+${retired_hits}
}${relative}:${hit}"
  done <<< "$file_hits"
done

if [[ -z "$retired_hits" ]]; then
  pass_check "no_${RETIRED_PLATFORM_VARIABLE}_on_the_named_build_path"
else
  fail_check "no_${RETIRED_PLATFORM_VARIABLE}_on_the_named_build_path" \
    "'${RETIRED_PLATFORM_VARIABLE}' still appears on the build path:" \
    "$retired_hits" \
    "both names hold the same string, so a missed rename gets the right platform by" \
    "accident and only this name check finds it"
fi

# -------- 6. the base image does not pin a build platform in its FROM --------
# `FROM --platform=${BUILDPLATFORM:-linux/amd64} ubuntu:24.04` is the mechanical
# cause of the mislabelled arm64 image the set once carried: it pins the
# userland to the BUILD host's architecture while buildx labels the result with
# the TARGET platform. With arm64 sanctioned again this line is the difference
# between a native arm64 image and an amd64 userland wearing an arm64 label, so
# the rule matters MORE now than it did while the set held 1 platform.
from_hits=""
from_status=0
from_hits="$(grep -nE '^[[:space:]]*FROM[[:space:]]+--platform=' "$REPO_ROOT/base/Dockerfile")" || from_status=$?
if [[ "$from_status" -ne 0 ]]; then
  pass_check "base_Dockerfile_FROM_pins_no_platform"
else
  fail_check "base_Dockerfile_FROM_pins_no_platform" \
    "base/Dockerfile still pins a platform on a FROM line:" \
    "$from_hits" \
    "want: FROM ubuntu:24.04"
fi

test_summary "$TEST_NAME"
