#!/usr/bin/env bash
# tools/env/setup.sh — populate .env files from .env.example templates.
#
# Usage: bash tools/env/setup.sh <configuration>
#   development  — copy all .env.example → .env (skip existing)
#   staging      — validate helm values for staging
#   production   — validate helm values for production
#
# Fails if any .env.example exists in the repo that isn't registered
# in tools/env/known-env-files.txt. This enforces the env contract.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGISTRY="$REPO_ROOT/tools/env/known-env-files.txt"
CONFIG="${1:-development}"

# ── Helpers ──────────────────────────────────────────────────────────────────

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Registry validation ─────────────────────────────────────────────────────
# Every .env.example in the repo MUST appear in known-env-files.txt.
# This catches new services that forgot to register their env config.

validate_registry() {
  bold "Validating env file registry..."

  # Load known paths (strip comments and blanks)
  local known
  known=$(grep -v '^#' "$REGISTRY" | grep -v '^\s*$' | sort)

  # Find all .env.example in repo (exclude node_modules, .git, .venv, .yarn)
  local found
  found=$(cd "$REPO_ROOT" && find . -name ".env.example" \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/.venv/*" \
    -not -path "*/.yarn/*" \
    -not -path "*/.nx/*" \
    | sed 's|^\./||' | sort)

  # Diff: find unregistered .env.example files
  local unregistered
  unregistered=$(comm -23 <(echo "$found") <(echo "$known"))

  if [[ -n "$unregistered" ]]; then
    red "ERROR: Unregistered .env.example files found!"
    red "Add these to tools/env/known-env-files.txt:"
    echo "$unregistered" | while read -r f; do
      red "  $f"
    done
    exit 1
  fi

  # Check for stale entries (registered but file doesn't exist)
  local stale
  stale=$(comm -13 <(echo "$found") <(echo "$known"))

  if [[ -n "$stale" ]]; then
    yellow "WARNING: Stale entries in known-env-files.txt (file not found):"
    echo "$stale" | while read -r f; do
      yellow "  $f"
    done
  fi

  green "Registry valid — $(echo "$known" | wc -l | tr -d ' ') env files registered."
}

# ── Development setup ────────────────────────────────────────────────────────
# Copy every .env.example → .env. Skip if .env already exists.

setup_development() {
  bold "Setting up development environment..."

  local known copied=0 skipped=0
  known=$(grep -v '^#' "$REGISTRY" | grep -v '^\s*$')

  while IFS= read -r example_path; do
    local env_path="${example_path%.example}"
    local full_example="$REPO_ROOT/$example_path"
    local full_env="$REPO_ROOT/$env_path"

    if [[ ! -f "$full_example" ]]; then
      yellow "  skip (missing): $example_path"
      continue
    fi

    if [[ -f "$full_env" ]]; then
      skipped=$((skipped + 1))
      echo "  exists: $env_path"
      continue
    fi

    cp "$full_example" "$full_env"
    copied=$((copied + 1))
    green "  created: $env_path"
  done <<< "$known"

  echo ""
  bold "Done — $copied created, $skipped existing (untouched)."

  if [[ $copied -gt 0 ]]; then
    yellow "Review the new .env files and fill in secrets before running services."
  else
    green "All .env files already in place."
  fi
}

# ── Staging/Production validation ────────────────────────────────────────────
# Verify helm values have all required config/secret keys.

setup_deployed() {
  local env="$1"
  bold "Validating $env environment..."

  local values_file="$REPO_ROOT/deploy/production/helm/values-${env}.yaml"
  local secrets_file="$REPO_ROOT/deploy/production/helm/values-${env}-secrets.yaml"

  if [[ ! -f "$values_file" ]]; then
    red "ERROR: $values_file not found"
    exit 1
  fi

  green "  values: $values_file exists"

  if [[ -f "$secrets_file" ]]; then
    green "  secrets: $secrets_file exists"
  else
    yellow "  secrets: $secrets_file not found (using defaults from values)"
  fi

  # Check for placeholder values that should have been overridden
  local placeholders
  placeholders=$(grep -c "CHANGE-ME" "$values_file" 2>/dev/null || true)
  if [[ "$placeholders" -gt 0 ]]; then
    if [[ ! -f "$secrets_file" ]]; then
      red "ERROR: $values_file has $placeholders CHANGE-ME placeholders and no secrets overlay"
      exit 1
    fi
    yellow "  $placeholders CHANGE-ME placeholders (should be overridden by secrets overlay)"
  fi

  green "  $env environment looks good."
}

# ── Main ─────────────────────────────────────────────────────────────────────

validate_registry

case "$CONFIG" in
  development)
    setup_development
    ;;
  staging)
    setup_deployed "staging"
    ;;
  production)
    setup_deployed "production"
    ;;
  *)
    red "Unknown configuration: $CONFIG"
    echo "Usage: $0 [development|staging|production]"
    exit 1
    ;;
esac
