#!/usr/bin/env bash
# test-bootstrap.sh — Validates bootstrap.sh exists and supports --dry-run.
# Tests that dry-run mode produces expected kubectl commands without mutating.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); echo "  ✓ $1"; }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); echo "  ✗ $1"; }

# ── Every cluster must have a bootstrap.sh ────────────────────
for cluster_dir in "${INFRA_ROOT}"/clusters/*/; do
  cluster=$(basename "${cluster_dir}")
  echo "--- Cluster: ${cluster} ---"

  bootstrap="${cluster_dir}bootstrap.sh"
  if [[ ! -f "${bootstrap}" ]]; then
    fail "${cluster}: bootstrap.sh not found"
    continue
  fi
  pass "${cluster}: bootstrap.sh exists"

  # Must be executable
  if [[ ! -x "${bootstrap}" ]]; then
    fail "${cluster}: bootstrap.sh is not executable"
  else
    pass "${cluster}: bootstrap.sh is executable"
  fi

  # Must support --dry-run flag
  if ! grep -q '\-\-dry-run' "${bootstrap}"; then
    fail "${cluster}: bootstrap.sh does not support --dry-run flag"
  else
    pass "${cluster}: bootstrap.sh supports --dry-run"
  fi

  # Dry-run must produce output without errors
  dry_output=$(bash "${bootstrap}" --dry-run 2>&1) || {
    fail "${cluster}: bootstrap.sh --dry-run exited with error"
    echo "    Output: ${dry_output}"
    continue
  }

  if [[ -z "${dry_output}" ]]; then
    fail "${cluster}: bootstrap.sh --dry-run produced no output"
  else
    pass "${cluster}: bootstrap.sh --dry-run produced output"
  fi

  # Dry-run output should reference kubectl apply
  if echo "${dry_output}" | grep -q "kubectl apply"; then
    pass "${cluster}: dry-run references kubectl apply"
  else
    fail "${cluster}: dry-run does not reference kubectl apply"
  fi

  # Dry-run should reference helm upgrade (cluster dependencies)
  if echo "${dry_output}" | grep -q "helm upgrade"; then
    pass "${cluster}: dry-run references helm upgrade (dependencies)"
  else
    fail "${cluster}: dry-run does not reference helm upgrade"
  fi

  # teardown.sh must exist
  teardown="${cluster_dir}teardown.sh"
  if [[ -f "${teardown}" ]]; then
    pass "${cluster}: teardown.sh exists"
    if [[ -x "${teardown}" ]]; then
      pass "${cluster}: teardown.sh is executable"
    else
      fail "${cluster}: teardown.sh is not executable"
    fi
    # Must support --dry-run
    if grep -q '\-\-dry-run' "${teardown}"; then
      pass "${cluster}: teardown.sh supports --dry-run"
    else
      fail "${cluster}: teardown.sh does not support --dry-run"
    fi
  else
    fail "${cluster}: teardown.sh not found"
  fi
done

# ── ctl.sh must exist at infrastructure root ──────────────────
echo "--- Infrastructure CLI ---"
ctl="${INFRA_ROOT}/ctl.sh"
if [[ ! -f "${ctl}" ]]; then
  fail "ctl.sh not found at infrastructure root"
else
  pass "ctl.sh exists"
  if [[ ! -x "${ctl}" ]]; then
    fail "ctl.sh is not executable"
  else
    pass "ctl.sh is executable"
  fi

  # Must accept <cluster> <action> args
  help_output=$(bash "${ctl}" --help 2>&1 || true)
  if echo "${help_output}" | grep -q "bootstrap\|status\|validate"; then
    pass "ctl.sh help mentions expected actions"
  else
    fail "ctl.sh help does not mention expected actions (bootstrap, status, validate)"
  fi
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=== bootstrap: ${PASS} passed, ${FAIL} failed ==="
if [[ ${FAIL} -gt 0 ]]; then
  echo "Failures:"
  for e in "${ERRORS[@]}"; do echo "  - ${e}"; done
  exit 1
fi
