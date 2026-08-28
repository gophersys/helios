#!/usr/bin/env bash
#
# scripts/gen-go-work.sh — deterministically (re)generate the workspace go.work from a CURATED
# module list.
#
# go.work is gitignored (a per-developer file Go rewrites on every `go work use`, .gitignore:38), so
# it has NO committed copy. This script is its ONE reproducible source: the deploy image builds RUN
# it before `go build`, so a clean checkout — or any `git archive` / CI image-build context that has
# no go.work — still resolves the unpublished `v0.0.0` sibling libraries to their in-repo source
# instead of dropping into module mode and failing the lookup on the proxy.
#
# The module list is CURATED, never a blind `find -name go.mod`: poc/knowledge carries
# deliberately-isolated go.mod test FIXTURES (bad module paths, conflicting names) that must NEVER
# enter the workspace, and the other poc/ donor modules (poc/agents, poc/codeinsight)
# stay out too — poc/ is reference-only material (ADR-0009 D), never workspace members. The three
# GOWORK=off build-time renderers are also EXCLUDED on purpose so they keep resolving in module
# mode (their go.mod docs say so):
#   - deploy/servicespec                     (the typed deploy renderer; stdlib-only, own module)
#   - apps/platformgateway/deploy            (a GOWORK=off image-build module)
#   - libs/templates/go/http-gateway/deploy  (the template's GOWORK=off image-build module)
#
# Curated does NOT mean optional. `libs/go/<library>` has ONE rule with no exception: a library that
# holds a go.mod is a workspace member. The script asserts that rule and every listed path before it
# writes anything, and a mismatch is a FAILURE. It used to be a warning, and the warning let
# libs/go/envelope sit outside the workspace while apps/platformgateway imported it.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Keep the go directive in lockstep with the module toolchain + .devcontainer ARG GO_VERSION
# (go.work's own `go 1.26.4`); the deploy images pin the same.
GO_DIRECTIVE="1.26.4"

# The workspace member modules — relative dirs each holding a go.mod. Curated and ordered.
# Only modules that benefit from in-repo sibling resolution are members. A module that must build
# standalone is deliberately absent, and its own ctl.sh runs with GOWORK=off.
USE_DIRS=(
  libs/templates/go/http-gateway
  libs/templates/go/http-gateway/clients/go
  apps/agent-runtime
  apps/agentgateway
  apps/platformgateway
  apps/platformgateway/clients/go
  libs/go/agentruntime
  libs/go/agentsession
  libs/go/codeinsight
  libs/go/configuration
  libs/go/dependencies
  libs/go/edenhttp
  libs/go/envelope
  libs/go/errors
  libs/go/forge
  libs/go/gitrepository
  libs/go/objectstorage
  libs/go/observability
  libs/go/orchestrator
  libs/go/secrets
  libs/go/testing
  libs/go/workspaceprovider
  poc/codingharness
  tools/documentvalidator
)

# ── The curated list is checked against the tree BEFORE go.work is touched, so a failure never
# leaves a half-written workspace behind.

# 1. Every listed module must exist. An absent one used to print a WARNING and exit 0, which wrote
#    a silently INCOMPLETE go.work; the build then failed far away from the cause. It is a failure
#    here instead. An uninitialized libs/ submodule trips this, which is the correct report.
missing=()
for dir in "${USE_DIRS[@]}"; do
  if [[ ! -f "$dir/go.mod" ]]; then
    missing+=("$dir")
  fi
done

# 2. Every libs/go/<library> that HAS a go.mod must be listed. The replace loop below walks
#    libs/go/*/ by directory, so a new library silently got a replace and no `use`, and dropped out
#    of the workspace. libs/go/envelope did exactly that: apps/platformgateway imports it in
#    production code, yet `go list ./libs/go/envelope/...` answered "outside module roots". This
#    check makes listing a new library mandatory instead of remembered.
unlisted=()
for libdir in libs/go/*/; do
  if [[ ! -f "${libdir}go.mod" ]]; then
    continue
  fi
  candidate="${libdir%/}"
  listed=0
  for dir in "${USE_DIRS[@]}"; do
    if [[ "$dir" == "$candidate" ]]; then
      listed=1
      break
    fi
  done
  if [[ $listed -eq 0 ]]; then
    unlisted+=("$candidate")
  fi
done

if [[ ${#missing[@]} -gt 0 || ${#unlisted[@]} -gt 0 ]]; then
  printf 'gen-go-work: FAILED — the curated module list does not match the tree.\n' >&2
  if [[ ${#missing[@]} -gt 0 ]]; then
    printf '  listed but absent (restore the module, or remove the entry): %s\n' "${missing[*]}" >&2
  fi
  if [[ ${#unlisted[@]} -gt 0 ]]; then
    printf '  holds a go.mod but is not a workspace member (add it to USE_DIRS): %s\n' "${unlisted[*]}" >&2
  fi
  exit 1
fi

rm -f go.work go.work.sum
go work init
go work edit -go="$GO_DIRECTIVE"

for dir in "${USE_DIRS[@]}"; do
  go work use "./$dir"
done

# Pin every unpublished v0.0.0 sibling library to its in-repo source. This is load-bearing only for a
# module that also pulls a pre-1.17 (+incompatible) dependency — e.g. workspaceprovider's docker SDK —
# whose unpruned module graph would otherwise look up the siblings@v0.0.0 on the proxy instead of
# honoring the `use` directives. A replace for a module nobody requires at v0.0.0 is harmless, so the
# whole libs/go set is pinned uniformly (one rule, no per-lib judgement).
for libdir in libs/go/*/; do
  [[ -f "${libdir}go.mod" ]] || continue
  name="$(basename "$libdir")"
  go work edit -replace="github.com/gophersys/libs/go/${name}@v0.0.0=./libs/go/${name}"
done

printf 'gen-go-work: wrote %s/go.work (%d curated modules)\n' "$ROOT" "${#USE_DIRS[@]}"
