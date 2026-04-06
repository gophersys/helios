#!/usr/bin/env bash
# Run integration + e2e tests against real infrastructure.
# Spins up an isolated test compose stack, migrates, seeds, tests, tears down.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"

COMPOSE_FILE="deploy/development/docker-compose.test.yaml"
PROJECT="concord-test"

cleanup() {
  log_info "Tearing down test stack..."
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" down -v 2>/dev/null || true
}
trap cleanup EXIT

log_stage "test-integration — isolated stack"

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
until docker compose -f "$COMPOSE_FILE" -p "$PROJECT" exec -T test-db pg_isready -U concord 2>/dev/null; do
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
log_info "Waiting for test API..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:9010/v2/docs > /dev/null 2>&1; then
    log_ok "Test API ready"
    break
  fi
  sleep 2
done

# Run integration tests
log_info "Running integration tests..."
PYTHONPATH="apps/backend/http-api/src:apps/backend/http-api:libs/python:libs:libs/protocols" \
  python3 -m pytest tests/integration/ -v --timeout=60 || true

# Run e2e tests
log_info "Running e2e tests..."
PYTHONPATH="apps/backend/http-api/src:libs/python:libs:libs/protocols" \
  python3 -m pytest tests/e2e/ -v --timeout=300 -x || true

log_stage_end
