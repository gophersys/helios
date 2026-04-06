#!/usr/bin/env bash
# deploy/development/start.sh — full platform startup for local dev.
# Called by: nx start platform -c development
set -euo pipefail

G='\033[0;32m' B='\033[0;34m' D='\033[2m' R='\033[0m'
step() { echo -e "\n${B}▸${R} $*"; }
ok()   { echo -e "  ${G}✓${R} $*"; }

COMPOSE="docker compose -f deploy/development/docker-compose.yaml"

# ── Protobuf ────────────────────────────────────────────────────────────────
step "Generating protobuf code"
bash libs/protocols/ctl.sh generate 2>&1 | grep -E "^(Generating|Processing)" || true
ok "protobuf"

# ── Docker images ───────────────────────────────────────────────────────────
step "Building service images"
nx build http-api -c development 2>&1 | tail -1
nx build git-poller -c development 2>&1 | tail -1
nx build build-service -c development 2>&1 | tail -1
ok "http-api, git-poller, build-service"

# ── Infrastructure ──────────────────────────────────────────────────────────
step "Starting infrastructure"
$COMPOSE up -d db minio pypi 2>&1 | grep -v "^$"
ok "postgres, minio, pypi"

# ── Wait for DB ─────────────────────────────────────────────────────────────
step "Waiting for postgres"
until $COMPOSE exec -T db pg_isready -U concord 2>/dev/null; do sleep 1; done
ok "postgres ready"

# ── Database ────────────────────────────────────────────────────────────────
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

# ── Backend services ────────────────────────────────────────────────────────
step "Starting backend services"
$COMPOSE up -d 2>&1 | grep -v "^$"
ok "all services up"

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${G}Platform running${R}"
echo -e "  ${D}http-api       ${R} localhost:9001"
echo -e "  ${D}build-service  ${R} localhost:9002"
echo -e "  ${D}git-poller     ${R} running"
echo -e "  ${D}postgres       ${R} localhost:5433"
echo -e "  ${D}minio          ${R} localhost:8675 ${D}(console: 8676)${R}"
echo -e "  ${D}pypi           ${R} localhost:8091"
echo ""
echo -e "Start the UI:  ${B}nx serve app${R}  → localhost:4200"
