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

function on_exit() {
  local rc=$?
  return "$rc"
}
trap on_exit EXIT

# ── affected-projects helper ─────────────────────────────────────────────────
# affected_projects prints the changed project roots (one per line, repo-relative)
# via cictl — the nx-free, uniform "what changed". A project is a dir with both
# ctl.sh and project.json.
function affected_projects() {
  require_cmd cictl
  cictl affected -C "$REPO_ROOT" --base "$NX_BASE"
}

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
  mapfile -t projects < <(affected_projects)

  if [[ ${#projects[@]} -eq 0 ]]; then
    log_info "no affected projects for base '${NX_BASE}' — clean no-op"
    return 0
  fi

  local ran=0 proj proj_dir
  for proj in "${projects[@]}"; do
    [[ -z "$proj" ]] && continue
    proj_dir="$REPO_ROOT/$proj"
    if [[ ! -f "$proj_dir/ctl.sh" ]]; then
      log_warn "skipping '$proj': no ctl.sh (not a gateable project)"
      continue
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
function cmd_validate() {
  bash "$REPO_ROOT/ctl.sh" validate "$@"
}

function cmd_status() {
  bash "$REPO_ROOT/ctl.sh" status "$@"
}

function cmd_release_check() {
  require_cmd git
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
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
  validate       Delegates to repo-level ctl.sh validate
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
