#!/usr/bin/env bash
# Run integration + e2e tests against real infrastructure.
# Spins up an isolated test compose stack, migrates, seeds, tests, tears down.
# Gate: FAILS if any integration or e2e test fails.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

COMPOSE_FILE="deploy/development/docker-compose.test.yaml"
PROJECT="concord-test"
FAILED=false

cleanup() {
  log_info "Tearing down test stack..."
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" down -v 2>/dev/null || true
}
trap cleanup EXIT

log_stage "test-integration — isolated stack (real DB, real services)"

# Build images first
log_info "Building service images..."
npx nx build http-api -c development
npx nx build git-poller -c development
npx nx build build-service -c development

# Start infra
log_info "Starting test infrastructure..."
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" up -d test-db test-minio

# Wait for DB
log_info "Waiting for test postgres..."
for i in $(seq 1 30); do
  if docker compose -f "$COMPOSE_FILE" -p "$PROJECT" exec -T test-db pg_isready -U concord 2>/dev/null; then
    break
  fi
  sleep 1
done

# Migrate + seed against test DB (port 5434)
log_info "Migrating test database..."
cd prisma
DATABASE_URL="postgresql://concord:concord-test@localhost:5434/concord" \
DIRECT_DATABASE_URL="postgresql://concord:concord-test@localhost:5434/concord" \
  yarn prisma migrate deploy
DATABASE_URL="postgresql://concord:concord-test@localhost:5434/concord" \
DIRECT_DATABASE_URL="postgresql://concord:concord-test@localhost:5434/concord" \
PYTHONPATH="../libs/python:../libs:../libs/protocols" \
  python3 -m seed.main
cd ..

# Start all services
log_info "Starting test services..."
docker compose -f "$COMPOSE_FILE" -p "$PROJECT" up -d

# Wait for API
log_info "Waiting for test API (max 90s)..."
for i in $(seq 1 45); do
  if curl -sf http://localhost:9010/v2/docs > /dev/null 2>&1; then
    log_ok "Test API ready"
    break
  fi
  if [[ "$i" -eq 45 ]]; then
    log_error "Test API failed to start within 90s"
    docker compose -f "$COMPOSE_FILE" -p "$PROJECT" logs test-api --tail=50
    exit 1
  fi
  sleep 2
done

# Run integration tests — MUST PASS
log_info "Running integration tests..."
if ! PYTHONPATH="apps/backend/http-api/src:apps/backend/http-api:libs/python:libs:libs/protocols" \
  python3 -m pytest tests/integration/ -v --timeout=60 2>&1; then
  log_error "Integration tests FAILED"
  FAILED=true
fi

# Run e2e tests — MUST PASS
log_info "Running e2e tests..."
if ! PYTHONPATH="apps/backend/http-api/src:libs/python:libs:libs/protocols" \
  python3 -m pytest tests/e2e/ -v --timeout=300 -x 2>&1; then
  log_error "E2E tests FAILED"
  FAILED=true
fi

if $FAILED; then
  log_error "Integration/E2E test gate FAILED"
  # Dump service logs for debugging
  log_info "=== Service logs ==="
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" logs --tail=30
  exit 1
fi

log_stage_end
