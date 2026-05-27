#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# Concord Platform CLI
# ───────────────────────────────────────────────────────────────
# Single entry point for all platform lifecycle operations across
# development, staging, and production environments.
#
# Usage:
#   ./deploy/ctl.sh <environment> <action> [args...]
#
# Environments:
#   development   Docker Compose (local containers)
#   staging       Kubernetes staging namespace
#   production    Kubernetes production namespace
#
# Lifecycle:
#   start         Full 0→running (idempotent)
#   update        Rebuild + redeploy (fast, cached)
#   stop          Teardown app workloads (safe)
#   status        Show what's running
#   logs          Tail component logs
# ───────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE="docker compose -f deploy/development/docker-compose.yaml"
HELM_DIR="${SCRIPT_DIR}/production/helm"

REGISTRY="containers.ad.corekinect.com"
REGISTRY_API="${REGISTRY}/concord-http-api"
REGISTRY_FRONTEND="${REGISTRY}/concord-frontend"
REGISTRY_GIT_POLLER="${REGISTRY}/concord-git-poller"
REGISTRY_BUILD_SERVICE="${REGISTRY}/concord-build-service"
REGISTRY_DOCS="${REGISTRY}/concord-docs"
REGISTRY_TEST_RUNNER="${REGISTRY}/concord-test-runner"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[concord]${NC} $*"; }
warn() { echo -e "${YELLOW}[concord]${NC} $*"; }
err()  { echo -e "${RED}[concord]${NC} $*" >&2; }
info() { echo -e "${CYAN}[concord]${NC} $*"; }
step() { echo -e "\n${CYAN}▸${NC} $*"; }

TIMER_START=0
timer_start() { TIMER_START=$(date +%s%N); }
timer_end() {
  local elapsed_ms=$(( ($(date +%s%N) - TIMER_START) / 1000000 ))
  if (( elapsed_ms > 60000 )); then
    info "  ${1}: ${BOLD}$(( elapsed_ms / 1000 ))s${NC}"
  else
    info "  ${1}: ${BOLD}${elapsed_ms}ms${NC}"
  fi
}

# ═════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════

# Git metadata — works in standalone clones and inside containers.
# In standalone clones, git works directly. In submodule workspaces where the
# parent .git/modules isn't mounted, falls back to .git-build-info (a 3-line
# file: commit, branch, dirty). The caller is responsible for refreshing that
# file before invoking ctl.sh if git isn't available inside the container.
_git_info_file="${SCRIPT_DIR}/../.git-build-info"

_git_commit() {
  git rev-parse --short HEAD 2>/dev/null \
    || sed -n '1p' "${_git_info_file}" 2>/dev/null \
    || echo "unknown"
}

_git_branch() {
  git rev-parse --abbrev-ref HEAD 2>/dev/null \
    || sed -n '2p' "${_git_info_file}" 2>/dev/null \
    || echo "unknown"
}

_git_dirty() {
  if git rev-parse --git-dir &>/dev/null; then
    [ -n "$(git status --porcelain 2>/dev/null)" ] && echo true || echo false
  else
    sed -n '3p' "${_git_info_file}" 2>/dev/null || echo "false"
  fi
}

_git_describe() {
  git describe --tags --exact-match 2>/dev/null || true
}

# ═════════════════════════════════════════════════════════════════
# Phase D Layer 2 — runner freshness gate
# ═════════════════════════════════════════════════════════════════
#
# Compute a deterministic SHA for the libs/python/corekinect/ tree at
# HEAD. The runner Docker image bakes this in as COREKINECT_GIT_SHA at
# build time, and `_check_runner_corekinect_freshness` compares the
# baked value against this helper's output before a deploy. If they
# diverge, the live runner pods are running stale corekinect against
# the new platform — the v0.12.0->0.12.3 silent-skew failure mode.
#
# Primary: `git log -1 --format=%H -- libs/python/corekinect/` returns
# the commit SHA that last touched the tree. Deterministic across
# clones (everyone on the same commit gets the same SHA).
#
# Fallback: tree-hash via `git ls-tree HEAD libs/python/corekinect/`,
# sha256summed. Used when `git log` is unavailable (e.g., shallow
# clones in CI). The hash space is different from a commit SHA but
# still serves the equality check.
#
# Last resort: read .git-build-info (line 4 — see _populate_build_info
# helper that gets called from the umbrella refresh script). Returns
# "unknown" if nothing works.
_corekinect_sha() {
  local sha
  sha=$(git log -1 --format=%H -- libs/python/corekinect/ 2>/dev/null)
  if [[ -n "${sha}" ]]; then
    echo "${sha}"
    return 0
  fi
  sha=$(git ls-tree -d HEAD libs/python/corekinect 2>/dev/null | awk '{print $3}')
  if [[ -n "${sha}" ]]; then
    echo "${sha}"
    return 0
  fi
  # File fallback (e.g., container without parent .git)
  sed -n '4p' "${_git_info_file}" 2>/dev/null || echo "unknown"
}

# Verify the runner image bundled at the registry tag for `<env>` has the
# same corekinect tree SHA baked in as the current workspace HEAD.
# Behavior (see deploy/runner/tests/test_ctl_runner_freshness_gate.py):
#   - SHAs match                  → exit 0, silent
#   - SHAs diverge                → exit 1, name the drift, mention the
#                                   CONCORD_FORCE_STALE_RUNNER bypass
#   - No COREKINECT_GIT_SHA env   → warn (legacy image), exit 0
#   - Image not present locally   → warn (registry-only / other node),
#                                   exit 0
#   - CONCORD_FORCE_STALE_RUNNER  → downgrade fail-on-divergence to a
#     ="1"                          loud warn and exit 0
#
# The gate runs BEFORE `cmd_deploy`. `cmd_deploy` rebuilds the image
# with the current SHA baked in, so the gate's purpose is to catch
# operators who skipped the rebuild (e.g., running `nx update platform`
# against a hand-built runner that hasn't been rebuilt for the current
# corekinect HEAD).
_check_runner_corekinect_freshness() {
  local env="$1"
  local image_ref="${REGISTRY_TEST_RUNNER}:${env}"
  local workspace_sha
  workspace_sha=$(_corekinect_sha)

  # Probe the local image. If it's not present, the freshness check
  # can't run here (the image may live only on the registry / a CI
  # builder). Warn and pass.
  local inspect_json
  if ! inspect_json=$(docker image inspect "${image_ref}" 2>/dev/null); then
    warn "Runner freshness gate: image ${image_ref} not present locally; skipping check."
    info "  (Build the image first with \`nx run test-runner:build -c ${env}\`, or run the gate on the node that built it.)"
    return 0
  fi

  # Extract COREKINECT_GIT_SHA from Config.Env. Use a tolerant parser
  # rather than jq — jq isn't a guaranteed dep on every operator host.
  local baked_sha
  baked_sha=$(echo "${inspect_json}" \
    | tr ',' '\n' \
    | grep -oE '"COREKINECT_GIT_SHA=[^"]*"' \
    | head -1 \
    | sed -E 's/^"COREKINECT_GIT_SHA=//' \
    | sed -E 's/"$//')

  if [[ -z "${baked_sha}" || "${baked_sha}" == "unknown" ]]; then
    warn "Runner freshness gate: no baked COREKINECT_GIT_SHA in ${image_ref}."
    warn "  This is a legacy image (pre-Phase-D). The next rebuild will populate it."
    warn "  Passing through; rebuild and redeploy to enable the gate on the next update."
    return 0
  fi

  if [[ "${baked_sha}" == "${workspace_sha}" ]]; then
    info "  ✓ runner freshness: corekinect SHA ${baked_sha:0:12} matches workspace"
    return 0
  fi

  # SHAs diverged. Either fail or, with the explicit escape hatch, warn loudly.
  if [[ "${CONCORD_FORCE_STALE_RUNNER:-0}" == "1" ]]; then
    warn "═══════════════════════════════════════════════════════════════════"
    warn "  CONCORD_FORCE_STALE_RUNNER=1 — bypassing runner freshness gate"
    warn "  Image ${image_ref} bakes corekinect ${baked_sha:0:12}"
    warn "  Workspace HEAD libs/python/corekinect/ is ${workspace_sha:0:12}"
    warn "  This is an explicit override. The deployed runner WILL run stale"
    warn "  corekinect code against the current platform. You have been warned."
    warn "═══════════════════════════════════════════════════════════════════"
    return 0
  fi

  err "Runner freshness gate: corekinect SHA diverged."
  err "  baked in image ${image_ref}: ${baked_sha}"
  err "  workspace HEAD:                ${workspace_sha}"
  err ""
  err "  The runner image is stale relative to libs/python/corekinect/."
  err "  This is the v0.12.0->0.12.3 skew failure mode — deploying now would"
  err "  leave runner pods executing old corekinect against new test packages."
  err ""
  err "  Rebuild the runner:"
  err "    nx run test-runner:build -c ${env}"
  err "    nx run test-runner:push -c ${env}"
  err ""
  err "  Or, to deploy anyway (e.g., emergency fix), set:"
  err "    CONCORD_FORCE_STALE_RUNNER=1"
  err "  Loud warning will be logged."
  return 1
}

get_version() {
    local version_file="${REPO_ROOT}/VERSION"
    local sha
    sha=$(git rev-parse --short=8 HEAD 2>/dev/null || echo "")
    if [[ -f "$version_file" ]]; then
        local ver
        ver=$(cat "$version_file" | tr -d '[:space:]')
        # If HEAD is an exact tag match, use clean version; otherwise append sha
        local tag
        tag=$(_git_describe)
        if [[ -n "$tag" && "$tag" == "v${ver}" ]]; then
            echo "${ver}"
        elif [[ -n "$sha" ]]; then
            echo "${ver}-${sha}"
        else
            echo "${ver}"
        fi
    else
        echo "0.0.1-${sha:-dev}"
    fi
}

_preflight() {
  # Verify cluster access for staging/production operations
  if ! kubectl cluster-info &>/dev/null; then
    err "Cannot reach Kubernetes cluster"
    err "Check your kubeconfig: kubectl cluster-info"
    exit 1
  fi
  if ! command -v helm &>/dev/null; then
    err "helm not found — install: https://helm.sh/docs/intro/install/"
    exit 1
  fi
}

_prisma_schema_hash() {
  sha256sum prisma/schema.prisma 2>/dev/null | awk '{print $1}'
}

# Run a command; on failure, dump full output and exit. On success, optionally
# grep a filter pattern out of the log for human-readable summary output.
# Using a temp log avoids the `cmd | grep || true` trap that silently swallows
# failures when the command's error output doesn't match the filter pattern.
_run_logged() {
  local filter="$1"
  local label="$2"
  shift 2
  local log
  log=$(mktemp)
  if ! "$@" > "${log}" 2>&1; then
    err "${label} failed:"
    sed 's/^/  /' "${log}" >&2
    rm -f "${log}"
    return 1
  fi
  if [[ -n "${filter}" ]]; then
    grep -E "${filter}" "${log}" 2>/dev/null || true
  fi
  rm -f "${log}"
}

_db_setup() {
  # Prisma generate + push + seed (shared by dev start and dev update)
  local db_url="postgresql://concord:concord@localhost:5433/concord"
  cd prisma
  if [[ "${CI:-false}" == "true" ]]; then
    # CI: stream output, let set -e catch failures
    yarn prisma generate
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      yarn prisma db push --accept-data-loss --skip-generate
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      PYTHONPATH=../libs/python:../libs:../libs/protocols \
      python3 -m seed.main
  else
    # Interactive: filter output on success, show full output on failure
    _run_logged "^✔|Generated" "Prisma generate" \
      yarn prisma generate
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      _run_logged "^🚀|Your database" "Prisma db push" \
      yarn prisma db push --accept-data-loss --skip-generate
    DATABASE_URL="${db_url}" DIRECT_DATABASE_URL="${db_url}" \
      PYTHONPATH=../libs/python:../libs:../libs/protocols \
      _run_logged "^===|Product access:" "Seed" \
      python3 -m seed.main
  fi
  cd ..
}

# ═════════════════════════════════════════════════════════════════
# Build (shared by dev + staging + production)
# ═════════════════════════════════════════════════════════════════

cmd_build() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller" "build-service" "runner" "docs")

  # In CI, stream docker build output instead of suppressing it
  local build_redirect="/dev/null"
  if [[ "${CI:-false}" == "true" ]]; then
    build_redirect="/dev/stdout"
  fi

  local version
  version=$(get_version)

  log "Building  version=${BOLD}${version}${NC}  env=${BOLD}${env}${NC}  targets=${BOLD}${targets[*]}${NC}"

  export APP_VERSION="${version}"
  export PUBLIC_APP_VERSION="${version}"
  export ENVIRONMENT="${env}"
  export PUBLIC_APP_ENVIRONMENT="${env}"
  export GIT_COMMIT="$(_git_commit)"
  export GIT_BRANCH="$(_git_branch)"
  export GIT_DIRTY="$(_git_dirty)"
  export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  export BUILD_HOST="$(hostname)"
  # Phase D Layer 2 — bake the corekinect tree SHA into the runner image.
  # Read by `_check_runner_corekinect_freshness` at deploy time.
  export COREKINECT_GIT_SHA="$(_corekinect_sha)"

  info "  commit=${GIT_COMMIT} branch=${GIT_BRANCH} dirty=${GIT_DIRTY}"

  local pids=()
  local names=()
  local failed=0

  timer_start
  for target in "${targets[@]}"; do
    case "${target}" in
      api|http-api|backend)
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/http-api/deploy/Dockerfile \
          --tag "${REGISTRY_API}:${env}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("API")
        ;;
      frontend|fe|app|ui)
        docker buildx build \
          --build-arg PUBLIC_APP_ENVIRONMENT="${env}" \
          --build-arg PUBLIC_APP_VERSION="${version}" \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/frontend/app/deploy/Dockerfile \
          --tag "${REGISTRY_FRONTEND}:${env}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("Frontend")
        ;;
      git-poller|poller)
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/git-poller/deploy/Dockerfile \
          --tag "${REGISTRY_GIT_POLLER}:${env}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("Git-poller")
        ;;
      runner|test-runner)
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --build-arg COREKINECT_GIT_SHA \
          --file deploy/runner/Dockerfile \
          --tag "${REGISTRY_TEST_RUNNER}:${env}" \
          --tag "${REGISTRY_TEST_RUNNER}:${env}-${GIT_COMMIT}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("Test runner")
        ;;
      build-service)
        docker buildx build \
          --build-arg APP_VERSION --build-arg ENVIRONMENT \
          --build-arg GIT_COMMIT --build-arg GIT_BRANCH --build-arg GIT_DIRTY \
          --build-arg BUILD_TIME --build-arg BUILD_HOST \
          --file apps/backend/build-service/deploy/Dockerfile \
          --tag "${REGISTRY_BUILD_SERVICE}:${env}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("Build-service")
        ;;
      docs)
        docker buildx build \
          --file apps/frontend/docs/deploy/Dockerfile \
          --tag "${REGISTRY_DOCS}:${env}" \
          --load . > "${build_redirect}" 2>&1 &
        pids+=($!); names+=("Docs")
        ;;
      *)
        err "Unknown build target: ${target}"
        err "Valid: api, frontend, git-poller, runner, build-service, docs"
        exit 1
        ;;
    esac
  done

  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      info "  ✓ ${names[$i]}"
    else
      err "  ✗ ${names[$i]} failed"
      failed=1
    fi
  done
  timer_end "Parallel build (${#pids[@]} images)"

  if [[ $failed -ne 0 ]]; then
    err "One or more builds failed"
    exit 1
  fi
  log "Build complete."
}

# ═════════════════════════════════════════════════════════════════
# Push / Helm (staging + production)
# ═════════════════════════════════════════════════════════════════

_push_images() {
  local env="$1"
  shift
  local targets=("$@")

  local pids=()
  local names=()
  local failed=0

  if command -v k3s &>/dev/null; then
    log "Importing images into K3s..."
    timer_start
    for target in "${targets[@]}"; do
      case "${target}" in
        api|http-api|backend)     (docker save "${REGISTRY_API}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("API") ;;
        frontend|fe|app|ui)       (docker save "${REGISTRY_FRONTEND}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("Frontend") ;;
        git-poller|poller)        (docker save "${REGISTRY_GIT_POLLER}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("Git-poller") ;;
        runner|test-runner)       (docker save "${REGISTRY_TEST_RUNNER}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("Test runner") ;;
        build-service)            (docker save "${REGISTRY_BUILD_SERVICE}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("Build-service") ;;
        docs)                     (docker save "${REGISTRY_DOCS}:${env}" | sudo k3s ctr images import -) &>/dev/null & pids+=($!); names+=("Docs") ;;
      esac
    done
    for i in "${!pids[@]}"; do
      if wait "${pids[$i]}"; then
        info "  ✓ ${names[$i]}"
      else
        err "  ✗ ${names[$i]} import failed"
        failed=1
      fi
    done
    timer_end "K3s import (${#pids[@]} images)"
  else
    log "Pushing images to registry..."
    timer_start
    for target in "${targets[@]}"; do
      case "${target}" in
        api|http-api|backend)     docker push "${REGISTRY_API}:${env}" > /dev/null & pids+=($!); names+=("API") ;;
        frontend|fe|app|ui)       docker push "${REGISTRY_FRONTEND}:${env}" > /dev/null & pids+=($!); names+=("Frontend") ;;
        git-poller|poller)        docker push "${REGISTRY_GIT_POLLER}:${env}" > /dev/null & pids+=($!); names+=("Git-poller") ;;
        runner|test-runner)       docker push "${REGISTRY_TEST_RUNNER}:${env}" > /dev/null & pids+=($!); names+=("Test runner") ;;
        build-service)            docker push "${REGISTRY_BUILD_SERVICE}:${env}" > /dev/null & pids+=($!); names+=("Build-service") ;;
        docs)                     docker push "${REGISTRY_DOCS}:${env}" > /dev/null & pids+=($!); names+=("Docs") ;;
      esac
    done
    for i in "${!pids[@]}"; do
      if wait "${pids[$i]}"; then
        info "  ✓ ${names[$i]}"
      else
        err "  ✗ ${names[$i]} push failed"
        failed=1
      fi
    done
    timer_end "Push (${#pids[@]} images)"
  fi

  if [[ $failed -ne 0 ]]; then
    err "One or more image pushes failed"
    exit 1
  fi
}

_cleanup_orphaned_pvcs() {
  # PVCs bound to non-existent PVs cause pods to hang in Pending forever.
  # This happens when PVs are deleted (e.g., finalizer removal) but PVCs survive
  # (helm.sh/resource-policy: keep). Fix: delete orphaned PVCs so Helm recreates them.
  local env="$1"
  local orphaned=0
  for pvc in $(kubectl get pvc -n "${env}" -o jsonpath='{range .items[*]}{.metadata.name}={.spec.volumeName}{"\n"}{end}' 2>/dev/null); do
    local pvc_name="${pvc%%=*}"
    local pv_name="${pvc##*=}"
    if [[ -n "${pv_name}" ]] && ! kubectl get pv "${pv_name}" &>/dev/null; then
      info "  Removing orphaned PVC ${pvc_name} (PV ${pv_name} gone)"
      kubectl delete pvc "${pvc_name}" -n "${env}" --force --grace-period=0 &>/dev/null || true
      orphaned=$((orphaned + 1))
    fi
  done
  # Also clear any PVs stuck in Terminating with dead finalizers
  for pv in $(kubectl get pv -o jsonpath='{range .items[?(@.status.phase=="Terminating")]}{.metadata.name}{"\n"}{end}' 2>/dev/null); do
    kubectl patch pv "${pv}" -p '{"metadata":{"finalizers":null}}' &>/dev/null || true
  done
  # `[[ ]] && info` returns non-zero when the guard is false, which `set -e`
  # treats as a fatal error at function-exit scope on some bash versions —
  # use an explicit if/then so a "nothing was orphaned" path never kills the
  # deploy before helm runs.
  if (( orphaned > 0 )); then
    info "  Cleaned ${orphaned} orphaned PVC(s)"
  fi
}

_helm_deploy() {
  local env="$1"

  # Clean orphaned PVCs before Helm install (prevents Pending pod deadlock)
  _cleanup_orphaned_pvcs "${env}"

  # Clean stale Helm release secrets (prevents "release not found" on upgrade)
  local release_count
  release_count=$(kubectl get secrets -n "${env}" -l "name=concord,owner=helm" --no-headers 2>/dev/null | wc -l)
  if [[ "${release_count}" -gt 5 ]]; then
    kubectl get secrets -n "${env}" -l "name=concord,owner=helm" \
      --sort-by=.metadata.creationTimestamp -o name 2>/dev/null \
      | head -n -5 | xargs kubectl delete -n "${env}" 2>/dev/null || true
  fi

  local helm_args=(
    upgrade --install concord
    "${HELM_DIR}/concord"
    -n "${env}" --create-namespace
    -f "${HELM_DIR}/values-${env}.yaml"
    --set "httpApi.image.tag=${env}"
    --set "frontend.image.tag=${env}"
    --set "gitPoller.image.tag=${env}"
  )

  timer_start
  # Don't use --wait (it blocks on CronJobs/Ingress which don't have Ready state).
  # Rollout verification is handled by _verify_rollout() after this step.
  helm "${helm_args[@]}" --timeout 600s
  timer_end "Helm install"
}

_verify_rollout() {
  local env="$1"
  info "Verifying rollout..."
  # Scope verification to Helm-managed deployments only.
  #
  # The platform namespace also hosts dynamic, application-managed
  # deployments (mtib-server pods, one per fixture slot, created at
  # runtime by http-api against the K8s API). Their readiness depends
  # on whether the corresponding edge hardware is powered on, NOT on
  # whether the Helm release deployed cleanly. Including them in the
  # rollout check used to trip a `helm rollback` whenever a verdin
  # node was off-cluster, even though no platform image had regressed.
  #
  # Helm sets ``app.kubernetes.io/managed-by=Helm`` on every chart
  # template; MTIB deployments use ``corekinect.com/managed-by=concord``.
  # The selector below is the cleanest separator and matches what the
  # chart's standard labels include via ``concord.labels``.
  local deployments
  deployments=$(kubectl get deployments -n "${env}" \
    -l app.kubernetes.io/managed-by=Helm \
    --no-headers -o custom-columns=":metadata.name" 2>/dev/null || true)

  if [[ -z "${deployments}" ]]; then
    warn "No Helm-managed deployments found in namespace ${env}"
    return 1
  fi

  local pids=()
  local names=()
  local failed=0

  timer_start
  for dep in ${deployments}; do
    kubectl rollout status "deployment/${dep}" -n "${env}" --timeout=180s &>/dev/null &
    pids+=($!)
    names+=("${dep}")
  done
  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      info "  ✓ ${names[$i]}"
    else
      err "  ✗ ${names[$i]} not ready"
      failed=1
    fi
  done
  timer_end "Rollout verification (${#pids[@]} deployments)"

  if [[ $failed -ne 0 ]]; then
    err "One or more deployments failed to reach Ready state"
    return 1
  fi
}

_smoke_test() {
  local env="$1"
  info "Running smoke tests..."
  local all_ok=true

  # Get an http-api pod to exec from (it has Python for HTTP checks)
  local api_pod
  api_pod=$(kubectl get pods -n "${env}" -l app.kubernetes.io/name=concord-http-api \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

  if [[ -z "${api_pod}" ]]; then
    warn "  ✗ No running http-api pod found for smoke tests"
    return 1
  fi

  # Smoke test each service endpoint from inside the cluster.
  #
  # Only services the http-api pod is allowed to reach per
  # concord-http-api-restrict's egress list. Frontend + docs listen on
  # port 80 which is NOT in that list, so smoke-ing them from the
  # http-api pod will always hit ``Connection refused`` — not a deploy
  # regression, just a NetworkPolicy boundary. Their readiness probes
  # (kube-probe from the node) already gate the rollout; if those
  # succeed the pods are serving traffic.
  local -A checks=(
    ["http-api|concord-http-api:9001/v2/docs"]="API docs"
  )

  # Endpoints can be momentarily unreachable immediately after rollout
  # (Service DNS propagation, iptables update, pod listen-port warmup).
  # Retry each check up to 5 times with a 4 s gap — still ~20 s worst-case,
  # but enough to mask the known startup race without masking real regressions.
  for key in "${!checks[@]}"; do
    local label="${checks[$key]}"
    local url="http://${key#*|}"
    local svc="${key%%|*}"

    local status=""
    local attempt
    for attempt in 1 2 3 4 5; do
      status=$(kubectl exec -n "${env}" "${api_pod}" -- \
        python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('${url}', timeout=10)
    print(r.status)
except Exception as e:
    print(f'ERR:{e}')
" 2>/dev/null || echo "ERR:exec-failed")

      if [[ "${status}" =~ ^2[0-9][0-9]$ ]]; then
        break
      fi
      if [[ "${attempt}" -lt 5 ]]; then
        sleep 4
      fi
    done

    if [[ "${status}" =~ ^2[0-9][0-9]$ ]]; then
      info "  ✓ ${label} → ${status}"
    else
      warn "  ✗ ${label} → ${status} (after 5 attempts)"
      all_ok=false
    fi
  done

  # Build-service has no K8s Service (it's a worker, not an endpoint).
  # Check that the pod is running and healthy via its liveness probe.
  local bs_ready
  bs_ready=$(kubectl get pods -n "${env}" -l app.kubernetes.io/name=concord-build-service \
    --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
  if [[ "${bs_ready}" -gt 0 ]]; then
    info "  ✓ Build service pod running"
  else
    warn "  ✗ Build service pod not running"
    all_ok=false
  fi

  if $all_ok; then
    info "Smoke tests passed"
    return 0
  else
    warn "Smoke tests FAILED"
    return 1
  fi
}

_rollback_on_failure() {
  local env="$1"
  warn "Rolling back to previous release..."

  local prev_rev
  prev_rev=$(helm history concord -n "${env}" -o json 2>/dev/null \
    | python3 -c "
import sys, json
h = json.load(sys.stdin)
deployed = [r for r in h if r.get('status') == 'deployed']
print(deployed[-1]['revision'] if deployed else '')
" 2>/dev/null || echo "")

  if [[ -z "${prev_rev}" ]]; then
    err "No previous revision to rollback to"
    return 1
  fi

  info "Rolling back to revision ${prev_rev}..."
  helm rollback concord "${prev_rev}" -n "${env}" --wait --timeout 300s

  # Verify rollback — don't fail hard here, rollback itself already succeeded
  if _verify_rollout "${env}"; then
    info "Rollback complete. Investigate and fix before re-deploying."
  else
    warn "Rollback deployed but verification failed. Manual investigation required."
  fi
  return 0
}

# ═════════════════════════════════════════════════════════════════
# Deploy (staging/production) — build + push + helm
# ═════════════════════════════════════════════════════════════════

cmd_deploy() {
  local env="$1"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend" "git-poller" "build-service" "runner" "docs")

  local version
  version=$(get_version)
  local total_start
  total_start=$(date +%s)

  log "Deploying to ${BOLD}${env}${NC}  version=${BOLD}${version}${NC}  targets=${BOLD}${targets[*]}${NC}"
  echo ""

  cmd_build "${env}" "${targets[@]}"
  echo ""

  _push_images "${env}" "${targets[@]}"
  echo ""

  log "Helm upgrade..."
  _helm_deploy "${env}"

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Deployed in ${total_elapsed}s${NC}"
}

# ═════════════════════════════════════════════════════════════════
# Quick deploy (staging/production) — build + push + restart
# ═════════════════════════════════════════════════════════════════

_restart_targets() {
  local env="$1"
  shift
  local targets=("$@")
  local restart_args=""
  for target in "${targets[@]}"; do
    case "${target}" in
      api|http-api|backend)     restart_args="${restart_args} deployment/concord-http-api" ;;
      frontend|fe|app|ui)       restart_args="${restart_args} deployment/concord-frontend" ;;
      git-poller|poller)        restart_args="${restart_args} deployment/concord-git-poller" ;;
      docs)                     restart_args="${restart_args} deployment/concord-docs" ;;
      build-service)            restart_args="${restart_args} deployment/concord-build-service" ;;
    esac
  done

  if [[ -z "${restart_args}" ]]; then
    return 0
  fi

  timer_start
  if ! kubectl rollout restart ${restart_args} -n "${env}"; then
    err "Rollout restart command failed"
    return 1
  fi

  local pids=()
  local names=()
  local failed=0

  for target in "${targets[@]}"; do
    case "${target}" in
      api|http-api|backend)
        kubectl rollout status deployment/concord-http-api -n "${env}" --timeout=90s &>/dev/null &
        pids+=($!); names+=("http-api")
        ;;
      frontend|fe|app|ui)
        kubectl rollout status deployment/concord-frontend -n "${env}" --timeout=30s &>/dev/null &
        pids+=($!); names+=("frontend")
        ;;
      git-poller|poller)
        kubectl rollout status deployment/concord-git-poller -n "${env}" --timeout=30s &>/dev/null &
        pids+=($!); names+=("git-poller")
        ;;
      docs)
        kubectl rollout status deployment/concord-docs -n "${env}" --timeout=30s &>/dev/null &
        pids+=($!); names+=("docs")
        ;;
      build-service)
        kubectl rollout status deployment/concord-build-service -n "${env}" --timeout=90s &>/dev/null &
        pids+=($!); names+=("build-service")
        ;;
    esac
  done

  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      info "  ✓ ${names[$i]}"
    else
      err "  ✗ ${names[$i]} rollout failed"
      failed=1
    fi
  done
  timer_end "Rollout (${#pids[@]} deployments)"

  if [[ $failed -ne 0 ]]; then
    err "One or more rollouts failed"
    return 1
  fi
}

cmd_quick() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend")
  local total_start
  total_start=$(date +%s)
  log "Quick deploy  env=${BOLD}${env}${NC}  targets=${BOLD}${targets[*]}${NC}"
  echo ""
  cmd_build "${env}" "${targets[@]}"
  echo ""
  _push_images "${env}" "${targets[@]}"
  echo ""
  _restart_targets "${env}" "${targets[@]}"
  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Quick deploy done in ${total_elapsed}s${NC}"
}

# ═════════════════════════════════════════════════════════════════
# Status / Logs / Diff
# ═════════════════════════════════════════════════════════════════

cmd_status() {
  local env="${1:-staging}"
  echo ""
  echo -e "${BOLD}=== ${env} Pods ===${NC}"
  kubectl get pods -n "${env}" --no-headers 2>/dev/null | grep -v Terminating || echo "  No pods found"
  echo ""
  echo -e "${BOLD}=== ${env} Services ===${NC}"
  kubectl get svc -n "${env}" 2>/dev/null || echo "  No services found"
}

cmd_logs() {
  local env="${1:-staging}"
  local component="${2:-http-api}"
  kubectl logs -n "${env}" -l "app.kubernetes.io/name=concord-${component}" -f --tail=100 2>/dev/null || \
    kubectl logs -n "${env}" -l "app=concord-${component}" -f --tail=100
}

cmd_restart() {
  local env="${1:-staging}"
  shift || true
  local targets=("$@")
  [[ ${#targets[@]} -eq 0 ]] && targets=("api" "frontend")
  _restart_targets "${env}" "${targets[@]}"
  log "Restart complete."
}

cmd_diff() {
  local env="${1:-staging}"
  local values_file="${HELM_DIR}/values-${env}.yaml"
  [[ ! -f "${values_file}" ]] && { err "No values file for: ${env}"; exit 1; }

  # Check plugin first so we can give a clean message if it's missing,
  # instead of swallowing every helm error behind the generic install hint.
  if ! helm plugin list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "diff"; then
    err "helm-diff plugin not installed"
    err "Install: helm plugin install https://github.com/databus23/helm-diff"
    exit 1
  fi

  helm diff upgrade concord "${HELM_DIR}/concord" -n "${env}" -f "${values_file}"
}

# ═════════════════════════════════════════════════════════════════
# DEVELOPMENT — start / update / stop / status / logs / ready
# ═════════════════════════════════════════════════════════════════

cmd_dev_start() {
  local total_start
  total_start=$(date +%s)
  log "${BOLD}Starting development platform${NC}"

  # Protobuf
  step "Generating protobuf code"
  _run_logged "^(Generating|Processing)" "Protobuf generation" \
    bash libs/protocols/ctl.sh generate
  info "  ✓ protobuf"

  # Build service images (parallel via Nx)
  step "Building service images"
  timer_start
  if [[ "${CI:-false}" == "true" ]]; then
    npx nx run-many -t build -p http-api git-poller build-service -c development --output-style=stream --verbose 2>&1
  else
    npx nx run-many -t build -p http-api git-poller build-service -c development 2>&1 | tail -5
  fi
  timer_end "Image builds"

  # Start infrastructure first
  step "Starting infrastructure"
  $COMPOSE up -d db minio pypi 2>&1 | grep -v "^$"
  info "  ✓ postgres, minio, pypi"

  # Wait for DB
  step "Waiting for postgres"
  until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
  info "  ✓ postgres ready"

  # Database setup
  step "Database setup (generate → push → seed)"
  _db_setup
  info "  ✓ schema pushed, data seeded"

  # Start all services
  step "Starting backend services"
  $COMPOSE up -d 2>&1 | grep -v "^$"

  # Wait for http-api to be healthy (has a healthcheck in compose)
  step "Waiting for services to be healthy"
  local retries=0
  while [[ $retries -lt 30 ]]; do
    local health
    health=$($COMPOSE ps http-api --format '{{.Health}}' 2>/dev/null || echo "unknown")
    if [[ "$health" == "healthy" ]]; then
      break
    fi
    retries=$((retries + 1))
    sleep 2
  done

  if [[ $retries -ge 30 ]]; then
    warn "  http-api did not become healthy within 60s"
    warn "  Check logs: deploy/ctl.sh development logs http-api"
  else
    info "  ✓ http-api healthy"
  fi

  # Verify no containers exited
  local exited
  exited=$($COMPOSE ps --filter "status=exited" --format '{{.Name}}' 2>/dev/null || true)
  if [[ -n "$exited" ]]; then
    warn "  Exited containers: $exited"
    warn "  Check logs: deploy/ctl.sh development logs <service>"
  else
    info "  ✓ all services running"
  fi

  # Summary
  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform running${NC}  (${total_elapsed}s)"
  echo -e "  ${DIM}http-api       ${NC} localhost:9001"
  echo -e "  ${DIM}build-service  ${NC} localhost:9002"
  echo -e "  ${DIM}git-poller     ${NC} running"
  echo -e "  ${DIM}postgres       ${NC} localhost:5433"
  echo -e "  ${DIM}minio          ${NC} localhost:8675 ${DIM}(console: 8676)${NC}"
  echo -e "  ${DIM}pypi           ${NC} localhost:8091"
  echo ""
  echo -e "Start the UI:  ${CYAN}nx serve app${NC}  → localhost:4200"
}

cmd_dev_update() {
  local total_start
  total_start=$(date +%s)
  log "${BOLD}Updating development platform${NC}"

  # Rebuild + restart — Docker layer cache handles unchanged layers automatically.
  # The COPY of source code is near the end of each Dockerfile, so only that
  # layer (and below) rebuilds when code changes. Heavy layers (apt, pip, prisma
  # generate, query engine download) stay cached → sub-second for unchanged services.
  step "Rebuilding containers"
  timer_start
  $COMPOSE build --parallel http-api git-poller build-service 2>&1 | tail -5
  # Test runner is not a compose service — built separately (spawned on-demand by API)
  cmd_build development runner 2>&1 | tail -3
  timer_end "Image builds"

  step "Restarting containers"
  $COMPOSE up -d --force-recreate --no-build 2>&1 | grep -v "^$"

  # Wait for http-api to be healthy
  local retries=0
  while [[ $retries -lt 30 ]]; do
    local health
    health=$($COMPOSE ps http-api --format '{{.Health}}' 2>/dev/null || echo "unknown")
    if [[ "$health" == "healthy" ]]; then break; fi
    retries=$((retries + 1))
    sleep 2
  done
  if [[ $retries -ge 30 ]]; then
    warn "  http-api did not become healthy within 60s"
  else
    info "  ✓ http-api healthy"
  fi

  # Check if schema changed — if so, push + seed
  local local_hash
  local_hash=$(_prisma_schema_hash)
  local cache_file="${REPO_ROOT}/.nx/prisma-schema-hash-dev"
  local cached_hash=""
  [[ -f "${cache_file}" ]] && cached_hash=$(cat "${cache_file}" 2>/dev/null)
  if [[ "${local_hash}" != "${cached_hash}" ]]; then
    step "Prisma schema changed — updating database"
    # Wait for DB to be ready (might have just restarted)
    until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
    _db_setup
    mkdir -p "$(dirname "${cache_file}")"
    echo "${local_hash}" > "${cache_file}"
    info "  ✓ schema pushed, data seeded"
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Update complete${NC}  (${total_elapsed}s)"
}

cmd_dev_stop() {
  log "${BOLD}Stopping development platform${NC}"
  if [[ "${CI:-false}" == "true" ]]; then
    # In CI: remove volumes too — clean slate, no leaks
    $COMPOSE down -v --remove-orphans 2>&1 | grep -v "^$"
  else
    $COMPOSE down 2>&1 | grep -v "^$"
  fi
  log "Platform stopped."
}

cmd_dev_status() {
  $COMPOSE ps
}

cmd_dev_logs() {
  local component="${1:-}"
  if [[ -n "${component}" ]]; then
    $COMPOSE logs -f --tail=50 "${component}"
  else
    $COMPOSE logs -f --tail=50
  fi
}

cmd_dev_ready() {
  # Re-migrate + re-seed without restarting containers
  step "Waiting for postgres"
  until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
  info "  ✓ postgres ready"

  step "Database setup (generate → push → seed)"
  _db_setup
  info "  ✓ schema pushed, data seeded"
}

# ═════════════════════════════════════════════════════════════════
# STAGING / PRODUCTION — start / update / stop
# ═════════════════════════════════════════════════════════════════

cmd_start() {
  local env="$1"
  local total_start
  total_start=$(date +%s)

  log "${BOLD}Starting platform: ${env}${NC}"
  echo ""

  # Preflight
  step "Preflight checks"
  _preflight
  info "  ✓ cluster reachable, helm available"

  # Bootstrap infrastructure (idempotent)
  step "Ensuring infrastructure"
  bash infrastructure/ctl.sh office bootstrap
  echo ""

  # Sync secrets for this namespace
  step "Syncing secrets (${env})"
  bash infrastructure/clusters/office/secrets/create-all.sh "${env}"
  echo ""

  # Build + push + helm deploy
  step "Deploying applications"
  cmd_deploy "${env}"
  echo ""

  # Verify — rollback if any deployment fails to reach Ready
  step "Verifying rollout"
  if ! _verify_rollout "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  # Smoke test — rollback on failure
  step "Smoke testing"
  if ! _smoke_test "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform started: ${env}${NC}  (${total_elapsed}s)"
}

cmd_update() {
  local env="$1"
  shift || true
  local SYNC_SECRETS=false
  for arg in "$@"; do
    case "${arg}" in
      --sync-secrets) SYNC_SECRETS=true ;;
    esac
  done
  local total_start
  total_start=$(date +%s)

  log "${BOLD}Updating platform: ${env}${NC}"
  echo ""

  # Preflight
  step "Preflight checks"
  _preflight
  info "  ✓ cluster reachable, helm available"

  # Sync secrets — skip if already present (run `nx run platform:sync-secrets -c <env>` to force)
  step "Checking secrets (${env})"
  if kubectl get secret concord-secrets -n "${env}" &>/dev/null && \
     kubectl get secret concord-infra-credentials -n "${env}" &>/dev/null && \
     [[ "${SYNC_SECRETS:-false}" != "true" ]]; then
    info "  ✓ secrets present, skipping sync (use --sync-secrets to force)"
  else
    bash infrastructure/clusters/office/secrets/create-all.sh "${env}"
  fi
  echo ""

  # Phase D Layer 2 — runner freshness gate. Refuse the update if the
  # cached runner image bakes a different corekinect SHA than HEAD.
  # cmd_deploy below rebuilds the image, so this gate is for the case
  # where the operator skipped a rebuild on this node (or where the
  # registry tag drifted from the workspace).
  step "Runner freshness check"
  if ! _check_runner_corekinect_freshness "${env}"; then
    exit 1
  fi
  echo ""

  # Build + push + helm deploy
  step "Deploying applications"
  cmd_deploy "${env}"
  echo ""

  # Verify — rollback if any deployment fails to reach Ready
  step "Verifying rollout"
  if ! _verify_rollout "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  # Smoke test — rollback on failure
  step "Smoke testing"
  if ! _smoke_test "${env}"; then
    _rollback_on_failure "${env}"
    exit 1
  fi

  local total_elapsed=$(( $(date +%s) - total_start ))
  echo ""
  log "${BOLD}Platform updated: ${env}${NC}  (${total_elapsed}s)"
}

cmd_stop() {
  local env="$1"

  # Production safety gate — require explicit confirmation
  if [[ "${env}" == "production" ]]; then
    if [[ "${2:-}" != "--confirm-delete" ]]; then
      err "Refusing to stop production without explicit confirmation."
      echo ""
      echo "  Production stop will:"
      echo "    • Remove all application pods (http-api, frontend, etc.)"
      echo "    • PVCs are protected (helm.sh/resource-policy: keep)"
      echo "    • Database and MinIO data survive on disk"
      echo ""
      echo "  If you are sure, run:"
      echo "    ./deploy/ctl.sh production stop --confirm-delete"
      echo ""
      exit 1
    fi
    warn "Production stop confirmed. Proceeding..."
  fi

  log "${BOLD}Stopping platform: ${env}${NC}"

  _preflight

  # Check if release exists
  if helm list -n "${env}" --short 2>/dev/null | grep -q "^concord$"; then
    log "Removing Helm release from ${env}..."
    helm uninstall concord -n "${env}" --wait 2>&1 | sed 's/^/  /'
    log "${BOLD}Platform stopped: ${env}${NC}"
    info "PVCs preserved — data is safe. Run 'nx start platform -c ${env}' to redeploy."
  else
    info "Nothing to stop — no Helm release 'concord' in namespace ${env}"
  fi
}

# ═════════════════════════════════════════════════════════════════
# Help
# ═════════════════════════════════════════════════════════════════

usage() {
  cat <<EOF

${BOLD}Concord Platform CLI${NC}

${BOLD}Usage:${NC}
  ./deploy/ctl.sh <environment> <action> [args...]

${BOLD}Environments:${NC}
  ${GREEN}development${NC}    Docker Compose (local containers)
  ${GREEN}staging${NC}        Kubernetes staging namespace
  ${GREEN}production${NC}     Kubernetes production namespace

${BOLD}Lifecycle:${NC}
  ${GREEN}start${NC}          Full 0→running setup (idempotent, safe to run twice)
  ${GREEN}update${NC}         Rebuild changed images + redeploy (fast, cached)
  ${GREEN}stop${NC}           Teardown app workloads (keeps infrastructure)

${BOLD}Operations:${NC}
  ${GREEN}status${NC}         Show what's running
  ${GREEN}logs [comp]${NC}    Tail component logs
  ${GREEN}deploy${NC}         Build + push + helm upgrade (staging/prod)
  ${GREEN}quick${NC}          Build + push + restart, skip helm (staging/prod)
  ${GREEN}restart${NC}        Rolling restart (staging/prod)
  ${GREEN}ready${NC}          Re-migrate + re-seed DB (development)
  ${GREEN}diff${NC}           Preview Helm changes (staging/prod)

${BOLD}Examples:${NC}
  ./deploy/ctl.sh development start       Full dev startup
  ./deploy/ctl.sh development update      Fast rebuild + restart changed
  ./deploy/ctl.sh development stop        Compose down

  ./deploy/ctl.sh staging start           Bootstrap + build + deploy
  ./deploy/ctl.sh staging update          Rebuild + redeploy (cached)
  ./deploy/ctl.sh staging stop            Helm uninstall
  ./deploy/ctl.sh staging status          Show pods + services

  ./deploy/ctl.sh production start        Full production deploy
  ./deploy/ctl.sh production update       Update production
  ./deploy/ctl.sh production stop         Remove production workloads

${BOLD}Nx shortcuts:${NC}
  nx start platform                       → development start
  nx update platform                      → development update
  nx stop platform                        → development stop
  nx start platform -c staging            → staging start
  nx update platform -c staging           → staging update
  nx run platform:status -c staging       → staging status

EOF
}

# ═════════════════════════════════════════════════════════════════
# Main dispatch
# ═════════════════════════════════════════════════════════════════
#
# Only run when invoked as a script. When `source`d (e.g., from the
# Phase D Layer 2 freshness-gate test harness), the dispatcher MUST NOT
# fire — otherwise sourcing with no args would unconditionally print
# usage and exit. The harness sets CONCORD_CTL_NO_DISPATCH=1 to be
# extra explicit; the BASH_SOURCE check covers the common `source`d
# case automatically.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]] || [[ "${CONCORD_CTL_NO_DISPATCH:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]] || [[ "$1" == "help" ]]; then
  usage
  exit 0
fi

ENV="$1"
shift

# Dispatch by environment
case "${ENV}" in
  development|dev)
    ACTION="${1:-start}"; shift || true
    case "${ACTION}" in
      start)   cmd_dev_start ;;
      update)  cmd_dev_update ;;
      stop)    cmd_dev_stop ;;
      status)  cmd_dev_status ;;
      logs)    cmd_dev_logs "$@" ;;
      ready)   cmd_dev_ready ;;
      *)       err "Unknown development action: ${ACTION}"; usage; exit 1 ;;
    esac
    ;;

  staging|production)
    ACTION="${1:-start}"; shift || true
    case "${ACTION}" in
      start)   cmd_start "${ENV}" ;;
      update)  cmd_update "${ENV}" "$@" ;;
      stop)    cmd_stop "${ENV}" "$@" ;;
      deploy)  cmd_deploy "${ENV}" "$@" ;;
      quick)   cmd_quick "${ENV}" "$@" ;;
      status)  cmd_status "${ENV}" ;;
      logs)    cmd_logs "${ENV}" "$@" ;;
      restart) cmd_restart "${ENV}" "$@" ;;
      diff)    cmd_diff "${ENV}" ;;
      *)       err "Unknown ${ENV} action: ${ACTION}"; usage; exit 1 ;;
    esac
    ;;

  version) get_version ;;

  *)
    err "Unknown environment: ${ENV}"
    usage
    exit 1
    ;;
esac
