#!/usr/bin/env bash
#
# .ci/ctl.sh — orchestration-layer CI for gophersys/libs.
#
# This is the PROVIDER-NEUTRAL CI layer (the cictl contract). The three CI tiers
# (pr / merge / nightly) each invoke one or more of THESE verbs, identically
# whether run locally or on a remote provider. The .github/workflows/*.yml are
# GENERATED from .ci/ci.contract.yaml by `cictl generate`; never hand-edit them —
# `cictl drift` is the CI-on-CI gate that enforces it.
#
# Tier verbs map to the per-lib SDLC gate (ADR-0020, libs/go/_ctl/lib.sh):
#   affected-gate-fast       → for each affected project: ctl.sh phase-gate implementation
#                              (build + strict lint/hnslint + apidiff-no-break + vet + unit) — no
#                              real substrate; the minutes lane on every push.
#   affected-gate-substrate  → for each affected project: the integration/lifecycle/load lanes on
#                              the REAL docker+k3d+kind host (never mocked) — the merge lane.
#   gate-all                 → for each affected project: ctl.sh phase-gate all (1→4) — the nightly
#                              exhaustive lane.
#   updatability             → cictl updatability: the pinned-version audit (ADR-0021 generalised).
#
set -Eeuo pipefail
# INERT for both `$( … )` this file contains today, and kept anyway. A command-substitution
# subshell does not inherit errexit by default; this option gives it errexit — but only where
# errexit is live to begin with. Both substitutions here sit on the LEFT of `||`, which
# suppresses errexit for that whole command, and bash propagates the suppression into the
# subshell, where it overrides this option. Measured, bash 5.2.21:
#
#   x="$(false; echo late)"            without: x=late rc=0     with: rc=1
#   x="$(false; echo late)" || s=$?    without: s=0 x=late       with: s=0 x=late   ← identical
#
# So this line covers a future NEUTRAL substitution somewhere else in this file, and nothing
# that is in it now. What keeps today's two status reads honest is that each holds exactly ONE
# command — the invariant require_single_command_status_reads checks and the comment at the
# call site states. Nor does it cover process substitution: `< <(f)` still discards f's status,
# and THAT — not this default — was the swallow the affected set was fixed for.
shopt -s inherit_errexit
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel)"

# Diff base for affected detection. CI sets NX_BASE per tier; locally it defaults
# to origin/main.
NX_BASE="${NX_BASE:-origin/main}"

function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

# require_cmd <tool>… — each tool must be an EXECUTABLE FILE this shell will really run.
#
# `command -v` answers 0 for a shell FUNCTION, so it could not establish that, and the affected
# set below reads a status through `$( … ) || status=$?`, where errexit is suppressed for
# whatever sits on the left. An external command has exactly one status there; a function has a
# BODY, and only its last command's status survives. Measured on the unmodified file with a
# `cictl()` whose first command failed and whose last succeeded — injected by `export -f` and
# again by BASH_ENV — the tier printed git's own `fatal:` and still exited 0 with "all 1
# affected project(s) green". `type -t` names what the next call will actually run, so the
# premise the call site states is now asserted rather than assumed.
#
# Both arms exit 127: from the tier's side the required tool is not there to be run, which is
# the value rule 20 states for that, and one value keeps the tier's contract readable.
function require_cmd() {
  local missing=() shadowed=()
  local cmd kind
  for cmd in "$@"; do
    kind="$(type -t "$cmd")" || kind=""
    case "$kind" in
      file) ;;
      "")   missing+=("$cmd") ;;
      *)    shadowed+=("$cmd is a shell $kind") ;;
    esac
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
  if [[ ${#shadowed[@]} -gt 0 ]]; then
    log_error "required tool(s) shadowed in this shell: ${shadowed[*]}; the gate reads the TOOL's exit status, and a shell body drops every status but its last"
    exit 127
  fi
}

function on_exit() {
  local rc=$?
  return "$rc"
}
trap on_exit EXIT

# run_phase_gate_over_affected <selector> — for each affected project, run its
# per-lib gate. A run with no affected project is a CLEAN no-op success (an empty
# diff must not fail the tier).
#
# $1 selects what to run:
#   implementation | testing | qa | architecture | all → ctl.sh phase-gate <$1>
#   substrate                                           → the real-substrate lanes
#                                                         (integration + lifecycle + load)
function run_phase_gate_over_affected() {
  local selector="$1"
  local -a projects=()
  local listing="" status=0

  # The affected set is produced HERE, in the tier's own shell — the changed project roots,
  # one per line, repo-relative, via cictl (the nx-free, uniform "what changed"). It is NOT
  # produced by a helper this function reads through a subshell, because both ways of reading
  # a FUNCTION through one throw its status away, and that status is the only byte that tells
  # a cictl which FAILED from a cictl that ran and found nothing:
  #
  #   mapfile -t projects < <(producer)   a process substitution is a subshell, so
  #                                       require_cmd's `exit 127` — and equally a bad base
  #                                       ref, a shallow clone, a git fault — killed the
  #                                       subshell alone. mapfile read an empty stream and
  #                                       the tier reported a clean no-op over libraries it
  #                                       had never looked at.
  #   listing="$(producer)" || status=$?  a FUNCTION on the left of `||` runs with errexit
  #                                       disabled for its WHOLE body, so only its LAST
  #                                       command's status becomes the function's. The same
  #                                       swallow, one function inward, and silent until the
  #                                       body grows a second command.
  #
  # The `|| status=$?` below is NOT that shape: ONE external command sits on the left, so `$?`
  # is exactly that command's status and there is no earlier command whose status could be
  # dropped. Both halves of that are checked rather than trusted — require_cmd rejects a cictl
  # that is a shell function (a body there would drop statuses exactly as the producer did),
  # and require_single_command_status_reads fails `validate` if this line ever grows a second
  # command. Keep it one command — a second one goes on its own line ABOVE, in this shell,
  # where errexit reads it. require_cmd runs here too, so an absent tool exits 127 (rule 20)
  # from the tier verb itself.
  require_cmd cictl
  listing="$(cictl affected -C "$REPO_ROOT" --base "$NX_BASE")" || status=$?
  if [[ "$status" -ne 0 ]]; then
    # A cictl that fails silently prints nothing of its own, so without this line the whole CI
    # log of a red job is the tier's announcement: nothing naming the tool, nothing saying the
    # affected set was never known.
    log_error "cictl affected failed (exit $status) for base '${NX_BASE}'; the affected set is unknown, so nothing was gated"
    return "$status"
  fi
  # `<<<""` yields ONE empty element, which would take a genuinely empty affected set out of
  # the no-op arm below.
  [[ -z "$listing" ]] || mapfile -t projects <<<"$listing"

  if [[ ${#projects[@]} -eq 0 ]]; then
    log_info "no affected projects for base '${NX_BASE}' — clean no-op"
    return 0
  fi

  local ran=0 proj proj_dir
  for proj in "${projects[@]}"; do
    [[ -z "$proj" ]] && continue
    # A LIBRARY is go/<name> or typescript/<name>. Nothing else is.
    #
    # `cictl affected` reports any directory holding both ctl.sh and project.json.
    # The repository root holds both, and so does .ci/, so a change to either
    # selected a "project" whose ctl.sh has no phase-gate — the gate then failed
    # with "unknown command: 'phase-gate'". Naming each offender in turn is a fix
    # that has to be repeated, so the rule is structural instead: gate what is a
    # library, not everything that looks like a project.
    #
    # go/_ctl holds the shared verb bodies the per-library ctl.sh files dispatch
    # to. It is not a library either.
    case "$proj" in
      go/_ctl)                  log_info "skipping $proj: shared verb bodies, not a library"; continue ;;
      go/*|typescript/*)        ;;
      *)                        log_info "skipping $proj: not a library (libraries are go/<name> or typescript/<name>)"; continue ;;
    esac

    proj_dir="$REPO_ROOT/$proj"
    if [[ ! -f "$proj_dir/ctl.sh" ]]; then
      log_error "'$proj' is a library path but has no ctl.sh"
      exit 1
    fi

    ran=$((ran + 1))
    case "$selector" in
      substrate)
        log_info "gate(substrate): $proj → integration + lifecycle + load (REAL docker+k3d+kind)"
        ( cd "$proj_dir" && bash ./ctl.sh integration && bash ./ctl.sh lifecycle && bash ./ctl.sh load )
        ;;
      *)
        log_info "gate: $proj → phase-gate $selector"
        ( cd "$proj_dir" && bash ./ctl.sh phase-gate "$selector" )
        ;;
    esac
  done

  if [[ "$ran" -eq 0 ]]; then
    log_info "affected projects had no gateable ctl.sh — clean no-op"
    return 0
  fi
  log_success "gate ($selector): all $ran affected project(s) green"
}

# ── tier verbs (uniform local & remote; referenced by the cictl contract) ────
function cmd_affected_gate_fast() {
  log_info "affected-gate-fast: phase-gate implementation over affected projects (base=${NX_BASE})"
  run_phase_gate_over_affected implementation
}

function cmd_affected_gate_substrate() {
  log_info "affected-gate-substrate: real-substrate lanes over affected projects (base=${NX_BASE})"
  run_phase_gate_over_affected substrate
}

function cmd_gate_all() {
  log_info "gate-all: phase-gate all (1→4) over affected projects (base=${NX_BASE})"
  run_phase_gate_over_affected all
}

function cmd_updatability() {
  require_cmd cictl
  log_info "updatability: pinned-version matrix from the contract's toolMatrix.sources"
  cictl updatability -C "$REPO_ROOT" "$@"
}

# ci-drift — re-render the workflows from the contract and fail if the committed
# files differ. This is the gate that makes the "DO NOT EDIT" banner true: without
# it, a hand-edit to a generated workflow is invisible and the contract silently
# stops being the source of truth.
#
# It runs in the pr tier so a hand-edit fails the pull request that introduced it,
# rather than surfacing later as an unexplained difference between repos.
function cmd_ci_drift() {
  require_cmd cictl
  log_info "ci-drift: generated workflows match .ci/ci.contract.yaml"
  cictl drift -C "$REPO_ROOT" "$@"
}

# ── existing meta verbs (preserved) ──────────────────────────────────────────

# require_single_command_status_reads <file> — the one-command invariant, checked.
#
# Every `x="$( … )" || rc=$?` in this file is safe for ONE reason: the substitution holds a
# single command, so `$?` is that command's status. Grow one to two and the first command's
# failure is gone — measured end to end, a `git fetch` added ahead of cictl printed its own
# `fatal: 'origin' does not appear to be a git repository` and the tier still exited 0 with
# "all 1 affected project(s) green", which is the original false green. Nothing else catches
# it: `shopt -s inherit_errexit` is overridden in that position (see the header) and
# `shellcheck -o all` reports no SC231x for it. So the invariant lived only in a comment, in a
# file whose comments about that exact line have now been wrong three times.
#
# What it reads: every non-comment line that takes a status with `|| <var>=$?`. Each must be
# one assignment of one substitution holding one command — no `;`, no `|`, no `&&`, no
# trailing `&`. A redirection (`2>&1`) is not a second command, which is why a bare `&` is not
# the test. A status read in any OTHER shape fails here too, loudly: this check must never go
# quiet because the code moved out from under it.
#
# What it does NOT read: process substitution (`< <(f)`, of which this file has none); a
# substitution whose status is masked in a condition rather than read (shellcheck's SC2312
# lane, 0 in this file); a function on the left of `||`, whose whole body loses its statuses
# (SC2310, which .ci/ctl_test.sh switches on for this file); and any file but this one. The
# same shape lives in the repository-level ctl.sh (cmd_validate's jq read, and its _usage_verbs
# read, which IS a function on the left of `||`), in go/_ctl/lib.sh, typescript/_ctl/lib.sh and
# templates/_ctl/template.sh — none of which this change owns.
function require_single_command_status_reads() {
  local file="$1"
  local line body number=0 reads=0 flaws=0
  local status_read='\|\|[[:space:]]*[A-Za-z_][A-Za-z_0-9]*=\$\?'
  local one_command='^[[:space:]]*[A-Za-z_][A-Za-z_0-9]*="\$\(([^()]*)\)"[[:space:]]*\|\|[[:space:]]*[A-Za-z_][A-Za-z_0-9]*=\$\?[[:space:]]*(#.*)?$'
  local sequenced='[;|]|&&|&[[:space:]]*$'
  # `|| [[ -n "$line" ]]`: read reports EOF for a last line with no trailing newline, and that
  # line would otherwise be the one place a status read could hide from this check.
  while IFS= read -r line || [[ -n "$line" ]]; do
    number=$((number + 1))
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ $status_read ]] || continue
    reads=$((reads + 1))
    if [[ ! "$line" =~ $one_command ]]; then
      log_error "$file:$number takes a status from a shape this check cannot read as one substitution holding one command; restore the shape or re-read this check:$line"
      flaws=$((flaws + 1))
      continue
    fi
    body="${BASH_REMATCH[1]}"
    if [[ "$body" =~ $sequenced ]]; then
      log_error "$file:$number holds more than one command inside \$( … ), so only the LAST one's status can reach \$?:$line"
      flaws=$((flaws + 1))
    fi
  done < "$file"
  # A floor, as _floor_of_one in the repository-level ctl.sh: 0 reads found and 0 reads checked
  # are the same green, so a rename or a refactor that puts this file's status reads out of
  # this check's reach fails here instead of reporting a clean sheet over nothing.
  if [[ "$reads" -eq 0 ]]; then
    log_error "no '|| <var>=\$?' status read found in $file; reading them is all this check does, so finding none means it read nothing"
    return 1
  fi
  [[ "$flaws" -eq 0 ]] || return 1
  log_info "status reads in ${file#"$REPO_ROOT"/}: $reads, each holding one command"
}

function cmd_validate() {
  # Before the delegation, which is the twenty-minute half: the invariant that makes this
  # file's two status reads safe, checked in a verb the pr and push tiers already run.
  require_single_command_status_reads "$PROJECT_ROOT/ctl.sh"
  bash "$REPO_ROOT/ctl.sh" validate "$@"
}

function cmd_status() {
  bash "$REPO_ROOT/ctl.sh" status "$@"
}

function cmd_release_check() {
  require_cmd git
  # Same class as the affected set above: a `git status` that FAILS prints nothing on stdout,
  # so `[[ -n "$(git … status --porcelain)" ]]` read it as a clean tree and waved a dirty one
  # through. Measured with `status.showUntrackedFiles` set to a bad value — status exits 128
  # printing nothing, while rev-parse and fetch stay healthy, so nothing downstream catches it
  # and release-check printed "ready" over an uncommitted file. Read the status, then the
  # output. (A corrupt .git/index does NOT show it: fetch fails too, and the verb dies there.)
  local dirty="" status=0
  dirty="$(git -C "$REPO_ROOT" status --porcelain)" || status=$?
  if [[ "$status" -ne 0 ]]; then
    log_error "git status failed (exit $status) in $REPO_ROOT; the tree's cleanliness is unknown, so nothing is being released"
    return "$status"
  fi
  if [[ -n "$dirty" ]]; then
    log_error "working tree dirty; commit or stash before release"
    git -C "$REPO_ROOT" status --short >&2
    return 1
  fi
  local branch
  branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
  if [[ "$branch" != "main" ]]; then
    log_error "not on main (on '$branch')"
    return 1
  fi
  git -C "$REPO_ROOT" fetch --quiet origin
  local head remote
  head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  remote="$(git -C "$REPO_ROOT" rev-parse origin/main)"
  if [[ "$head" != "$remote" ]]; then
    log_error "main ($head) != origin/main ($remote); pull/push before release"
    return 1
  fi
  log_success "release-check: ready (HEAD $head)"
}

# ── conformance hidden lister ────────────────────────────────────────────────
# __verbs is the hidden command `cictl conformance` invokes to learn which verbs
# this dispatcher defines. It MUST list every tier-referenced verb. Keep it in
# sync with the case arms below (the conformance gate fails loudly if a tier
# references a verb absent here).
function cmd_list_verbs() {
  cat <<'EOF'
affected-gate-fast
affected-gate-substrate
gate-all
updatability
ci-drift
validate
status
release-check
EOF
}

function usage() {
  cat <<EOF
Usage: bash .ci/ctl.sh <command> [args]

Tier verbs (referenced by .ci/ci.contract.yaml; uniform local & remote):
  affected-gate-fast       phase-gate implementation over affected projects (pr tier)
  affected-gate-substrate  integration/lifecycle/load on real docker+k3d+kind (merge tier)
  gate-all                 phase-gate all (1->4) over affected projects (nightly tier)
  updatability             pinned-version matrix from the contract toolMatrix (nightly tier)
  ci-drift                 generated workflows still match the contract (pr tier)

Meta verbs:
  validate       Checks this file's status reads, then delegates to repo-level ctl.sh validate
  status         Delegates to repo-level ctl.sh status
  release-check  Preflight for brain's release.sh
  help           Show this message
EOF
}

function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    affected-gate-fast)       cmd_affected_gate_fast       "$@" ;;
    affected-gate-substrate)  cmd_affected_gate_substrate  "$@" ;;
    gate-all)                 cmd_gate_all                 "$@" ;;
    updatability)             cmd_updatability             "$@" ;;
    ci-drift)                 cmd_ci_drift                 "$@" ;;
    validate)                 cmd_validate                 "$@" ;;
    status)                   cmd_status                   "$@" ;;
    release-check)            cmd_release_check            "$@" ;;
    __verbs)                  cmd_list_verbs               "$@" ;;
    help|"")                  usage ;;
    *) log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
