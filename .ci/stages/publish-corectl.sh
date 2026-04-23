#!/usr/bin/env bash
# Publish the corectl wheel to the internal PyPI for the target environment.
#
# Runs after the main pipeline's deploy step on a push to ``main``. Uses
# ``--skip-existing`` so a re-run on the same version is a no-op instead
# of an error (the wheel version comes from ``corectl.__version__`` and
# only changes on a deliberate bump).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

CONFIG="${1:-staging}"

log_stage "publish-corectl — $CONFIG"

if [[ "$CI" != "true" ]]; then
  log_warn "Skipping publish-corectl — not in CI. Run with CI=true to force."
  log_stage_end
  exit 0
fi

npx nx run corectl:publish-wheel -c "$CONFIG"

log_stage_end
