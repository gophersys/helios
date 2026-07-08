#!/usr/bin/env bash
#
# apps/frontend/ctl.sh — control script for @eden/frontend, the SvelteKit
# development spine that hosts the document workspace (ADR-0015).
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json
# targets are thin wrappers that delegate here, so a consumer can invoke
# `nx run frontend:build` without reading source. The dev/build verbs first ensure
# the documentvalidator binary exists — it is the projection source of truth that
# the SvelteKit server routes shell out to (ADR-0015 §2, the projection seam).
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")"
VALIDATOR_SOURCE="$REPO_ROOT/tools/documentvalidator"
VALIDATOR_BINARY="$PROJECT_ROOT/.eden/documentvalidator"

# The package-manager / runner invocation, held as an array so the multi-word default
# survives the restricted IFS above. The base devcontainer is bun-only (no node/yarn/
# corepack on PATH), so the default runner is `bun x` — it executes the workspace-local
# vite / svelte-kit / svelte-check / playwright binaries directly. Override with EDEN_YARN
# (whitespace-separated) on a host that resolves the toolchain through corepack yarn instead.
IFS=' ' read -r -a YARN <<<"${EDEN_YARN:-bun x}"
# A space-joined rendering for log lines (the global IFS above would otherwise join
# array elements with a newline). The array itself is what gets executed.
printf -v YARN_DISPLAY '%s ' "${YARN[@]}"
YARN_DISPLAY="${YARN_DISPLAY% }"

# -------- logging --------
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

# -------- tool gate --------
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

# -------- projection source of truth --------
# Build the documentvalidator CLI into .eden/ (gitignored). This is the projection
# contract the SvelteKit server routes consume; dev/build ensure it is present so the
# workspace can render projections without a separate setup step.
function ensure_validator() {
  require_cmd go
  if [[ ! -d "$VALIDATOR_SOURCE" ]]; then
    log_error "documentvalidator source not found at $VALIDATOR_SOURCE"
    exit 1
  fi
  log_info "ensure: building documentvalidator -> $VALIDATOR_BINARY"
  mkdir -p "$(dirname "$VALIDATOR_BINARY")"
  go build -C "$VALIDATOR_SOURCE" -o "$VALIDATOR_BINARY" ./cmd/documentvalidator
  log_success "ensure: documentvalidator binary is current"
}

# -------- commands --------
function cmd_dev() {
  ensure_validator
  log_info "dev: $YARN_DISPLAY vite dev"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" vite dev "$@")
}

function cmd_build() {
  ensure_validator
  log_info "build: $YARN_DISPLAY vite build"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" vite build "$@")
  log_success "build: OK"
}

function cmd_preview() {
  log_info "preview: $YARN_DISPLAY vite preview"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" vite preview "$@")
}

function cmd_lint() {
  log_info "lint: $YARN_DISPLAY prettier --check (svelte + ts + config)"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" prettier --check .)
  log_success "lint: OK"
}

function cmd_typecheck() {
  log_info "typecheck: $YARN_DISPLAY svelte-kit sync && svelte-check"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" svelte-kit sync && "${YARN[@]}" svelte-check --tsconfig ./tsconfig.json)
  log_success "typecheck: OK"
}

# check is the alias the library gate (ADR-0020) and package.json `check` script use for the
# svelte-check / tsc pass — same body as typecheck.
function cmd_check() { cmd_typecheck "$@"; }

# e2e runs the Playwright forced-CRUD suite against a REAL agentgateway dev-serve. The runner
# (tests/e2e/run.sh) builds + boots the dev-serve on a free port, serves the production build via
# vite preview on a free port, points the UI at the dev-serve, drives the browser, and tears both
# down. No mocked fetch/SSE — the HTTP/SSE the UI exercises is 100% real (the dev-serve's harness
# is the deterministic fake, which is the gateway's concern). Browsers are installed on first run.
function cmd_e2e() {
  require_cmd bun
  log_info "e2e: Playwright forced-CRUD against a real dev-serve"
  (cd "$PROJECT_ROOT" && bash tests/e2e/run.sh "$@")
  log_success "e2e: OK"
}

# unit runs the vitest unit suite (the openEditor desktop/web branch-selection test lives here). The
# frontend is a yarn workspace member, so `bun x vitest` resolves the workspace-hoisted vitest (the same
# pin the @eden/* TS libs gate against). jsdom is wired in vitest.config.unit.ts for the window/location
# mocking the branch test needs. Run-once (no watch) so it is a clean gate. svelte-kit sync first:
# tsconfig.json extends the GENERATED .svelte-kit/tsconfig.json, which a fresh checkout (CI) does not
# have — without the sync, vite-tsconfig parsing fails before a single test runs (self-sufficient
# gate; locally the file exists from dev, which hid this).
function cmd_unit() {
  require_cmd bun
  log_info "unit: $YARN_DISPLAY svelte-kit sync && vitest run --config vitest.config.unit.ts"
  (cd "$PROJECT_ROOT" && "${YARN[@]}" svelte-kit sync && "${YARN[@]}" vitest run --config vitest.config.unit.ts "$@")
  log_success "unit: OK"
}

# tauri drives the desktop shell (ADR-0006) via the Tauri CLI. The shell wraps the SAME web bundle
# (src-tauri/tauri.conf.json points at this app's dev server / build output) and bakes
# PUBLIC_EDEN_RUNTIME=desktop so isDesktop() resolves true. The Tauri CLI is the `cargo tauri` cargo
# subcommand (cargo-tauri); if the toolchain is absent this FAILS LOUDLY (FAIL-NOT-SKIP) rather than
# pretend a build happened. The default action is `build`; pass dev/build/info through.
#   ./ctl.sh tauri info       # report the Tauri/Rust/webview toolchain status
#   ./ctl.sh tauri dev        # run the desktop shell over the live vite dev server
#   ./ctl.sh tauri build      # package the desktop app (needs the SvelteKit static adapter — see tauri.conf.json)
function cmd_tauri() {
  require_cmd cargo
  if ! cargo tauri --help >/dev/null 2>&1; then
    log_error "the Tauri CLI (cargo-tauri) is not installed — install it with: cargo install tauri-cli --version '^2'"
    log_error "(the src-tauri scaffold is complete; only the CLI binary is missing)"
    exit 127
  fi
  local action="${1:-build}"
  shift || true
  log_info "tauri: cargo tauri $action (desktop shell over the web bundle, PUBLIC_EDEN_RUNTIME=desktop)"
  (cd "$PROJECT_ROOT/src-tauri" && PUBLIC_EDEN_RUNTIME=desktop cargo tauri "$action" "$@")
  log_success "tauri: OK"
}

# -------- usage --------
function usage() {
  cat <<EOF
Usage: ./ctl.sh <command> [args...]

Commands:
  dev          Start the Vite dev server (ensures the documentvalidator binary first)
  build        Production build via Vite (ensures the documentvalidator binary first)
  preview      Serve the production build locally
  lint         Check formatting with prettier
  typecheck    Sync SvelteKit types and run svelte-check (TypeScript strict)
  check        Alias of typecheck (the ADR-0020 gate / package.json check)
  e2e          Playwright forced-CRUD E2E against a real agentgateway dev-serve
  unit         Vitest unit suite (openEditor desktop/web branch selection)
  tauri        Drive the desktop shell (cargo tauri <dev|build|info>); FAILS if the CLI is absent
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    dev)       cmd_dev       "$@" ;;
    build)     cmd_build     "$@" ;;
    preview)   cmd_preview   "$@" ;;
    lint)      cmd_lint      "$@" ;;
    typecheck) cmd_typecheck "$@" ;;
    check)     cmd_check     "$@" ;;
    e2e)       cmd_e2e       "$@" ;;
    unit)      cmd_unit      "$@" ;;
    tauri)     cmd_tauri     "$@" ;;
    help|"")   usage ;;
    *)         log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
