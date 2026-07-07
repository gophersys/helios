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
# The module list is CURATED, never a blind `find -name go.mod`: poc/knowledge and the hnslint
# checker carry deliberately-isolated go.mod test FIXTURES (bad module paths, conflicting names) that
# must NEVER enter the workspace, and the other poc/ donor modules (poc/agents, poc/codeinsight)
# stay out too — poc/ is reference-only material (ADR-0009 D), never workspace members. The three
# GOWORK=off build-time renderers are also EXCLUDED on purpose so they keep resolving in module
# mode (their go.mod docs say so):
#   - deploy/servicespec                     (the typed deploy renderer; stdlib-only, own module)
#   - apps/platformgateway/deploy            (a GOWORK=off image-build module)
#   - libs/templates/go/http-gateway/deploy  (the template's GOWORK=off image-build module)
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Keep the go directive in lockstep with the module toolchain + .devcontainer ARG GO_VERSION
# (go.work's own `go 1.26.4`); the deploy images and tools/cictl's updatability gate pin the same.
GO_DIRECTIVE="1.26.4"

# The workspace member modules — relative dirs each holding a go.mod. Curated + ordered. tools/cictl
# IS a member (a normal tool module that benefits from in-repo sibling resolution); the GOWORK=off
# renderers above are intentionally absent.
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
  tools/cictl
  tools/documentvalidator
  tools/hnslint
)

rm -f go.work go.work.sum
go work init
go work edit -go="$GO_DIRECTIVE"

missing=()
for dir in "${USE_DIRS[@]}"; do
  if [[ -f "$dir/go.mod" ]]; then
    go work use "./$dir"
  else
    missing+=("$dir")
  fi
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

if [[ ${#missing[@]} -gt 0 ]]; then
  printf 'gen-go-work: WARNING — listed module(s) absent, skipped: %s\n' "${missing[*]}" >&2
fi
printf 'gen-go-work: wrote %s/go.work (%d curated modules)\n' "$ROOT" "$(( ${#USE_DIRS[@]} - ${#missing[@]} ))"
