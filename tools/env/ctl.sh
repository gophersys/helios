#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# Concord Environment CLI
# ───────────────────────────────────────────────────────────────
# Single entry point for environment setup across all configurations.
#
# Usage:
#   ./tools/env/ctl.sh <environment> <action>
#
# Environments:
#   development   Local dev (Docker Compose)
#   staging       K8s staging namespace
#   production    K8s production namespace
#
# Actions:
#   setup         Create .env files + show secrets guide (idempotent)
#   status        Show what's populated vs missing
#   validate      Registry check (all .env.example files accounted for)
#
# Nx shortcuts:
#   npx nx run env:setup                 → development setup
#   npx nx run env:setup -c staging      → staging setup
#   npx nx run env:status -c production  → production status
# ───────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REGISTRY="${SCRIPT_DIR}/known-env-files.txt"

# ── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()  { echo -e "${GREEN}[env]${NC} $*"; }
warn() { echo -e "${YELLOW}[env]${NC} $*"; }
err()  { echo -e "${RED}[env]${NC} $*" >&2; }
info() { echo -e "${CYAN}[env]${NC} $*"; }

# ── File groups by environment ──────────────────────────────────────────────

# Core: needed for local dev (nx start platform)
CORE_FILES=(
  ".env.example"
  "apps/backend/http-api/.env.example"
  "apps/backend/build-service/.env.example"
  "apps/backend/git-poller/.env.example"
  "deploy/development/.env.example"
  "apps/frontend/app/.env.example"
  "prisma/.env.example"
)

# Test harnesses: needed for hardware testing
TEST_FILES=(
  "apps/validation/alpha/.env.example"
  "apps/manufacturing/alpha/.env.example"
  "apps/edge/mtib-server/.env.example"
)

# Infrastructure: needed for cluster management (ADMIN only)
INFRA_FILES=(
  "infrastructure/clusters/office/secrets/.env.example"
)

# ── Helpers ─────────────────────────────────────────────────────────────────

copy_if_missing() {
  local example="$1"
  local target="${example%.example}"
  local full_example="${REPO_ROOT}/${example}"
  local full_target="${REPO_ROOT}/${target}"

  if [[ ! -f "${full_example}" ]]; then
    warn "  skip (template missing): ${example}"
    return
  fi

  if [[ -f "${full_target}" ]]; then
    echo -e "  ${DIM}exists${NC}  ${target}"
  else
    cp "${full_example}" "${full_target}"
    echo -e "  ${GREEN}created${NC} ${target}"
  fi
}

check_var() {
  local file="$1" var="$2" label="$3" required="${4:-false}"
  local full="${REPO_ROOT}/${file}"

  if [[ ! -f "${full}" ]]; then
    echo -e "  ${RED}✗${NC} ${label} ${DIM}(file missing: ${file})${NC}"
    return
  fi

  local val
  val=$(grep "^${var}=" "${full}" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)

  if [[ -n "${val}" && "${val}" != "you@corekinect.com" && "${val}" != "OVERRIDE-IN-SECRETS-OVERLAY" ]]; then
    echo -e "  ${GREEN}✓${NC} ${label}"
  elif [[ "${required}" == "true" ]]; then
    echo -e "  ${RED}✗${NC} ${label} ${DIM}(empty — required)${NC}"
  else
    echo -e "  ${YELLOW}○${NC} ${label} ${DIM}(empty — optional)${NC}"
  fi
}

check_file_exists() {
  local file="$1" label="$2"
  if [[ -f "${REPO_ROOT}/${file}" ]]; then
    echo -e "  ${GREEN}✓${NC} ${label}"
  else
    echo -e "  ${RED}✗${NC} ${label} ${DIM}(missing)${NC}"
  fi
}

# ── Registry validation ────────────────────────────────────────────────────

cmd_validate() {
  local known found unregistered stale

  known=$(grep -v '^#' "${REGISTRY}" | grep -v '^\s*$' | sort)
  found=$(cd "${REPO_ROOT}" && find . -name ".env.example" \
    -not -path "*/node_modules/*" -not -path "*/.git/*" \
    -not -path "*/.venv/*" -not -path "*/.yarn/*" -not -path "*/.nx/*" \
    | sed 's|^\./||' | sort)

  unregistered=$(comm -23 <(echo "${found}") <(echo "${known}"))
  if [[ -n "${unregistered}" ]]; then
    err "Unregistered .env.example files — add to tools/env/known-env-files.txt:"
    echo "${unregistered}" | while read -r f; do err "  ${f}"; done
    exit 1
  fi

  stale=$(comm -13 <(echo "${found}") <(echo "${known}"))
  if [[ -n "${stale}" ]]; then
    warn "Stale registry entries (file not found):"
    echo "${stale}" | while read -r f; do warn "  ${f}"; done
  fi

  log "Registry valid — $(echo "${known}" | wc -l | tr -d ' ') env files registered."
}

# ── Setup: development ──────────────────────────────────────────────────────

cmd_setup_development() {
  log "${BOLD}Setting up: development${NC}"
  echo ""

  info "Creating .env files from templates (skips existing)..."
  echo ""

  for f in "${CORE_FILES[@]}" "${TEST_FILES[@]}"; do
    copy_if_missing "${f}"
  done

  echo ""
  log "Development .env files ready."
  echo ""

  # Show secrets that need filling
  info "Secrets status for local dev:"
  echo ""
  check_var "deploy/development/.env" "BITBUCKET_SSH_KEY" "Bitbucket SSH key (firmware repo access)"
  check_var "deploy/development/.env" "BITBUCKET_API_TOKEN" "Bitbucket API token (PR integration)"
  check_var "deploy/development/.env" "BITBUCKET_EMAIL" "Bitbucket email" "true"

  echo ""
  info "How to populate:"
  echo -e "  ${CYAN}BITBUCKET_SSH_KEY${NC}    cat ~/.ssh/keys/bitbucket | base64 -w0"
  echo -e "  ${CYAN}BITBUCKET_API_TOKEN${NC}  Bitbucket → Settings → App Passwords → Create"
  echo -e "  ${CYAN}BITBUCKET_EMAIL${NC}      your@corekinect.com"
  echo ""
  echo -e "  ${DIM}All optional for basic dev — leave empty if you don't need firmware builds.${NC}"
  echo ""

  log "Run: ${BOLD}nx start platform${NC}"
}

# ── Setup: staging ──────────────────────────────────────────────────────────

cmd_setup_staging() {
  log "${BOLD}Setting up: staging${NC}"
  echo ""

  # Development files are a prerequisite
  info "Core .env files (for local dev + staging deploys)..."
  echo ""
  for f in "${CORE_FILES[@]}" "${TEST_FILES[@]}"; do
    copy_if_missing "${f}"
  done

  echo ""
  info "Infrastructure secrets..."
  echo ""
  for f in "${INFRA_FILES[@]}"; do
    copy_if_missing "${f}"
  done

  echo ""
  log "Staging .env files ready."
  echo ""

  # Secrets status
  info "Shared secrets:"
  echo ""
  check_file_exists "infrastructure/clusters/office/secrets/shared.env" "shared.env"
  check_var "infrastructure/clusters/office/secrets/shared.env" "BITBUCKET_SSH_KEY_PATH" "SSH key path" "true"
  check_var "infrastructure/clusters/office/secrets/shared.env" "BUILD_SERVICE_API_KEY" "Build service API key" "true"
  check_var "infrastructure/clusters/office/secrets/shared.env" "COREOPS_API_KEY" "CoreOps API key"

  echo ""
  info "Per-environment secrets:"
  echo ""
  check_file_exists "infrastructure/clusters/office/secrets/staging.env" "staging.env"
  check_var "infrastructure/clusters/office/secrets/staging.env" "JWT_SECRET_KEY" "JWT secret key" "true"
  check_var "infrastructure/clusters/office/secrets/staging.env" "DATABASE_URL" "Database URL" "true"

  echo ""
  info "How to populate:"
  echo -e "  ${CYAN}See${NC} infrastructure/clusters/office/secrets/.env.example for full template"
  echo -e "  ${CYAN}Sync${NC} nx run platform:sync-secrets -c staging"
  echo ""

  log "Run: ${BOLD}nx start platform -c staging${NC}"
}

# ── Setup: production ──────────────────────────────────────────────────────

cmd_setup_production() {
  log "${BOLD}Setting up: production${NC}"
  echo ""

  # Same files as staging
  info "Core + infrastructure .env files..."
  echo ""
  for f in "${CORE_FILES[@]}" "${TEST_FILES[@]}" "${INFRA_FILES[@]}"; do
    copy_if_missing "${f}"
  done

  echo ""
  log "Production .env files ready."
  echo ""

  # Secrets status
  info "Shared secrets:"
  echo ""
  check_file_exists "infrastructure/clusters/office/secrets/shared.env" "shared.env"
  check_var "infrastructure/clusters/office/secrets/shared.env" "BITBUCKET_SSH_KEY_PATH" "SSH key path" "true"
  check_var "infrastructure/clusters/office/secrets/shared.env" "BUILD_SERVICE_API_KEY" "Build service API key" "true"
  check_var "infrastructure/clusters/office/secrets/shared.env" "COREOPS_API_KEY" "CoreOps API key"

  echo ""
  info "Per-environment secrets:"
  echo ""
  check_file_exists "infrastructure/clusters/office/secrets/staging.env" "staging.env"
  check_file_exists "infrastructure/clusters/office/secrets/production.env" "production.env"
  check_var "infrastructure/clusters/office/secrets/production.env" "JWT_SECRET_KEY" "Production JWT secret" "true"
  check_var "infrastructure/clusters/office/secrets/production.env" "DATABASE_URL" "Production DB URL" "true"

  echo ""
  info "How to populate:"
  echo -e "  ${CYAN}See${NC} infrastructure/clusters/office/secrets/.env.example for full template"
  echo -e "  ${CYAN}Sync${NC} nx run platform:sync-secrets -c production"
  echo ""

  log "Run: ${BOLD}nx start platform -c production${NC}"
}

# ── Status ──────────────────────────────────────────────────────────────────

cmd_status() {
  local env="$1"

  log "${BOLD}Environment status: ${env}${NC}"
  echo ""

  case "${env}" in
    development)
      info ".env files:"
      for f in "${CORE_FILES[@]}" "${TEST_FILES[@]}"; do
        local target="${f%.example}"
        check_file_exists "${target}" "${target}"
      done

      echo ""
      info "Dev secrets:"
      check_var "deploy/development/.env" "BITBUCKET_SSH_KEY" "Bitbucket SSH key"
      check_var "deploy/development/.env" "BITBUCKET_API_TOKEN" "Bitbucket API token"
      check_var "deploy/development/.env" "BITBUCKET_EMAIL" "Bitbucket email" "true"
      ;;

    staging|production)
      info ".env files:"
      for f in "${CORE_FILES[@]}" "${TEST_FILES[@]}" "${INFRA_FILES[@]}"; do
        local target="${f%.example}"
        check_file_exists "${target}" "${target}"
      done

      echo ""
      info "Shared secrets:"
      check_file_exists "infrastructure/clusters/office/secrets/shared.env" "shared.env"
      check_var "infrastructure/clusters/office/secrets/shared.env" "BITBUCKET_SSH_KEY_PATH" "SSH key path" "true"
      check_var "infrastructure/clusters/office/secrets/shared.env" "BUILD_SERVICE_API_KEY" "Build service API key" "true"

      echo ""
      info "Per-environment secrets:"
      check_file_exists "infrastructure/clusters/office/secrets/${env}.env" "${env}.env"
      check_var "infrastructure/clusters/office/secrets/${env}.env" "JWT_SECRET_KEY" "JWT secret" "true"
      check_var "infrastructure/clusters/office/secrets/${env}.env" "DATABASE_URL" "Database URL" "true"
      ;;
  esac
  echo ""
}

# ── Help ────────────────────────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Concord Environment CLI${NC}

${BOLD}Usage:${NC}
  ./tools/env/ctl.sh <environment> <action>

${BOLD}Environments:${NC}
  ${GREEN}development${NC}   Local dev stack (Docker Compose)
  ${GREEN}staging${NC}       K8s staging namespace
  ${GREEN}production${NC}    K8s production namespace

${BOLD}Actions:${NC}
  ${GREEN}setup${NC}         Create .env files + show secrets guide (idempotent)
  ${GREEN}status${NC}        Show what's populated vs missing
  ${GREEN}validate${NC}      Check all .env.example files are registered

${BOLD}Nx shortcuts:${NC}
  npx nx run env:setup                  → development setup
  npx nx run env:setup -c staging       → staging setup
  npx nx run env:setup -c production    → production setup
  npx nx run env:status                 → development status
  npx nx run env:status -c staging      → staging status

EOF
}

# ── Main ────────────────────────────────────────────────────────────────────

if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  usage
  exit 0
fi

# Special case: validate doesn't need an environment
if [[ "$1" == "validate" ]]; then
  cmd_validate
  exit 0
fi

ENV="${1:-development}"
ACTION="${2:-setup}"

# Always validate registry first
cmd_validate
echo ""

case "${ACTION}" in
  setup)
    case "${ENV}" in
      development|dev) cmd_setup_development ;;
      staging)         cmd_setup_staging ;;
      production)      cmd_setup_production ;;
      *) err "Unknown environment: ${ENV}"; usage; exit 1 ;;
    esac
    ;;
  status)
    case "${ENV}" in
      development|dev) cmd_status "development" ;;
      staging)         cmd_status "staging" ;;
      production)      cmd_status "production" ;;
      *) err "Unknown environment: ${ENV}"; usage; exit 1 ;;
    esac
    ;;
  *)
    err "Unknown action: ${ACTION}"
    usage
    exit 1
    ;;
esac
