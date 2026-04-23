#!/usr/bin/env bash
# Verify the env file registry matches reality.
# Catches: new services that forgot to register their .env.example.
set -euo pipefail
source "$(dirname "$0")/../lib/log.sh"
log_stage "env-check — validating .env.example registry"
bash tools/env/setup.sh development
log_stage_end
