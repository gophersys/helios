#!/usr/bin/env bash
#
# apps/agent-runtime/ctl.sh — control script for the Eden agent-pod PID-1 runtime sidecar: the
# container's main process (the workspaceprovider Entrypoint/workload-pod capability, ADR-0022 §4).
# It builds the agentruntime.Runtime via its composition root (real NATS/JetStream bus,
# observability, the agentsession harness factory) and runs it as PID-1, serving /live +
# /health/{id} for the kubelet.
#
# Usage: ./ctl.sh <command> [args...]
#
# Verbs are uniform with the monorepo's nx:run-commands convention: project.json targets are
# thin wrappers that delegate here, so a consumer can invoke `nx run agent-runtime:test`
# without reading source. The Go tooling runs WITH the repo workspace (GOWORK) so the in-repo
# sibling libraries (agentruntime, agentsession, observability, secrets, …) resolve to their
# source, and golangci-lint runs against the shared libs config (one standard, no per-app
# copy — ADR-0018).
#
set -Eeuo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_ROOT")"

# The repo workspace (gitignored) pins every in-repo sibling library to its source. Building
# and testing the app WITH it is load-bearing: the app's go.mod carries no replace directives
# (the workspace owns resolution), so a bare `go build` outside the workspace cannot resolve
# the v0.0.0 siblings.
GOWORK_FILE="$REPO_ROOT/go.work"
export GOWORK="$GOWORK_FILE"

# The shared, strict golangci-lint config lives in the libs submodule root (ADR-0018 Layer 1).
GOLANGCI_CONFIG="$REPO_ROOT/libs/.golangci.yml"

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

# -------- commands --------
function cmd_build() {
  require_cmd go
  log_info "build: go build ./... (GOWORK=$GOWORK_FILE)"
  (cd "$PROJECT_ROOT" && go build ./...)
  log_success "build: OK"
}

function cmd_test() {
  require_cmd go
  log_info "test: go test ./... -race -count=1 (handler + fake-harness suite)"
  (cd "$PROJECT_ROOT" && go test ./... -race -count=1)
  log_success "test: OK"
}

function cmd_integration() {
  require_cmd go
  log_info "integration: go test -tags integration ./... -race -count=1 (concurrent SSE fan-out + replay + credential seam)"
  (cd "$PROJECT_ROOT" && go test -tags integration ./... -race -count=1)
  log_success "integration: OK"
}

function cmd_vet() {
  require_cmd go
  log_info "vet: go vet ./... (default + integration tags)"
  (cd "$PROJECT_ROOT" && go vet ./...)
  (cd "$PROJECT_ROOT" && go vet -tags integration ./...)
  log_success "vet: OK"
}

function cmd_fmt() {
  require_cmd gofumpt
  log_info "fmt: gofumpt -w ."
  (cd "$PROJECT_ROOT" && gofumpt -w .)
  log_success "fmt: OK"
}

function cmd_lint() {
  require_cmd go gofumpt
  log_info "lint: gofumpt -l ."
  local unformatted
  unformatted="$(cd "$PROJECT_ROOT" && gofumpt -l .)"
  if [[ -n "$unformatted" ]]; then
    log_error "gofumpt found unformatted files:"
    printf '  %s\n' "$unformatted" >&2
    exit 1
  fi
  cmd_vet
  if command -v golangci-lint >/dev/null 2>&1; then
    log_info "lint: golangci-lint run --config $GOLANGCI_CONFIG ./... (default + integration tags)"
    (cd "$PROJECT_ROOT" && golangci-lint run --config "$GOLANGCI_CONFIG" ./...)
    (cd "$PROJECT_ROOT" && golangci-lint run --build-tags integration --config "$GOLANGCI_CONFIG" ./...)
  else
    log_warn "lint: golangci-lint not installed — skipping (install per ADR-0018)"
  fi
  log_success "lint: OK"
}

function cmd_cover() {
  require_cmd go
  log_info "cover: go test ./... -coverprofile"
  local profile
  profile="$(mktemp -t agent-runtime-cover.XXXXXX)"
  (cd "$PROJECT_ROOT" && go test ./... -covermode=atomic -coverprofile="$profile")
  (cd "$PROJECT_ROOT" && go tool cover -func="$profile" | tail -1)
  rm -f "$profile"
  log_success "cover: OK"
}

# cmd_smoke — bootstrap smoke: build the binary, run it in EDEN_PROBE_ONLY mode (no bus, no
# harness), confirm it serves /live, then SIGTERM it and confirm a graceful exit-0. Proves the
# PID-1 entrypoint compiles, starts, serves the kubelet probe, and shuts down cleanly on a signal.
function cmd_smoke() {
  require_cmd go curl
  local binary port
  binary="$(mktemp -t agent-runtime-smoke.XXXXXX)"
  port="$(( (RANDOM % 20000) + 20000 ))"
  log_info "smoke: building the agent-runtime binary"
  (cd "$PROJECT_ROOT" && go build -o "$binary" ./cmd/agent-runtime)

  log_info "smoke: starting in probe-only mode on :${port}"
  EDEN_PROBE_ONLY=1 EDEN_AGENT_ID="smoke-1" EDEN_PROBE_ADDR=":${port}" "$binary" &
  # Reap on any exit path. SMOKE_PID/SMOKE_BIN are non-local so the EXIT trap sees them robustly
  # under `set -u` even after the function's locals unwind.
  SMOKE_PID=$!
  SMOKE_BIN="$binary"
  # The cleanup kills the child ONLY when SMOKE_PID names a real pid (never `kill 0`, which would
  # signal the whole process group including this shell), and removes the temp binary.
  trap '[[ -n "${SMOKE_PID:-}" ]] && kill "${SMOKE_PID}" 2>/dev/null; rm -f "${SMOKE_BIN:-}" 2>/dev/null; true' EXIT

  # Wait for /live to answer 200 (bounded).
  local ok="" attempt
  for attempt in $(seq 1 50); do
    : "$attempt"
    if curl -fsS "http://127.0.0.1:${port}/live" >/dev/null 2>&1; then ok=1; break; fi
    sleep 0.1
  done
  if [[ -z "$ok" ]]; then
    log_error "smoke: /live did not answer 200 within 5s"
    exit 1
  fi
  log_success "smoke: /live answered 200"

  log_info "smoke: sending SIGTERM (the graceful-shutdown path)"
  kill -TERM "$SMOKE_PID"
  local rc=0
  wait "$SMOKE_PID" || rc=$?
  SMOKE_PID=""
  if [[ "$rc" -ne 0 ]]; then
    log_error "smoke: graceful shutdown returned non-zero exit ${rc}"
    exit 1
  fi
  log_success "smoke: graceful exit-0 on SIGTERM — PID-1 entrypoint OK"
}

# -------- usage --------
function usage() {
  cat <<'EOF'
Usage: ./ctl.sh <command> [args...]

Commands:
  build        Compile the app (go build ./...)
  test         Run the composition unit suite with the race detector (go test ./... -race -count=1)
  integration  Run the integration suite (go test -tags integration ./... -race -count=1)
  smoke        Boot the PID-1 binary probe-only, confirm /live, SIGTERM it, confirm graceful exit-0
  lint         Check formatting (gofumpt), go vet (both tags), and golangci-lint (both tags, libs config)
  vet          Run go vet ./... (default + integration tags)
  fmt          Format sources in place (gofumpt -w .)
  cover        Run tests with coverage and print the total
  help         Show this message
EOF
}

# -------- dispatcher --------
function main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    build)       cmd_build       "$@" ;;
    test)        cmd_test        "$@" ;;
    integration) cmd_integration "$@" ;;
    smoke)       cmd_smoke       "$@" ;;
    lint)        cmd_lint        "$@" ;;
    vet)         cmd_vet         "$@" ;;
    fmt)         cmd_fmt         "$@" ;;
    cover)       cmd_cover       "$@" ;;
    help|"")     usage ;;
    *)           log_error "unknown command: '$cmd'"; usage; exit 1 ;;
  esac
}

main "$@"
