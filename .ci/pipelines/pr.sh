#!/usr/bin/env bash
# Pipeline: Pull Request
# Runs on every PR. Must pass before merge.
# Catches errors as early as possible — cheapest checks first.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

bash "$DIR/stages/env-check.sh"       # 1. contract: no unregistered env files
bash "$DIR/stages/lint.sh"            # 2. style: dead imports, formatting
bash "$DIR/stages/typecheck.sh"       # 3. types: broken interfaces, missing deps
bash "$DIR/stages/test.sh"            # 4. logic: regressions, broken behavior
bash "$DIR/stages/build.sh" staging   # 5. build: Dockerfile errors (don't push)
