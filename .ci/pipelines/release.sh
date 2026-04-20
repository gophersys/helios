#!/usr/bin/env bash
# Pipeline: Release to Production
# Triggered manually or by tag push. Promotes staging to production.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$DIR/lib/log.sh"
source "$DIR/lib/context.sh"

# Pre-flight: staging must be healthy before we touch production
log_stage "pre-flight — verify staging is healthy"
bash "$DIR/stages/smoke.sh" staging
log_stage_end

# Build + push production images
bash "$DIR/stages/build.sh" production
bash "$DIR/stages/push.sh" production

# Deploy to production
bash "$DIR/stages/deploy.sh" production

# Publish the corectl wheel to production's internal PyPI. Mirrors the
# staging pipeline — keeps the two environments in sync so upgrade
# behaviour is identical.
bash "$DIR/stages/publish-corectl.sh" production

# Verify production
bash "$DIR/stages/smoke.sh" production

# Tag the release
if [[ "$CI" == "true" ]]; then
  log_stage "tag — creating release tag"
  VERSION=$(date -u +%Y.%m.%d)-${GIT_COMMIT}
  git tag -a "v${VERSION}" -m "Release ${VERSION}"
  git push origin "v${VERSION}"
  log_ok "tagged v${VERSION}"
  log_stage_end
fi
