#!/usr/bin/env bash
# .ci/lib/context.sh — detect CI vs local, git state, base branch.

# ── CI detection ─────────────────────────────────────────────────────────────
# Most CI providers set CI=true. We also check provider-specific vars.
export CI=${CI:-false}
export CI_PROVIDER="local"

if [[ "$CI" == "true" ]]; then
  if [[ -n "${BITBUCKET_BUILD_NUMBER:-}" ]]; then
    CI_PROVIDER="bitbucket"
  elif [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    CI_PROVIDER="github"
  elif [[ -n "${TEAMCITY_VERSION:-}" ]]; then
    CI_PROVIDER="teamcity"
  elif [[ -n "${KUBERNETES_SERVICE_HOST:-}" ]]; then
    CI_PROVIDER="kubernetes"
  else
    CI_PROVIDER="unknown"
  fi
fi

export CI_PROVIDER

# ── Git state ────────────────────────────────────────────────────────────────
export GIT_BRANCH
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

export GIT_COMMIT
GIT_COMMIT=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "unknown")

export GIT_DIRTY="false"
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  GIT_DIRTY="true"
fi

# Base branch for `nx affected` (what to diff against).
# In CI, providers typically set this. Locally, default to main.
export NX_BASE
if [[ -n "${BITBUCKET_PR_DESTINATION_BRANCH:-}" ]]; then
  NX_BASE="origin/$BITBUCKET_PR_DESTINATION_BRANCH"
elif [[ -n "${GITHUB_BASE_REF:-}" ]]; then
  NX_BASE="origin/$GITHUB_BASE_REF"
else
  NX_BASE="${NX_BASE:-origin/main}"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
ci_summary() {
  # Note: log.sh must already be sourced by the calling script.
  # Do NOT re-source here — it resets _STAGE_START and breaks log_stage_end timing.
  log_info "provider=$CI_PROVIDER  branch=$GIT_BRANCH  commit=$GIT_COMMIT  dirty=$GIT_DIRTY"
  log_info "nx base=$NX_BASE"
}
