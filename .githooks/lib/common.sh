#!/usr/bin/env bash
#
# .githooks/lib/common.sh — shared helpers for the Eden git hooks (ADR-0018 Layer 1,
# the client-side teeth of the deterministic gate). Sourced by pre-commit and pre-push.
#
# Design notes:
#   - These hooks are the FIRST line of defense; CI re-runs the identical gate (10 §8,
#     "client hooks are bypassable with --no-verify; the server gate is not"). So a tool
#     being absent locally degrades to a loud WARN, never a silent pass — the gate is
#     authoritative in CI regardless.
#   - Fast and fail-clear: we only ever look at the files in *this* change, resolve them
#     to their owning Go module, and run each check once per touched module.
#
# shellcheck shell=bash

# -------- output (fail-clear, colour only on a tty) --------
if [[ -t 2 ]]; then
  _C_RED=$'\033[0;31m'; _C_GRN=$'\033[0;32m'; _C_YEL=$'\033[0;33m'
  _C_CYN=$'\033[0;36m'; _C_DIM=$'\033[2m'; _C_RST=$'\033[0m'
else
  _C_RED=''; _C_GRN=''; _C_YEL=''; _C_CYN=''; _C_DIM=''; _C_RST=''
fi

hook_info()  { printf '%s[hook]%s %s\n' "$_C_CYN" "$_C_RST" "$*" >&2; }
hook_ok()    { printf '%s[hook ok]%s %s\n' "$_C_GRN" "$_C_RST" "$*" >&2; }
hook_warn()  { printf '%s[hook warn]%s %s\n' "$_C_YEL" "$_C_RST" "$*" >&2; }
hook_fail()  { printf '%s[hook FAIL]%s %s\n' "$_C_RED" "$_C_RST" "$*" >&2; }
hook_dim()   { printf '%s%s%s\n' "$_C_DIM" "$*" "$_C_RST" >&2; }

# Repo root (eden monorepo). Hooks always run with cwd = repo root, but be explicit.
REPO_ROOT="$(git rev-parse --show-toplevel)"
export REPO_ROOT

# NOTE: macOS ships bash 3.2 (no `mapfile`/`readarray`). These hooks therefore avoid
# bash-4-only builtins. `hook_read_lines <arrayname>` reads newline-delimited stdin into
# the named array, portably. Usage:  hook_read_lines FOO < <(some_command)
hook_read_lines() {
  local __name="$1" __line
  eval "$__name=()"
  while IFS= read -r __line; do
    [[ -n "$__line" ]] || continue
    eval "$__name+=(\"\$__line\")"
  done
}

# have <cmd> — is a tool on PATH? (also probes $(go env GOPATH)/bin, where the pinned
# Go tools land). Returns 0 and echoes the resolved path; 1 if missing.
hook_have() {
  local cmd="$1" p
  if p="$(command -v "$cmd" 2>/dev/null)"; then printf '%s\n' "$p"; return 0; fi
  if command -v go >/dev/null 2>&1; then
    p="$(go env GOPATH 2>/dev/null)/bin/$cmd"
    if [[ -x "$p" ]]; then printf '%s\n' "$p"; return 0; fi
  fi
  return 1
}

# hook_staged_go_files — staged (Added/Copied/Modified) *.go files, NUL-safe, repo-relative.
# Prints one path per line. Use the *cached* tree so we check exactly what is committed.
hook_staged_go_files() {
  git diff --cached --name-only --diff-filter=ACM -z -- '*.go' \
    | tr '\0' '\n' | sed '/^$/d'
}

# hook_changed_go_files_range <range> — *.go files changed across a commit range
# (pre-push). Prints repo-relative paths, one per line.
hook_changed_go_files_range() {
  local range="$1"
  git diff --name-only --diff-filter=ACM -z "$range" -- '*.go' \
    | tr '\0' '\n' | sed '/^$/d'
}

# hook_module_dir <file> — walk up from a file to the nearest dir containing go.mod.
# Prints the absolute module dir, or nothing if the file is not inside a Go module.
hook_module_dir() {
  local f="$1" dir
  dir="$(cd "$REPO_ROOT" && cd "$(dirname "$f")" 2>/dev/null && pwd)" || return 0
  while [[ -n "$dir" && "$dir" != "/" ]]; do
    if [[ -f "$dir/go.mod" ]]; then printf '%s\n' "$dir"; return 0; fi
    dir="$(dirname "$dir")"
  done
}

# hook_unique_modules — read repo-relative go files on stdin, print the unique set of
# absolute owning-module directories (one per line).
hook_unique_modules() {
  local f md
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    # testdata/ holds deliberately-malformed fixtures (Go ignores it by convention) —
    # never lint them, and they are separate modules so they break workspace resolution.
    case "$f" in */testdata/*) continue ;; esac
    md="$(hook_module_dir "$f")"
    [[ -n "$md" ]] && printf '%s\n' "$md"
  done | sort -u
}

# hook_touched_libs_go — read repo-relative go files on stdin, print the unique set of
# touched `libs/go/<lib>` slugs (one per line). These are what hnslint structurally checks.
hook_touched_libs_go() {
  local f
  while IFS= read -r f; do
    case "$f" in
      libs/go/*/*) printf '%s\n' "$f" | sed -E 's#^(libs/go/[^/]+)/.*#\1#' ;;
    esac
  done | sort -u
}

# hook_gofumpt_check <file...> — gofumpt -l on the given files; any output = a violation.
# gofumpt is the stricter-than-gofmt formatter (ADR-0018 Layer 1, "zero tolerance").
hook_gofumpt_check() {
  local bin out
  if ! bin="$(hook_have gofumpt)"; then
    hook_warn "gofumpt not found — formatting NOT verified locally (CI will). install: go install mvdan.cc/gofumpt@latest"
    return 0
  fi
  out="$("$bin" -l "$@" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    hook_fail "gofumpt: the following files are not formatted:"
    printf '%s\n' "$out" | sed 's/^/    /' >&2
    hook_dim "    fix: gofumpt -w <file>   (or: run ctl.sh fmt in the module)"
    return 1
  fi
  return 0
}

# hook_golangci_module <module-dir> — golangci-lint over a single module. Picks up the
# shared libs/.golangci.yml by upward discovery (ADR-0018 Layer 1). Runs the FULL set, not
# --fast-only: forbidigo (the HNS-1 banned-token gate) and the naming linters are NOT in the
# fast set, so --fast-only silently disarms the teeth this gate exists to provide (C25). The
# pattern libraries are small; the full set runs in ~1s.
# hook_module_gowork <module-dir> — echo the GOWORK env for linting a module. A module that
# requires the UNPUBLISHED workspace siblings (github.com/gophersys/libs/go/*, pinned at
# v0.0.0 and resolved only via the dev go.work) can ONLY typecheck WITH the workspace; it is
# linted by inheriting the active go.work. That set is libs/go/* AND any app/tool/poc that
# imports a sibling lib (e.g. apps/agentgateway over orchestrator+agentsession). A module with
# no such require is standalone and lints in release isolation (GOWORK=off) so its own
# go.mod/go.sum stays honest. This is the one rule that makes the gate correct across the monorepo.
hook_module_gowork() {
  local dir="$1"
  case "$dir" in
    */libs/go/*) printf ''; return ;;  # always a workspace member
  esac
  if [[ -f "$dir/go.mod" ]] && grep -q 'github.com/gophersys/libs/go/' "$dir/go.mod"; then
    printf ''           # depends on unpublished workspace siblings -> inherit the go.work
  else
    printf 'GOWORK=off' # standalone module -> release isolation
  fi
}

hook_golangci_module() {
  local module_dir="$1" bin gw
  if ! bin="$(hook_have golangci-lint)"; then
    hook_warn "golangci-lint not found — lint NOT verified locally (CI will). install: golangci-lint v2"
    return 0
  fi
  gw="$(hook_module_gowork "$module_dir")"
  ( cd "$module_dir" && env ${gw:+$gw} "$bin" run --timeout=120s ./... ) 1>&2
}

# hook_golangci_module_full <module-dir> — the full linter set (pre-push).
hook_golangci_module_full() {
  local module_dir="$1" bin
  if ! bin="$(hook_have golangci-lint)"; then
    hook_warn "golangci-lint not found — lint NOT verified locally (CI will)."
    return 0
  fi
  local gw; gw="$(hook_module_gowork "$module_dir")"
  ( cd "$module_dir" && env ${gw:+$gw} "$bin" run --timeout=180s ./... ) 1>&2
}

# hook_hnslint_lib <lib-dir> — the structural HNS-1 check (ADR-0018, tools/hnslint):
# module path = github.com/gophersys/libs/go/<slug>, package name = separator-free
# lowercase of the slug, directory = the slug. hnslint is a Go analyzer; until it is
# built (Layer 1, sibling task), we fall back to an inline structural check so this hook
# is useful from day one and gains precision once the analyzer lands.
hook_hnslint_lib() {
  local lib_dir="$1" bin slug rc=0
  slug="$(basename "$lib_dir")"
  # The real analyzer (tools/hnslint) takes lib *directory* paths and exits 1 on any
  # violation. Install it with: (cd tools/hnslint && GOWORK=off go install ./cmd/hnslint)
  if bin="$(hook_have hnslint)"; then
    "$bin" "$REPO_ROOT/$lib_dir" 1>&2 || rc=$?
    return $rc
  fi
  # --- inline fallback: the three structural invariants hnslint will own ---
  local expected_pkg modpath declared_pkg
  expected_pkg="$(printf '%s' "$slug" | tr -d '-')"               # separator-free lowercase
  # module path
  if [[ -f "$lib_dir/go.mod" ]]; then
    modpath="$(awk '/^module /{print $2; exit}' "$lib_dir/go.mod")"
    if [[ "$modpath" != "github.com/gophersys/libs/go/$slug" ]]; then
      hook_fail "hnslint($slug): module path is '$modpath', want 'github.com/gophersys/libs/go/$slug' (HNS-1, 10 §5)"
      rc=1
    fi
  fi
  # package name of the library root file (the slug-named .go file, else first non-test .go)
  local root_go candidate
  root_go="$lib_dir/$slug.go"
  if [[ ! -f "$root_go" ]]; then
    root_go=""
    for candidate in "$lib_dir"/*.go; do
      [[ -f "$candidate" ]] || continue           # no match — glob stayed literal
      [[ "$candidate" == *_test.go ]] && continue
      root_go="$candidate"; break
    done
  fi
  if [[ -n "$root_go" && -f "$root_go" ]]; then
    declared_pkg="$(awk '/^package /{print $2; exit}' "$root_go")"
    if [[ -n "$declared_pkg" && "$declared_pkg" != "$expected_pkg" ]]; then
      hook_fail "hnslint($slug): package is '$declared_pkg', want '$expected_pkg' (separator-free slug, HNS-1)"
      rc=1
    fi
  fi
  if [[ $rc -ne 0 ]]; then
    hook_dim "    (inline HNS-1 fallback — install tools/hnslint for the full structural analyzer)"
  fi
  return $rc
}

# hook_gotest_module <module-dir> — race-enabled test run for one module (pre-push).
hook_gotest_module() {
  local module_dir="$1"
  if ! hook_have go >/dev/null; then
    hook_warn "go not found — tests NOT run locally."
    return 0
  fi
  local gw; gw="$(hook_module_gowork "$module_dir")"
  ( cd "$module_dir" && env ${gw:+$gw} go test ./... -race -count=1 ) 1>&2
}
