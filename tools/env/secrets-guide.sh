#!/usr/bin/env bash
# tools/env/secrets-guide.sh — interactive guide for populating secrets.
#
# Usage:
#   bash tools/env/secrets-guide.sh              All secrets
#   bash tools/env/secrets-guide.sh development   Dev secrets only
#   bash tools/env/secrets-guide.sh staging        Staging/prod secrets
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[0;36m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

check_populated() {
  local file="$1" var="$2"
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  local val
  val=$(grep "^${var}=" "$file" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
  if [[ -n "$val" && "$val" != "you@corekinect.com" ]]; then
    return 0
  fi
  return 1
}

status_icon() {
  if check_populated "$1" "$2"; then
    printf '\033[0;32m✓\033[0m'
  else
    printf '\033[0;31m✗\033[0m'
  fi
}

SCOPE="${1:-all}"

echo ""
bold "╔══════════════════════════════════════════════╗"
bold "║  Concord Secrets Guide                       ║"
bold "╚══════════════════════════════════════════════╝"
echo ""

DEV_ENV="$REPO_ROOT/deploy/development/.env"
INFRA_ENV="$REPO_ROOT/infrastructure/clusters/office/secrets/.env"
STAGING_SECRETS="$REPO_ROOT/deploy/production/helm/values-staging-secrets.yaml"
PROD_SECRETS="$REPO_ROOT/deploy/production/helm/values-production-secrets.yaml"

# ─── Development Secrets ──────────────────────────────────────────────────

if [[ "$SCOPE" == "all" || "$SCOPE" == "development" ]]; then
  bold "═══ Development Secrets ═══"
  cyan "File: deploy/development/.env"
  echo ""

  echo "$(status_icon "$DEV_ENV" "BITBUCKET_SSH_KEY")  BITBUCKET_SSH_KEY"
  echo "   What: Base64-encoded SSH private key for Bitbucket"
  echo "   Who needs it: Anyone working with firmware repos (builds, git-poller)"
  echo "   How to get it:"
  cyan "     cat ~/.ssh/keys/bitbucket | base64 -w0"
  echo "   Where: deploy/development/.env → BITBUCKET_SSH_KEY=<paste>"
  echo "   Optional: Leave empty if you don't need firmware builds locally"
  echo ""

  echo "$(status_icon "$DEV_ENV" "BITBUCKET_API_TOKEN")  BITBUCKET_API_TOKEN"
  echo "   What: Bitbucket REST API app password"
  echo "   Who needs it: ADMIN/MAINTAINER (PR status, webhook management)"
  echo "   How to get it:"
  cyan "     Bitbucket → Personal Settings → App Passwords → Create"
  echo "     Permissions: Repositories (read), Pull requests (read/write)"
  echo "   Where: deploy/development/.env → BITBUCKET_API_TOKEN=<paste>"
  echo "   Optional: Leave empty if you don't need PR integration"
  echo ""

  echo "$(status_icon "$DEV_ENV" "BITBUCKET_EMAIL")  BITBUCKET_EMAIL"
  echo "   What: Your email for Bitbucket HTTP Basic auth"
  echo "   Where: deploy/development/.env → BITBUCKET_EMAIL=your@corekinect.com"
  echo ""

  echo "  SIGNING KEYS (all optional for dev)"
  echo "   BENCH_SIGNING_KEY, ENGINEERING_SIGNING_KEY, PRODUCTION_SIGNING_KEY"
  echo "   What: Base64-encoded PEM keys for firmware signing"
  echo "   How to get it: Ask ADMIN — these are shared team secrets"
  echo "   Leave empty to use dev defaults from seed data"
  echo ""
fi

# ─── Infrastructure Secrets (ADMIN only) ──────────────────────────────────

if [[ "$SCOPE" == "all" || "$SCOPE" == "staging" || "$SCOPE" == "infrastructure" ]]; then
  bold "═══ Infrastructure Secrets (ADMIN only) ═══"
  cyan "File: infrastructure/clusters/office/secrets/.env"
  echo ""

  echo "$(status_icon "$INFRA_ENV" "BITBUCKET_SSH_KEY_PATH")  BITBUCKET_SSH_KEY_PATH"
  echo "   What: File path to SSH private key (not base64 — the actual file)"
  echo "   Default: /root/.ssh/keys/bitbucket"
  echo "   This path must exist on the machine running 'create-all.sh'"
  echo ""

  echo "$(status_icon "$INFRA_ENV" "BUILD_SERVICE_API_KEY")  BUILD_SERVICE_API_KEY"
  echo "   What: API key for build-service → http-api authentication"
  echo "   Default: ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG (seed key)"
  echo "   For production: create a dedicated key via /v2/api-keys"
  echo ""

  echo "$(status_icon "$INFRA_ENV" "CORECLOUD_VALIDATION_API_KEY")  CORECLOUD_VALIDATION_API_KEY"
  echo "   What: CoreCloud FUOTA/device management API key"
  echo "   How to get it: CoreCloud admin panel or ask Jared"
  echo "   Optional: Only needed if running FUOTA validation"
  echo ""

  echo "  MCUBOOT_APP_KEY_PATH / MCUBOOT_COMMS_KEY_PATH"
  echo "   What: File paths to MCUboot encryption PEM keys"
  echo "   How to get it: Ask firmware team for the key files"
  echo "   Optional: Only needed for firmware signing/FUOTA"
  echo ""
fi

# ─── Helm Secrets (ADMIN only) ──────────────────────────────────────────

if [[ "$SCOPE" == "all" || "$SCOPE" == "staging" ]]; then
  bold "═══ Helm Secrets (Staging + Production) ═══"
  cyan "Files:"
  cyan "  deploy/production/helm/values-staging-secrets.yaml"
  cyan "  deploy/production/helm/values-production-secrets.yaml"
  echo ""

  echo "  These files are pre-populated with current values."
  echo "  If setting up from scratch, here's how to generate each:"
  echo ""

  echo "  JWT_SECRET_KEY"
  echo "   Generate a unique one per environment:"
  cyan "     openssl rand -hex 32"
  echo "   MUST be different between staging and production"
  echo ""

  echo "  DATABASE_URL / DIRECT_DATABASE_URL"
  echo "   Format: postgresql://<user>:<password>@concord-postgres:5432/concord"
  echo "   The password must match infrastructure.postgres.password in the same file"
  echo ""

  echo "  STORAGE_ACCESS_KEY / STORAGE_SECRET_ACCESS_KEY"
  echo "   Must match infrastructure.minio.rootUser/rootPassword in the same file"
  echo ""

  echo "  AUTH_SERVER_API_KEY"
  echo "   CoreCloud auth API key — get from CoreCloud admin panel"
  echo "   Same key works for both staging and production"
  echo ""

  echo "  DELETE_ALL_KEY"
  echo "   A random string that protects destructive API endpoints"
  cyan "     openssl rand -hex 16"
  echo ""

  echo "  BITBUCKET_WEBHOOK_SECRET"
  echo "   Set in Bitbucket repo webhook config → must match"
  cyan "     openssl rand -hex 20"
  echo ""
fi

# ─── Summary ─────────────────────────────────────────────────────────────

echo ""
bold "═══ Quick Status ═══"
echo ""

printf "  %-50s %s\n" "deploy/development/.env" "$(
  [[ -f "$DEV_ENV" ]] && green "exists" || red "missing"
)"
printf "  %-50s %s\n" "infrastructure/.../secrets/.env" "$(
  [[ -f "$INFRA_ENV" ]] && green "exists" || red "missing"
)"
printf "  %-50s %s\n" "values-staging-secrets.yaml" "$(
  [[ -f "$STAGING_SECRETS" ]] && green "exists" || red "missing"
)"
printf "  %-50s %s\n" "values-production-secrets.yaml" "$(
  [[ -f "$PROD_SECRETS" ]] && green "exists" || red "missing"
)"
echo ""
