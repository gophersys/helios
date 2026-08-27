#!/usr/bin/env bash
#
# ctl.sh — repo-wide control for gophersys/.devcontainer
#
# Builds, pushes, lists, and validates every image under the repo root.
# Delegates per-image work to <name>/ctl.sh.
#
# Platform policy:
#   - `build`               the sanctioned platform, explicitly (fast dev loop)
#   - `push`                buildx + --push, guarded (see _ctl/lib.sh)
#   - `verify-published`    the published manifest must carry that same set
#
# Usage: ./ctl.sh <command> [args...]
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The push guard lives in _ctl/lib.sh, 1 time only; the logging and the tool
# gate live in _ctl/standard.sh, which that file sources. This script owns the
# repo-wide verbs, which act on the whole set.
#
# This script does NOT call require_buildx_and_platforms, and that is
# deliberate. The guard enforces the platform list of 1 image, and an image is
# free to declare a measured narrower list. `push` delegates to the per-image
# ctl.sh, which calls the guard with its own list.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=_ctl/lib.sh
source "$PROJECT_ROOT/_ctl/lib.sh"

# Dependency order — parents first, and DERIVED. The set is declared in
# images.yaml and nowhere else; the order is the order the manifest writes the
# images in, and image_names refuses a manifest that puts a child above its
# parent. This array was a literal here and a second literal in .ci/ctl.sh, and
# holding the 2 to each other is what validate.yml's agreement step is for.
#
# `base` is the root of the dev-image family; `mobile` and `embedded` layer on
# top of `base`. `embedded` was 2 images — `zephyr` and `zephyr-devbox` on top
# of it — and the fold made the toolchain and the pod box 1 image with 1 pin
# home, whose 2 identities are a mode of its entrypoint. `cloud` is the
# successor image of the consolidation program (ledger #94): the reduced base +
# the CI fold, built FROM ubuntu directly. It is what all 3 ARC pools run.
#
# `base-runner` was here and is RETIRED. The `+ runner` layer existed to make an
# ARC pool image out of `base`; the pools run `cloud` now (gophersys/
# infrastructure #184, all 3 pinned to the cloud digest), so the image has no
# consumer. `runner/` is DELETED (D2, 2026-08-18) — the CI fold lives in `cloud`
# through `_delta/components/runner.sh`, which carries the same 2 downloads.
#
# Filled at SOURCE time, not lazily: _ctl/tests/publish-order.test.sh and
# _ctl/tests/scheduled-workflows.test.sh read this array out of a shell that has
# sourced this file, because the value the shell ends up holding is the value
# the script builds with.
DECLARED_IMAGES=()
_declared_images_text="$(image_names)" || exit 1
while IFS= read -r _image; do
  [[ -z "$_image" ]] && continue
  DECLARED_IMAGES+=("$_image")
done <<< "$_declared_images_text"
unset _declared_images_text

BUILD_ORDER=()
_build_order_text="$(active_image_names)" || exit 1
while IFS= read -r _image; do
  [[ -z "$_image" ]] && continue
  BUILD_ORDER+=("$_image")
done <<< "$_build_order_text"
unset _build_order_text _image

# -------- helpers --------
# Image name -> source directory. 1:1 for every image of the set. The `+ runner`
# variants were the 1 exception — one directory (`runner/`) built
# `<parent>-runner` for every parent, so `base-runner` resolved to `runner` — and
# they went with the directory (D2, 2026-08-18). `runner_parent` and the
# RUNNER_PARENT thread in image_ctl went in the same edit: with no name reaching
# the arm, both were code no invocation could enter.
function image_dir() {
  local name="$1"
  printf '%s/%s' "$PROJECT_ROOT" "$name"
}

function image_ctl() {
  local name="$1"
  shift
  local dir
  dir="$(image_dir "$name")"
  if [[ ! -x "$dir/ctl.sh" ]]; then
    log_error "missing or non-executable: $dir/ctl.sh"
    return 1
  fi
  (cd "$dir" && bash ./ctl.sh "$@")
}

# -------- commands --------
function cmd_build() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh build <image>"
    exit 2
  fi
  shift
  image_ctl "$name" build "$@"
}

function cmd_push() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh push <image>"
    exit 2
  fi
  shift
  image_ctl "$name" push "$@"
}

function cmd_verify_published() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh verify-published <image> [tag]"
    exit 2
  fi
  shift
  image_ctl "$name" verify-published "$@"
}

function cmd_pull() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh pull <image>"
    exit 2
  fi
  shift
  image_ctl "$name" pull "$@"
}

function cmd_inspect() {
  local name="${1:-}"
  if [[ -z "$name" ]]; then
    log_error "usage: ./ctl.sh inspect <image>"
    exit 2
  fi
  shift
  image_ctl "$name" inspect "$@"
}

# base-currency — does the registry still hold the digest UBUNTU_BASE_REF pins?
# The body is require_base_image_current in _ctl/lib.sh, 1 time only. The nightly
# runs this verb, so a moved ubuntu digest turns the scheduled run red.
function cmd_base_currency() {
  require_base_image_current "$@"
}

function cmd_list() {
  local name ref
  printf '%-13s  %s\n' "IMAGE" "REF"
  printf '%-13s  %s\n' "-----" "---"
  for name in "${BUILD_ORDER[@]}"; do
    ref="ghcr.io/gophersys/${name}:latest"
    printf '%-13s  %s\n' "$name" "$ref"
  done
}

# -------- the gate tools (ledger #117) --------
#
# A LINT'S VERDICT IS A FUNCTION OF ITS VERSION, so a gate that judges with
# whatever the machine holds gives an answer about the machine and not about the
# repository. It happened here: `resolve_image_platforms` in _ctl/lib.sh passed
# `ctl.sh validate` on a mac and failed the same verb in CI with SC2119 +
# SC2120 (run 32111944450), because the 2 hosts carried 2 shellchecks. The
# author had every reason to trust the green — same verb, same flags, same
# files — which is what makes this class worse than a check that cannot fail.
#
# GATE_TOOL_PINS is the answer, and it is deliberately SHORT. A tool belongs
# here when the verb's PASS/FAIL depends on that tool's own analysis of this
# repository's content. Both entries also come from versions.env into the
# images, so "the devcontainer ships exactly the pin" is a property of the build
# rather than a sentence in a document.
#
#   <tool>|<the versions.env row that pins it>
GATE_TOOL_PINS=(
  "shellcheck|SHELLCHECK_VERSION"
  "hadolint|HADOLINT_VERSION"
)

# GATE_TOOL_EXEMPT is the other half, and writing it down is the point. A tool
# that is neither pinned nor exempt is silence, and silence is what let
# the shell linter run unpinned for the life of this verb. Asserting every tool
# mechanically would be the opposite error: a pin that cannot change an answer
# is a bump nobody can review and a red nobody can act on.
#
# The test is the SHAPE of the question the verb asks the tool. jq and yq are
# asked "what does this document say", and the document decides that; docker is
# asked to carry a linter, and the tag it carries is the pin.
#
#   <tool>|<why its version cannot change a verdict>
GATE_TOOL_EXEMPT=(
  "jq|parser: validate asks it whether a file parses and what string sits at one key, and the document answers both"
  "yq|parser: same question against images.yaml, and manifest_yq already refuses anything but 4.x or the YQ_VERSION image"
  "docker|transport: it only runs a linter that is already pinned by tag, so it carries a verdict and never renders one"
)

# gate_tool_pin_name <tool> — the versions.env row GATE_TOOL_PINS names for it.
#
# BOTH TABLES ARE READ HERE, and that is what makes them the declaration rather
# than a comment beside one. A tool in the EXEMPT table reaching this function is
# a contradiction — the verb is demanding a version of a tool the repository has
# said cannot need one — and it stops here naming both halves. An unclassified
# tool is the silence the tables exist to break, and it stops here too.
function gate_tool_pin_name() {
  local tool="$1" row
  for row in "${GATE_TOOL_PINS[@]}"; do
    if [[ "${row%%|*}" == "$tool" ]]; then
      printf '%s' "${row#*|}"
      return 0
    fi
  done
  for row in "${GATE_TOOL_EXEMPT[@]}"; do
    if [[ "${row%%|*}" == "$tool" ]]; then
      log_error "${tool} is in GATE_TOOL_EXEMPT — ${row#*|}"
      log_error "so this verb must not demand a version of it: move the row, or drop the demand"
      return 1
    fi
  done
  log_error "${tool} is in neither GATE_TOOL_PINS nor GATE_TOOL_EXEMPT"
  log_error "a tool this verb judges with is pinned, or it says in writing why its version cannot matter"
  return 1
}

# gate_tool_pin <PIN NAME> — the semver versions.env declares for a gate tool.
#
# It FAILS naming the row rather than falling back to whatever the host holds,
# which is how a gate is supposed to lose its input. The reader is
# versions_env_pin in _ctl/lib.sh, 1 time only; the shape check is here because
# what this verb needs is a version to COMPARE, and a row holding `latest` or a
# package name would compare against nothing.
function gate_tool_pin() {
  local name="$1" pin
  pin="$(versions_env_pin "$name")"
  if [[ ! "$pin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "no '${name}=<semver>' in versions.env — the gate has no version to judge with"
    log_error "it reads '${pin:-<absent>}', and a gate that cannot name its version must not render a verdict"
    return 1
  fi
  printf '%s' "$pin"
}

# tool_reported_version <tool> — the first semver-shaped token the tool prints
# about itself, empty when it is not on PATH or reports none.
#
# 2>&1 rather than 2>/dev/null: a tool that cannot report its own version is a
# tool whose output belongs on screen, not in the bin.
function tool_reported_version() {
  local tool="$1" have=""
  if command -v "$tool" >/dev/null 2>&1; then
    have="$("$tool" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" || have=""
  fi
  printf '%s' "$have"
}

# require_tool_at_pin <tool> <pin name> <pin> — the tool on PATH reports exactly
# <pin>, or this fails naming all 4 things an operator needs: the tool, what it
# found, what this repository pins, and where a matching one lives.
#
# There is no container fallback here, and that is a decision rather than an
# omission. hadolint has one because it reads 1 self-contained file per call;
# `shellcheck -x` follows every `source` line relative to the script, so a
# container route would have to mount the whole repository and rewrite every
# path — a SECOND lint mechanism whose agreement with the first nothing checks.
# The devcontainer is the answer this repository already has.
function require_tool_at_pin() {
  local tool="$1" name="$2" pin="$3" have
  have="$(tool_reported_version "$tool")"
  [[ "$have" == "$pin" ]] && return 0
  log_error "${tool} ${have:-none} is on PATH and ${name} in versions.env pins ${pin}"
  log_error "this gate's verdict is a function of that number: a green here at ${have:-another version} says nothing about CI"
  log_error "run this inside the devcontainer, which ships exactly ${pin}, or install that version on this host"
  return 1
}

# The hadolint version versions.env pins. That row is the single source of truth
# for the whole repository: it is the hadolint the images ship, so it is the
# hadolint the gate must judge with. It was read out of the base/Dockerfile ARG
# until that ARG went value-less, and the read FAILED naming the pin rather than
# linting at whatever version the host happened to hold.
function hadolint_pin() {
  local name
  name="$(gate_tool_pin_name hadolint)" || return 1
  gate_tool_pin "$name"
}

# hadolint_resolve <pin> — print HOW to reach that exact version, `host` or
# `container`. Its stdout is captured, so it logs nothing there; log_info writes
# to stdout in this repository and the caller would read the log line as the
# mode. It prints nothing at all and fails when neither route exists, because a
# Dockerfile that no linter read must not report as a Dockerfile that passed.
function hadolint_resolve() {
  local pin="$1" have=""
  have="$(tool_reported_version hadolint)"
  if [[ "$have" == "$pin" ]]; then
    printf 'host'
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    printf 'container'
    return 0
  fi
  log_error "hadolint ${pin} is required and this host has ${have:-none}, with no docker to run the pinned image"
  log_error "run this inside the devcontainer, which ships exactly ${pin}, or install that version"
  return 1
}

# hadolint_at_pin <mode> <pin> <dockerfile>
function hadolint_at_pin() {
  local mode="$1" pin="$2" file="$3"
  case "$mode" in
    host)      hadolint --config "$PROJECT_ROOT/.hadolint.yaml" "$file" ;;
    container) docker run --rm -v "$(dirname "$file"):/w:ro" -v "$PROJECT_ROOT/.hadolint.yaml:/hadolint.yaml:ro" -w /w "hadolint/hadolint:v${pin}" hadolint --config /hadolint.yaml "$(basename "$file")" ;;
    *)         log_error "hadolint_at_pin: unknown mode '${mode}'"; return 1 ;;
  esac
}

# Print every shell script in the repository, 1 per line. Matched by name AND by
# shebang: `_ctl/tests/stubs/docker` is a bash script with no extension, and a
# *.sh glob alone left it linted by nothing while this script claimed to lint
# every shell script.
function shell_scripts() {
  local file first
  while IFS= read -r file; do
    case "$file" in
      *.sh) printf '%s\n' "$file"; continue ;;
    esac
    # No pipe into grep here: with pipefail, grep -q closing the pipe early can
    # make a MATCH read as a failure, which would silently drop the file.
    first="$(head -n 1 "$file")"
    case "$first" in
      '#!'*bash*|'#!'*ksh*|'#!'*/sh|'#!'*'env sh') printf '%s\n' "$file" ;;
    esac
  done < <(find "$PROJECT_ROOT" -type f -not -path '*/.git/*' | sort)
}

# zsh_username_run_references <dockerfile> — every RUN line that reads
# ${USERNAME} or $USERNAME AFTER the file switches SHELL to zsh, as
# `<line number>: <line>`. Prints nothing for a file that never makes that
# switch, and nothing for a reference made BEFORE it.
#
# THE TRAP (ledger #105). zsh sets USERNAME itself: it is a special parameter
# tied to the EFFECTIVE user, and zsh overwrites whatever the environment held
# at startup. Docker does not expand a RUN line — it hands the string to the
# shell — so under `SHELL ["/usr/bin/zsh", ...]` a `chown ${USERNAME}` means the
# user the layer happens to be running as, and NOT `ARG USERNAME=dev`. In a root
# layer it silently means `chown root`.
#
# The failure is silent by construction: the build succeeds, the image ships,
# and the wrong ownership surfaces at RUNTIME in another image. It has already
# happened here. mobile/Dockerfile chowned /opt/flutter and /opt/android-sdk
# through ${USERNAME} from zsh-as-root layers, so both shipped root-owned, and
# `flutter --version` as `dev` exited 128 with "detected dubious ownership in
# repository at '/opt/flutter'" — found by the first smoke run that ever
# executed it, not by a build.
#
# An ENV, a USER or a LABEL line is NOT a reference this reports, and that is
# not an omission: the Dockerfile PARSER expands those, out of the build args,
# and no shell is involved. Only RUN reaches zsh.
#
# THE HOLE, stated rather than left for a reader to find: the trigger is the
# SHELL line in THIS file. mobile and embedded declare no SHELL of their own
# and INHERIT zsh through their FROM, so their RUN layers run under exactly the
# same shell and this reader stays silent on them. Both hardcode
# `dev` today, and each says so in a header comment, so the hole costs nothing
# at the moment — closing it means resolving the FROM graph here, which is a
# design decision and not a widened regex.
function zsh_username_run_references() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    /^[[:space:]]*SHELL[[:space:]].*zsh/ { zsh = 1; in_run = 0; next }
    {
      if (!in_run) {
        if ($0 ~ /^[[:space:]]*RUN[[:space:]]/) { in_run = 1 } else { next }
      }
      # A Dockerfile comment line inside a RUN continuation is stripped by the
      # parser and never reaches the shell, so it is not a reference.
      if (zsh && $0 !~ /^[[:space:]]*#/ &&
          (($0 ~ /\$USERNAME([^A-Za-z0-9_]|$)/) || ($0 ~ /\$\{USERNAME[^A-Za-z0-9_]/))) {
        printf "%d: %s\n", NR, $0
      }
      if ($0 !~ /\\[[:space:]]*$/) { in_run = 0 }
    }
  ' "$file"
}

# Every devcontainer.json of an image directory, 1 per line. Found by the glob
# and not by BUILD_ORDER: a directory outside BUILD_ORDER would otherwise take a
# devcontainer.json with no check at all on the day somebody added one, which is
# what `runner/` would have done for as long as it sat on disk retired.
function devcontainer_files() {
  local file
  for file in "$PROJECT_ROOT"/*/devcontainer.json; do
    [[ -f "$file" ]] && printf '%s\n' "$file"
  done
}

# Hold every devcontainer.json to the 6 properties a consumer depends on. Until
# this pass these files were read by nothing in the repository: no verb, no test
# and no workflow opened one, so a typo in the image ref reached a developer's
# "Reopen in Container" and nowhere earlier.
#
# 4 of the 6 are the contract .claude/rules/00-identity.md states about 1 file —
# it parses, the published ref, the `dev` user (uid 1000, sudo-nopasswd), and
# /workspace, which is Eden's bind-mount convention. The other 2 are SET rules
# that no single file can answer, and the local/CI 1:1 workflow rests on both:
# the image set of images.yaml and the devcontainer set are ONE set, and each
# file opens the image of the directory it sits in. An image with no
# devcontainer.json is an image nobody can open locally; a file that names a
# SIBLING's ref passes the shape rule while handing the developer a container
# that no CI job of that directory ever runs.
#
# postCreateCommand is deliberately NOT a 7th: exactly 1 of the 6 files declares
# it and the other 5 must not, so agreement is the wrong property here. That
# document's dev-in-container section gives the reason per image.
function check_devcontainer_json() {
  local rc=0 file rel name value expected declared found
  local -a files=()
  while IFS= read -r file; do
    files+=("$file")
  done < <(devcontainer_files)

  # Zero matching files is a FAILURE. A glob that stopped matching leaves rc
  # untouched, and this pass would then report OK having opened no file.
  if [[ ${#files[@]} -eq 0 ]]; then
    log_error "no */devcontainer.json found under ${PROJECT_ROOT} — nothing was checked, so nothing is proven"
    return 1
  fi

  # The manifest half of the set equality. The glob answers the other half, and
  # it cannot answer this one: an image that ships without a devcontainer.json
  # is a file the glob never matches, so the pass would report OK about an image
  # a developer has no way to open.
  for name in "${DECLARED_IMAGES[@]}"; do
    if [[ ! -f "$(image_dir "$name")/devcontainer.json" ]]; then
      log_error "${name}/devcontainer.json: absent — ${IMAGES_MANIFEST} declares ${name}, and this is the file that opens it"
      rc=1
    fi
  done

  for file in "${files[@]}"; do
    rel="${file#"$PROJECT_ROOT"/}"
    name="${rel%%/*}"
    log_info "devcontainer: ${rel}"

    # The other half. A file in a directory the manifest does not declare points
    # at a ref nothing here builds or pushes — `runner/` sat retired on disk for
    # months, and a devcontainer.json added to it would have been read by
    # nothing.
    found=""
    for declared in "${DECLARED_IMAGES[@]}"; do
      [[ "$declared" == "$name" ]] && found="yes"
    done
    if [[ -z "$found" ]]; then
      log_error "${rel}: no such image in ${IMAGES_MANIFEST} — declare ${name} there, or delete ${name}/"
      rc=1
    fi

    if ! jq empty "$file"; then
      log_error "${rel}: not parseable JSON"
      rc=1
      continue
    fi

    # -r prints a bare string and `// empty` prints nothing for a null, so an
    # absent property and a wrong one take the same branch and name themselves.
    #
    # The self-reference is an `elif` and not a second `if`: a ref that fails the
    # shape is already refused, and printing both would report 1 defect twice
    # while leaving the reader to work out that the 2 lines are the same file.
    value="$(jq -r '.image // empty' "$file")"
    expected="ghcr.io/gophersys/${name}:latest"
    if [[ ! "$value" =~ ^ghcr\.io/gophersys/[a-z-]+:latest$ ]]; then
      log_error "${rel}: .image is '${value:-<absent>}' — must match ghcr.io/gophersys/<name>:latest"
      rc=1
    elif [[ "$value" != "$expected" ]]; then
      log_error "${rel}: .image is '${value}' — must be '${expected}'"
      rc=1
    fi

    value="$(jq -r '.remoteUser // empty' "$file")"
    if [[ "$value" != "dev" ]]; then
      log_error "${rel}: .remoteUser is '${value:-<absent>}' — must be 'dev'"
      rc=1
    fi

    value="$(jq -r '.workspaceFolder // empty' "$file")"
    if [[ "$value" != "/workspace" ]]; then
      log_error "${rel}: .workspaceFolder is '${value:-<absent>}' — must be '/workspace'"
      rc=1
    fi
  done

  return "$rc"
}

# Test: run every hermetic test file under _ctl/tests/. A suite that finds no
# test file is a FAILURE and not a pass — a glob that matched nothing is the
# exact way a green result can mean nothing was checked.
function cmd_test() {
  local -a files=()
  local f
  for f in "$PROJECT_ROOT"/_ctl/tests/*.test.sh; do
    [[ -f "$f" ]] && files+=("$f")
  done
  if [[ ${#files[@]} -eq 0 ]]; then
    log_error "no test file matched _ctl/tests/*.test.sh — nothing ran, so nothing is proven"
    return 1
  fi

  local rc=0
  for f in "${files[@]}"; do
    log_info "test: ${f#"$PROJECT_ROOT"/}"
    bash "$f" || rc=1
  done

  if [[ $rc -eq 0 ]]; then
    log_info "test: OK (${#files[@]} files)"
  else
    log_error "test: FAILED"
  fi
  return "$rc"
}

# Validate: hold every GATE_TOOL_PINS tool to the version versions.env pins, lint
# every shell script, assert every per-image ctl.sh the manifest names is
# executable, jq every project.json, hold every
# devcontainer.json to its 6 contract properties, hadolint every Dockerfile,
# refuse Dockerfiles that hardcode a semver-shaped version inside a RUN line
# instead of threading an ARG, and refuse a ${USERNAME} that a zsh RUN layer
# would read as the effective user.
function cmd_validate() {
  require_cmd shellcheck jq
  local rc=0
  local name dir script

  # Every shell script in the repository, not a hand-kept list. The list version
  # missed .ci/ctl.sh and .ci/smoke.sh, which no linter ran at all. -x follows
  # the source line, so each dispatcher is checked together with _ctl/lib.sh.
  local -a scripts=()
  while IFS= read -r script; do
    scripts+=("$script")
  done < <(shell_scripts)

  # The shell linter's verdict depends on its version, the way hadolint's does
  # below. 0.9.0 — the version both root images install from the ubuntu archive,
  # measured on ghcr.io/gophersys/cloud:latest as dpkg 0.9.0-1, and therefore the
  # version CI runs — reports SC2119 and SC2120 on a defaulted function argument
  # that a newer host build accepts in silence, so this verb was green on a
  # laptop and red in the pull request for one commit (run 32111944450). A gate
  # whose answer depends on the operator is not a gate.
  #
  # The REFUSAL REPLACES THE LINT, and does not follow it. Linting first and
  # reporting the mismatch afterwards still writes `shellcheck: <file>` lines
  # that a reader takes for a verdict, and the whole defect is that those lines
  # were believed. So a wrong version means no lines at all.
  local shellcheck_pin_name="" shellcheck_version=""
  if ! shellcheck_pin_name="$(gate_tool_pin_name shellcheck)"; then
    rc=1
  elif ! shellcheck_version="$(gate_tool_pin "$shellcheck_pin_name")"; then
    rc=1
  elif ! require_tool_at_pin shellcheck "$shellcheck_pin_name" "$shellcheck_version"; then
    log_error "nothing was linted: a verdict at another version is not this gate's verdict"
    rc=1
  # A lint that matched nothing is not a clean lint. Without this, a glob or a
  # find that stopped matching leaves rc untouched and validate prints OK having
  # read no file at all.
  elif [[ ${#scripts[@]} -eq 0 ]]; then
    log_error "no shell script found under ${PROJECT_ROOT} — nothing was linted, so nothing is proven"
    rc=1
  else
    log_info "shellcheck ${shellcheck_version} (host), pinned by ${shellcheck_pin_name} in versions.env"
    for script in "${scripts[@]}"; do
      log_info "shellcheck: ${script#"$PROJECT_ROOT"/}"
      shellcheck -x -S style "$script" || rc=1
    done
  fi

  for name in "${DECLARED_IMAGES[@]}"; do
    dir="$(image_dir "$name")"

    # A dispatcher's MODE is not something shellcheck can see. It reads the file
    # and says nothing about the executable bit, so a per-image ctl.sh committed
    # 100644 passes every check here and dies in image_ctl instead — which runs
    # AFTER the push. hardware/ctl.sh shipped that way (run 32133161779):
    # :latest and :<sha> were published, then `verify-published` failed on the
    # mode, leaving 2 tags that no verb could read back.
    if [[ ! -x "$dir/ctl.sh" ]]; then
      log_error "${name}/ctl.sh: missing or non-executable — image_ctl refuses it, so every per-image verb of ${name} fails"
      log_error "chmod +x ${name}/ctl.sh — git records the mode, and the sibling dispatchers are all 100755"
      rc=1
    fi

    log_info "jq parse: ${name}/project.json"
    jq empty "$dir/project.json" || rc=1

    if [[ ! -s "$dir/Dockerfile" ]]; then
      log_error "empty or missing Dockerfile: $dir/Dockerfile"
      rc=1
      continue
    fi
    if ! grep -qE '^[[:space:]]*FROM[[:space:]]+' "$dir/Dockerfile"; then
      log_error "Dockerfile has no FROM instruction: $dir/Dockerfile"
      rc=1
    fi

    # Reject semver literals inside RUN lines — every version MUST come
    # from an ARG at the top of the Dockerfile.
    local bad
    bad="$(grep -nE '^[[:space:]]*RUN[[:space:]].*=[0-9]+\.[0-9]+\.[0-9]+' "$dir/Dockerfile" || true)"
    if [[ -n "$bad" ]]; then
      log_error "${name}/Dockerfile: hardcoded version(s) in RUN lines — use ARGs"
      printf '%s\n' "$bad" >&2
      rc=1
    fi

    # The zsh-$USERNAME trap. See zsh_username_run_references: under a zsh
    # SHELL, ${USERNAME} in a RUN is the EFFECTIVE user and never the ARG.
    local trapped
    trapped="$(zsh_username_run_references "$dir/Dockerfile")"
    if [[ -n "$trapped" ]]; then
      log_error "${name}/Dockerfile: \${USERNAME} in a RUN after the SHELL switched to zsh"
      log_error "zsh auto-sets USERNAME to the EFFECTIVE user, so this reads the layer's uid and not the ARG"
      log_error "write the literal 'dev' — the pattern mobile/ and embedded/ document in their headers"
      printf '%s\n' "$trapped" >&2
      rc=1
    fi
  done

  log_info "jq parse: project.json"
  jq empty "$PROJECT_ROOT/project.json" || rc=1

  check_devcontainer_json || rc=1

  # hadolint's verdict depends on its version: 2.15.1 raises DL3064 and DL3066 on
  # Dockerfiles that 2.14.0 passes. A gate whose answer depends on what the
  # operator happened to install is not a gate, so it lints at the version
  # versions.env pins — the version the images themselves ship.
  # A missing tool is a FAILURE, never a skip. This once printed a warning and
  # returned OK, so `validate` reported success while linting no Dockerfile at
  # all — on a host without hadolint it checked nothing and said it passed.
  local hadolint_version="" hadolint_mode=""
  if ! hadolint_version="$(hadolint_pin)"; then
    rc=1
  elif ! hadolint_mode="$(hadolint_resolve "$hadolint_version")"; then
    rc=1
  else
    log_info "hadolint ${hadolint_version} (${hadolint_mode}), pinned by HADOLINT_VERSION in versions.env"
    for name in "${DECLARED_IMAGES[@]}"; do
      dir="$(image_dir "$name")"
      log_info "hadolint: ${name}/Dockerfile"
      hadolint_at_pin "$hadolint_mode" "$hadolint_version" "$dir/Dockerfile" || rc=1
    done
  fi

  if [[ $rc -eq 0 ]]; then
    log_info "validate: OK"
  else
    log_error "validate: FAILED"
  fi
  return "$rc"
}

# `propagate` and `release` were 2 more verbs here, and both are deleted. Each
# one shelled out to $(git rev-parse --show-superproject-working-tree)/.claude/
# scripts/, a layout of the pre-Eden `brain` parent. Eden is the only
# superproject and it has no .claude/scripts/, so both verbs took their own
# error branch at every invocation and told the caller to run them "from within
# brain". Moving the submodule pointer is 1 commit in 1 consumer; the README
# shows it. A verb that cannot succeed is worse than an absent verb, because the
# usage block reads as a list of things this script can do.

# -------- usage --------
function usage() {
  local order
  order="$(IFS=' '; printf '%s' "${BUILD_ORDER[*]}")"
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Images (build order): ${order}

Per-image commands (take <image> as first arg):
  build <image>                    Build for the sanctioned platform (fast dev loop)
  push <image>                     GUARDED buildx build + push
  verify-published <image> [tag]   Assert the published manifest carries exactly
                                   the sanctioned platform set
  pull <image>                     docker pull ghcr.io/gophersys/<image>:latest
  inspect <image>                  docker image inspect ghcr.io/gophersys/<image>:latest

Repo-wide commands:
  base-currency [reference]        Assert the registry still holds the digest
                                   UBUNTU_BASE_REF pins (default ubuntu:24.04)
  list                             Print managed image refs
  validate                         the gate tools at their versions.env pins,
                                   shellcheck, per-image ctl.sh executability,
                                   jq, devcontainer.json contract, hadolint,
                                   ARG-discipline checks, the zsh-\$USERNAME trap
  test                             Run every _ctl/tests/*.test.sh
  help                             Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)              cmd_build             "$@" ;;
    push)               cmd_push              "$@" ;;
    verify-published)   cmd_verify_published  "$@" ;;
    pull)               cmd_pull              "$@" ;;
    inspect)            cmd_inspect           "$@" ;;
    base-currency)      cmd_base_currency     "$@" ;;
    list)               cmd_list              "$@" ;;
    validate)           cmd_validate          "$@" ;;
    test)               cmd_test              "$@" ;;
    help|"")            usage ;;
    *)                  log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
