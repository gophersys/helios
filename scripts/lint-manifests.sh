#!/usr/bin/env bash
# lint-manifests.sh — the kubeconform gate for raw manifests, with a FLOOR.
#
# The old gate went green over ZERO files: validate.yml piped an empty find into
# `xargs -0 -r kubeconform` (-r, --no-run-if-empty, runs kubeconform 0 times and
# exits 0). A roots list that resolved to nothing, or a path narrowing to zero
# manifests, would have read as a pass — the same swallow the shellcheck floor
# (#57) closed one job over. This script discovers the raw manifests once (the
# static root set + the non-templated registry `path:` values, minus the 4
# excludes), FAILS if it finds none (the floor), runs kubeconform at full
# strictness with findings VISIBLE, and prints a witness count. validate.yml
# calls it, so the floor cannot be bypassed.
#
# Usage: lint-manifests.sh [dir]   # dir defaults to the repo root
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIR="${1:-$ROOT}"

# A missing linter is a FAILURE, never a skip: a gate that cannot run its tool
# has checked nothing while reading green.
command -v kubeconform >/dev/null 2>&1 || {
  echo "lint-manifests: kubeconform is required and is not installed" >&2
  exit 127
}

# Roots resolve relative to DIR, so a fixture [dir] works the same way the real
# gate works from the checkout root.
cd "$DIR"

# Static roots + every path an Argo registry Application actually deploys, so a
# new Application source dir (e.g. platform/core/edge/...) can never silently
# escape validation.
roots="apps platform/services/gitops/registry platform/core/secrets-operator/manifests"

# Only grep the registry when it exists — a fixture dir has none. This is an
# existence check, not a 2>/dev/null swallow: a real read error still surfaces.
if [ -d "platform/services/gitops/registry" ]; then
  while IFS= read -r p; do
    case "$p" in *'{{'*|'') continue;; esac
    [ -d "$p" ] && roots="$roots $p"
  done < <(grep -hE '^[[:space:]]*path:' platform/services/gitops/registry/*.yaml | sed -E "s/.*path:[[:space:]]*//; s/['\"]//g" | sort -u)
fi

# Skip roots that no longer exist. A deleted directory must not fail a validation
# that otherwise passed — that reads as a real failure and trains people to
# ignore red. An if/fi (not `[ -d ] && …`) so a trailing missing root does not
# trip set -e and swallow the floor below.
existing=""
# shellcheck disable=SC2086  # intentional word-splitting of the roots list
for r in $roots; do
  if [ -d "$r" ]; then
    existing="$existing $r"
  fi
done
roots="$existing"

# THE FLOOR, part one. No surviving root means a bare `find $roots` would degrade
# to `find .` and validate the whole tree — a second false green. Converge onto
# the floor instead of ever running find with an empty roots list.
if [ -z "$roots" ]; then
  echo "lint-manifests: no manifests found — no discovery root exists under $DIR" >&2
  exit 1
fi

# Discover once. bash 3.2 (the macOS system bash) has no mapfile, so read -d ''.
# NO `xargs -0 -r`: the -r is exactly the swallow this script replaces. The
# `sort -zu` is load-bearing — it dedups the roots that overlap (145 -> 92).
files=()
while IFS= read -r -d '' f; do
  files+=("$f")
done < <(
  # shellcheck disable=SC2086  # intentional word-splitting of the roots list
  find $roots \
    -name '*.yaml' \
    -not -path '*/config-enforce/*' \
    -not -path '*/zephyr-devbox/*' \
    -not -path '*/envs/*' \
    -not -name 'kustomization.yaml' \
    -print0 | sort -zu
)

# A HELM CHART DIRECTORY IS NOT A RAW MANIFEST TREE.
# `platform/services/observability/chart` is an in-repo chart that an Argo
# Application deploys by `path:`, so the registry scan above discovers it as a
# root. Its Chart.yaml and its 3 values files carry no `kind`, and a template
# carries `{{ }}` where a value belongs, so kubeconform errors on every one of
# them: 4 red findings for 4 files that were never manifests. Anchor on the file
# that DEFINES a chart — a Chart.yaml at or above the file — rather than on the
# one path this repo has today, so the next in-repo chart needs no edit here.
#
# WHAT THIS COSTS, STATED: an in-repo chart's RENDERED output is validated by
# nothing in CI. That is the same coverage every `chart:`-sourced Application
# already has (external-secrets, tailscale-operator, arc-runners), so this adds
# no new blind spot — but it is a real gap, and closing it needs `helm template`
# with the dependencies built, which needs network and a helm binary the runner
# image does not promise. The skipped count below is printed so the exemption
# cannot quietly grow to swallow a real manifest tree.
kept=()
skipped=0
for f in ${files[@]+"${files[@]}"}; do
  d="$(dirname "$f")"
  in_chart=0
  while [ "$d" != "." ] && [ "$d" != "/" ]; do
    if [ -f "$d/Chart.yaml" ]; then in_chart=1; break; fi
    d="$(dirname "$d")"
  done
  if [ "$in_chart" -eq 1 ]; then
    skipped=$((skipped + 1))
    continue
  fi
  kept+=("$f")
done
files=(${kept[@]+"${kept[@]}"})

# THE FLOOR, part two. Zero manifests means the gate measured nothing — the one
# false green this whole change exists to kill. It sits AFTER the chart filter on
# purpose: a discovery set that is entirely chart source has checked nothing, and
# that must read the same as finding nothing at all.
if [ "${#files[@]}" -eq 0 ]; then
  echo "lint-manifests: no manifests found under $DIR" >&2
  exit 1
fi

# Full strictness, findings VISIBLE. set -e propagates a schema violation as a
# non-zero exit; the summary and every finding reach stdout/stderr, which proves
# kubeconform RAN rather than merely counting files.
kubeconform -strict -ignore-missing-schemas -summary "${files[@]}"

echo "lint-manifests: skipped $skipped file(s) inside a Helm chart"
echo "lint-manifests: checked ${#files[@]} manifest(s)"
