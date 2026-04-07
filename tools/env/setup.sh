#!/usr/bin/env bash
# tools/env/setup.sh — environment setup walkthrough for Concord.
#
# Usage:
#   bash tools/env/setup.sh                    Interactive walkthrough (asks role)
#   bash tools/env/setup.sh --role DEVELOPER   Non-interactive with role
#   bash tools/env/setup.sh --validate         Registry validation only
#   bash tools/env/setup.sh --check <env>      Check staging/production readiness
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGISTRY="$REPO_ROOT/tools/env/known-env-files.txt"

# ── Colors ──────────────────────────────────────────────────────────────────

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
cyan()   { printf '\033[0;36m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Role definitions ────────────────────────────────────────────────────────
#
# Each role defines which .env files the developer needs.
# "core" = needed for `nx start platform` (local dev)
# "test" = needed for running validation/manufacturing tests
# "infra" = needed for cluster management (staging/production)

CORE_ENV_FILES=(
  "deploy/development/.env.example"
  "apps/frontend/app/.env.example"
  "prisma/.env.example"
)

TEST_ENV_FILES=(
  "apps/validation/alpha/.env.example"
  "apps/manufacturing/alpha/.env.example"
  "apps/edge/mtib-server/.env.example"
)

INFRA_ENV_FILES=(
  "infrastructure/clusters/office/secrets/.env.example"
)

# Files that are ALWAYS created (repo-level + per-service defaults)
AUTO_ENV_FILES=(
  ".env.example"
  "apps/backend/http-api/.env.example"
  "apps/backend/build-service/.env.example"
  "apps/backend/git-poller/.env.example"
)

# ── Registry validation ────────────────────────────────────────────────────

validate_registry() {
  local known found unregistered stale

  known=$(grep -v '^#' "$REGISTRY" | grep -v '^\s*$' | sort)

  found=$(cd "$REPO_ROOT" && find . -name ".env.example" \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/.venv/*" \
    -not -path "*/.yarn/*" \
    -not -path "*/.nx/*" \
    | sed 's|^\./||' | sort)

  unregistered=$(comm -23 <(echo "$found") <(echo "$known"))
  if [[ -n "$unregistered" ]]; then
    red "ERROR: Unregistered .env.example files found!"
    red "Add these to tools/env/known-env-files.txt:"
    echo "$unregistered" | while read -r f; do red "  $f"; done
    exit 1
  fi

  stale=$(comm -13 <(echo "$found") <(echo "$known"))
  if [[ -n "$stale" ]]; then
    yellow "WARNING: Stale entries in known-env-files.txt:"
    echo "$stale" | while read -r f; do yellow "  $f"; done
  fi

  green "Registry valid — $(echo "$known" | wc -l | tr -d ' ') env files registered."
}

# ── File creation ──────────────────────────────────────────────────────────

copy_env_file() {
  local example_path="$1"
  local env_path="${example_path%.example}"
  local full_example="$REPO_ROOT/$example_path"
  local full_env="$REPO_ROOT/$env_path"

  if [[ ! -f "$full_example" ]]; then
    yellow "  skip (missing): $example_path"
    return 1
  fi

  if [[ -f "$full_env" ]]; then
    echo "  exists: $env_path"
    return 0
  fi

  cp "$full_example" "$full_env"
  green "  created: $env_path"
  return 0
}

# ── Staging/Production check ───────────────────────────────────────────────

check_deployed() {
  local env="$1"
  bold "Checking $env environment..."

  local values_file="$REPO_ROOT/deploy/production/helm/values-${env}.yaml"
  local secrets_file="$REPO_ROOT/deploy/production/helm/values-${env}-secrets.yaml"
  local errors=0

  if [[ ! -f "$values_file" ]]; then
    red "  FAIL: $values_file not found"
    errors=$((errors + 1))
  else
    green "  values: $(basename "$values_file")"
  fi

  if [[ -f "$secrets_file" ]]; then
    green "  secrets: $(basename "$secrets_file")"
  else
    red "  FAIL: $(basename "${secrets_file}") not found"
    echo "    Create it with real secrets — see deploy/production/helm/ for the template"
    errors=$((errors + 1))
  fi

  # Check for placeholder values
  local placeholders
  placeholders=$(grep -c "OVERRIDE-IN-SECRETS-OVERLAY" "$values_file" 2>/dev/null || true)
  if [[ "$placeholders" -gt 0 ]] && [[ ! -f "$secrets_file" ]]; then
    red "  FAIL: $placeholders placeholder values with no secrets overlay"
    errors=$((errors + 1))
  elif [[ "$placeholders" -gt 0 ]]; then
    green "  $placeholders secrets overridden by overlay"
  fi

  if [[ $errors -eq 0 ]]; then
    green "  $env environment ready."
  else
    red "  $env has $errors issue(s)."
    return 1
  fi
}

# ── Interactive walkthrough ────────────────────────────────────────────────

walkthrough() {
  local role="${1:-}"

  echo ""
  bold "╔══════════════════════════════════════════════╗"
  bold "║  Concord Environment Setup                  ║"
  bold "╚══════════════════════════════════════════════╝"
  echo ""

  # Ask role if not provided
  if [[ -z "$role" ]]; then
    bold "What's your role?"
    echo ""
    echo "  1) ADMIN       — Full access. You manage infrastructure, secrets, and deployments."
    echo "  2) MAINTAINER  — Product owner. Full staging access, read-only production."
    echo "  3) DEVELOPER   — Build and test. Full staging, no production."
    echo "  4) OPERATOR    — Manufacturing only. Read-only staging."
    echo ""
    read -rp "  Enter role (1-4 or name): " role_input

    case "$role_input" in
      1|ADMIN|admin)       role="ADMIN" ;;
      2|MAINTAINER|maintainer) role="MAINTAINER" ;;
      3|DEVELOPER|developer)   role="DEVELOPER" ;;
      4|OPERATOR|operator)     role="OPERATOR" ;;
      *) red "Invalid role: $role_input"; exit 1 ;;
    esac
  fi

  role="${role^^}"
  echo ""
  bold "Setting up for role: $role"
  echo ""

  # ── Step 1: Core dev files (everyone except OPERATOR) ──
  local created=0 skipped=0

  if [[ "$role" != "OPERATOR" ]]; then
    bold "Step 1: Core development files"
    cyan "  These are needed for 'nx start platform' (local dev stack)"
    echo ""

    for f in "${AUTO_ENV_FILES[@]}" "${CORE_ENV_FILES[@]}"; do
      if copy_env_file "$f"; then
        if [[ -f "$REPO_ROOT/${f%.example}" ]]; then
          skipped=$((skipped + 1))
        else
          created=$((created + 1))
        fi
      fi
    done
    echo ""
  fi

  # ── Step 2: Test harness files (ADMIN, MAINTAINER, DEVELOPER) ──
  if [[ "$role" == "ADMIN" || "$role" == "MAINTAINER" || "$role" == "DEVELOPER" ]]; then
    bold "Step 2: Test harness files"
    cyan "  Needed for running validation/manufacturing tests against hardware"
    echo ""

    for f in "${TEST_ENV_FILES[@]}"; do
      copy_env_file "$f"
    done
    echo ""
  fi

  # ── Step 3: Infrastructure files (ADMIN only) ──
  if [[ "$role" == "ADMIN" ]]; then
    bold "Step 3: Infrastructure secrets"
    cyan "  Needed for cluster management (K8s secrets, Helm deploys)"
    echo ""

    for f in "${INFRA_ENV_FILES[@]}"; do
      copy_env_file "$f"
    done
    echo ""

    # Check Helm secrets overlays
    bold "Step 4: Helm secrets overlays"

    local staging_secrets="$REPO_ROOT/deploy/production/helm/values-staging-secrets.yaml"
    local prod_secrets="$REPO_ROOT/deploy/production/helm/values-production-secrets.yaml"

    if [[ -f "$staging_secrets" ]]; then
      green "  exists: values-staging-secrets.yaml"
    else
      yellow "  missing: values-staging-secrets.yaml"
      echo "    Create from the staging values file — move real secrets there"
    fi

    if [[ -f "$prod_secrets" ]]; then
      green "  exists: values-production-secrets.yaml"
    else
      yellow "  missing: values-production-secrets.yaml"
      echo "    Create from the production values file — move real secrets there"
    fi
    echo ""
  fi

  # ── Step N: Kubeconfig ──
  if [[ "$role" != "OPERATOR" ]]; then
    bold "Kubeconfig"
    local kc_dir="$REPO_ROOT/infrastructure/clusters/office/kubeconfigs/generated"
    if [[ -d "$kc_dir" ]] && ls "$kc_dir"/*.kubeconfig >/dev/null 2>&1; then
      green "  Kubeconfigs found in infrastructure/clusters/office/kubeconfigs/generated/"
      cyan "  Ask your ADMIN for your kubeconfig file, then:"
      echo "    export KUBECONFIG=\$HOME/.kube/concord.kubeconfig"
    else
      if [[ "$role" == "ADMIN" ]]; then
        cyan "  Generate kubeconfigs for your team:"
        echo "    ./infrastructure/ctl.sh office kubeconfig batch"
      else
        cyan "  Ask your ADMIN to run:"
        echo "    ./infrastructure/ctl.sh office kubeconfig create --user your@email.com --role $role"
      fi
    fi
    echo ""
  fi

  # ── Summary ──
  bold "═══════════════════════════════════════════════"
  echo ""

  case "$role" in
    ADMIN)
      bold "Next steps:"
      echo "  1. Review and fill in secrets in the .env files created above"
      echo "  2. Start the dev stack:  nx start platform"
      echo "  3. Start the frontend:   npx nx serve app"
      echo ""
      echo "  For staging/production:"
      echo "  4. Populate infrastructure/clusters/office/secrets/.env"
      echo "  5. Populate deploy/production/helm/values-*-secrets.yaml"
      echo "  6. Bootstrap cluster:    ./infrastructure/ctl.sh office bootstrap"
      echo "  7. Deploy staging:       nx start platform -c staging"
      ;;
    MAINTAINER)
      bold "Next steps:"
      echo "  1. Review and fill in secrets in the .env files created above"
      echo "  2. Get your kubeconfig from an ADMIN"
      echo "  3. Start the dev stack:  nx start platform"
      echo "  4. Start the frontend:   npx nx serve app"
      echo ""
      echo "  You have full access to staging, read-only production."
      ;;
    DEVELOPER)
      bold "Next steps:"
      echo "  1. Start the dev stack:  nx start platform"
      echo "  2. Start the frontend:   npx nx serve app"
      echo "  3. Run tests:            npx nx test http-api"
      echo ""
      echo "  You have full access to staging, read-only production."
      echo "  No secrets to fill in — dev defaults work out of the box."
      ;;
    OPERATOR)
      bold "Next steps:"
      echo "  1. Get your kubeconfig from an ADMIN"
      echo "  2. You have read-only staging access for manufacturing operations"
      echo "  3. Use the Concord UI at https://staging.concord.local"
      ;;
  esac

  echo ""
  green "Setup complete."
}

# ── Main ────────────────────────────────────────────────────────────────────

ROLE=""
ACTION="walkthrough"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --role)     ROLE="$2"; shift 2 ;;
    --validate) ACTION="validate"; shift ;;
    --check)    ACTION="check"; shift; CHECK_ENV="${1:-staging}"; shift || true ;;
    -h|--help|help)
      echo "Usage: $0 [--role ADMIN|MAINTAINER|DEVELOPER|OPERATOR] [--validate] [--check staging|production]"
      exit 0
      ;;
    *) ROLE="$1"; shift ;;
  esac
done

validate_registry

case "$ACTION" in
  walkthrough)  walkthrough "$ROLE" ;;
  validate)     ;; # registry validation already ran above
  check)        check_deployed "$CHECK_ENV" ;;
esac
