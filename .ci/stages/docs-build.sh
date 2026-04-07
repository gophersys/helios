#!/usr/bin/env bash
# Documentation build validation.
# Gate: fails if mkdocs build produces errors (broken links, missing pages).
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"

log_stage "docs-build — validate documentation site"

if ! npx nx run docs:build 2>&1; then
  log_error "Documentation build failed — check for broken links or missing pages"
  exit 1
fi

log_stage_end
