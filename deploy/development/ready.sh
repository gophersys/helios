#!/usr/bin/env bash
# deploy/development/ready.sh — re-migrate + re-seed without restarting compose.
# Called by: nx run platform:ready
set -euo pipefail

G='\033[0;32m' B='\033[0;34m' R='\033[0m'
step() { echo -e "\n${B}▸${R} $*"; }
ok()   { echo -e "  ${G}✓${R} $*"; }

COMPOSE="docker compose -f deploy/development/docker-compose.yaml"

step "Waiting for postgres"
until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
ok "postgres ready"

step "Database setup (generate → push → seed)"

cd prisma
yarn prisma generate 2>&1 | grep -E "^✔|Generated" || true

DATABASE_URL=postgresql://concord:concord@localhost:5433/concord \
DIRECT_DATABASE_URL=postgresql://concord:concord@localhost:5433/concord \
  yarn prisma db push --accept-data-loss --skip-generate 2>&1 | grep -E "^🚀|Your database" || true

DATABASE_URL=postgresql://concord:concord@localhost:5433/concord \
DIRECT_DATABASE_URL=postgresql://concord:concord@localhost:5433/concord \
PYTHONPATH=../libs/python:../libs:../libs/protocols \
  python3 seed.py 2>&1 | grep -E "^===|Product access:" | head -5 || true
cd ..

ok "schema pushed, data seeded"
