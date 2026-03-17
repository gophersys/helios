#!/bin/bash
# Quick deploy — builds only what changed, uses layer caching.
# Usage:
#   ./deploy/quick.sh                    # Build + deploy all changed
#   ./deploy/quick.sh frontend           # Frontend only
#   ./deploy/quick.sh api                # API only
#   ./deploy/quick.sh validation         # Validation only
#   ./deploy/quick.sh api frontend       # Multiple targets

set -e

REGISTRY="containers.ad.corekinect.com"
BUST=$(date +%s)

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${GREEN}[quick]${NC} $*"; }
timer_start() { TIMER_START=$(date +%s%N); }
timer_end() {
  local elapsed=$(( ($(date +%s%N) - TIMER_START) / 1000000 ))
  echo -e "${CYAN}[quick]${NC} ${1}: ${BOLD}${elapsed}ms${NC}"
}

# Parse targets (default: all)
TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=("frontend" "api" "validation")
fi

TOTAL_START=$(date +%s)

for target in "${TARGETS[@]}"; do
  case "$target" in
    frontend|fe|app)
      log "Building frontend..."
      timer_start
      docker buildx build \
        --build-arg PUBLIC_APP_ENVIRONMENT=staging \
        --build-arg PUBLIC_APP_VERSION=0.0.1-dev \
        --build-arg CACHE_BUST=$BUST \
        --file apps/frontend/app/deploy/Dockerfile \
        --tag $REGISTRY/concord-frontend:staging \
        --load . > /dev/null 2>&1
      timer_end "Frontend build"

      timer_start
      docker push $REGISTRY/concord-frontend:staging > /dev/null 2>&1
      timer_end "Frontend push"
      ;;

    api|http-api|backend)
      log "Building API..."
      timer_start
      docker buildx build \
        --build-arg CACHE_BUST=$BUST \
        --file apps/backend/http-api/deploy/Dockerfile \
        --tag $REGISTRY/concord-http-api:staging \
        --load . > /dev/null 2>&1
      timer_end "API build"

      timer_start
      docker push $REGISTRY/concord-http-api:staging > /dev/null 2>&1
      timer_end "API push"
      ;;

    validation|val)
      log "Building validation..."
      timer_start
      docker buildx build \
        --build-arg CACHE_BUST=$BUST \
        --file apps/validation/alpha/deploy/Dockerfile \
        --tag $REGISTRY/concord-validation-alpha:staging \
        --load . > /dev/null 2>&1
      timer_end "Validation build"

      timer_start
      docker push $REGISTRY/concord-validation-alpha:staging > /dev/null 2>&1
      timer_end "Validation push"
      ;;

    *)
      echo -e "${RED}Unknown target: $target${NC}"
      echo "Valid: frontend, api, validation"
      exit 1
      ;;
  esac
done

# Restart only the deployments we built
RESTART_ARGS=""
for target in "${TARGETS[@]}"; do
  case "$target" in
    frontend|fe|app) RESTART_ARGS="$RESTART_ARGS deployment/concord-frontend" ;;
    api|http-api|backend) RESTART_ARGS="$RESTART_ARGS deployment/concord-http-api" ;;
  esac
done

if [ -n "$RESTART_ARGS" ]; then
  log "Restarting:$RESTART_ARGS"
  timer_start
  kubectl rollout restart $RESTART_ARGS -n staging > /dev/null 2>&1

  for target in "${TARGETS[@]}"; do
    case "$target" in
      frontend|fe|app)
        kubectl rollout status deployment/concord-frontend -n staging --timeout=30s > /dev/null 2>&1 ;;
      api|http-api|backend)
        kubectl rollout status deployment/concord-http-api -n staging --timeout=90s > /dev/null 2>&1 ;;
    esac
  done
  timer_end "Rollout"
fi

TOTAL_ELAPSED=$(( $(date +%s) - TOTAL_START ))
echo ""
log "${BOLD}Done in ${TOTAL_ELAPSED}s${NC}"
